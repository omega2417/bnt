"""Figures 1-5 in journal formats (optional dependency: matplotlib).

Every figure is drawn from the files in ``results`` (logs and tables), never
from a fresh simulation, so a figure cannot disagree with the tables.

Artwork follows the Elsevier guidelines: widths of 90 mm (single column),
140 mm (1.5 column) or 190 mm (double column); a sans-serif face with text no
smaller than 7 pt at final size; vector PDF (the preferred format for line art), LZW-compressed
1000 dpi TIFF (the guideline minimum for bitmapped line drawings; 500 dpi for
combination artwork, 300 dpi for halftones) and 600 dpi PNG for previews.  Series are told apart by colour *and* by marker or line
style, and the palette is checked for colour-vision deficiency.
"""
from __future__ import annotations

import csv
import gzip
import json
from pathlib import Path
from typing import Dict, List

MM = 1 / 25.4
SINGLE, ONE_HALF, DOUBLE = 90 * MM, 140 * MM, 190 * MM
DPI = 600        # PNG previews
TIFF_DPI = 1000  # bitmapped line art
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#d9d8d4"
# fixed categorical assignment: colour follows the policy, never its rank
COLOR = {"P0": "#6250d6", "P1": "#eb6834", "P2": "#1baf7a", "P3": "#2a78d6"}
MARKER = {"P0": "D", "P1": "s", "P2": "^", "P3": "o"}
DASH = {"P0": (0, (1, 1.5)), "P1": (0, (4, 1.5)), "P2": (0, (4, 1.5, 1, 1.5)), "P3": "solid"}
LABEL = {"P0": "P0 age", "P1": "P1 event-driven", "P2": "P2 static importance", "P3": "P3 current influence"}
FAIL_COLOR, SHARED_EDGE = "#d03b3b", "#eb6834"
FASD_COLOR, FUSD_COLOR = "#2a78d6", "#eb6834"


def _plt():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
        "font.size": 7.5, "axes.labelsize": 7.5, "axes.titlesize": 8, "legend.fontsize": 7,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "axes.linewidth": 0.6,
        "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": MUTED, "ytick.color": MUTED, "xtick.labelcolor": INK, "ytick.labelcolor": INK,
        "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none",
        "savefig.dpi": DPI, "figure.dpi": 150, "savefig.facecolor": "white",
        "legend.frameon": False, "lines.linewidth": 1.2, "lines.markersize": 4,
    })
    return plt


def _save(fig, out: Path, stem: str) -> List[Path]:
    out.mkdir(parents=True, exist_ok=True)
    meta = {"Title": stem, "Creator": "recovery-evidence"}
    paths = []
    for ext, kw in (("pdf", {"metadata": {**meta, "CreationDate": None, "ModDate": None}}),
                    ("png", {"metadata": {"Software": "recovery-evidence"}}),
                    ("tif", {"pil_kwargs": {"compression": "tiff_lzw"}})):
        path = out / f"{stem}.{ext}"
        fig.savefig(path, dpi=TIFF_DPI if ext == "tif" else DPI, **kw)
        paths.append(path)
    import matplotlib.pyplot as plt

    plt.close(fig)
    return paths


