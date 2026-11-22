"""Figure 2 - logic-analyzer timing diagram of one simulated proposal (scenario S3,
replication 2, kill_process): predicate waveforms, warrant validity and the two outcomes."""
import json
import os

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Rectangle

from figstyle import FAINT, INK, MUTED, OI, RESDIR, save, setup

setup()
tr = json.load(open(os.path.join(RESDIR, "traces.json")))["S3|2|309"]
g, e = tr["GN"], tr["EB"]
t0 = g["t_obs"]
T = {k: g[k] - t0 for k in ("t_avail", "t_conf", "t_prop", "t_chk", "t_iss", "t_x", "t_done", "t_pc1")}
T["t_reval"] = e["t_reval"] - t0
tau_hat = 2.0 * 2.718281828 ** (1.2816 * 0.4)
PHI, D = g["Phi"], g["D"]
T_D = D - (g["dg"] + g["dc"] + tau_hat)
B = min(PHI, D - tau_hat)
XMAX = 186.0

fig, ax = plt.subplots(figsize=(10.6, 7.3))
ax.set_xlim(-3, XMAX)
H = 0.62          # signal swing
SL = 0.9          # transition slant (s)

rows = [  # (label, colour, segments [(t_start, t_end, level)], level: 1 high, 0 low, None undefined)
    (r"$P_1$  freshness  $a \leq \Phi_\alpha$", OI["blue"], [(-3, PHI, 1), (PHI, XMAX, 0)]),
    (r"$P_2$  calibrated  $c \geq \theta_\rho$", OI["purple"], [(-3, T["t_avail"], None), (T["t_avail"], XMAX, 1)]),
    (r"$P_3$  ledger quorum", OI["green"], [(-3, T["t_conf"], 0), (T["t_conf"], XMAX, 1)]),
    (r"$P_4$  policy  $v = v_w$", OI["orange"], [(-3, T["t_pc1"], 1), (T["t_pc1"], XMAX, 0)]),
    (r"$P_5$  deadline budget", OI["sky"], [(-3, T_D, 1), (T_D, XMAX, 0)]),
    (r"warrant $w$ valid", INK, [(-3, T["t_iss"], 0), (T["t_iss"], T["t_pc1"], 1), (T["t_pc1"], XMAX, 0)]),
]
n = len(rows)
ybase = {i: (n - i) * 1.0 + 1.6 for i in range(n)}


def trace(y0, segs, col):
    xs, ys = [], []
    for (a, b, lev) in segs:
        if lev is None:
            # undefined (bus "X") region
            ax.add_patch(Rectangle((a, y0), b - a, H, fc="white", ec=MUTED, lw=1.0, hatch="xx", zorder=2))
            continue
        yl = y0 + (H if lev else 0.0)
        if xs and abs(ys[-1] - yl) > 1e-9:
            xs.append(a + SL / 2)
            ys.append(yl)
        elif not xs:
            xs.append(a)
            ys.append(yl)
        xs.append(b - SL / 2)
        ys.append(yl)
        if lev:
            ax.add_patch(Polygon([(a + SL / 2, y0), (a + SL / 2, y0 + H), (b - SL / 2, y0 + H), (b - SL / 2, y0)],
                                 closed=True, fc=col, alpha=0.16, ec="none", zorder=1))
    ax.plot(xs, ys, color=col, lw=2.8, solid_joinstyle="miter", zorder=3)


for i, (lab, col, segs) in enumerate(rows):
    y0 = ybase[i]
    trace(y0, segs, col)
    ax.text(-4.5, y0 + H / 2, lab, ha="right", va="center", fontsize=13.5)

# event lines (labels on two tiers to avoid collisions)
events = [(T["t_avail"], r"score $s$", 0, "right", -0.8), (T["t_conf"], "ledger final", 1, "left", 0.8),
          (T["t_iss"], "warrant issued", 0, "left", 0.8),
          (T["t_pc1"], "policy change: action forbidden", 1, "center", 0.0), (T["t_x"], r"$t_{ready}$", 0, "center", 0.0)]
