"""Probabilistic block audit (manuscript Eq. 4-5).

A replica holds ``l`` blocks of which ``d`` are corrupted.  ``r`` distinct blocks
are challenged without replacement.  ``p_detect_exact`` implements the
hypergeometric probability of hitting at least one corrupted block;
``p_detect_bound`` implements the independent-sampling lower bound; and
``r_min`` inverts the bound to a sufficient challenge budget.
"""
from __future__ import annotations

import math

__all__ = ["p_detect_exact", "p_detect_bound", "r_min", "challenge_table"]


def p_detect_exact(l: int, d: int, r: int) -> float:
    """Exact without-replacement detection probability, Eq. (4).

    P_det = 1 - prod_{j=0}^{r-1} (l - d - j) / (l - j)
    """
    if not (0 <= d <= l):
        raise ValueError("require 0 <= d <= l")
    if not (0 <= r <= l):
        raise ValueError("require 0 <= r <= l")
    if d == 0:
        return 0.0
    if r > l - d:  # more challenges than clean blocks -> certain hit
        return 1.0
    miss = 1.0
    for j in range(r):
        miss *= (l - d - j) / (l - j)
    return 1.0 - miss


def p_detect_bound(p: float, r: int) -> float:
    """Conservative lower bound 1 - (1 - p)^r with p = d/l."""
    if not (0.0 <= p <= 1.0):
        raise ValueError("require 0 <= p <= 1")
    return 1.0 - (1.0 - p) ** r


def r_min(p: float, eta: float) -> int:
    """Smallest challenge count meeting a lower-bound target eta, Eq. (5)."""
    if not (0.0 < p < 1.0):
        raise ValueError("require 0 < p < 1")
    if not (0.0 < eta < 1.0):
        raise ValueError("require 0 < eta < 1")
    return int(math.ceil(math.log(1.0 - eta) / math.log(1.0 - p)))


def challenge_table(fractions=(0.01, 0.05, 0.10, 0.20),
                    targets=(0.90, 0.95, 0.99),
                    l: int = 10000):
    """Reproduce manuscript Table 5 and add the exact probability achieved."""
    rows = []
    for p in fractions:
        row = {"corrupted_fraction": p}
        for eta in targets:
            r = r_min(p, eta)
            row[f"r_min_{int(eta * 100)}"] = r
            row[f"p_exact_{int(eta * 100)}"] = p_detect_exact(l, int(round(p * l)), r)
        rows.append(row)
    return rows
