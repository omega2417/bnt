"""Type 6. Alluvial diagram: problem -> mechanism [P] -> accession track [A] (Figure 6)."""
from __future__ import annotations

import numpy as np

from .. import style as S

TITLE = "Alluvial diagram problem → mechanism → track"
NAME = "fig6_alluvial"

K = 0.74          # inches per unit of flow
NODE_W = 0.13


def _stack(order, sizes, top, gap):
    """Vertical positions of nodes stacked from ``top``."""
    pos, y = {}, top
    for key in order:
        pos[key] = [y, y + sizes[key] * K]
        y += sizes[key] * K + gap
    return pos


def _ribbon(ax, x0, x1, a0, a1, b0, b1, color):
    s = np.linspace(0, 1, 60)
    w = 3 * s ** 2 - 2 * s ** 3
    xs = x0 + (x1 - x0) * s
    top = a0 + (b0 - a0) * w
    bot = a1 + (b1 - a1) * w
    ax.fill_between(xs, top, bot, color=color, alpha=0.55, lw=0, zorder=2)
    ax.plot(xs, top, color="white", lw=0.5, zorder=2)


def draw(d):
    probs = d["problems"]
    mech_names = d["mechanisms"]
    tracks = d["tracks"]
    mech_order = [m for m in ("legal", "institutional", "financial", "procedural")
                  if any(m in p["mechanisms"] for p in probs)]
    track_order = [t for t in tracks if any(t in p["tracks"] for p in probs)]
    colors = {p["id"]: S.SERIES[i % len(S.SERIES)] for i, p in enumerate(probs)}

    # flows: (problem, mechanism, track, value)
    flows = []
    for p in probs:
        u = 1.0 / (len(p["mechanisms"]) * len(p["tracks"]))
        for m in p["mechanisms"]:
            for t in p["tracks"]:
                flows.append((p["id"], m, t, u))

    def total(idx, key):
        return sum(f[3] for f in flows if f[idx] == key)

    W, H = 9.6, 5.5
    fig, ax = S.new_figure(W, H)
    XP, XM, XT = 2.85, 5.0, 7.15
    top = 1.05
    pp = _stack([p["id"] for p in probs], {p["id"]: total(0, p["id"]) for p in probs}, top, 0.32)
    span = pp[probs[-1]["id"]][1] - top
    msz = {m: total(1, m) for m in mech_order}
    mgap = (span - sum(msz.values()) * K) / max(1, len(mech_order) - 1) if len(mech_order) > 1 else 0
    mp = _stack(mech_order, msz, top + 0.05, mgap)
    tsz = {t: total(2, t) for t in track_order}
    tgap = (span - sum(tsz.values()) * K) / max(1, len(track_order) - 1)
    tp = _stack(track_order, tsz, top, tgap)

    # running cursors on each side of each node
    cur = {}

    def take(side, key, base, v):
        y = cur.get((side, key), base)
        cur[(side, key)] = y + v * K
        return y, y + v * K

    pidx = {p["id"]: i for i, p in enumerate(probs)}
    # left segment: problem -> mechanism (problem side ordered by mechanism, mech side by problem)
    left = sorted(flows, key=lambda f: (pidx[f[0]], mech_order.index(f[1]), track_order.index(f[2])))
    seg_l = {}
    for f in left:
        seg_l[f] = take("p_out", f[0], pp[f[0]][0], f[3])
    for f in sorted(flows, key=lambda f: (mech_order.index(f[1]), pidx[f[0]], track_order.index(f[2]))):
        b = take("m_in", f[1], mp[f[1]][0], f[3])
        a = seg_l[f]
        _ribbon(ax, XP + NODE_W, XM, a[0], a[1], b[0], b[1], colors[f[0]])
    # right segment: mechanism -> track
    seg_r = {}
    for f in sorted(flows, key=lambda f: (mech_order.index(f[1]), track_order.index(f[2]), pidx[f[0]])):
        seg_r[f] = take("m_out", f[1], mp[f[1]][0], f[3])
    for f in sorted(flows, key=lambda f: (track_order.index(f[2]), mech_order.index(f[1]), pidx[f[0]])):
        b = take("t_in", f[2], tp[f[2]][0], f[3])
        a = seg_r[f]
        _ribbon(ax, XM + NODE_W, XT, a[0], a[1], b[0], b[1], colors[f[0]])

    def node(x, y0, y1):
        S.box(ax, x, y0, NODE_W, y1 - y0, fc="#111111", ec="#111111", lw=0, r=0.03, z=4)

    for p in probs:
        y0, y1 = pp[p["id"]]
        node(XP, y0, y1)
        cy = (y0 + y1) / 2
        S.box(ax, 0.1, cy - 0.21, 0.24, 0.24, fc=colors[p["id"]], ec=colors[p["id"]], lw=0, r=0.04)
        name = S.wrap(fig, p["name"], 2.25, 9.4, "bold")
        nl = name.count("\n") + 1
        ax.text(0.45, cy - 0.09 - 0.08 * (nl - 1), name, fontsize=9.4, fontweight="bold", va="center", linespacing=1.1)
        ax.text(0.45, cy + 0.12 + 0.08 * (nl - 1) + 0.08, S.wrap(fig, "Root cause: " + p["root_cause"], 2.25, 7.8),
                fontsize=7.8, color=S.MUTED, va="center", linespacing=1.1)
    for m in mech_order:
        y0, y1 = mp[m]
        node(XM, y0, y1)
        n = sum(1 for p in probs if m in p["mechanisms"])
        ax.text(XM + NODE_W / 2, y0 - 0.34, mech_names[m], ha="center", va="center", fontsize=9.6, fontweight="bold",
                zorder=6, bbox=dict(boxstyle="round,pad=0.12", fc="white", ec="none", alpha=0.85))
        ax.text(XM + NODE_W / 2, y0 - 0.14, "needed for %d of %d problems" % (n, len(probs)), ha="center",
                va="center", fontsize=7.8, color=S.MUTED, zorder=6,
                bbox=dict(boxstyle="round,pad=0.08", fc="white", ec="none", alpha=0.85))
    for t in track_order:
        y0, y1 = tp[t]
        node(XT, y0, y1)
        ax.text(XT + NODE_W + 0.12, (y0 + y1) / 2, S.wrap(fig, tracks[t], W - XT - 0.4, 9), va="center",
                fontsize=9, linespacing=1.15)

    for x, t in ((XP, "Problem\n(Table 2)"), (XM, "Mechanism of the\nproposed instrument [P]"),
                 (XT, "Accession track\nat risk [A]")):
        ax.text(x + NODE_W / 2, 0.32, t, ha="center", va="center", fontsize=9.4, fontweight="bold",
                color=S.MUTED, linespacing=1.1)
    ax.text(0.1, H - 0.22, "Ribbon width: each problem carries one unit, split equally over its mechanisms and "
            "tracks; multi-mechanism problems need synchronised instruments.", fontsize=7.8, color=S.MUTED, va="center")
    return fig
