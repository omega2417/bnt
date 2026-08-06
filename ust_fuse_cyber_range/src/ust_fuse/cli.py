"""Command-line interface for the UST-Fuse twin.

Examples
--------
    python -m ust_fuse.cli list
    python -m ust_fuse.cli run S04_sensor_dropout --seed 7 --out runs/s04
    python -m ust_fuse.cli campaign S01_baseline_clear -n 20 --out runs/camp01
    python -m ust_fuse.cli suite --out runs/suite       # all scenarios + index
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")  # headless by default

from . import __version__, run as run_scenario
from .campaign import Campaign
from .scenarios import SCENARIO_LIBRARY, list_scenarios
from .viz import figure_pack
from .viz.plots import plot_paired_forest, plot_campaign_box
from .report import write_report


def _cmd_list(args):
    print(f"UST-Fuse cyber-range digital twin v{__version__}")
    print(f"{len(SCENARIO_LIBRARY)} built-in scenarios:\n")
    for sid, scn in SCENARIO_LIBRARY.items():
        print(f"  {sid:28s} [{scn.lab or '—':6s}] {scn.title}")


def _cmd_run(args):
    res = run_scenario(args.scenario, seed=args.seed)
    out = args.out or os.path.join("runs", args.scenario)
    figs = figure_pack(res, out)
    paths = write_report(res, out, figures=figs)
    with open(os.path.join(out, "summary.json"), "w", encoding="utf-8") as f:
        json.dump({"manifest": res.manifest.to_dict(),
                   "summary": res.summary_table()}, f, indent=2, default=str, ensure_ascii=False)
    print(f"[run] {args.scenario} seed={args.seed} -> {out}")
    print(f"      report: {paths['html']}")


def _cmd_campaign(args):
    camp = Campaign(args.scenario, n_missions=args.n, base_seed=args.seed,
                    domain_randomize=args.domain_randomize).run(verbose=True)
    out = args.out or os.path.join("runs", f"campaign_{args.scenario}")
    os.makedirs(out, exist_ok=True)
    # representative single-mission figures + report with campaign section
    res0 = camp.results[0]
    figs = figure_pack(res0, out)
    plot_paired_forest(camp, save=os.path.join(out, "campaign_forest.png"))
    plot_campaign_box(camp, "mota", save=os.path.join(out, "campaign_box.png"))
    write_report(res0, out, figures=figs, campaign=camp, basename="campaign_report")
    camp.per_mission.to_csv(os.path.join(out, "per_mission.csv"), index=False)
    camp.paired_table().to_csv(os.path.join(out, "paired_stats.csv"), index=False)
    print(f"[campaign] {args.scenario} n={args.n} -> {out}")


def _cmd_suite(args):
    out = args.out or "runs/suite"
    os.makedirs(out, exist_ok=True)
    index = []
    for sid in list_scenarios():
        res = run_scenario(sid, seed=args.seed)
        sub = os.path.join(out, sid)
        figs = figure_pack(res, sub)
        write_report(res, sub, figures=figs)
        row = {"scenario": sid, "title": res.config.scenario.title,
               "lab": res.config.scenario.lab}
        for m in res.summary_table():
            row[f"{m['mode']}_mota"] = round(m["mota"], 3)
            row[f"{m['mode']}_rmse"] = round(m["rmse_pos"], 2)
        index.append(row)
        print(f"  done {sid}")
    with open(os.path.join(out, "index.json"), "w", encoding="utf-8") as f:
        json.dump(index, f, indent=2, ensure_ascii=False)
    print(f"[suite] {len(index)} scenarios -> {out}")


def build_parser():
    p = argparse.ArgumentParser(prog="ust_fuse", description="UST-Fuse cyber-range digital twin")
    p.add_argument("--version", action="version", version=f"ust_fuse {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)

    sp = sub.add_parser("list", help="list scenarios"); sp.set_defaults(func=_cmd_list)

    sp = sub.add_parser("run", help="run one scenario")
    sp.add_argument("scenario"); sp.add_argument("--seed", type=int, default=20260101)
    sp.add_argument("--out", default=None); sp.set_defaults(func=_cmd_run)

    sp = sub.add_parser("campaign", help="run a multi-mission campaign")
    sp.add_argument("scenario"); sp.add_argument("-n", type=int, default=20)
    sp.add_argument("--seed", type=int, default=20260101)
    sp.add_argument("--domain-randomize", action="store_true")
    sp.add_argument("--out", default=None); sp.set_defaults(func=_cmd_campaign)

    sp = sub.add_parser("suite", help="run all scenarios and build an index")
    sp.add_argument("--seed", type=int, default=20260101)
    sp.add_argument("--out", default=None); sp.set_defaults(func=_cmd_suite)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
