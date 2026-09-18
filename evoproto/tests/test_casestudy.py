"""The case study end to end, and the deliverable of Section 6.4."""

import pytest

from evoproto.casestudy import build_demo_kg, candidate_analogs, run_case_study
from evoproto.kg import EdgeType


def test_demo_graph_has_three_independent_origins_of_the_mechanism():
    kg = build_demo_kg()
    assert kg.independent_origins("sandwich_stiffening") == 3


def test_demo_graph_marks_the_avian_traits_as_homologous_not_convergent():
    kg = build_demo_kg()
    assert kg.has_edge("strutted_long_bone", "strutted_long_bone_2", EdgeType.HOMOLOGOUS_TO)
    assert not kg.has_edge("strutted_long_bone", "strutted_long_bone_2", EdgeType.CONVERGENT_WITH)
    assert kg.has_edge("strutted_long_bone", "diaphragmed_culm", EdgeType.CONVERGENT_WITH)


def test_trade_off_edge_links_the_competing_functions():
    kg = build_demo_kg()
    assert "impact_tolerance" in kg.trade_offs("bending_stiffness_per_mass")


def test_candidates_reproduce_the_transfer_uncertainty_of_section_6_3():
    bamboo = next(c for c in candidate_analogs() if c.identifier == "bamboo_culm")
    U, components = bamboo.transfer_uncertainty()
    assert U == pytest.approx(0.38, abs=0.005)
    assert components["u_mat"] > components["u_scale"] > components["u_load"]


def test_case_study_delivers_the_bundle_of_section_6_4():
    result = run_case_study(population_size=20, generations=8)
    assert result["tag"] == "SYNTHETIC"
    assert result["prototypes"], "the search should find at least one feasible prototype"
    for prototype in result["prototypes"]:
        assert set(prototype["design"]) == {"b", "h", "t", "rho"}
        assert prototype["predictions_modeled"]["tag"] == "MODELED"
        assert prototype["measured"]["mass_kg"] is None  # nothing is measured yet
        assert prototype["gate"]["decision"] in {"RECOMMEND", "ABSTAIN", "REJECT"}
        assert len(prototype["gate"]["chain"]["provenance"]) == 4
    assert 0.0 <= result["abstention_rate"] <= 1.0


def test_case_study_is_reproducible():
    first = run_case_study(population_size=20, generations=8)
    second = run_case_study(population_size=20, generations=8)
    assert first["snapshot_hash"] == second["snapshot_hash"]
    assert [p["design"] for p in first["prototypes"]] == [p["design"] for p in second["prototypes"]]


def test_a_thin_corpus_makes_the_framework_abstain():
    """The gate must be able to decline: weak supports have to reach ABSTAIN."""
    from evoproto.gate import decide
    from evoproto.kg import EvidenceChain
    from evoproto.data import Provenance, ProvenanceTag

    weak = Provenance("thin corpus", "1", "CC0", ProvenanceTag.EXTERNAL, u=0.6)
    chain = EvidenceChain(
        nodes=("org", "trait", "fun", "mech", "param"),
        supports=(0.4, 0.3, 0.05, 0.4),
        provenance=(weak, weak, weak, weak),
    )
    result = decide(chain, U=0.2, n_conv_weighted=0.0, verified=True)
    assert result.decision.value == "ABSTAIN"
    assert result.report.weakest_edge == "explainedBy"
    assert result.report.suggested_experiment  # abstention names the next experiment
