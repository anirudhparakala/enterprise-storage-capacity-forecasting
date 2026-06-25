# Stage 0 Task Brief

## Scope

Implement Stage 0 only for the Enterprise Storage Capacity Forecasting and Risk Dashboard.

Do not implement Stage 1 or any downstream script.
Do not create screenshots.
Do not make a git commit.
Keep validation inside the Stage 0 script for now; do not create a separate `tests/` suite.

## Files Owned By This Task

- Create or modify: `src/00_profile_raw_data.py`
- Create when the script runs: `data/processed/raw_data_profile.csv`
- Create when the script runs: `docs/data_profile_summary.md`

## Inputs

- `data/raw/**/*.csv`

## Required Raw Parsing Rules

- Recursively discover all `.csv` files under `data/raw`.
- Raw rows are semicolon-delimited with optional whitespace or tab after semicolons; use logic equivalent to regex `;\s*`.
- Some rows may be wrapped in double quotes; strip one pair of outer double quotes before splitting.
- Valid Bitbrains sample rows have 11 expected fields.
- Do not use plain `pd.read_csv(file)` for raw parsing.
- The timestamp header says `Timestamp [ms]`, but sample values such as `1376314846` must be detected as Unix seconds because they convert to 2013 dates.

## Required Logic

- Count total raw CSV files.
- Count files by `trace_type`.
- Count files by `source_month_folder`.
- Infer `trace_type` from path parts such as `fastStorage` or `Rnd`.
- Infer `source_month_folder` from path parts matching `YYYY-M` or `YYYY-MM`, such as `2013-8`.
- Inspect at least two sample files when two or more files exist.
- Detect whether sampled rows are wrapped in double quotes.
- Detect delimiter pattern.
- Detect header row existence.
- Detect header and sample data column counts.
- Infer timestamp unit from magnitude:
  - `1_000_000_000 <= value <= 2_000_000_000`: Unix seconds.
  - `value >= 1_000_000_000_000`: Unix milliseconds.
- Convert sample timestamps to datetime strings.
- Write parsed sample rows in a useful form.
- Enforce the Stage 0 stop condition before exiting successfully.

## Output Requirements

`data/processed/raw_data_profile.csv` should contain enough detail to answer:

- total raw CSV count
- sampled source files
- detected trace types
- detected source month folders
- whether rows are wrapped in quotes
- delimiter detection result
- header existence
- parsed header column count
- parsed sample data column count
- timestamp raw value
- timestamp unit detection
- converted sample datetime
- whether sample datetime is in 2013
- stop condition status

`docs/data_profile_summary.md` should summarize:

- files created
- total raw CSV count
- detected trace types
- source month folders
- whether rows are wrapped in quotes
- parsed column count
- timestamp unit detection
- converted sample datetimes
- whether the stop condition passed
- limitation that only `fastStorage/2013-8` is present if confirmed

## Required Helper Functions

- `discover_raw_files(raw_root: Path) -> list[Path]`
- `infer_trace_type(path: Path) -> str`
- `infer_source_month_folder(path: Path) -> str`
- `clean_raw_line(line: str) -> str`
- `split_trace_line(line: str) -> list[str]`
- `infer_timestamp_unit(value: float) -> str`
- `profile_file(path: Path) -> dict`
- `main() -> int`

## Validation / Stop Condition

The script should exit with success only when:

- at least one raw CSV exists
- at least two sample files are inspected when at least two raw files exist
- sampled data rows parse to 11 fields
- header rows parse to 11 fields when present
- sample timestamp unit detection identifies `1376314846`-style values as seconds
- converted sample datetimes are in 2013

If the stop condition fails, write the profile and summary with failure details and exit nonzero.

## Verification Commands

Run:

```powershell
python src/00_profile_raw_data.py
```

Then inspect:

```powershell
Get-Content docs\data_profile_summary.md
Import-Csv data\processed\raw_data_profile.csv | Select-Object -First 5
```

## Report Contract

Write your report to `.superpowers/sdd/reports/stage-0-report.md`.

Return only:

- status: DONE, DONE_WITH_CONCERNS, NEEDS_CONTEXT, or BLOCKED
- files changed
- commands run and result
- short concerns, if any
