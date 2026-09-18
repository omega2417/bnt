"""Schema enforcement, Eq. (3) and Eq. (4)."""

import pytest

from evoproto.data import Provenance, ProvenanceTag
from evoproto.casestudy import CLADE_SAMPLING, build_demo_kg
from evoproto.kg import EdgeType, EvoKG, NodeType, SchemaError

PROV = Provenance("demo", "1", "CC0", ProvenanceTag.EXTERNAL)


def _minimal_graph():
    kg = EvoKG()
    kg.add_node("org", NodeType.ORGANISM, clade="X")
    kg.add_node("trait", NodeType.TRAIT, clade="X")
    kg.add_node("fun", NodeType.FUNCTION)
    kg.add_node("mech", NodeType.MECHANISM)
    kg.add_node("param", NodeType.ENG_PARAMETER)
    kg.add_edge("org", "trait", EdgeType.HAS_TRAIT, 0.9, PROV)
    kg.add_edge("trait", "fun", EdgeType.PERFORMS, 0.8, PROV)
    kg.add_edge("fun", "mech", EdgeType.EXPLAINED_BY, 0.7, PROV)
    kg.add_edge("mech", "param", EdgeType.MAPS_TO, 0.6, PROV)
    return kg


def test_edge_signature_is_enforced():
    kg = _minimal_graph()
    with pytest.raises(SchemaError):
        kg.add_edge("org", "fun", EdgeType.HAS_TRAIT, 0.5, PROV)


def test_edges_require_provenance_and_a_valid_support():
    kg = _minimal_graph()
    with pytest.raises(SchemaError):
        kg.add_edge("org", "trait", EdgeType.HAS_TRAIT, 0.5, None)
    with pytest.raises(SchemaError):
        kg.add_edge("org", "trait", EdgeType.HAS_TRAIT, 1.7, PROV)


def test_homology_and_convergence_are_mutually_exclusive():
    kg = _minimal_graph()
    kg.add_node("trait2", NodeType.TRAIT, clade="Y")
    kg.add_edge("trait", "trait2", EdgeType.HOMOLOGOUS_TO, 0.9, PROV)
    with pytest.raises(SchemaError):
        kg.add_edge("trait", "trait2", EdgeType.CONVERGENT_WITH, 0.9, PROV)
    with pytest.raises(SchemaError):  # also in the reverse direction
        kg.add_edge("trait2", "trait", EdgeType.CONVERGENT_WITH, 0.9, PROV)


def test_symmetric_edges_are_inserted_both_ways():
    kg = _minimal_graph()
    kg.add_node("trait2", NodeType.TRAIT)
    kg.add_edge("trait", "trait2", EdgeType.HOMOLOGOUS_TO, 0.9, PROV)
    assert kg.has_edge("trait", "trait2", EdgeType.HOMOLOGOUS_TO)
    assert kg.has_edge("trait2", "trait", EdgeType.HOMOLOGOUS_TO)


def test_independent_origins_counts_homology_classes():
    kg = build_demo_kg()
    # four traits reach the mechanism; the two avian traits are homologous
    assert len(kg.traits_of_mechanism("sandwich_stiffening")) == 4
    assert kg.independent_origins("sandwich_stiffening") == 3


def test_weighted_origins_downweight_thinly_sampled_clades():
    kg = build_demo_kg()
    unweighted = kg.independent_origins("sandwich_stiffening")
    weighted = kg.weighted_independent_origins("sandwich_stiffening", CLADE_SAMPLING)
    assert 0 < weighted < unweighted
    # with complete sampling the weighted count returns to the plain count
    full = {clade: (1.0, 1.0) for clade in CLADE_SAMPLING}
    assert kg.weighted_independent_origins("sandwich_stiffening", full) == float(unweighted)


def test_evidence_chain_has_four_edges_and_four_provenance_records():
    kg = _minimal_graph()
    chains = kg.evidence_chains("param")
    assert len(chains) == 1
    chain = chains[0]
    assert chain.nodes == ("org", "trait", "fun", "mech", "param")
    assert chain.supports == (0.9, 0.8, 0.7, 0.6)
    assert len(chain.provenance) == 4
    assert chain.weakest_edge() == 3


def test_measured_fraction_is_the_M_of_equation_8():
    kg = build_demo_kg()
    chain = kg.best_chain("core_relative_density")
    assert chain is not None
    assert chain.measured_fraction == pytest.approx(0.25)


def test_block_split_removes_held_out_clades_from_the_training_graph():
    kg = build_demo_kg()
    train, holdout = kg.block_split(["Bambusoideae"])
    assert "Bambusoideae.sp1" not in train.graph
    assert "diaphragmed_culm" not in train.graph
    assert "Bambusoideae.sp1" in holdout.graph
    assert train.independent_origins("sandwich_stiffening") == 2


def test_ablations_drop_edges_without_touching_records():
    kg = build_demo_kg()
    no_convergence = kg.without_edge_type(EdgeType.CONVERGENT_WITH)
    assert no_convergence.independent_origins("sandwich_stiffening") == 3
    assert not any(
        k is EdgeType.CONVERGENT_WITH for _, _, k in no_convergence.graph.edges(keys=True)
    )
    no_reconstruction = kg.without_reconstructions()
    assert all(
        not d["provenance"].reconstructed
        for _, _, d in no_reconstruction.graph.edges(data=True)
    )


def test_json_round_trip_preserves_structure():
    kg = build_demo_kg()
    restored = EvoKG.from_dict(kg.to_dict())
    assert restored.graph.number_of_nodes() == kg.graph.number_of_nodes()
    assert restored.graph.number_of_edges() == kg.graph.number_of_edges()
    assert restored.independent_origins("sandwich_stiffening") == kg.independent_origins(
        "sandwich_stiffening"
    )


def test_feedback_updates_weights_not_records():
    kg = _minimal_graph()
    before = kg.edge("fun", "mech", EdgeType.EXPLAINED_BY)["provenance"]
    kg.set_support("fun", "mech", EdgeType.EXPLAINED_BY, 0.95)
    assert kg.support("fun", "mech", EdgeType.EXPLAINED_BY) == 0.95
    assert kg.edge("fun", "mech", EdgeType.EXPLAINED_BY)["provenance"] is before
