"""Solver correctness: GL weights, grid convergence, GL vs ABM, integer-order."""
import numpy as np

from src.ima_dynamics import IMADynamics, ScenarioParams
from src.fractional_solver import solve_gl, solve_abm, gl_weights


def _seed_state(graph, dyn):
    x0 = np.zeros(graph.n)
    x0[graph.index["RDC1"]] = 0.55
    return x0, dyn.q_star.copy()


def test_gl_weights_alpha_one():
    # for alpha=1 the GL weights are 1, -1, 0, 0, ... (first difference)
    c = gl_weights(1.0, 5)
    assert np.isclose(c[0], 1.0)
    assert np.isclose(c[1], -1.0)
    assert np.allclose(c[2:], 0.0)


def test_caputo_preserves_constant(graph):
    # C D^alpha of a constant is zero -> a state at equilibrium stays put
    dyn = IMADynamics(graph, ScenarioParams(0.0, 5.0, 0.8, 0.8), 0.05)  # no coupling
    q0 = dyn.q_star.copy()
    x0 = np.zeros(graph.n)
    sim = solve_gl(dyn, x0, q0, 20.0)
    assert np.max(np.abs(sim.Q - q0)) < 1e-6
    assert np.max(np.abs(sim.X)) < 1e-6


def test_grid_convergence(graph):
    p = ScenarioParams(0.93, 0.55, 0.8, 0.8)
    dyn1 = IMADynamics(graph, p, 0.05)
    x0, q0 = _seed_state(graph, dyn1)
    s1 = solve_gl(dyn1, x0, q0, 60.0)
    s2 = solve_gl(IMADynamics(graph, p, 0.025), x0, q0, 60.0)
    idx = (s1.t / 0.025).round().astype(int)
    dev = np.max(np.abs(s1.X - s2.X[idx]))
    assert dev < 1e-2          # first-order scheme, coarse grid


def test_gl_vs_abm_agreement(graph):
    p = ScenarioParams(0.93, 0.55, 0.8, 0.8)
    dyn = IMADynamics(graph, p, 0.05)
    x0, q0 = _seed_state(graph, dyn)
    gl = solve_gl(dyn, x0, q0, 60.0)
    abm = solve_abm(dyn, x0, q0, 60.0)
    assert np.max(np.abs(gl.X - abm.X)) < 1e-2


def test_integer_order_baseline_runs(graph):
    p = ScenarioParams(1.60, 0.38, 1.0, 1.0)
    dyn = IMADynamics(graph, p, 0.05)
    x0, q0 = _seed_state(graph, dyn)
    sim = solve_gl(dyn, x0, q0, 200.0)
    assert not sim.nan_flag
