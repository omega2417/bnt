"""Parametric bracket and analytic evaluator (Section 6.2)."""

from __future__ import annotations

import numpy as np
import pytest

from evoproto.design import (
    DESIGN_VARIABLES,
    BracketSpec,
    analog_prior_sampler,
    bounds_array,
    evaluate,
    evaluate_population,
    feasible_fraction_uniform,
    template_ratio_sampler,
    uniform_sampler,
)


def test_tip_load_follows_table_6():
    spec = BracketSpec()
    assert spec.tip_load == pytest.approx(2.0 * 5 * 9.81)     # 98.1 N


def test_solid_section_reduces_to_the_textbook_cantilever():
    # With rho = 1 and a wall thick enough to fill the section, the model must
    # return delta = P L^3 / (3 E I) for a solid rectangle, I = b h^3 / 12.
    spec = BracketSpec()
    b, h = 0.030, 0.050
    x = np.array([[b, h, h / 2, 1.0]])
    f, _, extras = evaluate_population(x, spec)
    inertia = b * h**3 / 12.0
    expected = spec.tip_load * spec.length**3 / (3.0 * spec.modulus * inertia)
    assert f[0, 1] == pytest.approx(expected, rel=1e-9)
    assert f[0, 0] == pytest.approx(spec.rho_solid * b * h * spec.length, rel=1e-9)


def test_hollow_section_is_lighter_and_less_stiff_than_solid():
    spec = BracketSpec()
    solid = evaluate([0.030, 0.050, 0.025, 1.0], spec)
    hollow = evaluate([0.030, 0.050, 0.001, 0.10], spec)
    assert hollow["objectives"]["mass_kg"] < solid["objectives"]["mass_kg"]
    assert hollow["objectives"]["deflection_m"] > solid["objectives"]["deflection_m"]


def test_gibson_ashby_scaling_enters_the_rigidity():
    spec = BracketSpec()
    dense = evaluate([0.030, 0.050, 0.001, 0.8], spec)
    sparse = evaluate([0.030, 0.050, 0.001, 0.2], spec)
    ratio = dense["EI_Nm2"] / sparse["EI_Nm2"]
    assert ratio > 1.0            # E_core scales with rho^2, so density stiffens


def test_constraints_are_normalized_margins():
    spec = BracketSpec()
    record = evaluate([0.040, 0.060, 0.002, 0.3], spec)
    assert set(record["constraints"]) == {
        "deflection", "yield", "buckling", "mass", "wall_fit"
    }
    assert record["feasible"] == all(v >= 0 for v in record["constraints"].values())
    assert record["violation"] == pytest.approx(
        sum(max(0.0, -v) for v in record["constraints"].values())
    )


def test_degenerate_geometry_is_infeasible_not_crashing():
    spec = BracketSpec()
    record = evaluate([0.010, 0.010, 0.004, 1.0], spec)    # walls meet in the middle
    assert np.isfinite(record["objectives"]["mass_kg"])
    assert record["feasible"] is False


def test_uniform_feasible_fraction_is_about_one_percent():
    # Section 6.2 reports about 1 % under Table 6 (MODELED, 20 000 samples):
    # the constraints bind, so the task discriminates between search strategies.
    fraction = feasible_fraction_uniform(BracketSpec(), n_samples=20_000, seed=0)
    assert 0.002 < fraction < 0.05


def test_samplers_stay_inside_the_design_space():
    spec = BracketSpec()
    lower, upper = bounds_array(spec)
    rng = np.random.default_rng(0)
    for sampler in (uniform_sampler(spec), analog_prior_sampler(spec),
                    template_ratio_sampler(spec)):
        x = sampler(500, rng)
        assert x.shape == (500, len(DESIGN_VARIABLES))
        assert np.all(x >= lower - 1e-12) and np.all(x <= upper + 1e-12)


def test_analog_prior_concentrates_on_thin_walls_and_light_cores():
    spec = BracketSpec()
    rng = np.random.default_rng(1)
    analog = analog_prior_sampler(spec)(4000, rng)
    uniform = uniform_sampler(spec)(4000, rng)
    assert np.median(analog[:, 2]) < np.median(uniform[:, 2])   # wall thickness
    assert np.median(analog[:, 3]) < np.median(uniform[:, 3])   # core density


def test_evaluator_rejects_wrong_dimensionality():
    with pytest.raises(ValueError):
        evaluate_population(np.zeros((3, 2)))