def _rows(path: Path) -> List[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def _panel(ax, letter: str) -> None:
    ax.text(-0.02, 1.04, f"({letter})", transform=ax.transAxes, fontsize=8, fontweight="bold",
            ha="right", va="bottom")


# ---------------------------------------------------------------------------
def figure1(results: Path, out: Path) -> List[Path]:
    """Reference dependency map, drawn from the map definition itself."""
    from .topology import reference_map

    plt = _plt()
    from matplotlib.patches import FancyBboxPatch

    ref = reference_map()
    shared = set(ref.shared_components())
    fig, ax = plt.subplots(figsize=(ONE_HALF, 62 * MM))
    ax.set_axis_off()
    ax.set_xlim(-0.6, 7.6)
    ax.set_ylim(-0.95, 2.6)
    cx = {c: i for i, c in enumerate(ref.components)}
    sx = {"S1": 1.2, "S2": 3.6, "S3": 6.2}
    roles = {"A": "identity", "B": "app data", "C": "state store", "D": "primary\ncompute",
             "E": "standby\ncompute", "F": "network\npath", "G": "archive\ngateway", "H": "archive\nstore"}
    for name, groups in ref.services:
        for group in groups:
            for comp in group:
                ax.plot([sx[name], cx[comp]], [1.72, 0.28], color=MUTED, lw=0.8,
                        ls=(0, (3, 2)) if len(group) > 1 else "solid", zorder=1)
    for name, x in sx.items():
        ax.add_patch(FancyBboxPatch((x - 0.62, 1.72), 1.24, 0.5, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="#eef3fb", ec=INK, lw=0.8, zorder=2))
        ax.text(x, 1.97, f"Service {name}", ha="center", va="center", fontsize=8, fontweight="bold", zorder=3)
    for comp, x in cx.items():
        is_shared = comp in shared
        ax.add_patch(FancyBboxPatch((x - 0.3, -0.22), 0.6, 0.5, boxstyle="round,pad=0.02,rounding_size=0.08",
                                    fc="white", ec=SHARED_EDGE if is_shared else INK,
                                    lw=1.8 if is_shared else 0.8, zorder=2))
        ax.text(x, 0.03, comp, ha="center", va="center", fontsize=9, fontweight="bold", zorder=3)
        ax.text(x, -0.34, roles[comp], ha="center", va="top", fontsize=6.5, color=MUTED, linespacing=1.15)
    handles = [
        plt.Line2D([], [], color=MUTED, lw=0.8, label="required component"),
        plt.Line2D([], [], color=MUTED, lw=0.8, ls=(0, (3, 2)), label="redundant pair (one suffices)"),
        plt.Line2D([], [], marker="s", ls="none", mfc="white", mec=SHARED_EDGE, mew=1.8, ms=7,
                   label="shared by two or more services"),
    ]
    ax.legend(handles=handles, loc="upper center", ncol=3, bbox_to_anchor=(0.5, 1.02), handlelength=2.2,
              columnspacing=1.4)
    fig.subplots_adjust(0.01, 0.01, 0.99, 0.99)
    return _save(fig, out, "Figure1_dependency_map")


def figure2(results: Path, out: Path, replicate: int = 0) -> List[Path]:
    """One trajectory of C0: hidden incapability, notices, checks and false assurances."""
    plt = _plt()
    logs = results / "logs" / "C0"
    rep = str(replicate)
    hidden = [r for r in _rows(logs / "hidden_states.csv.gz") if r["replicate"] == rep]
    notices = [r for r in _rows(logs / "notices.csv.gz") if r["replicate"] == rep and r["delivered_to_operator"] == "1"]
    checks = [r for r in _rows(logs / "checks.csv.gz") if r["replicate"] == rep and r["policy"] in ("P1", "P3")]
    verdicts = [r for r in _rows(logs / "verdicts.csv.gz") if r["replicate"] == rep and r["policy"] in ("P1", "P3")]
    comps = [k for k in hidden[0] if k not in ("replicate", "day")]
    T = len(hidden)
    fig, (ax, bx) = plt.subplots(2, 1, figsize=(DOUBLE, 120 * MM), sharex=True,
                                 gridspec_kw={"height_ratios": [3.3, 1], "hspace": 0.1})
    for i, comp in enumerate(comps):
        y = len(comps) - 1 - i
        down = [int(r["day"]) for r in hidden if r[comp] == "0"]
        ax.bar(down, [0.34] * len(down), bottom=y - 0.17, width=1.0, color=FAIL_COLOR, alpha=0.55, lw=0)
        nd = [int(r["delivered_day"]) for r in notices if r["component"] == comp]
        ax.plot(nd, [y + 0.33] * len(nd), ls="none", marker="v", ms=3.2, mfc=INK, mec="none")
        for pol, off in (("P1", -0.30), ("P3", -0.42)):
            days = [int(r["day"]) for r in checks if r["policy"] == pol and r["component"] == comp]
            ax.vlines(days, y + off - 0.05, y + off + 0.05, color=COLOR[pol], lw=0.9)
        ax.axhline(y - 0.5, color=GRID, lw=0.4)
    ax.set_yticks(range(len(comps)))
    ax.set_yticklabels(reversed(comps))
    ax.set_ylim(-0.6, len(comps) - 0.4)
    ax.set_ylabel("Component")
    ax.tick_params(axis="y", length=0)
    handles = [
        plt.Rectangle((0, 0), 1, 1, fc=FAIL_COLOR, alpha=0.55, label="truly incapable"),
        plt.Line2D([], [], ls="none", marker="v", ms=3.5, mfc=INK, mec="none", label="notice delivered"),
        plt.Line2D([], [], ls="none", marker="|", ms=6, mew=1.2, color=COLOR["P1"], label="check by P1"),
        plt.Line2D([], [], ls="none", marker="|", ms=6, mew=1.2, color=COLOR["P3"], label="check by P3"),
    ]
    ax.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncol=4, columnspacing=1.6)
    _panel(ax, "a")
    for pol, off in (("P1", 0.0), ("P3", 0.06)):
        fa = [0] * (T + 1)
        for r in verdicts:
            if r["policy"] == pol and r["verdict"] == "1" and r["reference"] == "0":
                fa[int(r["day"])] += 1
        bx.step(range(1, T + 1), [v + off for v in fa[1:]], where="mid", color=COLOR[pol],
                ls=DASH[pol], lw=1.1, label=LABEL[pol])
    bx.set_ylim(-0.15, 3.3)
    bx.set_yticks([0, 1, 2, 3])
    bx.set_ylabel("Falsely assured\nservices")
    bx.set_xlabel("Day")
    bx.set_xlim(0.5, T + 0.5)
    bx.grid(axis="y", color=GRID, lw=0.4)
    bx.legend(loc="upper left", ncol=2)
    _panel(bx, "b")
    fig.subplots_adjust(0.075, 0.075, 0.99, 0.94)
    return _save(fig, out, "Figure2_trajectory")


