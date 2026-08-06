"""The digital-twin world orchestrator.

:class:`DigitalTwin` runs one mission of the virtual range:

    ground truth  ->  per-sensor scans  ->  faults  ->  network transport
                                                        ->  RAW detection set

The RAW detection set is deliberately *immutable* once produced — it is the
"незмінювані RAW-дані" the proposal requires (sections 2, 15).  Both fusion
pipelines (Reference and Full UST-Fuse) consume the *same* RAW set, which is
what makes the paired comparison scientifically valid.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

import numpy as np

from .config import RangeConfig, ScenarioConfig
from .datatypes import Detection, GroundTruth
from .domain import DomainScales, resolve_domain
from .faults import apply_faults
from .network import transport
from .rng import RNGHub
from .sensors import build_sensor
from .trajectories import generate_ground_truth


@dataclass
class RawMission:
    """The immutable RAW output of one twin mission."""

    scenario: ScenarioConfig
    range_cfg: RangeConfig
    truths: List[GroundTruth]
    detections: List[Detection]
    domain: DomainScales
    seed: int
    stats: Dict = field(default_factory=dict)

    def detections_by_sensor(self) -> Dict[str, List[Detection]]:
        out: Dict[str, List[Detection]] = {}
        for d in self.detections:
            out.setdefault(d.sensor_id, []).append(d)
        return out


class DigitalTwin:
    """Runs a mission and returns its RAW detection set."""

    def __init__(self, range_cfg: RangeConfig):
        self.range_cfg = range_cfg
        self.sensors = [build_sensor(s) for s in range_cfg.enabled_sensors()]

    def run(self, scn: ScenarioConfig, rng_hub: RNGHub) -> RawMission:
        domain = resolve_domain(scn)
        truths = generate_ground_truth(scn, rng_hub)

        raw: List[Detection] = []
        for sensor in self.sensors:
            for t in sensor.scan_times(scn.duration_s):
                dets = sensor.scan(
                    t,
                    truths,
                    rng_hub,
                    env_scale=domain.env_scale(),
                    clutter_scale=domain.clutter_scale,
                )
                for d in dets:
                    d.R = d.R * domain.noise_scale
                    d.meta["_base_latency_ms"] = sensor.cfg.latency_ms
                raw.extend(dets)

        # fault injection (ЛР-5) then network transport
        raw = apply_faults(raw, scn.faults, truths, rng_hub)
        raw = transport(
            raw,
            rng_hub,
            packet_loss=_global_packet_loss(scn.faults),
            jitter_ms=3.0,
        )

        stats = _raw_stats(raw, truths)
        return RawMission(
            scenario=scn,
            range_cfg=self.range_cfg,
            truths=truths,
            detections=raw,
            domain=domain,
            seed=rng_hub.master_seed,
            stats=stats,
        )


def _global_packet_loss(faults: List[Dict]) -> float:
    for f in faults:
        if f.get("kind") == "packet_loss" and f.get("global"):
            return float(f.get("prob", 0.0))
    return 0.0


def _raw_stats(raw: List[Detection], truths: List[GroundTruth]) -> Dict:
    n_true = sum(1 for d in raw if not d.is_clutter)
    n_clutter = sum(1 for d in raw if d.is_clutter)
    per_sensor: Dict[str, int] = {}
    for d in raw:
        per_sensor[d.sensor_id] = per_sensor.get(d.sensor_id, 0) + 1
    return {
        "n_detections": len(raw),
        "n_true": n_true,
        "n_clutter": n_clutter,
        "clutter_fraction": (n_clutter / len(raw)) if raw else 0.0,
        "per_sensor": per_sensor,
        "n_targets": len(truths),
    }
