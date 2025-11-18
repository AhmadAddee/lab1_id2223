import os
import datetime as dt
import matplotlib.pyplot as plt
import json
from xgboost import XGBRegressor
import pandas as pd
from air_quality_backfill_cardiff import get_hopsworks_project, get_sensor_metadata


def load_model_and_features(project):
    mr = project.get_model_registry()

    model_obj = mr.get_model(name="air_quality_xgboost_model", version=None)  # None = latest
    local_dir = model_obj.download()
    print(f"📦 Downloaded model artifacts to: {local_dir}")
    model_path = os.path.join(local_dir, "model.json")
    feature_cols_path = os.path.join(local_dir, "feature_columns.json")
    model = XGBRegressor()
    model.load_model(model_path)
    with open("air_quality_model_locally/feature_columns.json", "r") as f:
        feature_columns = json.load(f)
    return model, feature_columns


def get_forecast_features(fs, feature_columns):
    fg_weather = fs.get_feature_group(name="weather", version=1)
    # df_weather = fg_weather.read()
    # df_weather["date"] = pd.to_datetime(df_weather["date"], utc=True)
    # today = pd.Timestamp(dt.date.today(), tz="UTC")
    # df_future = df_weather[df_weather["date"] >= today].copy()
    # df_future = df_future.sort_values("date")
    today = dt.datetime.now() - dt.timedelta(0)
    df_future = fg_weather.filter(fg_weather.date >= today).read()
    if df_future.empty:
        raise ValueError("No future weather rows found in 'weather' Feature Group.")
    print(f"Forecast weather rows: {df_future[['date']].head()}")
    x_future = df_future[feature_columns].copy()
    return df_future, x_future


def get_hindcast_features(fs, feature_columns, days_back=14):
    fg_weather = fs.get_feature_group(name="weather", version=1)
    fg_aq = fs.get_feature_group(name="air_quality", version=1)

    df_weather = fg_weather.read()
    df_aq = fg_aq.read()

    df_weather["date"] = pd.to_datetime(df_weather["date"], utc=True)
    df_aq["date"] = pd.to_datetime(df_aq["date"], utc=True)
    join_cols = ["city", "date"]
    df_join = pd.merge(
        df_weather,
        df_aq[join_cols + ["pm25"]],
        on=join_cols,
        how="inner",
        suffixes=("_weather", "_aq"),
    )
    if not df_join.empty:
        max_date = df_join["date"].max()
        cutoff = max_date - pd.Timedelta(days=days_back)
        df_join = df_join[df_join["date"] >= cutoff]
    df_join = df_join.sort_values("date")
    if df_join.empty:
        raise ValueError("No overlapping weather/air_quality rows for hindcast.")
    print(f"Hindcast rows (last {days_back} days): {len(df_join)}")
    x_hist = df_join[feature_columns].copy()
    y_hist = df_join["pm25"].copy()
    return df_join, x_hist, y_hist


def run_prediction(model, x):
    y_pred = model.predict(x)
    return y_pred


def plot_forecast(df_future, y_pred_future, output_path="cardiff_forecast.png"):
    plt.figure(figsize=(10, 5))
    plt.plot(df_future["date"], y_pred_future, marker="o")
    plt.xlabel("Date")
    plt.ylabel("Predicted PM2.5")
    plt.title("Predicted PM2.5 - Forecast (Cardiff Newport Road)")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print("📊 Saved forecast to plot to:", output_path)


def plot_hindcast(df_hist, y_pred_hist, output_path="cardiff_hindcast.png"):
    plt.figure(figsize=(10, 5))
    plt.plot(df_hist["date"], df_hist["pm25"], marker="o", label="Actual PM2.5")
    plt.plot(df_hist["date"], y_pred_hist, marker="x", linestyle="--", label="Predicted PM2.5")
    plt.xlabel("Date")
    plt.ylabel("PM2.5")
    plt.title("Hindcast: Actual vs. Predicted PM2.5 (Cardiff Newport Road)")
    plt.legend()
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()
    print("📊 Saved hindcast plot to:", output_path)


def main():
    project = get_hopsworks_project()
    fs = project.get_feature_store()
    model, feature_columns = load_model_and_features(project)
    df_future, x_future = get_forecast_features(fs, feature_columns)
    y_pred_future = run_prediction(model, x_future)

    result_dir = "air_quality_training"
    if not os.path.exists(result_dir):
        os.mkdir(result_dir)

    plot_forecast(df_future, y_pred_future, output_path=result_dir + "/cardiff_forecast.png")

    df_hist, x_hist, y_hist = get_hindcast_features(fs, feature_columns)
    y_pred_hist = run_prediction(model, x_hist)
    plot_hindcast(df_hist, y_pred_hist, output_path=result_dir + "/cardiff_hindcast.png")

    df_future_out = df_future.copy()
    df_future_out["predicted_pm25"] = y_pred_future
    df_future_out.to_csv(result_dir + "/cardiff_forecast_prediction.csv", index=False)

    df_hist_out = df_hist.copy()
    df_hist_out["predicted_pm25"] = y_pred_hist
    df_hist_out.to_csv(result_dir + "/cardiff_hindcast_predictions.csv", index=False)


if __name__ == "__main__":
    main()
