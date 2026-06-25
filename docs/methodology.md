# Methodology

## Overview

This pipeline converts raw VM-level datacenter workload traces from the Bitbrains GWA dataset into a storage capacity forecasting and risk scoring system. It uses a staged, file-based architecture in which each stage reads validated artifacts from the prior stage and writes named outputs to `data/processed/`. All simulated inventory fields are clearly labeled as `Simulated` and kept separate from real workload telemetry throughout.

---

## Stage 0: Raw Data Profiling

**Goal:** Prove that the custom parser can read valid 11-column rows with 2013 timestamps before committing to full ingestion.

The profiler recursively scans `data/raw/**/*.csv` and collects file counts by trace type and source month folder. It opens sample files, strips outer double quotes, splits on semicolons with optional whitespace, and verifies that rows produce 11 columns. Timestamp unit is inferred from numeric magnitude: values around 1,376,314,846 are treated as Unix seconds and convert to August 2013.

**Output:** `data/processed/raw_data_profile.csv`, `docs/data_profile_summary.md`.

---

## Stage 1: Data Ingestion

**Goal:** Ingest all 1,250 raw VM trace CSVs into a single standardized Parquet dataset.

The ingester applies the same parser rules validated in Stage 0. Each file is parsed row-by-row: outer quotes stripped, split on `;\s*`, validated for exactly 11 fields. Timestamps are converted to UTC datetimes. Numeric columns are cast to float. Failed rows are counted; if the failure rate exceeds 5% the stage aborts. `vm_id`, `trace_type`, and `source_month_folder` are attached using the file path.

**Output:** `data/processed/vm_metrics_cleaned.parquet` (11,221,800 rows), `data/processed/vm_metrics_sample.csv`.

---

## Stage 2: Feature Engineering

**Goal:** Collapse 5-minute interval VM telemetry to one row per VM per calendar day.

Grouping is by `vm_id` and date derived from the UTC timestamp. Aggregations include mean values for CPU, memory, disk, and network columns. The 95th percentile is computed for memory utilization and disk total throughput to capture workload burst pressure. Disk spike counts are computed as the number of 5-minute intervals exceeding the VM's own daily p95 disk total. Negative disk throughput values are rejected before aggregation.

**Output:** `data/processed/vm_daily_metrics.csv` (37,124 rows, one per VM per day).

---

## Stage 3: Cluster Assignment

**Goal:** Assign each of the 1,250 VMs to one of 20 simulated enterprise storage clusters.

Assignment uses `numpy.random.default_rng(42)` for full reproducibility. Clusters are labeled with simulated datacenter and business unit names drawn from a fixed lookup. `trace_type` is preserved so downstream stages can separate workload signal by storage profile if additional trace types are added.

**Output:** `data/processed/vm_cluster_mapping.csv`.

---

## Stage 4: Daily and Monthly Cluster Metrics

**Goal:** Aggregate VM-level daily features to cluster-level daily and monthly summaries.

The daily cluster table groups `vm_daily_metrics` by cluster name and date, averaging workload metrics across all VMs in the cluster and summing spike counts. The monthly table derives from the daily cluster table by grouping on cluster name and calendar month. Both tables are used downstream as workload driver inputs for Power BI.

**Output:** `data/processed/cluster_daily_metrics.csv` (620 rows), `data/processed/cluster_monthly_metrics.csv` (40 rows).

---

## Stage 5: Simulated Capacity Inventory

**Goal:** Attach one clearly labeled simulated storage inventory record to each cluster.

Because the Bitbrains dataset contains no storage inventory, all capacity fields are generated deterministically using `numpy.random.default_rng(42)`. Fast SAN-style clusters receive raw capacity in the 800–2,500 TB range with usable capacity at 72–82% of raw. Mixed SAN/NAS-style clusters receive 500–1,800 TB raw with 65–78% usable efficiency. Every row carries `inventory_type = Simulated`. No simulated field is derived from or implied by the Bitbrains traces.

**Output:** `data/processed/capacity_inventory.csv` (20 rows).

---

## Stage 6: Capacity Usage Estimation

**Goal:** Build a daily capacity utilization time series per cluster that reflects real workload growth pressure on top of a simulated starting inventory.

