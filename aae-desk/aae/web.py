"""Вебінтерфейс на стандартній бібліотеці Python (без зовнішніх залежностей).

Прототип без автентифікації: роль та ім'я обираються у формі вгорі сторінки.
Сервер типово слухає лише 127.0.0.1. Для промислового використання потрібні
автентифікація посадових осіб (наприклад, КЕП), TLS і захист від CSRF.
"""
from __future__ import annotations

import html
import json
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, unquote, urlparse

from . import autonomy, frameworks, roles
from .indicators import case_indicators
from .record import RecordError
from .roles import AGENT, ANALYST, COORDINATOR, OFFICIAL, OVERSIGHT
from .workflow import Desk, WorkflowError, actor

E = lambda v: html.escape(str(v if v is not None else ""), quote=True)

CSS = """
:root{--ink:#16202c;--mut:#5b6877;--line:#d9dfe7;--bg:#f4f6f9;--card:#fff;--acc:#1f5fbf;--ok:#17794a;--bad:#b3261e;--warn:#9a5b00}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;color:var(--ink);background:var(--bg)}
header{background:#12233d;color:#fff;padding:10px 24px;display:flex;gap:20px;align-items:center;flex-wrap:wrap}
header a{color:#cfe0ff;text-decoration:none;margin-right:14px}header a:hover{color:#fff}
header .brand{font-weight:700;font-size:17px;color:#fff;margin-right:8px}
header form{margin-left:auto;display:flex;gap:6px;align-items:center;font-size:13px}
main{max-width:1180px;margin:0 auto;padding:20px 24px 60px}
h1{font-size:22px;margin:6px 0 4px}h2{font-size:17px;margin:0 0 10px}h3{font-size:14px;margin:14px 0 6px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px 18px;margin:14px 0}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{border-bottom:1px solid var(--line);padding:7px 8px;text-align:left;vertical-align:top}
th{font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--mut);font-weight:600}
.mut{color:var(--mut)}.small{font-size:13px}.mono{font-family:ui-monospace,Menlo,Consolas,monospace;font-size:12.5px}
.badge{display:inline-block;padding:1px 8px;border-radius:10px;font-size:12px;font-weight:600;white-space:nowrap}
.z1{background:#cfe2fb;color:#12335f}.z2{background:#8fbcf2;color:#0c2b55}.z3{background:#2a69c0;color:#fff}.z4{background:#123f7e;color:#fff}
.ok{background:#dcf3e6;color:var(--ok)}.bad{background:#fbe0de;color:var(--bad)}.warn{background:#fdeccb;color:var(--warn)}.neutral{background:#e8ecf2;color:#39485a}
.flash{padding:10px 14px;border-radius:6px;margin:12px 0;background:#fbe0de;color:var(--bad);border:1px solid #f1b8b3}
.flash.good{background:#dcf3e6;color:var(--ok);border-color:#a9dcc0}
input,select,textarea,button{font:inherit;padding:6px 8px;border:1px solid #b9c3d0;border-radius:5px;background:#fff;color:var(--ink)}
textarea{width:100%;min-height:54px}input[type=text]{width:100%}
button{background:var(--acc);color:#fff;border-color:var(--acc);cursor:pointer;font-weight:600}button.sec{background:#fff;color:var(--acc)}
form.inline{display:inline}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:10px}
label{display:block;font-size:12.5px;color:var(--mut);margin-bottom:2px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}
.kpi{background:#fff;border:1px solid var(--line);border-radius:8px;padding:10px 12px}.kpi b{display:block;font-size:20px}
.steps{display:flex;gap:4px;flex-wrap:wrap;margin:10px 0}.step{padding:4px 10px;border-radius:4px;font-size:12.5px;background:#e8ecf2;color:#5b6877}
.step.done{background:#dcf3e6;color:var(--ok)}.step.human{border-left:3px solid #e06a2b}
.chain{display:flex;flex-wrap:wrap;gap:4px;align-items:center}.chain span{border:1px solid #9aa7b6;border-radius:12px;padding:1px 9px}
.boundary{color:var(--bad);font-weight:700;border:none!important}
details{margin:6px 0}summary{cursor:pointer;color:var(--acc);font-weight:600}
.raci td{text-align:center}.raci td:first-child,.raci td:nth-child(2){text-align:left}
.A{background:#1a4f91;color:#fff;font-weight:700}.R{background:#5a9be6;color:#06254d;font-weight:700}.C{background:#bcd6f6}.I{background:#eef3fa;color:#5b6877}
pre{white-space:pre-wrap;background:#f7f9fb;border:1px solid var(--line);border-radius:6px;padding:12px;font-size:13.5px}
"""

ROLE_HINT = {ANALYST: "Олена Коваль (демо)", OFFICIAL: "Ірина Савченко (демо)", COORDINATOR: "Андрій Бойко (демо)",
             OVERSIGHT: "Відділ внутрішнього аудиту (демо)"}
