"""Type 8. Sequencing roadmap of reforms; phases are ordinal, not calendar-scaled (Figure 8)."""
from __future__ import annotations

from matplotlib.patches import Rectangle

from .. import style as S

TITLE = "Reform sequencing roadmap"
NAME = "fig8_roadmap"

FS = 8.6
ITEM = {
    "P":  ("#EEEDE9", "#444444", "[P] authors' proposal"),
    "L":  ("#BFD6F6", S.PROV["L"], "[L] legal act or statutory effect"),
    "EC": ("#FCE0D6", S.PROV["EC"], "[EC] Commission recommendation"),
    "A":  ("#DDF3EA", S.PROV["A"], "[A] authors' assessment"),
}


def _pack(items):
    """Assign items to sub-lanes so that boxes in one sub-lane never overlap."""
    lanes = []
    for it in items:
        for ln in lanes:
            if all(it["from"] >= o["to"] or it["to"] <= o["from"] for o in ln):
                ln.append(it)
                break
        else:
            lanes.append([it])
    return lanes


def draw(d):
    r = d["roadmap"]
    phases = r["phases"]
    W = 9.6
    fig, ax = S.new_figure(W, 6.0)
    PX0, PX1 = 2.0, W - 0.1
    PW = (PX1 - PX0) / len(phases)

    def x(f):
        return PX0 + f * PW

    lh = S.line_height(FS)
    y = 0.62
    rows_geom = []
    for row in r["rows"]:
        y0 = y
        for lane in _pack(row["items"]):
            lane_h = 0
            for it in lane:
                bx0, bx1 = x(it["from"]) + 0.07, x(it["to"]) - 0.07
                txt = S.wrap(fig, it["text"], bx1 - bx0 - 0.42, FS)
                h = (txt.count("\n") + 1) * lh + 0.17
                it["_geom"] = (bx0, bx1, txt, h)
                lane_h = max(lane_h, h)
            for it in lane:
                bx0, bx1, txt, h = it["_geom"]
                fc, ec, _ = ITEM[it["tag"]]
                S.box(ax, bx0, y + 0.06, bx1 - bx0, h, fc=fc, ec=ec, lw=1.6, r=0.04, z=4)
                ax.text(bx0 + 0.12, y + 0.06 + h / 2, txt, va="center", fontsize=FS, linespacing=1.15, zorder=5)
                ax.text(bx1 - 0.08, y + 0.15, "[%s]" % it["tag"], ha="right", va="center", fontsize=7,
                        fontweight="bold", color=ec, zorder=5)
            y += lane_h + 0.1
        ms = row.get("milestone")
        if ms:
            mx = x(ms["at"])
            ax.plot(mx, y + 0.12, marker="D", ms=7, mfc=S.PROV[ms["tag"]], mec="white", zorder=6)
            mt = S.wrap(fig, ms["text"], PX1 - mx - 0.25, FS, "bold")
            nl = mt.count("\n") + 1
            ax.text(mx + 0.14, y + 0.03, mt, va="top", fontsize=FS, fontweight="bold", zorder=6, linespacing=1.15)
            y += 0.12 + nl * lh + 0.06
        y += 0.1
        rows_geom.append((row, y0, y))

    bottom = y
    # phase panels (drawn under the items)
    for i, ph in enumerate(phases):
        shade = ["#F6F5F2", "#F0EFEB", "#E9E8E3"][min(i, 2)]
        ax.add_patch(Rectangle((x(i) + 0.03, 0.5), PW - 0.06, bottom - 0.5, fc=shade, ec="none", zorder=0))
        ax.text(x(i) + PW / 2, 0.27, ph, ha="center", va="center", fontsize=8.9, fontweight="bold")
        if i:
            S.arrow(ax, (x(i) - 0.07, 0.27), (x(i) + 0.07, 0.27), color="#555555", lw=1.2, mutation=8)
    ax.text(0.1, 0.25, r.get("note", ""), fontsize=7.8, style="italic", color=S.MUTED, va="center", linespacing=1.1)
    for i, (row, y0, y1) in enumerate(rows_geom):
        ax.text(0.12, (y0 + y1) / 2, S.wrap(fig, row["name"], PX0 - 0.25, 9.6, "bold"), va="center",
                fontsize=9.6, fontweight="bold", linespacing=1.1)
        if i < len(rows_geom) - 1:
            ax.plot([0.05, W - 0.05], [y1, y1], color="#C9C7BE", lw=0.9, zorder=1)

    # legend
    ly = bottom + 0.3
    lx = 0.12
    used = []
    for row in r["rows"]:
        for it in row["items"]:
            if it["tag"] not in used:
                used.append(it["tag"])
    for tag in [t for t in ("P", "L", "EC", "A") if t in used]:
        fc, ec, lab = ITEM[tag]
        S.box(ax, lx, ly - 0.09, 0.42, 0.18, fc=fc, ec=ec, lw=1.6, r=0.04)
        ax.text(lx + 0.55, ly, lab, va="center", fontsize=8.6)
        lx += 0.75 + S.text_size(fig, lab, 8.6)[0] + 0.35
    H = ly + 0.3
    fig.set_size_inches(W, H)
    ax.set_ylim(H, 0)
    return fig
