"""Protocol runner and the statistical analysis plan (Section 7)."""

from __future__ import annotations

import json

import pytest

from evoproto.data import Tag, stable_seed
from evoproto.experiment import (
    ARMS,
    bootstrap_ci,
    cliffs_delta,
    environment_record,
    holm_correction,
    paired_contrast,
    required_pairs,
    run_cell,
    run_protocol,
    wilcoxon_signed_rank,
)


def test_holm_correction_against_a_hand_computed_case():
    # p = (0.01, 0.02, 0.03) with n = 3:
    #   3*0.01 = 0.03, max(0.03, 2*0.02 = 0.04) = 0.04, max(0.04, 1*0.03) = 0.04
    assert holm_correction([0.01, 0.02, 0.03]) == pytest.approx([0.03, 0.04, 0.04])


def test_holm_correction_is_monotone_and_clipped():
    adjusted = holm_correction([0.2, 0.5, 0.9])
    assert all(a <= 1.0 for a in adjusted)
    assert adjusted == sorted(adjusted)
    assert holm_correction([]) == []


def test_holm_preserves_input_order():
    assert holm_correction([0.03, 0.01]) == pytest.approx([0.03, 0.02])


def test_cliffs_delta_extremes_and_labels():
    assert cliffs_delta([3, 4, 5], [0, 1, 2])["delta"] == pytest.approx(1.0)
    assert cliffs_delta([0, 1, 2], [3, 4, 5])["delta"] == pytest.approx(-1.0)
    assert cliffs_delta([1, 2, 3], [1, 2, 3])["magnitude"] == "negligible"
    assert cliffs_delta([3, 4, 5], [0, 1, 2])["magnitude"] == "large"


def test_wilcoxon_handles_all_zero_differences():
    result = wilcoxon_signed_rank([0.0, 0.0, 0.0])
    assert result["p_value"] == 1.0
    assert result["n_effective"] == 0.0


def test_wilcoxon_detects_a_consistent_shift():
    result = wilcoxon_signed_rank([0.4, 0.5, 0.3, 0.6, 0.2, 0.5, 0.45, 0.35])
    assert result["p_value"] < 0.05


def test_bootstrap_ci_brackets_the_median():
    values = [0.1, 0.2, 0.3, 0.4, 0.5]
    ci = bootstrap_ci(values, n_resamples=500, seed=0)
    assert ci["low"] <= ci["median"] <= ci["high"]


def test_required_pairs_matches_the_numbers_quoted_in_section_7_6():
    assert required_pairs(1.0) == pytest.approx(9, abs=1.0)
    assert required_pairs(0.8) == pytest.approx(14, abs=1.5)
    with pytest.raises(ValueError):
        required_pairs(0.0)


def test_cell_is_reproducible_and_tagged_synthetic():
    a = run_cell("T1", "C", 0, population=16, generations=5)
    b = run_cell("T1", "C", 0, population=16, generations=5)
    assert a.metrics == b.metrics
    assert a.seed == stable_seed("T1", "C", 0)
    assert a.tag == Tag.SYNTHETIC.value
    assert set(a.metrics) >= {"FSR", "HV", "D", "ITS"}


def test_arms_share_the_budget_but_not_the_seed():
    b = run_cell("T1", "B", 0, population=16, generations=5)
    c = run_cell("T1", "C", 0, population=16, generations=5)
    assert b.seed != c.seed


def test_unimplemented_tasks_fail_loudly():
    with pytest.raises(NotImplementedError):
        run_cell("T2", "C", 0)
    with pytest.raises(KeyError):
        run_cell("T9", "C", 0)
    with pytest.raises(KeyError):
        run_cell("T1", "Z", 0)


def test_protocol_smoke_run_produces_a_complete_analysis(tmp_path):
    result = run_protocol(replicates=4, population=16, generations=6, n_resamples=200)
    assert len(result.cells) == 3 * 4
    rows = result.statistics["T1"]
    assert len(rows) == 2 * 4                      # two contrasts x four metrics
    for row in rows:
        assert 0.0 <= row["p_value"] <= 1.0
        assert 0.0 <= row["p_holm"] <= 1.0
        assert row["p_holm"] >= row["p_value"] - 1e-12
        assert -1.0 <= row["cliffs_delta"]["delta"] <= 1.0
        assert row["n_pairs"] == 4
    assert set(result.table()) == set(ARMS)
    directory = result.save(tmp_path / "run")
    payload = json.loads((directory / "results.json").read_text())
    assert payload["configuration"]["provenance_tag"] == Tag.SYNTHETIC.value
    assert (directory / "cells.csv").read_text().startswith("task,arm,replicate")


def test_paired_contrast_pairs_by_replicate():
    result = run_protocol(replicates=3, population=12, generations=4, n_resamples=100)
    row = paired_contrast(result.cells, "T1", "C", "B", "HV", n_resamples=100)
    assert row["n_pairs"] == 3
    assert row["contrast"] == "C vs B"


def test_environment_record_names_the_package_versions():
    record = environment_record()
    assert record["evoproto"]
    assert "numpy" in record["packages"]
