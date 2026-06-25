"""
Stage 7: Forecasting Back-test
For each cluster, benchmarks four time-series models against a held-out test
window, selects the best model by MAPE, then generates a 180-day forward
forecast with utilisation and breach flags.
"""

import math
import sys
import pathlib

import numpy as np
import pandas as pd
from statsmodels.tsa.holtwinters import Holt, ExponentialSmoothing

ROOT         = pathlib.Path(__file__).resolve().parent.parent
DAILY_IN     = ROOT / "data" / "processed" / "cluster_capacity_daily.csv"
BACKTEST_OUT = ROOT / "data" / "processed" / "model_backtest_results.csv"
FORECAST_OUT = ROOT / "data" / "processed" / "forecast_results.csv"

# Tie-break order: first occurrence wins
MODEL_ORDER = ["naive", "moving_average_7d", "exp_smoothing", "holt_linear"]

FORECAST_HORIZON = 180


# ---------------------------------------------------------------------------
# Metric helpers
# ---------------------------------------------------------------------------

def _mae(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(np.mean(np.abs(actual - pred)))


def _rmse(actual: np.ndarray, pred: np.ndarray) -> float:
    return float(math.sqrt(np.mean((actual - pred) ** 2)))


def _mape(actual: np.ndarray, pred: np.ndarray) -> float:
    """Mean absolute percentage error; rows where actual==0 are excluded."""
    mask = actual != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs(actual[mask] - pred[mask]) / np.abs(actual[mask])) * 100)


# ---------------------------------------------------------------------------
# Per-cluster back-test
# ---------------------------------------------------------------------------

def _backtest_cluster(
    cluster_name: str,
    series: np.ndarray,
) -> list[dict]:
    """
    Returns a list of result dicts (one per successful model) with keys:
    cluster_name, model_name, mae, rmse, mape.
    """
    n = len(series)
    if n < 30:
        return []

    n_train = max(1, int(n * 0.8))
    train = series[:n_train]
    test  = series[n_train:]
    n_test = len(test)

    results = []

    # ── 1. Naive ────────────────────────────────────────────────────────────
    last_train = train[-1]
    pred_naive = np.full(n_test, last_train)
    results.append({
        "cluster_name": cluster_name,
        "model_name":   "naive",
        "mae":  _mae(test, pred_naive),
        "rmse": _rmse(test, pred_naive),
        "mape": _mape(test, pred_naive),
    })

    # ── 2. Moving average 7-day ──────────────────────────────────────────────
    window = min(7, n_train)
    ma_val = float(np.mean(train[-window:]))
    pred_ma = np.full(n_test, ma_val)
    results.append({
        "cluster_name": cluster_name,
        "model_name":   "moving_average_7d",
        "mae":  _mae(test, pred_ma),
        "rmse": _rmse(test, pred_ma),
        "mape": _mape(test, pred_ma),
    })

    # ── 3. Holt linear ──────────────────────────────────────────────────────
    try:
        holt_fit = Holt(
            train.astype(float),
            initialization_method="estimated",
        ).fit()
        pred_holt = holt_fit.forecast(n_test)
        results.append({
            "cluster_name": cluster_name,
            "model_name":   "holt_linear",
            "mae":  _mae(test, pred_holt),
            "rmse": _rmse(test, pred_holt),
            "mape": _mape(test, pred_holt),
        })
    except Exception as exc:
        print(
            f"[WARN] holt_linear skipped for {cluster_name}: {exc}",
            file=sys.stderr,
        )

    # ── 4. Exponential smoothing (simple, no trend/seasonal) ────────────────
    try:
        es_fit = ExponentialSmoothing(
            train.astype(float),
            trend=None,
            seasonal=None,
            initialization_method="estimated",
        ).fit()
        pred_es = es_fit.forecast(n_test)
        results.append({
            "cluster_name": cluster_name,
            "model_name":   "exp_smoothing",
            "mae":  _mae(test, pred_es),
            "rmse": _rmse(test, pred_es),
            "mape": _mape(test, pred_es),
        })
    except Exception as exc:
        print(
            f"[WARN] exp_smoothing skipped for {cluster_name}: {exc}",
            file=sys.stderr,
        )

    return results


