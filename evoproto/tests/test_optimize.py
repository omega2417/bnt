"""Non-dominated sorting, hypervolume, diversity and Algorithm 1."""

import numpy as np
import pytest

from evoproto import design, optimize


def test_domination_is_strict():
    assert optimize.dominates([1.0, 1.0], [2.0, 2.0])
    assert optimize.dominates([1.0, 2.0], [1.0, 3.0])
    assert not optimize.dominates([1.0, 1.0], [1.0, 1.0])
    assert not optimize.dominates([1.0, 3.0], [2.0, 2.0])


def test_non_dominated_sort_splits_a_known_case_into_fronts():
    F = np.array([[1.0, 3.0], [2.0, 2.0], [3.0, 1.0], [4.0, 4.0]])
    fronts = optimize.non_dominated_sort(F)
    assert fronts[0] == [0, 1, 2]
    assert fronts[1] == [3]


def test_constraint_domination_prefers_feasible_then_least_violating():
    F = np.array([[5.0, 5.0], [1.0, 1.0], [2.0, 2.0]])
    violation = np.array([0.0, 3.0, 1.0])  # only the first design is feasible
    fronts = optimize.non_dominated_sort(F, violation)
    assert fronts[0] == [0]
    assert fronts[1] == [2]   # smaller violation beats better objectives
    assert fronts[2] == [1]


def test_crowding_distance_is_infinite_at_the_boundaries():
    F = np.array([[1.0, 4.0], [2.0, 3.0], [3.0, 2.0], [4.0, 1.0]])
    distances = optimize.crowding_distance(F)
    assert np.isinf(distances[0]) and np.isinf(distances[3])
    assert np.all(np.isfinite(distances[1:3]))


def test_hypervolume_matches_a_hand_computed_case():
    """Appendix A.3 on the staircase (1,3), (2,2), (3,1) with r = (4, 4)."""
    F = np.array([[1.0, 3.0], [2.0, 2.0], [3.0, 1.0]])
    assert optimize.hypervolume_2d(F, (4.0, 4.0)) == pytest.approx(6.0)


def test_hypervolume_of_a_single_point_is_the_rectangle():
    assert optimize.hypervolume_2d(np.array([[1.0, 1.0]]), (3.0, 5.0)) == pytest.approx(8.0)


def test_hypervolume_ignores_points_beyond_the_reference():
    F = np.array([[1.0, 1.0], [5.0, 0.5]])
    assert optimize.hypervolume_2d(F, (4.0, 4.0)) == pytest.approx(9.0)
    assert optimize.hypervolume_2d(np.array([[9.0, 9.0]]), (4.0, 4.0)) == 0.0


def test_hypervolume_is_monotone_under_adding_a_non_dominated_point():
    base = np.array([[2.0, 2.0]])
    extended = np.array([[2.0, 2.0], [1.0, 3.0]])
    assert optimize.hypervolume_2d(extended, (4.0, 4.0)) > optimize.hypervolume_2d(base, (4.0, 4.0))


def test_normalized_hypervolume_lies_in_the_unit_interval():
    F = np.array([[1.0, 1.0], [2.0, 0.5]])
    value = optimize.normalized_hypervolume(F, (4.0, 4.0))
    assert 0.0 <= value <= 1.0


def test_hypervolume_requires_two_objectives():
    with pytest.raises(ValueError):
        optimize.hypervolume_2d(np.zeros((3, 3)), (1.0, 1.0, 1.0))


def test_design_diversity_is_zero_for_identical_designs_and_scaled_by_dimension():
    lo, hi = np.zeros(4), np.ones(4)
    identical = np.ones((5, 4)) * 0.5
    assert optimize.design_diversity(identical, lo, hi) == pytest.approx(0.0)
    # two opposite corners of the unit box: distance sqrt(q), divided by sqrt(q)
    corners = np.array([np.zeros(4), np.ones(4)])
    assert optimize.design_diversity(corners, lo, hi) == pytest.approx(1.0)


def test_constraint_violation_sums_the_negative_margins():
    G = np.array([[1.0, -2.0, -0.5], [0.0, 1.0, 2.0]])
    assert optimize.constraint_violation(G).tolist() == [2.5, 0.0]


def _bracket_search(arm="C", seed=0, generations=12):
    spec = design.EOAT_BRACKET
    lo, hi = design.design_bounds(spec)
    prior = design.PRIORS[arm]

    def evaluator(X):
        out = design.evaluate_population(X, spec)
        return out["F"], out["G"]

    return optimize.search(
        evaluator,
        lambda n, rng: prior(n, spec, rng),
        lo, hi, population_size=24, generations=generations, seed=seed, arm=arm,
        projection=design.template_projection if arm == "A" else None,
    )


def test_search_is_reproducible_for_a_fixed_seed():
    first = _bracket_search(seed=42)
    second = _bracket_search(seed=42)
    assert np.array_equal(first.population, second.population)
    assert first.feasible_fraction_per_generation == second.feasible_fraction_per_generation


def test_search_respects_the_box_and_the_evaluation_budget():
    result = _bracket_search(seed=1, generations=10)
    lo, hi = design.design_bounds()
    assert np.all(result.population >= lo - 1e-12)
    assert np.all(result.population <= hi + 1e-12)
    assert result.evaluations == 24 * (10 + 1)


def test_archive_is_feasible_and_non_dominated():
    result = _bracket_search(seed=2)
    if result.archive.shape[0]:
        out = design.evaluate_population(result.archive)
        assert np.all(out["feasible"])
        fronts = optimize.non_dominated_sort(result.archive_objectives)
        assert len(fronts[0]) == result.archive.shape[0]


def test_its_is_the_first_generation_with_a_feasible_design():
    result = _bracket_search(seed=3)
    its = int(result.iterations_to_specification)
    log = result.feasible_fraction_per_generation
    assert log[its - 1] > 0
    assert all(value == 0 for value in log[: its - 1])


def test_its_is_capped_at_the_generation_count_when_nothing_is_feasible():
    lo, hi = np.zeros(2), np.ones(2)

    def evaluator(X):
        F = X.copy()
        G = -np.ones((X.shape[0], 1))  # nothing is ever feasible
        return F, G

    result = optimize.search(evaluator, lambda n, rng: rng.random((n, 2)), lo, hi,
                             population_size=8, generations=5, seed=0)
    assert result.iterations_to_specification == 5.0
    assert result.archive.shape[0] == 0
