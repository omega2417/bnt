"""Simulator behaviour and Table A2/A3 conformance."""

import pytest

from acp_sme.scenarios import ARCHETYPES, BY_KEY, DEMAND_CAP, HORIZON_DAYS
from acp_sme.selector import assert_invariants
from acp_sme.simulator import (
    MONTHLY_REVIEW_DAYS,
    PRIMARY_TAU,
    TRIGGERED_DELAY_WEIGHTS,
    false_trigger_probability,
    observe,
    run_trace,
)


def test_scenario_inputs_match_table_4():
    expected = {"micro": (8, 34, 4), "small": (46, 45, 5), "medium": (180, 54, 5)}
    for key, (staff, budget, events) in expected.items():
        archetype = BY_KEY[key]
        assert (archetype.staff, archetype.budget, len(archetype.events)) == (
            staff, budget, events,
        )


def test_event_days_match_table_a2():
    assert [e.day for e in BY_KEY["micro"].events] == [20, 45, 72, 96]
    assert [e.day for e in BY_KEY["small"].events] == [18, 40, 67, 91, 108]
    assert [e.day for e in BY_KEY["medium"].events] == [15, 34, 59, 80, 103]


def test_demand_accumulates_at_the_event_day_and_never_before():
    archetype = BY_KEY["micro"]
    assert archetype.demand_at(19)["CLD"] == 0.0
    assert archetype.demand_at(20)["CLD"] == pytest.approx(0.95)
    assert archetype.demand_at(119)["CLD"] == pytest.approx(0.95)


def test_demand_is_capped():
    for archetype in ARCHETYPES:
        for value in archetype.demand_at(HORIZON_DAYS - 1).values():
            assert value <= DEMAND_CAP


def test_micro_dat_demand_is_capped_by_accumulated_events():
    # 0.90 base + 0.45 + 0.45 = 1.80, capped at 1.75.
    assert BY_KEY["micro"].demand_at(119)["DAT"] == pytest.approx(DEMAND_CAP)


def test_proxy_score_is_the_disclosed_root_mean_square():
    event = BY_KEY["micro"].events[0]  # CLD +0.95, TPR +0.65, IAM +0.35
    expected = ((0.95 ** 2 + 0.65 ** 2 + 0.35 ** 2) / 3) ** 0.5
    assert event.proxy_score_base() == pytest.approx(expected)


def test_designed_event_magnitudes_sit_well_above_the_primary_threshold():
    """Section 5.4: this separation is why coverage barely responds to tau."""
    for archetype in ARCHETYPES:
        for event in archetype.events:
            assert event.proxy_score_base() > PRIMARY_TAU + 0.2


def test_triggered_delay_weights_are_a_distribution():
    assert sum(TRIGGERED_DELAY_WEIGHTS) == pytest.approx(1.0)
    assert all(w > 0 for w in TRIGGERED_DELAY_WEIGHTS)


def test_all_three_conditions_share_the_day_zero_profile():
    trace = run_trace(ARCHETYPES[2], 3)
    day0 = {c: t.profiles[0] for c, t in trace.conditions.items()}
    assert len(set(day0.values())) == 1


def test_static_condition_never_changes():
    trace = run_trace(ARCHETYPES[0], 1)
    profiles = trace.conditions["static"].profiles
    assert len(set(profiles)) == 1
    assert trace.conditions["static"].reassessment_days == ()


def test_monthly_condition_only_changes_on_review_days():
    trace = run_trace(ARCHETYPES[1], 2)
    profiles = trace.conditions["monthly"].profiles
    change_days = {d for d in range(1, HORIZON_DAYS) if profiles[d] != profiles[d - 1]}
    assert change_days <= set(MONTHLY_REVIEW_DAYS)


def test_acp_reassessments_follow_events_and_nuisance_triggers():
    trace = run_trace(ARCHETYPES[0], 5)
    days = set(trace.conditions["acp"].reassessment_days)
    assert days == set(trace.triggered_review_days) | set(trace.false_trigger_days)


def test_acp_reacts_within_the_disclosed_delay_window():
    for replicate in range(10):
        trace = run_trace(ARCHETYPES[0], replicate)
        for event_day, review_day in zip(trace.event_days, trace.triggered_review_days):
            assert 0 <= review_day - event_day <= 8


def test_every_profile_in_every_condition_respects_the_budget():
    from acp_sme.capabilities import cost_of, is_dependency_valid

    for archetype in ARCHETYPES:
        trace = run_trace(archetype, 0)
        for condition in trace.conditions.values():
            for profile in set(condition.profiles):
                assert cost_of(profile) <= archetype.budget
                assert is_dependency_valid(profile)


def test_budget_factor_scales_the_envelope():
    low = run_trace(ARCHETYPES[2], 0, budget_factor=0.85)
    high = run_trace(ARCHETYPES[2], 0, budget_factor=1.15)
    assert low.budget < ARCHETYPES[2].budget < high.budget


def test_observation_is_clipped_to_the_valid_range():
    from random import Random

    demand = {"GOV": 0.0, "XRI": DEMAND_CAP}
    for seed in range(30):
        observed = observe(demand, Random(seed), sigma=0.5, attenuate=True)
        assert all(0.0 <= v <= DEMAND_CAP for v in observed.values())


def test_attenuation_only_touches_immersive_twin_and_ai_signals():
    from random import Random

    from acp_sme.capabilities import CODES

    demand = {code: 1.0 for code in CODES}
    # sigma = 0 isolates the attenuation branch from the noise branch.
    attenuated = set()
    for seed in range(400):
        observed = observe(demand, Random(seed), sigma=0.0, attenuate=True)
        for code, value in observed.items():
            if value < 0.9:
                attenuated.add(code)
    assert attenuated <= {"XRI", "DTI", "AIG"}
    assert attenuated, "expected at least one attenuated draw in 400 seeds"


def test_false_trigger_probability_is_monotone_decreasing_in_tau():
    values = [false_trigger_probability(t) for t in (0.18, 0.23, 0.28, 0.33, 0.38)]
    assert values == sorted(values, reverse=True)
    assert all(0.0 < v < 0.02 for v in values)
