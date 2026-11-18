"""Два демонстраційні сценарії. Імена осіб та орган вигадані."""
from __future__ import annotations

import json

from .roles import ANALYST, COORDINATOR, OFFICIAL, OVERSIGHT
from .workflow import Desk, actor

ANALYST_1 = actor(ANALYST, "Олена Коваль (демо)")
ANALYST_2 = actor(ANALYST, "Тарас Мельник (демо)")
OFFICIAL_1 = actor(OFFICIAL, "Ірина Савченко (демо)")
COORD = actor(COORDINATOR, "Андрій Бойко (демо)")
AUDITOR = actor(OVERSIGHT, "Відділ внутрішнього аудиту (демо)")

# Еталонні набори для ілюстрації показників повноти й точності (не емпіричні дані).
REFERENCE = {1: ["nis2", "aiact", "csf2", "ua-strategy"], 2: ["nis2", "ua-law", "ua-strategy", "carr2016"]}


def scenario_training(desk: Desk):
    """Зона Z2: агенти пропонують, аналітик перевіряє кожне твердження."""
    case = desk.create_case(
        ANALYST_1, question="Чи запроваджувати в органі обов'язкове регулярне навчання керівництва з управління кіберризиками?",
        decision="Затвердження внутрішнього порядку навчання керівного складу",
        options=["Обов'язкове щорічне навчання керівного складу", "Добровільне навчання за потреби"],
        consequence="tactical", uncertainty="moderate", jurisdictions=["UA"],
        official=OFFICIAL_1["name"], horizon="2027 рік",
        evidence_types=["правові акти", "стандарти", "стратегії"])
    case.approve_scope(OFFICIAL_1, "Межі погоджено")
    case.run_discovery(ANALYST_1, ["навчання", "training", "керівні органи"])
    case.run_provenance(ANALYST_1)
    case.run_appraisal(ANALYST_1)
    case.propose_claims(ANALYST_1)
    st = case.state()
    key = {e["id"]: st["sources"][e["payload"]["index"]]["record"]["key"] for e in st["candidates"].values()}
    for kid, e in sorted(st["candidates"].items()):
        text, src = e["payload"]["statement"], key[kid]
        if "40 годин" in text:
            case.verify_claim(ANALYST_1, kid, "reject",
                              reason="У тексті Art. 20(2) немає жодної норми про кількість годин; твердження не підтверджено.")
        elif src == "aiact":
            case.verify_claim(ANALYST_1, kid, "modify", location="Art. 4",
                              reason="Стаття не вимагає сертифікації; вона вимагає вжити заходів для достатнього рівня ШІ-грамотності.",
                              statement="Акт про ШІ зобов'язує постачальників і розгортачів систем ШІ вживати заходів для забезпечення достатнього рівня ШІ-грамотності персоналу.",
                              option="opt1", stance="supports",
                              uncertainty="Норма права ЄС; для українського органу застосовна за аналогією.")
        elif src == "nis2" and "навчання" in text:
            case.verify_claim(ANALYST_1, kid, "accept", location="Art. 20(2)",
                              reason="Фрагмент прямо встановлює обов'язок навчання членів керівних органів.",
                              option="opt1", stance="supports",
                              uncertainty="Директива ЄС; в Україні не діє безпосередньо.")
        elif src == "nis2" and "затверджують" in text:
            case.verify_claim(ANALYST_1, kid, "accept", location="Art. 20(1)",
                              reason="Фрагмент підтверджує відповідальність керівних органів.", option="context")
        elif src == "nis2":
            case.verify_claim(ANALYST_1, kid, "accept", location="Art. 23(4)",
                              reason="Строки підтверджено текстом; для питання навчання це лише контекст.", option="context")
        elif src == "csf2":
            case.verify_claim(ANALYST_1, kid, "accept", location="PR.AT (PR.AT-01, PR.AT-02)",
                              reason="Категорія описує навчання, але як добровільний результат без періодичності.",
                              option="opt2", stance="supports",
                              uncertainty="Добровільна рамка: не встановлює обов'язку.")
        elif "підготовки кадрів" in text:
            case.verify_claim(ANALYST_1, kid, "accept", location="розділ про пріоритети, кіберстійкість",
                              reason="Стратегія передбачає реформу підготовки та підвищення кіберграмотності.",
                              option="opt1", stance="supports")
        else:
            case.verify_claim(ANALYST_1, kid, "accept", location="розділи про засади та взаємодію",
                              reason="Підтверджено текстом; контекст для координації.", option="context")
    case.draft_brief(ANALYST_1)
    case.sign_brief(ANALYST_1, "Обов'язок навчання керівництва закріплено в праві ЄС і узгоджується зі Стратегією "
                    "кібербезпеки України. Рекомендую обов'язкове щорічне навчання.", "opt1")
    claims = sorted(c for c, v in case.state()["claims"].items() if v["option"] == "opt1")
    case.decide(OFFICIAL_1, "opt1", "Обов'язкове навчання відповідає напряму наближення до права ЄС і пріоритетам "
                "Стратегії; добровільний формат не гарантує охоплення керівного складу.", claims)
    approval = case.approve_transfer(OFFICIAL_1, "Партнерський орган (демо)", claims[:2])
    _, path = case.transfer(COORD, approval["id"])
    case.audit(AUDITOR, "Обґрунтування рішення відтворюється з журналу; відхилення твердження про 40 годин задокументовано.",
               rationale_clear=True, blind_checked=len(claims), blind_unsupported=0)
    return case, path


