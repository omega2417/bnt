"""Type 4. Compliance matrix of criteria C1-C4 with the resulting rating (Figure 4)."""
from __future__ import annotations

from matplotlib.patches import Wedge, Circle

from .. import style as S
from ..data import CRITERIA

TITLE = "Compliance matrix C1–C4 (heatmap + status)"
NAME = "fig4_compliance_matrix"

ORDER = ("procurement", "state_aid", "eia", "regional", "anticorruption")


def _icon(ax, x, y, rating, r=0.075):
    c = S.RATING[rating][0]
    if rating == "partly_aligned":           # half-filled circle
        ax.add_patch(Circle((x, y), r, fc="white", ec=c, lw=1.6, zorder=6))
        ax.add_patch(Wedge((x, y), r, 90, 270, fc=c, ec=c, lw=1.6, zorder=7))
    elif rating == "misaligned":             # cross
        k = r * 0.85
        ax.plot([x - k, x + k], [y - k, y + k], color=c, lw=1.8, zorder=7)
        ax.plot([x - k, x + k], [y + k, y - k], color=c, lw=1.8, zorder=7)
    else:                                    # tick
        ax.plot([x - r, x - r * 0.2, x + r], [y, y + r * 0.8, y - r * 0.9], color=c, lw=2, zorder=7)


def draw(d):
    by_id = {a["id"]: a for a in d["areas"]}
    areas = [by_id[i] for i in ORDER if i in by_id] + [a for a in d["areas"] if a["id"] not in ORDER]
    W = 9.75
    cw, ch, gx, gy = 1.36, 0.56, 0.08, 0.08
    X0, top = 2.3, 0.92
    H = top + len(areas) * (ch + gy) + 0.55
    fig, ax = S.new_figure(W, H)

    S.tag_chip(ax, 0.25, 0.22, "A", size=8)
    ax.text(0.45, 0.22, "Authors' assessment of the recovery-specific regime (criteria of Section 2.3)",
            fontsize=9.4, color=S.MUTED, va="center")

    cols = list(CRITERIA) + ["rating"]
    for j, c in enumerate(cols):
        cx = X0 + j * (cw + gx) + cw / 2
        if c == "rating":
            cx += 0.05
            ax.text(cx, top - 0.37, "Rating", ha="center", fontsize=10.5, fontweight="bold", va="center")
            ax.text(cx, top - 0.14, "overall", ha="center", fontsize=8.4, color=S.MUTED, va="center")
        else:
            ax.text(cx, top - 0.37, c, ha="center", fontsize=10.5, fontweight="bold", va="center")
            ax.text(cx, top - 0.14, d["criteria"][c], ha="center", fontsize=8.4, color=S.MUTED, va="center")

    for i, a in enumerate(areas):
        y = top + i * (ch + gy)
        ax.text(0.12, y + 0.2, S.wrap(fig, a["name"], X0 - 0.25, 9.4, "bold"), fontsize=9.4,
                fontweight="bold", va="center", linespacing=1.1)
        ax.text(0.12, y + ch - 0.07, "Chapter %d" % a["chapter"], fontsize=8.2, color=S.MUTED, va="center")
        au = a["authors"]
        for j, c in enumerate(CRITERIA):
            x = X0 + j * (cw + gx)
            cell = au[c]
            fc, tc, lab = S.STATE[cell["state"]]
            if cell["state"] == "na":
                S.box(ax, x, y, cw, ch, fc="white", ec="#C9C7BE", lw=1, r=0.04, hatch="////")
                ax.text(x + cw / 2, y + ch / 2, "n/a", ha="center", va="center", fontsize=8.6,
                        color=S.FAINT, fontweight="bold",
                        bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none"))
                continue
            S.box(ax, x, y, cw, ch, fc=fc, ec=fc, lw=0, r=0.04)
            note = cell.get("note")
            if note:
                ax.text(x + cw / 2, y + 0.17, lab, ha="center", va="center", fontsize=9, fontweight="bold", color=tc)
                ax.text(x + cw / 2, y + 0.39, S.wrap(fig, note, cw - 0.1, 7.4), ha="center", va="center",
                        fontsize=7.4, color=tc, linespacing=1.05)
            else:
                ax.text(x + cw / 2, y + ch / 2, lab, ha="center", va="center", fontsize=9, fontweight="bold", color=tc)
        x = X0 + 4 * (cw + gx) + 0.05
        rc, rl = S.RATING[au["rating"]]
        S.box(ax, x, y, cw + 0.1, ch, fc="white", ec=rc, lw=1.8, r=0.04)
        _icon(ax, x + 0.2, y + ch / 2, au["rating"])
        ax.text(x + 0.36, y + ch / 2, rl, va="center", fontsize=8.8, fontweight="bold", linespacing=1.05)

    # legend
    ly = H - 0.25
    ax.text(0.12, ly, "Scale:", fontsize=8.4, va="center", color=S.MUTED)
    lx = 0.75
    for key, lab in (("met", "met"), ("largely_met", "largely met"), ("met_in_form", "met in form / met but exposed"),
                     ("partly_met", "partly met"), ("not_met", "not met"), ("na", "n/a")):
        fc = S.STATE[key][0]
        S.box(ax, lx, ly - 0.08, 0.26, 0.16, fc=fc, ec="#C9C7BE" if key in ("na", "partly_met") else fc, lw=0.8,
              r=0.01, hatch="////" if key == "na" else None)
        ax.text(lx + 0.32, ly, lab, fontsize=8.2, va="center")
        lx += 0.42 + S.text_size(fig, lab, 8.2)[0] + 0.12
    return fig
