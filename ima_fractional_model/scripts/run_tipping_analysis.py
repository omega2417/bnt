#!/usr/bin/env python3
"""Reconfiguration tipping point, priority-conflict sensitivity, and mean-field
bistability -> Figures 7 and 8."""
import numpy as np
import pandas as pd

from _common import graph_config, RESULTS_DIR, FIG_DIR, print_header
from src import load_graph
from src.scenarios import (tipping_sweep, priority_sweep, mean_field_trajectory,
                           mean_field_fixed_points, MEANFIELD)
from src.visualization import figure7_phase_portrait, figure8_tipping


def _tipping_point(rows):
    """Smallest xi beyond which no catastrophe occurs."""
    cat_xi = [r["xi"] for r in rows if r["catastrophe"]]
    return max(cat_xi) if cat_xi else rows[0]["xi"]


def main(fast: bool = False):
    print_header("Reconfiguration tipping & priority sensitivity (Figures 7-8)")
    graph = load_graph(graph_config())

    # ---- Figure 8a: tipping point over reconfiguration capacity xi ----
    xi_values = np.linspace(0.35, 0.75, 6 if fast else 11)
    tip = tipping_sweep(graph, xi_values, T=300.0 if fast else 400.0)
    pd.DataFrame(tip).to_csv(RESULTS_DIR / "tables" / "tipping_sweep.csv", index=False)
    xi_star = _tipping_point(tip)
    print(f"  reconfiguration tipping xi* ~= {xi_star:.3f}")

    # ---- Figure 8b: priority-conflict scale ----
    theta_scales = np.linspace(0.4, 2.0, 5 if fast else 9)
    pri = priority_sweep(graph, theta_scales, T=300.0 if fast else 400.0)
    pd.DataFrame(pri).to_csv(RESULTS_DIR / "tables" / "priority_sweep.csv", index=False)

    figure8_tipping(tip, pri, xi_star, FIG_DIR)
    print("  Figure 8 -> figures/figure_8.*")

    # ---- Figure 7: mean-field bistability phase portrait ----
    P = dict(MEANFIELD)
    P["xi"] = 0.50
    trajectories = []
    for x0 in np.linspace(0.0, 1.0, 7):
        for q0 in np.linspace(0.2, 2.0, 7):
            _, X, Q = mean_field_trajectory(x0, q0, T=120.0, P=P)
            kind = "CAT" if X[-1] > 0.5 else "NOM"
            trajectories.append((X, Q, kind))
    fps = mean_field_fixed_points(P)
    # add the catastrophic boundary attractor observed by integration
    _, Xc, Qc = mean_field_trajectory(0.9, 1.8, T=200.0, P=P)
    fp_list = [(f[0], f[1], "stable") for f in fps if f[0] < 0.3]
    fp_list.append((float(Xc[-1]), float(Qc[-1]), "stable"))
    figure7_phase_portrait(trajectories, fp_list, FIG_DIR)
    print(f"  mean-field attractors: {fp_list}")
    print("  Figure 7 -> figures/figure_7.*")
    return tip, pri, xi_star


if __name__ == "__main__":
    main()
