"""Оркестрація експерименту: сценарії × методи → таблиця метрик.

Experiment orchestration: scenarios x methods -> metrics table.

Сценарії:

* ``clean``             — без атак (базова точність);
* ``evil_twin``         — RSSI обраного AP підвищено (клонування довіри);
* ``deceptive_ranging`` — FTM-дальність обраного AP зміщено;
* ``deauth``            — обраний AP відключено (атака на доступність).

Для кожного сценарію обчислюються всі чотири методи локалізації. Уся випадковість
походить з єдиного генератора ``rng(SEED)`` у фіксованому порядку, тож результати
відтворюються біт-у-біт.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import adversary, environment as env
from .localization import METHODS, localize
from .metrics import evaluate, metrics_table
from .sensing import Observations, generate_observations

SEED = 80211  # зерно відтворюваності (натяк на IEEE 802.11)
N_EVENTS = 1500

# Параметри атак (детерміновані)
EVIL_TWIN_AP = 4  # центральний AP (15, 12)
EVIL_TWIN_BOOST_DB = 15.0
DECEPTIVE_AP = 5  # FTM-сумісний AP біля критичної зони (24, 18)
DECEPTIVE_BIAS_M = 8.0
DEAUTH_AP = 3  # кутовий AP (28, 22)

SCENARIOS = ["clean", "evil_twin", "deceptive_ranging", "deauth"]


@dataclass
class Experiment:
    radiomap: tuple
    base_obs: Observations
    scenarios: dict  # {name: Observations}


def build_scenarios(rng: np.random.Generator, base: Observations) -> dict:
    """Побудувати спостереження для кожного сценарію з базового набору."""
    return {
        "clean": base,
        "evil_twin": adversary.apply_evil_twin(base, EVIL_TWIN_AP, EVIL_TWIN_BOOST_DB),
        "deceptive_ranging": adversary.apply_deceptive_ranging(base, DECEPTIVE_AP, DECEPTIVE_BIAS_M),
        "deauth": adversary.apply_deauth(base, DEAUTH_AP),
    }


def run_experiment(seed: int = SEED, n_events: int = N_EVENTS) -> Experiment:
    """Згенерувати середовище, події та всі сценарії атак."""
    radiomap = env.build_radiomap()
    rng = np.random.default_rng(seed)
    base = generate_observations(rng, n_events)
    scenarios = build_scenarios(rng, base)
    return Experiment(radiomap=radiomap, base_obs=base, scenarios=scenarios)


def compute_results(exp: Experiment, boot_seed: int = SEED + 1) -> dict:
    """Обчислити метрики для всіх сценаріїв і методів → ``{scenario: {method: row}}``."""
    results = {}
    for sc_name, obs in exp.scenarios.items():
        results[sc_name] = {}
        for method in METHODS:
            res = localize(obs, exp.radiomap, method)
            results[sc_name][method] = evaluate(res, obs, boot_seed)
    return results


def run(seed: int = SEED, n_events: int = N_EVENTS):
    """Повний прогін: повертає ``(experiment, results_dict, metrics_dataframe)``."""
    exp = run_experiment(seed, n_events)
    results = compute_results(exp)
    table = metrics_table(results)
    return exp, results, table
