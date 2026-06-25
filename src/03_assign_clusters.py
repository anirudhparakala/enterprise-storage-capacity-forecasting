from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


PROCESSED_ROOT = Path("data/processed")
INPUT_PATH = PROCESSED_ROOT / "vm_daily_metrics.csv"
OUTPUT_PATH = PROCESSED_ROOT / "vm_cluster_mapping.csv"

RANDOM_SEED = 42
DEFAULT_TARGET_CLUSTERS = 20

DATACENTERS = ["Memphis", "Indianapolis", "Dallas", "Atlanta"]
BUSINESS_UNITS = ["Logistics", "Operations", "Finance", "Customer Systems", "Analytics"]
STORAGE_PLATFORM_BY_TRACE_TYPE = {
    "fastStorage": "Fast SAN-style storage",
    "Rnd": "Mixed SAN/NAS-style storage",
}
CLUSTER_PREFIX_BY_TRACE_TYPE = {
    "fastStorage": "FS",
    "Rnd": "RND",
}

REQUIRED_INPUT_COLUMNS = ["vm_id", "trace_type"]
CLUSTER_MAPPING_COLUMNS = [
    "vm_id",
    "trace_type",
    "cluster_name",
    "datacenter",
    "business_unit",
    "storage_platform",
]


@dataclass(frozen=True)
class Stage3ValidationSummary:
    input_unique_vm_count: int
    output_mapping_row_count: int
    cluster_count: int
    cluster_names: list[str]
    vm_count_per_cluster: dict[str, int]
    unique_trace_types: list[str]
    unique_storage_platform_values: list[str]
    datacenter_distribution: dict[str, int]
    business_unit_distribution: dict[str, int]
    every_vm_appears_exactly_once: bool
    rnd_absence_documented: bool
    stop_condition_passed: bool


def validate_input(df: pd.DataFrame) -> None:
    failures: list[str] = []
    missing_columns = [column for column in REQUIRED_INPUT_COLUMNS if column not in df.columns]
    if missing_columns:
        failures.append(f"Missing required input columns: {', '.join(missing_columns)}.")

    if not missing_columns:
        for column in REQUIRED_INPUT_COLUMNS:
            values = df[column]
            if values.isna().any() or (values.astype(str).str.len() == 0).any():
                failures.append(f"Input column has missing values: {column}.")

        unknown_trace_types = sorted(set(df["trace_type"]) - set(STORAGE_PLATFORM_BY_TRACE_TYPE))
        if unknown_trace_types:
            failures.append(f"Unsupported trace_type values: {', '.join(unknown_trace_types)}.")

        trace_counts_per_vm = df.groupby("vm_id")["trace_type"].nunique()
        mixed_trace_vms = trace_counts_per_vm[trace_counts_per_vm != 1]
        if not mixed_trace_vms.empty:
            failures.append(f"VMs have multiple trace_type values: {mixed_trace_vms.index.tolist()}.")

    if failures:
        raise ValueError("Stage 3 cluster assignment input validation failed:\n- " + "\n- ".join(failures))


def _target_cluster_count(vm_count: int, desired_cluster_count: int = DEFAULT_TARGET_CLUSTERS) -> int:
    if vm_count <= 0:
        return 0
    if vm_count == 1:
        return 1
    if vm_count < desired_cluster_count * 2:
        return max(1, vm_count // 2)
    return desired_cluster_count


def _cluster_names(trace_type: str, cluster_count: int) -> list[str]:
    prefix = CLUSTER_PREFIX_BY_TRACE_TYPE[trace_type]
    return [f"{prefix}-CLUSTER-{idx:02d}" for idx in range(1, cluster_count + 1)]


def _cluster_dimensions(cluster_names: list[str]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "cluster_name": cluster_name,
                "datacenter": DATACENTERS[idx % len(DATACENTERS)],
                "business_unit": BUSINESS_UNITS[idx % len(BUSINESS_UNITS)],
            }
            for idx, cluster_name in enumerate(cluster_names)
        ]
    )


def _assign_trace_type_vms(vm_trace: pd.DataFrame, trace_type: str, rng: np.random.Generator) -> pd.DataFrame:
    trace_vms = vm_trace.loc[vm_trace["trace_type"] == trace_type, ["vm_id", "trace_type"]].sort_values("vm_id")
    vm_count = len(trace_vms)
    cluster_count = _target_cluster_count(vm_count)
    cluster_names = _cluster_names(trace_type, cluster_count)

    shuffled_positions = rng.permutation(vm_count)
    assignments = pd.DataFrame(
        {
            "vm_id": trace_vms.iloc[shuffled_positions]["vm_id"].to_numpy(),
            "trace_type": trace_type,
            "cluster_name": [cluster_names[idx % cluster_count] for idx in range(vm_count)],
        }
    )
    dimensions = _cluster_dimensions(cluster_names)
    assignments = assignments.merge(dimensions, on="cluster_name", how="left", validate="many_to_one")
    assignments["storage_platform"] = STORAGE_PLATFORM_BY_TRACE_TYPE[trace_type]
    return assignments[CLUSTER_MAPPING_COLUMNS]


def build_cluster_mapping(daily_metrics: pd.DataFrame) -> pd.DataFrame:
    validate_input(daily_metrics)
    vm_trace = daily_metrics[["vm_id", "trace_type"]].drop_duplicates().sort_values(["trace_type", "vm_id"])
    rng = np.random.default_rng(RANDOM_SEED)

    frames = []
    for trace_type in sorted(vm_trace["trace_type"].unique()):
        frames.append(_assign_trace_type_vms(vm_trace, trace_type, rng))

    mapping = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=CLUSTER_MAPPING_COLUMNS)
    return mapping.sort_values(["cluster_name", "vm_id"]).reset_index(drop=True)


