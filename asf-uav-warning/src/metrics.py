"""Метрики, калібрування порогів та довірчі інтервали.

Metrics, threshold calibration and bootstrap confidence intervals.

Протокол. Поріг спрацьовування ``tau`` кожної архітектури калібрується на
**тренувальній** частині за цільовим рівнем хибних тривог (квантиль фонових
оцінок). Усі метрики обчислюються **лише на тестовій частині** (19 200 подій).
95 % CI — percentile bootstrap, :data:`N_BOOT` перевибірок тестової множини.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, f1_score, roc_auc_score

from .asf_simulation import (
    ARCH_NAMES,
    CONDS,
    FAR_TARGET,
    N_BOOT,
    SEED,
    SimulationData,
    agentic_score,
)


def calibrate_threshold(
    scores: np.ndarray, y: np.ndarray, test_mask: np.ndarray, far_target: float
) -> float:
    """(1 - far_target)-квантиль фонових оцінок ТРЕНУВАЛЬНОЇ частини."""
    background_train = scores[(y == 0) & ~test_mask]
    return float(np.quantile(background_train, 1 - far_target))


def compute_metrics_table(sim: SimulationData):
    """Таблиця 4 статті: метрики + 95 % CI (bootstrap). Повертає ``(df, thresholds)``."""
    test_mask = sim.test_mask
    y = sim.y
    y_te = sim.y_test

    rows: list[dict] = []
    thresholds: dict[str, float] = {}
    boot_rng = np.random.default_rng(SEED + 1)

    for a in ARCH_NAMES:
        s = sim.arch[a]
        tau = calibrate_threshold(s, y, test_mask, FAR_TARGET[a])
        thresholds[a] = tau

        s_te = s[test_mask]
        pred = s_te >= tau
        lat_te = sim.latency[a][test_mask]

        pd_ = pred[y_te == 1].mean()
        far = pred[y_te == 0].mean()
        prec = pred[(y_te == 1) & pred].size / max(pred.sum(), 1)
        f1 = f1_score(y_te, pred)
        auc = roc_auc_score(y_te, s_te)
        brier = brier_score_loss(y_te, np.clip(s_te, 0, 1))

        # --- percentile bootstrap для Pd і FAR ---
        n = len(y_te)
        pd_b, far_b = [], []
        for _ in range(N_BOOT):
            idx = boot_rng.integers(0, n, n)
            yb, pb = y_te[idx], pred[idx]
            pd_b.append(pb[yb == 1].mean())
            far_b.append(pb[yb == 0].mean())
        lo_pd, hi_pd = np.percentile(pd_b, [2.5, 97.5])
        lo_far, hi_far = np.percentile(far_b, [2.5, 97.5])

        rows.append(
            dict(
                architecture=a, threshold=tau, precision=prec, pd=pd_, f1=f1, far=far,
                roc_auc=auc, brier=brier,
                pd_ci_lo=lo_pd, pd_ci_hi=hi_pd, far_ci_lo=lo_far, far_ci_hi=hi_far,
                latency_median_s=np.median(lat_te),
                latency_p95_s=np.percentile(lat_te, 95),
            )
        )

    return pd.DataFrame(rows), thresholds


def pd_by_distance(sim: SimulationData, thresholds: dict[str, float]) -> pd.DataFrame:
    """Pd БпЛА за кілометровими інтервалами дальності (рис. 3)."""
    bins = np.arange(0.5, 8.5 + 1e-9, 1.0)
    labels = [f"{a:.1f}–{b:.1f}" for a, b in zip(bins[:-1], bins[1:])]
    d_te = sim.dist[sim.test_mask]
    y_te = sim.y_test

    rows: list[dict] = []
    for a in ARCH_NAMES:
        pred = sim.arch[a][sim.test_mask] >= thresholds[a]
        for j in range(len(bins) - 1):
            sel = (y_te == 1) & (d_te >= bins[j]) & (d_te < bins[j + 1])
            rows.append(
                dict(
                    architecture=a, dist_bin=labels[j],
                    bin_center=(bins[j] + bins[j + 1]) / 2,
                    n=int(sel.sum()), pd=pred[sel].mean(),
                )
            )
    return pd.DataFrame(rows)


def metrics_by_condition(
    sim: SimulationData, thresholds: dict[str, float]
) -> pd.DataFrame:
    """Pd та FAR кожної архітектури окремо для кожної умови спостереження (рис. 5а)."""
    c_te = sim.cond[sim.test_mask]
    y_te = sim.y_test

    rows: list[dict] = []
    for a in ARCH_NAMES:
        pred = sim.arch[a][sim.test_mask] >= thresholds[a]
        for c in CONDS:
            sel = (y_te == 1) & (c_te == c)
            self_far = pred[(y_te == 0) & (c_te == c)].mean()
            rows.append(dict(architecture=a, cond=c, pd=pred[sel].mean(), far=self_far))
    return pd.DataFrame(rows)


def ablation(sim: SimulationData) -> pd.DataFrame:
    """Абляція агентного злиття: по черзі вилучаємо одну модальність (рис. 5)."""
    from .asf_simulation import MODALITIES

    y = sim.y
    y_te = sim.y_test
    test_mask = sim.test_mask

    rows: list[dict] = []
    for ex in [None, *MODALITIES]:
        s = agentic_score(sim.S, sim.A, sim.W_ag, excluded=ex)
        tau = calibrate_threshold(s, y, test_mask, FAR_TARGET["agentic_fusion"])
        pred = s[test_mask] >= tau
        rows.append(
            dict(
                config="повна система" if ex is None else f"без {ex}",
                f1=f1_score(y_te, pred),
                pd=pred[y_te == 1].mean(),
                far=pred[y_te == 0].mean(),
            )
        )
    return pd.DataFrame(rows)


def time_margin(sim: SimulationData, thresholds: dict[str, float]) -> pd.DataFrame:
    """Часовий резерв до цілі після машинного рішення та людського підтвердження.

    Використовує *живий* ``sim.rng`` (розташований після розіграшу латентностей),
    щоб зберегти точну послідовність відтворюваності оригінального ноутбука.
    """
    rng = sim.rng
    test_mask = sim.test_mask
    y_te = sim.y_test
    d_te = sim.dist[test_mask]

    pred_ag = sim.arch["agentic_fusion"][test_mask] >= thresholds["agentic_fusion"]
    det = (y_te == 1) & pred_ag  # виявлені БпЛА в тесті

    v = rng.uniform(15, 30, det.sum())  # швидкість цілі, м/с
    t_arr = 1000 * d_te[det] / v  # час підльоту, с
    lat_det = sim.latency["agentic_fusion"][test_mask][det]  # латентність машини
    t_human = rng.lognormal(np.log(6.0), 0.5, det.sum())  # час підтвердження оператором

    return pd.DataFrame(
        {
            "dist_km": d_te[det],
            "speed_ms": v,
            "t_arrival_s": t_arr,
            "margin_after_machine_s": t_arr - lat_det,
            "margin_after_human_s": t_arr - lat_det - t_human,
        }
    )
