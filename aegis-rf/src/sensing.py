"""Генерація спостережень: RSSI-відбитки та FTM/RTT-дальності.

Observation generation: RSSI fingerprints and FTM/RTT ranges.

RSSI:  s_{i,a} = pathloss(d_{i,a}) + N(0, sigma^2);  AP недоступний з imовірністю
       P_DROP_RSSI або якщо сигнал нижчий за поріг чутливості.
FTM:   r_{i,a} = d_{i,a} + bias_NLOS + N(0, sigma_ftm^2);  доступний лише для
       FTM-сумісних AP і з imовірністю (1 - P_DROP_FTM).

Усі функції приймають генератор ``rng`` — це зберігає точний порядок відтворюваності.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import environment as env


@dataclass
class Observations:
    """Пакет спостережень для набору подій."""

    pos: np.ndarray  # (E, 2) істинні позиції джерел
    rssi: np.ndarray  # (E, N_AP) виміряний RSSI, дБм
    rssi_avail: np.ndarray  # (E, N_AP) доступність RSSI
    ftm: np.ndarray  # (E, N_AP) виміряна дальність FTM, м
    ftm_avail: np.ndarray  # (E, N_AP) доступність FTM
    in_crit: np.ndarray  # (E,) чи є істинна позиція в критичній зоні

    def copy(self) -> "Observations":
        return Observations(
            self.pos.copy(), self.rssi.copy(), self.rssi_avail.copy(),
            self.ftm.copy(), self.ftm_avail.copy(), self.in_crit.copy(),
        )


def generate_positions(rng: np.random.Generator, n: int, crit_fraction: float = 0.45) -> np.ndarray:
    """Згенерувати ``n`` істинних позицій; частка ``crit_fraction`` — у критичній зоні."""
    n_crit = int(round(n * crit_fraction))
    n_free = n - n_crit

    crit = np.column_stack(
        [
            rng.uniform(env.CRIT_X0, env.CRIT_X1, n_crit),
            rng.uniform(env.CRIT_Y0, env.CRIT_Y1, n_crit),
        ]
    )
    # Позиції поза критичною зоною: відбір із прийняттям (rejection sampling)
    free = np.empty((n_free, 2))
    filled = 0
    while filled < n_free:
        cand = np.column_stack(
            [rng.uniform(0, env.AREA_W, n_free), rng.uniform(0, env.AREA_H, n_free)]
        )
        ok = ~env.in_critical(cand)
        take = cand[ok][: n_free - filled]
        free[filled : filled + len(take)] = take
        filled += len(take)

    pos = np.vstack([crit, free])
    order = rng.permutation(n)  # перемішуємо, щоб зони не йшли блоками
    return pos[order]


def observe_rssi(rng: np.random.Generator, pos: np.ndarray):
    """Згенерувати RSSI-спостереження. Повертає ``(rssi, avail)`` форми ``(E, N_AP)``."""
    dist = env.ap_distances(pos)
    mean = env.pathloss_mean(dist)
    rssi = mean + rng.normal(0.0, env.RSSI_SIGMA, dist.shape)
    dropped = rng.random(dist.shape) < env.P_DROP_RSSI
    avail = (~dropped) & (rssi > env.RSSI_SENSITIVITY)
    return rssi, avail


def observe_ftm(rng: np.random.Generator, pos: np.ndarray):
    """Згенерувати FTM/RTT-дальності. Повертає ``(ftm, avail)`` форми ``(E, N_AP)``."""
    dist = env.ap_distances(pos)
    nlos = rng.random(dist.shape) < env.FTM_P_NLOS
    bias = nlos * rng.exponential(env.FTM_NLOS_BIAS, dist.shape)
    ftm = dist + bias + rng.normal(0.0, env.FTM_SIGMA, dist.shape)
    ftm = np.maximum(ftm, env._DIST_FLOOR)
    dropped = rng.random(dist.shape) < env.P_DROP_FTM
    avail = env.FTM_CAPABLE[None, :] & (~dropped)
    return ftm, avail


def generate_observations(rng: np.random.Generator, n: int) -> Observations:
    """Повний конвеєр генерації подій (позиції → RSSI → FTM)."""
    pos = generate_positions(rng, n)
    rssi, rssi_avail = observe_rssi(rng, pos)
    ftm, ftm_avail = observe_ftm(rng, pos)
    return Observations(
        pos=pos, rssi=rssi, rssi_avail=rssi_avail,
        ftm=ftm, ftm_avail=ftm_avail, in_crit=env.in_critical(pos),
    )
