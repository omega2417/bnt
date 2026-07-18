"""Spatial Attribution Record (SAR) — мінімальна одиниця доказу для SOC/SIEM.

Формує доказовий запис просторової атрибуції (п. 1.5.3): оцінена позиція,
невизначеність, апостеріорна ймовірність критичної зони, використані модальності,
ознаки цілісності (integrity flags) та провенанс. Придатний для відображення у
модель даних SIEM і подальшої SOAR-обробки (п. 1.5.4).

Записи *демонстраційні*; поля провенансу (seed, версія радіокарти) фіксують
відтворюваність, а не реальні часові мітки.
"""

from __future__ import annotations

import json

import numpy as np

from . import environment as env
from .localization import LocResult
from .sensing import Observations


def build_records(obs: Observations, res: LocResult, radiomap, *,
                  scenario: str, method: str, seed: int,
                  integrity_flags: np.ndarray | None = None,
                  indices=None) -> list[dict]:
    """Сформувати список SAR-записів для обраних подій ``indices`` (за замовч. усі)."""
    grid, _, _, _ = radiomap
    if indices is None:
        indices = range(len(obs.pos))

    records = []
    for i in indices:
        est = res.est[i]
        p_crit = float(res.p_crit[i])
        zone = "critical" if p_crit >= 0.5 else "allowed"
        flags = []
        if integrity_flags is not None and integrity_flags[i]:
            flags.append("modality_inconsistency")
        n_rssi = int(obs.rssi_avail[i].sum())
        n_ftm = int(obs.ftm_avail[i].sum())
        if n_rssi + n_ftm < 3:
            flags.append("sparse_observation")

        records.append(
            {
                "record_type": "SpatialAttributionRecord",
                "event_id": int(i),
                "estimate_xy_m": [round(float(est[0]), 3), round(float(est[1]), 3)],
                "position_error_m": round(float(res.error[i]), 3),
                "zone_posterior": {"critical": round(p_crit, 4),
                                    "allowed": round(1.0 - p_crit, 4)},
                "attributed_zone": zone,
                "modalities": {"rssi_aps": n_rssi, "ftm_aps": n_ftm},
                "integrity_flags": flags,
                "fusion_method": method,
                "provenance": {
                    "scenario": scenario,
                    "seed": int(seed),
                    "radiomap_grid_points": int(grid.shape[0]),
                    "n_ap": int(env.N_AP),
                },
            }
        )
    return records


def to_siem_json(records: list[dict]) -> str:
    """Серіалізувати SAR-записи у JSON (по одному об'єкту на рядок — SIEM-friendly)."""
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in records)


def integrity_flags(obs: Observations, radiomap) -> np.ndarray:
    """Ознака неузгодженості модальностей: розбіжність RSSI- та FTM-оцінок понад поріг.

    Використовується як детектор навмисної маніпуляції (evil twin / deceptive
    ranging): якщо позиції за окремими модальностями розходяться більше, ніж на
    ``gate`` метрів, подія позначається для перевірки оператором.
    """
    from .localization import localize_ftm, localize_rssi

    gate = 5.0
    r = localize_rssi(obs, radiomap).est
    f = localize_ftm(obs, radiomap).est
    disagreement = np.sqrt(((r - f) ** 2).sum(axis=1))
    return disagreement > gate
