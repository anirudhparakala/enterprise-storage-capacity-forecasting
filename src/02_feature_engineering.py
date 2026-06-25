from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PROCESSED_ROOT = Path("data/processed")
INPUT_PATH = PROCESSED_ROOT / "vm_metrics_cleaned.parquet"
OUTPUT_PATH = PROCESSED_ROOT / "vm_daily_metrics.csv"

REQUIRED_INPUT_COLUMNS = [
    "vm_id",
    "trace_type",
    "date",
    "memory_capacity_kb",
    "memory_usage_kb",
    "disk_read_kbps",
    "disk_write_kbps",
    "network_rx_kbps",
    "network_tx_kbps",
]

DISK_THROUGHPUT_COLUMNS = ["disk_read_kbps", "disk_write_kbps"]
NUMERIC_INPUT_COLUMNS = [
    "memory_capacity_kb",
    "memory_usage_kb",
    "disk_read_kbps",
    "disk_write_kbps",
    "network_rx_kbps",
    "network_tx_kbps",
]

DAILY_OUTPUT_COLUMNS = [
    "vm_id",
    "trace_type",
    "date",
    "avg_memory_utilization_pct",
    "p95_memory_utilization_pct",
    "avg_disk_read_kbps",
    "avg_disk_write_kbps",
    "avg_disk_total_kbps",
    "p95_disk_total_kbps",
    "avg_network_total_kbps",
    "high_disk_spike_count",
]


@dataclass(frozen=True)
class Stage2ValidationSummary:
    input_row_count: int
    output_row_count: int
    unique_vm_count: int
    date_range: str
    duplicate_vm_date_rows: int
    negative_disk_throughput_count: int
    memory_utilization_anomaly_count: int
    total_high_disk_spike_count: int
    stop_condition_passed: bool


def _negative_disk_throughput_count(df: pd.DataFrame) -> int:
    available_columns = [column for column in DISK_THROUGHPUT_COLUMNS if column in df.columns]
    if not available_columns:
        return 0
    return int((df[available_columns] < 0).sum().sum())


def validate_input(df: pd.DataFrame) -> None:
    failures: list[str] = []

    missing_columns = [column for column in REQUIRED_INPUT_COLUMNS if column not in df.columns]
    if missing_columns:
        failures.append(f"Missing required input columns: {', '.join(missing_columns)}.")

    if not missing_columns:
        negative_count = _negative_disk_throughput_count(df)
        if negative_count:
            failures.append(f"Found {negative_count} negative disk throughput values.")

        for column in NUMERIC_INPUT_COLUMNS:
            if column in df.columns and not pd.api.types.is_numeric_dtype(df[column]):
                failures.append(f"Input column is not numeric: {column}.")

        for column in ["vm_id", "trace_type", "date"]:
            if column in df.columns and (df[column].isna().any() or (df[column].astype(str).str.len() == 0).any()):
                failures.append(f"Input column has missing values: {column}.")

    if failures:
        raise ValueError("Stage 2 feature engineering input validation failed:\n- " + "\n- ".join(failures))


def add_workload_features(df: pd.DataFrame) -> pd.DataFrame:
    validate_input(df)
    featured = df.copy()

    featured["date"] = pd.to_datetime(featured["date"], errors="raise").dt.strftime("%Y-%m-%d")
    for column in NUMERIC_INPUT_COLUMNS:
        featured[column] = pd.to_numeric(featured[column], errors="raise")

    memory_capacity = featured["memory_capacity_kb"]
    featured["memory_utilization_pct"] = np.where(
        memory_capacity > 0,
        featured["memory_usage_kb"] / memory_capacity * 100,
        np.nan,
    )

    featured["disk_total_kbps"] = featured["disk_read_kbps"] + featured["disk_write_kbps"]
    featured["network_total_kbps"] = featured["network_rx_kbps"] + featured["network_tx_kbps"]

    disk_total = featured["disk_total_kbps"]
    featured["disk_write_ratio"] = np.where(
        disk_total > 0,
        featured["disk_write_kbps"] / disk_total,
        np.nan,
    )
    featured["disk_read_ratio"] = np.where(
        disk_total > 0,
        featured["disk_read_kbps"] / disk_total,
        np.nan,
    )

    vm_disk_p95 = featured.groupby("vm_id")["disk_total_kbps"].transform(lambda values: values.quantile(0.95))
    featured["is_high_disk_spike"] = featured["disk_total_kbps"] > vm_disk_p95
    return featured


