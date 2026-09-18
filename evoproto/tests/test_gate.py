"""Eq. (13), Eq. (14) and Algorithm 2."""

import pytest

from evoproto.data import Provenance, ProvenanceTag
from evoproto.gate import (
    Decision,
    EvidenceWeights,
    GateThresholds,
    KAPPA_DEFAULT,
    RHO_REC_RECONSTRUCTED,
    decide,
    evidence_score,
)
from evoproto.kg import EvidenceChain

MEASURED = Provenance("lit", "1", "CC-BY", ProvenanceTag.MEASURED)
RECONSTRUCTED = Provenance("ace", "1", "CC0", ProvenanceTag.MODELED, r=1, method="ML under BM")


def _chain(supports=(0.9, 0.8, 0.85, 0.7), reconstructed=False):
    record = RECONSTRUCTED if reconstructed else MEASURED
    return EvidenceChain(
        nodes=("org", "trait", "fun", "mech", "param"),
        supports=tuple(supports),
        provenance=(record, record, record, record),
    )


def test_evidence_score_follows_equation_13():
    import math

    supports = (0.9, 0.8, 0.85, 0.7)
    n_conv = 2.0
    expected = (
        sum(0.25 * s for s in supports) * (1 + KAPPA_DEFAULT * math.log1p(n_conv))
    )
    assert evidence_score(supports, n_conv) == pytest.approx(expected)


def test_evidence_score_is_capped_at_one():
    assert evidence_score((1.0, 1.0, 1.0, 1.0), 50.0) == 1.0


def test_reconstruction_only_chains_are_downweighted():
    plain = evidence_score((0.8, 0.8, 0.8, 0.8), 1.0)
    reconstructed = evidence_score((0.8, 0.8, 0.8, 0.8), 1.0, reconstruction_only=True)
    assert reconstructed == pytest.approx(plain * RHO_REC_RECONSTRUCTED)


def test_convergence_bonus_is_monotone_with_diminishing_returns():
    scores = [evidence_score((0.5, 0.5, 0.5, 0.5), n) for n in (0.0, 1.0, 2.0, 3.0)]
    assert scores == sorted(scores)
    assert (scores[2] - scores[1]) > (scores[3] - scores[2])


def test_evidence_weights_must_sum_to_one():
    with pytest.raises(ValueError):
        EvidenceWeights(w=(0.5, 0.5, 0.5, 0.5))
    with pytest.raises(ValueError):
        EvidenceWeights(w=(0.5, 0.5))


def test_supports_outside_the_unit_interval_are_rejected():
    with pytest.raises(ValueError):
        evidence_score((1.2, 0.5, 0.5, 0.5), 1.0)
    with pytest.raises(ValueError):
        evidence_score((0.5, 0.5, 0.5), 1.0)


def test_failed_verification_rejects_regardless_of_position():
    result = decide(_chain(), U=0.0, n_conv_weighted=3.0, verified=False)
    assert result.decision is Decision.REJECT
    assert "verification" in result.report.reason


def test_weak_evidence_abstains_and_names_the_weakest_edge():
    chain = _chain(supports=(0.5, 0.4, 0.1, 0.45))
    result = decide(chain, U=0.1, n_conv_weighted=0.0, verified=True)
    assert result.decision is Decision.ABSTAIN
    assert result.report.weakest_edge == "explainedBy"
    assert result.report.weakest_support == pytest.approx(0.1)
    assert "three-point bending" in result.report.suggested_experiment


def test_high_transfer_uncertainty_abstains_and_names_the_dominant_term():
    components = {"u_scale": 0.9, "u_mat": 0.4, "u_load": 0.1}
    result = decide(
        _chain(), U=0.62, n_conv_weighted=2.0, verified=True,
        uncertainty_components=components,
    )
    assert result.decision is Decision.ABSTAIN
    assert result.report.dominant_uncertainty_term == "u_scale"
    assert "dimensional analysis" in result.report.suggested_experiment


def test_strong_evidence_and_low_uncertainty_recommends():
    result = decide(_chain(), U=0.38, n_conv_weighted=2.0, verified=True)
    assert result.decision is Decision.RECOMMEND
    assert result.report is None
    assert result.recommended
    assert "engineer approval" in result.as_dict()["note"]


def test_evidence_is_checked_before_uncertainty():
    """Algorithm 2 tests E first, so a chain that fails both reports the edge."""
    result = decide(
        _chain(supports=(0.1, 0.1, 0.1, 0.1)), U=0.9, n_conv_weighted=0.0, verified=True,
        uncertainty_components={"u_scale": 0.9},
    )
    assert result.decision is Decision.ABSTAIN
    assert result.report.weakest_edge is not None
    assert result.report.dominant_uncertainty_term is None


def test_thresholds_move_the_decision_boundary():
    chain = _chain(supports=(0.55, 0.55, 0.55, 0.55))
    strict = decide(chain, U=0.2, n_conv_weighted=0.0, verified=True,
                    thresholds=GateThresholds(tau_E=0.9, tau_U=0.5))
    lenient = decide(chain, U=0.2, n_conv_weighted=0.0, verified=True,
                     thresholds=GateThresholds(tau_E=0.3, tau_U=0.5))
    assert strict.decision is Decision.ABSTAIN
    assert lenient.decision is Decision.RECOMMEND
