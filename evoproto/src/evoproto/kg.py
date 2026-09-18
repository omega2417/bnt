"""Evolutionary-engineering knowledge graph, EE-KG (Section 4.2).

The EE-KG is a directed multigraph ``G = (V, E)`` with six node types and nine
typed edge types (Table 4).  Two properties distinguish it from earlier
biologically-inspired-design representations:

* ``homologousTo`` and ``convergentWith`` are mutually exclusive between any
  pair of trait nodes, and the choice is made by the phylogeny (Section 4.3),
  not by visual similarity.  The schema enforces the exclusion at insertion.
* The number of independent origins of a mechanism is a *derived* property of
  the graph: the number of homology classes among the traits that support it
  (Eq. 3), optionally sampling-weighted (Eq. 2).

Every edge carries a :class:`~evoproto.data.Provenance` record and a support
weight ``w`` in ``[0, 1]``; an edge whose endpoints violate its type signature
is rejected rather than stored.
"""

from __future__ import annotations

import itertools
from collections.abc import Iterable, Iterator, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

import networkx as nx

from evoproto.data import Provenance, sampling_weight

__all__ = [
    "Chain",
    "ChainLink",
    "EdgeType",
    "EvoKG",
    "NodeType",
    "SchemaError",
]


class NodeType(str, Enum):
    """The six node types of the EE-KG (Section 4.2)."""

    ORGANISM = "Organism"
    ENVIRONMENT = "Environment"
    TRAIT = "Trait"
    FUNCTION = "Function"
    MECHANISM = "Mechanism"
    ENG_PARAMETER = "EngParameter"


class EdgeType(str, Enum):
    """The nine edge types of the EE-KG (Table 4)."""

    HAS_TRAIT = "hasTrait"
    LIVES_IN = "livesIn"
    PERFORMS = "performs"
    EXPLAINED_BY = "explainedBy"
    MAPS_TO = "mapsTo"
    HOMOLOGOUS_TO = "homologousTo"
    CONVERGENT_WITH = "convergentWith"
    TRADES_OFF_WITH = "tradesOffWith"
    DERIVED_FROM = "derivedFrom"


#: Type signature of every edge type: ``(tail type, head type, symmetric?)``.
EDGE_SIGNATURE: dict[EdgeType, tuple[NodeType, NodeType, bool]] = {
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

#: The chain of Eq. (4): trait -> function -> mechanism -> engineering parameter.
CHAIN_EDGE_ORDER: tuple[EdgeType, ...] = (
    EdgeType.PERFORMS,
    EdgeType.EXPLAINED_BY,
    EdgeType.MAPS_TO,
)


class SchemaError(ValueError):
    """Raised when an insertion would violate the EE-KG schema."""


@dataclass(frozen=True)
class ChainLink:
    """One edge of a traceability chain, with its support and provenance."""

    edge_type: EdgeType
    tail: str
    head: str
    support: float
    provenance: Provenance

    def to_dict(self) -> dict[str, Any]:
        return {
            "edge_type": self.edge_type.value,
            "tail": self.tail,
            "head": self.head,
            "support": self.support,
            "provenance": self.provenance.to_dict(),
        }


@dataclass(frozen=True)
class Chain:
    """A traceability chain of Eq. (4).

    ``links`` holds the ``hasTrait``, ``performs``, ``explainedBy`` and
    ``mapsTo`` edges that connect an organism's trait to an engineering
    parameter.  Every recommendation must expose at least one chain with all
    four provenance records (Section 4.2).
    """

    links: tuple[ChainLink, ...]

    @property
    def supports(self) -> tuple[float, ...]:
        """Per-edge support values ``s_k`` used by Eq. (13)."""
        return tuple(link.support for link in self.links)

    @property
    def reconstructed(self) -> bool:
        """``r`` of Eq. (13): ``True`` if any link rests on a reconstruction."""
        return any(link.provenance.reconstructed for link in self.links)

    @property
    def nodes(self) -> tuple[str, ...]:
        if not self.links:
            return ()
        return (self.links[0].tail,) + tuple(link.head for link in self.links)

    @property
    def measured_fraction(self) -> float:
        """Fraction of links whose support derives from measurement.

        This is the mechanism-evidence score ``M`` of Eq. (8): the fraction of
        chain edges whose support comes from experimental measurement rather
        than from inference.
        """
        if not self.links:
            return 0.0
        from evoproto.data import Tag

        measured = sum(link.provenance.tag is Tag.MEASURED for link in self.links)
        return measured / len(self.links)

    def weakest_link(self) -> ChainLink:
        """Link with the smallest support - the ``k*`` of Algorithm 2."""
        if not self.links:
            raise ValueError("an empty chain has no weakest link")
        return min(self.links, key=lambda link: link.support)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": list(self.nodes),
            "links": [link.to_dict() for link in self.links],
            "supports": list(self.supports),
            "reconstructed": self.reconstructed,
            "measured_fraction": self.measured_fraction,
        }


