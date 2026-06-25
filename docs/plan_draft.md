You are working inside the current repository. Use Superpowers-style planning.

Do not start implementation yet.

First inspect:

* repository structure
* AGENTS.md
* docs/manual_dataset_notes.md
* data/raw folder structure
* sample raw CSV files

Then create a detailed stage-by-stage implementation plan.

Project objective:
Build an Enterprise Storage Capacity Forecasting and Risk Dashboard using the Kaggle GWA-Bitbrains datacenter VM traces. The final project should process real VM workload traces, engineer infrastructure workload features, create a clearly labeled simulated enterprise storage capacity inventory layer, benchmark forecasting models, generate storage capacity risk scores, and export clean CSV tables for a manually built Power BI dashboard.

Business question:
Which infrastructure storage clusters are likely to hit utilization risk thresholds in the next 3 to 6 months, and what action should leadership take?

Important dataset context:
The Bitbrains dataset contains real datacenter VM workload traces such as CPU usage, memory usage, disk read/write throughput, network throughput, and timestamps.

The dataset does not contain real enterprise storage capacity inventory fields such as raw capacity, usable capacity, metadata overhead, protection overhead, reserved capacity, datacenter ownership, business unit ownership, or expansion recommendations. Those fields must be simulated and clearly labeled as simulated.

Important raw file context:

* Raw files are .csv.
* The files are not normal comma CSV files.
* Rows are semicolon-delimited with optional whitespace/tab after semicolons.
* Use delimiter logic equivalent to regex `;\s*`.
* Some rows may be wrapped in double quotes, so strip outer quotes before splitting.
* The timestamp header says `Timestamp [ms]`, but sample values look like Unix seconds. Do not blindly trust the header.
* Example timestamp: `1376314846`, which maps to 2013 if interpreted as Unix seconds.
* The raw dataset may be nested like `data/raw/fastStorage/2013-8/`.
* The scripts must recursively scan under `data/raw`.

Do not claim:

* FedEx production data
* Dell ECS experience
* Dell PowerScale experience
* ServiceNow experience
* PDSM experience
* Real enterprise storage inventory from the dataset

Planning outputs required before coding:
Create these documents:

1. docs/implementation_plan.md
2. docs/data_assumptions.md
3. docs/validation_checklist.md
4. docs/powerbi_dashboard_plan.md

The implementation plan must be stage-based. Each stage must include:

* Goal
* Files to create or modify
* Inputs
* Outputs
* Logic
* Validation checks
* Stop condition before moving to next stage

Required stages:

Stage 0: Raw data profiling

Create later:
src/00_profile_raw_data.py

Goal:
Profile the raw dataset before ingestion.

Required logic:

* Recursively scan all .csv files under data/raw.
* Count total files.
* Count files by trace_type.
* Count files by source_month_folder.
* Infer trace_type from path parts such as fastStorage or Rnd.
* Infer source_month_folder from path parts such as 2013-8.
* Inspect at least 2 sample files.
* Detect whether rows are wrapped in double quotes.
* Detect delimiter pattern.
* Detect column count.
* Detect whether header row exists.
* Infer timestamp unit from magnitude:

  * if timestamp is around 1,000,000,000 to 2,000,000,000, treat as Unix seconds
  * if timestamp is around 1,000,000,000,000, treat as Unix milliseconds
* Write parsed sample rows.

Expected outputs:

* data/processed/raw_data_profile.csv
* docs/data_profile_summary.md

Stop condition:
Do not proceed to ingestion unless the profiler confirms parsed rows have 11 expected columns and datetime conversion produces 2013 dates for sample timestamps.

Stage 1: Data ingestion

Create later:
src/01_ingest_bitbrains.py

Goal:
Read raw VM trace files into a clean standardized VM-level dataset.

Parsing requirements:

