"""Power federate: the state machine of section 9.9 over real components.

States: ``MAINS``, ``BATTERY``, ``LOAD_SHED``, ``ISOLATED``,
``MAINS_RECOVERY_HOLD``, ``CHARGE_DELAY``. ``TELEMETRY_DEGRADED`` is *not* a
power state - it is an orthogonal observation state owned by the telemetry
federate, exactly as the specification requires.
"""

from __future__ import annotations

from typing import Any

from ...core.clock import Phase
from ...core.events import EventIndex
from ...core.federate import Federate, FederateHealth
from ...core.rng import RngHub
from .ats import TransferSwitch
from .bms import BatteryManagementSystem, BmsLimits
from .charger import Charger
from .ecoflow import EcoFlowBank
from .load_manager import LoadManager
from .pack import BatteryPack

__all__ = ["PowerFederate", "PowerState"]


class PowerState:
    MAINS = "MAINS"
    BATTERY = "BATTERY"
    LOAD_SHED = "LOAD_SHED"
    ISOLATED = "ISOLATED"
    MAINS_RECOVERY_HOLD = "MAINS_RECOVERY_HOLD"
    CHARGE_DELAY = "CHARGE_DELAY"


class PowerFederate(Federate):
    order = 20

    def __init__(self, config: dict[str, Any], events: EventIndex, rng: RngHub,
                 site_id: str = "site_a", name: str = "power") -> None:
        super().__init__(name)
        self.site_id = site_id
        self.events = events
        self.rng = rng
        self.cfg = config
        self.pack = BatteryPack(
            usable_energy_wh=float(config["usable_energy_wh"]),
            soc_pct=float(config["initial_soc_pct"]),
            soh_pct=float(config["soh_pct"]),
            resistance_ohm=float(config["pack_resistance_ohm"]),
            path_efficiency=float(config["path_efficiency"]),
            ambient_c=float(config["ambient_c"]),
            temp_c=float(config["ambient_c"]),
            thermal_gain_c_per_w=float(config["thermal_gain_c_per_w"]),
            thermal_tau_s=float(config["thermal_tau_s"]),
        )
        self.bms = BatteryManagementSystem(BmsLimits(
            cell_over_voltage_v=float(config["synthetic_max_cell_v"]),
            cell_under_voltage_v=float(config["synthetic_min_cell_v"]),
            pack_min_terminal_v=float(config["synthetic_min_terminal_v"]),
            charge_current_limit_a=float(config["synthetic_charge_current_limit_a"]),
            discharge_current_limit_a=float(config["synthetic_discharge_current_limit_a"]),
        ))
        self.charger = Charger(
            nameplate_max_a=float(config["charger_nameplate_max_a"]),
            software_limit_a=float(config["synthetic_charge_current_limit_a"]),
            power_limit_w=float(config["charger_power_limit_w"]),
        )
        self.ats = TransferSwitch(transition_ms=float(config["ats_transition_ms"]))
        self.ecoflow = EcoFlowBank.default()
        self.loads = LoadManager(shed_soc_pct=float(config.get("critical_soc_pct", 20)))
        self.state = PowerState.MAINS
        self.mains_present = True
        self.mains_return_since_s: float | None = None
        self.charge_enable_at_s: float | None = None
        self.row: dict[str, Any] = {}
        # Set from the previous step's BMS verdict: the current that a load
        # draws is only known after the electrical solve, so power-limited
        # shedding necessarily acts one step later, exactly as a real
        # controller reacting to a measured overcurrent would.
        self.overcurrent_flag = False
        self.transition_log: list[dict[str, Any]] = []

    # -- helpers ---------------------------------------------------------
    def _log_transition(self, t_s: float, previous: str, cause: str) -> None:
        if previous != self.state:
            self.transition_log.append({"t_s": t_s, "from": previous,
                                        "to": self.state, "cause": cause})

    def _group_loads(self) -> dict[int, float]:
        shared = self.context["shared"]
        assets = shared.get("assets", {}).get(self.site_id, {})
        groups = {1: 0.0, 2: 0.0, 3: 0.0}
        for row in assets.get("rows", []):
            groups[int(row["power_group"])] = groups.get(int(row["power_group"]), 0.0) \
                + float(row["power_w"])
        if not any(groups.values()):
            base = float(self.cfg["critical_load_w"])
            groups = {1: base * 0.55, 2: base * 0.25, 3: base * 0.20}
        return groups

    # -- federate API ----------------------------------------------------
    def advance(self, t_ns: int, dt_ns: int) -> None:
        t_s, dt_s = t_ns / 1e9, dt_ns / 1e9
        shared = self.context["shared"]
        policy = self.context["policy"]
        previous_state = self.state

        active = self.events.active(t_s, self.site_id)
        self.mains_present = not any(e.event_type == "mains_loss" for e in active)
        imbalance = next((e for e in active if e.event_type == "cell_imbalance"), None)
        charge_event = next((e for e in active if e.event_type == "charge_start"), None)
        self.pack.stack.apply_imbalance(int(imbalance.params["cell_index"]),
                                        imbalance.scaled("delta_mv", t_s)) if imbalance \
            else self.pack.stack.apply_imbalance(0, 0.0)

        group_loads = self._group_loads()
        extra_w = policy.clamp_power(float(shared.get("compute_add_w", {})
                                           .get(self.site_id, 0.0)))
        group_loads[3] = group_loads.get(3, 0.0) + extra_w

        # --- state machine -------------------------------------------------
        stable_s = float(self.cfg["mains_stable_before_return_s"])
        delay_s = float(self.cfg["recharge_delay_s"])

        if not self.mains_present:
            self.mains_return_since_s = None
            if self.state in (PowerState.MAINS, PowerState.MAINS_RECOVERY_HOLD,
                              PowerState.CHARGE_DELAY):
                self.state = PowerState.BATTERY
        else:
            if self.state in (PowerState.BATTERY, PowerState.LOAD_SHED):
                if self.mains_return_since_s is None:
                    self.mains_return_since_s = t_s
                self.state = PowerState.MAINS_RECOVERY_HOLD
            elif self.state == PowerState.MAINS_RECOVERY_HOLD:
                if self.mains_return_since_s is not None \
                        and t_s - self.mains_return_since_s >= stable_s:
                    self.state = PowerState.CHARGE_DELAY
                    self.charge_enable_at_s = t_s + delay_s
            elif self.state == PowerState.CHARGE_DELAY:
                if self.charge_enable_at_s is not None and t_s >= self.charge_enable_at_s:
                    self.state = PowerState.MAINS
                    self.bms.clear_latch()

        on_battery = self.state in (PowerState.BATTERY, PowerState.LOAD_SHED,
                                    PowerState.MAINS_RECOVERY_HOLD, PowerState.ISOLATED)
        self.ats.request("BATTERY" if on_battery else "MAINS", t_s)

        autonomy = self.pack.autonomy_min(sum(group_loads.values()))
        shed_row = self.loads.update(self.pack.soc_pct, autonomy, on_battery,
                                     overcurrent=self.overcurrent_flag and on_battery)
        retained_w = self.loads.retained_load_w(group_loads)
        if shed_row["shed_groups"] and self.state == PowerState.BATTERY:
            self.state = PowerState.LOAD_SHED
        elif not shed_row["shed_groups"] and self.state == PowerState.LOAD_SHED:
            self.state = PowerState.BATTERY

        # --- electrical step -------------------------------------------------
        eco = {"ecoflow_supplied_w": 0.0, "ecoflow_units_online": 0,
               "ecoflow_min_soc_pct": 100.0, "ecoflow_depleted": False}
        if self.state == PowerState.ISOLATED:
            report = self.pack.idle(dt_s)
        elif on_battery:
            eco = self.ecoflow.supply(retained_w * 0.35, dt_s)
            report = self.pack.discharge(max(0.0, retained_w - eco["ecoflow_supplied_w"]),
                                         dt_s)
        else:
            self.ecoflow.recharge(dt_s)
            self.charger.enabled = (self.state == PowerState.MAINS) or charge_event is not None
            request_w = self.charger.request_power_w(self.pack.soc_pct)
            if charge_event is not None:
                request_w = max(request_w, float(charge_event.params["power_w"]))
            report = self.pack.charge(request_w, dt_s,
                                      self.charger.effective_current_limit_a,
                                      self.bms.limits.cell_over_voltage_v) \
                if request_w > 0 else self.pack.idle(dt_s)
        self.charger.account(report.get("battery_power_w", 0.0) if report["mode"] == "CHARGE"
                             else 0.0, dt_s)

        protection = self.bms.evaluate(report, dt_s)
        self.overcurrent_flag = "OCP_DSG" in protection["protection_trip"]
        if not self.overcurrent_flag and not protection["protection_trip"]:
            self.bms.clear_latch()
        if protection["bms_latched"] and (report.get("infeasible")
                                          or self.pack.soc_pct <= 0.0):
            self.state = PowerState.ISOLATED
        self._log_transition(t_s, previous_state,
                             "mains_loss" if not self.mains_present else "recovery")

        self.row = {
            "site_id": self.site_id,
            "power_state_start": previous_state,
            "power_state_end": self.state,
            "mains_present": self.mains_present,
            "on_battery": on_battery,
            "load_w": retained_w,
            "unshed_load_w": sum(group_loads.values()),
            "autonomy_min": autonomy,
            "isolated": self.state == PowerState.ISOLATED,
            **{k: v for k, v in report.items() if k != "mode"},
            "charge_state": report["mode"],
            **protection,
            **shed_row,
            **self.ats.request(self.ats.source, t_s),
            **eco,
        }
        shared["power"] = self.row
        self.emit("power_state", {"state": self.state,
                                  "soc_pct": self.pack.soc_pct}, Phase.PROTECTION)

    def observe(self) -> dict[str, Any]:
        return self.row

    def health(self) -> FederateHealth:
        if self.state == PowerState.ISOLATED:
            return FederateHealth.failed(self.name, "battery isolated by protection")
        if self.row.get("shed_groups"):
            return FederateHealth.degraded(self.name, "load shedding active")
        return FederateHealth.ok(self.name)

    def checkpoint(self) -> dict[str, Any]:
        return {"name": self.name, "state": self.state, "soc_pct": self.pack.soc_pct,
                "temp_c": self.pack.temp_c, "transitions": list(self.transition_log)}
