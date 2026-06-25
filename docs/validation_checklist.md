# Validation Checklist

Use this checklist as the gate between stages. A stage is complete only when its outputs exist and its stop condition passes.

## Stage 0: Raw Data Profiling

- [ ] `src/00_profile_raw_data.py` exists.
- [ ] `data/processed/raw_data_profile.csv` exists.
- [ ] `docs/data_profile_summary.md` exists.
- [ ] Total raw CSV file count is greater than zero.
- [ ] File counts by trace type are reported.
- [ ] File counts by source month folder are reported.
- [ ] At least two sample files are inspected when available.
- [ ] Parser detects whether rows are wrapped in double quotes.
- [ ] Parser confirms semicolon delimiter with optional whitespace or tab.
- [ ] Parsed sample data rows have 11 columns.
- [ ] Header row has 11 columns when present.
- [ ] Timestamp unit inference treats `1376314846`-style values as Unix seconds.
- [ ] Sample datetime conversion produces 2013 dates.
- [ ] Stop condition passes before Stage 1 starts.

## Stage 1: Data Ingestion

- [ ] `src/01_ingest_bitbrains.py` exists.
- [ ] `data/processed/vm_metrics_cleaned.parquet` exists.
- [ ] `data/processed/vm_metrics_sample.csv` exists.
- [ ] No accepted dataframe has only one column.
- [ ] Failed parse rate is less than or equal to 5%.
- [ ] Standardized target columns are present.
- [ ] Numeric columns are numeric.
- [ ] Datetime values show 2013 dates for sample values.
- [ ] `trace_type` is populated.
- [ ] `source_month_folder` is populated.
- [ ] `vm_id` is unique per source file.
- [ ] Stop condition passes before Stage 2 starts.

## Stage 2: Feature Engineering

- [ ] `src/02_feature_engineering.py` exists.
- [ ] `data/processed/vm_daily_metrics.csv` exists.
- [ ] No negative disk throughput values are accepted.
- [ ] Memory utilization anomalies are counted and explained.
- [ ] Output has one row per VM per day.
- [ ] `p95_memory_utilization_pct` is present.
- [ ] `p95_disk_total_kbps` is present.
- [ ] `high_disk_spike_count` is not all zero.
- [ ] Stop condition passes before Stage 3 starts.

## Stage 3: Cluster Assignment

- [ ] `src/03_assign_clusters.py` exists.
- [ ] `data/processed/vm_cluster_mapping.csv` exists.
- [ ] Deterministic random seed `42` is used.
- [ ] Approximately 20 clusters are created when VM count supports it.
- [ ] Every VM maps to exactly one cluster.
- [ ] Every cluster has multiple VMs where possible.
- [ ] `trace_type` is preserved.
- [ ] Datacenter assignment is deterministic.
- [ ] Business unit assignment is deterministic.
- [ ] Absence of `Rnd` is documented if only fastStorage exists.
- [ ] Stop condition passes before Stage 4 starts.

## Stage 4: Daily and Monthly Cluster Metrics

- [ ] `src/04_build_monthly_cluster_metrics.py` exists.
- [ ] `data/processed/cluster_daily_metrics.csv` exists.
- [ ] `data/processed/cluster_monthly_metrics.csv` exists.
- [ ] Daily output has one row per cluster per date.
- [ ] Output has one row per cluster per month.
- [ ] No cluster names are missing.
- [ ] Date field is valid.
- [ ] Month field is valid.
- [ ] `p95_disk_total_kbps` exists and is numeric in both daily and monthly outputs.
- [ ] `vm_count` is positive.
- [ ] Stop condition passes before Stage 5 starts.

## Stage 5: Simulated Capacity Inventory

- [ ] `src/05_create_capacity_inventory.py` exists.
- [ ] `data/processed/capacity_inventory.csv` exists.
- [ ] Every cluster has exactly one capacity inventory row.
- [ ] `inventory_type` is populated for every row.
- [ ] `inventory_type` equals `Simulated`.
- [ ] Usable capacity is always less than raw capacity.
- [ ] No capacity value is negative.
- [ ] Fast SAN-style percentages fall within configured ranges.
- [ ] Mixed SAN/NAS-style percentages fall within configured ranges when present.
- [ ] Stop condition passes before Stage 6 starts.

## Stage 6: Estimated Capacity Usage

