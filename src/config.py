"""
Centralized configuration for the Dengue Forecast project.

Contains:
- project paths
- RDHS definitions
- RDHS coordinates
- WER historical table schemas
"""

from pathlib import Path


# =============================================================================
# PROJECT PATHS
# =============================================================================

PROJECT_ROOT = Path(__file__).resolve().parents[1]

DATA_DIR = PROJECT_ROOT / "data"

RAW_DIR = DATA_DIR / "raw"
RAW_PDF_DIR = RAW_DIR / "wer_pdfs"
RAW_WEATHER_DIR = RAW_DIR / "weather"
RAW_EXTERNAL_DIR = RAW_DIR / "external"

BRONZE_DIR = DATA_DIR / "bronze"
WER_TEXT_DIR = BRONZE_DIR / "wer_text"

DENGUE_BRONZE_PATH = BRONZE_DIR / "dengue_raw_panel.parquet"
WEATHER_BRONZE_PATH = BRONZE_DIR / "weather_daily_raw.parquet"

SILVER_DIR = DATA_DIR / "silver"

DENGUE_SILVER_PATH = SILVER_DIR / "dengue_weekly.parquet"
WEATHER_SILVER_PATH = SILVER_DIR / "weather_weekly.parquet"
COMBINED_SILVER_PATH = SILVER_DIR / "dengue_weather_weekly.parquet"

GOLD_DIR = DATA_DIR / "gold"

NOTEBOOK_DIR = PROJECT_ROOT / "notebooks"
TEST_DIR = PROJECT_ROOT / "tests"


# =============================================================================
# RDHS
# =============================================================================

CANONICAL_RDHS = [
    "Colombo",
    "Gampaha",
    "Kalutara",

    "Kandy",
    "Matale",
    "Nuwara Eliya",

    "Galle",
    "Matara",
    "Hambantota",

    "Jaffna",
    "Kilinochchi",
    "Mannar",
    "Vavuniya",
    "Mullaitivu",

    "Batticaloa",
    "Ampara",
    "Kalmunai",
    "Trincomalee",

    "Kurunegala",
    "Puttalam",

    "Anuradhapura",
    "Polonnaruwa",

    "Badulla",
    "Monaragala",

    "Ratnapura",
    "Kegalle",
]


# =============================================================================
# RDHS REPRESENTATIVE COORDINATES
# =============================================================================

DISTRICT_COORDS: dict[str, dict[str, float]] = {

    "Colombo": {
        "lat": 6.9271,
        "lon": 79.8612,
    },

    "Gampaha": {
        "lat": 7.0840,
        "lon": 80.0098,
    },

    "Kalutara": {
        "lat": 6.5854,
        "lon": 79.9607,
    },

    "Kandy": {
        "lat": 7.2906,
        "lon": 80.6337,
    },

    "Matale": {
        "lat": 7.4675,
        "lon": 80.6234,
    },

    "Nuwara Eliya": {
        "lat": 6.9497,
        "lon": 80.7891,
    },

    "Galle": {
        "lat": 6.0535,
        "lon": 80.2210,
    },

    "Matara": {
        "lat": 5.9549,
        "lon": 80.5550,
    },

    "Hambantota": {
        "lat": 6.1429,
        "lon": 81.1212,
    },

    "Jaffna": {
        "lat": 9.6615,
        "lon": 80.0255,
    },

    "Kilinochchi": {
        "lat": 9.3803,
        "lon": 80.3770,
    },

    "Mannar": {
        "lat": 8.9810,
        "lon": 79.9044,
    },

    "Vavuniya": {
        "lat": 8.7542,
        "lon": 80.4982,
    },

    "Mullaitivu": {
        "lat": 9.2671,
        "lon": 80.8142,
    },

    "Batticaloa": {
        "lat": 7.7310,
        "lon": 81.6747,
    },

    "Ampara": {
        "lat": 7.2975,
        "lon": 81.6720,
    },

    "Kalmunai": {
        "lat": 7.4167,
        "lon": 81.8333,
    },

    "Trincomalee": {
        "lat": 8.5874,
        "lon": 81.2152,
    },

    "Kurunegala": {
        "lat": 7.4863,
        "lon": 80.3623,
    },

    "Puttalam": {
        "lat": 8.0408,
        "lon": 79.8394,
    },

    "Anuradhapura": {
        "lat": 8.3114,
        "lon": 80.4037,
    },

    "Polonnaruwa": {
        "lat": 7.9403,
        "lon": 81.0188,
    },

    "Badulla": {
        "lat": 6.9934,
        "lon": 81.0550,
    },

    "Monaragala": {
        "lat": 6.8728,
        "lon": 81.3507,
    },

    "Ratnapura": {
        "lat": 6.6828,
        "lon": 80.4037,
    },

    "Kegalle": {
        "lat": 7.2513,
        "lon": 80.3464,
    },
}


# =============================================================================
# HISTORICAL WER TABLE SCHEMAS
# =============================================================================
#
# These describe the total number of numeric values appearing in a
# district row after PDF extraction.
#
# Do NOT add new schemas just because a parser fails.
# First inspect the actual PDF and understand the new layout.
#

TABLE_SCHEMAS: dict[int, dict[str, list[str]]] = {

    # Early reports
    19: {
        "diseases": [
            "dengue_fever",
            "dysentery",
            "encephalitis",
            "enteric_fever",
            "food_poisoning",
            "leptospirosis",
            "typhus",
            "viral_hepatitis",
            "human_rabies",
        ],
        "trailing_fields": [
            "returns_pct",
        ],
    },

    # Variant with reporting fields
    20: {
        "diseases": [
            "dengue_fever",
            "dysentery",
            "encephalitis",
            "enteric_fever",
            "food_poisoning",
            "leptospirosis",
            "typhus",
            "viral_hepatitis",
            "human_rabies",
        ],
        "trailing_fields": [
            "timeliness_pct",
            "completeness_pct",
        ],
    },

    # Mid-era reports
    29: {
        "diseases": [
            "dengue_fever",
            "dysentery",
            "encephalitis",
            "enteric_fever",
            "food_poisoning",
            "leptospirosis",
            "typhus",
            "viral_hepatitis",
            "human_rabies",
            "chickenpox",
            "meningitis",
            "leishmaniasis",
            "tuberculosis",
            "leprosy",
        ],
        "trailing_fields": [
            "completeness_pct",
        ],
    },

    # Modern reports
    30: {
        "diseases": [
            "dengue_fever",
            "dysentery",
            "encephalitis",
            "enteric_fever",
            "food_poisoning",
            "leptospirosis",
            "typhus",
            "viral_hepatitis",
            "human_rabies",
            "chickenpox",
            "meningitis",
            "leishmaniasis",
            "tuberculosis",
            "leprosy",
        ],
        "trailing_fields": [
            "timeliness_pct",
            "completeness_pct",
        ],
    },
}


# =============================================================================
# BASIC VALIDATION
# =============================================================================

if set(CANONICAL_RDHS) != set(DISTRICT_COORDS):
    missing_coordinates = set(CANONICAL_RDHS) - set(DISTRICT_COORDS)
    extra_coordinates = set(DISTRICT_COORDS) - set(CANONICAL_RDHS)

    raise ValueError(
        f"RDHS configuration mismatch. "
        f"Missing coordinates: {missing_coordinates}; "
        f"Extra coordinates: {extra_coordinates}"
    )