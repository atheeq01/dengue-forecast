from __future__ import annotations

import pandas as pd


def merge_dengue_weather(
    dengue: pd.DataFrame,
    weather: pd.DataFrame,
) -> pd.DataFrame:

    dengue = dengue.copy()
    weather = weather.copy()

    keys = [
        "district",
        "week_start",
    ]

    weather_columns = [
        "district",
        "week_start",
        "rainfall_mm",
        "temperature_mean",
        "temperature_max",
        "temperature_min",
        "humidity_mean",
        "wind_speed_mean",
        "dtr_mean",
        "weather_days",
    ]

    weather = weather[
        [
            column
            for column in weather_columns
            if column in weather.columns
        ]
    ]

    merged = dengue.merge(
        weather,
        on=keys,
        how="left",
        validate="one_to_one",
    )

    return merged.sort_values(
        [
            "district",
            "week_start",
        ]
    ).reset_index(drop=True)