# Parameters

Every value here is a **design value**. The costs and effectiveness coefficients are
dimensionless transparent prioritization parameters. They are not market prices, not
observed control performance, and not fitted to any data. Dump them machine-readably with:

```bash
acp-sme params -o results/parameters.json
```

## Table A1 — capability parameters (`capabilities.py`)

| Code | Capability | Cost units | Effectiveness | Prerequisites |
| --- | --- | --- | --- | --- |
| GOV | Governance and risk | 4 | 0.93 | — |
| AST | Asset inventory | 3 | 0.92 | — |
| IAM | Identity and access | 5 | 0.95 | AST |
| DAT | Data protection | 5 | 0.94 | AST |
| CFG | Secure configuration | 4 | 0.88 | AST |
| TPR | Supplier assurance | 4 | 0.86 | GOV |
| DET | Logging and detection | 5 | 0.90 | AST |
| IR | Incident response | 4 | 0.87 | GOV |
| REC | Recovery and continuity | 4 | 0.86 | IR |
| CLD | Cloud-edge security | 4 | 0.88 | IAM |
| XRI | XR identity and virtual assets | 5 | 0.91 | IAM, DAT |
| DTI | IoT and digital-twin integrity | 6 | 0.93 | DAT, DET |
| AIG | AI service governance | 5 | 0.89 | GOV, DAT |
| TRN | Awareness and role training | 3 | 0.83 | GOV |

Total cost of all 14 capabilities: **61 units**. Of the 2¹⁴ = 16,384 candidate subsets,
**919** are prerequisite-closed and form the feasible region of Equation (4).

Because every effectiveness coefficient is below 1.0, modeled coverage **cannot reach
100%** even when every capability is selected. Maximum attainable coverage is the
demand-weighted mean of `e(c)`, around 90%. This is intentional: the index measures
weighted capability demand met, not perfect security.

## Table 4 — scenario inputs (`scenarios.py`)

| Archetype | Staff | Budget units | Principal metaverse exposure |
| --- | --- | --- | --- |
| Micro retail | 8 | 34 | XR storefront, cloud identity, AI service |
| Small manufacturer | 46 | 45 | Digital twin, IoT/edge, supplier XR |
| Medium services | 180 | 54 | AI agents, immersive workspace, virtual assets |

Base demand vectors (all unlisted capabilities are 0):

- **Micro retail** — GOV 0.65, AST 0.75, IAM 0.85, DAT 0.90, CFG 0.70, IR 0.55, REC 0.60,
  TRN 0.55
- **Small manufacturer** — GOV 0.75, AST 0.90, IAM 0.85, DAT 0.85, CFG 0.85, TPR 0.60,
  DET 0.80, IR 0.65, REC 0.70, CLD 0.60, TRN 0.60
- **Medium services** — GOV 0.90, AST 0.85, IAM 0.95, DAT 0.95, CFG 0.80, TPR 0.80,
  DET 0.85, IR 0.75, REC 0.75, CLD 0.85, TRN 0.70

## Table A2 — event catalog and demand increments

Demand accumulates at the event day and is capped at **1.75**. Each event occurs on the
same day in all 30 replicates of its archetype; observation noise and review delay vary by
seed.

| Archetype | Day | Event | Demand increments |
| --- | --- | --- | --- |
| Micro | 20 | Cloud point-of-sale migration | CLD +0.95; TPR +0.65; IAM +0.35 |
| Micro | 45 | Immersive storefront | XRI +1.15; DAT +0.45; IAM +0.35 |
| Micro | 72 | Credential-stuffing incident | DET +1.20; IR +0.60; REC +0.35 |
| Micro | 96 | Generative-AI sales assistant | AIG +1.05; GOV +0.35; DAT +0.45 |
| Small | 18 | Production digital twin | DTI +1.25; DET +0.45; DAT +0.40 |
| Small | 40 | Supplier API | TPR +1.05; CLD +0.55; IAM +0.35 |
| Small | 67 | Remote XR maintenance | XRI +1.05; IAM +0.45; DTI +0.35 |
| Small | 91 | AI quality inspection | AIG +1.00; DAT +0.35; GOV +0.30 |
| Small | 108 | Edge-gateway outage | REC +0.95; IR +0.55; CLD +0.35 |
| Medium | 15 | Agentic-AI workflow | AIG +1.20; GOV +0.45; DAT +0.40 |
| Medium | 34 | Acquired supplier platform | TPR +1.05; IAM +0.40; AST +0.25 |
| Medium | 59 | Persistent XR workspace | XRI +1.15; IAM +0.40; DAT +0.35 |
| Medium | 80 | Multi-region edge expansion | CLD +0.85; DET +0.55; REC +0.35 |
| Medium | 103 | Virtual-asset fraud attempt | XRI +0.65; DET +0.75; IR +0.55 |

