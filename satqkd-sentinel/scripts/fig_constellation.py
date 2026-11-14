import sys, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon, Circle, FancyBboxPatch, Wedge
from matplotlib.lines import Line2D
from mpl_toolkits.basemap import Basemap
from satqkd_sentinel import style as S
from satqkd_sentinel.linkmodel import R_E, R_GEO, C_LIGHT
from satqkd_sentinel.geo import coverage_angle, isl_chord, slots
S.apply()
out = sys.argv[1]
N, LON0 = 4, 35.0
k = 1e-6                                   # metres -> 10^3 km
rg, re, rl = R_GEO * k, R_E * k, (R_E + 500e3) * k
ang = lambda lon_deg: np.radians(lon_deg - LON0 + 90.0)      # B1 at the top
P = lambda r, lon: np.array([r * np.cos(ang(lon)), r * np.sin(ang(lon))])
lons = np.degrees(slots(N, LON0))
fig = plt.figure(figsize=(6.25, 6.25)); ax = fig.add_axes([0.0, 0.0, 1, 1]); ax.set_aspect("equal")
ax.set_xlim(-56, 56); ax.set_ylim(-56, 56); ax.axis("off")
ax.add_patch(Circle((0, 0), rg, fill=False, ec=GRID if False else S.GRID, lw=1.0, zorder=1))
psi = np.degrees(coverage_angle(np.radians(20)))
# coverage wedges (equatorial section of the eps >= 20 deg zones)
for lon in lons:
    pts = [P(rg, lon), P(re, lon - psi)] + [P(re, lon + a) for a in np.linspace(-psi, psi, 40)] + [P(re, lon + psi)]
    ax.add_patch(Polygon(pts, closed=True, fc=S.BLUE, alpha=0.07, ec="none", zorder=2))
    for s in (-1, 1):
        ax.plot(*zip(P(rg, lon), P(re, lon + s * psi)), color=S.BLUE, lw=0.5, alpha=0.55, zorder=2)
# backbone ring links
for i in range(N):
    a, b = P(rg, lons[i]), P(rg, lons[(i + 1) % N])
    d = (b - a) / np.linalg.norm(b - a); n = np.array([-d[1], d[0]])
    ax.plot(*zip(a + 0.45 * n, b + 0.45 * n), color=S.BLUE, lw=1.6, zorder=3, solid_capstyle="round")
    ax.plot(*zip(a - 0.45 * n, b - 0.45 * n), color=S.ORANGE, lw=1.4, ls=(0, (1, 1.6)), zorder=3)
m = 0.5 * (P(rg, lons[0]) + P(rg, lons[1]))
ax.text(m[0] + 2.9, m[1] - 2.9, f"backbone ring link\n{isl_chord(N)/1e3:,.0f} km · {isl_chord(N)/C_LIGHT*1e3:.0f} ms".replace(",", " "),
        ha="center", va="center", rotation=45, fontsize=7.6, color=S.INK2, linespacing=1.15)
