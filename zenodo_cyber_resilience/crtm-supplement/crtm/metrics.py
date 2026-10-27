"""Metric model (Section 4) and loaders for the supplementary data files."""
from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from .hierarchy import Projection
from .normalization import ClassTable

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


@dataclass
class Metric:
    """Metric descriptor M = (X, u, sigma, tau, A, xi) with an observed value (Definition 4)."""

    code: str
    name: str
    unit: str
    table: ClassTable
    value: float = math.nan
    core: bool = False
    timing: str = ""            # 'ex-ante', 'ex-post' or '' (unspecified, ⊥)
    printed_classes: str = ""
    support: frozenset = frozenset()

    @property
    def observed(self) -> bool:
        return not math.isnan(self.value)

    @property
    def sigma(self) -> int:
        return self.table.sigma

    def normalized(self, method: str = "anchored") -> float:
        return math.nan if not self.observed else float(self.table.normalize(self.value, method))

    def tabulated_level(self) -> int:
        return 0 if not self.observed else int(self.table.tabulated_level(self.value))


@dataclass
class Action:
    """Basic action beta with its ordered metric tuple M(beta) and weights."""

    ident: str
    goal: str
    metrics: list[Metric] = field(default_factory=list)
    weights: np.ndarray | None = None
    weights_specified: bool = False

    @property
    def q(self) -> int:
        return len(self.metrics)

    @property
    def core(self) -> list[int]:
        return [p for p, m in enumerate(self.metrics) if m.core]

    def w(self) -> np.ndarray:
        if self.weights is None:
            return np.full(self.q, 1.0 / self.q)
        return np.asarray(self.weights, dtype=float)

    def vector(self, method: str = "anchored") -> np.ndarray:
        return np.array([m.normalized(method) for m in self.metrics])

    def check_support(self, alpha: frozenset) -> list[str]:
        """Support condition A_p ⊆ alpha(beta) of Definition 4."""
        return [f"{self.ident} p={p + 1}: support {sorted(m.support)} ⊄ {sorted(alpha)}"
                for p, m in enumerate(self.metrics) if not m.support <= alpha]


def _f(s: str) -> float:
    return math.nan if s.strip() == "" else float(s)


def load_metrics(path: str | Path | None = None) -> dict[str, Action]:
    """Load ``phishing_metrics.csv`` into an ordered dict of actions."""
    path = Path(path) if path else DATA_DIR / "phishing_metrics.csv"
    actions: dict[str, Action] = {}
    raw_w: dict[str, list[float]] = {}
    with open(path, encoding="utf-8", newline="") as fh:
        for row in csv.DictReader(fh):
            a = actions.setdefault(row["action"], Action(row["action"], row["goal"]))
            xi = tuple(float(row[f"xi{r}"]) for r in range(6))
            a.metrics.append(Metric(code=row["code"], name=row["metric"], unit=row["unit"],
                                    table=ClassTable(xi), value=_f(row["value"]),
                                    core=row["core"].strip() == "1", timing=row["timing"],
                                    printed_classes=row["printed_classes"]))
            raw_w.setdefault(a.ident, []).append(_f(row["weight"]))
    for a in actions.values():
        w = raw_w[a.ident]
        if all(not math.isnan(v) for v in w):
            a.weights, a.weights_specified = np.array(w), True
            if not math.isclose(sum(w), 1.0, abs_tol=1e-9):
                raise ValueError(f"weights of {a.ident} do not sum to 1")
    return actions


def load_scenarios(path: str | Path | None = None) -> dict:
    """Load ``scenarios.json``: catalog, projections and goal assignment."""
    path = Path(path) if path else DATA_DIR / "scenarios.json"
    with open(path, encoding="utf-8") as fh:
        d = json.load(fh)
    d["projections"] = {k: Projection(v["actions"], name=k) for k, v in d["scenarios"].items()}
    return d
