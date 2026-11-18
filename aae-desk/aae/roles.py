"""Розподіл ролей і відповідальності (RACI) за рис. 4 публікації.

Центральне правило: ШІ-агент може бути виконавцем (R), але ніколи не є
підзвітним (A). Перевірка виконується під час імпорту модуля.
"""
from __future__ import annotations

AGENT, ANALYST, OFFICIAL, COORDINATOR, OVERSIGHT = (
    "agent", "analyst", "official", "coordinator", "oversight")

ROLES = {
    AGENT: "ШІ-агент",
    ANALYST: "Аналітик",
    OFFICIAL: "Підзвітна посадова особа",
    COORDINATOR: "Міжвідомчий координатор",
    OVERSIGHT: "Наглядовий форум",
}
HUMAN_ROLES = [ANALYST, OFFICIAL, COORDINATOR, OVERSIGHT]

# номер завдання -> (етап, назва, {роль: R/A/C/I})
TASKS: dict[int, tuple[str, str, dict[str, str]]] = {
    1: ("Визначення меж", "Визначити інформаційну потребу та межі пошуку",
        {ANALYST: "R", OFFICIAL: "A", COORDINATOR: "C"}),
    2: ("Підготовка доказів", "Виконати запити до джерел метаданих",
        {AGENT: "R", ANALYST: "A"}),
    3: ("Підготовка доказів", "Розв'язати ідентифікатори, перевірити походження",
        {AGENT: "R", ANALYST: "A"}),
    4: ("Підготовка доказів", "Оцінити актуальність і релевантність, зазначити невизначеність",
        {AGENT: "R", ANALYST: "A"}),
    5: ("Підготовка доказів", "Перевірити твердження за повними текстами (G1)",
        {AGENT: "C", ANALYST: "A"}),
    6: ("Підготовка доказів", "Скласти й підписати аналітичну довідку",
        {AGENT: "R", ANALYST: "A", OFFICIAL: "I"}),
    7: ("Рішення", "Ухвалити рішення та зафіксувати обґрунтування (G2)",
        {ANALYST: "C", OFFICIAL: "A", COORDINATOR: "I", OVERSIGHT: "I"}),
    8: ("Координація та перегляд", "Передати докази партнерським органам",
        {ANALYST: "C", OFFICIAL: "A", COORDINATOR: "R"}),
    9: ("Координація та перегляд", "Переглянути журнали рішень постфактум (G3)",
        {ANALYST: "C", OFFICIAL: "I", COORDINATOR: "I", OVERSIGHT: "A"}),
    10: ("Координація та перегляд", "Переглянути правила та конфігурацію агентів",
         {ANALYST: "R", OFFICIAL: "A", OVERSIGHT: "C"}),
}

for _n, (_stage, _title, _raci) in TASKS.items():
    assert _raci.get(AGENT) != "A", f"Завдання {_n}: агент не може бути підзвітним"
    assert list(_raci.values()).count("A") == 1, f"Завдання {_n}: рівно одна підзвітна роль"


class NotPermitted(Exception):
    """Роль не має повноважень на цю дію."""


def raci(task: int, role: str) -> str:
    return TASKS[task][2].get(role, "")


def accountable_role(task: int) -> str:
    return next(r for r, v in TASKS[task][2].items() if v == "A")


def authorize(role: str, task: int, *, need: str = "RA") -> None:
    """Дозволити дію лише ролі з потрібною літерою RACI для завдання.

    ``need="R"`` - виконання, ``need="A"`` - дія підзвітної особи,
    ``need="RA"`` - виконавець або підзвітний (A виконує там, де R не названо).
    """
    letter = raci(task, role)
    if not letter or letter not in need:
        title = TASKS[task][1]
        raise NotPermitted(
            f"Роль «{ROLES.get(role, role)}» не має повноважень на завдання {task} «{title}» "
            f"(потрібно {'/'.join(need)}, має «{letter or '—'}»)")
