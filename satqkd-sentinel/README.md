# SatQKD-Sentinel v2.0.0

Simulation, telemetry analytics and geostationary-backbone toolkit for satellite QKD networks with optical phased arrays.

Software accompanying the article *AI-Driven Telemetry Analytics for Cybersecurity of Satellite Quantum Key Distribution Networks with a Geostationary Backbone and Optical Phased Arrays: Architecture, Link Modelling and Fault-Attack Discrimination* (Information, MDPI).

## Modules

| Module | Content | Article elements |
|---|---|---|
| `satqkd_sentinel.linkmodel` | Slant range, link budget, decoy-state BB84 asymptotic key rate, pass geometry | Equations (1)-(9), Table 2, Section 4.2, Table 5 (K_inf), Figure 9 |
| `satqkd_sentinel.finitekey` | Decoy-state finite-key bound with statistical fluctuation analysis | Equation (10), Table 5 (K_finite), Figures 8, 10, 16 |
| `satqkd_sentinel.opa` | Optical phased array: array factor, beam steering, phase errors | Equations (12)-(16), Figure 6 |
| `satqkd_sentinel.network` | Trusted-relay network: key store, availability, daily key budget | Equations (17)-(22), Figure 11, Section 4.3 |
| `satqkd_sentinel.geo` | Geostationary coverage, ring links, relay-backbone visibility, contact plan | Equations (28)-(32), Table 7, Figures 4, 17-19 |
| `satqkd_sentinel.telemetry` | Simulator of the ten link states (nominal, 5 faults, 4 attacks) | Section 3.6, Table 3, Equations (23)-(24), Figure 12 |
| `satqkd_sentinel.features` | 24 physics-informed features from four source groups | Equations (25)-(26), feature dictionary |
| `satqkd_sentinel.models` | Gradient boosting, random forest, logistic regression, isolation forest, Mahalanobis | Equation (27), Table 6, Figures 13-16 |
| `satqkd_sentinel.evaluation` | Full evaluation pipeline with alarm logic, block policies, leave-one-out | Sections 4.5-4.8 |
| `scripts/` | Figure and table generators | Figures 3-5, 9, 17-19; Table 7 |
| `tests/` | Regression tests against the numbers printed in the article | Sections 4.2 and 4.9 |
| `notebooks/` | Comprehensive demonstration notebook | All modules, all visualisations |

## Quick start

```bash
python -m pip install -r requirements.txt
make test       # regression tests
make tables     # prints the link numbers, writes results/geo_table.json
make figures    # writes figures/*.png at 300 dpi
```

## Demonstration notebook

The notebook `notebooks/demo_satqkd_sentinel.ipynb` provides a complete walkthrough of all modules with interactive calculations, visualisations and conclusions. To run it:

```bash
jupyter notebook notebooks/demo_satqkd_sentinel.ipynb
```

Or execute it non-interactively:

```bash
make notebook
```

## Status of the results

All numbers are model estimates under the assumptions of Table 2 and Table 4 of the article. No experimental data are included. The telemetry simulator generates synthetic data for demonstration purposes. The contact plan uses two-body motion and ideal station keeping.

## Licence and citation

Code: MIT. Figures and result files: CC BY 4.0. Please cite the article and this record (see `CITATION.cff`).
