from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "src" / "05_create_capacity_inventory.py"
INPUT = REPO_ROOT / "data" / "processed" / "cluster_monthly_metrics.csv"
OUTPUT = REPO_ROOT / "data" / "processed" / "capacity_inventory.csv"


@pytest.fixture(scope="module")
def inventory() -> pd.DataFrame:
    if not SCRIPT.exists():
        pytest.fail("Stage 5 implementation module is missing")
    result = subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True
    )
    assert result.returncode == 0, result.stderr
    return pd.read_csv(OUTPUT)


def test_output_file_exists(inventory: pd.DataFrame) -> None:
    assert OUTPUT.exists()


def test_one_row_per_cluster(inventory: pd.DataFrame) -> None:
    df_in = pd.read_csv(INPUT)
    assert len(inventory) == df_in["cluster_name"].nunique()


def test_no_duplicate_cluster_name(inventory: pd.DataFrame) -> None:
    assert inventory["cluster_name"].duplicated().sum() == 0


def test_inventory_type_column_exists_and_all_simulated(inventory: pd.DataFrame) -> None:
    assert "inventory_type" in inventory.columns
    assert inventory["inventory_type"].notna().all()
    assert (inventory["inventory_type"] == "Simulated").all()


def test_usable_capacity_less_than_raw(inventory: pd.DataFrame) -> None:
    assert (inventory["usable_capacity_tb"] < inventory["raw_capacity_tb"]).all()


def test_raw_capacity_within_range(inventory: pd.DataFrame) -> None:
    assert inventory["raw_capacity_tb"].between(800, 2500).all()


def test_metadata_overhead_within_range(inventory: pd.DataFrame) -> None:
    assert inventory["metadata_overhead_pct"].between(3, 6).all()


def test_protection_overhead_within_range(inventory: pd.DataFrame) -> None:
    assert inventory["protection_overhead_pct"].between(12, 22).all()


def test_reserved_capacity_within_range(inventory: pd.DataFrame) -> None:
    assert inventory["reserved_capacity_pct"].between(5, 10).all()


def test_output_is_deterministic() -> None:
    if not SCRIPT.exists():
        pytest.fail("Stage 5 implementation module is missing")
    subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, check=True)
    h1 = hashlib.md5(OUTPUT.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, check=True)
    h2 = hashlib.md5(OUTPUT.read_bytes()).hexdigest()
    assert h1 == h2
