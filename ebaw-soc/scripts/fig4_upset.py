"""Figure 4 - UpSet plot of predicate-failure intersections for the full EBAW gateway
under S7 (30 replications pooled), with the class composition of each intersection."""
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Rectangle

from figstyle import FAINT, INK, MUTED, OI, RESDIR, save, setup

setup()


def fmt(n):
    """MDPI style: thousands separator only for numbers with five or more digits."""
    n = int(n)
    return f"{n:,}" if n >= 10000 else str(n)


u = pd.read_csv(os.path.join(RESDIR, "upset_EB_S7.csv"), dtype={"fails_all": str}).fillna("")
u["cat"] = np.where(u.kind != "gen", "adversarial", np.where(u.y == 1, "malicious", "benign"))
f = u[u.fails_all != ""]
counts = f.groupby("fails_all").size().sort_values(ascending=False)
inter = [k for k, v in counts.items() if v >= 20]
comp = pd.crosstab(f.fails_all, f.cat).reindex(inter).fillna(0)
P = ["F", "C", "L", "V", "D"]
names = {"F": r"$P_1$ freshness", "C": r"$P_2$ confidence", "L": r"$P_3$ ledger", "V": r"$P_4$ policy",
         "D": r"$P_5$ deadline"}
setsize = {p: int(f.fails_all.str.contains(p).sum()) for p in P}
ncol = len(inter)
CAP = 1650

fig = plt.figure(figsize=(10.6, 7.6))
gs = fig.add_gridspec(3, 3, width_ratios=[1.25, 1.35, 6.0], height_ratios=[3.3, 0.62, 2.0], wspace=0.02,
                      hspace=0.07)
axb = fig.add_subplot(gs[0, 2])
axc = fig.add_subplot(gs[1, 2], sharex=axb)
axm = fig.add_subplot(gs[2, 2], sharex=axb)
axs = fig.add_subplot(gs[2, 0], sharey=axm)
axn = fig.add_subplot(gs[2, 1], sharey=axm)
x = np.arange(ncol)
BAR = "#3b4a5a"

# intersection sizes (linear, tallest bar broken)
for i, k in enumerate(inter):
    v = counts[k]
    h = min(v, CAP)
    axb.add_patch(Rectangle((i - 0.36, 0), 0.72, h, fc=BAR, ec="none"))
    axb.text(i, h + 25, fmt(v), ha="center", va="bottom", fontsize=12.0, rotation=0)
    if v > CAP:
        for dy in (0.0, 70.0):
            axb.plot([i - 0.46, i + 0.46], [CAP - 300 + dy, CAP - 240 + dy], color="white", lw=4.0, zorder=3)
axb.set_ylim(0, CAP + 230)
axb.set_ylabel("Proposals with exactly\nthis failure set")
axb.spines["bottom"].set_visible(False)
axb.tick_params(axis="x", bottom=False, labelbottom=False)
axb.yaxis.grid(True, color=FAINT, lw=1.2)
axb.set_axisbelow(True)

# composition strip (100 % stacked)
cols = {"malicious": OI["blue"], "benign": OI["orange"], "adversarial": OI["purple"]}
for i, k in enumerate(inter):
    tot = comp.loc[k].sum()
    b = 0.0
    for c in ("malicious", "benign", "adversarial"):
        w = comp.loc[k, c] / tot if c in comp.columns else 0.0
        if w > 0:
            axc.add_patch(Rectangle((i - 0.36, b), 0.72, w, fc=cols[c], ec="white", lw=1.2))
        b += w
axc.set_ylim(0, 1)
axc.set_yticks([0, 1])
axc.set_yticklabels(["0", "100%"])
axc.set_ylabel("class\nmix", rotation=0, ha="right", va="center", labelpad=6)
axc.tick_params(axis="x", bottom=False, labelbottom=False)
for s in ("bottom", "left"):
    axc.spines[s].set_visible(False)
axc.tick_params(axis="y", length=0)
handles = [Rectangle((0, 0), 1, 1, fc=cols[c]) for c in cols]
axb.legend(handles, ["genuine, malicious", "genuine, benign", "adversarial (hallucinated, injected, tampered)"],
           loc="upper right", fontsize=12.6, handlelength=1.2, borderaxespad=0.2)

# membership matrix
for j, p in enumerate(P):
    yj = len(P) - 1 - j
    if j % 2 == 0:
        axm.add_patch(Rectangle((-0.6, yj - 0.5), ncol + 0.2, 1.0, fc=FAINT, ec="none", zorder=0))
    for i, k in enumerate(inter):
        on = p in k
        axm.plot(i, yj, "o", ms=13 if on else 11, color=INK if on else "#cfcfcf", zorder=2)
for i, k in enumerate(inter):
    ys = [len(P) - 1 - P.index(p) for p in k]
    if len(ys) > 1:
        axm.plot([i, i], [min(ys), max(ys)], color=INK, lw=3.2, zorder=1)
axm.set_xlim(-0.75, ncol - 0.35)
axm.set_ylim(-0.6, len(P) - 0.4)
axm.set_yticks([])
axm.set_xticks([])
for s in ("left", "bottom"):
    axm.spines[s].set_visible(False)

# set sizes and names
for j, p in enumerate(P):
    yj = len(P) - 1 - j
    axs.barh(yj, setsize[p], height=0.56, color=BAR)
    axs.text(setsize[p] * 1.04 + 60, yj, fmt(setsize[p]), ha="right", va="center", fontsize=12.0)
    axn.text(0.04, yj, names[p], ha="left", va="center", fontsize=13.0)
axs.set_xlim(max(setsize.values()) * 1.75, 0)
axs.set_yticks([])
axs.set_xticks([])
for a in (axs, axn):
    for sp in ("left", "bottom", "top", "right"):
        a.spines[sp].set_visible(False)
axn.set_xlim(0, 1)
axn.set_xticks([])
axn.tick_params(axis="y", left=False, labelleft=False)
axs.set_xlabel("failing proposals", fontsize=13.0, labelpad=2)
fig.text(0.05, 0.93, f"S7, 30 replications, {fmt(len(u))} proposals;\n{fmt(len(f))} with at least one failed predicate",
         fontsize=12.6, ha="left", va="top")
save(fig, "fig4_upset")
print(counts.head(16).to_dict(), setsize)
