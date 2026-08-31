# Claims boundary

This document states, component by component, what this software supports and what it does
not. It exists because the most likely misuse of an artifact like this is not a bug — it is
an overstated claim.

## What ACP-SME is

A **governance decision-support artifact**. It recommends changes to an enterprise's
approved cybersecurity profile, explains why, and routes the recommendation to an
accountable person.

## What ACP-SME is not

| It is not | Because |
| --- | --- |
| An anti-malware packer | It observes metadata; it never touches an endpoint or a file. |
| A vulnerability scanner | It consumes counts and ratios; it never probes a system. |
| A SIEM | It reasons about a profile decision, not high-volume technical events. |
| An autonomous enforcement engine | It cannot implement a safeguard. `ProfileLedger.apply` refuses anything but an authorized approval. |
| An actuarial loss model | No monetary consequence, threat interaction, or loss distribution is modeled. |
| A certification system | It never asserts conformity with any standard. |

## What each number means

| Output | What it is | What it is **not** |
| --- | --- | --- |
| Modeled coverage | Effectiveness-weighted selected capability demand ÷ total current demand, under encoded parameters | A probability of avoiding an incident; a measure of implementation depth or evidence truthfulness |
| Adaptation delay | Days from a labeled synthetic event to inclusion of its target capabilities | Evidence that the selected capability was implemented well, or at all |
| Review hours | Assigned accounting constants from Table A3 | A measured labor saving, an implementation cost, or a time-and-motion observation |
| False alerts | Reassessments caused only by the simulator's nuisance-trigger process | A detector false-positive rate measured against real telemetry |
| Effectiveness `e(c)` and cost `k(c)` | Dimensionless transparent prioritization parameters | Market prices or observed control performance |
| Confidence intervals | Variation across 90 synthetic traces | Inference to any national or global SME population |

## What each component's evidence status is

| Component | Implemented | Verified by | Evidence status |
| --- | --- | --- | --- |
| Exact selector (Eq. 3–4) | Yes | Unit tests + the reported experiment | Budget and prerequisite feasibility are **algorithmic invariants**, proven by construction and asserted at every selection — not empirical success rates |
| Capability–demand coverage | Yes | The reported experiment | Synthetic model output under encoded assumptions |
| MNMM and metadata guard | Yes | Unit tests and `acp-sme demo` | **Design claim.** The experiment used event-level demand increments, not live connector records. Representational sufficiency is untested in the field |
| Material-change detector (Eq. 1–2) | Yes | Unit tests and `acp-sme demo` | **Not exercised by the reported experiment**, which used the disclosed event-score proxy instead |
| Typed crosswalk | Yes | Unit tests (100% complete-path rate) | **Artifact design.** Formal semantic validation by independent standards specialists remains outstanding |
| Approval lifecycle and ledger | Yes | Unit tests and `acp-sme demo` | Structural properties (role separation, hash chaining, replay, rollback) hold by construction |

## Why the experiment is a surrogate

Section 3.7 of the article states it plainly: the evaluation is a **component-level
surrogate**, not a full connector deployment. It verifies selection and profile-update
behavior under a disclosed event-level detector. It does not verify end-to-end MNMM
sufficiency.

Consequently the experiment does **not** test: extensive missingness, connector delay,
correlated connector failure, forged events, slow adversarial drift, gradual poisoning,
operator fatigue, or malicious mapping updates. Those conditions are named in the threat
model (Table 8) as future evaluation work, and this package does not represent them as
completed tests.

## Limits on external validity

Every organization, event, budget, effectiveness coefficient and output in the experiment is
synthetic, and the same design defined the scenario demands, the dependencies and the
utility function. Higher coverage therefore demonstrates **consistency with the encoded
model**. It cannot establish real SME risk reduction, adoption, usability, cost or
certification readiness. No expert assessment, field deployment, interview or case study is
claimed.

The material-event magnitudes were deliberately separated from the trigger boundary, which
is why coverage responds weakly to the threshold τ. That is a **property of the scenario
design**, not evidence that threshold selection is generally unimportant.

## Standards and regulatory limits

- The crosswalk is **illustrative**. ISO/IEC control text is licensed and is not reproduced;
  identifiers and author-generated summaries must be checked against the editions the
  adopting organization holds.
- A mapping states relevance in a stated context. It is **not** semantic identity and
  **not** a conformity claim.
- Regulatory applicability must be evaluated, not inferred from company size. A protector
  requires jurisdiction-, sector-, product- and contract-specific review. ACP-SME labels a
  requirement mandatory only after an authorized governance owner enters the applicable
  source and scope.
- A draft Statement of Applicability produced by `crosswalk.draft_soa_rows` is input for
  management review. Every row is marked `PENDING MANAGEMENT REVIEW` with
  `conformity_claim: none asserted`. Management remains responsible for the risk-treatment
  decision.

## Privacy

Pseudonymized metadata **must not be described as anonymous**. Tenant-keyed hashes prevent
cross-tenant linkage; they do not make a record anonymous under GDPR.

The prototype requires no external telemetry aggregation. If future research aggregates
results across enterprises, that requires a separate legal basis, a minimum group size,
export review and an explicit privacy mechanism. Local differential privacy is one
candidate; it is **not** a component of this package.