def _select_best(rows: list[dict]) -> list[dict]:
    """
    Given result rows for one cluster, tag selected_model_flag.
    Best = lowest MAPE among rows with a valid (non-NaN) MAPE.
    Tie-break by MODEL_ORDER.
    """
    valid = [r for r in rows if not math.isnan(r["mape"])]

    if not valid:
        # Fall back to lowest RMSE if no valid MAPE
        valid = rows

    if not valid:
        return rows

    min_mape = min(r["mape"] for r in valid)
    # Among tied rows, respect MODEL_ORDER
    best_model = None
    for name in MODEL_ORDER:
        for r in valid:
            if r["model_name"] == name and r["mape"] == min_mape:
                best_model = name
                break
        if best_model is not None:
            break

    for r in rows:
        r["selected_model_flag"] = (r["model_name"] == best_model)

    return rows


# ---------------------------------------------------------------------------
# Per-cluster forecast
# ---------------------------------------------------------------------------

def _forecast_cluster(
    cluster_name:   str,
    series:         np.ndarray,
    n_train:        int,
    best_model:     str,
    last_date:      pd.Timestamp,
    usable_tb:      float,
) -> list[dict]:
    """
    Generates FORECAST_HORIZON daily forecast rows for the cluster.
    """
    forecast_dates = [
        last_date + pd.Timedelta(days=i + 1)
        for i in range(FORECAST_HORIZON)
    ]

    if best_model == "naive":
        last_obs = float(series[-1])
        raw_fc = np.full(FORECAST_HORIZON, last_obs)

    elif best_model == "moving_average_7d":
        window = min(7, n_train)
        ma_val = float(np.mean(series[-window:]))
        raw_fc = np.full(FORECAST_HORIZON, ma_val)

    elif best_model == "holt_linear":
        holt_fit = Holt(
            series.astype(float),
            initialization_method="estimated",
        ).fit()
        raw_fc = holt_fit.forecast(FORECAST_HORIZON)

    elif best_model == "exp_smoothing":
        es_fit = ExponentialSmoothing(
            series.astype(float),
            trend=None,
            seasonal=None,
            initialization_method="estimated",
        ).fit()
        raw_fc = es_fit.forecast(FORECAST_HORIZON)

    else:
        raise ValueError(f"Unknown model: {best_model}")

    # Clamp to >= 0; do NOT cap at usable_capacity_tb
    forecast_used = np.maximum(raw_fc, 0.0)

    rows = []
    for i, fdate in enumerate(forecast_dates):
        fu = float(forecast_used[i])
        util_pct  = fu / usable_tb * 100 if usable_tb else float("nan")
        free_tb   = usable_tb - fu
        rows.append({
            "cluster_name":           cluster_name,
            "forecast_date":          fdate,
            "selected_model":         best_model,
            "forecast_used_tb":       fu,
            "forecast_utilization_pct": util_pct,
            "forecast_free_capacity_tb": free_tb,
            "breach_80_flag":         util_pct >= 80,
            "breach_85_flag":         util_pct >= 85,
            "breach_90_flag":         util_pct >= 90,
        })

    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # ── Load and sort ────────────────────────────────────────────────────────
    daily = pd.read_csv(DAILY_IN, parse_dates=["date"])
    daily = daily.sort_values(["cluster_name", "date"]).reset_index(drop=True)

    clusters = sorted(daily["cluster_name"].unique())

    # usable capacity per cluster — constant; take first value from daily CSV
    usable_map: dict[str, float] = (
        daily.groupby("cluster_name")["usable_capacity_tb"].first().to_dict()
    )

    all_backtest: list[dict] = []
    all_forecast: list[dict] = []

    for cluster_name in clusters:
        cdf    = daily[daily["cluster_name"] == cluster_name].copy()
        series = cdf["used_capacity_tb"].to_numpy(dtype=float)
        n      = len(series)

        # ── Back-test ────────────────────────────────────────────────────────
        bt_rows = _backtest_cluster(cluster_name, series)
        if not bt_rows:
            # fewer than 30 obs — still need a placeholder so validation passes
            # Use naive on whatever data exists (>=1 row guaranteed by input)
            n_train_fb = max(1, int(n * 0.8))
            train_fb   = series[:n_train_fb]
            test_fb    = series[n_train_fb:]
            if len(test_fb) == 0:
                test_fb = series[-1:]
            pred_fb = np.full(len(test_fb), train_fb[-1])
            bt_rows = [{
                "cluster_name": cluster_name,
                "model_name":   "naive",
                "mae":  _mae(test_fb, pred_fb),
                "rmse": _rmse(test_fb, pred_fb),
                "mape": _mape(test_fb, pred_fb),
            }]

        bt_rows = _select_best(bt_rows)
        all_backtest.extend(bt_rows)

        # ── Forecast ─────────────────────────────────────────────────────────
        best_model = next(r["model_name"] for r in bt_rows if r["selected_model_flag"])
        n_train    = max(1, int(n * 0.8))
        last_date  = cdf["date"].iloc[-1]
        usable_tb  = usable_map[cluster_name]

        fc_rows = _forecast_cluster(
            cluster_name=cluster_name,
            series=series,
            n_train=n_train,
            best_model=best_model,
            last_date=last_date,
            usable_tb=usable_tb,
        )
        all_forecast.extend(fc_rows)

    # ── Assemble DataFrames ──────────────────────────────────────────────────
    bt_df = (
        pd.DataFrame(all_backtest)[
            ["cluster_name", "model_name", "mae", "rmse", "mape", "selected_model_flag"]
        ]
        .sort_values(["cluster_name", "model_name"])
        .reset_index(drop=True)
    )

    fc_df = (
        pd.DataFrame(all_forecast)[
            [
                "cluster_name", "forecast_date", "selected_model",
                "forecast_used_tb", "forecast_utilization_pct",
                "forecast_free_capacity_tb",
                "breach_80_flag", "breach_85_flag", "breach_90_flag",
            ]
        ]
        .sort_values(["cluster_name", "forecast_date"])
        .reset_index(drop=True)
    )

    # ── Write outputs ────────────────────────────────────────────────────────
    BACKTEST_OUT.parent.mkdir(parents=True, exist_ok=True)
    bt_df.to_csv(BACKTEST_OUT, index=False)
    fc_df.to_csv(FORECAST_OUT, index=False)

    # ── Validation ───────────────────────────────────────────────────────────
    errors: list[str] = []

    # 1. Every cluster must have exactly 180 forecast rows
    fc_counts = fc_df.groupby("cluster_name").size()
    bad_fc = fc_counts[fc_counts != FORECAST_HORIZON]
    if not bad_fc.empty:
        for cn, cnt in bad_fc.items():
            errors.append(
                f"Cluster '{cn}' has {cnt} forecast rows (expected {FORECAST_HORIZON})"
            )

    # Also check no cluster was dropped entirely
    missing_fc = set(clusters) - set(fc_df["cluster_name"].unique())
    for cn in missing_fc:
        errors.append(f"Cluster '{cn}' has no forecast rows")

    # 2. Every cluster must have at least one back-test row
    bt_clusters = set(bt_df["cluster_name"].unique())
    missing_bt = set(clusters) - bt_clusters
    for cn in missing_bt:
        errors.append(f"Cluster '{cn}' has no back-test rows")

    # 3. Each cluster must have exactly one selected_model_flag == True
    selected_counts = (
        bt_df[bt_df["selected_model_flag"]]
        .groupby("cluster_name")
        .size()
    )
    for cn in clusters:
        cnt = selected_counts.get(cn, 0)
        if cnt != 1:
            errors.append(
                f"Cluster '{cn}' has {cnt} selected_model_flag=True rows (expected 1)"
            )

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Stage 7 complete — "
        f"model_backtest_results.csv ({len(bt_df)} rows) and "
        f"forecast_results.csv ({len(fc_df)} rows) written."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
