"""Operators of the metric model: normalization (4), aggregation (5)-(7), roll-up (8)-(10)."""
from __future__ import annotations

import numpy as np

from .levels import BREAKPOINTS


def normalize(x: float, eta: tuple[float, ...], sigma: int = 1,
              y: tuple[float, ...] = BREAKPOINTS) -> float:
    """Anchored piecewise-linear normalization nu_xi(x) (eq. 4).

    `eta` are anchors in quality coordinates (eta_r = sigma xi_r), `x` is the
    physical value. The level of the score equals the tabulated class of x.
    """
    u = sigma * x
    if u < eta[0]:
        return 0.0
    if u >= eta[5]:
        return 1.0
    for r in range(5):
        if eta[r] <= u < eta[r + 1] and eta[r] < eta[r + 1]:
            return y[r] + (y[r + 1] - y[r]) * (u - eta[r]) / (eta[r + 1] - eta[r])
    # u equals a degenerate anchor (eta_r == eta_{r+1}); take the upper band
    for r in range(5, -1, -1):
        if u >= eta[r]:
            return y[r]
    return 0.0  # pragma: no cover


def normalize_slope(x: float, eta: tuple[float, ...], sigma: int = 1,
                    y: tuple[float, ...] = BREAKPOINTS) -> float:
    """Derivative d nu / d x (0 on saturated parts); used by the advisor agent."""
    u = sigma * x
    if u < eta[0] or u >= eta[5]:
        return 0.0
    for r in range(5):
        if eta[r] <= u < eta[r + 1] and eta[r] < eta[r + 1]:
            return sigma * (y[r + 1] - y[r]) / (eta[r + 1] - eta[r])
    return 0.0


def linear_normalize(x: float, lo: float, hi: float, sigma: int = 1) -> float:
    """Min-max rescaling between the critical and ideal anchors (for comparison only)."""
    u, a, b = sigma * x, sigma * lo, sigma * hi
    if b == a:
        return 1.0 if u >= b else 0.0
    return float(np.clip((u - a) / (b - a), 0.0, 1.0))


def aggregate_action(m: np.ndarray, w: np.ndarray, observed: np.ndarray, core: np.ndarray,
                     theta: float, operator: str = "capped") -> dict:
    """Non-compensatory aggregation within a basic action (eqs. 5-7).

    Returns S (renormalized mean), c (cap), mu (score), L, U (enclosure),
    kappa (completeness) and flags.
    """
    m = np.asarray(m, float)
    w = np.asarray(w, float)
    obs = np.asarray(observed, bool)
    core = np.asarray(core, bool)
    kappa = float(w[obs].sum())
    S = float((w[obs] * m[obs]).sum() / kappa)
    core_obs = core & obs
    c = float(np.min(m[core_obs] / theta)) if core_obs.any() else float("inf")
    veto = bool(core_obs.any() and np.any(m[core_obs] <= 0.0))
    if operator == "capped":
        mu = min(S, c)
        L = min(kappa * S, c)
        U = min(kappa * S + 1.0 - kappa, c)
    elif operator == "hard":
        gate = 0.0 if veto else 1.0
        mu = S * gate
        L, U = kappa * S * gate, (kappa * S + 1.0 - kappa) * gate
    elif operator == "additive":
        mu, L, U = S, kappa * S, kappa * S + 1.0 - kappa
    else:
        raise ValueError(f"unknown operator {operator!r}")
    return {"S": S, "c": c, "mu": float(mu), "L": float(L), "U": float(U), "kappa": kappa,
            "veto": veto if operator != "additive" else False,
            "cap_active": bool(operator == "capped" and c < S)}
