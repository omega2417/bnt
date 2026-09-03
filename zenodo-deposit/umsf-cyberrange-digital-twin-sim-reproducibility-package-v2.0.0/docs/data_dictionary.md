# Data dictionary — release 2.0.0, schema 2.0.0

Every record-level file below is a **synthetic output of a software model**. No
field in this package holds a physical measurement. The provenance vector of all
files is `stimulus_origin = scripted_synthetic`,
`observation_origin = simulator_output`, `label_origin = scenario_controller`,
`curation_origin = automated_pipeline`, `analysis_origin = derived_metric`.

## Files per run directory

| File | Contents |
|---|---|
| `telemetry.csv` | One row per site per simulation step; the observable record |
| `ground_truth.csv` | Scenario-controller intervals and state transitions |
| `alerts.csv` | Detector output, one row per alert |
| `response_audit.json` | Response actions, state transitions and approvals |
| `parameters.json` | Every parameter with value, unit, evidence status and source |
| `scenario.resolved.json` | The fully resolved configuration after defaults |
| `summary.json` | Aggregated metrics, their denominators and gate verdicts |
| `manifest.json` | Config, source and environment hashes; SHA-256 of each artifact |
| `report.md` | Generated run report; every number traces to an artifact |

## `telemetry.csv` — 63 fields

Identity and time. Timestamps are UTC and belong to the simulated clock, not to
wall-clock acquisition.

| Field | Unit | Meaning |
|---|---|---|
| `run_id` | id | Run directory identity |
| `replicate_id` | int | Replicate index; separates random streams |
| `step` | int | Simulation step, monotonically increasing within a run |
| `timestamp_utc` | ISO-8601 | Start of the simulated interval |
| `interval_end_utc` | ISO-8601 | End of the simulated interval |
| `observed_time_utc` | ISO-8601 | Simulated sensor observation time (may lag) |
| `ingest_time_utc` | ISO-8601 | Simulated arrival time at the collector |
| `site_id` | enum | `site_a` or `site_b` |
| `mode` | enum | Always `SIM` in this deposit |
| `evidence_class` | enum | Always `synthetic_demo` in this deposit |

Network.

| Field | Unit | Meaning |
|---|---|---|
| `active_wan_id` | id | WAN link currently carrying traffic |
| `wan_state` | enum | `UP` / `DEGRADED` / `DOWN` / `RECOVERING` |
| `wan_capacity_mbps` | Mbit/s | Effective capacity of the active link |
| `offered_load_mbps` | Mbit/s | Demand presented to the link |
| `throughput_mbps` | Mbit/s | Delivered load after queueing and loss |
| `queue_delay_ms` | ms | Fluid-queue delay component |
| `rtt_ms` | ms | Modelled round-trip time |
| `jitter_ms` | ms | Modelled RTT variation |
| `loss_pct` | % | Modelled packet loss |
| `failover_active` | 0/1 | Router is on a backup link |
| `vpn_state` | enum | `UP` / `DEGRADED` / `REKEYING` / `DOWN` / `RECONNECTING` |
| `vpn_latency_ms` | ms | Inter-site tunnel latency contribution |
| `vpn_loss_pct` | % | Inter-site tunnel loss contribution |

Wi-Fi.

| Field | Unit | Meaning |
|---|---|---|
| `ap_total` | count | Access points configured at the site |
| `ap_online` | count | Access points visible to the controller |
| `wifi_clients` | count | Associated clients (negative-binomial with daily seasonality) |
| `mean_rssi_dbm` | dBm | Mean modelled client RSSI |
| `channel_util_pct` | % | Modelled airtime utilisation |
| `retry_pct` | % | Modelled retry rate |
| `auth_failures` | count | Authentication failures in the interval |
| `roaming_events` | count | Roaming events in the interval |
| `rogue_ap_count` | count | Rogue APs reported by the modelled controller |

Assets, workload and threat features. Threat activity is represented as feature
changes only; no traffic is generated.

| Field | Unit | Meaning |
|---|---|---|
| `assets_ready` | count | Managed nodes in a serving state |
| `assets_degraded` | count | Managed nodes degraded or unpowered |
| `flows_per_s` | 1/s | Aggregate flow rate |
| `scan_rate_pps` | 1/s | Reconnaissance feature intensity |
| `lateral_events` | count | Lateral-movement feature intensity |
| `c2_beacons` | count | Command-and-control beacon feature intensity |

Power. Populated for the site that carries the modelled 48 V subsystem; blank at
the other site. Blank means *not applicable*, never zero.

