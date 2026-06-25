from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "03_assign_clusters.py"


def load_cluster_module():
    if not MODULE_PATH.exists():
        pytest.fail("Stage 3 implementation module is missing")
    spec = importlib.util.spec_from_file_location("stage_3_assign_clusters", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def make_daily_metrics(vm_count: int = 43) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "vm_id": [f"vm-{idx:03d}" for idx in range(1, vm_count + 1)],
            "trace_type": ["fastStorage"] * vm_count,
            "date": ["2013-08-12"] * vm_count,
            "avg_memory_utilization_pct": [50.0] * vm_count,
            "p95_memory_utilization_pct": [60.0] * vm_count,
            "avg_disk_read_kbps": [1.0] * vm_count,
            "avg_disk_write_kbps": [2.0] * vm_count,
            "avg_disk_total_kbps": [3.0] * vm_count,
            "p95_disk_total_kbps": [4.0] * vm_count,
            "avg_network_total_kbps": [5.0] * vm_count,
            "high_disk_spike_count": [1] * vm_count,
        }
    )


def test_build_cluster_mapping_is_deterministic_balanced_and_preserves_faststorage_metadata() -> None:
    module = load_cluster_module()
    daily = make_daily_metrics()

    first = module.build_cluster_mapping(daily)
    second = module.build_cluster_mapping(daily)

    pd.testing.assert_frame_equal(first, second)
    assert list(first.columns) == module.CLUSTER_MAPPING_COLUMNS
    assert len(first) == daily["vm_id"].nunique()
    assert first["vm_id"].is_unique
    assert first["trace_type"].unique().tolist() == ["fastStorage"]
    assert first["storage_platform"].unique().tolist() == ["Fast SAN-style storage"]
    assert first["cluster_name"].nunique() == module.DEFAULT_TARGET_CLUSTERS
    assert first["cluster_name"].str.startswith("FS-CLUSTER-").all()
    assert first.groupby("cluster_name")["vm_id"].nunique().min() > 1
    assert set(first["datacenter"]).issubset(set(module.DATACENTERS))
    assert set(first["business_unit"]).issubset(set(module.BUSINESS_UNITS))


def test_build_cluster_mapping_caps_cluster_count_when_vm_count_is_small() -> None:
    module = load_cluster_module()
    daily = make_daily_metrics(vm_count=5)

    mapping = module.build_cluster_mapping(daily)

    assert mapping["cluster_name"].nunique() == 2
    assert mapping.groupby("cluster_name")["vm_id"].nunique().min() >= 2


def test_validate_cluster_mapping_rejects_duplicate_vm_assignments() -> None:
    module = load_cluster_module()
    mapping = module.build_cluster_mapping(make_daily_metrics(vm_count=8))
    bad_mapping = pd.concat([mapping, mapping.iloc[[0]]], ignore_index=True)

    with pytest.raises(ValueError, match="exactly once"):
        module.validate_cluster_mapping(make_daily_metrics(vm_count=8), bad_mapping)
