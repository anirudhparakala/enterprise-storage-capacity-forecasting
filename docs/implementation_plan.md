# Enterprise Storage Capacity Forecasting and Risk Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an Enterprise Storage Capacity Forecasting and Risk Dashboard from Kaggle GWA-Bitbrains VM traces, ending with clean Power BI-ready CSV tables and documented simulated storage inventory assumptions.

**Architecture:** Use a staged, file-based Python pipeline under `src/`, with each stage reading validated outputs from the prior stage and writing named artifacts under `data/processed/`. Daily cluster-level history is the analytical spine for capacity usage, forecasting, and risk scoring because the available Kaggle extraction contains one month folder; monthly tables are retained as Power BI summary outputs. Real Bitbrains VM workload telemetry remains separate from clearly labeled simulated enterprise storage inventory, ownership, and recommendation fields.

**Tech Stack:** Python, pandas, numpy, pyarrow, scikit-learn metrics, statsmodels forecasting, CSV and Parquet outputs, Power BI as the manual dashboard layer.

## Global Constraints

- Do not start implementation until this plan is approved.
- Raw trace files are `.csv` files nested recursively under `data/raw`.
- Raw rows are semicolon-delimited with optional whitespace or tab after semicolons; parser logic must be equivalent to regex `;\s*`.
- Some rows may be wrapped in double quotes; strip outer quotes before splitting.
- Do not use plain `pd.read_csv(file)` without custom parsing safeguards.
- Do not accept a one-column dataframe as valid ingestion.
- The timestamp header says `Timestamp [ms]`, but sample values such as `1376314846` map to 2013 when interpreted as Unix seconds.
- Planning inspection found only one month folder, `data/raw/fastStorage/2013-8`; do not design forecasting around monthly backtesting unless additional month folders are added and validated.
- Forecasting must be performed on daily cluster-level capacity history and then summarized into 30-day, 90-day, and 180-day planning windows.
- Simulated fields must be labeled as simulated and must not be presented as real enterprise inventory.
- Do not claim FedEx production data, Dell ECS experience, Dell PowerScale experience, ServiceNow experience, PDSM experience, or real enterprise storage inventory from this dataset.
- Final Power BI work is manual; this pipeline exports clean CSV tables for the dashboard.

---

## Repository Findings

- `AGENTS.md` exists and is empty.
- `README.md` exists and is empty.
- `requirements.txt` already includes `pandas`, `numpy`, `scikit-learn`, `statsmodels`, `matplotlib`, `seaborn`, `pyarrow`, and `openpyxl`.
- `docs/plan_draft.md` contains the project objective and stage requirements.
- `docs/manual_dataset_notes.md` does not exist.
- `src/` currently exists and is empty.
- `data/raw` contains `1250` CSV files under `data/raw/fastStorage/2013-8`.
- No `Rnd` trace folder was found during planning inspection.
- Sample files `1.csv` and `10.csv` have a header row and 11 semicolon-delimited columns.
- Sample timestamp `1376314846` converts to `2013-08-12 13:40:46` as Unix seconds.

## Implementation Sequence

1. Stage 0 profiles raw data and proves the parser assumptions.
2. Stage 1 ingests raw VM traces into a standardized VM-level Parquet dataset.
3. Stage 2 engineers daily VM workload features.
4. Stage 3 assigns VMs to simulated enterprise storage clusters.
5. Stage 4 aggregates daily and monthly cluster workload metrics.
6. Stage 5 creates clearly labeled simulated capacity inventory.
7. Stage 6 estimates daily capacity usage and derives monthly capacity summaries.
8. Stage 7 benchmarks forecasting models on daily capacity history and produces 180 daily forecasts.
9. Stage 8 scores capacity risk using daily forecasts and 30-day, 90-day, and 180-day planning windows.
10. Stage 9 exports clean Power BI CSV tables.
11. Stage 10 completes README and methodology documentation.

## Shared Implementation Conventions

- Create helper functions inside each stage script first; extract shared helpers only if duplication becomes substantial across stages.
- Use `Path("data/raw").rglob("*.csv")` for recursive discovery.
- Use deterministic seeds for every simulated field: `numpy.random.default_rng(42)`.
- Write every data artifact to `data/processed/`; create the directory if missing.
- Use ISO date strings in CSV outputs: dates as `YYYY-MM-DD`, months as `YYYY-MM-01`.
- Keep percentages consistently represented as `0-100` values in exported tables.
- Fail loudly with a clear validation summary when a stage's stop condition is not met.

---

### Stage 0: Raw Data Profiling

**Goal:** Profile the raw dataset before ingestion and prove that the custom parser can read valid 11-column rows with 2013 timestamps.

**Files:**
- Create: `src/00_profile_raw_data.py`
- Create output: `data/processed/raw_data_profile.csv`
- Create output: `docs/data_profile_summary.md`

**Inputs:**
- `data/raw/**/*.csv`

