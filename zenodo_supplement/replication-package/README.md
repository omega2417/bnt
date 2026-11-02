# Replication package: Admission channels and origin diversification in Polish labour migration, 2008–2025

[Authors]. [Year]. "Admission channels and origin diversification in Polish labour migration from 2008 to 2025." *Journal of Ethnic and Migration Studies*. doi:[article DOI]

Package DOI: doi:10.5281/zenodo.[XXXXXXX] · Version 1.0.0 · [date]

> **Status of this copy (anonymised, for review).** Author names, ORCID iDs and DOIs are
> placeholders in square brackets. Files that still need the authors' input are listed in
> section *Completeness* below. Remove this note before publishing the Zenodo record.

## Overview

The code in this package builds an origin-by-year panel of Polish work-authorisation documents
for 2008–2025: work permits, employer declarations, seasonal work permits and notifications of
employment of Ukrainian citizens. It reproduces Tables 2–6, Figures 1–5 and Online Appendix
Tables A1–A14. Running `python code/run_all.py` from the package root reproduces all outputs in
approximately [N] minutes on [hardware]. The pairs bootstrap (999 draws) and the placebo event
studies take most of that time.

The unit of observation is an **administrative document, not a unique person**. The data are
aggregated by citizenship and contain no individual-level records.

## Data availability and provenance

| Source | Content | Access | Licence / terms | Included |
|---|---|---|---|---|
| MRPiPS, Public Employment Services portal | 88 statistical tables (2007–2025) | https://psz.praca.gov.pl/rynek-pracy/statystyki-i-analizy/zatrudnianie-cudzoziemcow-w-polsce, accessed 2026-10-25 | Polish public-sector information; re-use with attribution (Act of 11 August 2021 on open data and the re-use of public-sector information) | [Yes / download script] — see `data/raw/mrpips/source_inventory.csv` |
| MRPiPS reports 2025a, 2025b, 2026 | ZUS stocks, document holders, applications, processing times | URLs in the article's references | as above | Extracts: `data/raw/mrpips_reports/` |
| World Bank WDI | NY.GDP.PCAP.KD.ZG, NY.GDP.PCAP.PP.CD, NY.GDP.PCAP.CD, SL.UEM.TOTL.ZS, SP.POP.TOTL; 2006–2025 | https://api.worldbank.org/v2/, accessed 2026-10-25 | CC BY 4.0 | Snapshot: `data/raw/worldbank/` |
| GeoNames | cities15000, countryInfo | https://download.geonames.org/export/dump/, accessed 2026-10-25 | CC BY 4.0 | Snapshot: `data/raw/geonames/` |
| REST Countries | regional coding (Figure 2) | https://restcountries.com/, [version/date] | MPL 2.0 (REST Countries project) | Snapshot: `data/raw/restcountries/` |
| Legal acts (Dziennik Ustaw) | policy coding | https://isap.sejm.gov.pl/ | public | Coded in `data/policy/` |

All data are aggregated by citizenship. No individual-level or personal data are included.

**Zero versus NA.** `0` means that a channel existed but no documents were recorded for the
origin. `NA` means that the channel did not yet exist (seasonal permits before 2018,
notifications before 2022). The `channel_available_*` columns make this explicit.

## Computational requirements

* Python ≥ 3.10 with numpy, pandas, scipy, statsmodels, matplotlib, openpyxl, python-docx
  (`pip install -r environment/requirements.txt`). LibreOffice (optional) converts the Online
  Appendix to PDF/A.
* Estimates in the article: [Stata 18 MP with ppmlhdfe [version], reghdfe [version], ftools
  [version]]. The Python scripts are a complete re-implementation. Before publication they must
  reproduce the published numbers; see `environment/software.md`.
* Random seed: 20261025 (set in `code/00_config.py`). Memory: < 2 GB. Runtime: [ ] minutes.

## Directory structure

```text
README.md  CITATION.cff  LICENSE-data.txt  LICENSE-code.txt  CHECKSUMS.sha256  .zenodo.json
codebook/        codebook.md, variables.csv
data/raw/        mrpips/ (source tables, source_inventory.csv, table_map.csv), worldbank/,
                 geonames/, restcountries/, mrpips_reports/ (report extracts, ZUS stock)
data/crosswalks/ citizenship_crosswalk.csv
data/policy/     legal_acts.csv, access_spells.csv, policy_coding.csv, document_duration.csv
data/derived/    panels produced by code/01–03
code/            00_config.py … 11_build_appendix.py, run_all.py, download_sources.py, lib/
output/          tables/, figures/, logs/
appendix/        Online_Appendix.pdf (+ .docx source), table_specs.json, draft_tables/
environment/     software.md, requirements.txt
tests/           smoke_test.py (synthetic data; checks that the pipeline runs)
```

