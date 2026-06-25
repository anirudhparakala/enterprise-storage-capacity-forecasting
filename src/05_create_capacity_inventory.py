"""
Stage 5: Create Capacity Inventory
Generates one simulated Fast SAN-style capacity inventory row per cluster.
"""

import sys
import pathlib
import numpy as np
import pandas as pd

ROOT = pathlib.Path(__file__).resolve().parent.parent
INPUT = ROOT / "data" / "processed" / "cluster_monthly_metrics.csv"
OUTPUT = ROOT / "data" / "processed" / "capacity_inventory.csv"

# Capacity rules for Fast SAN-style storage
RAW_MIN, RAW_MAX = 800.0, 2500.0
USABLE_RATIO_MIN, USABLE_RATIO_MAX = 0.72, 0.82
METADATA_MIN, METADATA_MAX = 3.0, 6.0
PROTECTION_MIN, PROTECTION_MAX = 12.0, 22.0
RESERVED_MIN, RESERVED_MAX = 5.0, 10.0


def main():
    df = pd.read_csv(INPUT)

    # One row per cluster — take first occurrence to get datacenter, business_unit, storage_platform
    clusters = (
        df[["cluster_name", "datacenter", "business_unit", "storage_platform"]]
        .drop_duplicates(subset=["cluster_name"])
        .reset_index(drop=True)
    )

    rng = np.random.default_rng(seed=42)
    n = len(clusters)

    raw_capacity_tb = rng.uniform(RAW_MIN, RAW_MAX, size=n)
    usable_ratio = rng.uniform(USABLE_RATIO_MIN, USABLE_RATIO_MAX, size=n)
    usable_capacity_tb = raw_capacity_tb * usable_ratio
    metadata_overhead_pct = rng.uniform(METADATA_MIN, METADATA_MAX, size=n)
    protection_overhead_pct = rng.uniform(PROTECTION_MIN, PROTECTION_MAX, size=n)
    reserved_capacity_pct = rng.uniform(RESERVED_MIN, RESERVED_MAX, size=n)

    inventory = clusters.copy()
    inventory["raw_capacity_tb"] = raw_capacity_tb
    inventory["usable_capacity_tb"] = usable_capacity_tb
    inventory["protection_overhead_pct"] = protection_overhead_pct
    inventory["metadata_overhead_pct"] = metadata_overhead_pct
    inventory["reserved_capacity_pct"] = reserved_capacity_pct
    inventory["inventory_type"] = "Simulated"

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(OUTPUT, index=False)

    # ── Validation ──────────────────────────────────────────────────────────
    errors = []

    input_clusters = df["cluster_name"].nunique()
    if len(inventory) != input_clusters:
        errors.append(f"Row count {len(inventory)} != input cluster count {input_clusters}")

    if inventory["inventory_type"].isna().any():
        errors.append("inventory_type has null values")

    if (inventory["inventory_type"] != "Simulated").any():
        errors.append("inventory_type contains values other than 'Simulated'")

    bad_usable = inventory[inventory["usable_capacity_tb"] >= inventory["raw_capacity_tb"]]
    if not bad_usable.empty:
        errors.append(f"{len(bad_usable)} rows where usable_capacity_tb >= raw_capacity_tb")

    for col in ["raw_capacity_tb", "usable_capacity_tb", "metadata_overhead_pct",
                "protection_overhead_pct", "reserved_capacity_pct"]:
        if (inventory[col] < 0).any():
            errors.append(f"Negative values in {col}")

    if not (inventory["raw_capacity_tb"].between(RAW_MIN, RAW_MAX)).all():
        errors.append("raw_capacity_tb out of range")
    if not (inventory["metadata_overhead_pct"].between(METADATA_MIN, METADATA_MAX)).all():
        errors.append("metadata_overhead_pct out of range")
    if not (inventory["protection_overhead_pct"].between(PROTECTION_MIN, PROTECTION_MAX)).all():
        errors.append("protection_overhead_pct out of range")
    if not (inventory["reserved_capacity_pct"].between(RESERVED_MIN, RESERVED_MAX)).all():
        errors.append("reserved_capacity_pct out of range")

    if errors:
        for e in errors:
            print(f"VALIDATION ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    print("Stage 5 complete — capacity_inventory.csv written.")
    sys.exit(0)


if __name__ == "__main__":
    main()
