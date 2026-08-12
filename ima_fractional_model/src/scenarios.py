"""Scenario orchestration: build initial conditions, run a simulation, and
extract catastrophe metrics (time-to-catastrophe, terminal cascade size, ...).

Catastrophe definition (Equation 1): the event that all DAL-A functions exceed
the certification degradation threshold x_cat,

    K = { x : min_{i in C_A} x_i >= x_cat },   T_cat = inf{ t : x(t) in K }.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, Optional

import numpy as np
import yaml

from .graph_model import IMAGraph, load_graph
from .ima_dynamics import IMADynamics, ScenarioParams
from .fractional_solver import solve_gl, SolverResult
from .cascade_threshold import cascade_threshold


@dataclass
class ScenarioResult:
    name: str
    Rc: float
    catastrophe: bool
    T_cat: Optional[float]
    terminal_cascade_size: float        # fraction of nodes degraded >= x_cat at T
    n_degraded: int
    peak_backlog: float
    max_dalA: float
    relaxation_time: Optional[float]
    sim: SolverResult = field(repr=False, default=None)
    params: Dict = field(default_factory=dict)


def build_initial_state(graph: IMAGraph, q_star: np.ndarray,
                        seed_node: str, seed_magnitude: float,
                        rng: Optional[np.random.Generator] = None,
                        backlog_pert: float = 0.0, bg_degradation: float = 0.0):
    """Nominal equilibrium (0, q*) plus a single-fault seed at ``seed_node``."""
    n = graph.n
    x0 = np.zeros(n)
    q0 = q_star.copy()
    if bg_degradation and rng is not None:
        x0 = np.clip(rng.uniform(0.0, bg_degradation, n), 0.0, 1.0)
    idx = graph.index[seed_node]
    x0[idx] = seed_magnitude
    if backlog_pert and rng is not None:
        q0 = np.maximum(q0 * (1.0 + rng.uniform(-backlog_pert, backlog_pert, n)), 0.0)
    return x0, q0


def detect_catastrophe(sim: SolverResult, dalA_idx: np.ndarray, x_cat: float):
    """Return (is_catastrophe, T_cat) per Equation (1)."""
    dalA = sim.X[:, dalA_idx]
    hit = np.all(dalA >= x_cat, axis=1)
    if np.any(hit):
        k = int(np.argmax(hit))
        return True, float(sim.t[k])
    return False, None


def relaxation_time(sim: SolverResult, x0: np.ndarray, frac: float = 0.05):
    """Time after which max degradation stays below ``frac`` (absorption)."""
    maxdeg = sim.X.max(axis=1)
    below = maxdeg < frac
    # last index where it is >= frac, then +1
    idx = np.where(~below)[0]
    if len(idx) == 0:
        return 0.0
    last = idx[-1]
    if last >= len(sim.t) - 1:
        return None       # not relaxed within horizon
    return float(sim.t[last + 1])


def run_scenario(graph: IMAGraph, params: ScenarioParams, *, name: str,
                 seed_node: str, seed_magnitude: float, T: float, h: float,
                 x_cat: float, short_memory: Optional[int] = None,
                 rng: Optional[np.random.Generator] = None,
                 backlog_pert: float = 0.0, bg_degradation: float = 0.0,
                 hist_x=None, hist_q=None) -> ScenarioResult:
    """Run one deterministic scenario and compute catastrophe metrics."""
    dyn = IMADynamics(graph, params, h)
    x0, q0 = build_initial_state(graph, dyn.q_star, seed_node, seed_magnitude,
                                 rng=rng, backlog_pert=backlog_pert,
                                 bg_degradation=bg_degradation)
    sim = solve_gl(dyn, x0, q0, T, hist_x=hist_x, hist_q=hist_q,
                   short_memory=short_memory)

    tr = cascade_threshold(graph, params)
    dalA_idx = graph.dal_A_idx
    is_cat, T_cat = detect_catastrophe(sim, dalA_idx, x_cat)

    final = sim.X[-1]
    n_degraded = int(np.sum(final >= x_cat))
    terminal_cascade = n_degraded / graph.n
    peak_backlog = float(np.max(sim.Q))
    max_dalA = float(np.max(sim.X[:, dalA_idx]))
    relax = relaxation_time(sim, x0) if not is_cat else None

    return ScenarioResult(
        name=name, Rc=tr.Rc, catastrophe=is_cat, T_cat=T_cat,
        terminal_cascade_size=terminal_cascade, n_degraded=n_degraded,
        peak_backlog=peak_backlog, max_dalA=max_dalA, relaxation_time=relax,
        sim=sim, params=dict(kappa_scale=params.kappa_scale, xi=params.xi,
                             alpha=params.alpha, beta_order=params.beta_order,
                             seed_node=seed_node, seed_magnitude=seed_magnitude,
                             T=T, h=h, x_cat=x_cat),
    )


def load_scenario_config(path: str | Path) -> dict:
    with open(path, "r") as fh:
        return yaml.safe_load(fh)


def scenario_from_config(graph: IMAGraph, cfg: dict) -> ScenarioResult:
    """Run a scenario described by a scenario_*.yaml file."""
    gp = graph.global_params
    params = ScenarioParams(
        kappa_scale=cfg["kappa_scale"], xi=cfg["xi"],
        alpha=cfg.get("alpha", gp.get("alpha", 0.8)),
        beta_order=cfg.get("beta_order", gp.get("beta_order", 0.8)))
    return run_scenario(
        graph, params, name=cfg["name"], seed_node=cfg["seed_node"],
        seed_magnitude=cfg["seed_magnitude"], T=cfg["T"], h=cfg["h"],
        x_cat=cfg.get("x_cat", gp.get("x_cat", 0.6)),
        short_memory=cfg.get("short_memory"))


# =====================================================================
#  Reduced mean-field model (Figure 7: bistability / phase portrait)
# =====================================================================
# Parameters from the footnote beneath Table 1 of the manuscript.
MEANFIELD = dict(k=0.75, mu=0.5, gamma=0.3, eta_theta=0.35, lam=0.35,
                 c=1.0, delta=0.3, r=0.45, q_ref=0.30, load_gain=0.8,
                 kappa=14.0, nu=0.35, xi=0.5)


def _mf_rhs(x, q, P):
    fx = x / (1 + x)
    excess = max(q - P["q_ref"], 0.0)
    gq = excess / (1 + excess)
    hq = q / (1 + q / 2)
    load = x + P["nu"] * q - P["xi"]
    pi = 0.5 * (1 + np.tanh(0.5 * P["kappa"] * load))
    rho = P["r"] * (1 - pi)
    m3 = P["eta_theta"] * q * x / (1 + x)
    Fx = -P["mu"] * x + P["k"] * fx + P["gamma"] * gq + m3 - rho * x
    Fq = P["lam"] * (1 + P["load_gain"] * x) - P["c"] * (1 - x) * hq - P["delta"] * q
    return Fx, Fq


def mean_field_trajectory(x0, q0, alpha=0.8, beta=0.8, T=120.0, h=0.05, P=None):
    """Integrate the 2D mean-field system with the GL scheme (no delays)."""
    from .fractional_solver import gl_weights
    P = P or MEANFIELD
    N = int(round(T / h))
    X = np.zeros(N + 1)
    Q = np.zeros(N + 1)
    X[0], Q[0] = x0, q0
    ca, cb = gl_weights(alpha, N + 1), gl_weights(beta, N + 1)
    ha, hb = h ** alpha, h ** beta
    for k in range(N):
        Fx, Fq = _mf_rhs(X[k], Q[k], P)
        # Caputo GL: memory of (y - y0)
        mem_x = ca[1:k + 2] @ (X[k::-1] - x0)
        mem_q = cb[1:k + 2] @ (Q[k::-1] - q0)
        X[k + 1] = np.clip(ha * Fx - mem_x + x0, 0.0, 1.0)
        Q[k + 1] = max(hb * Fq - mem_q + q0, 0.0)
    return np.arange(N + 1) * h, X, Q


def mean_field_fixed_points(P=None):
    """Locate equilibria of the mean-field system (nominal & catastrophic)."""
    from scipy.optimize import fsolve
    P = P or MEANFIELD

    def eqs(v):
        return _mf_rhs(v[0], v[1], P)
    seeds = [(0.0, 0.3), (0.5, 1.0), (1.0, 1.5), (0.9, 1.2)]
    fps = []
    for s in seeds:
        sol, info, ier, _ = fsolve(eqs, s, full_output=True)
        if ier == 1 and 0 <= sol[0] <= 1.001 and sol[1] >= 0:
            if not any(np.allclose(sol, f, atol=1e-3) for f in fps):
                fps.append(tuple(np.round(sol, 4)))
    return sorted(fps)


# =====================================================================
#  Parameter-sweep experiments (Figures 6b, 8)
# =====================================================================
def tipping_sweep(graph, xi_values, *, kappa_scale=1.60, alpha=0.8, beta=0.8,
                  seed_node="RDC1", seed_magnitude=0.55, T=400.0, h=0.05,
                  x_cat=0.6):
    """Sweep the reconfiguration-capacity threshold xi (Figure 8a)."""
    rows = []
    for xi in xi_values:
        p = ScenarioParams(kappa_scale, float(xi), alpha, beta)
        r = run_scenario(graph, p, name=f"xi={xi:.3f}", seed_node=seed_node,
                         seed_magnitude=seed_magnitude, T=T, h=h, x_cat=x_cat)
        rows.append(dict(xi=float(xi), catastrophe=r.catastrophe,
                         T_cat=r.T_cat if r.T_cat is not None else np.nan,
                         peak_backlog=r.peak_backlog,
                         terminal_cascade_size=r.terminal_cascade_size))
    return rows


def priority_sweep(graph, theta_scales, *, kappa_scale=1.60, xi=0.38,
                   alpha=0.8, beta=0.8, seed_node="RDC1", seed_magnitude=0.55,
                   T=400.0, h=0.05, x_cat=0.6):
    """Sweep the priority-conflict scale theta/theta0 (Figure 8b)."""
    rows = []
    for ts in theta_scales:
        p = ScenarioParams(kappa_scale, xi, alpha, beta, theta_scale=float(ts))
        r = run_scenario(graph, p, name=f"theta={ts:.2f}", seed_node=seed_node,
                         seed_magnitude=seed_magnitude, T=T, h=h, x_cat=x_cat)
        rows.append(dict(theta_scale=float(ts), catastrophe=r.catastrophe,
                         T_cat=r.T_cat if r.T_cat is not None else np.nan,
                         terminal_cascade_size=r.terminal_cascade_size))
    return rows


def delay_memory_grid(graph, alphas, taus, *, kappa_scale=1.60, xi=0.64,
                      seed_node="RDC1", seed_magnitude=0.55, T=400.0, h=0.05,
                      x_cat=0.6):
    """Terminal cascade size on the (alpha, tau) grid (Figure 6b).

    ``tau`` scales all communication delays via the delay multiplier.
    """
    grid = np.zeros((len(alphas), len(taus)))
    for ia, a in enumerate(alphas):
        for it, tau in enumerate(taus):
            p = ScenarioParams(kappa_scale, xi, float(a), float(a),
                               delay_mult=float(tau))
            r = run_scenario(graph, p, name="dm", seed_node=seed_node,
                             seed_magnitude=seed_magnitude, T=T, h=h, x_cat=x_cat)
            grid[ia, it] = r.terminal_cascade_size
    return grid


__all__ = ["ScenarioResult", "run_scenario", "build_initial_state",
           "detect_catastrophe", "relaxation_time", "load_scenario_config",
           "scenario_from_config", "mean_field_trajectory",
           "mean_field_fixed_points", "MEANFIELD", "tipping_sweep",
           "priority_sweep", "delay_memory_grid"]
