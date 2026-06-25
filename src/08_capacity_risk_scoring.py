"""
Stage 8: Capacity Risk Scoring
Combines latest actual utilization, monthly growth, and 180-day forecasts to
assign each cluster a risk level (Critical / High / Medium / Low) and a
recommended action.
"""

import math
import sys
import pathlib

import pandas as pd

ROOT         = pathlib.Path(__file__).resolve().parent.parent
DAILY_IN     = ROOT / "data" / "processed" / "cluster_capacity_daily.csv"
FORECAST_IN  = ROOT / "data" / "processed" / "forecast_results.csv"
INVENTORY_IN = ROOT / "data" / "processed" / "capacity_inventory.csv"
RISK_OUT     = ROOT / "data" / "processed" / "capacity_risk_summary.csv"

REQUIRED_COLS = [
    "cluster_name", "datacenter", "business_unit", "storage_platform",
    "current_used_tb", "usable_capacity_tb", "current_utilization_pct",
    "forecast_30d_utilization_pct", "forecast_90d_utilization_pct",
    "forecast_180d_utilization_pct",
    "days_until_80_pct", "days_until_85_pct", "days_until_90_pct",
    "months_until_80_pct", "months_until_85_pct", "months_until_90_pct",
    "monthly_growth_tb", "risk_level", "recommended_action",
]

