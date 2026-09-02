# Reproduction map

Where each numbered result in the article comes from in this archive. Every path
is relative to `cloud-integration-mcdm/`.

## Equations

| Article | Implementation |
|---|---|
| Eq. 1 — three-objective minimization | `PortfolioModel.objectives` (`src/cimcdm/model.py`) |
| Eq. 2 — per-system benefit `b_i(t)` | `PortfolioModel._benefit_vector` |
| Eq. 3-5 — normalized benefit, cost, risk | `PortfolioModel.objectives` |
| Eq. 6-7 — feasible set | `PortfolioModel.is_feasible`, `.constraint_violation` |
| Eq. 8-9 — `P_i(t)`, `E_i(t)` | `PortfolioModel._benefit_vector` |
| Eq. 10 — `r_i(t)` | `PortfolioModel._risk_vector` |
| Eq. 11 — normalized-distance knee | `PortfolioModel.knee` |

The two portfolio-average constraints of Eq. 7 are stored pre-centred as
`reliability_slack` and `technical_slack`, so feasibility is a matrix product
against zero rather than a division by the portfolio size.

## Tables

| Table | Content | Produced by |
|---|---|---|
| 2 | Baseline scenario and feasibility settings | `ScenarioConfig` (`src/cimcdm/config.py`); verified by `validate_scenario` |
| 3 | Algorithm and replication settings | `AlgorithmConfig` |
| 4 | Convergence checkpoints | `BenchmarkResult.convergence_table()` |
| 5 | Quality and runtime | `BenchmarkResult.summary_table()` |
| 6 | Paired Wilcoxon tests, Holm-corrected | `BenchmarkResult.tests_table()` |
| 7 | Selected exact sensitivity outcomes | `corner_summary()` (`src/cimcdm/sensitivity.py`) |
| A1, A2 | Synthetic benchmark inputs | `data/appendix_A1_*.csv`, `data/appendix_A2_*.csv` |
| B1, B2 | Run-level algorithm results | `data/appendix_B1_*.csv`, `data/appendix_B2_*.csv` (the article's own outputs, for comparison) |
| C1 | Aggregate plot data for Figure 2 | `data/appendix_C1_convergence.csv` |

## Figures

| Figure | Produced by |
|---|---|
| 2 — archive hypervolume by generation | `figures.figure_convergence` |
| 3 — metric distributions across runs | `figures.figure_metric_distributions` |
| 4 — pairwise objective projections | `figures.figure_front_projections` |
| 5 — sensitivity to temporal-rate multipliers | `figures.figure_sensitivity` |
| supplementary — response curves (Eqs. 8-10) | `figures.figure_response_curves` |

Figure 1 of the article is a conceptual workflow diagram with no computed
content, so it has no counterpart here.

## Numbered claims in the text

| Claim | Section | Check |
|---|---|---|
| 262,144 portfolios, 83,657 feasible (31.91%) | 3.1 | `validate_exact` |
| 446 Pareto-optimal portfolios | 3.1 | `validate_exact` |
| Exact hypervolume 0.421543 | 3.1 | `validate_exact` |
| NSGA-II / NSGA-III recover 99.31% / 99.39% of exact HV | 3.2 | `BenchmarkResult.recovery_percentages()` |
| WSM recovers 99.10% of HV but only 6.50% of the front | 3.2 | `validate_algorithms` |
| Corner-to-corner HV +7.87%, knee benefit +8.04% | 3.3 | notebook §8; `sensitivity_grid` |
| Knee composition invariant across 25 cells | 3.3 | `knee_is_invariant`, `validate_sensitivity` |
| Knee: 124 cost units, 35 system-months, coverage 5.954293, mean reliability 0.939143, mean technical 0.745268 | 3.3 | `validate_exact` |

## How to run each piece

```bash
python -m cimcdm exact          # Table 2 bounds, Section 3.1, knee portfolio
python -m cimcdm benchmark      # Tables 4, 5, 6
python -m cimcdm sensitivity    # Table 7
python -m cimcdm all -o results # everything, plus Figures 2-5 as PNG
pytest                          # 40 tests, including reproduction assertions
```

Or open `notebooks/Cloud_Integration_MCDM_Colab.ipynb` in Colab, which walks the
same ground with narrative and inline plots.

## What "reproduced" means here

Two different standards apply, and it matters which one a given number falls
under.

**Deterministic.** Enumeration-driven results are exact functions of the
Appendix A inputs. They reproduce on any platform, to within the 1e-7 floor
imposed by publishing those inputs rounded to six decimals. If one of these
fails, something is genuinely wrong.

**Stochastic.** The NSGA-II and NSGA-III results depend on a random stream. The
original implementation is not public, so this archive re-implements the
protocol described in Table 3 rather than the original code. Matched seeds
therefore do not reproduce the article's individual runs; what agrees is the
distribution of each metric and the ordering of the two methods.
`validate_algorithms` uses a correspondingly loose tolerance and should not be
tightened to force a match.

Two differences are known and documented in the README rather than tuned away:
this implementation reaches no statistically significant metric difference over
30 seeds (the article reports three), and it recovers ~43% exact-front coverage
against the published ~60%.

## A convention the article does not state

Spacing is defined in the article only by name. Its weighted-sum front is
deterministic and is reproduced here exactly — the same 29 portfolios, the same
hypervolume, IGD+ and coverage — so the front itself could be ruled out as the
source of any disagreement, leaving the indicator definition. On that front:

| Spacing variant | Value |
|---|---|
| Manhattan nearest-neighbour distance (Schott's original) | 0.022544 |
| **Euclidean nearest-neighbour distance** | **0.016338** |
| Published | 0.016338 |

`metrics.spacing` therefore uses the Euclidean form. Anyone comparing spacing
numbers against the published tables needs the same convention; the two differ
by roughly 40% on this front.
