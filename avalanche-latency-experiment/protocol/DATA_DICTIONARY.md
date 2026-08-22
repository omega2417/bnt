# Data dictionary

Every file the campaign produces, and what each field means. The analysis
depends on these names, not on how the file was produced: measured records
and reference-model records share one schema, and `provenance` is the only
field that distinguishes them.

## `data/raw/tx/<run_id>.jsonl[.gz]` — transaction records

One JSON object per line, one line per submitted transaction of the
measurement window. Warm-up transactions are executed but not written.

| Field | Type | Meaning |
| --- | --- | --- |
| `run_id` | string | key of the randomized schedule |
| `config` | string | C0...C4 |
| `topology` | string | T0_local, T1_vpn, T2_three_region_emulated |
| `load_tps` | int | offered load of the run |
| `repeat` | int | repeat index within the cell |
| `trace_id` | string | immutable trace shared by all configurations |
| `client_id` | string | generator workstation, K00...K24 |
| `account_token` | string | pseudonymised account handle; never a key or an address |
| `seq` | int | monotonic sequence number written to the probe |
| `key_hex` | string | probe key, unique per client and trace |
| `tx_hash` | string | transaction hash |
| `t_send_ns` | int64 | monotonic clock, before `send_raw_transaction` |
| `t_hash_ns` | int64 | monotonic clock, after the RPC returned the hash |
| `t_receipt_ns` | int64 | monotonic clock, when the receipt was observed |
| `t_read_R1_ns`, `t_read_R2_ns` | int64 | monotonic clock, first confirmed read per node |
| `t_visible_first_ms` | float | equation (5) |
| `t_visible_all_ms` | float | equation (6) |
| `t_convergence_ms` | float | equation (7) |
| `block_number` | int | including block, `-1` if never included |
| `block_time_ms` | float | block timestamp; prefer millisecond headers after ACP-226 |
| `status` | enum | `success`, `timeout`, `revert`, `error` |
| `error_class` | string | `not_included`, `state_visibility_timeout`, `read_mismatch`, exception class |
| `payload_bytes` | int | size of the signed raw transaction |
| `gas_used` | int | gas consumed by the probe write |
| `provenance` | enum | `MEASURED` or `SIMULATED` |

Private keys, internal IP or MAC addresses and personal data never appear
in this file.

## `data/raw/nodes/<run_id>_blocks.csv` — block series

| Column | Meaning |
| --- | --- |
| `block_number` | sequential index within the run |
| `t_proposal_ms` | proposal time, run-relative |
| `t_accept_ms` | consensus acceptance time |
| `n_tx` | probe transactions included |
| `interval_ms` | difference from the previous proposal; feeds equation (13) |
| `commit_ms` | state-commit latency of the block |

## `data/raw/nodes/<run_id>_resources.csv` — 1 Hz telemetry

| Column | Meaning |
| --- | --- |
| `t_s` | second within the run, from 0 |
| `phase` | `warmup`, `measure`, `drain`; only `measure` enters the statistics |
| `cpu_pct` | validator CPU utilisation |
| `mem_mib` | resident memory |
| `disk_p99_ms` | p99 storage-commit latency in that second |
| `queue_depth` | transactions ready but not yet included; feeds equation (14) |
| `blocks_per_s` | blocks produced in that second |

## `data/raw/network/<run_id>_probes.json` — active probes

A list of objects with `phase` (`before`, `during`, `after`), the netem
description, and per-target `rtt_min/avg/max_ms`, `jitter_ms`, `loss_pct`.
The requested netem target and the realised path are recorded separately.

## `data/raw/manifests/<run_id>.json` — run passport

Factor levels, seeds, phase durations, the trace SHA-256, the git commit,
software versions, chain and contract identifiers, clock discipline and the
provenance label. Fields that a real campaign must fill are listed in
`protocol/DATA_REQUIRED.md`.

## `results/run_level_summary.csv` — the inferential unit

One row per run: `p50_ms`, `p95_ms`, `p99_ms`, `all_p99_ms`,
`convergence_p99_ms`, `goodput_tps`, `availability_pct`, `consistency_pct`,
`p99_drift_pct`, `observed_block_interval_ms`, `tx_per_block_mean`,
`queue_slope_tx_per_s` with its CI, `queue_depth_p95`, `cpu_p95_pct`,
`cpu_max_pct`, `cpu_saturated_s`, `disk_p99_ms`, `mem_p95_mib`.

## `results/paired_effects.csv` — effects against the baseline

`metric`, `profile`, `baseline`, `topology`, `load_tps`, `n_pairs`,
`delta_improvement_ms` (positive means faster than the baseline),
`delta_improvement_pct`, `ci_low`, `ci_high`, `ci_halfwidth_rel`,
`p_value`, `significant`, `holm_p`, `holm_reject`.

## `results/run_stability.csv` and `results/cell_stability.csv`

The pre-registered criteria of protocol section 12, evaluated per run and
aggregated per `config x topology x load` cell, with `failed_criteria`
naming every rule a run violated.
