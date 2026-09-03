"""Normalisation stage: one shape for simulated, emulated and replayed data.

REPLAY mode feeds real collector exports through exactly this function, which
is what makes a sim-to-real comparison an apples-to-apples one.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..core.contracts import TELEMETRY_FIELDS

__all__ = ["normalize_rows", "ALIASES"]

#: Vendor field name -> twin contract field name.
ALIASES = {
    "rtt": "rtt_ms", "latency_ms": "rtt_ms", "packet_loss": "loss_pct",
    "loss": "loss_pct", "tx_bps": "throughput_mbps", "clients": "wifi_clients",
    "rssi": "mean_rssi_dbm", "battery_soc": "soc_pct", "pack_v": "pack_voltage_v",
    "pack_i": "pack_current_a", "temp": "battery_temp_c",
}


def normalize_rows(rows: Iterable[dict[str, Any]], mode: str = "REPLAY",
                   evidence_class: str = "measured") -> list[dict[str, Any]]:
    output = []
    for raw in rows:
        row = {ALIASES.get(key, key): value for key, value in raw.items()}
        if "throughput_mbps" in row and "tx_bps" in raw:
            try:
                row["throughput_mbps"] = float(raw["tx_bps"]) / 1e6
            except (TypeError, ValueError):
                row["throughput_mbps"] = ""
        normalized = {name: row.get(name, "") for name in TELEMETRY_FIELDS}
        normalized["mode"] = mode
        normalized["evidence_class"] = evidence_class
        flags = str(normalized.get("quality_flags") or "").split("|")
        extra = [flag for flag in flags if flag] or ["OK"]
        unknown = sorted(set(row) - set(TELEMETRY_FIELDS))
        if unknown:
            extra.append("SCHEMA_MISMATCH")
        normalized["quality_flags"] = "|".join(dict.fromkeys(extra))
        output.append(normalized)
    return output
