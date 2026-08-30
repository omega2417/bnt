# DTCR — controlled evaluation of a digital-twin cyber-resilience framework

Reproducibility deposit for the manuscript *Digital-Twin-Enabled Cyber-Resilience
Framework for Secure Edge-Cloud Orchestration and Data Integrity in Distributed
Smart-Region Infrastructure* (`Man-V3`), together with the frozen protocol for the
physical campaign on the UMSF laboratory cyber range.

---

## ⚠ Read this before using any number from this deposit

**The physical experiment on the UMSF cyber range has not been performed.**
Gate 0 (authorization, isolation, safety) is unsigned and Gate 1 (inventory) is not
done — see `authorization/` and `inventory/inventory_status.md`. Nothing here
measures Keenetic, UniFi, EcoFlow, the 48 V circuit, Raspberry Pi hardware,
Kubernetes, or Eclipse Ditto.

What **was** performed is a fully pre-registered **software-in-the-loop (SIL)**
campaign of the framework's algorithmic core: 120 pilot + **1296 confirmatory runs**,
6 arms × 4 scenarios × 54 repetitions, blocked by seed, 0 exclusions, 318
right-censored runs. Every row carries `data_origin = simulation`, and
`analysis/audit_provenance.py` fails the build if a simulation row is ever used to
support a physical-testbed claim.

Start with **`docs/EXPERIMENT_REPORT.md`**.

## Directory layout

| Path | Contents |
|---|---|
| `dtcr/` | Reference implementation: one module per block of the mathematical model |
| `harness/` | Environment generator, scenario injectors, arm definitions, run executor, campaign driver |
| `tests/` | 37 unit checks; several fail against the manuscript's printed equations by design |
| `protocol/` | Frozen pre-registration, hypotheses, randomisation plans |
| `authorization/` | Gate 0 checklist — **unsigned** |
| `inventory/` | Asset inventory (`PENDING`), status analysis, SIL topology |
| `data/real/` | **Empty.** Reserved for the physical campaign |
| `data/pilot/`, `data/simulation/` | Pilot and confirmatory runs plus per-run evidence bundles |
| `processed/` | `runs.csv`, descriptive statistics, data dictionary |
| `analysis/` | Calibration, statistics, figures, checksums, provenance audit, `reproduce.sh` |
| `figures/` | All six figures, regenerated from `processed/runs.csv` |
| `docs/` | Experiment report, manuscript corrections, claim matrix |
| `checksums/` | `SHA256SUMS` over every artefact |

## Reproduce everything

```bash
pip install "numpy>=2.0" "scipy>=1.14" "pandas>=2.2" "matplotlib>=3.9"
bash analysis/reproduce.sh
```

About two minutes. The script runs the unit tests, the pilot, the Gate-3 power
analysis, the 1296-run confirmatory campaign, the statistics, the data dictionary,
the figures, the checksums, and finally the provenance audit — which exits non-zero
if anything is inconsistent. Exact versions are in `analysis/environment.lock`.

## What the campaign found

**Ten reproducible defects in `Man-V3`** (`docs/manuscript_corrections.md`), including:

- a Mahalanobis threshold that, taken at `p = 2` instead of the deployed `p = 9`,
  runs at an **actual 41.8 % false-positive rate** against a nominal 1 %;
- an anomaly transform (Eq. 7) that scores a **median healthy asset 0.985** at `p = 9`;
- a worked example (Table 6) that contradicts the paper's own stated column
  normalisation of `W`;
- a dimensionally inconsistent objective (Eq. 12) whose risk/cost balance swings by
  a factor of 3.5 between runs of the same deployment;
- a headline mean detection latency that **is not estimable**, because the baseline
  detects in 2 of 54 runs in one scenario and 0 of 54 in two others;
- a cited GitHub repository whose default branch is the MATLAB Bayes Net Toolbox.

**Honest null results**, reported as found rather than tuned away: no detection
advantage under pure volumetric DoS; no graph benefit for a leaf-node integrity
fault; no measurable improvement in action *ranking* from what-if planning in this
environment.

**Verified analytical claims:** the manuscript's block-audit results
(`r_min = 59`, `P_bound = 0.9515`, `P_exact = 0.9519`, all of Table 5) and its trust
worked examples (0.895, 0.910) reproduce exactly.

## Licences

- Code (`dtcr/`, `harness/`, `analysis/`, `tests/`): MIT — `LICENSE-CODE`
- Data, figures, documentation: CC BY 4.0 — `LICENSE-DATA`

## Citing

See `CITATION.cff`.
