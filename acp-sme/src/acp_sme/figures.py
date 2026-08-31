"""Figures 3-6 of the article.

matplotlib is an optional dependency: the numerical results, the CSV exports
and the test suite never require it, so the experiment reproduces on a bare
Python installation (R8).  Import this module only when plotting.
"""

from __future__ import annotations

from pathlib import Path
from statistics import fmean
from typing import Dict, List, Sequence

from .experiment import CONDITION_LABELS, CONDITIONS, PrimaryResults
from .metrics import daily_coverage, mean_ci
from .scenarios import ARCHETYPES, HORIZON_DAYS

#: Colour-blind-safe qualitative palette (Okabe-Ito subset).
COLOURS: Dict[str, str] = {
    "static": "#767676",
    "monthly": "#0072B2",
    "acp": "#D55E00",
}
ARCHETYPE_COLOURS = ("#0072B2", "#009E73", "#CC79A7")


def _pyplot():
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - exercised only without matplotlib
        raise SystemExit(
            "matplotlib is required for figures. Install it with "
            "`pip install matplotlib`, or run the experiment without --figures."
        ) from exc
    plt.rcParams.update(
        {
            "font.size": 9,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.grid": True,
            "grid.alpha": 0.25,
            "grid.linewidth": 0.6,
            "figure.dpi": 150,
        }
    )
    return plt