class EvoKG:
    """Schema-enforcing evolutionary-engineering knowledge graph.

    Examples
    --------
    >>> from evoproto.data import Provenance, Tag
    >>> p = Provenance("demo", "1", "CC0", tag=Tag.SYNTHETIC)
    >>> g = EvoKG()
    >>> g.add_node("bird", NodeType.ORGANISM)
    >>> g.add_node("hollow_bone", NodeType.TRAIT)
    >>> g.add_edge(EdgeType.HAS_TRAIT, "bird", "hollow_bone", 0.9, p)
    >>> g.add_edge(EdgeType.PERFORMS, "bird", "hollow_bone", 0.9, p)
    Traceback (most recent call last):
        ...
    evoproto.kg.SchemaError: performs requires Trait -> Function, got Organism -> Trait
    """

    def __init__(self) -> None:
        self._graph = nx.MultiDiGraph()

    # ------------------------------------------------------------------ nodes
    def add_node(self, name: str, node_type: NodeType, **attrs: Any) -> None:
        """Insert or update a typed node.  Re-typing an existing node fails."""
        node_type = NodeType(node_type)
        if name in self._graph:
            existing = self._graph.nodes[name]["node_type"]
            if existing is not node_type:
                raise SchemaError(
                    f"node {name!r} is already typed {existing.value}; "
                    f"cannot re-type it as {node_type.value}"
                )
        self._graph.add_node(name, node_type=node_type, **attrs)

    def node_type(self, name: str) -> NodeType:
        if name not in self._graph:
            raise KeyError(f"unknown node {name!r}")
        return self._graph.nodes[name]["node_type"]

    def nodes(self, node_type: NodeType | None = None) -> list[str]:
        if node_type is None:
            return list(self._graph.nodes)
        node_type = NodeType(node_type)
        return [n for n, d in self._graph.nodes(data=True) if d["node_type"] is node_type]

    # ------------------------------------------------------------------ edges
    def add_edge(
        self,
        edge_type: EdgeType,
        tail: str,
        head: str,
        support: float,
        provenance: Provenance,
        **attrs: Any,
    ) -> None:
        """Insert a typed, provenance-labeled edge with support weight ``w``.

        The type signature of Table 4 is enforced here, as is the mutual
        exclusion of ``homologousTo`` and ``convergentWith``.
        """
        edge_type = EdgeType(edge_type)
        if not 0.0 <= float(support) <= 1.0:
            raise SchemaError("support weight w must lie in [0, 1]")
        for endpoint in (tail, head):
            if endpoint not in self._graph:
                raise SchemaError(f"unknown node {endpoint!r}; add it before the edge")
        want_tail, want_head, symmetric = EDGE_SIGNATURE[edge_type]
        got_tail, got_head = self.node_type(tail), self.node_type(head)
        if (got_tail, got_head) != (want_tail, want_head):
            raise SchemaError(
                f"{edge_type.value} requires {want_tail.value} -> {want_head.value}, "
                f"got {got_tail.value} -> {got_head.value}"
            )
        if edge_type in (EdgeType.HOMOLOGOUS_TO, EdgeType.CONVERGENT_WITH):
            if tail == head:
                raise SchemaError(f"{edge_type.value} needs two distinct trait nodes")
            other = (
                EdgeType.CONVERGENT_WITH
                if edge_type is EdgeType.HOMOLOGOUS_TO
                else EdgeType.HOMOLOGOUS_TO
            )
            if self.has_edge(other, tail, head):
                raise SchemaError(
                    f"{tail!r} and {head!r} are already related by {other.value}; "
                    "homologousTo and convergentWith are mutually exclusive (Section 4.2)"
                )
        self._graph.add_edge(
            tail, head, key=edge_type.value, edge_type=edge_type,
            support=float(support), provenance=provenance, **attrs,
        )
        if symmetric:
            self._graph.add_edge(
                head, tail, key=edge_type.value, edge_type=edge_type,
                support=float(support), provenance=provenance, mirrored=True, **attrs,
            )

    def has_edge(self, edge_type: EdgeType, tail: str, head: str) -> bool:
        edge_type = EdgeType(edge_type)
        if self._graph.has_edge(tail, head, key=edge_type.value):
            return True
        if EDGE_SIGNATURE[edge_type][2]:
            return self._graph.has_edge(head, tail, key=edge_type.value)
        return False

    def edges(self, edge_type: EdgeType | None = None) -> list[tuple[str, str, dict[str, Any]]]:
        out = []
        for tail, head, data in self._graph.edges(data=True):
            if data.get("mirrored"):
                continue
            if edge_type is None or data["edge_type"] is EdgeType(edge_type):
                out.append((tail, head, data))
        return out

    def support(self, edge_type: EdgeType, tail: str, head: str) -> float:
        data = self._graph.edges[tail, head, EdgeType(edge_type).value]
        return float(data["support"])

    def update_support(self, edge_type: EdgeType, tail: str, head: str, support: float,
                       provenance: Provenance) -> None:
        """Feedback update of a support weight (Section 4.7).

        Physical measurements change *weights and priors*, never the biological
        records themselves; the new provenance record is appended to the edge's
        history so the graph's own evolution stays versioned.
        """
        if not 0.0 <= float(support) <= 1.0:
            raise SchemaError("support weight w must lie in [0, 1]")
        key = EdgeType(edge_type).value
        data = self._graph.edges[tail, head, key]
        data.setdefault("history", []).append(
            {"support": data["support"], "provenance": data["provenance"]}
        )
        data["support"] = float(support)
        data["provenance"] = provenance

    # ------------------------------------------------------- derived properties
    def homology_classes(self, traits: Iterable[str]) -> list[set[str]]:
        """Partition ``traits`` into connected components under ``homologousTo``.

        Implemented with union-find over homology edges only; convergence edges
        never merge classes, which is what makes independent origins countable.
        """
        parent: dict[str, str] = {t: t for t in traits}

        def find(x: str) -> str:
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        def union(a: str, b: str) -> None:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra

        for tail, head, _ in self.edges(EdgeType.HOMOLOGOUS_TO):
            if tail in parent and head in parent:
                union(tail, head)
        classes: dict[str, set[str]] = {}
        for trait in parent:
            classes.setdefault(find(trait), set()).add(trait)
        return sorted(classes.values(), key=lambda s: sorted(s)[0])

    def supporting_traits(self, mechanism: str) -> set[str]:
        """Trait nodes reachable backwards from ``mechanism`` (Eq. 3).

        The backwards walk follows ``explainedBy`` then ``performs``.
        """
        if self.node_type(mechanism) is not NodeType.MECHANISM:
            raise SchemaError(f"{mechanism!r} is not a Mechanism node")
        functions = {
            tail
            for tail, head, data in self.edges(EdgeType.EXPLAINED_BY)
            if head == mechanism
        }
        return {
            tail
            for tail, head, data in self.edges(EdgeType.PERFORMS)
            if head in functions
        }

    def independent_origins(
        self,
        mechanism: str,
        clade_of: Mapping[str, str] | None = None,
        clade_sampling: Mapping[str, tuple[int, int]] | None = None,
        reference_fraction: float = 0.1,
    ) -> float:
        """Number of independent evolutionary origins ``N_conv`` (Eq. 3).

        Unweighted, this is the number of homology classes among the traits
        that support ``mechanism``: a mechanism realized by traits in three
        homology classes has evolved three times.

        When ``clade_of`` maps trait -> clade and ``clade_sampling`` maps clade
        -> ``(n_c, N_c)``, the sampling-bias-aware form of Eq. (2) is returned
        instead: one representative clade per homology class contributes
        ``w_c`` rather than 1.
        """
        traits = self.supporting_traits(mechanism)
        classes = self.homology_classes(traits)
        if clade_of is None or clade_sampling is None:
            return float(len(classes))
        total = 0.0
        for klass in classes:
            weights = []
            for trait in sorted(klass):
                clade = clade_of.get(trait)
                if clade is None or clade not in clade_sampling:
                    continue
                n_c, richness = clade_sampling[clade]
                weights.append(sampling_weight(n_c, richness, reference_fraction))
            total += max(weights) if weights else 0.0
        return float(total)

    def convergent_pairs(self, mechanism: str) -> list[tuple[str, str]]:
        """Trait pairs supporting ``mechanism`` that are related by convergence."""
        traits = self.supporting_traits(mechanism)
        return [
            (a, b)
            for a, b in itertools.combinations(sorted(traits), 2)
            if self.has_edge(EdgeType.CONVERGENT_WITH, a, b)
        ]

    def trade_offs(self, function: str) -> list[tuple[str, float]]:
        """Functions that trade off against ``function``, with their supports."""
        return [
            (head, float(data["support"]))
            for tail, head, data in self.edges(EdgeType.TRADES_OFF_WITH)
            if tail == function
        ] + [
            (tail, float(data["support"]))
            for tail, head, data in self.edges(EdgeType.TRADES_OFF_WITH)
            if head == function
        ]

    # ------------------------------------------------------------------ chains
    def evidence_chain(self, eng_parameter: str) -> list[Chain]:
        """All traceability chains ending at ``eng_parameter`` (Eq. 4).

        A chain is a path

        ``Organism -hasTrait-> Trait -performs-> Function -explainedBy->
        Mechanism -mapsTo-> EngParameter``

        and every recommendation must expose at least one such chain with all
        four provenance records.  Chains are returned sorted by descending
        minimum support, so ``chains[0]`` is the strongest available evidence.
        """
        if self.node_type(eng_parameter) is not NodeType.ENG_PARAMETER:
            raise SchemaError(f"{eng_parameter!r} is not an EngParameter node")
        chains: list[Chain] = []
        for mech, param, maps_to in self.edges(EdgeType.MAPS_TO):
            if param != eng_parameter:
                continue
            for func, mech2, explained in self.edges(EdgeType.EXPLAINED_BY):
                if mech2 != mech:
                    continue
                for trait, func2, performs in self.edges(EdgeType.PERFORMS):
                    if func2 != func:
                        continue
                    for organism, trait2, has_trait in self.edges(EdgeType.HAS_TRAIT):
                        if trait2 != trait:
                            continue
                        chains.append(
                            Chain(
                                (
                                    _link(EdgeType.HAS_TRAIT, organism, trait, has_trait),
                                    _link(EdgeType.PERFORMS, trait, func, performs),
                                    _link(EdgeType.EXPLAINED_BY, func, mech, explained),
                                    _link(EdgeType.MAPS_TO, mech, param, maps_to),
                                )
                            )
                        )
        chains.sort(key=lambda c: (-min(c.supports), c.nodes))
        return chains

    # -------------------------------------------------------------- utilities
    def __len__(self) -> int:
        return self._graph.number_of_nodes()

    def __contains__(self, name: object) -> bool:
        return name in self._graph

    def __iter__(self) -> Iterator[str]:
        return iter(self._graph)

    @property
    def graph(self) -> nx.MultiDiGraph:
        """The underlying NetworkX multigraph (read-only by convention)."""
        return self._graph

    def summary(self) -> dict[str, Any]:
        """Node and edge counts per type, for reporting and tests."""
        return {
            "nodes": {t.value: len(self.nodes(t)) for t in NodeType},
            "edges": {t.value: len(self.edges(t)) for t in EdgeType},
        }


