from __future__ import annotations

import math
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT   = Path(__file__).resolve().parents[1]
SCRIPT      = REPO_ROOT / "src" / "08_capacity_risk_scoring.py"
RISK_OUT    = REPO_ROOT / "data" / "processed" / "capacity_risk_summary.csv"
DAILY_IN    = REPO_ROOT / "data" / "processed" / "cluster_capacity_daily.csv"
FORECAST_IN = REPO_ROOT / "data" / "processed" / "forecast_results.csv"

REQUIRED_COLS = [
    "cluster_name", "datacenter", "business_unit", "storage_platform",
    "current_used_tb", "usable_capacity_tb", "current_utilization_pct",
    "forecast_30d_utilization_pct", "forecast_90d_utilization_pct",
    "forecast_180d_utilization_pct",
    "days_until_80_pct", "days_until_85_pct", "days_until_90_pct",
    "months_until_80_pct", "months_until_85_pct", "months_until_90_pct",
    "monthly_growth_tb", "risk_level", "recommended_action",
]

RISK_ACTION_MAP = {
    "Critical": "Expand capacity immediately and validate workload drivers.",
    "High":     "Plan capacity expansion within the next planning cycle.",
    "Medium":   "Monitor weekly and optimize storage overhead.",
    "Low":      "No immediate action required.",
}


@pytest.fixture(scope="module")
def risk_df() -> pd.DataFrame:
    if not SCRIPT.exists():
        pytest.fail(f"Stage 8 script not found: {SCRIPT}")
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"Script exited with code {result.returncode}.\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    return pd.read_csv(RISK_OUT)


# ---------------------------------------------------------------------------
# 1. Output file exists
# ---------------------------------------------------------------------------

def test_output_file_exists(risk_df: pd.DataFrame) -> None:
    assert RISK_OUT.exists(), f"Output file not found: {RISK_OUT}"


# ---------------------------------------------------------------------------
# 2. Required columns
# ---------------------------------------------------------------------------

def test_required_columns(risk_df: pd.DataFrame) -> None:
    for col in REQUIRED_COLS:
        assert col in risk_df.columns, f"Missing required column: {col}"


# ---------------------------------------------------------------------------
# 3. One row per cluster
# ---------------------------------------------------------------------------

def test_one_row_per_cluster(risk_df: pd.DataFrame) -> None:
    daily = pd.read_csv(DAILY_IN)
    expected_clusters = set(daily["cluster_name"].unique())
    actual_clusters   = set(risk_df["cluster_name"].unique())

    missing = expected_clusters - actual_clusters
    assert not missing, f"Clusters missing from output: {missing}"

    extra = actual_clusters - expected_clusters
    assert not extra, f"Unexpected clusters in output: {extra}"

    assert len(risk_df) == len(expected_clusters), (
        f"Expected {len(expected_clusters)} rows, got {len(risk_df)}"
    )


# ---------------------------------------------------------------------------
# 4. At least 2 distinct risk_level values
# ---------------------------------------------------------------------------

def test_risk_levels_not_all_same(risk_df: pd.DataFrame) -> None:
    unique_levels = risk_df["risk_level"].nunique()
    assert unique_levels >= 2, (
        f"Only {unique_levels} distinct risk_level value(s) found; expected >= 2"
    )


# ---------------------------------------------------------------------------
# 5. Critical clusters are assigned 'Critical' (not High/Medium/Low)
# ---------------------------------------------------------------------------

def test_critical_before_high_and_medium(risk_df: pd.DataFrame) -> None:
    critical_rows = risk_df[risk_df["risk_level"] == "Critical"]
    for _, row in critical_rows.iterrows():
        assert row["risk_level"] == "Critical", (
            f"Cluster {row['cluster_name']} should be Critical but got {row['risk_level']}"
        )


# ---------------------------------------------------------------------------
# 6. High rule fired correctly
# ---------------------------------------------------------------------------

def test_high_before_medium_and_low(risk_df: pd.DataFrame) -> None:
    high_rows = risk_df[risk_df["risk_level"] == "High"]
    # Skip check if all High clusters have util >= 85 (rule fired on current util)
    below_85_high = high_rows[high_rows["current_utilization_pct"] < 85]
    if below_85_high.empty:
        return
    # Those with util < 85 must have days_until_85_pct <= 180
    for _, row in below_85_high.iterrows():
        days = row["days_until_85_pct"]
        assert not (pd.isna(days) or float(days) > 180), (
            f"Cluster {row['cluster_name']} has risk_level=High but "
            f"current_utilization_pct={row['current_utilization_pct']:.2f} (<85) "
            f"and days_until_85_pct={days} (>180 or NaN)"
        )


