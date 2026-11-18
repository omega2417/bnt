"""Командний рядок: python -m aae <команда>."""
from __future__ import annotations

import argparse
import json
import sys

from . import autonomy, frameworks, roles
from .indicators import case_indicators, recall_precision
from .workflow import Desk


def _pct(value) -> str:
    return "—" if value is None else f"{value:.0%}"


def cmd_demo(args) -> int:
    from .demo import REFERENCE, run_demo
    desk = run_demo(args.data)
    for case in desk.cases():
        ind, st = case_indicators(case), case.state()
        rp = recall_precision(ind["retrieved_keys"], REFERENCE[case.number])
        print(f"\nСправа № {case.number}: {st['need']['question']}")
        print(f"  зона Z{ind['zone']}, ескалацій: {ind['escalations']}, записів у журналі: {ind['record_entries']}")
        print(f"  G1: прийнято {ind['g1_accept']}, змінено {ind['g1_modify']}, відхилено {ind['g1_reject']}")
        print(f"  простежуваність тверджень: {_pct(ind['traceability_rate'])}; "
              f"рішення відтворюване: {'так' if ind['reconstructable'] else 'ні'}; "
              f"цілісність журналу: {'так' if ind['integrity_ok'] else 'НІ'}")
        print(f"  повнота {_pct(rp['recall'])}, точність {_pct(rp['precision'])} (ілюстративний еталонний набір)")
    print(f"\nДані збережено в {args.data}. Вебінтерфейс: python -m aae serve --data {args.data}")
    return 0


def cmd_verify(args) -> int:
    desk, bad = Desk(args.data), 0
    for name, record in [("системний журнал", desk.system)] + [(f"справа № {c.number}", c.record) for c in desk.cases()]:
        problems = record.verify()
        bad += bool(problems)
        print(f"{name}: {len(record)} записів, " + ("цілісність підтверджено" if not problems else "ПОРУШЕННЯ"))
        for p in problems:
            print("   -", p)
    return 1 if bad else 0


def cmd_trace(args) -> int:
    case = Desk(args.data).case(args.case)
    start = args.entry or f"D-{args.case}"
    for e in case.record.trace_back(start):
        who = f"{roles.ROLES[e['actor']['role']]}: {e['actor']['name']}"
        print(f"{e['id']:<14} {e['type']:<20} {e['ts']}  {who}  <- {', '.join(e['refs']) or '—'}")
    return 0


def cmd_indicators(args) -> int:
    desk = Desk(args.data)
    out = {c.number: case_indicators(c) for c in desk.cases()}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_brief(args) -> int:
    print(Desk(args.data).case(args.case).brief_markdown())
    return 0


def cmd_frameworks(args) -> int:
    docs = list(frameworks.DOCUMENTS)
    print("Елемент".ljust(52) + " ".join(d.ljust(3) for d in docs))
    for e, title in frameworks.ELEMENTS.items():
        print(f"{e} {title}".ljust(52) + " ".join((frameworks.CODING[e][d][0] or "–").ljust(3) for d in docs))
    cov = frameworks.coverage_by_document()
    print("Індекс покриття (макс. 8)".ljust(52) + " ".join(f"{cov[d]:g}".ljust(3) for d in docs))
    return 0


def cmd_matrix(args) -> int:
    matrix = Desk(args.data).config["autonomy_matrix"] if args.data else autonomy.DEFAULT_MATRIX
    cons = list(autonomy.CONSEQUENCES)
    print("невизначеність \\ наслідки".ljust(28) + " ".join(c.ljust(14) for c in cons))
    for u in reversed(list(autonomy.UNCERTAINTIES)):
        print(u.ljust(28) + " ".join(f"Z{matrix[u][c]}".ljust(14) for c in cons))
    return 0


def cmd_serve(args) -> int:
    from .web import serve
    serve(args.data, args.host, args.port)
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="aae", description="AAE-Desk: підзвітна агентна підготовка доказів")
    sub = parser.add_subparsers(dest="cmd", required=True)

    def add(name, func, help, data=True):
        p = sub.add_parser(name, help=help)
        p.add_argument("--data", required=data, default=None, help="каталог даних органу")
        p.set_defaults(func=func)
        return p

    add("demo", cmd_demo, "створити два демонстраційні сценарії в порожньому каталозі")
    add("verify", cmd_verify, "перевірити цілісність усіх журналів рішень")
    p = add("trace", cmd_trace, "простежити запис назад до запиту")
    p.add_argument("case", type=int)
    p.add_argument("entry", nargs="?")
    add("indicators", cmd_indicators, "показники справ у форматі JSON")
    add("brief", cmd_brief, "вивести довідку справи (Markdown)").add_argument("case", type=int)
    add("frameworks", cmd_frameworks, "матриця кодування семи рамкових документів", data=False)
    add("matrix", cmd_matrix, "матриця зон автономії", data=False)
    p = add("serve", cmd_serve, "запустити вебінтерфейс")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (roles.NotPermitted, Exception) as exc:  # зрозуміле повідомлення замість трасування
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise
        print(f"Помилка: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
