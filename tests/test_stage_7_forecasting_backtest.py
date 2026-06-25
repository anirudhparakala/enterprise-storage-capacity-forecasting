from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest

REPO_ROOT    = Path(__file__).resolve().parents[1]
SCRIPT       = REPO_ROOT / "src" / "07_forecasting_backtest.py"
BACKTEST_OUT = REPO_ROOT / "data" / "processed" / "model_backtest_results.csv"
FORECAST_OUT = REPO_ROOT / "data" / "processed" / "forecast_results.csv"
DAILY_IN     = REPO_ROOT / "data" / "processed" / "cluster_capacity_daily.csv"

BACKTEST_REQUIRED_COLS = [
    "cluster_name", "model_name", "mae", "rmse", "mape", "selected_model_flag",
]
FORECAST_REQUIRED_COLS = [
    "cluster_name", "forecast_date", "selected_model",
    "forecast_used_tb", "forecast_utilization_pct", "forecast_free_capacity_tb",
    "breach_80_flag", "breach_85_flag", "breach_90_flag",
]


@pytest.fixture(scope="module")
def outputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    if not SCRIPT.exists():
        pytest.fail("Stage 7 script not found")
    result = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    backtest = pd.read_csv(BACKTEST_OUT)
    forecast = pd.read_csv(FORECAST_OUT, parse_dates=["forecast_date"])
    return backtest, forecast


def test_output_files_exist(outputs: tuple) -> None:
    assert BACKTEST_OUT.exists(), "model_backtest_results.csv does not exist"
    assert FORECAST_OUT.exists(), "forecast_results.csv does not exist"


def test_backtest_required_columns(outputs: tuple) -> None:
    backtest, _ = outputs
    for col in BACKTEST_REQUIRED_COLS:
        assert col in backtest.columns, f"Missing column in model_backtest_results: {col}"


def test_forecast_required_columns(outputs: tuple) -> None:
    _, forecast = outputs
    for col in FORECAST_REQUIRED_COLS:
        assert col in forecast.columns, f"Missing column in forecast_results: {col}"


def test_every_cluster_has_model_results(outputs: tuple) -> None:
    backtest, _ = outputs
    daily_in = pd.read_csv(DAILY_IN)
    expected_clusters = set(daily_in["cluster_name"].unique())
    actual_clusters = set(backtest["cluster_name"].unique())
    missing = expected_clusters - actual_clusters
    assert not missing, f"Clusters missing from model_backtest_results: {missing}"


def test_every_cluster_has_exactly_one_selected_model(outputs: tuple) -> None:
    backtest, _ = outputs
    backtest = backtest.copy()
    backtest["selected_model_flag"] = (
        backtest["selected_model_flag"].astype(str).str.lower() == "true"
    )
    selected_counts = backtest[backtest["selected_model_flag"]].groupby("cluster_name").size()
    bad = selected_counts[selected_counts != 1]
    assert bad.empty, (
        f"Clusters without exactly one selected model: {bad.to_dict()}"
    )
    # Also ensure every cluster from backtest has at least one selected row
    all_clusters = set(backtest["cluster_name"].unique())
    clusters_with_selection = set(selected_counts.index)
    missing = all_clusters - clusters_with_selection
    assert not missing, f"Clusters with no selected model: {missing}"


def test_every_cluster_has_180_forecast_rows(outputs: tuple) -> None:
    _, forecast = outputs
    counts = forecast.groupby("cluster_name").size()
    bad = counts[counts != 180]
    assert bad.empty, (
        f"Clusters without exactly 180 forecast rows: {bad.to_dict()}"
    )


def test_forecast_date_after_latest_actual_date(outputs: tuple) -> None:
    _, forecast = outputs
    daily_in = pd.read_csv(DAILY_IN, parse_dates=["date"])
    max_actual_date = daily_in["date"].max()
    min_forecast_date = forecast["forecast_date"].min()
    assert min_forecast_date > max_actual_date, (
        f"Some forecast dates ({min_forecast_date.date()}) are not after the latest "
        f"actual date ({max_actual_date.date()})"
    )


def test_backtest_metrics_present(outputs: tuple) -> None:
    backtest, _ = outputs
    import math
    for metric in ("mae", "rmse", "mape"):
        null_count = backtest[metric].isnull().sum()
        assert null_count == 0, f"Column '{metric}' has {null_count} null value(s)"
        non_finite = backtest[metric].apply(lambda v: not math.isfinite(float(v))).sum()
        assert non_finite == 0, f"Column '{metric}' has {non_finite} non-finite value(s)"


