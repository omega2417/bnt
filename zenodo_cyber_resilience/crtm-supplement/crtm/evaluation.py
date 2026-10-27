"""Evaluation algorithm for one threat scenario (Section 6.7, Figure 8)
and roll-up to a resilience profile (Definition 10)."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import aggregation as agg
from .metrics import Action
from .scale import level, level_abbr

OPERATORS = ("additive", "hard_gate", "power", "capped")


@dataclass
class ActionResult:
    ident: str
    goal: str
    status: str
    score: float
    level: int
    kappa: float
    lower: float
    upper: float
    contributions: list[float] = field(default_factory=list)
    normalized: list[float] = field(default_factory=list)
    inconsistent: list[int] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = self.__dict__.copy()
        d["level_abbr"] = level_abbr(self.score)
        return d


def score_vector(m, w, K, operator: str = "hard_gate", gamma: float = 1.0, theta=0.5) -> float:
    """Apply one of the action operators to a complete vector."""
    if operator == "additive":
        return agg.additive(m, w)
    if operator == "hard_gate":
        return agg.hard_gate(m, w, K)
    if operator == "power":
        return agg.power(m, w, K, gamma)
    if operator == "capped":
        return agg.capped(m, w, K, theta)
    raise ValueError(f"unknown operator {operator!r}")


def evaluate_action(action: Action, method: str = "anchored", operator: str = "hard_gate",
                    gamma: float = 1.0, theta=0.5) -> ActionResult:
    """Score one basic action following Figure 8.

    1. validate class tables (8) and weights;
    2. refuse to score if a core (knockout) metric is missing;
    3. normalize each observed metric once;
    4. apply the operator; if metrics are missing, return mu_O with the
       enclosure of Proposition 6.
    """
    for mt in action.metrics:
        mt.table.validate()
    w = action.w()
    agg._w(w, action.q)
    K = action.core
    m = action.vector(method)
    inconsistent = [p for p, mt in enumerate(action.metrics)
                    if mt.observed and level(mt.normalized(method)) != mt.tabulated_level()]
    if any(math.isnan(m[k]) for k in K):
        return ActionResult(action.ident, action.goal, "not computed: missing core metric",
                            math.nan, 0, float(w[~np.isnan(m)].sum()), math.nan, math.nan,
                            normalized=m.tolist(), inconsistent=inconsistent)
    contrib = [float(w[p] * m[p]) if not math.isnan(m[p]) else math.nan for p in range(action.q)]
    if not np.isnan(m).any():
        s = score_vector(m, w, K, operator, gamma, theta)
        return ActionResult(action.ident, action.goal, "ok", s, level(s), 1.0, s, s,
                            contrib, m.tolist(), inconsistent)
    if operator not in ("hard_gate", "capped", "additive"):
        raise ValueError("the enclosure of Proposition 6 is stated for additive, gate and cap")
    enc = agg.missing_enclosure(m, w, K if operator != "additive" else (),
                                theta if operator == "capped" else None)
    return ActionResult(action.ident, action.goal, enc["status"], enc["mu_O"], level(enc["mu_O"]),
                        enc["kappa"], enc["lower"], enc["upper"], contrib, m.tolist(), inconsistent)


def evaluate_scenario(actions: dict[str, Action], selected=None, method: str = "anchored",
                      operator: str = "hard_gate", **kw) -> dict:
    """Evaluate the selected actions and roll up to goals (mean and minimum)."""
    selected = list(selected) if selected is not None else list(actions)
    res = {b: evaluate_action(actions[b], method, operator, **kw) for b in selected}
    goals: dict[str, list[float]] = {}
    for r in res.values():
        if not math.isnan(r.score):
            goals.setdefault(r.goal, []).append(r.score)
    profile = {g: {"mean": float(np.mean(v)), "min": float(np.min(v)),
                   "level_mean": level_abbr(np.mean(v)), "level_min": level_abbr(np.min(v))}
               for g, v in goals.items()}
    n_metrics = sum(actions[b].q for b in selected)
    return {"actions": res, "profile": profile, "N_theta": n_metrics,
            "observed": sum(mt.observed for b in selected for mt in actions[b].metrics)}


def dominates(p: dict, q: dict, key: str = "mean") -> bool:
    """Product order on profiles: p >= q in every goal."""
    return all(p[g][key] >= q[g][key] for g in q)
