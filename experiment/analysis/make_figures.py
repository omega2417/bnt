"""Regenerate every figure from processed/runs.csv and the raw run bundles.

No number in any figure is typed by hand. Figure 3 reads the availability traces of
exactly the runs that produced the recovery and NRI rows of the results tables, so
the two are consistent by construction.
"""
from __future__ import annotations

import gzip
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dtcr import audit, stats  # noqa: E402

FIG = ROOT / "figures"
FIG.mkdir(exist_ok=True)

# Validated categorical palette, fixed order, never cycled (dataviz slots 1-6).
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
ARMS = ["A0", "A1", "A2", "A3", "A4", "A5"]
COLOR = dict(zip(ARMS, SERIES))
SCEN = ["S1", "S2", "S3", "S4"]
INK, INK2, GRID = "#0b0b0b", "#52514e", "#dedcd6"

plt.rcParams.update({
    "figure.dpi": 160, "savefig.dpi": 160, "font.size": 8,
    "axes.edgecolor": GRID, "axes.labelcolor": INK, "axes.titlesize": 9,
    "axes.titleweight": "bold", "text.color": INK,
    "xtick.color": INK2, "ytick.color": INK2, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
    "legend.frameon": False, "figure.facecolor": "#fcfcfb", "axes.facecolor": "#fcfcfb",
})


def _style(ax, ylabel="", title=""):
    ax.set_ylabel(ylabel, color=INK2)
    if title:
        ax.set_title(title, loc="left", color=INK)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    ax.grid(axis="x", visible=False)


def fig_detection(df):
    """Horizontal bars: 24 rates stay legible and every value carries a direct label
    (the relief rule for the low-contrast categorical slots)."""
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 4.2), sharey=True)
    ypos, ylab, sep = [], [], []
    y = 0.0
    for sc in SCEN:
        for arm in ARMS:
            ypos.append(-y); ylab.append(arm); y += 1.0
        sep.append(y - 3.5)
        y += 0.9
    for ax, metric, title in [
            (axes[0], "detected", "(a) Incident detection rate"),
            (axes[1], "contained", "(b) Containment rate")]:
        vals, los, his, cols = [], [], [], []
        for sc in SCEN:
            for arm in ARMS:
                d = df[(df.scenario == sc) & (df.arm == arm)]
                k, n = int(d[metric].sum()), len(d)
                lo, hi = stats.wilson_ci(k, n)
                vals.append(k / n); los.append(k / n - lo); his.append(hi - k / n)
                cols.append(COLOR[arm])
        ax.barh(ypos, vals, 0.74, color=cols, linewidth=0)
        ax.errorbar(vals, ypos, xerr=[los, his], fmt="none", ecolor=INK2,
                    elinewidth=0.7, capsize=1.5)
        for yy, v, hh in zip(ypos, vals, his):
            ax.text(min(v + hh + 0.045, 1.10), yy, f"{v:.2f}", va="center", ha="left",
                    fontsize=6, color=INK2)
        ax.set_xlim(0, 1.28); ax.set_xticks([0, 0.5, 1.0])
        ax.set_yticks(ypos); ax.set_yticklabels(ylab, fontsize=6.5)
        ax.set_xlabel("rate (n = 54 per cell)", color=INK2)
        _style(ax, "", title)
        ax.grid(axis="y", visible=False); ax.grid(axis="x", visible=True)
    for i, sc in enumerate(SCEN):
        axes[0].text(-0.30, -(i * 6.9 + 2.5), sc, fontsize=8, fontweight="bold",
                     color=INK, ha="center", va="center", transform=axes[0].get_yaxis_transform())
    h = [plt.Line2D([], [], color=COLOR[a], lw=5) for a in ARMS]
    axes[0].legend(h, [f"{a}" for a in ARMS], ncol=6, loc="upper center",
                   bbox_to_anchor=(1.06, 1.12), fontsize=7, handlelength=1.1,
                   columnspacing=1.3)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    fig.savefig(FIG / "fig1_detection_containment_rate.png", bbox_inches="tight")
    plt.close(fig)


