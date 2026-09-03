"""Packet loss processes.

The Gilbert-Elliott chain gives bursty loss, which is what real degraded WAN
links produce; the independent Bernoulli model is kept only for MVP parity and
is explicitly marked as a simplification in the telemetry quality flags.
"""

from __future__ import annotations

from dataclasses import dataclass
import random

__all__ = ["GilbertElliott", "IndependentLoss"]


@dataclass
class GilbertElliott:
    """Two-state burst-loss chain (GOOD/BAD)."""

    good_loss_pct: float = 0.05
    bad_loss_pct: float = 12.0
    p_good_to_bad: float = 0.002
    p_bad_to_good: float = 0.25
    state: str = "GOOD"
    bad_steps: int = 0

    def step(self, rng: random.Random, stress: float = 0.0) -> float:
        """Return the loss percentage of this step.

        ``stress`` in ``0..1`` raises the transition probability into the BAD
        state; the network federate feeds it link utilisation and event load.
        """

        stress = max(0.0, min(1.0, stress))
        if self.state == "GOOD":
            if rng.random() < self.p_good_to_bad * (1.0 + 8.0 * stress):
                self.state = "BAD"
        else:
            self.bad_steps += 1
            if rng.random() < self.p_bad_to_good * (1.0 - 0.5 * stress):
                self.state = "GOOD"
        base = self.good_loss_pct if self.state == "GOOD" else self.bad_loss_pct
        return max(0.0, base * (1.0 + 0.5 * stress))

    def reset(self) -> None:
        self.state = "GOOD"
        self.bad_steps = 0


@dataclass
class IndependentLoss:
    """Constant-probability loss; permitted only as a documented simplification."""

    loss_pct: float = 0.1
    quality_flag: str = "ASSUMED_PARAMETER"

    def step(self, rng: random.Random, stress: float = 0.0) -> float:
        return max(0.0, self.loss_pct * (1.0 + stress))

    def reset(self) -> None:
        return None
