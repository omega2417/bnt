"""Data charts: Figures 5-7 of the manuscript and the agent/neural extensions."""
from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from .. import levels as lv
from ..core import linear_normalize, normalize
from ..model import GOAL_NAMES
from ..scenarios import STATE_NAMES
from .style import (AXIS, GOAL_COLORS, INK, INK2, LEVEL_COLORS, LEVEL_TEXT, MUTED, SERIES, STATUS,
                    level_bands, level_color)

STATES = ["E4", "E2", "E1", "E3", "E5"]


def adequacy_figure(adq: dict):
    """Figure 5: (a) R with enclosure, R_min and 5-95% weight range; (b) goal profile."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1, 1.35]})
    x = np.arange(5)
    for i, e in enumerate(STATES):
        d = adq[e]
        mc = d["mc"]
        a.add_patch(plt.Rectangle((i - 0.3, mc["q05"]), 0.6, max(mc["q95"] - mc["q05"], 0.004),
                                  fc="#d9d8d2", ec="none", zorder=2))
        a.errorbar(i, d["R"], yerr=[[d["R"] - d["R_L"]], [d["R_U"] - d["R"]]], fmt="o", ms=9,
                   color=level_color(d["R"]), mec="white", mew=1.5, ecolor=INK, elinewidth=1.4,
                   capsize=5, zorder=4)
        a.plot(i + 0.18, d["R_min"], marker="v", ms=8, color=INK2, mec="white", zorder=4, ls="none")
        a.text(i, min(d["R_U"], 1) + 0.04, f"{d['R']:.3f}\n{d['level_code']}", ha="center", fontsize=8, color=INK)
    level_bands(a)
    a.set_xticks(x, [f"{e}\n{STATE_NAMES[e].split()[0]}" for e in STATES])
    a.set_ylim(-0.03, 1.12)
    a.set_ylabel("integral index R")
    a.set_title("(a) Integral index, enclosure, weakest link, weight range")
    from matplotlib.lines import Line2D
    a.legend(handles=[Line2D([], [], marker="o", ls="none", color=INK2, label="R ± missing-data enclosure"),
                      Line2D([], [], marker="v", ls="none", color=INK2, label="R_min (weakest link)"),
                      plt.Rectangle((0, 0), 1, 1, fc="#d9d8d2", label="5–95% under random weights")],
             loc="upper left", fontsize=7.5)
    goals = ["ANT", "WITH", "REC", "AD"]
    bw = 0.19
    for gi, g in enumerate(goals):
        xs = x + (gi - 1.5) * bw
        means = [adq[e]["goals_mean"][g] for e in STATES]
        mins = [adq[e]["goals_min"][g] for e in STATES]
        b.bar(xs, means, bw * 0.9, color=GOAL_COLORS[g], label=GOAL_NAMES[g], zorder=3)
        b.scatter(xs, mins, marker="_", s=120, color=INK, zorder=4, lw=2)
    level_bands(b)
    b.set_xticks(x, STATES)
    b.set_ylim(0, 1.05)
    b.set_ylabel("goal score")
    b.set_title("(b) Goal profile: mean roll-up (bars), minimum roll-up (ticks)")
    b.legend(ncol=4, loc="upper left", fontsize=8)
    fig.tight_layout()
    return fig


def actions_and_sweep(adq: dict, sw: dict, cfg):
    """Figure 6: (a) action scores by state; (b) R and R_min along the sweep."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.6), gridspec_kw={"width_ratios": [1.4, 1]})
    acts = [x.code for x in cfg.actions]
    order = ["E1", "E2", "E3", "E4", "E5"]
    bw = 0.16
    for si, e in enumerate(order):
        for ai, c in enumerate(acts):
            v = adq[e]["actions"][c]
            xx = ai + (si - 2) * bw
            a.bar(xx, max(v, 0.006), bw * 0.88, color=LEVEL_COLORS[lv.code(lv.level(v))], zorder=3)
            if c in adq[e]["vetoed"]:
                a.text(xx, 0.03, "*", ha="center", fontsize=12, color="#b8322f", fontweight="bold")
        a.text(-0.32 + si * bw, 1.03, e, fontsize=6.5, color=MUTED, ha="center", rotation=90)
    a.set_xticks(range(len(acts)), acts, rotation=0, fontsize=7.8)
    a.set_ylim(0, 1.1)
    a.set_ylabel("action score μ")
    a.set_title("(a) Action scores in E1–E5 (left→right), colored by level; * veto")
    hs = [plt.Rectangle((0, 0), 1, 1, fc=LEVEL_COLORS[c]) for c in LEVEL_COLORS]
    a.legend(hs, [f"{c} {n}" for c, n in zip(LEVEL_COLORS, lv.LEVEL_NAMES)], ncol=5, fontsize=7,
             loc="upper center", bbox_to_anchor=(0.5, -0.1))
    level_bands(b, labels=True)
    b.plot(sw["t"], sw["R"], color=SERIES[0], label="R", zorder=3)
    b.plot(sw["t"], sw["R_min"], color=SERIES[1], label="R_min", zorder=3)
    for e in order:
        t = {"E1": 0, "E2": -0.5, "E3": 0.5, "E4": -1, "E5": 1}[e]
        b.plot(t, adq[e]["R"], "o", ms=7, color=SERIES[0], mec="white", zorder=4)
        b.annotate(e, (t, adq[e]["R"]), xytext=(-12, 6), textcoords="offset points", fontsize=8)
    for bnd, t in sw["crossings"].items():
        if bnd in (0.4, 0.7, 0.9):
            b.axvline(t, color=AXIS, lw=0.8, ls="--")
            b.text(t, 0.02, f"t≈{t:.3f}", rotation=90, fontsize=7, color=MUTED, ha="right", va="bottom")
    b.set_xlabel("state parameter t of rule (12)")
    b.set_ylabel("index")
    b.set_ylim(0, 1.02)
    b.set_title("(b) Response along the sweep (81 points)")
    b.legend(loc="upper left")
    fig.tight_layout()
    return fig


