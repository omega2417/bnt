"""Coverage map, contact plan and tier link budget of the geostationary backbone."""
import sys, json, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap, BoundaryNorm, LinearSegmentedColormap
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
from mpl_toolkits.basemap import Basemap
from satqkd_sentinel import style as S
from satqkd_sentinel.linkmodel import Link, slant_range, R_E, R_GEO, H_GEO, C_LIGHT
from satqkd_sentinel.geo import *
S.apply()
outdir = sys.argv[1]
SITES = [("G-A", 48.46, 35.05), ("G-B", 28.30, -16.51)]
SEQ = LinearSegmentedColormap.from_list("seq", ["#eef4fc", "#9cc3ee", S.BLUE, S.NAVY])

# ------------------------------------------------------------------ coverage map
fig, axes = plt.subplots(2, 1, figsize=(6.25, 5.9))
cm = ListedColormap(["#ffffff", "#c9dff6", "#6da4e3"]); norm = BoundaryNorm([-0.5, 0.5, 1.5, 2.5], 3)
for ax, n, tag in zip(axes, (3, 4), "ab"):
    c = coverage_stats(n)
    bm = Basemap(projection="cyl", llcrnrlat=-72, urcrnrlat=72, llcrnrlon=-180, urcrnrlon=180, resolution="c", ax=ax)
    LON, LAT = np.meshgrid(np.degrees(c["lon"]), np.degrees(c["lat"]))
    bm.pcolormesh(LON, LAT, np.minimum(c["k"], 2), cmap=cm, norm=norm, shading="auto", rasterized=True)
    bm.drawcoastlines(linewidth=0.35, color=S.INK2)
    cs = bm.contour(LON, LAT, np.degrees(c["best_elev"]), levels=[40, 60], colors=S.NAVY, linewidths=0.6, linestyles=[(0, (4, 2))])
    ax.clabel(cs, fmt="%d°", fontsize=6.5, inline_spacing=2)
    bm.drawparallels([-60, -30, 0, 30, 60], labels=[1, 0, 0, 0], linewidth=0.3, color=S.GRID, fontsize=7.5, dashes=[1, 0])
    bm.drawmeridians(np.arange(-180, 181, 60), labels=[0, 0, 0, 1 if tag == "b" else 0], linewidth=0.3, color=S.GRID, fontsize=7.5, dashes=[1, 0])
    for i, ls in enumerate(np.degrees(slots(n))):
        ax.plot(ls, 0, marker="s", ms=7, mfc=S.BLUE, mec="white", mew=0.8, zorder=6)
        ax.text(ls, -9, f"B{i+1}", ha="center", va="center", fontsize=8, fontweight="bold", zorder=6)
    for name, la, lo in SITES:
        ax.plot(lo, la, marker="^", ms=6, mfc=S.ORANGE, mec="white", mew=0.7, zorder=7)
        ax.text(lo + 5, la + 1, name, fontsize=7.5, va="center", zorder=7,
                bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.8))
    lc = c["lat_cont"]
    ax.set_title(f"({tag}) {'three' if n == 3 else 'four'} nodes: {100*c['share1']:.1f}% of the surface sees a node above 20°, {100*c['share2']:.1f}% sees two", fontsize=9)
    for sp in ax.spines.values(): sp.set_visible(True); sp.set_linewidth(0.6)
h = [Patch(fc="#ffffff", ec=S.INK2, lw=0.5, label="no node above 20°"), Patch(fc="#c9dff6", ec="none", label="one node"),
     Patch(fc="#6da4e3", ec="none", label="two nodes"), Line2D([], [], color=S.NAVY, lw=0.8, ls=(0, (4, 2)), label="best elevation 40°, 60°"),
     Line2D([], [], marker="s", ls="", mfc=S.BLUE, mec="white", ms=7, label="backbone node"),
     Line2D([], [], marker="^", ls="", mfc=S.ORANGE, mec="white", ms=6.5, label="ground station")]
