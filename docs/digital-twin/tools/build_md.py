#!/usr/bin/env python3
"""Assemble the expanded specification from the verified sources.

The document is generated, never hand-copied: every code block is read from
the file that the test suite executes, and every result table is read from the
artifacts of an actual run. Regenerate with::

    python3 tools/build_md.py

Any drift between the document and the implementation therefore shows up as a
diff in the generated file rather than as a silent inconsistency.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "source" / "UMSF_CyberRange_Digital_Twin_Expanded_UA.md"
EVIDENCE = ROOT / "evidence"
TARGET = ROOT / "UMSF_CyberRange_Digital_Twin_Modules_UA.md"

FENCE = {".py": "python", ".json": "json", ".toml": "toml", ".md": "markdown",
         "": "make"}


def plural(count: int, one: str, few: str, many: str) -> str:
    """Ukrainian numeral agreement, e.g. 1 рядок / 43 рядки / 15 рядків."""

    tens = count % 100
    units = count % 10
    if 11 <= tens <= 14:
        return many
    if units == 1:
        return one
    if 2 <= units <= 4:
        return few
    return many


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8").rstrip("\n")


def embed(relative: str, note: str = "") -> str:
    path = ROOT / relative
    language = FENCE.get(path.suffix, "text")
    lines = read(path).splitlines()
    # A Markdown file may itself contain fenced blocks, so it is wrapped in a
    # longer fence; everything else uses the ordinary three backticks.
    fence = "````" if path.suffix == ".md" else "```"
    header = [f"#### `{relative}`", ""]
    if note:
        header += [note, ""]
    header += [f"*{len(lines)} {plural(len(lines), 'рядок', 'рядки', 'рядків')}.*",
               "", f"{fence}{language}"]
    return "\n".join(header + lines + [fence, ""])


def group(title: str, intro: str, files: list[str]) -> str:
    parts = [f"### {title}", "", intro, ""]
    parts.extend(embed(name) for name in files)
    return "\n".join(parts)


# --------------------------------------------------------------- groups ----
GROUPS: list[tuple[str, str, list[str]]] = [
    ("H.1. Ядро: провенанс параметрів, час, випадковість, шина, контракт федерата",
     "Ядро не моделює жодного пристрою. Воно задає правила, за якими всі інші "
     "модулі можуть бути одночасно детермінованими, причинними та придатними "
     "до аудиту: кожен параметр несе власний статус доказовості, час зберігається "
     "цілим числом наносекунд із фіксованим порядком фаз, кожен стохастичний "
     "компонент має власний іменований потік випадковості, а кожна подія має "
     "стабільний ключ сортування.",
     ["umsf_twin/__init__.py",
      "umsf_twin/core/errors.py",
      "umsf_twin/core/parameters.py",
      "umsf_twin/core/clock.py",
      "umsf_twin/core/rng.py",
      "umsf_twin/core/bus.py",
      "umsf_twin/core/events.py",
      "umsf_twin/core/federate.py",
      "umsf_twin/core/safety.py",
      "umsf_twin/core/contracts.py",
      "umsf_twin/core/provenance.py",
      "umsf_twin/core/orchestrator.py"]),

    ("H.2. Мережа: 5 + 2 WAN-канали, маршрутизатори, черги, втрати, VPN",
     "Кожний фізичний канал є окремим об'єктом `WanLink` із власними health "
     "probes, hold-down, моделлю пакетних втрат Gilbert-Elliott та групою "
     "спільної причини відмови. Маршрутизатори Keenetic Titan і Viva "
     "представлені класом `MultiWanRouter` із політиками `primary_backup`, "
     "`balance` і `policy_routing`, затримкою failover, перебудовою NAT-стану та "
     "ймовірністю виживання сесій. Тунель між ділянками залишається "
     "surrogate-моделлю: `protocol` і `mtu` мають статус `UNINVENTORIED`.",
     ["umsf_twin/federates/network/queue.py",
      "umsf_twin/federates/network/loss.py",
      "umsf_twin/federates/network/wan.py",
      "umsf_twin/federates/network/router.py",
      "umsf_twin/federates/network/vpn.py",
      "umsf_twin/federates/network/federate.py"]),

    ("H.3. Wi-Fi: 48 + 6 точок доступу, контролери CloudKey, популяція клієнтів",
     "Усі 54 точки доступу інстанціюються поіменно. Дванадцять AP ділянки A "
     "мають відомий 1-Гбіт/с uplink, тридцять шість - `uplink_mbps=None`, і "
     "кожний похідний запис отримує прапорець `UNKNOWN_UPLINK`. Ефективна "
     "пропускна здатність обчислюється за формулою розділу 9.4, а контролер "
     "моделюється як елемент *видимості*: його втрата прибирає телеметрію AP, "
     "але не вимикає радіо.",
     ["umsf_twin/federates/wifi/ap.py",
      "umsf_twin/federates/wifi/clients.py",
      "umsf_twin/federates/wifi/controller.py",
      "umsf_twin/federates/wifi/federate.py"]),

    ("H.4. Активи: маршрутизатори, комутатори, сервери, 25 станцій Kali",
     "Кожний керований вузол - окремий екземпляр `Asset` із життєвим циклом "
     "`OFF -> BOOTING -> READY -> DEGRADED -> SHUTTING_DOWN -> FAILED`, власним "
     "енергетичним профілем і членством у групі живлення I, II або III. Саме це "
     "членство зв'язує активи з логікою відключення навантажень енергетичного "
     "федерата, тому послідовність III -> II -> I перевіряється на рівні "
     "конкретних вузлів, а не скалярного коефіцієнта.",
     ["umsf_twin/federates/assets/asset.py",
      "umsf_twin/federates/assets/fleet.py",
      "umsf_twin/federates/assets/federate.py"]),

    ("H.5. Штатне навантаження: DNS, DHCP, web, file, update, control",
     "Фонове навантаження не є білим шумом. Кожний сервіс має названу "
     "кандидатну модель (негативний біном для потоків, логнормаль для обсягів, "
     "самозбудження для burst-режимів) і добову сезонність, а агрегований рівень "
     "формується AR(1)-процесом. Родини розподілів названо явно саме для того, "
     "щоб етап калібрування розділу 13 міг їх оцінити, а не замінювати "
     "анонімний шум.",
     ["umsf_twin/federates/workload/services.py",
      "umsf_twin/federates/workload/federate.py"]),

    ("H.6. Синтетичні кіберподії: напівмарковський ланцюг стадій",
     "Багатокрокові події проходять причинний ланцюг "
     "`DORMANT -> RECON -> FOOTHOLD -> LATERAL -> C2 -> COLLECTION -> CONTAINED` "
     "із логнормальними часами перебування. Федерат змінює лише ознаки та "
     "лічильники подій; він не має жодного шляху виконання, який відкриває "
     "сокет, генерує пакет або називає зовнішню ціль, і відмовляється "
     "стартувати, якщо політика безпеки дозволяє egress.",
     ["umsf_twin/federates/threats/kill_chain.py",
      "umsf_twin/federates/threats/federate.py"]),

    ("H.7. Живлення: 13 комірок, пакет, BMS, АВР, зарядний пристрій, три EcoFlow",
     "Енергетична підсистема розкладена на фізичні елементи. `CellStack` "
     "містить тринадцять комірок із власними OCV і розбалансом; `BatteryPack` "
     "розв'язує узгоджене рівняння постійної потужності та теплову RC-модель; "
     "`BatteryManagementSystem` перевіряє COV/CUV/OCP/OTP/SCD і тримає latch; "
     "`TransferSwitch`, `Charger` і три окремі `EcoFlowUnit` більше не "
     "агрегуються в одну «батарею»; `LoadManager` виконує відключення груп "
     "III -> II зі збереженням групи I. Усі електричні межі мають статус "
     "`SYNTHETIC_DEMO_ONLY_UNVERIFIED` і не є дозволом для HIL.",
     ["umsf_twin/federates/power/cell.py",
      "umsf_twin/federates/power/pack.py",
      "umsf_twin/federates/power/bms.py",
      "umsf_twin/federates/power/ats.py",
      "umsf_twin/federates/power/charger.py",
      "umsf_twin/federates/power/ecoflow.py",
      "umsf_twin/federates/power/load_manager.py",
      "umsf_twin/federates/power/federate.py"]),

    ("H.8. Телеметрія: сенсори, дефекти вимірювання, store-and-forward",
     "Модуль реалізує вимоги розділу 9.11, яких не мав вихідний MVP: шум і "
     "квантування, зсув та дрейф годинника, пропуски MCAR/MAR/MNAR, застиглі "
     "значення, локальну буферизацію під час втрати транспорту, пакетну "
     "доставку після відновлення, дублікати та порушення порядку. Рядок із "
     "`telemetry_gap_marker=1` зберігає ідентифікацію й метадані якості, але "
     "не містить вимірювань і не отримує оцінки детектора.",
     ["umsf_twin/federates/telemetry/sensor.py",
      "umsf_twin/federates/telemetry/buffer.py",
      "umsf_twin/federates/telemetry/federate.py"]),

    ("H.9. Виявлення та реагування: правила, Edge-AI, кореляція, playbooks",
     "Три порівнювані режими розділу 9.12 реалізовані як окремі модулі й "
     "бачать однакові рядки телеметрії разом з їхніми дефектами. Онлайн-детектор "
     "навчається лише на слабких мітках прозорого правила, а не на ground truth, "
     "тому витік міток структурно неможливий. Реагування працює у shadow-режимі: "
     "рекомендація, пояснення, план відкату й запис аудиту формуються, але "
     "нічого не виконується.",
     ["umsf_twin/federates/detection/rules.py",
      "umsf_twin/federates/detection/edge_ai.py",
      "umsf_twin/federates/detection/correlation.py",
      "umsf_twin/federates/detection/federate.py",
      "umsf_twin/federates/response/playbooks.py",
      "umsf_twin/federates/response/federate.py"]),

    ("H.10. Ground truth: інжектовані інтервали та журнал переходів",
     "Вихідний MVP зберігав лише наперед задані інтервали інжекцій. Тут "
     "додано другий, окремо позначений тип істини - фактичні переходи станів "
     "(failover WAN, стан живлення, спрацювання BMS, втрата AP). Мітки для "
     "метрик виявлення беруться виключно з інжектованих інтервалів, тож "
     "детектор не може отримати кредит за спостереження наслідку замість "
     "причини.",
     ["umsf_twin/federates/truth/federate.py"]),

    ("H.11. Конвеєр даних: нормалізація, ознаки, розмітка, gates, експорт",
     "Конвеєр однаковий для `SIM`, `EMU` і `REPLAY`: реальні експорти "
     "колекторів проходять ту саму нормалізацію, що й синтетичні рядки, тому "
     "sim-to-real порівняння виконується над однією схемою. Gates розділу 15 є "
     "виконуваними перевірками, а не текстом: повнота, монотонність часу, частка "
     "дублікатів, неперервність SoC, знак струму, узгодженість напруг і "
     "коректність gap-рядків.",
     ["umsf_twin/pipelines/normalization.py",
      "umsf_twin/pipelines/features.py",
      "umsf_twin/pipelines/labeling.py",
      "umsf_twin/pipelines/validation.py",
      "umsf_twin/pipelines/export.py"]),

    ("H.12. Рівень експерименту: сценарії, DOE, Monte Carlo, калібрування, звіт",
     "Компілятор сценаріїв перевіряє схему, політику безпеки та документовані "
     "інваріанти інвентаризації одночасно. DOE підтримує повний і дробовий "
     "факторний план, латинський гіперкуб і послідовність низької розбіжності з "
     "рандомізацією за блоками. Monte Carlo зупиняється за досягнутою "
     "півшириною довірчого інтервалу на рівні прогону як одиниці аналізу. "
     "Калібрування містить KS, Wasserstein-1, покриття, Nelder-Mead і ABC, з "
     "роздільним звітуванням zero-shot і adapted transfer.",
     ["umsf_twin/experiment/scenario.py",
      "umsf_twin/experiment/doe.py",
      "umsf_twin/experiment/stats.py",
      "umsf_twin/experiment/metrics.py",
      "umsf_twin/experiment/montecarlo.py",
      "umsf_twin/experiment/calibration.py",
      "umsf_twin/experiment/runner.py",
      "umsf_twin/experiment/report.py"]),

    ("H.13. Адаптери вендорської телеметрії",
     "Адаптери переводять експорти UniFi, Keenetic, BMS/MQTT та OpenTelemetry у "
     "контракти двійника. У режимі `SIM` вони є чистими парсерами над "
     "збереженими фікстурами: жоден адаптер не відкриває з'єднання, а адаптер "
     "BMS навмисно не має функції публікації - це кодове вираження правила, що "
     "двійник ніколи не пише у пристрій безпеки.",
     ["umsf_twin/adapters/unifi.py",
      "umsf_twin/adapters/keenetic.py",
      "umsf_twin/adapters/bms_mqtt.py",
      "umsf_twin/adapters/otel.py"]),

    ("H.14. Інтерфейс командного рядка",
     "CLI повторює робочий процес розділу 18: `validate`, `run`, `doe`, `mc`, "
     "`gates`, `report`, `calibrate` через модуль калібрування і `verify` для "
     "перевірки детермінізму та розділення seed. Проєктований CLI розділу 24 "
     "цим реалізовано; нереалізованими лишаються лише режими `EMU` і `HIL`.",
     ["umsf_twin/cli.py",
      "umsf_twin/__main__.py"]),
]

CONFIG_FILES = ["umsf_twin/config/inventory/demo.json",
                "umsf_twin/config/policies/safety.json",
                "umsf_twin/config/policies/factors.json",
                "umsf_twin/config/scenarios/baseline-quiet.json",
                "umsf_twin/config/scenarios/wan-failover.json",
                "umsf_twin/config/scenarios/power-outage.json",
                "umsf_twin/config/scenarios/cyber-campaign.json",
                "umsf_twin/config/scenarios/compound-challenge.json"]


def module_index() -> str:
    rows = ["| Модуль | Елемент полігону | Відповідальність | Рядків |",
            "|---|---|---|---:|"]
    mapping = [
        ("core/parameters.py", "будь-який параметр", "значення + одиниця + доказовість + джерело + невизначеність"),
        ("core/clock.py", "єдиний логічний час", "наносекунди, фази 0-8, мітка інтервалу"),
        ("core/rng.py", "стохастика", "іменовані потоки з (seed, replicate, namespace)"),
        ("core/bus.py", "причинність", "черга з ключем (t, phase, source, seq, id)"),
        ("core/events.py", "сценарна подія", "контракт параметрів, профілі наростання"),
        ("core/federate.py", "будь-який федерат", "initialize/next_time/apply_event/advance/observe/checkpoint/reset/health"),
        ("core/safety.py", "політика безпеки", "allowlist подій, режими, бюджети, заборона egress"),
        ("core/contracts.py", "схеми даних", "конверт події, телеметрія, ground truth, alert"),
        ("core/provenance.py", "run manifest", "хеші конфігурації, коду, артефактів, відбиток середовища"),
        ("core/orchestrator.py", "федерація", "майстер-годинник, фазовий крок, інваріанти"),
        ("federates/network/wan.py", "WAN-канал (5 + 2)", "UP/DEGRADED/DOWN/RECOVERING, probes, hold-down, common cause"),
        ("federates/network/router.py", "Keenetic Titan / Viva", "вибір каналу, failover, NAT, виживання сесій"),
        ("federates/network/queue.py", "черга каналу", "флюїдна модель, затримка, дропи"),
        ("federates/network/loss.py", "втрати пакетів", "Gilbert-Elliott та незалежна модель"),
        ("federates/network/vpn.py", "міжсайтовий VPN", "UP/DEGRADED/REKEYING/DOWN/RECONNECTING, буферизація"),
        ("federates/wifi/ap.py", "точка доступу (48 + 6)", "C_eff, RSSI, airtime, retries, невідомий uplink"),
        ("federates/wifi/clients.py", "клієнти Wi-Fi", "негативний біном із добовою сезонністю"),
        ("federates/wifi/controller.py", "CloudKey Gen1/Gen2", "adoption, видимість, розриви телеметрії"),
        ("federates/assets/asset.py", "керований вузол", "життєвий цикл, споживання, група живлення"),
        ("federates/assets/fleet.py", "інвентар вузлів", "маршрутизатори, комутатори, сервери, 25 Kali"),
        ("federates/workload/services.py", "штатні сервіси", "DNS/DHCP/web/file/update/control"),
        ("federates/threats/kill_chain.py", "стадії атаки", "напівмарковський причинний ланцюг"),
        ("federates/threats/federate.py", "профілі подій", "ознакові ефекти без реального трафіку"),
        ("federates/power/cell.py", "13 комірок 13S", "OCV, розбаланс, термінальна напруга"),
        ("federates/power/pack.py", "48-В пакет", "P=I(U-IR), енергія, теплова RC-модель"),
        ("federates/power/bms.py", "BMS", "COV/CUV/OCP/OTP/SCD, latch, балансування"),
        ("federates/power/ats.py", "АВР", "перемикання джерела, час переходу, лічильники"),
        ("federates/power/charger.py", "зарядний пристрій", "паспортна межа 10 A, програмна межа 4 A, taper"),
        ("federates/power/ecoflow.py", "3 станції EcoFlow", "окремі black-box моделі, крива ККД"),
        ("federates/power/load_manager.py", "групи I/II/III", "shedding III -> II зі збереженням I"),
        ("federates/power/federate.py", "стан живлення", "MAINS/BATTERY/LOAD_SHED/ISOLATED/HOLD/CHARGE_DELAY"),
        ("federates/telemetry/sensor.py", "сенсор", "шум, квантування, годинник, MCAR/MAR/MNAR"),
        ("federates/telemetry/buffer.py", "транспорт телеметрії", "буферизація, burst, дублікати, out-of-order"),
        ("federates/telemetry/federate.py", "запис телеметрії", "збірка контрактного рядка, gap marker"),
        ("federates/detection/rules.py", "прозорий baseline", "іменовані правила з вагами"),
        ("federates/detection/edge_ai.py", "Edge-AI", "онлайн-логістична регресія на EWMA-ознаках"),
        ("federates/detection/correlation.py", "міжсайтова кореляція", "причинне вікно, спільна оцінка"),
        ("federates/response/playbooks.py", "playbooks", "дія, відкат, радіус впливу, вимога апруву"),
        ("federates/response/federate.py", "реагування", "shadow-режим, відкладений ефект, аудит"),
        ("federates/truth/federate.py", "ground truth", "інжектовані інтервали + журнал переходів"),
        ("pipelines/validation.py", "data-quality gates", "виконувані перевірки розділу 15"),
        ("experiment/scenario.py", "сценарій", "схема + політика + інваріанти інвентаризації"),
        ("experiment/doe.py", "план експерименту", "факторний, LHS, low-discrepancy, блоки"),
        ("experiment/montecarlo.py", "Monte Carlo", "послідовна зупинка, рідкісні події"),
        ("experiment/calibration.py", "sim-to-real", "KS, Wasserstein, Nelder-Mead, ABC"),
        ("experiment/runner.py", "прогон", "федерація, артефакти, manifest"),
        ("cli.py", "інтерфейс", "validate/run/doe/mc/gates/report/verify"),
    ]
    for relative, element, duty in mapping:
        path = ROOT / "umsf_twin" / relative
        count = len(read(path).splitlines()) if path.exists() else 0
        rows.append(f"| `umsf_twin/{relative}` | {element} | {duty} | {count} |")
    return "\n".join(rows)


def updated_summary(text: str) -> str:
    """Bring the closing summary of version 1.0 in line with version 2.0.

    Only the sentence that enumerated what was *not* yet implemented is
    replaced; the scientific boundary of the original summary is preserved
    verbatim, because version 2.0 does not weaken it.
    """

    return text.strip().replace(
        "Фактично виконаний результат — демонстраційний aggregate-SIM MVP, "
        "що пройшов 10 smoke/unit tests",
        "Фактично виконаним результатом версії 1.0 був демонстраційний "
        "aggregate-SIM MVP, що пройшов 10 smoke/unit tests").replace(
        "EMU, REPLAY реальних даних, HIL, калібрування, AI, усі "
        "data-quality/safety gates і фізичний runbook залишаються вимогами "
        "майбутньої реалізації, а не вже отриманим доказом реальної "
        "ефективності.",
        "У версії 2.0 виконуваними стали також data-quality і safety gates, "
        "конвеєр ознак і розмітки, DOE, Monte Carlo, калібрувальні процедури, "
        "Edge-AI з міжсайтовою кореляцією та повний CLI (додатки H-K). "
        "Режими EMU і HIL, REPLAY реальних даних, packet/RF backend і фізичний "
        "runbook залишаються вимогами майбутньої реалізації, а жодна із "
        "синтетичних метрик не є доказом реальної ефективності.")


def passed_test_count() -> int:
    """Read the number of passing checks from the recorded test output."""

    for line in read(EVIDENCE / "tests.txt").splitlines():
        if "passed in" in line and "/" in line:
            return int(line.split("/", 1)[0].strip())
    return 0


def totals() -> tuple[int, int]:
    files = [p for p in (ROOT / "umsf_twin").rglob("*.py")
             if "__pycache__" not in p.parts]
    files.append(ROOT / "tests" / "run_tests.py")
    return len(files), sum(len(read(p).splitlines()) for p in files)


def build() -> str:
    original = read(SOURCE)
    marker = "\n# Підсумок\n"
    head, _, tail_summary = original.partition(marker)

    head = head.replace(
        'version: "1.0"',
        'version: "2.0"\nimplementation: "umsf_twin modular reference package"')
    head = head.replace(
        'subtitle: "Розширена технічна специфікація, еталонний MVP і протокол '
        'синтетичних експериментів для підготовки реального випробування"',
        'subtitle: "Розширена технічна специфікація, модульна еталонна реалізація '
        'та протокол синтетичних експериментів для підготовки реального випробування"')
    head = head.replace(
        "7. Перенести лише сценарії, що пройшли всі readiness gates, на фізичний полігон.",
        "7. Перенести лише сценарії, що пройшли всі readiness gates, на фізичний полігон.\n\n"
        "> **Оновлення версії 2.0.** Розділи 1-27 і додатки A-G описують "
        "специфікацію та вихідний монолітний MVP без змін. Додатки H-N, додані у "
        "цій версії, містять повну модульну програмну реалізацію, у якій кожний "
        "елемент полігону представлено окремим модулем, а також процедуру "
        "відтворення експериментів, матрицю трасування та перевірені результати "
        "прогонів. Для відтворення експериментів слід використовувати саме "
        "модульну реалізацію (додаток H); додатки B-D збережено як історичний "
        "MVP і базу порівняння.")

    # Two places in Part I described the monolithic MVP as the only executable
    # artifact. They are updated here - not silently rewritten elsewhere - so
    # that Part I cannot contradict the evidence of Appendix K.
    head = head.replace(
        "Він **не** реалізує окремі моделі трьох EcoFlow, packet/RF backend, "
        "реальну буферизацію/duplicates/out-of-order delivery, повний "
        "asset-level load shedding, ML/AI або EMU/HIL. Повна реалізація повинна "
        "перейти до per-parameter wrapper із `value`, `unit`, `evidence_status`, "
        "`source` та `uncertainty`.",
        "Він **не** реалізує окремі моделі трьох EcoFlow, packet/RF backend, "
        "реальну буферизацію/duplicates/out-of-order delivery, повний "
        "asset-level load shedding, ML/AI або EMU/HIL. Повна реалізація повинна "
        "перейти до per-parameter wrapper із `value`, `unit`, `evidence_status`, "
        "`source` та `uncertainty`.\n\n"
        "> Усе перелічене в цьому абзаці, окрім packet/RF backend та режимів "
        "`EMU`/`HIL`, реалізовано у модульному пакеті `umsf_twin` (додаток H): "
        "окремі моделі трьох EcoFlow, дефекти й буферизація телеметрії, "
        "asset-level load shedding за групами I/II/III, Edge-AI з міжсайтовою "
        "кореляцією та per-parameter wrapper `Parameter` зі статусом доказовості. "
        "Межі, що лишаються, зведено в додатку N.")

    file_count, line_count = totals()
    evidence_scenarios = read(EVIDENCE / "scenarios.md")

    parts: list[str] = [head.rstrip("\n"), "", "---", ""]
    parts.append(f"""# Частина II. Модульна програмна реалізація

