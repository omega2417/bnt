# ACP-SME — Adaptive Cybersecurity Protector for SMEs

Reference implementation and reproduction package for:

> Prokopovych-Tkachenko, D. **A Metadata-Driven Adaptive Cybersecurity Protector for SMEs
> in Metaverse-Enabled Ecosystems: Resource-Aware Tailoring of NIST CSF 2.0,
> ISO/IEC 27001:2022, and CIS Controls v8.1.**

ACP-SME treats an SME's approved cybersecurity profile as a **versioned decision object**.
Minimized, locally processed business metadata flags a material change; a typed capability
graph explains why that change matters across three complementary standards; a constrained
exact selector builds a resource-feasible profile delta; and an authorized person decides
whether the baseline actually changes.

---

## ⚠️ Claims boundary — read this first

ACP-SME is a **governance decision-support artifact**. It is not an anti-malware packer,
vulnerability scanner, SIEM, autonomous enforcement engine, actuarial loss model, or
certification system.

* Every number this package produces is **model output over explicitly synthetic traces**.
  No real SME, employee, customer, supplier, or incident is represented anywhere.
* "Coverage" is a **modeled capability-demand index**, not a probability of avoiding an
  incident and not a measure of implementation depth or evidence truthfulness.
* A standards reference states **why a recommendation is relevant**. It does not prove
  conformity and does not assert certification readiness.
* Review hours are **assigned accounting constants**, not time-and-motion observations.
* The software **cannot** implement a safeguard, change an approved profile, or accept
  risk. Only an authorized human decision does that, and the code enforces it.

The results verify internal behavior under encoded assumptions. They do **not** demonstrate
real-world incident reduction, standards conformity, or certification readiness.

---

## Requirements

Python **3.9+**. The core artifact, the full experiment, and the entire test suite run on a
**bare standard-library installation** — no third-party packages required. `matplotlib` is
optional and needed only to render the figures.

```bash
python -m pip install -e .            # core only, zero dependencies
python -m pip install -e ".[figures]" # adds matplotlib for figure rendering
python -m pip install -e ".[dev]"     # adds pytest
```

You can also run it straight from the source tree without installing anything:

```bash
PYTHONPATH=src python -m acp_sme selftest
```

## Quick start

```bash
acp-sme selftest      # selector, guard and reproducibility invariants
acp-sme demo          # worked end-to-end governance walkthrough
acp-sme reproduce     # full reproduction package -> results/
acp-sme params        # dump every parameter pack as JSON
```

`acp-sme reproduce` takes well under a minute on a laptop and writes:

| File | Contents |
| --- | --- |
| `results/primary_summary.json` | Table 6 with 95% confidence intervals and paired differences |
| `results/trace_outcomes.csv` | one row per trace per condition (270 rows) |
| `results/sensitivity.csv` | Table 7 grid: 5 thresholds x 3 budget factors |
| `results/run_environment.json` | Python version and platform for provenance |
| `results/figures/*.png` | Figures 3–6 (requires matplotlib) |
| `results/daily_coverage.csv` | per-day coverage, with `--daily` (large) |

## What the code contains

| Module | Article element |
| --- | --- |
| `capabilities.py` | Table A1 — 14 capabilities, costs, effectiveness, prerequisites |
| `metadata_model.py` | Table 2 — Minimum Necessary Metadata Model and the local metadata guard |
| `crosswalk.py` | Table 3 — typed, directional, versioned capability→standards graph |
| `detector.py` | Equations (1) and (2) — distance, critical predicates, 2-of-3 persistence, timer |
| `selector.py` | Equations (3) and (4) — exact resource-constrained selection |
| `profile.py` | Figure 2 — proposals, roles, approval, hash-chained versioning, rollback |
| `scenarios.py` | Table 4 and Table A2 — archetypes and the synthetic event catalog |
| `simulator.py` | Section 3.7 and Table A3 — the seeded surrogate experiment |
| `metrics.py` | Equation (5) and Section 3.8 — coverage, delay, burden, intervals |
| `experiment.py` | Tables 6 and 7 |
| `figures.py` | Figures 3–6 (optional matplotlib) |
| `demo.py` | End-to-end walkthrough of the parts the surrogate does not exercise |

### Scope note: what the experiment does and does not exercise

The reported experiment is a **component-level surrogate**, exactly as Section 3.7 states.
It exercises the exact selector and profile-update timing under the disclosed *event-score
proxy*. It does **not** instantiate raw MNMM records and does **not** exercise the full
Equation (2) branches.

That is not a gap in this package — it is the article's stated design. The metadata guard,
the complete detector, the typed crosswalk traversal, and the approval lifecycle are all
implemented here and are verified by the **test suite** and the `demo` command rather than
by the reported experiment. `docs/CLAIMS_BOUNDARY.md` states precisely which claims each
artifact component supports.

## Requirements traceability

Table 1 of the article defines eight requirements and their planned verification. Each is
mapped to executable tests:

| ID | Requirement | Where it is verified |
| --- | --- | --- |
| R1 | Metadata minimization | `tests/test_metadata_model.py` — schema and prohibited-field tests |
| R2 | Local-first processing | No network or I/O egress in the package; `docs/ARCHITECTURE.md` |
| R3 | Semantic traceability | `tests/test_crosswalk.py` — complete-path rate is 100% |
| R4 | Resource feasibility | `tests/test_selector.py` — budget, dependency, exception queue |
| R5 | Human authority | `tests/test_profile.py` — role and approval-path tests |
| R6 | Fail-safe uncertainty | `tests/test_metadata_model.py`, `tests/test_detector.py` |
| R7 | Versioned standards logic | `tests/test_profile.py` — hash chain, replay, rollback |
| R8 | SME operability | Zero runtime dependencies; `tests/test_reproducibility.py` |

```bash
python -m pytest              # 140 tests
python -m pytest -m "not slow"
```

## Reproduction fidelity

Every value this implementation produces falls **inside the confidence interval the article
reports**. See `docs/REPRODUCIBILITY.md` for the side-by-side comparison and for the one
documented deviation (finite-sample false-alert counts in the sensitivity grid, where the
article reports the analytic design expectation).

The article specifies every parameter but not the order in which pseudo-random draws are
consumed, so an independent implementation reproduces the reported *intervals*, not
identical digits. `tests/test_reproducibility.py` asserts exactly that claim.

## Data availability

No confidential, personal, or real-enterprise data were used, and none are required. All
scenario definitions and parameters are in `src/acp_sme/scenarios.py` and
`src/acp_sme/simulator.py`, and are dumped machine-readably by `acp-sme params`.

## Citation

See `CITATION.cff`. Please cite both the article and this software record.

## License

MIT for the source code (`LICENSE`). Documentation and figures are CC BY 4.0.

Standards identifiers (NIST CSF 2.0, ISO/IEC 27001:2022 Annex A, CIS Controls v8.1) are
cited as references only. **No ISO/IEC control text is reproduced** — ISO control text is
licensed, and identifiers must be checked against the edition held by the adopting
organization. Mappings should be independently reviewed, versioned, and regression-tested
before any operational use.