def build_daily_metrics(featured: pd.DataFrame) -> pd.DataFrame:
    daily = (
        featured.groupby(["vm_id", "trace_type", "date"], as_index=False)
        .agg(
            avg_memory_utilization_pct=("memory_utilization_pct", "mean"),
            p95_memory_utilization_pct=("memory_utilization_pct", lambda values: values.quantile(0.95)),
            avg_disk_read_kbps=("disk_read_kbps", "mean"),
            avg_disk_write_kbps=("disk_write_kbps", "mean"),
            avg_disk_total_kbps=("disk_total_kbps", "mean"),
            p95_disk_total_kbps=("disk_total_kbps", lambda values: values.quantile(0.95)),
            avg_network_total_kbps=("network_total_kbps", "mean"),
            high_disk_spike_count=("is_high_disk_spike", "sum"),
        )
        .sort_values(["vm_id", "date", "trace_type"])
        .reset_index(drop=True)
    )

    daily["high_disk_spike_count"] = daily["high_disk_spike_count"].astype(int)
    return daily[DAILY_OUTPUT_COLUMNS]


def _memory_utilization_anomaly_count(featured: pd.DataFrame) -> int:
    anomalies = featured["memory_utilization_pct"].notna() & (
        (featured["memory_utilization_pct"] < 0) | (featured["memory_utilization_pct"] > 100)
    )
    return int(anomalies.sum())


def validate_daily_metrics(featured: pd.DataFrame, daily: pd.DataFrame) -> Stage2ValidationSummary:
    duplicate_vm_date_rows = int(daily.duplicated(["vm_id", "date"]).sum())
    negative_disk_count = _negative_disk_throughput_count(featured)
    memory_anomaly_count = _memory_utilization_anomaly_count(featured)
    total_high_disk_spike_count = int(daily["high_disk_spike_count"].sum()) if "high_disk_spike_count" in daily else 0

    failures: list[str] = []
    if list(daily.columns) != DAILY_OUTPUT_COLUMNS:
        failures.append("Daily output columns do not match the Stage 2 contract.")
    if negative_disk_count:
        failures.append(f"Found {negative_disk_count} negative disk throughput values.")
    if duplicate_vm_date_rows:
        failures.append(f"Found {duplicate_vm_date_rows} duplicate vm_id + date rows.")
    for column in ["p95_memory_utilization_pct", "p95_disk_total_kbps"]:
        if column not in daily.columns:
            failures.append(f"Missing required daily output column: {column}.")
    if total_high_disk_spike_count == 0:
        failures.append("high_disk_spike_count is all zero.")

    min_date = daily["date"].min() if not daily.empty else "None"
    max_date = daily["date"].max() if not daily.empty else "None"
    summary = Stage2ValidationSummary(
        input_row_count=len(featured),
        output_row_count=len(daily),
        unique_vm_count=int(daily["vm_id"].nunique()) if "vm_id" in daily else 0,
        date_range=f"{min_date} to {max_date}",
        duplicate_vm_date_rows=duplicate_vm_date_rows,
        negative_disk_throughput_count=negative_disk_count,
        memory_utilization_anomaly_count=memory_anomaly_count,
        total_high_disk_spike_count=total_high_disk_spike_count,
        stop_condition_passed=not failures,
    )

    if failures:
        raise ValueError("Stage 2 feature engineering validation failed:\n- " + "\n- ".join(failures))
    return summary


def _print_summary(summary: Stage2ValidationSummary, output_columns: list[str]) -> None:
    print("Stage 2 feature engineering validation summary")
    print(f"- Input row count: {summary.input_row_count}")
    print(f"- Output row count: {summary.output_row_count}")
    print(f"- Unique VM count: {summary.unique_vm_count}")
    print(f"- Date range: {summary.date_range}")
    print(f"- Duplicate vm_id + date rows: {summary.duplicate_vm_date_rows}")
    print(f"- Negative disk throughput count: {summary.negative_disk_throughput_count}")
    print(f"- Memory utilization anomaly count: {summary.memory_utilization_anomaly_count}")
    print(f"- Total high_disk_spike_count: {summary.total_high_disk_spike_count}")
    print(f"- Output columns: {', '.join(output_columns)}")
    print(f"- Stop condition passed: {summary.stop_condition_passed}")


def main() -> int:
    if not INPUT_PATH.exists():
        print(f"Stage 2 feature engineering failed: required Stage 1 output is missing at {INPUT_PATH}.")
        return 1

    try:
        source = pd.read_parquet(INPUT_PATH)
        featured = add_workload_features(source)
        daily = build_daily_metrics(featured)
        summary = validate_daily_metrics(featured, daily)
    except Exception as exc:
        print(str(exc))
        return 1

    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    daily.to_csv(OUTPUT_PATH, index=False)
    _print_summary(summary, list(daily.columns))
    print(f"- Wrote daily VM metrics: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
