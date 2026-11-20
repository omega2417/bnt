"""Type 7. Ishikawa (fishbone) diagram of causes grouped by mechanism type (Figure 7)."""
from __future__ import annotations

from .. import style as S

TITLE = "Ishikawa (fishbone) diagram"
NAME = "fig7_fishbone"

LAYOUT = (("institutional", 0, -1), ("legal", 1, -1), ("financial", 0, 1), ("procedural", 1, 1))


def draw(d):
    fb = d["fishbone"]
    names = d["mechanisms"]
    W, H = 10.4, 5.8
    fig, ax = S.new_figure(W, H)
    spine_y = H / 2
    sx0, sx1 = 1.2, 8.45
    S.arrow(ax, (sx0, spine_y), (sx1, spine_y), color="#111111", lw=2.4, mutation=16)

    # effect box
    ex, ew, eh = 8.5, 1.8, 1.0
    S.box(ax, ex, spine_y - eh / 2, ew, eh, fc="#E04848", ec="#E04848", r=0.08)
    ax.text(ex + ew / 2, spine_y - 0.3, "EFFECT", ha="center", va="center", color="white", fontsize=8, fontweight="bold")
    ax.text(ex + ew / 2, spine_y + 0.1, S.wrap(fig, fb["effect"], ew - 0.2, 9.4, "bold"), ha="center", va="center",
            color="white", fontsize=9.4, fontweight="bold", linespacing=1.15)

    bone_len = spine_y - 0.6
    dx = 1.35                    # horizontal run of each bone
    joints = (4.6, 8.2)          # where the bones meet the spine
    for key, col, side in LAYOUT:
        if key not in fb["causes"]:
            continue
        c = S.MECH[key]
        jx = joints[col]
        tx, ty = jx - dx, spine_y + side * bone_len
        ax.plot([jx, tx], [spine_y, ty], color=c, lw=3, solid_capstyle="round", zorder=3)
        lab = names[key]
        lw_ = S.text_size(fig, lab, 10.5, "bold")[0] + 0.24
        ly = ty + side * 0.27
        S.box(ax, tx - lw_ / 2, ly - 0.17, lw_, 0.34, fc="white", ec=c, lw=2, r=0.05, z=5)
        ax.text(tx, ly, lab, ha="center", va="center", fontsize=10.5, fontweight="bold", zorder=6)
        causes = fb["causes"][key]
        n = len(causes)
        for i, cause in enumerate(causes):
            f = (n - i) / (n + 1.0) if side < 0 else (i + 1) / (n + 1.0)
            px = jx + (tx - jx) * f
            py = spine_y + (ty - spine_y) * f
            ax.plot([px - 0.55, px], [py, py], color=c, lw=1.3, zorder=3)
            ax.plot(px, py, marker="o", ms=5, mfc=c, mec=c, zorder=4)
            ax.text(px - 0.6, py, S.wrap(fig, cause, 2.1, 8.6), ha="right", va="center", fontsize=8.6,
                    linespacing=1.15, zorder=4)
    return fig
