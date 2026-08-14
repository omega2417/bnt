"""Common agent scaffolding: I/O contract, logging, deterministic mode, config
versioning and explanation hooks (prompt §agents)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..logging_utils import get_logger

__all__ = ["BaseAgent", "AgentResult"]


@dataclass
class AgentResult:
    """Standard agent output envelope."""

    agent: str
    outputs: dict[str, Any] = field(default_factory=dict)
    explanation: dict[str, Any] = field(default_factory=dict)


class BaseAgent:
    """Base class giving every agent a name, logger, deterministic seed and a
    versioned config fingerprint."""

    name: str = "agent"

    def __init__(self, config: Any, seed: int = 0, deterministic: bool = True) -> None:
        self.config = config
        self.seed = seed
        self.deterministic = deterministic
        self.logger = get_logger(self.name)

    def config_version(self) -> str:
        from ..config import config_hash

        return config_hash(self.config)

    def _explain(self, **fields: Any) -> dict[str, Any]:
        return dict(fields)
