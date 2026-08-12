"""Graph model for the synthetic 22-node IMA architecture.

Loads the weighted directed graph (CPM / SW / RDC nodes with DAL-differentiated
parameters) from a YAML configuration file and exposes the matrices required by
the fractional-order dynamics and the cascade-threshold computation.

The architecture is *synthetic* and mechanism-oriented; it is NOT calibrated to
any real Airbus/Boeing or certified IMA platform (see the manuscript, Sec. 6).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List

import numpy as np
import yaml

try:  # NetworkX is optional at import time (only needed for topology plots)
    import networkx as nx
except Exception:  # pragma: no cover
    nx = None


DAL_PRIORITY = {"A": 3, "B": 2, "C": 1}


@dataclass
class IMAGraph:
    """Container for the parsed IMA graph and its derived matrices."""

    n: int
    node_ids: List[str]
    node_type: List[str]
    dal: List[str]
    priority: np.ndarray                # p_i
    crit_weight: np.ndarray             # w_i  (sum = 1)
    service_capacity: np.ndarray        # c_i
    recovery_rate: np.ndarray           # mu_i
    reconf_rate: np.ndarray             # r_i
    traffic_arrival: np.ndarray         # lambda_i
    A: np.ndarray                       # weighted adjacency a_ij  (A[i,j] = weight of edge j->i)
    prop_coeff: np.ndarray              # base degradation-propagation coeff per edge (i,j)
    spillover: np.ndarray               # backlog spillover w_ij  (W[i,j])
    tau: np.ndarray                     # communication delay per edge (i,j); NaN where no edge
    contention: List[List[int]]         # H_i : indices of higher-priority contenders of i
    global_params: Dict
    index: Dict[str, int] = field(default_factory=dict)

    # ------------------------------------------------------------------ helpers
    @property
    def dal_A_idx(self) -> np.ndarray:
        return np.array([i for i, d in enumerate(self.dal) if d == "A"], dtype=int)

    def type_mask(self, ntype: str) -> np.ndarray:
        return np.array([t == ntype for t in self.node_type], dtype=bool)

    def coupling_matrix(self, kappa: float) -> np.ndarray:
        """Effective M1 degradation-coupling matrix B (B[i,j] multiplies f(x_j)).

        B[i,j] = kappa * beta_base * a_ij  (only where edge j->i exists).
        This is the (B o A) block that enters the cascade threshold.
        """
        return kappa * self.prop_coeff * self.A

    def to_networkx(self):  # pragma: no cover - used only for Figure 1
        if nx is None:
            raise ImportError("networkx is required for topology visualisation")
        G = nx.DiGraph()
        for i, nid in enumerate(self.node_ids):
            G.add_node(nid, node_type=self.node_type[i], dal=self.dal[i],
                       priority=int(self.priority[i]))
        for i in range(self.n):
            for j in range(self.n):
                if self.A[i, j] > 0:
                    G.add_edge(self.node_ids[j], self.node_ids[i],
                               weight=float(self.A[i, j]),
                               delay=float(self.tau[i, j]))
        return G


def load_graph(config_path: str | Path) -> IMAGraph:
    """Parse the YAML configuration into an :class:`IMAGraph`."""
    config_path = Path(config_path)
    with open(config_path, "r") as fh:
        cfg = yaml.safe_load(fh)

    nodes = cfg["nodes"]
    n = len(nodes)
    node_ids = [nd["node_id"] for nd in nodes]
    index = {nid: i for i, nid in enumerate(node_ids)}

    node_type = [nd["node_type"] for nd in nodes]
    dal = [nd["dal"] for nd in nodes]
    priority = np.array([nd["priority"] for nd in nodes], dtype=float)
    crit_weight = np.array([nd["criticality_weight"] for nd in nodes], dtype=float)
    service_capacity = np.array([nd["service_capacity"] for nd in nodes], dtype=float)
    recovery_rate = np.array([nd["recovery_rate"] for nd in nodes], dtype=float)
    reconf_rate = np.array([nd["reconfiguration_rate"] for nd in nodes], dtype=float)
    traffic_arrival = np.array([nd["traffic_arrival"] for nd in nodes], dtype=float)

    A = np.zeros((n, n))
    prop_coeff = np.zeros((n, n))
    spillover = np.zeros((n, n))
    tau = np.full((n, n), np.nan)

    for ed in cfg["edges"]:
        j = index[ed["source"]]       # source (upstream) node
        i = index[ed["destination"]]  # destination (depends on source)
        A[i, j] = ed["dependency_weight"]
        prop_coeff[i, j] = ed.get("degradation_propagation_coeff", 0.25)
        spillover[i, j] = ed.get("backlog_spillover_coeff", 0.04)
        tau[i, j] = ed.get("communication_delay", 0.5)

    # Contention sets H_i : higher-priority nodes that share a switch attachment
    # or CPM with node i (approximated via shared graph neighbours here).
    contention = _build_contention_sets(n, A, priority)

    return IMAGraph(
        n=n, node_ids=node_ids, node_type=node_type, dal=dal, priority=priority,
        crit_weight=crit_weight, service_capacity=service_capacity,
        recovery_rate=recovery_rate, reconf_rate=reconf_rate,
        traffic_arrival=traffic_arrival, A=A, prop_coeff=prop_coeff,
        spillover=spillover, tau=tau, contention=contention,
        global_params=cfg.get("global_params", {}), index=index,
    )


def _build_contention_sets(n: int, A: np.ndarray, priority: np.ndarray) -> List[List[int]]:
    """H_i = { k : p_k > p_i, k and i share a resource }.

    Two nodes are taken to share a resource when they are both connected (in
    either direction) to a common node in the dependency graph.  Highest-priority
    nodes have H_i = {} and are never blocked (ARINC 653 scheduling).
    """
    adj = (A > 0) | (A.T > 0)
    contention: List[List[int]] = []
    for i in range(n):
        neigh_i = set(np.where(adj[i])[0])
        Hi = []
        for k in range(n):
            if k == i or priority[k] <= priority[i]:
                continue
            neigh_k = set(np.where(adj[k])[0])
            if neigh_i & neigh_k or adj[i, k] or adj[k, i]:
                Hi.append(k)
        contention.append(sorted(Hi))
    return contention


__all__ = ["IMAGraph", "load_graph", "DAL_PRIORITY"]
