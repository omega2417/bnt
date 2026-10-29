# Zenodo deposit texts

Copy each block into the Zenodo upload form (or let Zenodo read `.zenodo.json` from the archive). Upload type: Software. Licence: MIT. Access: open. Language: English.


## rbaa-sim — version 1.1.0

**Deposit:** new version of the existing record https://doi.org/10.5281/zenodo.23421069 (use "New version" on that record)

**Title**

rbaa-sim: Reproducible Colab notebook for the risk-based attention allocation model of AI oversight in SMEs

**Version**

1.1.0

**Description (abstract)**

Self-contained Jupyter/Google Colab notebook that reproduces the model-based results of the article "Cognitive optimisation of AI-supported SME decisions through risk-based allocation of managerial attention" (submitted to Digital Business, Elsevier). It implements the risk-based attention allocation (RBAA) model: expected loss (Eq. 1), value of human review (Eq. 2) and the routing rule with scope gate, hard floor and four levels of AI authority (Table 2). It reproduces the worked routing example (Table A1) and the analytic sample-size table for the proposed cluster-randomised field experiment (Table 7, all 24 cells); verifies the derivatives (A1)-(A2) of Appendix A by finite differences; computes the load-aware optimum e* and the marginal-only stopping rate e_m within valid probability bounds (Figure A1); estimates simulation-based power for the severity-weighted primary outcome with a restricted wild bootstrap (Figure A2); and runs the full analysis plan of Appendix C.9 (H1a-H5) on synthetic trial data with a probability-based, design-weighted outcome audit, randomised threshold-policy contrasts for H4 and a firm-level moderation model for H5. Version 1.1.0 aligns numbering, estimands and figures with the revised article; 36 built-in checks pass.

*Scope:* No empirical data are included. All simulations illustrate the logic of the model under stated assumptions and synthetic data-generating processes; they are not evidence for the hypotheses.

**Keywords**

risk-based attention allocation; managerial attention; human-AI decision-making; AI governance; small and medium-sized enterprises; workload externality; cluster-randomised trial; power analysis; Horvitz-Thompson estimator; preregistration; digital business

**Creator**

Prokopovych-Tkachenko, Dmytro (University of Customs and Finance; ORCID 0000-0002-6590-3898)

**Contributors (type: Researcher)**

Torstensson, Olga (Halmstad University; ORCID 0009-0007-2169-6851); Britchenko, Igor (Higher School of Business (WSB-NLU) in Nowy Sącz; ORCID 0000-0002-9196-8740); Ilessova, Bakytgul (Almaty Technological University; ORCID 0000-0001-8357-519X); Chubaievskyi, Nazarii (State University of Trade and Economics; ORCID 0009-0006-2422-1192); Merkibaeva, Ayaulym (Almaty Technological University; ORCID 0009-0006-4951-3415)

**Additional notes**

Run in Google Colab: File > Upload notebook > RBAA_sim_colab.ipynb, then Runtime > Run all (about one minute). All 36 built-in checks pass in the archived run (outputs/test_report.csv). Previous version: https://doi.org/10.5281/zenodo.23421069.

**File to upload**

`rbaa-sim-v1.1.0.zip`


## rbaa-validation — version 1.1.0

**Deposit:** new version of the existing record https://doi.org/10.5281/zenodo.23421157 (use "New version" on that record)

**Title**

rbaa-validation: Back-test of risk-based attention allocation on real open data — Eurostat AI adoption and 284,807 real transactions

**Version**

1.1.0

**Description (abstract)**

Validation companion to the article "Cognitive optimisation of AI-supported SME decisions through risk-based allocation of managerial attention" (submitted to Digital Business, Elsevier); it reproduces Appendix B and Figures B1-B3. A self-contained Google Colab notebook (i) documents AI adoption in EU enterprises by size class, 2023-2025, from Eurostat's 2026 statistical report (Figure B1), and (ii) back-tests the RBAA routing rule on 284,807 real card transactions with fraud labels (Worldline and ULB Machine Learning Group; Open Database License). A calibrated gradient-boosting classifier is trained on the first 60% of elapsed time; on the remaining 129,878 transactions RBAA is compared in euros with amount-based approval limits, random spot checks and an AI-score alert queue under the same managerial-attention budget, with load-aware and isolated stopping rules, a EUR 1,000 hard floor, hour-block bootstrap intervals, sensitivity and robustness analyses and an HTML report. Version 1.1.0 aligns framing and Eurostat values with the revised article, labels bootstrap tail proportions correctly and checks that all 14 values printed in Appendix B are reproduced; the back-test computations are unchanged from v1.0.0.