VERDICT_UK = {"accept": ("прийнято", "ok"), "modify": ("змінено", "warn"), "reject": ("відхилено", "bad")}
TYPE_UK = {
    "need_defined": "інформаційна потреба", "scope_approved": "межі затверджено", "zone_set": "зона автономії",
    "query_run": "запит (F1)", "metadata_record": "запис метаданих (F1)", "provenance_checked": "походження (F2)",
    "appraisal_rated": "оцінювання (F3)", "claim_proposed": "твердження-кандидат", "passage_verified": "фрагмент тексту (G1)",
    "claim_confirmed": "підтверджене твердження", "claim_imported": "твердження з пакета", "research_requested": "повернення до пошуку",
    "brief_drafted": "проєкт довідки (F4)", "brief_signed": "довідку підписано", "brief_reviewed": "другий рецензент",
    "decision_taken": "рішення (G2)", "transfer_approved": "дозвіл на передачу", "evidence_transferred": "передача доказів",
    "audit_review": "перегляд (G3)", "config_revised": "зміна конфігурації"}


def zone_badge(zone) -> str:
    return f'<span class="badge z{zone}">Z{zone}</span>' if zone else '<span class="badge neutral">—</span>'


def pct(value) -> str:
    return "—" if value is None else f"{value:.0%}"


def select(name: str, options: dict, selected: str = "") -> str:
    opts = "".join(f'<option value="{E(k)}"{" selected" if k == selected else ""}>{E(v)}</option>'
                   for k, v in options.items())
    return f'<select name="{name}">{opts}</select>'


def act_form(case_no: int, do: str, button: str, fields: str = "", secondary: bool = False, inline: bool = False) -> str:
    cls = ' class="sec"' if secondary else ""
    return (f'<form method="post" action="/case/{case_no}/act"{" class=inline" if inline else ""}>'
            f'<input type="hidden" name="do" value="{do}">{fields}<button{cls}>{E(button)}</button></form>')


class App:
    def __init__(self, data_dir: str):
        self.data_dir = data_dir

    @property
    def desk(self) -> Desk:
        return Desk(self.data_dir)

    # ---- сторінки --------------------------------------------------------
    def page(self, title: str, body: str, who: dict, flash: str = "", good: bool = False) -> str:
        role_select = select("role", {r: roles.ROLES[r] for r in roles.HUMAN_ROLES}, who["role"])
        note = f'<div class="flash{" good" if good else ""}">{E(flash)}</div>' if flash else ""
        return f"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{E(title)} · AAE-Desk</title><style>{CSS}</style></head><body>
<header><span class="brand">AAE-Desk</span><nav><a href="/">Справи</a><a href="/new">Нова справа</a>
<a href="/model">Ролі та автономія</a><a href="/frameworks">Рамкові документи</a><a href="/config">Конфігурація</a></nav>
<form method="post" action="/actor">Працюю як {role_select}<input name="name" value="{E(who['name'])}" size="26" aria-label="Ім'я">
<button class="sec">Змінити</button></form></header><main>{note}{body}</main></body></html>"""

    def home(self, who) -> str:
        rows = ""
        for case in self.desk.cases():
            st, ok = case.state(), not case.record.verify()
            rows += (f'<tr><td><a href="/case/{case.number}">№ {case.number}</a></td><td>{E(st["need"]["question"])}</td>'
                     f'<td>{zone_badge(st["zone"])}</td><td>{E(st["stage"])}</td><td>{len(case.record)}</td>'
                     f'<td><span class="badge {"ok" if ok else "bad"}">{"цілісний" if ok else "порушено"}</span></td></tr>')
        if not rows:
            rows = '<tr><td colspan="6" class="mut">Справ ще немає. Створіть нову справу або запустіть демонстрацію: <span class="mono">python -m aae demo --data КАТАЛОГ</span></td></tr>'
        return f"""<h1>Справи підготовки доказів</h1>
<p class="mut">Кожна справа веде власний журнал рішень. Агенти виконують пошук і перевірку метаданих, люди перевіряють тексти, ухвалюють рішення та проводять перегляд.</p>
<div class="card"><table><tr><th>Справа</th><th>Питання</th><th>Зона</th><th>Етап</th><th>Записів</th><th>Журнал</th></tr>{rows}</table></div>"""

    def new_form(self) -> str:
        return f"""<h1>Нова справа: інформаційна потреба</h1>
