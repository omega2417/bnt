"""Proposition 1 (identifiers) and Proposition 2 (lattice of projections)."""
import itertools
import random

import pytest

import crtm
from crtm.hierarchy import Projection, check_code, iota, iota_inv, jaccard_index


def test_iota_roundtrip_and_injective():
    ids = {}
    for i in crtm.TASKS:
        for j in range(1, 12):
            for k in range(1, 12):
                s = iota(i, j, k)
                assert iota_inv(s) == (i, j, k)
                ids[(i, j, k)] = s
    assert len(set(ids.values())) == len(ids)
    assert iota(6, 1, 1) == "UN.S1.A1"


def test_homoglyph_detection():
    assert check_code("CN") == []
    assert check_code("СN")          # Cyrillic Es looks like Latin C
    with pytest.raises(ValueError):
        iota_inv("СN.S1.A1")


def test_technique_codes_injective():
    assert crtm.hierarchy.is_injective(crtm.TECHNIQUES)
    assert len(crtm.TECHNIQUES) == 14


@pytest.fixture(scope="module")
def scen():
    return crtm.load_scenarios()


def test_projections_admissible(scen):
    for p in scen["projections"].values():
        assert p.is_admissible(scen["catalog"])
    bad = Projection({"UN.S3.A1": {"CA"}})
    assert not bad.is_admissible(scen["catalog"])     # example of Section 3.3


def test_section_3_5_numbers(scen):
    P, Q = scen["projections"]["DDoS"], scen["projections"]["phishing"]
    assert sorted((P & Q).actions) == ["CN.S1.A1", "TR.S1.A1", "TR.S2.A2", "UN.S1.A1"]
    assert len((P | Q).actions) == 12
    assert jaccard_index(P.actions, Q.actions) == pytest.approx(1 / 3)
    assert (len(P.downset()), len(Q.downset())) == (26, 23)
    assert jaccard_index(P.downset(), Q.downset()) == pytest.approx(13 / 36)


def _random_projection(cat, rng):
    return Projection({b: {t for t in ts if rng.random() < 0.6}
                       for b, ts in cat.items() if rng.random() < 0.5})


def test_proposition2_distributive_lattice(scen):
    cat = scen["catalog"]
    rng = random.Random(5)
    Ps = [_random_projection(cat, rng) for _ in range(12)]
    for A, B, C in itertools.product(Ps[:6], repeat=3):
        J, M = A | B, A & B
        assert J.is_admissible(cat) and M.is_admissible(cat)
        assert A <= J and B <= J and M <= A and M <= B
        assert A & (B | C) == (A & B) | (A & C)
        assert A | (B & C) == (A | B) & (A | C)
        # order embedding into down-sets
        assert (A <= B) == (A.downset() <= B.downset())