# Додаток H. Модульний еталонний двійник `umsf_twin`

Додатки B-D містять монолітний MVP: один файл, один клас `TwinSimulation`,
скалярні наближення замість елементів. Цього достатньо для перевірки формату
даних, але недостатньо для відтворення експериментів, у яких треба міняти
окремий канал, окрему точку доступу, окрему комірку батареї або окремий сенсор
і бачити наслідок.

Додаток H містить повну модульну реалізацію `umsf_twin`: **{file_count} {plural(file_count, "файл", "файли", "файлів")}
пакета й набору тестів, {line_count} {plural(line_count, "рядок", "рядки", "рядків")} Python, лише стандартна
бібліотека**. Кожний елемент
полігону є окремим програмним об'єктом із власним станом, власним потоком
випадковості та власним внеском у телеметрію. Пакет виконується, покритий
тестами додатка J і згенерував результати додатка K.

## H.0. Принципи модульної декомпозиції

1. **Один елемент - один модуль.** WAN-канал, маршрутизатор, точка доступу,
   контролер, вузол, сервіс, стадія атаки, комірка, пакет, BMS, АВР, зарядний
   пристрій, станція EcoFlow, група навантаження, сенсор, буфер транспорту,
   детектор, playbook - окремі класи, а не поля одного словника.
