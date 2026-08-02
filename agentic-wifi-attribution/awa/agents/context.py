"""Shared blackboard passed between agents, plus SOC decision tiers."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any, Dict, List, Optional

import numpy as np

from ..config import PlatformConfig
from ..localization.grid import Grid
from ..localization.radiomap import RadioMap
from ..site import Site
from ..telemetry.quality import IncidentWindow


class DecisionTier(IntEnum):
    """SOC decision tiers (prompt Module 13)."""

    LOG_ONLY = 0
    OBSERVE = 1
    ENRICH = 2
    VERIFY = 3
    HUMAN_IN_THE_LOOP = 4
    LIMITED_CONTAINMENT = 5
    FULL_CONTAINMENT = 6


DECISION_TIER_NAMES = {t.value: t.name for t in DecisionTier}


@dataclass
class AgentContext:
    """Mutable blackboard threaded through the agent pipeline."""

    cfg: PlatformConfig
    site: Site
    grid: Grid
    radiomap: RadioMap
    twin: Any                        # DigitalTwin (avoid import cycle)
    sample: Any                      # TelemetrySample

    # Populated by agents as they run:
    incident: Optional[IncidentWindow] = None
    posterior: Optional[np.ndarray] = None
    rssi_posterior: Optional[np.ndarray] = None
    ftm_posterior: Optional[np.ndarray] = None
    sensor_contributions: Dict[str, float] = field(default_factory=dict)
    used_modalities: List[str] = field(default_factory=list)
    missing_modalities: List[str] = field(default_factory=list)
    uncertainty: Dict[str, Any] = field(default_factory=dict)
    drift_state: Dict[str, Any] = field(default_factory=dict)
    consistency: Dict[str, Any] = field(default_factory=dict)
    threat_state: Dict[str, Any] = field(default_factory=dict)
    verification_plan: Dict[str, Any] = field(default_factory=dict)
    readiness_profile: Dict[str, Any] = field(default_factory=dict)
    decision: Dict[str, Any] = field(default_factory=dict)
    sar: Dict[str, Any] = field(default_factory=dict)

    audit_log: List[Dict[str, Any]] = field(default_factory=list)

    def log(self, agent: str, message: str, **data: Any) -> None:
        """Append-only audit entry (prompt Module 16)."""
        self.audit_log.append(
            {"agent": agent, "message": message, "data": data}
        )
