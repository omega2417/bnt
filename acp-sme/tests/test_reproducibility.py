"""Reproducibility of the reported synthetic experiment.

The tolerances below are deliberate.  The article specifies every parameter but
not the order in which the pseudo-random draws are consumed, so an independent
implementation reproduces the *reported intervals*, not identical digits.  Each
assertion therefore checks that this implementation lands inside the confidence
interval the article reports, which is the reproducibility claim that can
legitimately be made.
"""

import pytest

from acp_sme.experiment import (
    CONDITIONS,
    run_primary,
    run_sensitivity,
    summarise_primary,
)
from acp_sme.metrics import mean_ci
from acp_sme.scenarios import ARCHETYPES, HORIZON_DAYS, labelled_event_count
from acp_sme.simulator import (
    PRIMARY_SEED,
    false_trigger_probability,
    run_trace,
    trace_seed,
)


@pytest.fixture(scope="module")
def summary():
    return summarise_primary(run_primary())


def test_design_matches_the_article():
    assert len(ARCHETYPES) == 3
    assert HORIZON_DAYS == 120
    assert labelled_event_count(30) == 420
    assert PRIMARY_SEED == 27012026


def test_experiment_size(summary):
    design = summary["design"]
    assert design["traces"] == 90
    assert design["enterprise_days"] == 10800
    assert design["labelled_material_events"] == 420


def test_same_seed_reproduces_bit_identical_traces():
    a = run_trace(ARCHETYPES[1], 7)
    b = run_trace(ARCHETYPES[1], 7)
    for condition in CONDITIONS:
        assert a.conditions[condition].profiles == b.conditions[condition].profiles
    assert a.triggered_review_days == b.triggered_review_days
    assert a.false_trigger_days == b.false_trigger_days


def test_different_seeds_produce_different_traces():
    a = run_trace(ARCHETYPES[1], 7)
    b = run_trace(ARCHETYPES[1], 8)
    assert a.seed != b.seed
    assert a.conditions["acp"].reassessment_days != b.conditions["acp"].reassessment_days


def test_seed_schedule_is_the_documented_formula():
    assert trace_seed("micro", 0) == 27012026
    assert trace_seed("micro", 3) == 27012026 + 303
    assert trace_seed("small", 0) == 27012026 + 10007
    assert trace_seed("medium", 2) == 27012026 + 202 + 20014


@pytest.mark.parametrize(
    "condition,low,high",
    [("acp", 79.2, 81.6), ("monthly", 77.5, 80.1), ("static", 74.3, 76.8)],
)
def test_mean_coverage_falls_inside_the_reported_interval(summary, condition, low, high):
    assert low <= summary[condition]["mean_coverage_pct"]["mean"] <= high


@pytest.mark.parametrize(
    "condition,low,high",
    [("acp", 72.2, 76.1), ("monthly", 70.3, 73.8), ("static", 65.9, 69.5)],
)
def test_p10_coverage_falls_inside_the_reported_interval(summary, condition, low, high):
    assert low <= summary[condition]["p10_coverage_pct"]["mean"] <= high


@pytest.mark.parametrize(
    "condition,low,high",
    [("acp", 1.7, 2.4), ("monthly", 5.5, 7.2), ("static", 16.5, 19.9)],
)
def test_adaptation_delay_falls_inside_the_reported_interval(summary, condition, low, high):
    assert low <= summary[condition]["adaptation_delay_days"]["mean"] <= high


def test_coverage_ordering_is_acp_then_monthly_then_static(summary):
    acp = summary["acp"]["mean_coverage_pct"]["mean"]
    monthly = summary["monthly"]["mean_coverage_pct"]["mean"]
    static = summary["static"]["mean_coverage_pct"]["mean"]
    assert acp > monthly > static


def test_adaptation_delay_ordering(summary):
    assert (
        summary["acp"]["adaptation_delay_days"]["mean"]
        < summary["monthly"]["adaptation_delay_days"]["mean"]
        < summary["static"]["adaptation_delay_days"]["mean"]
    )


def test_paired_gain_over_static_is_positive_in_every_matched_trace(summary):
    paired = summary["paired"]
    assert paired["acp_minus_static_positive"] == "90/90"
    assert 4.25 <= paired["acp_minus_static_pp"]["mean"] <= 5.29


def test_paired_gain_over_monthly_is_small_but_consistent(summary):
    paired = summary["paired"]
    assert 1.39 <= paired["acp_minus_monthly_pp"]["mean"] <= 1.67
    positive, total = paired["acp_minus_monthly_positive"].split("/")
    assert int(positive) >= 80 and int(total) == 90


def test_review_hour_accounting_matches_the_assigned_schedule(summary):
    assert summary["static"]["review_hours"]["mean"] == 4.0
    assert summary["monthly"]["review_hours"]["mean"] == 14.4
    assert 3.5 <= summary["acp"]["review_hours"]["mean"] <= 3.9


def test_false_alerts_are_consistent_with_the_disclosed_nuisance_process(summary):
    observed = summary["acp"]["false_alerts"]["mean"]
    expected = (HORIZON_DAYS - 1) * false_trigger_probability(0.28)
    assert observed == pytest.approx(expected, abs=0.25)


def test_only_acp_reports_false_alerts(summary):
    assert summary["static"]["false_alerts"] is None
    assert summary["monthly"]["false_alerts"] is None


def test_irrelevant_resource_units_are_lowest_for_acp(summary):
    assert (
        summary["acp"]["irrelevant_units"]
        < summary["monthly"]["irrelevant_units"]
        < summary["static"]["irrelevant_units"]
    )


def test_false_trigger_probability_formula():
    assert false_trigger_probability(0.28) == pytest.approx(0.0008 + 0.012 * 2.718281828 ** -1.456, rel=1e-4)
    assert false_trigger_probability(0.18) > false_trigger_probability(0.38)


@pytest.mark.slow
def test_sensitivity_is_budget_dominated_not_threshold_dominated():
    rows = run_sensitivity()
    by_factor = {}
    for row in rows:
        by_factor.setdefault(row["budget_factor"], []).append(row["coverage_pct"])
    # Coverage barely moves across tau within a budget factor ...
    for coverages in by_factor.values():
        assert max(coverages) - min(coverages) < 1.0
    # ... but moves substantially across budget factors.
    means = {f: sum(v) / len(v) for f, v in by_factor.items()}
    assert means[1.15] - means[0.85] > 8.0
    assert 71.5 <= means[0.85] <= 73.5
    assert 79.5 <= means[1.00] <= 81.5
    assert 84.5 <= means[1.15] <= 86.5


@pytest.mark.slow
def test_higher_threshold_reduces_nuisance_alerts():
    rows = [r for r in run_sensitivity() if r["budget_factor"] == 1.0]
    by_tau = {r["tau"]: r["false_alerts"] for r in rows}
    assert by_tau[0.18] > by_tau[0.38]
    for row in rows:
        assert row["expected_false_alerts"] == pytest.approx(
            (HORIZON_DAYS - 1) * false_trigger_probability(row["tau"]), abs=1e-3
        )