2. **Єдиний контракт федерата.** Усі підсистеми реалізують
   `initialize`, `next_time`, `apply_event`, `advance`, `observe`,
   `checkpoint`, `reset`, `health`, тому оркестратор не знає нічого про їхню
   фізику.
3. **Провенанс замість чисел.** Параметр без статусу доказовості не потрапляє
   в модель; режим `HIL` відмовляється стартувати, якщо хоча б один параметр
   слабший за `VENDOR_SPEC`.
4. **Безпека як код.** Політика безпеки перевіряється компілятором сценаріїв,
   федератом загроз і оркестратором; порушення підіймає виняток, а не
   попередження.
5. **Причинність за побудовою.** Порядок фаз 0-8 і мінімальна затримка реакції
   `T + delta_min` реалізовані у ядрі, а не в кожному модулі окремо.
6. **Відтворюваність за побудовою.** Хеш конфігурації, хеш вихідного коду,
   відбиток середовища й SHA-256 кожного артефакту записуються у manifest
   кожного прогону.

## H.0.1. Карта модулів

{module_index()}

## H.0.2. Порядок кроку федерації

```mermaid
flowchart LR
    P["20 power"] --> A["30 assets"] --> W["40 workload"] --> T["45 threats"]
    T --> N["50 network"] --> F["55 wifi"] --> M["60 telemetry"]
    M --> D["70 detection"] --> R["80 response"] --> G["90 ground truth"]
```

