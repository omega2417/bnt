"""Figures of the digital supplement (matplotlib).

Every function returns a ``matplotlib.figure.Figure`` and draws only from
the data model, so the notebook and ``scripts/reproduce.py`` share one
source of truth.
"""
from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import BoundaryNorm, ListedColormap
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

from . import aggregation as agg
from . import sensitivity as sens
from . import uncertainty as unc
from .evaluation import evaluate_scenario
from .scale import LEVEL_ABBR, LEVEL_NAMES, Y, level

# five ordered levels: red arm -> neutral -> blue arm (diverging, gray midpoint)
LEVEL_COLORS = ("#c8433a", "#ef9a7f", "#e3e1dc", "#8fbbee", "#2a78d6")
LINEAR = "#eb6834"      # two-anchor linear normalization
ANCHORED = "#1f1f1d"    # anchored piecewise-linear normalization
MUTED = "#6b6a63"

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 300, "font.size": 9,
    "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#8a8980", "axes.labelcolor": "#2b2b28",
    "xtick.color": "#4a4a45", "ytick.color": "#4a4a45",
    "axes.grid": False, "legend.frameon": False,
})


def _bands(ax, orientation: str = "h", alpha: float = 0.35):
    for r in range(5):
        if orientation == "h":
            ax.axhspan(Y[r], Y[r + 1], color=LEVEL_COLORS[r], alpha=alpha, lw=0, zorder=0)
        else:
            ax.axvspan(Y[r], Y[r + 1], color=LEVEL_COLORS[r], alpha=alpha, lw=0, zorder=0)


def _level_legend(ax, loc="lower center", ncol=5, **kw):
    handles = [Patch(color=c, alpha=0.6, label=n) for c, n in zip(LEVEL_COLORS, LEVEL_NAMES)]
    return ax.legend(handles=handles, loc=loc, ncol=ncol, fontsize=7.5, **kw)


# ------------------------------------------------------------------ Fig. A
def fig_projections(scen: dict):
    """Action × technique incidence for the DDoS and phishing projections,
    with their meet and join (Proposition 2)."""
    P, Q = scen["projections"]["DDoS"], scen["projections"]["phishing"]
    J, M = P | Q, P & Q
    acts = sorted(J.actions, key=lambda b: (b[:2], b))
    techs = sorted({t for b in acts for t in J.techniques(b)})
    fig, ax = plt.subplots(figsize=(6.4, 4.6))
    for i, b in enumerate(acts):
        for j, t in enumerate(techs):
            inP, inQ = t in P.techniques(b), t in Q.techniques(b)
            if inP and inQ:
                ax.scatter(j, i, s=150, marker="s", color="#2a78d6", ec="white", lw=2, zorder=3)
            elif inP:
                ax.scatter(j, i, s=150, marker="s", color="#eb6834", ec="white", lw=2, zorder=3)
            elif inQ:
                ax.scatter(j, i, s=150, marker="s", color="#1baf7a", ec="white", lw=2, zorder=3)
    ax.set_xticks(range(len(techs)), techs)
    ax.set_yticks(range(len(acts)), [b + ("  ⊓" if b in M.actions else "") for b in acts])
    ax.invert_yaxis()
    ax.set_xlim(-0.6, len(techs) - 0.4)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Scenario projections: DDoS ⊔ phishing (|join| = %d, |meet| = %d actions)"
                 % (len(J.actions), len(M.actions)), fontsize=9, loc="left")
    ax.legend(handles=[Line2D([], [], ls="", marker="s", ms=9, color=c, label=l) for c, l in
                       (("#eb6834", "DDoS only"), ("#1baf7a", "phishing only"),
                        ("#2a78d6", "both (meet)"))],
              loc="upper left", bbox_to_anchor=(1.0, 1.0), fontsize=8)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ Fig. 5
