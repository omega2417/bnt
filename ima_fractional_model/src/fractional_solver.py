"""Numerical solvers for delayed Caputo fractional-order systems.

Primary integrator: explicit Grunwald-Letnikov (GL) scheme on a uniform grid,

    y_{k+1} = h^nu F(y_k, y_{k-d}) - sum_{j=1}^{k+1} c_j^nu y_{k+1-j},
    c_0 = 1,  c_j = (1 - (nu+1)/j) c_{j-1},

with delays realised as integer lags d = round(tau/h) and an optional
short-memory truncation window.  Two independent orders are supported
(``alpha`` for degradation, ``beta`` for backlog); at ``alpha=beta=1`` the scheme
reduces to the explicit integer-order (Euler-type) baseline.

A secondary Adams-Bashforth-Moulton (ABM) predictor-corrector integrator
(Diethelm-Ford-Freed, adapted to fixed delays) is provided for independent
solver verification (manuscript, Sec. 5 / Sec. 11).
"""
from __future__ import annotations

from dataclasses import dataclass
from math import gamma as _gamma
from typing import Optional

import numpy as np

from .ima_dynamics import IMADynamics


# --------------------------------------------------------------------- GL weights
def gl_weights(order: float, n: int) -> np.ndarray:
    """Grunwald-Letnikov coefficients c_0..c_n for the given fractional order."""
    c = np.empty(n + 1)
    c[0] = 1.0
    for j in range(1, n + 1):
        c[j] = (1.0 - (order + 1.0) / j) * c[j - 1]
    return c


@dataclass
class SolverResult:
    t: np.ndarray
    X: np.ndarray               # degradation trajectories (steps+1, n)
    Q: np.ndarray               # backlog trajectories (steps+1, n)
    pi_fail: np.ndarray         # reconfiguration-failure probability per step
    weighted_x: np.ndarray
    weighted_q: np.ndarray
    h: float
    alpha: float
    beta: float
    nan_flag: bool = False


def solve_gl(dyn: IMADynamics, x0: np.ndarray, q0: np.ndarray, T: float,
             hist_x: Optional[np.ndarray] = None, hist_q: Optional[np.ndarray] = None,
             short_memory: Optional[int] = None,
             x_bounds=(0.0, 1.0), q_min: float = 0.0) -> SolverResult:
    """Integrate Equations (3)-(6) with the GL scheme.

    Parameters
    ----------
    dyn : IMADynamics
    x0, q0 : initial state at t=0 (length n)
    T : simulation horizon (dimensionless)
    hist_x, hist_q : optional history arrays of shape (P, n) covering
        t in [-P*h, -h] (row 0 earliest).  If omitted a constant history equal to
        the initial state is used.
    short_memory : optional truncation window (number of memory terms).
    """
    n = dyn.g.n
    h = dyn.h
    alpha, beta = dyn.p.alpha, dyn.p.beta_order
    N = int(round(T / h))
    P = int(dyn.max_lag)

    # ---- allocate padded buffers: rows 0..P-1 history, row P = t0 ----
    X = np.zeros((P + N + 1, n))
    Q = np.zeros((P + N + 1, n))
    if hist_x is None:
        X[:P + 1] = x0
    else:
        X[:P] = hist_x[-P:] if hist_x.shape[0] >= P else np.vstack(
            [np.repeat(hist_x[:1], P - hist_x.shape[0], axis=0), hist_x])
        X[P] = x0
    if hist_q is None:
        Q[:P + 1] = q0
    else:
        Q[:P] = hist_q[-P:] if hist_q.shape[0] >= P else np.vstack(
            [np.repeat(hist_q[:1], P - hist_q.shape[0], axis=0), hist_q])
        Q[P] = q0

    ca = gl_weights(alpha, N + 1)
    cb = gl_weights(beta, N + 1)
    ha, hb = h ** alpha, h ** beta

    pi_fail = np.zeros(N + 1)
    wx = np.zeros(N + 1)
    wq = np.zeros(N + 1)
    _, _, d0 = dyn.rhs(P, X, Q)
    pi_fail[0], wx[0], wq[0] = d0["pi_fail"], d0["weighted_x"], d0["weighted_q"]

    nan_flag = False
    xlo, xhi = x_bounds
    for k in range(N):
        p = P + k                       # absolute row of current state (t = k*h)
        Fx, Fq, _ = dyn.rhs(p, X, Q)

        kk = k + 1
        m = kk if short_memory is None else min(kk, short_memory)
        # Caputo GL: C D^nu y = RL D^nu (y - y0). Memory is taken of (y - y0) so a
        # constant initial state is preserved (C D^nu const = 0). Rows p..p+1-m are
        # all at t>=0; y0 is the state at t=0 (row P).
        rows = p + 1 - np.arange(1, m + 1)
        mem_x = ca[1:m + 1] @ (X[rows] - x0)
        mem_q = cb[1:m + 1] @ (Q[rows] - q0)

        xk = x0 + ha * Fx - mem_x
        qk = q0 + hb * Fq - mem_q

        # ---- physical bounds / numerical guards ----
        xk = np.clip(xk, xlo, xhi)
        qk = np.maximum(qk, q_min)
        if not (np.all(np.isfinite(xk)) and np.all(np.isfinite(qk))):
            nan_flag = True
            xk = np.nan_to_num(xk, nan=xhi, posinf=xhi, neginf=xlo)
            qk = np.nan_to_num(qk, nan=0.0, posinf=1e6, neginf=0.0)

        X[p + 1] = xk
        Q[p + 1] = qk
        _, _, dd = dyn.rhs(p + 1, X, Q)
        pi_fail[kk], wx[kk], wq[kk] = dd["pi_fail"], dd["weighted_x"], dd["weighted_q"]
        if nan_flag:
            # freeze remainder to avoid propagating NaNs; flagged for the caller
            pass

    t = np.arange(N + 1) * h
    return SolverResult(t=t, X=X[P:], Q=Q[P:], pi_fail=pi_fail,
                        weighted_x=wx, weighted_q=wq, h=h,
                        alpha=alpha, beta=beta, nan_flag=nan_flag)