Порядок задано полем `order` кожного федерата: живлення визначає, які активи
живляться; активи визначають попит; попит і синтетичні події визначають стан
мережі та Wi-Fi; телеметрія збирає спостережуване; детектори бачать лише те,
що доставила телеметрія; реагування діє не раніше наступного такту; ground
truth фіксує і інжекції, і фактичні переходи.
""")

    for title, intro, files in GROUPS:
        parts.append(group(title, intro, files))

    parts.append(f"""---

# Додаток I. Конфігурації, політики та сценарії

Конфігурація є єдиним джерелом чисел. Усі непідтверджені значення мають
`evidence_class: synthetic_demo`, а невідомі - літерал `UNINVENTORIED`, який
реєстр параметрів переводить у статус `UNKNOWN` і який блокує режим `HIL`.

П'ять сценаріїв покривають базовий стан, мережеві відмови, енергетичну
відмову, багатоетапну синтетичну кампанію та комбінований стрес.

""" + "\n".join(embed(name) for name in CONFIG_FILES))

    parts.append("""---

# Додаток J. Тести модульної реалізації

Набір відповідає восьми родинам додатка G: unit, property, contract,
determinism, safety, integration, calibration, performance. Він не потребує
`pytest` і виконується як звичайний скрипт.

""" + embed("tests/run_tests.py"))

    parts.append(f"""---

