"""Uncertainty calibration metrics (ЛР-7. Калібрування невизначеності).

The tracker emits an *existence probability* per track state.  We score how well
that probability matches reality (whether the track state was actually matched
to a true target) using:

* **ECE** — expected calibration error,
* **Brier score**,
* a **reliability diagram** (binned confidence vs empirical accuracy),
* a **selective-risk** curve (risk vs coverage as a confidence threshold sweeps).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..datatypes import GroundTruth, Track


@dataclass
class CalibrationResult:
    ece: float = float("nan")
    brier: float = float("nan")
    bin_conf: List[float] = field(default_factory=list)
    bin_acc: List[float] = field(default_factory=list)
    bin_count: List[int] = field(default_factory=list)
    risk_coverage: List[Tuple[float, float]] = field(default_factory=list)
    n_samples: int = 0

    def to_dict(self) -> Dict:
        return {
            "ece": self.ece,
            "brier": self.brier,
            "n_samples": self.n_samples,
        }


def _collect_confidence_labels(
    tracks: List[Track], truths: List[GroundTruth], match_gate: float = 80.0,
    eval_rate_hz: float = 5.0, duration_s: float = 120.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Return (confidences, labels) where label=1 if the track state matched a truth."""
    # index track states by rounded time for quick lookup
    tracks = [t for t in tracks if t.was_confirmed]
    times = np.arange(0.0, duration_s + 1e-9, 1.0 / eval_rate_hz)
    tol = 0.5 / eval_rate_hz + 1e-6
    confs, labels = [], []
    for t in times:
        # gather truth points
        gt_pts = []
        for gt in truths:
            p = gt.position_at(t)
            if p is not None:
                gt_pts.append(p)
        # gather track states near t (post-confirmation only)
        st_list = []
        for trk in tracks:
            states = [s for s in trk.history if s.t >= trk.t_confirmed]
            if not states:
                continue
            ts = np.array([s.t for s in states])
            i = int(np.argmin(np.abs(ts - t)))
            if abs(ts[i] - t) <= tol:
                st_list.append(states[i])
        if not st_list:
            continue
        tr_pts = [s.mean[:3] for s in st_list]
        matched = set()
        if gt_pts and tr_pts:
            C = np.zeros((len(gt_pts), len(tr_pts)))
            for a, gp in enumerate(gt_pts):
                for b, tp in enumerate(tr_pts):
                    C[a, b] = np.linalg.norm(gp - tp)
            row, col = linear_sum_assignment(C)
            for r, cc in zip(row, col):
                if C[r, cc] <= match_gate:
                    matched.add(cc)
        for b, s in enumerate(st_list):
            confs.append(float(np.clip(s.confidence, 0, 1)))
            labels.append(1.0 if b in matched else 0.0)
    return np.array(confs), np.array(labels)


def calibration_metrics(
    tracks: List[Track], truths: List[GroundTruth],
    duration_s: float = 120.0, n_bins: int = 10, eval_rate_hz: float = 5.0,
) -> CalibrationResult:
    confs, labels = _collect_confidence_labels(
        tracks, truths, duration_s=duration_s, eval_rate_hz=eval_rate_hz
    )
    if len(confs) == 0:
        return CalibrationResult()

    brier = float(np.mean((confs - labels) ** 2))
    edges = np.linspace(0, 1, n_bins + 1)
    bin_conf, bin_acc, bin_count = [], [], []
    ece = 0.0
    n = len(confs)
    for k in range(n_bins):
        lo, hi = edges[k], edges[k + 1]
        mask = (confs > lo) & (confs <= hi) if k > 0 else (confs >= lo) & (confs <= hi)
        c = mask.sum()
        if c == 0:
            bin_conf.append((lo + hi) / 2)
            bin_acc.append(np.nan)
            bin_count.append(0)
            continue
        mean_conf = confs[mask].mean()
        mean_acc = labels[mask].mean()
        bin_conf.append(float(mean_conf))
        bin_acc.append(float(mean_acc))
        bin_count.append(int(c))
        ece += (c / n) * abs(mean_acc - mean_conf)

    # selective risk vs coverage
    order = np.argsort(-confs)
    sorted_labels = labels[order]
    risk_cov = []
    for frac in np.linspace(0.05, 1.0, 20):
        k = max(int(frac * n), 1)
        cov = k / n
        risk = 1.0 - sorted_labels[:k].mean()   # error rate among most-confident
        risk_cov.append((float(cov), float(risk)))

    return CalibrationResult(
        ece=float(ece),
        brier=brier,
        bin_conf=bin_conf,
        bin_acc=bin_acc,
        bin_count=bin_count,
        risk_coverage=risk_cov,
        n_samples=int(n),
    )
