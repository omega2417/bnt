# Submission notes for *Computers & Security* (Elsevier)

How the package maps onto the journal's submission items, with text that can be pasted into
the manuscript. Requirements are summarised from Elsevier's general author and artwork
instructions; check them against the journal's current Guide for Authors before submitting.

## 1. Items and where they come from

| Submission item | Provided by | Open point for the authors |
| --- | --- | --- |
| Research data / software in a repository with a persistent identifier | `make release` → `dist/recovery-evidence-1.0.0.zip`; `.zenodo.json`, `CITATION.cff`, `codemeta.json` | deposit, mint the DOI, insert it in the data statement, `CITATION.cff` and the reference list |
| Data availability statement | section 2 below | insert DOI |
| Data/software citation in the reference list | section 3 | insert DOI |
| Supplementary material (e-component) | `make supplement` → `dist/Supplementary_Material_S1.zip` | upload as "Supplementary material"; cite as "Supplementary Material S1" in the text |
| Figures as separate files | `results/figures/Figure1…5.{pdf,tif}` | upload PDF (vector) or TIFF; do not embed in the manuscript only |
| Figure captions and table descriptions | sections 5 and 6 | — |
| Highlights (3–5 bullets, at most 85 characters each) | section 7 | — |
| Declarations (competing interest, funding, CRediT, generative AI) | manuscript | still placeholders in the draft |
| Author details | manuscript title page | affiliations and ORCID of two authors are placeholders; add them to `CITATION.cff` and `.zenodo.json` too |
| Agreement between article and archive | `results/tables/manuscript_alignment.md` | **replace the listed numbers in Tables 5–8 and in the text**; reword the three statements in `REPRODUCIBILITY.md` |

## 2. Data availability statement

> The simulation and analysis code, the configuration of all conditions, the primary logs
> (hidden states, notices, checks and verdicts), the summary tables, the figures, the 27
> implementation checks and a register that links every reported number to its source file
> are openly available in Zenodo at https://doi.org/10.5281/zenodo.XXXXXXX (version 1.0.0;
> code under the MIT licence, generated data under CC BY 4.0). The command
> `recovery-evidence reproduce --check` regenerates all outputs and compares them with the
> published SHA-256 digests. The study uses no personal or confidential data.

## 3. Reference-list entry

> [dataset] Torstensson, O., Prokopovych-Tkachenko, D., Khokhlachova, Y., 2026.
> recovery-evidence: simulation code, primary logs and analysis for prioritizing
> recovery-evidence verification under limited audit capacity, version 1.0.0. Zenodo.
> https://doi.org/10.5281/zenodo.XXXXXXX

Cite it where the code is first mentioned (Section 1, contribution iv) and in Section 4.6.
The `[dataset]` tag is removed by the publisher at typesetting.

## 4. Statements in the article that refer to the package

| Article text | In this package |
| --- | --- |
| "27 automated checks (file `control_checks.txt`)" | `results/control_checks.txt`, 27 checks, all pass |
| "The analysis script does not import the simulator" | `analysis.py`; enforced by `test_analysis_does_not_import_the_simulator` |
| "All comparisons agreed in all 13 conditions" | `results/tables/integrity_report.txt` |
| "A full second run … produced byte-identical output files (80 files compared by SHA-256; only the run manifest … differs)" | 80 log and table files plus 15 figure files, 95 in total, are byte-identical on a second run. Suggested wording: "95 files compared by SHA-256, of which 80 are logs and tables" |
| "dependency-free script in the supplementary material" | `supplementary/worked_example.py` |
| "claim-to-evidence register" | `results/tables/claims_register.csv` |
| Spawn key `(configuration_id, replicate_id, stream_id)`, root entropy 20261123, analysis seed 20261124 | as stated; consumption order in `RNG_STREAMS.md`. Suggested addition to Section 4.1: "Each stream is drawn as one block of shape (T + 1) × m before any policy is run; the order is documented in the archive." |

## 5. Artwork

| Figure | File stem | Width | Type | Formats |
| --- | --- | --- | --- | --- |
| 1 Dependency map | `Figure1_dependency_map` | 140 mm (1.5 column) | line art | PDF, TIFF 1000 dpi, PNG 600 dpi |
| 2 One trajectory of C0 | `Figure2_trajectory` | 190 mm (double column) | line art | same |
| 3 Primary difference | `Figure3_primary_difference` | 190 mm | line art | same |
| 4 Budget | `Figure4_budget` | 190 mm | line art | same |
| 5 Notice, map and weight conditions | `Figure5_conditions` | 190 mm | line art | same |

Fonts are embedded (TrueType, sans-serif, at least 6.5 pt at final size). Series differ by
colour and by marker or line style, and the four-colour palette passes a colour-vision-deficiency
check, so the figures remain readable in greyscale print. Colour is used online at no charge;
no figure relies on colour alone.

Captions matching the regenerated artwork (panel letters were added):

