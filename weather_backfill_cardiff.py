import os
from pathlib import Path
import pandas as pd
from dotenv import load_dotenv
from great_expectations.dataset import PandasDataset
from util import get_city_coordinates, get_historical_weather
from air_quality_backfill_cardiff import get_hopsworks_project, get_sensor_metadata


def get_location_and_weather_config():
    load_dotenv()
    country, city, street, _ = get_sensor_metadata()
    # get_city_coordinates(city)
    lat = float(os.getenv("WEATHER_LAT"))
    lon = float(os.getenv("WEATHER_LON"))

    return country, city, street, lat, lon


def get_date_range_from_air_quality(csv_path: str):
    df = pd.read_csv(csv_path, parse_dates=['date'], skipinitialspace=True)
    start_date = df["date"].min().date()
    end_date = df["date"].max().date()
    print(f"Air quality date range: {start_date} -> {end_date}")
    return start_date, end_date


def fetch_weather_history(city, start_date, end_date, lat, lon) -> pd.DataFrame:
    return get_historical_weather(city, start_date, end_date, lat, lon)


def build_weather_dataframe(
        df_weather_raw: pd.DataFrame,
        city: str,
) -> pd.DataFrame:
    df = df_weather_raw.copy()
    df["city"] = city
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["wind_speed_10m_max", "temperature_2m_mean"])
    print(f"Prepared weather Dataframe with {len(df)} rows")
    return df


def build_weather_expectation_suite(df: pd.DataFrame):
    print(f"Columns received in build_weather_expectation_suite: {len(df)}")
    ge_df = PandasDataset(df.copy())
    ge_df.expect_column_values_to_be_between("wind_speed_10m_max", min_value=0.0, max_value=1000.0)
    ge_df.expect_column_values_to_be_between("precipitation_sum", min_value=0.0, max_value=1000.0)
    ge_df.expect_column_values_to_not_be_null("date")
    return ge_df.get_expectation_suite()


def write_weather_feature_group(fs, df_weather: pd.DataFrame):
    weather_expectation_suite = build_weather_expectation_suite(df_weather)
    weather_fg = fs.get_or_create_feature_group(
        name="weather",
        version=1,
        description="Daily weather data for air quality prediction (cardiff sensor)",
        primary_key=["city"],
        event_time="date",
        expectation_suite=weather_expectation_suite
    )
    print("created or retrieved feature group 'air_quality' (v1)")

    weather_fg.insert(df_weather)
    print(f"Inserted {len(df_weather)} rows into 'air_quality' Feature Group")


def main():
    fs = get_hopsworks_project().get_feature_store()
    country, city, street, lat, lon = get_location_and_weather_config()
    root_dir = Path().absolute()
    csv_file = f"{root_dir}/data/cardiff-air-quality.csv"
    start_date, end_date = get_date_range_from_air_quality(csv_file)
    df_weather_raw = fetch_weather_history(city, start_date, end_date, lat, lon)
    df_weather = build_weather_dataframe(df_weather_raw, city)
    write_weather_feature_group(fs, df_weather)

if __name__ == "__main__":
    main()