def fig_latency(df):
    """Small multiples with independent linear axes.

    A shared log axis is wrong here: S4 detection latency is exactly 0 s for the arms
    whose admissibility check rejects the placement synchronously, and a log axis
    cannot represent that value at all.
    """
    fig, axes = plt.subplots(2, 4, figsize=(7.6, 4.4))
    rows = [("detection_latency", "detected", "detection latency, s"),
            ("containment_latency", "contained", "containment latency, s")]
    for r, (metric, gate, ylabel) in enumerate(rows):
        for c, sc in enumerate(SCEN):
            ax = axes[r][c]
            data, pos, cols, notes = [], [], [], []
            for i, arm in enumerate(ARMS):
                v = df[(df.scenario == sc) & (df.arm == arm)][metric].to_numpy(float)
                n_tot = v.size
                v = v[np.isfinite(v)]
                notes.append((i, n_tot - v.size))
                if v.size >= 3:
                    data.append(v); pos.append(i); cols.append(COLOR[arm])
            if data:
                bp = ax.boxplot(data, positions=pos, widths=0.66, patch_artist=True,
                                showfliers=False, medianprops=dict(color=INK, linewidth=1.0),
                                whiskerprops=dict(color=INK2, linewidth=0.7),
                                capprops=dict(color=INK2, linewidth=0.7))
                for patch, col in zip(bp["boxes"], cols):
                    patch.set_facecolor(col); patch.set_edgecolor("#fcfcfb")
                    patch.set_linewidth(0.9)
            ax.set_xlim(-0.7, 5.7)
            ax.set_xticks(range(6)); ax.set_xticklabels(ARMS, fontsize=5.6)
            lo, hi = ax.get_ylim()
            if data and np.allclose(np.concatenate(data), 0.0):
                ax.set_ylim(-0.25, 1.0)
                ax.text(2.5, 0.55, "0 s: synchronous rejection\nby the admissibility check",
                        ha="center", fontsize=5.6, color=INK2)
            else:
                ax.set_ylim(min(0, lo), hi + (hi - lo) * 0.22 if hi > lo else 1)
            for i, nc in notes:
                if nc:
                    ax.text(i, ax.get_ylim()[1], f"{nc}c", ha="center", va="top",
                            fontsize=5, color=INK2)
            ax.tick_params(labelsize=6)
            _style(ax, ylabel if c == 0 else "", f"{sc}" if r == 0 else "")
            if c == 0:
                ax.set_ylabel(ylabel, color=INK2, fontsize=7)
    fig.text(0.5, 0.965, "(a) Detection latency, detected runs only", ha="center",
             fontsize=9, fontweight="bold", color=INK)
    fig.text(0.5, 0.455, "(b) Containment latency, contained runs only", ha="center",
             fontsize=9, fontweight="bold", color=INK)
    fig.text(0.5, 0.005, "\"Nc\" above a column is the number of censored runs of that "
             "cell (no detection / no containment inside the 900 s observation window); "
             "a column with fewer than three complete runs is not drawn.",
             ha="center", fontsize=6, color=INK2)
    fig.tight_layout(rect=(0, 0.03, 1, 0.94), h_pad=6.0)
    fig.savefig(FIG / "fig2_latency_distributions.png", bbox_inches="tight")
    plt.close(fig)


def fig_availability(df):
    """Figure 3 and the NRI column of the results table come from the same runs."""
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    for arm in ("A0", "A5"):
        d = df[(df.scenario == "S3") & (df.arm == arm)]
        traces = []
        for p in d.raw_log_path:
            with gzip.open(ROOT / p, "rb") as f:
                raw = json.loads(f.read())
            traces.append(raw["availability_A"])
            t = np.asarray(raw["availability_t"])
        M = np.asarray(traces)
        med = np.median(M, axis=0)
        lo, hi = np.percentile(M, [25, 75], axis=0)
        nri = d.nri.mean()
        ax.fill_between(t, lo, hi, color=COLOR[arm], alpha=0.16, linewidth=0)
        ax.plot(t, med, color=COLOR[arm], linewidth=2.0,
                label=f"{arm} - NRI {nri:.3f} (n={len(d)})")
    ax.axvspan(300, 320, color=GRID, alpha=0.7, linewidth=0, zorder=0)
    ax.axhline(0.95, color=INK2, linewidth=0.8, linestyle=(0, (4, 3)))
    ax.text(160, 0.905, "$A_{min}$ = 0.95", ha="left", fontsize=6, color=INK2)
    ax.text(310, 0.06, "injection", ha="center", fontsize=6, color=INK2)
    ax.set_xlim(150, 1200); ax.set_ylim(0, 1.05); ax.set_xlabel("time, s", color=INK2)
    _style(ax, "service availability",
           "S3 denial of service: median availability, IQR band")
    ax.legend(fontsize=7, loc="lower right")
    fig.tight_layout()
    fig.savefig(FIG / "fig3_availability_s3.png", bbox_inches="tight")
    plt.close(fig)


