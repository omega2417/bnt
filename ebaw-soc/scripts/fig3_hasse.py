"""Figure 3 - Hasse diagram of the 32 admission contracts (subsets of P1..P5, all with
revalidation) under the combined-stress scenario S7; fill = unsafe executions per 1000
proposals (log scale), thick path = greedy safety path."""
import os
from itertools import combinations

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyBboxPatch

from figstyle import INK, MUTED, OI, RESDIR, save, setup

setup()
lat = pd.read_csv(os.path.join(RESDIR, "lattice_runs.csv"), dtype={"subset": str})
m = lat.groupby("subset")[["UER", "ESC", "DMR", "CVR", "J"]].mean()
P = "FCLVD"


def key(S):
    return "".join(x for x in P if x in S) or "0"


levels = {k: [frozenset(c) for c in combinations(P, k)] for k in range(6)}
pos = {}
for k, subs in levels.items():
    subs = sorted(subs, key=lambda S: [P.index(x) for x in sorted(S, key=P.index)])
    n = len(subs)
    span = {0: 0, 1: 9.6, 2: 12.6, 3: 12.6, 4: 9.6, 5: 0}[k]
    xs = np.linspace(-span / 2, span / 2, n) if n > 1 else [0.0]
    for S, x in zip(subs, xs):
        pos[key(S)] = (x, k * 1.55)

cmap = mcolors.LinearSegmentedColormap.from_list("verm", ["#fdeee6", "#f6b48f", "#e3732f", "#b4410a", "#6e2302"])
norm = mcolors.LogNorm(vmin=10, vmax=400)

fig, ax = plt.subplots(figsize=(10.6, 8.0))
# edges
for k in range(5):
    for S in levels[k]:
        for p in P:
            if p not in S:
                a, b = pos[key(S)], pos[key(S | {p})]
                ax.plot([a[0], b[0]], [a[1], b[1]], color="#b9b9b9", lw=1.1, zorder=1)

# greedy safety path: from the empty set, add the predicate with the largest UER reduction
path = [frozenset()]
while len(path[-1]) < 5:
    cur = path[-1]
    nxt = min((cur | {p} for p in P if p not in cur), key=lambda S: m.loc[key(S), "UER"])
    path.append(nxt)
for a, b in zip(path[:-1], path[1:]):
    pa, pb = pos[key(a)], pos[key(b)]
    ax.plot([pa[0], pb[0]], [pa[1], pb[1]], color=INK, lw=4.2, zorder=2, solid_capstyle="round")

W, Hh = 1.16, 0.52
for k, subs in levels.items():
    for S in subs:
        kk = key(S)
        x, y = pos[kk]
        u = m.loc[kk, "UER"]
        col = cmap(norm(u))
        lum = 0.2126 * col[0] + 0.7152 * col[1] + 0.0722 * col[2]
        ax.add_patch(FancyBboxPatch((x - W / 2, y - Hh / 2), W, Hh, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=col, ec=INK, lw=1.3, zorder=3))
        lab = "∅" if kk == "0" else kk
        ax.text(x, y + 0.01, lab, ha="center", va="center", fontsize=12.6 if len(lab) < 5 else 12.0, zorder=4,
                color="white" if lum < 0.45 else INK)
        ax.text(x, y - Hh / 2 - 0.13, f"{u:.1f}", ha="center", va="top", fontsize=11.2, color=INK, zorder=4,
                bbox=dict(fc="white", ec="none", pad=1.6))

# call-outs
def callout(kk, text, dx, dy, ha):
    x, y = pos[kk]
    ax.annotate(text, xy=(x + (W / 2 if dx > 0 else -W / 2) * 0.9, y), xytext=(x + dx, y + dy), ha=ha,
                va="center", fontsize=12.6, zorder=6,
                arrowprops=dict(arrowstyle="-", lw=1.4, color=INK, shrinkA=2, shrinkB=0))


callout("0", "no admission control", 1.8, 0.0, "left")
callout("C", "confidence only", -1.0, -0.95, "center")
callout("L", "ledger receipt only", 1.4, -0.95, "left")
notes = {"FCLVD": "full contract: CVR = 0", "FCLV": "minimum unsafe-execution rate", "CLV": "minimum expected cost $J$"}
for kk in ("CLV", "FCLV", "FCLVD"):
    x, y = pos[kk]
    ax.add_patch(FancyBboxPatch((x - W / 2 - 0.08, y - Hh / 2 - 0.08), W + 0.16, Hh + 0.16,
                                boxstyle="round,pad=0.02,rounding_size=0.15", fc="none", ec=OI["blue"], lw=3.0,
                                zorder=5))
ly = 5 * 1.55 + 0.25
for i, kk in enumerate(("FCLVD", "FCLV", "CLV")):
    yy = ly - i * 0.5
    ax.add_patch(FancyBboxPatch((3.05, yy - 0.15), 0.5, 0.3, boxstyle="round,pad=0.01,rounding_size=0.08", fc="white",
                                ec=OI["blue"], lw=2.6, zorder=5))
    ax.text(3.75, yy, f"{kk}: {notes[kk]}", ha="left", va="center", fontsize=12.4)
ax.text(3.05, ly + 0.45, "thick path: greedy safety path", ha="left", va="center", fontsize=12.4)
ax.plot([3.05 + 0.0, 3.55], [ly + 0.45 - 0.0, ly + 0.45], alpha=0)

for k in range(6):
    ax.text(-7.0, k * 1.55, f"$|S| = {k}$", ha="right", va="center", fontsize=13.0, color=MUTED)

sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
cax = ax.inset_axes([1.005, 0.0, 0.022, 0.62])
cb = fig.colorbar(sm, cax=cax, ticks=[10, 20, 50, 100, 200, 400])
cb.ax.set_yticklabels(["10", "20", "50", "100", "200", "400"])
cb.set_label("Unsafe executions\nper 1000 proposals (log)", fontsize=13.0, linespacing=1.0)
cb.outline.set_linewidth(1.2)
ax.set_xlim(-8.1, 8.6)
ax.set_ylim(-1.2, 5 * 1.55 + 0.95)
ax.axis("off")
save(fig, "fig3_hasse")
print("greedy path:", [key(S) for S in path])
print(m.round(2).sort_values("UER").head(8))
