from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


RAW_ROOT = Path("data/raw")
PROCESSED_ROOT = Path("data/processed")
PROFILE_OUTPUT = PROCESSED_ROOT / "raw_data_profile.csv"
CLEANED_OUTPUT = PROCESSED_ROOT / "vm_metrics_cleaned.parquet"
SAMPLE_OUTPUT = PROCESSED_ROOT / "vm_metrics_sample.csv"
ERROR_SUMMARY_OUTPUT = PROCESSED_ROOT / "ingestion_error_summary.csv"

EXPECTED_COLUMN_COUNT = 11
MAX_FAILED_PARSE_RATE = 0.05
KNOWN_TRACE_TYPES = {"fastStorage", "Rnd"}
MONTH_FOLDER_PATTERN = re.compile(r"^\d{4}-\d{1,2}$")
DELIMITER_PATTERN = re.compile(r";\s*")
VM_ID_INVALID_PATTERN = re.compile(r"[^A-Za-z0-9_-]+")

RAW_COLUMNS = [
    "timestamp_raw",
    "cpu_cores",
    "cpu_capacity_mhz",
    "cpu_usage_mhz",
    "cpu_usage_pct",
    "memory_capacity_kb",
    "memory_usage_kb",
    "disk_read_kbps",
    "disk_write_kbps",
    "network_rx_kbps",
    "network_tx_kbps",
]

METRIC_COLUMNS = RAW_COLUMNS[1:]

TARGET_COLUMNS = [
    "source_file",
    "source_month_folder",
    "trace_type",
    "vm_id",
    "timestamp_raw",
    "timestamp_unit_detected",
    "datetime",
    "date",
    "month",
    "hour",
    "cpu_cores",
    "cpu_capacity_mhz",
    "cpu_usage_mhz",
    "cpu_usage_pct",
    "memory_capacity_kb",
    "memory_usage_kb",
    "disk_read_kbps",
    "disk_write_kbps",
    "network_rx_kbps",
    "network_tx_kbps",
]


def discover_raw_files(raw_root: Path) -> list[Path]:
    """Return raw CSV files in deterministic order."""
    return sorted(raw_root.rglob("*.csv"))


def infer_trace_type(path: Path) -> str:
    for part in path.parts:
        if part in KNOWN_TRACE_TYPES:
            return part
    return "Unknown"


def infer_source_month_folder(path: Path) -> str:
    for part in path.parts:
        if MONTH_FOLDER_PATTERN.match(part):
            return part
    return "Unknown"


def clean_raw_line(line: str) -> str:
    cleaned = line.strip()
    if len(cleaned) >= 2 and cleaned.startswith('"') and cleaned.endswith('"'):
        return cleaned[1:-1]
    return cleaned


def split_trace_line(line: str) -> list[str]:
    cleaned = clean_raw_line(line)
    if not cleaned:
        return []
    return DELIMITER_PATTERN.split(cleaned)


def infer_timestamp_unit(value: float) -> str:
    if 1_000_000_000 <= value <= 2_000_000_000:
        return "seconds"
    if value >= 1_000_000_000_000:
        return "milliseconds"
    return "unknown"


def build_vm_id(path: Path, raw_root: Path) -> str:
    relative = path.relative_to(raw_root).with_suffix("")
    normalized_parts = []
    for part in relative.parts:
        normalized = VM_ID_INVALID_PATTERN.sub("_", part).strip("_")
        normalized_parts.append(normalized or "unknown")
    return "_".join(normalized_parts)


def convert_timestamp(timestamp_raw: str) -> tuple[float, str, pd.Timestamp]:
    try:
        timestamp_value = float(timestamp_raw)
    except ValueError as exc:
        raise ValueError(f"nonnumeric timestamp: {timestamp_raw}") from exc

    timestamp_unit = infer_timestamp_unit(timestamp_value)
    if timestamp_unit == "seconds":
        timestamp = datetime.fromtimestamp(timestamp_value, tz=timezone.utc).replace(tzinfo=None)
    elif timestamp_unit == "milliseconds":
        timestamp = datetime.fromtimestamp(timestamp_value / 1000, tz=timezone.utc).replace(tzinfo=None)
    else:
        raise ValueError(f"unknown timestamp unit: {timestamp_raw}")

    return timestamp_value, timestamp_unit, pd.Timestamp(timestamp)


