"""Type 1. Research design: sources -> analytical stages -> outputs (Figure 1)."""
from __future__ import annotations

from .. import style as S

TITLE = "Research design flow"
NAME = "fig1_research_design"


def draw(d):
    ds = d["design"]
    W, H = 9.6, 5.6
    fig, ax = S.new_figure(W, H)

    xs0, xs1 = 0.12, 3.05       # sources column
    xm0, xm1 = 3.45, 6.45       # stages column
    xo0, xo1 = 6.8, 9.48       # outputs column
    top = 0.42

    for x, t in ((xs0, "Sources (Section 2.2)"), (xm0, "Analysis (Sections 2.3–2.4)"), (xo0, "Outputs")):
        ax.text(x, 0.2, t, fontsize=10.5, fontweight="bold", color=S.MUTED, va="center")

    # --- sources
    n = len(ds["sources"])
    sh, sg = 0.86, 0.1
    src = []
    for i, s in enumerate(ds["sources"]):
        y = top + i * (sh + sg)
        S.box(ax, xs0, y, xs1 - xs0, sh, ec="#CFCDC4", lw=1.3)
        tx = xs0 + 0.55
        if s.get("tag"):
            S.tag_chip(ax, xs0 + 0.28, y + sh / 2, s["tag"], size=8)
        ax.text(tx, y + sh / 2, S.wrap(fig, s["text"], xs1 - tx - 0.1, 8.4), fontsize=8.4,
                va="center", linespacing=1.3)
        src.append((y, s))

    # --- stages
    mh, mg = 0.98, 0.32
    stage_y = []
    for j, st in enumerate(ds["stages"]):
        y = top + j * (mh + mg)
        stage_y.append(y)
        S.box(ax, xm0, y, xm1 - xm0, mh, fc="#EEF4FD", ec=S.PROV["L"], lw=1.8)
        ax.text(xm0 + 0.18, y + 0.27, st["title"], fontsize=10, fontweight="bold", va="center")
        ax.text(xm0 + 0.18, y + 0.66, S.wrap(fig, st["text"], xm1 - xm0 - 0.36, 8.6),
                fontsize=8.6, va="center", linespacing=1.3)
        if j:
            S.arrow(ax, ((xm0 + xm1) / 2, stage_y[j - 1] + mh), ((xm0 + xm1) / 2, y), color="#444444", lw=1.6)

    # --- source -> stage links (fan in, spread on the stage edge)
    incoming = {}
    for y, s in src:
        for t in s["to"]:
            if t != "discussion":
                incoming.setdefault(int(t), []).append(y)
    for t, ys in incoming.items():
        y0 = stage_y[t - 1]
        for k, ysrc in enumerate(ys):
            ytgt = y0 + mh * (0.35 + 0.3 * (k / max(1, len(ys) - 1) if len(ys) > 1 else 0.5))
            S.arrow(ax, (xs1, ysrc + sh / 2), (xm0, ytgt), color="#C9C7BE", lw=1.3)

    # --- outputs
    oh = 0.52
    for j, o in enumerate(ds["outputs"]):
        cy = stage_y[j] + mh / 2
        S.box(ax, xo0, cy - oh / 2, xo1 - xo0, oh, ec="#CFCDC4", lw=1.3)
        cx = xo0 + 0.25
        for t in o["tags"]:
            w = S.tag_chip(ax, cx, cy, t, size=8)
            cx += w + 0.08
        ax.text(cx + 0.02, cy, o["text"], fontsize=9.2, fontweight="bold", va="center")
        S.arrow(ax, (xm1, cy), (xo0, cy), color="#444444", lw=1.6)

    # --- discussion (literature only)
    dy = stage_y[-1] + mh + 0.42
    S.box(ax, xo0, dy - oh / 2, xo1 - xo0, oh, ec="#CFCDC4", lw=1.3)
    ax.text(xo0 + 0.15, dy, ds["discussion"], fontsize=9.2, fontweight="bold", va="center")
    last_out = stage_y[-1] + mh / 2 + oh / 2
    S.arrow(ax, ((xo0 + xo1) / 2, last_out), ((xo0 + xo1) / 2, dy - oh / 2), color="#444444", lw=1.6)
    lit_y = src[-1][0] + sh * 0.75
    S.polyline(ax, [(xs1, lit_y), (xs1 + 0.22, lit_y), (xs1 + 0.22, dy), (xo0, dy)], color="#C9C7BE", lw=1.3)

    # --- validation band
    vy = H - 0.62
    S.box(ax, xs0, vy, xo1 - xs0, 0.5, fc="#FFF8E8", ec="#E9A100", lw=1.5)
    ax.text(xs0 + 0.22, vy + 0.25, S.wrap(fig, ds["validation"], xo1 - xs0 - 0.4, 8.6),
            fontsize=8.6, va="center", linespacing=1.3)
    return fig
