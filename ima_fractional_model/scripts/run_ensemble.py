#!/usr/bin/env python3
"""Ensemble uncertainty & sensitivity analysis for S1-S3 -> Figure 9, Table 2,
and the PRCC table (manuscript Sec. 6.5)."""
import json

import numpy as np
import pandas as pd

from _common import graph_config, RESULTS_DIR, FIG_DIR, print_header, GLOBAL_SEED
from src import load_graph
from src.sensitivity import run_ensemble, summarize_ensemble, ensemble_prcc, PRCC_INPUTS
from src.visualization import figure9_ensemble

SCENARIOS = [("S1", 0.93, 0.55), ("S2", 1.60, 0.75), ("S3", 1.60, 0.38)]


def main(N: int = 100, fast: bool = False):
    if fast:
        N = 20
    print_header(f"Ensemble analysis (N={N} per scenario, LHS)")
    graph = load_graph(graph_config())
    horizon = 400.0

    summary = {}
    all_rows = {}
    for name, ks, xi in SCENARIOS:
        print(f"  running ensemble {name} ...")
        runs = run_ensemble(graph, name=name, kappa_scale=ks, xi=xi, N=N,
                            T=horizon, seed=GLOBAL_SEED)
        all_rows[name] = runs
        pd.DataFrame(runs).to_csv(
            RESULTS_DIR / "ensemble" / f"ensemble_{name}.csv", index=False)
        s = summarize_ensemble(runs, horizon)
        summary[name] = s
        print(f"    P_cat={s['p_cat']:.2f} "
              f"[{s['wilson_low']:.3f}, {s['wilson_high']:.3f}]  "
              f"KM median T_cat={s['km_median']}")

    # ---- Table 2 ----
    table2 = []
    for name in [s[0] for s in SCENARIOS]:
        s = summary[name]
        lo, hi = s["km_median_ci"]
        q1, q3 = s["iqr_tcat"]
        table2.append(dict(
            scenario=name,
            catastrophic_runs=f"{s['n_cat']}/{s['N']}",
            P_cat=round(s["p_cat"], 3),
            P_cat_CI=f"[{s['wilson_low']:.3f}, {s['wilson_high']:.3f}]",
            median_Tcat=("Not reached" if s["km_median"] is None
                         else round(s["km_median"], 1)),
            median_Tcat_CI=("n/a" if lo is None or s["km_median"] is None
                            else f"[{lo}, {hi}]"),
            IQR_Tcat=("n/a" if not np.isfinite(q1) else f"[{q1:.1f}, {q3:.1f}]"),
            median_terminal_cascade=f"{s['median_terminal_cascade']*100:.1f}%"))
    pd.DataFrame(table2).to_csv(RESULTS_DIR / "tables" / "table2_ensemble.csv",
                                index=False)

    # ---- PRCC on the pooled catastrophe-prone scenario (S3) ----
    prcc_res = ensemble_prcc(all_rows["S3"], PRCC_INPUTS, horizon)
    prcc_rows = [dict(parameter=k, **v) for k, v in prcc_res.items()]
    pd.DataFrame(prcc_rows).to_csv(RESULTS_DIR / "tables" / "prcc_S3.csv", index=False)
    print("  PRCC (S3, T_cat):")
    for k, v in prcc_res.items():
        print(f"    {k:16s} PRCC={v['prcc']:+.2f} "
              f"[{v['ci_low']:+.2f}, {v['ci_high']:+.2f}]")

    # ---- Figure 9 ----
    fig_summary = {name: dict(p_cat=summary[name]["p_cat"],
                              wilson_low=summary[name]["wilson_low"],
                              wilson_high=summary[name]["wilson_high"],
                              km_median=summary[name]["km_median"])
                   for name in [s[0] for s in SCENARIOS]}
    figure9_ensemble(fig_summary, FIG_DIR)
    with open(RESULTS_DIR / "ensemble" / "ensemble_summary.json", "w") as fh:
        json.dump(summary, fh, indent=2, default=str)
    print("  Figure 9 -> figures/figure_9.*   Table 2 -> results/tables/table2_ensemble.csv")
    return summary


if __name__ == "__main__":
    main()