def fig_normalizations(action):
    """Two-anchor linear vs anchored normalization for each metric of an action."""
    q = action.q
    cols = 3
    rows = math.ceil(q / cols)
    fig, axes = plt.subplots(rows, cols, figsize=(9.2, 2.9 * rows), squeeze=False)
    for p, (ax, mt) in enumerate(zip(axes.flat, action.metrics)):
        t = mt.table
        lo, hi = min(t.xi), max(t.xi)
        span = hi - lo
        xs = np.linspace(lo - 0.08 * span, hi + 0.08 * span, 1500)
        _bands(ax)
        ax.plot(xs, t.linear(xs), color=LINEAR, ls="--", lw=1.8, label="linear $n_{c,h}$")
        ax.plot(xs, t.anchored(xs), color=ANCHORED, lw=1.8, label="anchored $\\nu_\\xi$")
        # physical classes as a strip under the axis
        edges = [-np.inf, *t.eta[1:5], np.inf]
        for r in range(5):
            a, b = edges[r], edges[r + 1]
            xa, xb = sorted((t.sigma * a, t.sigma * b))
            ax.axvspan(max(xa, xs[0]), min(xb, xs[-1]), ymin=0, ymax=0.035,
                       color=LEVEL_COLORS[r], lw=0)
        if mt.observed:
            ax.plot(mt.value, t.linear(mt.value), "s", ms=7, mfc="white", mec=LINEAR, mew=1.6)
            ax.plot(mt.value, t.anchored(mt.value), "D", ms=6, color=ANCHORED, mec="white")
        ax.set_ylim(-0.03, 1.03)
        ax.set_xlim(xs[0], xs[-1])
        ax.set_title(f"M{p + 1}{'*' if mt.core else ''}: {mt.name}", fontsize=8, loc="left")
        ax.set_xlabel(mt.unit, fontsize=8)
        ax.set_yticks(Y)
    for ax in axes.flat[q:]:
        ax.set_visible(False)
    axes[0, 0].legend(loc="center right", fontsize=7.5)
    fig.suptitle(f"Normalizations of the metrics of {action.ident}  (□ linear, ◆ anchored, at the example value)",
                 fontsize=9.5, x=0.01, ha="left")
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ Fig. 6
def fig_consistency(actions):
    """Normalized scores against the band of the tabulated class (all metrics)."""
    rows = [(b, p, mt) for b, a in actions.items() for p, mt in enumerate(a.metrics)]
    fig, ax = plt.subplots(figsize=(9.6, 3.8))
    for i, (b, p, mt) in enumerate(rows):
        if not mt.observed:
            ax.text(i, 0.5, "n.r.", ha="center", va="center", fontsize=6.5, color=MUTED, rotation=90)
            continue
        r = mt.tabulated_level()
        ax.add_patch(plt.Rectangle((i - 0.38, Y[r - 1]), 0.76, Y[r] - Y[r - 1],
                                   color=LEVEL_COLORS[r - 1], alpha=0.75, lw=0))
        lin, anc = mt.normalized("linear"), mt.normalized("anchored")
        bad = level(lin) != r
        ax.plot(i, lin, "o", ms=6, mfc="white" if not bad else "#c8433a",
                mec="#c8433a" if bad else LINEAR, mew=1.4, zorder=4)
        ax.plot(i, anc, "D", ms=4.5, color=ANCHORED, zorder=5)
        if mt.core:
            ax.text(i, 1.04, "K", ha="center", fontsize=7, weight="bold")
    # action separators and labels
    start = 0
    for b, a in actions.items():
        end = start + a.q
        ax.axvline(end - 0.5, color="#c9c8c0", lw=0.8)
        ax.text((start + end - 1) / 2, -0.06, b, ha="right", va="top", fontsize=7.5, rotation=30,
                transform=ax.transData)
        start = end
    ax.set_xlim(-0.6, len(rows) - 0.4)
    ax.set_ylim(-0.02, 1.08)
    ax.set_xticks([])
    ax.set_yticks(Y)
    ax.set_ylabel("normalized score")
    n_bad = sum(1 for _, _, mt in rows if mt.observed and level(mt.normalized("linear")) != mt.tabulated_level())
    n_obs = sum(mt.observed for _, _, mt in rows)
    ax.set_title(f"Consistency with tabulated classes: linear outside its band in {n_bad} of {n_obs} "
                 f"observed metrics, anchored in 0", fontsize=9, loc="left")
    ax.legend(handles=[Line2D([], [], ls="", marker="o", mfc="white", mec=LINEAR, label="linear, consistent"),
                       Line2D([], [], ls="", marker="o", color="#c8433a", label="linear, inconsistent"),
                       Line2D([], [], ls="", marker="D", color=ANCHORED, label="anchored")],
              loc="upper center", bbox_to_anchor=(0.5, -0.2), ncol=3, fontsize=7.5)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ Fig. 7
