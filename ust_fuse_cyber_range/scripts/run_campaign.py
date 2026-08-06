"""Run a multi-mission paired campaign and export stats + figures.

    python scripts/run_campaign.py S04_sensor_dropout -n 20 --out out/camp_s04
"""
import argparse
import os
import sys

import matplotlib
matplotlib.use("Agg")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from ust_fuse.campaign import Campaign
from ust_fuse.viz import figure_pack
from ust_fuse.viz.plots import plot_paired_forest, plot_campaign_box
from ust_fuse.report import write_report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenario")
    ap.add_argument("-n", type=int, default=20)
    ap.add_argument("--seed", type=int, default=20260101)
    ap.add_argument("--domain-randomize", action="store_true")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    out = args.out or os.path.join("out", f"campaign_{args.scenario}")
    os.makedirs(out, exist_ok=True)

    camp = Campaign(args.scenario, n_missions=args.n, base_seed=args.seed,
                    domain_randomize=args.domain_randomize).run(verbose=True)

    camp.per_mission.to_csv(os.path.join(out, "per_mission.csv"), index=False)
    camp.paired_table().to_csv(os.path.join(out, "paired_stats.csv"), index=False)

    res0 = camp.results[0]
    figs = figure_pack(res0, out)
    plot_paired_forest(camp, save=os.path.join(out, "campaign_forest.png"))
    for metric in ["mota", "rmse_pos", "track_completeness", "ece"]:
        plot_campaign_box(camp, metric, save=os.path.join(out, f"box_{metric}.png"))
    write_report(res0, out, figures=figs, campaign=camp, basename="campaign_report")

    print("\nPaired stats (Reference vs UST-Fuse):")
    print(camp.paired_table()[["metric", "mean_diff", "ci_low", "ci_high",
                               "cohens_d", "better"]].round(3).to_string(index=False))
    print(f"\nCampaign complete -> {out}")


if __name__ == "__main__":
    main()
