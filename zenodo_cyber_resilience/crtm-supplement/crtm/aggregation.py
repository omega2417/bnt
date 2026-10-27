"""Non-compensatory aggregation operators (Section 6).

All operators take a vector m in [0, 1]^q of normalized metrics, a weight
vector w on the simplex and a set K of core (knockout) positions
(0-based indices).

  additive     S_w(m)                                  (weighted mean)
  hard_gate    mu^Phi   = Phi_K(m) S_w(m)              (eq. 14)
  power        mu^(g)   = (prod_K m_k)^g S_w(m)        (eq. 15)
  capped       mu^[th]  = min{S_w, min_K m_k / th_k}   (eq. 16)
  missing      mu_O and the enclosure of Proposition 6 (eqs. 17-18)
"""
from __future__ import annotations

from typing import Iterable, Sequence

import numpy as np


def _w(w, q: int | None = None) -> np.ndarray:
    w = np.asarray(w, dtype=float)
    if np.any(w < 0) or not np.isclose(w.sum(), 1.0, atol=1e-9):
        raise ValueError("weights must be nonnegative and sum to 1")
    if q is not None and w.size != q:
        raise ValueError("weights and metrics differ in length")
    return w


def _theta(theta, K: Sequence[int]) -> np.ndarray:
    th = np.broadcast_to(np.asarray(theta, dtype=float), (len(K),))
    if np.any(th <= 0) or np.any(th > 1):
        raise ValueError("thresholds theta_k must lie in (0, 1]")
    return th


def additive(m, w) -> float:
    """Weighted arithmetic mean S_w(m)."""
    m = np.asarray(m, dtype=float)
    return float(_w(w, m.size) @ m)


def gate(m, K: Iterable[int]) -> int:
    """Stop factor Phi_K(m) = prod_{k in K} 1[m_k > 0]."""
    m = np.asarray(m, dtype=float)
    return int(all(m[k] > 0 for k in K))


def hard_gate(m, w, K: Iterable[int] = ()) -> float:
    """Hard-gated score mu^Phi (eq. 14)."""
    return gate(m, K) * additive(m, w)


def power(m, w, K: Sequence[int], gamma: float = 1.0) -> float:
    """Power-discounted score mu^(gamma) (eq. 15)."""
    m = np.asarray(m, dtype=float)
    core = np.prod([m[k] for k in K]) if len(K) else 1.0
    return float(core ** gamma * additive(m, w))


def capped(m, w, K: Sequence[int], theta=0.5) -> float:
    """Capped knockout operator mu^[theta] (Definition 9, eq. 16)."""
    m = np.asarray(m, dtype=float)
    s = additive(m, w)
    if not len(K):
        return s
    th = _theta(theta, K)
    return float(min(s, min(m[k] / t for k, t in zip(K, th))))


def compensation_capacity_additive(w, k: int) -> float:
    """C_k(S_w) = 1 - w_k (Section 6.1)."""
    return float(1.0 - np.asarray(w, dtype=float)[k])


# ------------------------------------------------------------ missing data
def missing_enclosure(m, w, K: Sequence[int] = (), theta=None) -> dict:
    """Renormalized score and enclosure for missing metrics (Proposition 6).

    Missing metrics are NaN in ``m``. Returns a dict with completeness kappa,
    renormalized score mu_O (eq. 17), lower/upper bound of (18), and the
    status. A missing core metric gives status 'not computed'.
    """
    m = np.asarray(m, dtype=float)
    w = _w(w, m.size)
    obs = ~np.isnan(m)
    if any(not obs[k] for k in K):
        return {"status": "not computed: missing core metric", "kappa": float(w[obs].sum()),
                "mu_O": np.nan, "lower": np.nan, "upper": np.nan}
    kappa = float(w[obs].sum())
    if kappa <= 0:
        raise ValueError("no observed metric carries weight")
    g = gate(np.where(obs, m, 1.0), K)
    mu_o = g * float(w[obs] @ m[obs]) / kappa
    lower = kappa * mu_o
    upper = kappa * mu_o + (1 - kappa) if g else 0.0
    if theta is not None and len(K):
        th = _theta(theta, K)
        cap = min(m[k] / t for k, t in zip(K, th))
        lower, upper, mu_o_cap = min(lower, cap), min(upper, cap), min(mu_o, cap)
    else:
        mu_o_cap = mu_o
    return {"status": "ok" if kappa == 1 else "enclosure", "kappa": kappa,
            "mu_O": float(mu_o_cap), "lower": float(lower), "upper": float(upper),
            "max_deviation": float((1 - kappa) * max(mu_o, 1 - mu_o)) if g else 0.0}


# ---------------------------------------------------------- property tests
def is_idempotent(op, q: int, ts=np.linspace(0, 1, 101)) -> bool:
    """Numerically test A(t, ..., t) = t."""
    return bool(all(np.isclose(op(np.full(q, t)), t) for t in ts))


def has_veto(op, q: int, k: int, trials: int = 200, seed: int = 0) -> bool:
    """Numerically test m_k = 0 => A(m) = 0 on random points."""
    rng = np.random.default_rng(seed)
    for _ in range(trials):
        m = rng.random(q)
        m[k] = 0.0
        if op(m) != 0.0:
            return False
    return True


def max_jump_at(op, m, k: int, eps: float = 1e-9) -> float:
    """|A(m with m_k = eps) - A(m with m_k = 0)|: a continuity probe."""
    a = np.array(m, dtype=float)
    b = a.copy()
    a[k], b[k] = 0.0, eps
    return abs(op(b) - op(a))