def robustness_and_noncomp(adq: dict, nc: dict):
    """Figure 7: (a) distribution of R under random weights; (b) non-compensation control."""
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.4))
    level_bands(a, orient="v", labels=False)
    for e, col in zip(["E2", "E1", "E3"], [SERIES[1], SERIES[0], SERIES[2]]):
        s = adq[e]["samples"]
        a.hist(s, bins=np.linspace(0.3, 0.95, 240), color=col, alpha=0.85, label=f"{e}: {adq[e]['mc']['mean']:.3f} ± {adq[e]['mc']['sd']:.3f}",
               density=True, zorder=3)
    for bnd in (0.4, 0.7, 0.9):
        a.axvline(bnd, color=INK2, lw=0.8, ls="--")
    sh = adq["E1"]["mc"]["shares"]
    a.text(0.705, a.get_ylim()[1] * 0.8 if a.get_ylim()[1] else 10,
           f"E1: A {sh['A']:.1%} | AA {sh['AA']:.1%}", fontsize=8, color=INK)
    a.set_xlabel("integral index R")
    a.set_ylabel("density")
    a.set_title("(a) R under random weights w ~ Dirichlet(1)")
    a.legend(loc="upper left", fontsize=8)
    s = nc["sources"]
    lab = {"additive": "additive score", "hard": "hard gate (6)", "capped": "capped operator (5), ϑ=0.5"}
    for op, col, mk in zip(["additive", "hard", "capped"], SERIES[:3], ["o", "s", "D"]):
        b.plot(s, nc[op]["action"], marker=mk, color=col, label=lab[op], ms=7, mec="white", zorder=3)
    level_bands(b)
    b.set_xticks(s)
    b.set_xlabel("number of threat-intelligence sources (core metric of UN.S1.A1)")
    b.set_ylabel("score of UN.S1.A1")
    b.set_ylim(-0.02, 1.0)
    b.set_title("(b) Non-compensation control")
    b.annotate(f"R = {nc['capped']['R'][0]:.3f} but R_min = 0\n(veto flag raised)", (0, 0.0), xytext=(0.6, 0.18),
               fontsize=8, arrowprops=dict(arrowstyle="-", color=MUTED))
    b.legend(loc="lower right", fontsize=8)
    fig.tight_layout()
    return fig


