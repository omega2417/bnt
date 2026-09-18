"""Regeneration of every figure of the article from code.

Each ``fig_N`` function returns a Matplotlib figure and, when called through
:func:`render_all`, is written to ``figures/figN.pdf`` (vector, for the
publisher) and ``figures/figN.png`` (600 dpi raster, for preprints and the
repository).  Figures that show data are produced by the same code paths as the
protocol, so a figure cannot drift away from the numbers it illustrates: Fig. 3
calls :mod:`evoproto.phylo`, Fig. 7 runs the dry run of Section 7.7, and Fig. 8
calls :func:`evoproto.gate.decide` on the grid it colors.

Every panel built on generated data carries a SYNTHETIC marker in its caption
text, per Section 3.3.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle

__all__ = ["FIGURES", "render_all", "set_style"]

#: Elsevier single- and double-column widths in inches (90 mm and 190 mm).
COLUMN_SINGLE = 90 / 25.4
COLUMN_DOUBLE = 190 / 25.4

_BLUE = "#2b6ca3"
_GREEN = "#3f7d5a"
_ORANGE = "#c2703d"
_RED = "#b3402f"
_GREY = "#5b5b5b"
_LIGHT = "#e8eef3"


def set_style() -> None:
    """Journal-oriented Matplotlib defaults: no style file, no seaborn."""
    plt.rcParams.update(
        {
            "figure.dpi": 120,
            "savefig.dpi": 600,
            "savefig.bbox": "tight",
            "font.size": 7.5,
            "axes.titlesize": 8,
            "axes.labelsize": 7.5,
            "legend.fontsize": 6.8,
            "xtick.labelsize": 6.8,
            "ytick.labelsize": 6.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.6,
            "lines.linewidth": 1.1,
            "grid.linewidth": 0.4,
            "grid.alpha": 0.35,
            "pdf.fonttype": 42,     # embed TrueType, as Elsevier requires
            "ps.fonttype": 42,
        }
    )


def _box(ax, xy, w, h, text, color=_LIGHT, edge=_GREY, fontsize=6.6, weight="normal"):
    ax.add_patch(
        FancyBboxPatch(
            xy, w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=0.7, facecolor=color, edgecolor=edge,
        )
    )
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight=weight, wrap=True)


def _arrow(ax, start, end, color=_GREY, style="-|>", dashed=False, rad=0.0, lw=0.8):
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle=style, mutation_scale=7, linewidth=lw,
            color=color, linestyle="--" if dashed else "-",
            connectionstyle=f"arc3,rad={rad}", shrinkA=1.5, shrinkB=1.5,
        )
    )


# ------------------------------------------------------------------- Figure 1
def fig_1() -> plt.Figure:
    """Layered architecture of the framework (Section 4.1)."""
    fig, ax = plt.subplots(figsize=(COLUMN_DOUBLE, 0.42 * COLUMN_DOUBLE))
    layers = [
        ("L1 Data sources", "Open Tree of Life | MorphoBank | PBDB | experimental literature (DOI)", _LIGHT),
        ("L2 Curation and provenance", "taxonomic reconciliation | trait standardization | observation vs. reconstruction | missing-data and sampling-bias control", _LIGHT),
        ("L3 EE-KG", "six node types, nine typed edges; homology vs. convergence; trade-offs; support weights w", "#dce8f0"),
        ("L4 AI core", "multimodal embeddings | RAG analog search | generative parametric modeling | constrained multi-objective search", "#dce8f0"),
        ("L5 Verification and gate", "numerical verification | Pareto selection | evidence score E, transfer uncertainty U | RECOMMEND / ABSTAIN / REJECT", "#e3efe6"),
        ("L6 Physical test and approval", "printed prototypes | measured mass and stiffness | engineer approval (sole release authority)", "#e3efe6"),
    ]
    n = len(layers)
    height = 1.0 / (n + 0.6)
    for i, (title, detail, color) in enumerate(layers):
        y = 1.0 - (i + 1) * height * 1.08
        _box(ax, (0.06, y), 0.80, height * 0.86, "", color=color)
        ax.text(0.075, y + height * 0.43, title, ha="left", va="center",
                fontsize=7.2, fontweight="bold")
        ax.text(0.30, y + height * 0.43, detail, ha="left", va="center", fontsize=6.2)
        if i:
            _arrow(ax, (0.46, y + height * 1.08), (0.46, y + height * 0.86))
    top = 1.0 - height * 1.08
    bottom = 1.0 - n * height * 1.08
    _arrow(ax, (0.88, bottom + height * 0.43), (0.88, top + height * 0.43),
           color=_ORANGE, dashed=True, rad=-0.45)
    ax.text(0.945, (top + bottom) / 2 + height * 0.4,
            "feedback:\nMEASURED records\nupdate w and priors",
            ha="center", va="center", fontsize=6.0, color=_ORANGE)
    ax.set_xlim(0, 1.02)
    ax.set_ylim(bottom - 0.03, 1.0)
    ax.axis("off")
    return fig


# ------------------------------------------------------------------- Figure 2
def fig_2() -> plt.Figure:
    """Schema of the evolutionary-engineering knowledge graph (Table 4)."""
    fig, ax = plt.subplots(figsize=(COLUMN_DOUBLE, 0.42 * COLUMN_DOUBLE))
    w, h = 0.150, 0.115
    row = 0.46
    positions = {
        "Organism": (0.030, row),
        "Trait": (0.275, row),
        "Function": (0.520, row),
        "Mechanism": (0.765, row),
        "Environment": (0.030, 0.14),
        "EngParameter": (0.765, 0.14),
    }
    for name, (x, y) in positions.items():
        color = "#e3efe6" if name == "EngParameter" else "#dce8f0"
        _box(ax, (x, y), w, h, name, color=color, fontsize=6.8, weight="bold")

    def left(name):
        x, y = positions[name]
        return (x, y + h / 2)

    def right(name):
        x, y = positions[name]
        return (x + w, y + h / 2)

    def bottom(name):
        x, y = positions[name]
        return (x + w / 2, y)

    def top(name):
        x, y = positions[name]
        return (x + w / 2, y + h)

    for tail, head, label in (
        ("Organism", "Trait", "hasTrait"),
        ("Trait", "Function", "performs"),
        ("Function", "Mechanism", "explainedBy"),
    ):
        start_point, end_point = right(tail), left(head)
        _arrow(ax, start_point, end_point)
        ax.text((start_point[0] + end_point[0]) / 2, start_point[1] + 0.022, label,
                ha="center", va="bottom", fontsize=6.3, color=_GREY)
    for tail, head, label in (
        ("Organism", "Environment", "livesIn"),
        ("Mechanism", "EngParameter", "mapsTo"),
    ):
        start_point, end_point = bottom(tail), top(head)
        _arrow(ax, start_point, end_point)
        ax.text(start_point[0] + 0.012, (start_point[1] + end_point[1]) / 2, label,
                ha="left", va="center", fontsize=6.3, color=_GREY)

    # Trait-to-trait relations, stacked above the Trait box.
    tx = positions["Trait"][0] + w / 2
    ty = positions["Trait"][1] + h
    for offset, label, color in ((0.085, "homologousTo", _BLUE),
                                 (0.185, "convergentWith", _RED)):
        ax.annotate("", xy=(tx - 0.058, ty + offset), xytext=(tx + 0.058, ty + offset),
                    arrowprops=dict(arrowstyle="<|-|>", lw=0.8, color=color,
                                    connectionstyle="arc3,rad=0.40"))
        ax.text(tx, ty + offset + 0.048, label, ha="center", va="bottom",
                fontsize=6.3, color=color)
    ax.text(tx, ty + 0.285, "mutually exclusive between any two Trait nodes;\n"
                            "the phylogeny decides, not visual similarity",
            ha="center", va="bottom", fontsize=6.0, color=_GREY)

    # derivedFrom, below the Trait box.
    ax.annotate("", xy=(tx - 0.055, ty - h - 0.055), xytext=(tx + 0.055, ty - h - 0.055),
                arrowprops=dict(arrowstyle="-|>", lw=0.8, color=_GREEN,
                                connectionstyle="arc3,rad=-0.45"))
    ax.text(tx, ty - h - 0.115, "derivedFrom\n(ancestral-state change, r = 1)",
            ha="center", va="top", fontsize=6.3, color=_GREEN)

    # tradesOffWith, above the Function box.
    fx = positions["Function"][0] + w / 2
    fy = positions["Function"][1] + h
    ax.annotate("", xy=(fx - 0.055, fy + 0.085), xytext=(fx + 0.055, fy + 0.085),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.8, color=_ORANGE,
                                connectionstyle="arc3,rad=0.40"))
    ax.text(fx, fy + 0.133, "tradesOffWith", ha="center", va="bottom",
            fontsize=6.3, color=_ORANGE)

    ax.text(0.5, 0.005, "every edge carries a provenance record "
                        "p = (source, version, license, r, u) and a support weight w",
            ha="center", va="bottom", fontsize=6.2, color=_GREY, style="italic")
    ax.set_xlim(0, 0.935)
    ax.set_ylim(0.0, 1.06)
    ax.axis("off")
    return fig


# ------------------------------------------------------------------- Figure 3
def fig_3(seed: int = 20260918) -> plt.Figure:
    """Phylogenetic context on synthetic data (Section 4.3).  SYNTHETIC."""
    from evoproto.phylo import (
        blombergs_k,
        induce_convergence,
        pagels_lambda,
        random_ultrametric_tree,
        stayton_c1,
    )

    tree = random_ultrametric_tree(18, seed=seed)
    x, (tip_a, tip_b) = induce_convergence(tree, seed=seed)
    k = blombergs_k(tree, x)
    lam, lambdas, loglik = pagels_lambda(tree, x)
    c1 = stayton_c1(tree, x, tip_a, tip_b)

    fig, axes = plt.subplots(1, 3, figsize=(COLUMN_DOUBLE, 0.32 * COLUMN_DOUBLE))

    # (a) the tree, drawn by a simple recursive layout
    ax = axes[0]
    tips = tree.tips
    order = {tip: i for i, tip in enumerate(tips)}
    y_of: dict[int, float] = {}

    def y_position(node: int) -> float:
        if node in y_of:
            return y_of[node]
        children = tree.children(node)
        value = (order[node] if not children
                 else float(np.mean([y_position(c) for c in children])))
        y_of[node] = value
        return value

    for node in range(tree.n_nodes):
        parent = int(tree.parent[node])
        if parent < 0:
            continue
        xn, xp = tree.depth(node), tree.depth(parent)
        yn, yp = y_position(node), y_position(parent)
        color = _RED if node in (tip_a, tip_b) else _GREY
        lw = 1.2 if node in (tip_a, tip_b) else 0.7
        ax.plot([xp, xp], [yp, yn], color=_GREY, lw=0.7)
        ax.plot([xp, xn], [yn, yn], color=color, lw=lw)
    ax.set_xlabel("time (root to tips)")
    ax.set_yticks([])
    ax.set_title("(a) random ultrametric tree")

    # (b) the trait, with the two convergent tips marked
    ax = axes[1]
    colors = [_RED if t in (tip_a, tip_b) else _BLUE for t in tips]
    ax.barh(range(len(tips)), x, color=colors, height=0.72)
    ax.set_xlabel("trait value x")
    ax.set_ylabel("tip")
    ax.set_yticks([])
    ax.set_title(f"(b) BM trait with induced convergence\n$C_1$ = {c1:.2f} (red tips)")

    # (c) the profile likelihood of Pagel's lambda
    ax = axes[2]
    ax.plot(lambdas, loglik, color=_BLUE)
    ax.axvline(lam, color=_ORANGE, lw=0.9, ls="--")
    ax.set_xlabel(r"Pagel's $\lambda$")
    ax.set_ylabel("profile log-likelihood")
    ax.set_title(rf"(c) $\hat\lambda$ = {lam:.2f}, Blomberg's $K$ = {k:.2f}")
    ax.grid(True)
    fig.text(0.5, -0.02, "SYNTHETIC data generated by evoproto.phylo; values are illustrative.",
             ha="center", fontsize=6.0, style="italic", color=_GREY)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------- Figure 4
def fig_4() -> plt.Figure:
    """Traceability chain with supports, E and U against their thresholds."""
    from evoproto.gate import Thresholds, evidence_score
    from evoproto.kg import demo_graph
    from evoproto.retrieval import transfer_uncertainty

    graph = demo_graph()
    chain = graph.evidence_chain("par:flexural_rigidity_per_mass")[0]
    origins = graph.independent_origins("mech:sandwich_cellular_stiffening")
    e_value = evidence_score(chain.supports, chain.reconstructed, origins)
    u = transfer_uncertainty(3.0, "hierarchical_composite", "monolithic_alloy",
                             "cyclic", "intermittent_inertial")
    thresholds = Thresholds()

    fig = plt.figure(figsize=(COLUMN_DOUBLE, 0.30 * COLUMN_DOUBLE))
    grid = fig.add_gridspec(1, 3, width_ratios=[2.15, 0.55, 0.55], wspace=0.45)

    ax = fig.add_subplot(grid[0, 0])
    labels = ["Organism", "Trait", "Function", "Mechanism", "Eng-\nParameter"]
    w, h, pitch = 0.148, 0.26, 0.212
    for i, label in enumerate(labels):
        _box(ax, (i * pitch, 0.47), w, h, label, fontsize=5.9,
             color="#dce8f0" if i < 4 else "#e3efe6")
    for i, link in enumerate(chain.links):
        start = (i * pitch + w, 0.60)
        end = ((i + 1) * pitch, 0.60)
        _arrow(ax, start, end)
        ax.text((start[0] + end[0]) / 2, 0.76, link.edge_type.value,
                ha="center", va="bottom", fontsize=5.8, color=_GREY)
        ax.text(i * pitch + w / 2 + pitch / 2, 0.42,
                f"s = {link.support:.2f}\n{link.provenance.tag.value}",
                ha="center", va="top", fontsize=5.8, color=_BLUE)
    ax.text(0.0, 0.12, f"independent origins N_conv = {origins:.0f}    "
                       f"reconstructed r = {int(chain.reconstructed)}",
            fontsize=6.2, color=_GREY)
    ax.set_xlim(-0.01, 4 * pitch + w + 0.01)
    ax.set_ylim(0.05, 0.92)
    ax.axis("off")
    ax.set_title("(a) traceability chain with per-edge support and provenance", loc="left")

    for ax_index, (value, threshold, name, good_below) in enumerate(
        [(e_value, thresholds.tau_E, "evidence score $E$", False),
         (u["U"], thresholds.tau_U, "transfer uncertainty $U$", True)]
    ):
        ax = fig.add_subplot(grid[0, ax_index + 1])
        passes = (value <= threshold) if good_below else (value >= threshold)
        ax.bar([0], [value], width=0.5, color=_GREEN if passes else _RED)
        ax.axhline(threshold, color=_GREY, ls="--", lw=0.9)
        ax.text(0.28, threshold, r"$\tau$" + f" = {threshold:.2f}", fontsize=6.0,
                va="bottom", ha="left", color=_GREY)
        ax.set_ylim(0, 1)
        ax.set_xticks([])
        ax.set_title(f"({'b' if ax_index == 0 else 'c'}) {name}\n{value:.2f}")
    fig.text(0.5, -0.04, "SYNTHETIC demonstration graph; supports are illustrative.",
             ha="center", fontsize=6.0, style="italic", color=_GREY)
    return fig


# ------------------------------------------------------------------- Figure 5
def fig_5() -> plt.Figure:
    """Case study: cantilever idealization, section and candidate analogs."""
    fig, axes = plt.subplots(1, 3, figsize=(COLUMN_DOUBLE, 0.30 * COLUMN_DOUBLE))

    # (a) cantilever
    ax = axes[0]
    ax.add_patch(Rectangle((0.0, 0.42), 0.06, 0.30, facecolor=_GREY, edgecolor="none"))
    ax.add_patch(Rectangle((0.06, 0.50), 0.74, 0.14, facecolor=_LIGHT, edgecolor=_GREY, lw=0.8))
    ax.plot([0.06, 0.80], [0.57, 0.40], color=_BLUE, ls="--", lw=0.9)
    _arrow(ax, (0.80, 0.50), (0.80, 0.26), color=_RED)
    ax.text(0.82, 0.36, "$P = m_p a$", fontsize=6.6, color=_RED)
    ax.annotate("", xy=(0.06, 0.82), xytext=(0.80, 0.82),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.7, color=_GREY))
    ax.text(0.43, 0.85, "$L$", fontsize=6.8, ha="center")
    ax.annotate("", xy=(0.80, 0.50), xytext=(0.80, 0.40),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.7, color=_BLUE))
    ax.text(0.86, 0.45, r"$\delta$", fontsize=6.8, color=_BLUE)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0.15, 1.0)
    ax.axis("off")
    ax.set_title("(a) cantilever idealization")

    # (b) section
    ax = axes[1]
    ax.add_patch(Rectangle((0.15, 0.20), 0.60, 0.60, facecolor="#cfd9e0",
                           edgecolor=_GREY, lw=0.9))
    ax.add_patch(Rectangle((0.24, 0.29), 0.42, 0.42, facecolor="#f2f5f7",
                           edgecolor=_GREY, lw=0.7))
    rng = np.random.default_rng(3)
    for _ in range(38):                       # schematic cellular core
        cx, cy = rng.uniform(0.26, 0.64), rng.uniform(0.31, 0.69)
        ax.add_patch(plt.Circle((cx, cy), 0.028, fill=False, lw=0.45, color=_GREY))
    ax.annotate("", xy=(0.15, 0.13), xytext=(0.75, 0.13),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.7, color=_GREY))
    ax.text(0.45, 0.06, "$b$", fontsize=6.8, ha="center")
    ax.annotate("", xy=(0.83, 0.20), xytext=(0.83, 0.80),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.7, color=_GREY))
    ax.text(0.87, 0.48, "$h$", fontsize=6.8)
    ax.annotate("", xy=(0.15, 0.85), xytext=(0.24, 0.85),
                arrowprops=dict(arrowstyle="<|-|>", lw=0.7, color=_ORANGE))
    ax.text(0.14, 0.90, "$t$", fontsize=6.8, color=_ORANGE)
    ax.text(0.45, 0.50, r"core $\bar\rho$", fontsize=6.4, ha="center", color=_GREY)
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")
    ax.set_title("(b) thin-walled section with cellular core")

    # (c) candidate analogs
    ax = axes[2]
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0, 1.0)
    ax.axis("off")
    ax.set_title("(c) candidate analogs, independent origins")
    centres = [(0.18, 0.62), (0.50, 0.62), (0.82, 0.62)]
    names = ["avian long bone", "bamboo culm", "echinoid stereom"]
    for (cx, cy), name in zip(centres, names):
        ax.add_patch(plt.Circle((cx, cy), 0.115, facecolor="#dce8f0",
                                edgecolor=_GREY, lw=0.8))
        ax.text(cx, cy - 0.20, name, ha="center", fontsize=6.0)
    rng = np.random.default_rng(11)
    for angle in np.linspace(0, 2 * np.pi, 9)[:-1]:   # struts
        ax.plot([0.18, 0.18 + 0.105 * np.cos(angle)],
                [0.62, 0.62 + 0.105 * np.sin(angle)], color=_GREY, lw=0.4)
    for y in (0.55, 0.62, 0.69):                      # diaphragms
        ax.plot([0.40, 0.60], [y, y], color=_GREY, lw=0.5)
    for _ in range(26):                               # stereom
        ax.add_patch(plt.Circle(
            (0.82 + rng.uniform(-0.08, 0.08), 0.62 + rng.uniform(-0.08, 0.08)),
            0.017, fill=False, lw=0.4, color=_GREY))
    for (x0, _), (x1, _) in zip(centres[:-1], centres[1:]):
        ax.annotate("", xy=(x0 + 0.12, 0.62), xytext=(x1 - 0.12, 0.62),
                    arrowprops=dict(arrowstyle="<|-|>", lw=0.7, color=_RED))
    ax.text(0.50, 0.33, "convergentWith (independence tested on the phylogeny)",
            ha="center", fontsize=5.9, color=_RED)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------- Figure 6
def fig_6() -> plt.Figure:
    """Experimental design and validation stages (Section 7.5)."""
    fig, axes = plt.subplots(1, 2, figsize=(COLUMN_DOUBLE, 0.30 * COLUMN_DOUBLE),
                             gridspec_kw={"width_ratios": [1.25, 1.0]})
    ax = axes[0]
    arms = ["A expert", "B generative", "C proposed"]
    tasks = ["T1 bracket", "T2 fin", "T3 finger"]
    for i, arm in enumerate(arms):
        for j, task in enumerate(tasks):
            implemented = j == 0
            _box(ax, (0.10 + j * 0.29, 0.62 - i * 0.22), 0.26, 0.17,
                 f"{arm[0]} x {task[:2]}\n10 seeded replicates",
                 color="#dce8f0" if implemented else "#f3f0ea", fontsize=5.6)
    for j, task in enumerate(tasks):
        ax.text(0.23 + j * 0.29, 0.84, task, ha="center", fontsize=6.4, fontweight="bold")
    for i, arm in enumerate(arms):
        ax.text(0.07, 0.705 - i * 0.22, arm, ha="right", va="center", fontsize=6.4,
                fontweight="bold")
    ax.text(0.5, 0.11, "metrics per cell: FSR (Eq. 20), HV (Eq. 21), D (Eq. 22), ITS (Eq. 23)",
            ha="center", fontsize=6.0, color=_GREY)
    ax.text(0.5, 0.03, "T2 and T3 evaluators: NEEDS INPUT (partner solvers)",
            ha="center", fontsize=5.8, color=_ORANGE, style="italic")
    ax.set_xlim(-0.12, 1.0)
    ax.set_ylim(0, 0.95)
    ax.axis("off")
    ax.set_title("(a) factorial design: 3 arms x 3 tasks x 10 replicates", loc="left")

    ax = axes[1]
    stages = [
        "phylogenetic block split\n(held-out clades; no leakage by descent)",
        "ablation\n(no convergence / no reconstructions /\nno trade-offs / gate disabled)",
        "numerical verification\n(FE, buckling, manufacturability)",
        "physical test\n(9 printed brackets: mass, cantilever stiffness)",
    ]
    for i, stage in enumerate(stages):
        y = 0.80 - i * 0.21
        _box(ax, (0.06, y), 0.88, 0.16, stage, fontsize=6.0,
             color="#e3efe6" if i >= 2 else "#dce8f0")
        if i:
            _arrow(ax, (0.50, y + 0.21), (0.50, y + 0.16))
    ax.set_xlim(0, 1.0)
    ax.set_ylim(0.10, 1.0)
    ax.axis("off")
    ax.set_title("(b) validation stages", loc="left")
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------- Figure 7
def fig_7(replicates: int = 10, population: int = 40, generations: int = 25) -> plt.Figure:
    """Synthetic dry run of the protocol code on task T1 (Section 7.7).  SYNTHETIC."""
    from evoproto.design import BracketSpec, bounds_array
    from evoproto.experiment import run_cell

    spec = BracketSpec()
    lower, upper = bounds_array(spec)
    colors = {"A": _ORANGE, "B": _BLUE, "C": _GREEN}

    cells = {
        arm: [run_cell("T1", arm, r, population, generations, spec)
              for r in range(replicates)]
        for arm in ("A", "B", "C")
    }

    fig, axes = plt.subplots(1, 3, figsize=(COLUMN_DOUBLE, 0.31 * COLUMN_DOUBLE))

    # (a) final populations of replicate 0 in the mass-deflection plane
    ax = axes[0]
    from evoproto.data import stable_seed
    from evoproto.design import (
        analog_prior_sampler,
        evaluate_population,
        template_ratio_sampler,
        uniform_sampler,
    )
    from evoproto.optimize import (
        constrained_search,
        heuristic_refinement_search,
    )

    def evaluator(x):
        f, g, _ = evaluate_population(x, spec)
        return f, g

    for arm in ("A", "B", "C"):
        seed = stable_seed("T1", arm, 0)
        if arm == "A":
            result = heuristic_refinement_search(
                evaluator, template_ratio_sampler(spec), lower, upper,
                n_variants=4, rounds=generations, seed=seed, arm=arm)
        else:
            sampler = uniform_sampler(spec) if arm == "B" else analog_prior_sampler(spec)
            result = constrained_search(evaluator, sampler, lower, upper,
                                        population, generations, seed=seed, arm=arm)
        ax.scatter(result.f[:, 0] * 1e3, result.f[:, 1] * 1e6, s=7,
                   color=colors[arm], alpha=0.75, label=f"arm {arm}", edgecolors="none")
    ax.axvline(spec.mass_max * 1e3, color=_GREY, ls="--", lw=0.8)
    ax.axhline(spec.delta_max * 1e6, color=_GREY, ls="--", lw=0.8)
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("mass (g)")
    ax.set_ylabel(r"tip deflection ($\mu$m)")
    ax.set_title("(a) final populations, replicate 0")
    ax.legend(frameon=False, loc="upper right")
    ax.grid(True, which="both")

    # (b) feasible fraction per generation, mean and range
    ax = axes[1]
    for arm in ("A", "B", "C"):
        curves = np.array([[entry["feasible_fraction"] for entry in cell.log]
                           for cell in cells[arm]])
        gens = np.arange(1, curves.shape[1] + 1)
        ax.plot(gens, curves.mean(axis=0), color=colors[arm], label=f"arm {arm}")
        ax.fill_between(gens, curves.min(axis=0), curves.max(axis=0),
                        color=colors[arm], alpha=0.16, linewidth=0)
    ax.set_xlabel("generation")
    ax.set_ylabel("feasible fraction of population")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("(b) constraint satisfaction")
    ax.legend(frameon=False, loc="center right")
    ax.grid(True)

    # (c) normalized hypervolume over replicates
    ax = axes[2]
    data = [[cell.metrics["HV"] for cell in cells[arm]] for arm in ("A", "B", "C")]
    try:      # Matplotlib >= 3.9 renamed the argument
        parts = ax.boxplot(data, tick_labels=["A", "B", "C"], widths=0.5,
                           patch_artist=True)
    except TypeError:
        parts = ax.boxplot(data, labels=["A", "B", "C"], widths=0.5, patch_artist=True)
    for patch, arm in zip(parts["boxes"], ("A", "B", "C")):
        patch.set_facecolor(colors[arm])
        patch.set_alpha(0.45)
        patch.set_linewidth(0.7)
    for element in ("medians", "whiskers", "caps"):
        for item in parts[element]:
            item.set_linewidth(0.7)
            item.set_color(_GREY)
    ax.set_xlabel("arm")
    ax.set_ylabel("normalized hypervolume")
    ax.set_title(f"(c) HV over {replicates} replicates")
    ax.grid(True, axis="y")
    fig.text(0.5, -0.03, "SYNTHETIC; pipeline validation only - no inference about H1-H3.",
             ha="center", fontsize=6.0, style="italic", color=_GREY)
    fig.tight_layout()
    return fig


# ------------------------------------------------------------------- Figure 8
def fig_8() -> plt.Figure:
    """Evidence-gated decision map in the (E, U) plane (Section 4.6)."""
    from evoproto.gate import Decision, Thresholds, decide

    thresholds = Thresholds()
    e_grid = np.linspace(0, 1, 201)
    u_grid = np.linspace(0, 1, 201)
    field = np.zeros((u_grid.size, e_grid.size))
    for i, u in enumerate(u_grid):
        for j, e in enumerate(e_grid):
            # decide() is driven by the chain supports, so a flat chain whose
            # supports equal e reproduces E = e exactly (no reconstruction,
            # no convergence bonus) - the map is drawn by the gate itself.
            result = decide(True, [e] * 4, u, thresholds=thresholds)
            field[i, j] = 1.0 if result.decision is Decision.RECOMMEND else 0.0

    fig, ax = plt.subplots(figsize=(COLUMN_SINGLE, 0.85 * COLUMN_SINGLE))
    ax.imshow(field, origin="lower", extent=(0, 1, 0, 1), aspect="auto",
              cmap=matplotlib.colors.ListedColormap(["#f4e7e3", "#e0eee5"]))
    ax.axvline(thresholds.tau_E, color=_GREY, ls="--", lw=0.9)
    ax.axhline(thresholds.tau_U, color=_GREY, ls="--", lw=0.9)
    ax.text(0.80, 0.22, "RECOMMEND\n(engineer approves)", ha="center", fontsize=6.4,
            color=_GREEN)
    ax.text(0.28, 0.22, "ABSTAIN\nmissing-evidence\nreport", ha="center", fontsize=6.4,
            color=_RED)
    ax.text(0.55, 0.80, "ABSTAIN: transfer uncertainty above budget", ha="center",
            fontsize=6.4, color=_RED)
    ax.text(thresholds.tau_E + 0.01, 0.98, r"$\tau_E$", fontsize=6.6, va="top", color=_GREY)
    ax.text(0.99, thresholds.tau_U + 0.01, r"$\tau_U$", fontsize=6.6, ha="right", color=_GREY)
    ax.set_xlabel("evidence score $E$")
    ax.set_ylabel("transfer uncertainty $U$")
    ax.set_title("candidates that passed numerical verification\n"
                 "(others are REJECTed regardless of position)", fontsize=7)
    return fig


#: Figure identifier -> builder.
FIGURES: dict[str, Callable[[], plt.Figure]] = {
    "fig1": fig_1,
    "fig2": fig_2,
    "fig3": fig_3,
    "fig4": fig_4,
    "fig5": fig_5,
    "fig6": fig_6,
    "fig7": fig_7,
    "fig8": fig_8,
}


def render_all(
    directory: str | Path = "figures",
    names: Iterable[str] | None = None,
    formats: Sequence[str] = ("pdf", "png"),
) -> list[Path]:
    """Render figures to ``directory`` and return the paths written."""
    set_style()
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for name in (names or FIGURES):
        builder = FIGURES[name]
        figure = builder()
        for extension in formats:
            path = directory / f"{name}.{extension}"
            figure.savefig(path)
            written.append(path)
        plt.close(figure)
    return written
