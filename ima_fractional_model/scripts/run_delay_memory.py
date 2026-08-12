#!/usr/bin/env python3
"""Delay-memory experiment: critical delay tau*(alpha) (Theorem 4) and the
terminal-cascade map on the (alpha, tau) grid -> Figure 6."""
import numpy as np
import pandas as pd

from _common import graph_config, RESULTS_DIR, FIG_DIR, print_header
from src import load_graph, critical_delay_scalar
from src.scenarios import delay_memory_grid
from src.visualization import figure6_delay_memory


def main(fast: bool = False):
    print_header("Delay-memory experiment (Figure 6)")
    graph = load_graph(graph_config())

    # (a) scalar critical delay tau*(alpha) -- Theorem 4
    alphas = [0.6, 0.7, 0.8, 0.9, 1.0]
    tau_star = [critical_delay_scalar(a)[0] for a in alphas]
    pd.DataFrame({"alpha": alphas, "tau_star": tau_star}).to_csv(
        RESULTS_DIR / "tables" / "critical_delay.csv", index=False)
    for a, t in zip(alphas, tau_star):
        print(f"  tau*({a}) = {t:.3f}")

    # (b) network delay-memory grid (terminal cascade size)
    grid_alphas = [0.6, 0.7, 0.8, 0.9, 1.0]
    grid_taus = np.linspace(0.5, 2.5, 5 if fast else 6)
    print("  computing (alpha, tau) cascade map ...")
    grid = delay_memory_grid(graph, grid_alphas, grid_taus, xi=0.64,
                             T=250.0 if fast else 400.0)
    np.savez(RESULTS_DIR / "tables" / "delay_memory_grid.npz",
             alphas=grid_alphas, taus=grid_taus, grid=grid)

    figure6_delay_memory(alphas, tau_star, grid_alphas, grid_taus, grid, FIG_DIR)
    print(f"  Figure 6 -> figures/figure_6.*")
    return alphas, tau_star, grid_alphas, grid_taus, grid


if __name__ == "__main__":
    main()
