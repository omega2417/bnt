"""Exact binary enumeration of the 18-system benchmark.

With n = 18 there are 2^18 = 262,144 candidate portfolios, so the complete
feasible set and the true Pareto front can be computed directly. That front is
the ground truth against which every heuristic in this package is scored.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .metrics import hypervolume
from .model import KneeSolution, PortfolioModel
from .pareto import nondominated_mask


@dataclass(frozen=True)
class ExactResult:
    """Outcome of one complete enumeration."""

    n_total: int
    """Number of binary portfolios examined (2^n)."""

    X_feasible: np.ndarray
    F_feasible: np.ndarray
    X_front: np.ndarray
    F_front: np.ndarray
    hypervolume: float
    knee: KneeSolution

    @property
    def n_feasible(self) -> int:
        return len(self.X_feasible)

    @property
    def feasible_fraction(self) -> float:
        return self.n_feasible / self.n_total

    @property
    def front_size(self) -> int:
        return len(self.F_front)

    def summary(self) -> dict[str, object]:
        return {
            "portfolios": self.n_total,
            "feasible": self.n_feasible,
            "feasible_percent": 100.0 * self.feasible_fraction,
            "front_size": self.front_size,
            "hypervolume": self.hypervolume,
            "knee_systems": list(self.knee.selected),
            "knee_benefit": self.knee.benefit,
            "knee_cost_normalized": float(self.knee.objectives[1]),
            "knee_risk_normalized": float(self.knee.objectives[2]),
        }


def all_binary_vectors(n: int) -> np.ndarray:
    """Every binary vector of length ``n``, one per row, in ascending integer order."""
    if n > 24:
        raise ValueError(f"Refusing to enumerate 2^{n} portfolios; use a heuristic")
    codes = np.arange(1 << n, dtype=np.uint32)[:, None]
    bits = np.arange(n, dtype=np.uint32)[None, :]
    return ((codes >> bits) & 1).astype(np.float64)


def enumerate_exact(model: PortfolioModel, chunk_size: int = 1 << 15) -> ExactResult:
    """Enumerate every portfolio and return the feasible set and exact front.

    Enumeration is chunked so that peak memory stays modest even though the full
    decision space is visited.
    """
    n = model.instance.n
    total = 1 << n

    feasible_X: list[np.ndarray] = []
    codes = np.arange(total, dtype=np.uint32)
    bits = np.arange(n, dtype=np.uint32)[None, :]

    for start in range(0, total, chunk_size):
        block = codes[start : start + chunk_size][:, None]
        X = ((block >> bits) & 1).astype(np.float64)
        keep = model.is_feasible(X)
        if np.any(keep):
            feasible_X.append(X[keep])

    X_feasible = (
        np.vstack(feasible_X) if feasible_X else np.zeros((0, n), dtype=float)
    )
    F_feasible = model.objectives(X_feasible)

    mask = nondominated_mask(F_feasible)
    X_front, F_front = X_feasible[mask], F_feasible[mask]

    order = np.lexsort(F_front.T[::-1])
    X_front, F_front = X_front[order], F_front[order]

    return ExactResult(
        n_total=total,
        X_feasible=X_feasible,
        F_feasible=F_feasible,
        X_front=X_front,
        F_front=F_front,
        hypervolume=hypervolume(F_front, model.scenario.reference_point),
        knee=model.knee(X_front, F_front),
    )
