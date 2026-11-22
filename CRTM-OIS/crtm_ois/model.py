"""Data model: metric descriptors, basic actions, assessment configuration.

The notation follows CRTM (Korchenko et al., Information 2026, 17, 1170):
a threat scenario theta projects the CREF hierarchy onto admissible basic
actions beta, each carrying a tuple of metric descriptors M(beta).
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Optional

GOALS: tuple[str, ...] = ("ANT", "WITH", "REC", "AD")
GOAL_NAMES = {"ANT": "Anticipate", "WITH": "Withstand", "REC": "Recover", "AD": "Adapt"}


@dataclass(frozen=True)
class Metric:
    """Metric descriptor of CRTM.

    xi      printed class table as six numbers (critical anchor, four class
            boundaries, ideal anchor) in physical units;
    sigma   +1 larger is better, -1 smaller is better;
    core    core metric (member of K_beta) with cap threshold theta;
    step    resolution of a discrete metric (None = continuous);
    source  identifier of the physical measurement (several metrics may share it).
    """
    code: str
    name: str
    unit: str
    xi: tuple[float, float, float, float, float, float]
    sigma: int
    weight: float
    core: bool = False
    step: Optional[float] = None
    timing: str = "after"
    techniques: tuple[str, ...] = ()
    source: str = ""

    @property
    def anchors(self) -> tuple[float, ...]:
        """Anchors eta_r = sigma * xi_r in quality coordinates."""
        return tuple(self.sigma * v for v in self.xi)

    @property
    def x_ideal(self) -> float:
        return self.xi[5]

    @property
    def x_critical(self) -> float:
        return self.xi[0]


@dataclass(frozen=True)
class BasicAction:
    code: str
    name: str
    goal: str
    task: str
    metrics: tuple[Metric, ...]

    @property
    def q(self) -> int:
        return len(self.metrics)


@dataclass
class Configuration:
    """Assessment policy fixed in Stage 1 (B1) before data are collected."""
    scenario: str
    threat: str
    actions: tuple[BasicAction, ...]
    theta: float = 0.5
    operator: str = "capped"          # capped | hard | additive
    goal_weights: dict = field(default_factory=lambda: {g: 0.25 for g in GOALS})
    rho: float = 1.0
    n_samples: int = 200_000
    seed: int = 20261122
    breakpoints: tuple[float, ...] = (0.0, 0.2, 0.4, 0.7, 0.9, 1.0)

    @property
    def goals(self) -> tuple[str, ...]:
        return tuple(g for g in GOALS if any(a.goal == g for a in self.actions))

    def actions_of(self, goal: str) -> list[BasicAction]:
        return [a for a in self.actions if a.goal == goal]

    def action(self, code: str) -> BasicAction:
        for a in self.actions:
            if a.code == code:
                return a
        raise KeyError(code)

    @property
    def n_metrics(self) -> int:
        return sum(a.q for a in self.actions)

    def keys(self) -> list[tuple[str, str]]:
        return [(a.code, m.code) for a in self.actions for m in a.metrics]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["actions"] = [asdict(a) for a in self.actions]
        return d

    @property
    def version(self) -> str:
        """Configuration version: short hash of the policy (not of the data)."""
        payload = json.dumps(self.to_dict(), sort_keys=True, default=str)
        return "cfg-" + hashlib.sha256(payload.encode()).hexdigest()[:12]

    def replace(self, **kw) -> "Configuration":
        d = {k: getattr(self, k) for k in (
            "scenario", "threat", "actions", "theta", "operator", "goal_weights",
            "rho", "n_samples", "seed", "breakpoints")}
        d.update(kw)
        return Configuration(**d)
