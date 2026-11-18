"""Градуйована автономія агентів (рис. 5 публікації).

Зона Z1-Z4 визначається наслідками рішення та невизначеністю доказів.
Тригери ескалації переводять завдання в суворішу зону. Матриця є
дискретизацією рис. 5 і зберігається в конфігурації, яку можна змінити
лише за процедурою завдання 10 (пропонує аналітик, затверджує посадова особа).
"""
from __future__ import annotations

CONSEQUENCES = {
    "routine": "рутинне операційне",
    "tactical": "тактичне (підрозділ)",
    "institutional": "інституційне (орган)",
    "strategic": "стратегічне (національне)",
}
UNCERTAINTIES = {
    "low": "низька: усталені, узгоджені джерела",
    "moderate": "помірна",
    "high": "висока: суперечливі, нові або неповні дані",
}
TRIGGERS = {
    "source_conflict": "джерела суперечать одне одному",
    "provenance_unresolved": "походження джерела не вдалося встановити",
    "novel_threat": "нова загроза",
    "cross_jurisdiction": "докази однієї юрисдикції застосовано до іншої",
    "classified": "задіяно інформацію з обмеженим доступом",
}

DEFAULT_MATRIX = {
    "low":      {"routine": 1, "tactical": 2, "institutional": 2, "strategic": 3},
    "moderate": {"routine": 2, "tactical": 2, "institutional": 3, "strategic": 4},
    "high":     {"routine": 2, "tactical": 3, "institutional": 4, "strategic": 4},
}

# Що дозволено агентам у кожній зоні та які людські перевірки обов'язкові.
ZONES = {
    1: {"name": "Виконують агенти, вибірковий аудит",
        "agent_functions": ["F1", "F2", "F3", "F4"],
        "g1": "sample", "second_reviewer": False,
        "note": "агенти виконують пошук і відбір; аналітики перевіряють вибірку записів"},
    2: {"name": "Пропонують агенти, перевіряє аналітик",
        "agent_functions": ["F1", "F2", "F3", "F4"],
        "g1": "all", "second_reviewer": False,
        "note": "агенти готують проєкт; кожне твердження проходить G1"},
    3: {"name": "Веде аналітик, агенти допомагають",
        "agent_functions": ["F1", "F2"],
        "g1": "all", "second_reviewer": False,
        "note": "агенти обмежені пошуком і перевіркою походження"},
    4: {"name": "Дорадче (деліберативне) рішення",
        "agent_functions": ["F1"],
        "g1": "all", "second_reviewer": True,
        "note": "агенти лише знаходять джерела; другий рецензент і зафіксована окрема думка до G2"},
}

FUNCTIONS = {
    "F1": "Пошук джерел (discovery)",
    "F2": "Перевірка походження (provenance)",
    "F3": "Оцінювання актуальності та застосовності (appraisal)",
    "F4": "Підготовка довідки (briefing)",
}


def base_zone(consequence: str, uncertainty: str, matrix: dict | None = None) -> int:
    matrix = matrix or DEFAULT_MATRIX
    if consequence not in CONSEQUENCES:
        raise ValueError(f"Невідомий рівень наслідків: {consequence}")
    if uncertainty not in UNCERTAINTIES:
        raise ValueError(f"Невідомий рівень невизначеності: {uncertainty}")
    return int(matrix[uncertainty][consequence])


def effective_zone(consequence: str, uncertainty: str, triggers=(), matrix: dict | None = None) -> int:
    """Базова зона плюс один рівень, якщо спрацював хоча б один тригер (не вище Z4)."""
    unknown = [t for t in triggers if t not in TRIGGERS]
    if unknown:
        raise ValueError(f"Невідомі тригери: {unknown}")
    zone = base_zone(consequence, uncertainty, matrix)
    return min(4, zone + 1) if triggers else zone


def agent_may(zone: int, function: str) -> bool:
    return function in ZONES[zone]["agent_functions"]


def validate_matrix(matrix: dict) -> None:
    """Матриця має бути повною та монотонною: зона не знижується зі зростанням ризику."""
    cons, unc = list(CONSEQUENCES), list(UNCERTAINTIES)
    for u in unc:
        for c in cons:
            if matrix.get(u, {}).get(c) not in (1, 2, 3, 4):
                raise ValueError(f"Матриця автономії: немає коректної зони для ({u}, {c})")
    for ui, u in enumerate(unc):
        for ci, c in enumerate(cons):
            if ci and matrix[u][c] < matrix[u][cons[ci - 1]]:
                raise ValueError("Матриця автономії має не спадати зі зростанням наслідків")
            if ui and matrix[u][c] < matrix[unc[ui - 1]][c]:
                raise ValueError("Матриця автономії має не спадати зі зростанням невизначеності")