*Scope:* No open data record the use of RBAA in enterprises. This is a counterfactual back-test with assumed reviewer behaviour, not a measured effect in any company. Raw transaction data are downloaded at run time and verified by SHA-256; they are not redistributed.

**Keywords**

risk-based attention allocation; managerial attention; human-AI decision-making; back-test; fraud detection; cost of control; Eurostat; AI adoption; managerial economics; digital business

**Creator**

Prokopovych-Tkachenko, Dmytro (University of Customs and Finance; ORCID 0000-0002-6590-3898)

**Contributors (type: Researcher)**

Torstensson, Olga (Halmstad University; ORCID 0009-0007-2169-6851); Britchenko, Igor (Higher School of Business (WSB-NLU) in Nowy Sącz; ORCID 0000-0002-9196-8740); Ilessova, Bakytgul (Almaty Technological University; ORCID 0000-0001-8357-519X); Chubaievskyi, Nazarii (State University of Trade and Economics; ORCID 0009-0006-2422-1192); Merkibaeva, Ayaulym (Almaty Technological University; ORCID 0009-0006-4951-3415)

**Additional notes**

Run in Google Colab: upload RBAA_validation_colab.ipynb, Runtime > Run all (1-3 minutes including the data download). Data provenance and licences: DATA_SOURCES.md. Previous version: https://doi.org/10.5281/zenodo.23421157.

**File to upload**

`rbaa-validation-v1.1.0.zip`


## rbaa-benchmark — version 1.0.0

**Deposit:** new record

**Title**

rbaa-benchmark: Comparative validation of risk-based attention allocation against seven review-allocation rules on 129,878 real card transactions

**Version**

1.0.0

**Description (abstract)**

Code, configuration and archived outputs that reproduce Section 5, Tables 3-4, Figures 2-3 and the Appendix B reconciliation of the article "Cognitive optimisation of AI-supported SME decisions through risk-based allocation of managerial attention" (submitted to Digital Business, Elsevier; Supplementary Material S1). On the out-of-time test period of the public ULB/Worldline card-transaction data (129,878 transactions, 143 frauds, EUR 21,159.67 fraud value), RBAA is compared with seven allocation rules: random audit, amount-based approval limits, a classifier threshold, an AI-score alert queue, cost-sensitive expected-loss ranking, fixed-accuracy deferral (learning-to-defer logic) and an isolated value-of-review rule. Rules are evaluated under a tight (0.1%) and a generous (0.5%) review budget and at matched volume, with a paired 10-minute block bootstrap that re-applies the whole policy, a 324-scenario reviewer-behaviour sensitivity grid, calibration distortion, alternative classifiers, a budget sweep, the shadow price of attention, total-cost-of-control indicators and the price of a mandatory-review hard floor. Under the generous budget RBAA earned EUR 79.3 per 1,000 operations (AI-score queue EUR 48.3) with 27 instead of 108 review hours and reduced the total cost of control by 48.7%. A built-in check reproduces all 74 numbers quoted in the article.

*Scope:* Transaction amounts and fraud labels are observed; reviewer behaviour and costs are assumed. The results validate the allocation logic against established methods under explicit assumptions; they are not a field study of SME managers. Raw data are downloaded and verified by SHA-256; they are not redistributed.

**Keywords**

risk-based attention allocation; human oversight of AI; learning to defer; alert triage; cost-sensitive learning; workload externality; total cost of control; shadow price of attention; block bootstrap; fraud detection; digital business

**Creator**

Prokopovych-Tkachenko, Dmytro (University of Customs and Finance; ORCID 0000-0002-6590-3898)

**Contributors (type: Researcher)**

Torstensson, Olga (Halmstad University; ORCID 0009-0007-2169-6851); Britchenko, Igor (Higher School of Business (WSB-NLU) in Nowy Sącz; ORCID 0000-0002-9196-8740); Ilessova, Bakytgul (Almaty Technological University; ORCID 0000-0001-8357-519X); Chubaievskyi, Nazarii (State University of Trade and Economics; ORCID 0009-0006-2422-1192); Merkibaeva, Ayaulym (Almaty Technological University; ORCID 0009-0006-4951-3415)

**Additional notes**

Run: ./run_all.sh (Python 3.13, scikit-learn 1.9.1; about 5 minutes) or the Colab notebook RBAA_benchmark_colab.ipynb. The check outputs/paper_values_check.csv lists every number of Section 5 with the value computed by the code.

**File to upload**

`rbaa-benchmark-v1.0.0.zip`
