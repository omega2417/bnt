# `manuscript/`

## Why there is no rewritten `Man-V3` here

Section 16 of the review protocol is explicit: the manuscript is rewritten **only
after Gate 5**, and the empirical section is replaced with results from the real
confirmatory dataset. Gate 0 and Gate 1 are open, so the physical dataset does not
exist. Producing a "revised manuscript" now would mean either leaving the old,
unsupported numbers in place or substituting simulation values for testbed
measurements. Both are excluded by the integrity rules of the protocol
(sections 2.1-2.3).

What **can** be delivered without physical data is everything that is a matter of
mathematics, specification or scholarly record. That is delivered here.

| Deliverable | File | Depends on physical data? |
|---|---|---|
| Corrected equations and definitions, ready to paste | `corrected_equations.md` | no |
| Full defect list with quantitative evidence | `../docs/manuscript_corrections.md` | no |
| Adjudication of every legacy headline number | `../docs/issue_evidence_correction_matrix.md` | no |
| Rewritten Experimental Setup | — | **yes** (Gate 1 inventory act) |
| Rewritten Results, tables and figures | — | **yes** (Gate 4 confirmatory campaign) |
| Revised Abstract and Conclusions | — | **yes** (they quote the results) |

## Order of work once the physical campaign completes

1. Close Gate 0 and Gate 1; write §2.6 from the signed inventory act, never from the
   cyber-range narrative. Remove every component that the act does not list.
2. Apply `corrected_equations.md` to §2.3-§2.5 and §2.8. These edits are independent
   of the data and can be made now.
3. Run Gates 2-5 on the physical range under `../protocol/preregistration.yaml`,
   unchanged. Do not re-tune parameters between the pilot and the confirmatory
   series.
4. Regenerate §3 by pointing `analysis/reproduce.sh` at `data/real/`. No analysis
   code changes: the pipeline reads the schema in `../processed/data_dictionary.md`.
5. Every table gets `n`, SD or IQR, 95% CI, effect size, Holm-adjusted p and units;
   every latency figure gets its censored count beside it.
6. Add Threats to Validity covering the two-site limit, the specific equipment,
   laboratory injections, scale, operator effects, drift and transferability.
7. Fix the Data Availability statement and the repository link (defect C10); verify
   the link in a signed-out browser.
8. State in the generative-AI declaration exactly what the tools were used for. They
   are not a source of experimental facts or of unverified references.

## Scope of the claim

The facility is two sites. Whatever the physical campaign shows, the manuscript's
title, abstract and conclusions must claim **proof-of-concept validity on a two-site
laboratory cyber range**, not universal production validity for smart-region
infrastructure.
