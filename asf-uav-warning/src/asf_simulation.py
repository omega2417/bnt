"""Генеративна Monte Carlo модель агентного мультисенсорного виявлення БпЛА.

Generative Monte Carlo model of agentic multisensor UAV detection.

Цей модуль містить *лише* синтетичну генеративну модель: параметри сенсорів,
генерацію подій та побудову оцінок трьох архітектур ухвалення рішення. Він не
залежить від ``matplotlib`` чи ``sklearn`` — тільки ``numpy`` та ``pandas``.

Усі числові результати є **демонстраційними**: вони характеризують синтетичну
модель, параметри якої задані авторами статті, а не реальні вимірювання.

Порядок звертань до спільного генератора ``rng`` збережено точно таким, як в
оригінальному ноутбуці, тому за ``SEED = 20260`` метрики відтворюються біт-у-біт.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

# ============================================================
# Гіперпараметри відтворюваності / Reproducibility hyperparameters
# ============================================================
SEED = 20260  # фіксоване зерно відтворюваності
N_EVENTS = 64_000  # загальна кількість подій Monte Carlo
N_TEST = 19_200  # розмір тестової частини (30 %)
N_BOOT = 800  # кількість bootstrap-перевибірок для 95 % CI

MODALITIES = ["radar", "rf", "acoustic", "optical"]

# --- Параметри генеративної моделі (відкалібровані під цільові метрики статті) ---
BASE = {"radar": 0.885, "rf": 0.93, "acoustic": 0.84, "optical": 0.90}  # β_m
DSLOPE = {"radar": 0.052, "rf": 0.048, "acoustic": 0.075, "optical": 0.058}  # α_m, 1/км
NOISE = {"radar": 0.185, "rf": 0.13, "acoustic": 0.175, "optical": 0.15}  # σ_m
P_DROP = {"radar": 0.04, "rf": 0.06, "acoustic": 0.08, "optical": 0.07}  # p_drop

# Штрафи умов π_m(c): наскільки умова "гасить" відповідну модальність
PENALTY = {
    "radar": {"clear": 0.00, "rain": 0.06, "fog": 0.02, "night": 0.00, "ew_jam": 0.30},
    "rf": {"clear": 0.00, "rain": 0.02, "fog": 0.00, "night": 0.00, "ew_jam": 0.35},
    "acoustic": {"clear": 0.00, "rain": 0.20, "fog": 0.05, "night": -0.02, "ew_jam": 0.00},
    "optical": {"clear": 0.00, "rain": 0.15, "fog": 0.35, "night": 0.30, "ew_jam": 0.00},
}

CONDS = np.array(["clear", "rain", "fog", "night", "ew_jam"])
P_CONDS = [0.42, 0.18, 0.12, 0.18, 0.10]

BACKGROUND_LEVEL = 0.22  # константний шумовий рівень μ_m для фону

# --- Архітектури ухвалення рішення ---
FUSION_WEIGHTS = np.array([0.35, 0.30, 0.15, 0.20])  # фіксовані ваги w_m
LAMBDA_ADAPT = 4.0  # λ для контекстно-адаптивних ваг агентного злиття

ARCH_NAMES = ["single_radar", "static_fusion", "agentic_fusion"]
ARCH_TITLES = {
    "single_radar": "Один радарний агент",
    "static_fusion": "Статичне злиття",
    "agentic_fusion": "Агентне злиття",
}
ARCH_COLORS = {
    "single_radar": "#777777",
    "static_fusion": "#EE854A",
    "agentic_fusion": "#4878CF",
}

# --- Латентності рішення, с (логнормальні; медіана = exp(mu)) ---
LAT_MED = {"single_radar": 1.23, "static_fusion": 1.56, "agentic_fusion": 0.85}
LAT_SIG = {"single_radar": 0.40, "static_fusion": 0.35, "agentic_fusion": 0.45}

# --- Цільові рівні хибних тривог для калібрування порогів ---
FAR_TARGET = {"single_radar": 0.051, "static_fusion": 0.043, "agentic_fusion": 0.035}


@dataclass
class SimulationData:
    """Контейнер результатів однієї Monte Carlo симуляції.

    Поле ``rng`` зберігає *живий* генератор, розташований одразу після розіграшу
    латентностей, — це дозволяє наступним крокам (напр. часовому резерву в
    :func:`asf_uav.metrics.time_margin`) продовжити ту саму послідовність.
    """

    y: np.ndarray  # мітки класу (0 = фон, 1 = БпЛА)
    dist: np.ndarray  # дальність, км
    cond: np.ndarray  # умови спостереження
    scores: dict[str, np.ndarray]  # оцінки сенсорних агентів s_{i,m}
    avail: dict[str, np.ndarray]  # доступність сенсорів a_{i,m}
    S: np.ndarray  # (4, N) стек оцінок
    A: np.ndarray  # (4, N) стек доступності
    W_ag: np.ndarray  # (4, N) контекстно-адаптивні ваги
    arch: dict[str, np.ndarray]  # оцінки трьох архітектур
    latency: dict[str, np.ndarray]  # латентності трьох архітектур
    test_mask: np.ndarray  # булева маска тестової частини
    rng: np.random.Generator  # живий генератор після латентностей

    @property
    def y_test(self) -> np.ndarray:
        return self.y[self.test_mask]


def make_rng(seed: int = SEED) -> np.random.Generator:
    """Створити фіксований PCG64-генератор відтворюваності."""
    return np.random.default_rng(seed)


def _condition_penalty(modality: str, cond: np.ndarray) -> np.ndarray:
    """Вектор штрафів π_m(c_i) для заданої модальності."""
    return np.array([PENALTY[modality][c] for c in cond])


def generate_events(rng: np.random.Generator):
    """Згенерувати сирі масиви подій та оцінок сенсорів.

    Генеративна модель оцінки модальності ``m``::

        s_{i,m} = clip(mu_m(y_i, d_i, c_i) + eps_{i,m}, 0, 1),  eps ~ N(0, sigma_m^2)

    де для БпЛА ``mu_m = BASE_m - DSLOPE_m * d_i - PENALTY_m(c_i)``, а для фону
    ``mu_m = BACKGROUND_LEVEL``. Кожен сенсор із імовірністю ``P_DROP_m`` недоступний.
    """
    y = rng.integers(0, 2, N_EVENTS)  # 0 = фон, 1 = БпЛА
    dist = rng.uniform(0.5, 8.0, N_EVENTS)  # дальність, км
    cond = rng.choice(CONDS, N_EVENTS, p=P_CONDS)  # умови спостереження

    scores: dict[str, np.ndarray] = {}
    avail: dict[str, np.ndarray] = {}
    for m in MODALITIES:
        pen = _condition_penalty(m, cond)
        mu = np.where(y == 1, BASE[m] - DSLOPE[m] * dist - pen, BACKGROUND_LEVEL)
        scores[m] = np.clip(mu + rng.normal(0, NOISE[m], N_EVENTS), 0, 1)
        avail[m] = rng.random(N_EVENTS) > P_DROP[m]  # True = сенсор доступний
    return y, dist, cond, scores, avail


def adaptive_weights(cond: np.ndarray) -> np.ndarray:
    """Контекстно-адаптивні ваги агентного злиття w^{ag}_{i,m}.

    Модальність, деградована поточними умовами, експоненційно послаблюється::

        w^{ag}_{i,m} = w_m * exp(-lambda * PENALTY_m(c_i))
    """
    w_ag = np.tile(FUSION_WEIGHTS[:, None], (1, len(cond))).astype(float)
    for i, m in enumerate(MODALITIES):
        w_ag[i] *= np.exp(-LAMBDA_ADAPT * _condition_penalty(m, cond))
    return w_ag


def build_architectures(scores, avail, cond, rng: np.random.Generator):
    """Побудувати оцінки трьох архітектур та їх латентності.

    Повертає ``(S, A, W_ag, arch, latency)``. Латентності розігруються зі
    *спільного* ``rng`` у порядку :data:`ARCH_NAMES`.
    """
    S = np.stack([scores[m] for m in MODALITIES])  # (4, N)
    A = np.stack([avail[m] for m in MODALITIES])  # (4, N)
    W = FUSION_WEIGHTS[:, None]

    # Архітектура 1: один радарний агент (0, якщо радар недоступний)
    s_radar = np.where(avail["radar"], scores["radar"], 0.0)

    # Архітектура 2: статичне злиття (фіксовані ваги по доступних сенсорах)
    Wm = W * A
    s_static = (S * Wm).sum(0) / np.maximum(Wm.sum(0), 1e-9)

    # Архітектура 3: агентне злиття (контекстно-адаптивні ваги)
    W_ag = adaptive_weights(cond)
    Wm2 = W_ag * A
    s_agentic = (S * Wm2).sum(0) / np.maximum(Wm2.sum(0), 1e-9)

    arch = {
        "single_radar": s_radar,
        "static_fusion": s_static,
        "agentic_fusion": s_agentic,
    }

    latency = {
        a: rng.lognormal(np.log(LAT_MED[a]), LAT_SIG[a], N_EVENTS) for a in ARCH_NAMES
    }
    return S, A, W_ag, arch, latency


def agentic_score(S, A, W_ag, excluded: str | None = None) -> np.ndarray:
    """Оцінка агентного злиття з можливим вилученням однієї модальності (абляція)."""
    keep = [m for m in MODALITIES if m != excluded]
    idx = [MODALITIES.index(m) for m in keep]
    Wm = W_ag[idx] * A[idx]
    return (S[idx] * Wm).sum(0) / np.maximum(Wm.sum(0), 1e-9)


def simulate(seed: int = SEED) -> SimulationData:
    """Повний конвеєр генерації: події → оцінки архітектур → латентності."""
    rng = make_rng(seed)
    y, dist, cond, scores, avail = generate_events(rng)
    S, A, W_ag, arch, latency = build_architectures(scores, avail, cond, rng)
    test_mask = np.arange(N_EVENTS) >= N_EVENTS - N_TEST
    return SimulationData(
        y=y, dist=dist, cond=cond, scores=scores, avail=avail,
        S=S, A=A, W_ag=W_ag, arch=arch, latency=latency,
        test_mask=test_mask, rng=rng,
    )


def to_dataframe(sim: SimulationData) -> pd.DataFrame:
    """Зібрати повний датафрейм подій (для збереження в ``data/``)."""
    df = pd.DataFrame({"y": sim.y, "dist_km": sim.dist, "cond": sim.cond})
    for m in MODALITIES:
        df[f"s_{m}"] = sim.scores[m]
        df[f"avail_{m}"] = sim.avail[m]
    df["split"] = np.where(sim.test_mask, "test", "train")
    for a in ARCH_NAMES:
        df[f"score_{a}"] = sim.arch[a]
        df[f"lat_{a}"] = sim.latency[a]
    return df
