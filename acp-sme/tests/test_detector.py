"""Equations (1) and (2): distance, critical predicates, persistence, timer."""

import pytest

from acp_sme.detector import (
    CRITICAL_PREDICATES,
    DEFAULT_FEATURES,
    FeatureSpec,
    FeatureType,
    MaterialChangeDetector,
    distance,
    normalise_weights,
    profile_distance,
)

BASE = {
    "cloud_service_count": 4, "xr_asset_count": 0, "digital_twin_count": 0,
    "ai_service_count": 1, "iot_asset_count": 10, "privileged_account_count": 3,
    "mfa_coverage": 0.9, "end_of_support_ratio": 0.1, "residency_class": "domestic",
    "supplier_access_type": "read", "headcount_band": "micro", "sector": "retail",
    "internet_facing_critical_count": 1, "new_restricted_flow": "no",
    "twin_operational_link": "no", "backup_coverage": 0.9, "logging_coverage": 0.8,
}


def test_weights_are_non_negative_and_sum_to_one():
    normalised = normalise_weights(DEFAULT_FEATURES)
    assert all(spec.weight >= 0 for spec in normalised)
    assert sum(spec.weight for spec in normalised) == pytest.approx(1.0)


def test_negative_weight_is_rejected():
    with pytest.raises(ValueError):
        normalise_weights([FeatureSpec("a", FeatureType.NUMERIC, -1.0)])


def test_every_distance_is_bounded_in_unit_interval():
    numeric = FeatureSpec("n", FeatureType.NUMERIC, 1.0, scale=2.0)
    assert distance(numeric, 100.0, 0.0) == 1.0
    assert distance(numeric, 0.0, 0.0) == 0.0
    assert distance(numeric, 1.0, 0.0) == pytest.approx(0.5)
    category = FeatureSpec("c", FeatureType.CATEGORY, 1.0)
    assert distance(category, "a", "a") == 0.0
    assert distance(category, "a", "b") == 1.0
    sets = FeatureSpec("s", FeatureType.SET, 1.0)
    assert distance(sets, {"a", "b"}, {"a", "b"}) == 0.0
    assert distance(sets, {"a"}, {"b"}) == 1.0
    assert distance(sets, {"a", "b"}, {"b", "c"}) == pytest.approx(1 - 1 / 3)


def test_numeric_distance_supports_an_approved_range():
    spec = FeatureSpec("n", FeatureType.NUMERIC, 1.0, scale=10.0)
    assert distance(spec, 5.0, (0.0, 10.0)) == 0.0
    assert distance(spec, 15.0, (0.0, 10.0)) == pytest.approx(0.5)


def test_unknown_value_contributes_maximum_uncertainty():
    # R6: missing evidence is not "no change".
    spec = FeatureSpec("n", FeatureType.NUMERIC, 1.0)
    assert distance(spec, None, 1.0) == 1.0


def test_identical_state_has_zero_distance():
    assert profile_distance(DEFAULT_FEATURES, BASE, BASE) == pytest.approx(0.0)


@pytest.mark.parametrize(
    "change,label_fragment",
    [
        ({"internet_facing_critical_count": 2}, "internet-facing"),
        ({"supplier_access_type": "privileged"}, "supplier access"),
        ({"new_restricted_flow": "yes"}, "restricted-data flow"),
        ({"twin_operational_link": "yes"}, "digital twin"),
        ({"mfa_coverage": 0.5}, "MFA"),
        ({"backup_coverage": 0.5}, "MFA"),
        ({"logging_coverage": 0.5}, "MFA"),
    ],
)
def test_each_critical_predicate_fires_deterministically(change, label_fragment):
    current = dict(BASE, **change)
    detector = MaterialChangeDetector(DEFAULT_FEATURES, tau=0.99, review_period_days=None)
    decision = detector.evaluate(current, BASE)
    assert decision.material
    assert decision.critical
    assert label_fragment in decision.trigger


def test_critical_predicates_do_not_fire_without_a_change():
    assert not [label for label, p in CRITICAL_PREDICATES if p(BASE, BASE)]


def test_subthreshold_change_never_becomes_material():
    current = dict(BASE, cloud_service_count=5)
    detector = MaterialChangeDetector(DEFAULT_FEATURES, tau=0.9, review_period_days=None)
    for _ in range(5):
        assert not detector.evaluate(current, BASE).material


def test_two_of_three_persistence_rule():
    current = dict(BASE, xr_asset_count=20, ai_service_count=20, digital_twin_count=20)
    detector = MaterialChangeDetector(DEFAULT_FEATURES, tau=0.2, review_period_days=None)
    first = detector.evaluate(current, BASE)
    assert first.distance >= 0.2
    assert not first.material, "a single above-threshold window must not be material"
    second = detector.evaluate(current, BASE)
    assert second.material and second.persistent


def test_scheduled_timer_fires_a_review_without_any_change():
    detector = MaterialChangeDetector(DEFAULT_FEATURES, tau=0.99, review_period_days=3)
    outcomes = [detector.evaluate(BASE, BASE).material for _ in range(7)]
    assert outcomes == [False, False, False, True, False, False, True]


def test_stale_observations_become_verification_tasks():
    from datetime import datetime, timedelta

    from acp_sme.metadata_model import MetadataGuard

    now = datetime(2026, 8, 31)
    guard = MetadataGuard("t", b"k", now=now)
    stale = guard.accept({"mfa_coverage": 0.9}, "id", observed_at=now - timedelta(days=200))
    detector = MaterialChangeDetector(DEFAULT_FEATURES, review_period_days=None)
    decision = detector.evaluate(BASE, BASE, observations=stale)
    assert decision.verification_tasks