ytop = ybase[0] + H + 0.25
for x, lab, tier, ha, dx in events:
    ax.plot([x, x], [0.15, ytop + 0.05 + 0.45 * tier], color=MUTED, lw=1.3, ls=(0, (2, 3)), zorder=0)
    ax.text(x + dx, ytop + 0.12 + 0.45 * tier, lab, ha=ha, va="bottom", fontsize=12.5, color=INK, linespacing=1.0)

# latency budget bar (top)
yb = ytop + 1.35
segs = [(0, T["t_avail"], r"$a_0$", OI["blue"]), (T["t_avail"], T["t_prop"], r"agent $\Delta_a$", OI["purple"]),
        (T["t_iss"], T["t_x"], r"orchestration $\Delta_o$ (queue + playbook)", OI["sky"])]
for a, b, lab, col in segs:
    ax.add_patch(Rectangle((a, yb), b - a, 0.5, fc=col, ec="white", lw=2.0, alpha=0.85, zorder=2))
    ax.text((a + b) / 2, yb + 0.25, lab, ha="center", va="center", fontsize=12.0,
            color="white" if col in (OI["blue"], OI["purple"]) else INK, zorder=3)
ax.add_patch(Rectangle((T["t_x"], yb), B - T["t_x"], 0.5, fc="white", ec=OI["green"], lw=1.8, hatch="////",
                       zorder=2))
ax.text((T["t_x"] + B) / 2, yb + 0.86, "slack $S$", ha="center", va="center", fontsize=12.0)
ax.plot([B, B], [yb - 0.15, yb + 0.65], color=INK, lw=2.2)
ax.text(B + 1.2, yb + 0.25, r"$B_\alpha = \min(\Phi_\alpha, D_\alpha - \tau_\alpha)$", ha="left", va="center",
        fontsize=12.5)
ax.text(-4.5, yb + 0.25, r"budget  $\Lambda \leq B_\alpha$", ha="right", va="center", fontsize=13.5)
ax.add_patch(Rectangle((T["t_conf"] - 1.3, yb - 0.32), 1.3, 0.22, fc=OI["green"], ec="none", zorder=2))
ax.text(T["t_conf"] + 0.8, yb - 0.21, r"$L_c$ (overlapped)", ha="left", va="center", fontsize=11.5, color=INK)

# outcomes
y_gn, y_eb = 1.15, 0.35
ax.text(-4.5, y_gn, "no revalidation (GN)", ha="right", va="center", fontsize=13.5)
ax.text(-4.5, y_eb, "revalidation (EBAW)", ha="right", va="center", fontsize=13.5)
ax.annotate("", xy=(T["t_x"], y_gn), xytext=(T["t_iss"], y_gn),
            arrowprops=dict(arrowstyle="<->", lw=1.8, color=MUTED, shrinkA=0, shrinkB=0))
ax.text((T["t_iss"] + T["t_x"]) / 2, y_gn + 0.13, f"check-to-act window $W$ = {T['t_x'] - T['t_iss']:.1f} s",
        ha="center", va="bottom", fontsize=12.2)
ax.add_patch(Rectangle((T["t_x"], y_gn - 0.2), T["t_done"] - T["t_x"], 0.4, fc=OI["verm"], ec=INK, lw=1.2, zorder=3))
ax.text(T["t_done"] + 1.6, y_gn, r"executes under superseded policy: $P_4$ violated", ha="left", va="center",
        fontsize=12.2, color=INK)
ax.plot([T["t_reval"]], [y_eb], marker="D", ms=11, color=OI["green"], mec=INK, mew=1.2, zorder=4)
ax.text(T["t_reval"] + 2.2, y_eb, r"revalidation: $P_4$ false $\rightarrow$ re-evaluated, forbidden $\rightarrow$ "
        "blocked\n" r"(residual window $\delta_c \approx 20$ ms)", ha="left", va="center", fontsize=12.2,
        linespacing=1.05)

ax.set_ylim(-0.15, yb + 1.1)
ax.set_yticks([])
ax.spines["left"].set_visible(False)
ax.set_xlabel(r"Time since primary observation, $t - t_{obs}$ (s)")
ax.set_xticks([0, 20, 40, 60, 80, 100, 120, 140, 160, 180])
save(fig, "fig2_timing")
print("ok", {k: round(v, 2) for k, v in T.items()}, round(B, 2), round(T_D, 2))
