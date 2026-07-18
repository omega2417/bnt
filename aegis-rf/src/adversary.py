"""Модель супротивника: evil twin, deceptive ranging, deauthentication.

Adversary model for the localization pipeline.

Реалізує три класи навмисних впливів із Розділу 1:

* **evil_twin** — клонування довіри: атакуючий підвищує уявний RSSI обраного AP,
  щоб «підтягнути» RSSI-локалізацію до хибної точки (п. 1.1.4);
* **deceptive_ranging** — маніпуляція часовою дальнометрією: додатне/від'ємне
  зміщення FTM-дальності обраного AP (п. 1.3.8);
* **deauth** — атака на доступність: примусове відключення каналу AP (п. 1.1.5).

Кожна функція повертає *нову* копію :class:`~aegis_rf.sensing.Observations`, не
змінюючи вхідні дані. Індекси/зміщення атак — детерміновані параметри.
"""

from __future__ import annotations

import numpy as np

from .sensing import Observations


def apply_evil_twin(obs: Observations, ap_index: int, boost_db: float = 15.0,
                    fraction: float = 1.0, rng: np.random.Generator | None = None) -> Observations:
    """Підняти RSSI AP ``ap_index`` на ``boost_db`` дБ для частки подій ``fraction``."""
    out = obs.copy()
    mask = _event_mask(len(out.pos), fraction, rng)
    out.rssi[mask, ap_index] += boost_db
    out.rssi_avail[mask, ap_index] = True  # клон завжди «видно»
    return out


def apply_deceptive_ranging(obs: Observations, ap_index: int, bias_m: float = 8.0,
                            fraction: float = 1.0, rng: np.random.Generator | None = None) -> Observations:
    """Внести зміщення ``bias_m`` (м) у FTM-дальність AP ``ap_index``."""
    out = obs.copy()
    mask = _event_mask(len(out.pos), fraction, rng) & out.ftm_avail[:, ap_index]
    out.ftm[mask, ap_index] = np.maximum(out.ftm[mask, ap_index] + bias_m, 0.3)
    return out


def apply_deauth(obs: Observations, ap_index: int, fraction: float = 1.0,
                 rng: np.random.Generator | None = None) -> Observations:
    """Відключити RSSI та FTM AP ``ap_index`` для частки подій ``fraction``."""
    out = obs.copy()
    mask = _event_mask(len(out.pos), fraction, rng)
    out.rssi_avail[mask, ap_index] = False
    out.ftm_avail[mask, ap_index] = False
    return out


def _event_mask(n: int, fraction: float, rng: np.random.Generator | None) -> np.ndarray:
    """Маска подій, до яких застосовується атака."""
    if fraction >= 1.0:
        return np.ones(n, dtype=bool)
    if rng is None:
        # Детермінований префікс, якщо генератор не передано
        mask = np.zeros(n, dtype=bool)
        mask[: int(round(n * fraction))] = True
        return mask
    return rng.random(n) < fraction