* **Fig. 1.** Reference dependency map. Services S1–S3 (top) require every linked component;
  dashed links mark the redundant pair D/E, of which one capable node suffices. Thick orange
  outlines mark components used by two or more services. The operator and the evaluator use
  the same map except in C8 (the operator omits F from S2) and C9 (S2 uses dedicated copies
  A2 and F2).
* **Fig. 2.** First replicate of C0. (a) Red bars: days on which a component was truly
  incapable; triangles: notices delivered to the operator; short ticks: checks by P1 (orange,
  upper row) and P3 (blue, lower row). (b) Number of services falsely assured on each day
  under P1 (dashed) and P3 (solid, offset slightly upward for visibility). One check per day;
  one trajectory shown.
* **Fig. 3.** (a) Distribution of the paired difference P3 − P1 in falsely assured
  service-days per 100 over the 300 trajectories of C0; solid line: zero; dashed line: mean.
  (b) Mean P3 − P1 difference in every condition with 95% percentile bootstrap intervals
  (10,000 resamples of whole trajectories).
* **Fig. 4.** (a) False assurance and (b) false rejection per 100 service-days as functions of
  the daily budget *b* (C1: 0; C0: 1; C2: 2; C3: 4). Points are means over 300 trajectories;
  bars are ±1.96 Monte Carlo standard errors, mostly smaller than the markers. Conditions use
  independent trajectories.
* **Fig. 5.** Mean P3 − P1 difference in false assurance (blue circles) and false rejection
  (orange squares) per 100 service-days under (a) varying notice completeness, (b) notice
  suppression, a map error and joint failure of the redundant pair, and (c) varying notice
  weight; 95% bootstrap intervals, 300 trajectories per condition.

## 6. Table descriptions

Reviewers of the group's previous submission asked for a description of every table. One
sentence per table that can precede its first citation:

* **Table 4** lists, for each of the 13 conditions, the single generator or policy parameter
  that differs from the primary configuration C0 and the question the condition answers; the
  machine-readable form is `results/parameters.json`.
* **Table 5** gives, for each policy in C0, the mean rate of each error with its Monte Carlo
  standard error, the share of assurances that were false, and the length and censoring of
  false-assurance spells (`policy_summary.csv`).
* **Table 6** gives every paired contrast in C0 with its bootstrap interval, dispersion and
  the share of trajectories in which the difference was negative, zero or positive
  (`paired_results.csv`).
* **Table 7** shows how each policy distributed its 180 checks over the eight components and
  how old the evidence was when checked (`allocation.csv`).
* **Table 8** repeats the main contrasts in every condition (`paired_results.csv`).
* **Appendix A** contains two single-day cases with identical operator information and
  different hidden states, one favouring each rule, for checking sign and denominator by hand.

## 7. Highlights (values of this package)

* Recovery-evidence checks are framed as a budgeted choice over shared dependencies
* A transparent rule weights evidence age and notices by influence on verdicts
* False assurances fall by 0.42 per 100 service-days versus an event-driven rule
* False rejections fall by 2.12 per 100; a static ranking does as well on assurances
* Gains grow when change notices are incomplete or suppressed, shrink when complete

## 8. Lessons taken from the reviews of COSE-D-26-05437

The earlier submission of the group received comments that apply to any simulation paper with
released code. This package was built to meet them in advance.

| Comment on the earlier paper | Provision here |
| --- | --- |
| Package output and article disagree (75.88% vs 75.6%; 86/90 vs 84/90); is the package the original implementation or a re-implementation? Provide configuration, random-number consumption and the outputs behind the tables | One implementation produces the released files; `conditions.json` holds every parameter; `RNG_STREAMS.md` fixes the consumption order; all logs are archived with digests; `claims_register.csv` pairs each printed number with its source. The remaining step is to update the draft (`manuscript_alignment.md`) |
| State per component what is implemented, unit-tested, integration-tested, used in the experiment, planned | `COMPONENT_STATUS.md` |
| Text, equation and implementation give different rules; add test cases | `ARCHITECTURE.md`, equation-to-code table; one test per rule, including isolated cases (single check, `b > 1`, `b = 0`, `b = m`, tie-break, notice filter) |
| Provide a complete executable workflow from inputs to outputs | `recovery-evidence reproduce`; no manual step |
| Evaluation shares inputs with the decision rule; add an independent criterion | The evaluator uses hidden states that no policy can read; outcomes are recomputed by a module that does not import the simulator. Not provided: distance to an optimal policy (stated as a limitation) |
| Transition costs and effort are not modelled | Stated: checks are exact, immediate and of equal cost; `COMPONENT_STATUS.md` lists this as not implemented |
| Show which domain-specific property changes the decision; add a counterfactual | C9 removes sharing for one service, C5 removes notice incompleteness, C7 breaks the redundancy assumption; P2 versus P3 isolates current from static dependency information |
| Figures at 300 dpi or better; describe figures and tables; concise abstract and conclusion | Vector PDF and 1000 dpi TIFF; captions and table descriptions above |
