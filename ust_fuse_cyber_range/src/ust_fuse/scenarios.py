"""Built-in scenario library and campaign runner.

Each scenario is the machine-readable mission the proposal's LLM "scenario
generator" is meant to emit (section 5).  The library spans the ten lab works
(ЛР-1 … ЛР-10) plus red-team negative tests, so a course can be assembled
entirely from virtual missions ("не менше 50 версіонованих сценаріїв", KPI 13).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List

from .config import ScenarioConfig


def _scn(**kw) -> ScenarioConfig:
    return ScenarioConfig(**kw)


# --------------------------------------------------------------------------- #
# The library
# --------------------------------------------------------------------------- #
SCENARIO_LIBRARY: Dict[str, ScenarioConfig] = {}


def _register(scn: ScenarioConfig) -> None:
    SCENARIO_LIBRARY[scn.scenario_id] = scn


_register(_scn(
    scenario_id="S01_baseline_clear",
    title="Baseline — clear weather, 3 targets",
    description="Reference mission: three cooperative UAVs, clear sky, no faults.",
    duration_s=120.0, n_targets=3,
    uav_classes=["multirotor", "fpv", "fixedwing"],
    trajectory_kinds=["orbit", "ingress", "lemniscate"],
    weather="clear", lab="ЛР-3", tags=["baseline", "fusion"],
))

_register(_scn(
    scenario_id="S02_time_calibration",
    title="Time calibration stress (clock drift)",
    description="Exaggerated sensor clock drift to exercise ЛР-1 calibration.",
    duration_s=150.0, n_targets=2,
    uav_classes=["multirotor", "fixedwing"],
    trajectory_kinds=["orbit", "orbit"],
    weather="clear", lab="ЛР-1", tags=["clock", "sync"],
))

_register(_scn(
    scenario_id="S03_multitarget_crossing",
    title="Multi-target crossing (ID-switch stress)",
    description="Trajectories forced to cross near the origin (ЛР-4).",
    duration_s=140.0, n_targets=4,
    uav_classes=["multirotor", "multirotor", "fpv", "fpv"],
    trajectory_kinds=["lemniscate", "lemniscate", "orbit", "ingress"],
    crossing=True, weather="clear", lab="ЛР-4", tags=["tracking", "association"],
))

_register(_scn(
    scenario_id="S04_sensor_dropout",
    title="Fault tolerance — radar dropout",
    description="Radar goes dark 50–90 s; fusion must coast on passive sensors.",
    duration_s=140.0, n_targets=3,
    uav_classes=["multirotor", "fpv", "fixedwing"],
    trajectory_kinds=["orbit", "ingress", "orbit"],
    faults=[{"kind": "sensor_dropout", "sensor": "RAD-1", "t0": 50.0, "t1": 90.0}],
    weather="clear", lab="ЛР-5", tags=["faults", "robustness"],
))

_register(_scn(
    scenario_id="S05_packet_loss",
    title="Fault tolerance — network packet loss",
    description="30% global packet loss between 40 s and 100 s.",
    duration_s=140.0, n_targets=3,
    uav_classes=["multirotor", "fpv", "fixedwing"],
    trajectory_kinds=["orbit", "lemniscate", "ingress"],
    faults=[{"kind": "packet_loss", "global": True, "prob": 0.3, "t0": 40.0, "t1": 100.0}],
    weather="clear", lab="ЛР-5", tags=["faults", "network"],
))

_register(_scn(
    scenario_id="S06_domain_rain",
    title="Domain shift — heavy rain",
    description="Rain profile lowers Pd and raises noise/clutter (ЛР-6).",
    duration_s=130.0, n_targets=3,
    uav_classes=["multirotor", "fpv", "fixedwing"],
    trajectory_kinds=["orbit", "ingress", "lemniscate"],
    weather="rain", lab="ЛР-6", tags=["domain", "weather"],
))

_register(_scn(
    scenario_id="S07_domain_night",
    title="Domain shift — night operations",
    description="Night profile: EO degraded, RF/radar relatively better (ЛР-6).",
    duration_s=130.0, n_targets=3,
    uav_classes=["multirotor", "silent_glider", "fpv"],
    trajectory_kinds=["orbit", "orbit", "ingress"],
    weather="night", lab="ЛР-6", tags=["domain", "weather"],
))

_register(_scn(
    scenario_id="S08_redteam_spoof",
    title="Red-team — spoofed telemetry",
    description="Injected false detections near true targets (section 5 red-team).",
    duration_s=140.0, n_targets=3,
    uav_classes=["multirotor", "fpv", "fixedwing"],
    trajectory_kinds=["orbit", "ingress", "lemniscate"],
    faults=[{"kind": "spoof", "sensor": "RAD-1", "t0": 30.0, "t1": 110.0,
             "count": 60, "offset_m": 60.0}],
    red_team=["spoofed_telemetry"], weather="haze", lab="ЛР-5", tags=["redteam", "security"],
))

_register(_scn(
    scenario_id="S09_swarm_dense",
    title="Dense swarm — 6 targets",
    description="Six mixed-class UAVs, high clutter — capacity stress.",
    duration_s=150.0, n_targets=6,
    uav_classes=["multirotor", "fpv", "fixedwing", "multirotor", "fpv", "silent_glider"],
    trajectory_kinds=["orbit", "ingress", "lemniscate", "orbit", "hover_dash", "orbit"],
    crossing=True, clutter_scale=1.6, weather="haze", lab="ЛР-4", tags=["swarm", "capacity"],
))

_register(_scn(
    scenario_id="S10_degradation",
    title="Sensor degradation — EO noise burst",
    description="EO camera noise inflated 3x between 60–110 s (ЛР-5).",
    duration_s=140.0, n_targets=3,
    uav_classes=["multirotor", "fpv", "fixedwing"],
    trajectory_kinds=["orbit", "ingress", "orbit"],
    faults=[{"kind": "degradation", "sensor": "EO-1", "t0": 60.0, "t1": 110.0,
             "noise_scale": 3.0}],
    weather="clear", lab="ЛР-5", tags=["faults", "degradation"],
))

_register(_scn(
    scenario_id="S11_silent_glider",
    title="Low-observable silent glider",
    description="Non-RF-emitting platform invisible to SDR — fusion must rely on radar/EO.",
    duration_s=140.0, n_targets=3,
    uav_classes=["silent_glider", "multirotor", "fpv"],
    trajectory_kinds=["ingress", "orbit", "lemniscate"],
    weather="clear", lab="ЛР-2", tags=["low_observable"],
))

_register(_scn(
    scenario_id="S12_calibration_focus",
    title="Uncertainty calibration mission",
    description="Mixed difficulty to populate the reliability diagram (ЛР-7).",
    duration_s=160.0, n_targets=4,
    uav_classes=["multirotor", "fpv", "fixedwing", "silent_glider"],
    trajectory_kinds=["orbit", "ingress", "lemniscate", "hover_dash"],
    weather="haze", lab="ЛР-7", tags=["calibration"],
))


# --------------------------------------------------------------------------- #
# Access helpers
# --------------------------------------------------------------------------- #
def list_scenarios() -> List[str]:
    return list(SCENARIO_LIBRARY)


def build_scenario(scenario_id: str) -> ScenarioConfig:
    if scenario_id not in SCENARIO_LIBRARY:
        raise KeyError(
            f"unknown scenario {scenario_id!r}; available: {list(SCENARIO_LIBRARY)}"
        )
    import copy
    return copy.deepcopy(SCENARIO_LIBRARY[scenario_id])


def scenarios_for_lab(lab: str) -> List[ScenarioConfig]:
    return [s for s in SCENARIO_LIBRARY.values() if s.lab == lab]