**Outputs:**
- `data/processed/raw_data_profile.csv`
- `docs/data_profile_summary.md`

**Logic:**
- Recursively discover all `.csv` files below `data/raw`.
- Count total files.
- Count files by `trace_type`, inferred from path parts matching known values such as `fastStorage` or `Rnd`.
- Count files by `source_month_folder`, inferred from path parts matching `YYYY-M` or `YYYY-MM`.
- Inspect at least two sample files; use the first two discovered files sorted by path for deterministic behavior.
- Read raw text lines rather than relying on pandas CSV parsing.
- Strip a single pair of outer double quotes from each line when present.
- Split each cleaned line using regex `;\s*`.
- Detect whether a header row exists by checking for `Timestamp` in the first parsed cell.
- Detect delimiter pattern by confirming semicolon separators and 11 parsed fields.
- Detect column count for header and sample data rows.
- Infer timestamp units from magnitude:
  - `1_000_000_000 <= value <= 2_000_000_000`: Unix seconds.
  - `1_000_000_000_000 <= value`: Unix milliseconds.
- Convert sample timestamps to datetimes and record whether they are in 2013.
- Write parsed sample rows and file-level profile records.
- Write a Markdown summary with dataset shape, parser findings, timestamp finding, and any discovered limitations such as absence of `Rnd`.

**Validation checks:**
- `raw_data_profile.csv` exists and has at least one row.
- Total file count is greater than zero.
- At least two files are sampled when at least two files exist.
- Parsed sample rows have exactly 11 columns.
- Header row has exactly 11 columns.
- Timestamp unit detection returns `seconds` for sample value `1376314846`.
- Datetime conversion produces 2013 dates for sampled rows.

**Stop condition before moving to Stage 1:**
- Proceed only if sampled data rows parse to 11 expected columns and sample timestamp conversion produces 2013 dates.

**Step-by-step implementation checklist:**
- [ ] Create `src/00_profile_raw_data.py` with constants for raw root, processed root, and expected column count.
- [ ] Add `discover_raw_files(raw_root: Path) -> list[Path]`.
- [ ] Add `infer_trace_type(path: Path) -> str` using path parts; return `Unknown` only when no known trace type is found.
- [ ] Add `infer_source_month_folder(path: Path) -> str` using regex `^\d{4}-\d{1,2}$`.
- [ ] Add `clean_raw_line(line: str) -> str` to trim whitespace and remove one pair of outer quotes.
- [ ] Add `split_trace_line(line: str) -> list[str]` using regex `;\s*`.
- [ ] Add `infer_timestamp_unit(value: float) -> str`.
- [ ] Add `profile_file(path: Path) -> dict` that records wrapping, delimiter, header, column count, timestamp unit, converted datetime, and parsed sample rows.
- [ ] Add `main()` to profile discovered files, write CSV, write Markdown summary, and enforce the stop condition.
- [ ] Run `python src/00_profile_raw_data.py`.
- [ ] Confirm `data/processed/raw_data_profile.csv` and `docs/data_profile_summary.md` were created.
- [ ] Commit with message `feat: profile raw bitbrains traces`.

---

### Stage 1: Data Ingestion

**Goal:** Read raw VM trace files into a clean standardized VM-level dataset.

**Files:**
- Create: `src/01_ingest_bitbrains.py`
- Create output: `data/processed/vm_metrics_cleaned.parquet`
- Create output: `data/processed/vm_metrics_sample.csv`
- Optional create output on failure: `data/processed/ingestion_error_summary.csv`

**Inputs:**
- `data/raw/**/*.csv`
- `data/processed/raw_data_profile.csv`

**Outputs:**
- `data/processed/vm_metrics_cleaned.parquet`
- `data/processed/vm_metrics_sample.csv`

**Target columns:**
- `source_file`
- `source_month_folder`
- `trace_type`
- `vm_id`
- `timestamp_raw`
- `timestamp_unit_detected`
- `datetime`
- `date`
- `month`
- `hour`
- `cpu_cores`
- `cpu_capacity_mhz`
- `cpu_usage_mhz`
- `cpu_usage_pct`
- `memory_capacity_kb`
- `memory_usage_kb`
- `disk_read_kbps`
- `disk_write_kbps`
- `network_rx_kbps`
- `network_tx_kbps`

**Logic:**
- Reuse Stage 0 parser conventions.
- Treat each raw file as one VM trace.
- Assign `vm_id` from the relative file path without extension, normalized to a stable string such as `fastStorage_2013-8_1`.
- Preserve `source_file`, `source_month_folder`, and `trace_type`.
- Skip the header row when present.
- Parse exactly 11 raw columns into standardized column names.
- Convert numeric fields with `pd.to_numeric(errors="coerce")`.
- Infer timestamp unit per row or per file from timestamp magnitude; record the detected unit.
- Convert timestamp to pandas datetime using seconds or milliseconds as detected.
- Create `date`, `month`, and `hour`.
- Count failed parse rows and numeric conversion failures.
- If more than 5% of data rows fail parsing, write `ingestion_error_summary.csv` and stop without writing the final Parquet.
- Write a sample CSV for manual inspection.

