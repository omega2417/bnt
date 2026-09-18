# Pre-registration template (Section 7.8)

Before any physical build, the items below are frozen and archived with a
persistent identifier. Deviations are reported as deviations.

Fill in every `[[NEEDS INPUT]]`; the shipped defaults are the values
`evoproto info` prints, and any change to them after this document is archived
is a deviation, not a setting.

## 1. Hypotheses and predictions

- **H1 (feasibility)** — arm C attains a higher feasible-solution rate than
  arms B and A under a matched search budget. Null: no difference.
- **H2 (front quality)** — arm C attains a higher normalised hypervolume.
  Null: no difference.
- **H3 (diversity)** — arm C attains a higher design diversity on the Pareto
  set. Null: no difference.

Predictions are directional; tests are two-sided, so evidence against the
framework is reported with the same weight.

## 2. Corpus

| item | value |
|---|---|
| corpus snapshot hash | `[[NEEDS INPUT]]` |
| OTOL synthetic-tree version | `[[NEEDS INPUT]]` |
| MorphoBank project and matrix ids | `[[NEEDS INPUT]]` |
| PBDB retrieval date and age model | `[[NEEDS INPUT]]` |
| completeness threshold `c_min` (Eq. 1) | `[[NEEDS INPUT]]` |
| convergence significance level `α` (Eq. A.2) | 0.05 |
| held-out clades for the block split | `[[NEEDS INPUT]]` |

## 3. Frozen parameters

| symbol | value | equation |
|---|---|---|
| `w_F, w_M, w_C, w_U` | 0.40, 0.30, 0.15, 0.40 | (8) |
| `α, β, γ` | 0.35, 0.35, 0.30 | (9) |
| `w_1..w_4` | 0.25, 0.25, 0.25, 0.25 | (13) |
| `κ` | 0.15 | (13) |
| `ρ_rec` | 0.7 | (13) |
| `τ_E` | 0.5 `[[confirm]]` | (14) |
| `τ_U` | 0.5 | (14) |
| arm-C prior centre / spread | (0.45, 0.80, 0.25, 0.20) / (0.20, 0.15, 0.15, 0.12) | §4.5 |
| population size, generations | 40, 25 `[[confirm for the FE evaluator]]` | Algorithm 1 |
| replicates per cell | 10 (extendable to 20 per §7.6) | §7.5 |
| seed derivation string | `evoproto\|version\|task\|arm\|replicate`, blake2b | §5 |

## 4. Retrieval components

| item | value |
|---|---|
| multimodal encoder and version | `[[NEEDS INPUT]]` |
| retrieval LLM identifier and version | `[[NEEDS INPUT]]` |
| prompts issued to the retrieval LLM | `[[NEEDS INPUT — archive verbatim]]` |
| admissible citation set per query | the retrieved subgraph and its DOI-backed excerpts |

## 5. Specification and materials

Replace every assumption A1–A7 of Table 6 with the partner's certified data:
cantilever length, moving payload, peak acceleration from the robot motion
profile, allowable tip deflection, safety factor, mass cap, and the certified
AlSi10Mg datasheet values. Record the machine, build-plate orientation, powder
lot and post-processing.

## 6. Analysis plan

Cells are paired by `(task, replicate seed)`. For each metric and each contrast
(C vs B, C vs A) a two-sided Wilcoxon signed-rank test is applied to the ten
paired differences; the eight p-values per task form one Holm family at
family-wise 0.05. Effect sizes are Cliff's δ with the conventional
interpretation, plus median paired differences with 95 % bootstrap confidence
intervals (B = 2000). No result is described as significant without its
Holm-adjusted p-value and its effect size.

## 7. Verification and physical test

Top-`k` (k = 3) designs per arm per task are re-evaluated by FE (linear elastic
and linear buckling for T1) and checked for manufacturability (overhang angle,
`t ≥ t_min`, support-removal access). The verified top-3 per arm for T1 are
printed in AlSi10Mg on one machine and orientation; mass is measured on a
laboratory balance and cantilever stiffness in a displacement-controlled
quasi-static test with the load applied at `L`, three cycles per part, the last
used for stiffness.

## 8. Reporting commitments

- All prototypes are reported — recommended, abstained and rejected — so the
  abstention rate is a measured quantity.
- Every number is tagged `MEASURED`, `MODELED`, `PROXY`, `EXTERNAL` or
  `SYNTHETIC`.
- The corpus snapshot hash under which each recommendation was generated is
  reported with it.
- Ablations (a) convergence edges removed, (b) reconstructed states removed,
  (c) trade-off constraints removed, (d) evidence gate disabled are reported
  whether or not they favour the framework.