Starting used capacity is simulated using a deterministic tiered utilization distribution to create realistic portfolio capacity-planning scenarios. Real workload metrics are not modified.

Starting utilization is drawn from a tiered distribution (35%–70% of usable capacity) seeded with `42`. Daily incremental growth is estimated from each cluster's mean disk write throughput:

```
daily_growth_tb = avg_disk_write_kbps × 86,400 / (1024³) × retention_factor
```

`retention_factor = 0.08` approximates net new data retained from write activity. Cumulative growth is applied forward from the starting date. Capacity utilization is computed as `used_capacity_tb / usable_capacity_tb × 100`. Monthly capacity summaries are derived from the daily history.

**Output:** `data/processed/cluster_capacity_daily.csv` (620 rows), `data/processed/cluster_capacity_monthly.csv` (40 rows).

---

## Stage 7: Forecasting and Backtesting

**Goal:** Select the best-performing model per cluster and generate a 180-day utilization forecast.

Because the available Kaggle extraction contains one month folder, forecasting is performed on daily cluster-level capacity history and then summarized into 30-day, 90-day, and 180-day planning windows.

**Candidate models:**

- `naive`: Last observed value carried forward.
- `moving_average_7d`: 7-day rolling mean of `used_capacity_tb`.
- `holt_linear`: Holt linear trend model from `statsmodels.tsa.holtwinters`.
- `exp_smoothing`: Simple exponential smoothing from `statsmodels.tsa.holtwinters`.

**Backtesting procedure:**

1. Sort daily capacity history by date.
2. Use the earliest 70–80% of observations as training data.
3. Use the remaining 20–30% as the test window.
4. Generate one-step-ahead predictions over the test window.
5. Compute MAE, RMSE, and MAPE.
6. Select the model with the lowest MAPE.

If a cluster's history is too short for meaningful backtesting, the limited-history fallback is applied and the flag is noted in the backtest output.

**Forecast generation:**

The selected model is re-fit on all available history, then projected 180 days forward. Each forecast row includes `forecast_used_tb`, `forecast_utilization_pct`, `forecast_free_capacity_tb`, and breach flags at 80%, 85%, and 90% thresholds.

**Results:** Holt linear selected for 18 clusters; naive for 2 clusters. Total forecast rows: 3,600.

**Output:** `data/processed/forecast_results.csv` (3,600 rows), `data/processed/model_backtest_results.csv`.

---

## Stage 8: Risk Scoring

**Goal:** Assign each cluster a risk level and a recommended action using forecasted utilization.

The 30-day, 90-day, and 180-day forecast utilization values are extracted by averaging forecast rows within each planning window. Risk rules are evaluated in strict priority order:

| Priority | Level | Condition |
|---|---|---|
| 1 | Critical | Current utilization ≥ 90%, or 30-day forecast ≥ 90% |
| 2 | High | 90-day forecast ≥ 85%, or 30-day forecast ≥ 85% |
| 3 | Medium | 180-day forecast ≥ 80% |
| 4 | Low | All forecasts below 80% |

Days until each threshold (80%, 85%, 90%) is crossed are computed from the daily forecast series. Months are derived from the daily crossing dates.

**Result:** Critical 0, High 2, Medium 6, Low 12.

**Output:** `data/processed/capacity_risk_summary.csv` (20 rows).

---

## Stage 9: Power BI Export

**Goal:** Export eight clean, index-free CSV files ready for import into Power BI Desktop.

Each source table is filtered to its relevant columns, date formats are standardized to `YYYY-MM-DD`, percentage fields are confirmed in 0–100 representation, and debug or intermediate columns are dropped. No index column is written.

**Output:** Eight `data/processed/pbi_*.csv` files totaling the row counts documented in Stage outputs above.

---

## Stage 10: Documentation

**Goal:** Produce complete, honest documentation that correctly separates real Bitbrains VM workload telemetry from simulated capacity inventory fields.

Outputs: `README.md`, `docs/methodology.md`, `docs/limitations.md`, updated `docs/data_assumptions.md`, updated `docs/powerbi_dashboard_plan.md`, and updated `docs/validation_checklist.md`.
