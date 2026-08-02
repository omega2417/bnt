"""Mission timeline and fleet mobility (discrete-time waypoint model)."""

from __future__ import annotations

import numpy as np

from ..rng import SeededRng
from ..schemas import ScenarioConfig

__all__ = ["build_timeline", "phase_per_step", "simulate_positions"]


def build_timeline(scenario: ScenarioConfig) -> np.ndarray:
    n_steps = int(round(scenario.mission_duration_s / scenario.export_period_s))
    return np.arange(n_steps, dtype=float) * scenario.export_period_s


def phase_per_step(scenario: ScenarioConfig, n_steps: int) -> np.ndarray:
    """Assign each timestep to a mission phase (takeoff/transit/loiter/return)."""
    phases = scenario.phases
    boundaries = np.cumsum([p.fraction for p in phases]) * n_steps
    out = np.empty(n_steps, dtype=object)
    start = 0
    for phase, end in zip(phases, boundaries, strict=True):
        end_i = int(round(end))
        out[start:end_i] = phase.name
        start = end_i
    out[start:] = phases[-1].name
    return out


def simulate_positions(
    scenario: ScenarioConfig, n_steps: int, rng: SeededRng
) -> dict[str, np.ndarray]:
    """Simulate smooth per-UAV trajectories inside the mission area.

    Returns arrays shaped ``(n_uav, n_steps)`` for the true kinematic state.
    """
    n = scenario.fleet_size
    area = scenario.area_size_m
    gen = rng.generator

    # Each UAV holds a slot in a loose formation and drifts around a waypoint.
    home = gen.uniform(-area / 2, area / 2, size=(n, 2))
    waypoint = gen.uniform(-area / 2, area / 2, size=(n, 2))
    altitude_target = gen.uniform(60, 140, size=n)

    pos = np.zeros((n, n_steps, 3))
    vel = np.zeros((n, n_steps, 3))
    for k in range(n_steps):
        frac = k / max(n_steps - 1, 1)
        # Interpolate horizontally home -> waypoint -> home (there and back).
        tri = 1.0 - abs(2.0 * frac - 1.0)
        target_xy = home + (waypoint - home) * tri
        jitter = gen.normal(0, 1.5, size=(n, 2))
        pos[:, k, :2] = target_xy + jitter
        pos[:, k, 2] = altitude_target * min(frac * 6, 1.0) + gen.normal(0, 0.5, size=n)
        if k > 0:
            vel[:, k, :] = (pos[:, k, :] - pos[:, k - 1, :]) / scenario.export_period_s

    return {"position": pos, "velocity": vel, "home": home}
