from __future__ import annotations

from datetime import date
from pathlib import Path

import requests
import pandas as pd

from src.config import DISTRICT_COORDS


BASE_URL = (
    "https://power.larc.nasa.gov/api/temporal/daily/point"
)


PARAMETERS = [
    "PRECTOTCORR",
    "T2M",
    "T2M_MAX",
    "T2M_MIN",
    "RH2M",
    "WS10M",
]


def fetch_weather_for_district(
    district: str,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:

    coords = DISTRICT_COORDS[district]

    params = {
        "parameters": ",".join(PARAMETERS),
        "community": "AG",
        "longitude": coords["lon"],
        "latitude": coords["lat"],
        "start": start_date.strftime("%Y%m%d"),
        "end": end_date.strftime("%Y%m%d"),
        "format": "JSON",
    }

    response = requests.get(
        BASE_URL,
        params=params,
        timeout=60,
    )

    response.raise_for_status()

    payload = response.json()

    properties = (
        payload["properties"]
        ["parameter"]
    )

    rows = []

    for date_key in properties["T2M"].keys():

        row = {
            "district": district,
            "date": pd.to_datetime(
                date_key,
                format="%Y%m%d",
            ),
        }

        for parameter in PARAMETERS:
            row[parameter] = properties[
                parameter
            ].get(date_key)

        rows.append(row)

    return pd.DataFrame(rows)


def fetch_all_weather(
    start_date: date,
    end_date: date,
) -> pd.DataFrame:

    frames = []

    for district in DISTRICT_COORDS:

        print(
            f"[weather] {district}"
        )

        try:

            df = fetch_weather_for_district(
                district,
                start_date,
                end_date,
            )

            frames.append(df)

        except Exception as exc:

            print(
                f"[ERROR] {district}: {exc}"
            )

    if not frames:
        raise RuntimeError(
            "No weather data was downloaded."
        )

    result = pd.concat(
        frames,
        ignore_index=True,
    )

    return result