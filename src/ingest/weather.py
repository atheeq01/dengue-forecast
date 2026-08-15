import requests
import pandas as pd

from src.config import DISTRICT_COORDS


def fetch_daily_weather(district: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
        Pulls daily weather (rain, temp, humidity) for one district from the open meteo
        start_date / end_date format: 'YYYY-MM-DD'
    """
    coords = DISTRICT_COORDS[district]
    url = "https://api.open-meteo.com/v1/archive"
    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "start_date": start_date,
        "end_date": end_date,
        "daily": "precipitation_sum,temperature_2m_max,temperature_2m_min,relative_humidity_2m_mean",
        "timezone": "Asia/Colombo",
    }

    response = requests.get(
        url,
        params=params,
        timeout=30
    )
    response.raise_for_status()
    daily = response.json()["daily"]

    df = pd.DataFrame({
        "date": pd.to_datetime(daily["time"]),
        "rain_mm": daily["precipitation_sum"],
        "temp_max": daily["temperature_2m_max"],
        "temp_min": daily["temperature_2m_min"],
        "humidity": daily["relative_humidity_2m_mean"],
    })

    df["district"] = district
    return df

def daily_to_weekly(daily_df: pd.DataFrame) -> pd.DataFrame:
    """
        Aggregates daily weather into weekly buckets:
        - rain is SUMMED (total weekly rainfall is what matters for mosquito
          breeding it accumulates)
        - temperature/humidity are avg (typical level that week)

        Weeks are anchored to end on Saturday (W-SAT) as a starting point.
        Adjust the anchor day once you've confirmed exactly how the
        Epidemiology Unit's own reporting week aligns to calendar days.
    """
    daily_df = daily_df.set_index("date")
    weekly = daily_df.resample("W-SAT").agg({
        "rain_mm": "sum",
        "temp_max": "mean",
        "temp_min": "mean",
        "humidity_mean": "mean",
        "district": "first",
    })
    return weekly.reset_index().rename(columns={"date": "week_ending"})

def fetch_weather_all_districts(start_date: str, end_date: str) -> pd.DataFrame:
    """Loops the fetch + weekly-aggregate over every district, concatenated into one table."""
    all_weekly = []
    for district in DISTRICT_COORDS.keys():
        print(f"Fetching weather for district {district} ...")
        daily = fetch_daily_weather(district, start_date, end_date)
        all_weekly.append(daily_to_weekly(daily))
    return pd.concat(all_weekly,ignore_index=True)