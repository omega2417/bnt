"""Shared helpers for the reproduction scripts: path setup, seeds, I/O."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

# Make the package importable whether run as `python scripts/run_s1.py`
# or from an installed environment.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Master random seed for full reproducibility.
GLOBAL_SEED = 12345

CONFIG_DIR = ROOT / "config"
RESULTS_DIR = ROOT / "results"
FIG_DIR = ROOT / "figures"
DATA_DIR = ROOT / "data"

for _d in (RESULTS_DIR / "scenarios", RESULTS_DIR / "tables",
           RESULTS_DIR / "ensemble", FIG_DIR, DATA_DIR / "generated"):
    _d.mkdir(parents=True, exist_ok=True)


def graph_config():
    return CONFIG_DIR / "ima_22node.yaml"


def save_scenario_outputs(result, outdir: Path, tag: str):
    """Persist a scenario run to CSV + NPZ + JSON (manuscript Sec. 22)."""
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    sim = result.sim

    # --- CSV: per-timestep global quantities ---
    import pandas as pd
    df = pd.DataFrame({
        "t": sim.t,
        "weighted_x": sim.weighted_x,
        "weighted_q": sim.weighted_q,
        "reconfig_failure_prob": sim.pi_fail,
        "max_degradation": sim.X.max(axis=1),
        "max_backlog": sim.Q.max(axis=1),
    })
    df.to_csv(outdir / f"{tag}_timeseries.csv", index=False)

    # --- NPZ: full state trajectories ---
    np.savez_compressed(
        outdir / f"{tag}_states.npz",
        t=sim.t, X=sim.X, Q=sim.Q, pi_fail=sim.pi_fail,
        weighted_x=sim.weighted_x, weighted_q=sim.weighted_q,
        alpha=sim.alpha, beta=sim.beta)

    # --- JSON: metadata & scalar outcomes ---
    meta = dict(
        name=result.name, Rc=result.Rc, catastrophe=bool(result.catastrophe),
        T_cat=result.T_cat, terminal_cascade_size=result.terminal_cascade_size,
        n_degraded=result.n_degraded, peak_backlog=result.peak_backlog,
        max_dalA=result.max_dalA, relaxation_time=result.relaxation_time,
        nan_flag=bool(sim.nan_flag), params=result.params)
    with open(outdir / f"{tag}_metadata.json", "w") as fh:
        json.dump(meta, fh, indent=2, default=float)
    return meta


def print_header(title: str):
    print("=" * 72)
    print(title)
    print("=" * 72)
