"""Local risk and dependency-graph risk propagation (manuscript Eq. 8-11).

Two local-risk aggregations are provided.  ``local_risk_product`` is the
multiplicative form printed in the manuscript; it implements a hard AND and
collapses to zero whenever any single factor is zero.  ``local_risk_additive``
is the weighted alternative whose weights are chosen by ROC analysis on the
calibration set.  ``select_aggregation`` performs that comparison so the choice
is empirical rather than asserted.
"""
from __future__ import annotations

import numpy as np

__all__ = [
    "local_risk_product",
    "local_risk_additive",
    "row_normalise",
    "spectral_radius",
    "convergence_margin",
    "propagate",
    "propagate_iterative",
    "amplification",
    "select_aggregation",
]


def local_risk_product(a, T, s):
    """R_i = a_i (1 - T_i) s_i, Eq. (8) as printed."""
    return np.asarray(a, float) * (1.0 - np.asarray(T, float)) * np.asarray(s, float)


def local_risk_additive(a, T, s, w_a=0.45, w_t=0.35, w_at=0.20):
    """R_i = s_i [ w_a a_i + w_t (1 - T_i) + w_at a_i (1 - T_i) ], weights sum to 1."""
    total = w_a + w_t + w_at
    if abs(total - 1.0) > 1e-9:
        raise ValueError(f"weights must sum to 1, got {total}")
    a = np.asarray(a, float)
    t = 1.0 - np.asarray(T, float)
    return np.asarray(s, float) * (w_a * a + w_t * t + w_at * a * t)


def row_normalise(W: np.ndarray) -> np.ndarray:
    """Normalise each column of W to unit outgoing influence mass.

    W[i, j] is the weight of the dependency of j on i, so the propagation
    operator is W^T.  Normalising the outgoing mass of every source keeps the
    spectral radius bounded by 1 and makes lambda the only tuning knob.
    """
    W = np.asarray(W, dtype=float).copy()
    out = W.sum(axis=1, keepdims=True)
    nz = out.squeeze(-1) > 0
    W[nz] = W[nz] / out[nz]
    return W


def spectral_radius(W: np.ndarray, lam: float) -> float:
    """rho(lambda W^T)."""
    eig = np.linalg.eigvals(lam * np.asarray(W, float).T)
    return float(np.max(np.abs(eig)))


def convergence_margin(W: np.ndarray, lam: float) -> float:
    """1 - rho(lambda W^T); must be strictly positive for Eq. (10) to hold."""
    return 1.0 - spectral_radius(W, lam)


def propagate(R, W, lam: float):
    """Closed form R~ = (I - lambda W^T)^-1 R, Eq. (10), with a convergence guard."""
    R = np.asarray(R, float)
    W = np.asarray(W, float)
    margin = convergence_margin(W, lam)
    if margin <= 0:
        raise ValueError(
            f"rho(lambda W^T) = {1 - margin:.4f} >= 1; Eq. (10) does not converge"
        )
    return np.linalg.solve(np.eye(W.shape[0]) - lam * W.T, R)


def propagate_iterative(R, W, lam: float, iters: int = 200):
    """Fixed-point iteration of Eq. (9); used to verify the closed form."""
    R = np.asarray(R, float)
    W = np.asarray(W, float)
    x = R.copy()
    for _ in range(iters):
        x = R + lam * W.T @ x
    return x


def amplification(R, R_tilde) -> float:
    """kappa = ||R~||_1 / ||R||_1, Eq. (11); returns 1.0 when ||R||_1 = 0."""
    denom = float(np.abs(np.asarray(R, float)).sum())
    if denom == 0.0:
        return 1.0  # no local risk anywhere: define no amplification
    return float(np.abs(np.asarray(R_tilde, float)).sum()) / denom


def _auc(scores, labels) -> float:
    """Rank-based AUC without external dependencies."""
    scores = np.asarray(scores, float)
    labels = np.asarray(labels, int)
    pos, neg = labels == 1, labels == 0
    if pos.sum() == 0 or neg.sum() == 0:
        return float("nan")
    order = np.argsort(scores, kind="mergesort")
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, scores.size + 1, dtype=float)
    # average ranks for ties
    uniq, inv, counts = np.unique(scores, return_inverse=True, return_counts=True)
    mean_rank = np.zeros(uniq.size)
    np.add.at(mean_rank, inv, ranks)
    mean_rank /= counts
    ranks = mean_rank[inv]
    n_pos, n_neg = pos.sum(), neg.sum()
    return float((ranks[pos].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


def select_aggregation(a, T, s, labels, weight_grid=None):
    """Compare Eq. (8) against the additive form by AUC on labelled data.

    Returns the AUC of each candidate and the selected form, so the manuscript
    reports an empirically chosen aggregation instead of a postulated one.
    """
    weight_grid = weight_grid or [
        (0.45, 0.35, 0.20), (0.34, 0.33, 0.33), (0.60, 0.30, 0.10), (0.30, 0.50, 0.20)
    ]
    prod = local_risk_product(a, T, s)
    result = {"product_auc": _auc(prod, labels), "additive": []}
    best = ("product", result["product_auc"], None)
    for w in weight_grid:
        add = local_risk_additive(a, T, s, *w)
        auc = _auc(add, labels)
        result["additive"].append({"weights": w, "auc": auc})
        if auc > best[1]:
            best = ("additive", auc, w)
    result["selected_form"] = best[0]
    result["selected_auc"] = best[1]
    result["selected_weights"] = best[2]
    return result
