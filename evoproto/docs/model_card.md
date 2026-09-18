# Model card: the evoproto decision pipeline

Following Mitchell et al., *Model Cards for Model Reporting* (FAT* 2019,
https://doi.org/10.1145/3287560.3287596).

## Model details

`evoproto` v0.1.0 is not a learned model; it is a decision pipeline with
explicit, pre-registered parameters. Three components produce numbers that
reach the engineer:

1. **Analog scoring** (Eq. 8) — a weighted sum of functional match, mechanism
   evidence and the log of the sampling-weighted number of independent origins,
   penalised by transfer uncertainty. Weights `w_F = 0.40`, `w_M = 0.30`,
   `w_C = 0.15`, `w_U = 0.40`.
2. **Constrained multi-objective search** (Algorithm 1) — NSGA-II-style
   selection with Deb's constraint domination over an analytic evaluator.
3. **The evidence gate** (Eqs. 13–14, Algorithm 2) — `RECOMMEND`, `ABSTAIN` or
   `REJECT`, with thresholds `τ_E = τ_U = 0.5`.

A deployment adds two learned components the package does not ship: a
multimodal encoder for the first retrieval stage and a retrieval-augmented LLM
for the functional-correspondence statements. The package ships the *filter*
that constrains the latter: any statement citing material outside the retrieved
subgraph is discarded (`retrieval.filter_grounded_statements`). Whoever supplies
those components records their identifiers and prompts in the pre-registration.

## Intended use

Supporting an engineer in transferring a biological mechanism into a parametric
design, with the evidence for that transfer made explicit and auditable.
The intended user is a design engineer working inside an existing change-control
process. The output is a recommendation with a traceability chain, or an
abstention with a missing-evidence report.

## Out-of-scope use

- Any autonomous release of a design. `RECOMMEND` is a recommendation awaiting
  engineer approval; the engineer is the only actor who can release a design.
- Load-bearing or safety-critical parts without the finite-element verification
  stage. The analytic evaluator shipped here is a surrogate that ignores shear
  deformation, stress concentration, LPBF anisotropy and lattice discreteness.
- Any claim that a recommended design is optimal, or that natural selection
  found an optimum. Convergence is evidence of repeated adequacy.
- Any biological claim. The shipped graph is a synthetic illustration.

## Factors and metrics

Search quality is reported as the feasible-solution rate, the normalised
hypervolume, design diversity and iterations to specification (Eqs. 20–23).
Decision quality is reported as the abstention rate — all prototypes are
reported, recommended, abstained and rejected alike, so the abstention rate is
itself a measured quantity.

Evaluation follows the pre-registered protocol of Section 7: three arms, three
task families, ten seeded replicates, paired two-sided Wilcoxon tests with Holm
correction at family-wise 0.05, Cliff's δ and bootstrap confidence intervals.
Ten replicates detect large effects only (Eq. 24 gives n = 9 for d = 1.0 and
n = 13 for d = 0.8).

## Training data

None: no component shipped here is trained. The corpus a deployment builds is
described in `datasheet.md`. Where an encoder or an LLM is added, its own
training data becomes a factor the deployment must document, including the
possibility that it has memorised the biological literature it is meant to
retrieve.

## Ethical considerations and caveats

The framework's principal failure mode is a confident recommendation resting on
a mechanism that does not survive the transfer — because the engineering
material lies outside the regime in which the biological mechanism operates, or
because the selective regime that produced the trait is not the one the engineer
cares about (an exaptation). The transfer-uncertainty term and the abstention
rule exist to make such cases visible; they do not eliminate them.

The demonstration verification step is a surrogate stand-in, explicitly tagged
`PROXY`. Treating it as a substitute for finite-element verification would
invert the framework's central claim, which is that biological evidence *never*
replaces physical verification.
