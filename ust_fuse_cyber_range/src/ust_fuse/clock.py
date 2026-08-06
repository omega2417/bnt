"""Time synchronisation model and analysis (ЛР-1. Калібрування часу).

The proposal insists on a *single time* across all sensors as a core scientific
requirement (sections 2, 15).  Here we (a) model each sensor's imperfect clock
(offset + drift + jitter, in :mod:`sensors.base`), (b) *estimate* and correct it
from the data, and (c) expose drift / desynchronisation diagnostics used by the
Full UST-Fuse pipeline and by the ЛР-1 report.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List

import numpy as np

from .config import RangeConfig
from .datatypes import Detection


@dataclass
class ClockEstimate:
    sensor_id: str
    offset_est_ms: float
    drift_est_ppm: float
    residual_ms: float
    n: int


def estimate_clock(detections: List[Detection]) -> ClockEstimate:
    """Least-squares estimate of a sensor's clock offset & drift.

    Uses ``t_stamp - t_true`` regressed on ``t_true``.  In a real range the
    reference would be RTK-GNSS/PPS; here the twin's ground-truth clock plays
    that role, which is exactly how a calibration session is validated.
    """
    if not detections:
        return ClockEstimate(detections and detections[0].sensor_id or "?", 0, 0, 0, 0)
    t_true = np.array([d.t_true for d in detections])
    err_ms = np.array([(d.t_stamp - d.t_true) for d in detections]) * 1e3
    A = np.vstack([np.ones_like(t_true), t_true]).T
    coef, *_ = np.linalg.lstsq(A, err_ms, rcond=None)
    offset_ms, slope_ms_per_s = coef
    drift_ppm = slope_ms_per_s * 1e3  # ms/s -> ppm
    resid = err_ms - A @ coef
    return ClockEstimate(
        sensor_id=detections[0].sensor_id,
        offset_est_ms=float(offset_ms),
        drift_est_ppm=float(drift_ppm),
        residual_ms=float(np.std(resid)),
        n=len(detections),
    )


def estimate_all_clocks(
    detections: List[Detection], range_cfg: RangeConfig
) -> Dict[str, ClockEstimate]:
    by_sensor: Dict[str, List[Detection]] = {}
    for d in detections:
        by_sensor.setdefault(d.sensor_id, []).append(d)
    return {sid: estimate_clock(ds) for sid, ds in by_sensor.items()}


def apply_clock_correction(
    detections: List[Detection], estimates: Dict[str, ClockEstimate]
) -> List[Detection]:
    """Return detections with a *corrected* arrival time.

    The Full UST-Fuse pipeline calls this so that heterogeneous sensors are
    aligned to a common timeline; the Reference pipeline skips it, which is what
    the ЛР-1 / ЛР-3 comparison quantifies.
    """
    corrected = []
    for d in detections:
        est = estimates.get(d.sensor_id)
        if est is None:
            corrected.append(d)
            continue
        corr = est.offset_est_ms * 1e-3 + est.drift_est_ppm * 1e-6 * d.t_stamp
        d2 = Detection(**{**d.__dict__})
        d2.t_stamp = d.t_stamp - corr
        corrected.append(d2)
    return corrected


def desync_matrix(estimates: Dict[str, ClockEstimate]) -> np.ndarray:
    """Pairwise absolute offset differences (ms) between sensors — a heatmap."""
    ids = list(estimates)
    n = len(ids)
    M = np.zeros((n, n))
    for i, a in enumerate(ids):
        for j, b in enumerate(ids):
            M[i, j] = abs(estimates[a].offset_est_ms - estimates[b].offset_est_ms)
    return M
