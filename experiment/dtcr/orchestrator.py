"""Policy-constrained security orchestration - Eq. (12), (13).

Corrections relative to Man-V3:

* The admissibility constraints of Eq. (13) are HARD: an inadmissible candidate is
  removed from the feasible set, it is not merely penalised. P_viol therefore never
  appears in the objective of a selected action; it is retained only as a diagnostic
  for the shadow-mode audit trail.
* Node capacity is a VECTOR (cpu, ram, net). The scalar capacity of the manuscript
  is replaced by an element-wise comparison r_i <= C_j.
* The what-if evaluation returns the twin's PREDICTED post-action risk together with
  the identity of the evaluated candidate, so prediction error against the realised
  next state can be measured (H6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

import numpy as np

__all__ = ["Node", "Workload", "Action", "Decision", "Orchestrator"]

RESOURCES = ("cpu", "ram", "net")


@dataclass
class Node:
    node_id: str
    capacity: np.ndarray            # vector over RESOURCES
    used: np.ndarray                # vector over RESOURCES
    security_label: int             # higher dominates
    trust: float

    def headroom(self) -> np.ndarray:
        return self.capacity - self.used


@dataclass
class Workload:
    workload_id: str
    demand: np.ndarray              # r_i over RESOURCES
    security_label: int             # l_i
    min_host_trust: float           # tau_i


@dataclass
class Action:
    name: str
    kind: str                       # isolate | migrate | rate_limit | revoke | restore | none
    target_node: str | None = None
    risk_reduction: float = 0.0     # multiplicative factor applied to twin risk
    overhead: np.ndarray = field(default_factory=lambda: np.zeros(len(RESOURCES)))
    disruption: float = 0.0


@dataclass
class Decision:
    action: Action | None
    objective: float
    predicted_risk: float
    admissible: list[str]
    rejected: dict[str, str]        # action name -> hard-constraint violation reason
    unsafe_selected: bool
    evaluated: int


class Orchestrator:
    """Selects the lowest-objective admissible action - Eq. (12) under Eq. (13)."""

    #: every admissibility dimension defined by Eq. (13)
    ALL_CONSTRAINTS = ("capacity", "security_label", "host_trust")

    def __init__(self, mu: Sequence[float] = (0.35, 0.35, 0.30), theta: float = 0.30,
                 constraints: Sequence[str] = ALL_CONSTRAINTS):
        self.mu = np.asarray(mu, dtype=float)
        if self.mu.shape[0] != len(RESOURCES):
            raise ValueError("mu must have one coefficient per resource dimension")
        unknown = set(constraints) - set(self.ALL_CONSTRAINTS)
        if unknown:
            raise ValueError(f"unknown constraint(s): {sorted(unknown)}")
        self.theta = float(theta)
        self.constraints = tuple(constraints)

    # -- Eq. (13): hard admissibility ------------------------------------------------
    def placement_admissible(self, w: Workload, n: Node) -> tuple[bool, str]:
        """A constraint dimension that the deployed configuration does not implement
        cannot reject anything; this is how the ablation arms are expressed."""
        if "capacity" in self.constraints and np.any(w.demand > n.headroom()):
            return False, "capacity"
        if "security_label" in self.constraints and n.security_label < w.security_label:
            return False, "security_label"
        if "host_trust" in self.constraints and n.trust < w.min_host_trust:
            return False, "host_trust"
        return True, ""

    def evaluate(
        self,
        candidates: Sequence[Action],
        twin_risk: Callable[[Action], float],
        workload: Workload | None = None,
        nodes: dict[str, Node] | None = None,
        unsafe: Callable[[Action], bool] | None = None,
    ) -> Decision:
        admissible: list[tuple[Action, float, float]] = []
        rejected: dict[str, str] = {}
        for act in candidates:
            if act.kind == "migrate" and workload is not None and nodes is not None:
                node = nodes.get(act.target_node or "")
                if node is None:
                    rejected[act.name] = "unknown_node"
                    continue
                ok, why = self.placement_admissible(workload, node)
                if not ok:
                    rejected[act.name] = why
                    continue
            r_pred = float(twin_risk(act))
            j = r_pred + float(self.mu @ act.overhead) + act.disruption
            admissible.append((act, j, r_pred))

        if not admissible:
            return Decision(None, float("inf"), float("nan"), [], rejected, False, len(candidates))

        act, j, r_pred = min(admissible, key=lambda t: t[1])
        return Decision(
            action=act, objective=j, predicted_risk=r_pred,
            admissible=[a.name for a, _, _ in admissible], rejected=rejected,
            unsafe_selected=bool(unsafe(act)) if unsafe else False,
            evaluated=len(candidates),
        )
