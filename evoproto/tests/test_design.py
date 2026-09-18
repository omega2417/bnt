"""The parametric bracket and its analytic evaluator (Eqs. 15-19)."""

import numpy as np
import pytest

from evoproto import design


def test_tip_load_follows_table_6():
    spec = design.EOAT_BRACKET
    assert spec.tip_load == pytest.approx(2.0 * 5 * 9.81)
    assert spec.sigma_allow == pytest.approx(230e6 / 2.0)
    assert spec.reference_point == (spec.mass_max, spec.delta_max)


def test_second_moments_follow_equation_15():
    spec = design.EOAT_BRACKET
    b, h, t, rho = 0.030, 0.050, 0.001, 0.2
    result = design.evaluate([b, h, t, rho], spec)
    b_i, h_i = b - 2 * t, h - 2 * t
    assert result["I_shell"] == pytest.approx((b * h ** 3 - b_i * h_i ** 3) / 12.0)
    assert result["I_core"] == pytest.approx(b_i * h_i ** 3 / 12.0)


def test_flexural_rigidity_uses_the_gibson_ashby_scaling():
    spec = design.EOAT_BRACKET
    solid = design.evaluate([0.03, 0.05, 0.001, 1.0], spec)
    hollow = design.evaluate([0.03, 0.05, 0.001, 0.0], spec)
    # with rho = 1 the core contributes its full second moment
    assert solid["EI"] == pytest.approx(
        spec.material.E_s * (solid["I_shell"] + solid["I_core"])
    )
    assert hollow["EI"] == pytest.approx(spec.material.E_s * hollow["I_shell"])
    # the core stiffness scales as rho^2
    half = design.evaluate([0.03, 0.05, 0.001, 0.5], spec)
    assert (half["EI"] - hollow["EI"]) == pytest.approx(
        0.25 * (solid["EI"] - hollow["EI"])
    )


def test_deflection_and_stress_follow_equation_17():
    spec = design.EOAT_BRACKET
    d = [0.03, 0.05, 0.001, 0.2]
    result = design.evaluate(d, spec)
    assert result["deflection"] == pytest.approx(
        spec.tip_load * spec.L ** 3 / (3.0 * result["EI"])
    )
    assert result["stress"] == pytest.approx(
        spec.tip_load * spec.L * (d[1] / 2.0) / result["I_effective"]
    )
    nu = spec.material.nu
    assert result["stress_buckling"] == pytest.approx(
        (4 * np.pi ** 2 * spec.material.E_s / (12 * (1 - nu ** 2))) * (d[2] / d[0]) ** 2
    )


def test_mass_follows_equation_18():
    spec = design.EOAT_BRACKET
    b, h, t, rho = 0.03, 0.05, 0.001, 0.3
    result = design.evaluate([b, h, t, rho], spec)
    b_i, h_i = b - 2 * t, h - 2 * t
    expected = spec.material.rho_s * spec.L * ((b * h - b_i * h_i) + rho * b_i * h_i)
    assert result["mass"] == pytest.approx(expected)
    assert result["cost"] > result["mass"] * spec.material.cost_per_kg


def test_constraint_vector_has_the_five_margins_of_equation_19():
    result = design.evaluate([0.03, 0.05, 0.001, 0.2])
    assert tuple(result["constraints"]) == (
        "strength", "deflection", "buckling", "wall_thickness", "mass_cap",
    )


def test_a_degenerate_section_is_infeasible_rather_than_an_error():
    # a wall thicker than half the section leaves no interior
    result = design.evaluate([0.010, 0.010, 0.006, 0.5])
    assert not result["feasible"]
    assert result["constraints"]["wall_thickness"] < 0


def test_uniform_feasible_fraction_is_about_one_percent():
    """Section 6.2 reports ~1 % under the assumptions of Table 6 (20 000 samples)."""
    fraction = design.feasible_fraction_uniform(n_samples=20000, seed=0)
    assert 0.003 < fraction < 0.03


def test_results_are_tagged_modeled():
    result = design.evaluate([0.03, 0.05, 0.001, 0.2])
    assert result["tag"] == "MODELED"
    assert result["provenance"].tag.value == "MODELED"


def test_population_evaluation_matches_single_evaluation():
    rng = np.random.default_rng(0)
    lo, hi = design.design_bounds()
    X = lo + rng.random((16, 4)) * (hi - lo)
    batch = design.evaluate_population(X)
    for i, row in enumerate(X):
        single = design.evaluate(row)
        assert single["mass"] == pytest.approx(batch["mass"][i])
        assert single["deflection"] == pytest.approx(batch["deflection"][i])


def test_priors_stay_inside_the_design_box():
    lo, hi = design.design_bounds()
    rng = np.random.default_rng(1)
    for name, prior in design.PRIORS.items():
        X = prior(256, design.EOAT_BRACKET, rng)
        assert X.shape == (256, 4)
        assert np.all(X >= lo - 1e-12) and np.all(X <= hi + 1e-12), name


def test_template_projection_is_idempotent_and_keeps_the_family():
    rng = np.random.default_rng(2)
    X = design.template_ratio_prior(64, design.EOAT_BRACKET, rng)
    once = design.template_projection(X)
    twice = design.template_projection(once)
    assert np.allclose(once, twice)
    ratios = once[:, 1] / once[:, 0]
    assert np.all(np.min(np.abs(ratios[:, None] - np.array([1.0, 1.5, 2.0])), axis=1) < 1e-6)


def test_analog_prior_concentrates_on_thin_walls_and_light_cores():
    rng = np.random.default_rng(3)
    lo, hi = design.design_bounds()
    analog = design.analog_prior(2000, design.EOAT_BRACKET, rng)
    uniform = design.uniform_prior(2000, design.EOAT_BRACKET, rng)
    assert analog[:, 3].mean() < uniform[:, 3].mean()      # lighter core
    assert analog[:, 1].mean() > uniform[:, 1].mean()      # taller section