def metric_heatmap(adq: dict, cfg, norm_by_state: dict):
    """39 metrics x 5 states: normalized score m, cell color = level."""
    keys = cfg.keys()
    states = ["E1", "E2", "E3", "E4", "E5"]
    fig, ax = plt.subplots(figsize=(7.8, 12))
    ax.set_xlim(0, 5)
    ax.set_ylim(len(keys), 0)
    ax.grid(False)
    for i, k in enumerate(keys):
        for j, e in enumerate(states):
            s = norm_by_state[e][k]
            if s is None:
                ax.add_patch(plt.Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, fc="white", ec=AXIS, ls="--"))
                ax.text(j + 0.5, i + 0.5, "n.r.", ha="center", va="center", fontsize=7, color=MUTED)
                continue
            c = lv.code(lv.level(s))
            ax.add_patch(plt.Rectangle((j + 0.04, i + 0.06), 0.92, 0.88, fc=LEVEL_COLORS[c], ec="none"))
            ax.text(j + 0.5, i + 0.5, f"{s:.2f}", ha="center", va="center", fontsize=7, color=LEVEL_TEXT[c])
    ax.set_xticks(np.arange(5) + 0.5, states)
    ax.xaxis.tick_top()
    ax.set_yticks(np.arange(len(keys)) + 0.5,
                  [f"{a} · {m}{'*' if cfg.action(a).metrics[[x.code for x in cfg.action(a).metrics].index(m)].core else ''}"
                   for a, m in keys], fontsize=7)
    prev = None
    for i, (a, _) in enumerate(keys):
        if prev and a != prev:
            ax.axhline(i, color=INK2, lw=1)
        prev = a
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Normalized scores m of all 39 metrics (bus M), color = level", pad=24)
    return fig


def normalization_figure(cfg):
    """Anchored piecewise-linear normalization vs. min-max rescaling for two metrics."""
    picks = [("UN.S1.A1", "M3"), ("CN.S1.A1", "SI-IC-2")]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    for ax, (ac, mc) in zip(axes, picks):
        m = [x for x in cfg.action(ac).metrics if x.code == mc][0]
        lo, hi = min(m.xi), max(m.xi)
        xs = np.linspace(lo - 0.05 * (hi - lo), hi + 0.05 * (hi - lo), 600)
        an = [normalize(x, m.anchors, m.sigma) for x in xs]
        li = [linear_normalize(x, m.xi[0], m.xi[5], m.sigma) for x in xs]
        level_bands(ax)
        for b in m.xi[1:5]:
            ax.axvline(b, color=AXIS, lw=0.8, ls=":")
        ax.plot(xs, an, color=SERIES[0], label="anchored (4): band = tabulated class", zorder=3)
        ax.plot(xs, li, color=SERIES[1], ls="--", label="min–max rescaling", zorder=3)
        ax.set_title(f"{ac}.{mc}: {m.name}")
        ax.set_xlabel(f"x [{m.unit}]  ({'smaller' if m.sigma < 0 else 'larger'} is better)")
        ax.set_ylabel("normalized score")
        ax.set_ylim(-0.02, 1.04)
        ax.legend(loc="lower left" if m.sigma > 0 else "lower right", fontsize=7.5)
    fig.tight_layout()
    return fig


def goal_radar(adq: dict):
    goals = ["ANT", "WITH", "REC", "AD"]
    ang = np.linspace(0, 2 * np.pi, 5)[:-1]
    fig = plt.figure(figsize=(5.6, 5.4))
    ax = fig.add_subplot(projection="polar")
    for e, col in zip(["E2", "E1", "E3"], [SERIES[1], SERIES[0], SERIES[2]]):
        v = [adq[e]["goals_mean"][g] for g in goals]
        ax.plot(np.r_[ang, ang[0]], np.r_[v, v[0]], color=col, label=f"{e} (R={adq[e]['R']:.3f})")
        ax.fill(np.r_[ang, ang[0]], np.r_[v, v[0]], color=col, alpha=0.08)
    for b in (0.4, 0.7, 0.9):
        ax.plot(np.linspace(0, 2 * np.pi, 100), [b] * 100, color=AXIS, lw=0.8, ls="--")
    ax.set_xticks(ang, [GOAL_NAMES[g] for g in goals])
    ax.set_ylim(0, 1)
    ax.set_yticks([0.4, 0.7, 0.9], ["0.4", "0.7", "0.9"], fontsize=7)
    ax.set_title("Resilience profile π_θ (mean roll-up)", pad=18)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.12), fontsize=8)
    return fig


