"""Tests for metrics and the statistical protocol."""

from __future__ import annotations

import numpy as np

from aegis_uav.evaluation.metrics import binary_detection_metrics, tune_threshold
from aegis_uav.evaluation.statistics import (
    bootstrap_ci,
    expected_calibration_error,
    rank_biserial,
    wilcoxon_holm,
)


def test_binary_detection_metrics_perfect():
    scores = np.array([0.1, 0.2, 0.8, 0.9])
    y = np.array([0, 0, 1, 1])
    m = binary_detection_metrics(scores, y, 0.5)
    assert m["precision"] == 1.0 and m["recall"] == 1.0 and m["f1"] == 1.0
    assert m["fpr"] == 0.0 and m["auroc"] == 1.0


def test_tune_threshold_returns_reasonable():
    rng = np.random.default_rng(0)
    scores = np.concatenate([rng.normal(0.2, 0.05, 50), rng.normal(0.8, 0.05, 50)])
    y = np.concatenate([np.zeros(50), np.ones(50)])
    thr = tune_threshold(scores, y)
    assert 0.3 < thr < 0.7


def test_bootstrap_ci_orders():
    point, lo, hi = bootstrap_ci([0.1, 0.2, 0.3, 0.4, 0.5], seed=0)
    assert lo <= point <= hi


def test_rank_biserial_sign():
    x = np.array([1.0, 1.0, 1.0, 1.0])
    y = np.array([0.0, 0.0, 0.0, 0.0])
    assert rank_biserial(x, y) > 0


def test_wilcoxon_holm_monotone_correction():
    comps = {
        "a": (np.array([1.0, 1.1, 1.2, 1.3]), np.array([0.0, 0.1, 0.2, 0.3])),
        "b": (np.array([1.0, 1.0, 1.0, 1.0]), np.array([0.9, 1.0, 1.1, 1.0])),
    }
    res = wilcoxon_holm(comps)
    for r in res:
        assert 0.0 <= r.p_holm <= 1.0
        assert r.p_holm >= r.p_value - 1e-9


def test_ece_bounds():
    conf = np.array([0.9, 0.8, 0.7, 0.6])
    correct = np.array([1, 1, 0, 1])
    ece = expected_calibration_error(conf, correct)
    assert 0.0 <= ece <= 1.0
