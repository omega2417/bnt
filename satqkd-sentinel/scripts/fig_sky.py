"""Sky view of the passes of Table 4 and elevation share of the pass key."""
import sys, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap, Normalize
from satqkd_sentinel import style as S
from satqkd_sentinel.linkmodel import Link, pass_profile
S.apply(); out = sys.argv[1]
SEQ = LinearSegmentedColormap.from_list("seq", ["#b9d5f3", S.BLUE, S.NAVY])
lk = Link(); norm = Normalize(0, 24)
fig = plt.figure(figsize=(6.25, 3.5))
ax = fig.add_axes([0.075, 0.185, 0.36, 0.64], projection="polar"); cax = fig.add_axes([0.095, 0.065, 0.32, 0.024])
bx = fig.add_axes([0.635, 0.16, 0.345, 0.66])
ax.set_theta_zero_location("N"); ax.set_theta_direction(-1); ax.set_ylim(0, 72)
ax.set_yticks([0, 30, 50, 70]); ax.set_yticklabels(["", "60°", "40°", "20°"], fontsize=7.2, color=S.INK2); ax.set_rlabel_position(202)
ax.set_xticks(np.radians([0, 90, 180, 270])); ax.set_xticklabels(["N", "E", "S", "W"], fontsize=8.5); ax.tick_params(axis="x", pad=1)
ax.grid(True, color=S.GRID, lw=0.5); ax.spines["polar"].set_color(S.INK2); ax.spines["polar"].set_linewidth(0.7)
res = {}
styles = {25: (0, (1, 1.4)), 30: (0, (3, 1.5)), 40: (0, (5, 1.5, 1, 1.5)), 60: (0, (7, 2)), 90: "-"}
for em in (25, 30, 40, 60, 90):
    t, el, L, az = pass_profile(np.radians(em))
    r, q = lk.rate(lk.eta(L, el)); r = r / 1e3
    th = az if em < 90 else np.where(t < 0, np.pi, 0.0)
    zen = 90 - np.degrees(el)
    pts = np.column_stack([th, zen]).reshape(-1, 1, 2); seg = np.concatenate([pts[:-1], pts[1:]], axis=1)
    lc = LineCollection(seg, cmap=SEQ, norm=norm, lw=3.2, capstyle="round", zorder=3); lc.set_array(0.5 * (r[:-1] + r[1:])); ax.add_collection(lc)
    i = len(t) // 2
    if em == 90:
        ax.text(np.radians(90), 8, "90°", fontsize=7.6, ha="center", va="center", zorder=5)
    else:
        ax.text(th[-1], 79, f"{em}°", fontsize=7.6, ha="center", va="center", zorder=5, clip_on=False)
    # share of the asymptotic pass key collected above elevation e
    es = np.linspace(20, 90, 141); share = np.array([r[np.degrees(el) >= e].sum() / r.sum() for e in es])
    bx.plot(es, 100 * share, color=SEQ(norm(r.max())), lw=1.8, ls=styles[em], label=f"{em}°  ({r.sum()/1e3:.2f} Mbit)")
    half = es[np.argmin(np.abs(share - 0.5))]
    res[em] = dict(maxR=float(r.max()), K=float(r.sum()/1e3), elev_half=float(half), share_above_0p8max=float(r[np.degrees(el) >= 0.8*em].sum()/r.sum()),
                   time_share_half=float((np.degrees(el) >= half).mean()))
cb = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=SEQ), cax=cax, orientation="horizontal"); cb.outline.set_visible(False)
cb.set_ticks([0, 6, 12, 18, 24]); cb.ax.tick_params(labelsize=7.5, length=2)
fig.text(0.425, 0.077, "kbit/s", fontsize=8, va="center")
fig.text(0.012, 0.94, "(a) sky tracks coloured by key rate", fontsize=9.5, fontweight="bold", va="center")
fig.text(0.545, 0.94, "(b) share of the pass key above ε", fontsize=9.5, fontweight="bold", va="center")
bx.set_xlim(20, 90); bx.set_ylim(0, 100); bx.set_xticks([20, 30, 45, 60, 75, 90]); bx.set_xlabel("elevation ε, deg"); bx.set_ylabel("share of $K_\\infty$, %")
bx.grid(True, axis="y"); bx.axhline(50, color=S.INK2, lw=0.6, ls=(0, (1, 1.5)))
bx.legend(title="ε$_{max}$  ($K_\\infty$ of the pass)", title_fontsize=7.4, fontsize=7.4, loc="upper right", handlelength=2.6, labelspacing=0.3)
fig.savefig(out, dpi=300)
import json; print(json.dumps(res, indent=1))
