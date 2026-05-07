import os
import math
import json
from datetime import datetime
from flask import Flask, request, jsonify


SAMPLE_POINTS_LAT = 5
SAMPLE_POINTS_LON = 5

app = Flask(__name__)

# Returns the predicted noise value for a certain location, time and noise category.
# time is a datetime object (or string; here we'll pass the parsed datetime)
def get_noise_prediction(lat, lon, time_obj, noise_class):
    # Dummy formula: just to return something interesting for testing.
    # Uses the hour component of the datetime for the dummy calculation.
    # TODO: OBV. REPLACE THIS.
    hour = time_obj.hour

    # Time and space ([0; 50]).
    geographic = (math.sin(lat * 0.5) + math.cos(lon * 0.5) + 2) / 4  # 0-1 range
    time_factor = (hour % 24) / 24.0  # 0-1 range
    base_value = (geographic * 0.7 + time_factor * 0.3) * 50  # 0-50

    # Class-specific multipliers ([0.5; 1.5]).
    class_multipliers = {
        "all": 1.0,
        "alert": 1.5,
        "building_noise": 1.2,
        "human": 0.9,
        "others": 0.5,
        "transport": 1.4
    }
    multiplier = class_multipliers.get(noise_class, 1.0)

    # 1.33 multiplier and [0; 100] clamp.
    return min(100, max(0, base_value * multiplier * 1.33))


# Generates points within a bounding box.
# bbox: [min_lon, min_lat, max_lon, max_lat]
# Returns a list of (lon, lat) tuples.
def generate_grid(bbox):
    min_lon, min_lat, max_lon, max_lat = bbox
    points = []
    lat = min_lat
    for lat_part in range(SAMPLE_POINTS_LAT):
        for lon_part in range(SAMPLE_POINTS_LON):
            lat = lat_part / (SAMPLE_POINTS_LAT - 1) * (max_lat - min_lat) + min_lat
            lon = lon_part / (SAMPLE_POINTS_LON - 1) * (max_lon - min_lon) + min_lon
            points.append((lon, lat))
    return points


# Returns the prediction.
# Expects query parameters:
#    bbox: min_lon,min_lat,max_lon,max_lat (e.g., "13.0,52.0,13.1,52.1")
#    time: ISO format datetime string (e.g., "2025-03-29T14:30:00")
# Returns GeoJSON FeatureCollection with point features.
@app.route('/predict', methods=['GET'])
def predict():
    # Parse parameters
    bbox_str = request.args.get('bbox')
    if not bbox_str:
        return jsonify({'error': 'Missing "bbox" parameter'}), 400

    try:
        min_lon, min_lat, max_lon, max_lat = map(float, bbox_str.split(','))
    except ValueError:
        return jsonify({'error': 'Invalid bbox format. Use "min_lon,min_lat,max_lon,max_lat"'}), 400

    time_str = request.args.get('time')
    if not time_str:
        return jsonify({'error': 'Missing "time" parameter'}), 400

    try:
        time_obj = datetime.fromisoformat(time_str)
    except ValueError:
        return jsonify({'error': 'Invalid time format. Use ISO format like "2025-03-29T14:30:00"'}), 400

    noise_class = request.args.get('noise_class', 'all')
    if noise_class not in ['all', 'alert', 'building_noise', 'human', 'transport', 'others']:
        return jsonify({'error': f'Invalid noise_class. Use one of: all, alert, building_noise, human, others, transport'}), 400

    # Generate grid points
    points = generate_grid([min_lon, min_lat, max_lon, max_lat])

    # Build GeoJSON FeatureCollection
    features = []
    for lon, lat in points:
        pred = get_noise_prediction(lat, lon, time_obj, noise_class)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "prediction": pred,
                "time": time_str,
                "noise_class": noise_class
            }
        })

    geojson = {
        "type": "FeatureCollection",
        "features": features
    }

    return jsonify(geojson)


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