- [ ] `src/06_estimate_capacity_usage.py` exists.
- [ ] `data/processed/cluster_capacity_daily.csv` exists.
- [ ] `data/processed/cluster_capacity_monthly.csv` exists.
- [ ] `retention_factor = 0.08` is used.
- [ ] Daily write throughput is converted from KB/s to TB/day using 86,400 seconds per day.
- [ ] Starting utilization is between 35% and 70%.
- [ ] Daily utilization changes over time for clusters with nonzero growth.
- [ ] Some clusters approach 75%, 80%, or 85% when data and simulation support it.
- [ ] Not every cluster is low risk.
- [ ] Not every cluster is critical.
- [ ] Used capacity is never negative.
- [ ] Any capacity breach is rare and explainable.
- [ ] Monthly capacity output is derived from daily capacity history.
- [ ] Stop condition passes before Stage 7 starts.

## Stage 7: Forecasting and Backtesting

- [ ] `src/07_forecasting_backtest.py` exists.
- [ ] `data/processed/model_backtest_results.csv` exists.
- [ ] `data/processed/forecast_results.csv` exists.
- [ ] Naive baseline model is included.
- [ ] Seven-day moving average model is included.
- [ ] Holt linear trend model is included.
- [ ] Exponential smoothing model is included.
- [ ] Linear regression is not the main forecasting method.
- [ ] Backtesting uses daily cluster capacity history.
- [ ] Training data uses the earliest 70% to 80% of daily observations.
- [ ] Test data uses the remaining 20% to 30% of daily observations.
- [ ] Every cluster has model results.
- [ ] Every cluster has one selected model.
- [ ] Every cluster has 180 forecast dates.
- [ ] MAE, RMSE, and MAPE are present when daily history supports backtesting.
- [ ] Limited-history fallback is documented when history is insufficient.
- [ ] Forecast utilization is not negative.
- [ ] Forecast free capacity can decline over time.
- [ ] Stop condition passes before Stage 8 starts.

## Stage 8: Risk Scoring and Recommendations

- [ ] `src/08_capacity_risk_scoring.py` exists.
- [ ] `data/processed/capacity_risk_summary.csv` exists.
- [ ] Every cluster has one risk summary row.
- [ ] Risk levels are not all the same.
- [ ] Critical rule is applied before High, Medium, and Low rules.
- [ ] High rule is applied before Medium and Low rules.
- [ ] `forecast_30d_utilization_pct` is present.
- [ ] `forecast_90d_utilization_pct` is present.
- [ ] `forecast_180d_utilization_pct` is present.
- [ ] `days_until_80_pct`, `days_until_85_pct`, and `days_until_90_pct` are present.
- [ ] `months_until_80_pct`, `months_until_85_pct`, and `months_until_90_pct` are derived from daily threshold crossings.
- [ ] Recommended action maps exactly to risk level.
- [ ] Clusters above thresholds are correctly flagged.
- [ ] Days and months until threshold breach are understandable.
- [ ] Stop condition passes before Stage 9 starts.

## Stage 9: Power BI Export Tables

- [ ] `src/09_generate_powerbi_tables.py` exists.
- [ ] `data/processed/pbi_cluster_daily_metrics.csv` exists.
- [ ] `data/processed/pbi_cluster_monthly_metrics.csv` exists.
- [ ] `data/processed/pbi_capacity_inventory.csv` exists.
- [ ] `data/processed/pbi_cluster_capacity_daily.csv` exists.
- [ ] `data/processed/pbi_cluster_capacity_monthly.csv` exists.
- [ ] `data/processed/pbi_forecast_results.csv` exists.
- [ ] `data/processed/pbi_model_backtest_results.csv` exists.
- [ ] `data/processed/pbi_capacity_risk_summary.csv` exists.
- [ ] No exported CSV contains an index column.
- [ ] Date formats are consistent.
- [ ] Percentage fields use consistent `0-100` representation.
- [ ] Debug fields are excluded.
- [ ] Stop condition passes before Stage 10 starts.

## Stage 10: Documentation and README

- [ ] `README.md` includes the business problem.
- [ ] `README.md` includes the dataset description.
- [ ] `README.md` includes tools used.
- [ ] `README.md` includes methodology.
- [ ] `README.md` includes parsing and ingestion decisions.
- [ ] `README.md` includes feature engineering.
- [ ] `README.md` includes capacity inventory simulation.
- [ ] `README.md` includes forecasting and backtesting.
- [ ] `README.md` includes risk scoring logic.
- [ ] `README.md` includes Power BI dashboard design.
- [ ] `README.md` includes key outputs.
- [ ] `README.md` includes limitations.
- [ ] `README.md` includes how to run.
- [ ] `README.md` includes honest resume bullets.
- [ ] `docs/methodology.md` exists.
- [ ] `docs/limitations.md` exists.
- [ ] Required limitation statement is present.
- [ ] Required daily forecasting-history statement is present.
- [ ] Documentation does not claim real enterprise storage inventory.
- [ ] Documentation does not claim FedEx production data or Dell product experience.
