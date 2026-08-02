"""Response Selection Agent (RSA).

Transparent utility policy U(r|E) = B(r,â) − λ₁·C(r) − λ₂·D(r) (Eq. 6) with a
safety mask R_safe and a confidence floor π_min (Eq. 7).  No reinforcement
learning: the policy is expert-parameterised and fully auditable.
"""

from __future__ import annotations

from ..config import load_yaml
from ..schemas import RSAConfig
from .base import BaseAgent

__all__ = ["ResponseSelectionAgent", "RESPONSES"]

RESPONSES = [
    "traffic_isolation",
    "route_reconfiguration",
    "session_termination",
    "credential_revocation",
    "secure_channel_migration",
    "escalate",
]


class ResponseSelectionAgent(BaseAgent):
    name = "rsa"

    def __init__(self, config: RSAConfig, seed: int = 0, deterministic: bool = True) -> None:
        super().__init__(config, seed, deterministic)
        policy = load_yaml(config.policy_file)
        self._levels = policy["level_values"]
        self._benefit = policy["benefit"]
        self._cost = policy["cost"]
        self._disruption = policy["disruption"]
        self._forbidden = policy.get("forbidden", {})
        self._static = policy["static_policy"]

    def benefit(self, response: str, attack: str) -> float:
        level = self._benefit.get(attack, {}).get(response, "low")
        return float(self._levels[level])

    def safe_actions(self, attack: str, use_mask: bool = True) -> list[str]:
        if not use_mask:
            return list(RESPONSES)
        forbidden = set(self._forbidden.get(attack, []))
        return [r for r in RESPONSES if r not in forbidden]

    def select(
        self, attack: str, confidence: float, use_mask: bool = True
    ) -> dict:
        """Select the utility-maximising safe response, or escalate below π_min."""
        cfg: RSAConfig = self.config
        if attack == "benign":
            return {"selected": "escalate", "runner_up": None, "utility_terms": {},
                    "safe_actions": ["escalate"], "reason": "no_attack"}
        if confidence < cfg.pi_min:
            return {"selected": "escalate", "runner_up": None, "utility_terms": {},
                    "safe_actions": self.safe_actions(attack, use_mask),
                    "reason": "below_confidence_floor"}

        safe = self.safe_actions(attack, use_mask)
        utilities: dict[str, dict[str, float]] = {}
        for r in safe:
            b = self.benefit(r, attack)
            c = float(self._cost[r])
            d = float(self._disruption[r])
            u = b - cfg.lambda1 * c - cfg.lambda2 * d
            utilities[r] = {"benefit": b, "cost": c, "disruption": d, "utility": u}
        ranked = sorted(utilities, key=lambda r: utilities[r]["utility"], reverse=True)
        return {
            "selected": ranked[0],
            "runner_up": ranked[1] if len(ranked) > 1 else None,
            "utility_terms": utilities,
            "safe_actions": safe,
            "reason": "utility_max",
        }

    def static_select(self, attack: str) -> dict:
        """Baseline B4: fixed attack -> response map (no utility reasoning)."""
        selected = self._static.get(attack, "escalate")
        return {"selected": selected, "runner_up": None, "utility_terms": {},
                "safe_actions": [selected], "reason": "static_policy"}
