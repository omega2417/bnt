"""Executable safety, dual-use and isolation policy (sections 19 and 25).

The policy is not documentation: the scenario compiler, the threat federate
and the orchestrator all consult it, and a violation raises rather than warns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .errors import SafetyViolation

__all__ = ["SafetyPolicy", "ALLOWED_EVENT_TYPES", "FORBIDDEN_CAPABILITIES"]

#: Synthetic event vocabulary. Anything outside this set is rejected at compile
#: time, which is what keeps the twin from expressing a real-world attack.
ALLOWED_EVENT_TYPES = frozenset({
    "wan_down", "wan_degrade", "vpn_degrade", "wifi_auth_burst", "rogue_ap_signal",
    "recon_burst", "lateral_sequence", "low_rate_c2", "traffic_burst", "mains_loss",
    "telemetry_loss", "cell_imbalance", "model_drift", "ap_down", "asset_fault",
    "charge_start", "clock_skew", "duplicate_storm",
})

#: Capabilities the twin must never acquire, in any mode.
FORBIDDEN_CAPABILITIES = frozenset({
    "external_egress", "real_credential_attack", "production_target",
    "safety_control_writeback", "raw_pcap_export", "user_identifier_export",
})


@dataclass
class SafetyPolicy:
    mode: str = "SIM"
    allow_external_egress: bool = False
    allow_hardware_writes: bool = False
    hil_approval_ref: str = ""
    max_duration_s: int = 7 * 24 * 3600
    max_events: int = 1000
    max_offered_load_mbps: float = 10_000.0
    max_injected_power_w: float = 2_000.0
    max_replicates: int = 1000
    allowed_event_types: frozenset[str] = field(default=ALLOWED_EVENT_TYPES)
    egress_allowlist: tuple[str, ...] = ()
    retention_days: int = 365

    # -- static guards ---------------------------------------------------
    def check_event_type(self, event_type: str) -> None:
        if event_type not in self.allowed_event_types:
            raise SafetyViolation(
                f"event type {event_type!r} is not in the synthetic allowlist"
            )

    def check_capability(self, capability: str) -> None:
        if capability in FORBIDDEN_CAPABILITIES:
            raise SafetyViolation(f"capability {capability!r} is forbidden in every mode")

    def check_mode(self) -> None:
        mode = self.mode.upper()
        if mode not in {"SIM", "EMU", "REPLAY", "HIL"}:
            raise SafetyViolation(f"unknown mode {self.mode!r}")
        if mode == "HIL" and not self.hil_approval_ref:
            raise SafetyViolation("HIL requires a signed approval reference")
        if mode in {"SIM", "REPLAY"} and self.allow_hardware_writes:
            raise SafetyViolation(f"{mode} must not enable hardware writes")
        if self.allow_external_egress and not self.egress_allowlist:
            raise SafetyViolation("egress enabled without an explicit allowlist")

    def check_budget(self, duration_s: int, event_count: int, replicates: int) -> None:
        if not 0 < duration_s <= self.max_duration_s:
            raise SafetyViolation(f"duration {duration_s}s outside 1..{self.max_duration_s}s")
        if event_count > self.max_events:
            raise SafetyViolation(f"{event_count} events exceed cap {self.max_events}")
        if not 0 < replicates <= self.max_replicates:
            raise SafetyViolation(f"replicates {replicates} outside 1..{self.max_replicates}")

    def clamp_load(self, mbps: float) -> float:
        return max(0.0, min(float(mbps), self.max_offered_load_mbps))

    def clamp_power(self, watts: float) -> float:
        return max(0.0, min(float(watts), self.max_injected_power_w))

    def assert_no_sockets(self, opened: Iterable[str]) -> None:
        """SIM must stay hermetic; the runner passes what it actually opened."""

        opened = list(opened)
        if self.mode.upper() == "SIM" and opened:
            raise SafetyViolation(f"SIM opened network endpoints: {opened}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "allow_external_egress": self.allow_external_egress,
            "allow_hardware_writes": self.allow_hardware_writes,
            "hil_approval_ref": self.hil_approval_ref or None,
            "max_duration_s": self.max_duration_s,
            "max_events": self.max_events,
            "max_offered_load_mbps": self.max_offered_load_mbps,
            "max_injected_power_w": self.max_injected_power_w,
            "allowed_event_types": sorted(self.allowed_event_types),
            "egress_allowlist": list(self.egress_allowlist),
            "retention_days": self.retention_days,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SafetyPolicy":
        known = {f for f in cls.__dataclass_fields__}  # type: ignore[attr-defined]
        payload = {k: v for k, v in data.items() if k in known}
        if "allowed_event_types" in payload:
            payload["allowed_event_types"] = frozenset(payload["allowed_event_types"])
        if "egress_allowlist" in payload:
            payload["egress_allowlist"] = tuple(payload["egress_allowlist"])
        return cls(**payload)
