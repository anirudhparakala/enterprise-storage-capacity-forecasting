# Stage 4 Brief: Daily and Monthly Cluster Metrics

Implement Stage 4 only for the Enterprise Storage Capacity Forecasting and Risk Dashboard.

## Scope

- Create `src/04_build_monthly_cluster_metrics.py`.
- Add focused tests under `tests/` for Stage 4 behavior.
- Do not create or edit Stage 5+ scripts.
- Do not delete or overwrite existing user data or generated artifacts except the Stage 4 output CSVs when the Stage 4 script runs.

## Inputs

- `data/processed/vm_daily_metrics.csv`
- `data/processed/vm_cluster_mapping.csv`

## Outputs

- `data/processed/cluster_daily_metrics.csv`
- `data/processed/cluster_monthly_metrics.csv`

## Required Logic

- Read VM daily metrics and VM cluster mapping.
- Join on `vm_id`.
- Validate that every VM in `vm_daily_metrics.csv` has a cluster mapping.
- Convert `date` to valid dates.
- Build daily cluster metrics by grouping on `date`, `cluster_name`, `datacenter`, `business_unit`, and `storage_platform`.
- Daily `vm_count` is distinct VM count.
- Average daily VM metric columns into daily cluster metrics.
- Sum `high_disk_spike_count` across VMs.
- Derive `month` as first day of month from the daily cluster table.
- Build monthly metrics from the daily cluster table, not independently from VM-level raw/daily data.
- Monthly `vm_count` should be positive and represent cluster membership over the monthly daily summary.
- Enforce exact output column order.
- Write CSVs with `index=False`.

## Daily Columns

1. `date`
2. `cluster_name`
3. `datacenter`
4. `business_unit`
5. `storage_platform`
6. `vm_count`
7. `avg_memory_utilization_pct`
8. `p95_memory_utilization_pct`
9. `avg_disk_read_kbps`
10. `avg_disk_write_kbps`
11. `avg_disk_total_kbps`
12. `p95_disk_total_kbps`
13. `avg_network_total_kbps`
14. `high_disk_spike_count`

## Monthly Columns

1. `month`
2. `cluster_name`
3. `datacenter`
4. `business_unit`
5. `storage_platform`
6. `vm_count`
7. `avg_memory_utilization_pct`
8. `p95_memory_utilization_pct`
9. `avg_disk_read_kbps`
10. `avg_disk_write_kbps`
11. `avg_disk_total_kbps`
12. `p95_disk_total_kbps`
13. `avg_network_total_kbps`
14. `high_disk_spike_count`

## Validation Requirements

- Daily output has one row per `date` + `cluster_name`.
- Monthly output has one row per `month` + `cluster_name`.
- No missing cluster names.
- Date field is valid.
- Month field is valid.
- `p95_disk_total_kbps` exists and is numeric in both outputs.
- `vm_count` is positive in both outputs.
- No duplicate `date` + `cluster_name` rows.
- No duplicate `month` + `cluster_name` rows.
- Monthly output is derived from the daily cluster table.

## Local Patterns

- Follow the dataclass summary and `main() -> int` style from Stages 2 and 3.
- Fail loudly with a clear validation summary.
- Use pandas and pathlib only unless a dependency is already present and necessary.
- Tests should import the stage script via `importlib.util.spec_from_file_location`, matching existing tests.

## Reporting

The final controller will report:

1. Exit code
2. Files created
3. Input VM daily row count
4. Input cluster mapping row count
5. Unmapped VM count after join
6. Daily row count
7. Monthly row count
8. Unique cluster count in daily output
9. Unique cluster count in monthly output
10. Daily date range
11. Monthly month range
12. Duplicate daily key rows
13. Duplicate monthly key rows
14. Min and max `vm_count`
15. Output column lists
16. First 5 daily rows
17. First 5 monthly rows
18. Whether Stage 4 stop condition passed
