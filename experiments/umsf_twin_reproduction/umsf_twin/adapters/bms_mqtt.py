"""BMS/ATS gateway adapter for MQTT payloads.

Read-only by construction: the adapter exposes no publish function, which is
the code-level expression of the rule that the twin never writes to a safety
device.
"""

from __future__ import annotations

import json
from typing import Any, Iterable

__all__ = ["parse_bms_payload", "parse_stream"]


def parse_bms_payload(payload: str | dict[str, Any]) -> dict[str, Any]:
    data = json.loads(payload) if isinstance(payload, str) else dict(payload)
    cells = [float(value) for value in data.get("cells_v", [])]
    return {
        "site_id": data.get("site_id", "site_a"),
        "soc_pct": float(data.get("soc", 0.0)),
        "soh_pct": float(data.get("soh", 0.0)),
        "pack_voltage_v": float(data.get("pack_v", 0.0)),
        "pack_current_a": float(data.get("pack_a", 0.0)),
        "battery_temp_c": float(data.get("temp_c", 0.0)),
        "cell_min_v": min(cells) if cells else "",
        "cell_max_v": max(cells) if cells else "",
        "cell_imbalance_mv": (max(cells) - min(cells)) * 1000.0 if cells else "",
        "protection_trip": "|".join(data.get("faults", [])),
        "charge_state": data.get("state", ""),
        "quality_flags": "OK" if cells else "SCHEMA_MISMATCH",
    }


def parse_stream(payloads: Iterable[str | dict[str, Any]]) -> list[dict[str, Any]]:
    return [parse_bms_payload(payload) for payload in payloads]
