"""Policy-constrained security orchestration (manuscript Eq. 12-13, Algorithm 1).

The manuscript prints a finite penalty ``P_viol`` inside the objective while
Algorithm 1 states that policy-violating candidates are rejected outright.  This
implementation resolves the inconsistency in favour of Algorithm 1: admissibility
is a hard constraint evaluated before scoring, and the objective contains only
the risk, overhead and disruption terms with the three separate coefficients
mu_1, mu_2, mu_3 used consistently.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

__all__ = ["ResourceVector", "Node", "Workload", "Candidate", "Objective",
           "admissible", "select_action"]


@dataclass(frozen=True)
class ResourceVector:
    """Vector capacity/demand; the manuscript's scalar C_j is generalised here."""

    cpu: float = 0.0
    ram: float = 0.0
    storage: float = 0.0
    network: float = 0.0

    def __le__(self, other: "ResourceVector") -> bool:
        return (self.cpu <= other.cpu and self.ram <= other.ram
                and self.storage <= other.storage and self.network <= other.network)

    def __add__(self, other: "ResourceVector") -> "ResourceVector":
        return ResourceVector(self.cpu + other.cpu, self.ram + other.ram,
                              self.storage + other.storage, self.network + other.network)


@dataclass
class Node:
    node_id: str
    capacity: ResourceVector
    used: ResourceVector = field(default_factory=ResourceVector)
    security_label: int = 0      # lattice level; higher dominates
    trust: float = 1.0
    domain: str = "d0"

    def free(self) -> ResourceVector:
        return ResourceVector(self.capacity.cpu - self.used.cpu,
                              self.capacity.ram - self.used.ram,
                              self.capacity.storage - self.used.storage,
                              self.capacity.network - self.used.network)


@dataclass
class Workload:
    workload_id: str
    demand: ResourceVector
    security_label: int = 0
    min_host_trust: float = 0.0   # tau_i
    allowed_domains: tuple = ()   # empty tuple means "no cross-domain restriction"


@dataclass
class Candidate:
    """A candidate protective action with its twin-predicted consequences."""

    action: str
    residual_risk: float          # sum_i R~_i(t | x)
    overhead_cpu: float           # O_cpu(x), normalised to [0, 1]
    overhead_net: float           # O_net(x), normalised to [0, 1]
    disruption: float             # D(x), normalised to [0, 1]
    placement: dict = field(default_factory=dict)   # workload_id -> node_id


@dataclass(frozen=True)
class Objective:
    """Coefficients of Eq. (12). All terms are dimensionless in [0, 1]."""

    mu1: float = 0.20   # compute overhead
    mu2: float = 0.15   # communication overhead
    mu3: float = 0.25   # service disruption

    def value(self, c: Candidate) -> float:
        return (c.residual_risk + self.mu1 * c.overhead_cpu
                + self.mu2 * c.overhead_net + self.mu3 * c.disruption)


def admissible(candidate: Candidate, nodes: dict, workloads: dict):
    """Evaluate the hard constraints of Eq. (13); returns (bool, reasons).

    Constraints, in the order checked:
      1. every workload is placed exactly once;
      2. vector capacity is respected on every node;
      3. the node security label dominates the workload label;
      4. the host trust meets the workload's minimum tau_i;
      5. the placement respects the workload's admissible domains.
    """
    reasons = []
    placed = candidate.placement
    for wid in workloads:
        if placed.get(wid) is None:
            reasons.append(f"workload {wid} unplaced")
    load = {nid: ResourceVector() for nid in nodes}
    for wid, nid in placed.items():
        if nid not in nodes:
            reasons.append(f"unknown node {nid}")
            continue
        load[nid] = load[nid] + workloads[wid].demand
        w, n = workloads[wid], nodes[nid]
        if n.security_label < w.security_label:
            reasons.append(f"label violation: {wid}@{nid}")
        if n.trust < w.min_host_trust:
            reasons.append(
                f"trust violation: {wid} needs {w.min_host_trust:.2f}, {nid} has {n.trust:.2f}")
        if w.allowed_domains and n.domain not in w.allowed_domains:
            reasons.append(f"domain violation: {wid} -> {n.domain}")
    for nid, used in load.items():
        n = nodes[nid]
        total = used + n.used
        if not (total <= n.capacity):
            reasons.append(f"capacity violation on {nid}")
    return (len(reasons) == 0), reasons


def select_action(candidates: Sequence[Candidate], nodes: dict, workloads: dict,
                  objective: Objective | None = None, tie_epsilon: float = 1e-9):
    """Algorithm 1 steps 7-9: reject inadmissible candidates, then argmin J(x).

    Ties within ``tie_epsilon`` are broken by lowest disruption, then lowest
    compute overhead, then lexicographic action name, so the selection is
    deterministic and reproducible across runs.
    """
    objective = objective or Objective()
    scored, rejected = [], []
    for c in candidates:
        ok, reasons = admissible(c, nodes, workloads)
        if ok:
            scored.append((objective.value(c), c))
        else:
            rejected.append({"action": c.action, "reasons": reasons})
    if not scored:
        return {"selected": None, "rejected": rejected, "ranking": []}
    best = min(s for s, _ in scored)
    tied = [c for s, c in scored if s <= best + tie_epsilon]
    tied.sort(key=lambda c: (c.disruption, c.overhead_cpu, c.action))
    ranking = sorted(({"action": c.action, "J": s} for s, c in scored),
                     key=lambda r: r["J"])
    return {"selected": tied[0], "objective_value": best,
            "rejected": rejected, "ranking": ranking}
