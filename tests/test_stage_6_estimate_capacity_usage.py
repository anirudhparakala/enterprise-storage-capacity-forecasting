from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT   = Path(__file__).resolve().parents[1]
SCRIPT      = REPO_ROOT / "src" / "06_estimate_capacity_usage.py"
DAILY_OUT   = REPO_ROOT / "data" / "processed" / "cluster_capacity_daily.csv"
MONTHLY_OUT = REPO_ROOT / "data" / "processed" / "cluster_capacity_monthly.csv"

DAILY_REQUIRED_COLS = [
    "date", "cluster_name", "datacenter", "business_unit", "storage_platform",
    "usable_capacity_tb", "raw_capacity_tb",
    "daily_write_tb_estimate", "net_new_storage_tb",
    "starting_used_tb", "starting_utilization_tier",
    "used_capacity_tb", "free_capacity_tb", "capacity_utilization_pct",
]
MONTHLY_REQUIRED_COLS = [
    "month", "cluster_name", "datacenter", "business_unit", "storage_platform",
    "usable_capacity_tb", "raw_capacity_tb",
    "monthly_write_tb_estimate", "monthly_net_new_storage_tb",
    "starting_used_tb", "starting_utilization_tier",
    "used_capacity_tb", "free_capacity_tb", "capacity_utilization_pct",
]
VALID_TIERS = {"Low", "Watchlist", "Medium", "High"}


@pytest.fixture(scope="module")
def outputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SCRIPT.exists():
        pytest.fail("Stage 6 script not found")
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    daily   = pd.read_csv(DAILY_OUT,   parse_dates=["date"])
    monthly = pd.read_csv(MONTHLY_OUT)
    return daily, monthly


def test_output_files_exist(outputs: tuple) -> None:
    assert DAILY_OUT.exists()
    assert MONTHLY_OUT.exists()


def test_daily_required_columns(outputs: tuple) -> None:
    daily, _ = outputs
    for col in DAILY_REQUIRED_COLS:
        assert col in daily.columns, f"Missing column in daily: {col}"


def test_monthly_required_columns(outputs: tuple) -> None:
    _, monthly = outputs
    for col in MONTHLY_REQUIRED_COLS:
        assert col in monthly.columns, f"Missing column in monthly: {col}"


def test_starting_utilization_range(outputs: tuple) -> None:
    daily, _ = outputs
    per_cluster = daily.drop_duplicates("cluster_name")
    start_pct = per_cluster["starting_used_tb"] / per_cluster["usable_capacity_tb"] * 100
    assert start_pct.ge(35.0).all(), f"Some clusters start below 35%: {start_pct.min():.2f}%"
    assert start_pct.le(88.0).all(), f"Some clusters start above 88%: {start_pct.max():.2f}%"


def test_starting_utilization_tier_column_exists(outputs: tuple) -> None:
    daily, monthly = outputs
    assert "starting_utilization_tier" in daily.columns
    assert "starting_utilization_tier" in monthly.columns
    bad_daily   = set(daily["starting_utilization_tier"].unique()) - VALID_TIERS
    bad_monthly = set(monthly["starting_utilization_tier"].unique()) - VALID_TIERS
    assert not bad_daily,   f"Invalid tiers in daily: {bad_daily}"
    assert not bad_monthly, f"Invalid tiers in monthly: {bad_monthly}"


def test_not_every_cluster_high_risk(outputs: tuple) -> None:
    daily, _ = outputs
    per_cluster = daily.drop_duplicates("cluster_name")
    high_count = (per_cluster["starting_utilization_tier"] == "High").sum()
    assert high_count < len(per_cluster), "Every cluster is High risk — distribution is wrong"


def test_nonnegative_used_capacity(outputs: tuple) -> None:
    daily, _ = outputs
    assert (daily["used_capacity_tb"] >= 0).all(), "used_capacity_tb has negative values"


def test_capacity_joined_correctly_from_inventory(outputs: tuple) -> None:
    """usable_capacity_tb and raw_capacity_tb must match capacity_inventory."""
    daily, _ = outputs
    ci = pd.read_csv(REPO_ROOT / "data" / "processed" / "capacity_inventory.csv")
    merged = daily[["cluster_name", "usable_capacity_tb", "raw_capacity_tb"]].drop_duplicates()
    joined = merged.merge(ci[["cluster_name", "usable_capacity_tb", "raw_capacity_tb"]],
                          on="cluster_name", suffixes=("_daily", "_inv"))
    assert (joined["usable_capacity_tb_daily"] - joined["usable_capacity_tb_inv"]).abs().max() < 1e-9
    assert (joined["raw_capacity_tb_daily"]    - joined["raw_capacity_tb_inv"]).abs().max() < 1e-9


