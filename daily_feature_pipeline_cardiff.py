import os
import datetime as dt
import pandas as pd
import requests
from dotenv import load_dotenv
from air_quality_backfill_cardiff import get_hopsworks_project, get_sensor_metadata


def get_config():
    load_dotenv()

    country, city, street, aqicn_url = get_sensor_metadata()
    aqicn_key = os.getenv("AQICN_API_KEY")

    lat = float(os.getenv("WEATHER_LAT"))
    lon = float(os.getenv("WEATHER_LON"))
    return {
        "country": country,
        "city": city,
        "street": street,
        "aqicn_url": aqicn_url,
        "aqicn_key": aqicn_key,
        "latitude": lat,
        "longitude": lon,
    }


def fetch_latest_air_quality(cfg) -> pd.DataFrame:
    api_key = cfg.pop("aqicn_key") #["aqicn_key"]
    url = f"{cfg['aqicn_url']}/?token={api_key}"

    resp = requests.get(url)
    data = resp.json()
    if data.get("status") != "ok":
        raise ValueError(f"AQICN API error: {data.get('status')}")

    print("Requested AQICN, status:", data.get("status"))

    aqi_data = data['data']
    aq_today_df = pd.DataFrame()
    aq_today_df['pm25'] = [aqi_data['iaqi'].get('pm25', {}).get('v', None)]
    aq_today_df['pm25'] = aq_today_df['pm25'].astype('float32')
    aq_today_df['country'] = cfg['country']
    aq_today_df['city'] = cfg['city']
    aq_today_df['street'] = cfg['street']
    aq_today_df['date'] = pd.to_datetime(dt.date.today())
    aq_today_df['url'] = cfg['aqicn_url']
    print("Weather rows (today + forecast):", aq_today_df.info())

    return aq_today_df


def fetch_weather_with_forecast(cfg) -> pd.DataFrame:
    base_url = "https://api.open-meteo.com/v1/ecmwf"
    today = dt.date.today()
    end_date = today + dt.timedelta(days=7)
    params = {
        "latitude": cfg['latitude'],
        "longitude": cfg['longitude'],
        "daily": ["temperature_2m_mean", "precipitation_sum", "wind_speed_10m_max", "wind_direction_10m_dominant"],
        "start_date": today.isoformat(),
        "end_date": end_date.isoformat(),
    }
    resp = requests.get(base_url, params=params)
    data = resp.json()
    if "daily" not in data:
        raise ValueError("Unexpected response from Open-Meteo: 'daily' missing", data.get("status"))

    daily = data['daily']
    df = pd.DataFrame()
    df["date"] = pd.to_datetime(daily["time"])
    df["temperature_2m_mean"] = daily["temperature_2m_mean"]
    df["temperature_2m_mean"] = df["temperature_2m_mean"].astype('float32')
    df["precipitation_sum"] = daily["precipitation_sum"]
    df["precipitation_sum"] = df["precipitation_sum"].astype('float32')
    df["wind_speed_10m_max"] = daily["wind_speed_10m_max"]
    df["wind_speed_10m_max"] = df["wind_speed_10m_max"].astype('float32')
    df["wind_direction_10m_dominant"] = daily["wind_direction_10m_dominant"]
    df["wind_direction_10m_dominant"] = df["wind_direction_10m_dominant"].astype('float32')
    df['city'] = cfg['city']
    print("Weather rows (today + forecast):", df.info())
    return df


def upsert_air_quality(fs, df_aq: pd.DataFrame):
    fg_aq = fs.get_feature_group(name="air_quality", version=1)
    print("Inserting into feature group 'air_quality'")
    fg_aq.insert(df_aq)
    print(f"Inserted {len(df_aq)} rows into 'air_quality'")


def upsert_weather(fs, df_weather: pd.DataFrame):
    fg_weather = fs.get_feature_group(name="weather", version=1)
    print("Inserting into feature group 'weather'")
    fg_weather.insert(df_weather)
    print(f"Inserted {len(df_weather)} rows into 'weather'")


def main():
    fs = get_hopsworks_project().get_feature_store()
    cfg = get_config()

    df_aq_latest = fetch_latest_air_quality(cfg)
    df_weather = fetch_weather_with_forecast(cfg)

    upsert_air_quality(fs, df_aq_latest)
    upsert_weather(fs, df_weather)


if __name__ == "__main__":
    main()