**Validation checks:**
- No accepted row has one column.
- Datetime values show 2013 dates for the inspected sample.
- Numeric columns have numeric dtypes.
- `trace_type` is populated.
- `source_month_folder` is populated.
- Each `source_file` maps to one `vm_id`.
- Failed parse rate is less than or equal to 5%.

**Stop condition before moving to Stage 2:**
- Proceed only if `vm_metrics_cleaned.parquet` exists, has the target columns, and passes validation checks.

**Step-by-step implementation checklist:**
- [ ] Create `src/01_ingest_bitbrains.py`.
- [ ] Copy or import parser helper logic from Stage 0 in a minimal way that avoids broad refactors.
- [ ] Add a canonical raw column list matching the 11 Bitbrains columns.
- [ ] Add `parse_trace_file(path: Path, raw_root: Path) -> tuple[pd.DataFrame, dict]`.
- [ ] Add robust row rejection for blank lines, malformed column counts, and nonnumeric timestamps.
- [ ] Add `build_vm_id(path: Path, raw_root: Path) -> str`.
- [ ] Add datetime parsing that uses seconds for 10-digit Unix values and milliseconds for 13-digit Unix values.
- [ ] Add `validate_ingested(df: pd.DataFrame, error_summary: pd.DataFrame) -> None`.
- [ ] Write `vm_metrics_cleaned.parquet` and `vm_metrics_sample.csv`.
- [ ] Run `python src/01_ingest_bitbrains.py`.
- [ ] Inspect the first rows of `data/processed/vm_metrics_sample.csv`.
- [ ] Commit with message `feat: ingest bitbrains vm metrics`.

---

### Stage 2: Feature Engineering

**Goal:** Create VM-level daily workload features for storage-oriented analysis.

**Files:**
- Create: `src/02_feature_engineering.py`
- Create output: `data/processed/vm_daily_metrics.csv`

**Inputs:**
- `data/processed/vm_metrics_cleaned.parquet`

**Outputs:**
- `data/processed/vm_daily_metrics.csv`

**Logic:**
- Read the cleaned Parquet dataset.
- Compute `memory_utilization_pct = memory_usage_kb / memory_capacity_kb * 100` only when memory capacity is greater than zero.
- Compute `disk_total_kbps = disk_read_kbps + disk_write_kbps`.
- Compute `network_total_kbps = network_rx_kbps + network_tx_kbps`.
- Compute `disk_write_ratio = disk_write_kbps / disk_total_kbps` when disk total is greater than zero.
- Compute `disk_read_ratio = disk_read_kbps / disk_total_kbps` when disk total is greater than zero.
- Compute VM-level 95th percentile of `disk_total_kbps`.
- Flag `is_high_disk_spike` when a row's `disk_total_kbps` is above that VM-level 95th percentile.
- Aggregate to one row per `vm_id`, `trace_type`, and `date`.

**Daily aggregation columns:**
- `vm_id`
- `trace_type`
- `date`
- `avg_memory_utilization_pct`
- `p95_memory_utilization_pct`
- `avg_disk_read_kbps`
- `avg_disk_write_kbps`
- `avg_disk_total_kbps`
- `p95_disk_total_kbps`
- `avg_network_total_kbps`
- `high_disk_spike_count`

**Validation checks:**
- No negative disk throughput values.
- Impossible memory utilization values, such as values below 0 or far above 100, are counted and explained in a validation summary printed by the script.
- Output has one row per VM per day.
- `p95_memory_utilization_pct` and `p95_disk_total_kbps` exist.
- `high_disk_spike_count` is not all zero.

**Stop condition before moving to Stage 3:**
- Proceed only if `vm_daily_metrics.csv` exists, one-row-per-VM-per-day uniqueness holds, and disk spike counts are not all zero.

**Step-by-step implementation checklist:**
- [ ] Create `src/02_feature_engineering.py`.
- [ ] Add feature calculations with divide-by-zero safeguards.
- [ ] Add VM-level p95 disk threshold calculation.
- [ ] Add daily aggregation.
- [ ] Add validation assertions for uniqueness and nonnegative disk metrics.
- [ ] Run `python src/02_feature_engineering.py`.
- [ ] Confirm `data/processed/vm_daily_metrics.csv` contains daily VM rows.
- [ ] Commit with message `feat: engineer vm daily workload features`.

---

### Stage 3: Cluster Assignment

**Goal:** Assign VM traces into deterministic simulated enterprise storage clusters.

**Files:**
- Create: `src/03_assign_clusters.py`
- Create output: `data/processed/vm_cluster_mapping.csv`
- Update: `docs/data_assumptions.md` if discovered trace types differ from planning assumptions.

**Inputs:**
- `data/processed/vm_daily_metrics.csv`

**Outputs:**
- `data/processed/vm_cluster_mapping.csv`

