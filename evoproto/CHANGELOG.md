# Changelog

All notable changes to `evoproto` are recorded here.
The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the project uses [semantic versioning](https://semver.org/).

## [0.1.0] - 2026-09-18

First release, accompanying the submission of the article.

### Added
- `evoproto.data`: the provenance record with its five tags, blake2b seed
  derivation, the completeness and sampling-weight controls of Eqs. (1)-(2),
  content-addressed corpus snapshots, and offline-by-default connectors for
  Open Tree of Life v3, PBDB v1.2 and MorphoBank.
- `evoproto.kg`: the EE-KG with schema enforcement, mutually exclusive homology
  and convergence edges, independent origins by union-find (Eq. 3), traceability
  chains (Eq. 4), phylogenetic block splitting and the ablation views.
- `evoproto.phylo`: Brownian-motion simulation, the variance-covariance matrix,
  Blomberg's K (Eq. 5), profile-likelihood Pagel's lambda (Eq. 6), two-pass
  maximum-likelihood ancestral states, Stayton's C1 (Eq. 7) and its
  simulation p-value (Eq. A.2).
- `evoproto.retrieval`: transfer uncertainty (Eqs. 9-10), the analog score
  (Eq. 8) and the grounding filter that discards statements citing material
  outside the retrieved subgraph.
- `evoproto.design`: the parametric EOAT bracket and its analytic evaluator
  (Eqs. 15-19) with the three arm priors.
- `evoproto.optimize`: non-dominated sorting with Deb's constraint domination,
  crowding distance, exact two-objective hypervolume (Eq. A.3), design
  diversity (Eq. 22) and the search loop of Algorithm 1.
- `evoproto.gate`: the evidence score (Eq. 13), the decision rule (Eq. 14) and
  the missing-evidence report of Algorithm 2.
- `evoproto.experiment`: the arms x tasks x replicates runner, the Wilcoxon
  signed-rank test, Holm correction, Cliff's delta, bootstrap confidence
  intervals, the sample-size formula (Eq. 24), the dry run and the ablations.
- `evoproto.casestudy`: the EOAT bracket case study end to end.
- `evoproto.figures`: regeneration of Figs. 1-8 from code.
- `evoproto.tools.verify_dois`: CrossRef check of the reference list.
- `notebooks/evoproto_walkthrough.ipynb`: a Colab-ready walkthrough of the whole
  framework with 17 generated plots, covering every section of the paper, plus
  two observations it surfaces about the specification (the sampling-weighted
  convergence bonus contributes ~1 % of the evidence score, and uniform edge
  weights make a single unsupported edge unable to trigger abstention).
- Command-line interface `evoproto` and a test suite covering seeding, schema
  enforcement, chain extraction, K / lambda / C1, Pareto and hypervolume, the
  gate logic, a protocol smoke test and the shipped notebook.