def _paired(results: Path) -> Dict[tuple, dict]:
    return {(r["condition"], r["contrast"], r["metric"]): {k: float(v) for k, v in r.items()
                                                           if k not in ("condition", "contrast", "metric")}
            for r in _rows(results / "tables" / "paired_results.csv")}


def _labels(results: Path) -> Dict[str, str]:
    par = json.loads((results / "parameters.json").read_text(encoding="utf-8"))
    return {c["name"]: c["label"] for c in par["conditions"]}


def figure3(results: Path, out: Path) -> List[Path]:
    """Distribution of the primary paired difference and its value in every condition."""
    plt = _plt()
    import numpy as np

    diffs = [float(r["FASD_P3"]) - float(r["FASD_P1"]) for r in _rows(results / "tables" / "paired_differences.csv")
             if r["condition"] == "C0"]
    paired, labels = _paired(results), _labels(results)
    fig, (ax, bx) = plt.subplots(1, 2, figsize=(DOUBLE, 82 * MM), gridspec_kw={"width_ratios": [1, 1.25], "wspace": 0.75})
    step = 100 / 540 * 2
    lim = max(abs(min(diffs)), abs(max(diffs))) + step
    edges = np.arange(-lim - step / 2, lim + step, step)
    ax.hist(diffs, bins=edges, color=COLOR["P3"], alpha=0.75, ec="white", lw=0.5)
    mean = sum(diffs) / len(diffs)
    ax.axvline(0, color=INK, lw=0.8)
    ax.axvline(mean, color=INK, lw=1.0, ls=(0, (4, 2)))
    ax.annotate(f"mean {mean:.2f}".replace("-", "−"), (mean, 1.0), xycoords=("data", "axes fraction"),
                xytext=(-4, -2), textcoords="offset points", ha="right", va="top")
    ax.set_xlabel("P3 − P1, falsely assured service-days per 100")
    ax.set_ylabel(f"Trajectories (R = {len(diffs)})")
    ax.grid(axis="y", color=GRID, lw=0.4)
    ax.set_axisbelow(True)
    _panel(ax, "a")
    names = [n for n in labels if (n, "P3-P1", "FASD") in paired]
    for i, name in enumerate(names):
        st = paired[(name, "P3-P1", "FASD")]
        y = len(names) - 1 - i
        bx.plot([st["ci_low"], st["ci_high"]], [y, y], color=COLOR["P3"], lw=1.3, solid_capstyle="butt")
        bx.plot(st["mean"], y, marker="o", ms=4.2, mfc=COLOR["P3"], mec="white", mew=0.6)
    bx.axvline(0, color=INK, lw=0.8)
    bx.set_yticks(range(len(names)))
    bx.set_yticklabels([f"{n}  {labels[n]}" for n in reversed(names)])
    bx.tick_params(axis="y", length=0)
    bx.set_ylim(-0.6, len(names) - 0.4)
    bx.set_xlabel("Mean P3 − P1 in FASD (95% bootstrap interval)")
    bx.grid(axis="x", color=GRID, lw=0.4)
    bx.set_axisbelow(True)
    _panel(bx, "b")
    fig.subplots_adjust(0.07, 0.13, 0.985, 0.93)
    return _save(fig, out, "Figure3_primary_difference")


