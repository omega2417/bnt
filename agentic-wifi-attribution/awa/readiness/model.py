"""Readiness assessment (prompt Module 11).

Implements four readiness dimensions (TRL, CRL, IRL, Operational Readiness)
each on a 1-9 scale, plus an *integrated* profile that applies
non-compensatory **gate rules** — a high TRL must not mask a low IRL, an
uncalibrated model caps the achievable level, and no dimension may be raised
without supporting evidence (prompt 11.5).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional


@dataclass
class ReadinessEvidence:
    """A single evidence item backing a readiness claim (prompt 11.1)."""

    evidence_id: str
    description: str
    artefact_ref: str            # e.g. test report id, notebook cell, doc anchor
    verified: bool = False


@dataclass
class ReadinessDimension:
    """One readiness axis with self-declared level and its evidence."""

    name: str                    # TRL | CRL | IRL | OperationalReadiness
    claimed_level: int           # 1..9
    scale_max: int = 9
    evidence: List[ReadinessEvidence] = field(default_factory=list)
    blocking_gaps: List[str] = field(default_factory=list)

    def evidence_completeness(self) -> float:
        """Fraction of claimed level that is backed by *verified* evidence.

        ASSUMPTION: we expect at least one verified evidence item per level
        step above 1.  This is a demonstration heuristic, not a standard.
        """
        need = max(self.claimed_level - 1, 1)
        have = sum(1 for e in self.evidence if e.verified)
        return min(have / need, 1.0)

    def supported_level(self) -> int:
        """Level actually supported once unverified evidence is discounted."""
        comp = self.evidence_completeness()
        # Linearly discount the claim by evidence completeness, floor at 1.
        supported = 1 + int(round((self.claimed_level - 1) * comp))
        if self.blocking_gaps:
            supported = min(supported, self.claimed_level - 1)
        return max(1, min(supported, self.scale_max))


# --------------------------------------------------------------------------- #
# Gate rules (non-compensatory).  Each returns an optional cap message.
# --------------------------------------------------------------------------- #
GateRule = Callable[[Dict[str, "ReadinessDimension"], float], Optional[str]]


def _gate_irl_caps_trl(dims, evidence_completeness):
    trl = dims.get("TRL")
    irl = dims.get("IRL")
    if trl and irl and trl.supported_level() > irl.supported_level() + 2:
        return ("TRL capped: integration readiness (IRL="
                f"{irl.supported_level()}) lags technology readiness (TRL="
                f"{trl.supported_level()}) by >2 levels")
    return None


def _gate_ops_caps_irl(dims, evidence_completeness):
    irl = dims.get("IRL")
    ops = dims.get("OperationalReadiness")
    if irl and ops and ops.supported_level() < 4 and irl.supported_level() >= 7:
        return ("High IRL does not compensate for missing operational "
                "procedures (OperationalReadiness < 4)")
    return None


def _gate_calibration(dims, evidence_completeness):
    crl = dims.get("CRL")
    trl = dims.get("TRL")
    if crl and trl and crl.supported_level() >= 6 and trl.supported_level() < 5:
        return ("High CRL does not compensate for an uncalibrated / "
                "insufficiently validated model (TRL < 5)")
    return None


def _gate_evidence_completeness(dims, evidence_completeness):
    if evidence_completeness < 0.5:
        return (f"Low overall evidence completeness ({evidence_completeness:.2f})"
                " reduces trust in every declared level")
    return None


GATE_RULES: List[GateRule] = [
    _gate_irl_caps_trl,
    _gate_ops_caps_irl,
    _gate_calibration,
    _gate_evidence_completeness,
]


@dataclass
class ReadinessProfile:
    """Integrated readiness profile (prompt 11.5 ReadinessProfile schema)."""

    system_id: str
    dimensions: Dict[str, ReadinessDimension]
    evidence_completeness: float
    blocking_gaps: List[str]
    gate_findings: List[str]
    production_ready: bool
    recommended_actions: List[str]
    residual_risk: str

    def to_dict(self) -> dict:
        return {
            "system_id": self.system_id,
            "TRL": self.dimensions["TRL"].supported_level(),
            "CRL": self.dimensions["CRL"].supported_level(),
            "IRL": self.dimensions["IRL"].supported_level(),
            "OperationalReadiness": self.dimensions[
                "OperationalReadiness"
            ].supported_level(),
            "claimed": {
                k: v.claimed_level for k, v in self.dimensions.items()
            },
            "evidence_completeness": round(self.evidence_completeness, 4),
            "blocking_gaps": self.blocking_gaps,
            "gate_findings": self.gate_findings,
            "production_ready": self.production_ready,
            "recommended_actions": self.recommended_actions,
            "residual_risk": self.residual_risk,
        }


def assess_profile(
    system_id: str, dimensions: List[ReadinessDimension]
) -> ReadinessProfile:
    dims = {d.name: d for d in dimensions}

    # Overall evidence completeness = mean across dimensions.
    comps = [d.evidence_completeness() for d in dimensions]
    overall_completeness = sum(comps) / len(comps) if comps else 0.0

    gate_findings: List[str] = []
    for rule in GATE_RULES:
        msg = rule(dims, overall_completeness)
        if msg:
            gate_findings.append(msg)

    blocking_gaps: List[str] = []
    for d in dimensions:
        blocking_gaps.extend(f"{d.name}: {g}" for g in d.blocking_gaps)

    # Production readiness requires: no gate findings, no blocking gaps, all
    # supported levels >= 7, and evidence completeness >= 0.8 (prompt 11.5).
    all_high = all(d.supported_level() >= 7 for d in dimensions)
    production_ready = (
        not gate_findings
        and not blocking_gaps
        and all_high
        and overall_completeness >= 0.8
    )

    actions: List[str] = []
    for d in dimensions:
        gap = d.claimed_level - d.supported_level()
        if gap > 0:
            actions.append(
                f"Provide {gap} more verified evidence item(s) to substantiate "
                f"{d.name} at level {d.claimed_level}"
            )
    actions.extend(f"Resolve gate finding: {g}" for g in gate_findings)

    residual_risk = "low" if production_ready else (
        "high" if gate_findings or blocking_gaps else "medium"
    )

    return ReadinessProfile(
        system_id=system_id,
        dimensions=dims,
        evidence_completeness=overall_completeness,
        blocking_gaps=blocking_gaps,
        gate_findings=gate_findings,
        production_ready=production_ready,
        recommended_actions=actions,
        residual_risk=residual_risk,
    )
