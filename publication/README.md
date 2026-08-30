# Publication deliverables — DTCR framework (*Electronics* submission)

This directory contains the reproducibility work for the manuscript
*Digital-Twin-Enabled Cyber-Resilience Framework for Secure Edge-Cloud
Orchestration and Data Integrity in Distributed Smart-Region Infrastructure*,
produced in response to the revision notes
(`Propozytsii_vypravlennia_Manuscript_v02_Electronics.md`).

## Contents

| Item | What it is |
|---|---|
| `dtcr-deposit/` | the full deposit: reference implementation, analysis pipeline, configs, attack recipes, reference dataset, figures, and the manuscript-integration pack |
| `dtcr-deposit.zip` | the same deposit as a single archive, ready to upload to Zenodo |
| `dtcr-deposit/notebooks/DTCR_analysis.ipynb` | the Google Colab notebook: algorithm, visualizations and report in one runnable file |

## Start here

1. `dtcr-deposit/README.md` — what every part is and how to run it.
2. `dtcr-deposit/PROVENANCE.md` — **read before citing anything**: the current
   `data/` is a synthetic reference dataset, not measurement.
3. `dtcr-deposit/manuscript_integration/` — the revised abstract, methods,
   mathematics, results, reference audit and declarations to fold into the DOCX.

## One-command reproduction

```bash
cd dtcr-deposit
pip install -r environment/requirements.txt
make all        # data -> statistics -> NRI -> figures -> verification
python analysis/test_dtcr.py
```

## What was delivered against the review

- **Run-level dataset** (160 runs) with timestamps, availability traces,
  confusion matrices, resource measurements and a 480-run ablation matrix.
- **Full statistics**: means, SD, median/IQR, 95% t and bootstrap CIs, paired
  tests with Holm correction, Hedges g and Cliff's delta, Wilson intervals.
- **Figures rebuilt from primary data** (Figures 5–11), with Figure 5 and
  Figure 6 computed from a single source so they cannot disagree.
- **Reconcilable NRI**: `calculate_nri.py` recomputes recovery time and NRI from
  the traces and fails if they disagree with the stored values.
- **Corrected mathematics**: chi-square anomaly calibration, empirically selected
  risk aggregation, column-normalised graph propagation with spectral radius and
  convergence margin, hard-constraint orchestration with vector capacities.
- **Actual parameters, attack recipes, threat model, implementation mapping.**
- **Bibliography DOI audit** and Related Work additions.
- **MDPI declarations, Data Availability, and AI disclosure** drafts.
- **Colab notebook** carrying the algorithm, the visualizations and the report.

The deposit is internally consistent today (`make verify` → structural PASS) and
reports **not submission-ready** until the synthetic dataset is replaced with
real measurements and a Zenodo DOI is minted — by design, so the honest status is
never lost.
