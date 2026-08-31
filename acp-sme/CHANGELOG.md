# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-08-31

First public release: the reference prototype and reproduction package for
ACP-SME v0.1 as described in the accompanying article.

### Added

- **Capability layer** (`capabilities.py`) — the 14 shared capabilities of
  Table A1 with cost units, effectiveness coefficients and prerequisites, plus
  exhaustive enumeration of the 919 dependency-valid subsets.
- **Minimum Necessary Metadata Model** (`metadata_model.py`) — the Table 2
  field allowlist, a deny list for the explicit exclusions, banding, tenant-keyed
  pseudonymization, retention deadlines, and fail-closed rejection. Missing and
  stale evidence produce verification tasks rather than zero-risk values.
- **Typed capability crosswalk** (`crosswalk.py`) — 43 directional, typed,
  versioned edges to NIST CSF 2.0, ISO/IEC 27001:2022 and CIS Controls v8.1,
  with a draft Statement of Applicability generator that never records a
  risk-treatment decision.
- **Material-change detector** (`detector.py`) — Equation (1) weighted
  approved-profile distance over numeric, categorical and set features;
  Equation (2) with five deterministic critical predicates, the two-of-three
  persistence rule and a scheduled-review timer.
- **Exact selector** (`selector.py`) — Equations (3) and (4) with budget and
  prerequisite constraints as algorithmic invariants, deterministic tie-breaking,
  and an exception queue for infeasible mandatory obligations.
- **Profile lifecycle** (`profile.py`) — explainable proposals carrying trigger,
  rationale, provenance, burden, confidence, alternatives, expiry and rollback
  implications; role-separated decisions; a hash-chained, replayable and
  rollback-capable ledger.
- **Synthetic experiment** (`scenarios.py`, `simulator.py`, `metrics.py`,
  `experiment.py`) — the three archetypes, the 420-event catalog, the seeded
  surrogate over 90 traces and 10,800 enterprise-days, and the sensitivity grid.
- **Figures** (`figures.py`) — Figures 3–6, with matplotlib as an optional
  dependency so the numerical results never require it.
- **Worked walkthrough** (`demo.py`) — the guard, detector, crosswalk and
  approval lifecycle exercised end to end.
- **CLI** (`acp-sme`) — `reproduce`, `experiment`, `sensitivity`, `demo`,
  `selftest` and `params`.
- **Tests** — 140 tests mapped to requirements R1–R8 of Table 1, including
  reproducibility tests that assert results fall inside the reported intervals.
- Zenodo deposition metadata, citation metadata, and reproducibility,
  architecture, parameter and claims-boundary documentation.
