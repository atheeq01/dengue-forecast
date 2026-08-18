from __future__ import annotations

from datetime import date

import pandas as pd

from src.config import (
    RAW_PDF_DIR,
    DENGUE_BRONZE_PATH,
    WEATHER_BRONZE_PATH,
    DENGUE_SILVER_PATH,
    WEATHER_SILVER_PATH,
    COMBINED_SILVER_PATH,
    DISTRICT_COORDS,
)

from src.ingest.pdf_parser import (
    parse_wer_pdf,
)

from src.ingest.download_wer import (
    download_all_wer_pdfs,
)

from src.ingest.weather import (
    fetch_weather_for_district,
)

from src.cleaning.dengue_cleaner import (
    clean_dengue_panel,
    create_complete_panel,
)

from src.cleaning.weather_cleaner import (
    clean_weather_daily,
    daily_to_weekly,
)

from src.cleaning.merge import (
    merge_dengue_weather,
)

from src.cleaning.validation import (
    validate_panel,
    print_validation_report,
)

from src.utils.io import (
    save_parquet,
)


WER_PARSE_MANIFEST_PATH = DENGUE_BRONZE_PATH.with_name(
    "wer_parse_manifest.parquet"
)


def refresh_wer_pdfs() -> None:
    try:
        download_all_wer_pdfs()
    except Exception as exc:
        print(
            "[WARNING] WER PDF download failed; "
            f"continuing with local PDFs. {exc}"
        )


def ingest_dengue_pdfs() -> pd.DataFrame:

    pdf_files = sorted(
        RAW_PDF_DIR.glob("*.pdf")
    )

    if not pdf_files:

        raise FileNotFoundError(
            f"No WER PDFs found in "
            f"{RAW_PDF_DIR}"
        )

    print(
        f"[WER] Found "
        f"{len(pdf_files):,} PDFs"
    )

    existing_raw = None
    already_parsed = set()
    parse_manifest = None
    already_handled = set()

    if DENGUE_BRONZE_PATH.exists():
        existing_raw = pd.read_parquet(
            DENGUE_BRONZE_PATH
        )

        if "source_file" in existing_raw.columns:
            already_parsed = set(
                existing_raw["source_file"]
                .dropna()
                .astype(str)
                .unique()
            )

    if WER_PARSE_MANIFEST_PATH.exists():
        parse_manifest = pd.read_parquet(
            WER_PARSE_MANIFEST_PATH
        )

        if "source_file" in parse_manifest.columns:
            handled = parse_manifest[
                parse_manifest["status"].isin(
                    [
                        "parsed",
                        "empty",
                    ]
                )
            ]
            already_handled = set(
                handled["source_file"]
                .dropna()
                .astype(str)
                .unique()
            )

    already_handled.update(
        already_parsed
    )

    new_pdf_files = [
        pdf_path
        for pdf_path in pdf_files
        if pdf_path.name not in already_handled
    ]

    print(
        "[WER] "
        f"{len(already_handled):,} PDFs already handled, "
        f"{len(new_pdf_files):,} new PDFs to parse"
    )

    frames = []
    manifest_records = []

    for index, pdf_path in enumerate(
        new_pdf_files,
        start=1,
    ):

        print(
            f"[WER] "
            f"{index}/{len(new_pdf_files)} "
            f"{pdf_path.name}"
        )

        try:

            parsed = parse_wer_pdf(
                pdf_path
            )

            if parsed is None:
                continue

            if isinstance(parsed, pd.DataFrame):
                frame = parsed

            elif isinstance(parsed, list):
                frame = pd.DataFrame(parsed)

            else:
                print(
                    "[WARNING] Parser returned "
                    f"{type(parsed)}"
                )
                manifest_records.append(
                    {
                        "source_file": pdf_path.name,
                        "status": "unsupported_return",
                        "rows": 0,
                    }
                )
                continue

            if not frame.empty:
                frames.append(frame)
                manifest_records.append(
                    {
                        "source_file": pdf_path.name,
                        "status": "parsed",
                        "rows": len(frame),
                    }
                )
            else:
                manifest_records.append(
                    {
                        "source_file": pdf_path.name,
                        "status": "empty",
                        "rows": 0,
                    }
                )

        except Exception as exc:

            print(
                f"[ERROR] {pdf_path.name}: "
                f"{exc}"
            )
            manifest_records.append(
                {
                    "source_file": pdf_path.name,
                    "status": "error",
                    "rows": 0,
                    "error": str(exc),
                }
            )

    if manifest_records:
        new_manifest = pd.DataFrame(
            manifest_records
        )

        if parse_manifest is not None:
            parse_manifest = pd.concat(
                [
                    parse_manifest,
                    new_manifest,
                ],
                ignore_index=True,
            )
        else:
            parse_manifest = new_manifest

        parse_manifest = parse_manifest.drop_duplicates(
            subset=[
                "source_file",
            ],
            keep="last",
        )

        WER_PARSE_MANIFEST_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        parse_manifest.to_parquet(
            WER_PARSE_MANIFEST_PATH,
            index=False,
        )

    if existing_raw is not None:
        frames.insert(
            0,
            existing_raw,
        )

    if not frames:

        raise RuntimeError(
            "No WER PDFs were successfully parsed."
        )

    result = pd.concat(
        frames,
        ignore_index=True,
    )

    if "source_file" in result.columns:
        result = result.drop_duplicates(
            subset=[
                "source_file",
                "district",
            ],
            keep="last",
        )

    return result


