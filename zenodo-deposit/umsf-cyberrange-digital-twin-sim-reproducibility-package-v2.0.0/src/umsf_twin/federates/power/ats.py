"""Automatic transfer switch with a measured-transition placeholder.

``transition_ms`` is a project value, not a measurement: the twin therefore
records both the modelled transition and the fact that it is unverified, so a
downstream claim about "8 ms transfer" cannot be made by accident.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["TransferSwitch"]


@dataclass
class TransferSwitch:
    transition_ms: float = 8.0
    evidence_status: str = "SYNTHETIC_DEMO_ONLY_UNVERIFIED"
    source: str = "MAINS"                 # MAINS | BATTERY
    transitions: int = 0
    last_transition_s: float | None = None
    outage_ms_total: float = 0.0

    def request(self, target: str, t_s: float) -> dict[str, Any]:
        changed = target != self.source
        if changed:
            self.source = target
            self.transitions += 1
            self.last_transition_s = t_s
            self.outage_ms_total += self.transition_ms
        return {
            "ats_source": self.source,
            "ats_transitions": self.transitions,
            "ats_transition_ms": self.transition_ms if changed else 0.0,
            "ats_outage_ms_total": self.outage_ms_total,
            "ats_evidence": self.evidence_status,
        }
