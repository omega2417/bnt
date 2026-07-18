"""Тести відтворюваності пакета ASF-UAV-Warning.

За фіксованого ``SEED = 20260`` усі метрики Таблиці 4 мають збігатися з
опублікованими у статті значеннями **до 4 знаків після коми**. Ці ж тести
гарантують детермінізм: повторний запуск конвеєра дає біт-у-біт ті самі числа.

Запуск::

    cd asf-uav-warning
    pytest -q
"""

from __future__ import annotations

import numpy as np
import pytest

from src.asf_simulation import (
    ARCH_NAMES,
    N_EVENTS,
    N_TEST,
    SEED,
    simulate,
)
from src.metrics import (
    ablation,
    compute_metrics_table,
    metrics_by_condition,
    pd_by_distance,
    time_margin,
)

# Опубліковані значення Таблиці 4 (демонстраційне відтворення, seed=20260).
# Джерело — вивід оригінального ноутбука ASF_UAV_Warning_Demo_Colab.ipynb.
EXPECTED_TABLE4 = {
    "single_radar": dict(
        precision=0.9265, pd=0.6498, f1=0.7639, far=0.0516,
        roc_auc=0.8791, brier=0.1530, latency_median_s=1.2323, latency_p95_s=2.3541,
    ),
    "static_fusion": dict(
        precision=0.9568, pd=0.9175, f1=0.9367, far=0.0415,
        roc_auc=0.9807, brier=0.1217, latency_median_s=1.5536, latency_p95_s=2.7471,
    ),
    "agentic_fusion": dict(
        precision=0.9648, pd=0.9330, f1=0.9487, far=0.0341,
        roc_auc=0.9870, brier=0.1120, latency_median_s=0.8491, latency_p95_s=1.7700,
    ),
}

METRIC_COLS = list(next(iter(EXPECTED_TABLE4.values())).keys())
DECIMALS = 4


@pytest.fixture(scope="module")
def sim():
    return simulate(SEED)


@pytest.fixture(scope="module")
def table4(sim):
    metrics, thresholds = compute_metrics_table(sim)
    return metrics.set_index("architecture"), thresholds


# ------------------------------------------------------------------
# Базова цілісність датасету
# ------------------------------------------------------------------
def test_dataset_shapes(sim):
    assert sim.y.shape == (N_EVENTS,)
    assert sim.dist.shape == (N_EVENTS,)
    assert sim.test_mask.sum() == N_TEST
    for m in ("radar", "rf", "acoustic", "optical"):
        assert sim.scores[m].shape == (N_EVENTS,)
        assert sim.scores[m].min() >= 0.0 and sim.scores[m].max() <= 1.0


# ------------------------------------------------------------------
# Головний тест: метрики Таблиці 4 збігаються до 4 знаків
# ------------------------------------------------------------------
@pytest.mark.parametrize("arch", ARCH_NAMES)
@pytest.mark.parametrize("col", METRIC_COLS)
def test_table4_matches_published(table4, arch, col):
    metrics, _ = table4
    got = round(float(metrics.loc[arch, col]), DECIMALS)
    exp = EXPECTED_TABLE4[arch][col]
    assert got == pytest.approx(exp, abs=1e-4), (
        f"{arch}.{col}: отримано {got}, очікувано {exp}"
    )


# ------------------------------------------------------------------
# Детермінізм: повторний запуск дає ідентичні числа
# ------------------------------------------------------------------
def test_pipeline_is_deterministic():
    m1, _ = compute_metrics_table(simulate(SEED))
    m2, _ = compute_metrics_table(simulate(SEED))
    num_cols = m1.select_dtypes(include="number").columns
    np.testing.assert_array_equal(m1[num_cols].to_numpy(), m2[num_cols].to_numpy())


def test_downstream_tables_are_deterministic():
    """Pd за дальністю, за умовами, абляція та часовий резерв — теж відтворювані."""
    def run():
        sim = simulate(SEED)
        _, thr = compute_metrics_table(sim)
        return (
            pd_by_distance(sim, thr).round(DECIMALS),
            metrics_by_condition(sim, thr).round(DECIMALS),
            ablation(sim).round(DECIMALS),
            time_margin(sim, thr).round(DECIMALS),
        )

    a = run()
    b = run()
    for ta, tb in zip(a, b):
        num_cols = ta.select_dtypes(include="number").columns
        np.testing.assert_array_equal(ta[num_cols].to_numpy(), tb[num_cols].to_numpy())


# ------------------------------------------------------------------
# Змістовні перевірки: агентне злиття домінує
# ------------------------------------------------------------------
def test_agentic_dominates(table4):
    metrics, _ = table4
    assert metrics.loc["agentic_fusion", "pd"] > metrics.loc["static_fusion", "pd"]
    assert metrics.loc["static_fusion", "pd"] > metrics.loc["single_radar", "pd"]
    # менша латентність завдяки адаптивному гейтуванню
    assert (
        metrics.loc["agentic_fusion", "latency_median_s"]
        < metrics.loc["static_fusion", "latency_median_s"]
    )


def test_ablation_full_system_is_best():
    """Повна система має не гірший F1, ніж будь-яка конфігурація без модальності."""
    abl = ablation(simulate(SEED)).set_index("config")
    full = abl.loc["повна система", "f1"]
    for cfg in abl.index:
        if cfg != "повна система":
            assert full >= abl.loc[cfg, "f1"] - 1e-9