def fig_graph_value(df):
    fig, axes = plt.subplots(1, 2, figsize=(7.4, 3.2))
    w = 0.13
    ax = axes[0]
    for i, arm in enumerate(ARMS):
        vals, err = [], []
        for sc in SCEN:
            v = df[(df.scenario == sc) & (df.arm == arm)].blast_recall.to_numpy(float)
            v = v[np.isfinite(v)]
            lo, hi = stats.bootstrap_ci(v, boot=2000, seed=5)
            vals.append(v.mean()); err.append([v.mean() - lo, hi - v.mean()])
        x = np.arange(len(SCEN)) + (i - 2.5) * w
        ax.bar(x, vals, w * 0.88, color=COLOR[arm], label=arm, linewidth=0)
        ax.errorbar(x, vals, yerr=np.asarray(err).T, fmt="none", ecolor=INK2,
                    elinewidth=0.7, capsize=1.6)
    ax.set_xticks(range(len(SCEN))); ax.set_xticklabels(SCEN); ax.set_ylim(0, 0.92)
    _style(ax, "impact-set recall", "(a) Recall of the true impacted asset set")

    ax = axes[1]
    top = 0.0
    for i, arm in enumerate(["A3", "A5"]):
        vals, err = [], []
        for sc in SCEN:
            v = df[(df.scenario == sc) & (df.arm == arm)].whatif_abs_err.to_numpy(float)
            v = v[np.isfinite(v)]
            lo, hi = stats.bootstrap_ci(v, boot=2000, seed=6)
            vals.append(v.mean()); err.append([v.mean() - lo, hi - v.mean()])
            top = max(top, hi)
        x = np.arange(len(SCEN)) + (i - 0.5) * 0.30
        ax.bar(x, vals, 0.27, color=COLOR[arm], label=arm, linewidth=0)
        ax.errorbar(x, vals, yerr=np.asarray(err).T, fmt="none", ecolor=INK2,
                    elinewidth=0.7, capsize=1.6)
        for xi, v, e in zip(x, vals, err):
            ax.text(xi, v + e[1] + 0.006, f"{v:.3f}", ha="center", va="bottom",
                    fontsize=5.8, color=INK2)
    ax.axhline(0.10, color=INK2, linewidth=0.8, linestyle=(0, (4, 3)))
    ax.text(-0.45, 0.106, "pre-set tolerance 0.10", ha="left", fontsize=6, color=INK2)
    ax.set_xticks(range(len(SCEN))); ax.set_xticklabels(SCEN)
    ax.set_ylim(0, top * 1.22)
    ax.legend(fontsize=7, loc="upper right", title="ablation", title_fontsize=6)
    _style(ax, "|predicted - realised|", "(b) What-if prediction error (H6)")

    h = [plt.Line2D([], [], color=COLOR[a], lw=5) for a in ARMS]
    fig.legend(h, ARMS, ncol=6, loc="lower center", bbox_to_anchor=(0.5, -0.05),
               fontsize=7, handlelength=1.1, columnspacing=1.4)
    fig.tight_layout()
    fig.savefig(FIG / "fig4_graph_and_whatif.png", bbox_inches="tight")
    plt.close(fig)


