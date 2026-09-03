"""Keenetic router export adapter (WAN interface statistics)."""

from __future__ import annotations

from typing import Any, Iterable

__all__ = ["parse_wan_stats"]

_STATE_MAP = {"up": "UP", "connected": "UP", "degraded": "DEGRADED",
              "down": "DOWN", "disconnected": "DOWN"}


def parse_wan_stats(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for record in records:
        output.append({
            "link_id": record.get("interface") or record.get("id"),
            "site_id": record.get("site_id", "site_a"),
            "wan_state": _STATE_MAP.get(str(record.get("state", "")).lower(), "DOWN"),
            "wan_capacity_mbps": float(record.get("speed_mbps", 0.0)),
            "rtt_ms": float(record.get("ping_ms", 0.0)) or "",
            "loss_pct": float(record.get("loss_pct", 0.0)),
            "priority": int(record.get("priority", 99)),
        })
    return output
