# Codebook

All files are CSV, UTF-8, comma-separated, with a dot as the decimal mark. Missing values are
written as `NA`. Polish citizenship labels are kept in a separate column (`polish_name`).
Variable-level definitions (name, label, type, unit, source, construction) are in
`variables.csv`; they are also reproduced as Online Appendix Table A13.

## Key conventions

* **Unit of observation**: an administrative document (issued permit, registered declaration,
  issued seasonal permit, filed notification), classified by the citizenship of the foreigner.
  Documents are not unique persons. A person can appear several times within a channel and in
  more than one channel.
* **Zero versus NA**: `0` means the channel existed and no documents were recorded. `NA` means
  the channel did not exist in that period (seasonal permits before 2018, notifications before
  2022, monthly permits before 2021). Cross-channel totals sum the channels in operation.
* **Origins**: ISO 3166-1 alpha-3; special codes `XKX` (Kosovo), `XXS` (stateless) and `XXU`
  (unknown). Mapping from MRPiPS labels: `data/crosswalks/citizenship_crosswalk.csv`
  (`polish_name` plus `|`-separated `polish_aliases`).
* **Six declaration origins**: ARM, BLR, GEO, MDA, RUS, UKR (`decl_ever = 1`).
* **Policy shares**: the share of calendar days in a year on which a right applied, computed
  from `data/policy/access_spells.csv` by `code/02_harmonise.py`.
* **Timing**: covariates are lagged one year. The recent flow uses t−1 to t−3 and the older
  flow t−4 to t−6. Estimation years are 2011–2025.

## Files

| File | Unit | Produced by |
|---|---|---|
| `data/derived/mrpips_long.csv` | sheet row × period | 01 |
| `data/derived/panel_origin_year.csv` | origin × year, 2008–2025 | 02 |
| `data/derived/halfyear_permits.csv` | origin × half-year | 02 |
| `data/derived/monthly_national.csv` | month | 02 |
| `data/derived/monthly_origin.csv` | origin × month × series | 02 |
| `data/derived/declaration_persons.csv` | origin × year, 2019–2025 | 02 |
| `data/derived/zus_stock.csv` | year | 02 (from report extracts) |
| `data/policy/policy_coding.csv` | origin × year | 02 |
| `data/derived/panel_covariates.csv` | origin × year | 03 |
| `data/derived/regression_sample.csv` | origin × year, 2011–2025 | 03 |
