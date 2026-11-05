# AIDE-6 — Agentic Design System for Complex Technical Systems (Google Colab)

A self-contained teaching software project based on the article *"Artificial Intelligence in the Design of Complex Technical
Systems: Integrating Engineering Knowledge, Multi-Objective Synthesis and Digital Twins"*. The end-to-end example is a Ka-band
satellite-communication antenna terminal for mobile platforms.

## Archive contents

| File | Purpose |
|---|---|
| `AIDE6_agentic_design_EN.ipynb` | Colab notebook (no outputs — runs from scratch) |
| `AIDE6_executed_EN.ipynb` | the same notebook, already executed: all figures, tables and conclusions |
| `aide6_outputs/` | artefacts of the executed run: figures, PROV-JSON, journal, decisions, claims, document drafts |
| `README.md` | this file |

## How to run in Google Colab

1. Open https://colab.research.google.com → **File → Upload notebook** → `AIDE6_agentic_design_EN.ipynb`.
2. **Runtime → Run all**. A standard CPU runtime needs about 3–6 minutes. Nothing has to be installed
   (NumPy, SciPy, pandas, scikit-learn, networkx, matplotlib and Numba are preinstalled in Colab).
3. At the end `aide6_outputs.zip` with all artefacts is downloaded automatically.

Flags in the first code cell: `FAST=True` — quick mode (fewer Monte Carlo runs); `INTERACTIVE=True` — gate decisions G1–G6 are
entered by a human via `input()` (by default they are simulated from the gate criteria and logged as `engineer(simulated)`).

## What is implemented

* **Data model:** Requirement, Artefact, Claim, Evidence, Decision, ToolRun, ModelVersion; SHA-256 hashes.
* **Knowledge and data:** W3C PROV-style provenance (PROV-JSON), hash-chained journal, versioned artefact repository, twin registry.
* **Tools as MCP servers:** catalog, stage123, morph, mcda, twin, verif, uq, faults, bo, lab — with JSON input/output schemas, budget and logging.
* **Orchestrator:** state machine S1→G1→…→G6→DONE with feedback loops 4→3, 5→3, 6→4; state persists between sessions.
* **Agents:** A1–A6, critic C (separate context, recomputation, quote search, protocol hash checks), traceability TR (graph, T_cov),
  documentation D (drafts of the specification, test programme, report, patent materials), security S (confidentiality, prompt-injection defence).
  Autonomy policy λ(a).
* **Stages 1–6:** knowledge extraction with quotes (LS1), element catalogue (C_F, deduplication), morphological space 4608 → 1476 → 810,
  exact Pareto front, NSGA-II, AHP/TOPSIS, novelty; digital twin (Monte Carlo, DVB-S2 ACM); V&V, LHS + GP + Sobol indices, faults,
  Bayesian optimisation, Clopper–Pearson; bench imitator, GUM, validation |E| ≤ 2u_val, calibration, thermal axis shift,
  2^(4−1) factorial design, isolation forest, TRL.
* **LS6:** 50 injected defects, ablations "without critic" and "without gates".

## Data status

All parameters are teaching values; patent documents and test results are synthetic; the LLM is imitated by a deterministic
`MockLLM` (the `LLMBackend` interface allows a local model to be plugged in). The results demonstrate that the procedure works,
not the characteristics of a real product.
