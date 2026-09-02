# Cloud-Integration Multicriteria Decision Model (`cimcdm`)

Reference implementation and reproducibility archive for:

> Torstensson, O.; Prokopovych-Tkachenko, D.; Lakhno, V.; Desiatko, A.; Fedotov, S.
> **Multicriteria Model for Integrating Distributed Systems into Cloud Services.**
> *Systems*, 2026 (submitted manuscript).

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/omega2417/bnt/blob/claude/zenodo-publication-project-sedznh/cloud-integration-mcdm/notebooks/Cloud_Integration_MCDM_Colab.ipynb)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22259414.svg)](https://doi.org/10.5281/zenodo.22259414)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

---

## What this is

Migrating distributed information-processing (DIP) systems to the cloud is a
**portfolio decision**, not a sequence of isolated technical upgrades. Business
value, integration cost, operational risk, reliability, technical readiness and
employee acceptance conflict with one another, and their consequences do not
materialize at the same rate.

This package implements a three-objective binary portfolio model in which
benefit accumulation, organizational adaptation and residual risk are **explicit
functions of time**, and it reproduces the complete computational study reported
in the article — including the exact Pareto front, which serves as ground truth
for judging the heuristics.

**Fastest way in:** open the Colab badge above. No installation, no accelerator,
no Drive mount. The full study runs in about ten minutes; a smoke pass in one.

If the badge does not resolve — the development branch name contains a slash,
which some link handlers mangle — open Colab, choose **File -> Open notebook ->
GitHub**, enter `omega2417/bnt`, pick the branch, and select
`cloud-integration-mcdm/notebooks/Cloud_Integration_MCDM_Colab.ipynb`. The
notebook also runs unchanged in a local Jupyter session or from the unpacked
Zenodo archive: its setup cell walks up from the working directory to find the
project, so it does not care where it is started from.

---

## Headline results reproduced

Run `python -m cimcdm exact` to verify the first block in about twenty seconds.

| Claim | Published | This code |
|---|---|---|
| Portfolios enumerated | 262,144 | 262,144 |
| Feasible portfolios | 83,657 (31.91%) | 83,657 (31.91%) |
| Pareto-optimal portfolios | 446 | 446 |
| Exact hypervolume | 0.421542857 | 0.421542897 |
| Knee portfolio | S01, S04, S05, S10, S12, S13, S16, S17, S18 | identical |
| Knee benefit / cost / risk | 0.522919 / 0.416107 / 0.241278 | 0.522919 / 0.416107 / 0.241277 |
| Knee cost / effort | 124 units / 35 system-months | 124 / 35 |
| WSM hypervolume / IGD+ / spacing | 0.417759 / 0.008742 / 0.016338 | identical |
| WSM front size and coverage | 29 solutions, 6.50% | 29 solutions, 6.50% |
| Sensitivity corners (HV) | 0.398392 / 0.429727 | 0.398392 / 0.429727 |
| Knee portfolios across 25 cells | 1 (invariant) | 1 (invariant) |

Residuals of order 1e-7 are expected and unavoidable: Appendix A publishes the
inputs rounded to six decimal places, so the code cannot recover more precision
than the inputs carry.

The evolutionary results are stochastic. Mean hypervolume over 30 matched seeds
lands within about 6e-4 of the published 0.418638 (NSGA-II) and 0.418961
(NSGA-III), and the methods order the same way — NSGA-III attains better
proximity to the exact front, NSGA-II is faster — but the re-implemented
variation pipeline does not reproduce individual runs value for value, does not
reach the article's statistical significance, and recovers a smaller share of
the exact front. See [Reproducibility scope](#reproducibility-scope) for exactly
what does and does not carry over.

---

## The model

Three objectives, all minimized (Eq. 1):

```
min F(x, t) = [ 1 - V(x,t),  C(x),  R(x,t) ],    x in {0,1}^n
```

| Symbol | Meaning |
|---|---|
| `V(x,t)` | normalized portfolio benefit, Eq. (3) |
| `C(x)` | normalized integration cost, Eq. (4) |
| `R(x,t)` | normalized residual risk, Eq. (5) |

Per-system benefit combines four components under weights that sum to one
(Eq. 2 — these weights combine components **of benefit only**; they never
scalarize the three top-level objectives):

```
b_i(t) = q_i * [ 0.35*P_i(t) + 0.25*E_i(t) + 0.25*T_i + 0.15*H_i ]
```

Temporal realization uses bounded monotone response functions (Eqs. 8-10):

```
P_i(t) = P_i0 + dP_i * (1 - exp(-alpha_i * t))     business performance
E_i(t) = E_i0 + dE_i * (1 - exp(-beta_i  * t))     economic benefit
r_i(t) = r_inf + (r_i0 - r_inf) * exp(-rho_i * t)  residual risk
```

Feasibility (Eqs. 6-7): budget, implementation effort, criticality coverage, and
two portfolio-*average* thresholds written in multiplied form —
`sum((q_i - q_min) * x_i) >= 0` — which avoids dividing by the portfolio size,
plus a non-emptiness condition.

**One subtlety worth knowing.** `Vmax` is computed once at the *upper boundary*
of the tested temporal-rate range (`s_alpha = s_beta = 1.5`) and then held fixed
for every cell of the sensitivity grid. Rescaling it per cell would make
objective values incomparable across the grid and would silently invalidate the
sensitivity analysis. `PortfolioModel` enforces this; `tests/test_model.py`
pins it.

---

## Installation

```bash
git clone https://github.com/omega2417/bnt.git
cd bnt/cloud-integration-mcdm
pip install -e .
```

Or from the Zenodo archive:

```bash
unzip cimcdm-1.0.0.zip && cd cloud-integration-mcdm
pip install -r requirements.txt
export PYTHONPATH=src
```

Requires Python 3.10+ with NumPy, SciPy, pandas and Matplotlib. `requirements.txt`
pins the exact versions from Section 2.4 of the article; newer releases give the
same results.

---

## Usage

### Command line

```bash
python -m cimcdm exact                    # exact enumeration + validation  (~20 s)
python -m cimcdm benchmark                # + 30 matched runs and statistics (~5 min)
python -m cimcdm benchmark --seeds 5      # quick pass over the first 5 seeds
python -m cimcdm sensitivity              # 25-cell temporal-rate grid       (~6 min)
python -m cimcdm all -o results           # everything, plus figures and CSVs
```

Every sub-command ends with a validation report and exits non-zero if any check
fails, so it works directly as a CI gate.

### Python

```python
from cimcdm import PortfolioModel, enumerate_exact, load_published_instance

model = PortfolioModel(load_published_instance())
exact = enumerate_exact(model)

print(exact.front_size)          # 446
print(exact.knee.selected)       # ('S01', 'S04', ..., 'S18')
print(exact.hypervolume)         # 0.4215428973421387
```

Comparing the algorithms:

```python
from cimcdm import load_published_instance, run_benchmark

result = run_benchmark(load_published_instance())
print(result.summary_table())    # Table 5
print(result.tests_table())      # Table 6
```

Studying a different scenario — every setting is a plain dataclass field:

```python
from cimcdm import PortfolioModel, ScenarioConfig, enumerate_exact, load_published_instance

tight = ScenarioConfig(budget_fraction=0.40, min_mean_reliability=0.92)
exact = enumerate_exact(PortfolioModel(load_published_instance(), tight))
print(exact.n_feasible, exact.front_size)
```

---

## Repository layout

```
cloud-integration-mcdm/
├── src/cimcdm/
│   ├── config.py        scenario, algorithm and sensitivity settings (Tables 2-3)
│   ├── instance.py      the 18-system benchmark; published values and a generator
│   ├── model.py         objectives, constraints, knee rule (Eqs. 1-11)
│   ├── pareto.py        dominance filtering and the persistent archive
│   ├── metrics.py       hypervolume, IGD+, spacing, exact-front coverage
│   ├── exact.py         complete binary enumeration -> ground-truth front
│   ├── operators.py     initialization, crossover, mutation, repair (shared)
│   ├── algorithms.py    NSGA-II, NSGA-III-type survival, weighted sum
│   ├── statistics.py    Wilcoxon (Pratt) + Holm, rank-biserial effect sizes
│   ├── sensitivity.py   25-cell temporal-rate grid
│   ├── experiment.py    end-to-end driver producing Tables 4-6
│   ├── figures.py       Figures 2-5 and the response-curve supplement
│   ├── validation.py    self-verification against the published numbers
│   └── cli.py           `python -m cimcdm`
├── data/                Appendices A, B and C as machine-readable CSV
├── notebooks/           the Colab notebook
├── tests/               40 tests: unit, reproduction and statistics
├── scripts/             one-shot reproduction and archive packaging
└── results/             generated output (not tracked)
```

---

## Data files

| File | Contents |
|---|---|
| `appendix_A1_benefit_parameters.csv` | Per-system `P0`, `dP`, `alpha`, `E0`, `dE`, `beta`, cost |
| `appendix_A2_system_parameters.csv` | Technical, human, reliability, risk, `rho`, effort, criticality |
| `appendix_B1_run_quality.csv` | The article's own 30 run-level HV, IGD+, spacing values |
| `appendix_B2_run_coverage_time.csv` | The article's own 30 run-level coverage, size, CPU times |
| `appendix_C1_convergence.csv` | Mean hypervolume and 95% CI at the six checkpoints |

The A-tables are inputs the code consumes. The B and C tables are the article's
published *outputs*, kept so that a new run can be compared against them
directly — the notebook does exactly this in Section 9.

---

## Reproducibility scope

Being precise about what reproduces exactly and what does not:

**Deterministic and exact.** Everything driven by enumeration: the feasible
count, the Pareto front, the exact hypervolume, the knee portfolio, the whole
sensitivity grid, and all four weighted-sum indicators. These match the
published values to within the 1e-7 rounding floor of the Appendix A inputs, on
any platform.

The weighted-sum row is worth dwelling on, because it pinned down a convention
the article does not state. Its front is deterministic and reproduced exactly
(the same 29 portfolios), so any disagreement had to come from an indicator
definition rather than from the search. Schott's original spacing uses the
**Manhattan** nearest-neighbour distance and gives 0.022544 on that front; the
**Euclidean** variant gives exactly the published 0.016338. `metrics.spacing`
therefore uses the Euclidean form. The two are not interchangeable when
comparing against the published tables.

**Stochastic, matching in distribution.** The NSGA-II and NSGA-III results. The
article's implementation is not public, so this is an independent
re-implementation of the described protocol — same population, generations,
operators, probabilities, reference directions and seeds, but not the same
sequence of random draws.

Mean hypervolume, IGD+ and spacing land close to the published values, and the
point estimates order the two methods the same way the article does: NSGA-III
attains lower IGD+ (0.00220 vs 0.00250) and higher hypervolume, NSGA-II is
faster (3.79 s vs 3.95 s). Two things do not carry over, and both are stated
here rather than smoothed away.

*Significance.* The article reports IGD+, coverage and CPU time as significant
after Holm correction. In this re-implementation none of the five metrics
reaches significance over 30 seeds: the differences point the same way but are
smaller relative to their spread. The CPU-time gap in particular is 3.9% here
against the article's 9.7%, which is unsurprising — relative runtime depends on
how each survival operator is coded, not on the model.

*Exact-front coverage.* This implementation recovers roughly 43% of the 446
exact objective vectors against the article's ~60%, even though its mean
hypervolume is marginally *higher*. Coverage counts exact objective vectors
matched to ten decimal places, so it is far more sensitive to which specific
portfolios a search happens to land on than to how good the resulting front is
overall — two archives of comparable quality can differ sharply on it. The
repair operator, which governs exactly this, is described in the article only as
"feasible initialization and repair", so it cannot be reproduced from the text.

Neither gap was tuned away. Fitting a search until it hits a published output
figure is precisely what a reproducibility archive should not do.

**Sampling protocol only.** `generate_instance()` reproduces the *ranges* and
determinism of the scenario generator (seed 20260902), not the original draw
order. It returns a valid sibling instance, never a copy of Appendix A. Use
`load_published_instance()` — the default everywhere — to reproduce the article.

**Labelling.** As the article states, the reference-direction method is called
"NSGA-III" for brevity but is not a full reproduction of every normalization
step of the canonical algorithm.

---

## Limitations

These carry over from the study and constrain what any result here can support:

- **The scenario is synthetic.** Exact validation demonstrates internal
  computational correctness for one instance. It says nothing about
  effectiveness in a deployed organization.
- **Decisions are binary.** Partial migration, hybrid-cloud allocation,
  sequencing, rollback, vendor switching and multi-cloud placement are outside
  the decision space.
- **Contributions are additive.** Interdependencies, shared services,
  incompatibilities and correlated failures would change the Pareto set.
- **Temporal rates are not calibrated.** `alpha`, `beta` and `rho` are assumed,
  and the 25-cell grid is a bounded sensitivity exercise, not probabilistic
  uncertainty quantification.
- **Two constraints bind averages, not systems.** The reliability and
  technical-readiness thresholds constrain portfolio *means*; they do not
  guarantee a threshold for each selected system.
- **Algorithm evidence is narrow.** One 18-system instance, one
  parameterization, one matched budget, no parameter tuning. Do not generalize
  it to all cloud-integration problems.
- **The knee rule is one preference model.** Stakeholder elicitation may
  legitimately select a different nondominated portfolio.

---

## Testing

```bash
pip install -e ".[dev]"
pytest                      # 40 tests, about a minute
```

The suite covers the model algebra and feasibility logic, closed-form checks of
each quality indicator, the Holm and rank-biserial machinery, and reproduction
tests that assert the published numbers come back out of the code.

---

## Citation

Cite both the software and the article. The archived release is deposited at
Zenodo under **[10.5281/zenodo.22259414](https://doi.org/10.5281/zenodo.22259414)**. Machine-readable metadata is in
[`CITATION.cff`](CITATION.cff) and [`.zenodo.json`](.zenodo.json).

```bibtex
@article{torstensson2026multicriteria,
  title   = {Multicriteria Model for Integrating Distributed Systems into Cloud Services},
  author  = {Torstensson, Olga and Prokopovych-Tkachenko, Dmytro and
             Lakhno, Valerii and Desiatko, Alona and Fedotov, Serhii},
  journal = {Systems},
  year    = {2026},
  note    = {Submitted manuscript}
}

@software{cimcdm2026,
  title     = {cimcdm: Reference Implementation and Reproducibility Archive for
               "Multicriteria Model for Integrating Distributed Systems into Cloud Services"},
  author    = {Torstensson, Olga and Prokopovych-Tkachenko, Dmytro and
               Lakhno, Valerii and Desiatko, Alona and Fedotov, Serhii},
  year      = {2026},
  version   = {1.0.0},
  publisher = {Zenodo},
  doi       = {10.5281/zenodo.22259414},
  url       = {https://doi.org/10.5281/zenodo.22259414},
  license   = {MIT}
}
```

## License

Source code: [MIT](LICENSE). Data files transcribed from the article's
appendices: CC BY 4.0, consistent with the manuscript's intended license.