# ----------------------------------------------------------------- neural
def surrogate_figure(evals: dict, nets: dict):
    """Training curves, parity plot, level confusion and monotonicity of the surrogates."""
    fig, ax = plt.subplots(1, 4, figsize=(15, 3.8), gridspec_kw={"width_ratios": [1, 1, 0.9, 0.7]})
    cols = {"monotone": SERIES[6], "unconstrained": SERIES[1]}
    for name, net in nets.items():
        ax[0].semilogy(net.history["val"], color=cols[name], label=f"{name} (val)")
        ax[0].semilogy(net.history["train"], color=cols[name], ls=":", lw=1.2)
    ax[0].set_xlabel("epoch"); ax[0].set_ylabel("MSE"); ax[0].set_title("(a) Training curves"); ax[0].legend(fontsize=7.5)
    ev = evals["monotone"]
    level_bands(ax[1], labels=False)
    ax[1].scatter(ev["R_true"], ev["R_pred"], s=4, color=SERIES[6], alpha=0.35, lw=0, zorder=3)
    ax[1].plot([0, 1], [0, 1], color=INK2, lw=1)
    ax[1].set_xlabel("exact R (system)"); ax[1].set_ylabel("neural R̂")
    ax[1].set_title(f"(b) Parity, MAE={ev['mae_R']:.4f}")
    C = ev["confusion"].astype(float)
    Cn = C / np.maximum(C.sum(1, keepdims=True), 1)
    ax[2].imshow(Cn, cmap="Blues", vmin=0, vmax=1)
    ax[2].grid(False)
    for i in range(5):
        for j in range(5):
            if C[i, j]:
                ax[2].text(j, i, f"{int(C[i, j])}", ha="center", va="center", fontsize=7,
                           color="white" if Cn[i, j] > 0.6 else INK)
    ax[2].set_xticks(range(5), lv.LEVEL_CODES); ax[2].set_yticks(range(5), lv.LEVEL_CODES)
    ax[2].set_xlabel("neural level"); ax[2].set_ylabel("exact level")
    ax[2].set_title(f"(c) Level agreement {ev['level_accuracy']:.1%}")
    names = list(evals)
    vals = [evals[n]["monotone_violations"] * 100 for n in names]
    ax[3].bar(names, vals, color=[cols[n] for n in names], width=0.55, zorder=3)
    for i, v in enumerate(vals):
        ax[3].text(i, v + 0.1, f"{v:.1f}%", ha="center", fontsize=8)
    ax[3].set_ylabel("% of +δ steps that lower R̂")
    ax[3].set_title("(d) Monotonicity violations")
    fig.tight_layout()
    return fig


def twin_dashboard(h: dict, cfg):
    """Operations dashboard of the multi-agent run on the digital twin."""
    fig, ax = plt.subplots(3, 1, figsize=(13, 9.5), sharex=True, gridspec_kw={"height_ratios": [2.2, 1.3, 0.9]})
    t = h["t"]
    for name, s, e in h["events"]:
        for a in ax[:2]:
            a.axvspan(s, min(e, t[-1] + 1), color="#f4e7c8" if "Improv" not in name else "#e3f1e8", alpha=0.6, lw=0, zorder=0)
        ax[0].text(s + 1, 1.0, name, fontsize=7.5, color=INK2, va="top")
    level_bands(ax[0], labels=True, alpha=0.1)
    ax[0].fill_between(t, h["R_L"], h["R_U"], color=SERIES[0], alpha=0.18, lw=0, label="[R_L, R_U]")
    ax[0].plot(t, h["R"], color=SERIES[0], lw=1.8, label="R (exact, block team)")
    ax[0].plot(t, h["R_min"], color=SERIES[1], lw=1.3, label="R_min")
    if h.get("nowcast") is not None:
        ax[0].plot(t, h["nowcast"][:len(t)], color=SERIES[6], lw=1, ls=":", label="neural nowcast R̂")
    if h.get("forecast") is not None:
        fc = h["forecast"]
        H = 6
        ax[0].plot(t[: len(fc)] + H - 1, fc, color=SERIES[4], lw=1.1, ls="--", label=f"forecast (+{H} ticks)")
    sev_y = {"critical": 0.06, "serious": 0.12, "warning": 0.18, "info": 0.24}
    for al in h["alerts"]:
        ax[0].plot(al["tick"], sev_y[al["severity"]], marker="v", ms=7, color=STATUS[al["severity"]],
                   mec="white", ls="none", zorder=5)
    ax[0].text(t[-1] + 2, 0.15, "alerts", fontsize=7, color=INK2)
    ax[0].set_ylim(0, 1.02)
    ax[0].set_ylabel("index")
    ax[0].set_title("Multi-agent run on the digital twin: exact verdict, neural nowcast/forecast, alerts")
    ax[0].legend(ncol=3, loc="lower right", bbox_to_anchor=(1.0, 0.27), fontsize=7.5)
    for gi, g in enumerate(cfg.goals):
        ax[1].plot(t, h["goals"][:, gi], color=GOAL_COLORS[g], lw=1.4, label=GOAL_NAMES[g])
    ax[1].set_ylabel("goal mean")
    ax[1].legend(ncol=4, fontsize=7.5, loc="lower right")
    F, Fl = h["faults"], h["flags"]
    tp = np.argwhere((F >= 2) & Fl)
    fn = np.argwhere((F >= 2) & ~Fl)
    fp = np.argwhere((F < 2) & Fl)
    ax[2].scatter(tp[:, 0], tp[:, 1], s=10, color=STATUS["good"], label=f"fault caught ({len(tp)})", marker="s")
    ax[2].scatter(fn[:, 0], fn[:, 1], s=12, color=STATUS["critical"], label=f"fault missed ({len(fn)})", marker="x")
    ax[2].scatter(fp[:, 0], fp[:, 1], s=8, color=MUTED, label=f"false flag ({len(fp)})", marker="o")
    ax[2].set_ylabel("metric #")
    ax[2].set_xlabel("tick")
    ax[2].set_ylim(-1, F.shape[1])
    ax[2].set_title("Data-quality agent (autoencoder): injected sensor faults vs. flags", fontsize=9.5)
    ax[2].legend(ncol=3, fontsize=7.5, loc="upper left", bbox_to_anchor=(0, -0.25))
    fig.tight_layout()
    return fig


