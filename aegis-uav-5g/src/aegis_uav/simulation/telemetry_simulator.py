"""Telemetry-modality raw signal generator."""

from __future__ import annotations

import numpy as np

from ..rng import SeededRng
from ..schemas import ScenarioConfig

__all__ = ["simulate_telemetry"]


def simulate_telemetry(
    scenario: ScenarioConfig,
    positions: dict[str, np.ndarray],
    n_steps: int,
    rng: SeededRng,
) -> dict[str, np.ndarray]:
    n = scenario.fleet_size
    tel = scenario.telemetry
    gen = rng.generator
    pos = positions["position"]
    vel = positions["velocity"]

    accel = np.zeros_like(vel)
    accel[:, 1:, :] = np.diff(vel, axis=1) / scenario.export_period_s

    roll = gen.normal(0, 3, size=(n, n_steps))
    pitch = gen.normal(0, 3, size=(n, n_steps))
    yaw = np.cumsum(gen.normal(0, 1.0, size=(n, n_steps)), axis=1) % 360
    yaw_rate = np.zeros((n, n_steps))
    yaw_rate[:, 1:] = np.diff(yaw, axis=1)

    sat = np.clip(gen.normal(tel.gnss_satellites, 1.0, size=(n, n_steps)), 5, 20)
    hdop = np.clip(gen.normal(tel.gnss_hdop, 0.15, size=(n, n_steps)), 0.4, 5.0)
    vdop = np.clip(gen.normal(tel.gnss_hdop * 1.3, 0.2, size=(n, n_steps)), 0.5, 6.0)
    gnss_residual = np.abs(gen.normal(0, tel.gnss_noise_m, size=(n, n_steps)))

    # True vs GNSS-reported horizontal position (spoofing modifies the reported).
    gnss_reported = pos[:, :, :2] + gen.normal(0, tel.gnss_noise_m, size=(n, n_steps, 2))

    battery = np.clip(
        100.0 - np.cumsum(np.full((n, n_steps), tel.battery_drain_per_s), axis=1)
        + gen.normal(0, 0.2, size=(n, n_steps)),
        0,
        100,
    )
    rssi = gen.normal(tel.rssi_dbm_mean, 3.0, size=(n, n_steps))
    sinr = gen.normal(tel.sinr_db_mean, 2.0, size=(n, n_steps))

    return {
        "position_x": pos[:, :, 0],
        "position_y": pos[:, :, 1],
        "position_z": pos[:, :, 2],
        "velocity_x": vel[:, :, 0],
        "velocity_y": vel[:, :, 1],
        "velocity_z": vel[:, :, 2],
        "accel_x": accel[:, :, 0],
        "accel_y": accel[:, :, 1],
        "accel_z": accel[:, :, 2],
        "roll": roll,
        "pitch": pitch,
        "yaw": yaw,
        "yaw_rate": yaw_rate,
        "gnss_sat_count": sat,
        "hdop": hdop,
        "vdop": vdop,
        "gnss_residual": gnss_residual,
        "gnss_reported_x": gnss_reported[:, :, 0],
        "gnss_reported_y": gnss_reported[:, :, 1],
        "battery": battery,
        "rssi": rssi,
        "sinr": sinr,
    }
