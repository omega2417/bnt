"""Provenance-aware dynamic trust - Eq. (2), (3)."""
from __future__ import annotations

from dataclasses import dataclass

__all__ = ["TrustParams", "instantaneous_trust", "TrustTracker"]


@dataclass(frozen=True)
class TrustParams:
    alpha: float = 0.40
    beta: float = 0.35
    gamma: float = 0.25
    rho: float = 0.60

    def __post_init__(self) -> None:
        s = self.alpha + self.beta + self.gamma
        if abs(s - 1.0) > 1e-9:
            raise ValueError(f"alpha+beta+gamma must equal 1, got {s}")
        if not (0.0 <= self.rho < 1.0):
            raise ValueError("rho must lie in [0,1)")


def instantaneous_trust(c: float, q: float, b: float, p: TrustParams) -> float:
    """T_i^inst(t) = alpha*c + beta*q + gamma*b."""
    return p.alpha * c + p.beta * q + p.gamma * b


class TrustTracker:
    """Exponentially smoothed trust with an explicit, inspectable state."""

    def __init__(self, params: TrustParams, initial: float = 1.0):
        self.p = params
        self.value = float(initial)
        self.history: list[float] = [float(initial)]

    def update(self, c: float, q: float, b: float) -> float:
        inst = instantaneous_trust(c, q, b, self.p)
        self.value = self.p.rho * self.value + (1.0 - self.p.rho) * inst
        self.history.append(self.value)
        return self.value