# Додаток K. Відтворення експериментів

## K.1. Команди

{embed("Makefile", "Мінімальний інтерфейс відтворення.")}

{embed("README.md", "Стислий опис пакета для нового користувача.")}

{embed("pyproject.toml")}

## K.2. Перевірений результат тестів

```text
{read(EVIDENCE / "tests.txt")}
```

## K.3. Перевірка інвентаризації та доказовості

```json
{read(EVIDENCE / "validate.json")}
```

Чотири параметри лишаються невідомими - `power.site_a.chemistry`,
`power.site_a.parallel_count`, `vpn.mtu`, `vpn.protocol`. Це не дефект
реалізації, а коректний стан: доки їх не виміряно, режим `HIL` заблоковано
програмно.

## K.4. Перевірка детермінізму та розділення seed

```json
{read(EVIDENCE / "verify.json")}
```

Два прогони з однаковим `replicate_id` дають ідентичний канонічний хеш рядків;
прогін з іншим `replicate_id` дає інший, тобто потоки випадковості справді
розділені.

## K.5. Демонстраційний прогін на три репліки

```json
{read(EVIDENCE / "run.json")}
```

## K.6. Перевірені результати п'яти сценаріїв

{evidence_scenarios}

Читання таблиці. `baseline-quiet` не дає жодної тривоги - прозорий baseline не
має хибних спрацювань на штатному навантаженні. `cyber-campaign` показує
precision 1.0 при низькому recall: правила ловлять лише інтенсивну
розвідку, а latent-стадії лишаються невиявленими; це і є смисл порівняння з
Edge-AI, а не доказ якості AI. `power-outage` демонструє 797 кроків із
відключеними групами навантаження при збереженні групи I. `compound-challenge`
одночасно ламає живлення, транспорт і телеметрію - доступність ділянки A падає
до 91.3%, а gates усе одно проходять, бо дефекти телеметрії позначені, а не
приховані.

