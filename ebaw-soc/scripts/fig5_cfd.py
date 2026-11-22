"""Figure 5 - cumulative flow diagram of proposals through the EBAW gateway during an
8-h shift with two alert surges (scenario S6, replication 0)."""
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from figstyle import FAINT, INK, MUTED, OI, RESDIR, save, setup

setup()
c = pd.read_csv(os.path.join(RESDIR, "cfd_S6_rep0.csv"))
d = c[c.policy == "EB"].copy()
inf = np.inf
auto = d.outcome == "executed_auto"
esc = d.escalated.astype(bool)
t_prop, t_dec, t_close = d.t_prop.values, d.t_decided.values, d.t_closed.values
t_disp = np.where(auto, d.t_disp.values, inf)


def occ(start, end, t):
    s = np.asarray(start)[:, None]
    e = np.asarray(end)[:, None]
    return ((s <= t[None, :]) & (t[None, :] < e)).sum(axis=0)


t = np.arange(0, 8 * 3600 + 60, 10.0)
arrived = (t_prop[:, None] <= t[None, :]).sum(axis=0)
closed = (t_close[:, None] <= t[None, :]).sum(axis=0)
w_adm = occ(t_prop, t_dec, t)
w_disp = occ(np.where(auto, t_dec, inf), np.where(auto, t_disp, inf), t)
w_exec = occ(np.where(auto, t_disp, inf), np.where(auto, t_close, inf), t)
w_ana = occ(np.where(esc, t_dec, inf), np.where(esc, t_close, inf), t)
check = closed + w_exec + w_disp + w_ana + w_adm
assert np.all(check == arrived), "flow conservation violated"

bands = [("closed", closed, "#cfd6de"), ("in playbook / execution", w_exec, OI["blue"]),
         ("warranted, awaiting dispatch", w_disp, OI["sky"]), ("escalated, with analyst", w_ana, OI["orange"]),
         ("awaiting admission (incl. ledger wait)", w_adm, OI["purple"])]
surges = [(2 * 3600, 2 * 3600 + 1200), (5 * 3600, 5 * 3600 + 1200)]

fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.6, 4.9), gridspec_kw=dict(width_ratios=[1.35, 1.0], wspace=0.22))
for ax, lo, hi in ((a1, 0, 8 * 3600), (a2, 1.75 * 3600, 3.25 * 3600)):
    m = (t >= lo) & (t <= hi)
    th = t[m] / 3600.0
    base = np.zeros(m.sum())
    for name, y, col in bands:
        ax.fill_between(th, base, base + y[m], color=col, lw=0, step="post", label=name,
                        alpha=1.0 if name != "closed" else 1.0)
        base = base + y[m]
    ax.plot(th, arrived[m], color=INK, lw=2.4, drawstyle="steps-post")
    for (s0, s1) in surges:
        if s1 / 3600 >= lo / 3600 and s0 / 3600 <= hi / 3600:
            ax.axvspan(s0 / 3600, s1 / 3600, color=FAINT, zorder=0)
    ax.set_xlim(lo / 3600, hi / 3600)
    ax.set_xlabel("Shift time (h)")
    ax.yaxis.grid(True, color=FAINT, lw=1.2)
    ax.set_axisbelow(True)
a1.set_ylabel("Cumulative proposals")
a1.set_ylim(0, arrived.max() * 1.04)
a1.text(2.17, arrived.max() * 0.97, "surge 1", ha="center", va="top", fontsize=12.6, color=MUTED)
a1.text(5.17, arrived.max() * 0.97, "surge 2", ha="center", va="top", fontsize=12.6, color=MUTED)
m2 = (t >= 1.75 * 3600) & (t <= 3.25 * 3600)
lo_y = closed[m2].min() - 5
a2.set_ylim(lo_y, arrived[m2].max() + 8)
a2.set_title("zoom: surge 1 (2:00 - 2:20)", fontsize=14.0, loc="left")
a1.set_title("(a) full 8-h shift", fontsize=14.0, loc="left")
a2.set_title("(b) zoom on surge 1 (2:00-2:20)", fontsize=14.0, loc="left")
# annotate the peak work in progress
wip = (w_exec + w_disp + w_ana + w_adm)
k = np.argmax(np.where(m2, wip, -1))
a2.annotate(f"peak WIP = {wip[k]}", xy=(t[k] / 3600, closed[k] + wip[k] / 2), xytext=(2.36, closed[k] - 28),
            fontsize=12.6, ha="left", arrowprops=dict(arrowstyle="-", lw=1.3, color=INK))
ka = np.argmin(np.abs(t - 2.45 * 3600))
a2.annotate("analyst backlog", xy=(2.45, closed[ka] + w_exec[ka] + w_disp[ka] + w_ana[ka] / 2),
            xytext=(2.62, closed[ka] - 22), fontsize=12.6, ha="left",
            arrowprops=dict(arrowstyle="-", lw=1.3, color=INK))
kd = np.argmax(np.where(m2, w_disp, -1))
a2.annotate("dispatch queue", xy=(t[kd] / 3600, closed[kd] + w_exec[kd] + w_disp[kd] / 2),
            xytext=(2.12, closed[kd] - 34), fontsize=12.6, ha="left",
            arrowprops=dict(arrowstyle="-", lw=1.3, color=INK))
h, l = a1.get_legend_handles_labels()
fig.legend(h[::-1], l[::-1], loc="upper center", ncol=3, fontsize=12.4, bbox_to_anchor=(0.5, 1.10),
           handlelength=1.2, columnspacing=1.2)
save(fig, "fig5_cfd")
print("peak WIP", wip.max(), "at", t[np.argmax(wip)] / 3600, "max analyst WIP", w_ana.max(), "max dispatch WIP",
      w_disp.max(), "arrived", arrived.max())