* Recursively read all .csv files under data/raw.
* Treat each file as one VM trace.
* Strip outer double quotes from each line if present.
* Split rows using semicolon with optional whitespace/tab.
* Standardize column names.
* Convert numeric columns safely.
* Infer timestamp unit from value magnitude.
* Parse datetime correctly.
* Preserve source_file.
* Preserve source_month_folder.
* Preserve trace_type.
* Assign vm_id based on source file path or filename.
* Do not use plain pd.read_csv(file) without custom parsing safeguards.
* Do not accept a one-column dataframe.

Expected outputs:

* data/processed/vm_metrics_cleaned.parquet
* data/processed/vm_metrics_sample.csv

Target standardized columns:

* source_file
* source_month_folder
* trace_type
* vm_id
* timestamp_raw
* timestamp_unit_detected
* datetime
* date
* month
* hour
* cpu_cores
* cpu_capacity_mhz
* cpu_usage_mhz
* cpu_usage_pct
* memory_capacity_kb
* memory_usage_kb
* disk_read_kbps
* disk_write_kbps
* network_rx_kbps
* network_tx_kbps

Validation checks:

* datetime should show 2013 dates for sample values, not 1970.
* Numeric columns should be numeric.
* trace_type should be populated from path.
* source_month_folder should be populated from path.
* vm_id should be unique per source file.
* If more than 5% of rows fail parsing, stop and write an error summary instead of continuing.

Stage 2: Feature engineering

Create later:
src/02_feature_engineering.py

Goal:
Create useful infrastructure workload features.

Input:
data/processed/vm_metrics_cleaned.parquet

Derived fields:

* memory_utilization_pct
* disk_total_kbps
* network_total_kbps
* disk_write_ratio
* disk_read_ratio
* is_high_disk_spike

High disk spike definition:
disk_total_kbps above the VM-level 95th percentile.

Expected output:
data/processed/vm_daily_metrics.csv

Daily aggregation columns:

* vm_id
* trace_type
* date
* avg_memory_utilization_pct
* p95_memory_utilization_pct
* avg_disk_read_kbps
* avg_disk_write_kbps
* avg_disk_total_kbps
* p95_disk_total_kbps
* avg_network_total_kbps
* high_disk_spike_count

Validation checks:

* No negative disk throughput values.
* No impossible memory utilization values without explanation.
* One row per VM per day.
* p95 fields are present.
* high_disk_spike_count is not all zero.

Stage 3: Cluster assignment

Create later:
src/03_assign_clusters.py

Goal:
Assign VM traces into simulated enterprise storage clusters.

Input:
data/processed/vm_daily_metrics.csv

Use deterministic random seed:
42

Create approximately 20 clusters.

Cluster fields:

* cluster_name
* datacenter
* business_unit
* storage_platform
* trace_type

Suggested datacenters:

* Memphis
* Indianapolis
* Dallas
* Atlanta

Suggested business units:

* Logistics
* Operations
* Finance
* Customer Systems
* Analytics

Storage platform mapping:

* fastStorage = Fast SAN-style storage
* Rnd = Mixed SAN/NAS-style storage

If Rnd does not exist in the raw data, support only fastStorage but document the limitation.

Expected output:
data/processed/vm_cluster_mapping.csv

Validation checks:

* Every VM maps to one cluster.
* Every cluster has multiple VMs where possible.
* trace_type is preserved.
* datacenter and business unit assignment is deterministic.

Stage 4: Monthly cluster metrics

Create later:
src/04_build_monthly_cluster_metrics.py

Goal:
Aggregate daily VM metrics into monthly cluster-level metrics.

Inputs:

* data/processed/vm_daily_metrics.csv
* data/processed/vm_cluster_mapping.csv

Expected output:
data/processed/cluster_monthly_metrics.csv

Columns:

* month
* cluster_name
* datacenter
* business_unit
* storage_platform
* vm_count
* avg_memory_utilization_pct
* p95_memory_utilization_pct
* avg_disk_read_kbps
* avg_disk_write_kbps
* avg_disk_total_kbps
* p95_disk_total_kbps
* avg_network_total_kbps
* high_disk_spike_count

