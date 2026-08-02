"""Attack engine: controlled, *simulation-only* injection of T1-T6.

This module perturbs synthetic signals to emulate the observable effects of the
six attack classes and emits ground-truth labels.  It contains **no** operational
instructions for compromising real UAVs; every effect is a numeric perturbation
of a synthetic array used solely for training/evaluating the defence.
"""

from __future__ import annotations

import numpy as np

from ..rng import SeededRng
from ..schemas import AttackConfig, ScenarioConfig

__all__ = ["apply_attack", "AttackGroundTruth"]


class AttackGroundTruth:
    """Per-(uav, step) ground-truth produced by an injected attack."""

    def __init__(self, n_uav: int, n_steps: int) -> None:
        self.label = np.full((n_uav, n_steps), "benign", dtype=object)
        self.is_attack = np.zeros((n_uav, n_steps), dtype=bool)
        self.origin = np.full((n_uav, n_steps), "", dtype=object)
        self.onset = np.full((n_uav, n_steps), np.nan)
        self.intensity = np.zeros((n_uav, n_steps))
        self.mission_impact = np.zeros((n_uav, n_steps), dtype=bool)


def _time_profile(profile: str, onset_i: int, end_i: int, n_steps: int) -> np.ndarray:
    """Return a per-step intensity envelope in ``[0, 1]`` over the attack window."""
    env = np.zeros(n_steps)
    length = max(end_i - onset_i, 1)
    idx = np.arange(onset_i, min(end_i, n_steps))
    local = (idx - onset_i) / length
    if profile == "gradual":
        env[idx] = local
    elif profile == "sudden":
        env[idx] = 1.0
    elif profile == "burst":
        env[idx] = (np.sin(local * np.pi * 6) > 0).astype(float)
    else:
        env[idx] = 1.0
    return env


def apply_attack(
    scenario: ScenarioConfig,
    attack: AttackConfig,
    tel: dict[str, np.ndarray],
    net: dict[str, np.ndarray],
    beh: dict[str, np.ndarray],
    n_steps: int,
    rng: SeededRng,
) -> AttackGroundTruth:
    """Mutate signal dicts in place and return the ground-truth record."""
    n = scenario.fleet_size
    gt = AttackGroundTruth(n, n_steps)
    if not attack.enabled:
        return gt

    dt = scenario.export_period_s
    onset_i = int(round(attack.onset_s / dt))
    end_i = int(round((attack.onset_s + attack.duration_s) / dt))
    env = _time_profile(attack.profile, onset_i, end_i, n_steps)  # (n_steps,)
    active = env > 0
    targets = [t for t in attack.target_uavs if 0 <= t < n] or [0]
    origin = f"uav_{targets[0]:02d}"
    scale = attack.intensity

    # Impact reached at 60% through the attack duration for still-active windows.
    impact_i = onset_i + int(0.6 * (end_i - onset_i))

    for u in targets:
        e = env * scale  # per-step perturbation magnitude for this UAV
        mask = active
        gt.label[u, mask] = attack.id
        gt.is_attack[u, mask] = True
        gt.origin[u, mask] = origin
        gt.onset[u, mask] = attack.onset_s
        gt.intensity[u, mask] = attack.intensity
        gt.mission_impact[u, impact_i:end_i] = True

        _inject_effects(attack.id, e, u, tel, net, beh, rng)

    return gt


def _inject_effects(
    attack_id: str,
    e: np.ndarray,
    u: int,
    tel: dict[str, np.ndarray],
    net: dict[str, np.ndarray],
    beh: dict[str, np.ndarray],
    rng: SeededRng,
) -> None:
    gen = rng.generator
    ns = e.shape[0]

    def noise(sd: float) -> np.ndarray:
        return gen.normal(0, sd, size=ns)

    if attack_id == "T1":  # GPS spoofing -> GNSS position/quality deviation
        drift = e * (60.0 + noise(3.0))
        tel["gnss_reported_x"][u] += drift
        tel["gnss_reported_y"][u] += 0.6 * drift
        tel["gnss_residual"][u] += e * (15.0 + np.abs(noise(2.0)))
        tel["hdop"][u] += e * 2.5
        tel["vdop"][u] += e * 2.5
        tel["gnss_sat_count"][u] -= e * 4.0

    elif attack_id == "T2":  # C2 hijacking / command injection
        beh["command_rate"][u] += e * (8.0 + np.abs(noise(1.0)))
        beh["unauthorised_command_count"][u] += e * 4.0
        beh["unusual_command_sequence_score"][u] = np.clip(
            beh["unusual_command_sequence_score"][u] + e * 0.8, 0, 1
        )
        beh["unexpected_operator"][u] = np.maximum(beh["unexpected_operator"][u], (e > 0.3))
        beh["session_origin_change"][u] = np.maximum(
            beh["session_origin_change"][u], (e > 0.4)
        )

    elif attack_id == "T3":  # DoS
        factor = 1.0 + e * 6.0
        net["packets_per_second"][u] *= factor
        net["packets_in"][u] *= factor
        net["packets_out"][u] *= factor
        net["bytes_per_second"][u] *= factor
        net["packet_loss"][u] = np.clip(net["packet_loss"][u] + e * 0.4, 0, 1)
        net["rtt"][u] += e * 120.0
        net["jitter"][u] += e * 25.0
        net["failed_connections"][u] += e * 8.0

    elif attack_id == "T4":  # Malicious routing / blackhole / grayhole
        net["route_changes"][u] += e * 10.0
        net["routing_control_rate"][u] += e * 8.0
        net["neighbour_churn"][u] += e * 0.6
        net["packet_loss"][u] = np.clip(net["packet_loss"][u] + e * 0.5, 0, 1)
        net["retransmission_rate"][u] = np.clip(net["retransmission_rate"][u] + e * 0.4, 0, 1)

    elif attack_id == "T5":  # Lateral movement
        net["source_fanout"][u] += e * 20.0
        net["destination_fanout"][u] += e * 25.0
        net["failed_connections"][u] += e * 15.0
        beh["authentication_failures"][u] += e * 10.0
        beh["privilege_escalation_count"][u] += e * 3.0
        beh["session_establishment_rate"][u] += e * 1.0

    elif attack_id == "T6":  # Compromised GCS
        beh["gcs_fanout"][u] += e * 12.0
        beh["command_rate"][u] += e * 5.0
        beh["credential_changes"][u] += e * 2.0
        beh["unexpected_operator"][u] = np.maximum(beh["unexpected_operator"][u], (e > 0.3))
        beh["session_origin_change"][u] = np.maximum(
            beh["session_origin_change"][u], (e > 0.3)
        )
