"""Type 2. Swim-lane chronology with an axis break (Figure 2)."""
from __future__ import annotations

from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

from .. import style as S
from ..data import fmt_date, parse_date

TITLE = "Chronology with lanes and axis break"
NAME = "fig2_timeline"

W, H = 9.6, 7.2
X0, X1 = 1.75, 8.85      # plot area
GAP = 0.16                # width of the axis break
COMPRESS = 0.32           # inches per year before the break
LEVEL = 0.19              # vertical distance between label levels
FS = 7.6


def _mapper(t):
    start, brk, end = t["start"], t["break_year"], t["end"]
    pre = (brk - start) * COMPRESS
    post = (X1 - X0 - pre - GAP) / (end - brk)

    def x(year):
        if year <= brk:
            return X0 + (year - start) * COMPRESS
        return X0 + pre + GAP + (year - brk) * post
    return x, X0 + pre, X0 + pre + GAP


SLOTS = [1, -1, 2, -2, 3, -3, 4, -4, 5, -5, 6, -6]


def _greedy(items, widths, order, x_right):
    occupied = {}   # slot -> [(a, b)]
    leaders = {}    # slot -> [x] of events whose leader passes this slot

    def ok(slot, a, b, x):
        if any(not (b + 0.06 < p or a - 0.06 > q) for p, q in occupied.get(slot, [])):
            return False                       # label overlaps a label
        if any(a - 0.03 <= lx <= b + 0.03 for lx in leaders.get(slot, [])):
            return False                       # label covers someone's leader
        step = 1 if slot > 0 else -1
        for s_ in range(step, slot, step):     # own leader crosses a lower label
            if any(p - 0.03 <= x <= q + 0.03 for p, q in occupied.get(s_, [])):
                return False
        return True

    res, fails, cost = {}, 0, 0
    for k in [i for i, it in enumerate(items) if "slot" in it]:
        it = items[k]
        a = min(it["x"], x_right - widths[k])
        res[k] = (it["slot"], a, a + widths[k])
        occupied.setdefault(it["slot"], []).append(res[k][1:])
    for k in order:
        it, w = items[k], widths[k]
        x = it["x"]
        anchors = [x - 0.04] if x - 0.04 + w <= x_right else [x - w + 0.04]
        chosen = None
        for slot in SLOTS:
            for a in anchors:
                if a >= X0 - 0.3 and ok(slot, a, a + w, x):
                    chosen = (slot, a, a + w)
                    break
            if chosen:
                break
        if not chosen:  # no clean place: first slot without label overlap
            fails += 1
            for slot in SLOTS:
                a = anchors[0]
                if all(a + w + 0.06 < p or a - 0.06 > q for p, q in occupied.get(slot, [])):
                    chosen = (slot, a, a + w)
                    break
            chosen = chosen or (SLOTS[-1], anchors[0], anchors[0] + w)
        res[k] = chosen
        occupied.setdefault(chosen[0], []).append(chosen[1:])
        step = 1 if chosen[0] > 0 else -1
        for s_ in range(step, chosen[0], step):
            leaders.setdefault(s_, []).append(x)
        cost += abs(chosen[0])
    return res, fails, cost


def _place(fig, items, x_right):
    """Collision-free placement of labels in levels above (-k) / below (+k) a lane.

    Several insertion orders are tried; the layout without crossings and with
    the lowest total level wins.  Deterministic for given data.
    """
    widths = [S.text_size(fig, it["text"], FS)[0] for it in items]
    ev = [i for i, it in enumerate(items) if "slot" not in it]
    over = [i for i in ev if items[i]["x"] - 0.04 + widths[i] > x_right]
    rtl = sorted(ev, key=lambda i: -items[i]["x"])
    ltr = sorted(ev, key=lambda i: items[i]["x"])
    orders = [rtl, ltr, [i for i in rtl if i not in over] + over,
              over + [i for i in rtl if i not in over], sorted(ev, key=lambda i: -widths[i])]
    best = None
    for order in orders:
        res, fails, cost = _greedy(items, widths, order, x_right)
        key = (fails, cost)
        if best is None or key < best[0]:
            best = (key, res)
    for k, (slot, a, b) in best[1].items():
        items[k].update(slot=slot, x0=a, x1=b)
    return items


