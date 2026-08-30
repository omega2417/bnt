# DTCR — reproducibility deposit

Reference implementation, analysis pipeline, configuration, attack recipes and
reference dataset for the manuscript

> **Digital-Twin-Enabled Cyber-Resilience Framework for Secure Edge-Cloud
> Orchestration and Data Integrity in Distributed Smart-Region Infrastructure**
> (submitted to *Electronics*, MDPI).

This deposit is the response to the reproducibility requirements of the journal
and to the specific reviewer requests collected in the revision notes: run-level
data, full statistics, figures rebuilt from primary data, a reconcilable NRI, an
ablation study, corrected mathematics, exact parameters, attack recipes, and a
threat model.

> ⚠️ **Read `PROVENANCE.md` first.** The `data/` directory of this release
> contains a **synthetic reference dataset**, not measurements. It exists so the
> whole analysis pipeline runs end to end today; every row is marked
> `data_origin = synthetic_reference`, and `analysis/verify_repository.py`
> refuses to certify the deposit as submission-ready until real measurements
> replace it. Nothing in `data/` may be cited as an experimental result.

## Quick start

```bash
cd dtcr-deposit
python -m pip install -r environment/requirements.txt
make all          # data -> statistics -> NRI -> figures -> verification
```

Individual stages:

```bash
make data         # regenerate the synthetic reference dataset (seed 20260731)
make analysis     # statistics.py + calculate_nri.py  -> results/
make figures      # generate_figures.py               -> figures/
make verify       # verify_repository.py: consistency + submission readiness
python analysis/test_dtcr.py    # unit tests: maths locked to the worked examples
```

## What each part is

| Path | Contents |
|---|---|
| `analysis/dtcr/` | the reference library: `audit`, `trust`, `anomaly`, `risk`, `orchestration`, `resilience`, `stats` — one module per block of the mathematical model |
| `analysis/statistics.py` | every reported effect: means, CIs, medians/IQR, bootstrap, effect sizes, paired/unpaired tests, confusion metrics, overhead, ablation |
| `analysis/calculate_nri.py` | recomputes recovery time and NRI **from the availability traces** and cross-checks them against the stored values; produces the Figure 6 trajectory with a 95% band |
| `analysis/generate_figures.py` | regenerates Figures 5–11 from the published data |
| `analysis/simulate_reference_dataset.py` | the synthetic-data generator (see `PROVENANCE.md`) |
| `analysis/verify_repository.py` | structural + consistency + submission-readiness checks |
| `analysis/test_dtcr.py` | unit tests binding the library to the manuscript's worked examples |
| `configs/` | actual framework parameters (replaces Table 1's illustrative column), K3s/Kubernetes/Suricata/Ditto configuration |
| `attacks/` | exact per-scenario attack recipes and reference drivers (isolated lab only) |
| `data/` | run-level metrics, availability traces, confusion matrices, resource measurements, ablation runs |
| `results/` | machine-readable tables and `summary.json` produced by the analysis |
| `figures/` | PNG (600 dpi) and PDF versions of every figure |
| `manuscript_integration/` | the revised text blocks, tables and declarations to fold back into the manuscript |
| `environment/` | pinned Python requirements and the testbed software inventory |

## How the deposit answers the reviewers

| Reviewer request | Where it is addressed |
|---|---|
| Restore or repeat run-level data (160 rows) | `data/run_level_metrics.csv`, 160 runs with onset/detection/containment/recovery timestamps |
| Publish data + code with a DOI | this deposit; mint a Zenodo DOI and set it in `README.md` and `CITATION.cff` |
| Full statistics: SD, median/IQR, 95% CI, effect sizes, tests | `analysis/statistics.py`, `results/table_S1..S3` |
| Figure 5 from primary data with points/box/CI | `figures/figure5_detection_recovery.*` |
| Reconcilable Figure 6 and NRI | `analysis/calculate_nri.py` derives NRI from the same traces Figure 6 plots; `make verify` proves they agree |
| Actual parameters (not illustrative) | `configs/framework_parameters.yaml` |
| Implementation mapping of each mechanism | `manuscript_integration/02_methods.md` |
| Exact attack recipes; precise S3 profile; S2 sub-cases | `attacks/`, `THREAT_MODEL.md` §2, §4 |
| Automated baseline + ablation study | `data/ablation_runs.csv`, `results/table_S6_ablation.csv`, `figures/figure11_ablation.*` |
| Corrected Eq. 7 (chi-square), risk aggregation, graph normalisation | `analysis/dtcr/anomaly.py`, `risk.py`; `manuscript_integration/03_mathematics.md` |
| Confusion matrices + denominators for the 98.7% claim | `data/confusion_matrices/`, `results/table_S4_integrity.csv`, `figures/figure9_integrity_metrics.*` |
| Exact overhead with both denominators | `results/table_S5_overhead.csv`, `figures/figure10_overhead.*` |
| Threat model + cryptographic description | `THREAT_MODEL.md` |
| Bibliography DOI audit | `manuscript_integration/05_references_audit.md` |
| MDPI declarations, Data Availability, AI disclosure | `manuscript_integration/06_declarations.md` |

## Reproducibility guarantee

`make verify` passes only if recovery time and NRI recomputed from the
availability traces match the stored per-run values, and only if the aggregates
in `results/summary.json` match the numbers printed in the manuscript to the
precision at which they are printed. Figure 5 (per-run latency/recovery) and
Figure 6 (NRI) are therefore computed from a single source and cannot disagree.

## Licence

Code and configuration: MIT (`LICENSE`). Data and figures: CC BY 4.0
(`LICENSE-DATA`). See `CITATION.cff` for how to cite.
