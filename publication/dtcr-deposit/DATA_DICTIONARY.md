# Data dictionary

Every table below is the contract between the measurement campaign and the
analysis code. Replacing the synthetic files with real exports that honour these
column names and units regenerates the whole Results section unchanged.

Common column: **`data_origin`** — free text identifying the source of the row.
`synthetic_reference` marks generated data (see `PROVENANCE.md`); a real campaign
should use an identifier such as `testbed_2026-09`.

---

## `data/run_level_metrics.csv` — one row per run

Design: 4 scenarios x 2 arms x 20 repetitions = **160 rows**.

| Column | Type | Unit | Definition |
|---|---|---|---|
| `run_id` | string | – | `{scenario}_{method}_r{NN}`; primary key, also names the trace file |
| `scenario` | enum | – | `S1` compromised edge, `S2` falsified telemetry, `S3` DoS, `S4` malicious migration |
| `method` | enum | – | `baseline` (IDS-only + manual recovery) or `framework` |
| `repetition` | int | – | 1..20; the same index in both arms is a matched pair |
| `attack_onset_s` | float | s | ground-truth `t_a`, from the attack driver's own log |
| `detection_s` | float | s | `t_det`, first alert or integrity failure attributable to the attack |
| `containment_s` | float | s | `t_c`, first enforced protective action |
| `recovery_s` | float | s | absolute time at which the Eq. (15) hold condition is first met |
| `disruption_onset_s` | float | s | `t_dis`, first sample with availability below `a_min`; anchors the NRI window |
| `detection_latency_s` | float | s | `detection_s - attack_onset_s` (Eq. 14 summand) |
| `recovery_time_s` | float | s | `recovery_s - attack_onset_s` (Eq. 15) |
| `availability_floor` | float | – | lowest sustained availability of the run; diagnostic only |
| `nri` | float | – | Eq. (18)–(19) over `[t_dis, t_dis + 2*RTO]` |
| `recovery_censored` | 0/1 | – | 1 when the hold condition is never met inside the window; excluded from means, retained in counts |
| `trace_file` | path | – | path relative to `data/` |

**Note on `t_det` vs `t_dis`.** The manuscript reuses `t_d` for both. This
deposit keeps them separate: detection latency is measured from `t_det`, the NRI
integration window is anchored on `t_dis`. They are not interchangeable and are
stored in different columns.

---

## `data/availability_traces/{run_id}.csv` — one row per sample

| Column | Type | Unit | Definition |
|---|---|---|---|
| `t_s` | float | s | time from the start of the observation window; sampling interval in `configs/framework_parameters.yaml` |
| `availability` | float | – | fraction in [0, 1] of successful service probes in the sampling interval |
| `run_id` | string | – | foreign key to `run_level_metrics.csv` |

`recovery_time_s` and `nri` in the summary table are **derived from these files**
by `analysis/calculate_nri.py`, which fails if the two disagree by more than one
unit in the last stored decimal place.

---

## `data/confusion_matrices/integrity_confusion.csv`

One row per (scenario, corruption level). **Observation unit: one challenged
telemetry block** — not a message, not a run.

| Column | Type | Definition |
|---|---|---|
| `scenario` | enum | S1–S4 |
| `corruption_fraction` | float | `d/l`, fraction of corrupted blocks in the replica |
| `observation_unit` | string | fixed: `challenged_telemetry_block` |
| `tp`, `fn`, `tn`, `fp` | int | counts; positives are genuinely corrupted blocks |
| `n` | int | `tp+fn+tn+fp` |
| `nominal_tpr`, `nominal_tnr` | float | operating point the counts were drawn from (synthetic data only) |

---

## `data/resource_measurements/resource_usage.csv`

One row per run per arm.

| Column | Unit | Definition |
|---|---|---|
| `cpu_pct` | % | mean cluster CPU utilisation over the run |
| `ram_mb` | MB | mean resident memory across the edge and cloud tiers |
| `network_kbps` | kbit/s | mean inter-tier traffic |
| `storage_mb_per_h` | MB/h | audit-log and evidence growth rate |
| `integrity_verification_ms` | ms | per-audit-round verification latency (framework only) |
| `graph_solver_ms` | ms | time to solve Eq. (10) on the affected subgraph (framework only) |
| `whatif_simulation_ms` | ms | time to simulate all candidate actions (framework only) |
| `end_to_end_orchestration_ms` | ms | evidence-to-enforcement latency; measured in both arms |

Empty cells mark components that do not exist in the baseline arm. They are
missing by design, not missing at random, and must not be imputed.

---

## `data/ablation_runs.csv`

One row per (variant, scenario, repetition); 6 variants x 4 x 20 = **480 rows**.

| Column | Definition |
|---|---|
| `variant` | `B0_ids_manual`, `B1_ids_playbook`, `B2_stack_no_dt`, `A1_no_graph`, `A2_no_whatif`, `FULL_framework` |
| `detection_latency_s`, `recovery_time_s` | as above |
| `unsafe_action` | 1 if the enforced action degraded a service it was not meant to touch |
| `policy_violation` | 1 if an enforced placement violated a label, trust or domain constraint |
| `rollback` | 1 if recovery validation failed and the action was reverted |
| `recovery_success` | 1 if service was restored within the observation window without operator intervention |
| `orchestration_decision_latency_ms` | evidence-to-decision latency |
| `twin_prediction_error` | \|predicted − observed\| post-action aggregate risk; empty for variants with no twin |
| `risk_ranking_correct` | 1 if the top-ranked at-risk asset matched the ground-truth incident trace |
