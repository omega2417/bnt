"""IMA fractional-order dynamics -- right-hand side of Equations (3)-(6).

Assembles the four escalation mechanisms into the vector field of the
2n-dimensional delayed Caputo fractional system:

    C D^alpha x_i = -mu_i x_i
                    + sum_j B_ij f(x_j(t - tau_ij))          # M1 propagation
                    + gamma_i g((q_i - q_i*)_+)              # M2 backlog->degradation
                    + eta_i Phi_i(t)                         # M3 priority conflict
                    - rho_i(t) x_i                           # M4 reconfiguration

    C D^beta  q_i = lambda_i - c_i (1 - x_i) h(q_i)
                    + sum_j w_ij q_j(t - sigma_ij)           # M2 spillover
                    - delta_i q_i

Saturating nonlinearities: f(u)=g(u)=u/(1+u), h(u)=u/(1+u/2).
Priority-conflict term (M3): Phi_i = q_i sum_{k in H_i} theta_ik x_k/(1+x_k).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np

from .graph_model import IMAGraph
from .reconfiguration import reconfig_failure_prob


# --------------------------------------------------------------------- nonlinearities
def f_sat(u: np.ndarray) -> np.ndarray:
    u = np.maximum(u, 0.0)
    return u / (1.0 + u)


g_sat = f_sat  # g(u) = u/(1+u), same as f


def h_sat(u: np.ndarray) -> np.ndarray:
    u = np.maximum(u, 0.0)
    return u / (1.0 + u / 2.0)


@dataclass
class ScenarioParams:
    """Coupling / reconfiguration parameters that vary between S1-S3."""
    kappa_scale: float          # coupling scale (varkappa) applied to beta
    xi: float                   # reconfiguration capacity threshold
    alpha: float = 0.8          # degradation fractional order
    beta_order: float = 0.8     # backlog fractional order
    theta_scale: float = 1.0    # priority-conflict multiplier (Figure 8b)
    # multiplicative parameter modifiers used by the ensemble (default = 1.0):
    prop_mult: float = 1.0
    backlog_mult: float = 1.0
    conflict_mult: float = 1.0
    reconf_mult: float = 1.0
    delay_mult: float = 1.0


class IMADynamics:
    """Vectorised right-hand side of Equations (3)-(6) on a fixed grid."""

    def __init__(self, graph: IMAGraph, params: ScenarioParams, h: float):
        self.g = graph
        self.p = params
        self.h = h
        gp = graph.global_params

        self.mu = graph.recovery_rate
        self.gamma = float(gp.get("gamma", 0.15)) * np.ones(graph.n)
        self.eta = float(gp.get("eta", 0.22)) * np.ones(graph.n)
        self.theta = float(gp.get("theta", 0.4)) * params.theta_scale * params.conflict_mult
        self.delta = float(gp.get("delta", 0.3)) * np.ones(graph.n)
        self.c = graph.service_capacity
        self.lam = graph.traffic_arrival
        self.r = graph.reconf_rate * params.reconf_mult
        self.w_crit = graph.crit_weight
        self.kappa_recon = float(gp.get("recon_kappa", 14.0))
        self.nu_recon = float(gp.get("recon_nu", 0.35))
        self.xi = params.xi

        # ---- Effective coupling matrix B (M1) : B_ij = kappa * beta_base * a_ij
        B = graph.coupling_matrix(params.kappa_scale) * params.prop_mult
        self.B = B
        self.W = graph.spillover * params.backlog_mult

        # ---- Nominal backlog reference q* (needed by M2 excess term & threshold) ----
        self.q_star = compute_nominal_backlog(graph, self.W, self.c, self.lam, self.delta)

        # ---- Pre-compute integer delay lags on the grid ----
        self._build_edge_arrays(h)

    # --------------------------------------------------------------- edge arrays
    def _build_edge_arrays(self, h: float):
        g = self.g
        dmax = self.p.delay_mult

        # M1 propagation edges (destination i, source j)
        i_p, j_p = np.where(self.B != 0)
        self.prop_i = i_p
        self.prop_j = j_p
        self.prop_coeff = self.B[i_p, j_p]
        tau_p = np.where(np.isnan(g.tau[i_p, j_p]), 0.5, g.tau[i_p, j_p]) * dmax
        self.prop_lag = np.maximum(1, np.round(tau_p / h).astype(int))

        # M2 spillover edges
        i_s, j_s = np.where(self.W != 0)
        self.spill_i = i_s
        self.spill_j = j_s
        self.spill_coeff = self.W[i_s, j_s]
        sig_s = np.where(np.isnan(g.tau[i_s, j_s]), 0.5, g.tau[i_s, j_s]) * dmax
        self.spill_lag = np.maximum(1, np.round(sig_s / h).astype(int))

        # M3 conflict pairs (i blocked by k in H_i)
        ci, ck, clag = [], [], []
        default_tau = 0.5 * dmax
        for i, Hi in enumerate(g.contention):
            for k in Hi:
                ci.append(i)
                ck.append(k)
                t = g.tau[i, k]
                if np.isnan(t):
                    t = g.tau[k, i]
                if np.isnan(t):
                    t = default_tau
                else:
                    t = t * dmax
                clag.append(max(1, int(round(t / h))))
        self.conf_i = np.array(ci, dtype=int)
        self.conf_k = np.array(ck, dtype=int)
        self.conf_lag = np.array(clag, dtype=int)

    @property
    def max_lag(self) -> int:
        lags = [1]
        for arr in (getattr(self, "prop_lag", None), getattr(self, "spill_lag", None),
                    getattr(self, "conf_lag", None)):
            if arr is not None and len(arr):
                lags.append(int(arr.max()))
        return max(lags)

    # --------------------------------------------------------------- RHS
    def rhs(self, k: int, X: np.ndarray, Q: np.ndarray,
            x_cur: Optional[np.ndarray] = None, q_cur: Optional[np.ndarray] = None):
        """Return (Fx, Fq, diagnostics) at grid step k.

        ``X`` and ``Q`` are history buffers of shape (steps+1, n); ``k`` is the
        index of the state whose derivative is being formed. Delayed lookups use
        rows ``k - lag`` (clamped to 0 by the method of steps).

        ``x_cur``/``q_cur`` optionally override the *current* (non-delayed) state
        while delayed terms are still read from the buffers -- used by the ABM
        predictor-corrector, where a trial current state is evaluated against the
        committed history.
        """
        n = self.g.n
        x = X[k] if x_cur is None else x_cur
        q = Q[k] if q_cur is None else q_cur

        # ---- M1 : network propagation of degradation (delayed) ----
        src_lag_idx = np.maximum(k - self.prop_lag, 0)
        x_del = X[src_lag_idx, self.prop_j]
        m1 = np.zeros(n)
        np.add.at(m1, self.prop_i, self.prop_coeff * f_sat(x_del))

        # ---- M2 : backlog -> degradation via excess over reference ----
        excess = np.maximum(q - self.q_star, 0.0)
        m2 = self.gamma * g_sat(excess)

        # ---- M3 : mixed-criticality priority conflict ----
        phi = np.zeros(n)
        if len(self.conf_i):
            xk_lag = X[np.maximum(k - self.conf_lag, 0), self.conf_k]
            contrib = self.theta * xk_lag / (1.0 + xk_lag)
            np.add.at(phi, self.conf_i, contrib)
        phi = q * phi
        m3 = self.eta * phi

        # ---- M4 : reconfiguration suppression ----
        pi_fail = reconfig_failure_prob(x, q, self.w_crit,
                                        self.kappa_recon, self.nu_recon, self.xi)
        rho = self.r * (1.0 - pi_fail)

        Fx = -self.mu * x + m1 + m2 + m3 - rho * x

        # ---- Equation (4): backlog dynamics ----
        s_lag_idx = np.maximum(k - self.spill_lag, 0)
        q_del = Q[s_lag_idx, self.spill_j]
        spill = np.zeros(n)
        np.add.at(spill, self.spill_i, self.spill_coeff * q_del)
        service = self.c * (1.0 - x) * h_sat(q)
        Fq = self.lam - service + spill - self.delta * q

        diag = dict(pi_fail=pi_fail, weighted_x=float(np.dot(self.w_crit, x)),
                    weighted_q=float(np.dot(self.w_crit, q)))
        return Fx, Fq, diag


def compute_nominal_backlog(graph: IMAGraph, W: np.ndarray, c: np.ndarray,
                            lam: np.ndarray, delta: np.ndarray) -> np.ndarray:
    """Solve the nominal (x=0) backlog equilibrium q* of Equation (4).

    0 = lambda_i - c_i h(q_i*) + sum_j W_ij q_j* - delta_i q_i*.
    Solved with a damped Newton iteration (robust: the Jacobi map is not a
    contraction because c_i h'(q)/delta_i can exceed one).
    """
    n = graph.n

    def F(q):
        return lam - c * h_sat(q) + W @ q - delta * q

    def J(q):
        # d/dq [ -c h(q) + W q - delta q ]; h'(q) = 1/(1+q/2)^2
        hp = 1.0 / (1.0 + q / 2.0) ** 2
        return -np.diag(c * hp) + W - np.diag(delta)

    q = lam / delta                          # good initial guess
    for _ in range(200):
        r = F(q)
        if np.max(np.abs(r)) < 1e-13:
            break
        dq = np.linalg.solve(J(q), -r)
        q = np.maximum(q + dq, 0.0)
    return q


__all__ = ["IMADynamics", "ScenarioParams", "compute_nominal_backlog",
           "f_sat", "g_sat", "h_sat"]
