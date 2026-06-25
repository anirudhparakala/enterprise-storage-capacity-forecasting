from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "02_feature_engineering.py"


def load_feature_module():
    if not MODULE_PATH.exists():
        pytest.fail("Stage 2 implementation module is missing")
    spec = importlib.util.spec_from_file_location("stage_2_feature_engineering", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_input_frame() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "vm_id": "vm-a",
                "trace_type": "fastStorage",
                "date": "2013-08-12",
                "memory_capacity_kb": 100.0,
                "memory_usage_kb": 50.0,
                "disk_read_kbps": 4.0,
                "disk_write_kbps": 6.0,
                "network_rx_kbps": 1.0,
                "network_tx_kbps": 2.0,
            },
            {
                "vm_id": "vm-a",
                "trace_type": "fastStorage",
                "date": "2013-08-12",
                "memory_capacity_kb": 100.0,
                "memory_usage_kb": 120.0,
                "disk_read_kbps": 10.0,
                "disk_write_kbps": 90.0,
                "network_rx_kbps": 3.0,
                "network_tx_kbps": 4.0,
            },
            {
                "vm_id": "vm-a",
                "trace_type": "fastStorage",
                "date": "2013-08-13",
                "memory_capacity_kb": 100.0,
                "memory_usage_kb": 70.0,
                "disk_read_kbps": 10.0,
                "disk_write_kbps": 20.0,
                "network_rx_kbps": 5.0,
                "network_tx_kbps": 6.0,
            },
            {
                "vm_id": "vm-b",
                "trace_type": "fastStorage",
                "date": "2013-08-12",
                "memory_capacity_kb": 0.0,
                "memory_usage_kb": 30.0,
                "disk_read_kbps": 0.0,
                "disk_write_kbps": 0.0,
                "network_rx_kbps": 7.0,
                "network_tx_kbps": 8.0,
            },
        ]
    )


def test_build_daily_metrics_calculates_features_and_daily_aggregates() -> None:
    module = load_feature_module()

    featured = module.add_workload_features(make_input_frame())
    daily = module.build_daily_metrics(featured)

    spike_row = featured.loc[featured["disk_total_kbps"] == 100.0].iloc[0]
    assert spike_row["disk_write_ratio"] == pytest.approx(0.9)
    assert spike_row["disk_read_ratio"] == pytest.approx(0.1)
    assert bool(spike_row["is_high_disk_spike"]) is True

    assert list(daily.columns) == module.DAILY_OUTPUT_COLUMNS
    assert len(daily) == 3
    assert daily.duplicated(["vm_id", "date"]).sum() == 0

    vm_a_day = daily[(daily["vm_id"] == "vm-a") & (daily["date"] == "2013-08-12")].iloc[0]
    assert vm_a_day["avg_memory_utilization_pct"] == pytest.approx(85.0)
    assert vm_a_day["p95_memory_utilization_pct"] == pytest.approx(116.5)
    assert vm_a_day["avg_disk_total_kbps"] == pytest.approx(55.0)
    assert vm_a_day["p95_disk_total_kbps"] == pytest.approx(95.5)
    assert vm_a_day["avg_network_total_kbps"] == pytest.approx(5.0)
    assert vm_a_day["high_disk_spike_count"] == 1


def test_validate_input_rejects_negative_disk_throughput() -> None:
    module = load_feature_module()
    df = make_input_frame()
    df.loc[0, "disk_write_kbps"] = -1.0

    with pytest.raises(ValueError, match="negative disk throughput"):
        module.validate_input(df)


def test_validation_summary_counts_memory_utilization_anomalies() -> None:
    module = load_feature_module()

    featured = module.add_workload_features(make_input_frame())
    daily = module.build_daily_metrics(featured)
    summary = module.validate_daily_metrics(featured, daily)

    assert summary.input_row_count == 4
    assert summary.output_row_count == 3
    assert summary.unique_vm_count == 2
    assert summary.duplicate_vm_date_rows == 0
    assert summary.negative_disk_throughput_count == 0
    assert summary.memory_utilization_anomaly_count == 1
    assert summary.total_high_disk_spike_count == 1
    assert summary.stop_condition_passed is True
