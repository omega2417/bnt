# Article → code map, and the open items

Every equation, algorithm, table and figure of the article has one place in the
code. Use this file when reviewing: it is the shortest path from a claim in the
manuscript to the lines that implement it and the test that pins them.

## Equations

| Article | Meaning | Implementation | Test |
|---|---|---|---|
| Eq. (1) | completeness of taxa and characters | `data.completeness` | `test_data.py::test_completeness_matches_equation_1` |
| Eq. (2) | sampling weight `w_c` of a clade | `data.sampling_weight` | `test_data.py::test_sampling_weight_caps_dense_clades` |
| Eq. (3) | independent origins `N_conv` | `kg.EvoKG.independent_origins` | `test_kg.py::test_independent_origins_counts_homology_classes` |
| Eq. (4) | traceability chain | `kg.EvoKG.evidence_chain` | `test_kg.py::test_evidence_chain_exposes_four_provenance_records` |
| Eq. (5) | Blomberg's `K` | `phylo.blombergs_k` | `test_phylo.py::test_blombergs_k_has_unit_expectation_under_bm` |
| Eq. (6) | Pagel's `lambda` (profile likelihood) | `phylo.pagels_lambda` | `test_phylo.py::test_pagels_lambda_is_high_for_bm_and_low_for_noise` |
| Eq. (7) | Stayton's `C1` | `phylo.stayton_c1` | `test_phylo.py::test_c1_is_zero_without_convergence_and_high_with_it` |
| Eq. (8) | analog score `S` | `retrieval.score_analog` | `test_retrieval.py::test_score_matches_equation_8` |
| Eqs. (9)–(10) | transfer uncertainty `U`, `u_scale` | `retrieval.transfer_uncertainty`, `retrieval.scale_mismatch` | `test_retrieval.py::test_scale_term_matches_the_stated_decades` |
| Eq. (11) | constrained multi-objective problem | `design.evaluate_population` + `optimize.constrained_search` | `test_optimize.py::test_search_finds_feasible_designs_and_respects_bounds` |
| Eq. (12) | hypervolume indicator | `optimize.hypervolume_2d`, `optimize.normalized_hypervolume` | `test_optimize.py::test_hypervolume_against_a_hand_computed_case` |
| Eq. (13) | evidence score `E` | `gate.evidence_score` | `test_gate.py::test_evidence_score_is_the_weighted_mean_of_the_supports` |
| Eq. (14) | decision rule | `gate.decide` | `test_gate.py::test_verified_well_supported_candidate_is_recommended` |
| Eqs. (15)–(18) | section properties, rigidity, deflection, stress, buckling, mass | `design._section_properties`, `design.evaluate_population` | `test_design.py::test_solid_section_reduces_to_the_textbook_cantilever` |
| Eq. (19) | constraint margins `g` | `design.evaluate_population` | `test_design.py::test_constraints_are_normalized_margins` |
| Eqs. (20)–(23) | FSR, HV, D, ITS | `experiment.metrics_from_result`, `optimize.design_diversity`, `ApproxSet.iterations_to_specification` | `test_experiment.py::test_cell_metrics_are_finite_and_in_range` |
| Eq. (24) | required replicates | `experiment.required_pairs` | `test_experiment.py::test_required_pairs_matches_the_numbers_quoted_in_section_7_6` |
| Eq. (A.1) | `E[K] = 1` under Brownian motion | `phylo.blombergs_k` (normalizer) | `test_phylo.py::test_blombergs_k_has_unit_expectation_under_bm` |
| Eq. (A.2) | significance of `C1` | `phylo.c1_significance` | `test_phylo.py::test_c1_significance_rejects_the_brownian_null_for_induced_convergence` |
| Eq. (A.3) | exact two-objective hypervolume | `optimize.hypervolume_2d` | `test_optimize.py::test_hypervolume_against_a_hand_computed_case` |

## Algorithms, tables, figures

| Article | Implementation |
|---|---|
| Algorithm 1 (evolution-informed constrained search) | `optimize.constrained_search` |
| Algorithm 2 (evidence-gated recommendation) | `gate.decide` |
| Table 2 (sources and provenance fields) | `data.OTOLConnector`, `data.PBDBConnector`, `data.MorphoBankConnector` |
| Table 3 (notation) | docstrings of the corresponding functions |
| Table 4 (edge types) | `kg.EDGE_SIGNATURE` |
| Table 5 (package structure) | the module layout itself; `evoproto/__init__.py` restates it |
| Table 6 (task specification, A1–A7) | `design.BracketSpec` |
| Table 7 (dry-run outputs) | `experiment.run_protocol`; regenerate with `evoproto dryrun` |
| Figures 1–8 | `figures.fig_1` … `figures.fig_8`; regenerate with `evoproto figures` |

## Open items the authors must close before submission

These are places where the manuscript states a quantity that the text does not
pin down numerically, or where a value is explicitly marked `NEEDS INPUT`. The
code carries a documented default in each case so that the pipeline runs; the
default is a placeholder, **not** a result, and every one of them must be
frozen in the pre-registration (Section 7.8) before the experiment is run.

1. **Eq. (2), functional form of `w_c`.** Implemented as
   `w_c = min(1, f_ref / (n_c / N_c))` with `f_ref = 0.1`. Confirm against the
   manuscript and record `f_ref` in the datasheet.
2. **Eq. (8), weights.** `w_F = 0.40`, `w_M = 0.30`, `w_N = 0.20`, `w_U = 0.30`
   (`retrieval.ScoreWeights`). The article states that defaults exist but the
   values must be reproduced here verbatim.
3. **Eq. (9), component weights of `U`.** `0.4 / 0.4 / 0.2` for scale, material
   and load (`retrieval.UncertaintyWeights`).
4. **Eq. (10), scale term.** `u_scale = min(1, |log10 r| / 2)`, so one decade
   gives 0.5 and two decades 1.0. Confirm the two values quoted in the text.
5. **Eq. (13), chain weights and penalties.** `w = (0.20, 0.25, 0.35, 0.20)`,
   reconstruction penalty `gamma = 0.20`, convergence bonus `beta = 0.15`
   (the article fixes `beta`; `gamma` and `w` are this implementation's).
6. **Eq. (14), thresholds.** `tau_E = 0.60`, `tau_U = 0.50` (`gate.Thresholds`).
   Section 6.3 quotes a `U` for the case study; recompute it with the confirmed
   weights and update the sentence.
7. **Table 6, A7.** AlSi10Mg properties are order-of-magnitude values; replace
   with the partner's certified datasheet.
8. **Tasks T2 and T3.** `experiment.TASKS` registers them and raises
   `NotImplementedError`: their evaluators are to be implemented with the
   partner's CFD and contact-mechanics solvers.
9. **Table 7.** The numbers in the manuscript came from the authors' original
   stand-in arms. Regenerate them from this implementation (`evoproto dryrun`)
   and replace the table, or state which implementation produced them. See
   `results/dry_run/` for the current output and `docs/reproducibility.md` for
   the comparison.
10. **Reference [24]** is flagged `[[VERIFY DOI]]` in the manuscript; run
    `evoproto verify-dois` with network access to settle it.
