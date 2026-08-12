# Delayed Fractional-Order Graph Dynamics for Integrated Modular Avionics
### Simulation and Reproducibility Model

Reproducibility package for the manuscript

> **Delayed Fractional-Order Graph Dynamics for Cascade Escalation and
> Reconfiguration Failure in Integrated Modular Avionics**
> (Korchenko, Torstensson, Kovalenko, Prokopovych-Tkachenko, Poplavskyi, Volkov).

This repository contains the complete Python/NumPy source code, the synthetic
22-node IMA configuration, all parameter files, and the scripts required to
reproduce the numerical scenarios and **Figures 1–9** of the article with a
single command.

> ⚠️ **Scientific scope.** This is a **synthetic, mechanism-oriented research
> model**. All numerical parameters are *synthetic / mechanism-oriented values*.
> They are **not** derived from any real Airbus, Boeing, or certified IMA
> platform, and are **not** validated against real flight telemetry. The model
> is **not** certification software and must not be used to control real
> avionics.

---

## 1. The mathematical model in brief

The IMA architecture is a weighted directed graph of **Core Processing Modules
(CPM)**, **AFDX/TSN switches (SW)** and **Remote Data Concentrators (RDC)**.
Each node *i* carries two states: a functional degradation level
`x_i(t) ∈ [0,1]` and a normalized queue backlog `q_i(t) ≥ 0`. The dynamics are a
`2n`-dimensional system of **delayed Caputo fractional differential equations**
(Eqs. 3–6), with two independent orders — `α` (degradation) and `β` (backlog) —
coupling four escalation mechanisms:

| | Mechanism | Term |
|----|-----------------------------------------------|-------------------------------|
| M1 | network propagation of degradation            | `Σ_j β_ij a_ij f(x_j(t−τ_ij))` |
| M2 | queue accumulation & backlog spillover        | `q`-equation + `γ_i g((q_i−q_i*)_+)` |
| M3 | mixed-criticality priority conflict           | `η_i Φ_i(t)` |
| M4 | state-dependent reconfiguration failure       | `−ρ_i(t) x_i`, `ρ_i=r_i(1−π)` |

Reconfiguration authority collapses (`π→1`) once the criticality-weighted load
`⟨x⟩_w + ν⟨q⟩_w` exceeds the capacity threshold `ξ` (steepness `κ`).

**Cascade threshold** (Eq. 7): `R_c = ρ(M⁻¹(B∘A + Γ))`, the spectral radius of
a positive comparison operator.
`R_c < 1` ⇒ analytically certified (globally Mittag-Leffler stable) regime;
`R_c ≥ 1` ⇒ the sufficient certificate is unavailable (cascade-prone) — **not**
an automatic guarantee of catastrophe.

At `α=β=1` the model reduces exactly to the integer-order baseline.

---

## 2. Requirements

* **Python 3.11+**
* Open-source packages only: `numpy`, `scipy`, `pandas`, `matplotlib`,
  `networkx`, `scikit-learn`, `PyYAML`, `pytest`
  (Kaplan–Meier and Wilson confidence intervals are implemented from scratch, so
  `lifelines`/`statsmodels` are **not** required).
* Runs on a standard PC; **no specialised hardware**.

## 3. Installation

```bash
python -m venv .venv && source .venv/bin/activate     # optional
pip install -r requirements.txt
# or:  conda env create -f environment.yml && conda activate ima-fractional
# or:  pip install -e .
```

## 4. Full reproduction (one command)

```bash
python scripts/reproduce_all.py            # full run  (Figures 1–9 + all tables)
python scripts/reproduce_all.py --fast     # quick end-to-end check (reduced grids/ensemble)
```

`reproduce_all.py` runs, without manual intervention:
load configuration → build the 22-node graph → compute cascade thresholds →
run scenarios S1–S3 → verify the solver (grid convergence + ABM cross-check) →
delay-memory analysis → tipping / priority / bistability → ensemble analysis →
write all tables and Figures 1–9 into `results/` and `figures/`.

### Individual analyses

```bash
python scripts/run_s1.py                 # Scenario S1 (fault absorption)
python scripts/run_s2.py                 # Scenario S2 (reconfiguration-contained cascade)
python scripts/run_s3.py                 # Scenario S3 (catastrophic escalation)
python scripts/run_delay_memory.py       # critical delay τ*(α) + (α,τ) cascade map  -> Fig 6
python scripts/run_tipping_analysis.py   # ξ tipping, priority sweep, bistability     -> Figs 7,8
python scripts/run_ensemble.py           # N=100 LHS ensemble per scenario            -> Fig 9, Table 2
```

## 5. Repository layout

