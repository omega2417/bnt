"""Synthetic SME archetypes and the designed business-change catalog.

Encodes Table 4 (scenario inputs), Table A2 (event catalog and capability-demand
increments) and the base-demand rows of Table A3.

No real SME, employee, customer, supplier or incident is represented.  The
staff counts, budgets, technology combinations, demands and timings are
stress-test design values and must not be interpreted as estimated
distributions in the SME population.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Dict, Mapping, Sequence, Tuple

from .capabilities import CODES

#: Version of the scenario pack (R7).
SCENARIO_PACK_VERSION = "scenario-pack-0.1.0"

#: Horizon of one trace, in daily decision windows.
HORIZON_DAYS = 120

#: Capability demand is capped after event accumulation (Table A2 note).
DEMAND_CAP = 1.75


@dataclass(frozen=True)
class Event:
    """One labelled material business change."""

    day: int
    name: str
    increments: Mapping[str, float]

    def proxy_score_base(self) -> float:
        """Deterministic part of the event-score proxy of Section 3.7.

        ``s = sqrt(sum of squared demand increments / number of increments)``
        The Gaussian nuisance term is added by the simulator, not here.
        """
        values = list(self.increments.values())
        return sqrt(sum(v * v for v in values) / len(values))

    def targets(self) -> Tuple[str, ...]:
        """Capabilities whose demand this event raises (adaptation-delay targets)."""
        return tuple(self.increments)


@dataclass(frozen=True)
class Archetype:
    """A designed SME scenario (Table 4)."""

    key: str
    label: str
    staff: int
    budget: int
    exposure: str
    base_demand: Mapping[str, float]
    events: Tuple[Event, ...]

    def demand_at(self, day: int) -> Dict[str, float]:
        """True capability-demand vector r(c, t) on ``day``.

        Demand starts at the archetype base, accumulates the increment of every
        event whose day has arrived, and is capped at ``DEMAND_CAP``.
        """
        demand = {code: float(self.base_demand.get(code, 0.0)) for code in CODES}
        for event in self.events:
            if event.day <= day:
                for code, delta in event.increments.items():
                    demand[code] = min(DEMAND_CAP, demand[code] + delta)
        return demand


def _demand(**values: float) -> Dict[str, float]:
    unknown = set(values) - set(CODES)
    if unknown:
        raise ValueError(f"unknown capability codes: {sorted(unknown)}")
    return {code: float(values.get(code, 0.0)) for code in CODES}


MICRO = Archetype(
    key="micro",
    label="Micro retail",
    staff=8,
    budget=34,
    exposure="XR storefront, cloud identity, AI service",
    base_demand=_demand(
        GOV=0.65, AST=0.75, IAM=0.85, DAT=0.90, CFG=0.70, IR=0.55, REC=0.60, TRN=0.55
    ),
    events=(
        Event(20, "Cloud point-of-sale migration", {"CLD": 0.95, "TPR": 0.65, "IAM": 0.35}),
        Event(45, "Immersive storefront", {"XRI": 1.15, "DAT": 0.45, "IAM": 0.35}),
        Event(72, "Credential-stuffing incident", {"DET": 1.20, "IR": 0.60, "REC": 0.35}),
        Event(96, "Generative-AI sales assistant", {"AIG": 1.05, "GOV": 0.35, "DAT": 0.45}),
    ),
)

SMALL = Archetype(
    key="small",
    label="Small manufacturer",
    staff=46,
    budget=45,
    exposure="Digital twin, IoT/edge, supplier XR",
    base_demand=_demand(
        GOV=0.75, AST=0.90, IAM=0.85, DAT=0.85, CFG=0.85, TPR=0.60,
        DET=0.80, IR=0.65, REC=0.70, CLD=0.60, TRN=0.60,
    ),
    events=(
        Event(18, "Production digital twin", {"DTI": 1.25, "DET": 0.45, "DAT": 0.40}),
        Event(40, "Supplier API", {"TPR": 1.05, "CLD": 0.55, "IAM": 0.35}),
        Event(67, "Remote XR maintenance", {"XRI": 1.05, "IAM": 0.45, "DTI": 0.35}),
        Event(91, "AI quality inspection", {"AIG": 1.00, "DAT": 0.35, "GOV": 0.30}),
        Event(108, "Edge-gateway outage", {"REC": 0.95, "IR": 0.55, "CLD": 0.35}),
    ),
)

MEDIUM = Archetype(
    key="medium",
    label="Medium services",
    staff=180,
    budget=54,
    exposure="AI agents, immersive workspace, virtual assets",
    base_demand=_demand(
        GOV=0.90, AST=0.85, IAM=0.95, DAT=0.95, CFG=0.80, TPR=0.80,
        DET=0.85, IR=0.75, REC=0.75, CLD=0.85, TRN=0.70,
    ),
    events=(
        Event(15, "Agentic-AI workflow", {"AIG": 1.20, "GOV": 0.45, "DAT": 0.40}),
        Event(34, "Acquired supplier platform", {"TPR": 1.05, "IAM": 0.40, "AST": 0.25}),
        Event(59, "Persistent XR workspace", {"XRI": 1.15, "IAM": 0.40, "DAT": 0.35}),
        Event(80, "Multi-region edge expansion", {"CLD": 0.85, "DET": 0.55, "REC": 0.35}),
        Event(103, "Virtual-asset fraud attempt", {"XRI": 0.65, "DET": 0.75, "IR": 0.55}),
    ),
)

#: Archetype order is fixed; the index feeds the seed schedule of Table A3.
ARCHETYPES: Tuple[Archetype, ...] = (MICRO, SMALL, MEDIUM)
ARCHETYPE_INDEX: Dict[str, int] = {a.key: i for i, a in enumerate(ARCHETYPES)}
BY_KEY: Dict[str, Archetype] = {a.key: a for a in ARCHETYPES}


def all_events() -> Sequence[Tuple[str, Event]]:
    return [(a.key, event) for a in ARCHETYPES for event in a.events]


def labelled_event_count(replicates: int) -> int:
    """Number of labelled material events over the whole design."""
    return sum(len(a.events) for a in ARCHETYPES) * replicates
