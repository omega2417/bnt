#!/usr/bin/env python3
"""Platform comparison of Section 2.2 / Section 3.1 (Figure 2).

Reads data/platform_scores.csv (8 platforms x 20 criteria, scores 0/1/2),
computes the normalized group scores of Equation (1) and the aggregate
scores of Equation (2) with equal weights, samples 100,000 weight vectors
from the uniform Dirichlet distribution Dir(1,...,1) (seed 2026) to
measure rank stability, and runs a leave-one-group-out analysis.

Outputs:
  results/platform_group_scores.csv
  results/platform_ranking.json
"""
import csv
import json
import os
import sys

import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data", "platform_scores.csv")
RESULTS = os.path.join(ROOT, "results")

GROUPS = ["G1", "G2", "G3", "G4", "G5"]
GROUP_NAMES = {
    "G1": "Execution properties",
    "G2": "Expressiveness of the host",
    "G3": "Interoperability",
    "G4": "Tooling",
    "G5": "Implementation effort",
}
N_SAMPLES = 100_000
SEED = 2026


def load_scores(path=DATA):
    """Return (platforms in file order, dict (platform, group) -> list of scores)."""
    platforms, cells = [], {}
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            p, g, s = row["platform"], row["group"], int(row["score"])
            if s not in (0, 1, 2):
                sys.exit(f"invalid score {s} for {p}/{row['criterion']}")
            if p not in platforms:
                platforms.append(p)
            cells.setdefault((p, g), []).append(s)
    return platforms, cells


def group_scores(platforms, cells):
    """Equation (1): s_hat[p,g] = 1/(2 n_g) * sum_{c in C_g} s[p,c]."""
    m = np.zeros((len(platforms), len(GROUPS)))
    for i, p in enumerate(platforms):
        for j, g in enumerate(GROUPS):
            vals = cells[(p, g)]
            if len(vals) != 4:
                sys.exit(f"{p}/{g}: expected 4 criteria, got {len(vals)}")
            m[i, j] = sum(vals) / (2 * len(vals))
    return m


def ranking(scores):
    """Indices sorted by descending score. Scores are rounded to 9 decimals
    so that exact ties (e.g. 0.750 for .NET CIL and JavaScript source) are
    not broken by floating-point noise; ties keep the order of the data file."""
    return [int(i) for i in np.argsort(-np.round(scores, 9), kind="stable")]


def main():
    platforms, cells = load_scores()
    G = group_scores(platforms, cells)
    w_eq = np.full(len(GROUPS), 1 / len(GROUPS))
    S = G @ w_eq  # Equation (2)
    order = ranking(S)

    # Rank stability under Dir(1,...,1) weights.
    rng = np.random.default_rng(SEED)
    W = rng.dirichlet(np.ones(len(GROUPS)), size=N_SAMPLES)
    A = W @ G.T  # (samples, platforms)
    ranks = np.argsort(-A, axis=1, kind="stable")
    first = np.bincount(ranks[:, 0], minlength=len(platforms)) / N_SAMPLES
    top2 = (np.bincount(ranks[:, 0], minlength=len(platforms))
            + np.bincount(ranks[:, 1], minlength=len(platforms))) / N_SAMPLES

    # Leave-one-group-out with equal weights on the remaining groups.
    logo = {}
    for j, g in enumerate(GROUPS):
        keep = [k for k in range(len(GROUPS)) if k != j]
        s = G[:, keep].mean(axis=1)
        o = ranking(s)
        logo[g] = {
            "removed_group": GROUP_NAMES[g],
            "ranking": [platforms[i] for i in o],
            "scores": {platforms[i]: round(float(s[i]), 4) for i in o},
            "first": platforms[o[0]],
        }

    os.makedirs(RESULTS, exist_ok=True)
    with open(os.path.join(RESULTS, "platform_group_scores.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["platform"] + GROUPS + ["aggregate_equal_weights", "rank",
                                            "share_rank1", "share_top2"])
        for r, i in enumerate(order, 1):
            w.writerow([platforms[i]] + [f"{v:.3f}" for v in G[i]]
                       + [f"{S[i]:.3f}", r, f"{first[i]:.5f}", f"{top2[i]:.5f}"])

    out = {
        "method": {
            "equation_1": "s_hat[p,g] = sum_{c in C_g} s[p,c] / (2 n_g), n_g = 4",
            "equation_2": "S_p = sum_g w_g s_hat[p,g], sum w_g = 1, w_g >= 0",
            "dirichlet_alpha": [1.0] * len(GROUPS),
            "n_samples": N_SAMPLES,
            "seed": SEED,
            "rng": "numpy.random.default_rng(2026).dirichlet",
            "tie_breaking": "stable argsort in platform order of data/platform_scores.csv",
        },
        "groups": GROUP_NAMES,
        "group_scores": {platforms[i]: {g: float(G[i, j]) for j, g in enumerate(GROUPS)}
                         for i in range(len(platforms))},
        "aggregate_equal_weights": {platforms[i]: round(float(S[i]), 4) for i in order},
        "ranking_equal_weights": [platforms[i] for i in order],
        "share_rank1": {platforms[i]: float(first[i]) for i in order},
        "share_top2": {platforms[i]: float(top2[i]) for i in order},
        "leave_one_group_out": logo,
        "first_place_unchanged_in_logo": all(v["first"] == platforms[order[0]]
                                             for v in logo.values()),
    }
    with open(os.path.join(RESULTS, "platform_ranking.json"), "w") as f:
        json.dump(out, f, indent=2)

    print("platform               G1    G2    G3    G4    G5    S     rank1   top2")
    for i in order:
        print(f"{platforms[i]:20s} " + " ".join(f"{v:5.3f}" for v in G[i])
              + f" {S[i]:5.3f} {100*first[i]:6.2f}% {100*top2[i]:6.2f}%")
    for g, v in logo.items():
        print(f"without {g} ({v['removed_group']}): first = {v['first']}; "
              f"order = {', '.join(v['ranking'][:3])}, ...")


if __name__ == "__main__":
    main()
