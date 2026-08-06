"""Sensor-level detection metrics (ЛР-2. Модель сенсора).

Computed directly from the RAW detection set against ground truth:

* **Pd**  — fraction of target-present opportunities that produced a detection;
* **Pfa** proxy — clutter detections per scan;
* **ROC** — Pd vs false-alarm rate as the SNR acceptance threshold sweeps.
"""
from __future__ import annotations

from typing import Dict, List

import numpy as np

from ..datatypes import Detection, GroundTruth


def detection_metrics(
    detections: List[Detection], truths: List[GroundTruth], range_cfg
) -> Dict[str, Dict]:
    """Per-sensor Pd / clutter statistics from the RAW set."""
    out: Dict[str, Dict] = {}
    by_sensor: Dict[str, List[Detection]] = {}
    for d in detections:
        by_sensor.setdefault(d.sensor_id, []).append(d)

    for s in range_cfg.enabled_sensors():
        sid = s.sensor_id
        ds = by_sensor.get(sid, [])
        n_true = sum(1 for d in ds if not d.is_clutter)
        n_clutter = sum(1 for d in ds if d.is_clutter)
        n_scans = max(len(set(round(d.t_true, 4) for d in ds)), 1)
        # opportunity count: targets in-range at each scan time
        opportunities = _count_opportunities(s, truths)
        pd = n_true / opportunities if opportunities > 0 else 0.0
        out[sid] = {
            "sensor_type": s.sensor_type,
            "n_detections": len(ds),
            "n_true": n_true,
            "n_clutter": n_clutter,
            "pd_empirical": float(np.clip(pd, 0, 1)),
            "clutter_per_scan": n_clutter / n_scans,
            "mean_snr_db": float(np.mean([d.snr_db for d in ds if not d.is_clutter]))
            if n_true else 0.0,
        }
    return out


def _count_opportunities(sensor_cfg, truths: List[GroundTruth]) -> int:
    from ..geometry import cart_to_spherical

    pos = np.asarray(sensor_cfg.position)
    scan_dt = 1.0 / sensor_cfg.scan_rate_hz
    opp = 0
    for gt in truths:
        # sample at sensor scan cadence
        t_end = gt.t[-1]
        times = np.arange(0, t_end + 1e-9, scan_dt)
        for t in times:
            p = gt.position_at(t)
            if p is None:
                continue
            rng = np.linalg.norm(p - pos)
            if rng <= sensor_cfg.max_range:
                opp += 1
    return opp


def roc_curve(
    detections: List[Detection], truths: List[GroundTruth], n_points: int = 40
) -> Dict[str, np.ndarray]:
    """Sweep an SNR acceptance threshold to trace an ROC-like curve."""
    snrs = np.array([d.snr_db for d in detections])
    labels = np.array([0 if d.is_clutter else 1 for d in detections])
    if len(snrs) == 0:
        return {"thresh": np.array([]), "pd": np.array([]), "pfa": np.array([])}
    lo, hi = np.percentile(snrs, 1), np.percentile(snrs, 99)
    thr = np.linspace(lo, hi, n_points)
    n_pos = max(labels.sum(), 1)
    n_neg = max((1 - labels).sum(), 1)
    pd, pfa = [], []
    for th in thr:
        accept = snrs >= th
        tp = np.sum(accept & (labels == 1))
        fp = np.sum(accept & (labels == 0))
        pd.append(tp / n_pos)
        pfa.append(fp / n_neg)
    return {"thresh": thr, "pd": np.array(pd), "pfa": np.array(pfa)}
