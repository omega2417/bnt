"""Mechanism M4 -- state-dependent reconfiguration (Health Monitoring) failure.

Implements Equation (6) of the manuscript: the reconfiguration/suppression rate

    rho_i(t) = r_i * (1 - pi(t))

where pi(t) is the probability that reconfiguration *fails*, rising sigmoidally
once the criticality-weighted global load exceeds the capacity threshold xi:

    pi(t) = 1 / (1 + exp(-kappa * (<x>_w + nu * <q>_w - xi)))
    <y>_w = sum_i w_i y_i

kappa is the transition *steepness* (Table 1: kappa=14); xi is the
criticality-weighted-load capacity threshold; nu weights the backlog channel's
contribution to the aggregate load.  Reconfiguration authority collapses
(pi -> 1) once <x>_w + nu <q>_w exceeds xi.
"""
from __future__ import annotations

import numpy as np


def weighted_load(y: np.ndarray, w: np.ndarray) -> float:
    """Criticality-weighted mean <y>_w = sum_i w_i y_i."""
    return float(np.dot(w, y))


def reconfig_failure_prob(x: np.ndarray, q: np.ndarray, w: np.ndarray,
                          kappa: float, nu: float, xi: float) -> float:
    """pi(t): probability that reconfiguration fails (Equation 6)."""
    load = weighted_load(x, w) + nu * weighted_load(q, w) - xi
    # numerically stable logistic with steepness kappa
    return float(0.5 * (1.0 + np.tanh(0.5 * kappa * load)))


def reconfig_rate(x: np.ndarray, q: np.ndarray, w: np.ndarray, r: np.ndarray,
                  kappa: float, nu: float, xi: float) -> np.ndarray:
    """rho_i(t) = r_i * (1 - pi(t)) : effective per-node suppression rate."""
    pi = reconfig_failure_prob(x, q, w, kappa, nu, xi)
    return r * (1.0 - pi)


__all__ = ["weighted_load", "reconfig_failure_prob", "reconfig_rate"]
