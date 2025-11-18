




1. Backfill feature pipeline
   - Load historical air quality CSV from [aqicn.org](https://aqicn.org) and register it as Feature Group in Hopsworks.
   Done in [air_quality_backfill_cardiff.py](air_quality_backfill_cardiff.py)
   - Download historical weather data (> 1 year ideally), and register it as Feature Group in Hopsworks.
   Done in [weather_backfill_cardiff.py](weather_backfill_cardiff.py)
2. Schedule a daily feature pipeline notebook - done in [daily_feature_pipeline_cardiff.py](daily_feature_pipeline_cardiff.py):
   - Download yesterday's weather + air quality
   - Also weather predictions for next 7-10 days
   - Update Feature Groups in Hopsworks
   - Use GitHub Actions or Modal
3. Training pipeline - done in [training_pipeline_cardiff.py](training_pipeline_cardiff.py):
   - Select features into a Feature View
   - Read training data from FV
   - Train regression/classifier model to predict pm25
   - Register model in Hopsworks
4. Batch inference pipeline - done in [batch_inference_cardiff.py](batch_inference_cardiff.py):
   - Download model form Hopsworks
   - Plot dashboard predicting air quality next 7-10 days
5. Monitor accuracy - (also in [batch_inference_cardiff.py](batch_inference_cardiff.py))
   - Plot hindcast graph: predictions vs outcomes (measured air quality)
6. (Optional, C) Update model by adding lagged PM2.5 features (1, 2, 3 days) and analyze performance change.
7. (Optional, A) Provide predictions for all air quality sensors in that city

Deliverables
- GitHub rep with source code
- `README.md` describing the lab
- **Public URL** for the dashboard