# Earth (orthographic, north pole at the centre)
ins = ax.inset_axes([-re, -re, 2 * re, 2 * re], transform=ax.transData, zorder=4)
bm = Basemap(projection="ortho", lat_0=90, lon_0=LON0 - 180, resolution="c", ax=ins)
bm.drawmapboundary(fill_color="#eaf1fa", linewidth=0.6, color=S.INK2)
bm.fillcontinents(color="#cfd6d0", lake_color="#eaf1fa"); bm.drawcoastlines(linewidth=0.25, color=S.INK2)
ins.axis("off")
# LEO relay planes (near-polar orbits seen edge-on) and relays
ax.add_patch(Circle((0, 0), rl, fill=False, ec=S.INK2, lw=0.5, ls=(0, (2, 2)), zorder=5))
relays = [("R1", 20.0, "T"), ("R2", 150.0, "C"), ("R3", -95.0, "T")]
for name, lon, typ in relays:
    p = P(rl, lon)
    vis = [l for l in lons if abs((l - lon + 180) % 360 - 180) < 100.8]
    for l in vis:
        b = P(rg, l); d = (b - p) / np.linalg.norm(b - p); n = np.array([-d[1], d[0]])
        ax.plot(*zip(p + 0.3 * n, b + 0.3 * n), color=S.BLUE, lw=1.0, zorder=3)
        ax.plot(*zip(p - 0.3 * n, b - 0.3 * n), color=S.ORANGE, lw=1.0, ls=(0, (1, 1.8)), zorder=3)
    ax.plot(*p, marker="o", ms=5.5, mfc=S.PURPLE if typ == "T" else "white", mec=S.PURPLE, mew=1.2, zorder=7)
    q = P(rl + 3.3, lon)
    ax.text(q[0], q[1], f"{name} ({typ})", ha="center", va="center", fontsize=7.6, zorder=8,
            bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
# ground area X and the nodes it can see
lonX, latX = 35.05, 48.46
pX = P(re * np.cos(np.radians(latX)), lonX)
ax.plot(*pX, marker="*", ms=9, mfc=S.RED, mec="white", mew=0.6, zorder=9)
# GEO nodes
for i, lon in enumerate(lons):
    p = P(rg, lon)
    seen = np.cos(np.radians(latX)) * np.cos(np.radians(lon - lonX)) >= R_E / R_GEO
    ax.plot(*p, marker="s", ms=12, mfc=S.BLUE, mec=S.RED if seen else S.GREEN, mew=2.0, zorder=8)
    lab = f"B{i+1}\n{abs(lon):.0f}° {'E' if lon >= 0 else 'W'}"
    q = P(rg + 6.3, lon)
    ax.text(q[0], q[1], lab, ha="center", va="center", fontsize=9, fontweight="bold", linespacing=1.1)
ax.text(*P(rg * 0.52, lons[0] + 13), f"zone seen\nabove 20°:\n±{psi:.1f}°", fontsize=7.6, color=S.BLUE, ha="center", va="center", linespacing=1.1)
q = P(rg * 0.60, 20 - 45 + 11)
ax.text(*P(rg * 0.57, -33), "relay–backbone link\n35 286–43 968 km\n118–147 ms", fontsize=7.6, color=S.INK2, ha="center", va="center", linespacing=1.15)
ax.text(*P(rg + 1.0, lons[0] - 28), "geostationary ring, r = 42 164 km", fontsize=7.6, color=S.INK2, rotation=-28, ha="center", va="bottom")
# legend
h = [Line2D([], [], marker="s", ls="", ms=8, mfc=S.BLUE, mec=S.BLUE, label="backbone node B1–B4 (GEO)"),
     Line2D([], [], marker="o", ls="", ms=5.5, mfc=S.PURPLE, mec=S.PURPLE, label="relay, type T: trusted QKD node (LEO)"),
     Line2D([], [], marker="o", ls="", ms=5.5, mfc="white", mec=S.PURPLE, mew=1.2, label="relay, type C: ciphertext only (LEO)"),
     Line2D([], [], color=S.BLUE, lw=1.6, label="encrypted user-data channel (FSO)"),
     Line2D([], [], color=S.ORANGE, lw=1.4, ls=(0, (1, 1.6)), label="authenticated service channel"),
     Line2D([], [], marker="*", ls="", ms=9, mfc=S.RED, mec="white", label="ground area X (48.5° N, 35° E)"),
     Line2D([], [], marker="s", ls="", ms=8, mfc="white", mec=S.RED, mew=2, label="node above the horizon of X"),
     Line2D([], [], marker="s", ls="", ms=8, mfc="white", mec=S.GREEN, mew=2, label="node below the horizon of X")]
leg = ax.legend(handles=h, loc="lower left", bbox_to_anchor=(0.005, 0.005), fontsize=7.4, handlelength=2.0, labelspacing=0.42, borderpad=0.3)
# detail near the Earth (not to scale)
dx = fig.add_axes([0.685, 0.012, 0.305, 0.235]); dx.set_xlim(0, 10); dx.set_ylim(0, 10); dx.axis("off")
dx.add_patch(FancyBboxPatch((0.1, 0.1), 9.8, 9.8, boxstyle="round,pad=0,rounding_size=0.3", fc=S.PANEL, ec=S.GRID, lw=0.8))
dx.text(0.5, 9.3, "Detail near the Earth (not to scale)", fontsize=7.4, fontweight="bold", va="center")
th = np.linspace(np.radians(55), np.radians(125), 50)
dx.fill_between(5 + 13 * np.cos(th), -10.6 + 13 * np.sin(th), 0.1, color="#cfd6d0", lw=0, zorder=1)
dx.plot(5 + 14.2 * np.cos(th), -10.6 + 14.2 * np.sin(th), color="#dfe9f5", lw=5, zorder=1)
gs, rt, rc = (2.7, 2.2), (4.0, 6.2), (7.6, 6.0)
dx.plot(*zip(gs, rt), color=S.PURPLE, lw=1.5, ls=(0, (3, 2)), zorder=3)
dx.plot(*zip((gs[0] + 0.35, gs[1]), (rt[0] + 0.35, rt[1])), color=S.ORANGE, lw=1.2, ls=(0, (1, 1.6)), zorder=3)
dx.plot(*zip((6.9, 2.0), rc), color=S.BLUE, lw=1.5, zorder=3)
dx.plot(*zip(rt, rc), color=S.BLUE, lw=1.5, zorder=3)
for p in (rt, rc):
    dx.annotate("", xy=(p[0] + 0.45, 8.55), xytext=p, arrowprops=dict(arrowstyle="-|>", color=S.BLUE, lw=1.1), zorder=3)
dx.plot(*rt, marker="o", ms=6, mfc=S.PURPLE, mec=S.PURPLE, zorder=5); dx.plot(*rc, marker="o", ms=6, mfc="white", mec=S.PURPLE, mew=1.2, zorder=5)
dx.plot(*gs, marker="^", ms=7, mfc=S.INK2, mec=S.INK2, zorder=5); dx.plot(6.9, 2.0, marker="^", ms=7, mfc=S.INK2, mec=S.INK2, zorder=5)
dx.text(rt[0] - 0.4, rt[1] + 0.1, "T", fontsize=7.6, ha="right", va="center"); dx.text(rc[0] + 0.45, rc[1] - 0.1, "C", fontsize=7.6, va="center")
dx.text(6.35, 7.75, "to backbone\n(GEO)", fontsize=7.0, color=S.INK2, ha="center", va="center", linespacing=1.05)
dx.text(0.45, 4.3, "quantum\nchannel\n500–1193 km", fontsize=6.9, color=S.PURPLE, va="center", linespacing=1.1)
dx.text(2.7, 1.05, "station A", fontsize=7.2, ha="center"); dx.text(6.9, 0.85, "station B", fontsize=7.2, ha="center")
fig.savefig(out, dpi=300)
