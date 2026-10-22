"""MetaTwin-Guard assurance pipeline (Figure 2).

event -> integrity gateway -> static rules + robust score -> hybrid decision
      -> twin-state update (admitted events only) -> evidence block
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from . import config
from .crypto import hash_obj, sha256_hex
from .detector import RobustDetector, StaticRules, hybrid_decision
from .events import parse_ts
from .gateway import IntegrityGateway
from .ledger import QuorumEvidenceLedger
from .twin import TwinState


def received_hash(event: Any) -> str:
    """Hash of the envelope as received; malformed input is hashed by repr."""
    try:
        return hash_obj(event)
    except (TypeError, ValueError):
        return sha256_hex(repr(event).encode("utf-8"))


@dataclass
class MetaTwinGuard:
    registry: dict[str, Ed25519PublicKey]
    seed: int = config.MASTER_SEED
    detector: RobustDetector = field(default_factory=RobustDetector)
    rules: StaticRules = field(default_factory=StaticRules)

    def __post_init__(self) -> None:
        self.gateway = IntegrityGateway(dict(self.registry))
        self.twin = TwinState()
        self.ledger = QuorumEvidenceLedger(seed=self.seed)
        self._baseline: list[dict[str, float]] = []
        self.fitted = False

    def fit_baseline(self, rows: Iterable[dict[str, float]] | None = None) -> RobustDetector:
        """Fits median/MAD from the admitted baseline-phase events (or given rows)."""
        self.detector.fit(rows if rows is not None else self._baseline)
        self.fitted = True
        return self.detector

    def process(self, event: dict[str, Any]) -> dict[str, Any]:
        adm = self.gateway.admit(event)
        feats = event.get("features", {}) if isinstance(event, dict) else {}
        evaluable = adm.checks["schema"]

        rules_fired = self.rules.fired(feats) if evaluable else []
        rule_alert = bool(rules_fired)
        robust = self.detector.evaluate(feats) if (self.fitted and evaluable) else None
        robust_alert = bool(robust and robust.flagged)
        hybrid = hybrid_decision(rule_alert, robust_alert, adm.admitted)

        changed = self.twin.apply(event, adm.admitted)
        if adm.admitted and not self.fitted and event.get("phase") == "baseline":
            self._baseline.append(dict(feats))

        sync_ms = None
        if adm.admitted:
            sync_ms = (parse_ts(event["ingest_time_utc"]) - parse_ts(event["event_time_utc"])).total_seconds() * 1000.0

        top = [[f, round(c, 6)] for f, c in robust.top] if robust else []
        block = self.ledger.append(
            {
                "event_id": event.get("event_id") if isinstance(event, dict) else None,
                "event_payload_hash": received_hash(event),
                "integrity_admitted": adm.admitted,
                "integrity_reasons": adm.reasons,
                "rules_fired": rules_fired,
                "anomaly_score": round(robust.score, 6) if robust else None,
                "hybrid_alert": hybrid,
                "top_contributions": top,
                "twin_state_hash": self.twin.state_hash(),
            }
        )
        return {
            "event_id": event.get("event_id") if isinstance(event, dict) else None,
            "sensor_id": event.get("sensor_id") if isinstance(event, dict) else None,
            "topology_node": event.get("topology_node") if isinstance(event, dict) else None,
            "phase": event.get("phase") if isinstance(event, dict) else None,
            "admitted": adm.admitted,
            "reasons": adm.reasons,
            "rules_fired": rules_fired,
            "rule_alert": rule_alert,
            "robust_score": robust.score if robust else None,
            "robust_alert": robust_alert,
            "hybrid_alert": hybrid,
            "top_contributions": top,
            "state_changed": changed,
            "state_hash": self.twin.state_hash(),
            "sync_latency_ms": sync_ms,
            "append_ms": self.ledger.append_times_ms[-1],
            "block_index": block["body"]["index"],
        }
