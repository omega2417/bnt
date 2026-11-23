# Manuscript revision 1 — changes made

File: `Recovery_Evidence_Computers_and_Security_rev1.docx` (kept out of the Git repository;
the unpublished manuscript is delivered to the authors directly). The submitted draft is
unchanged. Edits are clean, not tracked; this list is the record.

## 1. Links and description

| Place | Change |
| --- | --- |
| Section 1, contribution (iv) | cites the archive (Prokopovych-Tkachenko, 2026a) and Supplementary Material S1 (2026b) |
| Section 4.1 | new sentence: each stream is drawn as one block of shape (T + 1) × m; order documented in `docs/RNG_STREAMS.md` of the archive |
| Section 4.6 | "supplementary material" → "Supplementary Material S1"; "80 files" → "95 files, of which 80 are logs and tables and 15 are figure files"; the `reproduce --check` command is named |
| Section 4.7 | new sentences: reported results are those of release 1.0.0; an earlier internal run with a different notice-stream order agreed within Monte Carlo error and is not reported |
| Data availability | placeholder replaced by the two Zenodo DOIs, the repository link, licences and the reproduction command |
| Appendix A | names the script `supplementary/worked_example.py` |
| Appendix B (new) | "Supplementary material": contents of S1 and both DOIs |
| References | two `[dataset]` entries added after Ouyang (2014) |

DOIs: complete archive https://doi.org/10.5281/zenodo.24466768; Supplementary Material S1
https://doi.org/10.5281/zenodo.24466855.

## 2. Numbers aligned with the archive

Tables 5, 6, 7 and 8 were refilled cell by cell from `results/tables/analysis.json`.
Figures 1–5 were replaced by the archived artwork; Fig. 4 with its heading and caption now
spans both columns. Text:

| Place | Draft | Revision 1 |
| --- | --- | --- |
| Abstract, Sections 5.1, 7: P3 − P1, false assurance | −0.54 [−0.72, −0.35]; 5.85 vs 5.31 | −0.42 [−0.60, −0.24]; 5.85 vs 5.43 |
| Abstract, Sections 5.2, 7: P3 − P1, false rejection | −1.97 [−2.19, −1.75] | −2.12 [−2.35, −1.90] |
| Section 5.1 | MCSE 0.094; about 9%; 2.9 service-days; SD 1.63; 56% / 3% / 41% | 0.092; about 7%; 2.3; 1.60; 54% / 4% / 42% |
| Section 5.2 | 6.36 → 4.39; 12.21 → 9.70 (−2.51 [−2.78, −2.24]); 84%; spells 1.68 vs 1.82; open spells "the same (47 versus 48)"; 8.0% → 7.1% | 6.47 → 4.35; 12.32 → 9.78 (−2.54 [−2.83, −2.26]); 83%; 1.73 vs 1.86; "fewer (36 versus 54)"; 8.0% → 7.2% |
| Section 5.3 | A 40.9; F 29.6; D and E "each 13.4"; re-check 5.59 vs 6.01 days | 40.8; 29.8; "13.5 and 13.3"; 5.55 vs 6.00 |
| Section 5.4 | P2 − P1 −0.42 [−0.59, −0.25]; P3 − P2 −0.12 [−0.29, 0.05]; FUSD −1.74 [−1.96, −1.52]; "both 1.72"; −0.47, −0.65 | [−0.59, −0.26]; 0.01 [−0.16, 0.17]; −1.90 [−2.11, −1.69]; "P2 1.71 and P1 1.72"; −0.43, −0.64 |
| Section 5.5 | −0.54, −0.57, −0.65; 1.07 vs 1.72, about 38% | −0.42, −0.64, −0.64; 1.08 vs 1.72, about 37% |
| Section 5.6, C5 | −0.18 [−0.30, −0.07]; P3 − P2 −0.02 [−0.13, 0.10] | −0.24 [−0.37, −0.11]; −0.04 [−0.16, 0.08] |
| Section 5.6, C4, C6 | −0.89 [−1.14, −0.64]; −0.98 [−1.22, −0.74] | −0.82 [−1.10, −0.54]; −1.02 [−1.28, −0.77] |
| Section 5.6, notice weight | w = 3: −1.15; w = 14: −0.44; FUSD range −1.01 to −3.85 | −1.23; −0.38; −0.98 to −3.85 |
| Section 5.6, C8 | spells 34–35 vs 10–15 days; −0.42 [−0.59, −0.25] | 34 vs 9–15 days; −0.40 [−0.56, −0.24] |
| Section 5.6, C7 | −0.17 [−0.34, −0.004] | −0.25 [−0.41, −0.09] |
| Section 5.6, C9 | −0.55 [−0.72, −0.37] | −0.45 [−0.61, −0.29] |

## 3. Statements reworded because the conclusion shifted

1. **Static importance (abstract, Sections 5.4, 6.2, 7).** "captured most of the gain in false
   assurances" → "captured the whole gain in the primary configuration": P3 − P2 is 0.01 per
   100 with an interval that includes zero.
2. **Joint failure, C7 (Section 5.6).** "nearly removed the advantage … only just excludes
   zero" → "reduced the advantage to −0.25 per 100 (−0.41 to −0.09)"; "offsets the gains" →
   "offsets part of the gains".
3. **Map error, C8 (Section 5.6).** Added: the difference from the static rule is no longer
   distinguishable from zero (−0.11; −0.25 to 0.04).
4. **Budget (Section 5.5).** "was similar at b = 1, 2 and 4" → "did not shrink with the budget".
5. **Abstract.** "became small when notices were complete…" → "became smaller".
6. **Section 6.1.** "about half a service-day per 100" → "about 0.4 service-days per 100".

## 4. Left for the authors

* Yellow placeholders: affiliations and ORCID, CRediT statement, acknowledgements, ChatGPT
  version in the AI declaration, status of the CRTM-OIS reference; competing-interest and
  funding statements still need confirmation.
* The two new references name one creator, as the Zenodo records do. If co-authors are added
  to the records, change the entries and the in-text citations.
* Zenodo record 10.5281/zenodo.24466670 has the title of the complete archive but contains the
  S1 file; the description of record …855 points to it. Correct or withdraw it.
* In the sentence added to Section 4.1 the expression (T + 1) × m is plain text, not an
  equation object.
