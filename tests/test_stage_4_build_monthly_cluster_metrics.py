from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "04_build_monthly_cluster_metrics.py"


def load_stage_4_module():
    if not MODULE_PATH.exists():
        pytest.fail("Stage 4 implementation module is missing")
    spec = importlib.util.spec_from_file_location("stage_4_build_monthly_cluster_metrics", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_vm_daily_metrics() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vm_id": "vm-1",
                "trace_type": "fastStorage",
                "date": "2013-08-12",
                "avg_memory_utilization_pct": 40.0,
                "p95_memory_utilization_pct": 50.0,
                "avg_disk_read_kbps": 1.0,
                "avg_disk_write_kbps": 3.0,
                "avg_disk_total_kbps": 4.0,
                "p95_disk_total_kbps": 5.0,
                "avg_network_total_kbps": 10.0,
                "high_disk_spike_count": 1,
            },
            {
                "vm_id": "vm-2",
                "trace_type": "fastStorage",
                "date": "2013-08-12",
                "avg_memory_utilization_pct": 80.0,
                "p95_memory_utilization_pct": 90.0,
                "avg_disk_read_kbps": 5.0,
                "avg_disk_write_kbps": 7.0,
                "avg_disk_total_kbps": 12.0,
                "p95_disk_total_kbps": 20.0,
                "avg_network_total_kbps": 14.0,
                "high_disk_spike_count": 2,
            },
            {
                "vm_id": "vm-1",
                "trace_type": "fastStorage",
                "date": "2013-08-13",
                "avg_memory_utilization_pct": 90.0,
                "p95_memory_utilization_pct": 95.0,
                "avg_disk_read_kbps": 9.0,
                "avg_disk_write_kbps": 1.0,
                "avg_disk_total_kbps": 10.0,
                "p95_disk_total_kbps": 30.0,
                "avg_network_total_kbps": 20.0,
                "high_disk_spike_count": 0,
            },
            {
                "vm_id": "vm-3",
                "trace_type": "fastStorage",
                "date": "2013-08-12",
                "avg_memory_utilization_pct": 55.0,
                "p95_memory_utilization_pct": 65.0,
                "avg_disk_read_kbps": 2.0,
                "avg_disk_write_kbps": 6.0,
                "avg_disk_total_kbps": 8.0,
                "p95_disk_total_kbps": 12.0,
                "avg_network_total_kbps": 11.0,
                "high_disk_spike_count": 4,
            },
        ]
    )


def make_cluster_mapping() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vm_id": "vm-1",
                "trace_type": "fastStorage",
                "cluster_name": "FS-CLUSTER-01",
                "datacenter": "Memphis",
                "business_unit": "Logistics",
                "storage_platform": "Fast SAN-style storage",
            },
            {
                "vm_id": "vm-2",
                "trace_type": "fastStorage",
                "cluster_name": "FS-CLUSTER-01",
                "datacenter": "Memphis",
                "business_unit": "Logistics",
                "storage_platform": "Fast SAN-style storage",
            },
            {
                "vm_id": "vm-3",
                "trace_type": "fastStorage",
                "cluster_name": "FS-CLUSTER-02",
                "datacenter": "Dallas",
                "business_unit": "Finance",
                "storage_platform": "Fast SAN-style storage",
            },
        ]
    )


def test_build_cluster_tables_aggregates_daily_metrics_and_derives_monthly_from_daily_table() -> None:
    module = load_stage_4_module()

    daily = module.build_cluster_daily_metrics(make_vm_daily_metrics(), make_cluster_mapping())
    monthly = module.build_cluster_monthly_metrics(daily)
    summary = module.validate_cluster_metrics(make_vm_daily_metrics(), make_cluster_mapping(), daily, monthly)

    assert list(daily.columns) == module.DAILY_OUTPUT_COLUMNS
    assert list(monthly.columns) == module.MONTHLY_OUTPUT_COLUMNS
    assert len(daily) == 3
    assert len(monthly) == 2
    assert daily.duplicated(["date", "cluster_name"]).sum() == 0
    assert monthly.duplicated(["month", "cluster_name"]).sum() == 0

    cluster_day = daily[(daily["date"] == "2013-08-12") & (daily["cluster_name"] == "FS-CLUSTER-01")].iloc[0]
    assert cluster_day["vm_count"] == 2
    assert cluster_day["avg_memory_utilization_pct"] == pytest.approx(60.0)
    assert cluster_day["p95_memory_utilization_pct"] == pytest.approx(70.0)
    assert cluster_day["avg_disk_total_kbps"] == pytest.approx(8.0)
    assert cluster_day["p95_disk_total_kbps"] == pytest.approx(12.5)
    assert cluster_day["avg_network_total_kbps"] == pytest.approx(12.0)
    assert cluster_day["high_disk_spike_count"] == 3

    cluster_month = monthly[(monthly["month"] == "2013-08-01") & (monthly["cluster_name"] == "FS-CLUSTER-01")].iloc[0]
    assert cluster_month["vm_count"] == 2
    assert cluster_month["avg_memory_utilization_pct"] == pytest.approx(75.0)
    assert cluster_month["p95_memory_utilization_pct"] == pytest.approx(82.5)
    assert cluster_month["avg_disk_read_kbps"] == pytest.approx(6.0)
    assert cluster_month["avg_disk_write_kbps"] == pytest.approx(3.0)
    assert cluster_month["avg_disk_total_kbps"] == pytest.approx(9.0)
    assert cluster_month["p95_disk_total_kbps"] == pytest.approx(21.25)
    assert cluster_month["avg_network_total_kbps"] == pytest.approx(16.0)
    assert cluster_month["high_disk_spike_count"] == 3

    assert summary.input_vm_daily_row_count == 4
    assert summary.input_cluster_mapping_row_count == 3
    assert summary.unmapped_vm_count == 0
    assert summary.daily_row_count == 3
    assert summary.monthly_row_count == 2
    assert summary.unique_cluster_count_daily == 2
    assert summary.unique_cluster_count_monthly == 2
    assert summary.duplicate_daily_key_rows == 0
    assert summary.duplicate_monthly_key_rows == 0
    assert summary.stop_condition_passed is True


