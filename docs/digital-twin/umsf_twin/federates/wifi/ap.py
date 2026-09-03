"""One object per access point (48 at site A, 6 at site B).

Effective throughput follows section 9.4:
``C_eff = min(C_radio * f_RSSI * (1 - airtime_overhead), C_uplink)``.
Access points whose uplink was never inventoried keep ``uplink_mbps=None`` and
stamp ``UNKNOWN_UPLINK`` on every record they influence.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Any

__all__ = ["AccessPoint", "ApState", "rssi_capacity_factor"]


class ApState:
    ONLINE = "ONLINE"
    DEGRADED = "DEGRADED"
    OFFLINE = "OFFLINE"
    UNADOPTED = "UNADOPTED"


def rssi_capacity_factor(rssi_dbm: float) -> float:
    """Piecewise-linear RSSI to usable-rate factor (synthetic, uncalibrated)."""

    anchors = ((-50.0, 1.00), (-60.0, 0.80), (-67.0, 0.60),
               (-72.0, 0.40), (-80.0, 0.15), (-90.0, 0.04))
    if rssi_dbm >= anchors[0][0]:
        return anchors[0][1]
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        if rssi_dbm >= x1:
            span = (rssi_dbm - x1) / (x0 - x1)
            return y1 + span * (y0 - y1)
    return anchors[-1][1]


@dataclass
class AccessPoint:
    ap_id: str
    site_id: str
    radio_capacity_mbps: float = 600.0
    uplink_mbps: float | None = None          # None => UNKNOWN_UPLINK
    band: str = "5GHz"
    power_group: int = 3                       # load-shed group I/II/III
    state: str = ApState.ONLINE
    clients: int = 0
    rssi_dbm: float = -62.0
    channel_util_pct: float = 20.0
    retry_pct: float = 4.0
    auth_failures: int = 0
    roaming_events: int = 0
    rogue_neighbors: int = 0

    @property
    def uplink_known(self) -> bool:
        return self.uplink_mbps is not None

    def effective_capacity_mbps(self) -> float:
        if self.state == ApState.OFFLINE:
            return 0.0
        airtime_overhead = min(0.85, self.channel_util_pct / 100.0)
        radio = self.radio_capacity_mbps * rssi_capacity_factor(self.rssi_dbm) \
            * (1.0 - airtime_overhead)
        if self.state == ApState.DEGRADED:
            radio *= 0.5
        # An uninventoried uplink is not silently assumed to be unlimited: the
        # conservative 100 Mbps surrogate is used and the record is flagged.
        uplink = self.uplink_mbps if self.uplink_known else 100.0
        return max(0.0, min(radio, uplink))

    def step(self, rng: random.Random, *, clients: int, rssi_shift_db: float = 0.0,
             congestion: float = 0.0, auth_burst: int = 0,
             powered: bool = True, rogue_count: int = 0) -> dict[str, Any]:
        if not powered:
            self.state = ApState.OFFLINE
            self.clients = 0
            self.channel_util_pct = 0.0
            self.retry_pct = 0.0
            self.auth_failures = 0
            return self.snapshot()

        if self.state == ApState.OFFLINE:
            self.state = ApState.ONLINE
        self.clients = max(0, clients)
        self.rssi_dbm = rng.gauss(-62.0 + rssi_shift_db, 3.0) if self.band == "5GHz" \
            else rng.gauss(-58.0 + rssi_shift_db, 4.0)
        load_factor = min(1.0, self.clients / 40.0) + congestion
        self.channel_util_pct = min(98.0, max(2.0, 100.0 * (0.12 + 0.55 * load_factor)
                                              + rng.gauss(0.0, 3.0)))
        self.retry_pct = min(60.0, max(0.5, 3.0 + 18.0 * load_factor
                                       + max(0.0, (-self.rssi_dbm - 62.0) * 0.35)
                                       + rng.gauss(0.0, 0.8)))
        self.auth_failures = max(0, auth_burst + (1 if rng.random() < 0.02 else 0))
        self.roaming_events = 1 if rng.random() < 0.05 * (1.0 + load_factor) else 0
        self.rogue_neighbors = rogue_count
        if self.retry_pct > 35.0 or self.channel_util_pct > 90.0:
            self.state = ApState.DEGRADED
        return self.snapshot()

    def snapshot(self) -> dict[str, Any]:
        return {
            "ap_id": self.ap_id,
            "site_id": self.site_id,
            "state": self.state,
            "clients": self.clients,
            "rssi_dbm": self.rssi_dbm,
            "channel_util_pct": self.channel_util_pct,
            "retry_pct": self.retry_pct,
            "auth_failures": self.auth_failures,
            "roaming_events": self.roaming_events,
            "rogue_neighbors": self.rogue_neighbors,
            "effective_capacity_mbps": self.effective_capacity_mbps(),
            "uplink_known": self.uplink_known,
            "quality_flag": "OK" if self.uplink_known else "UNKNOWN_UPLINK",
        }
