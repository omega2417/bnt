"""Behaviour/session-modality raw signal generator."""

from __future__ import annotations

import numpy as np

from ..rng import SeededRng
from ..schemas import ScenarioConfig

__all__ = ["simulate_behaviour"]


def simulate_behaviour(
    scenario: ScenarioConfig, n_steps: int, rng: SeededRng
) -> dict[str, np.ndarray]:
    n = scenario.fleet_size
    beh = scenario.behaviour
    gen = rng.generator

    command_rate = np.clip(gen.normal(beh.command_rate, 0.4, size=(n, n_steps)), 0, None)
    command_type = gen.integers(0, 4, size=(n, n_steps))  # entropy computed in features
    unauthorised_cmd = gen.poisson(0.02, size=(n, n_steps)).astype(float)
    session_establish = np.clip(gen.normal(beh.session_rate, 0.02, size=(n, n_steps)), 0, None)
    session_terminate = np.clip(gen.normal(beh.session_rate, 0.02, size=(n, n_steps)), 0, None)
    auth_failures = gen.poisson(beh.auth_failure_rate, size=(n, n_steps)).astype(float)
    credential_changes = gen.poisson(0.005, size=(n, n_steps)).astype(float)
    gcs_fanout = np.clip(gen.normal(1.0, 0.2, size=(n, n_steps)), 0, None)
    unexpected_operator = (gen.uniform(0, 1, size=(n, n_steps)) < 0.01).astype(float)
    unusual_cmd_seq = np.clip(gen.normal(0.1, 0.05, size=(n, n_steps)), 0, 1)
    session_origin_change = (gen.uniform(0, 1, size=(n, n_steps)) < 0.01).astype(float)
    privilege_escalation = gen.poisson(0.003, size=(n, n_steps)).astype(float)

    return {
        "command_rate": command_rate,
        "command_type_code": command_type.astype(float),
        "unauthorised_command_count": unauthorised_cmd,
        "session_establishment_rate": session_establish,
        "session_termination_rate": session_terminate,
        "authentication_failures": auth_failures,
        "credential_changes": credential_changes,
        "gcs_fanout": gcs_fanout,
        "unexpected_operator": unexpected_operator,
        "unusual_command_sequence_score": unusual_cmd_seq,
        "session_origin_change": session_origin_change,
        "privilege_escalation_count": privilege_escalation,
    }
