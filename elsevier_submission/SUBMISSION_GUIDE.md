# Submission package — *Digital Business* (Elsevier)

Manuscript: **Cognitive optimisation of AI-supported SME decisions through risk-based allocation of managerial attention**

| File | Purpose |
|---|---|
| `Manuscript_RBAA_DigitalBusiness.docx` | Final manuscript, clean text (no tracked changes, comments or colour marking), Elsevier back matter, line numbers |
| `Highlights.docx` | Five highlights (each ≤ 85 characters), uploaded as a separate file in Editorial Manager |
| `rbaa-sim-v1.1.0.zip` | Software package 1 — new version of Zenodo record 10.5281/zenodo.23421069 |
| `rbaa-validation-v1.1.0.zip` | Software package 2 — new version of Zenodo record 10.5281/zenodo.23421157 |
| `rbaa-benchmark-v1.0.0.zip` | Software package 3 — new Zenodo record; also uploaded as **Supplementary Material S1** |
| `ZENODO_TEXTS.md` | Title, version, description, keywords, creators/contributors and notes for each Zenodo form |
| `set_dois.py` | Inserts the three reserved Zenodo DOIs into the manuscript and the archives |

## 1. The three software packages and their place in the article

| Package | Reproduces | Built-in checks (archived run) |
|---|---|---|
| **rbaa-sim 1.1.0** (Prokopovych-Tkachenko, 2026a) — Colab/Jupyter notebook, no empirical data | Eqs. (1)–(3), Table 2 routing, **Table A1**, **Table 7**, Appendix A derivatives and optima (e\* = 0.592/0.393/0.307/0.218; eₘ = 0.592/0.534/0.485/0.404), **Figure A1**, **Figure A2**, analysis plan of Appendix C.9 on synthetic data (format of **Table 8**) | 36 / 36 passed |
| **rbaa-validation 1.1.0** (Prokopovych-Tkachenko, 2026b) — Colab/Jupyter notebook, downloads public data | **Appendix B**, **Figures B1–B3** (Eurostat context and archived back-test) | 5 / 5 passed; all 14 numbers printed in Appendix B reproduced |
| **rbaa-benchmark 1.0.0** (Prokopovych-Tkachenko, 2026c) — Python scripts + Colab runner, downloads public data | **Section 5**, **Tables 3–4**, **Figures 2–3**, robustness (324 scenarios, calibration, classifiers), price of the hard floor, Appendix B re-run paragraph | 74 / 74 numbers quoted in the article reproduced |

### Where the Zenodo links appear in the manuscript

| Location in the manuscript | What is cited |
|---|---|
| **Section 3.1**, paragraph "Three kinds of material…" | refers to the packages and to Section 3.3 |
| **Section 3.3 "Software and reproducibility"** (new) | full description of the three packages with their three DOIs |
| **Section 5.1**, first paragraph | rbaa-benchmark (2026c) as the code of the comparative validation |
| **Sources of Table 3, Figure 2, Table 4, Figure 3** | "authors' calculations with rbaa-benchmark (Prokopovych-Tkachenko, 2026c)" |
| **Section 5.5** and **Section 6.3** | rbaa-sim 1.1.0 implements the Appendix C protocol on synthetic data |
| **Appendix A** (text, Figure A1 and A2 sources, Table A1 and Table 7 notes) | rbaa-sim (2026a) |
| **Appendix B** (Figure B1 text, archived back-test paragraph, re-run paragraph, Figures B2–B3 sources) | rbaa-validation (2026b) and rbaa-benchmark (2026c) |
| **Data availability** statement | the three new DOIs and the two v1.0.0 DOIs (23421069, 23421157), data licence and SHA-256 |
| **References** | Prokopovych-Tkachenko, D. (2026a), (2026b), (2026c) with DOIs |

## 2. Zenodo upload — recommended order

1. **rbaa-sim:** open record 10.5281/zenodo.23421069 → *New version* → under *Digital Object Identifier* click
   *Get a DOI now!* and copy the reserved DOI. Do **not** publish yet.
2. **rbaa-validation:** record 10.5281/zenodo.23421157 → *New version* → reserve the DOI.
3. **rbaa-benchmark:** *New upload* → reserve the DOI.
4. In this folder run
   `python set_dois.py --sim 10.5281/zenodo.<sim> --val 10.5281/zenodo.<val> --ben 10.5281/zenodo.<ben>`.
   The script writes the DOIs into the manuscript (Section 3.3, Data availability, references), into the
   `CITATION.cff` and `.zenodo.json` files inside the three zip archives and into `ZENODO_TEXTS.md`. It reports
   "placeholders left in the manuscript: none" when complete.