fig.legend(handles=h, loc="lower center", ncol=3, fontsize=7.8, handlelength=1.6, columnspacing=2.2, bbox_to_anchor=(0.5, 0.0))
fig.subplots_adjust(left=0.075, right=0.985, top=0.955, bottom=0.125, hspace=0.17)
fig.savefig(f"{outdir}/fig_geo_coverage.png", dpi=300); plt.close(fig)

# ------------------------------------------------------------------ contact plan
N = 4
cp = contact_plan(N, [(la, lo) for _, la, lo in SITES], hours=24, dt=10.0)
long = contact_plan(N, [(la, lo) for _, la, lo in SITES], hours=240, dt=10.0)
def runs(mask, t):
    d = np.diff(np.concatenate([[0], mask.astype(int), [0]]))
    return [(t[a] / 3600, (t[min(b, len(t) - 1)] - t[a]) / 3600) for a, b in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1))]
fig = plt.figure(figsize=(6.25, 3.9))
ax = fig.add_axes([0.195, 0.13, 0.43, 0.76]); bx = fig.add_axes([0.80, 0.13, 0.185, 0.76])
rows = [(f"relay R1 → B{i+1}", cp["geo"][i], long["geo"][i], S.BLUE) for i in range(N)]
rows += [("≥ 1 backbone node", cp["geo"].any(0), long["geo"].any(0), S.NAVY), ("≥ 2 backbone nodes", cp["geo"].sum(0) >= 2, long["geo"].sum(0) >= 2, S.NAVY)]
rows += [(f"relay R1 → {SITES[i][0]}", cp["site"][i], long["site"][i], S.ORANGE) for i in range(len(SITES))]
stats = {}
for j, (lab, m, ml, col) in enumerate(rows):
    y = len(rows) - 1 - j
    ax.add_patch(plt.Rectangle((0, y - 0.3), 24, 0.6, fc="#f3f3f1", ec="none", zorder=1))
    if col == S.ORANGE:
        for a, w in runs(m, cp["t"]):
            ax.add_patch(plt.Rectangle((a, y - 0.3), max(w, 0.05), 0.6, fc=col, ec="none", zorder=3))
            ax.plot(a + w / 2, y + 0.42, marker="v", ms=3.5, color=col, zorder=3)
    else:
        ax.broken_barh(runs(m, cp["t"]), (y - 0.3, 0.6), facecolors=col, zorder=3)
    share = 100 * ml.mean(); stats[lab] = share
    ax.text(24.4, y, f"{share:.1f}%" if share >= 1 else f"{share:.2f}%", va="center", fontsize=8)
ax.set_yticks(range(len(rows))); ax.set_yticklabels([r[0] for r in rows][::-1], fontsize=8.2)
ax.set_xlim(0, 24); ax.set_ylim(-0.6, len(rows) - 0.4); ax.set_xticks(range(0, 25, 4)); ax.set_xlabel("time, h")
ax.tick_params(axis="y", length=0); ax.spines["left"].set_visible(False)
fig.text(0.012, 0.925, "(a) contact plan of a relay, 24 h", fontsize=9.5, fontweight="bold", va="center")
ax.text(24.4, len(rows) - 0.55, "share of time", fontsize=7.4, color=S.INK2, va="bottom")
# waiting time until the next contact (ground stations only)
def waits(mask, dt):
    w = np.zeros(len(mask)); nxt = np.inf
    for i in range(len(mask) - 1, -1, -1):
        nxt = 0 if mask[i] else nxt + dt
        w[i] = nxt
    return w[np.isfinite(w)] / 3600
for m, lab, ls in ((long["site"][0], "G-A", "-"), (long["site"].any(0), "G-A or G-B", (0, (4, 2)))):
    w = np.sort(waits(m, 10.0)); bx.plot(w, np.linspace(0, 1, len(w)), color=S.ORANGE, lw=1.6, ls=ls, label=lab)
    stats["wait_median_" + lab] = float(np.median(w)); stats["wait_p90_" + lab] = float(np.percentile(w, 90)); stats["wait_max_" + lab] = float(w.max())