## K.7. Monte Carlo з послідовною зупинкою

```json
{read(EVIDENCE / "mc.json")}
```

Кампанію зупинено на п'ятій репліці, щойно півширина довірчого інтервалу
досягла цілі; одиницею аналізу є прогін, тому інтервал будується кластерним
bootstrap.

## K.8. Автоматично згенерований звіт прогону

Файл `report.md` формується з артефактів завершеного прогону, тому кожне число
у ньому простежується до файлу, чий SHA-256 записано у manifest.

````markdown
{read(EVIDENCE / "report-power-outage.md")}
````
""")

    parts.append("""---

# Додаток L. Матриця трасування: вимога -> модуль -> тест

| Розділ специфікації | Модуль реалізації | Тест |
|---|---|---|
| 5.3 інваріанти інвентаризації | `experiment/scenario.py` | `test_inventory_invariants_enforced` |
| 6.4 контракт федерата | `core/federate.py`, `core/orchestrator.py` | `test_run_produces_valid_artifacts` |
| 6.5 єдиний логічний час і порядок фаз | `core/clock.py`, `core/bus.py` | `test_bus_orders_by_phase_then_source` |
| 9.1 модель черги | `federates/network/queue.py` | `test_queue_conservation`, `test_zero_capacity_marks_path_unavailable` |
| 9.2 multi-WAN і failover | `federates/network/wan.py`, `router.py` | `test_wan_failover_and_return` |
| 9.3 VPN | `federates/network/vpn.py` | `test_run_produces_valid_artifacts` |
| 9.4 Wi-Fi і невідомі uplink | `federates/wifi/ap.py` | `test_ap_capacity_uses_unknown_uplink_flag` |
| 9.5 штатне навантаження | `federates/workload/services.py` | `test_step_cost_is_bounded` |
| 9.6 синтетичні кіберподії | `federates/threats/kill_chain.py` | `test_kill_chain_is_causal` |
| 9.7 три EcoFlow | `federates/power/ecoflow.py` | `test_power_outage_drives_shedding_and_recovery` |
| 9.8 48-В батарея, P=I(U-IR) | `federates/power/pack.py`, `cell.py` | `test_constant_power_solution`, `test_voltage_within_cell_envelope` |
| 9.8 межі заряду і BMS | `federates/power/bms.py`, `charger.py` | `test_charge_and_discharge_current_signs` |
| 9.9 машина станів живлення | `federates/power/federate.py` | `test_power_outage_drives_shedding_and_recovery` |
| 9.9 групи I/II/III | `federates/power/load_manager.py` | `test_load_shedding_order_preserves_group_one` |
| 9.11 дефекти телеметрії | `federates/telemetry/sensor.py`, `buffer.py` | `test_gap_rows_blank_measurements` |
| 9.12 три режими виявлення | `federates/detection/*` | `test_detection_metrics_arithmetic` |
| 10 контракти даних | `core/contracts.py` | `test_record_rejects_unknown_and_missing_fields`, `test_strict_json_rejects_nan` |
| 10.5 ground truth | `federates/truth/federate.py` | `test_labels_ignore_transition_truth` |
| 10.8 run manifest | `core/provenance.py` | `test_run_produces_valid_artifacts`, `test_run_directory_is_not_overwritten` |
| 12 DOE | `experiment/doe.py` | `test_doe_design_is_within_bounds` |
| 12.6-12.7 Monte Carlo і рідкісні події | `experiment/montecarlo.py` | `test_monte_carlo_stops_on_target`, `test_statistics_helpers` |
| 13 калібрування і fidelity | `experiment/calibration.py` | `test_fidelity_detects_distribution_shift`, `test_abc_recovers_known_parameter`, `test_nelder_mead_finds_minimum` |
| 14 статистика | `experiment/stats.py` | `test_statistics_helpers` |
| 15 data-quality gates | `pipelines/validation.py` | `test_gates_detect_corrupted_data` |
| 16 контроль витоку | `pipelines/labeling.py`, `federates/detection/edge_ai.py` | `test_labels_ignore_transition_truth` |
| 17 версії та drift | `core/provenance.py`, `core/events.py` | `test_config_hash_covers_event_defaults` |
| 19 безпека і dual-use | `core/safety.py`, `federates/threats/federate.py` | `test_event_allowlist`, `test_egress_requires_allowlist`, `test_budget_limits` |
| 20 відтворюваність | `core/rng.py`, `experiment/runner.py` | `test_same_seed_same_rows`, `test_replicates_differ` |
| 22 готовність до фізичного полігону | `core/parameters.py` | `test_hil_requires_approval`, `test_hil_refuses_unknown_parameters` |
| 24 CLI | `cli.py` | `test_run_produces_valid_artifacts` |

