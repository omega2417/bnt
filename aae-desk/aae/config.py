"""Конфігурація правил агентів. Змінюється лише через Desk.revise_config (завдання 10)."""
from __future__ import annotations

import copy

from .autonomy import DEFAULT_MATRIX

DEFAULT_CONFIG = {
    "version": 1,
    "agency": "Демонстраційний орган",
    "autonomy_matrix": DEFAULT_MATRIX,
    "z1_sample_rate": 0.25,          # частка тверджень, які аналітик перевіряє в зоні Z1
    "currency_years": 5,             # поріг давності для наукових і аналітичних джерел
    "agents": {                      # розкриття версій агентів у кожному записі журналу
        "F1": "discovery-agent/1.0 (правила, локальний знімок метаданих)",
        "F2": "provenance-agent/1.0 (правила, реєстр довірених видавців)",
        "F3": "appraisal-agent/1.0 (правила)",
        "F4": "briefing-agent/1.0 (сценарні твердження, шаблон довідки)",
    },
    # Реєстр довірених видавців: простір ідентифікаторів -> очікуваний видавець.
    "trusted_issuers": {
        "celex": ["European Parliament and Council"],
        "rada": ["Президент України", "Верховна Рада України", "Кабінет Міністрів України"],
        "oecd": ["OECD Council"],
        "doi_prefix": {
            "10.6028": ["National Institute of Standards and Technology"],
            "10.1111": ["Wiley"], "10.1093": ["Oxford University Press"],
            "10.1016": ["Elsevier"], "10.3390": ["MDPI"], "10.1177": ["SAGE"],
            "10.1145": ["Association for Computing Machinery"], "10.1007": ["Springer"],
            "10.1080": ["Taylor & Francis"],
        },
    },
}


def default_config() -> dict:
    return copy.deepcopy(DEFAULT_CONFIG)
