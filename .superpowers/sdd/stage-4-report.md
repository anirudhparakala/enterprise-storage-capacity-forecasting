# Stage 4 Report

## Status

Completed for the requested Stage 4 scope.

## Files Changed

- `src/04_build_monthly_cluster_metrics.py`
- `tests/test_stage_4_build_monthly_cluster_metrics.py`

## Tests Run With Exit Codes

1. `pytest -q tests/test_stage_4_build_monthly_cluster_metrics.py`
   - Exit code: `1`
2. `pytest -q tests/test_stage_4_build_monthly_cluster_metrics.py`
   - Exit code: `0`
3. `python src/04_build_monthly_cluster_metrics.py`
   - Exit code: `0`

## TDD Red/Green Evidence

- Red: added `tests/test_stage_4_build_monthly_cluster_metrics.py` before production code existed; the first pytest run failed because `src/04_build_monthly_cluster_metrics.py` was missing.
- Initial green: created `src/04_build_monthly_cluster_metrics.py` with the minimal aggregation and validation logic required by the first tests; that pytest run passed with `2 passed`.
- Fresh verification: ran `python src/04_build_monthly_cluster_metrics.py` against repo inputs and it completed successfully, writing Stage 4 CSV outputs and reporting the stop condition as passed.

## Concerns

- Monthly `vm_count` is derived from the daily cluster table using the monthly maximum daily `vm_count`, which preserves a positive cluster membership signal without recomputing from VM-level rows. If the controller wants a different monthly membership rule, that should be decided explicitly before downstream stages depend on it.

---

## Fix Worker Follow-Up

### Scope

- Addressed the Stage 4 review findings only.
- Kept changes scoped to `src/04_build_monthly_cluster_metrics.py`, `tests/test_stage_4_build_monthly_cluster_metrics.py`, and this Stage 4 report.
- Did not touch Stage 5+ files or alter output column order.

### What Changed

- Added focused Stage 4 tests that lock in the monthly `vm_count` rule as the maximum observed daily `vm_count` within the month.
- Added focused validation tests for duplicate daily keys, duplicate monthly keys, invalid daily dates, invalid monthly dates, missing `cluster_name`, nonnumeric `p95_disk_total_kbps`, non-positive `vm_count`, and a monthly table manually altered away from the daily-derived result.
- Made the monthly `vm_count` intent explicit in production code with the helper name `_monthly_vm_count_from_max_daily_membership()`.
- Tightened validation flow so malformed daily outputs are reported as Stage 4 validation failures instead of surfacing raw pandas parse or aggregation exceptions.
- Tightened monthly date validation so `month` values must still parse as dates and must remain month-start values.

### Tests Run With Exit Codes

1. `pytest -q tests/test_stage_4_build_monthly_cluster_metrics.py`
   - Exit code: `1`
   - Expected red result: new validation coverage exposed Stage 4 validation-path gaps.
2. `pytest -q tests/test_stage_4_build_monthly_cluster_metrics.py`
   - Exit code: `0`
   - Green result: `14 passed`.
3. `python src/04_build_monthly_cluster_metrics.py`
   - Exit code: `0`
   - Fresh verification result: Stage 4 summary reported duplicate key counts of `0` and `Stage 4 stop condition passed: True`.

### Concerns

- The targeted pytest run still emits one pandas warning when intentionally feeding an invalid daily date string during a negative test. The behavior is correct and the validation message is now stable, but the warning remains in the test output.
