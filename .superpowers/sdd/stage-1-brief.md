# Stage 1 Brief: Bitbrains VM Trace Ingestion

Implement Stage 1 only.

## Scope

- Create `src/01_ingest_bitbrains.py`.
- Add focused tests only if useful for test-first implementation, preferably under `tests/`.
- Do not implement Stage 2 or any later stage.
- Do not delete or rewrite Stage 0 outputs or raw data.
- Treat existing untracked project files as intentional user work.

## Inputs

- Raw traces: recursively discovered with `Path("data/raw").rglob("*.csv")`.
- Stage 0 validated output: `data/processed/raw_data_profile.csv`.
- Parser precedent: `src/00_profile_raw_data.py`.

## Raw Parser Rules

- Reuse Stage 0 parser conventions in a minimal way, copying/importing only what Stage 1 needs.
- Raw rows are not normal comma CSV files.
- Strip whitespace.
- Strip one pair of outer double quotes when present.
- Split rows using semicolon plus optional whitespace or tab, equivalent to regex `;\s*`.
- Valid Bitbrains rows have exactly 11 fields.
- Do not use plain `pd.read_csv(file)` for raw trace ingestion.
- Do not accept one-column parsed rows as valid ingestion.
- Skip a header row when the first parsed cell contains `Timestamp`.

## Raw Columns

Parse the 11 fields into this canonical raw order:

1. `timestamp_raw`
2. `cpu_cores`
3. `cpu_capacity_mhz`
4. `cpu_usage_mhz`
5. `cpu_usage_pct`
6. `memory_capacity_kb`
7. `memory_usage_kb`
8. `disk_read_kbps`
9. `disk_write_kbps`
10. `network_rx_kbps`
11. `network_tx_kbps`

## Required Output Columns

The cleaned dataset must contain exactly these target columns, in this order:

1. `source_file`
2. `source_month_folder`
3. `trace_type`
4. `vm_id`
5. `timestamp_raw`
6. `timestamp_unit_detected`
7. `datetime`
8. `date`
9. `month`
10. `hour`
11. `cpu_cores`
12. `cpu_capacity_mhz`
13. `cpu_usage_mhz`
14. `cpu_usage_pct`
15. `memory_capacity_kb`
16. `memory_usage_kb`
17. `disk_read_kbps`
18. `disk_write_kbps`
19. `network_rx_kbps`
20. `network_tx_kbps`

## Metadata Rules

- Treat each raw file as one VM trace.
- Preserve `source_file`, `source_month_folder`, `trace_type`, and `vm_id`.
- Build `vm_id` from the raw-root-relative path without extension, normalized to a stable string such as `fastStorage_2013-8_1`.
- Infer `trace_type` from known path parts: `fastStorage`, `Rnd`; otherwise `Unknown`.
- Infer `source_month_folder` from path parts matching `^\d{4}-\d{1,2}$`; otherwise `Unknown`.

## Timestamp Rules

- Infer timestamp units from magnitude, not from header text.
- Values from 1,000,000,000 through 2,000,000,000 are Unix seconds.
- Values at or above 1,000,000,000,000 are Unix milliseconds.
- Ten-digit timestamps such as `1376314846` must be parsed as Unix seconds and convert to 2013 datetimes.
- Record the detected unit in `timestamp_unit_detected`.
- Create `datetime`, `date`, `month`, and `hour`.
- Dates should be ISO-friendly. `date` is `YYYY-MM-DD`; `month` is first-of-month `YYYY-MM-01`.

## Failure Handling

- Reject blank lines, malformed rows with a field count other than 11, one-column rows, rows with nonnumeric or unknown-unit timestamps, and rows whose timestamp cannot be converted.
- Convert metric columns with `pd.to_numeric(errors="coerce")`.
- Count failed parse rows separately from accepted rows. Rows with malformed structure or unusable timestamps count as failed parse rows.
- If more than 5% of data rows fail parsing, write `data/processed/ingestion_error_summary.csv`, print a clear validation summary, return nonzero, and do not write final `vm_metrics_cleaned.parquet`.
- If parse failure rate is <= 5%, write:
  - `data/processed/vm_metrics_cleaned.parquet`
  - `data/processed/vm_metrics_sample.csv`
- The sample CSV should be small enough for inspection and should use `index=False`.

## Validation Requirements

The script must fail loudly if:

- `data/processed/raw_data_profile.csv` is missing.
- No raw CSV files are found.
- The accepted dataframe is empty.
- Any target output column is missing or out of order.
- Any accepted row effectively came from one-column parsing.
- Numeric metric columns are not numeric dtypes.
- `trace_type` or `source_month_folder` is missing or `Unknown`.
- A `source_file` maps to more than one `vm_id`.
- Failed parse rate is greater than 5%.

## Expected Full-Run Behavior

- Recursively ingest all current raw CSV files under `data/raw`; planning found 1250 files under `data/raw/fastStorage/2013-8`.
- Produce one VM trace per source file.
- Preserve all accepted data rows from the raw traces.
- Print a concise Stage 1 validation summary including row counts, file counts, failed row count/rate, min/max datetime, unique trace types, unique source month folders, and whether the stop condition passed.
