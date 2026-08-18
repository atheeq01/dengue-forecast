from __future__ import annotations

from pathlib import Path
from typing import Iterable
import pandas as pd

from src.config import CANONICAL_RDHS

REQUIRED_COLUMNS = {
    "year",
    "week",
    "district",
    "case"
}


def standardize_district_name(value: str) -> str:
    """
    Convert district names produced by PDF parsing into
    the canonical names used by the project.
    """

    if value is None:
        return value

    value = str(value).strip()

    aliases = {
        "Colombo ": "Colombo",
        "Gampaha ": "Gampaha",
        "Kalutara ": "Kalutara",

        "Kandy ": "Kandy",
        "Matale ": "Matale",
        "Nuwara Eliya ": "Nuwara Eliya",

        "Galle ": "Galle",
        "Matara ": "Matara",
        "Hambantota ": "Hambantota",

        "Jaffna ": "Jaffna",
        "Kilinochchi ": "Kilinochchi",
        "Mannar ": "Mannar",
        "Vavuniya ": "Vavuniya",
        "Mullaitivu ": "Mullaitivu",

        "Batticaloa ": "Batticaloa",
        "Ampara ": "Ampara",
        "Trincomalee ": "Trincomalee",
        "Kalmunai ": "Kalmunai",

        "Kurunegala ": "Kurunegala",
        "Puttalam ": "Puttalam",

        "Anuradhapura ": "Anuradhapura",
        "Polonnaruwa ": "Polonnaruwa",

        "Badulla ": "Badulla",
        "Monaragala ": "Monaragala",

        "Ratnapura ": "Ratnapura",
        "Kegalle ": "Kegalle",
    }

    return aliases.get(value, value)


def clean_integer(value) -> int | None:
    """
       Convert OCR/PDF numeric values into integers.

       Examples:
           123 -> 123
           "123" -> 123
           "123.0" -> 123
           "1,234" -> 1234
           "" -> None
       """
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None
    text = text.replace(",", "")
    text = text.replace(".", "")
    text = text.replace("'", "")

    try:
        number=float(text)
    except ValueError:
        return None

    if number < 0:
        return None

    return int(round(number))

def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename_map = {}
    for column in df.columns:
       normalized = (
           str(column)
           .strip()
           .lower()
           .replace(" ", "_")
           .replace(",", "_")
       )
       rename_map[column] = normalized

    df= df.rename(columns=rename_map)

    return df

def validate_required_columns(df: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(df.columns)

    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")

def clean_dengue_panel(df:pd.DataFrame) -> pd.DataFrame:
    """
      Convert raw parsed WER rows into the canonical
      weekly dengue panel.
      """
    df = df.copy()
    df = normalize_columns(df)
    
    validate_required_columns(df)
    
    df["district"] = (
        df["district"]
        .astype(str)
        .str.strip()
        .map(standardize_district_name)
    )

    #change to the numeric
    df["year"]= pd.to_numeric(df["year"], errors="coerce")
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    # clean integer
    df["case"] = df["cases"].apply(clean_integer)

    # cast
    df["year"] = df["year"].astype(int)
    df["week"] = df["week"].astype(int)

    # only have 52/53 weeks
    df = df[df["week"].between(1, 54)]

    df = df[df["district"].isin(CANONICAL_RDHS)]

    df["cases"] = df["cases"].fillna(0).astype(int)

    # remove impossible duplicate observations
    df = (
        df
        .sort_values(
            [
                "year",
                "week",
                "district",
            ]
        )
        .drop_duplicates(
            subset=[
                "year",
                "week",
                "district",
            ],
            keep="last",
        )
    )
    # create a real weekly date.
    df["week_start"] = pd.to_datetime(
        df["year"].astype(str)
        + "-W"
        + df["week"].astype(str)
        + "-1",
        format="%G-W%V-%u",
        errors="coerce",
    )

    df = df.sort_values(
        [
            "district",
            "week_start",
        ]
    )

    df = df.reset_index(drop=True)

    return df



def create_complete_panel(df: pd.DataFrame) -> pd.DataFrame:
    """
     Ensure every district has every epidemiological
    week between the observed minimum and maximum.

    Missing observations are NOT automatically interpreted
    as zero disease. They are marked as missing.
    """

    df = df.copy()

    min_week = df["week_start"].min()
    max_week = df["week_start"].max()

    weeks = pd.date_range(
        min_week,
        max_week,
        freq="7D",
    )

    districts = sorted(CANONICAL_RDHS)

    index =  pd.MultiIndex.from_product(
        [districts,weeks],
        names=["district", "week_start"],
    )
    complete = (df.set_index(
        ["district", "week_start"]
    )
        .reindex(index)
        .reset_index()
    )

    complete["week"] = (
        complete["week_start"]
        .dt.isocalendar()
        .week
        .astype(int)
    )

    # IMPORTANT:
    # dont fill missing cases with zero.
    complete["is_missing_observation"] = (
        complete["cases"].isna()
    )

    complete["cases"] = complete["cases"].astype(
        "Int64"
    )

    complete = complete.sort_values(
        [
            "district",
            "week_start",
        ]
    )

    return complete.reset_index(drop=True)