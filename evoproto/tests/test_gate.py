"""Evidence score, thresholds and the abstention branch (Section 4.6)."""

from __future__ import annotations

import pytest

from evoproto.gate import (
    Decision,
    EvidenceWeights,
    Thresholds,
    decide,
    evidence_score,
)
from evoproto.kg import demo_graph
from evoproto.retrieval import transfer_uncertainty


def test_evidence_score_is_the_weighted_mean_of_the_supports():
    weights = EvidenceWeights()
    supports = [0.8, 0.8, 0.8, 0.8]
    assert evidence_score(supports) == pytest.approx(0.8)
    mixed = [0.2, 0.4, 0.9, 0.5]
    expected = sum(w * s for w, s in zip(weights.vector, mixed))
    assert evidence_score(mixed) == pytest.approx(expected)


def test_reconstruction_penalty_and_convergence_bonus():
    supports = [0.6, 0.6, 0.6, 0.6]
    base = evidence_score(supports)
    assert evidence_score(supports, reconstructed=True) == pytest.approx(base * 0.8)
    assert evidence_score(supports, n_independent_origins=2) == pytest.approx(base + 0.15)
    assert evidence_score(supports, n_independent_origins=1) == pytest.approx(base)


def test_evidence_score_is_clipped_to_the_unit_interval():
    assert evidence_score([1.0, 1.0, 1.0, 1.0], n_independent_origins=5) == 1.0
    assert evidence_score([0.0, 0.0, 0.0, 0.0]) == 0.0


def test_evidence_score_validates_its_inputs():
    with pytest.raises(ValueError):
        evidence_score([0.5, 0.5, 0.5])
    with pytest.raises(ValueError):
        evidence_score([0.5, 0.5, 0.5, 1.5])
    with pytest.raises(ValueError):
        EvidenceWeights(has_trait=0.5, performs=0.5, explained_by=0.5, maps_to=0.5)


def test_unverified_candidates_are_rejected_whatever_the_evidence():
    result = decide(False, [1.0, 1.0, 1.0, 1.0], 0.0, n_independent_origins=5)
    assert result.decision is Decision.REJECT
    assert "verification" in result.reason


def test_weak_evidence_abstains_and_names_the_weakest_edge():
    result = decide(True, [0.9, 0.05, 0.5, 0.4], 0.0)
    assert result.decision is Decision.ABSTAIN
    assert result.evidence < Thresholds().tau_E
    assert result.report["weakest_edge"] == "performs"
    assert result.report["weakest_support"] == pytest.approx(0.05)
    assert "experiment" in result.report["next_step"] or result.report["next_step"]


def test_high_transfer_uncertainty_abstains_and_names_the_dominant_term():
    uncertainty = transfer_uncertainty(1000.0, "viscoelastic", "monolithic_alloy",
                                       "static", "impact")
    result = decide(True, [0.9, 0.9, 0.9, 0.9], uncertainty)
    assert result.decision is Decision.ABSTAIN
    assert result.report["dominant_term"] in {"u_scale", "u_mat", "u_load"}
    assert result.transfer_uncertainty > Thresholds().tau_U


def test_verified_well_supported_candidate_is_recommended():
    graph = demo_graph()
    chain = graph.evidence_chain("par:flexural_rigidity_per_mass")[0]
    origins = graph.independent_origins("mech:sandwich_cellular_stiffening")
    uncertainty = transfer_uncertainty(3.0, "hierarchical_composite", "monolithic_alloy",
                                       "cyclic", "intermittent_inertial")
    result = decide(True, chain.supports, uncertainty, chain.reconstructed, origins,
                    chain=chain)
    assert result.decision is Decision.RECOMMEND
    assert result.recommended
    assert "engineer approval" in result.report["next_step"]
    assert result.report["chain"]["nodes"][-1] == "par:flexural_rigidity_per_mass"


def test_abstention_report_identifies_the_chain_edge_by_its_endpoints():
    graph = demo_graph()
    chain = graph.evidence_chain("par:flexural_rigidity_per_mass")[0]
    result = decide(True, [0.05, 0.5, 0.6, 0.5], 0.0, chain=chain)
    assert result.decision is Decision.ABSTAIN
    assert result.report["weakest_edge"] == "hasTrait"
    assert "->" in result.report["weakest_edge_endpoints"]


def test_thresholds_are_validated_and_serializable():
    with pytest.raises(ValueError):
        Thresholds(tau_E=1.5)
    assert Thresholds().to_dict() == {"tau_E": 0.60, "tau_U": 0.50}
