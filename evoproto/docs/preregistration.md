# Pre-registration (Section 7.8)

Everything in this file is frozen **before** any physical build, archived with
a persistent identifier, and cited in the article. Deviations are reported as
deviations. This file is the registry; the values it names live in code so that
they cannot drift.

## 1. Hypotheses and falsifiable predictions

Working hypothesis: evolutionary context increases the diversity of physically
realizable solutions compared with static biological analogies alone.

| ID | Prediction | Null |
|---|---|---|
| H1 | Under a matched search budget, arm C attains a higher feasible-solution rate than arms B and A | no difference |
| H2 | Arm C attains a higher normalized hypervolume than arms A and B | no difference |
| H3 | Arm C attains a higher design diversity on the Pareto set than arms A and B | no difference |

Predictions are directional; tests are two-sided, so evidence *against* the
framework is reported with the same weight.

## 2. Arms

| Arm | Description | Budget |
|---|---|---|
| A | expert biomimetic search (two engineers, catalog resources, standard CAD) | matched wall-clock time |
| B | generative design without evolutionary data (uniform prior on `D`) | matched evaluations and seeds |
| C | proposed framework (analog-shaped prior `p_c`, trade-off constraints) | matched evaluations and seeds |

Arms B and C differ **only** in the prior and the constraints derived from
evolutionary data. The evaluator, the budget and the seed derivation are shared,
so any difference is attributable to that data.

## 3. Frozen quantities

| Quantity | Value | Where it lives |
|---|---|---|
| Analog score weights | `w_F = 0.40, w_M = 0.30, w_N = 0.20, w_U = 0.30` | `retrieval.ScoreWeights` |
| `U` component weights | scale 0.4, material 0.4, load 0.2 | `retrieval.UncertaintyWeights` |
| Scale term | `u_scale = min(1, |log10 r| / 2)` | `retrieval.scale_mismatch` |
| Chain weights | `(0.20, 0.25, 0.35, 0.20)` | `gate.EvidenceWeights` |
| Reconstruction penalty / convergence bonus | `0.20` / `0.15` | `gate.EvidenceWeights` |
| Thresholds | `tau_E = 0.60`, `tau_U = 0.50` | `gate.Thresholds` |
| Convergence significance level | `alpha = 0.05` (Brownian null, Eq. A.2) | `phylo.c1_significance` |
| Sampling reference fraction | `f_ref = 0.1` | `data.sampling_weight` |
| Completeness threshold `c_min` | **NEEDS INPUT** | `data.admits_record` |
| Seed derivation string | `blake2b(package_version | task_id | arm | replicate)`, 32-bit | `data.stable_seed` |
| Corpus snapshot hash | **NEEDS INPUT** (recorded when the snapshot is cut) | `data.corpus_snapshot_hash` |
| Retrieval LLM and prompts | **NEEDS INPUT** (model identifier, version, exact prompts) | not bundled in this release |
| Population / generations / replicates | 40 / 25 / 10 | `experiment.run_protocol` defaults |

## 4. Tasks

- **T1** EOAT bracket, LPBF AlSi10Mg — primary task, fully specified evaluator
  (`design.evaluate_population`).
- **T2** heat-exchanger fin (CFD evaluator) — **NEEDS INPUT**.
- **T3** compliant gripper finger (contact-mechanics evaluator) — **NEEDS INPUT**.

## 5. Validation design

1. **Phylogenetic block split.** Arm C's graph is built from a training clade
   set; analogs whose traits appear in held-out clades are unavailable during
   search and are used only to test generalization. Splitting by clade, not by
   taxon, prevents leakage through relatives that share traits by descent.
2. **Ablation of arm C**: (a) `convergentWith` edges removed, (b) reconstructed
   states dropped, (c) `tradesOffWith` constraints removed, (d) evidence gate
   disabled. Each isolates one claimed source of value.
3. **Numerical verification.** Top-5 designs per arm per task re-evaluated by FE
   (linear elastic and linear buckling for T1), with manufacturability checks
   (overhang angle, `t ≥ t_min`, support-removal access).
4. **Physical test.** Verified top-3 designs per arm for T1 (nine brackets),
   printed in AlSi10Mg on the same machine and build-plate orientation; mass on a
   laboratory balance, cantilever stiffness in a displacement-controlled
   quasi-static test, three loading cycles per part, the last used for stiffness.

## 6. Analysis plan

- Cells paired by `(task, replicate seed)`.
- Two-sided Wilcoxon signed-rank test [60] on the ten paired differences, per
  metric and per contrast (C vs B, C vs A).
- Holm step-down correction [61] over the eight p-values per task, family-wise
  `alpha = 0.05`.
- Effect sizes: Cliff's delta [62] with the conventional labels, and median
  paired differences with 95 % bootstrap CIs [63] (`B = 2000`).
- **No result is called significant without its Holm-adjusted p-value and its
  effect size.** Power: ten replicates detect large effects only (Eq. 24;
  `experiment.required_pairs`), and the protocol allows extension to `n = 15` if
  interim variance from arm B — which is independent of the hypothesis — is
  larger than assumed.

## 7. Reporting

All prototypes are reported: recommended, abstained and rejected. The abstention
rate is itself a measured quantity of the framework. Every number in the paper
carries its provenance tag (MEASURED, MODELED, PROXY, EXTERNAL, SYNTHETIC).

## 8. What would falsify the claim

If arm C does not exceed arm B on FSR, HV and D under the matched budget, H1–H3
are not supported and the paper says so. The ablations then identify whether any
single component (convergence edges, reconstructions, trade-off constraints, the
gate) carried value on its own.
