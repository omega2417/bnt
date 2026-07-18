"""Метрики точності локалізації та зонової атрибуції з bootstrap-CI.

Localization-accuracy and zone-attribution metrics with bootstrap CIs.

* Точність позиціонування: медіана, RMSE, P90 похибки (м);
* Зонова атрибуція (критична зона): точність, Pd (виявлення істинно-критичних),
  FAR (хибні тривоги на дозволених позиціях);
* 95 % CI медіанної похибки — percentile bootstrap.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .localization import LocResult
from .sensing import Observations

N_BOOT = 600
CRIT_THRESHOLD = 0.5  # поріг рішення P(критична зона) → тривога


def localization_metrics(res: LocResult) -> dict:
    """Медіана, RMSE та P90 похибки локалізації (м)."""
    err = res.error
    return {
        "median_err_m": float(np.median(err)),
        "rmse_m": float(np.sqrt(np.mean(err**2))),
        "p90_err_m": float(np.percentile(err, 90)),
    }


def attribution_metrics(res: LocResult, obs: Observations) -> dict:
    """Метрики зонової атрибуції: accuracy, Pd, FAR."""
    pred = res.p_crit >= CRIT_THRESHOLD
    true = obs.in_crit
    pd_ = pred[true].mean() if true.any() else float("nan")
    far = pred[~true].mean() if (~true).any() else float("nan")
    return {
        "zone_acc": float((pred == true).mean()),
        "crit_pd": float(pd_),
        "crit_far": float(far),
    }


def bootstrap_median_ci(res: LocResult, seed: int, n_boot: int = N_BOOT):
    """95 % percentile-bootstrap CI медіанної похибки локалізації."""
    err = res.error
    n = len(err)
    rng = np.random.default_rng(seed)
    meds = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, n)
        meds[b] = np.median(err[idx])
    lo, hi = np.percentile(meds, [2.5, 97.5])
    return float(lo), float(hi)


def evaluate(res: LocResult, obs: Observations, boot_seed: int) -> dict:
    """Повний набір метрик для одного методу в одному сценарії."""
    row = {}
    row.update(localization_metrics(res))
    row.update(attribution_metrics(res, obs))
    lo, hi = bootstrap_median_ci(res, boot_seed)
    row["median_ci_lo"] = lo
    row["median_ci_hi"] = hi
    return row


def metrics_table(results: dict) -> pd.DataFrame:
    """Зібрати таблицю метрик з вкладеного словника ``{scenario: {method: row}}``."""
    rows = []
    for scenario, methods in results.items():
        for method, row in methods.items():
            rows.append({"scenario": scenario, "method": method, **row})
    return pd.DataFrame(rows)
