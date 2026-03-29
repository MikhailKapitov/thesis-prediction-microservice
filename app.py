import os
import math
import json
from datetime import datetime
from flask import Flask, request, jsonify

app = Flask(__name__)

# Returns the predicted noise value for a certain location and time.
# time is a datetime object (or string; here we'll pass the parsed datetime)
def get_noise_prediction(lat, lon, time_obj):
    # Dummy formula: just to return something interesting for testing.
    # Uses the hour component of the datetime for the dummy calculation.
    # TODO: OBV. REPLACE THIS.
    hour = time_obj.hour
    return (math.sin(lat * 0.1) + math.cos(lon * 0.1) + (hour % 24) / 24.0) * 50 + 50


# Generates points within a bounding box.
# bbox: [min_lon, min_lat, max_lon, max_lat]
# step_degrees: spacing in degrees
# Returns a list of (lon, lat) tuples.
def generate_grid(bbox, step_degrees=0.01):
    min_lon, min_lat, max_lon, max_lat = bbox
    points = []
    lat = min_lat
    while lat <= max_lat:
        lon = min_lon
        while lon <= max_lon:
            points.append((lon, lat))
            lon += step_degrees
        lat += step_degrees
    return points


# Returns the prediction.
# Expects query parameters:
#    bbox: min_lon,min_lat,max_lon,max_lat (e.g., "13.0,52.0,13.1,52.1")
#    time: ISO format datetime string (e.g., "2025-03-29T14:30:00")
#    step: optional, grid spacing in degrees (default 0.01)
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

    step = float(request.args.get('step', '0.01'))

    # Generate grid points
    points = generate_grid([min_lon, min_lat, max_lon, max_lat], step)

    # Build GeoJSON FeatureCollection
    features = []
    for lon, lat in points:
        pred = get_noise_prediction(lat, lon, time_obj)
        features.append({
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat]
            },
            "properties": {
                "prediction": pred,
                "time": time_str
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
