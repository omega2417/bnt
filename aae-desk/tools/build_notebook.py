"""Збирає notebooks/AAE_Desk_Colab.ipynb із вбудованим пакетом aae (самодостатній блокнот)."""
import base64, hashlib, io, json, os, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
    for base, _, files in sorted(os.walk(os.path.join(ROOT, "aae"))):
        if "__pycache__" in base:
            continue
        for name in sorted(files):
            path = os.path.join(base, name)
            info = zipfile.ZipInfo(os.path.relpath(path, ROOT), date_time=(2026, 11, 18, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            z.writestr(info, open(path, "rb").read())
blob = buf.getvalue()
b64 = base64.b64encode(blob).decode()
sha = hashlib.sha256(blob).hexdigest()
lines = "\n".join(b64[i:i + 100] for i in range(0, len(b64), 100))

cells = []
md = lambda s: cells.append({"cell_type": "markdown", "metadata": {}, "source": s.strip("\n").splitlines(True)})
code = lambda s: cells.append({"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
                               "source": s.strip("\n").splitlines(True)})

md("""
# AAE-Desk: підзвітна агентна підготовка доказів

Блокнот для Google Colab. Демонструє програмну реалізацію моделі **Accountable Agentic Evidence (AAE)** з публікації
Torstensson O., Antypenko I., Prokopovych-Tkachenko D. *AI Agents in National Cyber Resilience Governance: Metadata Discovery and Decision Accountability*.

Блокнот самодостатній: код системи вбудовано в першу комірку, доступ до мережі та сторонні бібліотеки не потрібні
(таблиці показуються через `pandas`, який у Colab уже є). Виконуйте комірки згори донизу: **Runtime → Run all**.

**Що важливо знати.** Агенти в прототипі є детермінованими компонентами на правилах, а не мовною моделлю.
Твердження-кандидати беруться зі сценарного файла, а пошук працює з локальним знімком із 22 записів метаданих.
Імена осіб та орган вигадані. Показники ілюстративні й не підтверджують пропозиції P1–P6 публікації.
""")
md("## 1. Встановлення\n\nКомірка розпаковує вбудований пакет `aae` (версія 0.1.0) і перевіряє його контрольну суму.")
code(f'''
import base64, hashlib, io, os, sys, zipfile

AAE_SHA256 = "{sha}"
AAE_ZIP_B64 = """
{lines}
"""
_blob = base64.b64decode("".join(AAE_ZIP_B64.split()))
assert hashlib.sha256(_blob).hexdigest() == AAE_SHA256, "Вбудований пакет пошкоджено"
WORKDIR = os.path.abspath("aae_desk_colab")
zipfile.ZipFile(io.BytesIO(_blob)).extractall(WORKDIR)
if WORKDIR not in sys.path:
    sys.path.insert(0, WORKDIR)
import aae
print("AAE-Desk", aae.__version__, "встановлено в", WORKDIR)
''')
code('''
import json, shutil, tempfile
import pandas as pd
from IPython.display import Markdown, display

from aae import autonomy, frameworks, roles
from aae.demo import (ANALYST_1, ANALYST_2, AUDITOR, COORD, OFFICIAL_1, REFERENCE,
                      scenario_training, scenario_transposition)
from aae.indicators import case_indicators, recall_precision
from aae.record import DecisionRecord, RecordError
from aae.roles import NotPermitted
from aae.workflow import Desk, WorkflowError, actor, verify_bundle

pd.set_option("display.max_colwidth", 120)

def refused(action, *args, **kwargs):
    """Виконати дію, яку система має відхилити, і показати пояснення відмови."""
    try:
        action(*args, **kwargs)
    except (WorkflowError, NotPermitted, RecordError) as exc:
        print("ВІДМОВЛЕНО:", exc)
    else:
        print("УВАГА: дію несподівано дозволено")
''')

md("""
## 2. Документний аналіз: сім рамкових документів

Кодування восьми елементів підзвітності (табл. 4 публікації). `E` — явне положення (1 бал), `P` — часткове (0,5), `–` — не розглянуто.
Індекс покриття є описовим засобом порівняння і статистичного значення не має.
""")
code('''
docs = frameworks.CYBER + frameworks.AI
coding = pd.DataFrame(
    {d: [frameworks.CODING[e][d][0] or "–" for e in frameworks.ELEMENTS] for d in docs},
    index=[f"{e} {t}" for e, t in frameworks.ELEMENTS.items()])
shade = {"E": "background-color:#1a4f91;color:white", "P": "background-color:#bcd6f6;color:#06254d", "–": "color:#888"}
display(coding.style.map(lambda v: shade[v]).set_properties(**{"text-align": "center"}))

coverage = frameworks.coverage_by_document()
display(pd.DataFrame({"Документ": [frameworks.DOCUMENTS[d] for d in docs],
                      "Індекс покриття (макс. 8)": [coverage[d] for d in docs]}, index=docs))
''')
code('''
summary = pd.DataFrame({
    "Елемент": list(frameworks.ELEMENTS.values()),
    "Явно закріплено (із 7)": [frameworks.explicit_count(e) for e in frameworks.ELEMENTS],
    "Сума балів": [frameworks.coverage_by_element()[e] for e in frameworks.ELEMENTS],
    "Як закрито в системі": [frameworks.SYSTEM_RESPONSE[e] for e in frameworks.ELEMENTS],
}, index=list(frameworks.ELEMENTS))
summary
''')
md("Найслабший елемент — **E7 (управління джерелами й даними)**: явно його не закріплює жоден документ. Саме цю прогалину закриває агент походження (F2) разом із контрольною точкою G1.")

md("## 3. Ролі та градуйована автономія\n\nРозподіл відповідальності за рис. 4 публікації. ШІ-агент ніколи не має ролі A (підзвітний).")
code('''
raci = pd.DataFrame([[r.get(role, "") for role in roles.ROLES] for _, _, r in roles.TASKS.values()],
                    index=[f"{n}. {t}" for n, (_, t, _) in roles.TASKS.items()],
                    columns=list(roles.ROLES.values()))
raci_shade = {"A": "background-color:#1a4f91;color:white;font-weight:bold", "R": "background-color:#5a9be6;font-weight:bold",
              "C": "background-color:#bcd6f6", "I": "background-color:#eef3fa", "": ""}
display(raci.style.map(lambda v: raci_shade[v]).set_properties(**{"text-align": "center"}))
assert "A" not in set(raci["ШІ-агент"]), "агент не може бути підзвітним"
''')
code('''
zone_shade = {"Z1": "background-color:#cfe2fb", "Z2": "background-color:#8fbcf2",
              "Z3": "background-color:#2a69c0;color:white", "Z4": "background-color:#123f7e;color:white"}
matrix = pd.DataFrame(
    [[f"Z{autonomy.DEFAULT_MATRIX[u][c]}" for c in autonomy.CONSEQUENCES] for u in reversed(list(autonomy.UNCERTAINTIES))],
    index=[autonomy.UNCERTAINTIES[u] for u in reversed(list(autonomy.UNCERTAINTIES))],
    columns=list(autonomy.CONSEQUENCES.values()))
display(matrix.style.map(lambda v: zone_shade[v]).set_properties(**{"text-align": "center"}))

display(pd.DataFrame([{"Режим": z["name"], "Функції агентів": ", ".join(z["agent_functions"]),
                       "Перевірка G1": "вибірка" if z["g1"] == "sample" else "кожне твердження",
                       "Другий рецензент": "так" if z["second_reviewer"] else "ні"} for z in autonomy.ZONES.values()],
                     index=[f"Z{k}" for k in autonomy.ZONES]))
print("Тригери ескалації (на одну зону вище):")
for t in autonomy.TRIGGERS.values():
    print(" -", t)
''')
md("П'ять ілюстративних завдань із рис. 5 публікації потрапляють у ті самі зони:")
code('''
examples = [("a", "тижневий дайджест повідомлень постачальників", "routine", "low", []),
            ("b", "перелік пріоритетів оновлень для систем органу", "tactical", "moderate", []),
            ("c", "порівняння варіантів транспозиції NIS2", "institutional", "moderate", []),
            ("d", "довідка для перегляду національного плану реагування", "strategic", "high", []),
            ("e", "стратегічне питання з усталеними доказами", "strategic", "low", []),
            ("b*", "те саме, що b, але виявлено нову загрозу", "tactical", "moderate", ["novel_threat"])]
pd.DataFrame([{"Завдання": name, "Наслідки": autonomy.CONSEQUENCES[c], "Невизначеність": u,
               "Зона": f"Z{autonomy.effective_zone(c, u, t)}"} for _, name, c, u, t in examples],
             index=[e[0] for e in examples])
''')

md("""
## 4. Сценарій 1: навчання керівництва з кіберризиків (зона Z2)

Агенти знаходять джерела, перевіряють походження і пропонують твердження. Аналітик звіряє кожне з повним текстом (G1).
Два твердження агента навмисно хибні, щоб показати, навіщо потрібна межа метаданих.
""")
code('''
DATA = tempfile.mkdtemp(prefix="aae-colab-")
desk = Desk(DATA)
case1, bundle_path = scenario_training(desk)
st = case1.state()
print("Питання:", st["need"]["question"])
print("Зона автономії: Z%d · етап: %s · записів у журналі: %d" % (st["zone"], st["stage"], len(case1.record)))
''')
code('''
def sources_table(case):
    rows = []
    for i, s in sorted(case.state()["sources"].items()):
        r, p, a = s["record"], s["prov"]["payload"], s["appraisal"]["payload"] if s["appraisal"] else {}
        ident = f'{r["identifier"]["scheme"]}:{r["identifier"]["value"]}' if r["identifier"] else "немає"
        rows.append({"Запис": s["meta"]["id"], "Джерело": r["title"][:70], "Ідентифікатор": ident,
                     "Придатне": "так" if p["usable"] else "НІ",
                     "Зауваги F2": "; ".join(p["flags"]) or p["status_uk"],
                     "Актуальність": a.get("currency", ""), "Застосовність": a.get("applicability", "")})
    return pd.DataFrame(rows).set_index("Запис")

q = st["queries"][0]["payload"]
print("Запит:", ", ".join(q["terms"]), "· знайдено", len(q["retrieved"]), "· дублікатів усунуто", len(q["duplicates"]))
sources_table(case1)
''')
md("### Контрольна точка G1\n\nМетадані підтверджують, що документ існує і хто його видав. Що саме в ньому сказано, встановлює лише аналітик.")
code('''
def g1_table(case):
    st, rows = case.state(), []
    verdict = {"accept": "прийнято", "modify": "ЗМІНЕНО", "reject": "ВІДХИЛЕНО"}
    for kid, cand in sorted(st["candidates"].items()):
        v = st["verifications"].get(kid)
        rows.append({"Кандидат": kid, "Запропонував": roles.ROLES[cand["actor"]["role"]],
                     "Твердження": cand["payload"]["statement"],
                     "Висновок": verdict[v["payload"]["verdict"]] if v else "очікує",
                     "Місце": v["payload"]["location"] if v else "", "Причина": v["payload"]["reason"] if v else ""})
    return pd.DataFrame(rows).set_index("Кандидат")

g1_table(case1)
''')
md("### Довідка, рішення та ланцюжок походження")
code('display(Markdown(case1.brief_markdown()))')
code('''
d = case1.state()["decision"]
print("Рішення:", d["payload"]["option"], "·", d["actor"]["name"])
print("Обґрунтування:", d["payload"]["rationale"])
print()
for row in case1.reconstruct()["claims"]:
    print(" ← ".join(["D-1"] + row["chain"]), "| повний" if row["ok"] else "| НЕПОВНИЙ")
''')

md("""
## 5. Сценарій 2: імплементація вимог NIS2 (Z3 з ескалацією до Z4)

Джерело без сталого ідентифікатора автоматично піднімає зону. Далі оцінювання й довідку веде аналітик,
другий рецензент фіксує окрему думку. Справа повторно використовує твердження, перевірені в першій справі.
""")
code('''
case2 = scenario_transposition(desk, bundle_path)
for e in case2.state()["zone_events"]:
    p = e["payload"]
    print(f'{e["id"]}: Z{p["previous_zone"] or "—"} → Z{p["zone"]} · {p["cause"]} · вніс: {roles.ROLES[e["actor"]["role"]]}')
sources_table(case2)
''')
code('''
st2 = case2.state()
for r in st2["reviews"]:
    print("Другий рецензент:", r["payload"]["reviewer"], "—", r["payload"]["comment"])
    print("Окрема думка:", r["payload"]["dissent"])
print("\\nРішення:", st2["decision"]["payload"]["rationale"])
print("\\nПовторно використані твердження:")
for c in st2["claims"].values():
    if c["reused"]:
        print(f' {c["id"]}: {c["statement"]}  [перевірив {c["origin"]["verified_by"]}, справа № {c["origin"]["case"]}]')
''')

md("## 6. Журнал рішень: простеження та цілісність\n\nВід рішення можна пройти назад до початкового запиту. Будь-яка пізніша зміна запису виявляється.")
code('''
trace = case2.record.trace_back("D-2")
pd.DataFrame([{"Запис": e["id"], "Тип": e["type"], "Виконавець": f'{roles.ROLES[e["actor"]["role"]]}: {e["actor"]["name"]}',
               "Підзвітний": e["accountable"]["name"], "Попередники": ", ".join(e["refs"]), "Час (UTC)": e["ts"]}
              for e in trace]).set_index("Запис")
''')
code('''
print("Перевірка цілісності справжнього журналу:", case1.record.verify() or "порушень немає")

# Спроба підробки на КОПІЇ журналу: змінюємо причину відхилення твердження про «40 годин».
copy = shutil.copy(case1.record.path, DATA + "/tampered.jsonl")
lines = open(copy, encoding="utf-8").read().splitlines()
for i, line in enumerate(lines):
    entry = json.loads(line)
    if entry["type"] == "passage_verified" and entry["payload"]["verdict"] == "reject":
        entry["payload"]["verdict"] = "accept"
        lines[i] = json.dumps(entry, ensure_ascii=False, sort_keys=True)
open(copy, "w", encoding="utf-8").write("\\n".join(lines) + "\\n")
print("Після підробки копії:")
for problem in DecisionRecord(copy).verify():
    print(" -", problem)
''')
code('''
bundle = json.load(open(bundle_path, encoding="utf-8"))
print("Пакет доказів:", bundle["claims"], "· записів у витягу:", len(bundle["record_excerpt"]))
print("Перевірка пакета отримувачем:", verify_bundle(bundle) or "пройдено")
bundle["record_excerpt"][-1]["payload"]["statement"] = "підмінене твердження"
print("Після підміни:", verify_bundle(bundle))
''')

md("""
## 7. Показники

Показники з плану оцінювання публікації (табл. 6), які система обчислює з журналу. Повноту й точність пораховано
відносно **ілюстративного** еталонного набору, складеного розробником, тому вони не є емпіричним результатом.
""")
code('''
labels = {"zone": "Зона автономії", "sources_retrieved": "Джерел знайдено", "sources_unusable": "із них непридатних",
          "g1_accept": "G1: прийнято", "g1_modify": "G1: змінено", "g1_reject": "G1: відхилено",
          "agent_override_rate": "Частка пропозицій агента, змінених або відхилених",
          "traceability_rate": "Простежуваність тверджень довідки", "escalations": "Ескалацій зони",
          "reused_claims": "Повторно використаних тверджень", "transfers": "Передано пакетів",
          "reconstructable": "Рішення відтворюване", "integrity_ok": "Журнал цілісний", "record_entries": "Записів у журналі"}
table = {}
for case in desk.cases():
    ind = case_indicators(case)
    rp = recall_precision(ind["retrieved_keys"], REFERENCE[case.number])
    column = {labels[k]: ind[k] for k in labels}
    column["Повнота (ілюстративний еталон)"] = rp["recall"]
    column["Точність (ілюстративний еталон)"] = rp["precision"]
    table[f"Справа № {case.number}"] = column
fmt = lambda v: "—" if v is None else ("так" if v is True else "ні" if v is False else f"{v:.0%}" if isinstance(v, float) else v)
pd.DataFrame(table).map(fmt)
''')

md("""
## 8. Власна справа крок за кроком

Тут можна змінити питання, варіанти, наслідки та невизначеність і подивитися, як система поводиться.
Комірки також показують відмови: дії, які модель забороняє.
""")
code('''
analyst = actor("analyst", "Аналітик (Colab)")
official = actor("official", "Посадова особа (Colab)")
reviewer = actor("analyst", "Другий аналітик (Colab)")

my = desk.create_case(
    analyst,
    question="Чи оновлювати внутрішню політику управління кіберризиками органу?",
    decision="Оновлення політики управління ризиками",
    options=["Оновити політику за чинною версією рамки", "Залишити без змін"],
    consequence="tactical",      # routine | tactical | institutional | strategic
    uncertainty="moderate",      # low | moderate | high
    jurisdictions=["UA"],
    official=official["name"])

refused(my.run_discovery, analyst, ["csf"])                 # межі ще не затверджено
refused(my.approve_scope, analyst)                          # аналітик не може затвердити межі
my.approve_scope(official)
print("Зона автономії: Z%d" % my.state()["zone"])
''')
code('''
my.run_discovery(analyst, ["risk management", "управління ризиками", "csf"])
my.run_provenance(analyst)
my.run_appraisal(analyst)
proposed = my.propose_claims(analyst)
print("Агент запропонував тверджень:", len(proposed))
refused(my.draft_brief, analyst)                            # G1 ще не пройдено
sources_table(my)
''')
code('''
idx = {s["record"]["key"]: i for i, s in my.state()["sources"].items()}
own = my.add_claim(analyst, idx["csf2"], "CSF 2.0 містить функцію GOVERN з категорією стратегії управління ризиками (GV.RM).")

refused(my.verify_claim, analyst, own["id"], "accept", reason="", location="GV.RM")        # без причини не можна
refused(my.verify_claim, official, own["id"], "accept", reason="так", location="GV.RM")    # G1 виконує лише аналітик
old = my.add_claim(analyst, idx["csf11"], "Твердження із заміненої версії рамки.")
refused(my.verify_claim, analyst, old["id"], "accept", reason="прочитано", location="розд. 1")  # джерело непридатне
my.verify_claim(analyst, old["id"], "reject", reason="Джерело замінено версією 2.0; твердження не використовую.")

my.verify_claim(analyst, own["id"], "accept", reason="Прочитано опис категорії GV.RM.", location="GV.RM", option="opt1")
for c in proposed:
    my.verify_claim(analyst, c["id"], "accept", reason="Підтверджено текстом.", location=c["payload"]["location_hint"],
                    option="context")
g1_table(my)
''')
code('''
my.draft_brief(analyst)
my.sign_brief(analyst, "Чинна версія рамки містить окрему функцію врядування. Рекомендую оновити політику.", "opt1")
relied = [c for c, v in my.state()["claims"].items() if v["option"] == "opt1"]

refused(my.decide, analyst, "opt1", "бо так", relied)                    # рішення ухвалює лише посадова особа
refused(my.decide, official, "opt1", "", relied)                         # без обґрунтування не можна
refused(my.decide, official, "opt2", "Бракує ресурсів", relied)          # відхід від оцінки аналітика без пояснення
my.decide(official, "opt1", "Політика має відповідати чинній версії рамки.", relied)
refused(my.run_discovery, analyst, ["nis2"])                             # після рішення докази не змінюються

my.audit(actor("oversight", "Внутрішній аудит (Colab)"), "Обґрунтування відтворюється з журналу.")
ind = case_indicators(my)
print("\\nЗаписів у журналі:", ind["record_entries"], "· цілісний:", ind["integrity_ok"], "· рішення відтворюване:", ind["reconstructable"])
display(Markdown(my.brief_markdown()))
''')
md("Агент не може бути підзвітною стороною навіть при прямому записі в журнал, а правила агентів змінюють лише люди:")
code('''
human = {"role": "analyst", "name": "Аналітик (Colab)"}
refused(my.record.append, id="X-1", type="test", actor=human, accountable={"role": "agent", "name": "briefing-agent"})
refused(desk.revise_config, actor("agent", "briefing-agent"), official, {"z1_sample_rate": 0.1}, "агент послаблює контроль")
entry = desk.revise_config(analyst, official, {"z1_sample_rate": 0.4}, "Посилення вибіркового контролю в зоні Z1")
print("Зміну зафіксовано:", entry["id"], entry["payload"]["before"], "→", entry["payload"]["after"])
''')

md("""
## 9. Вебінтерфейс (необов'язково)

Комірка запускає вебінтерфейс системи на даних цього блокнота і в Colab відкриває його в новій вкладці.
Роль обирають угорі сторінки. Цю комірку перевірено лише поза Colab: якщо вкладка не відкриється,
скористайтеся локальним запуском `python -m aae serve --data ./data`.
""")
code('''
import threading
from http.server import HTTPServer
from aae.web import App, make_handler

PORT = 8000
try:
    server
except NameError:
    server = HTTPServer(("127.0.0.1", PORT), make_handler(App(DATA)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
try:
    from google.colab import output
    output.serve_kernel_port_as_window(PORT, anchor_text="Відкрити AAE-Desk у новій вкладці")
except ImportError:
    print(f"Поза Colab: відкрийте http://127.0.0.1:{PORT}")
''')
md("""
## Обмеження

- Агенти є компонентами на правилах, а не мовною моделлю; твердження-кандидати сценарні.
- Метадані локальні (22 записи), живі реєстри не підключено.
- Автентифікації немає: роль та ім'я вказує користувач.
- Геш-ланцюг виявляє зміни, але не заважає повністю переписати файл тому, хто має до нього доступ.
- Показники демонстрації ілюстративні; пропозиції P1–P6 потребують порівняльного дослідження.
""")

nb = {"cells": cells, "nbformat": 4, "nbformat_minor": 5,
      "metadata": {"kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
                   "language_info": {"name": "python"}, "colab": {"provenance": [], "toc_visible": True}}}
for i, c in enumerate(cells):
    c["id"] = f"cell-{i:02d}"
out = os.path.join(ROOT, "notebooks", "AAE_Desk_Colab.ipynb")
json.dump(nb, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(out, os.path.getsize(out), "bytes;", len(cells), "cells")
