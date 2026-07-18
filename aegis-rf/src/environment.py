"""Синтетичне середовище КІІ: геометрія, зони, точки доступу, RSSI-радіокарта.

Synthetic critical-infrastructure (CII) indoor environment: geometry, zones,
access points and the RSSI radiomap.

Модель відтворює постановку Розділу 1: закрите приміщення КІІ з набором точок
доступу IEEE 802.11 (частина з яких підтримує FTM), виділеною **критичною зоною**
(напр. серверна) та регулярною сіткою опорних точок (RP-grid) для байєсівської
локалізації за RSSI-радіокартою. Радіокарта будується з детермінованої моделі
загасання log-distance — це «версіонований статистичний об'єкт» (п. 1.2.5).

Модуль залежить лише від :mod:`numpy`.
"""

from __future__ import annotations

import numpy as np

# ============================================================
# Геометрія приміщення / Room geometry (метри)
# ============================================================
AREA_W = 30.0  # ширина, м
AREA_H = 24.0  # глибина, м
GRID_STEP = 1.0  # крок RP-сітки радіокарти, м

# Точки доступу (anchors). Останні дві — всередині/біля критичної зони.
AP_POSITIONS = np.array(
    [
        [2.0, 2.0],
        [28.0, 2.0],
        [2.0, 22.0],
        [28.0, 22.0],
        [15.0, 12.0],
        [24.0, 18.0],
    ]
)
N_AP = len(AP_POSITIONS)

# Які AP підтримують FTM/RTT (802.11mc/az) — операційна асиметрія (п. 1.3.6).
FTM_CAPABLE = np.array([True, True, False, True, False, True])

# ============================================================
# Критична зона (напр. серверна) / Critical zone rectangle
# ============================================================
CRIT_X0, CRIT_X1 = 21.0, 29.0
CRIT_Y0, CRIT_Y1 = 15.0, 23.0

# ============================================================
# Параметри радіоканалу / Radio-channel parameters
# ============================================================
RSSI_P0 = -40.0  # опорна потужність на d0, дБм
RSSI_D0 = 1.0  # опорна відстань, м
RSSI_N = 3.0  # показник загасання (indoor)
RSSI_SIGMA = 4.0  # тіньове завмирання (shadowing), дБ
RSSI_SENSITIVITY = -92.0  # поріг чутливості приймача, дБм

FTM_SIGMA = 1.2  # СКВ похибки дальності FTM, м
FTM_NLOS_BIAS = 3.0  # середнє додатне зміщення NLOS, м
FTM_P_NLOS = 0.25  # частка NLOS-вимірювань

P_DROP_RSSI = 0.03  # ймовірність відсутності RSSI від AP
P_DROP_FTM = 0.15  # ймовірність відмови FTM-сеансу (енергетика/асиметрія)

_DIST_FLOOR = 0.3  # нижня межа відстані, щоб log10 не розходився


def build_grid(step: float = GRID_STEP) -> np.ndarray:
    """Регулярна RP-сітка кандидатних позицій, форма ``(G, 2)``."""
    xs = np.arange(step / 2, AREA_W, step)
    ys = np.arange(step / 2, AREA_H, step)
    gx, gy = np.meshgrid(xs, ys)
    return np.column_stack([gx.ravel(), gy.ravel()])


def in_critical(points: np.ndarray) -> np.ndarray:
    """Булева маска: чи належить точка критичній зоні. ``points`` форми ``(..., 2)``."""
    x, y = points[..., 0], points[..., 1]
    return (x >= CRIT_X0) & (x <= CRIT_X1) & (y >= CRIT_Y0) & (y <= CRIT_Y1)


def ap_distances(points: np.ndarray) -> np.ndarray:
    """Евклідові відстані від кожної точки до кожного AP → ``(P, N_AP)``."""
    diff = points[:, None, :] - AP_POSITIONS[None, :, :]
    dist = np.sqrt((diff**2).sum(-1))
    return np.maximum(dist, _DIST_FLOOR)


def pathloss_mean(dist: np.ndarray) -> np.ndarray:
    """Середній RSSI за log-distance моделлю (без завмирання), обрізаний знизу."""
    rssi = RSSI_P0 - 10.0 * RSSI_N * np.log10(dist / RSSI_D0)
    return np.maximum(rssi, RSSI_SENSITIVITY)


def build_radiomap(step: float = GRID_STEP):
    """Побудувати радіокарту. Повертає ``(grid, M, D_grid, crit_mask)``.

    * ``grid``      — ``(G, 2)`` координати RP;
    * ``M``         — ``(G, N_AP)`` середній RSSI у кожній RP для кожного AP;
    * ``D_grid``    — ``(G, N_AP)`` відстані RP→AP (для FTM-правдоподібності);
    * ``crit_mask`` — ``(G,)`` булева маска RP усередині критичної зони.
    """
    grid = build_grid(step)
    d_grid = ap_distances(grid)
    m = pathloss_mean(d_grid)
    crit_mask = in_critical(grid)
    return grid, m, d_grid, crit_mask
