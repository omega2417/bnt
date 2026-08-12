"""Positive invariance of the feasible domain (Theorem 1) and scenario regimes."""
import numpy as np
import pytest

from src import ScenarioParams
from src.scenarios import run_scenario


@pytest.mark.parametrize("ks,xi", [(0.93, 0.55), (1.60, 0.75), (1.60, 0.38)])
def test_state_bounds(graph, ks, xi):
    r = run_scenario(graph, ScenarioParams(ks, xi, 0.8, 0.8), name="t",
                     seed_node="RDC1", seed_magnitude=0.55, T=200.0, h=0.05,
                     x_cat=0.6)
    assert not r.sim.nan_flag
    assert r.sim.X.min() >= 0.0 and r.sim.X.max() <= 1.0
    assert r.sim.Q.min() >= 0.0
    assert np.all(np.isfinite(r.sim.X)) and np.all(np.isfinite(r.sim.Q))


def test_S1_absorbs(graph):
    r = run_scenario(graph, ScenarioParams(0.93, 0.55, 0.8, 0.8), name="S1",
                     seed_node="RDC1", seed_magnitude=0.55, T=200.0, h=0.05,
                     x_cat=0.6)
    assert not r.catastrophe
    assert r.max_dalA < 0.1


def test_S2_contains(graph):
    r = run_scenario(graph, ScenarioParams(1.60, 0.75, 0.8, 0.8), name="S2",
                     seed_node="RDC1", seed_magnitude=0.55, T=400.0, h=0.05,
                     x_cat=0.6)
    assert not r.catastrophe
    assert r.max_dalA < 0.6


def test_S3_catastrophe(graph):
    r = run_scenario(graph, ScenarioParams(1.60, 0.38, 0.8, 0.8), name="S3",
                     seed_node="RDC1", seed_magnitude=0.55, T=400.0, h=0.05,
                     x_cat=0.6)
    assert r.catastrophe
    assert r.T_cat is not None and 60.0 < r.T_cat < 160.0
