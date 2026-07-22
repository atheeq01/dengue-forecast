# scripts/sprint1_ingest_bronze.py

import pandas as pd

from src.config import RAW_PDF_DIR, BRONZE_DIR
from src.ingest.pdf_parser import parse_wer_pdf
from src.ingest.weather import fetch_weather_all_districts


def main():
    BRONZE_DIR.mkdir(parents=True, exist_ok=True)

    all_case_rows = []
    for pdf_path in sorted(RAW_PDF_DIR.glob("*.pdf")):
        all_case_rows.extend(parse_wer_pdf(pdf_path))

    cases_df = pd.DataFrame(all_case_rows)
    cases_df.to_parquet(BRONZE_DIR / "cases.parquet", index=False)
    print(f"Wrote {len(cases_df)} rows ({cases_df['district'].nunique()} divisions) "
          f"to bronze/cases.parquet")

    start = cases_df["week_ending"].min().strftime("%Y-%m-%d")
    end = cases_df["week_ending"].max().strftime("%Y-%m-%d")
    weather_df = fetch_weather_all_districts(start, end)
    weather_df.to_parquet(BRONZE_DIR / "weather.parquet", index=False)
    print(f"Wrote {len(weather_df)} weather rows to bronze/weather.parquet")


if __name__ == "__main__":
    main()