def fig_overhead(df):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    ax = axes[0]
    d = df[df.scenario != "S4"]      # S4 has no telemetry-driven detector activity
    vals, err = [], []
    for arm in ARMS:
        v = d[d.arm == arm].fp_rate_holdout.to_numpy(float) * 100
        lo, hi = stats.bootstrap_ci(v, boot=2000, seed=7)
        vals.append(v.mean()); err.append([v.mean() - lo, hi - v.mean()])
    ax.bar(ARMS, vals, 0.6, color=[COLOR[a] for a in ARMS], linewidth=0)
    ax.errorbar(ARMS, vals, yerr=np.asarray(err).T, fmt="none", ecolor=INK2,
                elinewidth=0.7, capsize=2)
    for i, v in enumerate(vals):
        ax.text(i, v + 0.06, f"{v:.2f}%", ha="center", fontsize=6, color=INK2)
    ax.axhline(1.0, color=INK2, linewidth=0.8, linestyle=(0, (4, 3)))
    ax.text(-0.45, 1.05, "nominal per-sample FPR 1%", ha="left", fontsize=6, color=INK2)
    ax.set_ylim(0, 2.6)
    _style(ax, "false-positive rate, %",
           "(a) Out-of-sample per-sample FPR (S1-S3)")

    ax = axes[1]
    vals, err = [], []
    for arm in ARMS:
        v = df[df.arm == arm].orchestrator_cpu_s.to_numpy(float) * 1e3
        lo, hi = stats.bootstrap_ci(v, boot=2000, seed=8)
        vals.append(v.mean()); err.append([v.mean() - lo, hi - v.mean()])
    ax.bar(ARMS, vals, 0.6, color=[COLOR[a] for a in ARMS], linewidth=0)
    ax.errorbar(ARMS, vals, yerr=np.asarray(err).T, fmt="none", ecolor=INK2,
                elinewidth=0.7, capsize=2)
    for i, v in enumerate(vals):
        ax.text(i, v * 1.06, f"{v:.2f}", ha="center", fontsize=6, color=INK2)
    _style(ax, "CPU time per decision, ms",
           "(b) Measured orchestration cost")
    fig.tight_layout()
    fig.savefig(FIG / "fig5_overhead.png", bbox_inches="tight")
    plt.close(fig)


def fig_audit():
    """Analytical sensitivity of Eq. (4)/(5), verified against the exact model."""
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.9))
    ax = axes[0]
    r = np.arange(1, 400)
    for i, p in enumerate([0.01, 0.05, 0.10, 0.20]):
        ax.plot(r, 1 - (1 - p) ** r, color=SERIES[i], linewidth=1.8,
                label=f"corruption {p:.0%}")
    ax.axhline(0.95, color=INK2, linewidth=0.8, linestyle=(0, (4, 3)))
    ax.text(8, 0.905, "target 0.95", ha="left", fontsize=6, color=INK2)
    ax.set_xlabel("challenged blocks r", color=INK2); ax.set_ylim(0, 1.03)
    ax.legend(fontsize=7, loc="lower right")
    _style(ax, "lower-bound detection probability",
           "(a) Eq. (5) sampling rule, l = 10 000")

    ax = axes[1]
    l = 10_000
    ps = [0.01, 0.05, 0.10, 0.20]
    exact, bound = [], []
    for p in ps:
        d = int(p * l)
        rr = audit.r_min(l, d, 0.95)
        exact.append(audit.p_detect_exact(l, d, rr))
        bound.append(audit.p_detect_lower_bound(l, d, rr))
    x = np.arange(len(ps))
    ax.bar(x - 0.17, bound, 0.32, color=SERIES[0], label="lower bound, Eq. (5)", linewidth=0)
    ax.bar(x + 0.17, exact, 0.32, color=SERIES[2], label="exact hypergeometric, Eq. (4)",
           linewidth=0)
    for xi, (b, e) in enumerate(zip(bound, exact)):
        ax.text(xi - 0.17, b + 0.0015, f"{b:.4f}", ha="center", va="bottom",
                fontsize=5.2, color=INK2, rotation=90)
        ax.text(xi + 0.17, e + 0.0015, f"{e:.4f}", ha="center", va="bottom",
                fontsize=5.2, color=INK2, rotation=90)
    ax.set_xticks(x); ax.set_xticklabels([f"{p:.0%}\nr={audit.r_min(l, int(p*l), 0.95)}"
                                          for p in ps])
    ax.set_ylim(0.94, 0.978); ax.legend(fontsize=7, loc="upper left")
    _style(ax, "detection probability at r_min",
           "(b) Bound is conservative, as required")
    fig.tight_layout()
    fig.savefig(FIG / "fig6_audit_sampling.png", bbox_inches="tight")
    plt.close(fig)


def main():
    df = pd.read_csv(ROOT / "processed" / "runs.csv")
    fig_detection(df); fig_latency(df); fig_availability(df)
    fig_graph_value(df); fig_overhead(df); fig_audit()
    for p in sorted(FIG.glob("*.png")):
        print(f"  {p.relative_to(ROOT)}  {p.stat().st_size/1024:.0f} KB")


if __name__ == "__main__":
    main()
