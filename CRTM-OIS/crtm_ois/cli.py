"""Command line: crtm-ois assess E1 | crtm-ois experiments | crtm-ois report E2 | crtm-ois ask "..."."""
from __future__ import annotations

import argparse
import json
import sys

from . import bnk_pay, five_states
from .experiments import run_all
from .system import AssessmentError, assess


def main(argv=None):
    p = argparse.ArgumentParser(prog="crtm-ois")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("assess", help="assess a state E1..E5 or a JSON sheet")
    a.add_argument("state")
    a.add_argument("--operator", default="capped", choices=["capped", "hard", "additive"])
    a.add_argument("--samples", type=int, default=200_000)
    e = sub.add_parser("experiments", help="run all experiments of Section 3")
    e.add_argument("--out", default="results/results.json")
    r = sub.add_parser("report", help="offline analyst report (Ukrainian)")
    r.add_argument("state", default="E1", nargs="?")
    q = sub.add_parser("ask", help="ask the Claude analyst agent (needs anthropic + credentials)")
    q.add_argument("question")
    args = p.parse_args(argv)
    cfg = bnk_pay()
    if args.cmd == "assess":
        cfg = cfg.replace(operator=args.operator)
        if args.state in ("E1", "E2", "E3", "E4", "E5"):
            sheet = five_states(cfg)[args.state]
        else:
            raw = json.load(open(args.state))
            sheet = {tuple(k.split("|")): v for k, v in raw.items()}
        try:
            res = assess(cfg, sheet, n=args.samples)
        except AssessmentError as err:
            print(f"failure {err.code}: {err.detail}")
            sys.exit(2)
        print(json.dumps(res.summary(), indent=2, default=str))
    elif args.cmd == "experiments":
        res = run_all(args.out)
        print(json.dumps({"reproduction_ok": res["reproduction"]["n_ok"],
                          "order_ok": res["adequacy"]["_order_ok"],
                          "levels": {e: res["adequacy"][e]["level_code"] for e in ("E1", "E2", "E3", "E4", "E5")}}))
    elif args.cmd == "report":
        from .agents.llm import OfflineAnalyst, ResilienceToolbox
        print(OfflineAnalyst(ResilienceToolbox(cfg)).report(args.state))
    elif args.cmd == "ask":
        from .agents.llm import ClaudeAnalyst, ResilienceToolbox
        print(ClaudeAnalyst(ResilienceToolbox(cfg)).ask(args.question))


if __name__ == "__main__":
    main()
