"""Type 3. Dumbbell chart of the Commission's ordinal ratings, 2025 -> 2026 (Figure 3)."""
from __future__ import annotations

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from .. import style as S

TITLE = "Commission ratings 2025 → 2026 (dumbbell)"
NAME = "fig3_ec_dumbbell"


def draw(d, years=(2025, 2026)):
    areas = sorted(d["areas"], key=lambda a: a["chapter"])
    scale = d["ec_scale"]
    y0, y1 = years
    W = 10.6
    row = 0.44
    top = 0.95
    H = top + row * len(areas) + 0.62
    fig, ax = S.new_figure(W, H)

    X0, X1 = 3.75, 7.3
    step = (X1 - X0) / (len(scale) - 1 + 0.5)

    def x(level):
        return X0 + 0.22 + (level - 1) * step

    bottom = top + row * len(areas) - 0.1
    # half-step band(s) actually used
    halves = sorted({r["level"] for a in areas for r in a["ec"].values() if r["level"] != int(r["level"])})
    for h in halves:
        ax.add_patch(Rectangle((x(h - 0.5), top - 0.25), x(h + 0.5) - x(h - 0.5), bottom - top + 0.25,
                               fc=S.PANEL, ec="none", zorder=0))
        ax.plot([x(h)] * 2, [top - 0.05, bottom], color=S.FAINT, lw=0.8, ls=(0, (2, 2)), zorder=1)
        lo, hi = scale[int(h) - 1].split()[0], scale[int(h)].split()[0]
        if hi.endswith("ly"):
            hi = hi[:-2]
        ax.text(x(h), top - 0.36, "between %s and\na %s level" % (lo, hi),
                ha="center", va="center", fontsize=7.2, color=S.MUTED, linespacing=1.1,
                bbox=dict(boxstyle="square,pad=0.1", fc=S.PANEL, ec="none"))
    for i, lab in enumerate(scale):
        xv = x(i + 1)
        ax.plot([xv, xv], [top - 0.25, bottom], color="#E3E1DA", lw=0.9, zorder=0)
        txt = lab[0].upper() + lab[1:]
        txt = txt.replace(" of preparation", "\nof preparation").replace(" stage", "\nstage") \
                 .replace("ly prepared", "ly\nprepared").replace("Well advanced", "Well\nadvanced")
        if txt.count("\n") > 1:
            txt = txt.replace("\n", " ", 1)
        ax.text(xv, bottom + 0.32, txt, ha="center", va="center", fontsize=8, color=S.MUTED, linespacing=1.15)
    ax.plot([X0, X1], [bottom, bottom], color=S.FAINT, lw=1)

    for i, a in enumerate(areas):
        y = top + row * i + row / 2 - 0.12
        ax.text(X0 - 0.1, y, "Ch. %d  %s" % (a["chapter"], a["name"]), ha="right", va="center", fontsize=9)
        r0, r1 = a["ec"].get(y0), a["ec"].get(y1)
        l0, l1 = r0["level"], r1["level"]
        if l1 != l0:
            S.arrow(ax, (x(l0) + 0.09, y), (x(l1) - 0.07, y), color="#444444", lw=1.5)
        ax.plot(x(l0), y, marker="o", ms=10, mfc="white", mec="#444444", mew=2, zorder=5)
        ax.plot(x(l1), y, marker="o", ms=6.5, mfc=S.PROV["EC"], mec="white", mew=1, zorder=6)
        if l1 > l0:
            head = "↑ rating raised"
        elif l1 < l0:
            head = "↓ rating lowered"
        else:
            head = "= unchanged"
        ax.text(X1 + 0.15, y - 0.08, head, fontsize=9, fontweight="bold", va="center")
        ax.text(X1 + 0.15, y + 0.1, "%d: %s; %d: %s" % (y0, r0.get("progress", "progress not stated"),
                                                        y1, r1.get("progress", "progress not stated")),
                fontsize=7.8, color=S.MUTED, va="center")

    S.tag_chip(ax, X1 + 0.27, 0.2, "EC", size=7.5)
    ax.text(X1 + 0.45, 0.2, "chapter-level ratings, not specific to recovery", fontsize=8, va="center", color=S.MUTED)
    handles = [
        Line2D([], [], marker="o", ls="none", mfc="white", mec="#444444", mew=2, ms=9, label="Ukraine %d Report" % y0),
        Line2D([], [], marker="o", ls="none", mfc=S.PROV["EC"], mec="white", ms=7, label="Ukraine %d Report" % y1),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(X0 / W, 1.0), ncol=2, frameon=False,
              fontsize=8.6, handletextpad=0.3, columnspacing=1.6, borderaxespad=0.15)
    return fig