# Додаток M. Покриття елементів полігону програмними об'єктами

| Елемент полігону | Кількість | Програмне представлення | Статус |
|---|---:|---|---|
| Маршрутизатор Keenetic Titan (ділянка A) | 1 | `MultiWanRouter` + `Asset("A-RTR-1")` | реалізовано |
| Маршрутизатор Keenetic Viva (ділянка B) | 1 | `MultiWanRouter` + `Asset("B-RTR-1")` | реалізовано |
| WAN-канали ділянки A | 5 | `WanLink` × 5 з групами спільної причини | реалізовано |
| WAN-канали ділянки B | 2 | `WanLink` × 2 | реалізовано |
| Міжсайтовий VPN | 1 | `VpnTunnel` | surrogate, параметри `UNINVENTORIED` |
| Точки доступу ділянки A | 48 | `AccessPoint` × 48 (12 із 1 Гбіт/с, 36 `UNKNOWN_UPLINK`) | реалізовано агреговано за RF |
| Точки доступу ділянки B | 6 | `AccessPoint` × 6 (100 Мбіт/с) | реалізовано агреговано за RF |
| Контролери CloudKey Gen2 / Gen1 | 2 | `Controller` × 2 | реалізовано |
| Робочі станції Kali (ділянка B) | 25 | `Asset(role="kali_workstation")` × 25 | реалізовано |
| Навчальні станції (ділянка A) | 24 | `Asset(role="workstation")` × 24 | демонстраційна кількість |
| Інфраструктурні вузли (комутатор, VPN-шлюз, monitoring, log, edge-AI) | 10 | `Asset` за ролями | реалізовано |
| Станції EcoFlow | 3 | `EcoFlowUnit` × 3 у `EcoFlowBank` | окремі black-box моделі, параметри не виміряні |
| Групи 13S проєктної 48-В батареї | 13 | `Cell` × 13 у `CellStack` | synthetic_demo_conditional |
| BMS | 1 | `BatteryManagementSystem` із COV/CUV/OCP/OTP/SCD | межі неверифіковані |
| АВР | 1 | `TransferSwitch` | час переходу неверифікований |
| Зарядний пристрій 10 A | 1 | `Charger` (паспорт 10 A, програмна межа 4 A) | не є дозволом для HIL |
| Групи навантаження I/II/III | 3 | `LoadManager` + поле `power_group` кожного активу | реалізовано на рівні вузлів |
| Штатні сервіси | 6 | `ServiceProfile` × 6 | кандидатні розподіли |
| Профілі синтетичних подій | 18 | `EVENT_PARAM_DEFAULTS` + `KillChain` | реалізовано |
| Сенсори телеметрії | 6 | `Sensor` із моделлю пропусків | реалізовано |
| Детектори | 3 | `RuleEngine`, `EdgeDetector`, `CrossSiteCorrelator` | реалізовано |
| Playbooks реагування | 6 | `Playbook` × 6 у shadow-режимі | реалізовано |