**Logic:**
- Read unique VM IDs and trace types from daily metrics.
- Use deterministic random seed `42`.
- Create approximately 20 clusters. If the VM count is too small, cap clusters so each cluster can receive at least one VM.
- Preserve trace type in cluster assignment.
- Use datacenters: `Memphis`, `Indianapolis`, `Dallas`, `Atlanta`.
- Use business units: `Logistics`, `Operations`, `Finance`, `Customer Systems`, `Analytics`.
- Map `fastStorage` to `Fast SAN-style storage`.
- Map `Rnd` to `Mixed SAN/NAS-style storage`.
- If `Rnd` is absent, create only `fastStorage` cluster assignments and document that limitation.
- Assign every VM to exactly one cluster.

**Cluster mapping columns:**
- `vm_id`
- `trace_type`
- `cluster_name`
- `datacenter`
- `business_unit`
- `storage_platform`

**Validation checks:**
- Every VM maps to one cluster.
- Every cluster has multiple VMs where possible.
- `trace_type` is preserved.
- Datacenter and business unit assignment is deterministic across reruns.

**Stop condition before moving to Stage 4:**
- Proceed only if every VM appears exactly once in `vm_cluster_mapping.csv`.

**Step-by-step implementation checklist:**
- [ ] Create `src/03_assign_clusters.py`.
- [ ] Add deterministic cluster name generation such as `FS-CLUSTER-01` for fastStorage and `RND-CLUSTER-01` for Rnd when present.
- [ ] Add storage platform mapping.
- [ ] Add round-robin or seeded assignment so cluster sizes are balanced where possible.
- [ ] Add validation for one mapping per VM.
- [ ] Run `python src/03_assign_clusters.py`.
- [ ] Confirm mappings are stable by rerunning and checking row counts and cluster names remain unchanged.
- [ ] Commit with message `feat: assign simulated storage clusters`.

---

### Stage 4: Daily and Monthly Cluster Metrics

**Goal:** Aggregate daily VM metrics into daily cluster-level workload metrics, then derive monthly cluster-level summary metrics for dashboard use.

**Files:**
- Create: `src/04_build_monthly_cluster_metrics.py`
- Create output: `data/processed/cluster_daily_metrics.csv`
- Create output: `data/processed/cluster_monthly_metrics.csv`

**Inputs:**
- `data/processed/vm_daily_metrics.csv`
- `data/processed/vm_cluster_mapping.csv`

**Outputs:**
- `data/processed/cluster_daily_metrics.csv`
- `data/processed/cluster_monthly_metrics.csv`

**Logic:**
- Join VM daily metrics to cluster mapping on `vm_id`.
- Convert `date` to datetime.
- Build `cluster_daily_metrics.csv` by grouping by `date`, `cluster_name`, `datacenter`, `business_unit`, and `storage_platform`.
- Count distinct VMs for each cluster-day.
- Average daily VM metrics into daily cluster metrics.
- Sum `high_disk_spike_count` across VMs for each cluster-day.
- Derive first-of-month `month` from `date`.
- Build `cluster_monthly_metrics.csv` from the daily cluster table by grouping by `month`, `cluster_name`, `datacenter`, `business_unit`, and `storage_platform`.
- Monthly metrics are dashboard summaries only; forecasting must use the daily cluster capacity table produced in Stage 6.

**`cluster_daily_metrics.csv` columns:**
- `date`
- `cluster_name`
- `datacenter`
- `business_unit`
- `storage_platform`
- `vm_count`
- `avg_memory_utilization_pct`
- `p95_memory_utilization_pct`
- `avg_disk_read_kbps`
- `avg_disk_write_kbps`
- `avg_disk_total_kbps`
- `p95_disk_total_kbps`
- `avg_network_total_kbps`
- `high_disk_spike_count`

**`cluster_monthly_metrics.csv` columns:**
- `month`
- `cluster_name`
- `datacenter`
- `business_unit`
- `storage_platform`
- `vm_count`
- `avg_memory_utilization_pct`
- `p95_memory_utilization_pct`
- `avg_disk_read_kbps`
- `avg_disk_write_kbps`
- `avg_disk_total_kbps`
- `p95_disk_total_kbps`
- `avg_network_total_kbps`
- `high_disk_spike_count`

**Validation checks:**
- Daily output has one row per cluster per date.
- One row per cluster per month.
- No missing cluster names.
- Date field is valid.
- Month field is valid.
- `p95_disk_total_kbps` exists and is numeric in both daily and monthly outputs.
- `vm_count` is positive.

**Stop condition before moving to Stage 5:**
- Proceed only if there are no duplicate `date` and `cluster_name` combinations in the daily table and no duplicate `month` and `cluster_name` combinations in the monthly table.

