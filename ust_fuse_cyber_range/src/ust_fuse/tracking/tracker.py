"""Multi-target tracker with track lifecycle management.

Processes a time-ordered list of :class:`ScanFrame` (one per fusion epoch),
runs predict / associate / update, spawns and prunes tracks with M-of-N
confirmation logic, and records a per-epoch history for provenance and plots.

Each track carries an *existence probability* (``confidence``) that is updated
online — this is the quantity the calibration lab (ЛР-7) scores with ECE /
Brier / reliability diagrams.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from ..datatypes import Detection, ScanFrame, Track, TrackState
from .association import gate_and_associate
from .kalman import KalmanCV


@dataclass
class TrackerParams:
    q: float = 12.0                    # process noise (UAVs manoeuvre)
    gate: float = 16.27                # chi2(0.99, df=3)
    confirm_hits: int = 4              # M
    confirm_window: int = 6            # N
    max_misses: int = 8                # delete after this many consecutive misses
    min_assoc_weight: float = 0.15     # ignore soft associations below this weight
    init_pos_var: float = 400.0
    init_vel_var: float = 400.0
    soft_association: bool = False     # JPDA-lite (Full UST-Fuse)
    birth_conf: float = 0.4
    conf_hit: float = 0.18
    conf_miss: float = 0.28
    birth_suppress_m: float = 70.0     # don't seed a track this close to an existing one
    merge_dist_m: float = 60.0         # merge tracks closer than this ...
    merge_vel_m_s: float = 14.0        # ... with consistent velocity


class _LiveTrack:
    _next_id = 1

    def __init__(self, det: Detection, params: TrackerParams, t: float):
        self.track_id = _LiveTrack._next_id
        _LiveTrack._next_id += 1
        mean = np.zeros(6)
        mean[:3] = det.z
        cov = np.diag(
            [params.init_pos_var] * 3 + [params.init_vel_var] * 3
        ).astype(float)
        cov[:3, :3] = det.R + np.eye(3) * 1.0
        self.kf = KalmanCV(mean, cov, q=params.q)
        self.status = "tentative"
        self.hits = 1
        self.misses = 0
        self.age = 1
        self.recent = [1]
        self.range_recent = [1]   # hits supported by a range-providing sensor
        self.t_start = t
        self.t_last = t
        self.confidence = params.birth_conf
        self.was_confirmed = False
        self.t_confirmed = float("inf")
        self.label_votes: Dict[str, int] = {}
        self.n_sensors_last = 1
        self.history: List[TrackState] = []
        if det.detected_class not in ("unknown", ""):
            self.label_votes[det.detected_class] = 1

    def label(self) -> str:
        if not self.label_votes:
            return "unknown"
        return max(self.label_votes, key=self.label_votes.get)

    def snapshot(self, t: float) -> None:
        self.history.append(
            TrackState(
                t=t,
                mean=self.kf.mean.copy(),
                cov=self.kf.cov.copy(),
                confidence=self.confidence,
                n_sensors=self.n_sensors_last,
            )
        )

    def to_track(self) -> Track:
        return Track(
            track_id=self.track_id,
            status=self.status,
            mean=self.kf.mean.copy(),
            cov=self.kf.cov.copy(),
            hits=self.hits,
            misses=self.misses,
            age=self.age,
            t_start=self.t_start,
            t_last=self.t_last,
            confidence=self.confidence,
            label_class=self.label(),
            was_confirmed=self.was_confirmed,
            t_confirmed=self.t_confirmed,
            history=list(self.history),
        )


class MultiTargetTracker:
    def __init__(self, params: TrackerParams | None = None):
        self.params = params or TrackerParams()
        self.live: List[_LiveTrack] = []
        self.finished: List[_LiveTrack] = []
        self._last_t: float | None = None

    def reset(self):
        self.live.clear()
        self.finished.clear()
        self._last_t = None
        _LiveTrack._next_id = 1

    # ------------------------------------------------------------------ #
    def _update_confidence(self, trk: _LiveTrack, hit: bool):
        p = self.params
        if hit:
            trk.confidence = min(0.99, trk.confidence + p.conf_hit * (1 - trk.confidence))
        else:
            trk.confidence = max(0.01, trk.confidence - p.conf_miss * trk.confidence)

    def process_frame(self, frame: ScanFrame):
        p = self.params
        t = frame.t
        dt = 0.0 if self._last_t is None else max(t - self._last_t, 0.0)
        self._last_t = t

        for trk in self.live:
            trk.kf.predict(dt)
            trk.age += 1

        dets = frame.detections
        res = gate_and_associate(self.live, dets, gate=p.gate, soft=p.soft_association)

        updated = set()
        for ti, dj in res.assignments.items():
            trk = self.live[ti]
            det = dets[dj]
            range_hit = det.provides_range
            n_contrib = 1
            if p.soft_association and res.soft_weights.get(ti):
                # Sequential multi-sensor update over all gated detections.  Each
                # detection is applied with its own covariance, so a radar return
                # fixes the range while accurate camera/RF bearings sharpen the
                # cross-range — without the range bias a naive position-average
                # (moment matching heterogeneous range/bearing sensors) would add.
                contrib = res.soft_weights[ti]
                n_contrib = self._sequential_update(trk, dets, contrib, p.min_assoc_weight)
                range_hit = any(
                    dets[j].provides_range for j, w in contrib.items()
                    if w >= p.min_assoc_weight
                )
            else:
                trk.kf.update(det.z, det.R)
            trk.hits += 1
            trk.misses = 0
            trk.recent.append(1)
            trk.range_recent.append(1 if range_hit else 0)
            trk.t_last = t
            trk.n_sensors_last = n_contrib
            if det.detected_class not in ("unknown", ""):
                trk.label_votes[det.detected_class] = trk.label_votes.get(det.detected_class, 0) + 1
            self._update_confidence(trk, hit=True)
            updated.add(ti)

        for ti, trk in enumerate(self.live):
            if ti not in updated:
                trk.misses += 1
                trk.recent.append(0)
                trk.range_recent.append(0)
                self._update_confidence(trk, hit=False)
            trk.recent = trk.recent[-p.confirm_window:]
            trk.range_recent = trk.range_recent[-p.confirm_window:]
            # Confirmation must be *range-supported*: bearing-only sensors refine
            # a confirmed track's cross-range but cannot, on their own, promote a
            # clutter-seeded tentative track.  This keeps the false-track rate of
            # the multi-sensor pipeline at or below the radar-only baseline.
            if trk.status == "tentative" and sum(trk.range_recent) >= p.confirm_hits:
                trk.status = "confirmed"
                trk.was_confirmed = True
                trk.t_confirmed = min(trk.t_confirmed, t)

        # spawn new tentative tracks from unassigned detections — but only from
        # range-providing sensors (radar).  A single bearing measurement cannot
        # localise a 3-D track, so bearing-only sensors may *update* existing
        # tracks but never *initiate* one.  This is the standard multi-sensor
        # track-initiation policy and it eliminates along-line-of-sight ghosts.
        # Birth suppression: do not seed a track on top of an existing one, or
        # transient duplicate tracks would proliferate on the same target.
        existing_pos = [trk.kf.position() for trk in self.live]
        for dj in res.unassigned_dets:
            det = dets[dj]
            if not det.provides_range:
                continue
            if any(np.linalg.norm(det.z - ep) < p.birth_suppress_m for ep in existing_pos):
                continue
            nt = _LiveTrack(det, p, t)
            self.live.append(nt)
            existing_pos.append(nt.kf.position())

        # merge redundant tracks that have converged onto the same target
        self._merge_tracks()

        # prune
        survivors = []
        for trk in self.live:
            if trk.misses > p.max_misses:
                trk.status = "deleted"
                self.finished.append(trk)
            else:
                trk.snapshot(t)
                survivors.append(trk)
        self.live = survivors

    def _merge_tracks(self) -> None:
        """Collapse pairs of tracks that follow the same target.

        Two tracks are merged when their positions are within
        ``merge_dist_m`` and their velocity vectors are consistent.  The older /
        better-supported track survives; this bounds the OSPA cardinality
        penalty and suppresses spurious ID switches.
        """
        p = self.params
        # order by strength so the survivor of each merge is the stronger track
        order = sorted(self.live, key=lambda tr: (-tr.hits, tr.track_id))
        kept: List[_LiveTrack] = []
        for cand in order:
            merged = False
            for keep in kept:
                dp = np.linalg.norm(cand.kf.position() - keep.kf.position())
                dv = np.linalg.norm(cand.kf.mean[3:] - keep.kf.mean[3:])
                if dp < p.merge_dist_m and dv < p.merge_vel_m_s:
                    keep.hits += cand.hits
                    keep.was_confirmed = keep.was_confirmed or cand.was_confirmed
                    keep.t_confirmed = min(keep.t_confirmed, cand.t_confirmed)
                    if keep.was_confirmed:
                        keep.status = "confirmed"
                    for k, v in cand.label_votes.items():
                        keep.label_votes[k] = keep.label_votes.get(k, 0) + v
                    merged = True
                    break
            if not merged:
                kept.append(cand)
        self.live = kept

    def _sequential_update(self, trk: _LiveTrack, dets: List[Detection],
                           weights: Dict[int, float], min_w: float) -> int:
        """Apply a KF update for every sufficiently-likely gated detection.

        The association weight inflates each measurement covariance (``R / w``)
        so uncertain associations contribute less — a pragmatic JPDA-style soft
        assignment that, unlike position moment-matching, is unbiased for mixed
        range/bearing sensors.  Returns the number of detections applied.
        """
        applied = 0
        # apply range-providing sensors first (they anchor the range), then
        # bearing-only refinements — order improves the linearisation.
        items = sorted(weights.items(), key=lambda kv: (not dets[kv[0]].provides_range, -kv[1]))
        for j, w in items:
            if w < min_w:
                continue
            trk.kf.update(dets[j].z, dets[j].R / max(w, 1e-3))
            applied += 1
        return max(applied, 1)

    def process(self, frames: List[ScanFrame]) -> List[Track]:
        self.reset()
        for frame in sorted(frames, key=lambda f: f.t):
            self.process_frame(frame)
        all_tracks = self.finished + self.live
        return [t.to_track() for t in all_tracks]