# Додаток N. Межі модульної реалізації

Реалізовано у версії 2.0 те, чого не мав MVP додатка B: окремі об'єкти для
кожного елемента, дефекти телеметрії (буферизація, дублікати, порушення
порядку, застиглі значення, MCAR/MAR/MNAR), asset-level відключення груп
навантаження, окремі моделі трьох EcoFlow, журнал переходів у ground truth,
Edge-AI та міжсайтова кореляція, DOE, Monte Carlo з послідовною зупинкою,
калібрування ABC/Nelder-Mead, повний CLI і виконувані data-quality gates.

Нереалізованим лишається таке, і жодне твердження документа на це не спирається:

| Обмеження | Наслідок | Умова зняття |
|---|---|---|
| Немає packet-level і RF-бекенду (ns-3) | Wi-Fi і черги лишаються агрегованими; тверджень про покриття немає | інтеграція ns-3 як федерата з тим самим контрактом |
| Немає FMU/Modelica та електрохімії | Батарея лишається gray-box surrogate | datasheet, PyBaMM або FMU після інвентаризації |
| Режими `EMU` і `HIL` не виконуються | перевірено лише `SIM`; `REPLAY` має конвеєр, але не має реальних даних | Containerlab/FRR для `EMU`; підписаний протокол для `HIL` |
| Параметри `UNINVENTORIED` | 4 параметри блокують `HIL` програмно | фізична інвентаризація розділу 3 |
| Синтетичні електричні межі | не є дозволом на струм чи напругу | datasheet і затверджений електричний розрахунок |
| Детектори не калібровані | метрики виявлення характеризують модель, не полігон | реальна телеметрія і holdout розділу 13 |
""")

    passed = passed_test_count()
    parts.append(f"""---

# Підсумок
{updated_summary(tail_summary)}

## Підсумок версії 2.0

Версія 2.0 перетворює специфікацію на виконувану систему. Кожний елемент
кіберполігону - канал, маршрутизатор, точка доступу, контролер, вузол, сервіс,
стадія атаки, комірка, пакет, BMS, АВР, зарядний пристрій, станція EcoFlow,
група навантаження, сенсор, транспорт телеметрії, детектор і playbook - має
власний програмний модуль зі спільним контрактом федерата. Разом це {file_count} {plural(file_count, "файл", "файли", "файлів")} пакета й тестів, {line_count} {plural(line_count, "рядок", "рядки", "рядків")} без зовнішніх залежностей і {passed} {plural(passed, "автоматична перевірка", "автоматичні перевірки", "автоматичних перевірок")}, які проходять повністю.

Це не робить синтетичні числа вимірюваннями. Воно робить інше й достатнє для
етапу підготовки: експеримент можна відтворити командою, кожний його елемент
можна змінити окремо, кожний параметр несе свій статус доказовості, кожне
порушення інваріанта зупиняє прогін, а межа між `synthetic`, `emulated` і
`measured` зафіксована в коді, а не в добрих намірах.
""")

    return "\n".join(parts).rstrip("\n") + "\n"


def main() -> int:
    TARGET.write_text(build(), encoding="utf-8")
    lines = len(TARGET.read_text(encoding="utf-8").splitlines())
    print(f"wrote {TARGET.relative_to(ROOT)} ({lines} lines, "
          f"{TARGET.stat().st_size // 1024} KiB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
