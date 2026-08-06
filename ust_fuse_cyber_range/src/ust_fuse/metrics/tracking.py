"""Track-level metrics (ЛР-3, ЛР-4): RMSE, OSPA, MOTA/MOTP, ID switches.

Tracks and ground truth are compared on a common time grid.  At every epoch a
Hungarian assignment (with a distance cutoff) matches estimated tracks to true
targets; from that matching we derive the standard multi-object tracking
figures of merit used on field trials.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

import numpy as np
from scipy.optimize import linear_sum_assignment

from ..datatypes import GroundTruth, Track


@dataclass
class TrackingMetrics:
    mode: str = ""
    rmse_pos: float = float("nan")
    mota: float = float("nan")
    motp: float = float("nan")
    id_switches: int = 0
    fragmentations: int = 0
    n_false_tracks: int = 0
    n_missed: int = 0
    n_gt: int = 0
    n_tracks: int = 0
    ospa_mean: float = float("nan")
    ospa_series: List[float] = field(default_factory=list)
    err_series: List[Tuple[float, float]] = field(default_factory=list)  # (t, mean err)
    track_completeness: float = float("nan")

    def to_dict(self) -> Dict:
        d = dict(self.__dict__)
        d.pop("ospa_series", None)
        d.pop("err_series", None)
        return d


def _track_pos_at(track: Track, t: float, tol: float = 0.35) -> Optional[np.ndarray]:
    """Position of a track at time ``t`` from its history (nearest within tol).

    Only states from after the track was confirmed are considered, so tentative
    (often clutter-seeded) states never contribute to the reported metrics.
    """
    if not track.history:
        return None
    states = [s for s in track.history if s.t >= track.t_confirmed]
    if not states:
        return None
    ts = np.array([s.t for s in states])
    i = int(np.argmin(np.abs(ts - t)))
    if abs(ts[i] - t) > tol:
        return None
    return states[i].mean[:3]


def _ospa(gt_pts: List[np.ndarray], tr_pts: List[np.ndarray], c: float, p: int = 2) -> float:
    m, n = len(gt_pts), len(tr_pts)
    if m == 0 and n == 0:
        return 0.0
    if m == 0 or n == 0:
        return c
    if m > n:
        gt_pts, tr_pts = tr_pts, gt_pts
        m, n = n, m
    D = np.zeros((m, n))
    for i in range(m):
        for j in range(n):
            D[i, j] = min(np.linalg.norm(gt_pts[i] - tr_pts[j]), c)
    row, col = linear_sum_assignment(D ** p)
    cost = (D[row, col] ** p).sum()
    cost += (c ** p) * (n - m)  # cardinality penalty
    return float((cost / n) ** (1.0 / p))


def evaluate_tracks(
    tracks: List[Track],
    truths: List[GroundTruth],
    duration_s: float,
    eval_rate_hz: float = 5.0,
    match_gate: float = 80.0,
    ospa_c: float = 100.0,
) -> TrackingMetrics:
    """Compute the multi-object tracking metric bundle.

    Only *confirmed* tracks are scored — this is standard field-trial practice
    and prevents transient clutter-seeded tentative tracks from dominating the
    false-track count.
    """
    tracks = [t for t in tracks if t.was_confirmed]
    times = np.arange(0.0, duration_s + 1e-9, 1.0 / eval_rate_hz)

    total_match_dist = 0.0
    total_matches = 0
    total_fn = 0
    total_fp = 0
    total_gt = 0
    id_switches = 0
    ospa_series: List[float] = []
    err_series: List[Tuple[float, float]] = []

    last_match: Dict[int, int] = {}     # truth_id -> track_id at previous epoch
    ever_matched: set = set()           # every track_id ever matched to a truth
    truth_seen_frames: Dict[int, int] = {t.truth_id: 0 for t in truths}
    truth_tracked_frames: Dict[int, int] = {t.truth_id: 0 for t in truths}
    frag_prev_tracked: Dict[int, bool] = {t.truth_id: False for t in truths}
    fragmentations = 0

    for t in times:
        gt_ids, gt_pts = [], []
        for gt in truths:
            p = gt.position_at(t)
            if p is not None:
                gt_ids.append(gt.truth_id)
                gt_pts.append(p)
                truth_seen_frames[gt.truth_id] += 1
        tr_ids, tr_pts = [], []
        for trk in tracks:
            p = _track_pos_at(trk, t)
            if p is not None:
                tr_ids.append(trk.track_id)
                tr_pts.append(p)

        total_gt += len(gt_pts)
        ospa_series.append(_ospa(gt_pts, tr_pts, c=ospa_c))

        if gt_pts and tr_pts:
            C = np.zeros((len(gt_pts), len(tr_pts)))
            for i, gp in enumerate(gt_pts):
                for j, tp in enumerate(tr_pts):
                    C[i, j] = np.linalg.norm(gp - tp)
            row, col = linear_sum_assignment(C)
            frame_errs = []
            matched_truth_ids = set()
            for r, cc in zip(row, col):
                if C[r, cc] <= match_gate:
                    gid = gt_ids[r]
                    tid = tr_ids[cc]
                    total_match_dist += C[r, cc]
                    total_matches += 1
                    frame_errs.append(C[r, cc])
                    matched_truth_ids.add(gid)
                    truth_tracked_frames[gid] += 1
                    ever_matched.add(tid)
                    if gid in last_match and last_match[gid] != tid:
                        id_switches += 1
                    last_match[gid] = tid
                    # fragmentation: track resumed after a gap
                    if not frag_prev_tracked[gid] and truth_tracked_frames[gid] > 1:
                        fragmentations += 1
                    frag_prev_tracked[gid] = True
            for gid in gt_ids:
                if gid not in matched_truth_ids:
                    frag_prev_tracked[gid] = False
            n_matched = len(matched_truth_ids)
            total_fn += len(gt_pts) - n_matched
            total_fp += len(tr_pts) - n_matched
            err_series.append((float(t), float(np.mean(frame_errs)) if frame_errs else np.nan))
        else:
            total_fn += len(gt_pts)
            total_fp += len(tr_pts)
            for gid in gt_ids:
                frag_prev_tracked[gid] = False

    rmse = (total_match_dist / total_matches) if total_matches else float("nan")
    motp = rmse
    mota = 1.0 - (total_fn + total_fp + id_switches) / max(total_gt, 1)
    completeness = np.mean(
        [truth_tracked_frames[i] / max(truth_seen_frames[i], 1) for i in truth_seen_frames]
    ) if truth_seen_frames else float("nan")

    # false / missed track counts (track-level): a confirmed track that never
    # matched any truth across the whole mission is a false track.
    n_false = sum(1 for trk in tracks if trk.track_id not in ever_matched)
    n_missed = sum(1 for i in truth_tracked_frames if truth_tracked_frames[i] == 0)

    return TrackingMetrics(
        rmse_pos=float(rmse),
        mota=float(mota),
        motp=float(motp),
        id_switches=int(id_switches),
        fragmentations=int(fragmentations),
        n_false_tracks=int(n_false),
        n_missed=int(n_missed),
        n_gt=len(truths),
        n_tracks=len(tracks),
        ospa_mean=float(np.nanmean(ospa_series)) if ospa_series else float("nan"),
        ospa_series=ospa_series,
        err_series=err_series,
        track_completeness=float(completeness),
    )
