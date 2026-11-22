"""Benchmark tasks T1-T3 on EBAW-SOC-Synth and Figures 7-8.

Outputs: results/dataset_benchmark.json, results/dataset_policies_test.csv,
results/dataset_J_by_scenario_test.csv, results/dataset_thresholds.csv,
figures/fig7_dataset.png, figures/fig8_calibration.png
"""
import json
import os
import sys

import matplotlib.pyplot as plt
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from ebaw import benchmark as B, dataset  # noqa: E402
from ebaw.model import BASE, Calibrator  # noqa: E402
from figstyle import INK, MUTED, OI, RESDIR, save, setup  # noqa: E402

DS = os.path.join(ROOT, "data", f"ebaw-soc-synth-{dataset.DATASET_VERSION}")
COL = {"AD": OI["verm"], "CO": OI["orange"], "RO": OI["purple"], "GN": OI["sky"], "EB": OI["blue"], "ET": OI["green"]}


def main():
    D = dataset.load(DS)
    cal = B.task_calibration(D)
    th = B.task_thresholds(D, cal["_cal"])
    pol = B.task_policies(D, "test")
    pol_all = B.task_policies(D, "all")
    pol["table"].round(4).to_csv(os.path.join(RESDIR, "dataset_policies_test.csv"))
    pol["J_by_scenario"].round(4).to_csv(os.path.join(RESDIR, "dataset_J_by_scenario_test.csv"))
    th.round(4).to_csv(os.path.join(RESDIR, "dataset_thresholds.csv"), index=False)
    out = dict(calibration={k: v for k, v in cal.items() if k not in ("map", "_cal")},
               calibration_map=cal["map"].round(4).to_dict(orient="records"),
               thresholds=th.round(4).to_dict(orient="records"),
               policies_test=pol["table"].round(4).to_dict(orient="index"),
               policies_all=pol_all["table"].round(4).to_dict(orient="index"),
               planning_test={k: (float(v) if v is not None else None) for k, v in pol["planning"].items()},
               planning_all={k: (float(v) if v is not None else None) for k, v in pol_all["planning"].items()})
    json.dump(out, open(os.path.join(RESDIR, "dataset_benchmark.json"), "w"), indent=1)

    setup()
    # ---- Figure 7: composition and policy comparison on the test split
    P = D["proposals"]
    fig, ax = plt.subplots(1, 2, figsize=(14.5, 5.4), gridspec_kw=dict(width_ratios=[1.05, 1]))
    sc = sorted(P.scenario_id.unique())
    kinds = [("genuine", OI["blue"]), ("hallucinated", OI["orange"]), ("injected", OI["verm"]),
             ("tampered", OI["purple"])]
    left = np.zeros(len(sc))
    for k, c in kinds:
        v = np.array([((P.scenario_id == s) & (P.kind == k)).sum() for s in sc])
        ax[0].barh(sc, v, left=left, color=c, edgecolor="white", linewidth=1.5, label=k, height=0.72)
        left += v
    for i, s in enumerate(sc):
        ax[0].text(left[i] + 15, i, f"{int(left[i])}", va="center", fontsize=12.5, color=INK)
    ax[0].invert_yaxis()
    ax[0].set_xlabel("Proposals")
    ax[0].set_xlim(0, left.max() * 1.15)
    ax[0].set_title("(a) EBAW-SOC-Synth: proposals by scenario")
    ax[0].legend(loc="center right", bbox_to_anchor=(1.0, 0.6), fontsize=12)
    t = pol["table"]
    y = np.arange(len(B.ORDER))
    for i, p in enumerate(B.ORDER):
        r = t.loc[p]
        ax[1].plot([r.UER_lo, r.UER_hi], [i, i], color=COL[p], lw=3)
        ax[1].plot(r.UER, i, "o", color=COL[p], ms=10, mec="white", mew=2)
        ax[1].text(r.UER_hi * 1.25, i, f"{r.UER:.1f}   adv. {int(r.adv_exec)}/{int(r.n_adv)}", va="center",
                   fontsize=12.5, color=INK)
    ax[1].set_xscale("log")
    ax[1].set_yticks(y, B.ORDER)
    ax[1].invert_yaxis()
    ax[1].set_xlim(5, 4000)
    ax[1].set_xlabel("Unsafe executions per 1000 proposals (95% Wilson CI, log scale)")
    ax[1].set_title("(b) Admission policies on the test split")
    fig.tight_layout()
    save(fig, "fig7_dataset")
    plt.close(fig)

    # ---- Figure 8: reliability of the conservative calibration map
    s_te, y_te, _ = B.labeled_scores(D, "test")
    fig, ax = plt.subplots(figsize=(7.2, 6.2))
    ax.plot([0, 1], [0, 1], color=MUTED, lw=1.4, ls="--", label="perfect calibration")
    edges = np.linspace(0, 1, 11)
    for name, g, c in (("fitted on train split", cal["_cal"], OI["blue"]),
                       ("article (40 000 samples)", Calibrator(BASE, 42), OI["orange"])):
        conf = g(s_te)
        idx = np.clip(np.digitize(conf, edges) - 1, 0, 9)
        xs = [conf[idx == b].mean() for b in range(10) if (idx == b).sum() >= 20]
        ys = [y_te[idx == b].mean() for b in range(10) if (idx == b).sum() >= 20]
        ax.plot(xs, ys, "o-", color=c, ms=8, mec="white", mew=1.5, label=name)
    ax.set_xlabel("Conservative confidence g(s)")
    ax.set_ylabel("Observed share malicious (test split)")
    ax.set_xlim(0, 1.02)
    ax.set_ylim(0, 1.02)
    ax.legend(loc="lower right", fontsize=12)
    ax.set_title("Reliability on held-out episodes")
    fig.tight_layout()
    save(fig, "fig8_calibration")
    plt.close(fig)
    print(json.dumps({k: out[k] for k in ("calibration", "planning_test", "planning_all")}, indent=1))
    print(pol["table"].round(2).to_string())


if __name__ == "__main__":
    main()