def _link(edge_type: EdgeType, tail: str, head: str, data: Mapping[str, Any]) -> ChainLink:
    return ChainLink(
        edge_type=edge_type,
        tail=tail,
        head=head,
        support=float(data["support"]),
        provenance=data["provenance"],
    )


def demo_graph() -> EvoKG:
    """A small SYNTHETIC EE-KG used by the tests, figures and notebooks.

    It encodes the three candidate analog families of Section 6.3 - avian long
    bone, bamboo culm and echinoid stereom - all supporting the mechanism
    "sandwich/cellular stiffening", which maps to the engineering parameter
    "flexural rigidity per unit mass".  No biological record is asserted as
    fact here: every provenance record is tagged SYNTHETIC.
    """
    from evoproto.data import Provenance, Tag

    def prov(tag: Tag = Tag.SYNTHETIC, reconstructed: bool = False) -> Provenance:
        return Provenance(
            source="evoproto demo corpus",
            version="0.1.0",
            license="MIT",
            tag=tag,
            reconstructed=reconstructed,
            method="illustrative placeholder" if reconstructed else None,
            note="SYNTHETIC: illustrative structure, not a biological claim",
        )

    g = EvoKG()
    organisms = {
        "bird": "avian long bone (thin cortex, internal struts)",
        "bamboo": "bamboo culm (hollow, periodically diaphragmed)",
        "echinoid": "echinoid stereom (open-cell mineral foam)",
    }
    traits = {
        "bird": "trait:strutted_cortical_bone",
        "bamboo": "trait:diaphragmed_culm",
        "echinoid": "trait:stereom_foam",
    }
    g.add_node("env:aerial_gravitational", NodeType.ENVIRONMENT)
    g.add_node("fn:bending_stiffness_per_mass", NodeType.FUNCTION)
    g.add_node("fn:impact_toughness", NodeType.FUNCTION)
    g.add_node("mech:sandwich_cellular_stiffening", NodeType.MECHANISM)
    g.add_node("par:flexural_rigidity_per_mass", NodeType.ENG_PARAMETER)
    for organism, description in organisms.items():
        g.add_node(organism, NodeType.ORGANISM, description=description)
        g.add_node(traits[organism], NodeType.TRAIT)
        g.add_edge(EdgeType.HAS_TRAIT, organism, traits[organism], 0.85, prov())
        g.add_edge(EdgeType.LIVES_IN, organism, "env:aerial_gravitational", 0.60, prov())
        g.add_edge(EdgeType.PERFORMS, traits[organism], "fn:bending_stiffness_per_mass",
                   0.80, prov())
    g.add_edge(EdgeType.EXPLAINED_BY, "fn:bending_stiffness_per_mass",
               "mech:sandwich_cellular_stiffening", 0.90, prov(Tag.MEASURED))
    g.add_edge(EdgeType.MAPS_TO, "mech:sandwich_cellular_stiffening",
               "par:flexural_rigidity_per_mass", 0.75, prov(Tag.MODELED))
    g.add_edge(EdgeType.TRADES_OFF_WITH, "fn:bending_stiffness_per_mass",
               "fn:impact_toughness", 0.55, prov())
    # The three trait families sit in mutually distant lineages: convergence,
    # not homology (the phylogeny decides; see evoproto.phylo).
    for a, b in itertools.combinations(sorted(traits.values()), 2):
        g.add_edge(EdgeType.CONVERGENT_WITH, a, b, 0.70, prov())
    return g
