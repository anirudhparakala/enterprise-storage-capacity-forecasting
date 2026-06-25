# Repository Instructions

This repository builds an Enterprise Storage Capacity Forecasting and Risk Dashboard from the Kaggle GWA-Bitbrains datacenter VM traces. Treat it as a portfolio analytics project with a strict separation between real VM workload telemetry and simulated enterprise storage capacity inventory.

## Required Workflow

- Use Superpowers-style workflows for planning, implementation, debugging, review, and verification.
- Do not implement code until the current implementation plan has been approved by the user.
- When implementation begins, follow [docs/implementation_plan.md](docs/implementation_plan.md) stage by stage.
- Prefer `superpowers:subagent-driven-development` for task-by-task execution when the user approves implementation.
- Use `superpowers:executing-plans` only when the user asks for inline execution in this session.
- Before claiming a stage is complete, use `superpowers:verification-before-completion` and run the stage's validation checks.
- If a bug, failed validation, or surprising data behavior appears, use `superpowers:systematic-debugging` before changing code.

## Project Truth Boundaries

- The Bitbrains traces provide real VM-level workload fields: CPU, memory, disk I/O, network throughput, and timestamps.
- The dataset does not provide real enterprise storage inventory, datacenter ownership, business unit ownership, storage platform inventory, or recommendations.
- Always label generated capacity inventory fields as simulated.
- Every simulated inventory row must use `inventory_type = Simulated`.
- Do not claim FedEx production data.
- Do not claim Dell ECS experience, Dell PowerScale experience, ServiceNow experience, or PDSM experience.
- Do not imply that raw capacity, usable capacity, overhead percentages, datacenter ownership, business unit ownership, or recommended actions came from the raw dataset.

## Source Data Rules

- Raw data lives under `data/raw` and must be scanned recursively.
- Current planning inspection found `1250` CSV files under `data/raw/fastStorage/2013-8`.
- Current planning inspection did not find an `Rnd` raw-data folder; keep support for `Rnd`, but document the limitation if it remains absent.
- Because the available extraction contains one month folder, forecasting must use daily cluster-level capacity history and then summarize into 30-day, 90-day, and 180-day planning windows.
- Each raw CSV file should be treated as one VM trace.
- Raw files are not normal comma CSV files.
- Parse raw rows with semicolon plus optional whitespace or tab, equivalent to regex `;\s*`.
- Strip one pair of outer double quotes from a row before splitting when present.
- Valid Bitbrains rows have 11 fields.
- Do not use plain `pd.read_csv(file)` without custom parsing safeguards for raw trace ingestion.
- Do not accept a one-column dataframe as valid ingestion.
- The timestamp header says `Timestamp [ms]`, but sample values such as `1376314846` should be treated as Unix seconds because they convert to 2013 dates.
- Infer timestamp units from magnitude, not from the header alone.

## Stage Order

Implement in this order only:

1. `src/00_profile_raw_data.py`
2. `src/01_ingest_bitbrains.py`
3. `src/02_feature_engineering.py`
4. `src/03_assign_clusters.py`
5. `src/04_build_monthly_cluster_metrics.py`
6. `src/05_create_capacity_inventory.py`
7. `src/06_estimate_capacity_usage.py`
8. `src/07_forecasting_backtest.py`
9. `src/08_capacity_risk_scoring.py`
10. `src/09_generate_powerbi_tables.py`
11. Final documentation updates in `README.md` and `docs/`.

Do not skip ahead. Each stage must read validated outputs from the previous stage and must satisfy its stop condition before the next stage begins.

## Validation Gates

- Use [docs/validation_checklist.md](docs/validation_checklist.md) as the stage gate checklist.
- Stage 0 must prove that sampled rows parse to 11 columns and sample datetimes convert to 2013 dates.
- Stage 1 must stop if more than 5% of rows fail parsing.
- Stage 2 must produce one row per VM per day and nonzero high disk spike counts.
- Stage 3 must map every VM to exactly one simulated cluster using deterministic seed `42`.
- Stage 4 must produce one row per cluster per date in `cluster_daily_metrics.csv` and one row per cluster per month in `cluster_monthly_metrics.csv`.
- Stage 5 must produce exactly one simulated capacity inventory row per cluster.
- Stage 6 must produce plausible, varied daily utilization in `cluster_capacity_daily.csv` and derive monthly summaries from daily capacity history.
- Stage 7 must produce model backtest results using daily capacity history and exactly 180 forecast dates per cluster.
- Stage 8 must produce one risk summary row per cluster with 30-day, 90-day, and 180-day forecast utilization fields plus days/months until threshold breach.
- Stage 9 must export clean Power BI CSVs with no index columns, including daily cluster metrics and daily capacity exports.

## Implementation Conventions

- Keep scripts focused and stage-specific.
- Use `Path("data/raw").rglob("*.csv")` for raw file discovery.
- Write processed artifacts under `data/processed`.
- Create missing output directories in scripts.
- Use deterministic simulation with `numpy.random.default_rng(42)`.
- Keep CSV date fields in ISO-friendly formats: dates as `YYYY-MM-DD`, months as `YYYY-MM-01`.
- Represent percentages consistently as `0-100` values.
- Fail loudly with clear validation summaries instead of silently continuing with bad data.
- Avoid broad refactors while implementing a stage.
- Add shared helpers only when duplication across stage scripts becomes meaningful.

## Forecasting and Risk Rules

- Forecast target is `used_capacity_tb`.
- Forecast frequency is daily.
- Forecast horizon is 180 days.
- Include these models: naive baseline, seven-day moving average, Holt linear trend, and exponential smoothing.
- Do not make linear regression the main forecasting method.
- Select the best model by lowest MAPE when enough daily history exists.
- Use the earliest 70% to 80% of daily observations as training data and the remaining 20% to 30% as test data.
- If daily capacity history is too short, use a documented limited-history fallback and do not overstate model confidence.
- Risk rules must be evaluated in this order: Critical, High, Medium, Low.
- Recommended actions must map exactly to risk level as defined in the implementation plan.

## Documentation Requirements

- Keep [docs/data_assumptions.md](docs/data_assumptions.md) updated when raw-data findings or simulation assumptions change.
- Keep [docs/powerbi_dashboard_plan.md](docs/powerbi_dashboard_plan.md) aligned with final exported CSV names.
- Final documentation must include the required limitation statement from `docs/data_assumptions.md`.
- Final documentation must include the required daily forecasting-history statement from `docs/data_assumptions.md`.
- README must explain the business problem, dataset, methodology, simulated inventory, forecasting, risk scoring, outputs, limitations, run order, and honest resume bullets.

## Safety Around Existing Work

- Do not overwrite user changes.
- Check `git status --short` before large edits.
- Treat untracked docs and data outputs as potentially intentional.
- Do not delete generated data, raw data, notebooks, screenshots, or Power BI assets unless the user explicitly asks.