# --------------------------------------------------------------- ABM verification
def _abm_a_coeff(nu: float, kk: int) -> np.ndarray:
    """Corrector weights a_{j,k+1}, j=0..kk for order nu (Diethelm-Ford-Freed)."""
    j = np.arange(0, kk + 1)
    a = np.empty(kk + 1)
    k = kk - 1
    # j = 0
    a[0] = (k ** (nu + 1)) - (k - nu) * (k + 1) ** nu
    # 1 <= j <= k
    if kk >= 2:
        jj = np.arange(1, kk)
        a[1:kk] = ((k - jj + 2) ** (nu + 1) + (k - jj) ** (nu + 1)
                   - 2 * (k - jj + 1) ** (nu + 1))
    a[kk] = 1.0
    return a


def solve_abm(dyn: IMADynamics, x0: np.ndarray, q0: np.ndarray, T: float,
              hist_x=None, hist_q=None) -> SolverResult:
    """Fractional Adams-Bashforth-Moulton predictor-corrector (fixed delays).

    Independent-solver cross-check for Scenario S1 (manuscript Sec. 5/11).
    Delayed arguments are taken from the committed trajectory (method of steps).
    """
    n = dyn.g.n
    h = dyn.h
    alpha, beta = dyn.p.alpha, dyn.p.beta_order
    N = int(round(T / h))
    P = int(dyn.max_lag)

    X = np.zeros((P + N + 1, n))
    Q = np.zeros((P + N + 1, n))
    X[:P + 1] = x0 if hist_x is None else np.vstack([hist_x[-P:], x0[None]])[:P + 1]
    Q[:P + 1] = q0 if hist_q is None else np.vstack([hist_q[-P:], q0[None]])[:P + 1]
    if hist_x is None:
        X[:P + 1] = x0
    if hist_q is None:
        Q[:P + 1] = q0

    Fx = np.zeros((N + 1, n))
    Fq = np.zeros((N + 1, n))
    Fx[0], Fq[0], _ = dyn.rhs(P, X, Q)

    ga2_a, ga2_b = _gamma(alpha + 2), _gamma(beta + 2)
    ga1_a, ga1_b = _gamma(alpha + 1), _gamma(beta + 1)

    for k in range(N):
        p = P + k
        kk = k + 1
        jj = np.arange(0, kk)
        # predictor weights b_{j,k+1} = (k+1-j)^nu - (k-j)^nu
        b_a = (kk - jj) ** alpha - (k - jj) ** alpha
        b_b = (kk - jj) ** beta - (k - jj) ** beta
        xP = x0 + (h ** alpha / ga1_a) * (b_a @ Fx[:kk])
        qP = q0 + (h ** beta / ga1_b) * (b_b @ Fq[:kk])
        xP = np.clip(xP, 0.0, 1.0)
        qP = np.maximum(qP, 0.0)

        # evaluate F at predictor (delayed args from committed history at row p+1)
        X[p + 1] = xP
        Q[p + 1] = qP
        FxP, FqP, _ = dyn.rhs(p + 1, X, Q, x_cur=xP, q_cur=qP)

        a_a = _abm_a_coeff(alpha, kk)
        a_b = _abm_a_coeff(beta, kk)
        xC = x0 + (h ** alpha / ga2_a) * (a_a[:kk] @ Fx[:kk] + a_a[kk] * FxP)
        qC = q0 + (h ** beta / ga2_b) * (a_b[:kk] @ Fq[:kk] + a_b[kk] * FqP)
        xC = np.clip(xC, 0.0, 1.0)
        qC = np.maximum(qC, 0.0)

        X[p + 1] = xC
        Q[p + 1] = qC
        Fx[kk], Fq[kk], _ = dyn.rhs(p + 1, X, Q, x_cur=xC, q_cur=qC)

    t = np.arange(N + 1) * h
    return SolverResult(t=t, X=X[P:], Q=Q[P:], pi_fail=np.zeros(N + 1),
                        weighted_x=np.zeros(N + 1), weighted_q=np.zeros(N + 1),
                        h=h, alpha=alpha, beta=beta)


__all__ = ["gl_weights", "solve_gl", "solve_abm", "SolverResult"]