## Description of programs

| Script | Purpose | Outputs |
|---|---|---|
| `00_config.py` | paths, seed, sample definitions, windows | — |
| `download_sources.py` | download / verify sources (`--verify`, `--discover`) | `data/raw/*`, checksums |
| `01_import_mrpips.py` | read the MRPiPS tables, harmonise citizenship names | `data/derived/mrpips_long.csv` |
| `02_harmonise.py` | panels; structural NA vs zero; policy coding | `panel_origin_year.csv`, `halfyear_permits.csv`, `monthly_national.csv`, `monthly_origin.csv`, `declaration_persons.csv`, `zus_stock.csv`, `policy_coding.csv` |
| `03_covariates.py` | relative real income, PPP gap, unemployment, distance, lagged flows; sample flags | `panel_covariates.csv`, `regression_sample.csv` |
| `04_concentration.py` | HHI, 1/HHI, segmented trends, duration weighting | Table 2, A3, A10 |
| `05_ppml.py` | PPML gravity models | Tables 3–4, A7 |
| `06_bootstrap.py` | group-difference inference: 999 pairs draws, wild cluster score bootstrap | A6 |
| `07_event_studies.py` | event studies, DiD summaries, placebo inference | Figure 4, Table 5, A8 |
| `08_its.py` | interrupted time series with standard errors; 2025 comparisons | Table 6, A9, A11 |
| `09_figures.py` | figures (PDF + PNG 300 dpi) | Figures 1–5 |
| `10_appendix_tables.py` | descriptive appendix tables; software versions | A1–A5, A12–A14 |
| `11_build_appendix.py` | Online Appendix DOCX → PDF/A | `appendix/Online_Appendix.pdf` |
| `run_all.py` | master script; records runtimes | `output/logs/runtime.csv` |
| `make_crosswalk_template.py` | one-off: generated the first crosswalk version | — |

## Instructions to replicators

1. Install the requirements: `pip install -r environment/requirements.txt`.
2. Optional: `python tests/smoke_test.py` runs the full pipeline on synthetic data in a temporary
   folder. This checks the installation only; its numbers are meaningless.
3. If the raw MRPiPS files are not included, run `python code/download_sources.py`. Then check
   the SHA-256 values with `python code/download_sources.py --verify`. If MRPiPS has revised a
   table since 2026-10-25, the script reports a checksum mismatch.
4. Run `python code/run_all.py` from the package root. All outputs are written to `output/`, and
   the Online Appendix to `appendix/`.

## List of tables and figures

| Exhibit | Program | Output file |
|---|---|---|
| Table 1 | — (legal compilation) | `data/policy/legal_acts.csv` |
| Table 2 | 04_concentration | `output/tables/table2.csv` |
| Table 3 | 05_ppml | `output/tables/table3.csv` |
| Table 4 | 05_ppml | `output/tables/table4.csv` |
| Table 5 | 07_event_studies | `output/tables/table5.csv` |
| Table 6 | 08_its | `output/tables/table6.csv` |
| Figures 1–5 | 09_figures | `output/figures/figure1–5.pdf/.png` |
| Tables A1–A14 | 04–10 | `output/tables/appendix_A*.csv` (+ `.tex`) |
| Online Appendix | 11_build_appendix | `appendix/Online_Appendix.pdf` |

## Completeness (remove this section before publication)

This version does **not** yet contain:

* the 88 MRPiPS spreadsheets, or their URLs and checksums in `source_inventory.csv`, plus the
  sheet layouts in `table_map.csv`;
* the World Bank, GeoNames and REST Countries snapshots used for the article (dated 2026-10-25);
* the derived panels in `data/derived/` (these are produced by steps 01–03);
* the complete ZUS series 2013–2025 and holders by citizenship (`data/raw/mrpips_reports/`);
* `output/` and the final, non-draft `appendix/Online_Appendix.pdf`.

Fields marked `verify_note` in `data/policy/*.csv` need exact in-force dates.

## Citation

Please cite both the article and this package (see `CITATION.cff`).

## Licences

Data and documentation: CC BY 4.0 (`LICENSE-data.txt`). Code: MIT (`LICENSE-code.txt`).
Third-party snapshots remain under their own terms (table above).
