import os
import pandas as pd
from dotenv import load_dotenv
from pathlib import Path
import hopsworks
from great_expectations.dataset import PandasDataset


def get_hopsworks_project():
    load_dotenv()
    api_key = os.environ.get("HOPSWORKS_API_KEY")
    if not api_key:
        raise ValueError("HOPSWORKS_API_KEY not found in .env")

    project = hopsworks.login(api_key_value=api_key)
    print(f"Project name: {project.name}, with ID {project.id}")
    return project


def get_sensor_metadata():
    load_dotenv()
    country = os.getenv("AQICN_COUNTRY", "united-kingdom")
    city = os.getenv("AQICN_CITY", "wales")
    street = os.getenv("AQICN_STREET", "cardiff-newport-road")
    url = os.getenv("AQICN_URL", "https://api.waqi.info/feed/@10684")

    print(f"Using sensor: country: {country}, city: {city}, street: {street}")
    return country, city, street, url


def load_air_quality_csv(csv_path: str, country: str, city: str, street: str, url: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path, parse_dates=['date'], skipinitialspace=True)

    # Build a clean dataframe
    aq = pd.DataFrame()
    aq["date"] = pd.to_datetime(df["date"])
    aq["pm25"] = df["pm25"].astype("float32")
    aq.dropna(inplace=True)
    # Add location columns
    aq['country']=country
    aq['city']=city
    aq['street']=street
    aq['url']=url

    print(f"Loaded {len(aq)} rows of air quality date.")
    return aq


def build_aq_expectation_suite(df: pd.DataFrame):
    ge_df = PandasDataset(df)
    ge_df.expect_column_values_to_be_between("pm25", min_value=0.0, max_value=500.0)
    ge_df.expect_column_values_to_not_be_null("date")
    return ge_df.get_expectation_suite()


def write_air_quality_feature_group(fs, df_aq: pd.DataFrame):
    aq_expectation_suite = build_aq_expectation_suite(df_aq)

    # Create or get the feature group
    air_quality_fg = fs.get_or_create_feature_group(
        name="air_quality",
        version=1,
        description="City air quality data (pm25) for a single sensor",
        primary_key=["country", "city", "street"],
        event_time="date",
        expectation_suite=aq_expectation_suite
    )

    print("created or retrieved feature group 'air_quality' (v1)")

    air_quality_fg.insert(df_aq)
    print(f"Inserted {len(df_aq)} rows into 'air_quality' Feature Group")


def main():
    fs = get_hopsworks_project().get_feature_store()
    country, city, street, url = get_sensor_metadata()
    root_dir = Path().absolute()
    csv_file=f"{root_dir}/data/cardiff-air-quality.csv"
    df_aq = load_air_quality_csv(csv_file, country, city, street, url)
    write_air_quality_feature_group(fs, df_aq)


if __name__ == "__main__":
    main()