Validation checks:

* One row per cluster per month.
* No missing cluster names.
* Month field is valid.
* p95 disk throughput exists.
* VM count is positive.

Stage 5: Simulated capacity inventory

Create later:
src/05_create_capacity_inventory.py

Goal:
Create a clearly labeled simulated enterprise storage capacity inventory layer.

Input:
data/processed/cluster_monthly_metrics.csv

Expected output:
data/processed/capacity_inventory.csv

Columns:

* cluster_name
* datacenter
* business_unit
* storage_platform
* raw_capacity_tb
* usable_capacity_tb
* protection_overhead_pct
* metadata_overhead_pct
* reserved_capacity_pct
* inventory_type

Set:
inventory_type = Simulated

Capacity rules:

For Fast SAN-style storage:

* raw_capacity_tb: 800 to 2500
* usable capacity ratio: 72% to 82%
* metadata overhead: 3% to 6%
* protection overhead: 12% to 22%
* reserved capacity: 5% to 10%

For Mixed SAN/NAS-style storage:

* raw_capacity_tb: 500 to 1800
* usable capacity ratio: 65% to 78%
* metadata overhead: 4% to 8%
* protection overhead: 15% to 28%
* reserved capacity: 7% to 12%

Validation checks:

* Usable capacity is always less than raw capacity.
* Every cluster has exactly one capacity inventory row.
* Overhead percentages are plausible.
* No negative capacity values.
* inventory_type is populated.

Stage 6: Estimated capacity usage

Create later:
src/06_estimate_capacity_usage.py

Goal:
Convert disk write workload pressure into estimated monthly storage growth and utilization.

Inputs:

* data/processed/cluster_monthly_metrics.csv
* data/processed/capacity_inventory.csv

Use:
retention_factor = 0.08

Logic:

* monthly_write_tb_estimate = avg_disk_write_kbps converted into monthly TB
* net_new_storage_tb = monthly_write_tb_estimate * retention_factor
* starting_used_tb = 35% to 70% of usable capacity
* used_capacity_tb = starting_used_tb + cumulative monthly growth
* free_capacity_tb = usable_capacity_tb - used_capacity_tb
* capacity_utilization_pct = used_capacity_tb / usable_capacity_tb

Expected output:
data/processed/cluster_capacity_monthly.csv

Validation checks:

* Utilization starts in a realistic range.
* Utilization changes over time.
* Some clusters approach 75%, 80%, or 85%.
* Not every cluster is low risk.
* Not every cluster is critical.
* Used capacity should not become negative.
* If used capacity exceeds usable capacity, it should be rare and explainable as a breach scenario.

Stage 7: Forecasting and backtesting

Create later:
src/07_forecasting_backtest.py

Goal:
Benchmark forecasting models and forecast storage usage 6 months forward.

Input:
data/processed/cluster_capacity_monthly.csv

Forecast target:
used_capacity_tb

Models:

1. Naive baseline
2. 3-month moving average
3. Holt linear trend
4. Exponential smoothing

Do not make linear regression the main forecasting method.

Backtesting logic:
For each cluster:

* Use earlier months as training data.
* Use most recent months as testing data.
* Calculate MAE, RMSE, and MAPE.
* Select best model by lowest MAPE.
* Forecast next 6 months.

Expected outputs:

* data/processed/model_backtest_results.csv
* data/processed/forecast_results.csv

model_backtest_results.csv columns:

* cluster_name
* model_name
* mae
* rmse
* mape
* selected_model_flag

forecast_results.csv columns:

* cluster_name
* forecast_month
* selected_model
* forecast_used_tb
* forecast_utilization_pct
* forecast_free_capacity_tb
* breach_80_flag
* breach_85_flag
* breach_90_flag

