"""Type 5. Multi-level governance map with typed links (Figure 5)."""
from __future__ import annotations

from matplotlib.lines import Line2D

from .. import style as S

TITLE = "Multi-level governance map"
NAME = "fig5_governance_map"

OX, OY = 0.55, 0.25      # origin of the layout grid (inches)
BAND, BAND_GAP = 0.86, 0.22
NODE_H = 0.5
FS = 8.6

LINK = {
    #             colour            lw    linestyle             arrow  legend
    "statutory":      ("#444444",    1.5, "-",                  True,  "statutory or operational link (arrow = direction)"),
    "conditionality": (S.PROV["EC"], 2.6, "-",                  True,  "conditionality, Reg. (EU) 2024/792 [L]"),
    "weak":           ("#E9A100",    1.8, (0, (5, 3)),          False, "weak or partial coordination"),
    "unstable":       ("#E04848",    1.8, (0, (6, 2, 1.5, 2)),  False, "unstable safeguard [L]"),
    "missing":        ("#E04848",    1.8, (0, (1.2, 2.2)),      False, "missing link (×)"),
    "data":           ("#E04848",    2.4, (0, (0.6, 3.2)),      False, "limited data integration [EC]"),
}
LAYER_FC = ["#EEEBFB", "#E5EFFC", "#E3F4EE", "#F1F0EC", "#F1F0EC"]


def _layer_y(i):
    return OY + i * (BAND + BAND_GAP)


def draw(d):
    g = d["governance"]
    layers = {l["id"]: l for l in g["layers"]}
    W = 11.3
    H = _layer_y(len(g["layers"])) + 0.6
    fig, ax = S.new_figure(W, H)

    dig_nodes = [n for n in g["nodes"] if n.get("digital")]
    main_right = OX + max(n["x"] + n["w"] / 2 for n in g["nodes"] if not n.get("digital")) + 0.25
    for i, l in enumerate(g["layers"]):
        y = _layer_y(l["y"])
        S.box(ax, OX - 0.3, y, main_right - OX + 0.3, BAND, fc=LAYER_FC[i % len(LAYER_FC)], ec="none", r=0.08, z=0)
        ax.text(OX - 0.42, y + BAND / 2, l["name"], rotation=90, ha="center", va="center",
                fontsize=8.6, fontweight="bold", color=S.MUTED, linespacing=1.05)
    if dig_nodes:
        dl = g.get("digital_layer", {"name": "Digital layer", "from": 1, "to": 3})
        x0 = OX + min(n["x"] - n["w"] / 2 for n in dig_nodes) - 0.18
        x1 = OX + max(n["x"] + n["w"] / 2 for n in dig_nodes) + 0.18
        y0 = _layer_y(dl["from"]) - 0.12
        y1 = _layer_y(dl["to"]) + BAND
        S.box(ax, x0, y0, x1 - x0, y1 - y0, fc="#FDF5E3", ec="none", r=0.08, z=0)
        ax.text((x0 + x1) / 2, y0 + 0.1, dl["name"], ha="center", va="center", fontsize=8.6,
                fontweight="bold", color=S.MUTED)

    # nodes
    pos = {}
    for n in g["nodes"]:
        li = layers[n["layer"]]["y"]
        cx = OX + n["x"]
        cy = _layer_y(li) + BAND / 2 + (0.06 if n.get("digital") else 0)
        x0, y0 = cx - n["w"] / 2, cy - NODE_H / 2
        key = n.get("key")
        S.box(ax, x0, y0, n["w"], NODE_H, fc="white", ec=S.INK if key else "#C2C0B7", lw=1.8 if key else 1.3,
              r=0.06, z=4)
        ax.text(cx, cy, n["label"], ha="center", va="center", fontsize=FS, fontweight="bold" if key else "normal",
                linespacing=1.15, zorder=5)
        pos[n["id"]] = (x0, y0, x0 + n["w"], y0 + NODE_H, li)

    # notes attached to nodes (e.g. weak horizontal cooperation inside the ministries block)
    for nt in g.get("notes", []):
        x0, y0, x1, y1, _ = pos[nt["node"]]
        c, lw, ls = LINK[nt["type"]][:3]
        tw = S.text_size(fig, nt["label"], 7.8, style="italic")[0] + 0.12
        bx = (x0 + x1) / 2 - tw / 2
        by = y1 + 0.02 if nt.get("side", "bottom") == "bottom" else y0 - 0.22
        S.box(ax, bx, by, tw, 0.2, fc="white", ec=c, lw=1.4, ls=ls, r=0.02, z=6)
        ax.text(bx + tw / 2, by + 0.1, nt["label"], ha="center", va="center", fontsize=7.8, style="italic", zorder=7)

    # edges
    for e in g["edges"]:
        c, lw, ls, head, _ = LINK[e["type"]]
        a, b = pos[e["from"]], pos[e["to"]]
        if e.get("route") == "direct":
            pts, lab_at, lab_side = _direct(a, b, e.get("label_t", 0.5))
        else:
            pts, lab_at, lab_side = _route(a, b, e.get("label_t", 0.5))
        lab_side = e.get("label_side", lab_side)
        if e.get("label_pos") == "below":
            lab_side = "below"
        if head:
            S.polyline(ax, pts, color=c, lw=lw, ls=ls, head=True, z=3)
        else:
            xs, ys = [p[0] for p in pts], [p[1] for p in pts]
            ax.plot(xs, ys, color=c, lw=lw, ls=ls, zorder=3, dash_capstyle="round" if e["type"] == "data" else "butt")
        if e["type"] == "missing":
            mx, my = pts[0][0] + (pts[-1][0] - pts[0][0]) * 0.5, pts[0][1] + (pts[-1][1] - pts[0][1]) * 0.5
            k = 0.055
            ax.plot([mx - k, mx + k], [my - k, my + k], color=c, lw=1.6, zorder=6)
            ax.plot([mx - k, mx + k], [my + k, my - k], color=c, lw=1.6, zorder=6)
        if e.get("label"):
            lx, ly = lab_at
            bbox = dict(boxstyle="square,pad=0.08", fc="white", ec="none", alpha=0.9)
            kw = dict(fontsize=7.8, linespacing=1.1, zorder=6, bbox=bbox)
            if lab_side == "right":
                ax.text(lx + 0.09, ly, e["label"], ha="left", va="center", **kw)
            elif lab_side == "left":
                ax.text(lx - 0.09, ly, e["label"], ha="right", va="center", **kw)
            elif lab_side == "below":
                ax.text(lx, ly + 0.36, e["label"], ha="center", va="top", **kw)
            else:
                ax.text(lx, ly - 0.08, e["label"], ha="center", va="bottom", **kw)

    # legend
    handles = [Line2D([], [], color=c, lw=lw, ls=ls, label=lab) for c, lw, ls, _, lab in LINK.values()]
    ax.legend(handles=handles, loc="lower left", bbox_to_anchor=(0.02, 0.0), ncol=3, frameon=False,
              fontsize=8, handlelength=3.2, columnspacing=2.2, borderaxespad=0.3)
    return fig


