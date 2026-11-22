"""Diagrams: staged method, structural model, hierarchy, agent topology, sequence chart."""
from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from .. import levels as lv
from ..model import GOAL_NAMES
from .style import AXIS, GOAL_COLORS, INK, INK2, LEVEL_COLORS, LEVEL_TEXT, MUTED, SERIES, SURFACE


def _box(ax, x, y, w, h, title, sub="", fc="#ffffff", ec=AXIS, tc=INK, fs=9, lw=1.2, sub_fs=7.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.06",
                                fc=fc, ec=ec, lw=lw, zorder=3))
    ax.text(x + w / 2, y + h * (0.64 if sub else 0.5), title, ha="center", va="center",
            fontsize=fs, fontweight="bold", color=tc, zorder=4)
    if sub:
        ax.text(x + w / 2, y + h * 0.3, sub, ha="center", va="center", fontsize=sub_fs, color=INK2,
                zorder=4, wrap=True)


def _arrow(ax, p, q, label="", style="-", color=INK2, lw=1.4, rad=0.0, fs=7.5, off=(0, 0.08)):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=11, lw=lw, color=color,
                                 linestyle=style, connectionstyle=f"arc3,rad={rad}", zorder=2))
    if label:
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], label, ha="center", va="bottom",
                fontsize=fs, color=INK, zorder=5,
                bbox=dict(boxstyle="round,pad=0.15", fc=SURFACE, ec="none"))


def _canvas(w, h, xlim, ylim):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    return fig, ax


def method_stages():
    """Figure 1: seven stages of the method with the bus produced by each stage."""
    stages = [("1. Formation of\ninitial data", "projection, tuples,\nanchors, policy", "⟨T, X, Ξ, W, K, ϑ⟩"),
              ("2. Verification &\ncompleteness", "checks E1–E4,\nmask O, κ", "⟨O, κ⟩"),
              ("3. Level-consistent\nnormalization", "anchored map (4),\nlevels (1)", "M, Λ"),
              ("4. Non-compensatory\naggregation", "mean, cap, μ (5),\nenclosure (7)", "A"),
              ("5. Roll-up\nto goals", "mean & min (8)", "π_θ (G)"),
              ("6. Integral index &\nclassification", "R, R_min (9),\n[R_L, R_U] (10)", "R"),
              ("7. Robustness &\nreporting", "Dirichlet (11),\nMonte Carlo, trace", "P, report")]
    fig, ax = _canvas(13, 3.4, (0, 13.2), (0, 3.4))
    w, h, gap = 1.6, 1.6, 0.22
    for i, (t, s, bus) in enumerate(stages):
        x = 0.2 + i * (w + gap)
        _box(ax, x, 1.1, w, h, t, s, fc="#f3f7fd" if i not in (1,) else "#fdf2f1", fs=7.6, sub_fs=7)
        if i < len(stages) - 1:
            _arrow(ax, (x + w, 1.9), (x + w + gap, 1.9))
        ax.text(x + w / 2, 0.75, f"bus: {bus}", ha="center", fontsize=7.8, color=SERIES[0], fontweight="bold")
    ax.text(0.2, 3.15, "Φ: ⟨θ, X, Ξ, W, K, ϑ, ω, ρ⟩ ↦ ⟨R, λ(R), R_min, [R_L, R_U], π_θ, A-records, P-record⟩",
            fontsize=10, color=INK)
    _arrow(ax, (0.2 + 1 * (w + gap) + w / 2, 1.1), (0.2 + 1 * (w + gap) + w / 2, 0.25), "", color="#d03b3b")
    ax.text(0.2 + 1 * (w + gap) + w / 2 + 0.1, 0.15, "failure code E1–E4 → stop", fontsize=7.5, color="#d03b3b")
    return fig


