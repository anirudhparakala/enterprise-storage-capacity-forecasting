# Raw Data Profile Summary

## Files Created

- `data/processed/raw_data_profile.csv`
- `docs/data_profile_summary.md`

## Dataset Shape

- Total raw CSV count: 1250
- Sample files inspected: 2
- Detected trace types: fastStorage
- Detected source month folders: 2013-8

### File Counts By Trace Type

- fastStorage: 1250

### File Counts By Source Month Folder

- 2013-8: 1250

## Parser Findings

- Rows wrapped in double quotes: False
- Delimiter detection: semicolon with optional whitespace or tab after semicolons
- Parsed sample data column counts: 11
- Expected Bitbrains column count: 11

## Timestamp Findings

- Timestamp unit detection: seconds
- Converted sample datetimes:
  - 2013-08-12 13:40:46
  - 2013-08-12 13:40:46
- Sample datetimes in 2013: True

## Stop Condition

- Stop condition passed: True
- Failure reasons: None

## Confirmed Limitation

Only `fastStorage/2013-8` is present in the current raw extraction. No `Rnd` raw-data folder was detected during Stage 0 profiling.
