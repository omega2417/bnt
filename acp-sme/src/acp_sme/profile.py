"""Versioned profile objects and the human-authorized adaptation lifecycle.

Figure 2 of the article: observe minimized metadata -> detect a material change
-> re-score coverage gaps -> recommend a profile delta -> obtain an authorized
decision -> verify implementation evidence.

Two properties are enforced structurally rather than by convention:

* **R5, human authority.** The protector cannot implement a safeguard, change
  the approved profile, or accept risk.  :meth:`ProfileLedger.apply` refuses
  anything but an ``APPROVED`` decision carrying an authorized approver, and
  the recommender has no other way to mutate the ledger.
* **R7, versioned logic.** Every approved profile is an immutable version in a
  hash-chained ledger, so a historical replay or rollback is possible and a
  silent edit of the decision history is detectable.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from enum import Enum
from hashlib import sha256
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .capabilities import BY_CODE, cost_of, order
from .crosswalk import CROSSWALK_PACK_VERSION, provenance
from .detector import Decision
from .selector import Selection, explain


class Role(Enum):
    """Separation of duties (Section 6.1)."""

    CONNECTOR = "connector"
    ANALYST = "analyst"
    APPROVER = "approver"
    AUDITOR = "auditor"


class Outcome(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    EVIDENCE_REQUESTED = "evidence_requested"


class UnauthorizedDecision(PermissionError):
    """Raised when a non-approver attempts to change the approved profile."""


@dataclass(frozen=True)
class Proposal:
    """An explainable, resource-feasible profile delta awaiting a human decision.

    Carries every element Section 3.6 requires of a proposal: trigger, affected
    capabilities, rationale, Current-to-Target delta, standards provenance,
    prerequisites, expected burden, confidence, alternatives, expiry and
    rollback implications.
    """

    proposal_id: str
    created_at: datetime
    trigger: str
    current_profile: Tuple[str, ...]
    target_profile: Tuple[str, ...]
    rationale: str
    confidence: float
    expected_burden_units: int
    budget: int
    expiry: date
    alternatives: Tuple[Tuple[str, ...], ...] = ()
    verification_tasks: Tuple[str, ...] = ()
    crosswalk_version: str = CROSSWALK_PACK_VERSION

    @property
    def added(self) -> Tuple[str, ...]:
        return order(set(self.target_profile) - set(self.current_profile))

    @property
    def removed(self) -> Tuple[str, ...]:
        return order(set(self.current_profile) - set(self.target_profile))

    @property
    def is_noop(self) -> bool:
        return not self.added and not self.removed

    def standards_provenance(self) -> Dict[str, Dict[str, List[str]]]:
        """R3: every proposed capability carries its standards path."""
        return {code: provenance(code) for code in self.added}

    def rollback_note(self) -> str:
        if not self.removed:
            return "Rollback: revert to the previous approved version; no capability is withdrawn."
        return (
            "Rollback: revert to the previous approved version. Withdrawing "
            + ", ".join(self.removed)
            + " reduces coverage of the demand those capabilities served; confirm "
            "that no obligation depends on them before approving."
        )

    def render(self) -> str:
        lines = [
            f"Proposal {self.proposal_id} ({self.created_at.isoformat(timespec='seconds')})",
            f"  Trigger        : {self.trigger}",
            f"  Current profile: {'+'.join(self.current_profile) or '(empty)'}",
            f"  Target profile : {'+'.join(self.target_profile) or '(empty)'}",
            f"  Add            : {', '.join(self.added) or '(none)'}",
            f"  Remove         : {', '.join(self.removed) or '(none)'}",
            f"  Rationale      : {self.rationale}",
            f"  Burden         : {self.expected_burden_units} of {self.budget} resource units",
            f"  Confidence     : {self.confidence:.2f}",
            f"  Expires        : {self.expiry.isoformat()}",
            f"  {self.rollback_note()}",
        ]
        for code, refs in self.standards_provenance().items():
            joined = "; ".join(f"{fw}: {', '.join(ids)}" for fw, ids in refs.items())
            lines.append(f"  Provenance {code}: {joined}")
        for task in self.verification_tasks:
            lines.append(f"  Verification task: {task}")
        if self.alternatives:
            for i, alt in enumerate(self.alternatives, 1):
                lines.append(f"  Alternative {i}: {'+'.join(alt)} ({cost_of(alt)} units)")
        lines.append(
            "  NOTE: a standards reference states why this is relevant. It does "
            "not prove conformity and does not assert certification."
        )
        return "\n".join(lines)


@dataclass(frozen=True)
class DecisionRecord:
    """An authorized human decision on a proposal."""

    proposal_id: str
    outcome: Outcome
    approver: str
    role: Role
    decided_at: datetime
    reason: str = ""

    def __post_init__(self) -> None:
        if self.outcome is Outcome.APPROVED and self.role is not Role.APPROVER:
            raise UnauthorizedDecision(
                f"role {self.role.value!r} may not approve a profile change"
            )


@dataclass(frozen=True)
class ProfileVersion:
    """An immutable approved profile version in the hash chain."""

    version: int
    capabilities: Tuple[str, ...]
    approved_at: datetime
    approver: str
    proposal_id: Optional[str]
    parent_hash: str
    digest: str
    evidence: Tuple[str, ...] = ()

    @property
    def cost(self) -> int:
        return cost_of(self.capabilities)


def _digest(payload: Mapping[str, Any], parent_hash: str) -> str:
    blob = json.dumps(payload, sort_keys=True, default=str) + parent_hash
    return sha256(blob.encode("utf-8")).hexdigest()


@dataclass
class ProfileLedger:
    """Append-only, hash-chained history of approved profiles (R7)."""

    tenant: str
    versions: List[ProfileVersion] = field(default_factory=list)
    decisions: List[DecisionRecord] = field(default_factory=list)

    @property
    def current(self) -> Tuple[str, ...]:
        return self.versions[-1].capabilities if self.versions else ()

    def baseline(
        self, capabilities: Sequence[str], approver: str, at: Optional[datetime] = None
    ) -> ProfileVersion:
        """Record the initial human-approved baseline (stage 1 of Section 6.3)."""
        if self.versions:
            raise ValueError("baseline already recorded; use apply() for later versions")
        return self._append(order(capabilities), approver, None, at or datetime.utcnow())

    def apply(
        self,
        proposal: Proposal,
        decision: DecisionRecord,
        evidence: Sequence[str] = (),
    ) -> Optional[ProfileVersion]:
        """Apply an authorized decision.

        Returns the new profile version when the decision approves the change,
        and ``None`` otherwise.  A rejected or deferred proposal changes
        nothing: the Current Profile is retained, and the decision stays linked
        to its evidence so the proposal can be reconsidered after expiry or a
        material evidence change.
        """
        if decision.proposal_id != proposal.proposal_id:
            raise ValueError("decision does not refer to this proposal")
        self.decisions.append(decision)
        if decision.outcome is not Outcome.APPROVED:
            return None
        if decision.role is not Role.APPROVER:
            raise UnauthorizedDecision("only an approver may change the approved profile")
        return self._append(
            proposal.target_profile,
            decision.approver,
            proposal.proposal_id,
            decision.decided_at,
            tuple(evidence),
        )

    def _append(
        self,
        capabilities: Tuple[str, ...],
        approver: str,
        proposal_id: Optional[str],
        at: datetime,
        evidence: Tuple[str, ...] = (),
    ) -> ProfileVersion:
        parent_hash = self.versions[-1].digest if self.versions else "0" * 64
        payload = {
            "tenant": self.tenant,
            "version": len(self.versions) + 1,
            "capabilities": list(capabilities),
            "approved_at": at.isoformat(),
            "approver": approver,
            "proposal_id": proposal_id,
            "evidence": list(evidence),
        }
        version = ProfileVersion(
            version=len(self.versions) + 1,
            capabilities=tuple(capabilities),
            approved_at=at,
            approver=approver,
            proposal_id=proposal_id,
            parent_hash=parent_hash,
            digest=_digest(payload, parent_hash),
            evidence=tuple(evidence),
        )
        self.versions.append(version)
        return version

    def verify_chain(self) -> bool:
        """Detect a silent edit of the decision history."""
        parent_hash = "0" * 64
        for version in self.versions:
            payload = {
                "tenant": self.tenant,
                "version": version.version,
                "capabilities": list(version.capabilities),
                "approved_at": version.approved_at.isoformat(),
                "approver": version.approver,
                "proposal_id": version.proposal_id,
                "evidence": list(version.evidence),
            }
            if version.parent_hash != parent_hash:
                return False
            if version.digest != _digest(payload, parent_hash):
                return False
            parent_hash = version.digest
        return True

    def rollback(self, to_version: int, approver: str, role: Role) -> ProfileVersion:
        """Re-approve an earlier profile as a new version (never a history edit)."""
        if role is not Role.APPROVER:
            raise UnauthorizedDecision("only an approver may roll back the profile")
        target = next((v for v in self.versions if v.version == to_version), None)
        if target is None:
            raise ValueError(f"no such version: {to_version}")
        return self._append(
            target.capabilities, approver, f"rollback-to-v{to_version}", datetime.utcnow()
        )

    def replay(self, until: datetime) -> Tuple[str, ...]:
        """Historical replay: the approved profile in force at ``until``."""
        current: Tuple[str, ...] = ()
        for version in self.versions:
            if version.approved_at <= until:
                current = version.capabilities
        return current


DEFAULT_PROPOSAL_VALIDITY_DAYS = 45


def build_proposal(
    proposal_id: str,
    decision: Decision,
    current_profile: Sequence[str],
    selection: Selection,
    relevance: Mapping[str, float],
    created_at: Optional[datetime] = None,
    validity_days: int = DEFAULT_PROPOSAL_VALIDITY_DAYS,
    alternatives: Sequence[Selection] = (),
) -> Proposal:
    """Turn a material-change decision and an exact selection into a proposal.

    Confidence is deliberately reduced when the evidence base carries unknown or
    stale fields: a proposal built on incomplete evidence must not present
    itself as certain (R6).
    """
    created_at = created_at or datetime.utcnow()
    target = tuple(selection.capabilities)
    added = order(set(target) - set(current_profile))
    reasons = [
        f"{code} ({BY_CODE[code].name}) demand {relevance.get(code, 0.0):.2f}"
        for code in added
    ]
    rationale = (
        "Material change raised demand for " + ", ".join(reasons)
        if reasons
        else "No capability change is justified within the approved budget."
    )
    confidence = 0.9 if not decision.verification_tasks else 0.55
    return Proposal(
        proposal_id=proposal_id,
        created_at=created_at,
        trigger=decision.trigger,
        current_profile=order(current_profile),
        target_profile=target,
        rationale=rationale,
        confidence=confidence,
        expected_burden_units=selection.cost,
        budget=selection.budget,
        expiry=(created_at + timedelta(days=validity_days)).date(),
        alternatives=tuple(tuple(alt.capabilities) for alt in alternatives),
        verification_tasks=tuple(decision.verification_tasks),
    )
