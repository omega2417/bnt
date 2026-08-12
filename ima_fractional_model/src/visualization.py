"""Automatic generation of Figures 1-9 of the manuscript.

Every figure is written to PNG (300 dpi), PDF and SVG in the target directory.
Figures are produced from computed data only -- nothing is hand-drawn.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import numpy as np
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from .graph_model import IMAGraph

# ---- consistent styling ----
DAL_COLORS = {"A": "#c0392b", "B": "#e67e22", "C": "#2980b9"}
TYPE_MARKER = {"CPM": "s", "SW": "D", "RDC": "o"}
plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 300, "font.size": 11,
    "axes.titlesize": 12, "axes.labelsize": 11, "legend.fontsize": 9,
    "axes.grid": True, "grid.alpha": 0.25, "savefig.bbox": "tight",
})


def save_figure(fig, outdir: str | Path, name: str, formats=("png", "pdf", "svg")):
    outdir = Path(outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    for ext in formats:
        fig.savefig(outdir / f"{name}.{ext}")
    plt.close(fig)
    return [str(outdir / f"{name}.{ext}") for ext in formats]


def _graph_layout(graph: IMAGraph) -> Dict[str, np.ndarray]:
    """Deterministic layout: switches in a ring centre, CPMs outer, RDCs periphery."""
    pos = {}
    sw = [i for i, t in enumerate(graph.node_type) if t == "SW"]
    cpm = [i for i, t in enumerate(graph.node_type) if t == "CPM"]
    rdc = [i for i, t in enumerate(graph.node_type) if t == "RDC"]
    for r, group in [(1.0, sw), (2.3, cpm), (3.8, rdc)]:
        m = len(group)
        for j, i in enumerate(group):
            ang = 2 * np.pi * j / max(m, 1) + (0.4 if r == 2.3 else 0.0)
            pos[graph.node_ids[i]] = np.array([r * np.cos(ang), r * np.sin(ang)])
    return pos


# ============================================================ Figure 1
def figure1_topology(graph: IMAGraph, outdir):
    pos = _graph_layout(graph)
    fig, ax = plt.subplots(figsize=(8, 7))
    amax = graph.A.max()
    for i in range(graph.n):
        for j in range(graph.n):
            w = graph.A[i, j]
            if w > 0:
                a, b = pos[graph.node_ids[j]], pos[graph.node_ids[i]]
                ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>",
                             mutation_scale=8, lw=0.4 + 2.2 * w / amax,
                             color="0.6", alpha=0.5,
                             connectionstyle="arc3,rad=0.08", zorder=1))
    for i, nid in enumerate(graph.node_ids):
        p = pos[nid]
        ax.scatter(*p, s=430, marker=TYPE_MARKER[graph.node_type[i]],
                   c=DAL_COLORS[graph.dal[i]], edgecolors="k", linewidths=1.1,
                   zorder=3)
        ax.text(*p, nid.replace("CPM", "C").replace("RDC", "R").replace("SW", "S"),
                ha="center", va="center", fontsize=7, color="w",
                fontweight="bold", zorder=4)
    handles = [Line2D([0], [0], marker=TYPE_MARKER[t], color="w",
                      markerfacecolor="0.5", markeredgecolor="k", markersize=12,
                      label=lbl) for t, lbl in
               [("CPM", "CPM (8)"), ("SW", "AFDX/TSN switch (4)"), ("RDC", "RDC (10)")]]
    handles += [Line2D([0], [0], marker="o", color="w", markerfacecolor=c,
                       markersize=12, label=f"DAL-{d}") for d, c in DAL_COLORS.items()]
    ax.legend(handles=handles, loc="upper left", bbox_to_anchor=(1.0, 1.0),
              frameon=True)
    ax.set_title("Figure 1. Synthetic 22-node IMA topology\n(edge thickness $\\propto$ dependency weight $a_{ij}$)")
    ax.set_aspect("equal"); ax.axis("off")
    return save_figure(fig, outdir, "figure_1")


# ============================================================ Figure 2
def figure2_model_structure(outdir):
    fig, ax = plt.subplots(figsize=(10, 6.5))
    ax.axis("off"); ax.set_xlim(0, 10); ax.set_ylim(0, 7)

    def box(x, y, w, h, text, color):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.08",
                     fc=color, ec="k", lw=1.3, alpha=0.9))
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=10)

    box(0.6, 4.6, 2.6, 1.4, "Degradation state\n$^{C}D^{\\alpha}x_i(t)$", "#f5b7b1")
    box(0.6, 1.0, 2.6, 1.4, "Backlog state\n$^{C}D^{\\beta}q_i(t)$", "#aed6f1")
    box(6.8, 4.6, 2.6, 1.4, "M1 network\npropagation $\\beta_{ij}a_{ij}$", "#d5f5e3")
    box(6.8, 3.0, 2.6, 1.3, "M2 backlog\nspillover $w_{ij}$", "#d5f5e3")
    box(6.8, 1.5, 2.6, 1.3, "M3 priority\nconflict $\\Phi_i$", "#d5f5e3")
    box(3.9, 0.0, 2.2, 1.0, "M4 reconfig.\nfailure $\\pi(t)$", "#fad7a0")

    def arrow(a, b, text="", rad=0.0, color="k", ls="-"):
        ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=15,
                     lw=1.6, color=color, ls=ls,
                     connectionstyle=f"arc3,rad={rad}"))
        if text:
            ax.text((a[0] + b[0]) / 2, (a[1] + b[1]) / 2 + 0.2, text,
                    ha="center", fontsize=8.5, color=color)

    arrow((3.2, 5.3), (6.8, 5.3), "$f(x_j(t-\\tau_{ij}))$")
    arrow((3.2, 1.7), (6.8, 3.6), "$q_j(t-\\sigma_{ij})$", rad=-0.15)
    arrow((3.2, 1.4), (6.8, 2.1), "$q_i,\\, x_k$", rad=-0.05)
    arrow((1.9, 4.6), (1.9, 2.4), "degradation $\\downarrow$ service", color="#7b241c")
    arrow((2.4, 2.4), (2.4, 4.6), "backlog $\\to$ degrad. ($\\gamma_i$)", color="#1b4f72")
    arrow((5.0, 1.0), (2.2, 4.6), "$-\\rho_i(t)x_i$ suppression", rad=0.2,
          color="#b9770e", ls="--")
    ax.set_title("Figure 2. Model structure: two fractional state blocks and mechanisms M1-M4\n"
                 "(dashed: reconfiguration suppression loop, collapses as $\\pi\\to1$)")
    return save_figure(fig, outdir, "figure_2")


# ============================================================ Figure 3
def figure3_trajectories(graph: IMAGraph, sims: Dict[str, object], x_cat: float,
                         tcat: Dict[str, Optional[float]], outdir):
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.6), sharey=True)
    for ax, name in zip(axes, ["S1", "S2", "S3"]):
        sim = sims[name]
        for i in range(graph.n):
            ax.plot(sim.t, sim.X[:, i], color=DAL_COLORS[graph.dal[i]],
                    lw=1.0, alpha=0.75)
        ax.axhline(x_cat, ls=":", color="k", lw=1.4, label="$x_{cat}$")
        if tcat.get(name):
            ax.axvline(tcat[name], ls="--", color="#7b241c", lw=1.6,
                       label=f"$T_{{cat}}={tcat[name]:.1f}$")
        ax.set_title(f"{name}  ($R_c$={_rc(sim)})")
        ax.set_xlabel("normalized time $t$")
        ax.legend(loc="upper right")
    axes[0].set_ylabel("functional degradation $x_i(t)$")
    handles = [Line2D([0], [0], color=c, lw=2, label=f"DAL-{d}")
               for d, c in DAL_COLORS.items()]
    axes[0].legend(handles=handles + axes[0].get_legend().legend_handles,
                   loc="upper left", fontsize=8)
    fig.suptitle("Figure 3. Degradation trajectories for scenarios S1-S3 "
                 "($\\alpha=\\beta=0.8$)", y=1.02)
    return save_figure(fig, outdir, "figure_3")


def _rc(sim):
    return getattr(sim, "_Rc", "-")


# ============================================================ Figure 4
def figure4_backlog_heatmap(graph: IMAGraph, sim_s3, tcat_s3, outdir):
    order = np.argsort([{"A": 0, "B": 1, "C": 2}[d] for d in graph.dal])
    Q = sim_s3.Q[:, order].T
    fig, ax = plt.subplots(figsize=(9, 6))
    im = ax.imshow(Q, aspect="auto", origin="lower", cmap="inferno",
                   extent=[sim_s3.t[0], sim_s3.t[-1], 0, graph.n])
    if tcat_s3:
        ax.axvline(tcat_s3, ls="--", color="cyan", lw=1.6,
                   label=f"$T_{{cat}}={tcat_s3:.1f}$")
        ax.legend(loc="upper right")
    ax.set_yticks(np.arange(graph.n) + 0.5)
    ax.set_yticklabels([graph.node_ids[i] for i in order], fontsize=6)
    ax.set_xlabel("normalized time $t$")
    ax.set_ylabel("node (sorted by DAL: A, B, C)")
    ax.set_title("Figure 4. Backlog heatmap $q_i(t)$ for scenario S3")
    fig.colorbar(im, ax=ax, label="backlog $q_i$")
    return save_figure(fig, outdir, "figure_4")


# ============================================================ Figure 5
def figure5_cascade_graph(graph: IMAGraph, sim_s3, outdir, instants=None):
    if instants is None:
        tf = sim_s3.t[-1]
        instants = [0.1 * tf, 0.3 * tf, 0.55 * tf, 0.9 * tf]
    pos = _graph_layout(graph)
    fig, axes = plt.subplots(1, 4, figsize=(17, 4.6))
    for ax, tt in zip(axes, instants):
        k = int(np.argmin(np.abs(sim_s3.t - tt)))
        for i in range(graph.n):
            for j in range(graph.n):
                if graph.A[i, j] > 0:
                    a, b = pos[graph.node_ids[j]], pos[graph.node_ids[i]]
                    ax.plot([a[0], b[0]], [a[1], b[1]], color="0.8", lw=0.5, zorder=1)
        xvals = sim_s3.X[k]
        for i, nid in enumerate(graph.node_ids):
            ax.scatter(*pos[nid], s=160, marker=TYPE_MARKER[graph.node_type[i]],
                       c=[xvals[i]], cmap="Reds", vmin=0, vmax=1,
                       edgecolors="k", linewidths=0.7, zorder=3)
        ax.set_title(f"$t={sim_s3.t[k]:.0f}$")
        ax.set_aspect("equal"); ax.axis("off")
    sm = plt.cm.ScalarMappable(cmap="Reds", norm=plt.Normalize(0, 1))
    fig.colorbar(sm, ax=axes, label="degradation $x_i$", fraction=0.02)
    fig.suptitle("Figure 5. Cascade propagation over the IMA graph (scenario S3)", y=1.03)
    return save_figure(fig, outdir, "figure_5")


# ============================================================ Figure 6
def figure6_delay_memory(alphas_scalar, tau_star, dm_alphas, dm_taus, dm_grid, outdir):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    axes[0].plot(alphas_scalar, tau_star, "o-", color="#1f618d", lw=2, ms=7)
    for a, t in zip(alphas_scalar, tau_star):
        axes[0].annotate(f"{t:.2f}", (a, t), textcoords="offset points",
                         xytext=(0, 8), fontsize=8, ha="center")
    axes[0].set_xlabel("fractional order $\\alpha$")
    axes[0].set_ylabel("critical delay $\\tau^*(\\alpha)$")
    axes[0].set_title("(a) Critical delay (Theorem 4)\nstronger memory $\\to$ larger stable region")

    im = axes[1].imshow(dm_grid, aspect="auto", origin="lower", cmap="viridis",
                        vmin=0, vmax=1,
                        extent=[dm_taus[0], dm_taus[-1], dm_alphas[0], dm_alphas[-1]])
    axes[1].set_xlabel("delay scale $\\tau$")
    axes[1].set_ylabel("fractional order $\\alpha$")
    axes[1].set_title("(b) Terminal cascade size on the $(\\alpha,\\tau)$ grid")
    fig.colorbar(im, ax=axes[1], label="terminal cascade size")
    fig.suptitle("Figure 6. Critical delay vs fractional order and delay-memory cascade map",
                 y=1.03)
    return save_figure(fig, outdir, "figure_6")


# ============================================================ Figure 7
def figure7_phase_portrait(trajectories, fixed_points, outdir):
    fig, ax = plt.subplots(figsize=(8, 6.5))
    for X, Q, kind in trajectories:
        color = "#c0392b" if kind == "CAT" else "#2471a3"
        ax.plot(X, Q, color=color, lw=1.0, alpha=0.7)
        ax.plot(X[0], Q[0], "o", color=color, ms=3)
    for (x, q, stab) in fixed_points:
        ax.plot(x, q, "*", ms=20, mec="k",
                mfc=("#c0392b" if q > 0.8 else "#1a5276"), zorder=5)
        ax.annotate(f"({x:.2f}, {q:.2f})", (x, q), textcoords="offset points",
                    xytext=(8, 6), fontsize=9)
    ax.set_xlabel("mean degradation $x$")
    ax.set_ylabel("mean backlog $q$")
    handles = [Line2D([0], [0], color="#2471a3", lw=2, label="$\\to$ nominal $E_0$"),
               Line2D([0], [0], color="#c0392b", lw=2, label="$\\to$ catastrophic $E^*$")]
    ax.legend(handles=handles, loc="upper left")
    ax.set_title("Figure 7. Mean-field phase portrait: bistability ($\\alpha=0.8$)")
    return save_figure(fig, outdir, "figure_7")


# ============================================================ Figure 8
def figure8_tipping(tipping_rows, priority_rows, xi_star, outdir):
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    xi = [r["xi"] for r in tipping_rows]
    tc = [r["T_cat"] for r in tipping_rows]
    axes[0].plot(xi, tc, "o-", color="#1f618d", lw=2)
    axes[0].axvspan(xi_star, max(xi), alpha=0.15, color="green",
                    label="no catastrophe")
    axes[0].axvline(xi_star, ls="--", color="k",
                    label=f"$\\xi^*\\approx{xi_star:.2f}$")
    axes[0].set_xlabel("reconfiguration capacity threshold $\\xi$")
    axes[0].set_ylabel("time-to-catastrophe $T_{cat}$")
    axes[0].set_title("(a) Reconfiguration tipping point")
    axes[0].legend()

    ts = [r["theta_scale"] for r in priority_rows]
    tc2 = [r["T_cat"] for r in priority_rows]
    axes[1].plot(ts, tc2, "s-", color="#922b21", lw=2)
    axes[1].set_xlabel("priority-conflict scale $\\theta/\\theta_0$")
    axes[1].set_ylabel("time-to-catastrophe $T_{cat}$")
    axes[1].set_title("(b) Priority-conflict sensitivity")
    fig.suptitle("Figure 8. Reconfiguration tipping point and priority-conflict sensitivity",
                 y=1.03)
    return save_figure(fig, outdir, "figure_8")


# ============================================================ Figure 9
def figure9_ensemble(ensemble_summary: Dict[str, dict], outdir):
    scen = list(ensemble_summary.keys())
    pcat = [ensemble_summary[s]["p_cat"] for s in scen]
    # asymmetric error bars (clip tiny negatives from float round-off)
    lo = [max(0.0, ensemble_summary[s]["p_cat"] - ensemble_summary[s]["wilson_low"])
          for s in scen]
    hi = [max(0.0, ensemble_summary[s]["wilson_high"] - ensemble_summary[s]["p_cat"])
          for s in scen]
    med = [ensemble_summary[s].get("km_median") for s in scen]

    fig, ax1 = plt.subplots(figsize=(9, 6))
    x = np.arange(len(scen))
    bars = ax1.bar(x, pcat, yerr=[lo, hi], capsize=6, color="#5499c7",
                   edgecolor="k", width=0.55, label="catastrophe probability")
    ax1.set_ylabel("catastrophe probability $P_{cat}$ (95% Wilson CI)")
    ax1.set_ylim(0, 1.05)
    ax1.set_xticks(x); ax1.set_xticklabels(scen)
    for xi_, p in zip(x, pcat):
        ax1.text(xi_, p + 0.03, f"{p:.2f}", ha="center", fontsize=10)

    ax2 = ax1.twinx()
    for xi_, m in zip(x, med):
        if m is not None and np.isfinite(m):
            ax2.plot(xi_, m, "D", ms=13, color="#c0392b", zorder=5)
            ax2.annotate(f"KM median\n$T_{{cat}}$={m:.1f}", (xi_, m),
                         textcoords="offset points", xytext=(12, 0), fontsize=9,
                         color="#c0392b", va="center")
        else:
            ax2.annotate("not reached", (xi_, 0.02), textcoords="offset points",
                         xytext=(12, 0), fontsize=9, color="0.4")
    ax2.set_ylabel("Kaplan-Meier median time-to-catastrophe", color="#c0392b")
    ax2.tick_params(axis="y", colors="#c0392b")
    ax1.set_title("Figure 9. Ensemble catastrophe probability and median time-to-catastrophe")
    ax1.legend(loc="upper left")
    return save_figure(fig, outdir, "figure_9")


__all__ = [f"figure{i}_" for i in range(1, 10)] + ["save_figure"]
