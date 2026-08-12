"""Determinism: identical seed -> identical results."""
import numpy as np

from src import ScenarioParams
from src.scenarios import run_scenario
from src.sensitivity import run_ensemble, sample_lhs


def test_scenario_deterministic(graph):
    kw = dict(name="S3", seed_node="RDC1", seed_magnitude=0.55, T=150.0,
              h=0.05, x_cat=0.6)
    r1 = run_scenario(graph, ScenarioParams(1.60, 0.38, 0.8, 0.8), **kw)
    r2 = run_scenario(graph, ScenarioParams(1.60, 0.38, 0.8, 0.8), **kw)
    assert np.array_equal(r1.sim.X, r2.sim.X)
    assert r1.T_cat == r2.T_cat


def test_lhs_deterministic():
    a = sample_lhs(30, 0.8, 0.8, seed=42)
    b = sample_lhs(30, 0.8, 0.8, seed=42)
    assert np.array_equal(a, b)


def test_ensemble_deterministic(graph):
    r1 = run_ensemble(graph, name="S3", kappa_scale=1.60, xi=0.38, N=4,
                      T=150.0, seed=7)
    r2 = run_ensemble(graph, name="S3", kappa_scale=1.60, xi=0.38, N=4,
                      T=150.0, seed=7)
    assert [x["catastrophe"] for x in r1] == [x["catastrophe"] for x in r2]
    assert [x["T_cat"] for x in r1] == [x["T_cat"] for x in r2]