def _route(a, b, t=0.5):
    """Orthogonal route between two node boxes; returns points, label anchor, label side."""
    ax0, ay0, ax1, ay1, al = a
    bx0, by0, bx1, by1, bl = b
    if al == bl:  # same layer: horizontal
        y = (ay0 + ay1) / 2
        if ax1 <= bx0:
            p0, p1 = (ax1, y), (bx0, y)
        else:
            p0, p1 = (ax0, y), (bx1, y)
        return [p0, p1], ((p0[0] + p1[0]) / 2, y), "top"
    lo, hi = max(ax0, bx0), min(ax1, bx1)
    down = al < bl
    if hi - lo > 0.15:  # overlapping columns: straight vertical
        x = (lo + hi) / 2
        p0 = (x, ay1 if down else ay0)
        p1 = (x, by0 if down else by1)
        return [p0, p1], (x, p0[1] + (p1[1] - p0[1]) * t), "right"
    # elbow: leave sideways, run vertically in the gap, enter the target from its side
    ya = (ay0 + ay1) / 2
    yb = (by0 + by1) / 2
    if ax1 <= bx0:
        xa, xb = ax1, bx0
    else:
        xa, xb = ax0, bx1
    xm = xb + (0.45 if xa > xb else -0.45)
    if (xa > xb and xm > xa - 0.1) or (xa < xb and xm < xa + 0.1):
        xm = (xa + xb) / 2
    pts = [(xa, ya), (xm, ya), (xm, yb), (xb, yb)]
    return pts, (xm, ya + (yb - ya) * t), "right"


def _clip(box, cx, cy, tx, ty):
    """Point where the segment from the box centre towards (tx, ty) leaves the box."""
    x0, y0, x1, y1 = box[:4]
    dx, dy = tx - cx, ty - cy
    ts = []
    if dx:
        ts += [(x0 - cx) / dx, (x1 - cx) / dx]
    if dy:
        ts += [(y0 - cy) / dy, (y1 - cy) / dy]
    t = min(t for t in ts if t > 0)
    return cx + dx * t, cy + dy * t


def _direct(a, b, t=0.5):
    """Straight (diagonal) link between box borders."""
    ca = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    cb = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    if b[0] >= a[2]:      # target to the right: leave from the right edge
        p0 = (a[2], ca[1])
    elif b[2] <= a[0]:
        p0 = (a[0], ca[1])
    else:
        p0 = _clip(a, ca[0], ca[1], cb[0], cb[1])
    p1 = _clip(b, cb[0], cb[1], p0[0], p0[1])
    return [p0, p1], (p0[0] + (p1[0] - p0[0]) * t, p0[1] + (p1[1] - p0[1]) * t), "right"
