"""Cross-site correlation with a causal window.

An alert at site B minutes after one at site A is only evidence of a campaign
if the ordering is physically possible. The correlator therefore respects a
minimum propagation delay and a maximum window, and it records the pair it
used so the claim can be audited.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Any

__all__ = ["CrossSiteCorrelator"]


@dataclass
class CrossSiteCorrelator:
    window_s: float = 120.0
    min_delay_s: float = 0.0
    recent: deque = field(default_factory=lambda: deque(maxlen=512))
    correlations: int = 0

    def offer(self, t_s: float, site_id: str, score: float,
              stage: str = "") -> dict[str, Any]:
        self.recent.append((t_s, site_id, score, stage))
        partners = [item for item in self.recent
                    if item[1] != site_id
                    and self.min_delay_s <= t_s - item[0] <= self.window_s
                    and item[2] >= 0.3]
        if not partners and score < 0.3:
            return {"correlated": False, "correlated_with": "", "joint_score": score}
        if not partners:
            return {"correlated": False, "correlated_with": "", "joint_score": score}
        best = max(partners, key=lambda item: item[2])
        self.correlations += 1
        joint = min(1.0, 1.0 - (1.0 - score) * (1.0 - best[2]))
        return {
            "correlated": True,
            "correlated_with": f"{best[1]}@{best[0]:.0f}s",
            "joint_score": joint,
            "partner_stage": best[3],
        }
