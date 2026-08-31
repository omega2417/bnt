"""R5 and R7: role, approval-path, versioning, replay and rollback tests."""

from datetime import datetime, timedelta

import pytest

from acp_sme.detector import DEFAULT_FEATURES, MaterialChangeDetector
from acp_sme.profile import (
    DecisionRecord,
    Outcome,
    ProfileLedger,
    ProfileVersion,
    Role,
    UnauthorizedDecision,
    build_proposal,
)
from acp_sme.selector import select

T0 = datetime(2026, 1, 1)
RELEVANCE = {"GOV": 0.9, "AST": 0.9, "IAM": 0.9, "DAT": 0.9, "DET": 0.8, "DTI": 1.2}


def make_proposal(ledger, pid="P-1"):
    detector = MaterialChangeDetector(DEFAULT_FEATURES, review_period_days=None)
    decision = detector.evaluate({"twin_operational_link": "yes"}, {"twin_operational_link": "no"})
    return build_proposal(pid, decision, ledger.current, select(RELEVANCE, 30), RELEVANCE, T0)


def test_baseline_is_recorded_by_a_named_owner():
    ledger = ProfileLedger("t")
    version = ledger.baseline(["GOV", "AST"], "owner", at=T0)
    assert version.version == 1
    assert version.approver == "owner"
    assert ledger.current == ("GOV", "AST")


def test_a_second_baseline_is_refused():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV"], "owner", at=T0)
    with pytest.raises(ValueError):
        ledger.baseline(["AST"], "owner", at=T0)


def test_non_approver_cannot_approve():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV", "AST"], "owner", at=T0)
    proposal = make_proposal(ledger)
    for role in (Role.ANALYST, Role.CONNECTOR, Role.AUDITOR):
        with pytest.raises(UnauthorizedDecision):
            DecisionRecord("P-1", Outcome.APPROVED, "someone", role, T0)


def test_rejected_and_deferred_proposals_change_nothing():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV", "AST"], "owner", at=T0)
    before = ledger.current
    proposal = make_proposal(ledger)
    for outcome in (Outcome.REJECTED, Outcome.DEFERRED, Outcome.EVIDENCE_REQUESTED):
        result = ledger.apply(
            proposal, DecisionRecord("P-1", outcome, "owner", Role.APPROVER, T0)
        )
        assert result is None
        assert ledger.current == before
    # The decisions stay linked to the proposal for later reconsideration.
    assert len(ledger.decisions) == 3


def test_approval_creates_a_new_version_with_evidence():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV", "AST"], "owner", at=T0)
    proposal = make_proposal(ledger)
    version = ledger.apply(
        proposal,
        DecisionRecord("P-1", Outcome.APPROVED, "ciso", Role.APPROVER, T0),
        evidence=("config-export.json",),
    )
    assert version.version == 2
    assert version.evidence == ("config-export.json",)
    assert ledger.current == proposal.target_profile


def test_decision_must_refer_to_its_own_proposal():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV"], "owner", at=T0)
    proposal = make_proposal(ledger, "P-1")
    with pytest.raises(ValueError):
        ledger.apply(proposal, DecisionRecord("P-2", Outcome.APPROVED, "c", Role.APPROVER, T0))


def test_hash_chain_detects_a_silent_edit():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV", "AST"], "owner", at=T0)
    proposal = make_proposal(ledger)
    ledger.apply(proposal, DecisionRecord("P-1", Outcome.APPROVED, "ciso", Role.APPROVER, T0))
    assert ledger.verify_chain()
    tampered = dict(ledger.versions[0].__dict__)
    tampered["capabilities"] = ("GOV",)
    ledger.versions[0] = ProfileVersion(**tampered)
    assert not ledger.verify_chain()


def test_historical_replay_returns_the_profile_in_force():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV", "AST"], "owner", at=T0)
    proposal = make_proposal(ledger)
    later = T0 + timedelta(days=10)
    ledger.apply(proposal, DecisionRecord("P-1", Outcome.APPROVED, "ciso", Role.APPROVER, later))
    assert ledger.replay(T0 + timedelta(days=5)) == ("GOV", "AST")
    assert ledger.replay(T0 + timedelta(days=20)) == proposal.target_profile


def test_rollback_appends_a_version_and_never_edits_history():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV", "AST"], "owner", at=T0)
    proposal = make_proposal(ledger)
    ledger.apply(proposal, DecisionRecord("P-1", Outcome.APPROVED, "ciso", Role.APPROVER, T0))
    version = ledger.rollback(1, "ciso", Role.APPROVER)
    assert version.version == 3
    assert version.capabilities == ("GOV", "AST")
    assert len(ledger.versions) == 3
    assert ledger.verify_chain()


def test_rollback_requires_an_approver():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV"], "owner", at=T0)
    with pytest.raises(UnauthorizedDecision):
        ledger.rollback(1, "analyst", Role.ANALYST)


def test_proposal_carries_every_required_element():
    ledger = ProfileLedger("t")
    ledger.baseline(["GOV", "AST"], "owner", at=T0)
    proposal = make_proposal(ledger)
    assert proposal.trigger and proposal.rationale
    assert proposal.expected_burden_units <= proposal.budget
    assert proposal.expiry > T0.date()
    assert proposal.standards_provenance()
    assert "rollback" in proposal.rollback_note().lower()
    text = proposal.render()
    assert "does not prove conformity" in text


def test_incomplete_evidence_lowers_proposal_confidence():
    from acp_sme.detector import Decision

    high = build_proposal(
        "P", Decision(0, 0.5, True, ("critical",), False, False), (),
        select(RELEVANCE, 30), RELEVANCE, T0,
    )
    low = build_proposal(
        "P", Decision(0, 0.5, True, ("critical",), False, False, ("stale evidence",)), (),
        select(RELEVANCE, 30), RELEVANCE, T0,
    )
    assert low.confidence < high.confidence


def test_soa_draft_never_asserts_conformity():
    from acp_sme.crosswalk import draft_soa_rows

    for row in draft_soa_rows(["IAM", "DAT"]):
        assert row["decision"] == "PENDING MANAGEMENT REVIEW"
        assert row["conformity_claim"] == "none asserted"
