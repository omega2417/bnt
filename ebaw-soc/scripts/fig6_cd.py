"""Figure 6 - critical difference diagrams (Friedman test with Nemenyi post hoc, alpha = 0.05)
over N = 30 independent blocks (replications; each block holds the metric averaged over the eight
scenarios, because the scenarios of one replication share the same base streams and are therefore
not independent) for (a) the expected cost J and (b) the unsafe-execution rate."""
import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from figstyle import INK, MUTED, OI, RESDIR, save, setup

setup()
df = pd.read_csv(os.path.join(RESDIR, "main_runs.csv"))
order = ["AD", "CO", "RO", "GN", "EB", "ET"]
NAMES = {"AD": "Agent-direct (no gate)", "CO": "Confidence-only", "RO": "Receipt-only",
         "GN": "Gateway, no revalidation", "EB": "EBAW, full contract", "ET": "EBAW, tier-scoped"}
Q05 = {2: 1.960, 3: 2.343, 4: 2.569, 5: 2.728, 6: 2.850, 7: 2.949, 8: 3.031}   # Demsar (2006), Table 5


def cd_stats(metric):
    piv = df.groupby(["rep", "policy"])[metric].mean().unstack()[order]
    N, k = piv.shape
    ranks = piv.rank(axis=1, method="average").mean()
    chi2, p = stats.friedmanchisquare(*[piv[c] for c in order])
    ff = (N - 1) * chi2 / (N * (k - 1) - chi2)
    p_ff = stats.f.sf(ff, k - 1, (k - 1) * (N - 1))
    cd = Q05[k] * np.sqrt(k * (k + 1) / (6.0 * N))
    return dict(N=N, k=k, ranks=ranks.to_dict(), chi2=float(chi2), p=float(p), FF=float(ff), p_FF=float(p_ff),
                CD=float(cd))


def cliques(ranks, cd):
    items = sorted(ranks.items(), key=lambda kv: kv[1])
    out = []
    for i in range(len(items)):
        j = i
        while j + 1 < len(items) and items[j + 1][1] - items[i][1] < cd:
            j += 1
        if j > i:
            grp = [items[t][0] for t in range(i, j + 1)]
            if not any(set(grp) <= set(g) for g in out):
                out.append(grp)
    return out


def draw(ax, st, title):
    ranks, cd, k = st["ranks"], st["CD"], st["k"]
    lo, hi = 1, k
    ax.set_xlim(lo - 4.55, hi + 4.55)
    ax.set_ylim(0.15, 1.78)
    ax.axis("off")
    yax = 1.15
    ax.plot([lo, hi], [yax, yax], color=INK, lw=2.0)
    for r in range(lo, hi + 1):
        ax.plot([r, r], [yax, yax + 0.07], color=INK, lw=2.0)
        ax.text(r, yax + 0.11, str(r), ha="center", va="bottom", fontsize=13.5)
    for r in np.arange(lo + 0.5, hi, 1.0):
        ax.plot([r, r], [yax, yax + 0.04], color=INK, lw=1.4)
    # CD bar
    ax.plot([lo, lo + cd], [yax + 0.45, yax + 0.45], color=INK, lw=2.6)
    for xx in (lo, lo + cd):
        ax.plot([xx, xx], [yax + 0.40, yax + 0.50], color=INK, lw=2.0)
    ax.text(lo + cd / 2, yax + 0.52, f"CD = {cd:.3f}", ha="center", va="bottom", fontsize=12.8)
    ax.text(hi + 4.4, yax + 0.45, title, ha="right", va="center", fontsize=14.2)
    items = sorted(ranks.items(), key=lambda kv: kv[1])
    half = len(items) // 2
    left, right = items[:half], items[half:]
    for i, (name, r) in enumerate(left):
        y = yax - 0.30 - 0.27 * i
        ax.plot([r, r, lo - 0.25], [yax, y, y], color=INK, lw=1.7)
        ax.text(lo - 0.32, y, f"{NAMES[name]}  ({r:.2f})", ha="right", va="center", fontsize=13.0)
    for i, (name, r) in enumerate(right[::-1]):
        y = yax - 0.30 - 0.27 * i
        ax.plot([r, r, hi + 0.25], [yax, y, y], color=INK, lw=1.7)
        ax.text(hi + 0.32, y, f"({r:.2f})  {NAMES[name]}", ha="left", va="center", fontsize=13.0)
    for j, grp in enumerate(cliques(ranks, cd)):
        rs = [ranks[g] for g in grp]
        yy = yax - 0.10 - 0.07 * j
        ax.plot([min(rs) - 0.02, max(rs) + 0.02], [yy, yy], color=OI["verm"], lw=5.0, solid_capstyle="round")


sJ, sU = cd_stats("J"), cd_stats("UER")
fig, (a1, a2) = plt.subplots(2, 1, figsize=(10.6, 5.4), gridspec_kw=dict(hspace=0.12))
draw(a1, sJ, "(a) expected cost $J$ (lower is better)")
draw(a2, sU, "(b) unsafe executions per 1000 proposals")
save(fig, "fig6_cd")


def wilcoxon_holm(metric, pairs=(("EB", "GN"), ("EB", "CO"), ("ET", "EB"), ("ET", "CO"), ("GN", "CO"), ("ET", "GN"))):
    """Two-sided Wilcoxon signed-rank tests on the 30 replication blocks with Holm's step-down
    correction within the metric (Demsar, 2006)."""
    piv = df.groupby(["rep", "policy"])[metric].mean().unstack()
    res = []
    for a, b in pairs:
        w = stats.wilcoxon(piv[a], piv[b], alternative="two-sided")
        d = piv[a] - piv[b]
        res.append(dict(pair=f"{a}-{b}", mean_diff=float(d.mean()), a_lower=int((d < 0).sum()),
                        a_higher=int((d > 0).sum()), W=float(w.statistic), p=float(w.pvalue)))
    order_p = sorted(range(len(res)), key=lambda i: res[i]["p"])
    m, run = len(res), 0.0
    for rank, i in enumerate(order_p):
        run = max(run, min(1.0, (m - rank) * res[i]["p"]))
        res[i]["p_holm"] = run
    return res


out = {"J": sJ, "UER": sU, "cliques_J": cliques(sJ["ranks"], sJ["CD"]), "cliques_UER": cliques(sU["ranks"], sU["CD"]),
       "wilcoxon_holm_J": wilcoxon_holm("J"), "wilcoxon_holm_UER": wilcoxon_holm("UER")}
json.dump(out, open(os.path.join(RESDIR, "friedman.json"), "w"), indent=1)
print(json.dumps(out, indent=1))
