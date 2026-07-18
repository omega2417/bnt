"""Тести відтворюваності та коректності пакета AEGIS-RF.

За фіксованого ``SEED = 80211`` усі метрики (точність локалізації + зонова
атрибуція) для 4 сценаріїв × 4 методів мають збігатися з еталонними значеннями
**до 4 знаків після коми**. Ці ж тести гарантують детермінізм та перевіряють
ключову тезу Розділу 1: **робастне злиття стійке до навмисних маніпуляцій**.

Запуск::

    cd aegis-rf
    pytest -q
"""

from __future__ import annotations

import numpy as np
import pytest

from src import attribution, environment as env
from src.localization import METHODS
from src.pipeline import N_EVENTS, SCENARIOS, SEED, run, run_experiment

DECIMALS = 4
METRIC_COLS = ["median_err_m", "rmse_m", "p90_err_m", "zone_acc", "crit_pd", "crit_far"]

# Еталонні значення (демонстраційне відтворення, seed=80211).
EXPECTED = {
    "clean/rssi": {"median_err_m": 2.179, "rmse_m": 3.5402, "p90_err_m": 5.6543, "zone_acc": 0.894, "crit_pd": 0.7822, "crit_far": 0.0145},
    "clean/ftm": {"median_err_m": 1.8086, "rmse_m": 4.5722, "p90_err_m": 6.1633, "zone_acc": 0.8333, "crit_pd": 0.64, "crit_far": 0.0085},
    "clean/fusion": {"median_err_m": 1.3673, "rmse_m": 2.9557, "p90_err_m": 4.5054, "zone_acc": 0.866, "crit_pd": 0.7111, "crit_far": 0.0073},
    "clean/robust": {"median_err_m": 1.2989, "rmse_m": 2.7621, "p90_err_m": 3.9835, "zone_acc": 0.892, "crit_pd": 0.7689, "crit_far": 0.0073},
    "evil_twin/rssi": {"median_err_m": 4.2699, "rmse_m": 5.1726, "p90_err_m": 7.9743, "zone_acc": 0.8113, "crit_pd": 0.5985, "crit_far": 0.0145},
    "evil_twin/ftm": {"median_err_m": 1.8086, "rmse_m": 4.5722, "p90_err_m": 6.1633, "zone_acc": 0.8333, "crit_pd": 0.64, "crit_far": 0.0085},
    "evil_twin/fusion": {"median_err_m": 1.5981, "rmse_m": 3.0337, "p90_err_m": 4.6298, "zone_acc": 0.8693, "crit_pd": 0.7215, "crit_far": 0.0097},
    "evil_twin/robust": {"median_err_m": 1.4811, "rmse_m": 2.9122, "p90_err_m": 4.4044, "zone_acc": 0.8887, "crit_pd": 0.7615, "crit_far": 0.0073},
    "deceptive_ranging/rssi": {"median_err_m": 2.179, "rmse_m": 3.5402, "p90_err_m": 5.6543, "zone_acc": 0.894, "crit_pd": 0.7822, "crit_far": 0.0145},
    "deceptive_ranging/ftm": {"median_err_m": 4.2559, "rmse_m": 6.6879, "p90_err_m": 9.7088, "zone_acc": 0.5913, "crit_pd": 0.0919, "crit_far": 0.0},
    "deceptive_ranging/fusion": {"median_err_m": 3.472, "rmse_m": 4.8615, "p90_err_m": 7.2945, "zone_acc": 0.6373, "crit_pd": 0.1956, "crit_far": 0.0012},
    "deceptive_ranging/robust": {"median_err_m": 1.6691, "rmse_m": 3.8743, "p90_err_m": 6.3783, "zone_acc": 0.832, "crit_pd": 0.6385, "crit_far": 0.0097},
    "deauth/rssi": {"median_err_m": 2.6969, "rmse_m": 4.1556, "p90_err_m": 6.5097, "zone_acc": 0.8587, "crit_pd": 0.7067, "crit_far": 0.017},
    "deauth/ftm": {"median_err_m": 2.0059, "rmse_m": 5.5512, "p90_err_m": 8.0222, "zone_acc": 0.8267, "crit_pd": 0.6296, "crit_far": 0.0121},
    "deauth/fusion": {"median_err_m": 1.5676, "rmse_m": 3.2281, "p90_err_m": 4.9194, "zone_acc": 0.8693, "crit_pd": 0.723, "crit_far": 0.0109},
    "deauth/robust": {"median_err_m": 1.5368, "rmse_m": 3.2057, "p90_err_m": 4.6139, "zone_acc": 0.8827, "crit_pd": 0.7541, "crit_far": 0.0121},
}


