"""Probabilistic block auditing - Eq. (4), (5) of the manuscript.

Exact detection probability uses the hypergeometric without-replacement model;
the lower bound uses independent sampling with replacement.
"""
from __future__ import annotations

import math

__all__ = ["p_detect_exact", "p_detect_lower_bound", "r_min", "challenge"]


def p_detect_exact(l: int, d: int, r: int) -> float:
    """P(at least one of d corrupted blocks among r drawn without replacement from l)."""
    if not (0 <= d <= l):
        raise ValueError("require 0 <= d <= l")
    if not (1 <= r <= l):
        raise ValueError("require 1 <= r <= l")
    if d == 0:
        return 0.0
    if r > l - d:
        return 1.0
    p_miss = 1.0
    for j in range(r):
        p_miss *= (l - d - j) / (l - j)
    return 1.0 - p_miss


def p_detect_lower_bound(l: int, d: int, r: int) -> float:
    """Conservative bound 1 - (1 - d/l)**r (independent sampling)."""
    if l <= 0:
        raise ValueError("l must be positive")
    return 1.0 - (1.0 - d / l) ** r


def r_min(l: int, d: int, eta: float) -> int:
    """Smallest r with lower-bound detection probability >= eta - Eq. (5)."""
    if not (0.0 < eta < 1.0):
        raise ValueError("eta must lie in (0,1)")
    p = d / l
    if p <= 0.0:
        raise ValueError("no corruption: r_min undefined")
    if p >= 1.0:
        return 1
    return int(math.ceil(math.log(1.0 - eta) / math.log(1.0 - p)))


def challenge(rng, l: int, corrupted_idx: set[int], r: int) -> tuple[bool, int]:
    """Draw r distinct block indices and report whether any corrupted block was hit.

    Returns (detected, n_corrupt_hits). This is the operational audit actually
    executed per cycle by the harness; it does not consult p_detect_exact.
    """
    r = max(1, min(r, l))
    drawn = rng.choice(l, size=r, replace=False)
    hits = sum(1 for b in drawn.tolist() if b in corrupted_idx)
    return hits > 0, hits