def draw(d):
    t = d["timeline"]
    fig, ax = S.new_figure(W, H)
    x, brk0, brk1 = _mapper(t)
    lanes = t["lanes"]

    # ---- label placement per lane (x only), then stack lanes to fit the labels
    placed = {}
    for l in lanes:
        items = []
        for s_ in t.get("spans", []):
            if s_["lane"] == l["id"]:
                items.append({"x": x(parse_date(s_["from"])) + 0.05, "text": s_["label"], "slot": 1, "span": True})
        for e in t["events"]:
            if e["lane"] == l["id"]:
                items.append({"x": x(parse_date(e["date"])), "e": e,
                              "text": "%s  %s" % (fmt_date(e["date"], e.get("precision")), e["label"])})
        placed[l["id"]] = _place(fig, items, W - 0.05)
    lane_y = {}
    y = 0.85
    for l in lanes:
        slots = [it["slot"] for it in placed[l["id"]]] or [1]
        up = max([-s_ for s_ in slots if s_ < 0] or [0])
        down = max([s_ for s_ in slots if s_ > 0] or [0])
        y += up * LEVEL + 0.22
        lane_y[l["id"]] = y
        y += down * LEVEL + 0.3
    bottom = y + 0.25
    Ht = bottom + 0.42

    # martial law and cut-off
    ml = x(parse_date(t["martial_law_from"]))
    ax.add_patch(Rectangle((ml, 0.42), X1 - ml, bottom - 0.42, fc=S.PANEL, ec="none", zorder=0))
    ax.text((ml + X1) / 2 - 0.35, 0.6, t["martial_law_label"], ha="center", va="center",
            fontsize=8.2, fontweight="bold", color=S.MUTED)
    cut = x(parse_date(d["meta"]["cutoff"]))
    ax.plot([cut, cut], [0.42, bottom], color=S.INK, lw=1.1, ls=(0, (4, 3)), zorder=1)
    ax.text(cut + 0.04, 0.6, "Cut-off " + _long(d["meta"]["cutoff"]), fontsize=8.2,
            fontweight="bold", va="center")

    # year grid and axis
    years = list(range(t["start"], t["break_year"], 2)) + list(range(t["break_year"], int(t["end"]) + 1))
    for yv in range(t["start"], int(t["end"]) + 1):
        if t["start"] < yv != t["break_year"]:
            ax.plot([x(yv), x(yv)], [0.42, bottom], color="#E6E4DD", lw=0.7, zorder=0)
    ax.plot([X0, brk0], [bottom, bottom], color=S.FAINT, lw=1)
    ax.plot([brk1, X1], [bottom, bottom], color=S.FAINT, lw=1)
    for yv in years:
        ax.plot([x(yv)] * 2, [bottom, bottom + 0.05], color=S.FAINT, lw=1)
        ax.text(x(yv), bottom + 0.17, str(yv), ha="center", va="center", fontsize=8.2, color=S.MUTED)
    for dx in (brk0 - 0.03, brk1 - 0.06):
        ax.plot([dx, dx + 0.09], [bottom + 0.09, bottom - 0.09], color=S.MUTED, lw=1)
    ax.text((brk0 + brk1) / 2, bottom - 0.3, "scale\nchange", ha="center", va="center",
            fontsize=6.8, color=S.FAINT, linespacing=1.1)

    for l in lanes:
        y = lane_y[l["id"]]
        c = S.LANE.get(l["id"], S.SERIES[lanes.index(l) % len(S.SERIES)])
        ax.plot([X0, brk0], [y, y], color=c, lw=2.2, solid_capstyle="butt", zorder=2)
        ax.plot([brk1, X1], [y, y], color=c, lw=2.2, solid_capstyle="butt", zorder=2)
        ax.text(X0 - 0.15, y, S.wrap(fig, l["name"], 1.55, 9.2, "bold"), ha="right", va="center",
                fontsize=9.2, fontweight="bold", linespacing=1.15)
        for s_ in t.get("spans", []):
            if s_["lane"] != l["id"]:
                continue
            a = x(parse_date(s_["from"]))
            b = X1 if s_["to"] == "open" else x(parse_date(s_["to"]))
            ax.add_patch(Rectangle((a, y - 0.07), b - a, 0.14, fc=c, alpha=0.32, ec="none", zorder=1))
        for it in placed[l["id"]]:
            ly = y + it["slot"] * LEVEL + (0.03 if it["slot"] > 0 else -0.03)
            if it.get("span"):
                ax.text(it["x0"], ly, it["text"], fontsize=FS, va="center", style="italic", color=S.MUTED, zorder=6)
                continue
            e = it["e"]
            if abs(it["slot"]) > 1:
                y_end = ly - 0.07 if it["slot"] > 0 else ly + 0.07
                ax.plot([it["x"], it["x"]], [y, y_end], color="#B8B6AD", lw=0.7, zorder=3)
            ax.text(it["x0"], ly, it["text"], fontsize=FS, va="center", zorder=6)
            if e["tag"] == "EC":
                ax.plot(it["x"], y, marker="D", ms=6.2, mfc=S.PROV["EC"], mec="white", mew=1, zorder=5)
            elif l["id"] == "derogation":
                ax.plot(it["x"], y, marker="o", ms=7, mfc="white", mec=c, mew=1.8, zorder=5)
            else:
                ax.plot(it["x"], y, marker="o", ms=6.5, mfc=c, mec="white", mew=1, zorder=5)

    fig.set_size_inches(W, Ht)
    ax.set_ylim(Ht, 0)
    handles = [
        Line2D([], [], marker="o", ls="none", mfc="#444444", mec="white", ms=7, label="[L] legal act (colour = lane)"),
        Line2D([], [], marker="D", ls="none", mfc=S.PROV["EC"], mec="white", ms=6.5, label="[EC] Commission report"),
    ]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(X0 / W, 1.0), ncol=2, frameon=False,
              fontsize=8.4, handletextpad=0.3, columnspacing=1.6, borderaxespad=0.25)
    return fig


def _long(iso):
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    y, m, dd = iso.split("-")
    return "%d %s %s" % (int(dd), months[int(m) - 1], y)
