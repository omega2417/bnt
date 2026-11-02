# Software and runtime

## Reference implementation (this package)

| Item | Version |
|---|---|
| Python | 3.13 (tested); ≥ 3.10 required |
| numpy / pandas / scipy | see `requirements.txt` (pinned versions used for the smoke test) |
| statsmodels | OLS with Newey-West (HAC) and clustered standard errors |
| matplotlib | figures |
| openpyxl | reading the MRPiPS `.xlsx` tables (`xlrd` is also needed for legacy `.xls` files) |
| python-docx + LibreOffice 24.2 | Online Appendix DOCX → PDF/A-2b |
| Random seed | 20261025 (`code/00_config.py`) |

PPML is implemented in `code/lib/ppml.py` with explicit fixed-effect dummies and IRLS. The
clustered variance uses the G/(G−1) correction, as `ppmlhdfe` does. Fixed-effect groups with
only zero outcomes are dropped iteratively. `ppmlhdfe` also runs a ReLU separation check, so if
the number of observations differs from the Stata log, that check is the first thing to
compare.

## Software used for the published estimates (authors to complete)

| Item | Version |
|---|---|
| Operating system | [ ] |
| Stata | [e.g. Stata 18 MP] |
| ppmlhdfe | [version] |
| reghdfe | [version] |
| ftools | [version] |
| Other | [ ] |

If the published numbers came from Stata, put the original `.do` files in `code/stata/`. Then
either (a) state that the Python scripts reproduce the published numbers to the reported
precision, or (b) state which script is authoritative.

## Runtime

Smoke test on synthetic data (164 origins, 49 pairs draws / 199 wild draws), on a cloud
container with 4 vCPU: 13 minutes in total. Most of it is the event-study placebos
(about 10 minutes with 115 comparison origins) and the wild-bootstrap test inversion
(about 3 minutes). With the full 999 pairs draws, allow roughly 30–40 additional minutes.
Real-data runtime: [ ] minutes on [hardware] (written to `output/logs/runtime.csv`).
