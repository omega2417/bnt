"""The evolutionary-engineering knowledge graph (EE-KG), Section 4.2.

Six node types and nine typed, provenance-labelled edge types (Table 4).  The
schema is enforced at insertion time: an edge whose endpoints violate its type
signature is rejected, and ``homologousTo`` / ``convergentWith`` are mutually
exclusive between any two trait nodes.

Derived quantities implemented here:

* Eq. (3)  ``N_conv(m)``, the number of independent evolutionary origins of a
  mechanism, as the number of homology classes among the trait nodes that
  reach it — computed with a union-find over ``homologousTo`` edges;
* Eq. (4)  the traceability chain
  ``Organism -hasTrait-> Trait -performs-> Function -explainedBy-> Mechanism
  -mapsTo-> EngParameter``, with all four provenance records.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set, Tuple

import networkx as nx

from .data import Provenance, ProvenanceTag, sampling_weight

__all__ = [
    "NodeType",
    "EdgeType",
    "EDGE_SIGNATURES",
    "SchemaError",
    "EvidenceChain",
    "EvoKG",
]


class NodeType(str, Enum):
    """The six node types of the EE-KG."""

    ORGANISM = "Organism"
    ENVIRONMENT = "Environment"
    TRAIT = "Trait"
    FUNCTION = "Function"
    MECHANISM = "Mechanism"
    ENG_PARAMETER = "EngParameter"


class EdgeType(str, Enum):
    """The nine edge types of Table 4."""

    HAS_TRAIT = "hasTrait"
    LIVES_IN = "livesIn"
    PERFORMS = "performs"
    EXPLAINED_BY = "explainedBy"
    MAPS_TO = "mapsTo"
    HOMOLOGOUS_TO = "homologousTo"
    CONVERGENT_WITH = "convergentWith"
    TRADES_OFF_WITH = "tradesOffWith"
    DERIVED_FROM = "derivedFrom"


#: Type signature of every edge type: (tail type, head type, symmetric?).
EDGE_SIGNATURES: Dict[EdgeType, Tuple[NodeType, NodeType, bool]] = {
    EdgeType.HAS_TRAIT: (NodeType.ORGANISM, NodeType.TRAIT, False),
    EdgeType.LIVES_IN: (NodeType.ORGANISM, NodeType.ENVIRONMENT, False),
    EdgeType.PERFORMS: (NodeType.TRAIT, NodeType.FUNCTION, False),
    EdgeType.EXPLAINED_BY: (NodeType.FUNCTION, NodeType.MECHANISM, False),
    EdgeType.MAPS_TO: (NodeType.MECHANISM, NodeType.ENG_PARAMETER, False),
    EdgeType.HOMOLOGOUS_TO: (NodeType.TRAIT, NodeType.TRAIT, True),
    EdgeType.CONVERGENT_WITH: (NodeType.TRAIT, NodeType.TRAIT, True),
    EdgeType.TRADES_OFF_WITH: (NodeType.FUNCTION, NodeType.FUNCTION, True),
    EdgeType.DERIVED_FROM: (NodeType.TRAIT, NodeType.TRAIT, False),
}

#: The four edges of a traceability chain, in order (Eq. 4).
CHAIN_EDGES: Tuple[EdgeType, ...] = (
    EdgeType.HAS_TRAIT,
    EdgeType.PERFORMS,
    EdgeType.EXPLAINED_BY,
    EdgeType.MAPS_TO,
)


class SchemaError(ValueError):
    """Raised when an insertion would violate the EE-KG schema."""


@dataclass(frozen=True)
class EvidenceChain:
    """One ``Organism -> Trait -> Function -> Mechanism -> EngParameter`` path.

    Attributes
    ----------
    nodes:
        The five node identifiers of the chain.
    supports:
        The four edge support weights ``s_1..s_4`` in ``[0, 1]``, in the order
        hasTrait, performs, explainedBy, mapsTo — the input of Eq. (13).
    provenance:
        The four provenance records; a recommendation must expose all of them.
    """

    nodes: Tuple[str, str, str, str, str]
    supports: Tuple[float, float, float, float]
    provenance: Tuple[Provenance, Provenance, Provenance, Provenance]

    @property
    def organism(self) -> str:
        return self.nodes[0]

    @property
    def trait(self) -> str:
        return self.nodes[1]

    @property
    def function(self) -> str:
        return self.nodes[2]

    @property
    def mechanism(self) -> str:
        return self.nodes[3]

    @property
    def parameter(self) -> str:
        return self.nodes[4]

    @property
    def reconstruction_only(self) -> bool:
        """True when every record of the chain is a reconstruction (rho_rec = 0.7)."""
        return all(p.reconstructed for p in self.provenance)

    @property
    def measured_fraction(self) -> float:
        """Fraction of chain edges supported by measurement — ``M`` of Eq. (8)."""
        return sum(p.tag is ProvenanceTag.MEASURED for p in self.provenance) / len(self.provenance)

    @property
    def tag(self) -> ProvenanceTag:
        return Provenance.combine(self.provenance)

    def weakest_edge(self) -> int:
        """Index ``k* = argmin_k s_k`` of the weakest edge (Algorithm 2, line 4)."""
        return int(min(range(len(self.supports)), key=lambda k: self.supports[k]))

    def as_dict(self) -> Dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "edges": [e.value for e in CHAIN_EDGES],
            "supports": list(self.supports),
            "provenance": [p.as_dict() for p in self.provenance],
            "reconstruction_only": self.reconstruction_only,
            "tag": self.tag.value,
        }


class _UnionFind:
    """Union-find over trait identifiers (homology classes of Eq. 3)."""

    def __init__(self, items: Iterable[str]) -> None:
        self._parent: Dict[str, str] = {i: i for i in items}

    def find(self, x: str) -> str:
        root = x
        while self._parent[root] != root:
            root = self._parent[root]
        while self._parent[x] != root:  # path compression
            self._parent[x], x = root, self._parent[x]
        return root

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[rb] = ra

    def classes(self) -> Dict[str, List[str]]:
        out: Dict[str, List[str]] = {}
        for item in self._parent:
            out.setdefault(self.find(item), []).append(item)
        return out


class EvoKG:
    """Directed multigraph with schema enforcement and provenance on every edge."""

    def __init__(self, name: str = "EE-KG") -> None:
        self.name = name
        self.graph = nx.MultiDiGraph(name=name)

    # ------------------------------------------------------------------ nodes
    def add_node(self, node_id: str, node_type: NodeType, **attrs: Any) -> str:
        node_type = NodeType(node_type)
        if node_id in self.graph and self.graph.nodes[node_id]["node_type"] is not node_type:
            raise SchemaError(
                f"node {node_id!r} already exists with type "
                f"{self.graph.nodes[node_id]['node_type'].value}"
            )
        self.graph.add_node(node_id, node_type=node_type, **attrs)
        return node_id

    def node_type(self, node_id: str) -> NodeType:
        if node_id not in self.graph:
            raise KeyError(f"unknown node {node_id!r}")
        return self.graph.nodes[node_id]["node_type"]

    def nodes_of_type(self, node_type: NodeType) -> List[str]:
        node_type = NodeType(node_type)
        return [n for n, d in self.graph.nodes(data=True) if d["node_type"] is node_type]

    # ------------------------------------------------------------------ edges
    def add_edge(
        self,
        tail: str,
        head: str,
        edge_type: EdgeType,
        support: float,
        provenance: Provenance,
        **attrs: Any,
    ) -> Tuple[str, str, EdgeType]:
        """Insert a typed edge, enforcing the schema of Table 4.

        Raises
        ------
        SchemaError
            If the endpoints violate the type signature, or if the insertion
            would make ``homologousTo`` and ``convergentWith`` hold between the
            same pair of trait nodes.
        """
        edge_type = EdgeType(edge_type)
        if not 0.0 <= float(support) <= 1.0:
            raise SchemaError("support weight w must lie in [0, 1]")
        if not isinstance(provenance, Provenance):
            raise SchemaError("every edge requires a Provenance record")
        tail_type, head_type, symmetric = EDGE_SIGNATURES[edge_type]
        if self.node_type(tail) is not tail_type or self.node_type(head) is not head_type:
            raise SchemaError(
                f"{edge_type.value} requires {tail_type.value} -> {head_type.value}, got "
                f"{self.node_type(tail).value} -> {self.node_type(head).value}"
            )
        if edge_type in (EdgeType.HOMOLOGOUS_TO, EdgeType.CONVERGENT_WITH):
            other = (
                EdgeType.CONVERGENT_WITH
                if edge_type is EdgeType.HOMOLOGOUS_TO
                else EdgeType.HOMOLOGOUS_TO
            )
            if self.has_edge(tail, head, other) or self.has_edge(head, tail, other):
                raise SchemaError(
                    f"{tail} and {head} are already related by {other.value}; homology and "
                    "convergence are mutually exclusive (Section 4.2)"
                )
        self.graph.add_edge(
            tail, head, key=edge_type, edge_type=edge_type,
            support=float(support), provenance=provenance, **attrs,
        )
        if symmetric:
            self.graph.add_edge(
                head, tail, key=edge_type, edge_type=edge_type,
                support=float(support), provenance=provenance, **attrs,
            )
        return (tail, head, edge_type)

    def has_edge(self, tail: str, head: str, edge_type: EdgeType) -> bool:
        return self.graph.has_edge(tail, head, key=EdgeType(edge_type))

    def edge(self, tail: str, head: str, edge_type: EdgeType) -> Mapping[str, Any]:
        return self.graph.edges[tail, head, EdgeType(edge_type)]

    def support(self, tail: str, head: str, edge_type: EdgeType) -> float:
        return float(self.edge(tail, head, edge_type)["support"])

    def set_support(self, tail: str, head: str, edge_type: EdgeType, support: float) -> None:
        """Update a support weight (the feedback path of Section 4.7).

        Feedback changes weights and priors, never the biological records
        themselves, so this method touches ``support`` only.
        """
        if not 0.0 <= float(support) <= 1.0:
            raise ValueError("support weight must lie in [0, 1]")
        edge_type = EdgeType(edge_type)
        self.graph.edges[tail, head, edge_type]["support"] = float(support)
        if EDGE_SIGNATURES[edge_type][2] and self.has_edge(head, tail, edge_type):
            self.graph.edges[head, tail, edge_type]["support"] = float(support)

    def out_edges(self, node: str, edge_type: EdgeType) -> List[Tuple[str, str]]:
        edge_type = EdgeType(edge_type)
        return [(u, v) for u, v, k in self.graph.out_edges(node, keys=True) if k is edge_type]

    def in_edges(self, node: str, edge_type: EdgeType) -> List[Tuple[str, str]]:
        edge_type = EdgeType(edge_type)
        return [(u, v) for u, v, k in self.graph.in_edges(node, keys=True) if k is edge_type]

    # ------------------------------------------------------- derived: Eq. (3)
    def traits_of_mechanism(self, mechanism: str) -> List[str]:
        """``T(m)``: trait nodes reachable backwards through explainedBy and performs."""
        if self.node_type(mechanism) is not NodeType.MECHANISM:
            raise SchemaError(f"{mechanism!r} is not a Mechanism node")
        traits: Set[str] = set()
        for function, _ in self.in_edges(mechanism, EdgeType.EXPLAINED_BY):
            for trait, _ in self.in_edges(function, EdgeType.PERFORMS):
                traits.add(trait)
        return sorted(traits)

    def homology_classes(self, traits: Sequence[str]) -> List[List[str]]:
        """Partition ``traits`` into homology classes (union-find over homologousTo)."""
        uf = _UnionFind(traits)
        trait_set = set(traits)
        for trait in traits:
            for _, other in self.out_edges(trait, EdgeType.HOMOLOGOUS_TO):
                if other in trait_set:
                    uf.union(trait, other)
        return [sorted(members) for _, members in sorted(uf.classes().items())]

    def independent_origins(self, mechanism: str) -> int:
        r"""Eq. (3): :math:`N_{\mathrm{conv}}(m) = |T(m)/\!\sim_{\mathrm{hom}}|`."""
        traits = self.traits_of_mechanism(mechanism)
        if not traits:
            return 0
        return len(self.homology_classes(traits))

    def weighted_independent_origins(
        self,
        mechanism: str,
        clade_sampling: Optional[Mapping[str, Tuple[float, float]]] = None,
    ) -> float:
        r"""Sampling-bias-aware :math:`N^w_{\mathrm{conv}}` (Eqs. 2-3).

        One representative clade per homology class contributes its sampling
        weight ``w_k = min(1, n_obs / n_accepted)``.  The clade of a trait is
        read from the trait node's ``clade`` attribute; a class whose clade has
        no sampling record contributes weight 1 (no correction available).
        """
        traits = self.traits_of_mechanism(mechanism)
        if not traits:
            return 0.0
        clade_sampling = clade_sampling or {}
        total = 0.0
        for members in self.homology_classes(traits):
            clades = [self.graph.nodes[t].get("clade") for t in members]
            clades = [c for c in clades if c]
            weight = 1.0
            if clades:
                representative = sorted(clades)[0]
                if representative in clade_sampling:
                    n_obs, n_accepted = clade_sampling[representative]
                    weight = sampling_weight(n_obs, n_accepted)
            total += weight
        return float(total)

    # ------------------------------------------------------- derived: Eq. (4)
    def evidence_chains(self, parameter: str) -> List[EvidenceChain]:
        """Eq. (4): every traceability chain that ends at ``parameter``."""
        if self.node_type(parameter) is not NodeType.ENG_PARAMETER:
            raise SchemaError(f"{parameter!r} is not an EngParameter node")
        chains: List[EvidenceChain] = []
        for mechanism, _ in self.in_edges(parameter, EdgeType.MAPS_TO):
            for function, _ in self.in_edges(mechanism, EdgeType.EXPLAINED_BY):
                for trait, _ in self.in_edges(function, EdgeType.PERFORMS):
                    for organism, _ in self.in_edges(trait, EdgeType.HAS_TRAIT):
                        steps = (
                            (organism, trait, EdgeType.HAS_TRAIT),
                            (trait, function, EdgeType.PERFORMS),
                            (function, mechanism, EdgeType.EXPLAINED_BY),
                            (mechanism, parameter, EdgeType.MAPS_TO),
                        )
                        edges = [self.edge(u, v, t) for u, v, t in steps]
                        chains.append(
                            EvidenceChain(
                                nodes=(organism, trait, function, mechanism, parameter),
                                supports=tuple(float(e["support"]) for e in edges),  # type: ignore[arg-type]
                                provenance=tuple(e["provenance"] for e in edges),  # type: ignore[arg-type]
                            )
                        )
        return chains

    def best_chain(self, parameter: str, weights: Sequence[float] = (0.25, 0.25, 0.25, 0.25)) -> Optional[EvidenceChain]:
        """The chain with the highest weighted support, or ``None`` if there is none."""
        chains = self.evidence_chains(parameter)
        if not chains:
            return None
        return max(chains, key=lambda c: sum(w * s for w, s in zip(weights, c.supports)))

    # -------------------------------------------------------- trade-offs, KG ops
    def trade_offs(self, function: str) -> List[str]:
        """Functions that trade off against ``function`` (``tradesOffWith`` edges)."""
        return sorted(v for _, v in self.out_edges(function, EdgeType.TRADES_OFF_WITH))

    def block_split(self, holdout_clades: Sequence[str]) -> Tuple["EvoKG", "EvoKG"]:
        """Phylogenetic block split of Section 7.5.

        Returns ``(train, holdout)``.  Splitting by clade rather than by taxon
        prevents leakage through closely related species that share traits by
        descent.  An organism belongs to the holdout block when its ``clade``
        attribute is listed in ``holdout_clades``; a trait follows it unless
        some training organism also exhibits that trait.  Function, mechanism,
        parameter and environment nodes are shared by both blocks, so the split
        removes evidence, not vocabulary.
        """
        holdout = set(holdout_clades)
        held_organisms = {
            n for n in self.nodes_of_type(NodeType.ORGANISM)
            if self.graph.nodes[n].get("clade") in holdout
        }
        held_traits = set()
        for organism in held_organisms:
            for _, trait in self.out_edges(organism, EdgeType.HAS_TRAIT):
                owners = {u for u, _ in self.in_edges(trait, EdgeType.HAS_TRAIT)}
                if not (owners - held_organisms):
                    held_traits.add(trait)
        held = held_organisms | held_traits
        train = self._subgraph(lambda n: n not in held)
        shared = {
            n for n in self.graph.nodes
            if self.node_type(n) not in (NodeType.ORGANISM, NodeType.TRAIT)
        }
        holdout_kg = self._subgraph(lambda n: n in held or n in shared)
        train.name = f"{self.name}:train"
        holdout_kg.name = f"{self.name}:holdout"
        return train, holdout_kg

    def _subgraph(self, keep) -> "EvoKG":
        sub = EvoKG(name=f"{self.name}:subgraph")
        for node, attrs in self.graph.nodes(data=True):
            if keep(node):
                sub.graph.add_node(node, **attrs)
        for u, v, k, attrs in self.graph.edges(keys=True, data=True):
            if keep(u) and keep(v):
                sub.graph.add_edge(u, v, key=k, **attrs)
        return sub

    def without_edge_type(self, edge_type: EdgeType) -> "EvoKG":
        """Ablation (a)/(c) of Section 7.5: drop every edge of one type."""
        edge_type = EdgeType(edge_type)
        sub = EvoKG(name=f"{self.name}:-{edge_type.value}")
        sub.graph.add_nodes_from(self.graph.nodes(data=True))
        for u, v, k, attrs in self.graph.edges(keys=True, data=True):
            if k is not edge_type:
                sub.graph.add_edge(u, v, key=k, **attrs)
        return sub

    def without_reconstructions(self) -> "EvoKG":
        """Ablation (b) of Section 7.5: drop every edge whose record has ``r = 1``."""
        sub = EvoKG(name=f"{self.name}:-reconstructed")
        sub.graph.add_nodes_from(self.graph.nodes(data=True))
        for u, v, k, attrs in self.graph.edges(keys=True, data=True):
            if not attrs["provenance"].reconstructed:
                sub.graph.add_edge(u, v, key=k, **attrs)
        return sub

    # ------------------------------------------------------------ serialisation
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "nodes": [
                {"id": n, "node_type": d["node_type"].value,
                 **{k: v for k, v in d.items() if k != "node_type"}}
                for n, d in self.graph.nodes(data=True)
            ],
            "edges": [
                {
                    "tail": u,
                    "head": v,
                    "edge_type": k.value,
                    "support": d["support"],
                    "provenance": d["provenance"].as_dict(),
                }
                for u, v, k, d in self.graph.edges(keys=True, data=True)
            ],
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "EvoKG":
        kg = cls(name=payload.get("name", "EE-KG"))
        for node in payload["nodes"]:
            attrs = {k: v for k, v in node.items() if k not in ("id", "node_type")}
            kg.add_node(node["id"], NodeType(node["node_type"]), **attrs)
        seen: Set[Tuple[str, str, str]] = set()
        for edge in payload["edges"]:
            etype = EdgeType(edge["edge_type"])
            key = (edge["tail"], edge["head"], etype.value)
            reverse = (edge["head"], edge["tail"], etype.value)
            if key in seen or reverse in seen:
                continue  # the symmetric twin is re-created by add_edge
            seen.add(key)
            prov = dict(edge["provenance"])
            prov["tag"] = ProvenanceTag(prov["tag"])
            kg.add_edge(edge["tail"], edge["head"], etype, edge["support"], Provenance(**prov))
        return kg

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"<EvoKG {self.name!r}: {self.graph.number_of_nodes()} nodes, {self.graph.number_of_edges()} edges>"

    def __len__(self) -> int:
        return self.graph.number_of_nodes()

    def __iter__(self) -> Iterator[str]:
        return iter(self.graph.nodes)
