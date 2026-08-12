"""Ensemble uncertainty and sensitivity analysis (manuscript Sec. 5.1, 6.5).

Latin Hypercube Sampling over the prescribed sensitivity ranges (Table A2),
N simulations per scenario, right-censored catastrophe statistics, and Partial
Rank Correlation Coefficients of T_cat against the sampled inputs.

The ranges are *prescribed sensitivity ranges*, NOT experimentally measured
uncertainties (manuscript, Table A2 note).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np
from scipy.stats import qmc

from .graph_model import IMAGraph
from .ima_dynamics import IMADynamics, ScenarioParams
from .scenarios import run_scenario
from .statistics import wilson_ci, kaplan_meier, prcc, iqr, median_or_nan


# Names of the LHS dimensions and the PRCC inputs (order matters).
LHS_DIMENSIONS = [
    "fault_magnitude",     # 0.44-0.66
    "seed_index",          # 0-1 -> RDC index
    "backlog_pert",        # 0-0.10
    "history_phase",       # 0-1 -> [0,2pi)
    "history_amp",         # 0-0.05
    "alpha",               # baseline +-0.05
    "beta",                # baseline +-0.05
    "prop_mult",           # 0.9-1.1
    "backlog_mult",        # 0.9-1.1
    "conflict_mult",       # 0.9-1.1
    "reconf_mult",         # 0.9-1.1
    "xi_mult",             # 0.95-1.05
    "delay_mult",          # 0.8-1.2
]

PRCC_INPUTS = ["xi_mult", "prop_mult", "conflict_mult", "fault_magnitude",
               "delay_mult", "alpha", "reconf_mult"]


def _bounds(base_alpha, base_beta):
    return {
        "fault_magnitude": (0.44, 0.66),
        "seed_index": (0.0, 1.0),
        "backlog_pert": (0.0, 0.10),
        "history_phase": (0.0, 1.0),
        "history_amp": (0.0, 0.05),
        "alpha": (max(0.05, base_alpha - 0.05), min(1.0, base_alpha + 0.05)),
        "beta": (max(0.05, base_beta - 0.05), min(1.0, base_beta + 0.05)),
        "prop_mult": (0.9, 1.1),
        "backlog_mult": (0.9, 1.1),
        "conflict_mult": (0.9, 1.1),
        "reconf_mult": (0.9, 1.1),
        "xi_mult": (0.95, 1.05),
        "delay_mult": (0.8, 1.2),
    }


def sample_lhs(n: int, base_alpha: float, base_beta: float, seed: int = 0):
    """Draw ``n`` Latin-Hypercube samples over the ensemble ranges."""
    b = _bounds(base_alpha, base_beta)
    dim = len(LHS_DIMENSIONS)
    sampler = qmc.LatinHypercube(d=dim, seed=seed)
    unit = sampler.random(n)
    lo = np.array([b[k][0] for k in LHS_DIMENSIONS])
    hi = np.array([b[k][1] for k in LHS_DIMENSIONS])
    return qmc.scale(unit, lo, hi)


def _build_history(graph, dyn, x0, q0, phase, amp, max_lag, h):
    """Oscillatory initial history phi on t in [-tau_max, 0] (Eq. Sec 5.1)."""
    P = max_lag
    ts = -(np.arange(P)[::-1] + 1) * h            # negative times
    tau_max = P * h
    hist_x = np.zeros((P, graph.n))
    hist_q = np.zeros((P, graph.n))
    for r, t in enumerate(ts):
        osc = np.sin(2 * np.pi * t / tau_max + 2 * np.pi * phase)
        hist_x[r] = np.clip(x0 + amp * osc, 0.0, 1.0)
        hist_q[r] = np.maximum(q0 * (1 + amp * osc), 0.0)
    return hist_x, hist_q


def run_ensemble(graph: IMAGraph, *, name: str, kappa_scale: float, xi: float,
                 base_alpha: float = 0.8, base_beta: float = 0.8, N: int = 100,
                 T: float = 400.0, h: float = 0.05, x_cat: float = 0.6,
                 seed: int = 12345) -> List[dict]:
    """Run an N-member LHS ensemble for one scenario."""
    samples = sample_lhs(N, base_alpha, base_beta, seed=seed)
    rdc_nodes = [nid for nid, t in zip(graph.node_ids, graph.node_type) if t == "RDC"]
    runs = []
    for m in range(N):
        s = dict(zip(LHS_DIMENSIONS, samples[m]))
        rng = np.random.default_rng(seed + m + 1)
        seed_node = rdc_nodes[int(s["seed_index"] * len(rdc_nodes)) % len(rdc_nodes)]
        params = ScenarioParams(
            kappa_scale=kappa_scale, xi=xi * s["xi_mult"],
            alpha=float(s["alpha"]), beta_order=float(s["beta"]),
            prop_mult=float(s["prop_mult"]), backlog_mult=float(s["backlog_mult"]),
            conflict_mult=float(s["conflict_mult"]),
            reconf_mult=float(s["reconf_mult"]), delay_mult=float(s["delay_mult"]))

        dyn = IMADynamics(graph, params, h)
        x0 = np.clip(rng.uniform(0.0, s["history_amp"], graph.n), 0.0, 1.0)
        x0[graph.index[seed_node]] = s["fault_magnitude"]
        q0 = np.maximum(dyn.q_star * (1 + rng.uniform(
            -s["backlog_pert"], s["backlog_pert"], graph.n)), 0.0)
        hist_x, hist_q = _build_history(graph, dyn, x0, q0, s["history_phase"],
                                        s["history_amp"], dyn.max_lag, h)

        r = run_scenario(graph, params, name=f"{name}_{m}", seed_node=seed_node,
                         seed_magnitude=s["fault_magnitude"], T=T, h=h,
                         x_cat=x_cat, hist_x=hist_x, hist_q=hist_q)
        row = dict(member=m, seed_node=seed_node, catastrophe=r.catastrophe,
                   T_cat=r.T_cat, terminal_cascade_size=r.terminal_cascade_size,
                   peak_backlog=r.peak_backlog, max_dalA=r.max_dalA,
                   nan_flag=bool(r.sim.nan_flag))
        row.update({k: float(v) for k, v in s.items()})
        runs.append(row)
    return runs


def summarize_ensemble(runs: List[dict], horizon: float) -> dict:
    """Right-censored catastrophe statistics for one scenario's ensemble."""
    N = len(runs)
    n_cat = sum(r["catastrophe"] for r in runs)
    p, lo, hi = wilson_ci(n_cat, N)

    durations = [r["T_cat"] if r["catastrophe"] else horizon for r in runs]
    events = [1 if r["catastrophe"] else 0 for r in runs]
    km = kaplan_meier(durations, events)

    tcat_events = [r["T_cat"] for r in runs if r["catastrophe"]]
    q1, q3 = iqr(tcat_events)
    return dict(
        N=N, n_cat=n_cat, p_cat=p, wilson_low=lo, wilson_high=hi,
        km_median=km.median, km_median_ci=km.median_ci,
        iqr_tcat=(q1, q3),
        median_terminal_cascade=median_or_nan([r["terminal_cascade_size"] for r in runs]),
        median_peak_backlog=median_or_nan([r["peak_backlog"] for r in runs]),
    )


def ensemble_prcc(runs: List[dict], inputs: Sequence[str] = PRCC_INPUTS,
                  horizon: float = 400.0) -> Dict[str, dict]:
    """PRCC of T_cat against sampled inputs (censored runs use the horizon)."""
    X = np.array([[r[k] for k in inputs] for r in runs], dtype=float)
    y = np.array([r["T_cat"] if r["catastrophe"] else horizon for r in runs],
                 dtype=float)
    # need variation in y
    if np.std(y) < 1e-9:
        return {k: dict(prcc=float("nan"), ci_low=float("nan"),
                        ci_high=float("nan"), p_value=float("nan")) for k in inputs}
    return prcc(X, y, list(inputs))


__all__ = ["sample_lhs", "run_ensemble", "summarize_ensemble", "ensemble_prcc",
           "LHS_DIMENSIONS", "PRCC_INPUTS"]