def structural_model():
    """Figure 2: nine blocks B0-B8, control unit CU and nine buses."""
    fig, ax = _canvas(13, 5.6, (0, 13), (0, 5.6))
    pos = {"B0": (0.2, 2.2), "B1": (1.75, 2.2), "B2": (3.3, 2.2), "B3": (4.85, 2.2), "B4": (6.4, 2.2),
           "B5": (7.95, 2.2), "B6": (9.5, 2.2), "B8": (11.3, 2.2), "B7": (6.4, 0.35), "CU": (5.6, 4.35)}
    names = {"B0": "Input\ninterface", "B1": "Scenario &\nconfiguration", "B2": "Verification &\ncompleteness",
             "B3": "Normalizer", "B4": "Action\naggregator", "B5": "Goal\nroll-up", "B6": "Integral index\n& classifier",
             "B7": "Robustness\nanalyzer", "B8": "Report &\ntrace register", "CU": "Control unit"}
    w, h = 1.12, 1.05
    for b, (x, y) in pos.items():
        fc = "#fff8ea" if b == "CU" else ("#eef8f3" if b in ("B7",) else "#f3f7fd")
        _box(ax, x, y, w if b != "CU" else 1.8, h if b != "CU" else 0.8, b, names[b].replace("\n", " ") if b == "CU" else names[b],
             fc=fc, fs=9.5, sub_fs=6.8)
    chain = [("B0", "B1", "X"), ("B1", "B2", "Ξ, W, K"), ("B2", "B3", "O, κ"), ("B3", "B4", "M, Λ"),
             ("B4", "B5", "A"), ("B5", "B6", "G"), ("B6", "B8", "R")]
    for a, b, lab in chain:
        (xa, ya), (xb, yb) = pos[a], pos[b]
        _arrow(ax, (xa + w, ya + h / 2), (xb, yb + h / 2), lab, off=(0, 0.1), fs=7)
    x3, y3 = pos["B3"]; x7, y7 = pos["B7"]; x8, y8 = pos["B8"]; x2, y2 = pos["B2"]; x4, _ = pos["B4"]
    _arrow(ax, (x3 + w / 2, y3), (x7, y7 + h / 2), "M", style="--", rad=0.25, off=(-0.35, -0.1))
    _arrow(ax, (x7 + w, y7 + h / 2), (x8 + w / 2, y8), "P", style="--", rad=0.25, off=(0.2, -0.25))
    _arrow(ax, (x2 + w * 0.8, y2 + h), (x4 + w * 0.2, y2 + h), "O, κ → B4", rad=-0.35, off=(0, 0.35), color=MUTED)
    cx, cy = pos["CU"]
    for b, (x, y) in pos.items():
        if b == "CU":
            continue
        top = (x + w / 2, y + h) if b != "B7" else (x + w + 0.02, y + h * 0.9)
        ax.plot([cx + 0.9, top[0]], [cy, top[1]], ls=":", lw=0.9, color="#c98500", zorder=1)
    ax.text(cx + 2.0, cy + 0.4, "control bus C: start/stop, status OK | E1–E4, configuration version",
            fontsize=8, color="#8a5c00")
    return fig


