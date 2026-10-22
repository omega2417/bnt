"""Signed telemetry envelope and software sensor (Section 3.4)."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from . import config
from .crypto import GENESIS_HASH, canonical_json, hash_obj, sign_hex

# Fields covered by the source signature. ingest_time_utc is assigned on
# receipt and payload_hash binds the feature map.
SIGNED_FIELDS = (
    "event_id",
    "scenario_id",
    "phase",
    "site_id",
    "sensor_id",
    "source_seq",
    "event_time_utc",
    "topology_node",
    "schema_version",
    "payload_hash",
    "previous_hash",
)
REQUIRED_FIELDS = {
    "event_id": str,
    "scenario_id": str,
    "phase": str,
    "site_id": str,
    "sensor_id": str,
    "source_seq": int,
    "event_time_utc": str,
    "ingest_time_utc": str,
    "topology_node": str,
    "schema_version": str,
    "features": dict,
    "payload_hash": str,
    "previous_hash": str,
    "signature": str,
}

_TS_FMT = "%Y-%m-%dT%H:%M:%S.%fZ"


def format_ts(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime(_TS_FMT)


def parse_ts(s: str) -> datetime:
    return datetime.strptime(s, _TS_FMT).replace(tzinfo=timezone.utc)


def payload_hash(features: dict[str, float]) -> str:
    return hash_obj({"features": features})


def signed_body(event: dict[str, Any]) -> dict[str, Any]:
    return {k: event[k] for k in SIGNED_FIELDS}


def event_hash(event: dict[str, Any]) -> str:
    """Hash that the next event of the same source must quote as previous_hash."""
    return hash_obj(signed_body(event))


@dataclass
class SoftwareSensor:
    """Creates canonical, signed, per-source hash-chained events."""

    sensor_id: str
    site_id: str
    topology_node: str
    private_key: Ed25519PrivateKey
    seq: int = 0
    last_hash: str = GENESIS_HASH
    _counter: int = field(default=0, repr=False)

    def emit(
        self,
        features: dict[str, float],
        event_time: datetime,
        ingest_delay_ms: float,
        scenario_id: str,
        phase: str,
    ) -> dict[str, Any]:
        self.seq += 1
        feats = {k: round(float(features[k]), 4) for k in config.FEATURES}
        event: dict[str, Any] = {
            "event_id": f"{scenario_id}:{self.sensor_id}:{self.seq:06d}",
            "scenario_id": scenario_id,
            "phase": phase,
            "site_id": self.site_id,
            "sensor_id": self.sensor_id,
            "source_seq": self.seq,
            "event_time_utc": format_ts(event_time),
            "ingest_time_utc": format_ts(event_time + timedelta(milliseconds=ingest_delay_ms)),
            "topology_node": self.topology_node,
            "schema_version": config.SCHEMA_VERSION,
            "features": feats,
            "payload_hash": payload_hash(feats),
            "previous_hash": self.last_hash,
        }
        event["signature"] = sign_hex(self.private_key, canonical_json(signed_body(event)))
        self.last_hash = event_hash(event)
        return event


def tamper_features(event: dict[str, Any], changes: dict[str, float], fix_payload_hash: bool) -> dict[str, Any]:
    """Post-signature modification by an on-path adversary without the key.

    With fix_payload_hash=False the payload hash no longer matches; with True
    the adversary recomputes it, so the Ed25519 signature check fails instead.
    """
    ev = copy.deepcopy(event)
    ev["features"].update({k: round(float(v), 4) for k, v in changes.items()})
    if fix_payload_hash:
        ev["payload_hash"] = payload_hash(ev["features"])
    return ev
