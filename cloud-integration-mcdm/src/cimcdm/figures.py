"""Figures 2-5 of the article.

Every function returns a Matplotlib figure and, when ``path`` is given, also
writes it to disk. Styling is intentionally plain so the figures render the same
way in Colab, in a notebook export and in a headless script.

The backend is deliberately left alone here: Matplotlib already falls back to Agg
when no display is available, and forcing it would fight the inline backend in a
notebook. Headless callers such as :mod:`cimcdm.cli` select Agg themselves.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

METHOD_COLORS = {"NSGA-II": "#1f77b4", "NSGA-III": "#d62728", "WSM": "#2ca02c"}
OBJECTIVE_LABELS = ("f1: benefit shortfall", "f2: normalized cost", "f3: normalized risk")


def _save(fig: plt.Figure, path: str | Path | None, dpi: int = 200) -> plt.Figure:
    if path is not None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(path, dpi=dpi, bbox_inches="tight")
    return fig


def figure_convergence(
    convergence: pd.DataFrame, exact_hypervolume: float, path=None
) -> plt.Figure:
    """Figure 2: archive hypervolume by generation, with pointwise 95% CIs."""
    fig, ax = plt.subplots(figsize=(7.2, 4.4))
    generation = convergence["generation"].to_numpy()

    for method, key in (("NSGA-II", "nsga2"), ("NSGA-III", "nsga3")):
        mean = convergence[f"{key}_mean"].to_numpy()
        half = convergence[f"{key}_ci"].to_numpy()
        color = METHOD_COLORS[method]
        ax.plot(generation, mean, label=method, color=color, linewidth=1.8)
        ax.fill_between(generation, mean - half, mean + half, color=color, alpha=0.18)

    ax.axhline(
        exact_hypervolume,
        linestyle="--",
        color="black",
        linewidth=1.2,
        label=f"Exact front ({exact_hypervolume:.6f})",
    )
    ax.set_xlabel("Generation")
    ax.set_ylabel("Archive hypervolume (higher is better)")
    ax.set_title("Convergence of the nondominated archive")
    ax.legend(loc="lower right", frameon=False)
    ax.grid(alpha=0.25)
    fig.tight_layout()
    return _save(fig, path)


def figure_metric_distributions(runs: pd.DataFrame, path=None) -> plt.Figure:
    """Figure 3: per-run distributions of hypervolume, IGD+ and spacing."""
    metrics = [
        ("hypervolume", "Hypervolume (higher is better)"),
        ("igd_plus", "IGD+ (lower is better)"),
        ("spacing", "Spacing (lower is better)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2))

    for ax, (metric, title) in zip(axes, metrics):
        groups = [
            runs[runs["method"] == method][metric].to_numpy()
            for method in ("NSGA-II", "NSGA-III")
        ]
        # Set tick labels separately: boxplot's own keyword was renamed from
        # `labels` to `tick_labels` in Matplotlib 3.9 and removed in 3.11.
        ax.boxplot(groups, widths=0.5, showfliers=False)
        ax.set_xticks([1, 2], ["NSGA-II", "NSGA-III"])
        for position, (method, values) in enumerate(
            zip(("NSGA-II", "NSGA-III"), groups), start=1
        ):
            jitter = np.random.default_rng(0).normal(0, 0.045, len(values))
            ax.scatter(
                position + jitter, values, s=16, alpha=0.65,
                color=METHOD_COLORS[method], zorder=3,
            )
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25, axis="y")

    fig.suptitle("Run-level metric distributions across matched seeds", fontsize=12)
    fig.tight_layout()
    return _save(fig, path)


def figure_front_projections(
    exact_front: np.ndarray,
    nsga2_front: np.ndarray,
    nsga3_front: np.ndarray,
    wsm_front: np.ndarray,
    path=None,
) -> plt.Figure:
    """Figure 4: pairwise objective projections of every method against the exact front."""
    pairs = [(0, 1), (0, 2), (1, 2)]
    fig, axes = plt.subplots(1, 3, figsize=(13.5, 4.4))

    for ax, (i, j) in zip(axes, pairs):
        ax.scatter(
            exact_front[:, i], exact_front[:, j], s=10, color="0.75",
            label="Exact front", zorder=1,
        )
        ax.scatter(
            nsga2_front[:, i], nsga2_front[:, j], s=9, alpha=0.8,
            color=METHOD_COLORS["NSGA-II"], label="NSGA-II", zorder=2,
        )
        ax.scatter(
            nsga3_front[:, i], nsga3_front[:, j], s=9, alpha=0.8,
            color=METHOD_COLORS["NSGA-III"], label="NSGA-III", zorder=3,
        )
        ax.scatter(
            wsm_front[:, i], wsm_front[:, j], s=42, marker="x",
            color=METHOD_COLORS["WSM"], label="WSM", zorder=4,
        )
        ax.set_xlabel(OBJECTIVE_LABELS[i])
        ax.set_ylabel(OBJECTIVE_LABELS[j])
        ax.grid(alpha=0.25)

    axes[0].legend(loc="upper right", frameon=False, fontsize=8)
    fig.suptitle("Pairwise objective projections (all objectives minimized)", fontsize=12)
    fig.tight_layout()
    return _save(fig, path)


def figure_sensitivity(grid_frame: pd.DataFrame, path=None) -> plt.Figure:
    """Figure 5: exact hypervolume and knee benefit over the temporal-rate grid."""
    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.4))
    panels = [
        ("hypervolume", "(a) Exact-front hypervolume"),
        ("knee_benefit", "(b) Knee-portfolio benefit"),
    ]

    for ax, (column, title) in zip(axes, panels):
        table = grid_frame.pivot(index="s_alpha", columns="s_beta", values=column)
        image = ax.imshow(table.to_numpy(), origin="lower", cmap="viridis", aspect="auto")
        ax.set_xticks(range(len(table.columns)), [f"{v:g}" for v in table.columns])
        ax.set_yticks(range(len(table.index)), [f"{v:g}" for v in table.index])
        ax.set_xlabel(r"$s_\beta$ (economic-benefit accumulation)")
        ax.set_ylabel(r"$s_\alpha$ (adaptation)")
        ax.set_title(title, fontsize=10)
        for row in range(table.shape[0]):
            for col in range(table.shape[1]):
                ax.text(
                    col, row, f"{table.to_numpy()[row, col]:.4f}",
                    ha="center", va="center", fontsize=7, color="white",
                )
        fig.colorbar(image, ax=ax, fraction=0.046)

    fig.suptitle("Exact sensitivity to temporal-rate multipliers", fontsize=12)
    fig.tight_layout()
    return _save(fig, path)


def figure_response_curves(model, path=None) -> plt.Figure:
    """Supplementary: the three bounded response functions (Eqs. 8-10)."""
    inst = model.instance
    t = np.linspace(0, model.scenario.horizon, 200)
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 3.8))

    curves = [
        (
            inst.p0[:, None] + inst.delta_p[:, None] * (1 - np.exp(-np.outer(inst.alpha, t))),
            "Business performance $P_i(t)$",
        ),
        (
            inst.e0[:, None] + inst.delta_e[:, None] * (1 - np.exp(-np.outer(inst.beta, t))),
            "Economic benefit $E_i(t)$",
        ),
        (
            inst.risk_residual[:, None]
            + (inst.risk_initial - inst.risk_residual)[:, None] * np.exp(-np.outer(inst.rho, t)),
            "Residual risk $r_i(t)$",
        ),
    ]

    for ax, (values, title) in zip(axes, curves):
        for row in values:
            ax.plot(t, row, linewidth=1.0, alpha=0.7)
        ax.set_xlabel("t, months")
        ax.set_title(title, fontsize=10)
        ax.grid(alpha=0.25)

    fig.suptitle("Bounded monotone temporal response functions", fontsize=12)
    fig.tight_layout()
    return _save(fig, path)
