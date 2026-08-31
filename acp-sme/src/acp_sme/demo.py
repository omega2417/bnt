"""Worked end-to-end walkthrough of the human-authorized adaptation lifecycle.

This is the part of the artifact the synthetic experiment deliberately does not
exercise (Section 3.7): raw MNMM records passing the local metadata guard, the
full Equation (2) detector, a typed capability traversal, an explainable
proposal, and an authorized decision written into a hash-chained ledger.

A micro retailer launches an immersive XR storefront.  Nothing below touches a
real enterprise; the numbers are illustrative inputs.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict

from .capabilities import BY_CODE
from .crosswalk import draft_soa_rows
from .detector import DEFAULT_FEATURES, MaterialChangeDetector
from .metadata_model import MetadataGuard, MetadataRejected, business_state
from .profile import (
    DecisionRecord,
    Outcome,
    ProfileLedger,
    Role,
    UnauthorizedDecision,
    build_proposal,
)
from .selector import explain, select

BUDGET = 34
TENANT_KEY = b"demo-tenant-key-not-a-real-secret"


def _rule(title: str) -> None:
    print()
    print(title)
    print("-" * len(title))


def run_demo() -> None:
    now = datetime(2026, 8, 31, 9, 0, 0)
    guard = MetadataGuard(tenant="micro-retail-demo", tenant_key=TENANT_KEY, now=now)

    _rule("Step 1. Connector records pass the local metadata guard (R1, R2)")
    baseline_record: Dict[str, object] = {
        "headcount_band": 8,
        "sector": "retail",
        "cloud_service_count": 4,
        "xr_asset_count": 0,
        "digital_twin_count": 0,
        "ai_service_count": 1,
        "iot_asset_count": 6,
        "privileged_account_count": 3,
        "mfa_coverage": 0.90,
        "backup_coverage": 0.85,
        "logging_coverage": 0.70,
        "end_of_support_ratio": 0.10,
        "residency_class": "domestic",
        "supplier_access_type": "read",
        "internet_facing_critical_count": 1,
        "new_restricted_flow": "no",
        "twin_operational_link": "no",
        "supplier_token": "Northgate Hosting Ltd",
    }
    accepted = guard.accept(baseline_record, source_type="asset-inventory", observed_at=now)
    print(f"accepted {len(accepted)} allowlisted observations")
    for obs in accepted[:4]:
        shown = obs.band if obs.band is not None else obs.value
        print(f"  {obs.field:<32} -> {shown!r:<14} state={obs.state.value}")
    print("  ... exact values are banded where precision is unnecessary")
    print(
        "  supplier_token stored as "
        f"{[o.value for o in accepted if o.field == 'supplier_token'][0]} "
        "(tenant-keyed pseudonym, NOT anonymous)"
    )

    _rule("Step 2. Prohibited fields fail closed, they are not silently dropped")
    for bad in (
        {"employee_name": "A. Kovalenko"},
        {"incident_narrative": "attacker reused leaked passwords"},
        {"api_key": "sk-live-000"},
        {"revenue_per_store": 12345},
    ):
        try:
            guard.accept(bad, source_type="rogue-connector")
        except MetadataRejected as exc:
            print(f"  REJECTED {exc}")

    _rule("Step 3. Missing evidence becomes a verification task, never a zero-risk value (R6)")
    for obs in guard.missing(["control_state"]):
        print(f"  {obs.field}: evidence state = {obs.state.value}, completeness = {obs.completeness}")
    print(f"  {guard.verification_tasks[-1]}")

    _rule("Step 4. Approved baseline profile is recorded by a named owner (R5, R7)")
    baseline_state = business_state(accepted)
    baseline_relevance = {
        "GOV": 0.65, "AST": 0.75, "IAM": 0.85, "DAT": 0.90,
        "CFG": 0.70, "IR": 0.55, "REC": 0.60, "TRN": 0.55,
    }
    initial = select(baseline_relevance, BUDGET)
    ledger = ProfileLedger(tenant="micro-retail-demo")
    version1 = ledger.baseline(initial.capabilities, approver="owner@micro-retail", at=now)
    print(f"  version {version1.version}: {'+'.join(version1.capabilities)}")
    print(f"  cost {version1.cost} of {BUDGET} budget units")
    print(f"  digest {version1.digest[:16]}...")

    _rule("Step 5. The business changes: an immersive XR storefront goes live")
    later = now + timedelta(days=45)
    guard_later = MetadataGuard("micro-retail-demo", TENANT_KEY, now=later)
    changed_record = dict(baseline_record)
    changed_record.update(
        {
            "xr_asset_count": 7,
            "cloud_service_count": 6,
            "privileged_account_count": 5,
            "new_restricted_flow": "yes",
            "internet_facing_critical_count": 2,
        }
    )
    changed = guard_later.accept(changed_record, "asset-inventory", observed_at=later)
    current_state = business_state(changed)

    detector = MaterialChangeDetector(DEFAULT_FEATURES, tau=0.28)
    decision = detector.evaluate(current_state, baseline_state, observations=changed)
    print(f"  Equation (1) approved-profile distance D_t = {decision.distance:.3f}")
    print(f"  material change = {decision.material}")
    print(f"  trigger = {decision.trigger}")

    _rule("Step 6. Re-score demand and recompute a resource-feasible Target Profile")
    updated_relevance = dict(baseline_relevance)
    updated_relevance.update({"XRI": 1.15, "DAT": 1.35, "IAM": 1.20, "CLD": 0.60})
    proposed = select(updated_relevance, BUDGET)
    for line in explain(proposed, updated_relevance):
        print("  " + line)

    _rule("Step 7. The proposal is explainable and carries standards provenance (R3)")
    proposal = build_proposal(
        proposal_id="P-2026-0045",
        decision=decision,
        current_profile=ledger.current,
        selection=proposed,
        relevance=updated_relevance,
        created_at=later,
    )
    print(proposal.render())

    _rule("Step 8. Only an authorized approver may change the approved profile (R5)")
    try:
        ledger.apply(
            proposal,
            DecisionRecord(
                "P-2026-0045", Outcome.APPROVED, "analyst@micro-retail",
                Role.ANALYST, later,
            ),
        )
    except UnauthorizedDecision as exc:
        print(f"  BLOCKED: {exc}")

    deferred = ledger.apply(
        proposal,
        DecisionRecord(
            "P-2026-0045", Outcome.DEFERRED, "owner@micro-retail", Role.APPROVER, later,
            reason="await XR supplier assurance evidence",
        ),
    )
    print(f"  deferred -> profile unchanged: {deferred is None}, "
          f"current still {'+'.join(ledger.current)}")

    version2 = ledger.apply(
        proposal,
        DecisionRecord(
            "P-2026-0045", Outcome.APPROVED, "owner@micro-retail", Role.APPROVER,
            later + timedelta(days=3), reason="assurance evidence received",
        ),
        evidence=("supplier-assurance-2026-10.pdf", "xr-identity-config-export"),
    )
    print(f"  approved -> version {version2.version}: {'+'.join(version2.capabilities)}")

    _rule("Step 9. The ledger is hash-chained, replayable and rollback-capable (R7)")
    print(f"  chain verifies: {ledger.verify_chain()}")
    print(f"  profile in force on day 0  : {'+'.join(ledger.replay(now))}")
    print(f"  profile in force on day 60 : {'+'.join(ledger.replay(later + timedelta(days=15)))}")
    version3 = ledger.rollback(1, approver="owner@micro-retail", role=Role.APPROVER)
    print(f"  rollback appended as version {version3.version} (history is never edited)")
    print(f"  chain still verifies: {ledger.verify_chain()}")

    _rule("Step 10. Optional draft Statement of Applicability input (never a decision)")
    for row in draft_soa_rows(proposal.added):
        print(f"  {row['capability']:<4} {row['iso_references']:<38} "
              f"{row['relation']:<18} {row['decision']}")
    print("  Management remains responsible for the risk-treatment decision.")

    print()
    print("=" * 78)
    print(
        "Nothing above implemented a safeguard, edited a published standard, or "
        "asserted\nconformity. The artifact recommends; an accountable person decides."
    )
    print("=" * 78)
