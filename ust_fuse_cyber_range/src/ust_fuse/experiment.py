"""Experiment runner — one reproducible mission, both fusion modes, all metrics.

This is the public entry point most users touch.  Given a scenario and a range
configuration it:

1. runs the digital twin to produce the immutable RAW mission,
2. runs each fusion mode on that same RAW set,
3. computes detection / tracking / calibration metrics for each mode,
4. builds a provenance manifest,

and returns an :class:`ExperimentResult` that the visualisation and report
layers consume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from .config import ExperimentConfig, RangeConfig, ScenarioConfig, default_range
from .clock import estimate_all_clocks
from .datatypes import GroundTruth
from .fusion import build_fusion
from .fusion.base import FusionOutput
from .metrics import (
    calibration_metrics,
    detection_metrics,
    evaluate_tracks,
    roc_curve,
)
from .metrics.calibration import CalibrationResult
from .metrics.tracking import TrackingMetrics
from .provenance import Manifest, build_manifest
from .rng import RNGHub
from .twin import DigitalTwin, RawMission


@dataclass
class ModeResult:
    mode: str
    fusion: FusionOutput
    tracking: TrackingMetrics
    calibration: CalibrationResult

    def summary(self) -> Dict:
        d = self.tracking.to_dict()
        d.update({"ece": self.calibration.ece, "brier": self.calibration.brier})
        d["mode"] = self.mode
        return d


@dataclass
class ExperimentResult:
    config: ExperimentConfig
    raw: RawMission
    manifest: Manifest
    detection: Dict = field(default_factory=dict)
    roc: Dict = field(default_factory=dict)
    modes: Dict[str, ModeResult] = field(default_factory=dict)

    # convenience accessors ------------------------------------------------
    @property
    def truths(self) -> List[GroundTruth]:
        return self.raw.truths

    def summary_table(self) -> List[Dict]:
        rows = []
        for m in self.modes.values():
            rows.append(m.summary())
        return rows

    def best_mode(self, metric: str = "mota", lower_is_better: bool = False) -> str:
        vals = {k: getattr(v.tracking, metric, np.nan) for k, v in self.modes.items()}
        vals = {k: v for k, v in vals.items() if not np.isnan(v)}
        if not vals:
            return ""
        return (min if lower_is_better else max)(vals, key=vals.get)


def run_experiment(cfg: ExperimentConfig) -> ExperimentResult:
    """Run one experiment end-to-end and return its result bundle."""
    rng_hub = RNGHub(cfg.seed)
    twin = DigitalTwin(cfg.range_cfg)
    raw = twin.run(cfg.scenario, rng_hub)

    det = detection_metrics(raw.detections, raw.truths, cfg.range_cfg)
    roc = roc_curve(raw.detections, raw.truths)

    modes: Dict[str, ModeResult] = {}
    for mode in cfg.fusion_modes:
        fout = build_fusion(mode).run(raw)
        tm = evaluate_tracks(fout.tracks, raw.truths, cfg.scenario.duration_s)
        cal = calibration_metrics(
            fout.tracks, raw.truths, duration_s=cfg.scenario.duration_s
        )
        tm.mode = mode
        modes[mode] = ModeResult(mode=mode, fusion=fout, tracking=tm, calibration=cal)

    manifest = build_manifest(cfg.to_dict(), cfg.seed, cfg.scenario.scenario_id)
    manifest.extra = {
        "raw_stats": raw.stats,
        "clock_estimates": {
            k: v.__dict__ for k, v in estimate_all_clocks(raw.detections, cfg.range_cfg).items()
        },
        "mode_summaries": {k: v.summary() for k, v in modes.items()},
    }
    return ExperimentResult(
        config=cfg, raw=raw, manifest=manifest,
        detection=det, roc=roc, modes=modes,
    )


class Experiment:
    """Thin OO wrapper for notebook ergonomics."""

    def __init__(self, scenario: ScenarioConfig, range_cfg: Optional[RangeConfig] = None,
                 seed: int = 20260101, fusion_modes: Optional[List[str]] = None):
        self.cfg = ExperimentConfig(
            scenario=scenario,
            range_cfg=range_cfg or default_range(),
            seed=seed,
            fusion_modes=fusion_modes or ["reference", "ust_fuse"],
        )

    def run(self) -> ExperimentResult:
        return run_experiment(self.cfg)


def run(scenario, range_cfg: Optional[RangeConfig] = None, seed: int = 20260101,
        fusion_modes: Optional[List[str]] = None) -> ExperimentResult:
    """Functional shortcut: ``ust_fuse.run(scenario)``.

    ``scenario`` may be a :class:`ScenarioConfig` or a scenario id string from
    the built-in library.
    """
    from .scenarios import build_scenario

    if isinstance(scenario, str):
        scenario = build_scenario(scenario)
    return Experiment(scenario, range_cfg, seed, fusion_modes).run()