5. Upload the updated zip files to the three drafts, fill each form from `ZENODO_TEXTS.md` (upload type *Software*,
   licence *MIT*, version as stated, creator and contributors as listed) and publish.
6. Submit `Manuscript_RBAA_DigitalBusiness.docx`, `Highlights.docx` and `rbaa-benchmark-v1.0.0.zip`
   (as Supplementary Material S1) in Editorial Manager. In the *Research data* step, link the three Zenodo DOIs.
7. After acceptance, add the article DOI to each Zenodo record as a related identifier ("is supplement to").

## 3. Changes made to the manuscript (R2 → final)

* Elsevier format: MDPI/*Administrative Sciences* header banner and footer removed; "Conceptual research article"
  label removed; hyphenation of the title and of the Section 4 heading corrected; keywords reduced to seven; CRediT
  authorship contribution statement; standard Elsevier declaration of competing interest; funding sentence on the APC
  removed; Data availability statement rewritten; continuous line numbers; Highlights file added.
* All revision marking removed (369 blue runs, the open editorial comment, and the comment parts); captions
  harmonised (bold label, regular text); Hypotheses 3 and 4 typeset like Hypotheses 1, 2 and 5; the generative-AI
  declaration in the declaration style.
* New **Section 3.3 "Software and reproducibility"** describing the three packages.
* Corrections found by re-running the code:
  * SHA-256 of the transaction file: `76274b69…51a89` (the R2 value `33a178be…` did not match the public file used by
    all three packages);
  * the constrained €1,000-floor variant: −€24,675.58 (not −€24,675.56);
  * Section 5.4: the shadow price refers to twenty additional *reviews* (200 review minutes), €1.66 per review minute;
  * Section 5.2: point estimates and bootstrap means are now distinguished (RBAA − AI-score queue €31.0, bootstrap
    mean 30.9; classifier threshold shortfall €19.1, bootstrap mean 18.3; load-awareness €3.2 and €5.2, bootstrap means
    3.3 and 5.0);
  * Section 5.3: with flattened probabilities (slope 0.5) RBAA also fell below the AI-score queue without a shift
    (€10.8), not only with shift +1;
  * Sections 5.5 and 6.3: the synthetic pipeline is no longer "to be updated" — rbaa-sim 1.1.0 implements the revised
    estimands of Appendix C;
  * Figure A2 regenerated (legend now refers to Table 7);
  * references: Prokopovych-Tkachenko (2026a–c) updated/added; uncited March & Shapira (1987) removed; Buçinca moved to
    its alphabetical position.

## 4. Changes made to the software packages

* **rbaa-sim 1.1.0:** article title/journal; numbering aligned with the article (Table 5 → 7, Table 6 → 8, protocol
  sections → Appendix C); admissible-interval computation of e\* and eₘ with a check against Appendix A; Figure A1 and
  Figure A2 exported as printed; synthetic pipeline aligned with Appendix C (stratified probability audit with
  inclusion probabilities and Horvitz–Thompson estimator, operation-weighted secondary estimand, H2b on total
  managerial time per operation, H3a escape rate with autonomous vs human escapes, H4 primary threshold-policy
  contrasts with the quadratic model secondary and without IV, carry-over sensitivity, firm-level H5).
* **rbaa-validation 1.1.0:** article title/journal; Eurostat values aligned with Eurostat (2026b), Figure 1, and
  Figure B1 redrawn from them; neutral size-class framing; bootstrap *tail proportion* instead of *p*-value; check that
  all 14 Appendix B values are reproduced; Ukrainian text removed from README and report. Back-test computations
  unchanged.
* **rbaa-benchmark 1.0.0** (former Supplementary S1 scripts): data download with checksum, Python-3.13/scikit-learn-1.9.1
  environment record, Figures 2–3 drawn from results (no hard-coded values), Tables 3–4 assembled automatically, check of
  74 numbers quoted in the article, Colab runner, README, licence, citation and Zenodo metadata.

## 5. Items for the authors to confirm before submission

* **Affiliation 3** (I. Britchenko): the text gives the Higher School of Business (WSB-NLU) in Nowy Sącz, while the
  e-mail domain is up.krakow.pl. The text was left unchanged; please confirm.
* The Zenodo records list D. Prokopovych-Tkachenko as creator and the five co-authors as contributors, consistent with
  the Data availability statement. Change both together if all authors should be creators.
