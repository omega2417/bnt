"""Core data structures shared across the twin.

All spatial quantities are in the local ENU frame (metres); all times in
seconds.  These small dataclasses are the "wire format" that flows from the
sensor models, through the network / clock layers, into fusion and tracking.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np


@dataclass
class Detection:
    """A single sensor return (target detection or clutter/false alarm)."""

    t_true: float              # true emission time (twin ground-truth clock)
    t_stamp: float             # time as stamped by the *sensor* clock (may drift)
    t_arrive: float            # time the fusion node receives it (network delay)
    sensor_id: str
    sensor_type: str           # 'radar' | 'eo_ir' | 'rf_sdr' | 'acoustic'
    z: np.ndarray              # position estimate in ENU (3,)
    R: np.ndarray              # 3x3 measurement covariance in ENU
    snr_db: float
    truth_id: int = -1         # -1 => clutter / false alarm
    detected_class: str = "unknown"
    provides_range: bool = True   # False => bearing-only (cannot initiate a track)
    meta: Dict = field(default_factory=dict)

    @property
    def is_clutter(self) -> bool:
        return self.truth_id < 0


@dataclass
class ScanFrame:
    """All detections that a fusion node processes at one alignment epoch."""

    t: float
    detections: List[Detection] = field(default_factory=list)


@dataclass
class GroundTruth:
    """Sampled ground-truth trajectory of one target."""

    truth_id: int
    uav_class: str
    t: np.ndarray              # (T,)
    pos: np.ndarray            # (T, 3) ENU
    vel: np.ndarray            # (T, 3)
    rf_active: bool = True     # emits an RF signature (detectable by SDR)
    t_appear: float = 0.0
    t_disappear: float = np.inf

    def position_at(self, t: float) -> Optional[np.ndarray]:
        """Linear-interpolated position at ``t`` or ``None`` if not present."""
        if t < self.t_appear or t > self.t_disappear:
            return None
        if t <= self.t[0]:
            return self.pos[0].copy()
        if t >= self.t[-1]:
            return self.pos[-1].copy()
        i = int(np.searchsorted(self.t, t))
        t0, t1 = self.t[i - 1], self.t[i]
        w = (t - t0) / max(t1 - t0, 1e-9)
        return (1 - w) * self.pos[i - 1] + w * self.pos[i]


@dataclass
class TrackState:
    """Snapshot of a track at one time step (for history / provenance)."""

    t: float
    mean: np.ndarray           # (6,) [x, y, z, vx, vy, vz]
    cov: np.ndarray            # (6, 6)
    confidence: float          # existence probability in [0, 1]
    n_sensors: int             # sensors that contributed this update


@dataclass
class Track:
    """A confirmed or tentative target track produced by the tracker."""

    track_id: int
    status: str = "tentative"  # 'tentative' | 'confirmed' | 'deleted'
    mean: np.ndarray = field(default_factory=lambda: np.zeros(6))
    cov: np.ndarray = field(default_factory=lambda: np.eye(6))
    hits: int = 0
    misses: int = 0
    age: int = 0
    t_start: float = 0.0
    t_last: float = 0.0
    confidence: float = 0.5
    label_class: str = "unknown"
    was_confirmed: bool = False   # reached 'confirmed' at any point in its life
    t_confirmed: float = float("inf")
    history: List[TrackState] = field(default_factory=list)

    @property
    def position(self) -> np.ndarray:
        return self.mean[:3].copy()

    @property
    def velocity(self) -> np.ndarray:
        return self.mean[3:].copy()
