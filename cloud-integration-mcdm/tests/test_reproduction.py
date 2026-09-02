"""Reproduction tests: the published numbers must come back out of the code.

The exact-enumeration tests are deterministic and strict. The evolutionary test
is stochastic and therefore only asserts that a short run lands close to the
exact front, not that it matches a published mean.
"""

import numpy as np
import pytest

from cimcdm import (
    DEFAULT_ALGORITHM,
    DEFAULT_SCENARIO,
    AlgorithmConfig,
    PortfolioModel,
    enumerate_exact,
    load_published_instance,
    run_nsga2,
    run_nsga3,
    run_weighted_sum,
    validate_exact,
    validate_scenario,
)
from cimcdm.validation import PUBLISHED


@pytest.fixture(scope="module")
def model():
    return PortfolioModel(load_published_instance(), DEFAULT_SCENARIO)


@pytest.fixture(scope="module")
def exact(model):
    return enumerate_exact(model)


def test_scenario_bounds_reproduce(model):
    checks = validate_scenario(model)
    failed = [c.name for c in checks if not c.passed]
    assert not failed, f"failed checks: {failed}"


def test_exact_enumeration_reproduces_every_published_claim(exact):
    checks = validate_exact(exact)
    failed = [str(c) for c in checks if not c.passed]
    assert not failed, "failed checks:\n" + "\n".join(failed)


def test_feasible_count(exact):
    assert exact.n_total == 262_144
    assert exact.n_feasible == 83_657
    assert round(100 * exact.feasible_fraction, 2) == 31.91


def test_front_size_and_hypervolume(exact):
    assert exact.front_size == 446
    assert exact.hypervolume == pytest.approx(PUBLISHED["exact_hypervolume"], abs=1e-6)


def test_knee_portfolio(exact):
    assert exact.knee.selected == PUBLISHED["knee_systems"]
    assert exact.knee.benefit == pytest.approx(PUBLISHED["knee_benefit"], abs=1e-5)
    assert exact.knee.cost_units == pytest.approx(124.0)
    assert exact.knee.effort_units == pytest.approx(35.0)


def test_every_front_member_is_feasible_and_nondominated(model, exact):
    assert np.all(model.is_feasible(exact.X_front))
    F = exact.F_front
    for i in range(len(F)):
        dominated = np.all(F <= F[i], axis=1) & np.any(F < F[i], axis=1)
        assert not dominated.any(), f"front member {i} is dominated"


def test_weighted_sum_reproduces_table_5(model, exact):
    run, n_weights = run_weighted_sum(
        model, exact.F_feasible, exact.X_feasible, DEFAULT_ALGORITHM
    )
    assert n_weights == 231
    assert len(run.F) == PUBLISHED["wsm_front_size"]

    from cimcdm import evaluate_front

    quality = evaluate_front(run.F, exact.F_front, DEFAULT_SCENARIO.reference_point)
    assert quality["hypervolume"] == pytest.approx(PUBLISHED["wsm_hypervolume"], abs=1e-5)
    assert round(100 * quality["coverage"], 2) == PUBLISHED["wsm_coverage_percent"]


@pytest.mark.parametrize("runner", [run_nsga2, run_nsga3])
def test_short_evolutionary_run_approaches_exact_front(model, exact, runner):
    """A 25-generation run should already recover most of the exact hypervolume.

    Table 4 of the article reports 0.4138 at generation 25, i.e. 98.2% of the
    exact hypervolume. The threshold here is deliberately looser so that the
    test is not flaky across NumPy versions and platforms.
    """
    config = AlgorithmConfig(population=60, generations=25)
    run = runner(model, seed=1001, config=config)

    assert np.all(model.is_feasible(run.X)), "archive contains infeasible portfolios"
    assert run.hypervolume_history[-1] >= run.hypervolume_history[0]
    assert run.hypervolume_history[-1] / exact.hypervolume > 0.96
    assert run.cpu_time > 0.0


def test_sensitivity_corners(model):
    """Table 7: the low and high temporal-rate corners."""
    instance = model.instance
    low = enumerate_exact(PortfolioModel(instance, DEFAULT_SCENARIO, 0.5, 0.5))
    high = enumerate_exact(PortfolioModel(instance, DEFAULT_SCENARIO, 1.5, 1.5))

    assert low.front_size == PUBLISHED["sensitivity_low_front"]
    assert high.front_size == PUBLISHED["sensitivity_high_front"]
    assert low.hypervolume == pytest.approx(
        PUBLISHED["sensitivity_low_hypervolume"], abs=1e-5
    )
    assert high.hypervolume == pytest.approx(
        PUBLISHED["sensitivity_high_hypervolume"], abs=1e-5
    )
    assert low.knee.selected == high.knee.selected == PUBLISHED["knee_systems"]