def build_dengue_layer() -> pd.DataFrame:

    refresh_wer_pdfs()

    raw = ingest_dengue_pdfs()

    print(
        f"[WER] Raw parsed rows: "
        f"{len(raw):,}"
    )

    save_parquet(
        raw,
        DENGUE_BRONZE_PATH,
    )

    clean = clean_dengue_panel(
        raw
    )

    print(
        f"[WER] Clean rows: "
        f"{len(clean):,}"
    )

    validation = validate_panel(
        clean
    )

    print_validation_report(
        validation
    )

    complete = create_complete_panel(
        clean
    )

    save_parquet(
        complete,
        DENGUE_SILVER_PATH,
    )

    return complete


def build_weather_layer(
    start_date: date,
    end_date: date,
) -> pd.DataFrame:

    frames = []

    if WEATHER_BRONZE_PATH.exists():
        existing = pd.read_parquet(
            WEATHER_BRONZE_PATH
        )
        existing["date"] = pd.to_datetime(
            existing["date"],
            errors="coerce",
        )
        frames.append(
            existing
        )
    else:
        existing = pd.DataFrame()

    requested_dates = pd.date_range(
        start_date,
        end_date,
        freq="D",
    )

    missing_requests = []

    for district in DISTRICT_COORDS:
        if existing.empty:
            existing_dates = set()
        else:
            existing_dates = set(
                existing.loc[
                    existing["district"].eq(
                        district
                    ),
                    "date",
                ]
                .dropna()
                .dt.normalize()
            )

        missing_dates = [
            day
            for day in requested_dates
            if day.normalize() not in existing_dates
        ]

        if missing_dates:
            missing_requests.append(
                (
                    district,
                    missing_dates[0].date(),
                    missing_dates[-1].date(),
                    len(missing_dates),
                )
            )

    print(
        "[weather] "
        f"{len(missing_requests):,} districts need new daily data"
    )

    for district, missing_start, missing_end, missing_days in missing_requests:
        print(
            f"[weather] {district} "
            f"{missing_start} → {missing_end} "
            f"({missing_days:,} days)"
        )

        try:
            df = fetch_weather_for_district(
                district,
                missing_start,
                missing_end,
            )
            frames.append(
                df
            )

        except Exception as exc:
            print(
                f"[ERROR] {district}: {exc}"
            )

    if not frames:
        raise RuntimeError(
            "No weather data is available."
        )

    raw = pd.concat(
        frames,
        ignore_index=True,
    )

    raw["date"] = pd.to_datetime(
        raw["date"],
        errors="coerce",
    )
    raw = (
        raw
        .dropna(
            subset=[
                "district",
                "date",
            ]
        )
        .drop_duplicates(
            subset=[
                "district",
                "date",
            ],
            keep="last",
        )
    )

    raw = raw[
        raw["date"].between(
            pd.Timestamp(start_date),
            pd.Timestamp(end_date),
        )
    ]

    save_parquet(
        raw,
        WEATHER_BRONZE_PATH,
    )

    daily = clean_weather_daily(
        raw
    )

    weekly = daily_to_weekly(
        daily
    )

    save_parquet(
        weekly,
        WEATHER_SILVER_PATH,
    )

    return weekly


def build_combined_layer(
    dengue: pd.DataFrame,
    weather: pd.DataFrame,
) -> pd.DataFrame:

    merged = merge_dengue_weather(
        dengue,
        weather,
    )

    save_parquet(
        merged,
        COMBINED_SILVER_PATH,
    )

    return merged


def main():

    print("\n")
    print("=" * 80)
    print("DENGUE FORECASTING PLATFORM")
    print("SPRINT 1 DATA PIPELINE")
    print("=" * 80)

    # ---------------------------------------------------------
    # 1. Dengue
    # ---------------------------------------------------------

    dengue = build_dengue_layer()

    # ---------------------------------------------------------
    # Determine weather range
    # ---------------------------------------------------------

    min_date = (
        dengue["week_start"]
        .min()
        .date()
    )

    max_date = (
        dengue["week_start"]
        .max()
        .date()
    )

    print(
        f"\nWeather range: "
        f"{min_date} → {max_date}"
    )

    # ---------------------------------------------------------
    # 2. Weather
    # ---------------------------------------------------------

    weather = build_weather_layer(
        min_date,
        max_date,
    )

    # ---------------------------------------------------------
    # 3. Merge
    # ---------------------------------------------------------

    combined = build_combined_layer(
        dengue,
        weather,
    )

    # ---------------------------------------------------------
    # Summary
    # ---------------------------------------------------------

    print("\n")
    print("=" * 80)
    print("SPRINT 1 COMPLETE")
    print("=" * 80)

    print(
        f"Dengue rows: "
        f"{len(dengue):,}"
    )

    print(
        f"Weather rows: "
        f"{len(weather):,}"
    )

    print(
        f"Combined rows: "
        f"{len(combined):,}"
    )

    print(
        "\nCombined columns:"
    )

    for column in combined.columns:
        print(
            f"  - {column}"
        )


if __name__ == "__main__":
    main()
