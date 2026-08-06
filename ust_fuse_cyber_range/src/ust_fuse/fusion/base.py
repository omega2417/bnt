"""Shared fusion machinery."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from ..datatypes import Detection, ScanFrame, Track


@dataclass
class FusionOutput:
    mode: str
    tracks: List[Track]
    frames: List[ScanFrame]
    clock_estimates: Dict = field(default_factory=dict)
    aux: Dict = field(default_factory=dict)


def build_frames(
    detections: List[Detection],
    rate_hz: float,
    duration_s: float,
    use_corrected_time: bool = True,
) -> List[ScanFrame]:
    """Bin detections into fusion epochs of width ``1/rate_hz``.

    ``use_corrected_time`` selects between the (clock-corrected) ``t_stamp`` and
    the raw arrival time; the Reference pipeline uses the uncorrected timeline,
    which is precisely the error the ЛР-1 / ЛР-3 comparison exposes.
    """
    dt = 1.0 / rate_hz
    n_epochs = int(np.ceil(duration_s / dt)) + 1
    bins: List[List[Detection]] = [[] for _ in range(n_epochs)]
    for d in detections:
        t = d.t_stamp if use_corrected_time else d.t_arrive
        idx = int(round(t / dt))
        idx = min(max(idx, 0), n_epochs - 1)
        bins[idx].append(d)
    frames = [ScanFrame(t=i * dt, detections=b) for i, b in enumerate(bins) if b]
    return frames
