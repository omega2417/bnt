"""Equation (5) and the statistical aggregation of Section 3.8."""

import pytest

from acp_sme.capabilities import BY_CODE
from acp_sme.metrics import Z95, coverage, mean_ci, paired_difference, percentile
from acp_sme.metrics import TraceOutcome


def test_coverage_is_effectiveness_weighted():
    demand = {"GOV": 1.0, "AST": 1.0}
    assert coverage(("GOV",), demand) == pytest.approx(0.93 / 2.0)
    assert coverage(("GOV", "AST"), demand) == pytest.approx((0.93 + 0.92) / 2.0)


def test_full_selection_never_reaches_one_because_effectiveness_is_below_one():
    demand = {code: 1.0 for code in BY_CODE}
    assert coverage(tuple(BY_CODE), demand) < 1.0


def test_empty_profile_has_zero_coverage():
    assert coverage((), {"GOV": 1.0}) == 0.0


def test_zero_demand_is_fully_covered_by_definition():
    assert coverage((), {code: 0.0 for code in BY_CODE}) == 1.0


def test_percentile_interpolates():
    values = [0.0, 1.0, 2.0, 3.0, 4.0]
    assert percentile(values, 0) == 0.0
    assert percentile(values, 100) == 4.0
    assert percentile(values, 50) == 2.0


def test_percentile_of_empty_sequence_is_an_error():
    with pytest.raises(ValueError):
        percentile([], 10)


def test_mean_ci_uses_the_normal_approximation():
    values = [1.0, 2.0, 3.0, 4.0, 5.0]
    interval = mean_ci(values)
    assert interval.mean == pytest.approx(3.0)
    assert interval.n == 5
    half = interval.mean - interval.low
    from statistics import stdev
    from math import sqrt

    assert half == pytest.approx(Z95 * stdev(values) / sqrt(5))


def test_single_trace_has_a_degenerate_interval():
    interval = mean_ci([2.0])
    assert (interval.mean, interval.low, interval.high) == (2.0, 2.0, 2.0)


def _outcome(archetype, replicate, condition, coverage_value):
    return TraceOutcome(
        archetype, replicate, condition, coverage_value, 0.0, 0.0, 0.0, 0.0, 0.0, 0
    )


def test_paired_difference_matches_scenario_and_replicate():
    left = [_outcome("micro", 0, "acp", 0.80), _outcome("small", 0, "acp", 0.70)]
    right = [_outcome("small", 0, "static", 0.60), _outcome("micro", 0, "static", 0.75)]
    interval, positive, n = paired_difference(left, right)
    assert n == 2 and positive == 2
    assert interval.mean == pytest.approx(7.5)


def test_paired_difference_rejects_an_unmatched_trace():
    left = [_outcome("micro", 0, "acp", 0.8)]
    right = [_outcome("micro", 1, "static", 0.7)]
    with pytest.raises(ValueError):
        paired_difference(left, right)
