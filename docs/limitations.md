# Limitations

## Dataset Scope

The Bitbrains dataset contains real VM-level datacenter workload traces, including CPU, memory, disk I/O, and network activity. It does not include actual enterprise storage inventory. Raw capacity, usable capacity, protection overhead, metadata overhead, datacenter ownership, business unit ownership, and recommended actions were simulated to create a realistic capacity planning layer for portfolio demonstration.

This project does not use or claim FedEx production data, Dell ECS experience, Dell PowerScale experience, ServiceNow experience, or PDSM experience.

---

## One-Month Observation Window

The available Kaggle extraction contains one source month folder (`fastStorage/2013-8`). All raw telemetry is from August 2013.

Because the available Kaggle extraction contains one month folder, forecasting is performed on daily cluster-level capacity history and then summarized into 30-day, 90-day, and 180-day planning windows.

This means:

- Monthly cluster aggregation produces only 1–2 distinct months depending on how August 2013 boundaries fall.
- Backtesting is performed on approximately 31 daily observations per cluster.
- With only ~31 daily history points, the training split contains roughly 22–25 days and the test split contains roughly 6–9 days.
- Backtest MAE, RMSE, and MAPE values are directional indicators. They are not production-grade evidence of model accuracy.
- Forecast outputs (30-day, 90-day, 180-day) project far beyond the length of observed history. They represent illustrative capacity trajectories based on the trend captured in one month of workload data.

---

## Simulated Inventory Fields

All capacity inventory fields are simulated:

- `raw_capacity_tb`
- `usable_capacity_tb`
- `protection_overhead_pct`
- `metadata_overhead_pct`
- `reserved_capacity_pct`
- `starting_used_capacity_tb`
- `datacenter`
- `business_unit`
- `storage_platform`
- `recommended_action`

Starting used capacity is simulated using a deterministic tiered utilization distribution to create realistic portfolio capacity-planning scenarios. Real workload metrics are not modified.

Every inventory row carries `inventory_type = Simulated`. Power BI visuals include a visible note that inventory fields are simulated.

---

## Growth Rate Estimation

The `retention_factor = 0.08` used to convert write throughput to net new stored data is a modeling assumption, not a measured value. Actual storage retention rates vary by workload type, deduplication ratio, compression ratio, and data protection policy. The simulated growth trajectory reflects illustrative planning scenarios rather than measured data growth.

---

## No Rnd Trace Type

The available extraction does not include a `Rnd` (random workload) trace folder. Only `fastStorage` traces are present. The pipeline handles this gracefully: cluster simulation and capacity estimation use only `fastStorage`-derived workload signals.

---

## Reproducibility

All simulated fields use `numpy.random.default_rng(42)` as the deterministic seed. Re-running the pipeline on the same raw data will produce identical outputs.

---

## What This Project Does Not Validate

- Real-world storage capacity thresholds or SLA requirements.
- Real cluster topology, RAID configuration, or tiering policies.
- Real data reduction ratios (deduplication, compression).
- Real datacenter ownership or business unit cost allocation.
- Production forecast accuracy beyond the one-month backtesting window.