<p class="mut">Завдання 1. Формулює аналітик, затверджує підзвітна посадова особа. Зону автономії система визначить за наслідками рішення та невизначеністю доказів.</p>
<form method="post" action="/new" class="card">
<label>Питання, на яке мають відповісти докази</label><textarea name="question" required></textarea>
<label>Рішення, яке підтримується</label><input type="text" name="decision" required>
<label>Варіанти рішення (кожен з нового рядка, щонайменше два)</label><textarea name="options" required></textarea>
<div class="grid"><div><label>Наслідки рішення</label>{select("consequence", autonomy.CONSEQUENCES, "tactical")}</div>
<div><label>Невизначеність доказів</label>{select("uncertainty", autonomy.UNCERTAINTIES, "moderate")}</div>
<div><label>Юрисдикції (через кому)</label><input type="text" name="jurisdictions" value="UA"></div>
<div><label>Часовий горизонт</label><input type="text" name="horizon"></div>
<div><label>Підзвітна посадова особа (ім'я)</label><input type="text" name="official" value="{E(ROLE_HINT[OFFICIAL])}" required></div>
<div><label>Консультації з координатором</label><input type="text" name="consulted"></div></div>
<p><button>Створити справу</button></p></form>"""

    def case_page(self, number: int, who) -> str:
        case = self.desk.case(number)
        st, ind = case.state(), case_indicators(case)
        need, zone, role = st["need"], st["zone"], who["role"]
        closed, n = bool(st["decision"]), number
        parts = [f'<h1>Справа № {n} {zone_badge(zone)}</h1><p>{E(need["question"])}</p>']
        steps = [("Потреба", True, 1), ("Межі", st["scope_ok"], 1), ("F1 пошук", st["sources"], 0),
                 ("F2 походження", any(s["prov"] for s in st["sources"].values()), 0),
                 ("F3 оцінювання", any(s["appraisal"] for s in st["sources"].values()), 0),
                 ("G1 повний текст", st["claims"], 1), ("F4 довідка", st["signed"], 0),
                 ("G2 рішення", st["decision"], 1), ("G3 перегляд", st["audits"], 1)]
        parts.append('<div class="steps">' + "".join(
            f'<span class="step{" done" if done else ""}{" human" if human else ""}">{label}</span>'
            for label, done, human in steps) + '</div><p class="small mut">Помаранчева позначка: крок виконує людина.</p>')
        parts.append(f"""<div class="kpis">
<div class="kpi"><b>{pct(ind['traceability_rate'])}</b>простежуваність тверджень</div>
<div class="kpi"><b>{ind['g1_accept']} / {ind['g1_modify']} / {ind['g1_reject']}</b>G1: прийнято / змінено / відхилено</div>
<div class="kpi"><b>{ind['sources_retrieved']} ({ind['sources_unusable']})</b>джерел (непридатних)</div>
<div class="kpi"><b>{ind['escalations']}</b>ескалацій зони</div>
<div class="kpi"><b>{'так' if ind['reconstructable'] else ('ні' if ind['reconstructable'] is False else '—')}</b>рішення відтворюване</div>
<div class="kpi"><b>{'так' if ind['integrity_ok'] else 'НІ'}</b>цілісність журналу ({ind['record_entries']} записів)</div></div>""")

        # --- межі та зона
        z = autonomy.ZONES.get(zone, {})
        options = "".join(f"<li><b>opt{i}</b>: {E(o)}</li>" for i, o in enumerate(need["options"], 1))
        scope = f"""<div class="card"><h2>Інформаційна потреба та межі</h2>
<p><b>Рішення:</b> {E(need['decision'])}</p><ul>{options}</ul>
<p class="small">Наслідки: {E(autonomy.CONSEQUENCES[need['consequence']])} · невизначеність: {E(autonomy.UNCERTAINTIES[need['uncertainty']])} ·
юрисдикції: {E(', '.join(need['jurisdictions']))} · аналітик: {E(need['analyst'])} · підзвітна посадова особа: {E(need['official'])}</p>"""
        if not st["scope_ok"]:
            scope += '<p><span class="badge warn">Очікує затвердження меж посадовою особою</span></p>'
            if role == OFFICIAL:
                scope += act_form(n, "approve_scope", "Затвердити межі", '<input type="text" name="note" placeholder="Примітка">')
        else:
            functions = ", ".join(z["agent_functions"])
            scope += f'<p>{zone_badge(zone)} <b>{E(z["name"])}</b>: {E(z["note"])}. Агентам дозволено: {functions}.</p>'
            if len(st["zone_events"]) > 1:
                scope += "<ul class=small>" + "".join(
                    f'<li><span class="mono">{E(e["id"])}</span> Z{e["payload"]["previous_zone"] or "—"} → Z{e["payload"]["zone"]}: {E(e["payload"]["cause"])}</li>'
                    for e in st["zone_events"][1:]) + "</ul>"
            if role == ANALYST and not closed:
                free = {k: v for k, v in autonomy.TRIGGERS.items() if k not in st["triggers"]}
                if free:
                    scope += act_form(n, "trigger", "Задіяти тригер ескалації", select("trigger", free), secondary=True)
        parts.append(scope + "</div>")

        # --- джерела
        if st["scope_ok"]:
            rows = ""
            for i, s in sorted(st["sources"].items()):
                r, prov, app = s["record"], s["prov"], s["appraisal"]
                ident = f'{r["identifier"]["scheme"]}: {r["identifier"]["value"]}' if r.get("identifier") else "немає"
                if prov:
                    p = prov["payload"]
                    pv = (f'<span class="badge {"ok" if p["usable"] else "bad"}">{"придатне" if p["usable"] else "непридатне"}</span> '
                          f'<span class="small">{E("; ".join(p["flags"]) if p["flags"] else p["status_uk"])}</span>')
                else:
                    pv = '<span class="badge neutral">не перевірено</span>'
                    if role == ANALYST and not closed:
                        pv += "<details><summary>Перевірити вручну</summary>" + act_form(n, "prov_manual", "Зафіксувати", (
                            f'<input type="hidden" name="index" value="{i}"><label><input type="checkbox" name="resolved" value="1"> ідентифікатор розв\'язано</label>'
                            '<label><input type="checkbox" name="issuer" value="1"> видавця підтверджено</label>'
                            + select("status", {"current": "чинна версія", "corrected": "виправлено", "superseded": "замінено", "repealed": "скасовано", "retracted": "відкликано"})
                            + '<input type="text" name="note" placeholder="Як перевірено" required>')) + "</details>"
                if app:
                    a = app["payload"]
                    av = f'<span class="small">{E(a["currency"])}; {E(a["applicability"])}; {E(a["evidence_type"])}<br><span class="mut">{E(a["uncertainty"])}</span></span>'
                elif prov and role == ANALYST and not closed:
                    av = "<details><summary>Оцінити вручну</summary>" + act_form(n, "appr_manual", "Зафіксувати", (
                        f'<input type="hidden" name="index" value="{i}"><input type="text" name="currency" placeholder="Актуальність" required>'
                        '<input type="text" name="applicability" placeholder="Застосовність" required>'
                        '<input type="text" name="evidence_type" placeholder="Тип доказу" required>'
                        '<input type="text" name="uncertainty" placeholder="Невизначеність" required>')) + "</details>"
                else:
                    av = '<span class="mut">—</span>'
                add = ""
                if prov and role == ANALYST and not closed:
                    add = "<details><summary>Додати твердження</summary>" + act_form(n, "add_claim", "Додати", (
                        f'<input type="hidden" name="index" value="{i}"><textarea name="statement" required></textarea>')) + "</details>"
                rows += (f'<tr><td class="mono">{E(s["meta"]["id"])}</td><td>{E(r["title"])}<br><span class="small mut">{E(r["issuer"])}, {r["year"]} · {E(ident)} · індекс {E(r["index"])}</span>{add}</td>'
                         f'<td>{pv}</td><td>{av}</td></tr>')
            block = '<div class="card"><h2>Джерела: метадані, походження, оцінювання (F1–F3)</h2>'
            if rows:
                block += f'<table><tr><th>Запис</th><th>Джерело</th><th>Походження (F2)</th><th>Оцінювання (F3)</th></tr>{rows}</table>'
            else:
                block += '<p class="mut">Джерел ще немає. Запустіть агент пошуку.</p>'
            for q in st["queries"]:
                qp = q["payload"]
                block += (f'<p class="small mut"><span class="mono">{E(q["id"])}</span> терміни: {E(", ".join(qp["terms"]))} · знайдено {len(qp["retrieved"])}, '
                          f'нових {len(qp["new"])}, дублікатів усунуто {len(qp["duplicates"])} · знімок каталогу {E(qp["snapshot"])}</p>')
            if role == ANALYST and not closed:
                block += act_form(n, "discover", "Запустити агент пошуку (F1)", '<input type="text" name="terms" placeholder="Пошукові терміни через кому" required>')
                block += "<p>" + act_form(n, "provenance", "Агент походження (F2)", secondary=True, inline=True) + " " \
                    + act_form(n, "appraise", "Агент оцінювання (F3)", secondary=True, inline=True) + " " \
                    + act_form(n, "propose", "Агент пропонує твердження (F4)", secondary=True, inline=True) + "</p>"
                block += '<p class="small mut">Якщо зона не дозволяє агентові функцію, система відмовить і цю роботу виконує аналітик власноруч.</p>'
            parts.append(block + "</div>")

        # --- G1
        if st["candidates"] or st["claims"]:
            g1 = case.g1_status(st)
            block = (f'<div class="card"><h2>Контрольна точка G1: перевірка тверджень за повним текстом</h2>'
                     f'<p>Перевірено {g1["checked"]} з {g1["total"]}; обов\'язково {g1["required"]} '
                     f'<span class="badge {"ok" if g1["passed"] else "warn"}">{"G1 пройдено" if g1["passed"] else "G1 не пройдено"}</span></p>'
                     '<p class="small mut">Метадані підтверджують, що документ існує, хто і коли його видав. Що саме в ньому сказано, встановлює лише аналітик, прочитавши фрагмент.</p><table>'
                     '<tr><th>Кандидат</th><th>Твердження</th><th>Висновок аналітика</th></tr>')
            opt_map = {f"opt{i}": f"opt{i}: {o[:40]}" for i, o in enumerate(need["options"], 1)} | {"context": "контекст"}
            for kid, cand in sorted(st["candidates"].items()):
                cp, ver = cand["payload"], st["verifications"].get(kid)
                by = "агент" if cand["actor"]["role"] == AGENT else "аналітик"
                src = st["sources"][cp["index"]]["record"]["title"]
                cell = f'{E(cp["statement"])}<br><span class="small mut">запропонував {by} · {E(src[:80])} · підказка: {E(cp["location_hint"] or "—")}</span>'
                if ver:
                    vp = ver["payload"]
                    label, cls = VERDICT_UK[vp["verdict"]]
                    final = st["claims"].get("C-" + kid[2:])
                    res = f'<span class="badge {cls}">{label}</span> <span class="small">{E(vp["location"])}<br>{E(vp["reason"])}'
                    if final and final["modified"]:
                        res += f'<br><b>Уточнено:</b> {E(final["statement"])}'
                    res += f'<br><span class="mut">{E(vp["reader"])}, {E(ver["ts"])}</span></span>'
                elif role == ANALYST and not closed:
                    res = act_form(n, "verify", "Зафіксувати", (
                        f'<input type="hidden" name="candidate" value="{E(kid)}">'
                        + select("verdict", {"accept": "прийняти", "modify": "змінити", "reject": "відхилити як непідтверджене"})
                        + '<input type="text" name="location" placeholder="Місце фрагмента: стаття, пункт, сторінка">'
                        '<input type="text" name="reason" placeholder="Причина висновку (обов\'язково)" required>'
                        '<input type="text" name="statement" placeholder="Уточнений текст (для зміни)">'
                        + select("option", opt_map, "context") + select("stance", {"supports": "на підтримку", "dissents": "проти"})
                        + '<input type="text" name="uncertainty" placeholder="Примітка про невизначеність">'))
                else:
                    res = '<span class="badge neutral">очікує перевірки</span>'
                block += f'<tr><td class="mono">{E(kid)}</td><td>{cell}</td><td>{res}</td></tr>'
            for cid, c in sorted(st["claims"].items()):
                if c["reused"]:
                    o = c["origin"]
                    block += (f'<tr><td class="mono">{E(cid)}</td><td>{E(c["statement"])}<br><span class="small mut">{E(o["source"][:80])} · {E(c["location"])}</span></td>'
                              f'<td><span class="badge ok">повторно використано</span> <span class="small">перевірив {E(o["verified_by"])}, {E(o["agency"])}, справа № {o["case"]}</span></td></tr>')
            parts.append(block + "</table></div>")

        # --- довідка
        if st["claims"]:
            block = '<div class="card"><h2>Аналітична довідка (F4)</h2>'
            if st["drafts"] or st["signed"]:
                block += f"<pre>{E(case.brief_markdown())}</pre>"
                for r in st["reviews"]:
                    rp = r["payload"]
                    block += (f'<p><span class="badge neutral">другий рецензент</span> {E(rp["reviewer"])}: {E(rp["comment"])}'
                              + (f'<br><b>Окрема думка:</b> {E(rp["dissent"])}' if rp["dissent"] else " Окремої думки немає.") + "</p>")
            if role == ANALYST and not closed:
                block += act_form(n, "draft", "Скласти проєкт довідки", secondary=True)
                if st["drafts"]:
                    opts = {"": "не визначено"} | {f"opt{i}": f"opt{i}" for i in range(1, len(need["options"]) + 1)}
                    block += "<h3>Підпис аналітика</h3>" + act_form(n, "sign", "Підписати довідку", (
                        '<textarea name="assessment" placeholder="Оцінка аналітика" required></textarea><label>Рекомендований варіант</label>' + select("recommended", opts)))
                if st["signed"]:
                    block += "<h3>Другий рецензент (обов'язковий у зоні Z4)</h3>" + act_form(n, "review", "Зафіксувати рецензію", (
                        '<input type="text" name="comment" placeholder="Висновок рецензента" required>'
                        '<input type="text" name="dissent" placeholder="Окрема думка (якщо є)">'), secondary=True)
            parts.append(block + "</div>")

        # --- рішення
        if st["signed"]:
            block = '<div class="card"><h2>Контрольна точка G2: рішення посадової особи</h2>'
            if st["decision"]:
                d = st["decision"]["payload"]
                block += (f'<p><b>Обрано:</b> {E(d["option"])} · <b>ухвалив(-ла):</b> {E(st["decision"]["actor"]["name"])}, {E(st["decision"]["ts"])}</p>'
                          f'<p><b>Обґрунтування:</b> {E(d["rationale"])}</p><p class="small">Спирається на: <span class="mono">{E(", ".join(d["relied"]))}</span></p>')
                if d["departs"]:
                    block += f'<p><span class="badge warn">відхід від оцінки аналітика</span> {E(d["departure"])}</p>'
                rec = case.reconstruct()
                block += "<h3>Ланцюжок походження рішення</h3>"
                for row in rec["claims"]:
                    chain = ["D-%d" % n] + row["chain"]
                    spans = ""
                    for item in chain:
                        if item.startswith("S-"):
                            spans += '<span class="boundary">┆ межа метаданих ┆</span>'
                        spans += f"<span>{E(item)}</span>←"
                    block += f'<div class="chain mono">{spans.rstrip("←")} <span class="badge {"ok" if row["ok"] else "bad"}">{"повний" if row["ok"] else "неповний"}</span></div>'
            elif role == OFFICIAL:
                content = st["signed"]["payload"]["content"]
                ids = list(content["context"])
                for o in content["options"]:
                    ids += o["supporting"] + o["dissenting"]
                checks = "".join(f'<label><input type="checkbox" name="relied" value="{E(c)}"> <span class="mono">{E(c)}</span> {E(st["claims"][c]["statement"][:110])}</label>' for c in ids)
                opts = {f"opt{i}": f"opt{i}: {o[:60]}" for i, o in enumerate(need["options"], 1)} | {"none": "жоден із варіантів"}
                block += act_form(n, "decide", "Ухвалити рішення", (
                    "<label>Варіант</label>" + select("option", opts) + '<label>Обґрунтування</label><textarea name="rationale" required></textarea>'
                    "<label>Твердження, на які спирається рішення</label>" + checks
                    + '<label>Пояснення відходу від оцінки аналітика (якщо є)</label><input type="text" name="departure">'))
            else:
                block += '<p class="mut">Рішення ухвалює названа підзвітна посадова особа.</p>'
            parts.append(block + "</div>")

        # --- передача та перегляд
        if st["signed"]:
            block = '<div class="card"><h2>Міжвідомча передача та перегляд постфактум (G3)</h2>'
            for t in st["transfers"]:
                tp = t["payload"]
                block += f'<p><span class="badge ok">передано</span> {E(tp["partner"])}: {E(", ".join(tp["claims"]))} · файл <span class="mono">{E(tp["file"])}</span> · геш <span class="mono">{E(tp["bundle_hash"][:16])}…</span></p>'
            done = {r for t in st["transfers"] for r in t["refs"]}
            for a in st["transfer_approvals"]:
                if a["id"] not in done:
                    block += f'<p><span class="badge warn">дозвіл {E(a["id"])}</span> {E(a["payload"]["partner"])}: {E(", ".join(a["payload"]["claims"]))} '
                    if role == COORDINATOR:
                        block += act_form(n, "transfer", "Передати пакет", f'<input type="hidden" name="approval" value="{E(a["id"])}">', inline=True)
                    block += "</p>"
            if role == OFFICIAL:
                own = [c for c, v in st["claims"].items() if not v["reused"]]
                checks = "".join(f'<label><input type="checkbox" name="claims" value="{E(c)}"> <span class="mono">{E(c)}</span></label>' for c in own)
                block += "<details><summary>Дозволити передачу доказів партнерському органу</summary>" + act_form(
                    n, "approve_transfer", "Дозволити", '<input type="text" name="partner" placeholder="Орган-отримувач" required>' + checks) + "</details>"
            for a in st["audits"]:
                ap = a["payload"]
                block += (f'<p><span class="badge neutral">G3 {E(a["id"])}</span> {E(a["actor"]["name"])}: {E(ap["finding"])} '
                          f'<span class="small mut">цілісність: {"так" if ap["integrity_ok"] else "ні"}; відтворюваність: {"так" if ap["reconstructable"] else "ні"}'
                          + (f'; приписи: {E(ap["corrections"])}' if ap["corrections"] else "") + "</span></p>")
            if role == OVERSIGHT and st["decision"]:
                block += act_form(n, "audit", "Зафіксувати перегляд", (
                    '<textarea name="finding" placeholder="Висновок перегляду" required></textarea>'
                    '<input type="text" name="corrections" placeholder="Приписи щодо виправлень">'))
            parts.append(block + "</div>")

        # --- журнал
        rows = ""
        for e in case.record.entries:
            rows += (f'<tr><td>{e["seq"]}</td><td class="mono">{E(e["id"])}</td><td>{E(TYPE_UK.get(e["type"], e["type"]))}</td>'
                     f'<td class="small">{E(roles.ROLES[e["actor"]["role"]])}: {E(e["actor"]["name"])}</td><td class="small">{E(e["accountable"]["name"])}</td>'
                     f'<td class="mono">{E(", ".join(e["refs"]))}</td><td class="small mut">{E(e["ts"])}</td><td class="mono">{E(e["hash"][:10])}</td></tr>')
        parts.append(f"""<div class="card"><h2>Журнал рішень</h2>
<p class="small mut">Лише дописування. Кожен запис містить геш попереднього. <a href="/case/{n}/record.json">Завантажити журнал (JSON)</a></p>
<details><summary>Показати всі {len(case.record)} записів</summary><table><tr><th>№</th><th>Запис</th><th>Тип</th><th>Виконавець</th><th>Підзвітний</th><th>Попередники</th><th>Час (UTC)</th><th>Геш</th></tr>{rows}</table></details></div>""")
        return "".join(parts)

    def model_page(self) -> str:
        head = "".join(f"<th>{E(v)}</th>" for v in roles.ROLES.values())
        rows = ""
        for num, (stage, title, raci) in roles.TASKS.items():
            cells = "".join(f'<td class="{raci.get(r, "")}">{raci.get(r, "")}</td>' for r in roles.ROLES)
            rows += f'<tr><td class="small mut">{E(stage)}</td><td>{num}. {E(title)}</td>{cells}</tr>'
        matrix, cons = self.desk.config["autonomy_matrix"], list(autonomy.CONSEQUENCES)
        mrows = ""
        for u in reversed(list(autonomy.UNCERTAINTIES)):
            mrows += f"<tr><td>{E(autonomy.UNCERTAINTIES[u])}</td>" + "".join(f"<td>{zone_badge(matrix[u][c])}</td>" for c in cons) + "</tr>"
        zones = "".join(f'<tr><td>{zone_badge(k)}</td><td><b>{E(v["name"])}</b><br><span class="small mut">{E(v["note"])}</span></td><td>{", ".join(v["agent_functions"])}</td>'
                        f'<td>{"вибірка" if v["g1"] == "sample" else "кожне твердження"}</td><td>{"так" if v["second_reviewer"] else "ні"}</td></tr>' for k, v in autonomy.ZONES.items())
        trig = "".join(f"<li>{E(v)}</li>" for v in autonomy.TRIGGERS.values())
        return f"""<h1>Ролі та градуйована автономія</h1>
<div class="card"><h2>Розподіл відповідальності (RACI)</h2><p class="small mut">A — підзвітний, R — виконавець, C — консультується, I — інформується. ШІ-агент ніколи не має ролі A.</p>
<table class="raci"><tr><th>Етап</th><th>Завдання</th>{head}</tr>{rows}</table></div>
<div class="card"><h2>Матриця зон автономії</h2><table><tr><th>Невизначеність \\ наслідки</th>{"".join(f"<th>{E(autonomy.CONSEQUENCES[c])}</th>" for c in cons)}</tr>{mrows}</table>
<h3>Зони</h3><table><tr><th>Зона</th><th>Режим</th><th>Функції агентів</th><th>G1</th><th>Другий рецензент</th></tr>{zones}</table>
<h3>Тригери ескалації (переводять справу на одну зону вище)</h3><ul>{trig}</ul></div>"""

    def frameworks_page(self) -> str:
        docs = frameworks.CYBER + frameworks.AI
        cov, sym = frameworks.coverage_by_document(), {"E": ("●", "ok"), "P": ("◐", "warn"), "": ("○", "neutral")}
        head = "".join(f'<th title="{E(frameworks.DOCUMENTS[d])}">{d}</th>' for d in docs)
        rows = ""
        for e, title in frameworks.ELEMENTS.items():
            cells = ""
            for d in docs:
                code, anchor = frameworks.CODING[e][d]
                cells += f'<td><span class="badge {sym[code][1]}" title="{E(anchor)}">{sym[code][0]}</span><br><span class="small mut">{E(anchor)}</span></td>'
            rows += f'<tr><td><b>{e}</b> {E(title)}<br><span class="small mut">У системі: {E(frameworks.SYSTEM_RESPONSE[e])}</span></td>{cells}</tr>'
        foot = "".join(f"<td><b>{cov[d]:g}</b></td>" for d in docs)
        legend = "".join(f"<li><b>{d}</b>: {E(t)}</li>" for d, t in frameworks.DOCUMENTS.items())
        return f"""<h1>Нормативне закріплення елементів підзвітності</h1>
<p class="mut">Результати кодування семи рамкових документів із публікації (табл. 4) і те, як кожен елемент закрито в системі. ● явне положення (1), ◐ часткове (0,5), ○ не розглянуто.</p>
<div class="card"><table><tr><th>Елемент</th>{head}</tr>{rows}<tr><td><b>Індекс покриття</b> (макс. 8)</td>{foot}</tr></table><ul class="small">{legend}</ul></div>"""

    def config_page(self) -> str:
        desk = self.desk
        rows = "".join(f'<tr><td class="mono">{E(e["id"])}</td><td>{E(e["payload"]["reason"])}</td><td>{E(e["actor"]["name"])}</td><td>{E(e["accountable"]["name"])}</td><td class="small mut">{E(e["ts"])}</td></tr>'
                       for e in desk.system.entries) or '<tr><td colspan="5" class="mut">Змін не було.</td></tr>'
        agents = "".join(f"<li><b>{k}</b>: {E(v)}</li>" for k, v in desk.config["agents"].items())
        return f"""<h1>Конфігурація правил агентів</h1>
<div class="card"><p>Версія конфігурації: <b>{desk.config['version']}</b> · орган: {E(desk.config['agency'])} · частка вибіркової перевірки в Z1: {desk.config['z1_sample_rate']:.0%}</p>
<ul>{agents}</ul><p class="small mut">Завдання 10: зміну пропонує аналітик, затверджує підзвітна посадова особа. Агенти не мають ролі у зміні власних правил.</p></div>
<div class="card"><h2>Змінити частку вибіркової перевірки (Z1)</h2><form method="post" action="/config">
<div class="grid"><div><label>Нова частка, %</label><input type="text" name="rate" value="{desk.config['z1_sample_rate'] * 100:.0f}"></div>
<div><label>Пропонує (аналітик)</label><input type="text" name="analyst" value="{E(ROLE_HINT[ANALYST])}"></div>
<div><label>Затверджує (посадова особа)</label><input type="text" name="official" value="{E(ROLE_HINT[OFFICIAL])}"></div>
<div><label>Причина</label><input type="text" name="reason" required></div></div><p><button>Внести зміну</button></p></form></div>
<div class="card"><h2>Системний журнал змін</h2><table><tr><th>Запис</th><th>Причина</th><th>Запропонував</th><th>Затвердив</th><th>Час</th></tr>{rows}</table></div>"""

    # ---- дії ---------------------------------------------------------------
    def act(self, number: int, who: dict, f) -> str:
        case, do = self.desk.case(number), f("do")
        terms = lambda key: [t.strip() for t in f(key).split(",") if t.strip()]
        if do == "approve_scope":
            case.approve_scope(who, f("note"))
        elif do == "trigger":
            case.raise_trigger(who, f("trigger"))
        elif do == "discover":
            case.run_discovery(who, terms("terms"))
        elif do == "provenance":
            case.run_provenance(who)
        elif do == "appraise":
            case.run_appraisal(who)
        elif do == "propose":
            if not case.propose_claims(who):
                return "Агент не запропонував нових тверджень для цих джерел; аналітик може додати їх власноруч."
        elif do == "prov_manual":
            case.record_provenance(who, int(f("index")), resolved=bool(f("resolved")), issuer_verified=bool(f("issuer")),
                                   status=f("status"), note=f("note"))
        elif do == "appr_manual":
            case.record_appraisal(who, int(f("index")), currency=f("currency"), applicability=f("applicability"),
                                  evidence_type=f("evidence_type"), uncertainty=f("uncertainty"))
        elif do == "add_claim":
            case.add_claim(who, int(f("index")), f("statement"))
        elif do == "verify":
            case.verify_claim(who, f("candidate"), f("verdict"), reason=f("reason"), location=f("location"),
                              statement=f("statement"), option=f("option"), stance=f("stance"), uncertainty=f("uncertainty"))
        elif do == "draft":
            case.draft_brief(who)
        elif do == "sign":
            case.sign_brief(who, f("assessment"), f("recommended"))
        elif do == "review":
            case.review_brief(who, f("comment"), f("dissent"))
        elif do == "decide":
            case.decide(who, f("option"), f("rationale"), f("relied", True), f("departure"))
        elif do == "approve_transfer":
            case.approve_transfer(who, f("partner"), f("claims", True))
        elif do == "transfer":
            case.transfer(who, f("approval"))
        elif do == "audit":
            case.audit(who, f("finding"), f("corrections"))
        else:
            raise WorkflowError("Невідома дія")
        return ""


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = "AAEDesk/0.1"

        def log_message(self, *args):
            pass

        def who(self) -> dict:
            cookie = SimpleCookie(self.headers.get("Cookie", ""))
            role = cookie["role"].value if "role" in cookie else ANALYST
            name = unquote(cookie["name"].value) if "name" in cookie else ""
            if role not in roles.HUMAN_ROLES:
                role = ANALYST
            return {"role": role, "name": name or ROLE_HINT[role]}

        def send(self, body, status=200, ctype="text/html; charset=utf-8", headers=()):
            data = body.encode("utf-8") if isinstance(body, str) else body
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            for k, v in headers:
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def redirect(self, location, flash="", good=False, headers=()):
            if flash:
                location += ("&" if "?" in location else "?") + ("ok=" if good else "err=") + quote(flash)
            self.send("", 303, headers=[("Location", location), *headers])

        def do_GET(self):
            url = urlparse(self.path)
            query = parse_qs(url.query)
            flash = (query.get("err") or query.get("ok") or [""])[0]
            good, who, path = "ok" in query, self.who(), url.path.rstrip("/") or "/"
            try:
                parts = path.strip("/").split("/")
                if path == "/":
                    title, body = "Справи", app.home(who)
                elif path == "/new":
                    title, body = "Нова справа", app.new_form()
                elif path == "/model":
                    title, body = "Ролі та автономія", app.model_page()
                elif path == "/frameworks":
                    title, body = "Рамкові документи", app.frameworks_page()
                elif path == "/config":
                    title, body = "Конфігурація", app.config_page()
                elif parts[0] == "case" and len(parts) == 2:
                    title, body = f"Справа № {parts[1]}", app.case_page(int(parts[1]), who)
                elif parts[0] == "case" and len(parts) == 3 and parts[2] == "record.json":
                    case = app.desk.case(int(parts[1]))
                    return self.send(json.dumps(case.record.entries, ensure_ascii=False, indent=1),
                                     ctype="application/json; charset=utf-8")
                else:
                    return self.send(app.page("Не знайдено", "<h1>Сторінку не знайдено</h1>", who), 404)
            except (WorkflowError, ValueError) as exc:
                return self.send(app.page("Помилка", "", who, str(exc)), 404)
            self.send(app.page(title, body, who, flash, good))

        def do_POST(self):
            length = int(self.headers.get("Content-Length") or 0)
            form = parse_qs(self.rfile.read(length).decode("utf-8"), keep_blank_values=True)
            f = lambda key, many=False: form.get(key, []) if many else (form.get(key) or [""])[0].strip()
            who, path = self.who(), urlparse(self.path).path
            back = self.headers.get("Referer") or "/"
            back = urlparse(back).path or "/"
            try:
                if path == "/actor":
                    role = f("role") if f("role") in roles.HUMAN_ROLES else ANALYST
                    name = f("name") if role == who["role"] and f("name") else ROLE_HINT[role]
                    cookies = [("Set-Cookie", f"role={role}; Path=/; SameSite=Strict"),
                               ("Set-Cookie", f"name={quote(name)}; Path=/; SameSite=Strict")]
                    return self.redirect(back, headers=cookies)
                if path == "/new":
                    case = app.desk.create_case(
                        who, question=f("question"), decision=f("decision"), options=f("options").splitlines(),
                        consequence=f("consequence"), uncertainty=f("uncertainty"),
                        jurisdictions=[j.strip() for j in f("jurisdictions").split(",") if j.strip()],
                        official=f("official"), horizon=f("horizon"), consulted=f("consulted"))
                    return self.redirect(f"/case/{case.number}", "Справу створено. Тепер межі має затвердити посадова особа.", True)
                if path == "/config":
                    app.desk.revise_config(actor(ANALYST, f("analyst")), actor(OFFICIAL, f("official")),
                                           {"z1_sample_rate": float(f("rate").replace(",", ".")) / 100}, f("reason"))
                    return self.redirect("/config", "Конфігурацію змінено й зафіксовано в системному журналі.", True)
                parts = path.strip("/").split("/")
                if len(parts) == 3 and parts[0] == "case" and parts[2] == "act":
                    message = app.act(int(parts[1]), who, f)
                    return self.redirect(f"/case/{parts[1]}", message or "Дію виконано й записано в журнал.", not message)
                self.send("Not found", 404)
            except (WorkflowError, roles.NotPermitted, RecordError, ValueError) as exc:
                self.redirect(back, str(exc))

    return Handler


def serve(data_dir: str, host: str = "127.0.0.1", port: int = 8000) -> None:
    # Однопотоковий сервер: записи до журналу дописуються строго послідовно.
    server = HTTPServer((host, port), make_handler(App(data_dir)))
    print(f"AAE-Desk: http://{host}:{port}  (дані: {data_dir}; зупинка: Ctrl+C)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
