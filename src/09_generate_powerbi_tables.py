"""Stage 9: Generate Power BI export tables from processed CSVs."""

import sys
import pathlib

import pandas as pd

ROOT    = pathlib.Path(__file__).resolve().parent.parent
SRC_DIR = ROOT / "data" / "processed"
DST_DIR = ROOT / "data" / "processed"

EXPORTS = [
    {
        "src":              "cluster_daily_metrics.csv",
        "dst":              "pbi_cluster_daily_metrics.csv",
        "daily_date_cols":  ["date"],
        "monthly_date_cols": [],
    },
    {
        "src":              "cluster_monthly_metrics.csv",
        "dst":              "pbi_cluster_monthly_metrics.csv",
        "daily_date_cols":  [],
        "monthly_date_cols": ["month"],
    },
    {
        "src":              "capacity_inventory.csv",
        "dst":              "pbi_capacity_inventory.csv",
        "daily_date_cols":  [],
        "monthly_date_cols": [],
    },
    {
        "src":              "cluster_capacity_daily.csv",
        "dst":              "pbi_cluster_capacity_daily.csv",
        "daily_date_cols":  ["date"],
        "monthly_date_cols": [],
    },
    {
        "src":              "cluster_capacity_monthly.csv",
        "dst":              "pbi_cluster_capacity_monthly.csv",
        "daily_date_cols":  [],
        "monthly_date_cols": ["month"],
    },
    {
        "src":              "forecast_results.csv",
        "dst":              "pbi_forecast_results.csv",
        "daily_date_cols":  ["forecast_date"],
        "monthly_date_cols": [],
    },
    {
        "src":              "model_backtest_results.csv",
        "dst":              "pbi_model_backtest_results.csv",
        "daily_date_cols":  [],
        "monthly_date_cols": [],
    },
    {
        "src":              "capacity_risk_summary.csv",
        "dst":              "pbi_capacity_risk_summary.csv",
        "daily_date_cols":  [],
        "monthly_date_cols": [],
    },
]


def main() -> None:
    source_row_counts: dict[str, int] = {}

    for spec in EXPORTS:
        src_path = SRC_DIR / spec["src"]
        dst_path = DST_DIR / spec["dst"]

        df = pd.read_csv(src_path)

        unnamed_cols = [c for c in df.columns if c.lower().startswith("unnamed:")]
        if unnamed_cols:
            df = df.drop(columns=unnamed_cols)

        for col in spec["daily_date_cols"]:
            df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d")

        for col in spec["monthly_date_cols"]:
            df[col] = (
                pd.to_datetime(df[col])
                .dt.to_period("M")
                .dt.to_timestamp()
                .dt.strftime("%Y-%m-%d")
            )

        source_row_counts[spec["dst"]] = len(df)

        dst_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(dst_path, index=False)

    errors: list[str] = []

    for spec in EXPORTS:
        dst_path = DST_DIR / spec["dst"]
        pbi_df = pd.read_csv(dst_path)

        unnamed = [c for c in pbi_df.columns if c.lower().startswith("unnamed:")]
        if unnamed:
            errors.append(
                f"{spec['dst']}: contains Unnamed columns after export: {unnamed}"
            )

        expected_rows = source_row_counts[spec["dst"]]
        if len(pbi_df) != expected_rows:
            errors.append(
                f"{spec['dst']}: row count {len(pbi_df)} != source row count {expected_rows}"
            )

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Stage 9 complete — {len(EXPORTS)} Power BI tables written to {DST_DIR}.")
    for spec in EXPORTS:
        dst_path = DST_DIR / spec["dst"]
        pbi_df = pd.read_csv(dst_path)
        print(f"  {spec['dst']}: {len(pbi_df)} rows")
    sys.exit(0)


if __name__ == "__main__":
    main()
