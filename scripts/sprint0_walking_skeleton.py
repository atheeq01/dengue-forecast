import pandas as pd
from sklearn.metrics import mean_absolute_error
from xgboost import XGBRegressor

from src.config import RAW_PDF_DIR
from src.ingest.pdf_parser import parse_wer_pdf_colombo_only
from src.ingest.weather import fetch_daily_weather, daily_to_weekly


def build_case_dataframe() -> pd.DataFrame:
    rows = []
    for pdf_path in sorted(RAW_PDF_DIR.glob("*.pdf")):
        parsed = parse_wer_pdf_colombo_only(pdf_path)
        if parsed is not None:
            rows.append(parsed)
    df = pd.DataFrame(rows)
    return df.sort_values("week_ending").reset_index(drop=True)


def main():
    cases_df = build_case_dataframe()
    print(f"Parsed {len(cases_df)} weeks of Colombo case data")

    start = cases_df["week_ending"].min().strftime("%Y-%m-%d")
    end = cases_df["week_ending"].max().strftime("%Y-%m-%d")
    weekly_weather = daily_to_weekly(fetch_daily_weather("Colombo", start, end))

    merged = pd.merge(cases_df, weekly_weather, on="week_ending", how="inner")

    merged["rain_lag_3w"] = merged["rain_mm"].shift(3)
    merged = merged.dropna(subset=["rain_lag_3w"]).reset_index(drop=True)

    # --- Baseline: "next week = this week" ---
    merged["baseline_pred"] = merged["dengue_this_week"].shift(1)
    valid = merged.dropna(subset=["baseline_pred"])
    baseline_mae = mean_absolute_error(valid["dengue_this_week"], valid["baseline_pred"])

    # --- XGBoost using the rain lag feature ---
    X = valid[["rain_lag_3w", "temp_max", "humidity_mean"]]
    y = valid["dengue_this_week"]

    # Tiny data -> tiny split. This is a smoke test, not a real evaluation.
    split = int(len(valid) * 0.8)
    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    model = XGBRegressor(n_estimators=50, max_depth=3, random_state=42)
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    xgb_mae = mean_absolute_error(y_test, preds)

    print(f"Baseline MAE (naive 'next week = this week'): {baseline_mae:.2f}")
    print(f"XGBoost MAE:                                   {xgb_mae:.2f}")


if __name__ == "__main__":
    main()