def scenario_transposition(desk: Desk, bundle_path: str | None = None):
    """Зона Z3 з ескалацією до Z4: веде аналітик, другий рецензент, окрема думка."""
    case = desk.create_case(
        ANALYST_1, question="Як доцільно запровадити в національне законодавство вимоги NIS2 щодо обов'язків керівних органів та звітування про інциденти?",
        decision="Вибір способу імплементації вимог NIS2",
        options=["Окремий новий закон", "Зміни до чинного Закону «Про основні засади забезпечення кібербезпеки України»"],
        consequence="institutional", uncertainty="moderate", jurisdictions=["UA"],
        official=OFFICIAL_1["name"], horizon="2027-2028 роки", evidence_types=["правові акти", "стратегії", "наукові публікації"])
    case.approve_scope(OFFICIAL_1)
    case.run_discovery(ANALYST_1, ["nis2", "транспозиція", "інциденти", "координація"])
    case.run_provenance(ANALYST_1)          # нерозв'язане джерело автоматично піднімає зону до Z4
    case.raise_trigger(ANALYST_1, "cross_jurisdiction")
    st = case.state()
    idx = {s["record"]["key"]: i for i, s in st["sources"].items()}
    for key, i in sorted(idx.items(), key=lambda kv: kv[1]):
        rec, prov = st["sources"][i]["record"], st["sources"][i]["prov"]["payload"]
        case.record_appraisal(
            ANALYST_1, i,
            currency="чинне" if prov["status"] == "current" else "застаріле або непридатне",
            applicability="пряма" if rec["jurisdiction"] == "UA" else "за аналогією, потребує адаптації",
            evidence_type={"law": "правовий акт", "strategy": "стратегія", "article": "наукова публікація",
                           "report": "інституційний звіт"}.get(rec["type"], rec["type"]),
            uncertainty="Походження не підтверджено, джерело не використовується." if not prov["usable"]
            else "Оцінено аналітиком після ознайомлення з текстом.")
    add = lambda key, text: case.add_claim(ANALYST_1, idx[key], text)["id"]
    k1 = add("nis2", "Керівні органи затверджують заходи з управління ризиками кібербезпеки, наглядають за їх виконанням і можуть нести відповідальність.")
    k2 = add("nis2", "Про значний інцидент подають раннє попередження протягом 24 годин і повідомлення протягом 72 годин.")
    k3 = add("ua-law", "Чинний закон уже визначає суб'єктів забезпечення кібербезпеки та засади координації їхньої діяльності.")
    k4 = add("ua-strategy", "Стратегія відводить координаційну роль Національному координаційному центру кібербезпеки.")
    case.verify_claim(ANALYST_1, k1, "accept", location="Art. 20(1)", reason="Прочитано повний текст статті.",
                      option="opt1", stance="supports", uncertainty="Новий для національного права обсяг обов'язків керівників.")
    case.verify_claim(ANALYST_1, k2, "accept", location="Art. 23(4)", reason="Строки підтверджено текстом.",
                      option="opt2", stance="dissents", uncertainty="Потребує узгодження з наявними порядками реагування.")
    case.verify_claim(ANALYST_1, k3, "accept", location="ст. 5, 8", reason="Підтверджено текстом закону.",
                      option="opt2", stance="supports")
    case.verify_claim(ANALYST_1, k4, "accept", location="розділ про взаємодію", reason="Підтверджено текстом.",
                      option="context")
    if bundle_path:
        with open(bundle_path, encoding="utf-8") as fh:
            bundle = json.load(fh)
        case.import_evidence(ANALYST_1, bundle, {cid: ("context", "supports") for cid in bundle["claims"]})
    case.draft_brief(ANALYST_1)
    case.sign_brief(ANALYST_1, "Чинний закон має придатну структуру суб'єктів і координації. Рекомендую зміни до "
                    "чинного закону; строки звітування потребують окремого узгодження.", "opt2")
    case.review_brief(ANALYST_2, "Докази перевірено, ланцюжки повні.",
                      dissent="Обсяг нових обов'язків керівників може вимагати окремого закону; ризик фрагментарних змін недооцінено.")
    relied = sorted(c for c, v in case.state()["claims"].items() if not v["reused"])
    case.decide(OFFICIAL_1, "opt2", "Зміни до чинного закону зберігають наявну систему суб'єктів і координації. "
                "Окрему думку рецензента враховано: обов'язки керівників виписати окремим розділом.", relied)
    case.audit(AUDITOR, "Журнал цілісний; ескалацію до Z4 та окрему думку зафіксовано до рішення.",
               corrections="Додати до каталогу офіційні джерела замість звіту без ідентифікатора.", rationale_clear=True)
    return case


def run_demo(data_dir: str) -> Desk:
    desk = Desk(data_dir)
    if desk.case_ids():
        raise SystemExit(f"У каталозі {data_dir} уже є справи; оберіть порожній каталог")
    _, bundle = scenario_training(desk)
    scenario_transposition(desk, bundle)
    return desk
