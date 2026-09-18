"""Analog scoring and transfer uncertainty (Section 4.4)."""

from __future__ import annotations

import math

import pytest

from evoproto.retrieval import (
    AnalogCandidate,
    ScoreWeights,
    UncertaintyWeights,
    load_mismatch,
    material_mismatch,
    rank_analogs,
    scale_mismatch,
    score_analog,
    transfer_uncertainty,
)


def test_scale_term_matches_the_stated_decades():
    assert scale_mismatch(1.0) == pytest.approx(0.0)
    assert scale_mismatch(10.0) == pytest.approx(0.5)
    assert scale_mismatch(100.0) == pytest.approx(1.0)
    assert scale_mismatch(0.1) == pytest.approx(0.5)      # symmetric in the ratio
    assert scale_mismatch(1e6) == pytest.approx(1.0)      # saturates
    with pytest.raises(ValueError):
        scale_mismatch(0.0)


def test_material_and_load_tables_are_symmetric_and_zero_on_identity():
    assert material_mismatch("polymer", "polymer") == 0.0
    assert material_mismatch("hierarchical_composite", "monolithic_alloy") == pytest.approx(
        material_mismatch("monolithic_alloy", "hierarchical_composite")
    )
    assert load_mismatch("cyclic", "impact") == pytest.approx(0.5)
    assert load_mismatch("unknown_a", "unknown_b") == 0.5   # documented default


def test_transfer_uncertainty_is_a_weighted_mean_and_names_its_dominant_term():
    result = transfer_uncertainty(10.0, "hierarchical_composite", "monolithic_alloy",
                                  "cyclic", "intermittent_inertial")
    weights = UncertaintyWeights()
    expected = (weights.scale * 0.5 + weights.material * 0.8 + weights.load * 0.2)
    assert result["U"] == pytest.approx(expected)
    assert result["dominant"] == "u_mat"
    assert 0.0 <= result["U"] <= 1.0


def test_uncertainty_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        UncertaintyWeights(scale=0.5, material=0.5, load=0.5)


def test_score_matches_equation_8():
    candidate = AnalogCandidate(
        identifier="c",
        functional_match=0.8,
        mechanism_evidence=0.5,
        n_independent_origins=3.0,
        length_ratio=1.0,
        material_biological="polymer",
        material_engineering="polymer",
        load_biological="static",
        load_engineering="static",
    )
    weights = ScoreWeights()
    scored = score_analog(candidate)
    assert scored["U"] == pytest.approx(0.0)
    expected = (weights.functional * 0.8 + weights.mechanism * 0.5
                + weights.origins * math.log1p(3.0))
    assert scored["S"] == pytest.approx(expected)


def test_origins_have_diminishing_returns():
    def score(n):
        return score_analog(AnalogCandidate("c", n_independent_origins=n))["S"]

    first = score(1) - score(0)
    second = score(2) - score(1)
    third = score(3) - score(2)
    assert first > second > third > 0


def test_uncertainty_penalizes_the_score():
    near = AnalogCandidate("near", functional_match=0.8, length_ratio=1.0,
                           material_biological="polymer", material_engineering="polymer",
                           load_biological="static", load_engineering="static")
    far = AnalogCandidate("far", functional_match=0.8, length_ratio=1000.0,
                          material_biological="viscoelastic",
                          material_engineering="monolithic_alloy",
                          load_biological="static", load_engineering="impact")
    ranked = rank_analogs([far, near])
    assert ranked[0]["identifier"] == "near"
    assert ranked[1]["U"] > ranked[0]["U"]


def test_candidate_validates_its_inputs():
    with pytest.raises(ValueError):
        AnalogCandidate("c", functional_match=1.4)
    with pytest.raises(ValueError):
        AnalogCandidate("c", n_independent_origins=-1)
