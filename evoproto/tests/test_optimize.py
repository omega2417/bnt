"""Dominance, hypervolume, diversity and the search loop (Section 4.5)."""

from __future__ import annotations

import numpy as np
import pytest

from evoproto.design import (
    BracketSpec,
    analog_prior_sampler,
    bounds_array,
    evaluate_population,
    uniform_sampler,
)
from evoproto.optimize import (
    constrained_search,
    crowding_distance,
    design_diversity,
    dominates,
    heuristic_refinement_search,
    hypervolume_2d,
    non_dominated_sort,
    normalized_hypervolume,
    pareto_front,
)


def test_dominance_definition():
    assert dominates([1, 1], [2, 2])
    assert dominates([1, 2], [1, 3])
    assert not dominates([1, 3], [2, 2])
    assert not dominates([1, 1], [1, 1])       # equality is not dominance


def test_hypervolume_against_a_hand_computed_case():
    # Front (1,3), (2,2), (3,1) with reference (4,4):
    #   (1,3): (4-1)(4-3) = 3
    #   (2,2): (4-2)(3-2) = 2
    #   (3,1): (4-3)(2-1) = 1     total 6
    front = np.array([[1.0, 3.0], [2.0, 2.0], [3.0, 1.0]])
    assert hypervolume_2d(front, (4.0, 4.0)) == pytest.approx(6.0)


def test_hypervolume_ignores_points_outside_the_reference_box():
    front = np.array([[1.0, 3.0], [5.0, 0.5]])
    assert hypervolume_2d(front, (4.0, 4.0)) == pytest.approx(3.0)
    assert hypervolume_2d(np.empty((0, 2)), (4.0, 4.0)) == 0.0


def test_hypervolume_is_monotone_under_improvement():
    worse = np.array([[2.0, 2.0]])
    better = np.array([[1.0, 1.0]])
    assert hypervolume_2d(better, (4.0, 4.0)) > hypervolume_2d(worse, (4.0, 4.0))


def test_normalized_hypervolume_is_bounded():
    assert normalized_hypervolume(np.array([[0.0, 0.0]]), (2.0, 2.0)) == pytest.approx(1.0)
    assert normalized_hypervolume(np.array([[1.0, 1.0]]), (2.0, 2.0)) == pytest.approx(0.25)


def test_non_dominated_sort_ranks_fronts():
    f = np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0]])
    fronts = non_dominated_sort(f)
    assert [list(front) for front in fronts] == [[0], [1], [2]]


def test_constraint_domination_prefers_feasible_then_least_violating():
    f = np.array([[5.0, 5.0], [1.0, 1.0], [2.0, 2.0]])
    violation = np.array([0.0, 3.0, 1.0])       # only the first is feasible
    fronts = non_dominated_sort(f, violation)
    assert list(fronts[0]) == [0]
    assert list(fronts[1]) == [2]               # smaller violation comes next
    assert list(fronts[2]) == [1]


def test_crowding_distance_is_infinite_at_the_extremes():
    f = np.array([[0.0, 3.0], [1.0, 2.0], [2.0, 1.0], [3.0, 0.0]])
    distance = crowding_distance(f)
    assert np.isinf(distance[0]) and np.isinf(distance[-1])
    assert np.all(np.isfinite(distance[1:-1]))


def test_pareto_front_indices():
    f = np.array([[1.0, 2.0], [2.0, 1.0], [3.0, 3.0]])
    assert list(pareto_front(f)) == [0, 1]


def test_design_diversity_bounds():
    lower, upper = np.zeros(2), np.ones(2)
    assert design_diversity(np.array([[0.5, 0.5]]), lower, upper) == 0.0
    identical = np.tile([0.3, 0.7], (5, 1))
    assert design_diversity(identical, lower, upper) == pytest.approx(0.0)
    spread = np.array([[0.0, 0.0], [1.0, 1.0]])
    assert design_diversity(spread, lower, upper) == pytest.approx(1.0)


def _bracket_evaluator(spec):
    def evaluator(x):
        f, g, _ = evaluate_population(x, spec)
        return f, g

    return evaluator


def test_search_is_reproducible_for_a_given_seed():
    spec = BracketSpec()
    lower, upper = bounds_array(spec)
    kwargs = {"population": 20, "generations": 6, "seed": 1234}
    a = constrained_search(_bracket_evaluator(spec), uniform_sampler(spec),
                           lower, upper, **kwargs)
    b = constrained_search(_bracket_evaluator(spec), uniform_sampler(spec),
                           lower, upper, **kwargs)
    assert np.allclose(a.x, b.x) and np.allclose(a.f, b.f)


def test_search_finds_feasible_designs_and_respects_bounds():
    spec = BracketSpec()
    lower, upper = bounds_array(spec)
    result = constrained_search(_bracket_evaluator(spec), analog_prior_sampler(spec),
                                lower, upper, population=30, generations=15, seed=7)
    assert np.any(result.feasible)
    assert np.all(result.x >= lower - 1e-12) and np.all(result.x <= upper + 1e-12)
    pareto_x, pareto_f = result.pareto()
    assert len(pareto_x) == len(pareto_f) >= 1
    assert len(pareto_front(pareto_f)) == len(pareto_f)   # the set is non-dominated


def test_generation_log_and_evaluation_budget():
    spec = BracketSpec()
    lower, upper = bounds_array(spec)
    result = constrained_search(_bracket_evaluator(spec), uniform_sampler(spec),
                                lower, upper, population=20, generations=8, seed=3)
    assert len(result.log) == 8
    assert result.evaluations == 20 * 9                    # initial + one per generation
    assert result.iterations_to_specification(cap=8) <= 8


def test_expert_arm_is_time_matched_not_evaluation_matched():
    spec = BracketSpec()
    lower, upper = bounds_array(spec)
    expert = heuristic_refinement_search(
        _bracket_evaluator(spec), uniform_sampler(spec), lower, upper,
        n_variants=4, rounds=25, seed=5)
    computational = constrained_search(
        _bracket_evaluator(spec), uniform_sampler(spec), lower, upper,
        population=40, generations=25, seed=5)
    assert expert.evaluations < computational.evaluations / 5
    assert len(expert.log) == 25
