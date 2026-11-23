# recovery-evidence

Simulation, analysis and reproduction package for the article

> Torstensson, O., Prokopovych-Tkachenko, D., Khokhlachova, Y.
> **Prioritizing Recovery Evidence Verification across Shared Service Dependencies under
> Limited Audit Capacity.** Submitted to *Computers & Security* (Elsevier).

A security team that can verify one recovery dependency per day has to decide which stale
record to refresh next. The package implements four deterministic verification policies
(age, event-driven, static structural importance, current influence on readiness verdicts),
replays them on identical simulated trajectories in which the operator never sees the hidden
component states, and measures how often the resulting readiness records are wrong.

One command regenerates every log, table and figure of the article and compares the files,
byte for byte, with the released SHA-256 digests:

```bash
python -m pip install -e ".[figures]"
recovery-evidence reproduce --check        # about 40 s on a 4-core laptop
```

## What the results do and do not mean

* Every number is **model output over synthetic trajectories**. No organisation, system,
  incident or person is represented, and no personal or confidential data are used.
* The outcome is the **correctness of readiness records** (false assurance, false rejection).
  It is not recovery time, loss, incident prevention or regulatory compliance.
* Checks are assumed exact, immediate and of equal cost. See `docs/COMPONENT_STATUS.md` for
  what is implemented, tested, used in the experiment, and deliberately left out.

## Headline result (condition C0, 300 paired trajectories of 180 days, one check per day)

| Policy | False assurance | False rejection | Total |
| --- | --- | --- | --- |
| P0 age | 10.15 | 9.69 | 19.84 |
| P1 event-driven | 5.85 | 6.47 | 12.32 |
| P2 static importance | 5.42 | 6.25 | 11.68 |
| P3 current influence | 5.43 | 4.35 | 9.78 |

Service-days per 100 observed service-days. Primary contrast P3 − P1 in false assurance:
**−0.42** (95% bootstrap interval −0.60 to −0.24); in false rejection: −2.12 (−2.35 to −1.90).
All tables: `results/tables/`.

> **Before submission.** The manuscript draft was written from an earlier run whose
> notice-stream draw order is not recoverable from the text. This package reproduces every
> draft number that does not depend on notices digit for digit (all of policy P0, conditions
> C1 and C10) and the remaining numbers within Monte Carlo error, with the same qualitative
> conclusions. `results/tables/manuscript_alignment.md` lists each printed number that has to
> be replaced so that the article and the archive agree exactly. See
> `docs/REPRODUCIBILITY.md`, section "Relation to the manuscript draft".

## Commands

| Command | Purpose | Article |
| --- | --- | --- |
| `recovery-evidence example` | worked example | Section 3.4 |
| `recovery-evidence checks` | the 27 implementation checks → `control_checks.txt` | Section 4.6 |
| `recovery-evidence params` | resolved parameters of C0–C12 | Table 4 |
| `recovery-evidence run` | experiment and primary logs | Sections 4.1–4.3 |
| `recovery-evidence analyze` | independent re-computation, statistics, tables | Sections 4.4–4.6, 5 |
| `recovery-evidence figures` | Figures 1–5 (PDF, TIFF 1000 dpi, PNG 600 dpi) | Figs. 1–5 |
| `recovery-evidence claims` | claim-to-evidence register | all reported numbers |
| `recovery-evidence verify` | compare `results/` with `SHA256SUMS.txt` | Section 4.6 |
| `recovery-evidence reproduce [--check]` | all of the above | — |

Without installation: `PYTHONPATH=src python -m recovery_evidence <command>`. A script with no
dependencies at all re-derives the worked example and the audit cases:
`python supplementary/worked_example.py`.

## Layout

| Path | Content | Article |
| --- | --- | --- |
| `src/recovery_evidence/topology.py` | dependency maps, readiness `g`, influence `D`, static importance `c` | Sections 3.2–3.3, Fig. 1, Table 2 |
| `src/recovery_evidence/policies.py` | policies P0–P3, tie-break rule | Table 3 |
| `src/recovery_evidence/generator.py` | hidden states and notices, five PCG64 streams | Section 4.1 |
| `src/recovery_evidence/simulation.py` | operator, guarded test module, evaluator | Sections 3.1, 3.5, 4.4 |
| `src/recovery_evidence/data/conditions.json` | every parameter of C0–C12 | Table 4 |
| `src/recovery_evidence/experiment.py` | runs and byte-reproducible logs | Section 4 |
| `src/recovery_evidence/analysis.py` | analysis that does not import the simulator | Sections 4.5–4.6, Tables 5–8 |
| `src/recovery_evidence/checks.py` | 27 implementation checks | Section 4.6, Appendix A |
| `src/recovery_evidence/figures.py` | Figures 1–5 | Figs. 1–5 |
| `src/recovery_evidence/claims.py` | claim-to-evidence register | — |
| `supplementary/worked_example.py` | dependency-free second implementation of the formulas | Section 3.4, Appendix A |
| `tests/` | 100 tests (27 are the implementation checks) | — |
| `results/` | released logs, tables, figures and digests | Section 5 |
| `docs/` | reproducibility, random streams, architecture, data dictionary, status, submission notes | — |

## Requirements

Python 3.9 or newer and NumPy (the article specifies NumPy's PCG64 generator). Matplotlib
and Pillow are needed only for the figures, pytest only for the tests. The released files were
produced with CPython 3.13.18, NumPy 2.5.3 and Matplotlib 3.11.2; see
`results/parameters.json` and `docs/REPRODUCIBILITY.md`.

```bash
python -m pip install -e ".[dev]"
python -m pytest                 # full suite, about 40 s
python -m pytest -m "not slow"   # about 15 s
```

## Data availability

No external data are required. All primary logs, summary tables and figures are generated by
the code. The Git repository carries the complete logs of the primary condition C0 and the
per-trajectory summaries of all 13 conditions; the archived release
(`make release`, deposited at https://doi.org/10.5281/zenodo.24466768) carries the complete
logs of all conditions. `results/SHA256SUMS.txt` covers all 95 files either way.
`dist/Supplementary_Material_S1.zip` is the compact journal e-component: code, tests, documents,
all tables, the C0 logs and the figures as PDF and TIFF; it is deposited at
https://doi.org/10.5281/zenodo.24466855.

## Citation and licence

Please cite the article and the archived software (`CITATION.cff`). Code: MIT (`LICENSE`).
Generated data, tables and figures: CC BY 4.0.
