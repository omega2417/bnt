"""Eqs. (8)-(10) and the grounding filter of the retrieval stage."""

import math

import pytest

from evoproto.retrieval import (
    AnalogCandidate,
    GroundedStatement,
    RetrievalWeights,
    TransferWeights,
    filter_grounded_statements,
    load_mismatch,
    material_mismatch,
    rank_analogs,
    score_analog,
    transfer_uncertainty,
    u_scale,
)


def _candidate(**overrides):
    kwargs = dict(
        identifier="c",
        name="candidate",
        functional_match=0.8,
        mechanism_evidence=0.5,
        n_conv_weighted=2.0,
        length_biological=0.02,
        length_engineering=0.05,
        material_biological="hierarchical_composite",
        material_engineering="monolithic_isotropic",
        load_biological="intermittent_inertial",
        load_engineering="intermittent_inertial",
    )
    kwargs.update(overrides)
    return AnalogCandidate(**kwargs)


def test_u_scale_matches_the_decade_values_of_equation_10():
    assert u_scale(1.0, 1.0) == pytest.approx(0.0)
    assert u_scale(10.0, 1.0) == pytest.approx(1 - math.exp(-1), abs=1e-12)
    assert u_scale(100.0, 1.0) == pytest.approx(1 - math.exp(-2), abs=1e-12)
    # the term is symmetric: scaling up or down by a decade costs the same
    assert u_scale(0.1, 1.0) == pytest.approx(u_scale(10.0, 1.0))


def test_u_scale_rejects_non_positive_lengths():
    with pytest.raises(ValueError):
        u_scale(0.0, 1.0)


def test_transfer_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        TransferWeights(alpha=0.5, beta=0.4, gamma=0.3)


def test_transfer_uncertainty_is_the_weighted_sum_of_its_three_terms():
    U, components = transfer_uncertainty(
        0.05, 0.02, "hierarchical_composite", "monolithic_isotropic",
        "intermittent_inertial", "impact",
    )
    weights = TransferWeights()
    expected = (
        weights.alpha * components["u_scale"]
        + weights.beta * components["u_mat"]
        + weights.gamma * components["u_load"]
    )
    assert U == pytest.approx(expected)
    assert 0.0 <= U <= 1.0


def test_case_study_transfer_uncertainty_reproduces_section_6_3():
    """Section 6.3 reports U ~ 0.38 for the bamboo culm analog, below tau_U = 0.5."""
    U, components = transfer_uncertainty(
        0.050, 0.023, "hierarchical_composite", "monolithic_isotropic",
        "intermittent_inertial", "intermittent_inertial",
    )
    assert U == pytest.approx(0.38, abs=0.005)
    assert components["u_mat"] > components["u_scale"]  # material dominates
    assert U < 0.5


def test_mismatch_tables_are_symmetric_and_zero_on_the_diagonal():
    assert material_mismatch("viscoelastic", "viscoelastic") == 0.0
    assert material_mismatch("viscoelastic", "monolithic_isotropic") == material_mismatch(
        "monolithic_isotropic", "viscoelastic"
    )
    assert load_mismatch("static", "impact") == 1.0
    with pytest.raises(KeyError):
        material_mismatch("unobtainium", "monolithic_isotropic")


def test_score_follows_equation_8():
    candidate = _candidate()
    result = score_analog(candidate)
    weights = RetrievalWeights()
    expected = (
        weights.w_F * candidate.functional_match
        + weights.w_M * candidate.mechanism_evidence
        + weights.w_C * math.log1p(candidate.n_conv_weighted)
        - weights.w_U * result["U"]
    )
    assert result["score"] == pytest.approx(expected)


def test_convergence_term_has_diminishing_returns():
    scores = [score_analog(_candidate(n_conv_weighted=n))["score"] for n in (1, 2, 3)]
    first_gain = scores[1] - scores[0]
    second_gain = scores[2] - scores[1]
    assert second_gain < first_gain


def test_transfer_uncertainty_lowers_the_score():
    near = score_analog(_candidate(length_biological=0.05))["score"]
    far = score_analog(_candidate(length_biological=0.0005))["score"]
    assert far < near


def test_ranking_is_deterministic_and_ordered():
    candidates = [
        _candidate(identifier="a", functional_match=0.6),
        _candidate(identifier="b", functional_match=0.9),
        _candidate(identifier="c", functional_match=0.9),
    ]
    ranked = rank_analogs(candidates)
    assert [r["identifier"] for r in ranked] == ["b", "c", "a"]  # ties broken by id
    assert ranked == rank_analogs(candidates)


def test_scores_out_of_range_are_rejected():
    with pytest.raises(ValueError):
        _candidate(functional_match=1.4)
    with pytest.raises(ValueError):
        _candidate(n_conv_weighted=-1.0)


def test_statements_citing_outside_the_retrieved_set_are_discarded():
    allowed = {"10.1017/CBO9781139878326", "edge:explainedBy:1"}
    statements = [
        GroundedStatement("c1", "grounded", ("10.1017/CBO9781139878326",)),
        GroundedStatement("c2", "cites something not retrieved", ("10.9999/fabricated",)),
        GroundedStatement("c3", "no citation at all", ()),
    ]
    kept, discarded = filter_grounded_statements(statements, allowed)
    assert [s.candidate_id for s in kept] == ["c1"]
    assert [s.candidate_id for s in discarded] == ["c2", "c3"]
