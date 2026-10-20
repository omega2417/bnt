#!/usr/bin/env python3
"""Figure 2: (a) heatmap of normalized group scores, (b) aggregate scores
with equal weights annotated with the Dirichlet rank-1 share.

Reads results/platform_ranking.json (run platform_ranking.py first) and
writes figures/figure2.pdf and figures/figure2.png.
"""
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GROUPS = ["G1", "G2", "G3", "G4", "G5"]
LABELS = ["G1 Execution", "G2 Expressiveness", "G3 Interoperability",
          "G4 Tooling", "G5 Effort"]


def main():
    with open(os.path.join(ROOT, "results", "platform_ranking.json")) as f:
        r = json.load(f)
    platforms = r["ranking_equal_weights"]
    G = np.array([[r["group_scores"][p][g] for g in GROUPS] for p in platforms])
    S = np.array([r["aggregate_equal_weights"][p] for p in platforms])
    share = r["share_rank1"]

    plt.rcParams.update({"font.size": 9, "font.family": "serif"})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.4),
                                   gridspec_kw={"width_ratios": [1.25, 1]})

    ax1.imshow(G, cmap="Blues", vmin=0, vmax=1.1, aspect="auto")
    for i in range(G.shape[0]):
        for j in range(G.shape[1]):
            v = G[i, j]
            ax1.text(j, i, f"{v:.2f}", ha="center", va="center",
                     color="white" if v > 0.55 else "#333333", fontsize=8)
    ax1.set_xticks(range(len(GROUPS)), LABELS, rotation=25, ha="right")
    ax1.set_yticks(range(len(platforms)), platforms)
    ax1.set_xticks(np.arange(-.5, len(GROUPS)), minor=True)
    ax1.set_yticks(np.arange(-.5, len(platforms)), minor=True)
    ax1.grid(which="minor", color="white", linewidth=2)
    ax1.tick_params(which="minor", length=0)
    for s in ax1.spines.values():
        s.set_visible(False)
    ax1.set_title(r"(a) Normalized group scores $\hat{s}_{p,g}$")

    y = np.arange(len(platforms))
    ax2.barh(y, S, color="#2f6fd6", height=0.6)
    for i, p in enumerate(platforms):
        lab = f"{S[i]:.3f}"
        if share[p] > 0:
            lab += f"  (rank 1: {100 * share[p]:.1f}%)"
        ax2.text(S[i] + 0.01, i, lab, va="center", fontsize=8)
    ax2.set_yticks(y, platforms)
    ax2.invert_yaxis()
    ax2.set_xlim(0, 1.45)
    ax2.set_xticks([0, .25, .5, .75, 1.0])
    ax2.set_xlabel(r"Aggregate score $S_p$ (equal weights)")
    ax2.spines[["top", "right"]].set_visible(False)
    ax2.set_title("(b) Aggregate score and rank stability")

    fig.tight_layout()
    out = os.path.join(ROOT, "figures")
    os.makedirs(out, exist_ok=True)
    fig.savefig(os.path.join(out, "figure2.pdf"))
    fig.savefig(os.path.join(out, "figure2.png"), dpi=200)
    print("wrote figures/figure2.pdf, figures/figure2.png")


if __name__ == "__main__":
    main()