# ---------------------------------------------------------------------------
# 7. Clusters >= 85% util are High or Critical
# ---------------------------------------------------------------------------

def test_clusters_above_85_are_high_or_critical(risk_df: pd.DataFrame) -> None:
    above_85 = risk_df[risk_df["current_utilization_pct"] >= 85]
    bad = above_85[~above_85["risk_level"].isin({"High", "Critical"})]
    assert bad.empty, (
        f"Clusters with utilization >= 85% not marked High/Critical:\n"
        f"{bad[['cluster_name', 'current_utilization_pct', 'risk_level']].to_string()}"
    )


# ---------------------------------------------------------------------------
# 8. Clusters >= 75% util are at least Medium
# ---------------------------------------------------------------------------

def test_clusters_above_75_are_at_least_medium(risk_df: pd.DataFrame) -> None:
    above_75 = risk_df[risk_df["current_utilization_pct"] >= 75]
    bad = above_75[~above_75["risk_level"].isin({"Medium", "High", "Critical"})]
    assert bad.empty, (
        f"Clusters with utilization >= 75% not marked Medium/High/Critical:\n"
        f"{bad[['cluster_name', 'current_utilization_pct', 'risk_level']].to_string()}"
    )


# ---------------------------------------------------------------------------
# 9. days_until == 0 when current utilization already exceeds threshold
# ---------------------------------------------------------------------------

def test_days_zero_when_utilization_already_exceeds_threshold(risk_df: pd.DataFrame) -> None:
    for thr in (80, 85, 90):
        col = f"days_until_{thr}_pct"
        already_over = risk_df[risk_df["current_utilization_pct"] >= thr]
        for _, row in already_over.iterrows():
            assert row[col] == 0, (
                f"Cluster {row['cluster_name']}: current_utilization_pct="
                f"{row['current_utilization_pct']:.2f} >= {thr} but {col}={row[col]}"
            )


# ---------------------------------------------------------------------------
# 10. months_until derived from days_until correctly
# ---------------------------------------------------------------------------

def test_months_derived_from_days(risk_df: pd.DataFrame) -> None:
    for thr in (80, 85, 90):
        d_col = f"days_until_{thr}_pct"
        m_col = f"months_until_{thr}_pct"
        for _, row in risk_df.iterrows():
            days   = row[d_col]
            months = row[m_col]
            days_is_nan   = pd.isna(days)
            months_is_nan = pd.isna(months)

            if days_is_nan:
                assert months_is_nan, (
                    f"Cluster {row['cluster_name']}: {d_col} is NaN but {m_col}={months}"
                )
            elif int(days) == 0:
                assert int(months) == 0, (
                    f"Cluster {row['cluster_name']}: {d_col}=0 but {m_col}={months}"
                )
            else:
                expected = math.ceil(int(days) / 30)
                assert int(months) == expected, (
                    f"Cluster {row['cluster_name']}: {d_col}={days} → expected "
                    f"{m_col}={expected}, got {months}"
                )


# ---------------------------------------------------------------------------
# 11. recommended_action maps exactly to risk_level; no nulls
# ---------------------------------------------------------------------------

def test_recommended_action_maps_to_risk_level(risk_df: pd.DataFrame) -> None:
    null_count = risk_df["recommended_action"].isnull().sum()
    assert null_count == 0, f"{null_count} null recommended_action value(s)"

    for _, row in risk_df.iterrows():
        expected = RISK_ACTION_MAP[row["risk_level"]]
        assert row["recommended_action"] == expected, (
            f"Cluster {row['cluster_name']}: risk_level={row['risk_level']} but "
            f"recommended_action='{row['recommended_action']}' "
            f"(expected '{expected}')"
        )


# ---------------------------------------------------------------------------
# 12. No Stage 9 files created
# ---------------------------------------------------------------------------

def test_no_stage9_file_created() -> None:
    stage9_src = list(REPO_ROOT.glob("src/09_*.py"))
    assert not stage9_src, (
        f"Unexpected Stage 9 source file(s) found: {stage9_src}"
    )
    stage9_processed_09 = list(REPO_ROOT.glob("data/processed/*09*"))
    assert not stage9_processed_09, (
        f"Unexpected Stage 9 output file(s) matching '*09*': {stage9_processed_09}"
    )
    stage9_processed_name = list(REPO_ROOT.glob("data/processed/*stage9*"))
    assert not stage9_processed_name, (
        f"Unexpected Stage 9 output file(s) matching '*stage9*': {stage9_processed_name}"
    )
