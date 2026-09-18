# Model card: the evoproto retrieval-and-gating model

Following *Model Cards for Model Reporting* (Mitchell et al., 2019) [56], as
required by Section 3.1. The "model" here is the composite scoring and decision
machinery of Sections 4.4 and 4.6, not a trained network: it has no learned
parameters in this release, and every weight is a pre-registered constant.

## Model details

- **Developed by** the authors of the accompanying article; software by
  D. Prokopovych-Tkachenko (CRediT: Software).
- **Version** 0.1.0, released 2026-09-18, MIT licensed.
- **Type** rule-based scoring over a typed knowledge graph, plus an
  evolutionary search. Components:
  - analog score `S` (Eq. 8) over functional match `F`, mechanism evidence `M`,
    the log of the sampling-weighted number of independent origins, and a
    transfer-uncertainty penalty `U` (Eqs. 9–10);
  - evidence score `E` (Eq. 13) over a four-edge traceability chain, with a
    reconstruction penalty and a convergence bonus;
  - decision rule (Eq. 14): RECOMMEND / ABSTAIN / REJECT.
- **Parameters** (all fixed before the experiment, all reported):
  `w_F = 0.40, w_M = 0.30, w_N = 0.20, w_U = 0.30`;
  `U` component weights `0.4 / 0.4 / 0.2`;
  chain weights `(0.20, 0.25, 0.35, 0.20)`, reconstruction penalty `0.20`,
  convergence bonus `0.15`; thresholds `tau_E = 0.60`, `tau_U = 0.50`.
  See `docs/paper_mapping.md` for which of these the manuscript pins and which
  are this implementation's defaults awaiting confirmation.

## Intended use

- **Primary use.** Ranking candidate biological analogs for an engineering
  functional requirement, and deciding whether the biological justification is
  strong enough to put in front of an engineer.
- **Primary users.** Design engineers and engineering-informatics researchers
  working with a curated, provenance-complete corpus.
- **Out of scope.** Any use where the output is treated as a release decision.
  The engineer is the only actor who can release a design; the model's strongest
  output is a recommendation with a traceability chain, and its weakest is an
  abstention with a missing-evidence report.

## Factors

Performance depends on: the completeness of the chain (a missing `explainedBy`
measurement is the usual weak link); whether ancestral reconstructions are
involved (`r = 1` costs 20 % of the evidence score); the distance between the
biological and engineering regimes, which enters as `U`; and the sampling
intensity of the clades involved, which enters through Eq. (2).

## Metrics

The model is not evaluated by accuracy — there is no ground-truth label for "is
this a good analog". It is evaluated indirectly through the protocol of Section
7 (FSR, HV, D, ITS on a matched search budget) and directly by its abstention
rate, which the protocol requires to be reported as a measured quantity
(Section 7.8): all prototypes are reported, recommended, abstained and rejected.

## Evaluation data

None yet. The release contains a synthetic dry run only (Section 7.7, `evoproto
dryrun`), whose purpose is to show that the pipeline and every branch of the
statistical plan execute — not to support any claim about H1–H3.

## Ethical considerations and caveats

- **The model can be confidently wrong.** A high `E` with a low `U` means the
  chain is well supported and the regimes are close; it does not mean the design
  is safe. Numerical verification is a precondition of RECOMMEND, and physical
  testing remains mandatory.
- **Retrieval is hallucination-prone without its guard.** The RAG stage must be
  restricted to the retrieved subgraph and its DOI-backed excerpts; statements
  citing anything outside the retrieved set are discarded (Section 4.4). This
  guard is a protocol requirement, and the language-model stage itself is
  **not** bundled with this release.
- **Selection is not optimization.** A convergent mechanism is evidence of
  repeated adequacy, not of optimality [16, 17, 37].
- **Coarse penalties.** The reconstruction penalty and the material/load
  mismatch tables are deliberately coarse and hand-curated; Section 9 proposes
  learning them from MEASURED records once enough exist.
