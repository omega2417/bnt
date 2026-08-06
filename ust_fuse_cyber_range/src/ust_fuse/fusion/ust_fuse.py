"""Full UST-Fuse pipeline — multi-sensor, clock-corrected, soft-associated.

This is the "product under test".  On the *same* RAW data as the Reference
pipeline it:

1. estimates and corrects each sensor's clock (ЛР-1),
2. bins all sensors onto the common corrected timeline,
3. runs the tracker with JPDA-lite soft association (robust at crossings, ЛР-4),
4. exploits the heterogeneous covariances so bearing-only sensors sharpen the
   radar's cross-range (the physical point of multi-sensor fusion).
"""
from __future__ import annotations

from ..clock import apply_clock_correction, estimate_all_clocks
from ..tracking import MultiTargetTracker, TrackerParams
from .base import FusionOutput, build_frames


class USTFuse:
    mode = "ust_fuse"

    def run(self, raw_mission) -> FusionOutput:
        scn = raw_mission.scenario
        # (1) clock calibration on the full RAW set
        estimates = estimate_all_clocks(raw_mission.detections, raw_mission.range_cfg)
        corrected = apply_clock_correction(raw_mission.detections, estimates)

        # (2) common timeline, all sensors
        frames = build_frames(
            corrected,
            rate_hz=raw_mission.range_cfg.fusion_rate_hz,
            duration_s=scn.duration_s,
            use_corrected_time=True,
        )

        # (3) soft-association tracker
        tracker = MultiTargetTracker(
            TrackerParams(
                soft_association=True,
                q=12.0,
                confirm_hits=4,
                confirm_window=6,
                max_misses=8,
            )
        )
        tracks = tracker.process(frames)
        return FusionOutput(
            mode=self.mode,
            tracks=tracks,
            frames=frames,
            clock_estimates={k: v.__dict__ for k, v in estimates.items()},
            aux={
                "n_sensors": len(raw_mission.range_cfg.enabled_sensors()),
                "n_input_detections": len(corrected),
            },
        )
