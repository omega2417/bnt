# Supplementary File S1 — Prospective field-experiment protocol

**Status: planned (evidence level C). No field run has been executed.**
This protocol accompanies the MetaTwin-Guard reference artifact and Section 3.10
of the article. Nothing in it may be executed before every gate in §1 is closed.

## 1. Execution gates (all mandatory)

| Gate | Required evidence before the first pilot run |
|---|---|
| G1 Written range authorization | Signed scope: responsible personnel, sites, address ranges, test services, dates, stop authority, abort chain |
| G2 Ethics / privacy determination | Institutional determination; required before any human, operator-performance or identifiable data |
| G3 Isolation and rollback | Experimental VLANs/SSIDs/identities separated from production; default-deny egress with allowlist; configuration backups; independent rollback path |
| G4 Inventory | Router/controller firmware, AP/switch models, VPN protocol/MTU, hosts, dependency versions recorded |
| G5 Telemetry interfaces | Approved read-only exports/APIs, otherwise the modality is omitted (recorded as missing, never as zero) |
| G6 Keys and time | Independent field keys generated and protected (test-fixture keys of the artifact are forbidden); clock synchronization and preregistered offset tolerance |
| G7 Power procedure (S7 only) | EcoFlow model, capacity, connected load, protective limits, electrical-safety procedure, responsible person |
| G8 Extended verification suite | Component failure, concurrent ingestion, crash recovery, interrupted evidence append, validator-key compromise |
| G9 Pilot variance | Three pilot runs (safety, timing, completeness, variance) followed by an a priori power analysis |

MetaTwin-Guard is never relied upon for safe termination of a scenario.

## 2. Experimental unit

One **independently reset run** (not a packet, not an event) is the statistical unit:

1. pre-run health and isolation gate (checklist in `S2_field_workbook.xlsx`, sheet `run_gates`);
2. 10 min baseline observation;
3. ≤ 5 min controlled perturbation;
4. 10 min recovery observation;
5. audit and reset.

Background load: 20 %, 50 % or 80 % of **separately measured** stable throughput of
the approved path (never of nominal provider rates). Scenario and load order are
randomized within day/site/path blocks; matched normal-operation controls (S0) are
interleaved.

## 3. Scenarios

| ID | Condition | Primary endpoints | Boundary |
|---|---|---|---|
| S0 | Matched normal-operation control | false alerts; synchronization; completeness; resource use | isolated benign test traffic only |
| S1 | Replay of a previously accepted signed test event | rejection recall; quarantine latency; state invariance | telemetry interface only |
| S2 | Modification of a test event after signing | modification rejection; reason correctness; state invariance | authoritative logs unchanged |
| S3 | Invalid signature / unregistered test key | rejection recall; false rejection; reason correctness | pre-created test keys only |
| S4 | Administratively controlled WAN failover | detection; session interruption; failover and recovery time | no production/emergency traffic; independent rollback |
| S5 | Controlled VPN delay/jitter/loss/rate limit | RTT; jitter; loss; throughput; detection and recovery | approved test path only; no cryptographic downgrade |
| S6 | Bounded test-client authentication anomaly | precision; recall; F1; AUPRC; explanation hit rate | test-only SSID/service and accounts |
| S7 | Conditional EcoFlow transition (exploratory) | availability; continuity; recovery | only after G7 |

## 4. Stop criteria

Immediate stop on: unexpected egress, production impact, loss of rollback access,
device alarm, exceeded safety limit, uncontrolled propagation, credential exposure,
or any operator concern. Invalid and safety-stopped runs stay in the accountability
table (`S2`, sheet `accountability`); they are never deleted or silently replaced.

## 5. Endpoints and analysis plan

* Detection latency, Eq. (8): `L_det,r = t_first_correct_alert,r − t_injection_start,r`;
  runs without an alert are **right-censored** (survival / restricted-mean methods).
* Synchronization latency, Eq. (9): `L_sync,i = t_twin_commit,i − t_event,i`; valid only
  while clock offset ≤ preregistered tolerance.
* Precision, recall, F1, AUPRC (Saito & Rehmsmeier 2015), false alerts per hour
  (exposure time), integrity-rejection recall, false-rejection rate, explanation
  top-3 hit rate, recovery, evidence verification, CPU, memory, storage growth.
* Freshness contract: node state is `current` (Δ ≤ τ_fresh), `stale`
  (τ_fresh < Δ ≤ τ_lost) or `unknown` (Δ > τ_lost); τ values preregistered
  (artifact defaults 30 s / 120 s, `config.py`).
* Partitions (calibration/validation/test) contain complete runs or days.
* Mode comparisons paired within run; confidence intervals by cluster bootstrap over
  runs; Holm adjustment within each confirmatory endpoint family.
* Thresholds of static rules are re-derived from the pilot baseline of each approved
  path and frozen before confirmatory runs; binary indicators are handled by explicit
  rules; feature-specific dispersion floors are a preregistered alternative.
* Any post hoc tuning is reported as exploratory.

## 6. Data handling

Public artifacts exclude credentials, private keys, operational IP addressing,
sensitive topology, personal data and exploit-enabling configuration. The evidence
chain stores hashes and minimal decision metadata, not raw telemetry.
