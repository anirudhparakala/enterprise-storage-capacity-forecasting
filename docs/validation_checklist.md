# Validation Checklist

Use this checklist as the gate between stages. A stage is complete only when its outputs exist and its stop condition passes.

## Stage 0: Raw Data Profiling

- [x] `src/00_profile_raw_data.py` exists.
- [x] `data/processed/raw_data_profile.csv` exists.
- [x] `docs/data_profile_summary.md` exists.
- [x] Total raw CSV file count is greater than zero.
- [x] File counts by trace type are reported.
- [x] File counts by source month folder are reported.
- [x] At least two sample files are inspected when available.
- [x] Parser detects whether rows are wrapped in double quotes.
- [x] Parser confirms semicolon delimiter with optional whitespace or tab.
- [x] Parsed sample data rows have 11 columns.
- [x] Header row has 11 columns when present.
- [x] Timestamp unit inference treats `1376314846`-style values as Unix seconds.
- [x] Sample datetime conversion produces 2013 dates.
- [x] Stop condition passes before Stage 1 starts.

## Stage 1: Data Ingestion

- [x] `src/01_ingest_bitbrains.py` exists.
- [x] `data/processed/vm_metrics_cleaned.parquet` exists.
- [x] `data/processed/vm_metrics_sample.csv` exists.
- [x] No accepted dataframe has only one column.
- [x] Failed parse rate is less than or equal to 5%.
- [x] Standardized target columns are present.
- [x] Numeric columns are numeric.
- [x] Datetime values show 2013 dates for sample values.
- [x] `trace_type` is populated.
- [x] `source_month_folder` is populated.
- [x] `vm_id` is unique per source file.
- [x] Stop condition passes before Stage 2 starts.

## Stage 2: Feature Engineering

- [x] `src/02_feature_engineering.py` exists.
- [x] `data/processed/vm_daily_metrics.csv` exists.
- [x] No negative disk throughput values are accepted.
- [x] Memory utilization anomalies are counted and explained.
- [x] Output has one row per VM per day.
- [x] `p95_memory_utilization_pct` is present.
- [x] `p95_disk_total_kbps` is present.
- [x] `high_disk_spike_count` is not all zero.
- [x] Stop condition passes before Stage 3 starts.

## Stage 3: Cluster Assignment

- [x] `src/03_assign_clusters.py` exists.
- [x] `data/processed/vm_cluster_mapping.csv` exists.
- [x] Deterministic random seed `42` is used.
- [x] Approximately 20 clusters are created when VM count supports it.
- [x] Every VM maps to exactly one cluster.
- [x] Every cluster has multiple VMs where possible.
- [x] `trace_type` is preserved.
- [x] Datacenter assignment is deterministic.
- [x] Business unit assignment is deterministic.
- [x] Absence of `Rnd` is documented if only fastStorage exists.
- [x] Stop condition passes before Stage 4 starts.

## Stage 4: Daily and Monthly Cluster Metrics

- [x] `src/04_build_monthly_cluster_metrics.py` exists.
- [x] `data/processed/cluster_daily_metrics.csv` exists.
- [x] `data/processed/cluster_monthly_metrics.csv` exists.
- [x] Daily output has one row per cluster per date.
- [x] Output has one row per cluster per month.
- [x] No cluster names are missing.
- [x] Date field is valid.
- [x] Month field is valid.
- [x] `p95_disk_total_kbps` exists and is numeric in both daily and monthly outputs.
- [x] `vm_count` is positive.
- [x] Stop condition passes before Stage 5 starts.

## Stage 5: Simulated Capacity Inventory

- [x] `src/05_create_capacity_inventory.py` exists.
- [x] `data/processed/capacity_inventory.csv` exists.
- [x] Every cluster has exactly one capacity inventory row.
- [x] `inventory_type` is populated for every row.
- [x] `inventory_type` equals `Simulated`.
- [x] Usable capacity is always less than raw capacity.
- [x] No capacity value is negative.
- [x] Fast SAN-style percentages fall within configured ranges.
- [x] Mixed SAN/NAS-style percentages fall within configured ranges when present.
- [x] Stop condition passes before Stage 6 starts.

## Stage 6: Estimated Capacity Usage

