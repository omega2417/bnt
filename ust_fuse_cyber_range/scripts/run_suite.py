"""Run every scenario, render figures + reports, and a scenario×mode heatmap.

    python scripts/run_suite.py --out out/suite
"""
import argparse
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import ust_fuse as uf
from ust_fuse.viz import figure_pack
from ust_fuse.viz.plots import plot_scenario_heatmap
from ust_fuse.report import write_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="out/suite")
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args()

    os.makedirs(args.out, exist_ok=True)
    rows = []
    for sid in uf.list_scenarios():
        res = uf.run(sid, seed=args.seed)
        sub = os.path.join(args.out, sid)
        if not args.no_figures:
            figs = figure_pack(res, sub)
            write_report(res, sub, figures=figs)
        for m in res.summary_table():
            m = dict(m)
            m["scn"] = sid
            rows.append(m)
        print(f"  done {sid}")

    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(args.out, "suite_metrics.csv"), index=False)
    for metric in ["mota", "rmse_pos", "ospa_mean", "track_completeness", "ece"]:
        plot_scenario_heatmap(df, metric=metric,
                              save=os.path.join(args.out, f"heatmap_{metric}.png"))
    print(f"\nSuite complete -> {args.out}")


if __name__ == "__main__":
    main()
