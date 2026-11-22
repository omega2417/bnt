"""Calibration map, determinism of the stream generator and the formal propositions."""
import math

import numpy as np

from ebaw.benchmark import EmpiricalCalibrator
from ebaw.model import BASE, Calibrator, scenario_params, wilson_lcb
from ebaw.sim import MAIN_POLICIES, SHORT, generate, run, summarize
from ebaw.stats import n_two_proportions, rule_of_three_n, zero_event_upper


def test_calibrator_monotone_and_conservative():
    cal = Calibrator(BASE, 42)
    assert np.all(np.diff(cal.lcb) >= 0)
    assert np.all(cal.lcb <= cal.phat + 1e-12)
    s = np.linspace(0, 1, 1001)
    assert np.all(np.diff(cal(s)) >= 0)


def test_empirical_calibrator_matches_definition():
    rng = np.random.default_rng(0)
    y = (rng.random(5000) < 0.7).astype(int)
    s = np.where(y == 1, rng.beta(6, 1.5, 5000), rng.beta(1.5, 4, 5000))
    c = EmpiricalCalibrator(s, y, 10)
    assert np.all(np.diff(c.lcb) >= 0) and np.all(c.lcb <= c.phat + 1e-12)


def test_wilson_lcb_bounds():
    assert wilson_lcb(0, 10, 1.645) == 0.0
    assert 0 < wilson_lcb(9, 10, 1.645) < 0.9


def test_generator_is_deterministic_and_synchronized():
    cal = Calibrator(BASE, 42)
    a = generate(scenario_params("S0"), 42, cal)
    b = generate(scenario_params("S0"), 42, cal)
    assert [(p.t_prop, p.action, p.kind, p.s if p.kind == "gen" else 0) for p in a] == \
        [(p.t_prop, p.action, p.kind, p.s if p.kind == "gen" else 0) for p in b]
    # synchronized CRN: base genuine proposals are identical across scenarios that do not change them
    c = generate(scenario_params("S3"), 42, cal)
    ga = [(round(p.t_obs, 9), p.action, p.y) for p in a if p.kind == "gen"]
    gc = [(round(p.t_obs, 9), p.action, p.y) for p in c if p.kind == "gen"]
    assert ga == gc


def test_headline_properties_one_replication():
    cal = Calibrator(BASE, 42)
    P = scenario_params("S5")
    props = generate(P, 42, cal)
    res = {SHORT[p.name]: summarize(run(P, props, p), props) for p in MAIN_POLICIES}
    assert res["EB"]["adv_exec"] == 0 and res["EB"]["viol"] == 0
    assert res["AD"]["adv_exec"] == res["AD"]["n_adv"]
    assert res["EB"]["UER"] < res["CO"]["UER"] < res["AD"]["UER"]


def test_sample_size_and_rule_of_three():
    assert n_two_proportions(0.053, 0.015) == 354        # Section 6.3
    assert rule_of_three_n(0.01) == 300
    assert math.isclose(zero_event_upper(300), 0.00994, rel_tol=1e-2)
