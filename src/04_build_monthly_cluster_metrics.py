from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PROCESSED_ROOT = Path("data/processed")
VM_DAILY_INPUT_PATH = PROCESSED_ROOT / "vm_daily_metrics.csv"
CLUSTER_MAPPING_INPUT_PATH = PROCESSED_ROOT / "vm_cluster_mapping.csv"
DAILY_OUTPUT_PATH = PROCESSED_ROOT / "cluster_daily_metrics.csv"
MONTHLY_OUTPUT_PATH = PROCESSED_ROOT / "cluster_monthly_metrics.csv"

REQUIRED_VM_DAILY_COLUMNS = [
    "vm_id",
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

REQUIRED_CLUSTER_MAPPING_COLUMNS = [
    "vm_id",
    "trace_type",
    "cluster_name",
    "datacenter",
    "business_unit",
    "storage_platform",
]

DAILY_DIMENSION_COLUMNS = ["date", "cluster_name", "datacenter", "business_unit", "storage_platform"]
MONTHLY_DIMENSION_COLUMNS = ["month", "cluster_name", "datacenter", "business_unit", "storage_platform"]
AGGREGATED_METRIC_COLUMNS = [
    "avg_memory_utilization_pct",
    "p95_memory_utilization_pct",
    "avg_disk_read_kbps",
    "avg_disk_write_kbps",
    "avg_disk_total_kbps",
    "p95_disk_total_kbps",
    "avg_network_total_kbps",
    "high_disk_spike_count",
]

DAILY_OUTPUT_COLUMNS = [
    "date",
    "cluster_name",
    "datacenter",
    "business_unit",
    "storage_platform",
    "vm_count",
    "avg_memory_utilization_pct",
    "p95_memory_utilization_pct",
    "avg_disk_read_kbps",
    "avg_disk_write_kbps",
    "avg_disk_total_kbps",
    "p95_disk_total_kbps",
    "avg_network_total_kbps",
    "high_disk_spike_count",
]

MONTHLY_OUTPUT_COLUMNS = [
    "month",
    "cluster_name",
    "datacenter",
    "business_unit",
    "storage_platform",
    "vm_count",
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
class Stage4ValidationSummary:
    input_vm_daily_row_count: int
    input_cluster_mapping_row_count: int
    unmapped_vm_count: int
    daily_row_count: int
    monthly_row_count: int
    unique_cluster_count_daily: int
    unique_cluster_count_monthly: int
    daily_date_range: str
    monthly_month_range: str
    duplicate_daily_key_rows: int
    duplicate_monthly_key_rows: int
    min_vm_count: int
    max_vm_count: int
    stop_condition_passed: bool


def _monthly_vm_count_from_max_daily_membership(vm_counts: pd.Series) -> int:
    """Monthly vm_count comes from the peak observed daily cluster membership in the daily table."""
    return int(vm_counts.max())


def _validate_required_columns(df: pd.DataFrame, required_columns: list[str], label: str) -> None:
    missing_columns = [column for column in required_columns if column not in df.columns]
    if missing_columns:
        raise ValueError(f"Stage 4 cluster metrics input validation failed: missing {label} columns: {', '.join(missing_columns)}.")


def validate_inputs(vm_daily_metrics: pd.DataFrame, cluster_mapping: pd.DataFrame) -> None:
    failures: list[str] = []

    try:
        _validate_required_columns(vm_daily_metrics, REQUIRED_VM_DAILY_COLUMNS, "vm daily metrics")
        _validate_required_columns(cluster_mapping, REQUIRED_CLUSTER_MAPPING_COLUMNS, "cluster mapping")
    except ValueError as exc:
        failures.append(str(exc))

    if not failures:
        if cluster_mapping["vm_id"].duplicated().any():
            failures.append("Cluster mapping must contain exactly one row per vm_id.")

        for column in ["vm_id", "date"]:
            values = vm_daily_metrics[column]
            if values.isna().any() or (values.astype(str).str.len() == 0).any():
                failures.append(f"VM daily metrics column has missing values: {column}.")

        for column in ["vm_id", "cluster_name", "datacenter", "business_unit", "storage_platform"]:
            values = cluster_mapping[column]
            if values.isna().any() or (values.astype(str).str.len() == 0).any():
                failures.append(f"Cluster mapping column has missing values: {column}.")

        numeric_columns = [column for column in AGGREGATED_METRIC_COLUMNS if column != "high_disk_spike_count"]
        numeric_columns.append("high_disk_spike_count")
        for column in numeric_columns:
            if column in vm_daily_metrics.columns and not pd.api.types.is_numeric_dtype(vm_daily_metrics[column]):
                failures.append(f"VM daily metrics column is not numeric: {column}.")

    if failures:
        raise ValueError("Stage 4 cluster metrics input validation failed:\n- " + "\n- ".join(failures))


def _merge_vm_daily_with_cluster_mapping(vm_daily_metrics: pd.DataFrame, cluster_mapping: pd.DataFrame) -> pd.DataFrame:
    validate_inputs(vm_daily_metrics, cluster_mapping)
    joined = vm_daily_metrics.merge(
        cluster_mapping,
        on="vm_id",
        how="left",
        validate="many_to_one",
        suffixes=("", "_mapping"),
    )

    unmapped_vm_count = int(joined["cluster_name"].isna().sum())
    if unmapped_vm_count:
        raise ValueError(
            f"Stage 4 cluster metrics build failed: {unmapped_vm_count} VM daily rows are missing cluster mapping values."
        )

    if "trace_type" in vm_daily_metrics.columns and "trace_type_mapping" in joined.columns:
        mismatched = joined["trace_type"] != joined["trace_type_mapping"]
        if mismatched.any():
            raise ValueError("Stage 4 cluster metrics build failed: vm_id trace_type values do not match cluster mapping.")

    joined["date"] = pd.to_datetime(joined["date"], format="%Y-%m-%d", errors="raise")
    return joined


def build_cluster_daily_metrics(vm_daily_metrics: pd.DataFrame, cluster_mapping: pd.DataFrame) -> pd.DataFrame:
    joined = _merge_vm_daily_with_cluster_mapping(vm_daily_metrics, cluster_mapping)
    daily = (
        joined.groupby(DAILY_DIMENSION_COLUMNS, as_index=False)
        .agg(
            vm_count=("vm_id", "nunique"),
            avg_memory_utilization_pct=("avg_memory_utilization_pct", "mean"),
            p95_memory_utilization_pct=("p95_memory_utilization_pct", "mean"),
            avg_disk_read_kbps=("avg_disk_read_kbps", "mean"),
            avg_disk_write_kbps=("avg_disk_write_kbps", "mean"),
            avg_disk_total_kbps=("avg_disk_total_kbps", "mean"),
            p95_disk_total_kbps=("p95_disk_total_kbps", "mean"),
            avg_network_total_kbps=("avg_network_total_kbps", "mean"),
            high_disk_spike_count=("high_disk_spike_count", "sum"),
        )
        .sort_values(["date", "cluster_name", "datacenter", "business_unit", "storage_platform"])
        .reset_index(drop=True)
    )

    daily["date"] = daily["date"].dt.strftime("%Y-%m-%d")
    daily["vm_count"] = daily["vm_count"].astype(int)
    daily["high_disk_spike_count"] = daily["high_disk_spike_count"].astype(int)
    return daily[DAILY_OUTPUT_COLUMNS]


def build_cluster_monthly_metrics(cluster_daily_metrics: pd.DataFrame) -> pd.DataFrame:
    _validate_required_columns(cluster_daily_metrics, DAILY_OUTPUT_COLUMNS, "cluster daily metrics")
    daily_with_month = cluster_daily_metrics.copy()
    daily_with_month["date"] = pd.to_datetime(daily_with_month["date"], format="%Y-%m-%d", errors="raise")
    daily_with_month["month"] = daily_with_month["date"].dt.to_period("M").dt.to_timestamp()

    monthly = (
        daily_with_month.groupby(MONTHLY_DIMENSION_COLUMNS, as_index=False)
        .agg(
            vm_count=("vm_count", _monthly_vm_count_from_max_daily_membership),
            avg_memory_utilization_pct=("avg_memory_utilization_pct", "mean"),
            p95_memory_utilization_pct=("p95_memory_utilization_pct", "mean"),
            avg_disk_read_kbps=("avg_disk_read_kbps", "mean"),
            avg_disk_write_kbps=("avg_disk_write_kbps", "mean"),
            avg_disk_total_kbps=("avg_disk_total_kbps", "mean"),
            p95_disk_total_kbps=("p95_disk_total_kbps", "mean"),
            avg_network_total_kbps=("avg_network_total_kbps", "mean"),
            high_disk_spike_count=("high_disk_spike_count", "sum"),
        )
        .sort_values(["month", "cluster_name", "datacenter", "business_unit", "storage_platform"])
        .reset_index(drop=True)
    )

    monthly["month"] = monthly["month"].dt.strftime("%Y-%m-01")
    monthly["vm_count"] = monthly["vm_count"].astype(int)
    monthly["high_disk_spike_count"] = monthly["high_disk_spike_count"].astype(int)
    return monthly[MONTHLY_OUTPUT_COLUMNS]


def _validate_output_table(
    df: pd.DataFrame,
    *,
    label: str,
    date_column: str,
    failures: list[str],
) -> bool:
    is_valid = True

    if df["cluster_name"].isna().any() or (df["cluster_name"].astype(str).str.len() == 0).any():
        failures.append(f"{label.capitalize()} output contains missing cluster_name values.")
        is_valid = False

    try:
        parsed_dates = pd.to_datetime(df[date_column], format="%Y-%m-%d", errors="raise")
        if label == "monthly" and not parsed_dates.dt.is_month_start.all():
            failures.append("Monthly output has invalid month values.")
            is_valid = False
    except Exception:
        failures.append(f"{label.capitalize()} output has invalid {date_column} values.")
        is_valid = False

    if "p95_disk_total_kbps" not in df.columns or not pd.api.types.is_numeric_dtype(df["p95_disk_total_kbps"]):
        failures.append(f"{label.capitalize()} output must contain numeric p95_disk_total_kbps.")
        is_valid = False

    if (df["vm_count"] <= 0).any():
        failures.append(f"{label.capitalize()} output contains non-positive vm_count values.")
        is_valid = False

    return is_valid


def validate_cluster_metrics(
    vm_daily_metrics: pd.DataFrame,
    cluster_mapping: pd.DataFrame,
    cluster_daily_metrics: pd.DataFrame,
    cluster_monthly_metrics: pd.DataFrame,
) -> Stage4ValidationSummary:
    validate_inputs(vm_daily_metrics, cluster_mapping)
    failures: list[str] = []

    unmapped_check = vm_daily_metrics.merge(cluster_mapping[["vm_id"]], on="vm_id", how="left", indicator=True)
    unmapped_vm_count = int((unmapped_check["_merge"] != "both").sum())

    if list(cluster_daily_metrics.columns) != DAILY_OUTPUT_COLUMNS:
        failures.append("Daily output columns do not match the Stage 4 contract.")
    if list(cluster_monthly_metrics.columns) != MONTHLY_OUTPUT_COLUMNS:
        failures.append("Monthly output columns do not match the Stage 4 contract.")

    duplicate_daily_key_rows = int(cluster_daily_metrics.duplicated(["date", "cluster_name"]).sum())
    duplicate_monthly_key_rows = int(cluster_monthly_metrics.duplicated(["month", "cluster_name"]).sum())
    if duplicate_daily_key_rows:
        failures.append(f"Found {duplicate_daily_key_rows} duplicate date + cluster_name rows.")
    if duplicate_monthly_key_rows:
        failures.append(f"Found {duplicate_monthly_key_rows} duplicate month + cluster_name rows.")

    daily_output_valid = _validate_output_table(
        cluster_daily_metrics,
        label="daily",
        date_column="date",
        failures=failures,
    )
    _validate_output_table(
        cluster_monthly_metrics,
        label="monthly",
        date_column="month",
        failures=failures,
    )

    if daily_output_valid:
        rebuilt_monthly = build_cluster_monthly_metrics(cluster_daily_metrics)
        if not rebuilt_monthly.reset_index(drop=True).equals(cluster_monthly_metrics.reset_index(drop=True)):
            failures.append("Monthly output is not derived from the daily cluster table.")

    min_date = cluster_daily_metrics["date"].min() if not cluster_daily_metrics.empty else "None"
    max_date = cluster_daily_metrics["date"].max() if not cluster_daily_metrics.empty else "None"
    min_month = cluster_monthly_metrics["month"].min() if not cluster_monthly_metrics.empty else "None"
    max_month = cluster_monthly_metrics["month"].max() if not cluster_monthly_metrics.empty else "None"
    min_vm_count = int(min(cluster_daily_metrics["vm_count"].min(), cluster_monthly_metrics["vm_count"].min()))
    max_vm_count = int(max(cluster_daily_metrics["vm_count"].max(), cluster_monthly_metrics["vm_count"].max()))

    summary = Stage4ValidationSummary(
        input_vm_daily_row_count=len(vm_daily_metrics),
        input_cluster_mapping_row_count=len(cluster_mapping),
        unmapped_vm_count=unmapped_vm_count,
        daily_row_count=len(cluster_daily_metrics),
        monthly_row_count=len(cluster_monthly_metrics),
        unique_cluster_count_daily=int(cluster_daily_metrics["cluster_name"].nunique()),
        unique_cluster_count_monthly=int(cluster_monthly_metrics["cluster_name"].nunique()),
        daily_date_range=f"{min_date} to {max_date}",
        monthly_month_range=f"{min_month} to {max_month}",
        duplicate_daily_key_rows=duplicate_daily_key_rows,
        duplicate_monthly_key_rows=duplicate_monthly_key_rows,
        min_vm_count=min_vm_count,
        max_vm_count=max_vm_count,
        stop_condition_passed=not failures and unmapped_vm_count == 0,
    )

    if unmapped_vm_count:
        failures.append(f"Found {unmapped_vm_count} VM daily rows without a cluster mapping.")
    if failures:
        raise ValueError("Stage 4 cluster metrics validation failed:\n- " + "\n- ".join(failures))
    return summary


def _rows_preview(df: pd.DataFrame) -> str:
    if df.empty:
        return "[]"
    return str(df.head().to_dict(orient="records"))


def _print_summary(summary: Stage4ValidationSummary, cluster_daily_metrics: pd.DataFrame, cluster_monthly_metrics: pd.DataFrame) -> None:
    print("Stage 4 cluster metrics validation summary")
    print(f"- Input VM daily row count: {summary.input_vm_daily_row_count}")
    print(f"- Input cluster mapping row count: {summary.input_cluster_mapping_row_count}")
    print(f"- Unmapped VM count after join: {summary.unmapped_vm_count}")
    print(f"- Daily row count: {summary.daily_row_count}")
    print(f"- Monthly row count: {summary.monthly_row_count}")
    print(f"- Unique cluster count in daily output: {summary.unique_cluster_count_daily}")
    print(f"- Unique cluster count in monthly output: {summary.unique_cluster_count_monthly}")
    print(f"- Daily date range: {summary.daily_date_range}")
    print(f"- Monthly month range: {summary.monthly_month_range}")
    print(f"- Duplicate daily key rows: {summary.duplicate_daily_key_rows}")
    print(f"- Duplicate monthly key rows: {summary.duplicate_monthly_key_rows}")
    print(f"- Min vm_count: {summary.min_vm_count}")
    print(f"- Max vm_count: {summary.max_vm_count}")
    print(f"- Daily output columns: {', '.join(cluster_daily_metrics.columns)}")
    print(f"- Monthly output columns: {', '.join(cluster_monthly_metrics.columns)}")
    print(f"- First 5 daily rows: {_rows_preview(cluster_daily_metrics)}")
    print(f"- First 5 monthly rows: {_rows_preview(cluster_monthly_metrics)}")
    print(f"- Stage 4 stop condition passed: {summary.stop_condition_passed}")


def main() -> int:
    missing_inputs = [path for path in [VM_DAILY_INPUT_PATH, CLUSTER_MAPPING_INPUT_PATH] if not path.exists()]
    if missing_inputs:
        print(
            "Stage 4 cluster metrics failed: required input is missing at "
            + ", ".join(str(path) for path in missing_inputs)
            + "."
        )
        return 1

    try:
        vm_daily_metrics = pd.read_csv(VM_DAILY_INPUT_PATH)
        cluster_mapping = pd.read_csv(CLUSTER_MAPPING_INPUT_PATH)
        cluster_daily_metrics = build_cluster_daily_metrics(vm_daily_metrics, cluster_mapping)
        cluster_monthly_metrics = build_cluster_monthly_metrics(cluster_daily_metrics)
        summary = validate_cluster_metrics(vm_daily_metrics, cluster_mapping, cluster_daily_metrics, cluster_monthly_metrics)
    except Exception as exc:
        print(str(exc))
        return 1

    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    cluster_daily_metrics.to_csv(DAILY_OUTPUT_PATH, index=False)
    cluster_monthly_metrics.to_csv(MONTHLY_OUTPUT_PATH, index=False)
    _print_summary(summary, cluster_daily_metrics, cluster_monthly_metrics)
    print(f"- Wrote daily cluster metrics: {DAILY_OUTPUT_PATH}")
    print(f"- Wrote monthly cluster metrics: {MONTHLY_OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