def advisor_figure(cands: list, plan: dict):
    fig, (a, b) = plt.subplots(1, 2, figsize=(12.5, 4.4), gridspec_kw={"width_ratios": [1.3, 1]})
    top = cands[:10][::-1]
    labels = [c["source"] + ("  (shared ×2)" if len(c["metrics"]) > 1 else "") for c in top]
    a.barh(labels, [c["dR"] for c in top], color=SERIES[2], height=0.6, zorder=3)
    for i, c in enumerate(top):
        a.text(c["dR"] + 0.0003, i, f"+{c['dR']:.4f}", va="center", fontsize=7.5)
    a.set_xlabel("ΔR from moving the measurement to the next class boundary")
    a.set_title("(a) Exact single-step what-if gains (advisor agent)")
    a.tick_params(axis="y", labelsize=7.5)
    st = plan["steps"]
    xs = range(len(st))
    level_bands(b, labels=True)
    b.plot(xs, [s["R"] for s in st], "o-", color=SERIES[0], label="R")
    b.plot(xs, [s["R_L"] for s in st], "s--", color=SERIES[1], label="R_L (guaranteed)")
    b.axhline(plan["target"], color=INK2, lw=0.8)
    b.set_xticks(list(xs), ["now"] + [s["action"].split(".")[-1] for s in st[1:]], fontsize=7.5, rotation=20)
    lo = min(s["R_L"] for s in st) - 0.03
    b.set_ylim(lo, max(s["R_U"] for s in st) + 0.03)
    b.set_title(f"(b) Greedy plan to a stable level {lv.code(plan['target_level'])}")
    b.legend(fontsize=8)
    fig.tight_layout()
    return fig


def calibration_figure(cal, true_w, G, expert, before, after, goals):
    from ..neural.models import quadratic_kappa
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    x = np.arange(len(goals))
    ax[0].bar(x - 0.2, true_w, 0.38, color=MUTED, label="expert (hidden)", zorder=3)
    ax[0].bar(x + 0.2, cal.omega, 0.38, color=SERIES[6], label="learned ω", zorder=3)
    ax[0].axhline(0.25, color=INK2, ls="--", lw=0.8)
    ax[0].text(3.4, 0.255, "equal", fontsize=7, color=INK2, ha="right")
    ax[0].set_xticks(x, [GOAL_NAMES[g] for g in goals])
    ax[0].set_title("(a) Goal weights recovered from expert levels")
    ax[0].legend(fontsize=8)
    ax[1].plot(cal.loss, color=SERIES[6])
    ax[1].set_xlabel("iteration"); ax[1].set_ylabel("ordinal log-loss"); ax[1].set_title("(b) Calibration loss")
    for k, (lab, lev) in enumerate([("equal ω", before), ("learned ω", after)]):
        ax[2].bar(k, quadratic_kappa(expert, lev), 0.5, color=[MUTED, SERIES[6]][k], zorder=3)
        ax[2].text(k, quadratic_kappa(expert, lev) + 0.01, f"κw={quadratic_kappa(expert, lev):.3f}\nexact {np.mean(expert == lev):.0%}",
                   ha="center", fontsize=8)
    ax[2].set_xticks([0, 1], ["equal ω", "learned ω"])
    ax[2].set_ylim(0, 1.15)
    ax[2].set_title("(c) Agreement with expert levels")
    fig.tight_layout()
    return fig
