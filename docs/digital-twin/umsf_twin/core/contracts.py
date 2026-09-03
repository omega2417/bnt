"""Data contracts of specification section 10, enforced in code.

Each record type declares its fields, units and quality flags once; writers
and validators both import from here, so a schema change cannot silently
desynchronise the CSV writer from the gate that checks it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Iterable

from .errors import ContractError

__all__ = [
    "SCHEMA_VERSION", "QUALITY_FLAGS", "EVENT_ENVELOPE_FIELDS",
    "TELEMETRY_FIELDS", "GROUND_TRUTH_FIELDS", "ALERT_FIELDS",
    "make_envelope", "validate_record", "validate_strict_json",
]

SCHEMA_VERSION = "2.0.0"

#: Quality vocabulary attached to every telemetry record.
QUALITY_FLAGS = (
    "OK", "SYNTHETIC", "ASSUMED_PARAMETER", "UNKNOWN_UPLINK", "IMPUTED",
    "OUT_OF_ORDER", "DUPLICATE", "STALE", "GAP", "SCHEMA_MISMATCH",
    "CLOCK_SUSPECT", "SATURATED",
)

EVENT_ENVELOPE_FIELDS = (
    "event_id", "schema_version", "experiment_id", "run_id", "replicate_id",
    "mode", "site_id", "source_id", "event_time_utc", "observed_time_utc",
    "ingest_time_utc", "phase", "kind", "evidence_class", "quality_flags",
)

TELEMETRY_FIELDS = (
    # identity and time
    "run_id", "replicate_id", "step", "timestamp_utc", "interval_end_utc",
    "observed_time_utc", "ingest_time_utc", "site_id", "mode", "evidence_class",
    # network
    "active_wan_id", "wan_state", "wan_capacity_mbps", "offered_load_mbps",
    "throughput_mbps", "queue_delay_ms", "rtt_ms", "jitter_ms", "loss_pct",
    "failover_active", "vpn_state", "vpn_latency_ms", "vpn_loss_pct",
    # wifi
    "ap_total", "ap_online", "wifi_clients", "mean_rssi_dbm", "channel_util_pct",
    "retry_pct", "auth_failures", "roaming_events", "rogue_ap_count",
    # assets and workload
    "assets_ready", "assets_degraded", "flows_per_s", "scan_rate_pps",
    "lateral_events", "c2_beacons",
    # power (site A only, empty elsewhere)
    "power_state_start", "power_state_end", "mains_present", "ats_transitions",
    "soc_pct", "soh_pct", "pack_ocv_v", "pack_voltage_v", "pack_current_a",
    "cell_ocv_min_v", "cell_ocv_max_v", "cell_min_v", "cell_max_v",
    "cell_imbalance_mv", "battery_temp_c", "load_w", "shed_groups",
    "autonomy_min", "protection_trip", "charge_state",
    # detection
    "detector_score", "detector_alert", "alert_latency_s",
    # quality
    "quality_flags", "telemetry_gap_marker",
)

GROUND_TRUTH_FIELDS = (
    "run_id", "replicate_id", "truth_id", "kind", "cause", "site_id", "target",
    "stage", "intensity", "onset_utc", "end_utc", "onset_step", "end_step",
    "expected_observable", "notes",
)

ALERT_FIELDS = (
    "run_id", "replicate_id", "alert_id", "step", "timestamp_utc", "site_id",
    "detector", "score", "threshold", "rule_hits", "explanation",
    "correlated_with", "recommended_action", "approval_required", "shadow_mode",
)


def make_envelope(**values: Any) -> dict[str, Any]:
    """Build a universal event envelope, filling absent fields with ``None``."""

    envelope = {name: values.get(name) for name in EVENT_ENVELOPE_FIELDS}
    envelope["schema_version"] = values.get("schema_version", SCHEMA_VERSION)
    flags = envelope.get("quality_flags") or ["SYNTHETIC"]
    unknown = [flag for flag in flags if flag not in QUALITY_FLAGS]
    if unknown:
        raise ContractError(f"unknown quality flags: {unknown}")
    envelope["quality_flags"] = "|".join(flags)
    return envelope


def validate_record(record: dict[str, Any], fields: Iterable[str],
                    label: str = "record") -> dict[str, Any]:
    """Check field membership and reject non-finite numbers."""

    fields = tuple(fields)
    extra = sorted(set(record) - set(fields))
    if extra:
        raise ContractError(f"{label} has unexpected fields: {extra}")
    missing = sorted(set(fields) - set(record))
    if missing:
        raise ContractError(f"{label} is missing fields: {missing}")
    for key, value in record.items():
        if isinstance(value, float) and not math.isfinite(value):
            raise ContractError(f"{label}.{key} is not finite: {value}")
    return record


def validate_strict_json(value: Any, path: str = "$") -> None:
    """Reject NaN/Infinity and non-string keys before anything is written."""

    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ContractError(f"{path}: non-string key {key!r}")
            validate_strict_json(item, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            validate_strict_json(item, f"{path}[{index}]")
    elif isinstance(value, float):
        if not math.isfinite(value):
            raise ContractError(f"{path}: non-finite float {value}")
    elif not isinstance(value, (str, int, bool, type(None))):
        raise ContractError(f"{path}: unsupported type {type(value).__name__}")


@dataclass
class RecordBuilder:
    """Accumulates a telemetry row and blanks it out on a telemetry gap."""

    fields: tuple[str, ...] = TELEMETRY_FIELDS
    values: dict[str, Any] = field(default_factory=dict)

    def set(self, **values: Any) -> "RecordBuilder":
        unknown = sorted(set(values) - set(self.fields))
        if unknown:
            raise ContractError(f"unknown telemetry fields: {unknown}")
        self.values.update(values)
        return self

    def blank_measurements(self, keep: Iterable[str]) -> "RecordBuilder":
        keep = set(keep)
        for name in self.fields:
            if name not in keep:
                self.values[name] = ""
        return self

    def build(self) -> dict[str, Any]:
        row = {name: self.values.get(name, "") for name in self.fields}
        return validate_record(row, self.fields, "telemetry")
