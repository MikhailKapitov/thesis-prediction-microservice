from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import joblib
import numpy as np
import pandas as pd
from flask import Flask, jsonify, request


BASE_DIR = Path(__file__).resolve().parent
ARTIFACTS_DIR = BASE_DIR / "artifacts"
LEVEL_MODEL_PATH = ARTIFACTS_DIR / "noise_level_regressor.joblib"
SOURCE_MODEL_PATH = ARTIFACTS_DIR / "noise_source_classifier.joblib"
LEVEL_METADATA_PATH = ARTIFACTS_DIR / "noise_level_regressor_metadata.json"
SOURCE_METADATA_PATH = ARTIFACTS_DIR / "noise_source_classifier_metadata.json"

ALMATY_TZ = ZoneInfo("Asia/Almaty")
SAMPLE_POINTS_LAT = int(os.environ.get("SAMPLE_POINTS_LAT", "20"))
SAMPLE_POINTS_LON = int(os.environ.get("SAMPLE_POINTS_LON", "20"))

DAY_NAME_TO_NUM = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

app = Flask(__name__)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def require_file(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"Required model artifact was not found: {path}")


require_file(LEVEL_MODEL_PATH)
require_file(SOURCE_MODEL_PATH)
require_file(LEVEL_METADATA_PATH)
require_file(SOURCE_METADATA_PATH)

noise_level_model = joblib.load(LEVEL_MODEL_PATH)
noise_source_model = joblib.load(SOURCE_MODEL_PATH)
noise_level_metadata = load_json(LEVEL_METADATA_PATH)
noise_source_metadata = load_json(SOURCE_METADATA_PATH)

FEATURE_COLUMNS = noise_level_metadata["feature_columns"]
if FEATURE_COLUMNS != noise_source_metadata["feature_columns"]:
    raise RuntimeError("Classifier and regressor feature columns do not match.")


def period_from_hour(hour: int) -> str:
    if 6 <= hour <= 10:
        return "morning"
    if 11 <= hour <= 16:
        return "daytime"
    if 17 <= hour <= 20:
        return "evening"
    if 21 <= hour <= 23:
        return "late_evening"
    return "night"


def parse_day_of_week(day_value: str | None) -> int | None:
    if day_value is None or day_value == "":
        return None

    normalized = day_value.strip().lower()
    if normalized in DAY_NAME_TO_NUM:
        return DAY_NAME_TO_NUM[normalized]

    try:
        day_number = int(normalized)
    except ValueError as exc:
        raise ValueError("Invalid day_of_week. Use Monday-Sunday or 0-6.") from exc

    if not 0 <= day_number <= 6:
        raise ValueError("Invalid day_of_week. Use Monday-Sunday or 0-6.")
    return day_number


def parse_prediction_datetime(time_value: str | None) -> datetime:
    if not time_value:
        return datetime.now(ALMATY_TZ)

    normalized = time_value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError('Invalid time format. Use ISO format like "2026-05-31T14:30:00".') from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=ALMATY_TZ)
    return parsed.astimezone(ALMATY_TZ)


def build_feature_row(lat: float, lon: float, dt: datetime, day_override: int | None = None) -> dict:
    day_of_week_num = dt.weekday() if day_override is None else day_override
    hour = dt.hour

    return {
        "latitude": lat,
        "longitude": lon,
        "month": dt.month,
        "hour": hour,
        "day_of_week_num": day_of_week_num,
        "is_weekend": int(day_of_week_num >= 5),
        "hour_sin": float(np.sin(2 * np.pi * hour / 24)),
        "hour_cos": float(np.cos(2 * np.pi * hour / 24)),
        "dow_sin": float(np.sin(2 * np.pi * day_of_week_num / 7)),
        "dow_cos": float(np.cos(2 * np.pi * day_of_week_num / 7)),
        "period": period_from_hour(hour),
    }


def predict_noise(lat: float, lon: float, dt: datetime, day_override: int | None = None) -> dict:
    row = build_feature_row(lat, lon, dt, day_override)
    features = pd.DataFrame([row], columns=FEATURE_COLUMNS)

    noise_level = float(noise_level_model.predict(features)[0])
    noise_class = str(noise_source_model.predict(features)[0])

    return {
        "noise_level_dba": round(noise_level, 2),
        "noise_class": noise_class,
    }


def generate_grid(bbox: list[float]) -> list[tuple[float, float]]:
    min_lon, min_lat, max_lon, max_lat = bbox
    points = []

    for lat_part in range(SAMPLE_POINTS_LAT):
        for lon_part in range(SAMPLE_POINTS_LON):
            lat = lat_part / (SAMPLE_POINTS_LAT - 1) * (max_lat - min_lat) + min_lat
            lon = lon_part / (SAMPLE_POINTS_LON - 1) * (max_lon - min_lon) + min_lon
            points.append((lon, lat))

    return points


def parse_float_arg(name: str) -> float:
    value = request.args.get(name)
    if value is None or value == "":
        raise ValueError(f'Missing "{name}" parameter.')
    try:
        return float(value)
    except ValueError as exc:
        raise ValueError(f'Invalid "{name}" parameter. Use a number.') from exc


def prediction_context() -> tuple[datetime, int | None, str]:
    dt = parse_prediction_datetime(request.args.get("time"))
    day_override = parse_day_of_week(request.args.get("day_of_week"))
    effective_day_num = dt.weekday() if day_override is None else day_override
    effective_day_name = next(name.title() for name, number in DAY_NAME_TO_NUM.items() if number == effective_day_num)
    return dt, day_override, effective_day_name


@app.route("/predict", methods=["GET"])
def predict():
    try:
        dt, day_override, effective_day_name = prediction_context()
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    bbox_str = request.args.get("bbox")
    if bbox_str:
        try:
            bbox = list(map(float, bbox_str.split(",")))
        except ValueError:
            return jsonify({"error": 'Invalid bbox format. Use "min_lon,min_lat,max_lon,max_lat".'}), 400

        if len(bbox) != 4:
            return jsonify({"error": 'Invalid bbox format. Use "min_lon,min_lat,max_lon,max_lat".'}), 400

        min_lon, min_lat, max_lon, max_lat = bbox
        if min_lon > max_lon or min_lat > max_lat:
            return jsonify({"error": "Invalid bbox bounds."}), 400

        features = []
        for lon, lat in generate_grid(bbox):
            prediction = predict_noise(lat, lon, dt, day_override)
            features.append(
                {
                    "type": "Feature",
                    "geometry": {
                        "type": "Point",
                        "coordinates": [lon, lat],
                    },
                    "properties": {
                        **prediction,
                        "time": dt.isoformat(),
                        "day_of_week": effective_day_name,
                    },
                }
            )

        return jsonify({"type": "FeatureCollection", "features": features})

    try:
        lat = parse_float_arg("lat")
        lon = parse_float_arg("lon")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    prediction = predict_noise(lat, lon, dt, day_override)
    return jsonify(
        {
            **prediction,
            "latitude": lat,
            "longitude": lon,
            "time": dt.isoformat(),
            "day_of_week": effective_day_name,
        }
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify(
        {
            "status": "ok",
            "models": {
                "noise_level_regressor": LEVEL_MODEL_PATH.name,
                "noise_source_classifier": SOURCE_MODEL_PATH.name,
            },
            "classes": noise_source_metadata.get("classes", []),
            "feature_columns": FEATURE_COLUMNS,
            "metrics": {
                "noise_level_regressor": noise_level_metadata.get("metrics", {}),
                "noise_source_classifier": noise_source_metadata.get("metrics", {}),
            },
        }
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
