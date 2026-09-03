"""Charger surrogate with a nameplate ceiling and a software limit.

Two separate numbers, deliberately: ``nameplate_max_a`` is what the proposed
charger claims, ``software_limit_a`` is what the twin allows. Neither is a
safety authorisation; section 9.8 requires the minimum over cell, BMS, FET,
cable and fuse limits before any current reaches hardware.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = ["Charger"]


@dataclass
class Charger:
    nameplate_max_a: float = 10.0
    software_limit_a: float = 4.0
    power_limit_w: float = 450.0
    cv_cell_v: float = 4.20
    enabled: bool = False
    delivered_wh: float = 0.0
    evidence_status: str = "SYNTHETIC_DEMO_ONLY_UNVERIFIED"

    @property
    def effective_current_limit_a(self) -> float:
        return min(self.nameplate_max_a, self.software_limit_a)

    def request_power_w(self, soc_pct: float) -> float:
        """CC below the CV knee, then a linear taper - a coarse approximation."""

        if not self.enabled:
            return 0.0
        if soc_pct < 85.0:
            return self.power_limit_w
        taper = max(0.05, (100.0 - soc_pct) / 15.0)
        return self.power_limit_w * taper

    def account(self, accepted_w: float, dt_s: float) -> dict[str, Any]:
        self.delivered_wh += max(0.0, accepted_w) * dt_s / 3600.0
        return {
            "charger_enabled": self.enabled,
            "charger_current_limit_a": self.effective_current_limit_a,
            "charger_delivered_wh": self.delivered_wh,
            "charger_evidence": self.evidence_status,
        }