def figure3_event_catalog(path: Path) -> Path:
    """Synthetic business-change catalog and event timing."""
    plt = _pyplot()
    fig, ax = plt.subplots(figsize=(8.2, 3.2))
    for row, (archetype, colour) in enumerate(zip(ARCHETYPES, ARCHETYPE_COLOURS)):
        y = len(ARCHETYPES) - row
        ax.hlines(y, 0, HORIZON_DAYS, color="#CCCCCC", linewidth=1.0, zorder=1)
        days = [e.day for e in archetype.events]
        ax.scatter(days, [y] * len(days), s=46, color=colour, zorder=3, edgecolor="white")
        for event in archetype.events:
            ax.annotate(
                str(event.day),
                (event.day, y),
                textcoords="offset points",
                xytext=(0, 9),
                ha="center",
                fontsize=7.5,
                color=colour,
            )
        ax.text(-3, y, archetype.label, ha="right", va="center", fontsize=9)
    ax.set_xlim(-1, HORIZON_DAYS + 1)
    ax.set_ylim(0.4, len(ARCHETYPES) + 0.8)
    ax.set_yticks([])
    ax.set_xlabel("Simulation day")
    ax.set_title(
        "Figure 3. Synthetic business-change catalog and event timing\n"
        "(no operating enterprise or observed incident is represented)",
        fontsize=9.5,
    )
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def figure4_primary(results: PrimaryResults, path: Path) -> Path:
    """Mean coverage, adaptation delay and modelled review burden."""
    plt = _pyplot()
    fig, axes = plt.subplots(1, 3, figsize=(9.5, 3.1))
    panels = (
        ("mean_coverage", 100.0, "Mean modelled coverage (%)", "Capability-demand coverage"),
        ("adaptation_delay", 1.0, "Mean adaptation delay (days)", "Stale-profile interval"),
        ("review_hours", 1.0, "Modelled review hours / 120 d", "Assigned review burden"),
    )
    for ax, (attribute, scale, ylabel, title) in zip(axes, panels):
        means, errs, colours, labels = [], [], [], []
        for condition in CONDITIONS:
            values = [
                scale * getattr(o, attribute) for o in results.outcomes[condition]
            ]
            interval = mean_ci(values)
            means.append(interval.mean)
            errs.append(interval.mean - interval.low)
            colours.append(COLOURS[condition])
            labels.append(CONDITION_LABELS[condition])
        ax.bar(labels, means, yerr=errs, capsize=4, color=colours, width=0.62)
        ax.set_ylabel(ylabel, fontsize=8.5)
        ax.set_title(title, fontsize=9)
        ax.tick_params(axis="x", labelrotation=18, labelsize=8)
    fig.suptitle(
        "Figure 4. Synthetic model output across 90 traces; error bars are 95% CIs "
        "over complete traces",
        fontsize=9.5,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.93))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def figure5_trajectories(results: PrimaryResults, path: Path) -> Path:
    """Mean daily coverage trajectory per condition, with event markers."""
    plt = _pyplot()
    fig, axes = plt.subplots(1, len(ARCHETYPES), figsize=(10.5, 3.2), sharey=True)
    for ax, archetype in zip(axes, ARCHETYPES):
        traces = [t for t in results.traces if t.archetype == archetype.key]
        for condition in CONDITIONS:
            series = [daily_coverage(t, condition) for t in traces]
            mean_series = [
                100.0 * fmean([s[day] for s in series]) for day in range(HORIZON_DAYS)
            ]
            ax.plot(
                range(HORIZON_DAYS),
                mean_series,
                label=CONDITION_LABELS[condition],
                color=COLOURS[condition],
                linewidth=1.5,
            )
        for event in archetype.events:
            ax.axvline(event.day, color="#999999", linestyle="--", linewidth=0.7, zorder=0)
        ax.set_title(f"{archetype.label} (budget {archetype.budget})", fontsize=9)
        ax.set_xlabel("Simulation day")
    axes[0].set_ylabel("Mean modelled coverage (%)")
    axes[-1].legend(fontsize=7.5, loc="lower left", framealpha=0.9)
    fig.suptitle(
        "Figure 5. Modelled capability-demand coverage after business and technology "
        "changes\n(dashed lines mark designed material events; model behaviour, not "
        "observed risk reduction)",
        fontsize=9.5,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.88))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def figure6_sensitivity(rows: Sequence[Dict[str, float]], path: Path) -> Path:
    """Sensitivity of coverage and false-alert burden to threshold and budget."""
    plt = _pyplot()
    fig, (left, right) = plt.subplots(1, 2, figsize=(8.6, 3.2))
    taus = sorted({r["tau"] for r in rows})
    factors = sorted({r["budget_factor"] for r in rows})
    index = {(r["budget_factor"], r["tau"]): r for r in rows}

    for factor, colour in zip(factors, ARCHETYPE_COLOURS):
        left.plot(
            taus,
            [index[(factor, t)]["coverage_pct"] for t in taus],
            marker="o",
            color=colour,
            label=f"budget x{factor:.2f}",
            linewidth=1.5,
        )
    left.set_xlabel("Material-change threshold tau")
    left.set_ylabel("Mean modelled coverage (%)")
    left.set_title("Coverage is resource-limited", fontsize=9)
    left.legend(fontsize=7.5)

    observed = [index[(factors[0], t)]["false_alerts"] for t in taus]
    expected = [index[(factors[0], t)]["expected_false_alerts"] for t in taus]
    right.plot(taus, observed, marker="o", color=COLOURS["acp"], label="observed (30 traces)")
    right.plot(
        taus, expected, marker="s", linestyle="--", color="#767676",
        label="design expectation 119 p(tau)",
    )
    right.set_xlabel("Material-change threshold tau")
    right.set_ylabel("False alerts / 120 days")
    right.set_title("Nuisance alerts fall with tau by construction", fontsize=9)
    right.legend(fontsize=7.5)

    fig.suptitle(
        "Figure 6. Synthetic sensitivity of ACP-SME coverage and false-alert burden",
        fontsize=9.5,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


def render_all(
    results: PrimaryResults, sensitivity: Sequence[Dict[str, float]], directory: Path
) -> List[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    return [
        figure3_event_catalog(directory / "figure3_event_catalog.png"),
        figure4_primary(results, directory / "figure4_primary_comparison.png"),
        figure5_trajectories(results, directory / "figure5_coverage_trajectories.png"),
        figure6_sensitivity(sensitivity, directory / "figure6_sensitivity.png"),
    ]