def hierarchy(result):
    """Object -> goals -> basic actions -> metrics, colored by level for one result."""
    cfg = result.config
    acts = list(cfg.actions)
    n_m = cfg.n_metrics
    fig, ax = _canvas(13, 8.6, (0, 13), (-0.5, n_m + 0.5))
    ytot = n_m - 1
    # metrics
    ym, k = {}, 0
    for a in acts:
        for m in a.metrics:
            y = ytot - k
            ym[(a.code, m.code)] = y
            s = result.norm["M"][(a.code, m.code)]
            c = LEVEL_COLORS[lv.code(lv.level(s))] if s is not None else "#ffffff"
            ax.add_patch(FancyBboxPatch((8.2, y - 0.36), 0.55, 0.72, boxstyle="round,pad=0,rounding_size=0.08",
                                        fc=c, ec=AXIS if s is None else "none", lw=0.8, ls="--" if s is None else "-"))
            ax.text(8.47, y, "n.r." if s is None else f"{s:.2f}", ha="center", va="center", fontsize=6.3,
                    color=INK if s is None else LEVEL_TEXT[lv.code(lv.level(s))])
            ax.text(8.9, y, f"{m.code}{'*' if m.core else ''}  {m.name}", va="center", fontsize=6.8, color=INK2)
            k += 1
    # actions
    ya = {}
    for a in acts:
        ys = [ym[(a.code, m.code)] for m in a.metrics]
        y = sum(ys) / len(ys)
        ya[a.code] = y
        rec = result.A[a.code]
        c = LEVEL_COLORS[lv.code(rec["level"])]
        _box(ax, 4.6, y - 0.55, 2.2, 1.1, f"{a.code}   μ = {rec['mu']:.3f}" + ("  veto" if rec["veto"] else ""),
             fc=c, ec="none", tc=LEVEL_TEXT[lv.code(rec["level"])], fs=8)
        for yy in ys:
            ax.plot([6.8, 8.2], [y, yy], color=AXIS, lw=0.6, zorder=1)
    # goals
    yg = {}
    for g in cfg.goals:
        ys = [ya[a.code] for a in cfg.actions_of(g)]
        y = sum(ys) / len(ys)
        yg[g] = y
        G = result.G[g]
        _box(ax, 1.9, y - 1.2, 2.0, 2.4, f"{GOAL_NAMES[g]}\n{G['mean']:.3f} / {G['min']:.3f}",
             fc="#ffffff", ec=GOAL_COLORS[g], lw=2.2, fs=8.5)
        for yy in ys:
            ax.plot([3.9, 4.6], [y, yy], color=AXIS, lw=0.9, zorder=1)
    y0 = ytot / 2
    R = result.R
    _box(ax, 0.0, y0 - 2.5, 1.5, 5.0, "CIO", f"R = {R['R']:.3f} ({R['level_code']})\nR_min = {R['R_min']:.3f}\n[{R['R_L']:.3f}, {R['R_U']:.3f}]",
         fc=LEVEL_COLORS[R["level_code"]], ec="none", tc=LEVEL_TEXT[R["level_code"]], fs=10, sub_fs=8)
    for y in yg.values():
        ax.plot([1.5, 1.9], [y0, y], color=AXIS, lw=1.2, zorder=1)
    ax.text(0, n_m + 0.2, "Object → goals (mean / min) → basic actions → metrics (cell = normalized score m, color = level; * core)",
            fontsize=9, color=INK)
    return fig


def agent_topology(center=None):
    """Multi-agent architecture: block team on bus topics + operational/neural agents."""
    fig, ax = _canvas(13, 6.4, (0, 13), (0, 6.4))
    # bus backbone
    ax.add_patch(FancyBboxPatch((0.3, 2.85), 12.4, 0.5, boxstyle="round,pad=0,rounding_size=0.2",
                                fc="#eef2f8", ec="none"))
    ax.text(6.5, 3.1, "message bus — topics = buses of the structural model (X, Ξ, O, M, A, G, R, P, C) + "
            "telemetry · nowcast · forecast · alert · advice · report", ha="center", va="center", fontsize=8.5, color=INK)
    blocks = ["B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"]
    for i, b in enumerate(blocks):
        x = 0.55 + i * 1.33
        _box(ax, x, 1.2, 1.1, 0.9, b, ["input", "config", "verify", "normalize", "aggregate", "roll-up",
                                         "integral", "robust", "report"][i], fc="#f3f7fd", fs=9, sub_fs=7)
        ax.plot([x + 0.55, x + 0.55], [2.1, 2.85], color=AXIS, lw=1)
    _box(ax, 5.4, 0.1, 2.2, 0.7, "CU", "control unit (bus C)", fc="#fff8ea", fs=9, sub_fs=7)
    ax.plot([6.5, 6.5], [0.8, 1.2], color="#c98500", ls=":", lw=1)
    ax.text(0.3, 2.35, "symbolic core (exact, authoritative)", fontsize=8, color=INK2, style="italic")
    ops = [("TEL", "telemetry /\ndigital twin", "#ffffff", SERIES[0]),
           ("DQ", "data-quality guard\n(autoencoder)", "#ffffff", SERIES[6]),
           ("NN", "neural nowcast\n(monotone MLP)", "#ffffff", SERIES[6]),
           ("FC", "forecaster\n(window MLP)", "#ffffff", SERIES[6]),
           ("WD", "watchdog\n(hysteresis rules)", "#ffffff", SERIES[1]),
           ("ADV", "improvement\nadvisor (what-if)", "#ffffff", SERIES[2]),
           ("LLM", "analyst agent\n(Claude tools)", "#ffffff", SERIES[4])]
    for i, (n, s, fc, ec) in enumerate(ops):
        x = 0.4 + i * 1.8
        _box(ax, x, 4.25, 1.55, 1.1, n, s, fc=fc, ec=ec, lw=2, fs=9.5, sub_fs=7)
        ax.plot([x + 0.78, x + 0.78], [3.35, 4.25], color=AXIS, lw=1)
    ax.text(0.4, 5.6, "operational & neural agents (advisory)", fontsize=8, color=INK2, style="italic")
    ax.text(12.6, 5.95, "purple = neural  ·  orange = rules  ·  green = exact optimisation  ·  pink = LLM",
            ha="right", fontsize=7.5, color=MUTED)
    return fig


