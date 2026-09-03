"""OpenTelemetry-style export of twin observations.

Emits metric points as plain dictionaries. Whether they are ever shipped
anywhere is a deployment decision governed by the egress policy, not by this
module.
"""

from __future__ import annotations

from typing import Any, Iterable

__all__ = ["to_metric_points"]

_UNITS = {"rtt_ms": "ms", "loss_pct": "%", "throughput_mbps": "Mbit/s",
          "soc_pct": "%", "battery_temp_c": "Cel", "pack_voltage_v": "V",
          "pack_current_a": "A", "wifi_clients": "{client}"}


def to_metric_points(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    points = []
    for row in rows:
        for name, unit in _UNITS.items():
            value = row.get(name, "")
            if value in ("", None):
                continue
            points.append({
                "name": f"umsf.twin.{name}",
                "unit": unit,
                "value": float(value),
                "time_unix_nano": None,
                "timestamp_utc": row.get("timestamp_utc"),
                "attributes": {"site_id": row.get("site_id"),
                               "run_id": row.get("run_id"),
                               "mode": row.get("mode"),
                               "evidence_class": row.get("evidence_class")},
            })
    return points
