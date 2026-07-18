"""AEGIS-RF — Adversary-rEsistant Geolocation & Integrity for wi-fi Signals.

Демонстраційний відтворюваний пакет гібридної байєсівської просторової
ідентифікації Wi-Fi у критичній інформаційній інфраструктурі (КІІ): злиття
RSSI-радіокарти та FTM/RTT-дальнометрії, робастність до навмисних маніпуляцій
(evil twin, deceptive ranging, deauth), зонова атрибуція та доказові записи
Spatial Attribution Record для інтеграції із SOC/SIEM/SOAR.

Прикладний програмний проєкт за Розділом 1 дисертаційного дослідження.
Усі числові результати — демонстраційні (синтетична модель, не польові виміри).
"""

from . import (
    adversary,
    attribution,
    environment,
    localization,
    make_figures,
    metrics,
    pipeline,
    sensing,
)

__all__ = [
    "environment", "sensing", "adversary", "localization",
    "metrics", "attribution", "make_figures", "pipeline",
]
