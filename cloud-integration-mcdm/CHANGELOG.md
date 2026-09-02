# Changelog

## 1.0.0 - 2026-09-02

First public release, accompanying the submission of *Multicriteria Model for
Integrating Distributed Systems into Cloud Services*.

### Included

- `cimcdm` package implementing the three-objective, time-aware portfolio model
  of Equations (1)-(11).
- Exact binary enumeration of all 262,144 portfolios, yielding the ground-truth
  Pareto front used to score every heuristic.
- NSGA-II, a reference-direction (NSGA-III-type) variant, and a 231-weight
  weighted-sum baseline, sharing one variation and repair pipeline so that only
  the survival step differs between the two evolutionary methods.
- Hypervolume, IGD+, spacing and exact-front coverage indicators.
- Paired Wilcoxon signed-rank tests with Pratt zero handling, Holm correction
  and rank-biserial effect sizes.
- 25-cell temporal-rate sensitivity analysis with exact enumeration per cell.
- A self-verifying validation module that re-derives the published numbers and
  reports pass or fail per claim.
- Google Colab notebook covering the whole study end to end.
- Command-line interface (`python -m cimcdm`) and 40 tests.
- Appendices A, B and C transcribed as machine-readable CSV.

### Reproduction status

Exact, to the 1e-7 rounding floor of the published inputs: feasible count
(83,657), front size (446), hypervolume (0.421543), knee portfolio, the whole
sensitivity grid, and the weighted-sum baseline (0.417759, 29 solutions, 6.50%
coverage).

Matching in distribution, not run for run: the NSGA-II and NSGA-III results.
The original implementation is not public, so these are an independent
re-implementation of the described protocol. Mean hypervolume, IGD+ and spacing
land close to the published values and order the two methods the same way, but
this implementation does not reach the article's statistical significance on any
metric and recovers ~43% exact-front coverage against the published ~60%. Both
gaps are documented in the README rather than tuned away.

While building this archive, one convention the article leaves unstated was
recovered from its own deterministic output: spacing is computed with Euclidean
nearest-neighbour distances, not the Manhattan distances of Schott's original
formulation. Only the Euclidean form reproduces the published WSM spacing of
0.016338 on the exactly reproduced 29-point weighted-sum front.
