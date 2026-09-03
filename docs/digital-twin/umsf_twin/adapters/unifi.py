"""UniFi controller export adapter (AP statistics)."""

from __future__ import annotations

from typing import Any, Iterable

__all__ = ["parse_ap_stats"]


def parse_ap_stats(records: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Map controller AP records onto the twin's Wi-Fi fields."""

    output = []
    for record in records:
        output.append({
            "ap_id": record.get("name") or record.get("mac"),
            "site_id": record.get("site_id", "site_a"),
            "wifi_clients": int(record.get("num_sta", 0)),
            "mean_rssi_dbm": float(record.get("avg_client_signal", -70)),
            "channel_util_pct": float(record.get("channel_utilization", 0.0)),
            "retry_pct": float(record.get("tx_retries_pct", 0.0)),
            "uplink_mbps": (float(record["uplink_speed"])
                            if record.get("uplink_speed") else None),
            "quality_flags": "OK" if record.get("uplink_speed") else "UNKNOWN_UPLINK",
        })
    return output
