"""Pack-level energy, constant-power solve and thermal RC model.

Discharge solves ``P_bat = I(U_ocv - I R)`` for the physical root
``I = 2P / (U_ocv + sqrt(U_ocv^2 - 4 R P))`` so that terminal voltage and
current stay mutually consistent; a negative discriminant means the requested
power is not deliverable and is reported as such instead of being clipped
silently.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from .cell import CellStack

__all__ = ["BatteryPack", "solve_discharge_current", "solve_charge_current"]


def solve_discharge_current(power_w: float, ocv_v: float, resistance_ohm: float) -> float | None:
    """Return the current that delivers ``power_w``, or ``None`` if impossible."""

    if power_w <= 0.0:
        return 0.0
    discriminant = ocv_v * ocv_v - 4.0 * resistance_ohm * power_w
    if discriminant < 0.0:
        return None
    return 2.0 * power_w / (ocv_v + math.sqrt(discriminant))


def solve_charge_current(power_w: float, ocv_v: float, resistance_ohm: float) -> float:
    """Current absorbed when charging at ``power_w`` (always solvable)."""

    if power_w <= 0.0:
        return 0.0
    discriminant = ocv_v * ocv_v + 4.0 * resistance_ohm * power_w
    return (math.sqrt(discriminant) - ocv_v) / (2.0 * resistance_ohm)


@dataclass
class BatteryPack:
    usable_energy_wh: float = 2400.0
    soc_pct: float = 82.0
    soh_pct: float = 92.0
    resistance_ohm: float = 0.09
    path_efficiency: float = 0.91
    ambient_c: float = 23.0
    temp_c: float = 23.0
    thermal_gain_c_per_w: float = 0.45
    thermal_tau_s: float = 1200.0
    stack: CellStack = None            # type: ignore[assignment]
    cycles_wh_out: float = 0.0
    cycles_wh_in: float = 0.0
    charge_ah: float = 0.0

    def __post_init__(self) -> None:
        if self.stack is None:
            self.stack = CellStack()
        self.stack.set_soc(self.soc_pct / 100.0)

    # -- energy ----------------------------------------------------------
    @property
    def usable_now_wh(self) -> float:
        return self.usable_energy_wh * (self.soh_pct / 100.0)

    @property
    def energy_wh(self) -> float:
        return self.usable_now_wh * (self.soc_pct / 100.0)

    def discharge(self, load_w: float, dt_s: float) -> dict[str, Any]:
        """Draw ``load_w`` at the load side of the conversion path."""

        battery_w = max(0.0, load_w) / max(0.05, self.path_efficiency)
        ocv = self.stack.pack_ocv(self.temp_c)
        current = solve_discharge_current(battery_w, ocv, self.resistance_ohm)
        infeasible = current is None
        if infeasible:
            current = 0.0
            battery_w = 0.0

        available_wh = self.energy_wh
        drawn_wh = min(available_wh, battery_w * dt_s / 3600.0)
        if drawn_wh < battery_w * dt_s / 3600.0:
            infeasible = True
        self._set_energy(self.energy_wh - drawn_wh)
        self.cycles_wh_out += drawn_wh
        self.charge_ah -= current * dt_s / 3600.0
        self._thermal(current, dt_s)
        return self._report(current, battery_w, infeasible, "DISCHARGE")

    def charge(self, power_w: float, dt_s: float, current_limit_a: float,
               cell_ceiling_v: float) -> dict[str, Any]:
        ocv = self.stack.pack_ocv(self.temp_c)
        headroom_wh = max(0.0, self.usable_now_wh - self.energy_wh)
        requested_w = max(0.0, power_w)
        limit_w = current_limit_a * (ocv + current_limit_a * self.resistance_ohm)
        accepted_w = min(requested_w, limit_w, headroom_wh * 3600.0 / max(dt_s, 1e-9))

        inhibited = False
        current = solve_charge_current(accepted_w, ocv, self.resistance_ohm)
        cell_terminal = max(self.stack.terminals(-current, self.temp_c)) if current else 0.0
        if cell_terminal > cell_ceiling_v:
            inhibited = True
            accepted_w = 0.0
            current = 0.0

        added_wh = accepted_w * dt_s / 3600.0
        self._set_energy(self.energy_wh + added_wh)
        self.cycles_wh_in += added_wh
        self.charge_ah += current * dt_s / 3600.0
        self._thermal(current, dt_s)
        report = self._report(-current, accepted_w, False, "CHARGE")
        report["charge_inhibited"] = inhibited
        report["charge_current_limited"] = accepted_w < requested_w and not inhibited
        return report

    def idle(self, dt_s: float) -> dict[str, Any]:
        self._thermal(0.0, dt_s)
        return self._report(0.0, 0.0, False, "STANDBY")

    # -- internals -------------------------------------------------------
    def _set_energy(self, energy_wh: float) -> None:
        capacity = max(1e-9, self.usable_now_wh)
        self.soc_pct = max(0.0, min(100.0, 100.0 * energy_wh / capacity))
        self.stack.set_soc(self.soc_pct / 100.0)

    def _thermal(self, current_a: float, dt_s: float) -> None:
        joule_w = current_a * current_a * self.resistance_ohm
        gain = self.thermal_gain_c_per_w * joule_w
        self.temp_c += dt_s * ((gain - (self.temp_c - self.ambient_c))
                               / max(1.0, self.thermal_tau_s))

    def _report(self, current_a: float, battery_w: float, infeasible: bool,
                mode: str) -> dict[str, Any]:
        summary = self.stack.summary(current_a, self.temp_c)
        return {
            **summary,
            "mode": mode,
            "soc_pct": self.soc_pct,
            "soh_pct": self.soh_pct,
            "pack_current_a": current_a,
            "battery_power_w": battery_w,
            "battery_temp_c": self.temp_c,
            "energy_wh": self.energy_wh,
            "infeasible": infeasible,
            "coulomb_counter_ah": self.charge_ah,
        }

    def autonomy_min(self, critical_load_w: float) -> float:
        """``t_res = E_usable * eta / P_crit`` from section 9.8, in minutes."""

        if critical_load_w <= 0.0:
            return float("inf")
        return 60.0 * self.energy_wh * self.path_efficiency / critical_load_w
