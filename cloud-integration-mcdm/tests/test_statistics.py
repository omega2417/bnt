"""Tests for the paired-comparison machinery."""

import numpy as np
import pytest

from cimcdm import compare_methods, holm_adjust
from cimcdm.statistics import mean_confidence_interval, rank_biserial_correlation


def test_holm_is_identity_for_single_test():
    assert holm_adjust(np.array([0.03]))[0] == pytest.approx(0.03)


def test_holm_is_monotone_and_capped():
    adjusted = holm_adjust(np.array([0.001, 0.02, 0.04, 0.5, 0.9]))
    assert np.all(adjusted <= 1.0)
    assert np.all(adjusted >= np.array([0.001, 0.02, 0.04, 0.5, 0.9]))
    order = np.argsort([0.001, 0.02, 0.04, 0.5, 0.9])
    assert np.all(np.diff(adjusted[order]) >= -1e-12)


def test_holm_smallest_p_scaled_by_m():
    adjusted = holm_adjust(np.array([0.01, 0.2, 0.3]))
    assert adjusted[0] == pytest.approx(0.03)


def test_rank_biserial_signs():
    a = np.array([1.0, 2.0, 3.0])
    b = np.array([0.0, 1.0, 2.0])
    assert rank_biserial_correlation(a, b) == pytest.approx(1.0)
    assert rank_biserial_correlation(b, a) == pytest.approx(-1.0)
    assert rank_biserial_correlation(a, a) == pytest.approx(0.0)


def test_identical_samples_are_not_significant():
    values = {"hypervolume": np.linspace(0.4, 0.42, 12)}
    results = compare_methods(values, dict(values))
    assert results[0].adjusted_p == pytest.approx(1.0)
    assert results[0].interpretation == "No significant difference"


def test_cpu_time_interpretation_names_the_faster_method():
    rng = np.random.default_rng(0)
    fast = rng.uniform(2.6, 2.8, 30)
    slow = fast + 0.3
    results = compare_methods({"cpu_time": fast}, {"cpu_time": slow})
    assert results[0].adjusted_p < 0.05
    assert results[0].interpretation == "NSGA-II faster"


def test_quality_interpretation_respects_metric_direction():
    rng = np.random.default_rng(1)
    worse = rng.uniform(0.0014, 0.0016, 30)   # NSGA-II IGD+ (lower is better)
    better = worse - 0.0003                    # NSGA-III
    results = compare_methods({"igd_plus": worse}, {"igd_plus": better})
    assert results[0].adjusted_p < 0.05
    assert results[0].interpretation == "NSGA-III better"


def test_confidence_interval_half_width_shrinks_with_n():
    rng = np.random.default_rng(2)
    _, small = mean_confidence_interval(rng.normal(0, 1, 10))
    _, large = mean_confidence_interval(rng.normal(0, 1, 1000))
    assert large < small
