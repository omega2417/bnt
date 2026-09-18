"""The protocol runner and the statistical analysis plan (Section 7)."""

import numpy as np
import pytest

from evoproto import experiment
from evoproto.data import stable_seed


def test_cells_are_seeded_per_arm_and_replicate():
    cell = experiment.run_cell("T1", "C", 3, population_size=12, generations=4)
    assert cell.seed == stable_seed("T1", "C", 3)
    other = experiment.run_cell("T1", "B", 3, population_size=12, generations=4)
    assert other.seed != cell.seed


def test_running_a_cell_twice_gives_identical_metrics():
    first = experiment.run_cell("T1", "C", 0, population_size=12, generations=4)
    second = experiment.run_cell("T1", "C", 0, population_size=12, generations=4)
    assert first.as_dict() == second.as_dict()


def test_unimplemented_tasks_are_refused_explicitly():
    with pytest.raises(NotImplementedError, match="T2"):
        experiment.run_cell("T2", "C", 0)
    with pytest.raises(ValueError):
        experiment.run_cell("T1", "Z", 0)


def test_metrics_are_in_range_and_tagged_synthetic():
    cell = experiment.run_cell("T1", "B", 0, population_size=16, generations=5)
    assert 0.0 <= cell.FSR <= 1.0
    assert 0.0 <= cell.HV <= 1.0
    assert cell.D >= 0.0
    assert 1 <= cell.ITS <= 5
    assert cell.tag.value == "SYNTHETIC"


def _scipy_wilcoxon(scipy_stats, x, y, exact=True):
    """scipy renamed 'mode' to 'method' in 1.9; support both."""
    kwargs = {"method": "exact"} if exact else {"method": "approx", "correction": True}
    try:
        return scipy_stats.wilcoxon(x, y, **kwargs).pvalue
    except TypeError:
        legacy = {"mode": "exact"} if exact else {"mode": "approx", "correction": True}
        return scipy_stats.wilcoxon(x, y, **legacy).pvalue


def test_wilcoxon_matches_scipy_on_the_exact_branch():
    scipy_stats = pytest.importorskip("scipy.stats")
    rng = np.random.default_rng(0)
    for _ in range(8):
        n = int(rng.integers(6, 16))
        x = rng.normal(size=n)
        y = rng.normal(size=n)
        _, p = experiment.wilcoxon_signed_rank(x, y)
        expected = _scipy_wilcoxon(scipy_stats, x, y, exact=True)
        assert p == pytest.approx(expected, rel=1e-9)


def test_wilcoxon_with_ties_matches_the_normal_approximation():
    scipy_stats = pytest.importorskip("scipy.stats")
    x = np.array([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
    y = x + np.array([1.0, 1.0, 1.0, -1.0, 2.0, 2.0, -2.0, 3.0, 3.0, 3.0])
    _, p = experiment.wilcoxon_signed_rank(x, y)
    expected = _scipy_wilcoxon(scipy_stats, x, y, exact=False)
    assert p == pytest.approx(expected, rel=1e-6)


def test_wilcoxon_on_identical_samples_reports_no_difference():
    x = np.arange(10, dtype=float)
    statistic, p = experiment.wilcoxon_signed_rank(x, x)
    assert statistic == 0.0
    assert p == 1.0


def test_wilcoxon_requires_paired_shapes():
    with pytest.raises(ValueError):
        experiment.wilcoxon_signed_rank([1.0, 2.0], [1.0, 2.0, 3.0])


def test_holm_correction_is_monotone_and_never_below_the_raw_value():
    raw = [0.001, 0.02, 0.03, 0.9]
    adjusted = experiment.holm_correction(raw)
    assert adjusted == [pytest.approx(0.004), pytest.approx(0.06),
                        pytest.approx(0.06), pytest.approx(0.9)]
    assert all(a >= r for a, r in zip(adjusted, raw))
    assert experiment.holm_correction([]) == []


def test_holm_correction_caps_at_one():
    assert all(value <= 1.0 for value in experiment.holm_correction([0.4, 0.5, 0.6]))


def test_cliffs_delta_spans_minus_one_to_one_with_the_usual_labels():
    assert experiment.cliffs_delta([3, 4, 5], [0, 1, 2]) == 1.0
    assert experiment.cliffs_delta([0, 1, 2], [3, 4, 5]) == -1.0
    assert experiment.cliffs_delta([1, 2, 3], [1, 2, 3]) == 0.0
    assert experiment.cliffs_delta_magnitude(0.1) == "negligible"
    assert experiment.cliffs_delta_magnitude(0.2) == "small"
    assert experiment.cliffs_delta_magnitude(0.4) == "medium"
    assert experiment.cliffs_delta_magnitude(0.8) == "large"


def test_bootstrap_ci_brackets_the_estimate_and_is_reproducible():
    values = np.array([0.1, 0.2, 0.15, 0.3, 0.25, 0.05, 0.22, 0.18, 0.21, 0.19])
    estimate, low, high = experiment.bootstrap_ci(values, n_resamples=500, seed=1)
    assert low <= estimate <= high
    assert (estimate, low, high) == experiment.bootstrap_ci(values, n_resamples=500, seed=1)


def test_required_replicates_matches_the_values_quoted_in_section_7_6():
    assert experiment.required_replicates(1.0) == 9
    assert experiment.required_replicates(0.8) == 13
    assert experiment.required_replicates(0.5) > experiment.required_replicates(1.0)
    with pytest.raises(ValueError):
        experiment.required_replicates(0.0)


def test_compare_arms_reports_holm_adjusted_values_with_effect_sizes():
    results = experiment.run_protocol(replicates=4, population_size=16, generations=5)
    rows = experiment.compare_arms(results, task="T1")
    assert len(rows) == 8  # two contrasts x four metrics
    for row in rows:
        assert 0.0 <= row["p_raw"] <= 1.0
        assert row["p_raw"] <= row["p_holm"] + 1e-12
        assert -1.0 <= row["cliffs_delta"] <= 1.0
        assert row["ci_low"] <= row["median_difference"] <= row["ci_high"]
        assert row["n_pairs"] == 4


def test_protocol_smoke_run_produces_a_complete_report():
    """Section 7.7: every branch of the statistical plan must be exercised."""
    report = experiment.dry_run(replicates=4, population_size=16, generations=6)
    assert report["tag"] == "SYNTHETIC"
    assert "pipeline validation only" in report["warning"]
    assert len(report["snapshot_hash"]) == 32
    assert len(report["cells"]) == 3 * 4
    assert set(report["summary"]) == {"T1/A", "T1/B", "T1/C"}
    assert report["power"]["n_for_d_1.0"] == 9


def test_arms_b_and_c_differ_only_through_the_prior():
    """Identical budget and evaluator: any difference is attributable to the prior."""
    b = experiment.run_cell("T1", "B", 0, population_size=20, generations=6)
    c = experiment.run_cell("T1", "C", 0, population_size=20, generations=6)
    assert b.evaluations == c.evaluations


def test_ablation_reports_the_gate_side_variants():
    report = experiment.ablation(replicates=2, population_size=12, generations=4)
    assert len(report["baseline"]) == 2
    assert len(report["no_tradeoff_constraints"]) == 2
    assert set(report["gate_side_ablations"]) == {
        "no_convergence_edges", "no_reconstructed_states", "gate_disabled",
    }
