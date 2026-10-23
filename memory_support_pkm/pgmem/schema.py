"""Dataset metadata (Frictionless Data Package) and validation.

The same descriptor documents the synthetic data and lets a team check
that a real, ethically approved dataset with the same structure can be
analysed by this code without changes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

F = lambda name, type_, desc, **c: {"name": name, "type": type_, "description": desc,
                                     **({"constraints": c} if c else {})}

RESOURCES = {
    "participants": ("Учасники когорти та метадані, пов'язані з пам'яттю (одна стрічка = одна людина)", [
        F("participant_id", "string", "Псевдонімізований ідентифікатор", required=True, unique=True, pattern=r"P\d{3}"),
        F("age", "integer", "Вік, роки", minimum=18, maximum=110),
        F("age_band", "string", "Вікова група", enum=["<50", "50-64", "65-74", "75-84", "85+"]),
        F("sex", "string", "Стать", enum=["F", "M"]),
        F("diagnosis", "string", "MCI — помірний когнітивний розлад; mild_dementia — легка деменція; ABI — набуте ураження мозку",
          enum=["MCI", "mild_dementia", "ABI"]),
        F("cdr_global", "number", "Clinical Dementia Rating, глобальна оцінка (порожньо для ABI)", minimum=0, maximum=3),
        F("moca", "integer", "Montreal Cognitive Assessment з поправкою на освіту (0–30)", minimum=0, maximum=30),
        F("education_years", "integer", "Роки освіти", minimum=0, maximum=30),
        F("prmq_prospective", "integer", "PRMQ, проспективна шкала (8–40, більше = частіші збої)", minimum=8, maximum=40),
        F("prmq_retrospective", "integer", "PRMQ, ретроспективна шкала (8–40)", minimum=8, maximum=40),
        F("months_since_diagnosis", "integer", "Місяців від встановлення діагнозу", minimum=0),
        F("lives_alone", "boolean", "Живе сам(а)"),
        F("has_trusted_person", "boolean", "Є погоджена довірена особа (R8)"),
        F("trusted_relation", "string", "Хто довірена особа"),
        F("device", "string", "Пристрій", enum=["smartphone", "tablet", "both"]),
        F("digital_literacy", "integer", "Самооцінка цифрової грамотності (1–5)", minimum=1, maximum=5),
        F("uses_voice", "boolean", "Користується голосовою взаємодією (R6)"),
        F("sensors_connected", "boolean", "Підключені сенсори (таблетниця, крокомір)"),
        F("call_log_connected", "boolean", "Підключено журнал дзвінків"),
        F("language", "string", "Мова інтерфейсу", enum=["uk", "en"]),
        F("agrees_to_level_reduction", "boolean", "Згода на зниження стартового рівня підтримки (рівн. 3)"),
        F("ability_latent", "number", "ЛИШЕ ДЛЯ СИМУЛЯЦІЇ: латентна здатність, з якої генеруються відповіді"),
    ]),
    "episodes": ("Заплановані епізоди завдань (рутини, R1–R4)", [
        F("episode_id", "string", "Ідентифікатор епізоду", required=True, unique=True),
        F("participant_id", "string", "Посилання на participants", required=True),
        F("day", "integer", "День спостереження (0–27)", minimum=0),
        F("task_type", "string", "Тип завдання",
          enum=["medication_morning", "daily_walk", "appointment_prep", "bill_payment", "call_family"]),
        F("category", "string", "Категорія даних для згоди"),
        F("safety_critical", "boolean", "Завдання, критичне для безпеки"),
        F("sensorable", "boolean", "Виконання може бути зафіксоване сенсором"),
        F("scheduled", "datetime", "Запланований час (ISO 8601)"),
    ]),
    "records": ("Персональна база подій: записи r_i = (c, t, s, κ, σ, v, e), рівняння (1)", [
        F("record_id", "string", "Ідентифікатор запису", required=True, unique=True),
        F("person_id", "string", "Чий це запис", required=True),
        F("subject", "string", "Ідентичність події"),
        F("content", "string", "c_i — зміст"),
        F("time", "datetime", "t_i — час"),
        F("source", "string", "s_i — джерело/походження (calendar, user_voice, sensor, call_log, carer_entry)"),
        F("kappa", "number", "κ_i — індикатор довіри (не ймовірність)", minimum=0, maximum=1),
        F("scope", "string", "σ_i — кому дозволено (через кому)"),
        F("version", "integer", "v_i — версія", minimum=1),
        F("status", "string", "e_i — доказовий статус",
          enum=["plan", "self_report", "observation", "inference", "disputed"]),
        F("category", "string", "Категорія даних"),
        F("kind", "string", "Про що запис: scheduled / occurred / content", enum=["scheduled", "occurred", "content"]),
        F("value", "string", "Нормалізоване значення твердження"),
        F("supersedes", "string", "Попередня версія, яку замінює цей запис"),
        F("active", "boolean", "Поточна версія"),
        F("disputed", "boolean", "Позначено як спірний"),
    ]),
    "questions": ("Запитання до асистента про минуле зі стратами оцінювання", [
        F("question_id", "string", "Ідентифікатор", required=True, unique=True),
        F("person_id", "string", "Про кого запитання"),
        F("stratum", "string", "Страта", enum=["answerable_plan", "attendance", "self_report", "unanswerable",
                                                 "answerable_observation", "contradictory", "stale",
                                                 "answerable_note", "consent_restricted"]),
        F("requester", "string", "Хто питає (сама людина або trusted:<id>)"),
        F("subject", "string", "Подія"),
        F("kind", "string", "Тип твердження"),
        F("category", "string", "Категорія даних"),
        F("ideal", "string", "Еталонна поведінка", enum=["answer", "abstain", "clarify", "refuse"]),
        F("text", "string", "Текст запитання"),
    ]),
    "reference_history": ("Незалежна еталонна історія (ground truth) для сліпої оцінки тверджень", [
        F("person_id", "string", "Людина"),
        F("subject", "string", "Подія"),
        F("kind", "string", "scheduled / occurred / reported / content"),
        F("value", "string", "Істинне значення"),
    ]),
}


def descriptor(seed: int, n: int, days: int) -> dict:
    return {
        "name": "pgmem-synthetic-memory-support",
        "title": "Синтетичний датасет для оцінювання provenance-governed асистента пам'яті",
        "version": "1.0.0",
        "licenses": [{"name": "CC-BY-4.0"}],
        "description": (
            "Повністю синтетичні дані, згенеровані за рамкою Prokopovych-Tkachenko «Provenance-governed agentic AI "
            "for personal knowledge and memory support» (етап 1 протоколу оцінювання). Жоден запис не "
            "відповідає реальній людині; розподіли — проєктні припущення, а не емпіричні оцінки."),
        "synthetic": True,
        "generator": {"package": "pgmem", "seed": seed, "participants": n, "days": days},
        "resources": [
            {"name": k, "path": f"{k}.csv", "format": "csv", "description": d, "schema": {"fields": f}}
            for k, (d, f) in RESOURCES.items()
        ],
    }


def write_descriptor(path: Path, seed: int, n: int, days: int) -> None:
    path.write_text(json.dumps(descriptor(seed, n, days), ensure_ascii=False, indent=2), encoding="utf-8")


def validate(data_dir: Path) -> list[str]:
    """Check every CSV against datapackage.json; returns a list of problems."""
    desc = json.loads((Path(data_dir) / "datapackage.json").read_text(encoding="utf-8"))
    problems = []
    for res in desc["resources"]:
        df = pd.read_csv(Path(data_dir) / res["path"], keep_default_na=False, na_values=[""])
        for f in res["schema"]["fields"]:
            name, c = f["name"], f.get("constraints", {})
            if name not in df.columns:
                problems.append(f"{res['name']}: немає колонки {name}")
                continue
            col = df[name]
            if c.get("required") and col.isna().any():
                problems.append(f"{res['name']}.{name}: порожні значення")
            if c.get("unique") and col.duplicated().any():
                problems.append(f"{res['name']}.{name}: дублікати")
            if "enum" in c and not col.dropna().astype(str).isin(c["enum"]).all():
                problems.append(f"{res['name']}.{name}: значення поза enum")
            num = pd.to_numeric(col, errors="coerce")
            if "minimum" in c and (num < c["minimum"]).any():
                problems.append(f"{res['name']}.{name}: < {c['minimum']}")
            if "maximum" in c and (num > c["maximum"]).any():
                problems.append(f"{res['name']}.{name}: > {c['maximum']}")
            if "pattern" in c and not col.astype(str).str.fullmatch(c["pattern"]).all():
                problems.append(f"{res['name']}.{name}: не відповідає шаблону")
    return problems
