# Data dictionary - `processed/runs.csv`

One row per executed run. This campaign: **1296 confirmatory runs**, 24 cells
(4 scenarios x 6 arms) x 54 repetitions.

## Metric provenance classes

The `class` column is the most important field in this table. It states how a number
came to exist, and therefore what it can be used to argue:

| class | meaning | admissible use |
|---|---|---|
| `endogenous_algorithmic` | produced by executing the `dtcr` implementation against the generated stream | **evidence about the method**: arms may legitimately differ here |
| `parameterized_model` | produced by a declared actuation or availability model whose constants are assumptions | descriptive only; every claim built on these carries the sensitivity analysis |
| `measured_implementation` | real CPU cost of running the framework code in this container | evidence about implementation cost, not about hardware performance |

No column in this file has class `real_testbed_*`. Nothing here measures the physical cyber range.

## Columns

| column | group | type / unit | meaning | class |
|---|---|---|---|---|
| `run_id` | identifier | string | Unique run key: PHASE-scenario-arm-rNNN | `-` |
| `scenario` | design | enum S1..S4 | Evaluation scenario | `-` |
| `arm` | design | enum A0..A5 | Compared configuration | `-` |
| `repetition` | design | integer | Block index; the (scenario, repetition) pair fixes the world seed | `-` |
| `phase` | design | enum | pilot | confirmatory | `-` |
| `data_origin` | provenance | enum | simulation | simulation_pilot. Never real_testbed_* | `-` |
| `site` | provenance | string | Execution host; SIL-container for this campaign | `-` |
| `operator_id_pseudonym` | design | string | AUTO for automated arms, OP-SIM for the modelled manual arm | `-` |
| `target_node` | design | string | Asset selected by the injector as the incident source | `-` |
| `violation_type` | design | enum | S4 only: which admissibility dimension the request violates | `-` |
| `t_attack` | timestamp | seconds | Injection onset (machine timestamp) | `parameterized_model` |
| `t_detect` | timestamp | seconds | First persistent detector firing on the target; NaN if never | `endogenous_algorithmic` |
| `t_alert` | timestamp | seconds | Alert dispatch | `parameterized_model` |
| `t_action_start` | timestamp | seconds | Decision complete, actuation begins | `parameterized_model` |
| `t_contain` | timestamp | seconds | Containment action enacted | `parameterized_model` |
| `t_service_restore` | timestamp | seconds | Eq. (15) restoration instant; NaN = right-censored | `parameterized_model` |
| `t_recover` | duration | seconds | Containment plus post-action validation, relative to t_attack | `parameterized_model` |
| `detection_latency` | metric | seconds | t_detect - t_attack; NaN when not detected | `endogenous_algorithmic` |
| `containment_latency` | metric | seconds | t_contain - t_attack; NaN when never contained | `parameterized_model` |
| `detected` | metric | 0/1 | Incident detected inside the observation window | `endogenous_algorithmic` |
| `contained` | metric | 0/1 | A containment action was enacted | `endogenous_algorithmic` |
| `recovered` | metric | 0/1 | Availability met Eq. (15) inside the window | `parameterized_model` |
| `detector_used` | diagnostic | enum | ids | anomaly | integrity - which mechanism fired first | `endogenous_algorithmic` |
| `action_selected` | metric | enum | Action chosen by Eq. (12) under Eq. (13) | `endogenous_algorithmic` |
| `action_optimal` | metric | 0/1 | Chosen action equals the arm-independent true-objective minimiser | `endogenous_algorithmic` |
| `action_regret` | metric | [0,1] | Normalised regret against the true objective; 0 = optimal | `endogenous_algorithmic` |
| `containment_effect` | metric | [0,1] | Realised relative reduction of propagated risk | `endogenous_algorithmic` |
| `residual_impact` | metric | [0,1] | Residual impact driving the availability model | `endogenous_algorithmic` |
| `policy_violation` | metric | 0/1 | An inadmissible placement was admitted | `endogenous_algorithmic` |
| `unsafe_action` | metric | 0/1 | Action enacted while violating an unimplemented constraint | `endogenous_algorithmic` |
| `rollback` | metric | 0/1 | Automated rollback of an unsafe action was required | `endogenous_algorithmic` |
| `fp_samples_holdout` | metric | count | Per-sample detector exceedances on the held-out clean window | `endogenous_algorithmic` |
| `fp_rate_holdout` | metric | [0,1] | fp_samples_holdout / (assets x holdout samples); OUT OF SAMPLE | `endogenous_algorithmic` |
| `fp_nodes_persistent` | metric | count | Assets producing a persistent false firing on the holdout window | `endogenous_algorithmic` |
| `fp_per_hour` | metric | 1/h | Persistent false firings extrapolated to one hour | `endogenous_algorithmic` |
| `integrity_tp` | metric | count | Corrupted blocks found by the audit challenge | `endogenous_algorithmic` |
| `integrity_fp` | metric | count | Audit alarms on clean cycles | `endogenous_algorithmic` |
| `integrity_cycles` | metric | count | Audit cycles executed before detection or window end | `endogenous_algorithmic` |
| `kappa` | metric | >=1 | Risk amplification, Eq. (11); NaN for arms without the graph | `endogenous_algorithmic` |
| `convergence_margin` | diagnostic | (0,1] | 1 - spectral radius of lambda W^T | `endogenous_algorithmic` |
| `source_localized` | metric | 0/1 | argmax of the risk vector equals the true source | `endogenous_algorithmic` |
| `blast_recall` | metric | [0,1] | Share of the true impacted set flagged above theta | `endogenous_algorithmic` |
| `blast_precision` | metric | [0,1] | Share of flagged assets that are truly impacted | `endogenous_algorithmic` |
| `whatif_abs_err` | metric | [0,1] | |predicted - realised| relative residual risk; NaN without what-if | `endogenous_algorithmic` |
| `nri` | metric | [0,1] | Normalized resilience index, Eq. (18)/(19) | `parameterized_model` |
| `availability_below_amin` | metric | [0,1] | Share of the window below A_min | `parameterized_model` |
| `min_availability` | metric | [0,1] | Minimum of the availability trace | `parameterized_model` |
| `orchestrator_cpu_s` | metric | seconds | Measured CPU time of one decision cycle | `measured_implementation` |
| `run_cpu_s` | metric | seconds | Measured CPU time of the whole run | `measured_implementation` |
| `censored_restore` | quality | 0/1 | 1 = t_service_restore is right-censored | `-` |
| `exclusion_flag` | quality | 0/1 | 1 = excluded from analysis (0 runs in this campaign) | `-` |
| `exclusion_reason` | quality | string | Mandatory whenever exclusion_flag = 1 | `-` |
| `protocol_deviation` | quality | string | Free-text deviation note | `-` |
| `execution_order` | design | integer | Position in the pre-generated randomisation plan | `-` |
| `start_utc` | provenance | ISO-8601 | Wall-clock start of the run | `-` |
| `raw_log_path` | provenance | path | Gzipped JSON evidence bundle, relative to experiment/ | `-` |
| `raw_log_sha256` | provenance | hex64 | SHA-256 of the uncompressed bundle | `-` |

## Censoring

`t_service_restore` is right-censored in **318 of 1296** runs
(availability never met Eq. 15 inside the 900 s observation window). Censored runs are
**kept** in the dataset and reported as censored. They are never deleted, and they are
never silently dropped from a mean: `analysis/analyze.py` prints the censored count
beside every latency statistic and refuses to compute an effect size on fewer than
five complete pairs.

## Exclusions

`exclusion_flag = 1` in **0** runs. No run was excluded.

## Raw evidence bundles

Each `raw_log_path` is a gzipped JSON object holding the availability trace, the local
and propagated risk vectors, the realised risk and true objective of every candidate
action, the admissible and rejected candidate lists, the true impacted asset set and the
asset ordering. `analysis/audit_provenance.py` verifies every bundle against its
SHA-256 and recomputes the NRI from the stored trace.