14 designed events × 30 replicates = **420 labeled material events**.

## Table A3 — observation, detection, accounting and seed parameters

| Group | Value |
| --- | --- |
| Initial observation | Gaussian σ = 0.04; exact selector applied at day 0; no attenuation |
| Common reassessment model | Gaussian σ = 0.045; XRI/DTI/AIG attenuation probability 0.02; attenuated value × 0.35 |
| Event-score proxy | `s = √(Σ increment² / n) + ε`, ε ~ N(0, 0.055²); primary τ = 0.28 |
| Triggered review delay | P(0, 1, 2, 3 days) = 0.12, 0.44, 0.36, 0.08 above threshold; otherwise discrete-uniform 5–8 days |
| False triggers | Daily probability `0.0008 + 0.012·e^(−5.2τ)`, evaluated independently on days 1–119 |
| Selector and parsimony | Exhaustive over every dependency-valid subset; λ = 0.002 per selected resource-cost unit |
| Review-hour accounting | Static 4.0 h; monthly 3.6 h at days 0, 30, 60, 90; ACP-SME 1.0 h + 0.30 h per unique triggered reassessment + 0.12 h per changed profile membership |
| Irrelevance threshold | A selected capability with true relevance < 0.20 counts as irrelevant expenditure |
| Horizon | 120 daily decision windows |
| Seed schedule | `27012026 + 101 × replicate + 10007 × archetype_index`; sensitivity runs add 1000 to the replicate index |

Review hours are **descriptive accounting outputs**. They do not constrain the selector and
must not be read as measured labor savings or implementation cost.

## Detector configuration (`detector.py`)

The default feature weights are **approved configuration values**, renormalized to sum to
one by Equation (1). They are not fitted to the reported traces, and the reported experiment
does not use them — it uses the event-score proxy above.

| Feature | Type | Weight | Scale |
| --- | --- | --- | --- |
| `cloud_service_count` | numeric | 0.10 | 10 |
| `xr_asset_count` | numeric | 0.12 | 5 |
| `digital_twin_count` | numeric | 0.12 | 3 |
| `ai_service_count` | numeric | 0.12 | 5 |
| `iot_asset_count` | numeric | 0.08 | 50 |
| `privileged_account_count` | numeric | 0.08 | 10 |
| `mfa_coverage` | numeric | 0.10 | 1 |
| `end_of_support_ratio` | numeric | 0.06 | 1 |
| `residency_class` | category | 0.06 | — |
| `supplier_access_type` | category | 0.08 | — |
| `headcount_band` | category | 0.04 | — |
| `sector` | category | 0.04 | — |

Persistence rule: **2 of 3** consecutive decision windows above τ. Default scheduled-review
period: 90 windows.

The five critical predicates fire deterministically — no threshold, no persistence, no
probability:

1. a new internet-facing critical service;
2. persistent privileged supplier access;
3. a new restricted-data flow;
4. a digital twin connected to operational telemetry;
5. a material loss (≥ 0.10) of MFA, backup or logging coverage.

## Versioned packs (R7)

Each pack is versioned independently so that historical replay and rollback stay meaningful.
Changing any of them alters published results and requires a version bump — see
`CONTRIBUTING.md`.

| Pack | Constant | Value |
| --- | --- | --- |
| Capability | `CAPABILITY_PACK_VERSION` | `cap-pack-0.1.0` |
| Crosswalk | `CROSSWALK_PACK_VERSION` | `crosswalk-pack-0.1.0` |
| Detection rules | `RULE_PACK_VERSION` | `rule-pack-0.1.0` |
| Scenario | `SCENARIO_PACK_VERSION` | `scenario-pack-0.1.0` |
| MNMM schema | `SCHEMA_VERSION` | `mnmm-0.1.0` |
