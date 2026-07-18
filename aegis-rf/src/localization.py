"""Байєсівська локалізація та гібридне злиття модальностей.

Bayesian localization and hybrid modality fusion.

Правдоподібність позиції ``p`` за спостереженнями будується як добуток гауссових
членів по доступних AP (п. 1.2.4, 1.4.4):

* RSSI:  -0.5 * ((s_a - M_a(p)) / sigma_rssi)^2
* FTM:   -0.5 * ((r_a - ||p - AP_a||) / sigma_ftm)^2

Оцінка позиції — MAP (argmax апостеріорної щільності на RP-сітці). Апостеріорна
ймовірність перебування у критичній зоні — сума нормованої постеріорної маси по
RP усередині зони.

Чотири методи:

* ``rssi``   — лише RSSI-радіокарта;
* ``ftm``    — лише FTM/RTT-дальнометрія;
* ``fusion`` — зважений добуток правдоподібностей обох модальностей;
* ``robust`` — те саме зі стійким відсіюванням AP-викидів (evil twin / deceptive
  ranging): AP зі стандартизованим залишком понад поріг у поточному MAP
  вимикається, оцінка перераховується (ітеративне переважування).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import environment as env
from .sensing import Observations

# Ваги модальностей у злитті (довіра до RSSI-покриття vs FTM-геометрії)
W_RSSI = 1.0
W_FTM = 1.4

# Поріг стандартизованого залишку для робастного відсіювання AP
ROBUST_GATE = 3.0
ROBUST_ITERS = 2


@dataclass
class LocResult:
    """Результат локалізації набору подій одним методом."""

    est: np.ndarray  # (E, 2) оцінені позиції
    p_crit: np.ndarray  # (E,) апостеріорна P(критична зона)
    error: np.ndarray  # (E,) похибка локалізації, м


def _accum(values: np.ndarray, avail: np.ndarray, ref: np.ndarray,
           sigma: float, weights: np.ndarray | None = None) -> np.ndarray:
    """Накопичити 0.5*((value-ref)/sigma)^2 по AP → матриця ``(E, G)``.

    ``values``/``avail`` — ``(E, A)``; ``ref`` — ``(G, A)`` (радіокарта M або
    відстані D). Недоступні AP не враховуються; ``weights`` (E, A) множать внесок.
    """
    e, a = values.shape
    g = ref.shape[0]
    acc = np.zeros((e, g))
    for k in range(a):
        m = avail[:, k]
        if not m.any():
            continue
        diff = (values[m, k][:, None] - ref[None, :, k]) / sigma
        contr = 0.5 * diff * diff
        if weights is not None:
            contr = contr * weights[m, k][:, None]
        acc[m] += contr
    return acc


def _nll(obs: Observations, radiomap, w_rssi: float, w_ftm: float,
         wr: np.ndarray | None = None, wf: np.ndarray | None = None,
         use_rssi: bool = True, use_ftm: bool = True) -> np.ndarray:
    """Негативна лог-правдоподібність на сітці для заданих модальностей."""
    _, m, d_grid, _ = radiomap
    e = len(obs.pos)
    nll = np.zeros((e, m.shape[0]))
    if use_rssi:
        nll += w_rssi * _accum(obs.rssi, obs.rssi_avail, m, env.RSSI_SIGMA, wr)
    if use_ftm:
        nll += w_ftm * _accum(obs.ftm, obs.ftm_avail, d_grid, env.FTM_SIGMA, wf)
    return nll


def _finish(nll: np.ndarray, obs: Observations, radiomap) -> LocResult:
    grid, _, _, crit_mask = radiomap
    idx = np.argmin(nll, axis=1)
    est = grid[idx]
    # Апостеріорна маса в критичній зоні (softmax зі стабілізацією)
    shifted = nll - nll.min(axis=1, keepdims=True)
    w = np.exp(-shifted)
    w /= w.sum(axis=1, keepdims=True)
    p_crit = w[:, crit_mask].sum(axis=1)
    error = np.sqrt(((est - obs.pos) ** 2).sum(axis=1))
    return LocResult(est=est, p_crit=p_crit, error=error)


def localize_rssi(obs: Observations, radiomap) -> LocResult:
    return _finish(_nll(obs, radiomap, W_RSSI, W_FTM, use_ftm=False), obs, radiomap)


def localize_ftm(obs: Observations, radiomap) -> LocResult:
    return _finish(_nll(obs, radiomap, W_RSSI, W_FTM, use_rssi=False), obs, radiomap)


def localize_fusion(obs: Observations, radiomap) -> LocResult:
    return _finish(_nll(obs, radiomap, W_RSSI, W_FTM), obs, radiomap)


def localize_robust(obs: Observations, radiomap) -> LocResult:
    """Гібридне злиття з ітеративним відсіюванням AP-викидів."""
    grid, m, d_grid, _ = radiomap
    wr = obs.rssi_avail.astype(float)
    wf = obs.ftm_avail.astype(float)

    nll = _nll(obs, radiomap, W_RSSI, W_FTM, wr=wr, wf=wf)
    for _ in range(ROBUST_ITERS):
        idx = np.argmin(nll, axis=1)
        # Стандартизовані залишки в поточному MAP
        m_at = m[idx]  # (E, N_AP)
        d_at = d_grid[idx]  # (E, N_AP)
        resid_r = np.abs(obs.rssi - m_at) / env.RSSI_SIGMA
        resid_f = np.abs(obs.ftm - d_at) / env.FTM_SIGMA
        wr = obs.rssi_avail.astype(float) * (resid_r <= ROBUST_GATE)
        wf = obs.ftm_avail.astype(float) * (resid_f <= ROBUST_GATE)
        # Захист від виродженого випадку: якщо все відсіяно — лишаємо доступне
        wr = _guard(wr, obs.rssi_avail)
        wf = _guard(wf, obs.ftm_avail)
        nll = _nll(obs, radiomap, W_RSSI, W_FTM, wr=wr, wf=wf)
    return _finish(nll, obs, radiomap)


def _guard(weights: np.ndarray, avail: np.ndarray) -> np.ndarray:
    """Не дозволяти повністю відсіяти всі AP події (лишаємо доступні як є)."""
    kept = weights.sum(axis=1)
    empty = kept == 0
    if empty.any():
        weights = weights.copy()
        weights[empty] = avail[empty].astype(float)
    return weights


METHODS = {
    "rssi": localize_rssi,
    "ftm": localize_ftm,
    "fusion": localize_fusion,
    "robust": localize_robust,
}


def localize(obs: Observations, radiomap, method: str) -> LocResult:
    """Локалізувати події заданим методом (``rssi`` | ``ftm`` | ``fusion`` | ``robust``)."""
    return METHODS[method](obs, radiomap)
