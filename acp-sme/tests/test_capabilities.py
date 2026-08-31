"""Capability pack integrity (Table A1)."""

import pytest

from acp_sme import capabilities as cap


def test_pack_matches_table_a1():
    expected = {
        "GOV": (4, 0.93, ()), "AST": (3, 0.92, ()), "IAM": (5, 0.95, ("AST",)),
        "DAT": (5, 0.94, ("AST",)), "CFG": (4, 0.88, ("AST",)), "TPR": (4, 0.86, ("GOV",)),
        "DET": (5, 0.90, ("AST",)), "IR": (4, 0.87, ("GOV",)), "REC": (4, 0.86, ("IR",)),
        "CLD": (4, 0.88, ("IAM",)), "XRI": (5, 0.91, ("IAM", "DAT")),
        "DTI": (6, 0.93, ("DAT", "DET")), "AIG": (5, 0.89, ("GOV", "DAT")),
        "TRN": (3, 0.83, ("GOV",)),
    }
    assert len(cap.CAPABILITIES) == 14
    for code, (cost, eff, prereqs) in expected.items():
        c = cap.BY_CODE[code]
        assert (c.cost, c.effectiveness, c.prerequisites) == (cost, eff, prereqs)


def test_prerequisite_graph_is_acyclic():
    cap.validate_prerequisites()


def test_dependency_valid_subsets_are_closed():
    subsets = cap.dependency_valid_subsets()
    assert len(subsets) < (1 << 14)
    assert all(cap.is_dependency_valid(s) for s in subsets)
    assert frozenset() in subsets
    assert frozenset(cap.CODES) in subsets


def test_invalid_subset_is_rejected():
    # XRI requires IAM and DAT.
    assert not cap.is_dependency_valid({"XRI"})
    assert cap.is_dependency_valid(cap.closure({"XRI"}))


def test_closure_is_transitive():
    # REC -> IR -> GOV
    assert cap.closure({"REC"}) == frozenset({"REC", "IR", "GOV"})


def test_bad_capability_rejected():
    with pytest.raises(ValueError):
        cap.Capability("X", "x", 0, 0.5)
    with pytest.raises(ValueError):
        cap.Capability("X", "x", 1, 1.5)
