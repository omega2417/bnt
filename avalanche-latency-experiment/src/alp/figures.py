"""Figures of the protocol and of the results.

Figures 1-4 are schematics and closed-form curves: they can be drawn
before any data exists.  Figures 5-11 are result figures and are drawn
from the run-level summary, so they carry the provenance of the dataset
in a footer.  Nothing here reads a bitmap: every figure is generated
from code, which is what makes the article's illustrations reproducible.
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

from .config import CONFIG_BLOCK_MS, TOPOLOGY_LABELS
from . import theory

plt.rcParams.update(
    {
        "figure.dpi": 140,
        "savefig.dpi": 200,
        "font.size": 9,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "legend.frameon": False,
    }
)

CONFIG_COLORS = {
    "C0": "#4c4c4c",
    "C1": "#1f77b4",
    "C2": "#2ca02c",
    "C3": "#ff7f0e",
    "C4": "#d62728",
}


def config_label(config: str) -> str:
    ms = CONFIG_BLOCK_MS.get(config)
    return f"{config} stock" if ms is None else f"{config} {ms} ms"


def _footer(fig, provenance: str, extra: str = "") -> None:
    note = f"Data provenance: {provenance}."
    if provenance != "MEASURED":
        note += " Reference model output, not a cyber-range measurement."
    if extra:
        note += " " + extra
    fig.text(0.005, 0.005, note, fontsize=6.5, color="#666666", ha="left", va="bottom")


def _save(fig, out_dir: Path, name: str) -> Path:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{name}.png"
    fig.savefig(path, bbox_inches="tight")
    fig.savefig(out_dir / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    return path


def _box(ax, x, y, w, h, text, fc, ec="#333333", fontsize=7.5):
    ax.add_patch(
        FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.02",
            facecolor=fc, edgecolor=ec, linewidth=0.9,
        )
    )
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fontsize)


def _arrow(ax, p0, p1, style="-|>", color="#444444", ls="-", lw=0.9):
    ax.add_patch(
        FancyArrowPatch(
            p0, p1, arrowstyle=style, mutation_scale=9,
            color=color, linestyle=ls, linewidth=lw,
            shrinkA=2, shrinkB=2,
        )
    )


# --------------------------------------------------------------------------
# Schematics
# --------------------------------------------------------------------------

def fig1_lab_topology(out_dir: Path) -> Path:
    """Confirmed two-site topology of the cyber range (protocol Fig. 1)."""
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Fig. 1. Confirmed two-site topology of the cyber range", fontsize=9.5)

    _box(ax, 0.02, 0.70, 0.42, 0.16,
         "Site A — main building\nKeenetic Titan · 3x1 Gbit/s + 2x100 Mbit/s", "#e8f0fb")
    _box(ax, 0.02, 0.46, 0.42, 0.16,
         "UniFi CloudKey Gen2 (management plane)\n48 access points, 12 with gigabit uplink", "#f2f6fc")
    _box(ax, 0.02, 0.24, 0.42, 0.14, "3 x EcoFlow distributed power backup", "#fdf3e6")
    _box(ax, 0.02, 0.05, 0.42, 0.13, "Validators V1-V3 · read node R1\n(protocol placement)", "#eef7ee")

    _box(ax, 0.56, 0.70, 0.42, 0.16,
         "Site B — branch\nKeenetic Viva · 2x1 Gbit/s", "#e8f0fb")
    _box(ax, 0.56, 0.46, 0.42, 0.16,
         "UniFi CloudKey Gen1 (management plane)\n6 access points, 100 Mbit/s uplink", "#f2f6fc")
    _box(ax, 0.56, 0.24, 0.42, 0.14, "25 Kali Linux workstations\n(load generators, 1 EVM account each)", "#fdf3e6")
    _box(ax, 0.56, 0.05, 0.42, 0.13, "Validators V4-V5 · read node R2\n(protocol placement)", "#eef7ee")

    _arrow(ax, (0.44, 0.78), (0.56, 0.78), style="<|-|>", color="#b02a2a", lw=1.4)
    ax.text(0.50, 0.90, "protected\nsite-to-site VPN", ha="center", fontsize=7.5,
            color="#b02a2a")
    fig.text(0.005, 0.005,
             "Confirmed inventory from the laboratory description. Node placement "
             "(V1-V5, R1-R2) is a reproducible protocol decision, not an audited "
             "inventory.", fontsize=6.5, color="#666666")
    return _save(fig, out_dir, "fig01_lab_topology")


def fig2_logical_architecture(out_dir: Path) -> Path:
    """Generation, validation, independent read and collection (Fig. 2)."""
    fig, ax = plt.subplots(figsize=(7.4, 3.2))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Fig. 2. Logical architecture of the measured path", fontsize=9.5)

    _box(ax, 0.01, 0.40, 0.17, 0.26, "25 load generators\nopen-loop dispatcher\nimmutable trace", "#fdf3e6")
    _box(ax, 0.22, 0.40, 0.15, 0.26, "write RPC\nendpoint", "#e8f0fb")
    _box(ax, 0.41, 0.36, 0.19, 0.34, "permissioned\nAvalanche L1\nSubnet-EVM\nV1...V5", "#eef7ee")
    _box(ax, 0.64, 0.56, 0.15, 0.18, "read node R1\nsite A", "#f2f6fc")
    _box(ax, 0.64, 0.30, 0.15, 0.18, "read node R2\nsite B", "#f2f6fc")
    _box(ax, 0.83, 0.40, 0.16, 0.26, "collector\nJSONL + Prometheus\n+ active probes", "#f6eefb")

    _arrow(ax, (0.18, 0.53), (0.22, 0.53))
    _arrow(ax, (0.37, 0.53), (0.41, 0.53))
    _arrow(ax, (0.60, 0.60), (0.64, 0.65))
    _arrow(ax, (0.60, 0.46), (0.64, 0.39))
    _arrow(ax, (0.79, 0.65), (0.83, 0.58))
    _arrow(ax, (0.79, 0.39), (0.83, 0.48))
    _arrow(ax, (0.72, 0.56), (0.10, 0.40), style="-|>", color="#b02a2a", ls="--")
    ax.text(0.40, 0.20, "eth_call read-back to the generator's monotonic clock "
                        "(allow-unfinalized-queries = false)",
            fontsize=7, color="#b02a2a", ha="center")
    return _save(fig, out_dir, "fig02_logical_architecture")


def fig3_timestamp_path(out_dir: Path) -> Path:
    """Timestamps along the full path to confirmed state (Fig. 3)."""
    import textwrap

    stages = [
        ("t_send", "signed transaction leaves the generator", 0.00),
        ("t_hash", "RPC accepted, hash returned", 0.10),
        ("gossip", "dissemination to the proposer", 0.22),
        ("t_block", "block proposal", 0.38),
        ("accept", "consensus acceptance", 0.54),
        ("commit", "execution and state commit", 0.68),
        ("t_receipt", "receipt observed by the client", 0.81),
        ("t_read", "first independent read returns the state", 0.96),
    ]
    fig, ax = plt.subplots(figsize=(8.0, 3.4))
    ax.set_xlim(-0.06, 1.08)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.set_title("Fig. 3. Timestamps of the full path to confirmed state", fontsize=9.5)
    ax.annotate("", xy=(1.05, 0.50), xytext=(-0.04, 0.50),
                arrowprops=dict(arrowstyle="-|>", color="#333333", lw=1.1))
    for i, (name, desc, x) in enumerate(stages):
        up = i % 2 == 0
        tip = 0.62 if up else 0.38
        ax.plot([x], [0.50], marker="o", ms=5, color="#1f77b4", zorder=3)
        ax.plot([x, x], [0.50, tip], color="#9db8d2", lw=0.7, zorder=1)
        ax.text(x, tip + (0.015 if up else -0.015), name, ha="center",
                va="bottom" if up else "top", fontsize=7.5, fontweight="bold")
        ax.text(x, tip + (0.075 if up else -0.075),
                textwrap.fill(desc, 17), ha="center",
                va="bottom" if up else "top", fontsize=6.2, color="#555555",
                linespacing=1.25)
    ax.annotate("", xy=(0.96, 0.10), xytext=(0.0, 0.10),
                arrowprops=dict(arrowstyle="<|-|>", color="#b02a2a", lw=1.2))
    ax.text(0.48, 0.03, "T_visible,first  (eq. 5) — the primary metric",
            ha="center", fontsize=8, color="#b02a2a")
    return _save(fig, out_dir, "fig03_timestamp_path")


def fig4_theory_block_wait(out_dir: Path) -> Path:
    """Theoretical quantiles of the block-wait component only (Fig. 4)."""
    table = theory.table_block_wait()
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    x = np.arange(len(table))
    width = 0.26
    for k, (col, label) in enumerate(
        [("p50_ms", "p50"), ("p95_ms", "p95"), ("p99_ms", "p99")]
    ):
        ax.bar(x + (k - 1) * width, table[col], width, label=label)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{b} ms" for b in table.B_ms])
    ax.set_xlabel("target block interval B")
    ax.set_ylabel("W_block [ms]")
    ax.set_title("Fig. 4. Block-wait component under W ~ U(0, B)", fontsize=9.5)
    ax.legend(title="quantile")
    _footer(fig, "THEORY",
            "Structural component only; propagation, acceptance, execution, "
            "commit and read are added separately.")
    return _save(fig, out_dir, "fig04_theory_block_wait")


# --------------------------------------------------------------------------
# Result figures
# --------------------------------------------------------------------------

def fig5_latency_vs_load(summary: pd.DataFrame, out_dir: Path, provenance: str) -> Path:
    topologies = [t for t in TOPOLOGY_LABELS if t in set(summary.topology)]
    fig, axes = plt.subplots(
        3, len(topologies), figsize=(3.1 * len(topologies), 7.4), sharex=True
    )
    axes = np.atleast_2d(axes)
    if axes.shape[1] != len(topologies):
        axes = axes.T
    for col, topo in enumerate(topologies):
        for row, metric in enumerate(["p50_ms", "p95_ms", "p99_ms"]):
            ax = axes[row, col]
            sel = summary[summary.topology == topo]
            for config, group in sel.groupby("config"):
                agg = group.groupby("load_tps")[metric].mean()
                ax.plot(agg.index, agg.values, marker="o", ms=3.5,
                        color=CONFIG_COLORS.get(config), label=config_label(config))
            ax.set_yscale("log")
            if row == 0:
                ax.set_title(TOPOLOGY_LABELS[topo], fontsize=9)
            if col == 0:
                ax.set_ylabel(f"{metric[:-3]} T_visible,first [ms]")
            if row == 2:
                ax.set_xlabel("offered load [tx/s]")
    axes[0, -1].legend(fontsize=6.5, loc="upper left")
    fig.suptitle("Fig. 5. User-visible latency against offered load", fontsize=10)
    _footer(fig, provenance)
    fig.tight_layout(rect=(0, 0.02, 1, 0.98))
    return _save(fig, out_dir, "fig05_latency_vs_load")


def fig6_paired_effects(effects: pd.DataFrame, out_dir: Path, provenance: str,
                        metric: str = "p99_ms") -> Path:
    sel = effects[effects.metric == metric].copy()
    topologies = [t for t in TOPOLOGY_LABELS if t in set(sel.topology)]
    fig, axes = plt.subplots(1, len(topologies),
                             figsize=(3.4 * len(topologies), 3.8), sharey=True)
    axes = np.atleast_1d(axes)
    for ax, topo in zip(axes, topologies):
        sub = sel[sel.topology == topo].sort_values(["load_tps", "profile"])
        labels, y = [], 0
        for (load, profile), row in sub.groupby(["load_tps", "profile"]):
            r = row.iloc[0]
            ax.errorbar(
                r.delta_improvement_ms, y,
                xerr=[[r.delta_improvement_ms - r.ci_low],
                      [r.ci_high - r.delta_improvement_ms]],
                fmt="o", ms=3.5, capsize=2,
                color=CONFIG_COLORS.get(profile, "#333333"),
            )
            labels.append(f"{profile} @ {load}")
            y += 1
        ax.axvline(0, color="#b02a2a", lw=0.9, ls="--")
        ax.set_yticks(range(len(labels)))
        ax.set_yticklabels(labels, fontsize=6)
        ax.set_title(TOPOLOGY_LABELS[topo], fontsize=9)
        ax.set_xlabel(f"improvement of {metric} vs C0 [ms]")
    fig.suptitle("Fig. 6. Paired effects against the C0 baseline, 95 % CI", fontsize=10)
    _footer(fig, provenance, "Positive values mean lower latency than the baseline.")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    return _save(fig, out_dir, "fig06_paired_effects_p99")


def fig7_ecdf(records: pd.DataFrame, out_dir: Path, provenance: str,
              topology: str, load_tps: int) -> Path:
    fig, ax = plt.subplots(figsize=(5.6, 3.6))
    for config, group in records.groupby("config"):
        x = np.sort(group.t_visible_first_ms.to_numpy())
        if x.size == 0:
            continue
        ax.plot(x, np.arange(1, x.size + 1) / x.size, lw=1.2,
                color=CONFIG_COLORS.get(config), label=config_label(config))
    ax.set_xscale("log")
    ax.set_xlabel("T_visible,first [ms]")
    ax.set_ylabel("empirical CDF")
    ax.axhline(0.99, color="#999999", lw=0.7, ls=":")
    ax.text(ax.get_xlim()[0], 0.992, " p99", fontsize=6.5, color="#666666")
    ax.set_title(
        f"Fig. 7. Latency distribution — {TOPOLOGY_LABELS.get(topology, topology)}, "
        f"{load_tps} tx/s", fontsize=9.5
    )
    ax.legend(fontsize=7)
    _footer(fig, provenance, "One representative repeat per configuration.")
    return _save(fig, out_dir, "fig07_ecdf")


def fig8_queue_depth(resources: Dict[str, pd.DataFrame], out_dir: Path,
                     provenance: str) -> Path:
    fig, ax = plt.subplots(figsize=(6.2, 3.6))
    for label, df in resources.items():
        ax.plot(df.t_s, df.queue_depth, lw=1.1, label=label)
    ax.set_xlabel("time in run [s]")
    ax.set_ylabel("queue depth [tx]")
    ax.set_title("Fig. 8. Backlog behaviour: stable versus unstable regimes", fontsize=9.5)
    ax.legend(fontsize=7)
    _footer(fig, provenance,
            "A regime is unstable when the Theil-Sen slope CI confirms positive "
            "accumulation (eq. 14).")
    return _save(fig, out_dir, "fig08_queue_depth")


def fig9_resource_cost(summary: pd.DataFrame, out_dir: Path, provenance: str) -> Path:
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 3.4))
    for config, group in summary.groupby("config"):
        agg = group.groupby("load_tps")[["cpu_p95_pct", "disk_p99_ms"]].mean()
        axes[0].plot(agg.index, agg.cpu_p95_pct, marker="o", ms=3.5,
                     color=CONFIG_COLORS.get(config), label=config_label(config))
        axes[1].plot(agg.index, agg.disk_p99_ms, marker="o", ms=3.5,
                     color=CONFIG_COLORS.get(config))
    axes[0].set_xlabel("offered load [tx/s]")
    axes[0].set_ylabel("validator CPU p95 [%]")
    axes[1].set_xlabel("offered load [tx/s]")
    axes[1].set_ylabel("storage commit p99 [ms]")
    axes[0].legend(fontsize=6.5)
    fig.suptitle("Fig. 9. Resource cost of shorter block pacing (RQ2)", fontsize=10)
    _footer(fig, provenance,
            "Averaged over topologies; the block term does not vanish at low load.")
    fig.tight_layout(rect=(0, 0.02, 1, 0.95))
    return _save(fig, out_dir, "fig09_resource_cost")


def fig10_convergence(summary: pd.DataFrame, out_dir: Path, provenance: str) -> Path:
    fig, ax = plt.subplots(figsize=(6.0, 3.5))
    topologies = [t for t in TOPOLOGY_LABELS if t in set(summary.topology)]
    width = 0.8 / max(len(topologies), 1)
    configs = sorted(summary.config.unique())
    x = np.arange(len(configs))
    for k, topo in enumerate(topologies):
        vals = [
            summary[(summary.config == c) & (summary.topology == topo)]
            .convergence_p99_ms.mean()
            for c in configs
        ]
        ax.bar(x + k * width - 0.4 + width / 2, vals, width,
               label=TOPOLOGY_LABELS[topo])
    ax.set_xticks(x)
    ax.set_xticklabels([config_label(c) for c in configs], fontsize=7)
    ax.set_ylabel("p99 of T_convergence [ms]")
    ax.set_title("Fig. 10. Convergence between independent read nodes (eq. 7)",
                 fontsize=9.5)
    ax.legend(fontsize=7)
    _footer(fig, provenance,
            "Floor of 25 ms is the client polling grid, not a network effect.")
    return _save(fig, out_dir, "fig10_read_convergence")


def fig11_stability_map(cells: pd.DataFrame, out_dir: Path, provenance: str) -> Path:
    topologies = [t for t in TOPOLOGY_LABELS if t in set(cells.topology)]
    configs = sorted(cells.config.unique())
    loads = sorted(cells.load_tps.unique())
    fig, axes = plt.subplots(1, len(topologies),
                             figsize=(2.9 * len(topologies), 3.2), sharey=True)
    axes = np.atleast_1d(axes)
    cmap = matplotlib.colors.ListedColormap(["#d9534f", "#f0ad4e", "#5cb85c"])
    for ax, topo in zip(axes, topologies):
        grid = np.zeros((len(configs), len(loads)))
        for i, c in enumerate(configs):
            for j, l in enumerate(loads):
                row = cells[(cells.config == c) & (cells.topology == topo)
                            & (cells.load_tps == l)]
                if row.empty:
                    grid[i, j] = np.nan
                else:
                    grid[i, j] = (
                        2 if bool(row.stable_all.iloc[0])
                        else 1 if bool(row.stable_majority.iloc[0]) else 0
                    )
        ax.imshow(grid, cmap=cmap, vmin=0, vmax=2, aspect="auto")
        ax.set_xticks(range(len(loads)))
        ax.set_xticklabels(loads, fontsize=7)
        ax.set_yticks(range(len(configs)))
        ax.set_yticklabels([config_label(c) for c in configs], fontsize=7)
        ax.set_title(TOPOLOGY_LABELS[topo], fontsize=9)
        ax.set_xlabel("load [tx/s]")
        ax.grid(False)
    handles = [
        matplotlib.patches.Patch(color="#5cb85c", label="stable in all repeats"),
        matplotlib.patches.Patch(color="#f0ad4e", label="stable in the majority"),
        matplotlib.patches.Patch(color="#d9534f", label="unstable"),
    ]
    fig.suptitle("Fig. 11. Pre-registered stability classification", fontsize=10)
    fig.tight_layout(rect=(0, 0.12, 1, 0.95))
    fig.legend(handles=handles, fontsize=7, loc="lower center", ncol=3,
               bbox_to_anchor=(0.5, 0.02))
    _footer(fig, provenance)
    return _save(fig, out_dir, "fig11_stability_map")


def draw_protocol_figures(out_dir: Path) -> List[Path]:
    return [
        fig1_lab_topology(out_dir),
        fig2_logical_architecture(out_dir),
        fig3_timestamp_path(out_dir),
        fig4_theory_block_wait(out_dir),
    ]
