"""Measurement-to-track association.

Two strategies are provided:

* **GNN** (global nearest neighbour) via the Hungarian algorithm on a
  Mahalanobis cost matrix with chi-square gating — the default;
* **JPDA-lite**, a soft-association weighting used by the Full UST-Fuse mode to
  stay robust when trajectories cross (ЛР-4. Багатоцільове супроводження).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment
from scipy.stats import chi2

from ..datatypes import Detection


# 3-DoF gate; 0.99 quantile
GATE_THRESH = chi2.ppf(0.99, df=3)


@dataclass
class AssociationResult:
    assignments: Dict[int, int] = field(default_factory=dict)   # track_idx -> det_idx
    unassigned_tracks: List[int] = field(default_factory=list)
    unassigned_dets: List[int] = field(default_factory=list)
    soft_weights: Dict[int, Dict[int, float]] = field(default_factory=dict)


def gate_and_associate(
    tracks: List,
    detections: List[Detection],
    gate: float = GATE_THRESH,
    soft: bool = False,
) -> AssociationResult:
    """Associate ``detections`` to ``tracks`` (each track exposes a ``.kf``)."""
    n_t, n_d = len(tracks), len(detections)
    res = AssociationResult()
    if n_t == 0:
        res.unassigned_dets = list(range(n_d))
        return res
    if n_d == 0:
        res.unassigned_tracks = list(range(n_t))
        return res

    BIG = 1e6
    cost = np.full((n_t, n_d), BIG)
    m2 = np.full((n_t, n_d), np.inf)
    for i, trk in enumerate(tracks):
        for j, det in enumerate(detections):
            d2 = trk.kf.mahalanobis2(det.z, det.R)
            m2[i, j] = d2
            if d2 <= gate:
                cost[i, j] = d2

    if soft:
        # JPDA-lite soft weights per track over gated detections
        for i, trk in enumerate(tracks):
            weights: Dict[int, float] = {}
            liks = []
            idxs = []
            for j, det in enumerate(detections):
                if m2[i, j] <= gate:
                    liks.append(tracks[i].kf.likelihood(det.z, det.R))
                    idxs.append(j)
            s = sum(liks)
            if s > 0:
                for j, lik in zip(idxs, liks):
                    weights[j] = lik / s
            res.soft_weights[i] = weights

    row, col = linear_sum_assignment(cost)
    assigned_t, assigned_d = set(), set()
    for r, c in zip(row, col):
        if cost[r, c] < BIG:
            res.assignments[r] = c
            assigned_t.add(r)
            assigned_d.add(c)
    res.unassigned_tracks = [i for i in range(n_t) if i not in assigned_t]
    res.unassigned_dets = [j for j in range(n_d) if j not in assigned_d]
    return res
