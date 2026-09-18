"""Regenerate every figure of the paper from code.

``python -m evoproto.cli figures --outdir figures`` writes Figs. 1-8.  Figures
that display numbers (3, 7, 8) are generated from the reference implementation
itself and are labelled SYNTHETIC in their captions, as in the paper.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from . import design as design_module
from . import experiment as experiment_module
from . import optimize as optimize_module
from . import phylo as phylo_module
from .casestudy import CLADE_SAMPLING, build_demo_kg, candidate_analogs, run_case_study
from .gate import EvidenceWeights, GateThresholds, evidence_score
from .kg import CHAIN_EDGES
from .retrieval import TransferWeights

__all__ = ["FIGURES", "generate_all", "generate"]

_TEXT = "#1a1a1a"
_ACCENT = "#b2182b"
_BLUE = "#2166ac"
_GREY = "#8c8c8c"
_FILL = "#eef2f6"


def _style() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 150,
            "savefig.dpi": 300,
            "font.size": 8,
            "axes.labelsize": 8,
            "axes.titlesize": 8.5,
            "axes.edgecolor": _TEXT,
            "axes.linewidth": 0.7,
            "xtick.labelsize": 7,
            "ytick.labelsize": 7,
            "legend.fontsize": 7,
            "legend.frameon": False,
            "savefig.bbox": "tight",
        }
    )


def _box(ax, x, y, w, h, text, fc=_FILL, ec=_TEXT, fontsize=7.0, weight="normal") -> None:
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h,
            boxstyle="round,pad=0.012,rounding_size=0.02",
            linewidth=0.7, facecolor=fc, edgecolor=ec,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, color=_TEXT, weight=weight, wrap=True)


def _arrow(ax, start, end, style="-|>", color=_TEXT, ls="-", lw=0.8) -> None:
    ax.add_patch(
        FancyArrowPatch(
            start, end, arrowstyle=style, mutation_scale=7,
            linewidth=lw, color=color, linestyle=ls, shrinkA=1.5, shrinkB=1.5,
        )
    )


def fig1_architecture(path: str) -> str:
    """Fig. 1: the six layers of the framework, with the feedback path."""
    _style()
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    layers = [
        ("L6  physical testing and engineer approval", "the engineer is the only actor who can release a design"),
        ("L5  verification, Pareto selection, evidence gate", "RECOMMEND / ABSTAIN / REJECT (Eq. 14)"),
        ("L4  AI core", "embeddings - RAG analog search - generative parametric model - constrained MOO"),
        ("L3  evolutionary-engineering knowledge graph", "6 node types, 9 typed edges, provenance on every edge"),
        ("L2  curation and provenance pipeline", "taxonomic reconciliation, trait standardisation, r-flag, Eqs. (1)-(2)"),
        ("L1  data sources", "Open Tree of Life - MorphoBank - PBDB - experimental literature"),
    ]
    height = 0.132
    for i, (title, subtitle) in enumerate(layers):
        y = 0.06 + i * (height + 0.022)
        _box(ax, 0.06, y, 0.80, height, "", fc=_FILL)
        ax.text(0.085, y + height * 0.66, title, fontsize=7.6, weight="bold", color=_TEXT, va="center")
        ax.text(0.085, y + height * 0.28, subtitle, fontsize=6.6, color=_GREY, va="center")
        if i < len(layers) - 1:
            # the forward flow runs downwards, from the data sources (top) to the
            # prototype (bottom)
            _arrow(ax, (0.46, y + height + 0.019), (0.46, y + height + 0.003))
    # the dashed arrow is the feedback of measured results into models, priors
    # and knowledge-graph weights
    _arrow(ax, (0.885, 0.11), (0.885, 0.70), style="-|>", color=_ACCENT, ls=(0, (3, 2)))
    ax.text(0.905, 0.42, "measured results update\nmechanism weights and priors",
            fontsize=6.4, color=_ACCENT, rotation=90, ha="left", va="center")
    ax.set_title("Layered architecture of the evolution-informed design framework", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig2_kg_schema(path: str) -> str:
    """Fig. 2: node and edge types of the EE-KG."""
    _style()
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    nodes = {
        "Organism": (0.06, 0.55),
        "Environment": (0.06, 0.18),
        "Trait": (0.30, 0.55),
        "Function": (0.54, 0.55),
        "Mechanism": (0.76, 0.55),
        "EngParameter": (0.76, 0.18),
    }
    w, h = 0.17, 0.12
    for name, (x, y) in nodes.items():
        _box(ax, x, y, w, h, name, fc="#ffffff", fontsize=7.2, weight="bold")

    def centre(name: str, dx: float = 0.5, dy: float = 0.5) -> Tuple[float, float]:
        x, y = nodes[name]
        return (x + w * dx, y + h * dy)

    _arrow(ax, centre("Organism", 1.0), centre("Trait", 0.0))
    ax.text(0.245, 0.625, "hasTrait", fontsize=6.2, ha="center", color=_TEXT)
    _arrow(ax, centre("Organism", 0.5, 0.0), centre("Environment", 0.5, 1.0))
    ax.text(0.145, 0.375, "livesIn", fontsize=6.2, ha="left", color=_TEXT)
    _arrow(ax, centre("Trait", 1.0), centre("Function", 0.0))
    ax.text(0.485, 0.625, "performs", fontsize=6.2, ha="center", color=_TEXT)
    _arrow(ax, centre("Function", 1.0), centre("Mechanism", 0.0))
    ax.text(0.725, 0.625, "explainedBy", fontsize=6.2, ha="center", color=_TEXT)
    _arrow(ax, centre("Mechanism", 0.5, 0.0), centre("EngParameter", 0.5, 1.0))
    ax.text(0.855, 0.375, "mapsTo", fontsize=6.2, ha="left", color=_TEXT)

    ax.annotate("", xy=(0.33, 0.70), xytext=(0.44, 0.70),
                arrowprops=dict(arrowstyle="<->", lw=0.8, color=_BLUE,
                                connectionstyle="arc3,rad=0.45"))
    ax.text(0.385, 0.795, "homologousTo", fontsize=6.2, ha="center", color=_BLUE)
    ax.annotate("", xy=(0.33, 0.54), xytext=(0.44, 0.54),
                arrowprops=dict(arrowstyle="<->", lw=0.8, color=_ACCENT,
                                connectionstyle="arc3,rad=-0.45"))
    ax.text(0.385, 0.425, "convergentWith", fontsize=6.2, ha="center", color=_ACCENT)
    ax.annotate("", xy=(0.58, 0.70), xytext=(0.67, 0.70),
                arrowprops=dict(arrowstyle="<->", lw=0.8, color=_GREY,
                                connectionstyle="arc3,rad=0.5"))
    ax.text(0.625, 0.80, "tradesOffWith", fontsize=6.2, ha="center", color=_GREY)
    ax.annotate("", xy=(0.345, 0.55), xytext=(0.425, 0.55),
                arrowprops=dict(arrowstyle="-|>", lw=0.8, color=_TEXT,
                                connectionstyle="arc3,rad=-0.9"))
    ax.text(0.385, 0.30, "derivedFrom (r = 1)", fontsize=6.2, ha="center", color=_TEXT)

    ax.text(0.03, 0.06,
            "homologousTo and convergentWith are mutually exclusive between any two trait nodes; "
            "every edge carries a provenance record",
            fontsize=6.4, color=_GREY)
    ax.set_title("Schema of the evolutionary-engineering knowledge graph", fontsize=8.5)
    fig.savefig(path)
    plt.close(fig)
    return path


def fig3_phylogenetic_context(path: str, seed: int = 3, n_tips: int = 24) -> str:
    """Fig. 3: tree, convergent trait and the lambda profile (SYNTHETIC)."""
    _style()
    tree = phylo_module.random_ultrametric_tree(n_tips, seed=seed)
    C = phylo_module.vcv_matrix(tree)
    x, _ = phylo_module.simulate_brownian(tree, sigma2=1.0, seed=seed + 1)

    # Induce a convergent shift in two distantly related tips.
    tips = tree.tips
    distances = [(phylo_module.vcv_matrix(tree)[i, j], i, j)
                 for i in range(len(tips)) for j in range(i + 1, len(tips))]
    _, i, j = min(distances)  # the least shared ancestry = most distant pair
    target = float(np.max(x) + 1.0)
    x = x.copy()
    x[i] = x[j] = target

    K = phylo_module.blombergs_k(x, C)
    lam = phylo_module.pagels_lambda(x, C)
    grid, ll = phylo_module.lambda_profile(x, C)
    c1 = phylo_module.stayton_c1(tree, x, tips[i], tips[j])

    fig, axes = plt.subplots(1, 3, figsize=(6.8, 2.5))

    # (a) the tree
    ax = axes[0]
    y_of: Dict[int, float] = {}
    for order, tip in enumerate(tips):
        y_of[tip] = float(order)
    for node in tree.postorder():
        kids = tree.children[node]
        if kids:
            y_of[node] = float(np.mean([y_of[k] for k in kids]))
    for node in range(tree.n_nodes):
        parent = int(tree.parent[node])
        if parent < 0:
            continue
        colour = _ACCENT if node in (tips[i], tips[j]) else _TEXT
        ax.plot([tree.depth(parent), tree.depth(node)], [y_of[node], y_of[node]],
                color=colour, lw=0.8)
        ax.plot([tree.depth(parent), tree.depth(parent)],
                [y_of[node], y_of[parent]], color=_TEXT, lw=0.6)
    ax.set_yticks([])
    ax.set_xlabel("branch length from root")
    ax.set_title("(a) random ultrametric tree")

    # (b) the trait
    ax = axes[1]
    colours = [_ACCENT if k in (i, j) else _BLUE for k in range(len(tips))]
    ax.scatter(x, np.arange(len(tips)), s=9, c=colours, zorder=3)
    ax.axvline(float(phylo_module.pgls_root(x, C)), color=_GREY, lw=0.7, ls="--")
    ax.set_yticks([])
    ax.set_xlabel("trait value")
    ax.set_title(f"(b) BM trait, induced convergence\n$C_1$ = {c1:.2f} for the two red tips")

    # (c) the lambda profile
    ax = axes[2]
    ax.plot(grid, ll, color=_BLUE, lw=1.0)
    ax.axvline(lam, color=_ACCENT, lw=0.8)
    ax.text(lam, float(np.min(ll)), f"  $\\hat\\lambda$ = {lam:.2f}\n  K = {K:.2f}",
            fontsize=6.6, color=_ACCENT, va="bottom")
    ax.set_xlabel("Pagel's $\\lambda$")
    ax.set_ylabel("profile log-likelihood")
    ax.set_title("(c) profile likelihood")

    fig.suptitle("Phylogenetic context on synthetic data (SYNTHETIC; illustrative)", fontsize=8.5)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path)
    plt.close(fig)
    return path


def fig4_traceability_chain(path: str) -> str:
    """Fig. 4: the chain with its supports, and the two bars feeding Eq. (14)."""
    _style()
    kg = build_demo_kg()
    chain = kg.best_chain("core_relative_density")
    assert chain is not None
    n_conv_w = kg.weighted_independent_origins("sandwich_stiffening", CLADE_SAMPLING)
    E = evidence_score(chain.supports, n_conv_w, chain.reconstruction_only)
    candidate = candidate_analogs(kg)[0]
    U, components = candidate.transfer_uncertainty(TransferWeights())
    thresholds = GateThresholds()

    fig = plt.figure(figsize=(6.8, 2.9))
    grid = fig.add_gridspec(1, 3, width_ratios=[2.6, 0.9, 0.9], wspace=0.75)

    ax = fig.add_subplot(grid[0, 0])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    labels = ["Organism", "Trait", "Function", "Mechanism", "EngParameter"]
    for k, label in enumerate(labels):
        y = 0.88 - k * 0.2
        _box(ax, 0.06, y - 0.07, 0.62, 0.13,
             f"{label}\n{chain.nodes[k]}", fc="#ffffff", fontsize=6.2)
        if k < 4:
            _arrow(ax, (0.37, y - 0.075), (0.37, y - 0.128))
            ax.text(0.40, y - 0.10,
                    f"{CHAIN_EDGES[k].value}   s = {chain.supports[k]:.2f}   "
                    f"[{chain.provenance[k].tag.value}]",
                    fontsize=6.0, va="center", color=_TEXT)
    ax.set_title("traceability chain (Eq. 4)", fontsize=8)

    ax = fig.add_subplot(grid[0, 1])
    ax.bar([0], [E], width=0.5, color=_BLUE)
    ax.axhline(thresholds.tau_E, color=_ACCENT, lw=0.9, ls="--")
    ax.text(0.28, thresholds.tau_E, r"  $\tau_E$", color=_ACCENT, fontsize=6.6, va="bottom")
    ax.set_xticks([0])
    ax.set_xticklabels(["E"])
    ax.set_ylim(0, 1.05)
    ax.set_title(f"evidence score\nE = {E:.2f} (Eq. 13)", fontsize=7.4)

    ax = fig.add_subplot(grid[0, 2])
    ax.bar([0], [U], width=0.5, color=_GREY)
    ax.axhline(thresholds.tau_U, color=_ACCENT, lw=0.9, ls="--")
    ax.text(0.28, thresholds.tau_U, r"  $\tau_U$", color=_ACCENT, fontsize=6.6, va="bottom")
    ax.set_xticks([0])
    ax.set_xticklabels(["U"])
    ax.set_ylim(0, 1.05)
    ax.set_title(f"transfer uncertainty\nU = {U:.2f} (Eq. 9)", fontsize=7.4)
    ax.text(
        0.0, -0.22,
        f"$u_{{scale}}$ = {components['u_scale']:.2f}\n"
        f"$u_{{mat}}$ = {components['u_mat']:.2f}\n"
        f"$u_{{load}}$ = {components['u_load']:.2f}",
        transform=ax.transAxes, fontsize=6.2, color=_GREY, ha="center", va="top",
    )
    fig.savefig(path)
    plt.close(fig)
    return path


def fig5_case_study(path: str) -> str:
    """Fig. 5: cantilever idealisation, section, and the three candidate analogs."""
    _style()
    spec = design_module.EOAT_BRACKET
    fig, axes = plt.subplots(1, 3, figsize=(6.8, 2.3))

    ax = axes[0]
    ax.plot([0, 1], [0, 0], color=_TEXT, lw=2.0)
    ax.plot([0, 0], [-0.25, 0.25], color=_TEXT, lw=2.0)
    for y in np.linspace(-0.22, 0.22, 6):
        ax.plot([-0.06, 0], [y - 0.05, y], color=_GREY, lw=0.7)
    _arrow(ax, (1.0, 0.32), (1.0, 0.02), color=_ACCENT)
    ax.text(1.02, 0.18, f"$P$ = {spec.tip_load:.0f} N", fontsize=6.8, color=_ACCENT)
    ax.plot([0, 1], [0, -0.22], color=_BLUE, lw=1.0, ls="--")
    ax.text(0.62, -0.26, r"$\delta$", fontsize=7.2, color=_BLUE)
    ax.annotate("", xy=(0, 0.42), xytext=(1, 0.42), arrowprops=dict(arrowstyle="<->", lw=0.7, color=_TEXT))
    ax.text(0.5, 0.45, f"$L$ = {spec.L * 1000:.0f} mm", fontsize=6.8, ha="center")
    ax.set_xlim(-0.15, 1.3)
    ax.set_ylim(-0.45, 0.6)
    ax.axis("off")
    ax.set_title("(a) cantilever idealisation")

    ax = axes[1]
    b, h, t = 1.0, 1.5, 0.13
    ax.add_patch(plt.Rectangle((0, 0), b, h, facecolor="#cfd8e3", edgecolor=_TEXT, lw=0.9))
    ax.add_patch(plt.Rectangle((t, t), b - 2 * t, h - 2 * t, facecolor="#f6f2e8",
                               edgecolor=_TEXT, lw=0.7, hatch="xxx"))
    ax.annotate("", xy=(0, -0.12), xytext=(b, -0.12), arrowprops=dict(arrowstyle="<->", lw=0.7, color=_TEXT))
    ax.text(b / 2, -0.28, "$b$", fontsize=7.2, ha="center")
    ax.annotate("", xy=(-0.14, 0), xytext=(-0.14, h), arrowprops=dict(arrowstyle="<->", lw=0.7, color=_TEXT))
    ax.text(-0.30, h / 2, "$h$", fontsize=7.2, va="center")
    ax.plot([0, t], [h + 0.10, h + 0.10], color=_ACCENT, lw=1.2)
    ax.text(t + 0.04, h + 0.08, "$t$", fontsize=7.2, color=_ACCENT)
    ax.text(b / 2, h / 2, r"core $\rho$", fontsize=6.8, ha="center", va="center")
    ax.set_xlim(-0.5, 1.4)
    ax.set_ylim(-0.45, 1.95)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.set_title("(b) section, $d = (b, h, t, \\rho)$")

    ax = axes[2]
    ax.axis("off")
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    for k, (title, subtitle) in enumerate(
        [
            ("avian long bone", "thin cortex, internal struts"),
            ("bamboo culm", "hollow, periodic diaphragms"),
            ("echinoid stereom", "open-cell mineral foam"),
        ]
    ):
        y = 0.74 - k * 0.30
        _box(ax, 0.04, y, 0.92, 0.22, "", fc=_FILL)
        ax.text(0.08, y + 0.145, title, fontsize=7.0, weight="bold", va="center")
        ax.text(0.08, y + 0.06, subtitle, fontsize=6.3, color=_GREY, va="center")
    ax.set_title("(c) candidate analogs\n(independence established on the phylogeny)", fontsize=7.4)

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def fig6_experimental_design(path: str) -> str:
    """Fig. 6: the factorial design and the four validation stages."""
    _style()
    fig, axes = plt.subplots(1, 2, figsize=(6.8, 2.6))

    ax = axes[0]
    ax.set_xlim(0, 3)
    ax.set_ylim(0, 3)
    arms = ["A expert", "B generative", "C proposed"]
    tasks = ["T1 bracket", "T2 fin", "T3 gripper"]
    for i in range(3):
        for j in range(3):
            colour = "#dbe6f0" if i == 2 else "#f2f2f2"
            ax.add_patch(plt.Rectangle((j, 2 - i), 1, 1, facecolor=colour, edgecolor=_TEXT, lw=0.6))
            ax.text(j + 0.5, 2 - i + 0.5, "10 seeded\nreplicates", ha="center", va="center", fontsize=6.0)
    ax.set_xticks([0.5, 1.5, 2.5])
    ax.set_xticklabels(tasks, fontsize=6.6)
    ax.set_yticks([0.5, 1.5, 2.5])
    ax.set_yticklabels(list(reversed(arms)), fontsize=6.6)
    ax.set_title("(a) 3 arms x 3 tasks x 10 replicates\nmetrics: FSR, HV, D, ITS", fontsize=7.4)

    ax = axes[1]
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    stages = [
        ("phylogenetic block split", "held-out clades test whether retrieval generalises"),
        ("ablation", "no convergence / no reconstructions / no trade-offs / no gate"),
        ("numerical verification", "FE (linear elastic + buckling) and manufacturability"),
        ("physical test", "9 printed brackets: mass and cantilever stiffness"),
    ]
    for k, (title, subtitle) in enumerate(stages):
        y = 0.78 - k * 0.24
        _box(ax, 0.03, y, 0.94, 0.19, "", fc=_FILL)
        ax.text(0.06, y + 0.125, f"{k + 1}. {title}", fontsize=7.0, weight="bold", va="center")
        ax.text(0.06, y + 0.05, subtitle, fontsize=6.2, color=_GREY, va="center")
        if k < len(stages) - 1:
            _arrow(ax, (0.5, y - 0.002), (0.5, y - 0.045))
    ax.set_title("(b) validation stages", fontsize=7.4)

    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def fig7_dry_run(path: str, replicates: int = 10) -> str:
    """Fig. 7: the synthetic dry run of the protocol code (SYNTHETIC)."""
    _style()
    spec = design_module.EOAT_BRACKET
    lo, hi = design_module.design_bounds(spec)

    def evaluator(X: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        out = design_module.evaluate_population(X, spec)
        return out["F"], out["G"]

    runs: Dict[str, List[optimize_module.SearchResult]] = {}
    for arm in experiment_module.ARMS:
        prior = design_module.PRIORS[arm]
        projection = design_module.template_projection if arm == "A" else None
        runs[arm] = []
        for replicate in range(replicates):
            seed = experiment_module.stable_seed("T1", arm, replicate)
            runs[arm].append(
                optimize_module.search(
                    evaluator,
                    lambda n, rng, prior=prior: prior(n, spec, rng),
                    lo, hi, 40, 25, seed=seed, arm=arm, projection=projection,
                )
            )

    fig, axes = plt.subplots(1, 3, figsize=(6.8, 2.4))
    colours = {"A": _GREY, "B": _BLUE, "C": _ACCENT}

    ax = axes[0]
    for arm, results in runs.items():
        F = results[0].objectives
        ax.scatter(F[:, 0] * 1000.0, F[:, 1] * 1e6, s=7, alpha=0.75,
                   color=colours[arm], label=f"arm {arm}")
    ax.axvline(spec.mass_max * 1000.0, color=_TEXT, lw=0.7, ls="--")
    ax.axhline(spec.delta_max * 1e6, color=_TEXT, lw=0.7, ls="--")
    ax.set_xlabel("mass [g]")
    ax.set_ylabel("tip deflection [$\\mu$m]")
    ax.set_xlim(0, spec.mass_max * 1000.0 * 2.2)
    ax.set_ylim(0, spec.delta_max * 1e6 * 2.2)
    ax.legend(loc="upper right")
    ax.set_title("(a) final populations, replicate 0")

    ax = axes[1]
    for arm, results in runs.items():
        curves = np.asarray([r.feasible_fraction_per_generation for r in results], dtype=float)
        generations = np.arange(1, curves.shape[1] + 1)
        ax.plot(generations, curves.mean(axis=0), color=colours[arm], lw=1.1, label=f"arm {arm}")
        ax.fill_between(generations, curves.min(axis=0), curves.max(axis=0),
                        color=colours[arm], alpha=0.16, linewidth=0)
    ax.set_xlabel("generation")
    ax.set_ylabel("feasible fraction")
    ax.set_ylim(-0.03, 1.03)
    ax.set_title("(b) constraint satisfaction")

    ax = axes[2]
    data = []
    for arm, results in runs.items():
        values = []
        for r in results:
            values.append(
                optimize_module.normalized_hypervolume(r.archive_objectives, spec.reference_point)
                if r.archive.shape[0] else 0.0
            )
        data.append(values)
    # 'labels' was renamed to 'tick_labels' in matplotlib 3.9; set them separately
    # so the figure code works across the supported matplotlib range.
    parts = ax.boxplot(data, widths=0.55, patch_artist=True)
    ax.set_xticks(range(1, len(data) + 1))
    ax.set_xticklabels(list(runs))
    for patch, arm in zip(parts["boxes"], runs):
        patch.set_facecolor(colours[arm])
        patch.set_alpha(0.45)
    for element in ("medians", "whiskers", "caps"):
        for item in parts[element]:
            item.set_color(_TEXT)
    ax.set_xlabel("arm")
    ax.set_ylabel("normalised hypervolume")
    ax.set_title("(c) front quality")

    fig.suptitle("Synthetic dry run of the protocol code on task T1 (SYNTHETIC; pipeline validation only)",
                 fontsize=8)
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path)
    plt.close(fig)
    return path


def fig8_decision_map(path: str) -> str:
    """Fig. 8: the evidence-gated decision map in the (E, U) plane."""
    _style()
    thresholds = GateThresholds()
    fig, ax = plt.subplots(figsize=(3.6, 3.0))
    ax.add_patch(plt.Rectangle((thresholds.tau_E, 0), 1 - thresholds.tau_E, thresholds.tau_U,
                               facecolor="#d6e6d2", edgecolor="none"))
    ax.add_patch(plt.Rectangle((0, 0), thresholds.tau_E, 1, facecolor="#f5e6c8", edgecolor="none"))
    ax.add_patch(plt.Rectangle((thresholds.tau_E, thresholds.tau_U), 1 - thresholds.tau_E,
                               1 - thresholds.tau_U, facecolor="#f5e6c8", edgecolor="none"))
    ax.axvline(thresholds.tau_E, color=_TEXT, lw=0.8, ls="--")
    ax.axhline(thresholds.tau_U, color=_TEXT, lw=0.8, ls="--")
    ax.text(0.75, 0.22, "RECOMMEND\n(subject to engineer\napproval)", ha="center", fontsize=6.8)
    ax.text(0.24, 0.72, "ABSTAIN\nweak evidence", ha="center", fontsize=6.8)
    ax.text(0.75, 0.75, "ABSTAIN\nuncertain transfer", ha="center", fontsize=6.8)

    case = run_case_study(population_size=24, generations=12)
    for prototype in case["prototypes"]:
        ax.scatter(prototype["gate"]["E"], prototype["gate"]["U"], s=26, color=_ACCENT,
                   zorder=4, edgecolor="white", linewidth=0.5)
    ax.text(case["prototypes"][0]["gate"]["E"], case["prototypes"][0]["gate"]["U"] - 0.06,
            "case study", fontsize=6.4, color=_ACCENT, ha="center")

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_xlabel("evidence score $E$ (Eq. 13)")
    ax.set_ylabel("transfer uncertainty $U$ (Eq. 9)")
    ax.set_title("Evidence-gated decision map\n(candidates that passed verification)", fontsize=8)
    fig.savefig(path)
    plt.close(fig)
    return path


#: Every figure of the paper, by name.
FIGURES = {
    "fig1_architecture": fig1_architecture,
    "fig2_kg_schema": fig2_kg_schema,
    "fig3_phylogenetic_context": fig3_phylogenetic_context,
    "fig4_traceability_chain": fig4_traceability_chain,
    "fig5_case_study": fig5_case_study,
    "fig6_experimental_design": fig6_experimental_design,
    "fig7_dry_run": fig7_dry_run,
    "fig8_decision_map": fig8_decision_map,
}


def generate(name: str, outdir: str = "figures", extension: str = "png") -> str:
    """Generate one figure by name."""
    if name not in FIGURES:
        raise KeyError(f"unknown figure {name!r}; available: {sorted(FIGURES)}")
    os.makedirs(outdir, exist_ok=True)
    return FIGURES[name](os.path.join(outdir, f"{name}.{extension}"))


def generate_all(outdir: str = "figures", extension: str = "png") -> List[str]:
    """Regenerate every figure of the paper."""
    os.makedirs(outdir, exist_ok=True)
    return [generate(name, outdir, extension) for name in FIGURES]