bx.axvline(0, color=S.NAVY, lw=2.2); bx.annotate("via backbone:\nno waiting", xy=(0.05, 0.40), xytext=(6.3, 0.40), fontsize=7.4, color=S.NAVY, va="center", linespacing=1.05, arrowprops=dict(arrowstyle="-|>", color=S.NAVY, lw=0.8))
bx.set_xlim(-0.3, 13.5); bx.set_ylim(0, 1.0); bx.set_xticks([0, 4, 8, 12]); bx.set_xlabel("waiting time, h"); bx.set_ylabel("cumulative share")
bx.grid(True, axis="y"); bx.legend(loc="lower right", fontsize=7.4, handlelength=1.8, title="direct, ground only", title_fontsize=7.2)
fig.text(0.725, 0.925, "(b) wait for a contact", fontsize=9.5, fontweight="bold", va="center")
fig.savefig(f"{outdir}/fig_geo_contact.png", dpi=300); plt.close(fig)
print(json.dumps(stats, indent=1))

# ------------------------------------------------------------------ tier link budget
lk = Link()
psiA = central_angle(np.radians(48.46), np.radians(35.05), np.radians(35.0)); elA = elevation(psiA); LA = range_from_angle(psiA)
r_leo = R_E + 500e3
rmin = R_GEO - r_leo; rmax = np.sqrt(r_leo**2 - (R_E + H_GRAZE)**2) + np.sqrt(R_GEO**2 - (R_E + H_GRAZE)**2)
links = [("relay–ground, ε = 90°", lk, slant_range(np.pi/2, 500e3), np.pi/2),
         ("relay–ground, ε = 20°", lk, slant_range(np.radians(20), 500e3), np.radians(20)),
         ("backbone–ground, G-A", lk, LA, elA),
         ("relay–backbone, nearest", lk.with_(atmosphere=False), rmin, np.pi/2),
         ("relay–backbone, farthest", lk.with_(atmosphere=False), rmax, np.pi/2)]
comp_cols = {"diffraction": S.BLUE, "receiver": S.PURPLE, "lobes": S.ORANGE, "pointing": S.AMBER, "atmosphere": S.GREEN}
comp_lab = {"diffraction": "diffraction", "receiver": "receiver", "lobes": "OPA lobes", "pointing": "pointing", "atmosphere": "atmosphere"}
fig = plt.figure(figsize=(6.25, 3.55))
ax = fig.add_axes([0.225, 0.15, 0.27, 0.64]); bx = fig.add_axes([0.635, 0.15, 0.235, 0.64]); cax = fig.add_axes([0.885, 0.15, 0.014, 0.64])
tot = {}
for j, (lab, l, L, e) in enumerate(links):
    y = len(links) - 1 - j; c = l.components_db(L, e); x0 = 0
    for kcomp in ("diffraction", "receiver", "lobes", "pointing", "atmosphere"):
        if c[kcomp] > 0.02:
            ax.barh(y, c[kcomp], left=x0, height=0.55, color=comp_cols[kcomp], ec="white", lw=0.8, zorder=3)
            x0 += c[kcomp]
    tot[lab] = x0
    ax.text(x0 + 1.2, y, f"{x0:.1f} dB", va="center", fontsize=8, zorder=6, bbox=dict(boxstyle="round,pad=0.1", fc="white", ec="none"))
lim = lk.loss_limit_db()
ax.axvline(lim, color=S.INK, lw=0.9, ls=(0, (1, 1.5)), zorder=4)
ax.text(lim, len(links) - 0.42, f"key limit\n{lim:.1f} dB", ha="center", va="bottom", fontsize=7.4, linespacing=1.0)
ax.set_yticks(range(len(links))); ax.set_yticklabels([l[0] for l in links][::-1], fontsize=8.2); ax.tick_params(axis="y", length=0)
ax.set_xlim(0, 96); ax.set_ylim(-0.5, len(links) - 0.25); ax.set_xlabel("loss, dB"); ax.set_xticks([0, 20, 40, 60, 80])
fig.text(0.012, 0.955, "(a) channel loss by tier, baseline terminal", fontsize=9.5, fontweight="bold", va="center")
ax.legend(handles=[Patch(fc=v, label=comp_lab[k]) for k, v in comp_cols.items()], loc="lower left", bbox_to_anchor=(-0.86, 1.12), ncol=5,
          fontsize=7.4, handlelength=1.0, columnspacing=0.9, handletextpad=0.4)
