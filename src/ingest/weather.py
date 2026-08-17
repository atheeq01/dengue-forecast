import requests
import pandas as pd

from src.config import DISTRICT_COORDS

OPEN_METEO_ARCHIVE_URL = "https://api.open-meteo.com/v1/archive"


def fetch_daily_weather(
        district: str,
        start_date: str,
        end_date: str,
) -> pd.DataFrame:
    """
    Fetch daily historical weather for one RDHS representative coordinate.

    Parameters
    ----------
    district:
        Canonical RDHS name.

    start_date:
        YYYY-MM-DD

    end_date:
        YYYY-MM-DD
    """

    if district not in DISTRICT_COORDS:
        raise ValueError(
            f"Unknown RDHS '{district}'. "
            f"Expected one of: {list(DISTRICT_COORDS)}"
        )

    coords = DISTRICT_COORDS[district]

    params = {
        "latitude": coords["lat"],
        "longitude": coords["lon"],
        "start_date": start_date,
        "end_date": end_date,
        "daily": (
            "precipitation_sum,"
            "temperature_2m_max,"
            "temperature_2m_min,"
            "relative_humidity_2m_mean"
        ),
        "timezone": "Asia/Colombo",
    }

    response = requests.get(
        OPEN_METEO_ARCHIVE_URL,
        params=params,
        timeout=30,
    )

    response.raise_for_status()

    payload = response.json()

    if "daily" not in payload:
        raise ValueError(
            f"Open-Meteo response did not contain 'daily' data "
            f"for {district}"
        )

    daily = payload["daily"]

    df = pd.DataFrame(
        {
            "date": pd.to_datetime(daily["time"]),
            "rain_mm": daily["precipitation_sum"],
            "temp_max_c": daily["temperature_2m_max"],
            "temp_min_c": daily["temperature_2m_min"],
            "humidity_pct": daily["relative_humidity_2m_mean"],
        }
    )

    df["district"] = district

    return df


def daily_to_weekly(
        daily_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    Aggregate daily weather into Saturday-ending epidemiological-style
    calendar weeks.

    Rainfall:
        SUM

    Temperature:
        MEAN

    Humidity:
        MEAN
    """

    required_columns = {
        "date",
        "rain_mm",
        "temp_max_c",
        "temp_min_c",
        "humidity_pct",
        "district",
    }

    missing = required_columns - set(daily_df.columns)

    if missing:
        raise ValueError(
            f"Missing required weather columns: {sorted(missing)}"
        )

    df = daily_df.copy()

    df["date"] = pd.to_datetime(df["date"])

    weekly = (
        df.set_index("date")
        .resample("W-SAT")
        .agg(
            rain_mm=("rain_mm", "sum"),
            temp_max_c=("temp_max_c", "mean"),
            temp_min_c=("temp_min_c", "mean"),
            humidity_pct=("humidity_pct", "mean"),
            district=("district", "first"),
        )
        .reset_index()
        .rename(columns={"date": "week_ending"})
    )

    return weekly


def fetch_weather_all_districts(
        start_date: str,
        end_date: str,
) -> pd.DataFrame:
    """
    Fetch and aggregate weather for every RDHS.
    """

    all_weekly = []

    for district in DISTRICT_COORDS:
        print(
            f"[weather] Fetching {district} "
            f"from {start_date} to {end_date}"
        )

        daily = fetch_daily_weather(
            district=district,
            start_date=start_date,
            end_date=end_date,
        )

        weekly = daily_to_weekly(daily)

        all_weekly.append(weekly)

    if not all_weekly:
        return pd.DataFrame()

    return pd.concat(
        all_weekly,
        ignore_index=True,
    )
