"""Tests for Stage 9: Generate Power BI export tables."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT    = REPO_ROOT / "src" / "09_generate_powerbi_tables.py"
PROC_DIR  = REPO_ROOT / "data" / "processed"

PBI_FILES = {
    "pbi_cluster_daily_metrics":    PROC_DIR / "pbi_cluster_daily_metrics.csv",
    "pbi_cluster_monthly_metrics":  PROC_DIR / "pbi_cluster_monthly_metrics.csv",
    "pbi_capacity_inventory":       PROC_DIR / "pbi_capacity_inventory.csv",
    "pbi_cluster_capacity_daily":   PROC_DIR / "pbi_cluster_capacity_daily.csv",
    "pbi_cluster_capacity_monthly": PROC_DIR / "pbi_cluster_capacity_monthly.csv",
    "pbi_forecast_results":         PROC_DIR / "pbi_forecast_results.csv",
    "pbi_model_backtest_results":   PROC_DIR / "pbi_model_backtest_results.csv",
    "pbi_capacity_risk_summary":    PROC_DIR / "pbi_capacity_risk_summary.csv",
}

SOURCE_FILES = {
    "pbi_cluster_daily_metrics":    PROC_DIR / "cluster_daily_metrics.csv",
    "pbi_cluster_monthly_metrics":  PROC_DIR / "cluster_monthly_metrics.csv",
    "pbi_capacity_inventory":       PROC_DIR / "capacity_inventory.csv",
    "pbi_cluster_capacity_daily":   PROC_DIR / "cluster_capacity_daily.csv",
    "pbi_cluster_capacity_monthly": PROC_DIR / "cluster_capacity_monthly.csv",
    "pbi_forecast_results":         PROC_DIR / "forecast_results.csv",
    "pbi_model_backtest_results":   PROC_DIR / "model_backtest_results.csv",
    "pbi_capacity_risk_summary":    PROC_DIR / "capacity_risk_summary.csv",
}

KEY_COLUMNS = {
    "pbi_cluster_daily_metrics":    ["date", "cluster_name", "avg_memory_utilization_pct"],
    "pbi_cluster_monthly_metrics":  ["month", "cluster_name", "avg_memory_utilization_pct"],
    "pbi_capacity_inventory":       ["cluster_name", "usable_capacity_tb", "protection_overhead_pct"],
    "pbi_cluster_capacity_daily":   ["date", "cluster_name", "capacity_utilization_pct", "starting_utilization_tier"],
    "pbi_cluster_capacity_monthly": ["month", "cluster_name", "capacity_utilization_pct", "starting_utilization_tier"],
    "pbi_forecast_results":         ["cluster_name", "forecast_date", "forecast_utilization_pct"],
    "pbi_model_backtest_results":   ["cluster_name", "model_name", "mae", "rmse"],
    "pbi_capacity_risk_summary":    ["cluster_name", "risk_level", "recommended_action"],
}

PCT_COLUMNS = {
    "pbi_cluster_daily_metrics":    ["avg_memory_utilization_pct", "p95_memory_utilization_pct"],
    "pbi_cluster_monthly_metrics":  ["avg_memory_utilization_pct", "p95_memory_utilization_pct"],
    "pbi_capacity_inventory":       ["protection_overhead_pct", "metadata_overhead_pct", "reserved_capacity_pct"],
    "pbi_cluster_capacity_daily":   ["capacity_utilization_pct"],
    "pbi_cluster_capacity_monthly": ["capacity_utilization_pct"],
    "pbi_forecast_results":         ["forecast_utilization_pct"],
    "pbi_capacity_risk_summary":    [
        "current_utilization_pct",
        "forecast_30d_utilization_pct",
        "forecast_90d_utilization_pct",
        "forecast_180d_utilization_pct",
    ],
}


@pytest.fixture(scope="module")
def pbi_tables(tmp_path_factory):
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, (
        f"Stage 9 script failed.\nSTDOUT: {result.stdout}\nSTDERR: {result.stderr}"
    )
    tables = {}
    for name, path in PBI_FILES.items():
        tables[name] = pd.read_csv(path)
    return tables


# ---------------------------------------------------------------------------
# 1. All 8 pbi_ output files exist
# ---------------------------------------------------------------------------

def test_all_pbi_files_exist(pbi_tables) -> None:
    for name, path in PBI_FILES.items():
        assert path.exists(), f"Expected PBI output file not found: {path}"


# ---------------------------------------------------------------------------
# 2. No Unnamed index columns
# ---------------------------------------------------------------------------

def test_no_unnamed_index_columns(pbi_tables) -> None:
    for name, df in pbi_tables.items():
        unnamed = [c for c in df.columns if c.lower().startswith("unnamed:")]
        assert not unnamed, f"{name}: contains Unnamed columns: {unnamed}"


# ---------------------------------------------------------------------------
# 3. Row counts match source
# ---------------------------------------------------------------------------

def test_row_counts_match_source(pbi_tables) -> None:
    for name, pbi_df in pbi_tables.items():
        src_df = pd.read_csv(SOURCE_FILES[name])
        assert len(pbi_df) == len(src_df), (
            f"{name}: row count {len(pbi_df)} != source row count {len(src_df)}"
        )


# ---------------------------------------------------------------------------
# 4. Required key columns exist
# ---------------------------------------------------------------------------

def test_required_key_columns_exist(pbi_tables) -> None:
    for name, df in pbi_tables.items():
        for col in KEY_COLUMNS[name]:
            assert col in df.columns, f"{name}: missing required column '{col}'"


# ---------------------------------------------------------------------------
# 5. Daily tables have a date column
# ---------------------------------------------------------------------------

def test_daily_tables_have_date_column(pbi_tables) -> None:
    for name in ("pbi_cluster_daily_metrics", "pbi_cluster_capacity_daily"):
        assert "date" in pbi_tables[name].columns, f"{name}: missing 'date' column"


# ---------------------------------------------------------------------------
# 6. Monthly tables have a month column
# ---------------------------------------------------------------------------

def test_monthly_tables_have_month_column(pbi_tables) -> None:
    for name in ("pbi_cluster_monthly_metrics", "pbi_cluster_capacity_monthly"):
        assert "month" in pbi_tables[name].columns, f"{name}: missing 'month' column"


# ---------------------------------------------------------------------------
# 7. Forecast table has forecast_date column
# ---------------------------------------------------------------------------

def test_forecast_table_has_forecast_date(pbi_tables) -> None:
    df = pbi_tables["pbi_forecast_results"]
    assert "forecast_date" in df.columns, "pbi_forecast_results: missing 'forecast_date' column"


# ---------------------------------------------------------------------------
# 8. Risk summary has risk_level and recommended_action with no nulls
# ---------------------------------------------------------------------------

def test_risk_summary_has_risk_level_and_recommended_action(pbi_tables) -> None:
    df = pbi_tables["pbi_capacity_risk_summary"]
    assert "risk_level" in df.columns, "pbi_capacity_risk_summary: missing 'risk_level' column"
    assert "recommended_action" in df.columns, (
        "pbi_capacity_risk_summary: missing 'recommended_action' column"
    )
    null_count = df["recommended_action"].isnull().sum()
    assert null_count == 0, (
        f"pbi_capacity_risk_summary: {null_count} null value(s) in 'recommended_action'"
    )


# ---------------------------------------------------------------------------
# 9. Percentage fields are in 0–100 range (ignoring NaN)
# ---------------------------------------------------------------------------

def test_percentage_fields_in_0_to_100_range(pbi_tables) -> None:
    for name, cols in PCT_COLUMNS.items():
        df = pbi_tables[name]
        for col in cols:
            series = df[col].dropna()
            if series.empty:
                continue
            assert series.min() >= 0, (
                f"{name}.{col}: min value {series.min()} is below 0"
            )
            assert series.max() <= 100, (
                f"{name}.{col}: max value {series.max()} exceeds 100"
            )


# ---------------------------------------------------------------------------
# 10. starting_utilization_tier preserved with no nulls — daily
# ---------------------------------------------------------------------------

def test_starting_utilization_tier_preserved_daily(pbi_tables) -> None:
    df = pbi_tables["pbi_cluster_capacity_daily"]
    assert "starting_utilization_tier" in df.columns, (
        "pbi_cluster_capacity_daily: missing 'starting_utilization_tier' column"
    )
    null_count = df["starting_utilization_tier"].isnull().sum()
    assert null_count == 0, (
        f"pbi_cluster_capacity_daily: {null_count} null(s) in 'starting_utilization_tier'"
    )


# ---------------------------------------------------------------------------
# 11. starting_utilization_tier preserved with no nulls — monthly
# ---------------------------------------------------------------------------

def test_starting_utilization_tier_preserved_monthly(pbi_tables) -> None:
    df = pbi_tables["pbi_cluster_capacity_monthly"]
    assert "starting_utilization_tier" in df.columns, (
        "pbi_cluster_capacity_monthly: missing 'starting_utilization_tier' column"
    )
    null_count = df["starting_utilization_tier"].isnull().sum()
    assert null_count == 0, (
        f"pbi_cluster_capacity_monthly: {null_count} null(s) in 'starting_utilization_tier'"
    )


# ---------------------------------------------------------------------------
# 12. Date format in daily tables matches YYYY-MM-DD
# ---------------------------------------------------------------------------

def test_date_format_daily_tables(pbi_tables) -> None:
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    for name in ("pbi_cluster_daily_metrics", "pbi_cluster_capacity_daily"):
        df = pbi_tables[name]
        bad = [v for v in df["date"].dropna() if not pattern.match(str(v))]
        assert not bad, f"{name}: 'date' values not matching YYYY-MM-DD: {bad[:5]}"


# ---------------------------------------------------------------------------
# 13. Date format in monthly tables matches YYYY-MM-01
# ---------------------------------------------------------------------------

def test_date_format_monthly_tables(pbi_tables) -> None:
    pattern = re.compile(r"^\d{4}-\d{2}-01$")
    for name in ("pbi_cluster_monthly_metrics", "pbi_cluster_capacity_monthly"):
        df = pbi_tables[name]
        bad = [v for v in df["month"].dropna() if not pattern.match(str(v))]
        assert not bad, f"{name}: 'month' values not matching YYYY-MM-01: {bad[:5]}"


# ---------------------------------------------------------------------------
# 14. Date format in forecast table matches YYYY-MM-DD
# ---------------------------------------------------------------------------

def test_date_format_forecast_table(pbi_tables) -> None:
    pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")
    df = pbi_tables["pbi_forecast_results"]
    bad = [v for v in df["forecast_date"].dropna() if not pattern.match(str(v))]
    assert not bad, (
        f"pbi_forecast_results: 'forecast_date' values not matching YYYY-MM-DD: {bad[:5]}"
    )


# ---------------------------------------------------------------------------
# 15. No Stage 10 files created
# ---------------------------------------------------------------------------

def test_no_stage10_files_created() -> None:
    stage10_src = list(REPO_ROOT.glob("src/10_*.py"))
    assert not stage10_src, f"Unexpected Stage 10 source file(s) found: {stage10_src}"

    stage10_processed = list(REPO_ROOT.glob("data/processed/pbi_*10*"))
    assert not stage10_processed, (
        f"Unexpected Stage 10 PBI output file(s) found: {stage10_processed}"
    )

    stage10_docs = list(REPO_ROOT.glob("docs/*stage10*"))
    assert not stage10_docs, f"Unexpected Stage 10 doc file(s) found: {stage10_docs}"
