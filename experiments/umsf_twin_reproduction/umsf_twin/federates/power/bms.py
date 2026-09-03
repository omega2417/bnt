"""Battery management protections and balancing.

Trip thresholds are *not* tuned to make a scenario succeed: they are inputs
with their own evidence status. Until a datasheet exists they carry
``SYNTHETIC_DEMO_ONLY_UNVERIFIED`` and any trip they cause is reported as a
model artefact rather than a physical limit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["BmsLimits", "BatteryManagementSystem", "TRIP_CODES"]

TRIP_CODES = ("COV", "CUV", "OCP_CHG", "OCP_DSG", "OTP", "UTP", "SCD", "INFEASIBLE")


@dataclass
class BmsLimits:
    cell_over_voltage_v: float = 4.25
    cell_under_voltage_v: float = 2.50
    pack_min_terminal_v: float = 37.0
    charge_current_limit_a: float = 4.0
    discharge_current_limit_a: float = 15.0
    over_temp_c: float = 55.0
    under_temp_charge_c: float = 0.0
    short_circuit_a: float = 60.0
    balance_threshold_mv: float = 50.0
    balance_current_ma: float = 80.0
    #: Numerical tolerance so a current solved exactly at the limit does not
    #: trip on floating point noise. It is not a safety margin.
    current_tolerance_a: float = 1e-6
    evidence_status: str = "SYNTHETIC_DEMO_ONLY_UNVERIFIED"


@dataclass
class BatteryManagementSystem:
    limits: BmsLimits = field(default_factory=BmsLimits)
    latched: bool = False
    trips: list[str] = field(default_factory=list)
    trip_count: int = 0
    balancing: bool = False
    imbalance_over_threshold_s: float = 0.0

    def evaluate(self, report: dict[str, Any], dt_s: float) -> dict[str, Any]:
        """Check one pack report against the limits and update the latch."""

        active: list[str] = []
        limits = self.limits
        current = report["pack_current_a"]

        if report["cell_max_v"] > limits.cell_over_voltage_v:
            active.append("COV")
        if report["cell_min_v"] < limits.cell_under_voltage_v:
            active.append("CUV")
        if report["pack_voltage_v"] < limits.pack_min_terminal_v and current > 0:
            active.append("CUV")
        if current > limits.discharge_current_limit_a + limits.current_tolerance_a:
            active.append("OCP_DSG")
        if -current > limits.charge_current_limit_a + limits.current_tolerance_a:
            active.append("OCP_CHG")
        if abs(current) > limits.short_circuit_a:
            active.append("SCD")
        if report["battery_temp_c"] > limits.over_temp_c:
            active.append("OTP")
        if current < 0 and report["battery_temp_c"] < limits.under_temp_charge_c:
            active.append("UTP")
        if report.get("infeasible"):
            active.append("INFEASIBLE")

        if report["cell_imbalance_mv"] > limits.balance_threshold_mv:
            self.imbalance_over_threshold_s += dt_s
            self.balancing = True
        else:
            self.imbalance_over_threshold_s = 0.0
            self.balancing = False

        if active and not self.latched:
            self.latched = True
            self.trip_count += 1
        self.trips = active
        return {
            "protection_trip": "|".join(active),
            "bms_latched": self.latched,
            "bms_trip_count": self.trip_count,
            "balancing": self.balancing,
            "imbalance_over_threshold_s": self.imbalance_over_threshold_s,
            "imbalance_critical": report["cell_imbalance_mv"] > 100.0,
            "limits_evidence": limits.evidence_status,
        }

    def clear_latch(self) -> None:
        self.latched = False
        self.trips = []
