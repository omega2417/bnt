"""Tests for SAR schema validity, hashing, and agent governance invariants."""

import copy
import json
import pathlib

import jsonschema
import pytest

from awa.api import build_environment, run_incident
from awa.agents.context import DecisionTier
from awa.digital_twin.twin import Scenario
from awa.evidence.sar import sar_provenance_hash

SCHEMA_DIR = pathlib.Path(__file__).resolve().parents[1] / "schemas"


@pytest.fixture(scope="module")
def env():
    return build_environment(seed=1)


@pytest.fixture(scope="module")
def sar_schema():
    return json.loads((SCHEMA_DIR / "sar.schema.json").read_text())


@pytest.fixture(scope="module")
def readiness_schema():
    return json.loads((SCHEMA_DIR / "readiness_profile.schema.json").read_text())


def test_sar_validates_against_schema(env, sar_schema):
    ctx = run_incident(env, (33.0, 12.0), "sar1", Scenario.ROGUE_AP, seed=7)
    jsonschema.validate(ctx.sar, sar_schema)


def test_readiness_profile_validates(env, readiness_schema):
    ctx = run_incident(env, (33.0, 12.0), "sar2", Scenario.CLEAN_LOS, seed=8)
    jsonschema.validate(ctx.sar["readiness_profile"], readiness_schema)


def test_provenance_hash_detects_tampering(env):
    ctx = run_incident(env, (33.0, 12.0), "sar3", Scenario.CLEAN_LOS, seed=9)
    sar = ctx.sar
    assert sar["provenance_hash"] == sar_provenance_hash(sar)
    tampered = copy.deepcopy(sar)
    tampered["MAP"] = [0.0, 0.0]
    assert sar_provenance_hash(tampered) != sar["provenance_hash"]


def test_sar_is_deterministic(env):
    a = run_incident(env, (33.0, 12.0), "det", Scenario.CLEAN_LOS, seed=42).sar
    b = run_incident(env, (33.0, 12.0), "det", Scenario.CLEAN_LOS, seed=42).sar
    assert a["provenance_hash"] == b["provenance_hash"]


def test_unauthorised_containment_is_blocked(env):
    """Invariant: agents never auto-execute containment without approved
    policy; a high-anomaly incident is capped at HUMAN_IN_THE_LOOP."""
    ctx = run_incident(env, (33.0, 12.0), "cont", Scenario.ROGUE_AP, seed=10)
    assert ctx.decision["recommended_tier"] <= int(
        DecisionTier.HUMAN_IN_THE_LOOP)
    # If any containment was proposed it must be recorded as blocked.
    findings = ctx.decision.get("governance_findings", [])
    assert all("VIOLATION" not in f for f in findings)


def test_baseline_never_rewritten(env):
    """Invariant: drift is detected but the immutable baseline is not rewritten."""
    ctx = run_incident(env, (33.0, 12.0), "drift", Scenario.TEMPORAL_DRIFT,
                       seed=11)
    assert ctx.drift_state["baseline_rewritten"] is False


def test_uncertainty_always_surfaced(env):
    ctx = run_incident(env, (33.0, 12.0), "unc", Scenario.CLEAN_LOS, seed=12)
    assert ctx.uncertainty
    for k in ("entropy_nats", "HPD_area_m2", "zone_posterior"):
        assert k in ctx.uncertainty


def test_audit_trail_records_all_agents(env):
    ctx = run_incident(env, (33.0, 12.0), "audit", Scenario.CLEAN_LOS, seed=13)
    agents = {e["agent"] for e in ctx.audit_log}
    for expected in ("ObservationAgent", "LocalizationAgent",
                     "EvidenceAgent", "GovernanceAgent"):
        assert expected in agents
