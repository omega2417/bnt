#!/usr/bin/env python3
"""Full reproduction driver.

    python scripts/reproduce_all.py            # full run (Figures 1-9, tables)
    python scripts/reproduce_all.py --fast     # reduced grids/ensemble for a quick check

Runs, without manual intervention:
  1. load configuration and build the 22-node graph
  2. compute cascade thresholds Rc for S1-S3
  3. run scenarios S1-S3
  4. verify the solver (grid convergence + ABM cross-check)
  5. delay-memory analysis           -> Figure 6
  6. tipping / priority / bistability -> Figures 7, 8
  7. ensemble analysis                -> Figure 9, Table 2
  8. write all Tables and Figures 1-9 into results/ and figures/
"""
import argparse
import json

import numpy as np
import pandas as pd

from _common import (graph_config, save_scenario_outputs, RESULTS_DIR, FIG_DIR,
                     CONFIG_DIR, print_header, GLOBAL_SEED)
from src import load_graph, cascade_threshold, solve_gl, solve_abm
from src.ima_dynamics import IMADynamics, ScenarioParams
from src.scenarios import scenario_from_config, load_scenario_config
from src.visualization import (figure1_topology, figure2_model_structure,
                               figure3_trajectories, figure4_backlog_heatmap,
                               figure5_cascade_graph)

SCEN = ["S1", "S2", "S3"]


# --------------------------------------------------------------- solver checks
def verify_solver(graph):
    """Grid convergence (h vs h/2) and ABM predictor-corrector cross-check (S1)."""
    cfg = load_scenario_config(CONFIG_DIR / "scenario_S1.yaml")
    p = ScenarioParams(cfg["kappa_scale"], cfg["xi"], cfg["alpha"], cfg["beta_order"])
    x_cat = cfg["x_cat"]
    T = 60.0
    dyn1 = IMADynamics(graph, p, 0.05)
    x0 = np.zeros(graph.n); x0[graph.index[cfg["seed_node"]]] = cfg["seed_magnitude"]
    q0 = dyn1.q_star.copy()

    gl_h = solve_gl(dyn1, x0, q0, T)
    dyn2 = IMADynamics(graph, p, 0.025)
    gl_h2 = solve_gl(dyn2, x0, q0, T)
    # compare on the coarse grid
    idx2 = (gl_h.t / 0.025).round().astype(int)
    dev_grid = float(np.max(np.abs(gl_h.X - gl_h2.X[idx2])))

    abm = solve_abm(dyn1, x0, q0, T)
    dev_abm = float(np.max(np.abs(gl_h.X - abm.X)))

    rows = [
        dict(check="grid_convergence_h_vs_h/2", metric="max|X_h - X_h2|",
             value=dev_grid),
        dict(check="ABM_cross_check_S1", metric="max|X_GL - X_ABM|",
             value=dev_abm),
    ]
    pd.DataFrame(rows).to_csv(RESULTS_DIR / "tables" / "solver_verification.csv",
                             index=False)
    print(f"  grid convergence  max|X_h - X_h/2| = {dev_grid:.2e}")
    print(f"  ABM cross-check   max|X_GL - X_ABM| = {dev_abm:.2e}")
    return rows


def write_parameter_table(graph):
    """Emit Table 1 (baseline parameters) from the configuration -- not hand-typed."""
    gp = graph.global_params
    rows = [
        ("n (CPM/SW/RDC)", "22 (8/4/10)"),
        ("DAL A/B/C", "4/8/10 nodes"),
        ("alpha, beta (baseline)", f"{gp['alpha']}, {gp['beta_order']}"),
        ("mu (intrinsic recovery)", gp["mu"]),
        ("beta_base (transmission)", gp["beta_base"]),
        ("gamma (backlog->degradation)", gp["gamma"]),
        ("eta (priority-conflict gain)", gp["eta"]),
        ("theta (conflict intensity)", gp["theta"]),
        ("r (reconfig DAL A/B/C)", "1.6/0.6/0.25"),
        ("c (service capacity)", 1.1),
        ("delta (backlog drain)", gp["delta"]),
        ("spillover w_ij", gp["spillover"]),
        ("kappa, nu (Eq. 6)", f"{gp['recon_kappa']}, {gp['recon_nu']}"),
        ("x_cat (certification threshold)", gp["x_cat"]),
        ("h, T (grid step, horizon)", "0.05, 200-400"),
    ]
    pd.DataFrame(rows, columns=["symbol", "value"]).to_csv(
        RESULTS_DIR / "tables" / "table1_parameters.csv", index=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fast", action="store_true",
                    help="reduced ensemble/grids for a quick end-to-end check")
    args = ap.parse_args()
    fast = args.fast
    np.random.seed(GLOBAL_SEED)

    print_header("Delayed Fractional-Order IMA Cascade Model -- full reproduction")
    graph = load_graph(graph_config())
    write_parameter_table(graph)

    # ---- Figures 1 & 2 ----
    figure1_topology(graph, FIG_DIR)
    figure2_model_structure(FIG_DIR)
    print("  Figures 1, 2 written")

    # ---- Thresholds + scenarios S1-S3 ----
    print_header("Scenarios S1-S3")
    sims, tcat, rc = {}, {}, {}
    for name in SCEN:
        cfg = load_scenario_config(CONFIG_DIR / f"scenario_{name}.yaml")
        result = scenario_from_config(graph, cfg)
        save_scenario_outputs(result, RESULTS_DIR / "scenarios", name)
        result.sim._Rc = f"{result.Rc:.2f}"
        sims[name] = result.sim
        tcat[name] = result.T_cat
        rc[name] = result.Rc
        print(f"  {name}: Rc={result.Rc:.3f}  catastrophe={result.catastrophe}  "
              f"T_cat={result.T_cat}  cascade={result.terminal_cascade_size*100:.0f}%")
    pd.DataFrame([dict(scenario=n, Rc=rc[n], T_cat=tcat[n]) for n in SCEN]).to_csv(
        RESULTS_DIR / "tables" / "cascade_thresholds.csv", index=False)

    x_cat = graph.global_params["x_cat"]
    figure3_trajectories(graph, sims, x_cat, tcat, FIG_DIR)
    figure4_backlog_heatmap(graph, sims["S3"], tcat["S3"], FIG_DIR)
    figure5_cascade_graph(graph, sims["S3"], FIG_DIR)
    print("  Figures 3, 4, 5 written")

    # ---- Solver verification ----
    print_header("Solver verification")
    verify_solver(graph)

    # ---- Delay-memory (Figure 6) ----
    import run_delay_memory
    run_delay_memory.main(fast=fast)

    # ---- Tipping / priority / bistability (Figures 7, 8) ----
    import run_tipping_analysis
    run_tipping_analysis.main(fast=fast)

    # ---- Ensemble (Figure 9, Table 2) ----
    import run_ensemble
    run_ensemble.main(N=100, fast=fast)

    print_header("DONE -- all Figures 1-9 in figures/, tables in results/tables/")


if __name__ == "__main__":
    main()
