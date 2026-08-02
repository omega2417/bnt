"""Scenario engine: run one mission (benign or with one injected attack)."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from ..attacks.attack_engine import apply_attack
from ..rng import SeededRng
from ..schemas import AttackConfig, ScenarioConfig
from .behaviour_simulator import simulate_behaviour
from .mobility import build_timeline, phase_per_step, simulate_positions
from .network_simulator import simulate_network
from .telemetry_simulator import simulate_telemetry

__all__ = ["MissionData", "simulate_mission"]


@dataclass
class MissionData:
    scenario_id: str
    run_id: str
    seed: int
    attack_label: str  # dominant attack class of the mission ("benign" if none)
    frame: pd.DataFrame  # long format: one row per (uav, timestep)


def simulate_mission(
    scenario: ScenarioConfig,
    attack: AttackConfig | None,
    seed: int,
    mission_index: int,
    split: str | None = None,
) -> MissionData:
    """Simulate a single mission and return a long-format DataFrame.

    ``attack=None`` produces an attack-free control mission.
    """
    rng = SeededRng(seed).spawn(f"mission-{mission_index}")
    n_steps = int(round(scenario.mission_duration_s / scenario.export_period_s))
    n = scenario.fleet_size

    timeline = build_timeline(scenario)
    phases = phase_per_step(scenario, n_steps)
    positions = simulate_positions(scenario, n_steps, rng.spawn("mobility"))
    tel = simulate_telemetry(scenario, positions, n_steps, rng.spawn("telemetry"))
    net = simulate_network(scenario, n_steps, rng.spawn("network"))
    beh = simulate_behaviour(scenario, n_steps, rng.spawn("behaviour"))

    if attack is not None and attack.enabled:
        gt = apply_attack(scenario, attack, tel, net, beh, n_steps, rng.spawn("attack"))
        dominant = attack.id
    else:
        from ..attacks.attack_engine import AttackGroundTruth

        gt = AttackGroundTruth(n, n_steps)
        dominant = "benign"

    scenario_id = f"{scenario.name}_{dominant}_m{mission_index:03d}_s{seed}"
    run_id = scenario_id

    # Flatten (n_uav, n_steps) arrays into a long DataFrame.
    signals: dict[str, np.ndarray] = {**tel, **net, **beh}
    n_rows = n * n_steps
    uav_ids = np.repeat(np.arange(n), n_steps)
    ts = np.tile(timeline, n)
    phase_col = np.tile(phases, n)

    data: dict[str, np.ndarray] = {
        "scenario_id": np.full(n_rows, scenario_id, dtype=object),
        "run_id": np.full(n_rows, run_id, dtype=object),
        "seed": np.full(n_rows, seed),
        "timestamp": ts,
        "uav_id": np.array([f"uav_{u:02d}" for u in uav_ids], dtype=object),
        "uav_index": uav_ids,
        "mission_phase": phase_col,
        "attack_label": gt.label.reshape(-1),
        "attack_origin": gt.origin.reshape(-1),
        "attack_onset": gt.onset.reshape(-1),
        "attack_intensity": gt.intensity.reshape(-1),
        "is_attack": gt.is_attack.reshape(-1),
        "mission_impact": gt.mission_impact.reshape(-1),
        "split": np.full(n_rows, split if split else "", dtype=object),
    }
    for name, arr in signals.items():
        data[name] = arr.reshape(-1)

    frame = pd.DataFrame(data)
    return MissionData(
        scenario_id=scenario_id,
        run_id=run_id,
        seed=seed,
        attack_label=dominant,
        frame=frame,
    )
