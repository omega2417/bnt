"""Three independent EcoFlow stations as separate black-box models (9.7).

The source document lists three units but no measured parameters, so each unit
gets its own object with its own unknowns rather than being merged into one
aggregate battery. Transition time defaults are conditional and must not be
described as "zero-switchover" without measurement.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["EcoFlowUnit", "EcoFlowBank"]


@dataclass
class EcoFlowUnit:
    unit_id: str
    usable_energy_wh: float = 1000.0
    min_usable_soc_pct: float = 5.0
    soc_pct: float = 100.0
    transition_ms: float = 20.0
    efficiency_curve: tuple[tuple[float, float], ...] = ((100.0, 0.86), (300.0, 0.90),
                                                         (600.0, 0.88), (1200.0, 0.83))
    protected_group: int = 2
    recharge_w: float = 300.0
    online: bool = True
    evidence_status: str = "UNINVENTORIED"
    delivered_wh: float = 0.0

    def efficiency(self, load_w: float) -> float:
        points = self.efficiency_curve
        if load_w <= points[0][0]:
            return points[0][1]
        for (x0, y0), (x1, y1) in zip(points, points[1:]):
            if load_w <= x1:
                span = (load_w - x0) / (x1 - x0)
                return y0 + span * (y1 - y0)
        return points[-1][1]

    @property
    def available_wh(self) -> float:
        usable_pct = max(0.0, self.soc_pct - self.min_usable_soc_pct)
        return self.usable_energy_wh * usable_pct / 100.0

    def discharge(self, load_w: float, dt_s: float) -> dict[str, Any]:
        if not self.online or load_w <= 0.0:
            return {"unit_id": self.unit_id, "supplied_w": 0.0, "soc_pct": self.soc_pct,
                    "efficiency": 0.0, "depleted": self.available_wh <= 0.0}
        efficiency = self.efficiency(load_w)
        need_wh = load_w * dt_s / 3600.0 / efficiency
        supplied_wh = min(self.available_wh, need_wh)
        self.soc_pct = max(0.0, self.soc_pct - 100.0 * supplied_wh / self.usable_energy_wh)
        self.delivered_wh += supplied_wh
        return {
            "unit_id": self.unit_id,
            "supplied_w": supplied_wh * 3600.0 / dt_s * efficiency,
            "soc_pct": self.soc_pct,
            "efficiency": efficiency,
            "depleted": self.available_wh <= 0.0,
        }

    def recharge(self, dt_s: float) -> None:
        if self.soc_pct < 100.0:
            self.soc_pct = min(100.0, self.soc_pct
                               + 100.0 * self.recharge_w * dt_s / 3600.0
                               / self.usable_energy_wh)


@dataclass
class EcoFlowBank:
    units: list[EcoFlowUnit] = field(default_factory=list)

    @classmethod
    def default(cls) -> "EcoFlowBank":
        return cls([EcoFlowUnit(f"ECOFLOW-{index}") for index in (1, 2, 3)])

    def supply(self, load_w: float, dt_s: float) -> dict[str, Any]:
        """Split the load evenly across online units."""

        online = [unit for unit in self.units if unit.online and unit.available_wh > 0.0]
        if not online:
            return {"ecoflow_supplied_w": 0.0, "ecoflow_units_online": 0,
                    "ecoflow_min_soc_pct": min((u.soc_pct for u in self.units), default=0.0),
                    "ecoflow_depleted": True}
        share = load_w / len(online)
        rows = [unit.discharge(share, dt_s) for unit in online]
        return {
            "ecoflow_supplied_w": sum(row["supplied_w"] for row in rows),
            "ecoflow_units_online": len(online),
            "ecoflow_min_soc_pct": min(unit.soc_pct for unit in self.units),
            "ecoflow_depleted": all(unit.available_wh <= 0.0 for unit in self.units),
        }

    def recharge(self, dt_s: float) -> None:
        for unit in self.units:
            unit.recharge(dt_s)
