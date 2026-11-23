# Released results

Output of `recovery-evidence reproduce` (CPython 3.13.18, NumPy 2.5.3, Matplotlib 3.11.2).
Regenerate and compare with `recovery-evidence reproduce --check`.

| Path | Content |
| --- | --- |
| `control_checks.txt` | the 27 implementation checks of Section 4.6 |
| `parameters.json` | resolved configuration of C0–C12 (Table 4) |
| `logs/<Cx>/` | primary logs and per-trajectory summaries |
| `tables/` | Tables 5–8, statistics, integrity report, claim-to-evidence register |
| `figures/` | Figures 1–5 (`.pdf` vector, `.tif` 1000 dpi, `.png` 600 dpi) |
| `SHA256SUMS.txt` | digests of all 95 files |

Column definitions: `../docs/DATA_DICTIONARY.md`. All values are synthetic model output about
the correctness of readiness records; see `../docs/COMPONENT_STATUS.md`.

Data, tables and figures: CC BY 4.0.
