from __future__ import annotations

from pathlib import Path
from typing import Iterable
import pandas as pd

from src.config import CANONICAL_RDHS

REQUIRED_COLUMNS = {
    "year",
    "week",
    "district",
    "cases",
}

def compute_week_start(df: pd.DataFrame) -> pd.Series:
    """Compute the ISO 8601 start date for a given year and week."""
    iso_week_str = (
        df["year"].astype(str)
        + "-W"
        + df["week"].astype(str).str.zfill(2)
        + "-1"
    )
    week_start = pd.to_datetime(
        iso_week_str,
        format="%G-W%V-%u",
        errors="coerce",
    )

    mask_nat = week_start.isna()
    if mask_nat.any():
        fallback_str = df.loc[mask_nat, "year"].astype(str) + "-W52-1"
        fallback_dates = pd.to_datetime(
            fallback_str, format="%G-W%V-%u", errors="coerce"
        )
        extra_days = (df.loc[mask_nat, "week"] - 52) * 7
        week_start.loc[mask_nat] = fallback_dates + pd.to_timedelta(
            extra_days, unit="D"
        )

    return week_start


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
    text = text.replace("'", "")

    try:
        number = float(text)
    except (ValueError, TypeError):
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

def clean_dengue_panel(
    df: pd.DataFrame,
    verbose: bool = True,
) -> pd.DataFrame:
    """
    Convert raw parsed WER rows into the canonical
    weekly dengue panel.

    Validates columns, standardizes district names, extracts
    canonical (year, week) and week_start, logs any duplicate
    observations, and produces a clean panel.

    Parameters
    ----------
    df : pd.DataFrame
        Raw parsed WER data.
    verbose : bool
        If True, print row counts after each cleaning step
        for auditability.
    """
    import logging

    logger = logging.getLogger(__name__)

    def _log(step: str, before: int, after: int) -> None:
        delta = before - after
        msg = f"[clean] {step}: {before} → {after} rows (Δ {delta})"
        if verbose:
            print(msg)
        logger.info(msg)

    df = df.copy()
    n0 = len(df)
    df = normalize_columns(df)

    if "cases" not in df.columns and "dengue_fever_this_week" in df.columns:
        df["cases"] = df["dengue_fever_this_week"]

    if "week" not in df.columns and "epi_week" in df.columns:
        df["week"] = df["epi_week"]

    validate_required_columns(df)

    df["district"] = (
        df["district"]
        .astype(str)
        .str.strip()
        .map(standardize_district_name)
    )

    # ── numeric conversion ──────────────────────────────────
    df["year"] = pd.to_numeric(df["year"], errors="coerce")
    df["week"] = pd.to_numeric(df["week"], errors="coerce")
    df["cases"] = df["cases"].apply(clean_integer)

    # Drop rows where year/week could not be parsed at all
    n_before = len(df)
    df = df.dropna(subset=["year", "week"])
    _log("drop unparseable year/week", n_before, len(df))

    df["year"] = df["year"].astype(int)
    df["week"] = df["week"].astype(int)

    # ── valid week range ────────────────────────────────────
    n_before = len(df)
    df = df[df["week"].between(1, 54)]
    _log("filter weeks 1-54", n_before, len(df))

    # ── canonical districts ─────────────────────────────────
    n_before = len(df)
    df = df[df["district"].isin(CANONICAL_RDHS)]
    _log("filter canonical districts", n_before, len(df))

    df["cases"] = df["cases"].fillna(0).astype(int)

    # ── compute week_start date BEFORE dedup ────────────────
    # Override the typo-prone OCR text with the true publication 
    # year and week extracted directly from the filename if available.
    if "source_file" in df.columns:
        file_parts = df["source_file"].astype(str).str.extract(r"wer_(\d{4})_w(\d{1,2})")
        valid_mask = file_parts[0].notna() & file_parts[1].notna()
        if valid_mask.any():
            df.loc[valid_mask, "year"] = file_parts.loc[valid_mask, 0].astype(int)
            df.loc[valid_mask, "week"] = file_parts.loc[valid_mask, 1].astype(int)

    # Generate standard ISO week_start
    df["week_start"] = compute_week_start(df)

    # Drop rows where week_start could not be computed
    n_before = len(df)
    df = df.dropna(subset=["week_start"])
    _log("drop null week_start", n_before, len(df))

    df = df.sort_values(
        ["district", "week_start", "year", "week"]
    )

    duplicate_mask = df.duplicated(
        subset=["district", "week_start"],
        keep=False,
    )

    if duplicate_mask.any():
        cols_to_show = [
            c for c in [
                "district",
                "year",
                "week",
                "week_start",
                "source_file",
                "cases",
            ]
            if c in df.columns
        ]

        duplicates = df.loc[
            duplicate_mask,
            cols_to_show,
        ]

        msg = (
            f"[WARNING] Duplicate district/week observations "
            f"detected ({len(duplicates)} rows):\n"
            f"{duplicates.to_string(index=False)}"
        )

        if verbose:
            print(msg)

        logger.warning(msg)

    n_before = len(df)

    df = df.drop_duplicates(
        subset=["district", "week_start"],
        keep="last",
    )

    _log(
        "drop duplicate (district, week_start)",
        n_before,
        len(df),
    )

    df = df.sort_values(
        ["district", "week_start"]
    )

    df = df.reset_index(drop=True)

    _log("total", n0, len(df))

    return df



def create_complete_panel(df: pd.DataFrame) -> pd.DataFrame:

    df = df.copy()

    min_year = df["year"].min()
    min_week = df.loc[
        df["year"].eq(min_year),
        "week"
    ].min()

    max_year = df["year"].max()
    max_week = df.loc[
        df["year"].eq(max_year),
        "week"
    ].max()

    year_weeks = []

    for year in range(min_year, max_year + 1):
        weeks_in_year = df.loc[
            df["year"].eq(year),
            "week"
        ]

        if weeks_in_year.empty:
            continue

        start_week = (
            min_week
            if year == min_year
            else 1
        )

        end_week = (
            max_week
            if year == max_year
            else weeks_in_year.max()
        )

        for week in range(
            start_week,
            end_week + 1,
        ):
            year_weeks.append(
                (year, week)
            )

    week_index = pd.DataFrame(
        year_weeks,
        columns=[
            "year",
            "week",
        ],
    )

    districts = pd.DataFrame(
        {
            "district": sorted(
                CANONICAL_RDHS
            )
        }
    )

    index = (
        districts
        .merge(
            week_index,
            how="cross",
        )
    )

    complete = index.merge(
        df,
        on=[
            "district",
            "year",
            "week",
        ],
        how="left",
        suffixes=(
            "",
            "_original",
        ),
    )

    if "week_start_original" in complete.columns:
        complete["week_start"] = complete["week_start_original"]
        complete = complete.drop(columns=["week_start_original"])

    # Compute week_start for any missing rows that were generated
    mask_nat = complete["week_start"].isna()
    if mask_nat.any():
        complete.loc[mask_nat, "week_start"] = compute_week_start(complete.loc[mask_nat])

    complete["is_missing_observation"] = (
        complete["cases"].isna()
    )

    complete["cases"] = complete[
        "cases"
    ].astype("Int64")

    complete = complete.sort_values(
        [
            "district",
            "year",
            "week",
        ]
    )

    return complete.reset_index(
        drop=True
    )