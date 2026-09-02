# Manuscript insertions for the software deposit

Ready-to-paste text linking the article to its archived software.

| | |
|---|---|
| **Article** | Torstensson, O.; Prokopovych-Tkachenko, D.; Lakhno, V.; Desiatko, A.; Fedotov, S. *Multicriteria Model for Integrating Distributed Systems into Cloud Services.* Systems, 2026 (submitted manuscript). |
| **Software DOI** | [10.5281/zenodo.22259414](https://doi.org/10.5281/zenodo.22259414) |
| **Development repository** | https://github.com/omega2417/bnt |
| **Software version** | 1.0.0 |
| **License** | MIT (source code); CC BY 4.0 (appendix data files) |

Each block below is verbatim manuscript text. Reference numbers assume the
current 37-entry list, so the software becomes `[38]`; renumber if the list
changes before submission.

---

## Insert 1 — Section 2.4, Experimental Design and Reproducibility

**Replace the final sentence,** which currently reads:

> Synthetic inputs, settings, and run-level outputs are reproduced in the appendices; the machine-readable files and executable script are available from the corresponding author.

**with:**

> Synthetic inputs, settings, and run-level outputs are reproduced in the appendices. The complete implementation—exact binary enumeration, NSGA-II and NSGA-III survival, weighted-sum selection, metric calculation, statistical testing, and figure generation—is openly archived at Zenodo (DOI: 10.5281/zenodo.22259414) [38], with development history at https://github.com/omega2417/bnt. The archive includes the machine-readable Appendix A–C files, a validation module that re-derives each reported quantity and reports agreement per claim, a command-line interface, a unit and reproduction test suite, and a Google Colab notebook that executes the entire study in a browser without local installation.

---

## Insert 2 — Data Availability Statement

**Full replacement of the existing statement:**

> All synthetic input values, fixed seeds, algorithm settings, normalization constants, selected convergence checkpoints, and run-level outcome metrics reported in the tables are included in this article and Appendices A–C. The complete source code, the machine-readable Appendix A–C data files, and the scripts that regenerate every table and figure are openly available at Zenodo, DOI 10.5281/zenodo.22259414 [38], released under the MIT license for source code and CC BY 4.0 for the data files; the development repository is https://github.com/omega2417/bnt. Exact enumeration results—the feasible-portfolio count, the Pareto-front size, the exact hypervolume, the knee portfolio and its derived quantities, the weighted-sum indicators, and the complete 25-cell sensitivity grid—are deterministic and reproduce to within the rounding precision of the six-decimal inputs published in Appendix A. Evolutionary results depend on a pseudorandom stream and therefore reproduce in distribution rather than run for run. No external, personal, or confidential organizational data were used.

### Variant, if the original script that produced Appendix B is also deposited

The final two sentences above exist because the deposited code is a clean
implementation of the protocol in Table 3 rather than the exact script that
generated Appendix B, so a reader who runs it will not recover the run-level
values seed for seed. If the original script is added to the deposit, drop
those two sentences and use instead:

> Both the reference implementation and the original experiment script are included, so every reported quantity—including the run-level values of Appendix B—can be regenerated directly.

---

## Insert 3 — Reference list entry

> 38. Torstensson, O.; Prokopovych-Tkachenko, D.; Lakhno, V.; Desiatko, A.; Fedotov, S. cimcdm: Reference Implementation and Reproducibility Archive for "Multicriteria Model for Integrating Distributed Systems into Cloud Services", version 1.0.0; Zenodo, 2026. https://doi.org/10.5281/zenodo.22259414.

---

## Insert 4 — Section 1, contributions list (optional)

**Add as a fourth bullet,** after "a two-factor sensitivity analysis that separates local robustness of the compromise decision from empirical validation":

> an openly archived reference implementation that re-derives every reported quantity, verifies each against the published value, and runs in a browser without local installation.

---

## Insert 5 — separate Code Availability Statement (only if the journal requires one)

Some MDPI journals separate code from data. If Systems does, keep Insert 2 for
the data half and add:

> **Code Availability Statement.** The software supporting this study is openly available at Zenodo, DOI 10.5281/zenodo.22259414 [38], under the MIT license, with development history at https://github.com/omega2417/bnt. It implements the model of Equations (1)–(11), exact binary enumeration, the NSGA-II, NSGA-III and weighted-sum procedures, the quality indicators, the statistical tests, and the sensitivity analysis, and it ships a validation module that checks each computed quantity against the value reported here.

---

## What the deposit contains

For reference when responding to reviewers:

| Component | Detail |
|---|---|
| Model | Equations (1)–(11): three minimization objectives, six constraints, bounded monotone response functions, normalized-distance knee rule |
| Exact enumeration | All 262,144 portfolios → 83,657 feasible → 446 Pareto-optimal, hypervolume 0.421543 |
| Algorithms | NSGA-II; reference-direction (NSGA-III-type) survival on 55 Das–Dennis directions; weighted sum over 231 simplex-lattice weights |
| Indicators | Hypervolume, IGD+, spacing, exact-front coverage |
| Statistics | Paired Wilcoxon signed-rank with Pratt zero handling, Holm correction, rank-biserial effect sizes |
| Sensitivity | 25 cells, exact enumeration per cell |
| Verification | Validation module reporting pass/fail per published claim; 40 unit and reproduction tests |
| Access | Google Colab notebook, command-line interface, Python API |
| Data | Appendices A–C as machine-readable CSV |

### Reproduction status, stated precisely

Reproduces **exactly**, to the 1e-7 rounding floor of the six-decimal published
inputs: feasible count, front size, exact hypervolume, knee portfolio and all
its derived quantities, all 25 sensitivity cells, and all four weighted-sum
indicators.

Reproduces **in distribution**: the NSGA-II and NSGA-III results. Point
estimates order the two methods as the article does—NSGA-III attains lower IGD+,
NSGA-II is faster—but the re-implementation reaches no statistically significant
metric difference over 30 seeds where the article reports three, and it recovers
about 43% exact-front coverage against the published ~60%. The repair operator
that governs this is specified in the article only as "feasible initialization
and repair".

### A convention worth recording

The article names *spacing* without defining it. Its weighted-sum front is
deterministic and reproduces exactly (the same 29 portfolios, the same
hypervolume, IGD+ and coverage), so the indicator definition could be isolated
as the sole source of any disagreement. On that front, Schott's original
Manhattan formulation gives 0.022544 and the Euclidean form gives exactly the
published 0.016338. Should a reviewer query the spacing values, this is the
answer: the study uses Euclidean nearest-neighbour distances.

---

## Before submission

1. **Confirm which DOI you are citing.** Zenodo issues a concept DOI covering
   all versions and a version-specific DOI. Cite the concept DOI—shown as
   "Cite all versions" on the record page—so the reference survives any later
   release. If 10.5281/zenodo.22259414 is the version DOI, substitute the
   concept DOI in every block above.

2. **Make the GitHub link resolve.** The project currently lives on the branch
   `claude/zenodo-publication-project-sedznh`, so
   https://github.com/omega2417/bnt does not yet show the
   `cloud-integration-mcdm/` directory. Merge the branch into the default
   branch before submission, or the repository link in Inserts 1–3 will not
   lead a reader to the code. This also fixes the Colab badge in the README.

3. **Decide on Appendix B.** See the variant under Insert 2. Either deposit the
   original experiment script, or keep the two sentences that distinguish
   deterministic from stochastic reproduction. Reviewers do run archived code,
   and the discrepancy is easier to explain in advance than afterwards.
