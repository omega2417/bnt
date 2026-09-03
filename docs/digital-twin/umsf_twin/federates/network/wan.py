"""One programmable object per physical WAN link (section 9.2).

The demo inventory instantiates five links at site A and two at site B. Each
carries its own health-probe counters, hold-down timer, loss process and
common-cause group, so correlated upstream failures can be modelled instead of
assumed independent.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from .loss import GilbertElliott

__all__ = ["WanLink", "WanState"]


class WanState:
    UP = "UP"
    DEGRADED = "DEGRADED"
    DOWN = "DOWN"
    RECOVERING = "RECOVERING"


@dataclass
class WanLink:
    link_id: str
    capacity_mbps: float
    base_rtt_ms: float
    base_loss_pct: float
    priority: int
    site_id: str = ""
    common_cause_group: str = ""
    probe_interval_s: int = 1
    fail_threshold: int = 3
    recover_threshold: int = 5
    hold_down_s: int = 10
    jitter_sd_ms: float = 1.5
    state: str = WanState.UP
    consecutive_fail: int = 0
    consecutive_ok: int = 0
    hold_until_s: float = -1.0
    capacity_factor: float = 1.0
    latency_add_ms: float = 0.0
    loss_add_pct: float = 0.0
    forced_down: bool = False
    loss_model: GilbertElliott = field(default_factory=GilbertElliott)
    transitions: int = 0

    def __post_init__(self) -> None:
        self.loss_model.good_loss_pct = self.base_loss_pct

    # -- external influences --------------------------------------------
    def apply_scenario(self, *, down: bool = False, capacity_factor: float = 1.0,
                       latency_add_ms: float = 0.0, loss_add_pct: float = 0.0) -> None:
        self.forced_down = down
        self.capacity_factor = max(0.01, min(1.0, capacity_factor))
        self.latency_add_ms = max(0.0, latency_add_ms)
        self.loss_add_pct = max(0.0, loss_add_pct)

    def apply_common_cause(self, failed_groups: set[str]) -> None:
        if self.common_cause_group and self.common_cause_group in failed_groups:
            self.forced_down = True

    # -- state machine ---------------------------------------------------
    def step(self, t_s: float, rng: random.Random, utilization: float = 0.0) -> dict[str, Any]:
        healthy = not self.forced_down
        if healthy:
            self.consecutive_ok += 1
            self.consecutive_fail = 0
        else:
            self.consecutive_fail += 1
            self.consecutive_ok = 0

        previous = self.state
        if self.consecutive_fail >= self.fail_threshold:
            self.state = WanState.DOWN
            self.hold_until_s = t_s + self.hold_down_s
        elif self.state == WanState.DOWN and healthy:
            self.state = WanState.RECOVERING
        elif self.state == WanState.RECOVERING:
            if self.consecutive_ok >= self.recover_threshold and t_s >= self.hold_until_s:
                self.state = WanState.UP
        elif self.capacity_factor < 1.0 or self.latency_add_ms > 0.0:
            self.state = WanState.DEGRADED
        elif healthy:
            self.state = WanState.UP
        if self.state != previous:
            self.transitions += 1

        stress = max(0.0, min(1.0, utilization)) + (0.5 if self.state == WanState.DEGRADED else 0.0)
        loss_pct = self.loss_model.step(rng, min(1.0, stress)) + self.loss_add_pct
        jitter_ms = abs(rng.gauss(0.0, self.jitter_sd_ms)) * (1.0 + 2.0 * min(1.0, stress))
        return {
            "link_id": self.link_id,
            "state": self.state,
            "effective_capacity_mbps": self.effective_capacity,
            "rtt_ms": self.base_rtt_ms + self.latency_add_ms,
            "jitter_ms": jitter_ms,
            "loss_pct": loss_pct,
            "usable": self.usable,
            "transitions": self.transitions,
        }

    @property
    def effective_capacity(self) -> float:
        if self.state == WanState.DOWN:
            return 0.0
        return self.capacity_mbps * self.capacity_factor

    @property
    def usable(self) -> bool:
        return self.state in (WanState.UP, WanState.DEGRADED, WanState.RECOVERING) \
            and self.effective_capacity > 0.0

    def reset(self) -> None:
        self.state = WanState.UP
        self.consecutive_fail = self.consecutive_ok = self.transitions = 0
        self.hold_until_s = -1.0
        self.capacity_factor, self.latency_add_ms, self.loss_add_pct = 1.0, 0.0, 0.0
        self.forced_down = False
        self.loss_model.reset()

    @classmethod
    def from_config(cls, raw: dict[str, Any], site_id: str) -> "WanLink":
        return cls(
            link_id=str(raw["id"]),
            capacity_mbps=float(raw["capacity_mbps"]),
            base_rtt_ms=float(raw["base_rtt_ms"]),
            base_loss_pct=float(raw["base_loss_pct"]),
            priority=int(raw["priority"]),
            site_id=site_id,
            common_cause_group=str(raw.get("common_cause_group", "")),
            hold_down_s=int(raw.get("hold_down_s", 10)),
            fail_threshold=int(raw.get("fail_threshold", 3)),
            recover_threshold=int(raw.get("recover_threshold", 5)),
        )