# aperture map: key per clear hour of a backbone-ground link to G-A
dtx = np.linspace(0.1, 1.5, 141); drx = np.linspace(0.4, 2.5, 141)
def rate_map(sj):
    R = np.zeros((len(drx), len(dtx)))
    for i, b in enumerate(drx):
        for j2, a in enumerate(dtx):
            l = lk.with_(d_tx=a, d_rx=b, sigma_j=sj)
            R[i, j2] = l.rate(l.eta(LA, elA))[0]
    return R
R02 = rate_map(0.2e-6)
im = bx.pcolormesh(dtx, drx, np.where(R02 > 0, R02 * 3600 / 1e6, np.nan), cmap=SEQ, shading="auto", rasterized=True, vmin=0)
cb = fig.colorbar(im, cax=cax); cb.set_label("key per clear hour, Mbit", fontsize=8); cb.ax.tick_params(labelsize=7.5); cb.outline.set_visible(False)
for sj, ls in ((0.2e-6, "-"), (0.5e-6, (0, (4, 2))), (1.0e-6, (0, (1, 1.5)))):
    Rm = R02 if sj == 0.2e-6 else rate_map(sj)
    bx.contour(dtx, drx, Rm, levels=[1e-9], colors=S.INK, linewidths=1.0, linestyles=[ls])
bx.plot(0.1, 0.6, marker="o", ms=5, mfc="white", mec=S.RED, mew=1.4, zorder=5, clip_on=False)
bx.text(0.17, 0.60, "baseline", fontsize=7.4, va="center")
bx.text(0.2, 1.55, "no key", fontsize=8.5, color=S.INK2)
bx.set_xlabel("backbone aperture, m"); bx.set_ylabel("ground aperture, m"); bx.set_xlim(0.1, 1.5); bx.set_ylim(0.4, 2.5)
fig.text(0.555, 0.955, "(b) backbone–ground key vs. apertures", fontsize=9.5, fontweight="bold", va="center")
bx.legend(handles=[Line2D([], [], color=S.INK, lw=1, ls=ls, label=f"{v}") for v, ls in (("0.2", "-"), ("0.5", (0, (4, 2))), ("1.0", (0, (1, 1.5))))],
          title="key limit at σ$_j$, µrad", title_fontsize=7.2, fontsize=7.4, loc="lower left", bbox_to_anchor=(-0.03, 1.0), ncol=3, handlelength=1.8, columnspacing=0.9)
fig.savefig(f"{outdir}/fig_geo_links.png", dpi=300); plt.close(fig)
out = dict(tot=tot, limit=lim, elA=float(np.degrees(elA)), LA_km=LA/1e3)
# selected points of the aperture map
for a, b, sj in ((0.5, 1.5, 0.2e-6), (0.7, 1.5, 0.2e-6), (1.0, 1.5, 0.2e-6), (1.0, 2.0, 0.2e-6), (1.0, 1.0, 0.2e-6), (1.0, 1.5, 0.5e-6), (1.0, 1.5, 1.0e-6), (1.5, 2.5, 0.2e-6)):
    l = lk.with_(d_tx=a, d_rx=b, sigma_j=sj); r, q = l.rate(l.eta(LA, elA))
    out[f"{a}x{b}@{sj*1e6}"] = dict(loss=float(l.loss_db(LA, elA)), limit=l.loss_limit_db(), rate=float(r), qber=float(q), mbit_h=float(r*3600/1e6), theta_w=l.theta_w*1e6)
# smallest equal-product apertures that close the link at 0.2 urad
print(json.dumps(out, indent=1))
