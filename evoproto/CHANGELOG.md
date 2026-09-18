# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[semantic versioning](https://semver.org/).

## [0.1.0] - 2026-09-18

First public release, accompanying the submission of the article.

### Added

- `evoproto.data`: five-valued provenance tags, the `Provenance` record with its
  reconstruction flag and uncertainty, blake2b `stable_seed()`, completeness
  (Eq. 1) and sampling weight (Eq. 2), content-addressed corpus snapshot hashes,
  and offline-by-default connectors for Open Tree of Life, the Paleobiology
  Database and MorphoBank.
- `evoproto.kg`: the evolutionary–engineering knowledge graph with six node types
  and nine typed edges, schema enforcement at insertion, mutual exclusion of
  `homologousTo` and `convergentWith`, traceability chains (Eq. 4), independent
  origins by union–find over homology edges (Eq. 3), and versioned feedback
  updates of support weights (Section 4.7).
- `evoproto.phylo`: Brownian covariance and simulation, Blomberg's *K* (Eq. 5),
  profile-likelihood Pagel's *λ* (Eq. 6), maximum-likelihood ancestral states,
  Stayton's *C1* (Eq. 7) and its Brownian-null significance test (Eq. A.2).
- `evoproto.retrieval`: analog scoring (Eq. 8) and transfer uncertainty
  (Eqs. 9–10) with curated material and load mismatch tables.
- `evoproto.design`: the parametric EOAT bracket and its analytic evaluator
  (Eqs. 15–19), plus the three samplers that distinguish the arms.
- `evoproto.optimize`: constrained non-dominated sorting (Deb's rule), crowding
  distance, exact two-objective hypervolume (Eq. A.3), design diversity,
  Algorithm 1, and a time-matched heuristic stand-in for the expert arm.
- `evoproto.gate`: the evidence score (Eq. 13) and the decision rule (Eq. 14,
  Algorithm 2) with a missing-evidence report that names the experiment which
  would raise the score.
- `evoproto.experiment`: the three-arm protocol runner and the analysis plan of
  Section 7.6 (Wilcoxon, Holm, Cliff's δ, bootstrap CIs), the metrics of
  Eqs. (20)–(23), the power calculation of Eq. (24), and an environment record
  written with every result.
- `evoproto.figures`: regeneration of Figures 1–8 from code, in vector PDF and
  600 dpi PNG.
- `evoproto.tools.verify_dois`: CrossRef verification of all 63 references,
  comparing the resolved title with the stored one.
- 106 tests, three Colab-ready notebooks, a datasheet, a model card, a
  pre-registration, a reproducibility report, an article-to-code map, an
  Elsevier submission checklist and a Zenodo archive builder.

### Known limitations

- The retrieval language model of Section 4.4 is specified but not bundled.
- Tasks T2 and T3 raise `NotImplementedError` pending the partner's solvers.
- The analytic evaluator is a surrogate; FE verification precedes any build.
- Several constants are this implementation's defaults awaiting confirmation
  against the manuscript; see `docs/paper_mapping.md`.
