"""Cascade threshold Rc = spectral radius of the positive comparison operator.

Implements Equation (7) of the manuscript:

    Rc = rho( M^{-1} (B o A + Gamma) ),   M = diag(mu_i + r_i (1 - pi(0)))

where
  * B o A  is the M1 degradation-coupling matrix (B_ij = kappa beta_base a_ij),
  * Gamma  aggregates the linearised M2 (backlog) and M3 (priority-conflict)
    sensitivities at the nominal equilibrium E0 = (0, q*).

Classification:
  * Rc < 1  -> analytically certified (globally Mittag-Leffler stable) region;
  * Rc >= 1 -> sufficient stability certificate unavailable / cascade-prone.
Rc >= 1 is NOT interpreted as a guaranteed catastrophe (see manuscript Sec. 4).
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .graph_model import IMAGraph
from .ima_dynamics import IMADynamics, ScenarioParams
from .reconfiguration import reconfig_failure_prob


def _h_prime(u: np.ndarray) -> np.ndarray:
    """Derivative of h(u) = u/(1+u/2)."""
    return 1.0 / (1.0 + u / 2.0) ** 2


@dataclass
class ThresholdResult:
    Rc: float
    K: np.ndarray
    q_star: np.ndarray
    pi0: float
    regime: str

    @property
    def margin(self) -> float:
        return 1.0 - self.Rc


def comparison_matrix(graph: IMAGraph, params: ScenarioParams):
    """Build K = M^{-1}(B o A + Gamma) and return (K, q_star, pi0)."""
    dyn = IMADynamics(graph, params, h=0.05)   # h only affects delay lags, unused here
    q_star = dyn.q_star
    B = dyn.B                                   # M1 coupling (B o A)
    n = graph.n
    gp = graph.global_params
    xi_ref = float(gp.get("xi_ref", params.xi))
    gfac = float(gp.get("comparison_gamma_factor", 1.0))

    # ---- pi(0) at the structural reference reconfiguration point ----
    x0 = np.zeros(n)
    pi0 = reconfig_failure_prob(x0, q_star, dyn.w_crit,
                                dyn.kappa_recon, dyn.nu_recon, xi_ref)

    # ---- M = diag(mu_i + r_i (1 - pi(0))) ----
    M_diag = dyn.mu + dyn.r * (1.0 - pi0)

    # ---- Gamma_q : x_i -> q_i -> x_i gain via the q-block Jacobian inverse ----
    # steady-state sensitivity S = (D - W)^{-1} (c o h(q*)),  D = diag(c h'(q*)+delta)
    hq = q_star / (1.0 + q_star / 2.0)          # h(q*)
    D = np.diag(dyn.c * _h_prime(q_star) + dyn.delta)
    S = np.linalg.solve(D - dyn.W, dyn.c * hq)  # dq_i/dx_i, elementwise bound
    # g'(0) = 1 for the excess-backlog term gamma_i g((q_i-q*)_+)
    Gamma_q = np.diag(dyn.gamma * S)

    # ---- Gamma_Phi : priority-conflict sensitivity eta_i q_i* theta_ik ----
    Gamma_Phi = np.zeros((n, n))
    for i, Hi in enumerate(graph.contention):
        for k in Hi:
            Gamma_Phi[i, k] = dyn.eta[i] * q_star[i] * dyn.theta
    Gamma = gfac * (Gamma_q + Gamma_Phi)

    K = (B + Gamma) / M_diag[:, None]
    return K, q_star, pi0


def cascade_threshold(graph: IMAGraph, params: ScenarioParams) -> ThresholdResult:
    """Compute Rc and classify the operating regime."""
    K, q_star, pi0 = comparison_matrix(graph, params)
    eig = np.linalg.eigvals(K)
    Rc = float(np.max(np.abs(eig)))
    regime = ("certified-stable (Rc<1)" if Rc < 1.0
              else "cascade-prone (Rc>=1): stability certificate unavailable")
    return ThresholdResult(Rc=Rc, K=K, q_star=q_star, pi0=pi0, regime=regime)


def critical_delay_scalar(alpha: float, a: float = -0.6, b: float = 0.75):
    """Critical delay tau*(alpha) of the scalar test system (Theorem 4).

    System:  C D^alpha y = a y + b y(t - tau),  with a < 0 < b, b > |a|.
    A stability crossing s = i omega satisfies  s^alpha = a + b e^{-s tau}, i.e.
    the magnitude balance |omega^alpha e^{i alpha pi/2} - a| = b fixes omega, then

        tau*(alpha) = (1/omega) [ arg(omega^alpha e^{i alpha pi/2} - a) - arg(b) ]  (mod 2pi/omega).

    Returns (tau_star, omega) or (nan, nan) if no positive crossing exists.
    """
    # solve P(omega) = omega^{2a} - 2 a omega^alpha cos(alpha pi/2) + a^2 - b^2 = 0
    def P(w):
        return (w ** (2 * alpha) - 2 * a * w ** alpha * np.cos(alpha * np.pi / 2)
                + a**2 - b**2)

    # bracket a positive root by scanning
    ws = np.linspace(1e-4, 10.0, 20000)
    vals = P(ws)
    sign_change = np.where(np.diff(np.sign(vals)) != 0)[0]
    if len(sign_change) == 0:
        return float("nan"), float("nan")
    from scipy.optimize import brentq
    w0 = brentq(P, ws[sign_change[0]], ws[sign_change[0] + 1])
    s_alpha = w0 ** alpha * np.exp(1j * alpha * np.pi / 2)
    phase = np.angle(s_alpha - a) - np.angle(b + 0j)
    tau = (phase % (2 * np.pi)) / w0
    return float(tau), float(w0)


__all__ = ["cascade_threshold", "comparison_matrix", "ThresholdResult",
           "critical_delay_scalar"]
