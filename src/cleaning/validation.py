from __future__ import annotations

import pandas as pd

from src.config import CANONICAL_RDHS


def validate_districts(
    df: pd.DataFrame,
) -> dict:

    found = set(
        df["district"]
        .dropna()
        .unique()
    )

    expected = set(
        CANONICAL_RDHS
    )

    return {
        "expected": len(expected),
        "found": len(found),
        "missing": sorted(
            expected - found
        ),
        "unexpected": sorted(
            found - expected
        ),
    }


def validate_cases(
    df: pd.DataFrame,
) -> dict:

    negative = df[
        df["cases"].notna()
        & (df["cases"] < 0)
    ]

    return {
        "negative_cases": len(negative),
        "negative_rows": negative,
    }


def validate_duplicates(
    df: pd.DataFrame,
) -> dict:

    duplicated = df[
        df.duplicated(
            subset=[
                "district",
                "year",
                "week",
            ],
            keep=False,
        )
    ]

    return {
        "duplicate_rows": len(duplicated),
        "duplicates": duplicated,
    }


def validate_week_range(
    df: pd.DataFrame,
) -> dict:

    invalid = df[
        ~df["week"].between(1, 53)
    ]

    return {
        "invalid_week_rows": len(invalid),
        "invalid_rows": invalid,
    }


def validate_panel(
    df: pd.DataFrame,
) -> dict:

    district_check = validate_districts(df)
    case_check = validate_cases(df)
    duplicate_check = validate_duplicates(df)
    week_check = validate_week_range(df)

    report = {
        "rows": len(df),
        "districts": district_check,
        "cases": case_check,
        "duplicates": duplicate_check,
        "weeks": week_check,
    }

    return report


def print_validation_report(
    report: dict,
) -> None:

    print("\n" + "=" * 70)
    print("DENGUE DATA VALIDATION")
    print("=" * 70)

    print(
        f"Rows: {report['rows']:,}"
    )

    districts = report["districts"]

    print(
        f"Districts found: "
        f"{districts['found']}/"
        f"{districts['expected']}"
    )

    if districts["missing"]:
        print(
            "[WARNING] Missing districts:"
        )

        for district in districts["missing"]:
            print(
                f"  - {district}"
            )

    if districts["unexpected"]:
        print(
            "[WARNING] Unexpected districts:"
        )

        for district in districts["unexpected"]:
            print(
                f"  - {district}"
            )

    print(
        "Negative cases:",
        report["cases"]["negative_cases"],
    )

    print(
        "Duplicate rows:",
        report["duplicates"]["duplicate_rows"],
    )

    print(
        "Invalid weeks:",
        report["weeks"]["invalid_week_rows"],
    )

    print("=" * 70)