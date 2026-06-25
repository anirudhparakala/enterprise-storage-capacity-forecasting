# Data Assumptions

## Planning-Time Observations

- Raw data is stored under `data/raw`.
- During planning inspection, the raw folder contained `1250` CSV files.
- The discovered raw folder structure was `data/raw/fastStorage/2013-8`.
- No `data/raw/Rnd` folder was found during planning inspection.
- Because planning inspection found one month folder, monthly aggregation may produce only one month of cluster capacity history.
- Forecasting and backtesting must therefore use daily cluster-level capacity history rather than monthly cluster-level capacity history.
- `docs/manual_dataset_notes.md` was referenced by the draft plan but does not currently exist.
- Sample files `data/raw/fastStorage/2013-8/1.csv` and `data/raw/fastStorage/2013-8/10.csv` contain a header row and semicolon-delimited rows.
- Sample rows split into 11 columns using delimiter logic equivalent to regex `;\s*`.
- Sample timestamp `1376314846` converts to `2013-08-12 13:40:46` when interpreted as Unix seconds.

## Raw Dataset Assumptions

- Each raw CSV file represents one VM trace.
- Raw files may be nested below trace type and month folders.
- Trace type is inferred from path parts such as `fastStorage` or `Rnd`.
- Source month folder is inferred from path parts such as `2013-8`.
- The parser must recursively scan under `data/raw`; it must not assume only one folder level.
- The parser must strip one pair of outer double quotes from a row before splitting.
- The parser must split rows on semicolon plus optional whitespace or tab.
- A valid Bitbrains row has 11 fields.
- The timestamp header text is not reliable enough to determine units by itself.
- Timestamp unit must be inferred from numeric magnitude.
- Values around `1,000,000,000` to `2,000,000,000` are treated as Unix seconds.
- Values around `1,000,000,000,000` are treated as Unix milliseconds.

## Real Versus Simulated Fields

Real fields from the Bitbrains traces include:

- Timestamp.
- CPU cores.
- CPU capacity provisioned.
- CPU usage.
- Memory capacity provisioned.
- Memory usage.
- Disk read throughput.
- Disk write throughput.
- Network received throughput.
- Network transmitted throughput.

Simulated fields created for portfolio capacity planning include:

- Cluster name.
- Datacenter.
- Business unit.
- Storage platform label.
- Raw capacity.
- Usable capacity.
- Protection overhead.
- Metadata overhead.
- Reserved capacity.
- Starting used capacity.
- Recommended action.

Every simulated inventory row must include `inventory_type = Simulated`.

## Capacity Simulation Assumptions

- Cluster assignment uses deterministic seed `42`.
- Capacity inventory generation uses deterministic seed `42`.
- Starting utilization generation uses deterministic seed `42`.
- Fast SAN-style storage uses raw capacity between 800 TB and 2500 TB.
- Fast SAN-style storage uses usable capacity between 72% and 82% of raw capacity.
- Mixed SAN/NAS-style storage uses raw capacity between 500 TB and 1800 TB.
- Mixed SAN/NAS-style storage uses usable capacity between 65% and 78% of raw capacity.
- If `Rnd` data is absent, only fastStorage-derived clusters are expected.

## Storage Growth Assumptions

- Disk write workload pressure is used as the basis for estimated daily storage growth.
- Daily write throughput is converted from KB/s to TB/day using 86,400 seconds per day.
- `retention_factor = 0.08` is used to estimate net new retained storage from write activity.
- Capacity utilization equals used capacity divided by usable capacity, represented as a `0-100` percentage.
- Monthly capacity summaries are derived from daily capacity history for Power BI reporting.

## Forecasting Assumptions

- Forecast target is `used_capacity_tb`.
- Forecast frequency is daily.
- Forecast horizon is 180 days.
- Candidate models are naive baseline, seven-day moving average, Holt linear trend, and exponential smoothing.
- Linear regression is not the main forecasting method.
- Model selection is based on lowest MAPE when daily backtesting history supports comparison.
- Backtesting uses the earliest 70% to 80% of daily observations as training data and the remaining 20% to 30% as test data.
- Forecast output is summarized into 30-day, 90-day, and 180-day planning windows for risk scoring and Power BI.
- If daily history is too short for meaningful backtesting, the implementation must use a documented limited-history fallback and avoid overstating model confidence.

## Required Forecasting-History Statement

Use this statement in final documentation:

Because the available Kaggle extraction contains one month folder, forecasting is performed on daily cluster-level capacity history and then summarized into 30-day, 90-day, and 180-day planning windows.

## Limitation Language

Use this statement in final documentation:

The Bitbrains dataset contains real VM-level datacenter workload traces, including CPU, memory, disk I/O, and network activity. It does not include actual enterprise storage inventory. Raw capacity, usable capacity, protection overhead, metadata overhead, datacenter ownership, business unit ownership, and recommended actions were simulated to create a realistic capacity planning layer for portfolio demonstration.
