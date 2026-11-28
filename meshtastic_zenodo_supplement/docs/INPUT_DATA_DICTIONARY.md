# Input data dictionary

CSV encoding: UTF-8; delimiter: comma; decimal separator: period. Boolean fields use 0/1. UTC or offset-aware ISO 8601 timestamps are required. Empty templates contain headers only and intentionally fail validation until observations are supplied.

## Metadata and target

| Field | Meaning |
|---|---|
| event_id | Stable logical task identifier, retained across retries |
| group_id | Independent experimental block/campaign; all correlated runs and paired conditions share this value |
| run_id | Physical or simulated run; a run cannot be assigned to several groups |
| node_id | M1, M2 or S0; intended logistics endpoint for this decision |
| scenario | E0–E8 as defined in the experiment protocol |
| provenance | Exactly `synthetic` or `measured`; never change a synthetic label to measured |
| decision_time | Time at which the recommendation would have been made |
| feature_window_end | Most recent cutoff of the feature calculation; cannot exceed decision_time |
| completed_on_time | Training only: 1 if the specified logistics task was completed by its original deadline, otherwise 0 |
| outcome_observed_at | Training only: time the final outcome was established; must be no earlier than decision_time plus deadline_remaining_s |

The last two fields are targets/audit fields and are never neural inputs. Identifiers, scenario and provenance are not neural features either. Radios and operators that are unavailable remain in the planned task denominator. A radio ACK is not completion evidence.

## Neural features in fixed model order

| Feature | Unit and accepted range | Calculation available before the decision |
|---|---|---|
| rssi_dbm | dBm, −150 to −20 | Most recent valid received-signal observation for the intended path; retain receiver and hop provenance in raw logs |
| snr_db | dB, −30 to 30 | Most recent valid signal-to-noise observation; does not summarize an entire multihop path automatically |
| pdr_5m | Fraction, 0–1 | Unique prior events received before the cutoff / prior eligible transmitted events in the preceding five minutes; exclude the current task |
| latency_p95_5m_s | Seconds, 0–600 | 95th percentile of prior observed delays in that window; document clock synchronization and one-way vs RTT separately |
| aoi_s | Seconds, 0–7200 | decision_time minus creation time of the latest valid status update |
| battery_pct | Percent, 0–100 | Documented remaining capacity estimate of the mobile node relevant to the task |
| backup_minutes | Minutes, 0–1440 | Conservative estimate for the shortest-lived required dispatch-path component; use measured energy/power and record the method |
| queue_depth | Integer, 0–100 | Number of queued tasks at the decision cutoff |
| hop_count | Integer, 0–7 | Observed or configured path estimate available at decision time; record how it was obtained |
| terminal_available | 0 or 1 | Fresh check of the required operator terminal |
| s0_available | 0 or 1 | Fresh check of the stationary radio |
| external_connectivity | 0 or 1 | Independent observation of external Internet availability; not used as a mandatory prerequisite for local service |
| deadline_remaining_s | Seconds, 0–300 | Time remaining to the original task deadline; zero means expired |

These are software-domain limits, not manufacturer specifications. Values outside the declared domain are rejected. Zero is a real observation, not a code for missingness. If no prior transmission, reception or valid delay exists, leave the corresponding feature missing and obtain `INPUT_REVIEW`; do not impute a successful link. The current feature table is an explicit input interface, not a universal adapter for every Meshtastic firmware log format.

## Building the input table from field logs

Keep a durable event log with run_id, event_id, sender, recipient, creation/hand-off/reception/acceptance/completion timestamps, power states and radio metadata. Deduplicate retransmissions by logical event, preserving their individual trace records. Choose the historical cutoff before looking at the target outcome. Build the prior five-minute window and compute the features using only observations that had actually arrived by that cutoff. Events whose receipt becomes known later must not be used retrospectively in that window.

Record the raw log schema, clock errors, firmware settings, instruments, antenna geometry, units and provenance in the run manifest. An external preprocessing step must construct these features; no automatic Meshtastic serial/MQTT parser is claimed. Preserve the raw records so feature calculations can be audited. `feature_window_end <= decision_time` catches obvious time leakage; software cannot prove that a manually supplied feature was computed honestly from the preceding window.

Use full independent campaigns as groups when dependence extends beyond one run. Grouping only by individual packet, random splitting within a run, or separating M1 and M2 from the same run would overstate generalization. For final scientific evaluation, add a future-time or different-site test set that is never used in feature selection, threshold selection or stopping decisions.
