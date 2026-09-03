"""Asset lifecycle state machine (section 6.4).

Every managed node - router, switch, controller, log server, monitoring
gateway, training workstation, Kali workstation - is one instance of this
class. Power group membership (I, II, III) is what couples an asset to the
load-shedding logic of the power federate.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

__all__ = ["Asset", "AssetState", "POWER_GROUP_NAMES"]

POWER_GROUP_NAMES = {1: "I-critical", 2: "II-important", 3: "III-auxiliary"}


class AssetState:
    OFF = "OFF"
    BOOTING = "BOOTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    SHUTTING_DOWN = "SHUTTING_DOWN"
    FAILED = "FAILED"


@dataclass
class Asset:
    asset_id: str
    site_id: str
    role: str                        # router | switch | controller | server | workstation
    power_group: int = 3
    idle_power_w: float = 12.0
    active_power_w: float = 35.0
    boot_time_s: float = 45.0
    shutdown_time_s: float = 15.0
    state: str = AssetState.READY
    timer_s: float = 0.0
    utilization: float = 0.2
    fault_latched: bool = False
    restarts: int = 0

    # -- commands --------------------------------------------------------
    def power_off(self) -> None:
        if self.state not in (AssetState.OFF, AssetState.SHUTTING_DOWN):
            self.state = AssetState.SHUTTING_DOWN
            self.timer_s = self.shutdown_time_s

    def power_on(self) -> None:
        if self.state == AssetState.OFF and not self.fault_latched:
            self.state = AssetState.BOOTING
            self.timer_s = self.boot_time_s
            self.restarts += 1

    def inject_fault(self, kind: str = "DEGRADED") -> None:
        if kind == "FAILED":
            self.state = AssetState.FAILED
            self.fault_latched = True
        else:
            self.state = AssetState.DEGRADED

    def clear_fault(self) -> None:
        self.fault_latched = False
        if self.state in (AssetState.DEGRADED, AssetState.FAILED):
            self.state = AssetState.BOOTING
            self.timer_s = self.boot_time_s

    # -- integration -----------------------------------------------------
    def step(self, dt_s: float, rng: random.Random, *, powered: bool,
             load_factor: float = 1.0) -> dict[str, Any]:
        if not powered:
            self.power_off()
        elif self.state == AssetState.OFF:
            self.power_on()

        if self.state in (AssetState.BOOTING, AssetState.SHUTTING_DOWN):
            self.timer_s = max(0.0, self.timer_s - dt_s)
            if self.timer_s == 0.0:
                self.state = (AssetState.READY if self.state == AssetState.BOOTING
                              else AssetState.OFF)

        if self.state == AssetState.READY:
            self.utilization = max(0.02, min(1.0, 0.2 * load_factor
                                             + abs(rng.gauss(0.0, 0.05))))
        elif self.state == AssetState.DEGRADED:
            self.utilization = max(0.02, min(1.0, 0.5 * load_factor))
        else:
            self.utilization = 0.0

        return {
            "asset_id": self.asset_id,
            "site_id": self.site_id,
            "role": self.role,
            "state": self.state,
            "power_group": self.power_group,
            "power_w": self.power_draw_w,
            "utilization": self.utilization,
            "ready": self.state == AssetState.READY,
        }

    @property
    def power_draw_w(self) -> float:
        if self.state in (AssetState.OFF, AssetState.FAILED):
            return 0.0
        if self.state in (AssetState.BOOTING, AssetState.SHUTTING_DOWN):
            return self.active_power_w * 0.8
        return self.idle_power_w + (self.active_power_w - self.idle_power_w) * self.utilization
