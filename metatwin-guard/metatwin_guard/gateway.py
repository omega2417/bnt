"""Integrity admission gateway, Equation (1).

g(e) = C_schema AND C_hash AND C_signature AND C_id AND C_sequence AND C_chain
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import config
from .crypto import GENESIS_HASH, canonical_json, verify_hex
from .events import REQUIRED_FIELDS, event_hash, parse_ts, payload_hash, signed_body

CHECKS = ("schema", "hash", "signature", "id", "sequence", "chain")


@dataclass
class Admission:
    admitted: bool
    checks: dict[str, bool]
    reasons: list[str]


@dataclass
class IntegrityGateway:
    registry: dict[str, Ed25519PublicKey]
    accepted_ids: set[str] = field(default_factory=set)
    last_seq: dict[str, int] = field(default_factory=dict)
    last_hash: dict[str, str] = field(default_factory=dict)

    def _schema_ok(self, ev: Any) -> tuple[bool, str]:
        if not isinstance(ev, dict):
            return False, "schema:not_an_object"
        for name, typ in REQUIRED_FIELDS.items():
            if name not in ev:
                return False, f"schema:missing_{name}"
            if typ is int and isinstance(ev[name], bool):
                return False, f"schema:type_{name}"
            if not isinstance(ev[name], typ):
                return False, f"schema:type_{name}"
        if ev["schema_version"] != config.SCHEMA_VERSION:
            return False, "schema:version"
        feats = ev["features"]
        if set(feats) != set(config.FEATURES):
            return False, "schema:feature_set"
        for k in config.FEATURES:
            v = feats[k]
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return False, f"schema:feature_{k}"
            try:
                if not math.isfinite(float(v)):
                    return False, f"schema:feature_{k}"
            except OverflowError:
                return False, f"schema:feature_{k}"
        try:
            parse_ts(ev["event_time_utc"])
            parse_ts(ev["ingest_time_utc"])
        except ValueError:
            return False, "schema:timestamp"
        return True, ""

    def check(self, ev: Any) -> Admission:
        """Evaluates all checks without changing gateway state."""
        checks = dict.fromkeys(CHECKS, False)
        reasons: list[str] = []
        ok, why = self._schema_ok(ev)
        checks["schema"] = ok
        if not ok:
            reasons.append(why)
            return Admission(False, checks, reasons)

        checks["hash"] = payload_hash(ev["features"]) == ev["payload_hash"]
        if not checks["hash"]:
            reasons.append("payload_hash_mismatch")

        pub = self.registry.get(ev["sensor_id"])
        if pub is None:
            reasons.append("unknown_sensor_key")
        else:
            checks["signature"] = verify_hex(pub, ev["signature"], canonical_json(signed_body(ev)))
            if not checks["signature"]:
                reasons.append("signature_invalid")

        checks["id"] = ev["event_id"] not in self.accepted_ids
        if not checks["id"]:
            reasons.append("duplicate_event_id")

        src = ev["sensor_id"]
        checks["sequence"] = ev["source_seq"] > self.last_seq.get(src, 0)
        if not checks["sequence"]:
            reasons.append("non_increasing_sequence")

        checks["chain"] = ev["previous_hash"] == self.last_hash.get(src, GENESIS_HASH)
        if not checks["chain"]:
            reasons.append("previous_hash_mismatch")

        return Admission(all(checks.values()), checks, reasons)

    def admit(self, ev: Any) -> Admission:
        """Checks the event and, only if admitted, records it as accepted."""
        res = self.check(ev)
        if res.admitted:
            src = ev["sensor_id"]
            self.accepted_ids.add(ev["event_id"])
            self.last_seq[src] = ev["source_seq"]
            self.last_hash[src] = event_hash(ev)
        return res
