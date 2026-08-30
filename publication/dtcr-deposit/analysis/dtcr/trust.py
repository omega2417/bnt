"""Dynamic provenance-aware trust (manuscript Eq. 2-3)."""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["TrustWeights", "instantaneous_trust", "smooth_trust", "TrustTracker"]


@dataclass(frozen=True)
class TrustWeights:
    """Weights of the integrity / provenance / behaviour components; must sum to 1."""

    alpha: float = 0.40
    beta: float = 0.35
    gamma: float = 0.25

    def __post_init__(self) -> None:
        total = self.alpha + self.beta + self.gamma
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"alpha+beta+gamma must equal 1, got {total}")


def instantaneous_trust(c: float, q: float, b: float,
                        w: TrustWeights | None = None) -> float:
    """T_i^inst(t) = alpha*c + beta*q + gamma*b, Eq. (2)."""
    w = w or TrustWeights()
    return w.alpha * c + w.beta * q + w.gamma * b


def smooth_trust(prev: float, inst: float, rho: float = 0.60) -> float:
    """T_i(t) = rho*T_i(t-1) + (1-rho)*T_i^inst(t), Eq. (3)."""
    if not (0.0 <= rho < 1.0):
        raise ValueError("require 0 <= rho < 1")
    return rho * prev + (1.0 - rho) * inst


class TrustTracker:
    """Stateful per-asset trust with an explicit initial value."""

    def __init__(self, initial: float = 1.0, rho: float = 0.60,
                 weights: TrustWeights | None = None):
        self.value = float(initial)
        self.rho = rho
        self.weights = weights or TrustWeights()
        self.history = [self.value]

    def update(self, c: float, q: float, b: float) -> float:
        inst = instantaneous_trust(c, q, b, self.weights)
        self.value = smooth_trust(self.value, inst, self.rho)
        self.history.append(self.value)
        return self.value