def figure4(results: Path, out: Path) -> List[Path]:
    """Both error rates as functions of the daily budget (C1, C0, C2, C3)."""
    plt = _plt()
    par = {c["name"]: c for c in json.loads((results / "parameters.json").read_text(encoding="utf-8"))["conditions"]}
    summ = {(r["condition"], r["policy"]): r for r in _rows(results / "tables" / "policy_summary.csv")}
    conds = sorted((n for n in ("C1", "C0", "C2", "C3") if (n, "P0") in summ), key=lambda n: par[n]["b"])
    fig, axes = plt.subplots(1, 2, figsize=(DOUBLE, 70 * MM), gridspec_kw={"wspace": 0.25})
    for ax, m, title, letter in ((axes[0], "FASD", "False assurance", "a"), (axes[1], "FUSD", "False rejection", "b")):
        for pol in ("P0", "P1", "P2", "P3"):
            xs = [par[n]["b"] for n in conds]
            ys = [float(summ[(n, pol)][f"{m}_mean"]) for n in conds]
            es = [1.96 * float(summ[(n, pol)][f"{m}_mcse"]) for n in conds]
            ax.errorbar(xs, ys, yerr=es, color=COLOR[pol], ls=DASH[pol], marker=MARKER[pol], ms=4.5,
                        mec="white", mew=0.6, capsize=1.5, elinewidth=0.8, label=LABEL[pol])
        ax.set_xticks([par[n]["b"] for n in conds])
        ax.set_xlabel("Daily verification budget b (checks per day)")
        ax.set_ylabel(f"{title}, service-days per 100")
        ax.set_ylim(bottom=0)
        ax.grid(axis="y", color=GRID, lw=0.4)
        ax.set_axisbelow(True)
        _panel(ax, letter)
    axes[1].legend(loc="upper right")
    fig.subplots_adjust(0.065, 0.15, 0.99, 0.92)
    return _save(fig, out, "Figure4_budget")


def figure5(results: Path, out: Path) -> List[Path]:
    """P3 - P1 in both error directions under notice, map and weight conditions."""
    plt = _plt()
    paired, labels = _paired(results), _labels(results)
    groups = [("Notice completeness", ["C5", "C0", "C4"]), ("Suppression, map error,\ncorrelated failure", ["C6", "C8", "C7"]),
              ("Notice weight w", ["C10", "C11", "C0", "C12"])]
    short = {"C5": "p_report = 1.0", "C0": "baseline", "C4": "p_report = 0.3", "C6": "no notices\nfor A, H",
             "C8": "map omits\nF in S2", "C7": "joint D, E\nfailure", "C10": "w = 0", "C11": "w = 3", "C12": "w = 14"}
    fig, axes = plt.subplots(1, 3, figsize=(DOUBLE, 80 * MM), sharey=True,
                             gridspec_kw={"width_ratios": [3, 3, 4], "wspace": 0.08})
    for ax, (title, names), letter in zip(axes, groups, "abc"):
        names = [n for n in names if (n, "P3-P1", "FASD") in paired]
        for i, name in enumerate(names):
            for m, color, marker, off in (("FASD", FASD_COLOR, "o", -0.13), ("FUSD", FUSD_COLOR, "s", 0.13)):
                st = paired[(name, "P3-P1", m)]
                ax.plot([i + off, i + off], [st["ci_low"], st["ci_high"]], color=color, lw=1.3, solid_capstyle="butt")
                ax.plot(i + off, st["mean"], marker=marker, ms=4.5, mfc=color, mec="white", mew=0.6)
        ax.axhline(0, color=INK, lw=0.8)
        ax.set_xticks(range(len(names)))
        ax.set_xticklabels([f"{n}\n{short[n] if not (n == 'C0' and 'weight' in title) else 'w = 7'}" for n in names])
        ax.set_xlim(-0.6, len(names) - 0.4)
        ax.set_title(title, fontsize=7.5, color=INK)
        ax.grid(axis="y", color=GRID, lw=0.4)
        ax.set_axisbelow(True)
        ax.tick_params(axis="x", length=0)
        _panel(ax, letter)
    axes[0].set_ylabel("Mean P3 − P1, service-days per 100\n(95% bootstrap interval)")
    handles = [plt.Line2D([], [], color=FASD_COLOR, marker="o", mec="white", ms=4.5, label="False assurance (FASD)"),
               plt.Line2D([], [], color=FUSD_COLOR, marker="s", mec="white", ms=4.5, label="False rejection (FUSD)")]
    axes[0].legend(handles=handles, loc="lower left")
    fig.subplots_adjust(0.085, 0.17, 0.99, 0.87)
    return _save(fig, out, "Figure5_conditions")


FIGURES = (figure1, figure2, figure3, figure4, figure5)


def make_figures(results: Path, out: Path = None) -> List[Path]:
    results = Path(results)
    out = Path(out) if out else results / "figures"
    paths: List[Path] = []
    for fn in FIGURES:
        paths += fn(results, out)
    return paths
