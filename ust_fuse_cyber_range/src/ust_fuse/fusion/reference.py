"""Reference fusion — the naive single-sensor baseline (ЛР-3).

Represents "what you get for free": the ranging sensor (radar) alone, with **no**
clock correction and hard nearest-neighbour association.  It is deliberately
simple so that the Full UST-Fuse improvement can be measured against it on the
*same* RAW data.
"""
from __future__ import annotations

from typing import List

from ..datatypes import Detection
from ..tracking import MultiTargetTracker, TrackerParams
from .base import FusionOutput, build_frames


class ReferenceFusion:
    mode = "reference"

    def run(self, raw_mission) -> FusionOutput:
        scn = raw_mission.scenario
        # primary ranging sensor only (fallback: first sensor)
        primary = None
        for s in raw_mission.range_cfg.enabled_sensors():
            if s.provides_range:
                primary = s.sensor_id
                break
        if primary is None and raw_mission.range_cfg.sensors:
            primary = raw_mission.range_cfg.sensors[0].sensor_id

        dets: List[Detection] = [d for d in raw_mission.detections if d.sensor_id == primary]
        frames = build_frames(
            dets,
            rate_hz=raw_mission.range_cfg.fusion_rate_hz,
            duration_s=scn.duration_s,
            use_corrected_time=False,   # uncorrected clock => desync errors
        )
        tracker = MultiTargetTracker(
            TrackerParams(
                soft_association=False, q=12.0,
                confirm_hits=4, confirm_window=6, max_misses=8,
            )
        )
        tracks = tracker.process(frames)
        return FusionOutput(
            mode=self.mode,
            tracks=tracks,
            frames=frames,
            clock_estimates={},
            aux={"primary_sensor": primary, "n_input_detections": len(dets)},
        )
