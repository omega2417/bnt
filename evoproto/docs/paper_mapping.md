# Equation and algorithm map

Every numbered result of the paper, the function that implements it and the test
that checks it. Section numbers refer to the manuscript.

| paper | quantity | implementation | test |
|---|---|---|---|
| Eq. (1) | completeness of a taxon / character | `data.taxon_completeness`, `data.character_completeness`, `data.admit_by_completeness` | `test_data.py::test_completeness_equation_1` |
| Eq. (2) | clade sampling weight `w_k = min(1, n_obs/n̂)` | `data.sampling_weight` | `test_data.py::test_sampling_weight_equation_2_is_capped_at_one` |
| §3.3 | provenance record `π`, five tags, snapshot hash | `data.Provenance`, `data.ProvenanceTag`, `data.CorpusSnapshot` | `test_data.py::test_weakest_tag_propagates_to_derived_quantities`, `::test_snapshot_hash_is_content_addressed_and_order_independent` |
| §5 | blake2b seed derivation | `data.stable_seed` | `test_data.py::test_stable_seed_does_not_depend_on_python_hash_randomisation` |
| Table 4 | nine typed edges, schema enforcement | `kg.EDGE_SIGNATURES`, `kg.EvoKG.add_edge` | `test_kg.py::test_edge_signature_is_enforced`, `::test_homology_and_convergence_are_mutually_exclusive` |
| Eq. (3) | `N_conv(m)` = number of homology classes | `kg.EvoKG.independent_origins`, `.weighted_independent_origins` | `test_kg.py::test_independent_origins_counts_homology_classes` |
| Eq. (4) | traceability chain | `kg.EvoKG.evidence_chains`, `kg.EvidenceChain` | `test_kg.py::test_evidence_chain_has_four_edges_and_four_provenance_records` |
| §4.3 | BM variance–covariance matrix `C` | `phylo.vcv_matrix` | `test_phylo.py::test_vcv_is_symmetric_positive_definite_and_ultrametric` |
| Eq. (5) | Blomberg's K | `phylo.blombergs_k` | `test_phylo.py::test_blombergs_k_has_expectation_one_under_brownian_motion` |
| Eq. (6) | Pagel's λ by profile likelihood | `phylo.pagels_lambda`, `phylo.lambda_profile` | `test_phylo.py::test_pagels_lambda_is_high_for_brownian_and_low_for_white_noise` |
| Eq. (7) | Stayton's C1 | `phylo.stayton_c1` | `test_phylo.py::test_stayton_c1_is_one_for_identical_tips_and_zero_without_convergence` |
| Eq. (A.1) | `E[K] = 1` under BM | `phylo.expected_k_denominator` | `test_phylo.py::test_expected_k_denominator_matches_equation_a1` |
| Eq. (A.2) | simulation p-value of C1 | `phylo.c1_pvalue` | `test_phylo.py::test_c1_pvalue_is_small_for_strongly_convergent_tips` |
| §4.3 | ML ancestral states under BM | `phylo.ancestral_states` | `test_phylo.py::test_ancestral_states_match_the_joint_maximum_likelihood_solution` |
| Eq. (8) | analog score `S(c)` | `retrieval.score_analog`, `retrieval.RetrievalWeights` | `test_retrieval.py::test_score_follows_equation_8` |
| Eq. (9) | transfer uncertainty `U` | `retrieval.transfer_uncertainty`, `retrieval.TransferWeights` | `test_retrieval.py::test_transfer_uncertainty_is_the_weighted_sum_of_its_three_terms` |
| Eq. (10) | `u_scale` | `retrieval.u_scale` | `test_retrieval.py::test_u_scale_matches_the_decade_values_of_equation_10` |
| §4.4 | RAG grounding: discard uncited statements | `retrieval.filter_grounded_statements` | `test_retrieval.py::test_statements_citing_outside_the_retrieved_set_are_discarded` |
| Eq. (11) | the constrained MOO problem | `design.evaluate_population`, `optimize.search` | `test_optimize.py::test_archive_is_feasible_and_non_dominated` |
| Eq. (12), (A.3) | hypervolume | `optimize.hypervolume_2d`, `optimize.normalized_hypervolume` | `test_optimize.py::test_hypervolume_matches_a_hand_computed_case` |
| Algorithm 1 | evolution-informed search loop | `optimize.search` | `test_optimize.py::test_search_is_reproducible_for_a_fixed_seed` |
| Eq. (13) | evidence score `E` | `gate.evidence_score` | `test_gate.py::test_evidence_score_follows_equation_13` |
| Eq. (14), Algorithm 2 | RECOMMEND / ABSTAIN / REJECT | `gate.decide` | `test_gate.py::test_weak_evidence_abstains_and_names_the_weakest_edge` |
| §4.7 | feedback updates weights, not records | `kg.EvoKG.set_support` | `test_kg.py::test_feedback_updates_weights_not_records` |
| Eq. (15) | second moments of area | `design.evaluate_population` | `test_design.py::test_second_moments_follow_equation_15` |
| Eq. (16) | `EI` with Gibson–Ashby `E* = C1 E_s ρ²` | `design.evaluate_population` | `test_design.py::test_flexural_rigidity_uses_the_gibson_ashby_scaling` |
| Eq. (17) | `δ`, `σ`, `σ_cr` | `design.evaluate_population` | `test_design.py::test_deflection_and_stress_follow_equation_17` |
| Eq. (18) | mass and cost proxy | `design.evaluate_population` | `test_design.py::test_mass_follows_equation_18` |
| Eq. (19) | constraint margins `g ≥ 0` | `design.constraint_names`, `design.evaluate_population` | `test_design.py::test_constraint_vector_has_the_five_margins_of_equation_19` |
| §6.2 | ~1 % feasible under uniform sampling | `design.feasible_fraction_uniform` | `test_design.py::test_uniform_feasible_fraction_is_about_one_percent` |
| §6.3 | `U ≈ 0.38 < τ_U` for the case study | `casestudy.candidate_analogs` | `test_casestudy.py::test_candidates_reproduce_the_transfer_uncertainty_of_section_6_3` |
| §6.4 | per-prototype deliverable | `casestudy.run_case_study` | `test_casestudy.py::test_case_study_delivers_the_bundle_of_section_6_4` |
| Eq. (20) | FSR | `optimize.SearchResult.feasible_solution_rate` | `test_experiment.py::test_metrics_are_in_range_and_tagged_synthetic` |
| Eq. (21) | normalised HV | `optimize.normalized_hypervolume` | `test_optimize.py::test_normalized_hypervolume_lies_in_the_unit_interval` |
| Eq. (22) | design diversity `D` | `optimize.design_diversity` | `test_optimize.py::test_design_diversity_is_zero_for_identical_designs_and_scaled_by_dimension` |
| Eq. (23) | ITS | `optimize.SearchResult.iterations_to_specification` | `test_optimize.py::test_its_is_the_first_generation_with_a_feasible_design` |
| §7.5 | phylogenetic block split | `kg.EvoKG.block_split` | `test_kg.py::test_block_split_removes_held_out_clades_from_the_training_graph` |
| §7.5 | ablations | `kg.EvoKG.without_edge_type`, `.without_reconstructions`, `experiment.ablation` | `test_kg.py::test_ablations_drop_edges_without_touching_records` |
| §7.6 | Wilcoxon signed-rank | `experiment.wilcoxon_signed_rank` | `test_experiment.py::test_wilcoxon_matches_scipy_on_the_exact_branch` |
| §7.6 | Holm correction | `experiment.holm_correction` | `test_experiment.py::test_holm_correction_is_monotone_and_never_below_the_raw_value` |
| §7.6 | Cliff's δ | `experiment.cliffs_delta`, `.cliffs_delta_magnitude` | `test_experiment.py::test_cliffs_delta_spans_minus_one_to_one_with_the_usual_labels` |
| §7.6 | bootstrap CI | `experiment.bootstrap_ci` | `test_experiment.py::test_bootstrap_ci_brackets_the_estimate_and_is_reproducible` |
| Eq. (24) | required replicates | `experiment.required_replicates` | `test_experiment.py::test_required_replicates_matches_the_values_quoted_in_section_7_6` |
| §7.7 | dry run | `experiment.dry_run` | `test_experiment.py::test_protocol_smoke_run_produces_a_complete_report` |
| Figs. 1–8 | figure generation | `figures.generate_all` | `test_cli_and_figures.py::test_every_figure_of_the_paper_is_generated` |

## Constants fixed before the experiment

| symbol | value | where |
|---|---|---|
| `w_F, w_M, w_C, w_U` | 0.40, 0.30, 0.15, 0.40 | `retrieval.RetrievalWeights` |
| `α, β, γ` | 0.35, 0.35, 0.30 | `retrieval.TransferWeights` |
| `w_1..w_4` | 0.25 each (uniform) | `gate.EvidenceWeights` |
| `κ` | 0.15 | `gate.KAPPA_DEFAULT` |
| `ρ_rec` | 0.7 when a chain rests only on reconstructions | `gate.RHO_REC_RECONSTRUCTED` |
| `τ_E, τ_U` | 0.5, 0.5 | `gate.GateThresholds` |
| seed string | `evoproto\|version\|task\|arm\|replicate`, blake2b-4 | `data.stable_seed` |

`τ_U = 0.5` is the value used in Section 6.3. The paper leaves `τ_E` to
pre-registration; 0.5 is the shipped default and a deployment records its own
value in `docs/preregistration.md`.