- [x] `src/06_estimate_capacity_usage.py` exists.
- [x] `data/processed/cluster_capacity_daily.csv` exists.
- [x] `data/processed/cluster_capacity_monthly.csv` exists.
- [x] `retention_factor = 0.08` is used.
- [x] Daily write throughput is converted from KB/s to TB/day using 86,400 seconds per day.
- [x] Starting utilization is between 35% and 70%.
- [x] Daily utilization changes over time for clusters with nonzero growth.
- [x] Some clusters approach 75%, 80%, or 85% when data and simulation support it.
- [x] Not every cluster is low risk.
- [x] Not every cluster is critical.
- [x] Used capacity is never negative.
- [x] Any capacity breach is rare and explainable.
- [x] Monthly capacity output is derived from daily capacity history.
- [x] Stop condition passes before Stage 7 starts.

## Stage 7: Forecasting and Backtesting

- [x] `src/07_forecasting_backtest.py` exists.
- [x] `data/processed/model_backtest_results.csv` exists.
- [x] `data/processed/forecast_results.csv` exists.
- [x] Naive baseline model is included.
- [x] Seven-day moving average model is included.
- [x] Holt linear trend model is included.
- [x] Exponential smoothing model is included.
- [x] Linear regression is not the main forecasting method.
- [x] Backtesting uses daily cluster capacity history.
- [x] Training data uses the earliest 70% to 80% of daily observations.
- [x] Test data uses the remaining 20% to 30% of daily observations.
- [x] Every cluster has model results.
- [x] Every cluster has one selected model.
- [x] Every cluster has 180 forecast dates.
- [x] MAE, RMSE, and MAPE are present when daily history supports backtesting.
- [x] Limited-history fallback is documented when history is insufficient.
- [x] Forecast utilization is not negative.
- [x] Forecast free capacity can decline over time.
- [x] Stop condition passes before Stage 8 starts.

## Stage 8: Risk Scoring and Recommendations

- [x] `src/08_capacity_risk_scoring.py` exists.
- [x] `data/processed/capacity_risk_summary.csv` exists.
- [x] Every cluster has one risk summary row.
- [x] Risk levels are not all the same.
- [x] Critical rule is applied before High, Medium, and Low rules.
- [x] High rule is applied before Medium and Low rules.
- [x] `forecast_30d_utilization_pct` is present.
- [x] `forecast_90d_utilization_pct` is present.
- [x] `forecast_180d_utilization_pct` is present.
- [x] `days_until_80_pct`, `days_until_85_pct`, and `days_until_90_pct` are present.
- [x] `months_until_80_pct`, `months_until_85_pct`, and `months_until_90_pct` are derived from daily threshold crossings.
- [x] Recommended action maps exactly to risk level.
- [x] Clusters above thresholds are correctly flagged.
- [x] Days and months until threshold breach are understandable.
- [x] Stop condition passes before Stage 9 starts.

## Stage 9: Power BI Export Tables

- [x] `src/09_generate_powerbi_tables.py` exists.
- [x] `data/processed/pbi_cluster_daily_metrics.csv` exists.
- [x] `data/processed/pbi_cluster_monthly_metrics.csv` exists.
- [x] `data/processed/pbi_capacity_inventory.csv` exists.
- [x] `data/processed/pbi_cluster_capacity_daily.csv` exists.
- [x] `data/processed/pbi_cluster_capacity_monthly.csv` exists.
- [x] `data/processed/pbi_forecast_results.csv` exists.
- [x] `data/processed/pbi_model_backtest_results.csv` exists.
- [x] `data/processed/pbi_capacity_risk_summary.csv` exists.
- [x] No exported CSV contains an index column.
- [x] Date formats are consistent.
- [x] Percentage fields use consistent `0-100` representation.
- [x] Debug fields are excluded.
- [x] Stop condition passes before Stage 10 starts.

## Stage 10: Documentation and README

- [x] `README.md` includes the business problem.
- [x] `README.md` includes the dataset description.
- [x] `README.md` includes tools used.
- [x] `README.md` includes methodology.
- [x] `README.md` includes parsing and ingestion decisions.
- [x] `README.md` includes feature engineering.
- [x] `README.md` includes capacity inventory simulation.
- [x] `README.md` includes forecasting and backtesting.
- [x] `README.md` includes risk scoring logic.
- [x] `README.md` includes Power BI dashboard design.
- [x] `README.md` includes key outputs.
- [x] `README.md` includes limitations.
- [x] `README.md` includes how to run.
- [x] `README.md` includes honest resume bullets.
- [x] `docs/methodology.md` exists.
- [x] `docs/limitations.md` exists.
- [x] Required limitation statement is present.
- [x] Required daily forecasting-history statement is present.
- [x] Documentation does not claim real enterprise storage inventory.
- [x] Documentation does not claim FedEx production data or Dell product experience.
