"""R1 and R6: schema, prohibited-field, missingness and stale-evidence tests."""

from datetime import datetime, timedelta

import pytest

from acp_sme.metadata_model import (
    ALLOWLIST,
    EvidenceState,
    MetadataGuard,
    MetadataRejected,
    business_state,
    pseudonymize,
)

NOW = datetime(2026, 8, 31, 12, 0, 0)


def guard(**kwargs):
    return MetadataGuard(tenant="t", tenant_key=b"key", now=NOW, **kwargs)


@pytest.mark.parametrize(
    "record",
    [
        {"employee_name": "A"},
        {"customer_email": "a@b.c"},
        {"salary_band": 1},
        {"api_key": "x"},
        {"biometric_template": "x"},
        {"raw_log": "x"},
        {"incident_narrative": "x"},
        {"contract_text": "x"},
        {"ip_address": "10.0.0.1"},
        {"username": "root"},
    ],
)
def test_prohibited_fields_fail_closed(record):
    with pytest.raises(MetadataRejected):
        guard().accept(record, "connector")


def test_unknown_field_is_rejected():
    with pytest.raises(MetadataRejected):
        guard().accept({"revenue": 100}, "connector")


def test_free_text_is_rejected():
    with pytest.raises(MetadataRejected):
        guard().accept({"sector": "x" * 200}, "connector")


def test_category_outside_the_approved_set_is_rejected():
    with pytest.raises(MetadataRejected):
        guard().accept({"sector": "aerospace"}, "connector")


def test_ratio_outside_unit_interval_is_rejected():
    with pytest.raises(MetadataRejected):
        guard().accept({"mfa_coverage": 1.4}, "connector")


def test_count_must_be_a_non_negative_integer():
    with pytest.raises(MetadataRejected):
        guard().accept({"it_asset_count": -1}, "connector")
    with pytest.raises(MetadataRejected):
        guard().accept({"it_asset_count": 2.5}, "connector")


def test_banded_field_discards_the_exact_value():
    observation = guard().accept({"headcount_band": 8}, "hr-summary")[0]
    assert observation.value is None
    assert observation.band == "micro"


def test_tokens_are_pseudonymized_and_not_cross_tenant_linkable():
    a = MetadataGuard("t1", b"k1", now=NOW).accept({"supplier_token": "ACME"}, "c")[0]
    b = MetadataGuard("t2", b"k2", now=NOW).accept({"supplier_token": "ACME"}, "c")[0]
    assert a.value.startswith("tok_")
    assert "ACME" not in a.value
    assert a.value != b.value


def test_pseudonymize_is_stable_within_a_tenant():
    assert pseudonymize(b"k", "ACME") == pseudonymize(b"k", "ACME")


def test_missing_connector_yields_unknown_not_zero():
    g = guard()
    observations = g.missing(["mfa_coverage", "backup_coverage"])
    assert all(o.state is EvidenceState.UNKNOWN for o in observations)
    assert all(o.value is None and o.completeness == 0.0 for o in observations)
    assert len(g.verification_tasks) == 2
    # Unknown evidence must not enter the business-state vector at all.
    assert business_state(observations) == {}


def test_stale_evidence_is_flagged_and_raises_a_verification_task():
    g = guard()
    observation = g.accept(
        {"mfa_coverage": 0.9}, "identity", observed_at=NOW - timedelta(days=90)
    )[0]
    assert observation.state is EvidenceState.STALE
    assert not observation.is_usable
    assert g.verification_tasks


def test_retention_deadline_is_always_set():
    observation = guard(retention_days=30).accept({"it_asset_count": 5}, "c")[0]
    assert observation.delete_after == (NOW.date() + timedelta(days=30))


def test_every_allowlisted_field_declares_a_purpose():
    assert all(spec.purpose for spec in ALLOWLIST)
