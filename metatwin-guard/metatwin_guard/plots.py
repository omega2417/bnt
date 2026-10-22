"""Figures 1, 2 and 4 of the article plus executed-analysis plots (matplotlib)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

from . import config  # noqa: E402

# Validated categorical slots 1-3 (blue, orange, aqua) and neutral inks.
SERIES = {"rules": "#2a78d6", "robust": "#eb6834", "hybrid": "#1baf7a",
          "integrity_only": "#6250d6", "rules_integrity": "#eda100"}
INK, INK2, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#fcfcfb"
IMPL, PROP = "#2a78d6", "#8a8984"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
    "text.color": INK, "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
})


def _save(fig, out: Path | None, name: str) -> None:
    if out is None:
        return
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png", dpi=360, bbox_inches="tight")
    fig.savefig(out / f"{name}.svg", bbox_inches="tight")


def _box(ax, x, y, w, h, text, proposed=False, fs=8.5):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08",
                                fc=SURFACE, ec=PROP if proposed else IMPL, lw=1.4,
                                ls=(0, (4, 3)) if proposed else "-"))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs,
            color=INK2 if proposed else INK, wrap=True)


def _arrow(ax, a, b, dashed=False, color=INK2):
    ax.add_patch(FancyArrowPatch(a, b, arrowstyle="-|>", mutation_scale=10, lw=1.1, color=color,
                                 ls=(0, (4, 3)) if dashed else "-"))


def figure_topology(out: Path | None = None):
    """Figure 1: confirmed topology (solid) vs proposed research overlay (dashed)."""
    fig, ax = plt.subplots(figsize=(10, 5.6))
    ax.set_xlim(0, 10); ax.set_ylim(0, 6); ax.axis("off")
    for x0, title in ((0.2, "Site A"), (5.6, "Site B")):
        ax.add_patch(FancyBboxPatch((x0, 0.9), 4.2, 4.6, boxstyle="round,pad=0.02,rounding_size=0.15",
                                    fc="none", ec=GRID, lw=1.2))
        ax.text(x0 + 0.15, 5.3, title, fontsize=11, weight="bold")
    _box(ax, 0.5, 3.9, 1.9, 0.8, "5 provider links (nominal)\n3 × 1 Gbit/s, 2 × 100 Mbit/s", fs=7.5)
    _box(ax, 2.6, 3.9, 1.6, 0.8, "Keenetic Titan\nboundary router")
    _box(ax, 0.5, 2.6, 1.9, 0.9, "UniFi CloudKey Gen2\n48 APs (12 with\nconfirmed GbE uplink)", fs=7.5)
    _box(ax, 2.6, 2.6, 1.6, 0.9, "3 × EcoFlow\nbackup power\n(models n/s)", fs=7.5)
    _box(ax, 0.5, 1.2, 3.7, 0.9, "Proposed: read-only collectors,\nsigned telemetry export (not deployed)", proposed=True, fs=7.5)
    _box(ax, 7.7, 3.9, 1.9, 0.8, "2 provider links (nominal)\n2 × 1 Gbit/s", fs=7.5)
    _box(ax, 5.9, 3.9, 1.6, 0.8, "Keenetic Viva\nboundary router")
    _box(ax, 5.9, 2.6, 1.9, 0.9, "UniFi CloudKey Gen1\n6 APs @ 100 Mbit/s", fs=7.5)
    _box(ax, 8.0, 2.6, 1.6, 0.9, "Classroom:\n25 Kali Linux\nworkstations", fs=7.5)
    _box(ax, 5.9, 1.2, 3.7, 0.9, "Proposed: MetaTwin-Guard twin service\n+ evidence store (artifact runs here)", proposed=True, fs=7.5)
    _arrow(ax, (4.2, 4.25), (5.9, 4.25)); _arrow(ax, (5.9, 4.45), (4.2, 4.45))
    ax.text(5.05, 4.85, "protected inter-site VPN\n(protocol/MTU not supplied)", ha="center", fontsize=8, color=INK2)
    ax.plot([], [], color=IMPL, lw=1.4, label="confirmed (evidence level A)")
    ax.plot([], [], color=PROP, lw=1.4, ls=(0, (4, 3)), label="proposed overlay (level C)")
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.04), ncol=2, frameon=False, fontsize=8.5)
    ax.set_title("Two-site cyber range: confirmed topology and proposed overlay\n"
                 "(nominal provider rates are not measured throughput)", fontsize=10.5, color=INK)
    _save(fig, out, "fig1_topology")
    return fig


def figure_pipeline(out: Path | None = None):
    """Figure 2: trust pipeline. Solid = implemented (B); dashed = proposed (C)."""
    fig, ax = plt.subplots(figsize=(13, 4.4))
    ax.set_xlim(0, 11); ax.set_ylim(0, 4.2); ax.axis("off")
    y = 2.3
    stages = [
        (0.1, "Field collectors\n(proposed)", True),
        (1.55, "Software sensor\ncanonical + Ed25519\n+ prev-hash", False),
        (3.15, "Integrity gateway\nschema·hash·sig\nid·seq·chain  g(e)", False),
        (4.85, "Static rules d_R\n+ robust score d_X\n(median/MAD)", False),
        (6.5, "Hybrid\nd_R ∨ d_X ∨ ¬g\n+ top-3 explanation", False),
        (8.15, "Twin state\nupdate only if g=1", False),
        (9.7, "Metaverse view\n(proposed)", True),
    ]
    for x, t, p in stages:
        _box(ax, x, y, 1.3 if x < 9.7 else 1.2, 1.1, t, proposed=p, fs=7.6)
    for (x1, _, p1), (x2, _, p2) in zip(stages, stages[1:]):
        _arrow(ax, (x1 + 1.3, y + 0.55), (x2, y + 0.55), dashed=p1 or p2)
    _box(ax, 3.15, 0.35, 6.3, 0.95, "QuorumEvidenceLedger: block = {event hash, integrity result + reasons, score,\n"
         "decision, top contributions, twin-state hash}; 3-of-4 Ed25519 signatures\n"
         "single-process emulation — NOT a distributed blockchain", fs=7.6)
    _arrow(ax, (3.8, y), (3.8, 1.3), color="#eb6834")
    ax.text(3.88, 1.75, "rejected → evidence only,\nno state change", fontsize=7.4, color=INK2)
    _arrow(ax, (8.8, y), (8.8, 1.3))
    _box(ax, 9.7, 0.45, 1.2, 0.8, "Human-in-the-loop\naction (proposed)", proposed=True, fs=7.2)
    ax.set_title("MetaTwin-Guard trust pipeline (solid = implemented and verified, dashed = proposed)",
                 fontsize=10.5)
    _save(fig, out, "fig2_pipeline")
    return fig


def figure_f1(summary: list[dict[str, Any]], out: Path | None = None,
              modes=("rules", "robust", "hybrid"), name="fig4_f1"):
    """Figure 4: mean F1 ± sample SD per scenario and mode."""
    from .benchmark import MODE_LABELS
    fig, ax = plt.subplots(figsize=(10, 4.4))
    n = len(modes)
    w = 0.8 / n
    for k, m in enumerate(modes):
        xs, ys, es = [], [], []
        for i, sc in enumerate(config.SCENARIOS):
            r = next(r for r in summary if r["scenario"] == sc and r["mode"] == m)
            xs.append(i + (k - (n - 1) / 2) * w)
            ys.append(float(r["f1_mean"])); es.append(float(r["f1_sd"]))
        ax.bar(xs, ys, w * 0.9, color=SERIES[m], label=MODE_LABELS[m], edgecolor=SURFACE, linewidth=1)
        ax.errorbar(xs, ys, yerr=es, fmt="none", ecolor=INK2, elinewidth=1, capsize=2)
        for x_, y_ in zip(xs, ys):
            if y_ < 0.005:  # keep zero results visible
                ax.text(x_, 0.01, "0", ha="center", va="bottom", fontsize=8, color=INK2)
    ax.set_xticks(range(len(config.SCENARIOS)))
    ax.set_xticklabels([config.SCENARIO_LABELS[s].replace(" ", "\n", 1) for s in config.SCENARIOS], fontsize=8.5)
    ax.set_ylim(0, 1.08); ax.set_ylabel("F1 (mean ± SD, 8 runs)")
    ax.yaxis.grid(True, color=GRID, lw=0.8); ax.set_axisbelow(True)
    ax.legend(ncol=n, frameon=False, loc="upper center", bbox_to_anchor=(0.5, 1.12), fontsize=9)
    ax.text(1.0, -0.2, "Evidence level B: deterministic synthetic verification, not cyber-range field data.",
            transform=ax.transAxes, ha="right", fontsize=7.5, color=MUTED)
    _save(fig, out, name)
    return fig


def figure_sensitivity(sens_rows: list[dict[str, Any]], scenario: str = "power_transition",
                       out: Path | None = None):
    """Executed sensitivity: mean F1 of the robust score vs floor and threshold."""
    import statistics
    floors = sorted({float(r["floor"]) for r in sens_rows})
    ths = sorted({float(r["threshold"]) for r in sens_rows})
    grid = [[statistics.fmean(float(r["f1"]) for r in sens_rows if r["scenario"] == scenario
                              and float(r["floor"]) == fl and float(r["threshold"]) == th) for th in ths]
            for fl in floors]
    fig, ax = plt.subplots(figsize=(4.8, 3.4))
    im = ax.imshow(grid, cmap="Blues", vmin=0, vmax=1, origin="lower")
    for i in range(len(floors)):
        for j in range(len(ths)):
            v = grid[i][j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="white" if v > 0.55 else INK, fontsize=9)
    ax.set_xticks(range(len(ths)), [f"τ={t:g}" for t in ths]); ax.set_yticks(range(len(floors)), [f"s_min={f:g}" for f in floors])
    ax.spines[:].set_visible(False)
    fig.colorbar(im, ax=ax, label="mean F1 (robust score)", shrink=0.85)
    ax.set_title(f"Executed sensitivity — {config.SCENARIO_LABELS[scenario]}", fontsize=10)
    _save(fig, out, f"sensitivity_{scenario}")
    return fig
