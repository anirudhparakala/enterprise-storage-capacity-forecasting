"""
Stage 6: Estimate Capacity Usage
Joins cluster daily metrics to capacity inventory, computes cumulative daily
storage utilisation per cluster, and derives monthly summaries from the daily table.
"""

import sys
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
DAILY_METRICS = ROOT / "data" / "processed" / "cluster_daily_metrics.csv"
CAPACITY_INV  = ROOT / "data" / "processed" / "capacity_inventory.csv"
DAILY_OUT     = ROOT / "data" / "processed" / "cluster_capacity_daily.csv"
MONTHLY_OUT   = ROOT / "data" / "processed" / "cluster_capacity_monthly.csv"

RETENTION_FACTOR = 0.08

# Tiered starting utilisation — deterministic by sorted cluster position
# 20 clusters total: 8 Low | 5 Watchlist | 5 Medium | 2 High
TIERS = [
    ("Low",       0.35, 0.60, 8),
    ("Watchlist", 0.60, 0.72, 5),
    ("Medium",    0.72, 0.82, 5),
    ("High",      0.82, 0.88, 2),
]


def _build_tier_maps(clusters: list[str]) -> tuple[dict, dict]:
    """Return (starting_frac_map, tier_label_map) keyed by cluster name."""
    rng = np.random.default_rng(seed=42)
    fracs: list[float] = []
    labels: list[str]  = []
    for label, lo, hi, n in TIERS:
        fracs.extend(rng.uniform(lo, hi, size=n).tolist())
        labels.extend([label] * n)
    return dict(zip(clusters, fracs)), dict(zip(clusters, labels))


def main() -> None:
    dm = pd.read_csv(DAILY_METRICS, parse_dates=["date"])
    ci = pd.read_csv(CAPACITY_INV)

    df = dm.merge(
        ci[["cluster_name", "raw_capacity_tb", "usable_capacity_tb"]],
        on="cluster_name",
        how="left",
    )

    df["daily_write_tb_estimate"] = (
        df["avg_disk_write_kbps"] * 86_400 / 1024 / 1024 / 1024
    )
    df["net_new_storage_tb"] = df["daily_write_tb_estimate"] * RETENTION_FACTOR

    clusters = sorted(df["cluster_name"].unique())
    start_frac_map, tier_map = _build_tier_maps(clusters)

    cluster_usable = ci.set_index("cluster_name")["usable_capacity_tb"].reindex(clusters)
    starting_used = {c: start_frac_map[c] * cluster_usable[c] for c in clusters}

    df["starting_used_tb"]        = df["cluster_name"].map(starting_used)
    df["starting_utilization_tier"] = df["cluster_name"].map(tier_map)

    # Sort for deterministic cumulative sum within each cluster
    df = df.sort_values(["cluster_name", "date"]).reset_index(drop=True)

    df["cumulative_net_new_tb"] = (
        df.groupby("cluster_name")["net_new_storage_tb"].cumsum()
    )
    df["used_capacity_tb"]       = df["starting_used_tb"] + df["cumulative_net_new_tb"]
    df["free_capacity_tb"]       = df["usable_capacity_tb"] - df["used_capacity_tb"]
    df["capacity_utilization_pct"] = (
        df["used_capacity_tb"] / df["usable_capacity_tb"] * 100
    )

    daily_cols = [
        "date", "cluster_name", "datacenter", "business_unit", "storage_platform",
        "usable_capacity_tb", "raw_capacity_tb",
        "daily_write_tb_estimate", "net_new_storage_tb",
        "starting_used_tb", "starting_utilization_tier",
        "used_capacity_tb", "free_capacity_tb", "capacity_utilization_pct",
    ]
    daily = df[daily_cols].copy()
    DAILY_OUT.parent.mkdir(parents=True, exist_ok=True)
    daily.to_csv(DAILY_OUT, index=False)

    # ── Derive monthly from daily ────────────────────────────────────────────
    df["month"] = df["date"].dt.to_period("M").astype(str)

    # Within each (month, cluster_name), last row (sorted by date) = end-of-month state
    monthly_meta = (
        df.groupby(["month", "cluster_name"])
        .agg(
            datacenter=("datacenter", "first"),
            business_unit=("business_unit", "first"),
            storage_platform=("storage_platform", "first"),
            usable_capacity_tb=("usable_capacity_tb", "first"),
            raw_capacity_tb=("raw_capacity_tb", "first"),
            starting_used_tb=("starting_used_tb", "first"),
            starting_utilization_tier=("starting_utilization_tier", "first"),
            monthly_write_tb_estimate=("daily_write_tb_estimate", "sum"),
            monthly_net_new_storage_tb=("net_new_storage_tb", "sum"),
            used_capacity_tb=("used_capacity_tb", "last"),
        )
        .reset_index()
    )

    monthly_meta["free_capacity_tb"] = (
        monthly_meta["usable_capacity_tb"] - monthly_meta["used_capacity_tb"]
    )
    monthly_meta["capacity_utilization_pct"] = (
        monthly_meta["used_capacity_tb"] / monthly_meta["usable_capacity_tb"] * 100
    )

    monthly_cols = [
        "month", "cluster_name", "datacenter", "business_unit", "storage_platform",
        "usable_capacity_tb", "raw_capacity_tb",
        "monthly_write_tb_estimate", "monthly_net_new_storage_tb",
        "starting_used_tb", "starting_utilization_tier",
        "used_capacity_tb", "free_capacity_tb", "capacity_utilization_pct",
    ]
    monthly = monthly_meta[monthly_cols].sort_values(["month", "cluster_name"]).reset_index(drop=True)
    MONTHLY_OUT.parent.mkdir(parents=True, exist_ok=True)
    monthly.to_csv(MONTHLY_OUT, index=False)

    # ── Validation ───────────────────────────────────────────────────────────
    errors = []

    dups_daily = daily.duplicated(subset=["date", "cluster_name"]).sum()
    if dups_daily:
        errors.append(f"Daily: {dups_daily} duplicate (date, cluster_name) rows")

    dups_monthly = monthly.duplicated(subset=["month", "cluster_name"]).sum()
    if dups_monthly:
        errors.append(f"Monthly: {dups_monthly} duplicate (month, cluster_name) rows")

    cluster_meta = daily.drop_duplicates("cluster_name").copy()
    start_pct = cluster_meta["starting_used_tb"] / cluster_meta["usable_capacity_tb"] * 100
    if not start_pct.between(35.0, 88.0).all():
        errors.append("starting_used_tb outside 35–88 % of usable_capacity_tb")

    valid_tiers = {"Low", "Watchlist", "Medium", "High"}
    bad_tiers = set(daily["starting_utilization_tier"].unique()) - valid_tiers
    if bad_tiers:
        errors.append(f"Invalid starting_utilization_tier values: {bad_tiers}")

    if (daily["used_capacity_tb"] < 0).any():
        errors.append("used_capacity_tb has negative values")

    varying_clusters = (
        daily.groupby("cluster_name")["capacity_utilization_pct"].nunique().gt(1).sum()
    )
    if varying_clusters == 0:
        errors.append("No cluster shows utilisation change over time")

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print(
        f"Stage 6 complete — "
        f"cluster_capacity_daily.csv ({len(daily)} rows) and "
        f"cluster_capacity_monthly.csv ({len(monthly)} rows) written."
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
