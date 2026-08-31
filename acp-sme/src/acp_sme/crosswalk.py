"""Typed capability-standard crosswalk (Table 3).

Nodes are shared capabilities; edges are directional, typed and versioned
references to NIST CSF 2.0 outcomes, ISO/IEC 27001:2022 requirements and Annex A
control identifiers, and CIS Controls v8.1 actions.

Two boundaries are structural, not stylistic:

1. **No ISO control text is reproduced.**  Only identifiers and
   author-generated summaries appear here.  ISO/IEC control text is licensed
   and must be read from the edition held by the adopting organization.
2. **A mapping is a relevance claim in a stated context, never an assertion of
   semantic identity and never a conformity claim.**  The relation type records
   which kind of claim is being made.

Cross-framework mapping is prior art; CIS publishes an official CIS Controls
v8.1 to NIST CSF 2.0 mapping.  The contribution here is that direction,
context, version, confidence, prerequisites and evidence provenance survive the
traversal, so one business event can produce a coordinated capability bundle
instead of three duplicated checklist entries.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

from .capabilities import BY_CODE, CODES

#: Version of the crosswalk pack.  Pinned per deployment; a change is a signed,
#: dual-approved release with a regression replay (R7, Table 8).
CROSSWALK_PACK_VERSION = "crosswalk-pack-0.1.0"


class Framework(Enum):
    NIST_CSF_20 = "NIST CSF 2.0"
    ISO_27001_2022 = "ISO/IEC 27001:2022"
    CIS_V81 = "CIS Controls v8.1"


class Relation(Enum):
    """Typed, directional relations of Section 3.3."""

    SUPPORTS = "supports"
    PARTIALLY_COVERS = "partially covers"
    REQUIRES = "requires"
    PROVIDES_EVIDENCE_FOR = "provides evidence for"


@dataclass(frozen=True)
class StandardsEdge:
    """One directional capability -> standards reference edge."""

    capability: str
    framework: Framework
    identifiers: Tuple[str, ...]
    relation: Relation
    note: str
    confidence: float = 0.8
    source_version: str = CROSSWALK_PACK_VERSION

    def __post_init__(self) -> None:
        if self.capability not in BY_CODE:
            raise ValueError(f"unknown capability {self.capability!r}")
        if not 0.0 < self.confidence <= 1.0:
            raise ValueError("confidence must lie in (0, 1]")


def _edges() -> Tuple[StandardsEdge, ...]:
    E, F, R = StandardsEdge, Framework, Relation
    return (
        # Asset and service inventory
        E("AST", F.NIST_CSF_20, ("ID.AM-01", "ID.AM-02", "ID.AM-04"), R.SUPPORTS,
          "Inventory outcomes; supplier services need a separate governance view."),
        E("AST", F.ISO_27001_2022, ("A.5.9", "Clause 6.1", "Clause 8.1"), R.PARTIALLY_COVERS,
          "Inventory of information and assets, plus risk and change planning."),
        E("AST", F.CIS_V81, ("Control 1", "Control 2", "Control 15"), R.SUPPORTS,
          "Enterprise and software asset control; service providers are Control 15."),
        # Identity lifecycle, MFA, least privilege
        E("IAM", F.NIST_CSF_20, ("PR.AA-01", "PR.AA-02", "PR.AA-03", "PR.AA-04", "PR.AA-05"),
          R.SUPPORTS, "Identity, authentication and access-control outcomes."),
        E("IAM", F.ISO_27001_2022,
          ("A.5.15", "A.5.16", "A.5.17", "A.5.18", "A.8.2", "A.8.3", "A.8.5"),
          R.PARTIALLY_COVERS, "Partial many-to-many mapping; not equivalence."),
        E("IAM", F.CIS_V81, ("Control 5", "Control 6"), R.SUPPORTS,
          "Account and access management safeguards."),
        # Data classification and protection
        E("DAT", F.NIST_CSF_20, ("PR.DS",), R.SUPPORTS, "Data-security outcome category."),
        E("DAT", F.ISO_27001_2022,
          ("A.5.12", "A.5.13", "A.5.14", "A.8.10", "A.8.11", "A.8.12", "A.8.24"),
          R.PARTIALLY_COVERS,
          "Governance and technical implementation remain distinct decisions."),
        E("DAT", F.CIS_V81, ("Control 3",), R.SUPPORTS, "Data protection safeguards."),
        # Secure configuration and vulnerability handling
        E("CFG", F.NIST_CSF_20, ("PR.PS", "ID.RA"), R.SUPPORTS,
          "A single profile outcome can require several safeguards."),
        E("CFG", F.ISO_27001_2022, ("A.8.8", "A.8.9"), R.PARTIALLY_COVERS,
          "Technical vulnerability management and configuration management."),
        E("CFG", F.CIS_V81, ("Control 4", "Control 7"), R.SUPPORTS,
          "Secure configuration and continuous vulnerability management."),
        # Supplier and cloud governance
        E("TPR", F.NIST_CSF_20, ("GV.SC",), R.SUPPORTS,
          "Risk ownership is not supplied by a technical safeguard."),
        E("TPR", F.ISO_27001_2022,
          ("A.5.19", "A.5.20", "A.5.21", "A.5.22", "A.5.23"), R.PARTIALLY_COVERS,
          "Supplier relationships and cloud service acquisition and use."),
        E("TPR", F.CIS_V81, ("Control 15",), R.SUPPORTS, "Service provider management."),
        # Logging and continuous monitoring
        E("DET", F.NIST_CSF_20, ("DE.CM", "DE.AE"), R.SUPPORTS,
          "Scope, retention and evidence quality must be stated explicitly."),
        E("DET", F.ISO_27001_2022, ("A.8.15", "A.8.16"), R.PARTIALLY_COVERS,
          "Logging and monitoring activities."),
        E("DET", F.CIS_V81, ("Control 8", "Control 13"), R.SUPPORTS,
          "Audit log management and network monitoring and defence."),
        E("DET", F.ISO_27001_2022, ("Clause 9.1",), R.PROVIDES_EVIDENCE_FOR,
          "Monitoring output can evidence performance evaluation."),
        # Incident handling
        E("IR", F.NIST_CSF_20, ("RS.MA", "RS.AN", "RS.CO"), R.SUPPORTS,
          "Preparation, response, backup and restoration are separate states."),
        E("IR", F.ISO_27001_2022,
          ("A.5.24", "A.5.25", "A.5.26", "A.5.27", "A.5.28", "A.5.29", "A.5.30", "A.8.13"),
          R.PARTIALLY_COVERS, "Incident management planning and preparation."),
        E("IR", F.CIS_V81, ("Control 17",), R.SUPPORTS, "Incident response management."),
        # Recovery and continuity
        E("REC", F.NIST_CSF_20, ("RC.RP",), R.SUPPORTS, "Recovery plan execution outcomes."),
        E("REC", F.ISO_27001_2022, ("A.5.29", "A.5.30", "A.8.13"), R.PARTIALLY_COVERS,
          "ICT readiness for business continuity and information backup."),
        E("REC", F.CIS_V81, ("Control 11",), R.SUPPORTS, "Data recovery safeguards."),
        # Governance
        E("GOV", F.NIST_CSF_20, ("GV.OC", "GV.RM", "GV.RR", "GV.PO", "GV.OV"), R.SUPPORTS,
          "Organizational context, risk strategy, roles, policy and oversight."),
        E("GOV", F.ISO_27001_2022,
          ("Clause 4", "Clause 5", "Clause 6", "Clause 9", "Clause 10"), R.REQUIRES,
          "Management-system obligations that a technical control cannot satisfy."),
        E("GOV", F.CIS_V81, ("Control 17",), R.PARTIALLY_COVERS,
          "Governance is largely outside the CIS safeguard scope."),
        # Cloud-edge
        E("CLD", F.NIST_CSF_20, ("PR.PS", "PR.AA", "ID.AM-04"), R.SUPPORTS,
          "External service configuration and access."),
        E("CLD", F.ISO_27001_2022, ("A.5.23", "A.8.9", "A.8.20", "A.8.21"), R.PARTIALLY_COVERS,
          "Cloud service use, configuration, network security and network services."),
        E("CLD", F.CIS_V81, ("Control 4", "Control 12", "Control 15"), R.SUPPORTS,
          "Configuration, network infrastructure and service providers."),
        # XR identity and virtual assets
        E("XRI", F.NIST_CSF_20, ("PR.AA", "PR.DS", "ID.AM"), R.PARTIALLY_COVERS,
          "Composite capability; no framework creates metaverse certification by itself."),
        E("XRI", F.ISO_27001_2022, ("A.5.9", "A.8.5", "A.8.24"), R.PARTIALLY_COVERS,
          "Identity, asset and cryptography references applied to a new asset class."),
        E("XRI", F.CIS_V81, ("Control 3", "Control 5", "Control 6"), R.PARTIALLY_COVERS,
          "Existing safeguards applied to immersive identity and virtual assets."),
        # IoT and digital-twin integrity
        E("DTI", F.NIST_CSF_20, ("ID.AM", "ID.RA", "PR.PS", "DE.CM"), R.PARTIALLY_COVERS,
          "Composite capability spanning inventory, risk, hardening and monitoring."),
        E("DTI", F.ISO_27001_2022, ("A.5.9", "A.8.9", "A.8.20", "A.8.21", "A.8.22"),
          R.PARTIALLY_COVERS, "Segregation and network controls applied to twin telemetry."),
        E("DTI", F.CIS_V81, ("Control 1", "Control 4", "Control 12", "Control 13"),
          R.PARTIALLY_COVERS, "Inventory, configuration, network and monitoring safeguards."),
        # AI service governance
        E("AIG", F.NIST_CSF_20, ("GV.SC", "ID.AM-04", "PR.DS"), R.PARTIALLY_COVERS,
          "AI services are third-party data-processing dependencies."),
        E("AIG", F.ISO_27001_2022, ("A.5.19", "A.5.23", "A.8.10", "A.8.12"), R.PARTIALLY_COVERS,
          "Supplier, cloud, deletion and leakage-prevention references."),
        E("AIG", F.CIS_V81, ("Control 3", "Control 15"), R.PARTIALLY_COVERS,
          "Data protection and service-provider management applied to AI services."),
        # Awareness and training
        E("TRN", F.NIST_CSF_20, ("PR.AT",), R.SUPPORTS, "Awareness and training outcomes."),
        E("TRN", F.ISO_27001_2022, ("A.6.3", "Clause 7.2", "Clause 7.3"), R.PARTIALLY_COVERS,
          "Competence, awareness and information security awareness training."),
        E("TRN", F.CIS_V81, ("Control 14",), R.SUPPORTS,
          "Security awareness and skills training."),
    )


EDGES: Tuple[StandardsEdge, ...] = _edges()


def references_for(capability: str) -> Tuple[StandardsEdge, ...]:
    """All standards edges leaving one capability."""
    if capability not in BY_CODE:
        raise ValueError(f"unknown capability {capability!r}")
    return tuple(edge for edge in EDGES if edge.capability == capability)


def provenance(capability: str) -> Dict[str, List[str]]:
    """Compact ``{framework: [identifiers]}`` view used inside a proposal."""
    out: Dict[str, List[str]] = {}
    for edge in references_for(capability):
        out.setdefault(edge.framework.value, []).extend(edge.identifiers)
    return {k: sorted(set(v)) for k, v in out.items()}


def coverage_report() -> Dict[str, Dict[str, int]]:
    """Edge counts per capability and framework, for pack regression tests."""
    report: Dict[str, Dict[str, int]] = {}
    for code in CODES:
        report[code] = {f.value: 0 for f in Framework}
        for edge in references_for(code):
            report[code][edge.framework.value] += 1
    return report


def validate_pack() -> None:
    """Fail closed if any capability lacks a reference in all three frameworks."""
    report = coverage_report()
    missing = [
        f"{code}/{framework}"
        for code, counts in report.items()
        for framework, count in counts.items()
        if count == 0
    ]
    if missing:
        raise ValueError("crosswalk pack incomplete: " + ", ".join(missing))


def draft_soa_rows(capabilities: Iterable[str]) -> List[Dict[str, str]]:
    """Draft Statement of Applicability rows for an ISO/IEC 27001 organization.

    The output is a *draft for management review*.  It records that a capability
    was proposed and which Annex A references were cited; it never records a
    risk-treatment decision, an applicability determination or a conformity
    claim.  Those remain management responsibilities.
    """
    rows: List[Dict[str, str]] = []
    for code in capabilities:
        for edge in references_for(code):
            if edge.framework is not Framework.ISO_27001_2022:
                continue
            rows.append(
                {
                    "capability": code,
                    "capability_name": BY_CODE[code].name,
                    "iso_references": ", ".join(edge.identifiers),
                    "relation": edge.relation.value,
                    "justification_note": edge.note,
                    "decision": "PENDING MANAGEMENT REVIEW",
                    "conformity_claim": "none asserted",
                    "pack_version": edge.source_version,
                }
            )
    return rows


validate_pack()
