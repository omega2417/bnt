"""Topology-aware twin state with the admission invariant, Equation (2).

T_i = U(T_{i-1}, e_i) if g(e_i) = 1, otherwise T_{i-1}.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from . import config
from .crypto import hash_obj
from .events import parse_ts


@dataclass
class TwinState:
    nodes: dict[str, dict[str, Any]] = field(default_factory=dict)
    version: int = 0

    def state_hash(self) -> str:
        return hash_obj({"version": self.version, "nodes": self.nodes})

    def apply(self, event: dict[str, Any], admitted: bool) -> bool:
        """Deterministic update U. Returns True if the state changed."""
        if not admitted:
            return False
        self.nodes[event["topology_node"]] = {
            "site_id": event["site_id"],
            "sensor_id": event["sensor_id"],
            "source_seq": event["source_seq"],
            "event_id": event["event_id"],
            "event_time_utc": event["event_time_utc"],
            "ingest_time_utc": event["ingest_time_utc"],
            "features": dict(event["features"]),
        }
        self.version += 1
        return True

    def staleness_s(self, node: str, now: datetime) -> float | None:
        if node not in self.nodes:
            return None
        return (now - parse_ts(self.nodes[node]["event_time_utc"])).total_seconds()

    def freshness(
        self,
        node: str,
        now: datetime,
        tau_fresh: float = config.TAU_FRESH_S,
        tau_lost: float = config.TAU_LOST_S,
    ) -> str:
        """current (Δ ≤ τ_fresh), stale (τ_fresh < Δ ≤ τ_lost) or unknown (Δ > τ_lost / never seen)."""
        d = self.staleness_s(node, now)
        if d is None or d > tau_lost:
            return "unknown"
        return "current" if d <= tau_fresh else "stale"
