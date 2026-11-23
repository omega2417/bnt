"""Section 3.2-3.3: readiness functions, current influence, static importance."""
import itertools
from fractions import Fraction as Fr

import pytest

from recovery_evidence.topology import DependencyMap, get_map, less_sharing_map_c9, operator_map_c8, reference_map


def test_reference_map_shape():
    ref = reference_map()
    assert ref.m == 8 and ref.n_services == 3
    assert ref.shared_components() == ("A", "D", "E", "F")
    assert ref.users("A") == ("S1", "S2", "S3") and ref.users("F") == ("S1", "S2")


def test_all_capable_and_single_failures():
    ref = reference_map()
    assert ref.readiness([1] * 8) == (1, 1, 1)
    expected = {"A": (0, 0, 0), "B": (0, 1, 1), "C": (1, 0, 1), "D": (1, 1, 1), "E": (1, 1, 1),
                "F": (0, 0, 1), "G": (1, 1, 0), "H": (1, 1, 0)}
    for comp, want in expected.items():
        x = [1] * 8
        x[ref.index(comp)] = 0
        assert ref.readiness(x) == want


def test_redundant_pair_needs_one_node():
    ref = reference_map()
    x = [1] * 8
    x[3] = x[4] = 0
    assert ref.readiness(x) == (0, 0, 1)


def test_influence_is_zero_for_standby_when_primary_recorded_capable():
    ref = reference_map()
    d = ref.influence([1] * 8)
    assert d[ref.index("D")] == 0 and d[ref.index("E")] == 0 and d[ref.index("A")] == 3


def test_influence_of_blocking_component_concentrates():
    """Section 5.3: when one component blocks a service, the others lose influence."""
    ref = reference_map()
    z = [1] * 8
    z[ref.index("G")] = 0  # S3 recorded unready because of G only
    d = ref.influence(z)
    assert d[ref.index("G")] == 1 and d[ref.index("H")] == 0


def test_static_importance_is_mean_influence_over_all_states():
    for factory in (reference_map, operator_map_c8, less_sharing_map_c9):
        dm = factory()
        for j in range(dm.m):
            total = sum(dm.influence(v)[j] for v in itertools.product((0, 1), repeat=dm.m))
            assert dm.static_importance[j] == Fr(total, 2 ** dm.m)


def test_static_importance_c9():
    c = dict(zip(less_sharing_map_c9().components, less_sharing_map_c9().static_importance))
    assert c["A"] == Fr(3, 16) + Fr(1, 4) and c["A2"] == Fr(3, 16) and c["F"] == c["F2"] == Fr(3, 16)


def test_fast_lookup_equals_definition():
    dm = less_sharing_map_c9()
    for v in itertools.product((0, 1), repeat=dm.m):
        assert dm.readiness_fast(v) == dm.readiness(v)


def test_components_must_be_alphabetical():
    with pytest.raises(ValueError):
        DependencyMap.from_dict(["B", "A"], {"S": [["A"], ["B"]]})


def test_unknown_component_rejected():
    with pytest.raises(ValueError):
        DependencyMap.from_dict(["A"], {"S": [["Z"]]})


def test_round_trip_and_registry():
    ref = reference_map()
    assert DependencyMap.from_dict(**ref.to_dict()) == ref
    assert get_map("reference") == ref
    with pytest.raises(KeyError):
        get_map("nope")