def fig_operators(action, core_pos: int = 0, method: str = "linear"):
    """Response of the operators to the core metric, other metrics fixed."""
    w = action.w()
    K = action.core
    base = action.vector(method)
    t = np.linspace(0, 1, 801)

    def curve(op):
        out = []
        for v in t:
            m = base.copy()
            m[core_pos] = v
            out.append(op(m))
        return np.array(out)

    C = float(w @ base - w[core_pos] * base[core_pos])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(9.2, 3.5), sharey=True)
    for ax in (a1, a2):
        _bands(ax)
    add = curve(lambda m: agg.additive(m, w))
    a1.plot(t, add, ls="--", color=MUTED, lw=1.6, label="additive $S_w$ (= gate for $m_1>0$)")
    a1.plot([0], [0], "o", color=ANCHORED, ms=6, zorder=5, clip_on=False)
    a1.plot([0], [C], "o", mfc="white", mec=ANCHORED, ms=6, zorder=5, clip_on=False,
            label="hard gate jump at $m_1=0$")
    for g, c in zip((0.5, 1, 2), ("#86b6ef", "#2a78d6", "#104281")):
        a1.plot(t, curve(lambda m: agg.power(m, w, K, g)), color=c, lw=1.8, label=f"power, γ = {g}")
    a1.set_title("(a) additive, hard gate, power discounting", fontsize=9, loc="left")
    for th, c in zip((0.25, 0.5, 1.0), ("#86b6ef", "#2a78d6", "#104281")):
        y = curve(lambda m: agg.capped(m, w, K, th))
        a2.plot(t, y, color=c, lw=1.8, label=f"capped, ϑ = {th}")
        kink = th * C / (1 - w[core_pos] * th)   # m1/th = C + w1*m1
        if kink <= 1:
            a2.plot([kink], [kink / th], "|", color=c, ms=12, mew=2)
    a2.plot(t, add, ls="--", color=MUTED, lw=1.2, label="additive")
    a2.set_title("(b) capped knockout operator", fontsize=9, loc="left")
    tab = action.metrics[core_pos].table
    att = np.arange(int(min(tab.xi)), int(max(tab.xi)) + 1)
    for ax in (a1, a2):
        ax.set_xlabel(f"normalized core metric $m_{core_pos + 1}$ ({method})")
        ax.legend(fontsize=7, loc="lower right")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1.0)
        sec = ax.secondary_xaxis(-0.25)
        sec.set_xticks([float(tab.normalize(v, method)) for v in att], [str(v) for v in att])
        sec.set_xlabel(action.metrics[core_pos].unit, fontsize=8)
    a1.set_ylabel(f"score of {action.ident}")
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------ Fig. 9
def fig_contributions(action):
    """Contributions w_q m_q of the metrics under both normalizations."""
    w = action.w()
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.2), sharey=True)
    for ax, meth, title in zip(axes, ("linear", "anchored"),
                               ("(a) two-anchor linear", "(b) anchored piecewise-linear")):
        m = action.vector(meth)
        c = w * m
        left = 0.0
        for p, v in enumerate(c):
            ax.barh(0, v, left=left, height=0.6, color=LEVEL_COLORS[level(m[p]) - 1],
                    ec="white", lw=2, hatch="///" if p in action.core else None)
            if v > 0.05:
                ax.text(left + v / 2, 0, f"M{p + 1}\n{v:.3f}", ha="center", va="center", fontsize=7.5)
            left += v
        ax.axvline(left, color=ANCHORED, lw=1.4)
        ax.text(left - 0.01, 0.36, f"μ = {left:.4f} ({LEVEL_ABBR[level(left) - 1]})", ha="right", fontsize=8.5)
        for r in range(5):
            ax.axvspan(Y[r], Y[r + 1], ymin=0, ymax=0.06, color=LEVEL_COLORS[r], lw=0)
        ax.set_xlim(0, 1)
        ax.set_ylim(-0.5, 0.5)
        ax.set_yticks([])
        ax.set_xticks(Y)
        ax.set_title(title, fontsize=9, loc="left")
        ax.set_xlabel("cumulative contribution $\\sum w_q m_q$")
    fig.suptitle(f"Decomposition of the local score of {action.ident} (hatched: knockout metric; bar colour: level of $m_q$)",
                 fontsize=9.5, x=0.01, ha="left")
    fig.tight_layout()
    return fig