RISK_ACTIONS = {
    "Critical": "Expand capacity immediately and validate workload drivers.",
    "High":     "Plan capacity expansion within the next planning cycle.",
    "Medium":   "Monitor weekly and optimize storage overhead.",
    "Low":      "No immediate action required.",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _months_from_days(days) -> object:
    """Convert days to months (ceiling). Returns None/NaN for NaN input."""
    if days is None or (isinstance(days, float) and math.isnan(days)):
        return None
    days = int(days)
    if days == 0:
        return 0
    return math.ceil(days / 30)


def _assign_risk(
    current_utilization_pct: float,
    days_until_90: object,
    days_until_85: object,
    monthly_growth_tb: float,
    growth_75th_pct: float,
) -> str:
    """Assign risk level using strict priority (elif chain)."""
    # ── Critical ────────────────────────────────────────────────────────────
    if current_utilization_pct >= 90:
        return "Critical"
    if days_until_90 is not None and not (isinstance(days_until_90, float) and math.isnan(days_until_90)):
        if int(days_until_90) <= 90:
            return "Critical"

    # ── High ─────────────────────────────────────────────────────────────────
    if current_utilization_pct >= 85:
        return "High"
    if days_until_85 is not None and not (isinstance(days_until_85, float) and math.isnan(days_until_85)):
        if int(days_until_85) <= 180:
            return "High"

    # ── Medium ───────────────────────────────────────────────────────────────
    if current_utilization_pct >= 75:
        return "Medium"
    if monthly_growth_tb >= growth_75th_pct:
        return "Medium"

    # ── Low ──────────────────────────────────────────────────────────────────
    return "Low"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    # ── Load inputs ──────────────────────────────────────────────────────────
    daily     = pd.read_csv(DAILY_IN, parse_dates=["date"])
    forecast  = pd.read_csv(FORECAST_IN, parse_dates=["forecast_date"])
    inventory = pd.read_csv(INVENTORY_IN)

    daily    = daily.sort_values(["cluster_name", "date"]).reset_index(drop=True)
    forecast = forecast.sort_values(["cluster_name", "forecast_date"]).reset_index(drop=True)

    clusters = sorted(daily["cluster_name"].unique())
    n_clusters = len(clusters)

    # ── Step 1 & 2: Latest actual state + monthly growth ─────────────────────
    latest_rows = daily.groupby("cluster_name", as_index=False).apply(
        lambda g: g.sort_values("date").iloc[-1], include_groups=False
    ).reset_index(drop=True)
    # Re-attach cluster_name (lost when include_groups=False)
    if "cluster_name" not in latest_rows.columns:
        latest_rows = latest_rows.reset_index(drop=False).rename(
            columns={"cluster_name": "cluster_name"}
        )

    # monthly_growth_tb: sum of last ≤30 net_new_storage_tb values per cluster
    def _monthly_growth(g: pd.DataFrame) -> float:
        sorted_g = g.sort_values("date", ascending=False)
        last30   = sorted_g.head(30)
        return float(last30["net_new_storage_tb"].sum())

    growth_series = daily.groupby("cluster_name").apply(
        _monthly_growth, include_groups=False
    ).reset_index()
    growth_series.columns = ["cluster_name", "monthly_growth_tb"]

    # 75th percentile for Medium threshold
    growth_75th = float(growth_series["monthly_growth_tb"].quantile(0.75))

    # ── Step 3: Forecast utilization snapshots ────────────────────────────────
    fc_snapshots: list[dict] = []
    for cluster_name in clusters:
        cfc = forecast[forecast["cluster_name"] == cluster_name].sort_values(
            "forecast_date"
        ).reset_index(drop=True)

        def _get_util(idx: int) -> float:
            if idx < len(cfc):
                return float(cfc.loc[idx, "forecast_utilization_pct"])
            return float("nan")

        fc_snapshots.append({
            "cluster_name":               cluster_name,
            "forecast_30d_utilization_pct":  _get_util(29),
            "forecast_90d_utilization_pct":  _get_util(89),
            "forecast_180d_utilization_pct": _get_util(179),
        })

    fc_snap_df = pd.DataFrame(fc_snapshots)

    # ── Step 4: Threshold crossing days ──────────────────────────────────────
    threshold_rows: list[dict] = []
    for cluster_name in clusters:
        cfc = forecast[forecast["cluster_name"] == cluster_name].sort_values(
            "forecast_date"
        ).reset_index(drop=True)

        # latest actual date for this cluster
        cluster_daily = daily[daily["cluster_name"] == cluster_name]
        latest_actual_date = cluster_daily["date"].max()

        # current utilization
        row_latest = latest_rows[latest_rows["cluster_name"] == cluster_name].iloc[0]
        cur_util = float(row_latest["capacity_utilization_pct"])

        trow: dict = {"cluster_name": cluster_name}
        for thr in (80, 85, 90):
            col = f"days_until_{thr}_pct"
            if cur_util >= thr:
                trow[col] = 0
            else:
                first_breach = cfc[cfc["forecast_utilization_pct"] >= thr]
                if first_breach.empty:
                    trow[col] = None  # never crossed
                else:
                    breach_date = first_breach.iloc[0]["forecast_date"]
                    trow[col] = int((breach_date - latest_actual_date).days)
        threshold_rows.append(trow)

    threshold_df = pd.DataFrame(threshold_rows)

    # ── Step 5: months_until ─────────────────────────────────────────────────
    for thr in (80, 85, 90):
        d_col = f"days_until_{thr}_pct"
        m_col = f"months_until_{thr}_pct"
        threshold_df[m_col] = threshold_df[d_col].apply(_months_from_days)

    # ── Step 6 & 7: Risk level & recommended action ───────────────────────────
    # Merge all data
    df = (
        latest_rows[
            ["cluster_name", "datacenter", "business_unit", "storage_platform",
             "used_capacity_tb", "usable_capacity_tb", "capacity_utilization_pct",
             "free_capacity_tb"]
        ]
        .rename(columns={
            "used_capacity_tb":         "current_used_tb",
            "capacity_utilization_pct": "current_utilization_pct",
            "free_capacity_tb":         "current_free_tb",
        })
        .merge(fc_snap_df,   on="cluster_name", how="left")
        .merge(threshold_df, on="cluster_name", how="left")
        .merge(growth_series, on="cluster_name", how="left")
    )

    risk_levels: list[str] = []
    for _, row in df.iterrows():
        risk = _assign_risk(
            current_utilization_pct=float(row["current_utilization_pct"]),
            days_until_90=row["days_until_90_pct"],
            days_until_85=row["days_until_85_pct"],
            monthly_growth_tb=float(row["monthly_growth_tb"]),
            growth_75th_pct=growth_75th,
        )
        risk_levels.append(risk)

    df["risk_level"]          = risk_levels
    df["recommended_action"]  = df["risk_level"].map(RISK_ACTIONS)

    # ── Select and order output columns ──────────────────────────────────────
    df = df[REQUIRED_COLS].sort_values("cluster_name").reset_index(drop=True)

    # ── Write output ─────────────────────────────────────────────────────────
    RISK_OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(RISK_OUT, index=False)

    # ── Validation ───────────────────────────────────────────────────────────
    errors: list[str] = []

    # Row count == number of clusters
    if len(df) != n_clusters:
        errors.append(
            f"Row count {len(df)} != expected cluster count {n_clusters}"
        )

    # All required columns present
    for col in REQUIRED_COLS:
        if col not in df.columns:
            errors.append(f"Missing required column: {col}")

    # No duplicate cluster_name
    dup_count = df["cluster_name"].duplicated().sum()
    if dup_count:
        errors.append(f"{dup_count} duplicate cluster_name value(s)")

    # risk_level only in allowed set
    valid_levels = {"Critical", "High", "Medium", "Low"}
    bad_levels = set(df["risk_level"].unique()) - valid_levels
    if bad_levels:
        errors.append(f"Invalid risk_level value(s): {bad_levels}")

    # recommended_action not null
    null_actions = df["recommended_action"].isnull().sum()
    if null_actions:
        errors.append(f"{null_actions} null recommended_action value(s)")

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Stage 8 complete — capacity_risk_summary.csv ({len(df)} rows) written."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
