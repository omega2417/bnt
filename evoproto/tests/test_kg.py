"""Schema enforcement, chains and independent origins (Section 4.2)."""

from __future__ import annotations

import pytest

from evoproto.data import Provenance, Tag
from evoproto.kg import EdgeType, EvoKG, NodeType, SchemaError, demo_graph


def prov(tag=Tag.SYNTHETIC, reconstructed=False):
    return Provenance("test", "1", "CC0", tag=tag, reconstructed=reconstructed,
                      method="ML under BM" if reconstructed else None)


def test_edge_signature_is_enforced():
    graph = EvoKG()
    graph.add_node("bird", NodeType.ORGANISM)
    graph.add_node("bone", NodeType.TRAIT)
    graph.add_edge(EdgeType.HAS_TRAIT, "bird", "bone", 0.9, prov())
    with pytest.raises(SchemaError):
        graph.add_edge(EdgeType.PERFORMS, "bird", "bone", 0.9, prov())


def test_unknown_node_and_out_of_range_support_are_rejected():
    graph = EvoKG()
    graph.add_node("bird", NodeType.ORGANISM)
    graph.add_node("bone", NodeType.TRAIT)
    with pytest.raises(SchemaError):
        graph.add_edge(EdgeType.HAS_TRAIT, "bird", "ghost", 0.5, prov())
    with pytest.raises(SchemaError):
        graph.add_edge(EdgeType.HAS_TRAIT, "bird", "bone", 1.4, prov())


def test_retyping_a_node_fails():
    graph = EvoKG()
    graph.add_node("x", NodeType.TRAIT)
    with pytest.raises(SchemaError):
        graph.add_node("x", NodeType.FUNCTION)


def test_homology_and_convergence_are_mutually_exclusive():
    graph = EvoKG()
    graph.add_node("a", NodeType.TRAIT)
    graph.add_node("b", NodeType.TRAIT)
    graph.add_edge(EdgeType.HOMOLOGOUS_TO, "a", "b", 0.8, prov())
    with pytest.raises(SchemaError):
        graph.add_edge(EdgeType.CONVERGENT_WITH, "a", "b", 0.8, prov())
    with pytest.raises(SchemaError):          # also in the mirrored direction
        graph.add_edge(EdgeType.CONVERGENT_WITH, "b", "a", 0.8, prov())


def test_independent_origins_counts_homology_classes():
    # Three trait families in mutually distant lineages: three origins.
    assert demo_graph().independent_origins("mech:sandwich_cellular_stiffening") == 3.0

    # Built with two of the three traits homologous instead of convergent, the
    # same mechanism has only two independent origins - homology never adds a
    # unit, which is the whole point of Eq. (3).
    graph = EvoKG()
    graph.add_node("fn", NodeType.FUNCTION)
    graph.add_node("me", NodeType.MECHANISM)
    graph.add_edge(EdgeType.EXPLAINED_BY, "fn", "me", 0.9, prov())
    for name in ("t1", "t2", "t3"):
        graph.add_node(name, NodeType.TRAIT)
        graph.add_edge(EdgeType.PERFORMS, name, "fn", 0.8, prov())
    assert graph.independent_origins("me") == 3.0
    graph.add_edge(EdgeType.HOMOLOGOUS_TO, "t2", "t3", 0.9, prov())
    assert graph.independent_origins("me") == 2.0
    graph.add_edge(EdgeType.CONVERGENT_WITH, "t1", "t2", 0.7, prov())
    assert graph.independent_origins("me") == 2.0


def test_independent_origins_with_sampling_weights():
    graph = demo_graph()
    mechanism = "mech:sandwich_cellular_stiffening"
    clade_of = {
        "trait:strutted_cortical_bone": "Aves",
        "trait:diaphragmed_culm": "Bambusoideae",
        "trait:stereom_foam": "Echinoidea",
    }
    sampling = {"Aves": (100, 100), "Bambusoideae": (10, 100), "Echinoidea": (10, 100)}
    weighted = graph.independent_origins(mechanism, clade_of, sampling,
                                         reference_fraction=0.1)
    assert weighted == pytest.approx(0.1 + 1.0 + 1.0)
    assert weighted < graph.independent_origins(mechanism)


def test_evidence_chain_exposes_four_provenance_records():
    graph = demo_graph()
    chains = graph.evidence_chain("par:flexural_rigidity_per_mass")
    assert len(chains) == 3                      # one per organism
    chain = chains[0]
    assert [link.edge_type for link in chain.links] == [
        EdgeType.HAS_TRAIT, EdgeType.PERFORMS, EdgeType.EXPLAINED_BY, EdgeType.MAPS_TO
    ]
    assert len(chain.supports) == 4
    assert chain.measured_fraction == pytest.approx(0.25)
    assert chain.weakest_link().support == min(chain.supports)
    assert chain.nodes[-1] == "par:flexural_rigidity_per_mass"


def test_chain_reports_reconstruction():
    graph = EvoKG()
    for name, kind in [("org", NodeType.ORGANISM), ("tr", NodeType.TRAIT),
                       ("fn", NodeType.FUNCTION), ("me", NodeType.MECHANISM),
                       ("par", NodeType.ENG_PARAMETER)]:
        graph.add_node(name, kind)
    graph.add_edge(EdgeType.HAS_TRAIT, "org", "tr", 0.5, prov(reconstructed=True))
    graph.add_edge(EdgeType.PERFORMS, "tr", "fn", 0.6, prov())
    graph.add_edge(EdgeType.EXPLAINED_BY, "fn", "me", 0.7, prov())
    graph.add_edge(EdgeType.MAPS_TO, "me", "par", 0.8, prov())
    chain = graph.evidence_chain("par")[0]
    assert chain.reconstructed is True


def test_feedback_updates_weight_and_keeps_history():
    graph = demo_graph()
    before = graph.support(EdgeType.EXPLAINED_BY, "fn:bending_stiffness_per_mass",
                           "mech:sandwich_cellular_stiffening")
    graph.update_support(EdgeType.EXPLAINED_BY, "fn:bending_stiffness_per_mass",
                         "mech:sandwich_cellular_stiffening", 0.95,
                         prov(tag=Tag.MEASURED))
    after = graph.support(EdgeType.EXPLAINED_BY, "fn:bending_stiffness_per_mass",
                          "mech:sandwich_cellular_stiffening")
    assert after == pytest.approx(0.95) and after != before
    data = graph.graph.edges["fn:bending_stiffness_per_mass",
                             "mech:sandwich_cellular_stiffening",
                             EdgeType.EXPLAINED_BY.value]
    assert data["history"][0]["support"] == pytest.approx(before)


def test_trade_offs_and_convergent_pairs():
    graph = demo_graph()
    assert ("fn:impact_toughness", pytest.approx(0.55)) in graph.trade_offs(
        "fn:bending_stiffness_per_mass"
    )
    assert len(graph.convergent_pairs("mech:sandwich_cellular_stiffening")) == 3