def _empty_summary(path: Path, raw_root: Path) -> dict[str, Any]:
    return {
        "source_file": str(path),
        "trace_type": infer_trace_type(path),
        "source_month_folder": infer_source_month_folder(path),
        "vm_id": build_vm_id(path, raw_root),
        "data_rows_seen": 0,
        "accepted_rows": 0,
        "failed_rows": 0,
        "blank_rows": 0,
        "malformed_rows": 0,
        "one_column_rows": 0,
        "nonnumeric_timestamp_rows": 0,
        "unknown_timestamp_unit_rows": 0,
        "timestamp_conversion_error_rows": 0,
        "numeric_coerced_cells": 0,
    }


def parse_trace_file(path: Path, raw_root: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Parse one Bitbrains trace file into Stage 1 target columns."""
    summary = _empty_summary(path, raw_root)
    rows: list[list[Any]] = []

    with path.open("r", encoding="utf-8", errors="replace", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            fields = split_trace_line(line)
            if not fields:
                summary["blank_rows"] += 1
                continue
            if line_number == 1 and "Timestamp" in fields[0]:
                continue

            summary["data_rows_seen"] += 1
            if len(fields) == 1:
                summary["one_column_rows"] += 1
                summary["malformed_rows"] += 1
                summary["failed_rows"] += 1
                continue
            if len(fields) != EXPECTED_COLUMN_COUNT:
                summary["malformed_rows"] += 1
                summary["failed_rows"] += 1
                continue

            try:
                timestamp_value, timestamp_unit, timestamp = convert_timestamp(fields[0])
            except ValueError as exc:
                message = str(exc)
                if "nonnumeric" in message:
                    summary["nonnumeric_timestamp_rows"] += 1
                elif "unknown timestamp unit" in message:
                    summary["unknown_timestamp_unit_rows"] += 1
                else:
                    summary["timestamp_conversion_error_rows"] += 1
                summary["failed_rows"] += 1
                continue

            rows.append(
                [
                    str(path),
                    summary["source_month_folder"],
                    summary["trace_type"],
                    summary["vm_id"],
                    timestamp_value,
                    timestamp_unit,
                    timestamp,
                    timestamp.strftime("%Y-%m-%d"),
                    timestamp.strftime("%Y-%m-01"),
                    int(timestamp.hour),
                    *fields[1:],
                ]
            )
            summary["accepted_rows"] += 1

    df = pd.DataFrame(rows, columns=TARGET_COLUMNS)
    if not df.empty:
        before_na = df[METRIC_COLUMNS].isna().sum().sum()
        for column in METRIC_COLUMNS:
            df[column] = pd.to_numeric(df[column], errors="coerce")
        after_na = df[METRIC_COLUMNS].isna().sum().sum()
        summary["numeric_coerced_cells"] = int(after_na - before_na)
    return df, summary


def validate_ingested(
    df: pd.DataFrame,
    error_summary: pd.DataFrame,
    *,
    failed_parse_rate: float,
) -> None:
    failures: list[str] = []

    if df.empty:
        failures.append("Accepted dataframe is empty.")
    if list(df.columns) != TARGET_COLUMNS:
        failures.append("Target column order is invalid.")
    if len(df.columns) <= 1:
        failures.append("Accepted dataframe has one column or fewer.")
    missing_metadata = []
    for column in ["trace_type", "source_month_folder"]:
        if column not in df.columns or df[column].isna().any() or (df[column] == "").any() or (df[column] == "Unknown").any():
            missing_metadata.append(column)
    if missing_metadata:
        failures.append(f"Missing or Unknown metadata values found in: {', '.join(missing_metadata)}.")

    for column in METRIC_COLUMNS:
        if column not in df.columns or not pd.api.types.is_numeric_dtype(df[column]):
            failures.append(f"Metric column is not numeric: {column}.")

    if "datetime" in df.columns:
        converted = pd.to_datetime(df["datetime"], errors="coerce")
        if converted.isna().any():
            failures.append("One or more accepted rows has an invalid datetime.")

    if {"source_file", "vm_id"}.issubset(df.columns):
        vm_counts = df.groupby("source_file")["vm_id"].nunique()
        bad_sources = vm_counts[vm_counts != 1]
        if not bad_sources.empty:
            failures.append(f"source_file maps to more than one vm_id: {bad_sources.index.tolist()}.")

    if failed_parse_rate > MAX_FAILED_PARSE_RATE:
        failures.append(
            f"Failed parse rate {failed_parse_rate:.2%} exceeds {MAX_FAILED_PARSE_RATE:.0%} maximum."
        )

    if failures:
        raise ValueError("Stage 1 ingestion validation failed:\n- " + "\n- ".join(failures))


def _parse_all(raw_files: list[Path], raw_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    frames: list[pd.DataFrame] = []
    summaries: list[dict[str, Any]] = []
    for path in raw_files:
        frame, summary = parse_trace_file(path, raw_root)
        if not frame.empty:
            frames.append(frame)
        summaries.append(summary)

    if frames:
        ingested = pd.concat(frames, ignore_index=True)
    else:
        ingested = pd.DataFrame(columns=TARGET_COLUMNS)
    return ingested, pd.DataFrame(summaries)


def _write_error_summary(error_summary: pd.DataFrame) -> None:
    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    error_summary.to_csv(ERROR_SUMMARY_OUTPUT, index=False)


def _print_summary(
    *,
    df: pd.DataFrame,
    error_summary: pd.DataFrame,
    raw_file_count: int,
    failed_parse_rate: float,
    stop_condition_passed: bool,
) -> None:
    accepted_rows = len(df)
    failed_rows = int(error_summary["failed_rows"].sum()) if "failed_rows" in error_summary else 0
    data_rows_seen = int(error_summary["data_rows_seen"].sum()) if "data_rows_seen" in error_summary else 0
    min_datetime = df["datetime"].min() if not df.empty else "None"
    max_datetime = df["datetime"].max() if not df.empty else "None"
    trace_types = ", ".join(sorted(df["trace_type"].dropna().unique())) if not df.empty else "None"
    month_folders = ", ".join(sorted(df["source_month_folder"].dropna().unique())) if not df.empty else "None"

    print("Stage 1 Bitbrains ingestion validation summary")
    print(f"- Raw CSV files discovered: {raw_file_count}")
    print(f"- Data rows seen: {data_rows_seen}")
    print(f"- Accepted rows: {accepted_rows}")
    print(f"- Failed parse rows: {failed_rows}")
    print(f"- Failed parse rate: {failed_parse_rate:.2%}")
    print(f"- Datetime range: {min_datetime} to {max_datetime}")
    print(f"- Unique trace types: {trace_types}")
    print(f"- Unique source month folders: {month_folders}")
    print(f"- Stop condition passed: {stop_condition_passed}")


def main() -> int:
    if not PROFILE_OUTPUT.exists():
        print(f"Stage 1 ingestion failed: required Stage 0 profile is missing at {PROFILE_OUTPUT}.")
        return 1

    raw_files = discover_raw_files(RAW_ROOT)
    if not raw_files:
        print(f"Stage 1 ingestion failed: no raw CSV files found under {RAW_ROOT}.")
        return 1

    df, error_summary = _parse_all(raw_files, RAW_ROOT)
    failed_rows = int(error_summary["failed_rows"].sum()) if "failed_rows" in error_summary else 0
    data_rows_seen = int(error_summary["data_rows_seen"].sum()) if "data_rows_seen" in error_summary else 0
    failed_parse_rate = failed_rows / data_rows_seen if data_rows_seen else 1.0

    try:
        validate_ingested(df, error_summary, failed_parse_rate=failed_parse_rate)
    except ValueError as exc:
        _write_error_summary(error_summary)
        _print_summary(
            df=df,
            error_summary=error_summary,
            raw_file_count=len(raw_files),
            failed_parse_rate=failed_parse_rate,
            stop_condition_passed=False,
        )
        print(str(exc))
        return 1

    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    df = df[TARGET_COLUMNS]
    df.to_parquet(CLEANED_OUTPUT, index=False)
    df.head(1000).to_csv(SAMPLE_OUTPUT, index=False)

    _print_summary(
        df=df,
        error_summary=error_summary,
        raw_file_count=len(raw_files),
        failed_parse_rate=failed_parse_rate,
        stop_condition_passed=True,
    )
    print(f"- Wrote cleaned dataset: {CLEANED_OUTPUT}")
    print(f"- Wrote sample CSV: {SAMPLE_OUTPUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
