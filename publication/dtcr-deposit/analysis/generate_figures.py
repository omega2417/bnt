#!/usr/bin/env python3
"""Regenerate every manuscript figure from the published data.

Figures written to ``figures/`` (PNG at 600 dpi and PDF):

  figure5   detection latency and recovery time per scenario, with individual
            run points, box plots and mean +/- 95% CI (replaces the bar chart)
  figure6   mean availability trajectory with a 95% confidence band, the NRI
            integration window, and the per-run NRI distribution
  figure7   analytical audit-detection sensitivity (exact and lower bound)
  figure8   dependency-risk propagation example and lambda sensitivity
  figure9   integrity confusion metrics by corruption level (new)
  figure10  resource overhead with both denominators (new)
  figure11  ablation study across framework variants (new)

Usage:  python analysis/generate_figures.py --data data --results results --out figures
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt          # noqa: E402
import numpy as np                        # noqa: E402
import pandas as pd                       # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dtcr import audit, risk              # noqa: E402
from dtcr.resilience import NRIConfig     # noqa: E402
from calculate_nri import load_config     # noqa: E402

SCENARIOS = ["S1", "S2", "S3", "S4"]
C_BASE, C_FRAME = "#B4442E", "#2F6F8F"
C_GRID = "#D8D8D8"

plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 9,
    "axes.grid": True, "grid.color": C_GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "axes.spines.top": False, "axes.spines.right": False,
    "figure.dpi": 120, "savefig.bbox": "tight",
})


def save(fig, out: Path, name: str):
    out.mkdir(parents=True, exist_ok=True)
    fig.savefig(out / f"{name}.png", dpi=600)
    fig.savefig(out / f"{name}.pdf")
    plt.close(fig)
    print(f"  wrote {name}.png / {name}.pdf")


def _paired_panel(ax, runs, column, ylabel, title):
    """Individual points + box + mean with 95% CI, per scenario and arm."""
    width, offset = 0.30, 0.19
    for i, s in enumerate(SCENARIOS):
        for j, (method, colour) in enumerate([("baseline", C_BASE),
                                              ("framework", C_FRAME)]):
            v = runs[(runs.scenario == s) & (runs.method == method)][column].to_numpy(float)
            v = v[~np.isnan(v)]
            x = i + (-offset if j == 0 else offset)
            bp = ax.boxplot(v, positions=[x], widths=width, showfliers=False,
                            patch_artist=True, medianprops=dict(color="#222", lw=1.2),
                            whiskerprops=dict(color=colour, lw=1.0),
                            capprops=dict(color=colour, lw=1.0))
            bp["boxes"][0].set(facecolor=colour, alpha=0.20, edgecolor=colour, lw=1.1)
            jitter = (np.random.default_rng(hash((s, method)) % 2**32).uniform(-0.075, 0.075, v.size))
            ax.plot(x + jitter, v, "o", ms=2.6, color=colour, alpha=0.65, mec="none", zorder=3)
            m = v.mean()
            se = v.std(ddof=1) / np.sqrt(v.size)
            from scipy import stats as sps
            h = sps.t.ppf(0.975, v.size - 1) * se
            ax.errorbar(x, m, yerr=h, fmt="D", ms=4.2, color=colour, mec="white",
                        mew=0.7, ecolor=colour, elinewidth=1.6, capsize=3.5, zorder=4)
    ax.set_xticks(range(len(SCENARIOS)))
    ax.set_xticklabels(SCENARIOS)
    ax.set_xlabel("Scenario")
    ax.set_ylabel(ylabel)
    ax.set_title(title, loc="left", fontsize=9.5, fontweight="bold")
    ax.set_xlim(-0.6, len(SCENARIOS) - 0.4)


def figure5(runs: pd.DataFrame, out: Path):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.7))
    _paired_panel(axes[0], runs, "detection_latency_s",
                  "Detection latency (s)", "(a) Detection latency")
    _paired_panel(axes[1], runs, "recovery_time_s",
                  "Service recovery time (s)", "(b) Service recovery time")
    handles = [plt.Line2D([], [], color=C_BASE, marker="D", ls="", ms=5,
                          label="IDS-only + manual recovery (baseline)"),
               plt.Line2D([], [], color=C_FRAME, marker="D", ls="", ms=5,
                          label="Proposed framework")]
    fig.legend(handles=handles, loc="lower center", ncol=2, frameon=False,
               bbox_to_anchor=(0.5, -0.09))
    fig.text(0.5, -0.17, "n = 20 paired repetitions per scenario and arm; boxes show the "
             "median and IQR, diamonds the mean with a 95% confidence interval, "
             "dots the individual runs.", ha="center", fontsize=7.4, color="#555")
    save(fig, out, "figure5_detection_recovery")


def figure6(traj: pd.DataFrame, per_run: pd.DataFrame, cfg: NRIConfig, out: Path,
            scenario: str = "S3"):
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.7),
                             gridspec_kw={"width_ratios": [2.1, 1]})
    ax = axes[0]
    for method, colour, label in [("baseline", C_BASE, "Baseline"),
                                  ("framework", C_FRAME, "Proposed framework")]:
        t = traj[(traj.scenario == scenario) & (traj.method == method)]
        ax.fill_between(t.t_rel_s, t.ci95_lo, t.ci95_hi, color=colour, alpha=0.20, lw=0)
        ax.plot(t.t_rel_s, t["mean"], color=colour, lw=1.9, label=label)
    ax.axhline(cfg.a_min, color="#444", ls="--", lw=1.0)
    ax.annotate(f"$A_{{min}}$ = {cfg.a_min:g}", xy=(-58, cfg.a_min),
                xytext=(0, -12), textcoords="offset points", fontsize=7.6,
                color="#444", ha="left")
    ax.axvspan(0, 2 * cfg.rto, color="#999", alpha=0.07, lw=0)
    ax.axvline(0, color="#666", lw=0.9)
    ax.axvline(2 * cfg.rto, color="#666", lw=0.9)
    ax.annotate("NRI integration window\n$[t_{dis},\; t_{dis}+2\\,RTO]$",
                xy=(cfg.rto, 0.30), ha="center", fontsize=7.6, color="#444")
    ax.set_xlabel("Time relative to disruption onset $t_{dis}$ (s)")
    ax.set_ylabel("Service availability $A(t)$")
    ax.set_title(f"(a) Availability trajectory, {scenario}", loc="left",
                 fontsize=9.5, fontweight="bold")
    ax.set_ylim(0.15, 1.02)
    ax.set_xlim(-60, 2 * cfg.rto)
    ax.legend(frameon=False, loc="lower right", fontsize=8)

    ax2 = axes[1]
    data, colours = [], []
    for method, colour in [("baseline", C_BASE), ("framework", C_FRAME)]:
        data.append(per_run[(per_run.scenario == scenario) &
                            (per_run.method == method)].nri.to_numpy())
        colours.append(colour)
    parts = ax2.violinplot(data, positions=[0, 1], widths=0.75, showextrema=False)
    for body, colour in zip(parts["bodies"], colours):
        body.set(facecolor=colour, alpha=0.25, edgecolor=colour, lw=1.1)
    for i, (v, colour) in enumerate(zip(data, colours)):
        j = np.random.default_rng(7 + i).uniform(-0.07, 0.07, v.size)
        ax2.plot(i + j, v, "o", ms=3.0, color=colour, alpha=0.7, mec="none")
        from scipy import stats as sps
        h = sps.t.ppf(0.975, v.size - 1) * v.std(ddof=1) / np.sqrt(v.size)
        ax2.errorbar(i, v.mean(), yerr=h, fmt="D", ms=4.5, color=colour,
                     mec="white", mew=0.7, elinewidth=1.6, capsize=3.5, zorder=4)
        ax2.annotate(f"{v.mean():.3f}", xy=(i, v.mean()), xytext=(11, -2),
                     textcoords="offset points", fontsize=8, color=colour,
                     fontweight="bold")
    ax2.set_xticks([0, 1]); ax2.set_xticklabels(["Baseline", "Framework"])
    ax2.set_ylabel("Normalized resilience index")
    ax2.set_title("(b) Per-run NRI", loc="left", fontsize=9.5, fontweight="bold")
    fig.text(0.5, -0.10, "Shaded band: 95% confidence interval of the mean over "
             "n = 20 runs. Both panels are computed by analysis/calculate_nri.py "
             "from data/availability_traces/.", ha="center", fontsize=7.4, color="#555")
    save(fig, out, "figure6_availability_nri")


def figure7(out: Path):
    fig, ax = plt.subplots(figsize=(5.4, 3.6))
    r = np.arange(1, 401)
    for p, colour in zip([0.01, 0.05, 0.10, 0.20],
                         ["#2F6F8F", "#4E9A6B", "#C8862B", "#B4442E"]):
        ax.plot(r, audit.p_detect_bound(p, r), color=colour, lw=1.8,
                label=f"$p$ = {p:.0%} (bound)")
        exact = [audit.p_detect_exact(10000, int(p * 10000), int(k))
                 for k in np.linspace(1, 400, 60)]
        ax.plot(np.linspace(1, 400, 60), exact, ls=":", lw=1.2, color=colour)
    ax.axhline(0.95, color="#444", ls="--", lw=1.0)
    ax.annotate("target $\\eta$ = 0.95", xy=(300, 0.95), xytext=(0, -12),
                textcoords="offset points", fontsize=7.6, color="#444")
    ax.set_xlabel("Number of challenged blocks $r$")
    ax.set_ylabel("Probability of detecting at least one corrupted block")
    ax.set_title("Audit-detection sensitivity (l = 10,000 blocks)", loc="left",
                 fontsize=9.5, fontweight="bold")
    ax.legend(frameon=False, fontsize=7.8, loc="lower right")
    ax.set_ylim(0, 1.02); ax.set_xlim(0, 400)
    fig.text(0.5, -0.06, "Solid: independent-sampling lower bound, Eq. (5). "
             "Dotted: exact hypergeometric probability, Eq. (4).",
             ha="center", fontsize=7.4, color="#555")
    save(fig, out, "figure7_audit_sensitivity")


def figure8(out: Path):
    """Four-node dependency example of Section 3.5, recomputed from dtcr.risk.

    Panel (b) answers the reviewer request for a spectral radius and a
    convergence margin. The acyclic chain of Section 3.5 is nilpotent, so
    rho(lambda W^T) = 0 and Eq. (10) converges for every lambda; the constraint
    only binds once a feedback edge exists. Both cases are therefore plotted.
    """
    names = ["Sensor", "Edge broker", "Analytics", "Civil service"]
    W = np.zeros((4, 4))
    W[0, 1] = 0.70   # sensor -> broker
    W[1, 2] = 0.80   # broker -> analytics
    W[1, 3] = 0.40   # broker -> civil service
    W[2, 3] = 0.60   # analytics -> civil service
    R = np.array([0.60, 0.10, 0.05, 0.02])
    lam = 0.45
    Rt = risk.propagate(R, W, lam)

    # Cyclic variant: the civil service feeds a control signal back to the sensor.
    Wc = W.copy()
    Wc[3, 0] = 0.55

    fig, axes = plt.subplots(1, 2, figsize=(9.4, 3.7))
    ax = axes[0]
    pos = {0: (0.06, 0.52), 1: (0.38, 0.52), 2: (0.70, 0.86), 3: (0.97, 0.30)}
    label_off = {0: (0, -0.17), 1: (0, -0.17), 2: (-0.20, -0.02), 3: (0, -0.17)}
    edge_shift = {(0, 1): (0.0, 0.05), (1, 2): (-0.055, 0.02),
                  (1, 3): (0.0, 0.055), (2, 3): (0.06, 0.02)}
    for (i, j), w in [((0, 1), 0.70), ((1, 2), 0.80), ((1, 3), 0.40), ((2, 3), 0.60)]:
        x1, y1 = pos[i]; x2, y2 = pos[j]
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle="-|>", lw=0.7 + 2.2 * w,
                                    color="#8899A6", shrinkA=18, shrinkB=18))
        dx, dy = edge_shift[(i, j)]
        ax.text((x1 + x2) / 2 + dx, (y1 + y2) / 2 + dy, f"{w:.2f}", fontsize=7.8,
                ha="center", va="center", color="#5A6B77",
                bbox=dict(boxstyle="round,pad=0.15", fc="white", ec="none", alpha=0.85))
    for i, name in enumerate(names):
        x, y = pos[i]
        ax.scatter([x], [y], s=300 + 1700 * Rt[i], color=C_FRAME, alpha=0.28,
                   edgecolors=C_FRAME, linewidths=1.3, zorder=3)
        ax.text(x, y, f"{Rt[i]:.3f}", ha="center", va="center", fontsize=8,
                fontweight="bold", color="#12303D", zorder=4)
        ox, oy = label_off[i]
        ha = "center" if ox == 0 else ("right" if ox < 0 else "left")
        va = "center" if ox != 0 else ("top" if oy < 0 else "bottom")
        ax.text(x + ox, y + oy, f"{name}\n$R$={R[i]:.2f}", ha=ha, va=va,
                fontsize=7.6, color="#333")
    ax.set_xlim(-0.10, 1.14); ax.set_ylim(-0.02, 1.10)
    ax.axis("off")
    ax.set_title("(a) Local and propagated risk", loc="left", fontsize=9.5,
                 fontweight="bold")
    ax.text(0.0, 0.0, f"$\\kappa$ = {risk.amplification(R, Rt):.3f}", fontsize=8.4,
            color="#12303D", fontweight="bold")

    ax2 = axes[1]
    lam_star = 1.0 / risk.spectral_radius(Wc, 1.0)   # margin reaches zero here
    lams = np.linspace(0, lam_star * 1.12, 300)
    kap_a, kap_c, margin_c = [], [], []
    for lm in lams:
        kap_a.append(risk.amplification(R, risk.propagate(R, W, lm)))
        m = risk.convergence_margin(Wc, lm)
        margin_c.append(m)
        kap_c.append(risk.amplification(R, risk.propagate(R, Wc, lm)) if m > 1e-9 else np.nan)
    l1, = ax2.plot(lams, kap_a, color=C_FRAME, lw=1.9,
                   label="$\\kappa$, acyclic chain (Section 3.5)")
    l2, = ax2.plot(lams, kap_c, color="#C8862B", lw=1.9,
                   label="$\\kappa$, with feedback edge")
    ax2.axvline(lam, color="#444", ls="--", lw=1.0)
    ax2.annotate(f"operating point\n$\\lambda$ = {lam}", xy=(lam, 1.15),
                 xytext=(6, 0), textcoords="offset points", fontsize=7.6, color="#444")
    ax2.axvline(lam_star, color=C_BASE, ls="-.", lw=1.0, alpha=0.8)
    ax2.annotate(f"$\\lambda^*$ = {lam_star:.2f}", xy=(lam_star, 1.15), xytext=(-4, 0),
                 textcoords="offset points", fontsize=7.6, color=C_BASE, ha="right")
    ax3 = ax2.twinx()
    l3, = ax3.plot(lams, margin_c, color=C_BASE, lw=1.4, ls=":",
                   label="$1-\\rho(\\lambda W^T)$, with feedback edge")
    ax3.axhline(0, color=C_BASE, lw=0.8, alpha=0.5)
    ax3.set_ylabel("Convergence margin", color=C_BASE)
    ax3.tick_params(axis="y", colors=C_BASE); ax3.grid(False)
    ax2.set_yscale("log")
    ax2.set_xlabel("Damping factor $\\lambda$")
    ax2.set_ylabel("Aggregate risk amplification $\\kappa$ (log scale)")
    ax2.set_title("(b) Amplification and convergence", loc="left", fontsize=9.5,
                  fontweight="bold")
    ax2.legend([l1, l2, l3], [l.get_label() for l in (l1, l2, l3)], frameon=False,
               fontsize=7.4, loc="upper left")
    fig.text(0.5, -0.07, "Panel (a) uses the raw edge weights printed in Section 3.5. "
             "The acyclic chain is nilpotent, so $\\rho(\\lambda W^T)=0$ and Eq. (10) "
             "converges for all $\\lambda$; the margin is shown for the cyclic variant, "
             "whose convergence limit is $\\lambda^*=1/\\rho(W^T)$. The operating point "
             "$\\lambda=0.45$ lies well inside it.",
             ha="center", fontsize=7.4, color="#555")
    save(fig, out, "figure8_risk_propagation")


def figure9(integrity: pd.DataFrame, out: Path):
    d = integrity[(integrity.corruption_fraction != "all")].copy()
    d["corruption_fraction"] = d.corruption_fraction.astype(float)
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.5))
    ax = axes[0]
    for s, colour in zip(SCENARIOS, ["#2F6F8F", "#4E9A6B", "#C8862B", "#B4442E"]):
        sub = d[d.scenario == s].sort_values("corruption_fraction")
        ax.errorbar(sub.corruption_fraction * 100, sub.recall,
                    yerr=[sub.recall - sub.recall_ci95_lo,
                          sub.recall_ci95_hi - sub.recall],
                    marker="o", ms=4, lw=1.6, capsize=3, color=colour, label=s)
    ax.set_xlabel("Corrupted fraction of blocks (%)")
    ax.set_ylabel("Sensitivity (recall)")
    ax.set_title("(a) Detection sensitivity vs corruption level", loc="left",
                 fontsize=9.5, fontweight="bold")
    ax.legend(frameon=False, fontsize=8, ncol=2)

    ax2 = axes[1]
    pooled = integrity[(integrity.scenario != "pooled") &
                       (integrity.corruption_fraction == "all")]
    metrics = ["accuracy", "recall", "specificity", "precision", "f1"]
    x = np.arange(len(metrics))
    w = 0.19
    for i, (s, colour) in enumerate(zip(SCENARIOS,
                                        ["#2F6F8F", "#4E9A6B", "#C8862B", "#B4442E"])):
        row = pooled[pooled.scenario == s].iloc[0]
        ax2.bar(x + (i - 1.5) * w, [row[m] for m in metrics], width=w,
                color=colour, alpha=0.85, label=s)
    ax2.set_xticks(x)
    ax2.set_xticklabels(["Accuracy", "Recall", "Specificity", "Precision", "F1"],
                        fontsize=8)
    ax2.set_ylim(0.90, 1.005)
    ax2.set_ylabel("Value")
    ax2.set_title("(b) Integrity-verification metrics by scenario", loc="left",
                  fontsize=9.5, fontweight="bold")
    ax2.legend(frameon=False, fontsize=8, ncol=4, loc="lower center")
    fig.text(0.5, -0.06, "Observation unit: one challenged telemetry block. "
             "Error bars are Wilson 95% intervals.", ha="center", fontsize=7.4,
             color="#555")
    save(fig, out, "figure9_integrity_metrics")


def figure10(overhead: pd.DataFrame, out: Path):
    d = overhead.dropna(subset=["relative_overhead_pct_eq17"])
    d = d[d.relative_overhead_pct_eq17 > 0]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.4))
    labels = [m.replace("_", " ") for m in d.metric]
    y = np.arange(len(d))
    axes[0].barh(y, d.relative_overhead_pct_eq17, color=C_FRAME, alpha=0.85, height=0.55)
    axes[0].axvline(6.0, color=C_BASE, ls="--", lw=1.2)
    axes[0].annotate("published bound 6%", xy=(6.0, len(d) - 0.6), xytext=(4, 0),
                     textcoords="offset points", fontsize=7.6, color=C_BASE)
    for i, v in enumerate(d.relative_overhead_pct_eq17):
        axes[0].text(v + 0.12, i, f"{v:.2f}%", va="center", fontsize=8)
    axes[0].set_yticks(y); axes[0].set_yticklabels(labels, fontsize=8)
    axes[0].set_xlabel("Relative overhead vs baseline consumption (%), Eq. (17)")
    axes[0].set_title("(a) Eq. (17) denominator", loc="left", fontsize=9.5,
                      fontweight="bold")
    axes[0].set_xlim(0, 7.5)

    axes[1].barh(y, d.share_of_capacity_pct, color="#4E9A6B", alpha=0.85, height=0.55)
    for i, v in enumerate(d.share_of_capacity_pct):
        axes[1].text(v + 0.006, i, f"{v:.3f}%", va="center", fontsize=8)
    axes[1].set_yticks(y); axes[1].set_yticklabels([])
    axes[1].set_xlabel("Additional consumption as a share of cluster capacity (%)")
    axes[1].set_title("(b) Cluster-capacity denominator", loc="left", fontsize=9.5,
                      fontweight="bold")
    fig.text(0.5, -0.08, "The two panels use different denominators. Section 3.2 of the "
             "revised manuscript reports panel (a) and cites panel (b) separately.",
             ha="center", fontsize=7.4, color="#555")
    save(fig, out, "figure10_overhead")


def figure11(ablation: pd.DataFrame, out: Path):
    order = ["B0_ids_manual", "B1_ids_playbook", "B2_stack_no_dt",
             "A1_no_graph", "A2_no_whatif", "FULL_framework"]
    d = ablation.set_index("variant").loc[order].reset_index()
    short = [v.split("_", 1)[0] for v in d.variant]
    fig, axes = plt.subplots(1, 3, figsize=(11.0, 3.5))
    x = np.arange(len(d))

    axes[0].bar(x - 0.2, d.detection_latency_mean_s, 0.4, yerr=d.detection_latency_sd_s,
                color=C_BASE, alpha=0.85, capsize=3, label="Detection")
    axes[0].bar(x + 0.2, d.recovery_time_mean_s / 10, 0.4,
                yerr=d.recovery_time_sd_s / 10, color=C_FRAME, alpha=0.85,
                capsize=3, label="Recovery / 10")
    axes[0].set_xticks(x); axes[0].set_xticklabels(short, fontsize=8)
    axes[0].set_ylabel("Seconds")
    axes[0].set_title("(a) Latency", loc="left", fontsize=9.5, fontweight="bold")
    axes[0].legend(frameon=False, fontsize=8)

    for col, colour, label in [("unsafe_action_rate", "#B4442E", "Unsafe action"),
                               ("policy_violation_rate", "#C8862B", "Policy violation"),
                               ("rollback_rate", "#2F6F8F", "Rollback")]:
        axes[1].plot(x, d[col], marker="o", ms=4.5, lw=1.7, color=colour, label=label)
        axes[1].fill_between(x, d[f"{col}_ci95_lo"], d[f"{col}_ci95_hi"],
                             color=colour, alpha=0.15, lw=0)
    axes[1].set_xticks(x); axes[1].set_xticklabels(short, fontsize=8)
    axes[1].set_ylabel("Rate")
    axes[1].set_title("(b) Safety of automated action", loc="left", fontsize=9.5,
                      fontweight="bold")
    axes[1].legend(frameon=False, fontsize=8)

    axes[2].plot(x, d.recovery_success_rate, marker="s", ms=4.5, lw=1.7,
                 color="#4E9A6B", label="Recovery success")
    axes[2].fill_between(x, d.recovery_success_rate_ci95_lo,
                         d.recovery_success_rate_ci95_hi, color="#4E9A6B",
                         alpha=0.15, lw=0)
    axes[2].plot(x, d.risk_ranking_accuracy, marker="^", ms=4.5, lw=1.7,
                 color="#2F6F8F", label="Risk-ranking accuracy")
    axes[2].fill_between(x, d.risk_ranking_accuracy_ci95_lo,
                         d.risk_ranking_accuracy_ci95_hi, color="#2F6F8F",
                         alpha=0.15, lw=0)
    axes[2].set_xticks(x); axes[2].set_xticklabels(short, fontsize=8)
    axes[2].set_ylabel("Rate"); axes[2].set_ylim(0.5, 1.02)
    axes[2].set_title("(c) Correctness", loc="left", fontsize=9.5, fontweight="bold")
    axes[2].legend(frameon=False, fontsize=8, loc="lower left")
    fig.text(0.5, -0.07, "B0 IDS+manual; B1 IDS+playbook; B2 security stack without the "
             "digital twin; A1 framework without graph propagation; A2 framework without "
             "what-if simulation; FULL complete framework. Bands are Wilson 95% intervals.",
             ha="center", fontsize=7.4, color="#555")
    save(fig, out, "figure11_ablation")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--data", default="data")
    ap.add_argument("--results", default="results")
    ap.add_argument("--configs", default="configs/framework_parameters.yaml")
    ap.add_argument("--out", default="figures")
    args = ap.parse_args()
    data, res, out = Path(args.data), Path(args.results), Path(args.out)

    cfg = load_config(Path(args.configs))
    runs = pd.read_csv(data / "run_level_metrics.csv")
    traj = pd.read_csv(res / "availability_trajectories.csv")
    per_run = pd.read_csv(res / "nri_per_run.csv")
    integrity = pd.read_csv(res / "table_S4_integrity.csv")
    overhead = pd.read_csv(res / "table_S5_overhead.csv")
    ablation = pd.read_csv(res / "table_S6_ablation.csv")

    print("generating figures:")
    figure5(runs, out)
    figure6(traj, per_run, cfg, out)
    figure7(out)
    figure8(out)
    figure9(integrity, out)
    figure10(overhead, out)
    figure11(ablation, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
