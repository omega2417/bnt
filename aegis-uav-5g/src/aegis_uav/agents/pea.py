"""Policy Enforcement Agent (PEA).

Applies the selected response to the simulator state, verifies a post-condition,
and records success/failure/rollback/escalation with enforcement latency.
"""

from __future__ import annotations

from ..rng import SeededRng
from ..schemas import PEAConfig
from .base import BaseAgent

__all__ = ["PolicyEnforcementAgent"]

# Nominal post-condition success probability per response (simulation model).
_SUCCESS_PROB = {
    "traffic_isolation": 0.95,
    "route_reconfiguration": 0.9,
    "session_termination": 0.97,
    "credential_revocation": 0.93,
    "secure_channel_migration": 0.88,
    "escalate": 1.0,
}


class PolicyEnforcementAgent(BaseAgent):
    name = "pea"

    def __init__(self, config: PEAConfig, seed: int = 0, deterministic: bool = True) -> None:
        super().__init__(config, seed, deterministic)
        self._rng = SeededRng(seed).spawn("pea")

    def enforce(self, response: str, incident_id: str) -> dict:
        cfg: PEAConfig = self.config
        latency_ms = cfg.enforcement_latency_ms
        if response == "escalate":
            return {"status": "escalation", "attempts": 0, "latency_ms": latency_ms,
                    "post_condition_ok": True, "rolled_back": False}

        p = _SUCCESS_PROB.get(response, 0.9)
        attempts = 0
        rolled_back = False
        status = "failed"
        for attempt in range(cfg.max_retries + 1):
            attempts += 1
            ok = bool(self._rng.uniform() < p)
            if ok:
                status = "success"
                break
            if attempt < cfg.max_retries:
                rolled_back = True  # rollback then retry
                latency_ms += cfg.enforcement_latency_ms
        if status != "success":
            status = "escalation"  # exhausted retries -> escalate to operator
            rolled_back = True
        return {
            "status": status,
            "attempts": attempts,
            "latency_ms": latency_ms,
            "post_condition_ok": status == "success",
            "rolled_back": rolled_back,
        }
