# Materials and Methods — additions and corrections

Fold these into §2. They address the reviewer requests for actual parameters, an
implementation mapping, exact attack recipes, a fair baseline/ablation matrix,
the testbed-naming concern, and a statistical-analysis plan.

## 2.1a Threat model (new subsection)

Insert the per-scenario threat matrix and the trusted-computing-base description
from `THREAT_MODEL.md` §1–§2. State explicitly that compromise of the digital
twin, the policy engine and the orchestrator is out of the evaluated scope and
listed as a limitation.

## 2.6a Implementation mapping (new table)

Table 2 names the platforms but not which module realises each authored
mechanism. Add:

| Function | Realising module | Input | Output | Config / code |
|---|---|---|---|---|
| Homomorphic integrity proof | `integrity-agent` (edge DaemonSet) | 4 KiB MQTT/block data | proof tuple | `configs/framework_parameters.yaml → integrity_audit`; `dtcr.audit` |
| Trust calculation | `trust-service` | c, q, b per source | T_i | `→ trust`; `dtcr.trust` |
| Anomaly calculation | `detector` sidecar | 9-D feature vector | anomaly score | `→ anomaly`; `dtcr.anomaly` |
| Graph propagation | `risk-service` | R, W, λ | R̃ | `configs/kubernetes/cloud-tier.yaml → edges.csv`; `dtcr.risk` |
| What-if simulation | Ditto simulation service | candidate action | predicted state | `configs/eclipse_ditto/`; `dtcr.orchestration` |
| Policy validation | `policy-engine` | candidate placement | admit/deny | `→ orchestration`; `dtcr.orchestration.admissible` |
| Enforcement | orchestrator | selected action | deployment change | Kubernetes manifests |
| Recovery validation | `validation-module` | post-action telemetry | pass/fail | `→ orchestration.rollback` |

## 2.6b Testbed naming (correction)

The twelve sensors are **emulated** and no physical plant/actuator loop is
described, so "hardware-in-the-loop" is replaced throughout by **"hybrid
physical/emulated edge-cloud cybersecurity testbed"**: the four Raspberry Pi 5
edge nodes, the three cloud VMs and the attacker host are physical; the IoT
segment is emulated with Eclipse Mosquitto. If a physical actuator loop is added
later, the original term can be restored with the closed loop documented.

## 2.7a Actual experimental parameters (new table)

Replace the "illustrative value" column of Table 1 with a reference to
`configs/framework_parameters.yaml`, and add a table headed **"Actual
experimental parameters"** listing every value that file contains: ε_sync = 0.08;
trust weights α, β, γ = 0.40, 0.35, 0.25; ρ = 0.60; block size 4 KiB, l = 10,000,
r = 59, audit cadence 30 s; feature dimension p = 9 with the nine named features;
normal window 1800 s, calibration window 900 s; covariance shrinkage 0.05;
criticality weights s_i and host-trust minima τ_i as tabulated; λ = 0.45,
θ = 0.35 on the propagated exposure score; μ1, μ2, μ3 = 0.20, 0.15, 0.25;
action-simulation horizon 120 s; orchestration cycle 5 s; RTO 300 s, A_min 0.95,
Δ_h 30 s; solver = exhaustive enumeration over the affected subgraph, tolerance
1e-9, timeout 2 s.

## 2.7b Attack recipes (new tables)

Insert the four recipes from `attacks/` as a table with rows: target
asset/service, initial attacker privilege, command/payload, rate/intensity,
duration, ground-truth onset, attack-success criterion, expected defensive
action, reset/washout. Replace the vague "SYN/ACK flood" of S3 with the exact
profile from `attacks/s3_dos/recipe.yaml`: TCP SYN half-open flood, flag S,
randomised source addresses, 120-byte packets, 25,000 pps, destination port
8443, sustained 180 s. For S2, report the four sub-cases (replay, injection,
modification in transit, semantic falsification) separately, and state that the
homomorphic hash covers the first three but not semantic falsification by an
authenticated compromised sensor (`THREAT_MODEL.md` §4).

## 2.7c Baseline and ablation matrix (new)

Add the experimental matrix so the contribution of each component is measurable:

| Variant | IDS | Integrity/prov. | Trust | Graph prop. | DT what-if | Automated response |
|---|:--:|:--:|:--:|:--:|:--:|:--:|
| B0: IDS + manual recovery | ✓ | – | – | – | – | – |
| B1: IDS + automated playbook | ✓ | – | – | – | – | ✓ |
| B2: security stack without DT | ✓ | ✓ | ✓ | – | – | ✓ |
| A1: framework without graph | ✓ | ✓ | ✓ | – | ✓ | ✓ |
| A2: framework without what-if | ✓ | ✓ | ✓ | ✓ | – | ✓ |
| Full framework | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Measured endpoints beyond latency/recovery: unsafe-action rate, policy-violation
rate, rollback rate, recovery-success rate, orchestration decision latency,
digital-twin prediction error, and dependency-risk-ranking accuracy
(`results/table_S6_ablation.csv`, `figures/figure11_ablation.*`). For the manual
baseline, report operator count, experience, playbook, alert-delivery instant and
the human-response-time measurement rule.

## 2.8a Statistical analysis plan (new subsection)

Insert `PROTOCOL.md` §5 verbatim: paired design with matched-pair repetitions,
mean with 95% t and bootstrap CIs, paired t-test with Wilcoxon alongside, Holm
correction across the four scenarios, Hedges g and Cliff's delta, Wilson
intervals for all classification rates, and the fixed-before-analysis threshold
rule. Insert §4 (missed detections, failed recovery, censoring) and §7 (the
isolated-lab safe-experiment statement).