| Field | Unit | Meaning |
|---|---|---|
| `power_state_start` / `power_state_end` | enum | `MAINS` / `BATTERY` / `LOAD_SHED` / `ISOLATED` / `HOLD` / `CHARGE_DELAY` |
| `mains_present` | 0/1 | Mains supply present |
| `ats_transitions` | count | Automatic-transfer-switch transitions in the interval |
| `soc_pct` | % | Modelled state of charge |
| `soh_pct` | % | Assumed state of health |
| `pack_ocv_v` / `pack_voltage_v` | V | Pack open-circuit and terminal voltage |
| `pack_current_a` | A | Pack current, negative on discharge |
| `cell_ocv_min_v` / `cell_ocv_max_v` | V | Extremes of modelled cell open-circuit voltage |
| `cell_min_v` / `cell_max_v` | V | Extremes of modelled cell terminal voltage |
| `cell_imbalance_mv` | mV | Spread between cells |
| `battery_temp_c` | °C | Lumped RC thermal-model temperature |
| `load_w` | W | Served load |
| `shed_groups` | list | Load groups currently shed (group I is never shed) |
| `autonomy_min` | min | Projected remaining autonomy under current load |
| `protection_trip` | 0/1 | A BMS protection latched in this interval |
| `charge_state` | enum | Charger state |

Detection and quality.

| Field | Unit | Meaning |
|---|---|---|
| `detector_score` | 0..1 | Combined detector score |
| `detector_alert` | 0/1 | Score crossed the threshold |
| `alert_latency_s` | s | Delay from injected onset to the alert |
| `quality_flags` | `\|`-separated | From `OK`, `SYNTHETIC`, `ASSUMED_PARAMETER`, `UNKNOWN_UPLINK`, `IMPUTED`, `OUT_OF_ORDER`, `DUPLICATE`, `STALE`, `GAP`, `SCHEMA_MISMATCH`, `CLOCK_SUSPECT`, `SATURATED` |
| `telemetry_gap_marker` | 0/1 | The interval is a deliberately injected synthetic gap |

**Missing-value policy.** A gap row keeps its identity and time fields and blanks
every measurement field. Gaps are preserved as gaps; nothing is imputed silently,
and `NaN` is rejected by the contract layer. A gap in this package is an
**intentionally injected synthetic gap**, never a "real" data loss.

## `ground_truth.csv`

`run_id`, `replicate_id`, `truth_id`, `kind` (`injected` or `transition`),
`cause`, `site_id`, `target`, `stage`, `intensity`, `onset_utc`, `end_utc`,
`onset_step`, `end_step`, `expected_observable`, `notes`.

This file is produced by the **scenario controller**. It is the model's own
record of what it injected and how its state changed. It is not physical truth
and is not fed into the feature pipeline, which is what keeps the labels free of
leakage into detection.

## `alerts.csv`

`run_id`, `replicate_id`, `alert_id`, `step`, `timestamp_utc`, `site_id`,
`detector` (`rules`, `edge_ai`, `correlation`), `score`, `threshold`,
`rule_hits`, `explanation`, `correlated_with`, `recommended_action`,
`approval_required`, `shadow_mode`. Together with `ground_truth.csv` this file
allows TP/FP/FN to be recomputed independently of `summary.json`.

## `parameters.json`

Per parameter: `name`, `value`, `unit`, `evidence_status`, `deployment_status`,
`source_ref`, uncertainty where defined. `evidence_status` is one of `MEASURED`,
`VENDOR_SPEC`, `DERIVED`, `ASSUMED`, `SYNTHETIC_DEMO`, `UNKNOWN`. In this deposit
194 parameters are `SYNTHETIC_DEMO` and 4 are `UNKNOWN`; none is stronger.

## `summary.json`

Aggregated metrics with their denominators: per-site network availability, RTT
mean/p95/p99, loss, throughput, goodput ratio, failover steps; power SoC
start/end/drop/min, autonomy, battery steps, load-shed steps, protection-trip
steps, maximum temperature, cell imbalance; detection TP/FP/TN/FN, precision,
recall, F1, false-alarm rate, Wilson interval for recall, detection latency; the
gate verdict; and a per-replicate breakdown. `null` means the metric is undefined
for that run (for example precision with no alerts), not zero.

## `manifest.json`

`schema_version`, `run_id`, `experiment_id`, `mode`, `seed`, `engine_version`,
`created_utc`, `runtime` fingerprint, `hashes` (`config`, `engine_source`,
`summary`) and per-artifact `bytes` + `sha256`.

## `results/run_index.csv`

One row per independent run/replicate: `run_id`, `experiment_id`, `scenario_id`,
`component`, `replicate_id`, `mode`, `evidence_class`, `seed`, `duration_s`,
`rows`, `gates_passed`, `config_hash`, `engine_source_hash`, `run_dir`, `status`.

**This file defines the statistical unit of the campaign.** Rows of
`telemetry.csv` inside one run are dependent and must never be counted as
independent observations.
