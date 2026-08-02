"""Tests for the readiness model gate rules (prompt Modules 11.5 & 22)."""

from awa.readiness.model import (
    ReadinessDimension,
    ReadinessEvidence,
    assess_profile,
)


def _dim(name, level, n_verified, gaps=None):
    ev = [
        ReadinessEvidence(f"{name}-{i}", "e", "ref", True)
        for i in range(n_verified)
    ]
    return ReadinessDimension(name, level, evidence=ev,
                              blocking_gaps=gaps or [])


def test_cannot_raise_level_without_evidence():
    """Invariant: no evidence -> supported level collapses toward 1."""
    d = _dim("TRL", 8, 0)
    assert d.supported_level() < 8


def test_high_trl_does_not_mask_low_irl():
    """Gate: TRL far above IRL is capped/flagged."""
    dims = [
        _dim("TRL", 8, 7),
        _dim("CRL", 3, 2),
        _dim("IRL", 3, 2),
        _dim("OperationalReadiness", 5, 4),
    ]
    prof = assess_profile("s", dims)
    assert any("IRL" in f or "integration" in f.lower()
               for f in prof.gate_findings)
    assert not prof.production_ready


def test_ops_gate_blocks_production():
    """Gate: missing operational procedures block production readiness."""
    dims = [
        _dim("TRL", 8, 7),
        _dim("CRL", 8, 7),
        _dim("IRL", 8, 7),
        _dim("OperationalReadiness", 2, 1,
             gaps=["No incident-response playbook"]),
    ]
    prof = assess_profile("s", dims)
    assert not prof.production_ready
    assert prof.blocking_gaps


def test_production_ready_when_all_high_and_evidenced():
    dims = [
        _dim("TRL", 8, 8),
        _dim("CRL", 8, 8),
        _dim("IRL", 8, 8),
        _dim("OperationalReadiness", 8, 8),
    ]
    prof = assess_profile("s", dims)
    assert prof.production_ready
    assert prof.residual_risk == "low"


def test_profile_serialises():
    dims = [
        _dim("TRL", 4, 2),
        _dim("CRL", 2, 1),
        _dim("IRL", 3, 2),
        _dim("OperationalReadiness", 2, 1),
    ]
    d = assess_profile("s", dims).to_dict()
    for k in ("TRL", "CRL", "IRL", "OperationalReadiness",
              "evidence_completeness", "production_ready"):
        assert k in d
