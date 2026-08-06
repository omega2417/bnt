"""Minimal end-to-end example.

    python examples/quickstart.py

Runs one mission, prints the metric table, and writes a field-trial report to
``out/quickstart/``.
"""
import os
import sys

import matplotlib
matplotlib.use("Agg")

# allow running from the repo without installing
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd

import ust_fuse as uf
from ust_fuse.viz import figure_pack
from ust_fuse.report import write_report


def main():
    scenario = "S04_sensor_dropout"
    print(f"Running scenario {scenario} ...")
    res = uf.run(scenario, seed=7)

    print("\nMetric summary (Reference vs Full UST-Fuse):")
    df = pd.DataFrame(res.summary_table())
    cols = ["mode", "rmse_pos", "ospa_mean", "mota", "id_switches",
            "track_completeness", "ece"]
    print(df[[c for c in cols if c in df.columns]].to_string(index=False))

    out = os.path.join("out", "quickstart")
    figs = figure_pack(res, out)
    paths = write_report(res, out, figures=figs)
    print(f"\nManifest: {res.manifest.experiment_id}  (seed {res.config.seed})")
    print(f"Figures : {out}")
    print(f"Report  : {paths['html']}")


if __name__ == "__main__":
    main()