**Step-by-step implementation checklist:**
- [ ] Create `src/04_build_monthly_cluster_metrics.py`.
- [ ] Add input existence checks.
- [ ] Add join validation that rejects missing cluster mappings.
- [ ] Add daily cluster aggregation.
- [ ] Add monthly cluster aggregation derived from the daily cluster table.
- [ ] Add output column ordering for both daily and monthly tables.
- [ ] Run `python src/04_build_monthly_cluster_metrics.py`.
- [ ] Confirm `cluster_daily_metrics.csv` has one row per cluster-date.
- [ ] Confirm `cluster_monthly_metrics.csv` has one row per cluster-month.
- [ ] Commit with message `feat: build cluster workload metrics`.

---

### Stage 5: Simulated Capacity Inventory

**Goal:** Create a clearly labeled simulated enterprise storage capacity inventory layer.

**Files:**
- Create: `src/05_create_capacity_inventory.py`
- Create output: `data/processed/capacity_inventory.csv`
- Update: `docs/data_assumptions.md`

**Inputs:**
- `data/processed/cluster_monthly_metrics.csv`

**Outputs:**
- `data/processed/capacity_inventory.csv`

**Logic:**
- Read unique clusters and their dimensional fields.
- Use deterministic random seed `42`.
- Generate exactly one inventory row per cluster.
- Set `inventory_type = Simulated`.
- For `Fast SAN-style storage`:
  - `raw_capacity_tb`: 800 to 2500.
  - Usable capacity ratio: 72% to 82%.
  - Metadata overhead: 3% to 6%.
  - Protection overhead: 12% to 22%.
  - Reserved capacity: 5% to 10%.
- For `Mixed SAN/NAS-style storage`:
  - `raw_capacity_tb`: 500 to 1800.
  - Usable capacity ratio: 65% to 78%.
  - Metadata overhead: 4% to 8%.
  - Protection overhead: 15% to 28%.
  - Reserved capacity: 7% to 12%.
- Compute `usable_capacity_tb = raw_capacity_tb * usable_capacity_ratio`.
- Round capacities to one decimal place and percentages to two decimal places.

**Output columns:**
- `cluster_name`
- `datacenter`
- `business_unit`
- `storage_platform`
- `raw_capacity_tb`
- `usable_capacity_tb`
- `protection_overhead_pct`
- `metadata_overhead_pct`
- `reserved_capacity_pct`
- `inventory_type`

**Validation checks:**
- Usable capacity is always less than raw capacity.
- Every cluster has exactly one inventory row.
- Overhead percentages fall within configured ranges.
- No negative capacity values.
- `inventory_type` is populated and equals `Simulated`.

**Stop condition before moving to Stage 6:**
- Proceed only if each cluster has exactly one simulated capacity row and all capacity values are positive.

**Step-by-step implementation checklist:**
- [ ] Create `src/05_create_capacity_inventory.py`.
- [ ] Add platform-specific capacity range configuration.
- [ ] Add seeded inventory generation.
- [ ] Add validation for one row per cluster and plausible capacity values.
- [ ] Run `python src/05_create_capacity_inventory.py`.
- [ ] Confirm `capacity_inventory.csv` clearly labels every row as simulated.
- [ ] Commit with message `feat: create simulated capacity inventory`.

---

### Stage 6: Estimated Capacity Usage

**Goal:** Convert disk write workload pressure into estimated daily storage growth and utilization, then derive monthly capacity summaries for Power BI.

**Files:**
- Create: `src/06_estimate_capacity_usage.py`
- Create output: `data/processed/cluster_capacity_daily.csv`
- Create output: `data/processed/cluster_capacity_monthly.csv`
- Update: `docs/data_assumptions.md`

**Inputs:**
- `data/processed/cluster_daily_metrics.csv`
- `data/processed/capacity_inventory.csv`

**Outputs:**
- `data/processed/cluster_capacity_daily.csv`
- `data/processed/cluster_capacity_monthly.csv`

**Logic:**
- Join daily cluster metrics to capacity inventory on `cluster_name`.
- Use `retention_factor = 0.08`.
- Convert `avg_disk_write_kbps` to daily TB:
  - `daily_write_tb_estimate = avg_disk_write_kbps * 86400 / 1024 / 1024 / 1024`.
- Compute `net_new_storage_tb = daily_write_tb_estimate * retention_factor`.
- Use deterministic seed `42` to assign starting used capacity between 35% and 70% of usable capacity per cluster.
- Compute cumulative daily growth per cluster in date order.
- Compute `used_capacity_tb = starting_used_tb + cumulative net new storage`.
- Compute `free_capacity_tb = usable_capacity_tb - used_capacity_tb`.
- Compute `capacity_utilization_pct = used_capacity_tb / usable_capacity_tb * 100`.
- Write `cluster_capacity_daily.csv` as the authoritative actual capacity history for forecasting and risk scoring.
- Derive optional `cluster_capacity_monthly.csv` from the daily capacity table for Power BI summaries, using the last observed daily capacity state in each month plus monthly totals for write and net-new storage.
- If the natural workload does not create enough threshold variety, adjust only the simulated starting utilization distribution, not the real workload fields, and document the adjustment.

