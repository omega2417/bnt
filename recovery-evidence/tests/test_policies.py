"""Table 3: priorities, tie-breaking and the sequential rule for b > 1."""
from fractions import Fraction as Fr

import pytest

from recovery_evidence.policies import POLICIES, priorities, select, urgency
from recovery_evidence.topology import reference_map

REF = reference_map()


def test_urgency_formula():
    assert urgency((0, 5), (0, 1), 7) == (1, 13)
    assert urgency((0, 5), (0, 1), 0) == (1, 6)


def test_p0_ignores_notices_and_p1_uses_them():
    ages, n = [3] * 8, [0, 1, 0, 0, 0, 0, 0, 0]
    assert priorities("P0", REF, [1] * 8, ages, n, 7) == (4,) * 8
    assert priorities("P1", REF, [1] * 8, ages, n, 7)[1] == 11


def test_p1_equals_p0_when_notice_weight_is_zero():
    ages, n = [1, 2, 3, 4, 5, 6, 7, 8], [1, 0, 1, 0, 1, 0, 1, 0]
    assert priorities("P1", REF, [1] * 8, ages, n, 0) == priorities("P0", REF, [1] * 8, ages, n, 0)


def test_p2_is_exact_fraction():
    p = priorities("P2", REF, [1] * 8, [0] * 8, [0] * 8, 7)
    assert p[0] == Fr(13, 8) and all(isinstance(v, Fr) for v in p)


def test_p3_keeps_zero_influence_components_positive():
    p = priorities("P3", REF, [1] * 8, [4] * 8, [0] * 8, 7)
    assert p[REF.index("D")] == 5 and p[REF.index("A")] == 20


def test_ties_go_to_alphabetically_first():
    assert select((5, 5, 5)) == 0
    assert select((1, 5, 5)) == 1
    assert select((5, 5, 5), excluded=(0,)) == 1


def test_select_with_nothing_left():
    with pytest.raises(ValueError):
        select((1, 2), excluded=(0, 1))


def test_unknown_policy():
    with pytest.raises(ValueError):
        priorities("P9", REF, [1] * 8, [0] * 8, [0] * 8, 7)


def test_policy_list():
    assert POLICIES == ("P0", "P1", "P2", "P3")