# ----------------------------------------------------------------- Fig. 10
def fig_sensitivity(action, p1: int = 2, p2: int = 3, r1=(0, 200), r2=(0, 260)):
    """Score as a function of two response times; level regions and difference."""
    cmap = ListedColormap(LEVEL_COLORS)
    norm = BoundaryNorm(Y, 5)
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.6))
    Zs = {}
    for ax, meth, title in zip(axes[:2], ("linear", "anchored"), ("(a) linear", "(b) anchored")):
        xs, ys, Z = sens.grid(action, p1, p2, r1, r2, meth)
        Zs[meth] = Z
        ax.pcolormesh(xs, ys, Z, cmap=cmap, norm=norm, shading="auto", alpha=0.85, rasterized=True)
        ax.contour(xs, ys, Z, levels=np.arange(0.5, 1.0, 0.05), colors="#55544e", linewidths=0.4)
        ax.contour(xs, ys, Z, levels=[0.7, 0.9], colors=ANCHORED, linewidths=1.6)
        ax.set_title(f"{title}: {Z.min():.3f} … {Z.max():.3f}", fontsize=9, loc="left")
    D = Zs["anchored"] - Zs["linear"]
    lim = np.abs(D).max()
    im = axes[2].pcolormesh(xs, ys, D, cmap="RdBu", vmin=-lim, vmax=lim, shading="auto", rasterized=True)
    fig.colorbar(im, ax=axes[2], fraction=0.05, label="anchored − linear")
    axes[2].set_title(f"(c) difference, max |Δ| = {lim:.3f}", fontsize=9, loc="left")
    m1, m2 = action.metrics[p1], action.metrics[p2]
    for ax in axes:
        for v in m1.table.xi[1:5]:
            ax.axvline(v, ls=":", color=MUTED, lw=0.8)
        for v in m2.table.xi[1:5]:
            ax.axhline(v, ls=":", color=MUTED, lw=0.8)
        ax.plot(m1.value, m2.value, "*", ms=11, color="white", mec=ANCHORED)
        ax.set_xlabel(f"τ{p1 + 1}: {m1.name} ({m1.unit})", fontsize=7.5)
        ax.set_ylabel(f"τ{p2 + 1}: {m2.name} ({m2.unit})", fontsize=7.5)
    fig.tight_layout()
    return fig