@pytest.fixture(scope="module")
def full_run():
    exp, results, table = run()
    return exp, results, table.set_index(["scenario", "method"])


# ------------------------------------------------------------------
# Головний тест: усі метрики збігаються з еталоном до 4 знаків
# ------------------------------------------------------------------
@pytest.mark.parametrize("key", list(EXPECTED))
@pytest.mark.parametrize("col", METRIC_COLS)
def test_metrics_match_reference(full_run, key, col):
    _, _, table = full_run
    scenario, method = key.split("/")
    got = round(float(table.loc[(scenario, method), col]), DECIMALS)
    exp = EXPECTED[key][col]
    assert got == pytest.approx(exp, abs=1e-4), f"{key}.{col}: {got} != {exp}"


# ------------------------------------------------------------------
# Детермінізм
# ------------------------------------------------------------------
def test_pipeline_is_deterministic():
    _, _, t1 = run()
    _, _, t2 = run()
    num = t1.select_dtypes("number").columns
    np.testing.assert_array_equal(t1[num].to_numpy(), t2[num].to_numpy())


# ------------------------------------------------------------------
# Цілісність середовища
# ------------------------------------------------------------------
def test_environment_and_events(full_run):
    exp, _, _ = full_run
    assert len(exp.base_obs.pos) == N_EVENTS
    grid, m, d, crit = exp.radiomap
    assert grid.shape[1] == 2 and m.shape[1] == env.N_AP
    assert crit.sum() > 0  # критична зона не порожня
    # частина подій — у критичній зоні
    assert 0.2 < exp.base_obs.in_crit.mean() < 0.7


# ------------------------------------------------------------------
# Ключова теза: робастне злиття стійке до атак
# ------------------------------------------------------------------
def test_robust_beats_naive_under_attack(full_run):
    _, _, table = full_run
    for scenario in ("evil_twin", "deceptive_ranging"):
        naive = table.loc[(scenario, "fusion"), "median_err_m"]
        robust = table.loc[(scenario, "robust"), "median_err_m"]
        assert robust < naive, f"{scenario}: robust {robust} !< naive {naive}"


def test_deceptive_ranging_breaks_naive_fusion(full_run):
    """Deceptive ranging має суттєво псувати наївне злиття, але не робастне."""
    _, _, table = full_run
    naive = table.loc[("deceptive_ranging", "fusion"), "median_err_m"]
    robust = table.loc[("deceptive_ranging", "robust"), "median_err_m"]
    assert naive > 2.5  # наївне злиття «підтягнуто» атакою
    assert robust < 2.0  # робастне — відновлює точність


def test_fusion_beats_single_modalities_clean(full_run):
    _, _, table = full_run
    fusion = table.loc[("clean", "fusion"), "median_err_m"]
    assert fusion < table.loc[("clean", "rssi"), "median_err_m"]
    assert fusion < table.loc[("clean", "ftm"), "median_err_m"]


# ------------------------------------------------------------------
# Spatial Attribution Record
# ------------------------------------------------------------------
def test_attribution_record_shape():
    from src.localization import localize

    exp = run_experiment()
    obs = exp.scenarios["evil_twin"]
    res = localize(obs, exp.radiomap, "robust")
    flags = attribution.integrity_flags(obs, exp.radiomap)
    recs = attribution.build_records(
        obs, res, exp.radiomap, scenario="evil_twin", method="robust",
        seed=SEED, integrity_flags=flags, indices=range(5),
    )
    assert len(recs) == 5
    r = recs[0]
    assert r["record_type"] == "SpatialAttributionRecord"
    assert set(r["zone_posterior"]) == {"critical", "allowed"}
    assert r["attributed_zone"] in ("critical", "allowed")
    # серіалізація в SIEM-JSON не падає
    assert attribution.to_siem_json(recs).count("\n") == 4


def test_all_methods_registered():
    assert set(METHODS) == {"rssi", "ftm", "fusion", "robust"}
    assert set(SCENARIOS) == {"clean", "evil_twin", "deceptive_ranging", "deauth"}
