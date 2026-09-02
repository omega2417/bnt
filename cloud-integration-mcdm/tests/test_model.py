"""Unit tests for the model, indicators and dominance machinery."""

import numpy as np
import pytest

from cimcdm import (
    DEFAULT_SCENARIO,
    PortfolioModel,
    das_dennis_directions,
    exact_front_coverage,
    generate_instance,
    hypervolume,
    igd_plus,
    load_published_instance,
    nondominated_mask,
    spacing,
)


@pytest.fixture(scope="module")
def model():
    return PortfolioModel(load_published_instance(), DEFAULT_SCENARIO)


def test_instance_shape(model):
    assert model.instance.n == 18
    assert model.instance.names[0] == "S01"
    assert model.instance.names[-1] == "S18"


def test_derived_bounds_match_table_2(model):
    assert model.budget == pytest.approx(172.84, abs=1e-9)
    assert model.time_cap == pytest.approx(43.4, abs=1e-9)
    assert model.coverage_minimum == pytest.approx(5.8382, abs=1e-4)


def test_vmax_uses_upper_rate_boundary(model):
    """Vmax is evaluated at s_alpha = s_beta = 1.5 and held fixed thereafter."""
    baseline = PortfolioModel(model.instance, DEFAULT_SCENARIO, 1.0, 1.0)
    stretched = PortfolioModel(model.instance, DEFAULT_SCENARIO, 1.5, 1.5)
    assert baseline.v_max == pytest.approx(stretched.v_max)
    # Benefit at the upper boundary must not exceed the normalization constant.
    assert stretched.benefit.sum() <= stretched.v_max + 1e-12


def test_objectives_are_minimization_and_bounded(model):
    x = np.ones(model.instance.n)
    f = model.objectives(x)
    assert f.shape == (3,)
    assert 0.0 <= f[0] <= 1.0
    assert f[1] == pytest.approx(1.0)  # every system selected: full cost
    assert 0.0 <= f[2] <= 1.0


def test_empty_portfolio_is_infeasible(model):
    assert not model.is_feasible(np.zeros(model.instance.n))
    assert model.constraint_violation(np.zeros(model.instance.n)) > 0


def test_all_systems_violates_budget(model):
    """Selecting everything must break the 58% budget by construction."""
    x = np.ones(model.instance.n)
    assert not model.is_feasible(x)


def test_published_knee_is_feasible(model):
    knee = {"S01", "S04", "S05", "S10", "S12", "S13", "S16", "S17", "S18"}
    x = np.array([1.0 if n in knee else 0.0 for n in model.instance.names])
    assert model.is_feasible(x)
    assert model.constraint_violation(x) == pytest.approx(0.0)
    info = model.describe(x)
    assert info["cost_units"] == pytest.approx(124.0)
    assert info["effort_units"] == pytest.approx(35.0)


def test_batch_and_single_objectives_agree(model):
    rng = np.random.default_rng(7)
    X = (rng.random((16, model.instance.n)) < 0.5).astype(float)
    batch = model.objectives(X)
    for i, row in enumerate(X):
        assert model.objectives(row) == pytest.approx(batch[i])


def test_risk_decays_towards_residual(model):
    """r_i(t) is monotone non-increasing and bounded below by the residual risk."""
    inst = model.instance
    assert np.all(model.risk <= inst.risk_initial + 1e-12)
    assert np.all(model.risk >= inst.risk_residual - 1e-12)


def test_benefit_increases_with_faster_rates(model):
    slow = PortfolioModel(model.instance, DEFAULT_SCENARIO, 0.5, 0.5)
    fast = PortfolioModel(model.instance, DEFAULT_SCENARIO, 1.5, 1.5)
    assert np.all(fast.benefit >= slow.benefit - 1e-12)


def test_nondominated_mask_on_known_set():
    F = np.array([[0.0, 1.0], [1.0, 0.0], [0.5, 0.5], [2.0, 2.0]])
    assert nondominated_mask(F).tolist() == [True, True, True, False]


def test_nondominated_mask_keeps_duplicates():
    F = np.array([[1.0, 1.0], [1.0, 1.0]])
    assert nondominated_mask(F).sum() == 2


def test_hypervolume_unit_square():
    assert hypervolume(np.array([[0.0, 0.0]]), (1.0, 1.0)) == pytest.approx(1.0)


def test_hypervolume_unit_cube():
    assert hypervolume(np.array([[0.0, 0.0, 0.0]]), (1.0, 1.0, 1.0)) == pytest.approx(1.0)


def test_hypervolume_two_boxes():
    """Two non-dominating points; union of the two axis-aligned boxes."""
    F = np.array([[0.0, 0.5, 0.0], [0.5, 0.0, 0.0]])
    expected = 1.0 * 0.5 * 1.0 + 0.5 * 1.0 * 1.0 - 0.5 * 0.5 * 1.0
    assert hypervolume(F, (1.0, 1.0, 1.0)) == pytest.approx(expected)


def test_hypervolume_ignores_dominated_reference_points():
    F = np.array([[0.0, 0.0, 0.0], [2.0, 2.0, 2.0]])
    assert hypervolume(F, (1.0, 1.0, 1.0)) == pytest.approx(1.0)


def test_igd_plus_is_zero_for_exact_match():
    R = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    assert igd_plus(R, R) == pytest.approx(0.0)


def test_igd_plus_ignores_improvement():
    """IGD+ counts only shortfall, so dominating the reference costs nothing."""
    R = np.array([[0.5, 0.5, 0.5]])
    better = np.array([[0.1, 0.1, 0.1]])
    assert igd_plus(better, R) == pytest.approx(0.0)


def test_spacing_is_zero_for_evenly_spaced_points():
    F = np.array([[0.0, 0.0], [1.0, 1.0], [2.0, 2.0]])
    assert spacing(F) == pytest.approx(0.0, abs=1e-12)


def test_coverage_bounds():
    R = np.array([[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]])
    assert exact_front_coverage(R, R) == pytest.approx(1.0)
    assert exact_front_coverage(np.array([[9.0, 9.0, 9.0]]), R) == pytest.approx(0.0)
    assert exact_front_coverage(R[:1], R) == pytest.approx(0.5)


def test_das_dennis_counts():
    """H = 9 gives 55 directions and H = 20 gives 231, as in Table 3."""
    assert len(das_dennis_directions(3, 9)) == 55
    assert len(das_dennis_directions(3, 20)) == 231
    assert np.allclose(das_dennis_directions(3, 9).sum(axis=1), 1.0)


def test_generated_instance_is_deterministic_and_in_range():
    a = generate_instance(20260902)
    b = generate_instance(20260902)
    assert np.allclose(a.cost, b.cost)
    assert np.allclose(a.alpha, b.alpha)
    assert np.all(a.risk_residual <= a.risk_initial)
    assert np.all((a.cost >= 8) & (a.cost <= 26))
    assert np.all((a.effort >= 1) & (a.effort <= 6))