def test_build_cluster_daily_metrics_rejects_unmapped_vms() -> None:
    module = load_stage_4_module()
    vm_daily_metrics = make_vm_daily_metrics()
    extra_vm = vm_daily_metrics.iloc[[0]].copy()
    extra_vm["vm_id"] = "vm-unmapped"
    vm_daily_metrics = pd.concat([vm_daily_metrics, extra_vm], ignore_index=True)

    with pytest.raises(ValueError, match="missing cluster mapping"):
        module.build_cluster_daily_metrics(vm_daily_metrics, make_cluster_mapping())


def test_build_cluster_monthly_metrics_uses_maximum_daily_vm_count_for_monthly_membership() -> None:
    module = load_stage_4_module()
    daily = module.build_cluster_daily_metrics(make_vm_daily_metrics(), make_cluster_mapping())
    extra_day = daily.iloc[[0]].copy()
    extra_day["date"] = "2013-08-14"
    extra_day["vm_count"] = 1
    extra_day["avg_memory_utilization_pct"] = 65.0
    extra_day["p95_memory_utilization_pct"] = 75.0
    extra_day["avg_disk_read_kbps"] = 3.5
    extra_day["avg_disk_write_kbps"] = 4.5
    extra_day["avg_disk_total_kbps"] = 8.0
    extra_day["p95_disk_total_kbps"] = 16.0
    extra_day["avg_network_total_kbps"] = 13.0
    extra_day["high_disk_spike_count"] = 1
    daily = pd.concat([daily, extra_day], ignore_index=True)

    monthly = module.build_cluster_monthly_metrics(daily)
    cluster_month = monthly[(monthly["month"] == "2013-08-01") & (monthly["cluster_name"] == "FS-CLUSTER-01")].iloc[0]

    assert cluster_month["vm_count"] == 2


@pytest.mark.parametrize(
    ("table_name", "mutator", "message"),
    [
        (
            "daily",
            lambda df: pd.concat([df, df.iloc[[0]]], ignore_index=True),
            "duplicate date \\+ cluster_name rows",
        ),
        (
            "monthly",
            lambda df: pd.concat([df, df.iloc[[0]]], ignore_index=True),
            "duplicate month \\+ cluster_name rows",
        ),
        (
            "daily",
            lambda df: df.assign(date=lambda frame: frame["date"].mask(frame.index == 0, "not-a-date")),
            "Daily output has invalid date values",
        ),
        (
            "monthly",
            lambda df: df.assign(month=lambda frame: frame["month"].mask(frame.index == 0, "2013-08-15")),
            "Monthly output has invalid month values",
        ),
        (
            "daily",
            lambda df: df.assign(cluster_name=lambda frame: frame["cluster_name"].mask(frame.index == 0, "")),
            "Daily output contains missing cluster_name values",
        ),
        (
            "monthly",
            lambda df: df.assign(cluster_name=lambda frame: frame["cluster_name"].mask(frame.index == 0, "")),
            "Monthly output contains missing cluster_name values",
        ),
        (
            "daily",
            lambda df: df.assign(
                p95_disk_total_kbps=lambda frame: frame["p95_disk_total_kbps"].astype(object).mask(frame.index == 0, "oops")
            ),
            "Daily output must contain numeric p95_disk_total_kbps",
        ),
        (
            "monthly",
            lambda df: df.assign(
                p95_disk_total_kbps=lambda frame: frame["p95_disk_total_kbps"].astype(object).mask(frame.index == 0, "oops")
            ),
            "Monthly output must contain numeric p95_disk_total_kbps",
        ),
        (
            "daily",
            lambda df: df.assign(vm_count=lambda frame: frame["vm_count"].mask(frame.index == 0, 0)),
            "Daily output contains non-positive vm_count values",
        ),
        (
            "monthly",
            lambda df: df.assign(vm_count=lambda frame: frame["vm_count"].mask(frame.index == 0, 0)),
            "Monthly output contains non-positive vm_count values",
        ),
    ],
)
def test_validate_cluster_metrics_rejects_stage_4_validation_gate_failures(table_name, mutator, message) -> None:
    module = load_stage_4_module()
    vm_daily_metrics = make_vm_daily_metrics()
    cluster_mapping = make_cluster_mapping()
    daily = module.build_cluster_daily_metrics(vm_daily_metrics, cluster_mapping)
    monthly = module.build_cluster_monthly_metrics(daily)

    if table_name == "daily":
        daily = mutator(daily)
    else:
        monthly = mutator(monthly)

    with pytest.raises(ValueError, match=message):
        module.validate_cluster_metrics(vm_daily_metrics, cluster_mapping, daily, monthly)


def test_validate_cluster_metrics_rejects_monthly_table_not_derived_from_daily_results() -> None:
    module = load_stage_4_module()
    vm_daily_metrics = make_vm_daily_metrics()
    cluster_mapping = make_cluster_mapping()
    daily = module.build_cluster_daily_metrics(vm_daily_metrics, cluster_mapping)
    monthly = module.build_cluster_monthly_metrics(daily)
    monthly.loc[monthly["cluster_name"] == "FS-CLUSTER-01", "avg_disk_total_kbps"] = 999.0

    with pytest.raises(ValueError, match="Monthly output is not derived from the daily cluster table"):
        module.validate_cluster_metrics(vm_daily_metrics, cluster_mapping, daily, monthly)
