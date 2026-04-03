# Map prediction microservice

A part of our thesis project.

## Setup

1. Set up a venv. Python3 is needed.
   ```bash
   python3 -m venv venv
   ```
   To later use the venv:
   ```bash
   source venv/bin/activate
   ```
   To later deactivate the venv:
   ```bash
   deactivate
   ```
   Alternatively, use the ./venv/bin/python3 and ./venv/bin/pip directly or skip the venv and use system-wide Python.
2. Install dependencies.
   ```bash
   pip install -r requirements.txt
   ```
3. [**CURRENTLY UNUSED**] Create a .env file and add the required fields (See code or .env.example).
4. Run the app.
   ```bash
   python3 app.py
   ```

## Current endpoints

- /predict (GET). Takes a location and time. Returns a GeoJSON FeatureCollection with point features.

  Example:

  ```bash
  $> curl -X GET "http://localhost:5000/predict?bbox=13.0,52.0,13.1,52.1&time=2025-03-29T14:30:00"
   {
   "features": [
      {
         "geometry": {
         "coordinates": [
            13.0,
            52.0
         ],
         "type": "Point"
         },
         "properties": {
         "prediction": 48.368875311888374,
         "time": "2025-03-29T14:30:00"
         },
         "type": "Feature"
      },
      {
         "geometry": {
         "coordinates": [
            13.1,
            52.0
         ],
         "type": "Point"
         },
         "properties": {
         "prediction": 47.88643550729249,
         "time": "2025-03-29T14:30:00"
         },
         "type": "Feature"
      },
      ...
   ],
   "type": "FeatureCollection"
   }
  ```

## TODO

- Add Eureka integration.
- Make it use a proper, production-usable server.
- Prepare to docker it for deployment.
- Make actual predictions.
- Add unit testing?
- Add better error handling, logging.
