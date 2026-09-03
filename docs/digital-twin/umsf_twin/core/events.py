"""Scenario event objects shared by the compiler and every federate.

An event is a *declared intent* with an interval, a target set and typed
parameters. Its intensity profile is explicit so that ramped injections are
reproducible instead of hidden inside a federate.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .errors import ConfigError
from .safety import SafetyPolicy

__all__ = ["ScenarioEvent", "EVENT_PARAM_DEFAULTS", "materialize_params"]

#: Every event type materialises its full parameter set before hashing, so a
#: default change is visible in the config hash instead of silently altering
#: previously recorded runs.
EVENT_PARAM_DEFAULTS: dict[str, dict[str, Any]] = {
    "wan_down": {"link_id": None},
    "wan_degrade": {"link_id": None, "capacity_factor": 0.5,
                    "latency_add_ms": 20.0, "loss_add_pct": 1.0},
    "vpn_degrade": {"latency_add_ms": 0.0, "loss_add_pct": 0.0, "rekey": False},
    "wifi_auth_burst": {"add_failures_per_step": 25, "ap_fraction": 0.25},
    "rogue_ap_signal": {"rogue_count": 1, "rssi_dbm": -58.0},
    "recon_burst": {"scan_rate_pps": 20.0, "unique_ports": 120},
    "lateral_sequence": {"events_per_step": 1, "hops": 3},
    "low_rate_c2": {"period_s": 30, "bytes_per_beacon": 512},
    "traffic_burst": {"add_mbps": 0.0, "compute_add_w": 0.0},
    "mains_loss": {},
    "telemetry_loss": {"mode": "gap"},
    "cell_imbalance": {"cell_index": 6, "delta_mv": 0.0},
    "model_drift": {"load_factor": 1.25, "rssi_shift_db": -4.0},
    "ap_down": {"ap_ids": [], "count": 1},
    "asset_fault": {"asset_ids": [], "fault": "DEGRADED"},
    "charge_start": {"power_w": 300.0},
    "clock_skew": {"offset_ms": 250.0, "drift_ppm": 0.0},
    "duplicate_storm": {"duplicate_pct": 5.0},
}

#: Ramp shapes available to every event.
_RAMPS = {"step", "linear", "exponential"}


def materialize_params(event_type: str, params: dict[str, Any]) -> dict[str, Any]:
    defaults = EVENT_PARAM_DEFAULTS.get(event_type)
    if defaults is None:
        raise ConfigError(f"no parameter contract for event type {event_type!r}")
    unknown = sorted(set(params) - set(defaults))
    if unknown:
        raise ConfigError(f"{event_type}: unknown parameters {unknown}")
    merged = dict(defaults)
    merged.update(params)
    return merged


@dataclass(frozen=True)
class ScenarioEvent:
    event_id: str
    event_type: str
    start_s: int
    end_s: int
    targets: tuple[str, ...]
    params: dict[str, Any] = field(default_factory=dict)
    ramp: str = "step"
    ramp_s: int = 0

    def __post_init__(self) -> None:
        if self.end_s <= self.start_s:
            raise ConfigError(f"{self.event_id}: end_s must exceed start_s")
        if self.ramp not in _RAMPS:
            raise ConfigError(f"{self.event_id}: unknown ramp {self.ramp!r}")
        if self.ramp_s < 0:
            raise ConfigError(f"{self.event_id}: ramp_s must be >= 0")

    # -- activation ------------------------------------------------------
    def active(self, t_s: float, target: str | None = None) -> bool:
        if not (self.start_s <= t_s < self.end_s):
            return False
        return target is None or target in self.targets or "all" in self.targets

    def intensity(self, t_s: float) -> float:
        """Fraction of the nominal effect in force at ``t_s`` (0..1)."""

        if not self.active(t_s):
            return 0.0
        if self.ramp == "step" or self.ramp_s == 0:
            return 1.0
        progress = min(1.0, (t_s - self.start_s) / float(self.ramp_s))
        if self.ramp == "linear":
            return progress
        return 1.0 - pow(2.718281828459045, -3.0 * progress)

    def scaled(self, key: str, t_s: float, default: float = 0.0) -> float:
        """Parameter value multiplied by the current ramp intensity."""

        value = self.params.get(key, default)
        if value is None:
            return 0.0
        return float(value) * self.intensity(t_s)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "type": self.event_type,
            "start_s": self.start_s,
            "end_s": self.end_s,
            "targets": list(self.targets),
            "params": dict(self.params),
            "ramp": self.ramp,
            "ramp_s": self.ramp_s,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any], duration_s: int,
                  policy: SafetyPolicy | None = None) -> "ScenarioEvent":
        try:
            event_type = str(raw["type"])
            event_id = str(raw["event_id"])
            start_s = int(raw["start_s"])
            end_s = int(raw["end_s"])
        except KeyError as exc:
            raise ConfigError(f"event missing required field: {exc}") from exc
        if policy is not None:
            policy.check_event_type(event_type)
        if not 0 <= start_s < duration_s:
            raise ConfigError(f"{event_id}: start_s outside the run window")
        if end_s > duration_s:
            raise ConfigError(f"{event_id}: end_s beyond the run window")
        targets = tuple(str(t) for t in raw.get("targets", ["all"]))
        return cls(
            event_id=event_id,
            event_type=event_type,
            start_s=start_s,
            end_s=end_s,
            targets=targets,
            params=materialize_params(event_type, dict(raw.get("params", {}))),
            ramp=str(raw.get("ramp", "step")),
            ramp_s=int(raw.get("ramp_s", 0)),
        )


class EventIndex:
    """Interval index so per-step lookup does not rescan every event."""

    def __init__(self, events: list[ScenarioEvent]) -> None:
        self.events = list(events)

    def active(self, t_s: float, target: str | None = None) -> list[ScenarioEvent]:
        return [event for event in self.events if event.active(t_s, target)]

    def first(self, t_s: float, event_type: str,
              target: str | None = None) -> ScenarioEvent | None:
        for event in self.events:
            if event.event_type == event_type and event.active(t_s, target):
                return event
        return None

    def any_active(self, t_s: float, event_type: str, target: str | None = None) -> bool:
        return self.first(t_s, event_type, target) is not None