def validate_cluster_mapping(daily_metrics: pd.DataFrame, mapping: pd.DataFrame) -> Stage3ValidationSummary:
    validate_input(daily_metrics)
    failures: list[str] = []

    input_vm_trace = daily_metrics[["vm_id", "trace_type"]].drop_duplicates().sort_values("vm_id").reset_index(drop=True)

    if list(mapping.columns) != CLUSTER_MAPPING_COLUMNS:
        failures.append("Cluster mapping output columns do not match the Stage 3 contract.")

    if len(mapping) != len(input_vm_trace) or not mapping["vm_id"].is_unique:
        failures.append("Every input VM must appear exactly once in the cluster mapping.")

    mapped_vm_trace = mapping[["vm_id", "trace_type"]].sort_values("vm_id").reset_index(drop=True)
    if not input_vm_trace.equals(mapped_vm_trace):
        failures.append("trace_type is not preserved for every VM.")

    missing_platforms = mapping["storage_platform"].isna().any() or (mapping["storage_platform"].astype(str).str.len() == 0).any()
    if missing_platforms:
        failures.append("storage_platform must be populated for every mapping row.")

    invalid_datacenters = sorted(set(mapping["datacenter"]) - set(DATACENTERS))
    if invalid_datacenters:
        failures.append(f"Invalid datacenter values: {', '.join(invalid_datacenters)}.")

    invalid_business_units = sorted(set(mapping["business_unit"]) - set(BUSINESS_UNITS))
    if invalid_business_units:
        failures.append(f"Invalid business_unit values: {', '.join(invalid_business_units)}.")

    cluster_sizes = mapping.groupby("cluster_name")["vm_id"].nunique().sort_index()
    if len(input_vm_trace) >= 2 * len(cluster_sizes) and (cluster_sizes < 2).any():
        failures.append("Every cluster must have multiple VMs when the VM count supports it.")

    rerun_mapping = build_cluster_mapping(daily_metrics)
    if not mapping.reset_index(drop=True).equals(rerun_mapping.reset_index(drop=True)):
        failures.append("Cluster assignment is not deterministic across reruns.")

    rnd_absent = "Rnd" not in set(input_vm_trace["trace_type"])
    summary = Stage3ValidationSummary(
        input_unique_vm_count=len(input_vm_trace),
        output_mapping_row_count=len(mapping),
        cluster_count=int(mapping["cluster_name"].nunique()),
        cluster_names=sorted(mapping["cluster_name"].unique().tolist()),
        vm_count_per_cluster={str(key): int(value) for key, value in cluster_sizes.to_dict().items()},
        unique_trace_types=sorted(mapping["trace_type"].unique().tolist()),
        unique_storage_platform_values=sorted(mapping["storage_platform"].unique().tolist()),
        datacenter_distribution={str(key): int(value) for key, value in mapping["datacenter"].value_counts().sort_index().to_dict().items()},
        business_unit_distribution={
            str(key): int(value) for key, value in mapping["business_unit"].value_counts().sort_index().to_dict().items()
        },
        every_vm_appears_exactly_once=not failures and len(mapping) == len(input_vm_trace) and mapping["vm_id"].is_unique,
        rnd_absence_documented=rnd_absent,
        stop_condition_passed=not failures,
    )

    if failures:
        raise ValueError("Stage 3 cluster assignment validation failed:\n- " + "\n- ".join(failures))
    return summary


def _format_distribution(distribution: dict[str, int]) -> str:
    return ", ".join(f"{key}: {value}" for key, value in distribution.items()) if distribution else "None"


def _print_summary(summary: Stage3ValidationSummary) -> None:
    print("Stage 3 simulated cluster assignment validation summary")
    print(f"- Input unique VM count: {summary.input_unique_vm_count}")
    print(f"- Output mapping row count: {summary.output_mapping_row_count}")
    print(f"- Number of clusters created: {summary.cluster_count}")
    print(f"- Cluster names: {', '.join(summary.cluster_names)}")
    print(f"- VM count per cluster: {_format_distribution(summary.vm_count_per_cluster)}")
    print(f"- Unique trace types: {', '.join(summary.unique_trace_types)}")
    print(f"- Unique storage_platform values: {', '.join(summary.unique_storage_platform_values)}")
    print(f"- Datacenter distribution: {_format_distribution(summary.datacenter_distribution)}")
    print(f"- Business unit distribution: {_format_distribution(summary.business_unit_distribution)}")
    print(f"- Every VM appears exactly once: {summary.every_vm_appears_exactly_once}")
    if "Rnd" not in summary.unique_trace_types:
        print("- Rnd trace type absent: only fastStorage-derived simulated clusters were created.")
    print(f"- Stop condition passed: {summary.stop_condition_passed}")


def main() -> int:
    if not INPUT_PATH.exists():
        print(f"Stage 3 cluster assignment failed: required Stage 2 output is missing at {INPUT_PATH}.")
        return 1

    try:
        daily_metrics = pd.read_csv(INPUT_PATH)
        mapping = build_cluster_mapping(daily_metrics)
        summary = validate_cluster_mapping(daily_metrics, mapping)
    except Exception as exc:
        print(str(exc))
        return 1

    PROCESSED_ROOT.mkdir(parents=True, exist_ok=True)
    mapping.to_csv(OUTPUT_PATH, index=False)
    _print_summary(summary)
    print(f"- Wrote VM cluster mapping: {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
