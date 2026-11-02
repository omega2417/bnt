# MRPiPS source tables

Place the 88 spreadsheets downloaded from
https://psz.praca.gov.pl/rynek-pracy/statystyki-i-analizy/zatrudnianie-cudzoziemcow-w-polsce
(accessed 2026-10-25) in this folder, unchanged.

`source_inventory.csv` has one row per file:

| column | content |
|---|---|
| file | file name in this folder |
| url | download URL |
| series | permits / declarations / declaration_persons / seasonal / notifications |
| period | e.g. 2019, 2019H1, 2021-01..2021-12 |
| frequency | annual / halfyear / monthly |
| download_date | YYYY-MM-DD |
| sha256 | filled in by `code/download_sources.py` |
| use | 1 = read; 0 = superseded (e.g. the original 2021 tables, replaced by the revision published in 2025) |
| revision_note | free text |

`table_map.csv` tells `code/01_import_mrpips.py` how to read each sheet:

| column | content |
|---|---|
| file, sheet | file name and sheet (name or 0-based index) |
| series, frequency, year, half | what the sheet contains |
| header_row | 1-based row number of the header |
| citizenship_col | column with the citizenship (Excel letter such as `B`, or header text) |
| layout | `long` (one value column), `wide_months` (12 columns), `wide_halves` (2 columns) |
| value_cols | value column(s), `|`-separated, in month or half-year order |

Rows such as "Ogółem" / "Razem" are skipped automatically. Labels that do not match the
crosswalk stop the import and are listed in `output/logs/unmatched_citizenships.csv`.

If the right to redistribute the tables directly is in doubt, leave the spreadsheets out of the
deposit. Keep the inventory, with URLs and SHA-256, so that `code/download_sources.py` can
retrieve and verify them.