# ----------------------------------------------------------------- Fig. 11
def fig_dirichlet(action, alphas=(1, 4), n: int = unc.N_SAMPLES, seed: int = unc.SEED):
    """Distribution of the score under random Dirichlet weights."""
    fig, axes = plt.subplots(1, len(alphas), figsize=(9.2, 3.2), sharey=True)
    for ax, a in zip(np.atleast_1d(axes), alphas):
        _bands(ax, "v", alpha=0.25)
        for meth, c in (("linear", LINEAR), ("anchored", ANCHORED)):
            m = action.vector(meth)
            s = unc.sample_scores(m, a, n, seed)
            mean, sd = unc.dirichlet_moments(m, a)
            ax.hist(s, bins=np.linspace(0.45, 1.0, 111), density=True, histtype="step", lw=1.6, color=c,
                    label=f"{meth}: P(high) = {np.mean(s >= 0.9):.1%}")
            ax.axvline(mean, color=c, ls=":", lw=1.2)
            ax.axvline(agg.additive(m, action.w()), color=c, ls="--", lw=1.2)
        ax.set_title(f"w ~ Dirichlet({a}·1)", fontsize=9, loc="left")
        ax.set_xlabel(f"score of {action.ident}")
        ax.legend(fontsize=7.5, loc="upper left")
        ax.set_xlim(0.45, 1.0)
    np.atleast_1d(axes)[0].set_ylabel("density")
    fig.tight_layout()
    return fig


# ----------------------------------------------------------------- Fig. 12
def fig_profile(actions):
    """Action scores (both normalizations, enclosure) and goal roll-ups."""
    res = {m: evaluate_scenario(actions, method=m) for m in ("linear", "anchored")}
    names = list(actions)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 3.8), gridspec_kw={"width_ratios": [3, 2]})
    _bands(a1)
    _bands(a2)
    x = np.arange(len(names))
    for dx, meth, c, mk in ((-0.12, "linear", LINEAR, "o"), (0.12, "anchored", ANCHORED, "D")):
        r = res[meth]["actions"]
        s = [r[b].score for b in names]
        lo = [r[b].score - r[b].lower for b in names]
        hi = [r[b].upper - r[b].score for b in names]
        a1.errorbar(x + dx, s, yerr=[lo, hi], fmt=mk, color=c, ms=6, capsize=3, label=meth)
    a1.set_xticks(x, [f"{b}\n{actions[b].goal}" for b in names], fontsize=7.5)
    a1.set_ylim(0.4, 1.0)
    a1.set_yticks(Y[2:])
    a1.set_ylabel("action score (hard gate)")
    a1.set_title("(a) action scores; bars = enclosure for missing metrics", fontsize=9, loc="left")
    a1.legend(fontsize=7.5, loc="upper right")
    goals = list(res["anchored"]["profile"])
    gx = np.arange(len(goals))
    for dx, meth, c in ((-0.15, "linear", LINEAR), (0.15, "anchored", ANCHORED)):
        pr = res[meth]["profile"]
        a2.bar(gx + dx, [pr[g]["mean"] - 0.4 for g in goals], bottom=0.4, width=0.28, color=c,
               alpha=0.85, ec="white", lw=2, label=f"{meth}: mean")
        a2.plot(gx + dx, [pr[g]["min"] for g in goals], "_", ms=14, mew=2.5, color="#c8433a")
    a2.plot([], [], "_", ms=12, mew=2.5, color="#c8433a", label="minimum roll-up")
    a2.set_xticks(gx, goals)
    a2.set_ylim(0.4, 1.0)
    a2.set_yticks(Y[2:])
    a2.set_title("(b) resilience profile π (goal roll-ups)", fontsize=9, loc="left")
    a2.legend(fontsize=7.5, loc="upper right")
    fig.tight_layout()
    return fig


ALL = {
    "FigS_A_projections": ("scen", fig_projections),
    "FigS_05_normalizations_UN.S1.A1": ("UN.S1.A1", fig_normalizations),
    "FigS_06_consistency": ("actions", fig_consistency),
    "FigS_07_operators_UN.S1.A1": ("UN.S1.A1", fig_operators),
    "FigS_09_contributions_UN.S1.A1": ("UN.S1.A1", fig_contributions),
    "FigS_10_sensitivity_UN.S1.A1": ("UN.S1.A1", fig_sensitivity),
    "FigS_11_dirichlet_UN.S1.A1": ("UN.S1.A1", fig_dirichlet),
    "FigS_12_profile_phishing": ("actions", fig_profile),
}
