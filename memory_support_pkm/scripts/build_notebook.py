"""Build notebooks/PGMem_Colab.ipynb: a self-contained Colab notebook that
embeds the pgmem package via %%writefile, so it runs without uploads."""
from pathlib import Path

import nbformat as nbf

ROOT = Path(__file__).resolve().parents[1]
MODULES = ["__init__", "model", "governance", "assistance", "recall", "metrics", "synth",
           "simulate", "stats", "schema", "plots", "pipeline"]

md = nbf.v4.new_markdown_cell
code = nbf.v4.new_code_cell

cells = [
    md("""# Provenance-governed асистент пам'яті — датасет, симуляція та статистика

Програмна реалізація концептуальної рамки зі статті **D. Prokopovych-Tkachenko, «Provenance-governed agentic AI for personal knowledge and memory support: a conceptual framework»**.

Що робить цей ноутбук:

1. Встановлює пакет `pgmem` (код вбудовано нижче — нічого завантажувати не треба).
2. Генерує **синтетичний** датасет людей з порушеннями пам'яті (MCI, легка деменція, набуте ураження мозку) з повними **метаданими** (Frictionless Data Package: типи, одиниці, обмеження, походження).
3. Рахує описову статистику когорти за метаданими (вік, MoCA, PRMQ, CDR, умови проживання, цифрова грамотність…).
4. Відтворює сценарії статті (Олена, 72 роки) на реальному коді: рівняння (1)–(5), інваріанти I1–I4.
5. Порівнює три умови на однакових історіях — **нагадування**, **один агент + RAG**, **запропонована рамка** — за показниками TSR, FPR, F_ext, C (рівняння 6–7) та додатковими.
6. Перевіряє зв'язок метаданих з результатами (Kruskal–Wallis, Spearman, Mann–Whitney, логістична регресія) з кластерним бутстрепом.

> ⚠️ **Усі дані синтетичні.** Жоден запис не відповідає реальній людині; розподіли — проєктні припущення, а не клінічні оцінки. Результати показують, як поводяться правила рамки, і **не** доводять ефективності для людей (див. розділ 7.3 статті).
"""),
    md("## 0. Середовище"),
    code("""%pip -q install pandas numpy scipy matplotlib tabulate
import os, sys
PROJECT = "pgmem_project"
os.makedirs(f"{PROJECT}/pgmem", exist_ok=True)
os.makedirs(f"{PROJECT}/data", exist_ok=True)
sys.path.insert(0, PROJECT)"""),
    md("""### 0.1 Код пакета `pgmem`

Наступні клітинки записують модулі пакета у `pgmem_project/pgmem/`. Їх можна згорнути.
*Альтернатива:* завантажте `pgmem_project.zip` з комплекту та розпакуйте (клітинка після модулів)."""),
]
for m in MODULES:
    src = (ROOT / "pgmem" / f"{m}.py").read_text(encoding="utf-8")
    cells.append(code(f"%%writefile {{PROJECT}}/pgmem/{m}.py\n{src}".replace("{PROJECT}", "pgmem_project")))

