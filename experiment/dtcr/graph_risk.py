"""Dependency-graph risk propagation - Eq. (8)-(11).

Corrections relative to Man-V3, all mandated by section 6 of the experiment
protocol and reflected in docs/manuscript_corrections.md:

* W is COLUMN-normalised (each dependent node distributes unit in-weight over its
  parents). Columns that are entirely zero - i.e. nodes with in-degree 0 - are
  left as zero columns rather than being renormalised; such nodes receive no
  propagated contribution and keep R'_i = R_i.
* Local risk uses the multiplicative form R_i = a_i * (1 - T_i) * s_i exactly as
  written in Eq. (8); the code contains no additive variant, so text and
  implementation are identical.
* Convergence is checked explicitly via the spectral radius of lambda*W^T; the
  closed form is used only when the margin is positive.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

__all__ = ["local_risk", "column_normalize", "GraphRiskResult", "propagate", "spectral_radius"]


def local_risk(a: np.ndarray, T: np.ndarray, s: np.ndarray) -> np.ndarray:
    """R_i(t) = a_i(t) * (1 - T_i(t)) * s_i - Eq. (8), multiplicative composition."""
    a = np.asarray(a, dtype=float)
    T = np.asarray(T, dtype=float)
    s = np.asarray(s, dtype=float)
    return a * (1.0 - T) * s


def column_normalize(W: np.ndarray) -> np.ndarray:
    """Normalise each column to unit sum; zero columns (in-degree 0) stay zero."""
    W = np.asarray(W, dtype=float).copy()
    sums = W.sum(axis=0)
    nz = sums > 0
    W[:, nz] = W[:, nz] / sums[nz]
    return W


def spectral_radius(M: np.ndarray) -> float:
    return float(np.max(np.abs(np.linalg.eigvals(np.asarray(M, dtype=float)))))


@dataclass
class GraphRiskResult:
    R: np.ndarray
    R_prop: np.ndarray
    kappa: float
    rho_lambda_W: float
    converged: bool
    margin: float


def propagate(R: np.ndarray, W: np.ndarray, lam: float, normalize: bool = True) -> GraphRiskResult:
    """R' = (I - lambda W^T)^-1 R - Eq. (9), (10); kappa = ||R'||_1/||R||_1 - Eq. (11)."""
    R = np.asarray(R, dtype=float)
    W = column_normalize(W) if normalize else np.asarray(W, dtype=float)
    M = lam * W.T
    rho = spectral_radius(M)
    converged = rho < 1.0
    if not converged:
        raise ValueError(
            f"spectral radius rho(lambda W^T)={rho:.4f} >= 1; Eq. (10) does not converge"
        )
    R_prop = np.linalg.solve(np.eye(W.shape[0]) - M, R)
    denom = float(np.abs(R).sum())
    kappa = float(np.abs(R_prop).sum() / denom) if denom > 0 else 1.0
    return GraphRiskResult(
        R=R, R_prop=R_prop, kappa=kappa, rho_lambda_W=rho,
        converged=True, margin=1.0 - rho,
    )
