from __future__ import annotations

import pandas as pd


def clean_weather_daily(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df["date"] = pd.to_datetime(
        df["date"],
        errors="coerce",
    )

    numeric_columns = [
        "PRECTOTCORR",
        "T2M",
        "T2M_MAX",
        "T2M_MIN",
        "RH2M",
        "WS10M",
    ]

    for column in numeric_columns:

        if column in df.columns:

            df[column] = pd.to_numeric(
                df[column],
                errors="coerce",
            )

    df["DTR"] = (
        df["T2M_MAX"]
        - df["T2M_MIN"]
    )

    df = df.dropna(
        subset=[
            "district",
            "date",
        ]
    )

    df = df.sort_values(
        [
            "district",
            "date",
        ]
    )

    return df.reset_index(
        drop=True
    )


def daily_to_weekly(
    df: pd.DataFrame,
) -> pd.DataFrame:

    df = df.copy()

    df["week_start"] = (
        df["date"]
        - pd.to_timedelta(
            df["date"].dt.weekday,
            unit="D",
        )
    )

    grouped = (
        df.groupby(
            [
                "district",
                "week_start",
            ],
            as_index=False,
        )
        .agg(
            rainfall_mm=(
                "PRECTOTCORR",
                "sum",
            ),
            temperature_mean=(
                "T2M",
                "mean",
            ),
            temperature_max=(
                "T2M_MAX",
                "mean",
            ),
            temperature_min=(
                "T2M_MIN",
                "mean",
            ),
            humidity_mean=(
                "RH2M",
                "mean",
            ),
            wind_speed_mean=(
                "WS10M",
                "mean",
            ),
            dtr_mean=(
                "DTR",
                "mean",
            ),
            weather_days=(
                "date",
                "count",
            ),
        )
    )

    grouped["year"] = (
        grouped["week_start"]
        .dt.isocalendar()
        .year
        .astype(int)
    )

    grouped["week"] = (
        grouped["week_start"]
        .dt.isocalendar()
        .week
        .astype(int)
    )

    return grouped.sort_values(
        [
            "district",
            "week_start",
        ]
    ).reset_index(
        drop=True
    )