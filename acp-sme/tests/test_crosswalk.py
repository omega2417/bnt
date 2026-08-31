"""R3: semantic traceability and complete-path tests for the capability graph."""

import pytest

from acp_sme.capabilities import CODES
from acp_sme.crosswalk import (
    EDGES,
    Framework,
    Relation,
    coverage_report,
    draft_soa_rows,
    provenance,
    references_for,
    validate_pack,
)


def test_pack_is_complete_across_all_three_frameworks():
    validate_pack()


def test_every_capability_has_a_complete_standards_path():
    """Complete-path rate (Table 1, R3) must be 100%."""
    complete = [
        code
        for code in CODES
        if all(counts > 0 for counts in coverage_report()[code].values())
    ]
    assert len(complete) == len(CODES)


def test_every_edge_is_typed_directional_and_versioned():
    for edge in EDGES:
        assert isinstance(edge.relation, Relation)
        assert isinstance(edge.framework, Framework)
        assert edge.capability in CODES
        assert edge.identifiers
        assert edge.note
        assert edge.source_version
        assert 0.0 < edge.confidence <= 1.0


def test_mapping_is_many_to_many_not_one_to_one():
    """A relevance claim must not be reduced to an equivalence claim."""
    multi_identifier = [e for e in EDGES if len(e.identifiers) > 1]
    assert multi_identifier, "expected at least one one-to-many edge"
    # And at least one identifier is cited by more than one capability.
    seen = {}
    shared = False
    for edge in EDGES:
        for identifier in edge.identifiers:
            key = (edge.framework, identifier)
            if key in seen and seen[key] != edge.capability:
                shared = True
            seen[key] = edge.capability
    assert shared


def test_partial_coverage_is_labelled_as_such():
    partial = [e for e in EDGES if e.relation is Relation.PARTIALLY_COVERS]
    assert len(partial) >= 10


def test_governance_requires_management_system_clauses():
    gov_iso = [
        e for e in references_for("GOV") if e.framework is Framework.ISO_27001_2022
    ]
    assert gov_iso and gov_iso[0].relation is Relation.REQUIRES


def test_no_iso_control_text_is_reproduced():
    """Only identifiers and author-generated summaries may appear in the pack."""
    for edge in EDGES:
        if edge.framework is not Framework.ISO_27001_2022:
            continue
        for identifier in edge.identifiers:
            assert identifier.startswith(("A.", "Clause ")), identifier
            assert len(identifier) <= 12


def test_unknown_capability_is_rejected():
    with pytest.raises(ValueError):
        references_for("NOPE")


def test_provenance_is_grouped_and_deduplicated():
    refs = provenance("IAM")
    assert set(refs) == {f.value for f in Framework}
    for identifiers in refs.values():
        assert identifiers == sorted(set(identifiers))


def test_soa_draft_only_cites_iso_references():
    rows = draft_soa_rows(["IAM"])
    assert rows
    for row in rows:
        assert row["iso_references"]
        assert row["decision"] == "PENDING MANAGEMENT REVIEW"
