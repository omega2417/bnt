"""Configuration objects for the range, sensors, scenarios and experiments.

The configuration deliberately mirrors the budget MVP composition from the
proposal (section 7 "Мінімальний склад обладнання для MVP"):

* 1 portable sensor post with a PTZ/network camera,
* an RTK-GNSS ground-truth base,
* an SDR receiver for passive RF observation,
* 2-3 training-class UAVs,
* plus a *simulated* radar (rented / partner access in real life, section 4).

Everything is a plain dataclass so configs are trivially serialisable to the
experiment manifest (reproducibility, ЛР-8).
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

import numpy as np


# --------------------------------------------------------------------------- #
# Sensors
# --------------------------------------------------------------------------- #
@dataclass
class SensorConfig:
    """Parameters of one sensor in the digital twin.

    The four sensor archetypes correspond to the proposal's segments:
    radar (partner/rented), EO-IR camera (owned), RF-SDR (owned, passive) and
    a short-range acoustic array (low-cost).
    """

    sensor_id: str
    sensor_type: str                     # radar | eo_ir | rf_sdr | acoustic
    position: List[float]                # ENU (m)
    max_range: float                     # detection range (m)
    fov_az_deg: float = 360.0            # azimuth field of view
    fov_el_deg: float = 90.0             # elevation field of view
    scan_rate_hz: float = 10.0           # measurement rate
    # measurement 1-sigma noise
    sigma_range: float = 5.0             # m   (huge for bearing-only sensors)
    sigma_az_deg: float = 0.5            # deg
    sigma_el_deg: float = 0.5            # deg
    # detection statistics
    pd_ref: float = 0.95                 # nominal detection prob at ref range
    ref_range: float = 500.0
    snr0_db: float = 25.0                # SNR at ref range
    false_alarm_rate: float = 0.5        # expected clutter returns per scan
    latency_ms: float = 20.0             # transport latency (network layer adds jitter)
    # clock model (ЛР-1)
    clock_offset_ms: float = 0.0         # constant bias
    clock_drift_ppm: float = 0.0         # linear drift
    clock_jitter_ms: float = 0.2         # per-stamp jitter
    # capability flags
    provides_range: bool = True          # False => bearing-only
    can_classify: bool = False           # produces a class label
    enabled: bool = True
    meta: Dict = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Range (the physical/virtual site)
# --------------------------------------------------------------------------- #
@dataclass
class RangeConfig:
    """The whole range: its sensors and site-level parameters."""

    name: str = "UST-Fuse budget MVP range"
    sensors: List[SensorConfig] = field(default_factory=list)
    site_extent_m: float = 2000.0        # half-width of the area of interest
    ceiling_m: float = 400.0             # max operating altitude (VLOS-ish)
    fusion_rate_hz: float = 10.0         # alignment epoch rate at the fusion node

    def enabled_sensors(self) -> List[SensorConfig]:
        return [s for s in self.sensors if s.enabled]

    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "site_extent_m": self.site_extent_m,
            "ceiling_m": self.ceiling_m,
            "fusion_rate_hz": self.fusion_rate_hz,
            "sensors": [s.to_dict() for s in self.sensors],
        }


# --------------------------------------------------------------------------- #
# Scenario (a mission definition — the LLM "scenario generator" output, sec.5)
# --------------------------------------------------------------------------- #
@dataclass
class ScenarioConfig:
    """A single mission / experiment scenario.

    A scenario is the machine-readable JSON/YAML the proposal's LLM "scenario
    generator" is meant to emit (section 5): UAV classes, trajectories, weather,
    faults, metrics and risks.
    """

    scenario_id: str
    title: str
    description: str = ""
    duration_s: float = 120.0
    truth_rate_hz: float = 20.0
    n_targets: int = 3
    uav_classes: List[str] = field(default_factory=lambda: ["multirotor"])
    trajectory_kinds: List[str] = field(default_factory=lambda: ["orbit"])
    crossing: bool = False               # force trajectory crossings (ЛР-4)
    # environment / domain (ЛР-6)
    weather: str = "clear"               # clear | haze | rain | night
    clutter_scale: float = 1.0
    noise_scale: float = 1.0
    pd_scale: float = 1.0
    # fault injection (ЛР-5) — list of fault dicts (see faults.py)
    faults: List[Dict] = field(default_factory=list)
    # red-team negative tests (section 5, red-team agent)
    red_team: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    lab: str = ""                        # associated lab work (ЛР-x)

    def to_dict(self) -> Dict:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Experiment (one reproducible run)
# --------------------------------------------------------------------------- #
@dataclass
class ExperimentConfig:
    """Everything needed to reproduce one run bit-for-bit."""

    scenario: ScenarioConfig
    range_cfg: RangeConfig
    seed: int = 20260101
    fusion_modes: List[str] = field(default_factory=lambda: ["reference", "ust_fuse"])
    notes: str = ""

    def to_dict(self) -> Dict:
        return {
            "seed": self.seed,
            "fusion_modes": list(self.fusion_modes),
            "notes": self.notes,
            "scenario": self.scenario.to_dict(),
            "range": self.range_cfg.to_dict(),
        }


# --------------------------------------------------------------------------- #
# Default budget-MVP range factory
# --------------------------------------------------------------------------- #
def default_range() -> RangeConfig:
    """The recommended budget MVP sensor suite (proposal section 3 & 7).

    * ``RAD-1``  simulated / partner radar  — the ranging anchor.
    * ``EO-1``   PTZ / network camera       — bearing-only, can classify.
    * ``SDR-1``  passive RF receiver        — coarse bearing + RF class.
    * ``AC-1``   low-cost acoustic array    — short range bearing.
    """
    d = 900.0
    sensors = [
        SensorConfig(
            sensor_id="RAD-1",
            sensor_type="radar",
            position=[-d, -d, 3.0],
            max_range=2500.0,
            scan_rate_hz=10.0,
            sigma_range=8.0,
            sigma_az_deg=0.6,
            sigma_el_deg=0.9,
            pd_ref=0.93,
            ref_range=800.0,
            snr0_db=24.0,
            false_alarm_rate=0.35,
            latency_ms=15.0,
            clock_offset_ms=1.5,
            clock_drift_ppm=6.0,
            clock_jitter_ms=0.3,
            provides_range=True,
            can_classify=False,
        ),
        SensorConfig(
            sensor_id="EO-1",
            sensor_type="eo_ir",
            position=[d, -d, 6.0],
            max_range=1400.0,
            fov_az_deg=90.0,
            scan_rate_hz=25.0,
            sigma_range=1500.0,         # bearing-only: along-LOS ~ unconstrained
            sigma_az_deg=0.15,
            sigma_el_deg=0.15,
            pd_ref=0.9,
            ref_range=600.0,
            snr0_db=22.0,
            false_alarm_rate=0.10,
            latency_ms=35.0,
            clock_offset_ms=-2.0,
            clock_drift_ppm=12.0,
            clock_jitter_ms=0.8,
            provides_range=False,
            can_classify=True,
        ),
        SensorConfig(
            sensor_id="SDR-1",
            sensor_type="rf_sdr",
            position=[0.0, d, 4.0],
            max_range=1800.0,
            scan_rate_hz=4.0,
            sigma_range=2200.0,         # bearing-only, very coarse
            sigma_az_deg=2.5,
            sigma_el_deg=6.0,
            pd_ref=0.85,
            ref_range=900.0,
            snr0_db=18.0,
            false_alarm_rate=0.18,
            latency_ms=60.0,
            clock_offset_ms=4.0,
            clock_drift_ppm=20.0,
            clock_jitter_ms=1.5,
            provides_range=False,
            can_classify=True,
        ),
        SensorConfig(
            sensor_id="AC-1",
            sensor_type="acoustic",
            position=[0.0, 0.0, 2.0],
            max_range=450.0,
            scan_rate_hz=6.0,
            sigma_range=600.0,
            sigma_az_deg=3.0,
            sigma_el_deg=5.0,
            pd_ref=0.8,
            ref_range=250.0,
            snr0_db=15.0,
            false_alarm_rate=0.12,
            latency_ms=25.0,
            clock_offset_ms=0.5,
            clock_drift_ppm=15.0,
            clock_jitter_ms=1.0,
            provides_range=False,
            can_classify=False,
        ),
    ]
    return RangeConfig(sensors=sensors)


# --------------------------------------------------------------------------- #
# (De)serialisation helpers used by the YAML scenario library
# --------------------------------------------------------------------------- #
def scenario_from_dict(d: Dict) -> ScenarioConfig:
    known = ScenarioConfig.__dataclass_fields__.keys()
    return ScenarioConfig(**{k: v for k, v in d.items() if k in known})


def range_from_dict(d: Dict) -> RangeConfig:
    sensors = [SensorConfig(**s) for s in d.get("sensors", [])]
    kwargs = {k: v for k, v in d.items() if k != "sensors"}
    return RangeConfig(sensors=sensors, **kwargs)