def test_selected_model_has_lowest_mape(outputs: tuple) -> None:
    backtest = outputs[0].copy()
    backtest["selected_model_flag"] = (
        backtest["selected_model_flag"].astype(str).str.lower() == "true"
    )
    for cluster, group in backtest.groupby("cluster_name"):
        selected_rows = group[group["selected_model_flag"]]
        if selected_rows.empty:
            pytest.fail(f"Cluster '{cluster}' has no selected model")
        selected_mape = selected_rows["mape"].iloc[0]
        min_mape = group["mape"].min()
        assert selected_mape == min_mape, (
            f"Cluster '{cluster}': selected model MAPE ({selected_mape}) != "
            f"minimum MAPE ({min_mape})"
        )


def test_forecast_utilization_nonnegative(outputs: tuple) -> None:
    _, forecast = outputs
    neg_count = (forecast["forecast_utilization_pct"] < 0).sum()
    assert neg_count == 0, (
        f"forecast_utilization_pct has {neg_count} negative value(s)"
    )


def test_breach_flags_populated(outputs: tuple) -> None:
    _, forecast = outputs
    for col in ("breach_80_flag", "breach_85_flag", "breach_90_flag"):
        assert col in forecast.columns, f"Column '{col}' is missing from forecast_results"
        null_count = forecast[col].isnull().sum()
        assert null_count == 0, f"Column '{col}' has {null_count} null value(s)"


def test_breach_flag_consistency(outputs: tuple) -> None:
    _, forecast = outputs
    df = forecast.copy()
    # Coerce to bool regardless of storage type (bool or string)
    for col in ("breach_80_flag", "breach_85_flag", "breach_90_flag"):
        df[col] = df[col].astype(str).str.lower() == "true"

    # If breach_90 is True, breach_85 must be True
    violated_90_85 = df[df["breach_90_flag"] & ~df["breach_85_flag"]]
    assert violated_90_85.empty, (
        f"{len(violated_90_85)} row(s) have breach_90_flag=True but breach_85_flag=False"
    )

    # If breach_85 is True, breach_80 must be True
    violated_85_80 = df[df["breach_85_flag"] & ~df["breach_80_flag"]]
    assert violated_85_80.empty, (
        f"{len(violated_85_80)} row(s) have breach_85_flag=True but breach_80_flag=False"
    )


def test_deterministic_output() -> None:
    if not SCRIPT.exists():
        pytest.fail("Stage 7 script not found")
    subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, check=True)
    h1_b = hashlib.md5(BACKTEST_OUT.read_bytes()).hexdigest()
    h1_f = hashlib.md5(FORECAST_OUT.read_bytes()).hexdigest()
    subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, check=True)
    h2_b = hashlib.md5(BACKTEST_OUT.read_bytes()).hexdigest()
    h2_f = hashlib.md5(FORECAST_OUT.read_bytes()).hexdigest()
    assert h1_b == h2_b, "model_backtest_results.csv is not deterministic"
    assert h1_f == h2_f, "forecast_results.csv is not deterministic"


def test_no_stage8_file_created() -> None:
    stage8_src = list(REPO_ROOT.glob("src/08_*.py"))
    assert not stage8_src, (
        f"Unexpected Stage 8 source file(s) found: {stage8_src}"
    )
    stage8_processed_08 = list(REPO_ROOT.glob("data/processed/*08*"))
    assert not stage8_processed_08, (
        f"Unexpected Stage 8 output file(s) matching '*08*': {stage8_processed_08}"
    )
    stage8_processed_name = list(REPO_ROOT.glob("data/processed/*stage8*"))
    assert not stage8_processed_name, (
        f"Unexpected Stage 8 output file(s) matching '*stage8*': {stage8_processed_name}"
    )


def test_forecast_used_tb_nonnegative(outputs: tuple) -> None:
    _, forecast = outputs
    neg_count = (forecast["forecast_used_tb"] < 0).sum()
    assert neg_count == 0, (
        f"forecast_used_tb has {neg_count} negative value(s)"
    )


def test_forecast_date_is_daily(outputs: tuple) -> None:
    _, forecast = outputs
    one_day = pd.Timedelta(days=1)
    for cluster, group in forecast.groupby("cluster_name"):
        sorted_dates = group["forecast_date"].sort_values().reset_index(drop=True)
        diffs = sorted_dates.diff().dropna()
        bad = diffs[diffs != one_day]
        assert bad.empty, (
            f"Cluster '{cluster}' has non-daily forecast date gaps: {bad.tolist()}"
        )
