#!/usr/bin/env python3
"""Run scenario S3 and save its outputs (CSV/NPZ/JSON)."""
from _common import (graph_config, save_scenario_outputs, RESULTS_DIR,
                     CONFIG_DIR, print_header)
from src import load_graph
from src.scenarios import scenario_from_config, load_scenario_config


def main():
    print_header("Scenario S3")
    graph = load_graph(graph_config())
    cfg = load_scenario_config(CONFIG_DIR / "scenario_S3.yaml")
    result = scenario_from_config(graph, cfg)
    meta = save_scenario_outputs(result, RESULTS_DIR / "scenarios", "S3")
    print(f"  Rc                    = {result.Rc:.3f}")
    print(f"  catastrophe           = {result.catastrophe}")
    print(f"  time-to-catastrophe   = {result.T_cat}")
    print(f"  terminal cascade size = {result.terminal_cascade_size*100:.1f}%")
    print(f"  peak backlog          = {result.peak_backlog:.3f}")
    print(f"  max DAL-A degradation = {result.max_dalA:.3f}")
    print(f"  outputs -> results/scenarios/S3_*.{{csv,npz,json}}")
    return result


if __name__ == "__main__":
    main()