cells += [
    code("""# (Необов'язково) замість вбудованого коду — використати zip-комплект:
USE_ZIP = False
if USE_ZIP:
    from google.colab import files
    up = files.upload()                      # оберіть pgmem_project.zip
    import zipfile
    zipfile.ZipFile(next(iter(up))).extractall(".")
    PROJECT = "memory_support_pkm"; sys.path.insert(0, PROJECT)"""),
    code("""import importlib, pgmem
importlib.reload(pgmem)
import numpy as np, pandas as pd, matplotlib.pyplot as plt, json
from IPython.display import display, Markdown, Image
from pgmem import pipeline, schema, stats, plots, simulate
pd.set_option("display.width", 200, "display.max_columns", 40)
print("pgmem", pgmem.__version__)"""),

    md("""## 1. Синтетичний датасет і метадані

Параметри: кількість учасників, тривалість спостереження (днів) та seed для відтворюваності."""),
    code("""N_PARTICIPANTS, DAYS, SEED = 240, 28, 2026
DATA = f"{PROJECT}/data"
tables = pipeline.generate_dataset(DATA, N_PARTICIPANTS, DAYS, SEED)
for k, df in tables.items():
    print(f"{k:18s} {df.shape}")"""),
    md("""### 1.1 Метадані (datapackage.json)

Кожна таблиця описана схемою: тип поля, опис, діапазон, перелік допустимих значень. Ця ж схема використовується для **валідації** будь-якого датасету — зокрема реального, зібраного після етичного схвалення."""),
    code("""desc = json.load(open(f"{DATA}/datapackage.json", encoding="utf-8"))
print(desc["title"]); print(desc["description"]); print("generator:", desc["generator"])
meta = pd.DataFrame([dict(table=r["name"], field=f["name"], type=f["type"], description=f["description"],
                          constraints=json.dumps(f.get("constraints", {}), ensure_ascii=False))
                     for r in desc["resources"] for f in r["schema"]["fields"]])
display(meta[meta.table == "participants"])
print("Проблем валідації:", schema.validate(DATA) or "немає")"""),
    code("""t = pipeline.load_dataset(DATA)
cohort = t["participants"]
display(cohort.head())
display(t["records"].head())
display(t["questions"].sample(5, random_state=1)[["stratum", "requester", "text", "ideal"]])"""),

    md("## 2. Статистика людей з порушеннями пам'яті (за метаданими)"),
    code("""display(Markdown("### Характеристика когорти за діагнозом"))
display(stats.describe_cohort(cohort))
display(Markdown("### Тяжкість за MoCA × діагноз"))
display(stats.memory_impairment_profile(cohort))"""),
    code("""plots.cohort_overview(cohort); plt.show()
num = ["age", "moca", "prmq_prospective", "prmq_retrospective", "education_years", "digital_literacy", "months_since_diagnosis"]
display(Markdown("### Кореляції Спірмена між метаданими"))
display(cohort[num].corr(method="spearman").round(2))"""),
    code("""display(Markdown("### Частки за віковими групами та умовами проживання"))
display(pd.crosstab(cohort.age_band, cohort.diagnosis, margins=True))
display(cohort.groupby("diagnosis")[["lives_alone", "has_trusted_person", "sensors_connected", "uses_voice"]].mean().round(2))"""),

    md("""## 3. Сценарії статті на робочому коді

Персональна база подій (рівняння 1), політика доступу, grounded recall (рівняння 4–5)."""),
    code("""from datetime import datetime, timedelta
from pgmem import PersonalEventBase, PolicyEngine, GroundedRecall, Record, EvidenceStatus as ES, Question
from pgmem import ActionQueue, QueuedAction, next_level, gate

T = datetime(2026, 10, 2, 10)
base, pol = PersonalEventBase("olena"), PolicyEngine("olena")
gr = GroundedRecall(base, pol)
def add(subject, value, status, kind, cat, kappa=0.9, source="calendar"):
    return base.add(Record(base.new_id(), "olena", subject, value, T, source, kappa, frozenset({"self"}),
                           status=status, category=cat, kind=kind, value=value))
def ask(subject, kind, cat, who="olena"):
    a = gr.answer(Question("q", "olena", who, subject, kind, cat))
    print(f"[{a.decision}] {a.text}")
    return a

print("Минулий прийом (є лише план):")
add("appt:Коваленко", "2026-10-02", ES.PLAN, "scheduled", "appointments", 0.95)
ask("appt:Коваленко", "occurred", "appointments")
print("\\nЛіки (самозвіт о 08:47):")
add("med:2026-10-23", "true", ES.SELF_REPORT, "occurred", "medication", 0.85, "user_touch")
ask("med:2026-10-23", "occurred", "medication")
print("\\nДзвінок Андрія (журнал не підключено):")
ask("call:Андрій:2026-10-22", "occurred", "social")
print("\\nСпірний запис (рахунок):")
r1 = add("bill", "true", ES.SELF_REPORT, "occurred", "finance", 0.8, "user_voice")
r2 = add("bill", "false", ES.OBSERVATION, "occurred", "finance", 0.99, "carer_entry")
base.mark_disputed([r1.record_id, r2.record_id], "olena", T)
ask("bill", "occurred", "finance")
print("\\nОсобиста нотатка, питає донька без дозволу:")
add("note:1", "пароль від Wi-Fi на холодильнику", ES.SELF_REPORT, "content", "personal_note", source="user_voice")
ask("note:1", "content", "personal_note", who="iryna");"""),
    code("""print("I1: згоду відкликано після постановки повідомлення в чергу")
pol.grant("iryna", "medication", "message")
q = ActionQueue(pol)
q.enqueue(QueuedAction("msg-1", "message", "iryna", "medication", "Пропущено ранкові ліки", T))
pol.revoke("iryna", "medication", "message")
print("надіслано:", q.dispatch(T + timedelta(minutes=5)), "| скасовано:", [a.key for a in q.cancelled])

print("\\nI4: виправлення запису інвалідує кешовану відповідь")
r = add("appt:стоматолог", "2026-10-10", ES.PLAN, "scheduled", "appointments")
ask("appt:стоматолог", "scheduled", "appointments")
base.correct(r.record_id, "olena", T, value="2026-10-14", content="2026-10-14")
ask("appt:стоматолог", "scheduled", "appointments")

print("\\nРівняння (2): ескалація L1→L2 лише коли G_k=1")
for postponed, progress in [(False, True), (True, True), (False, False)]:
    g = gate(True, postponed, False, progress)
    print(f"  postponed={postponed}, progress_check={progress}: G={g}, L→{next_level(1, g, 4)}")

print("\\nАудит:"); display(pd.DataFrame([vars(e) for e in base.audit]).tail(6))"""),

    md("""## 4. Порівняльна симуляція трьох умов

Однакові синтетичні люди й дні (спільні випадкові числа) для: **нагадування** (фіксоване L1, тиша = пропуск), **один агент + RAG** (ескалація за таймаутом, без перевірки згоди при відправленні, без типів доказів) і **запропонованої рамки**."""),
    code("""%%time
ep, rc = pipeline.run_simulation(t, f"{PROJECT}/results", SEED)
out = pipeline.analyse(t, ep, rc, f"{PROJECT}/results", f"{PROJECT}/reports", n_boot=300)
display(Markdown("### Зведені показники (оцінка та 95% кластерний бутстреп ДІ)"))
display(out["by_condition"].round(3))"""),
    md("""**Як читати:**
* **TSR** = N_c/N_s — частка виконаних завдань; **FPR** = N_f/N_p — частка зайвих підказок (завдання вже виконано, або після відкладення/відмови).
* **independence** — частка виконань на рівнях L0–L1. Для «нагадування» вона 1.0 тривіально, бо інших рівнів немає.
* **invented_outcome_rate** — епізоди, де тишу перетворено на «пропущено» (порушення I3).
* **F_ext** = N_e/N_r — частка оприлюднених тверджень, підтверджених еталонною історією; **coverage** = N_a/N_q. F_ext не визначено (NaN), коли тверджень немає.
* Вищий TSR агента-базового досягається ескалацією попри відкладення та контактами без чинної згоди — за пропозицією P3 статті це **не** успіх."""),
    code("""plots.condition_bars(out["by_condition"], ["TSR", "FPR", "independence", "invented_outcome_rate"]); plt.show()
plots.condition_bars(out["by_condition"], ["F_ext", "coverage", "fabricated_per_100", "appropriate_behaviour"]); plt.show()
plots.level_distribution(ep); plt.show()
display(Markdown("### Безпека та інваріанти")); display(out["safety"])
display(Markdown("### Парні різниці по учасниках")); display(out["paired"].round(4))"""),

    md("## 5. Метадані × результати: хто отримує найменше користі?"),
    code("""display(out["by_condition_diagnosis"][["diagnosis", "condition", "TSR", "FPR", "independence", "F_ext", "coverage"]].round(3))
plots.tsr_by_diagnosis(out["participant_metrics"], cohort); plt.show()
display(Markdown("### Статистичні тести (запропонована рамка)")); display(out["group_tests"].round(4))
display(Markdown("### Логістична регресія виконання епізоду (OR, 95% ДІ)")); display(out["logit"].round(3))"""),
    code("""pm = out["participant_metrics"].merge(cohort, on="participant_id")
p = pm[pm.condition == "proposed"]
p = p.assign(moca_band=pd.cut(p.moca, [0, 17, 21, 25, 30], labels=["≤17", "18–21", "22–25", "26–30"]))
display(p.groupby("moca_band", observed=True)[["TSR", "independence", "FPR", "coverage"]].agg(["mean", "count"]).round(3))"""),

    md("## 6. Пригадування за стратами (контрприклади таблиці 2)"),
    code("""plots.recall_strata(out["strata"]); plt.show()
display(out["strata"].round(3))
display(Markdown("### Приклади відповідей"))
display(rc[rc.stratum.isin(["attendance", "unanswerable", "contradictory", "consent_restricted"])]
        .groupby(["stratum", "condition"]).head(1)[["stratum", "condition", "decision", "answer_text"]])"""),

    md("""## 7. Власні дані

Щоб проаналізувати реальний (етично схвалений, псевдонімізований) датасет: покладіть CSV з тими самими назвами та колонками в окрему теку разом із `datapackage.json`, перевірте `schema.validate(...)` і запустіть `pipeline.load_dataset` → `run_simulation`/`analyse`. Колонка `ability_latent` потрібна лише симуляції."""),
    code("""# MY_DATA = "my_data"          # тека з participants.csv, episodes.csv, ... та datapackage.json
# print(schema.validate(MY_DATA))
# t2 = pipeline.load_dataset(MY_DATA)"""),
    md("## 8. Завантажити результати"),
    code("""import shutil
archive = shutil.make_archive("pgmem_results", "zip", PROJECT)
print(archive)
try:
    from google.colab import files; files.download(archive)
except ImportError:
    pass"""),
]

nb = nbf.v4.new_notebook(cells=cells, metadata={
    "kernelspec": {"name": "python3", "display_name": "Python 3"},
    "language_info": {"name": "python"},
    "colab": {"provenance": [], "toc_visible": True},
})
out = ROOT / "notebooks" / "PGMem_Colab.ipynb"
nbf.write(nb, out)
print(out)
