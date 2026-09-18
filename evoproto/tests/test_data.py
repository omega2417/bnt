"""Provenance, seeding and curation controls (Section 3)."""

from __future__ import annotations

import math

import pytest

from evoproto.data import (
    MorphoBankConnector,
    OfflineAccessError,
    OTOLConnector,
    PBDBConnector,
    Provenance,
    Tag,
    completeness,
    corpus_snapshot_hash,
    sampling_weight,
    stable_seed,
)


def test_seed_is_stable_and_arm_separated():
    assert stable_seed("T1", "B", 0) == stable_seed("T1", "B", 0)
    assert stable_seed("T1", "B", 0) != stable_seed("T1", "C", 0)
    assert stable_seed("T1", "B", 0) != stable_seed("T1", "B", 1)
    assert stable_seed("T1", "B", 0) != stable_seed("T2", "B", 0)


def test_seed_is_known_constant_for_a_fixed_version():
    # Pins the derivation itself: if the hashing scheme ever changes, replicates
    # stop reproducing and this test must fail loudly rather than silently.
    assert stable_seed("T1", "C", 3, package_version="0.1.0") == 4150079716


def test_seed_fits_numpy_range():
    for replicate in range(50):
        seed = stable_seed("T1", "A", replicate)
        assert 0 <= seed < 2**32


def test_seed_rejects_negative_replicate():
    with pytest.raises(ValueError):
        stable_seed("T1", "A", -1)


def test_provenance_requires_core_fields():
    with pytest.raises(ValueError):
        Provenance("", "1", "CC0")
    with pytest.raises(ValueError):
        Provenance("src", "1", "CC0", uncertainty=1.5)


def test_reconstructed_record_must_name_its_method():
    with pytest.raises(ValueError):
        Provenance("src", "1", "CC0", reconstructed=True)
    record = Provenance("src", "1", "CC0", reconstructed=True, method="ML under BM")
    assert record.r == 1
    assert record.to_dict()["tag"] == Tag.EXTERNAL.value


def test_completeness_matches_equation_1():
    matrix = [[1, 1, None], [1, None, None], [1, 1, 1]]
    result = completeness(matrix)
    assert result["taxa"] == pytest.approx([2 / 3, 1 / 3, 1.0])
    assert result["characters"] == pytest.approx([1.0, 2 / 3, 1 / 3])


def test_completeness_treats_nan_as_missing():
    assert completeness([[1.0, math.nan]])["taxa"] == pytest.approx([0.5])


def test_sampling_weight_caps_dense_clades():
    # A clade sampled at the reference intensity keeps full weight; one sampled
    # ten times more intensively contributes a tenth.
    assert sampling_weight(10, 100, reference_fraction=0.1) == pytest.approx(1.0)
    assert sampling_weight(100, 100, reference_fraction=0.1) == pytest.approx(0.1)
    assert sampling_weight(0, 100) == 0.0
    with pytest.raises(ValueError):
        sampling_weight(5, 0)


def test_snapshot_hash_is_content_addressed():
    a = [{"id": 1, "x": "a"}, {"id": 2, "x": "b"}]
    b = list(reversed(a))
    assert corpus_snapshot_hash(a) == corpus_snapshot_hash(b)
    assert corpus_snapshot_hash(a) != corpus_snapshot_hash(a + [{"id": 3}])


@pytest.mark.parametrize(
    "connector,call",
    [
        (OTOLConnector(), lambda c: c.match_names(["Gallus gallus"])),
        (OTOLConnector(), lambda c: c.induced_subtree([12345])),
        (PBDBConnector(), lambda c: c.occurrences("Echinoidea")),
        (MorphoBankConnector(), lambda c: c.matrix(1234)),
    ],
)
def test_connectors_describe_without_network(connector, call):
    descriptor = call(connector)
    assert descriptor.url.startswith("https://")
    assert descriptor.provenance_fields
    with pytest.raises(OfflineAccessError):
        connector.fetch(descriptor)