def test_daily_utilization_changes_over_time(outputs: tuple) -> None:
    daily, _ = outputs
    varying = (
        daily.groupby("cluster_name")["capacity_utilization_pct"]
        .nunique()
        .gt(1)
        .sum()
    )
    assert varying > 0, "No cluster shows utilisation change across days"


def test_some_clusters_above_75_pct(outputs: tuple) -> None:
    daily, _ = outputs
    latest = daily[daily["date"] == daily["date"].max()]
    count = int((latest["capacity_utilization_pct"] >= 75).sum())
    assert count > 0, f"No cluster is at or above 75% utilisation at latest date (max={latest['capacity_utilization_pct'].max():.2f}%)"


def test_some_clusters_above_80_pct(outputs: tuple) -> None:
    daily, _ = outputs
    latest = daily[daily["date"] == daily["date"].max()]
    count = int((latest["capacity_utilization_pct"] >= 80).sum())
    assert count > 0, f"No cluster is at or above 80% utilisation at latest date"


def test_some_clusters_above_85_pct(outputs: tuple) -> None:
    daily, _ = outputs
    latest = daily[daily["date"] == daily["date"].max()]
    count = int((latest["capacity_utilization_pct"] >= 85).sum())
    assert count >= 1, f"No cluster is at or above 85% utilisation at latest date"


def test_no_duplicate_date_cluster_in_daily(outputs: tuple) -> None:
    daily, _ = outputs
    dups = daily.duplicated(subset=["date", "cluster_name"]).sum()
    assert dups == 0, f"{dups} duplicate (date, cluster_name) rows in daily output"


def test_no_duplicate_month_cluster_in_monthly(outputs: tuple) -> None:
    _, monthly = outputs
    dups = monthly.duplicated(subset=["month", "cluster_name"]).sum()
    assert dups == 0, f"{dups} duplicate (month, cluster_name) rows in monthly output"


def test_monthly_derived_from_daily(outputs: tuple) -> None:
    """Monthly used_capacity_tb must equal the last day's value in daily for each cluster-month."""
    daily, monthly = outputs
    daily = daily.copy()
    daily["month"] = daily["date"].dt.to_period("M").astype(str)

    last_daily = (
        daily.sort_values("date")
        .groupby(["month", "cluster_name"])["used_capacity_tb"]
        .last()
        .reset_index()
        .rename(columns={"used_capacity_tb": "expected_used"})
    )
    check = monthly.merge(last_daily, on=["month", "cluster_name"])
    delta = (check["used_capacity_tb"] - check["expected_used"]).abs()
    assert delta.max() < 1e-9, (
        f"Monthly used_capacity_tb diverges from daily last-day value "
        f"(max delta {delta.max():.2e})"
    )


def test_monthly_write_sums_match_daily(outputs: tuple) -> None:
    """monthly_write_tb_estimate must equal sum of daily_write_tb_estimate per cluster-month."""
    daily, monthly = outputs
    daily = daily.copy()
    daily["month"] = daily["date"].dt.to_period("M").astype(str)

    daily_sums = (
        daily.groupby(["month", "cluster_name"])["daily_write_tb_estimate"]
        .sum()
        .reset_index()
        .rename(columns={"daily_write_tb_estimate": "expected_sum"})
    )
    check = monthly.merge(daily_sums, on=["month", "cluster_name"])
    delta = (check["monthly_write_tb_estimate"] - check["expected_sum"]).abs()
    assert delta.max() < 1e-9, (
        f"monthly_write_tb_estimate does not match daily sum (max delta {delta.max():.2e})"
    )


def test_deterministic_output() -> None:
    if not SCRIPT.exists():
        pytest.fail("Stage 6 script not found")
    subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, check=True)
    h1_d = hashlib.md5(DAILY_OUT.read_bytes()).hexdigest()
    h1_m = hashlib.md5(MONTHLY_OUT.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, check=True)
    h2_d = hashlib.md5(DAILY_OUT.read_bytes()).hexdigest()
    h2_m = hashlib.md5(MONTHLY_OUT.read_bytes()).hexdigest()
    assert h1_d == h2_d, "cluster_capacity_daily.csv is not deterministic"
    assert h1_m == h2_m, "cluster_capacity_monthly.csv is not deterministic"