Validation checks:

* Every cluster has model results.
* Every cluster has one selected model.
* Every cluster has 6 forecast months.
* MAE, RMSE, and MAPE are present.
* Forecast utilization is not negative.
* Forecast free capacity can decline over time.
* At least some clusters breach 80% or 85% if data and simulated utilization support it.

Stage 8: Risk scoring and recommendations

Create later:
src/08_capacity_risk_scoring.py

Goal:
Translate forecasts into risk levels and business recommendations.

Inputs:

* data/processed/cluster_capacity_monthly.csv
* data/processed/forecast_results.csv
* data/processed/capacity_inventory.csv

Expected output:
data/processed/capacity_risk_summary.csv

Columns:

* cluster_name
* datacenter
* business_unit
* storage_platform
* current_used_tb
* usable_capacity_tb
* current_utilization_pct
* forecast_3mo_utilization_pct
* forecast_6mo_utilization_pct
* months_until_80_pct
* months_until_85_pct
* months_until_90_pct
* monthly_growth_tb
* risk_level
* recommended_action

Risk rules:

Critical:

* current_utilization_pct >= 90%
* OR forecast crosses 90% within 3 months

High:

* current_utilization_pct >= 85%
* OR forecast crosses 85% within 6 months

Medium:

* current_utilization_pct >= 75%
* OR monthly_growth_tb is in top 25% of clusters

Low:

* everything else

Recommended actions:

Critical:
Expand capacity immediately and validate workload drivers.

High:
Plan capacity expansion within the next planning cycle.

Medium:
Monitor weekly and optimize storage overhead.

Low:
No immediate action required.

Validation checks:

* Risk levels are not all the same.
* Recommended action maps correctly to risk level.
* Clusters above thresholds are correctly flagged.
* Forecast breach months are easy to understand.

Stage 9: Power BI export tables

Create later:
src/09_generate_powerbi_tables.py

Goal:
Create clean, flat, dashboard-ready CSV files for Power BI.

Inputs:

* data/processed/cluster_monthly_metrics.csv
* data/processed/capacity_inventory.csv
* data/processed/cluster_capacity_monthly.csv
* data/processed/model_backtest_results.csv
* data/processed/forecast_results.csv
* data/processed/capacity_risk_summary.csv

Expected outputs:

* data/processed/pbi_cluster_monthly_metrics.csv
* data/processed/pbi_capacity_inventory.csv
* data/processed/pbi_cluster_capacity_monthly.csv
* data/processed/pbi_forecast_results.csv
* data/processed/pbi_model_backtest_results.csv
* data/processed/pbi_capacity_risk_summary.csv

Validation checks:

* CSVs open cleanly.
* No index columns.
* Clean column names.
* Consistent date formats.
* Percent fields are represented consistently.
* No unnecessary debug fields.

Stage 10: Documentation and README

Create or update:

* README.md
* docs/methodology.md
* docs/limitations.md
* docs/powerbi_dashboard_plan.md

README must include:

* Business problem
* Dataset
* Tools
* Methodology
* Parsing and ingestion decisions
* Feature engineering
* Capacity inventory simulation
* Forecasting and backtesting
* Risk scoring logic
* Power BI dashboard design
* Key outputs
* Limitations
* How to run
* Resume bullets

Required limitation statement:
The Bitbrains dataset contains real VM-level datacenter workload traces, including CPU, memory, disk I/O, and network activity. It does not include actual enterprise storage inventory. Raw capacity, usable capacity, protection overhead, metadata overhead, datacenter ownership, business unit ownership, and recommended actions were simulated to create a realistic capacity planning layer for portfolio demonstration.

Before coding:
Create the four planning documents and summarize:

1. What you found in the repo
2. What you found in data/raw
3. Any risks or uncertainties
4. The exact implementation sequence you recommend
5. Any questions that must be answered before coding

Do not implement code until I approve the plan.
