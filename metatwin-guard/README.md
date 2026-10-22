# MetaTwin-Guard — reference artifact (Supplementary File S3)

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23557608.svg)](https://doi.org/10.5281/zenodo.23557608)

**Archived release:** https://doi.org/10.5281/zenodo.23557608

Explainable and verifiable digital-twin assurance backend for a documented
two-site university cyber range. Companion software for the article
*"An Explainable and Verifiable Digital Twin of a Two-Site Cyber Range for
Metaverse Infrastructure Assurance: Software Artifact and Field Protocol"*
(Korchenko, Prokopovych-Tkachenko, Davydenko, Askerov, Herasymenko, Zhurov).

> **Evidence boundary.** Everything this package produces is **level B —
> deterministic synthetic software verification**. It contains no cyber-range field
> data and no field-performance claim. The 3-of-4 quorum evidence chain is a
> **single-process emulation, not a distributed blockchain**. The deterministic
> Ed25519 keys are **test fixtures** and must never be used in a deployment.
> The code processes exported or synthetic telemetry only; it performs no
> scanning, exploitation, credential attack or network reconfiguration.

## What is implemented

| Article element | Module |
|---|---|
| Signed event envelope, canonical payload hash, per-source previous-hash (§3.4) | `metatwin_guard/events.py` |
| Ed25519 (RFC 8032) and SHA-256 (FIPS 180-4) primitives | `metatwin_guard/crypto.py` |
| Integrity admission g(e) = C_schema ∧ C_hash ∧ C_signature ∧ C_id ∧ C_sequence ∧ C_chain, Eq. (1) | `metatwin_guard/gateway.py` |
| Admission-before-state invariant, Eq. (2); staleness / freshness classes (§3.5) | `metatwin_guard/twin.py` |
| Median/MAD robust score, Eqs. (3)–(5); explanation c_j, Eq. (6); static rules; hybrid, Eq. (7) | `metatwin_guard/detector.py` |
| QuorumEvidenceLedger, 4 validators, 3-of-4 verification (§3.8) | `metatwin_guard/ledger.py` |
| Full pipeline (Figure 2) | `metatwin_guard/pipeline.py` |
| Deterministic generator, 6 scenarios (§3.9) | `metatwin_guard/generator.py` |
| Benchmark, metrics (P/R/F1, FP/1000, AUPRC), executed ablation, sensitivity, multi-seed | `metatwin_guard/benchmark.py`, `metrics.py` |
| Confirmed topology (Table 1) | `metatwin_guard/topology.py` |
| Figures 1, 2, 4 (+ ablation, sensitivity), 360 dpi PNG + SVG | `metatwin_guard/plots.py`, `scripts/make_figures.py`, `figures/` |
| Field protocol S1, blank workbook + data dictionary S2 | `field_protocol/` |
| Colab notebook with demonstrations and conclusions | `notebooks/MetaTwin_Guard_Colab.ipynb` |
| DOI-referenced sources and their role in the code | `REFERENCES.md`, `references.bib` |

## Quick start

```bash
python3 -m pip install -r requirements.txt
python3 -m unittest discover tests            # 27 tests (5 core of Table 4 + 22 extended/regression)
python3 -m compileall -q .
python3 -m metatwin_guard.benchmark --seed 20260823 --out results --extra-seeds 1 2 3 4
python3 scripts/make_figures.py
python3 scripts/make_field_workbook.py
```

Google Colab: open `notebooks/MetaTwin_Guard_Colab.ipynb` (File → Upload notebook)
and run all cells. The notebook carries an embedded copy of the package, so it needs
no repository access; if this Zenodo zip is uploaded to the Colab session instead,
the notebook uses it.

## Benchmark results of this release (seed 20260823, 6 × 8 runs, 17,280 events, 1,920 injected)

All 48 evidence chains verified; rejected events never changed the twin state.

| Scenario | Mode | Precision | Recall | F1 | FP / 1,000 normal |
|---|---|---|---|---|---|
| WAN failover | Rules | 0.913 ± 0.031 | 0.909 ± 0.038 | 0.911 ± 0.024 | 17.5 |
| WAN failover | Robust score | 0.819 ± 0.049 | 1.000 ± 0.000 | 0.900 ± 0.030 | 45.0 |
| WAN failover | Hybrid | 0.815 ± 0.053 | 1.000 ± 0.000 | 0.897 ± 0.032 | 46.2 |
| VPN degradation | Rules | 0.902 ± 0.035 | 0.953 ± 0.045 | 0.927 ± 0.039 | 20.6 |
| VPN degradation | Robust score | 0.791 ± 0.033 | 1.000 ± 0.000 | 0.883 ± 0.020 | 53.1 |
| VPN degradation | Hybrid | 0.791 ± 0.033 | 1.000 ± 0.000 | 0.883 ± 0.020 | 53.1 |
| Wi-Fi authentication surge | Rules | 0.915 ± 0.060 | 0.719 ± 0.068 | 0.803 ± 0.049 | 13.8 |
| Wi-Fi authentication surge | Robust score | 0.837 ± 0.073 | 0.844 ± 0.053 | 0.838 ± 0.038 | 34.4 |
| Wi-Fi authentication surge | Hybrid | 0.835 ± 0.073 | 0.844 ± 0.053 | 0.836 ± 0.036 | 35.0 |
| Power transition | Rules | 0.897 ± 0.029 | 1.000 ± 0.000 | 0.946 ± 0.016 | 23.1 |
| Power transition | Robust score | 0.143 ± 0.075 | 0.038 ± 0.013 | 0.059 ± 0.022 | 48.8 |
| Power transition | Hybrid | 0.795 ± 0.033 | 1.000 ± 0.000 | 0.886 ± 0.020 | 51.9 |
| Telemetry modification | Rules | 0.914 ± 0.047 | 1.000 ± 0.000 | 0.954 ± 0.026 | 19.4 |
| Telemetry modification | Robust score | 0.828 ± 0.036 | 1.000 ± 0.000 | 0.906 ± 0.022 | 41.9 |
| Telemetry modification | Hybrid | 0.826 ± 0.035 | 1.000 ± 0.000 | 0.904 ± 0.021 | 42.5 |
| Replay | Rules | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 21.9 |
| Replay | Robust score | 0.000 ± 0.000 | 0.000 ± 0.000 | 0.000 ± 0.000 | 46.9 |
| Replay | Hybrid | 0.811 ± 0.048 | 1.000 ± 0.000 | 0.895 ± 0.030 | 47.5 |

Executed ablation (`results/ablation_executed.csv`): integrity-only reaches
F1 = 1.000 for replay and telemetry modification and 0 elsewhere; rules + integrity
equals rules in the four operational scenarios. Executed sensitivity
(`results/sensitivity_executed.csv`): lowering the dispersion floor to 0.10 lifts the
robust-score F1 for power transition from ≈0.06 to ≈0.89 at τ = 3.2, as predicted
analytically in Table 7.

**Relation to the article's Table 5.** This package implements the methods,
constants and benchmark design exactly as specified in the article. The synthetic
generator's distributions are documented in `generator.py`; because they are an
independent implementation of the stated design, per-scenario numbers differ from
Table 5 in the second decimal place, while every qualitative finding is reproduced
(zero feature-only F1 for replay, integrity-attributed replay detection, robust-score
dilution for the binary power transition, rules ≥ robust for threshold-crossing
operational scenarios, sub-millisecond local append time, ≈46 ms vs ≈155–160 ms
generator sync latency). Report the numbers of the version you actually ran.

All result files are bit-identical across re-runs with the same seed except the
`append_median_ms` column, which is a wall-clock timing measurement of the host.

In the telemetry-modification scenario an on-path adversary alters a freshly signed
event and delivers it ahead of the original; identifier, sequence and chain remain
valid, so only the payload-hash or Ed25519 signature check rejects it, and the original
is then admitted (see `CHANGELOG.md`, v1.0.1).

Reference environment of this release: see `results/metadata.json`
(the article's run used CPython 3.11.8 and cryptography 42.0.5).

## Repository layout

```
metatwin_guard/      package (stdlib + cryptography)
tests/               unittest suite
scripts/             figure and workbook builders
results/             benchmark CSV/JSON outputs
figures/             PNG (360 dpi) + SVG
field_protocol/      S1 protocol, S2 workbook/schemas
notebooks/           Google Colab notebook
.zenodo.json  CITATION.cff  codemeta.json  references.bib  REFERENCES.md  LICENSE
```

## Zenodo record

This release is archived at https://doi.org/10.5281/zenodo.23557608. `.zenodo.json` supplies the title, creators with
ORCIDs, keywords, license and the article's 22 DOIs as `references` related identifiers.

## How to cite

Korchenko O, Prokopovych-Tkachenko D, Davydenko K, Askerov M, Herasymenko A, Zhurov Y. MetaTwin-Guard v1.0.1: Explainable and Verifiable Digital-Twin Assurance Backend for a Two-Site Cyber Range — Reference Software, Synthetic Benchmark, Colab Notebook and Field Protocol [Software]. Zenodo; 2026. doi: 10.5281/zenodo.23557608

The software accompanies the article cited above (Korchenko et al., *Metaverse*, under review);
the article's Data and code availability statement and reference [27] point to this DOI.

## License

Code: MIT (see `LICENSE`).
