"""Provenance, stable seeding and the curation controls of Section 3."""

import numpy as np
import pytest

from evoproto.data import (
    CorpusSnapshot,
    OfflineError,
    Provenance,
    ProvenanceTag,
    admit_by_completeness,
    character_completeness,
    default_connectors,
    sampling_weight,
    stable_seed,
    taxon_completeness,
)


def test_stable_seed_is_deterministic_and_arm_specific():
    assert stable_seed("T1", "C", 0) == stable_seed("T1", "C", 0)
    assert stable_seed("T1", "C", 0) != stable_seed("T1", "B", 0)
    assert stable_seed("T1", "C", 0) != stable_seed("T1", "C", 1)
    assert stable_seed("T1", "C", 0) != stable_seed("T2", "C", 0)


def test_stable_seed_does_not_depend_on_python_hash_randomisation():
    # Values recorded from the blake2b derivation; a change here means the seed
    # derivation string changed and every published replicate id is invalidated.
    assert stable_seed("T1", "A", 0, version="0.1.0") == 2917166677
    assert stable_seed("T1", "B", 0, version="0.1.0") == 3068853377
    assert stable_seed("T1", "C", 0, version="0.1.0") == 3742978528


def test_stable_seed_rejects_negative_replicate():
    with pytest.raises(ValueError):
        stable_seed("T1", "C", -1)


def test_provenance_requires_a_method_for_reconstructions():
    with pytest.raises(ValueError):
        Provenance("src", "1", "CC0", ProvenanceTag.MODELED, r=1)
    record = Provenance("src", "1", "CC0", ProvenanceTag.MODELED, r=1, method="ML under BM")
    assert record.reconstructed


def test_provenance_rejects_uncertainty_outside_unit_interval():
    with pytest.raises(ValueError):
        Provenance("src", "1", "CC0", ProvenanceTag.MEASURED, u=1.4)


def test_weakest_tag_propagates_to_derived_quantities():
    records = [
        Provenance("a", "1", "CC0", ProvenanceTag.MEASURED),
        Provenance("b", "1", "CC0", ProvenanceTag.PROXY),
        Provenance("c", "1", "CC0", ProvenanceTag.MODELED),
    ]
    assert Provenance.combine(records) is ProvenanceTag.PROXY


def test_completeness_equation_1():
    matrix = np.array([[1.0, np.nan, 0.0, 1.0], [1.0, 1.0, 1.0, 1.0]])
    assert taxon_completeness(matrix).tolist() == [0.75, 1.0]
    assert character_completeness(matrix).tolist() == [1.0, 0.5, 1.0, 1.0]


def test_admission_uses_only_the_query_characters():
    matrix = np.array([[1.0, np.nan, np.nan], [np.nan, 1.0, 1.0]])
    admitted = admit_by_completeness(matrix, c_min=0.9, query_characters=[1, 2])
    assert admitted.tolist() == [False, True]


def test_sampling_weight_equation_2_is_capped_at_one():
    assert sampling_weight(40, 1600) == pytest.approx(0.025)
    assert sampling_weight(2000, 1600) == 1.0
    with pytest.raises(ValueError):
        sampling_weight(1, 0)


def test_snapshot_hash_is_content_addressed_and_order_independent():
    a = CorpusSnapshot("corpus", {"x": 1, "y": [1, 2]})
    b = CorpusSnapshot("corpus", {"y": [1, 2], "x": 1})
    c = CorpusSnapshot("corpus", {"x": 2, "y": [1, 2]})
    assert a.hash == b.hash
    assert a.hash != c.hash


def test_connectors_are_offline_by_default():
    connectors = default_connectors()
    otol = connectors["otol"]
    url, payload = otol.match_names_request(["Gallus gallus"])
    assert url.endswith("/v3/tnrs/match_names")
    assert payload == {"names": ["Gallus gallus"]}
    with pytest.raises(OfflineError):
        otol.fetch(url, payload)


def test_pbdb_and_morphobank_requests_carry_their_api_versions():
    connectors = default_connectors()
    url, params = connectors["pbdb"].occurrences_request("Echinoidea", interval="Jurassic")
    assert "data1.2/occs/list" in url and params["base_name"] == "Echinoidea"
    assert connectors["pbdb"].api_version == "v1.2"
    url, params = connectors["morphobank"].matrix_download_request(1234, 1)
    assert "P1234" in url and params["format"] == "nexus"
