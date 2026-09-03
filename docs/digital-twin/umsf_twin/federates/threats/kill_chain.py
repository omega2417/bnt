"""Semi-Markov attack-stage machine (section 9.6).

Multi-step events must stay causal: a lateral movement cannot precede the
reconnaissance that motivated it. The chain below enforces that ordering and
gives each stage an explicit dwell-time distribution, which is what the
ground-truth labels are derived from.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

__all__ = ["KillChain", "STAGES", "STAGE_TRANSITIONS"]

STAGES = ("DORMANT", "RECON", "FOOTHOLD", "LATERAL", "C2", "COLLECTION", "CONTAINED")

#: stage -> ((next_stage, probability), ...)
STAGE_TRANSITIONS: dict[str, tuple[tuple[str, float], ...]] = {
    "DORMANT": (("RECON", 1.0),),
    "RECON": (("FOOTHOLD", 0.6), ("DORMANT", 0.1), ("RECON", 0.3)),
    "FOOTHOLD": (("LATERAL", 0.7), ("C2", 0.2), ("FOOTHOLD", 0.1)),
    "LATERAL": (("C2", 0.5), ("COLLECTION", 0.3), ("LATERAL", 0.2)),
    "C2": (("COLLECTION", 0.4), ("C2", 0.6)),
    "COLLECTION": (("CONTAINED", 0.3), ("COLLECTION", 0.7)),
    "CONTAINED": (("CONTAINED", 1.0),),
}

#: stage -> (median dwell seconds, lognormal sigma)
DWELL = {
    "DORMANT": (60.0, 0.5), "RECON": (45.0, 0.6), "FOOTHOLD": (30.0, 0.7),
    "LATERAL": (60.0, 0.8), "C2": (120.0, 0.9), "COLLECTION": (90.0, 0.7),
    "CONTAINED": (1e9, 0.1),
}


@dataclass
class KillChain:
    campaign_id: str
    site_id: str
    stage: str = "DORMANT"
    dwell_remaining_s: float = 0.0
    history: list[tuple[float, str]] = field(default_factory=list)

    def _draw_dwell(self, rng: random.Random) -> float:
        median, sigma = DWELL[self.stage]
        return min(1e6, rng.lognormvariate(__import__("math").log(median), sigma))

    def step(self, t_s: float, dt_s: float, rng: random.Random,
             active: bool) -> dict[str, Any]:
        if not active:
            if self.stage != "DORMANT":
                self.stage = "CONTAINED"
            return self.snapshot(t_s)
        if not self.history:
            self.history.append((t_s, self.stage))
            self.dwell_remaining_s = self._draw_dwell(rng)

        self.dwell_remaining_s -= dt_s
        if self.dwell_remaining_s <= 0.0:
            roll, cumulative = rng.random(), 0.0
            for candidate, probability in STAGE_TRANSITIONS[self.stage]:
                cumulative += probability
                if roll <= cumulative:
                    if candidate != self.stage:
                        self.stage = candidate
                        self.history.append((t_s, candidate))
                    break
            self.dwell_remaining_s = self._draw_dwell(rng)
        return self.snapshot(t_s)

    def snapshot(self, t_s: float) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "site_id": self.site_id,
            "stage": self.stage,
            "stage_index": STAGES.index(self.stage),
            "dwell_remaining_s": max(0.0, self.dwell_remaining_s),
            "transitions": len(self.history),
        }
