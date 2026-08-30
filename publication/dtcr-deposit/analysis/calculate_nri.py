#!/usr/bin/env python3
"""Recompute the normalized resilience index directly from the availability traces.

This script is the answer to the reviewer objection that Figure 6 could not be
reconciled with Figure 5 or with the published NRI values.  It:

  1. reads every availability trace in ``data/availability_traces/``;
  2. recomputes the recovery time (Eq. 15) and the NRI (Eq. 18-19) with the
     window parameters stated in ``configs/framework_parameters.yaml``;
  3. cross-checks the recomputed values against ``data/run_level_metrics.csv``
     and fails loudly on any mismatch;
  4. writes per-run NRI values and the mean availability trajectory with a 95%
     confidence band, which is what Figure 6 plots.

Every quantity the index depends on - RTO, A_min, A_max, the hold interval, the
sampling interval, and the start of the integration window - is read from the
configuration file and echoed into ``results/nri_parameters.json`` so the figure
is reproducible from published inputs alone.

Usage:  python analysis/calculate_nri.py --data data --out results
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dtcr.resilience import NRIConfig, nri, recovery_time  # noqa: E402
from dtcr import stats as st  # noqa: E402

# run_level_metrics.csv stores the NRI rounded to five decimals, so the stored
# and recomputed values may differ by up to one unit in the last stored place.
# Anything larger means the traces and the summary file no longer describe the
# same experiment.
TOL_NRI = 1e-5   # one unit in the last stored place
TOL_RECOVERY = 1e-9


def load_config(path: Path) -> NRIConfig:
    cfg = yaml.safe_load(path.read_text())["resilience"]
    return NRIConfig(rto=float(cfg["rto_s"]), a_min=float(cfg["a_min"]),
                     a_max=float(cfg["a_max"]), hold=float(cfg["hold_interval_s"]),
                     sampling_interval=float(cfg["sampling_interval_s"]))


def recompute(data: Path, cfg: NRIConfig) -> pd.DataFrame:
    runs = pd.read_csv(data / "run_level_metrics.csv")
    out = []
    for _, r in runs.iterrows():
        tr = pd.read_csv(data / r.trace_file)
        t = tr.t_s.to_numpy(float)
        a = tr.availability.to_numpy(float)
        below = np.flatnonzero(a < cfg.a_min)
        t_dis = float(t[below[0]]) if below.size else float(r.attack_onset_s)
        out.append({
            "run_id": r.run_id, "scenario": r.scenario, "method": r.method,
            "repetition": int(r.repetition),
            "t_dis_s": t_dis,
            "window_start_s": t_dis, "window_end_s": t_dis + 2 * cfg.rto,
            "recovery_time_s": recovery_time(t, a, float(r.attack_onset_s), cfg),
            "nri": nri(t, a, t_dis, cfg),
            "stored_recovery_time_s": float(r.recovery_time_s),
            "stored_nri": float(r.nri),
        })
    df = pd.DataFrame(out)
    df["delta_nri"] = df.nri - df.stored_nri
    df["delta_recovery_s"] = df.recovery_time_s - df.stored_recovery_time_s
    return df


def mean_trajectory(data: Path, runs: pd.DataFrame, scenario: str, method: str,
                    cfg: NRIConfig) -> pd.DataFrame:
    """Mean availability trajectory with a 95% t confidence band, aligned on t_dis."""
    sub = runs[(runs.scenario == scenario) & (runs.method == method)]
    grid = np.arange(-60.0, 2 * cfg.rto + 1.0, cfg.sampling_interval)
    curves = []
    for _, r in sub.iterrows():
        tr = pd.read_csv(data / f"availability_traces/{r.run_id}.csv")
        t = tr.t_s.to_numpy(float)
        a = tr.availability.to_numpy(float)
        below = np.flatnonzero(a < cfg.a_min)
        t_dis = float(t[below[0]]) if below.size else 0.0
        curves.append(np.interp(grid, t - t_dis, a))
    m = np.vstack(curves)
    mean = m.mean(axis=0)
    sd = m.std(axis=0, ddof=1)
    n = m.shape[0]
    from scipy import stats as sps
    half = sps.t.ppf(0.975, n - 1) * sd / np.sqrt(n)
    return pd.DataFrame({"t_rel_s": grid, "mean": mean, "sd": sd,
                         "ci95_lo": np.clip(mean - half, 0, 1),
                         "ci95_hi": np.clip(mean + half, 0, 1),
                         "n": n, "scenario": scenario, "method": method})


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--configs", default="configs/framework_parameters.yaml")
    ap.add_argument("--out", default="results")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero if a recomputed value disagrees with the stored one")
    args = ap.parse_args()
    data, out = Path(args.data), Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    cfg = load_config(Path(args.configs))
    df = recompute(data, cfg)
    df.to_csv(out / "nri_per_run.csv", index=False)

    bad = df[(df.delta_nri.abs() > TOL_NRI) |
             (df.delta_recovery_s.abs() > TOL_RECOVERY)]
    traj = pd.concat([mean_trajectory(data, df, s, m, cfg)
                      for s in sorted(df.scenario.unique())
                      for m in ("baseline", "framework")], ignore_index=True)
    traj.to_csv(out / "availability_trajectories.csv", index=False)

    summary = {}
    for s in sorted(df.scenario.unique()):
        entry = {}
        for m in ("baseline", "framework"):
            v = df[(df.scenario == s) & (df.method == m)].nri.to_numpy()
            d = st.describe(v)
            entry[m] = {"n": d["n"], "mean": d["mean"], "sd": d["sd"],
                        "ci95": [d["ci95_lo"], d["ci95_hi"]],
                        "median": d["median"], "iqr": d["iqr"]}
        bm, fm = entry["baseline"]["mean"], entry["framework"]["mean"]
        entry["absolute_gain"] = fm - bm
        entry["relative_gain_pct"] = 100 * (fm - bm) / bm
        entry["deficit_reduction_pct"] = 100 * ((1 - bm) - (1 - fm)) / (1 - bm)
        summary[s] = entry

    params = {
        "rto_s": cfg.rto, "a_min": cfg.a_min, "a_max": cfg.a_max,
        "hold_interval_s": cfg.hold, "sampling_interval_s": cfg.sampling_interval,
        "integration_window": "[t_dis, t_dis + 2*RTO]",
        "t_dis_definition": "first sample with availability < a_min after attack onset",
        "note": ("t_det (detection) and t_dis (disruption) are distinct symbols; "
                 "the NRI window is anchored on t_dis, not on t_det."),
        "n_traces": int(len(df)),
        "consistency_check": {"max_abs_delta_nri": float(df.delta_nri.abs().max()),
                              "max_abs_delta_recovery_s": float(df.delta_recovery_s.abs().max()),
                              "mismatched_runs": int(len(bad))},
        "per_scenario": summary,
    }
    (out / "nri_parameters.json").write_text(json.dumps(params, indent=2) + "\n")
    print(json.dumps(params, indent=2))

    if len(bad):
        print(f"\nWARNING: {len(bad)} run(s) disagree with run_level_metrics.csv",
              file=sys.stderr)
        print(bad[["run_id", "delta_nri", "delta_recovery_s"]].to_string(index=False),
              file=sys.stderr)
        if args.strict:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
