# Manuscript integration pack

These files are the revised text, tables and declarations to fold back into
`Manuscript_v02`. Each section says exactly what it replaces. Numbers are drawn
from `results/summary.json` and the `results/table_S*.csv` files, so they update
automatically when `data/` is replaced with real measurements and
`make analysis` is re-run.

| File | Replaces / adds |
|---|---|
| `01_abstract.md` | the Abstract |
| `02_methods.md` | §2.6–2.8 additions: implementation mapping, parameters, attack recipes, protocol |
| `03_mathematics.md` | corrections to Eq. 7, Eq. 8, graph normalisation, Eq. 12–13 |
| `04_results.md` | §3.1–3.6 rebuilt from primary data, with the new tables |
| `05_references_audit.md` | the DOI audit and the Related Work additions |
| `06_declarations.md` | Data Availability, AI disclosure, CRediT, and the MDPI checklist |
| `tables/` | CSV → Markdown renderings of every results table |

**Editorial hygiene.** Before submission, remove from the manuscript every
editorial phrase left over from the revision process: "supplied manuscript",
"supplied dataset", "during this revision", "authors should provide", "require
author review", "to be completed before submission". Update the DOCX metadata
(creator, title, subject, authors, description) and drop the "Working manuscript
version 02" description string.
