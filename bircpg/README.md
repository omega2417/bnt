# bircpg — Bio-Inspired Resource-Constrained Potential Games

Reference implementation of the formal model, equilibrium analysis and prospective
evaluation protocol of

> **Bio-Inspired Resource-Constrained Potential Games for Adaptive Coordination in
> Autonomous Multi-Agent Systems**

The package exists so that every mathematical statement in the manuscript can be
*checked by running it*, and so that the prospective evaluation of Section 7 has a
concrete, preregisterable implementation rather than a prose description.

---

## Scope of claims — read this first

The manuscript is explicit that it presents a candidate formulation and a
reproducible evaluation plan, not results. This package keeps to that boundary.

| Layer | Status here |
|---|---|
| **Level I** — finite-game identities, equilibrium calculations | **Implemented and exact.** Rational arithmetic throughout; residuals are identically zero, not "within tolerance". |
| **Level II** — synthetic multi-agent environments | **Implemented as a harness** with declared generative assumptions. Synthetic task success is *not* robot validation. |
| **Level III** — trained controllers, physical platforms, measured energy and latency | **Not implemented and not claimed.** |

Consequently:

* **No experiment reported in the manuscript has been executed.** The bundled
  demonstration study runs at reduced scale and supports no confirmatory claim.
  `study.preregistered_design()` returns the design of Section 7.2 verbatim
  (4 population sizes × 6 conditions × 30 seeds × 1000 epochs) for when it is.
* **Energy here is a modelled proxy.** Equation (2) is a preference model, not a
  physical-energy accounting identity, and operation counts are not measured watts.
* **Nothing demonstrates that the proposed method wins.** In the small
  demonstration condition shipped with the package, the trace-biased logit rule
  performs *worse* than its uniform-reference comparator B2 on cumulative welfare.
  That result is left exactly as it comes out. Section 8 says negative findings
  are informative, and the generator is deliberately built so that no method gets
  a cheaper cost or a better accuracy by construction.
* **A certified stop is distinguished from a budget-limited exit** everywhere, in
  the code and in the logs. Exhausting an update budget certifies nothing.

## What is implemented

| Manuscript | Module | What it gives you |
|---|---|---|
| §4.1 Eq (1) | `game` | Feasible sets under energy / computation / memory / latency caps, plus the outside action |
| §4.2 Eq (2)–(4) | `game` | Dimensionless cost `d_i`, payoff `u_i`, welfare `W` |
| §5.1 Eq (5)–(6) | `game`, `equilibria` | Exact potential `Φ`; **Proposition 1** verified on every unilateral deviation |
| §5.1 Cor. 1 | `equilibria` | Pure equilibria, potential maximiser, finite improvement paths, price of anarchy |
| §5.2 Eq (7)–(8) | `estimation` | Bounded-error estimator, **Proposition 2** (`η → η + 2δ`), the Eq (8) gate, the `4δ + θ` stopping certificate, calibration coverage |
| §5.3 Eq (9)–(10) | `traces` | Trace update with decay and delay; frozen full-support reference distribution |
| §5.3 Eq (11)–(13) | `logit` | Logit rule, exact transition matrix, **Proposition 3** stationary law, detailed-balance check, **Corollary 2** bound |
| §5.4 Algorithm 1 | `protocol` | Outer physical loop; the robust and logit branches as mutual alternatives |
| §6, Table 2, Eq (14)–(15) | `section6` | The constructed example, exactly |
| §7.1 | `level1` | Seeded exact sweep with the required edge cases |
| §7.2 Table 3 | `environments` | Unit-square generator, congestion family, noise, packet loss, trace ageing, scheduled change, dropout |
| §7.3 B1–B5 | `baselines` | All five baselines, with oracle advantages labelled |
| §7.4–7.5 | `metrics`, `study` | Endpoints with censoring, paired bootstrap over whole runs, Holm correction |
| Figure 3 | `figures` | Regenerated from the code, with a CSV table view beside it |

## Where this lives

Source: <https://github.com/omega2417/bnt/tree/claude/publication-zenodo-project-w2iwa0/bircpg>

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/omega2417/bnt/blob/claude/publication-zenodo-project-w2iwa0/bircpg/notebooks/bircpg_colab.ipynb)

The deposition archive is **not** committed — it is built from the sources with
`python tools/make_archive.py`, which prints its SHA-256. That keeps the archive
reproducible from any checkout rather than being a binary that can drift from
the code.

## Install

```bash
pip install -e ".[dev]"        # from this directory
```

The core has **no dependencies** — exact-arithmetic verification should not rest
on a numerical stack. `matplotlib` is needed only for figures, `pandas` only for
the notebook's tables.

## Run

```bash
bircpg section6     # Table 2, Equation (6) identity, Equation (15) — all exact
bircpg level1       # the Section 7.1 verification sweep
bircpg figures      # Figure 3 (png/pdf, light and dark) + its CSV table view
bircpg study        # a small Level II study; --full runs the preregistered design
bircpg all          # everything at demonstration scale, into results/
```

Equivalently `python -m bircpg <command>`. Or open
`notebooks/bircpg_colab.ipynb` in Google Colab — it is self-contained and needs
no local setup.

```bash
pytest -q           # 177 tests
```

## Reproducing the manuscript's own numbers

`bircpg section6` prints Table 2 and Equation (15). Every value matches the
published table exactly, in rational arithmetic:

```
   Profile    u_1    u_2   W(a)  Phi(a)   Gap  PNE
--------------------------------------------------
    (A, A)      3      2      5       9     3  No
    (A, B)      7      5     12      12     0  Yes
    (B, A)      4      6     10      10     0  Yes
    (B, B)      1      2      3       6     6  No
```

with pure-equilibrium price of anarchy `6/5 = 1.2`, an additive welfare loss of
2 utility units at the worse equilibrium, and

```
pi(A, A) = 0.04192   pi(A, B) = 0.84203   pi(B, A) = 0.11396   pi(B, B) = 0.00209
```

These are the manuscript's published figures, so `tests/test_section6.py` asserts
them literally: if a change to the model breaks any of them, the suite fails.

## A note on the equations

The manuscript's equation bodies are embedded as Office math objects. They were
read directly from the document's OMML and transcribed symbol by symbol; the
implementation is then pinned to the manuscript's own published arithmetic —
Table 2, the price of anarchy, and Equation (15) — which it reproduces exactly.
That agreement is the check that the transcription is faithful.

## Layout

```
bircpg/
├── src/bircpg/          the package (see the table above)
├── tests/               177 tests; the propositions are asserted, not assumed
├── notebooks/           Colab-ready notebook
├── examples/            standalone scripts
├── results/             generated output (not tracked)
├── ZENODO.md            deposition checklist
├── .zenodo.json         archive metadata (placeholders to complete)
└── CITATION.cff         citation metadata (placeholders to complete)
```

## Reproducibility

Following Section 7.6, a run log records per epoch: the selected profile, the
termination reason, updates and payoff evaluations spent, the evaluator-side true
Nash gap, welfare and potential, realised value, energy and latency, bytes moved,
trace age, lost reports, active agents, and any context change that invalidated
the previous episode's certificate. Estimated values and evaluator-side truth are
stored separately so that later analysis can detect oracle leakage. Random
streams are separated by role — environment, estimator, method — so a method's
control flow cannot alter the environment it faces.

`write_endpoints_csv` leaves a censored run's cell empty rather than imputing it,
and the paired bootstrap drops censored pairs and counts them.

## Licence

MIT, covering the `bircpg/` directory only. This is an independent implementation
and is not derived from the Bayes Net Toolbox that shares this repository.