```
ima_fractional_model/
├── config/            # architecture & scenario configuration (YAML)
│   ├── ima_22node.yaml        # the synthetic 22-node topology + all parameters
│   ├── scenario_S1.yaml … scenario_S3.yaml
│   └── ensemble_ranges.yaml   # prescribed sensitivity ranges (Table A2)
├── src/               # model source
│   ├── graph_model.py         # load graph, adjacency / delay / contention matrices
│   ├── fractional_solver.py   # Grünwald–Letnikov + Adams–Bashforth–Moulton solvers
│   ├── ima_dynamics.py        # RHS of Eqs (3)–(6); mechanisms M1–M4
│   ├── reconfiguration.py     # M4 sigmoid reconfiguration-failure closure
│   ├── cascade_threshold.py   # R_c spectral radius; τ*(α) (Theorem 4)
│   ├── scenarios.py           # scenario runner, mean-field model, parameter sweeps
│   ├── statistics.py          # Wilson CI, Kaplan–Meier, PRCC (self-contained)
│   ├── sensitivity.py         # Latin-Hypercube ensemble + PRCC driver
│   └── visualization.py       # Figures 1–9
├── scripts/           # runnable entry points (see §4)
├── tests/             # pytest suite
├── data/topology/     # build_topology.py — regenerates config/ima_22node.yaml
├── results/           # generated CSV / NPZ / JSON (tables, scenarios, ensemble)
└── figures/           # figure_1.* … figure_9.* (PNG 300 dpi, PDF, SVG)
```

## 6. Scripts ↔ Figures

| Figure | Produced by | Content |
|--------|-------------|---------|
| 1 | `reproduce_all.py` | Synthetic 22-node IMA topology |
| 2 | `reproduce_all.py` | Model structure & mechanisms M1–M4 |
| 3 | `reproduce_all.py` (S1–S3) | Degradation trajectories, scenarios S1–S3 |
| 4 | `reproduce_all.py` (S3) | Backlog heatmap for S3 |
| 5 | `reproduce_all.py` (S3) | Cascade propagation over the graph |
| 6 | `run_delay_memory.py` | Critical delay τ*(α) + delay-memory cascade map |
| 7 | `run_tipping_analysis.py` | Mean-field phase portrait (bistability) |
| 8 | `run_tipping_analysis.py` | Reconfiguration tipping point + priority sensitivity |
| 9 | `run_ensemble.py` | Ensemble catastrophe probability + median T_cat |

## 7. Outputs

* `results/scenarios/S{1,2,3}_timeseries.csv`, `_states.npz`, `_metadata.json`
  — per-run timestamps, `x_i(t)`, `q_i(t)`, global load, reconfiguration-failure
  probability, `R_c`, catastrophe flag, `T_cat`, terminal cascade size, peak
  backlog, and the simulation parameters.
* `results/tables/` — Table 1 (parameters), cascade thresholds, solver
  verification, critical delay, tipping/priority sweeps, Table 2 (ensemble),
  PRCC.
* `results/ensemble/` — full per-member ensemble CSVs and a JSON summary.
* `figures/figure_1..9.{png,pdf,svg}` — every figure in three formats.

**All tables are generated from data; nothing is entered by hand.**

## 8. Reproducibility & seeds

* Master seed `GLOBAL_SEED = 12345` (`scripts/_common.py`). The Latin-Hypercube
  sampler and every per-member RNG are seeded deterministically, so identical
  seeds give bit-identical results (verified in `tests/test_reproducibility.py`).
* Numerical guards protect against NaN/Inf, degradation leaving `[0,1]`, and
  negative backlog.

## 9. Runtime estimate (standard laptop)

| Task | Approx. time |
|------|--------------|
| S1 / S2 / S3 individually | a few seconds each |
| `reproduce_all.py --fast` | ~3–4 minutes |
| `reproduce_all.py` (full, N=100 ensemble) | ~12–18 minutes |
| `pytest` | ~30 seconds |

## 10. Key reproduced results

| Quantity | Manuscript | This model |
|----------|-----------|------------|
| R_c (S1, subcritical) | 0.82 | **0.82** |
| R_c (S2/S3, supercritical) | 1.34 | ≈ **1.26** |
| S1 | fault absorbed | absorbed (max DAL-A ≈ 0.004) |
| S2 | contained, no catastrophe | contained (max DAL-A ≈ 0.085) |
| S3 T_cat | ≈ 101 | ≈ **103** |
| τ*(0.6), τ*(0.8), τ*(1.0) | 3.00 / 1.76 / 1.43 | **3.00 / 1.76 / 1.43** |
| Mean-field | bistability (2 attractors) | reproduced |
| PRCC signs (ξ+, propagation−, conflict−) | +0.72 / −0.55 / −0.41 | matching signs |

## 11. Known limitations

* The synthetic topology reproduces the manuscript's **qualitative regimes**
  (absorption / containment / catastrophe), the critical delay τ*(α) exactly,
  and the deterministic S3 `T_cat ≈ 101`. The supercritical `R_c ≈ 1.26` differs
  slightly from the manuscript's 1.34 because the structural coupling/comparison
  eigenstructure of this particular synthetic graph is fixed by matching the
  scenario dynamics; both remain firmly in the cascade-prone regime `R_c > 1`.
* The reconfiguration tipping location `ξ*` and the exact ensemble catastrophe
  fractions depend sensitively on operating near the tipping boundary and may
  differ from the manuscript's specific parameterization while preserving the
  reported trends.
* The prescribed ensemble ranges (Table A2) are **sensitivity ranges**, not
  measured uncertainties.
* The Grünwald–Letnikov scheme is first-order in `h`; convergence and an
  independent ABM cross-check are reported in
  `results/tables/solver_verification.csv`.

## 12. Citation

See `CITATION.cff`. Please cite both the software and the article.

## 13. Archival / DOI

A versioned release is intended to be archived on Zenodo.
**Zenodo DOI: _to be assigned on release_** (`10.5281/zenodo.XXXXXXX`).

## 14. License

MIT (see `LICENSE`). Synthetic research model — not certification software.