**`cluster_capacity_daily.csv` columns:**
- `date`
- `cluster_name`
- `datacenter`
- `business_unit`
- `storage_platform`
- `usable_capacity_tb`
- `raw_capacity_tb`
- `daily_write_tb_estimate`
- `net_new_storage_tb`
- `starting_used_tb`
- `used_capacity_tb`
- `free_capacity_tb`
- `capacity_utilization_pct`

**Optional `cluster_capacity_monthly.csv` columns:**
- `month`
- `cluster_name`
- `datacenter`
- `business_unit`
- `storage_platform`
- `usable_capacity_tb`
- `raw_capacity_tb`
- `monthly_write_tb_estimate`
- `monthly_net_new_storage_tb`
- `starting_used_tb`
- `used_capacity_tb`
- `free_capacity_tb`
- `capacity_utilization_pct`

**Validation checks:**
- Starting utilization is between 35% and 70%.
- Daily utilization changes over time for clusters with nonzero growth.
- Some clusters approach 75%, 80%, or 85% when data and simulation support it.
- Not every cluster is low risk.
- Not every cluster is critical.
- Used capacity is not negative.
- Used capacity exceeding usable capacity is rare and treated as a breach scenario.
- Monthly capacity summary is derived from daily capacity, not independently recalculated from monthly workload metrics.

**Stop condition before moving to Stage 7:**
- Proceed only if daily capacity utilization is plausible, varied, and traceable to simulated starting usage plus workload-derived daily growth.

**Step-by-step implementation checklist:**
- [ ] Create `src/06_estimate_capacity_usage.py`.
- [ ] Add daily write conversion using 86,400 seconds per day.
- [ ] Add deterministic starting utilization generation.
- [ ] Add cumulative daily growth calculation by cluster.
- [ ] Add monthly summary derivation from the completed daily capacity table.
- [ ] Add validation for negative values and utilization distribution.
- [ ] Run `python src/06_estimate_capacity_usage.py`.
- [ ] Confirm `cluster_capacity_daily.csv` contains changing daily utilization values.
- [ ] Confirm `cluster_capacity_monthly.csv` is derived from the daily table for summary reporting.
- [ ] Commit with message `feat: estimate cluster capacity usage`.

---

### Stage 7: Forecasting and Backtesting

**Goal:** Benchmark forecasting models on daily cluster capacity history and forecast storage usage 180 days forward.

**Files:**
- Create: `src/07_forecasting_backtest.py`
- Create output: `data/processed/model_backtest_results.csv`
- Create output: `data/processed/forecast_results.csv`

**Inputs:**
- `data/processed/cluster_capacity_daily.csv`

**Outputs:**
- `data/processed/model_backtest_results.csv`
- `data/processed/forecast_results.csv`

**Forecast target:**
- `used_capacity_tb`

**Frequency:**
- Daily.

**Models:**
- Naive baseline.
- 7-day moving average.
- Holt linear trend.
- Exponential smoothing.

**Logic:**
- Do not make linear regression the main forecasting method.
- For each cluster, sort rows by `date`.
- Use the earliest 70% to 80% of daily observations as training data.
- Use the remaining 20% to 30% of daily observations as the test window.
- Prefer an 80/20 split when a cluster has at least 30 daily observations; use 70/30 when a cluster has fewer than 30 but enough observations to test.
- If there are too few daily observations for a meaningful split, use a documented limited-history fallback and mark limited backtest metrics as unavailable.
- Calculate MAE, RMSE, and MAPE on the daily test window when enough test observations exist.
- Select the best model by lowest MAPE.
- Forecast the next 180 days for each cluster.
- Join usable capacity so forecast utilization and free capacity can be calculated.
- Compute breach flags at 80%, 85%, and 90% utilization.
- Derive 30-day, 90-day, and 180-day forecast utilization views in Stage 8 from the daily forecast output.

**`model_backtest_results.csv` columns:**
- `cluster_name`
- `model_name`
- `mae`
- `rmse`
- `mape`
- `selected_model_flag`

**`forecast_results.csv` columns:**
- `cluster_name`
- `forecast_date`
- `selected_model`
- `forecast_used_tb`
- `forecast_utilization_pct`
- `forecast_free_capacity_tb`
- `breach_80_flag`
- `breach_85_flag`
- `breach_90_flag`

**Validation checks:**
- Every cluster has model results.
- Every cluster has one selected model.
- Every cluster has 180 forecast dates.
- MAE, RMSE, and MAPE are present when daily history length supports backtesting.
- Forecast utilization is not negative.
- Forecast free capacity can decline over time.
- At least some clusters breach 80% or 85% if data and simulated utilization support it.

**Stop condition before moving to Stage 8:**
- Proceed only if every cluster has one selected model and 180 daily forecast rows.

