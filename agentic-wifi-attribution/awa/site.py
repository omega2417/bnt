"""Site, zone and sensor/anchor domain model (prompt Modules 1 & 2).

Deliberately synthetic: no real building geometry, no real coordinates.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Tuple

import numpy as np


class ZoneClass(str, Enum):
    PUBLIC = "public"
    CONTROLLED = "controlled"
    RESTRICTED = "restricted"
    CRITICAL = "critical"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class Zone:
    """Axis-aligned rectangular zone (metres) with a security class."""

    zone_id: str
    zone_class: ZoneClass
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    def contains(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        return (
            (xs >= self.x_min)
            & (xs < self.x_max)
            & (ys >= self.y_min)
            & (ys < self.y_max)
        )


@dataclass(frozen=True)
class Sensor:
    """RSSI sensor / FTM anchor (prompt Module 2, pseudonymised)."""

    sensor_id: str
    x: float
    y: float
    supports_rssi: bool = True
    supports_ftm: bool = False
    supports_sensing: bool = False
    trust_domain: str = "primary"
    provenance_score: float = 1.0  # 0..1, degrades sensing/threat weighting
    health_score: float = 1.0
    pmf_enabled: bool = True       # 802.11w Protected Management Frames

    @property
    def position(self) -> np.ndarray:
        return np.array([self.x, self.y], dtype=float)


@dataclass
class Site:
    """A single-floor synthetic CII site."""

    site_id: str
    zones: List[Zone] = field(default_factory=list)
    sensors: List[Sensor] = field(default_factory=list)
    crs: str = "local-metric-synthetic"  # NOT a geodetic CRS

    def zone_of(self, x: float, y: float) -> str:
        for z in self.zones:
            if z.contains(np.array([x]), np.array([y]))[0]:
                return z.zone_id
        return "unzoned"

    def sensor_positions(self) -> np.ndarray:
        return np.array([s.position for s in self.sensors])


def demo_site() -> Site:
    """Deterministic synthetic site used across notebooks and tests.

    Layout (40 x 25 m single floor)::

        y
        25 +--------------------------------------+
           |  public   |  controlled |  critical  |
           |           |             | (server rm)|
         0 +--------------------------------------+
           0                                      40  x

    ASSUMPTION: purely fictional geometry for demonstration only.
    """
    zones = [
        Zone("Z-public", ZoneClass.PUBLIC, 0, 0, 14, 25),
        Zone("Z-controlled", ZoneClass.CONTROLLED, 14, 0, 28, 25),
        Zone("Z-critical", ZoneClass.CRITICAL, 28, 0, 40, 25),
    ]
    # Eight ceiling sensors; a subset are FTM anchors / sensing-capable.
    sensors = [
        Sensor("S1", 3, 3, supports_ftm=True, supports_sensing=True),
        Sensor("S2", 3, 22, supports_ftm=True),
        Sensor("S3", 12, 12, supports_sensing=True),
        Sensor("S4", 20, 3, supports_ftm=True),
        Sensor("S5", 20, 22, supports_ftm=True, supports_sensing=True),
        Sensor("S6", 30, 12, supports_ftm=True),
        Sensor("S7", 37, 3),
        Sensor("S8", 37, 22, supports_ftm=True, supports_sensing=True),
    ]
    return Site(site_id="SITE-DEMO-001", zones=zones, sensors=sensors)
