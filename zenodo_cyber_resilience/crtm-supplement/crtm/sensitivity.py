"""Sensitivity of an action score to two response times (Section 7.4)."""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq

from . import aggregation as agg
from .metrics import Action


def score_with(action: Action, values: dict[int, float], method: str) -> float:
    """Hard-gated score of ``action`` with metric values replaced (0-based positions)."""
    m = []
    for p, mt in enumerate(action.metrics):
        x = values.get(p, mt.value)
        m.append(float(mt.table.normalize(x, method)))
    return agg.hard_gate(np.array(m), action.w(), action.core)


def grid(action: Action, p1: int, p2: int, r1, r2, method: str, n1: int = 401, n2: int = 521):
    """Score on a (n2 x n1) grid over metric p1 (x-axis) and p2 (y-axis)."""
    xs, ys = np.linspace(*r1, n1), np.linspace(*r2, n2)
    t1 = action.metrics[p1].table.normalize(xs, method)
    t2 = action.metrics[p2].table.normalize(ys, method)
    base = action.vector(method)
    w = action.w()
    rest = base @ w - w[p1] * base[p1] - w[p2] * base[p2]
    Z = rest + w[p1] * t1[None, :] + w[p2] * t2[:, None]
    return xs, ys, Z


def threshold(action: Action, p: int, target: float, method: str, lo: float, hi: float,
              fixed: dict[int, float] | None = None) -> float:
    """Value of metric p at which the score crosses ``target`` (root in [lo, hi])."""
    fixed = dict(fixed or {})
    f = lambda x: score_with(action, {**fixed, p: x}, method) - target
    return float(brentq(f, lo, hi, xtol=1e-10))