**Step-by-step implementation checklist:**
- [ ] Create `src/07_forecasting_backtest.py`.
- [ ] Add metric helpers for MAE, RMSE, and MAPE with zero-actual safeguards.
- [ ] Add forecast functions for naive, moving average, Holt trend, and exponential smoothing.
- [ ] Add per-cluster daily backtest split logic using an 80/20 or 70/30 train/test split.
- [ ] Add limited-history fallback behavior.
- [ ] Add selected model choice by lowest MAPE.
- [ ] Add 180-day daily forecast generation.
- [ ] Add breach flag calculations.
- [ ] Run `python src/07_forecasting_backtest.py`.
- [ ] Confirm `forecast_results.csv` has exactly 180 forecast rows per cluster.
- [ ] Commit with message `feat: forecast cluster capacity usage`.

---

### Stage 8: Risk Scoring and Recommendations

**Goal:** Translate forecasts into risk levels and business recommendations.

**Files:**
- Create: `src/08_capacity_risk_scoring.py`
- Create output: `data/processed/capacity_risk_summary.csv`

**Inputs:**
- `data/processed/cluster_capacity_daily.csv`
- `data/processed/forecast_results.csv`
- `data/processed/capacity_inventory.csv`

**Outputs:**
- `data/processed/capacity_risk_summary.csv`

**Logic:**
- Identify the latest actual date per cluster.
- Compute current used TB, usable capacity, current utilization, and daily growth TB.
- Convert daily growth to `monthly_growth_tb` using the latest 30 actual daily net-new storage values when available.
- Extract forecast utilization at 30 days, 90 days, and 180 days from the daily forecast output.
- Compute days until crossing 80%, 85%, and 90% using forecast rows; leave blank if the threshold is not crossed within the 180-day forecast horizon.
- Derive months until crossing thresholds as `ceil(days_until_threshold / 30)` when the daily threshold value exists.
- Assign risk levels:
  - `Critical`: current utilization is at least 90% or forecast crosses 90% within 90 days.
  - `High`: current utilization is at least 85% or forecast crosses 85% within 180 days.
  - `Medium`: current utilization is at least 75% or monthly growth TB is in the top 25% of clusters.
  - `Low`: all remaining clusters.
- Assign recommended action:
  - `Critical`: `Expand capacity immediately and validate workload drivers.`
  - `High`: `Plan capacity expansion within the next planning cycle.`
  - `Medium`: `Monitor weekly and optimize storage overhead.`
  - `Low`: `No immediate action required.`

**Output columns:**
- `cluster_name`
- `datacenter`
- `business_unit`
- `storage_platform`
- `current_used_tb`
- `usable_capacity_tb`
- `current_utilization_pct`
- `forecast_30d_utilization_pct`
- `forecast_90d_utilization_pct`
- `forecast_180d_utilization_pct`
- `days_until_80_pct`
- `days_until_85_pct`
- `days_until_90_pct`
- `months_until_80_pct`
- `months_until_85_pct`
- `months_until_90_pct`
- `monthly_growth_tb`
- `risk_level`
- `recommended_action`

**Validation checks:**
- Risk levels are not all the same.
- Recommended action maps exactly to risk level.
- Clusters above thresholds are correctly flagged.
- Forecast breach days and derived breach months are easy to understand.

**Stop condition before moving to Stage 9:**
- Proceed only if every cluster has one risk summary row and risk rules map correctly.

**Step-by-step implementation checklist:**
- [ ] Create `src/08_capacity_risk_scoring.py`.
- [ ] Add current-state extraction from the latest actual date.
- [ ] Add threshold crossing helper that returns first forecast day index.
- [ ] Add derived month calculation using 30-day month approximations for planning labels.
- [ ] Add risk-level decision function in Critical, High, Medium, Low order.
- [ ] Add recommended-action mapping.
- [ ] Add validation for one row per cluster and nonuniform risk distribution.
- [ ] Run `python src/08_capacity_risk_scoring.py`.
- [ ] Confirm `capacity_risk_summary.csv` supports the business question directly.
- [ ] Commit with message `feat: score capacity risk`.

---

### Stage 9: Power BI Export Tables

**Goal:** Create clean, flat, dashboard-ready CSV files for Power BI.

**Files:**
- Create: `src/09_generate_powerbi_tables.py`
- Create outputs under `data/processed/`

**Inputs:**
- `data/processed/cluster_daily_metrics.csv`
- `data/processed/cluster_monthly_metrics.csv`
- `data/processed/capacity_inventory.csv`
- `data/processed/cluster_capacity_daily.csv`
- `data/processed/cluster_capacity_monthly.csv`
- `data/processed/model_backtest_results.csv`
- `data/processed/forecast_results.csv`
- `data/processed/capacity_risk_summary.csv`

**Outputs:**
- `data/processed/pbi_cluster_daily_metrics.csv`
- `data/processed/pbi_cluster_monthly_metrics.csv`
- `data/processed/pbi_capacity_inventory.csv`
- `data/processed/pbi_cluster_capacity_daily.csv`
- `data/processed/pbi_cluster_capacity_monthly.csv`
- `data/processed/pbi_forecast_results.csv`
- `data/processed/pbi_model_backtest_results.csv`
- `data/processed/pbi_capacity_risk_summary.csv`