def sequence_chart(bus, corr: int, title: str = ""):
    """Message sequence chart of one assessment run, replayed from the bus log."""
    run = [m for m in bus.log if m.corr == corr]
    tick0 = run[0].tick if run else 0
    msgs = [m for m in bus.log if m.corr == corr or (m.corr == 0 and m.tick == tick0
                                                       and m.topic in ("telemetry", "nowcast", "forecast", "alert"))]
    msgs = [m for m in msgs if m.topic != "C" or m.payload.get("command")]
    lanes = ["TEL", "NN", "DQ", "CU", "B0", "B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8", "FC", "WD"]
    dest = {"telemetry": ["NN", "DQ"], "nowcast": [], "sheet": ["B0"], "X": ["B1"], "XiWK": ["B2"], "O": ["B3"],
            "M": ["B4", "B7"], "A": ["B5"], "G": ["B6"], "R": ["B8"], "P": ["B8"], "report": ["FC", "WD"],
            "forecast": ["WD"], "alert": [], "C": []}
    keep = [m for m in msgs if m.topic in dest][:40]
    n = len(keep)
    fig, ax = plt.subplots(figsize=(12, 0.32 * n + 1.4))
    ax.set_xlim(-0.6, len(lanes) - 0.4)
    ax.set_ylim(n + 0.2, -1.2)
    ax.axis("off")
    for i, l in enumerate(lanes):
        ax.text(i, -0.8, l, ha="center", fontweight="bold", fontsize=8.5, color=INK)
        ax.plot([i, i], [-0.5, n], color="#e1e0d9", lw=1, zorder=0)
    for k, m in enumerate(keep):
        src = lanes.index(m.sender) if m.sender in lanes else None
        if src is None:
            continue
        targets = dest.get(m.topic, [])
        if m.topic == "C":
            ax.annotate(f"C: {m.payload.get('command')}", (src, k), fontsize=7, color="#8a5c00",
                        ha="left", va="center", xytext=(4, 0), textcoords="offset points")
            ax.plot(src, k, "o", ms=4, color="#c98500")
            continue
        for t in targets:
            ti = lanes.index(t)
            ax.annotate("", xy=(ti, k), xytext=(src, k),
                        arrowprops=dict(arrowstyle="-|>", color=SERIES[0], lw=1.1))
        if targets:
            x = (src + lanes.index(targets[0])) / 2
            ax.text(x, k - 0.12, m.topic, ha="center", va="bottom", fontsize=7, color=INK2)
        else:
            ax.plot(src, k, "s", ms=4, color=SERIES[6])
            ax.text(src + 0.12, k, m.topic, fontsize=7, va="center", color=INK2)
    if title:
        ax.set_title(title, loc="left")
    return fig