**Logic:**
- Read each final analytical table.
- Standardize column ordering.
- Confirm clean date formats.
- Confirm percentage fields use consistent `0-100` representation.
- Remove index columns or debug-only fields.
- Write CSVs with `index=False`.

**Validation checks:**
- CSVs open cleanly.
- No index columns such as `Unnamed: 0`.
- Clean column names.
- Consistent date formats.
- Daily tables preserve `date`; monthly tables preserve `month`.
- Percent fields are represented consistently.
- No unnecessary debug fields.

**Stop condition before moving to Stage 10:**
- Proceed only if all eight Power BI CSV exports exist and pass export checks.

**Step-by-step implementation checklist:**
- [ ] Create `src/09_generate_powerbi_tables.py`.
- [ ] Add required input and output table mapping.
- [ ] Add per-table cleaning and column ordering.
- [ ] Add export validation checks.
- [ ] Run `python src/09_generate_powerbi_tables.py`.
- [ ] Open or inspect the first rows of each generated CSV, including the daily cluster metrics and daily capacity exports.
- [ ] Commit with message `feat: export power bi tables`.

---

### Stage 10: Documentation and README

**Goal:** Document methodology, limitations, run sequence, and dashboard design for portfolio review.

**Files:**
- Update: `README.md`
- Create: `docs/methodology.md`
- Create: `docs/limitations.md`
- Update: `docs/powerbi_dashboard_plan.md`
- Update: `docs/data_assumptions.md`
- Update: `docs/validation_checklist.md`

**Inputs:**
- All completed pipeline scripts and outputs.
- `docs/data_profile_summary.md`
- Planning documents.

**Outputs:**
- Project README and methodology documentation.

**README required sections:**
- Business problem.
- Dataset.
- Tools.
- Methodology.
- Parsing and ingestion decisions.
- Feature engineering.
- Capacity inventory simulation.
- Forecasting and backtesting.
- Risk scoring logic.
- Power BI dashboard design.
- Key outputs.
- Limitations.
- How to run.
- Resume bullets.

**Required forecasting-history statement:**
Because the available Kaggle extraction contains one month folder, forecasting is performed on daily cluster-level capacity history and then summarized into 30-day, 90-day, and 180-day planning windows.

**Required limitation statement:**
The Bitbrains dataset contains real VM-level datacenter workload traces, including CPU, memory, disk I/O, and network activity. It does not include actual enterprise storage inventory. Raw capacity, usable capacity, protection overhead, metadata overhead, datacenter ownership, business unit ownership, and recommended actions were simulated to create a realistic capacity planning layer for portfolio demonstration.

**Validation checks:**
- README does not imply production enterprise storage inventory.
- Documentation clearly separates real workload telemetry from simulated storage capacity and ownership fields.
- Run commands are listed in stage order.
- Power BI dashboard plan maps to exported CSV names.
- Resume bullets describe the project honestly.

**Final stop condition:**
- The project is ready for manual Power BI dashboard construction only after all exported CSVs exist and documentation is complete.

**Step-by-step implementation checklist:**
- [ ] Update README with all required sections.
- [ ] Create `docs/methodology.md` with stage-by-stage methods.
- [ ] Create `docs/limitations.md` with the required limitation statement.
- [ ] Update `docs/powerbi_dashboard_plan.md` with final table names and visual mappings.
- [ ] Update `docs/data_assumptions.md` with final observed raw-data and simulation assumptions.
- [ ] Update `docs/validation_checklist.md` with completed validation results.
- [ ] Commit with message `docs: document capacity forecasting dashboard`.

---

## Risks and Uncertainties

- Only `fastStorage` data was found during planning inspection; `Rnd` support should remain in code, but dashboard examples may only show fastStorage unless more raw data is added.
- The available raw data appears to cover `2013-8` only. Monthly aggregation may produce only one month of cluster capacity history, so forecasting and backtesting must use daily cluster-level capacity history.
- Some VM files contain all-zero resource values; downstream feature and risk logic must avoid divide-by-zero issues and document inactive or zero-capacity traces.
- Simulated starting utilization may need careful deterministic tuning to create a useful risk distribution without misrepresenting real workload telemetry.
- Forecast model comparison depends on daily history length; with short daily history, model metrics should be presented as limited evidence rather than strong proof.

## Questions Before Coding

1. Should the implementation process add lightweight automated tests under `tests/`, or should validation remain inside each stage script for this portfolio build?
2. Will additional raw folders such as `Rnd` or later months be added before coding starts?
3. Should the Power BI dashboard use the project name exactly as `Enterprise Storage Capacity Forecasting and Risk Dashboard`, or do you want a shorter portfolio title?
4. Should generated charts or static screenshots be added later under `screenshots/`, or should all visualization work happen only in Power BI?
