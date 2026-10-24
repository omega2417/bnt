"""Static report figures (matplotlib).

Design rules used throughout: each entity keeps one colour in every figure
(conditions: blue / orange / aqua; diagnoses: violet / magenta / green),
"higher is better" axes are oriented so that outward/up always means better,
violations of the invariants are shown as counts next to a tick or a cross,
never by colour alone, and grids and spines stay recessive.
"""
from __future__ import annotations

import warnings
from pathlib import Path

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

COND_ORDER = ["reminder", "single_agent", "proposed"]
COND_COLORS = {"proposed": "#2a78d6", "single_agent": "#eb6834", "reminder": "#1baf7a"}
COND_LABELS = {"reminder": "Reminder app", "single_agent": "Single agent + RAG", "proposed": "Proposed framework"}
DX_ORDER = ["MCI", "mild_dementia", "ABI"]
DX_COLORS = {"MCI": "#6250d6", "mild_dementia": "#e87ba4", "ABI": "#008300"}
DX_LABELS = {"MCI": "MCI", "mild_dementia": "Mild dementia", "ABI": "Acquired brain injury"}
INK, INK2, MUTED, SURFACE = "#0b0b0b", "#52514e", "#8a8984", "#fcfcfb"
BLUES = LinearSegmentedColormap.from_list("pg_blues", ["#eef4fc", "#9cc2ee", "#2a78d6", "#123f78"])
REDS = LinearSegmentedColormap.from_list("pg_reds", ["#fdf0ef", "#f2a3a2", "#e34948", "#8c1d1c"])
DIVERGE = LinearSegmentedColormap.from_list("pg_div", ["#d95926", "#f3c6b1", "#e9e8e4", "#a9c9ef", "#2a78d6"])

plt.rcParams.update({
    "figure.dpi": 110, "savefig.dpi": 160, "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#c9c8c2",
    "axes.grid": True, "grid.color": "#e4e3de", "grid.linewidth": 0.6, "axes.axisbelow": True,
    "font.size": 9.5, "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
    "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2, "text.color": INK,
    "legend.frameon": False,
})


def _save(fig, out: Path | None, name: str):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)   # colorbar axes vs tight_layout
        fig.tight_layout()
    if out is not None:
        fig.savefig(Path(out) / name, bbox_inches="tight", facecolor=SURFACE)
    return fig


def _kde(x: np.ndarray, grid: np.ndarray, bw: float | None = None) -> np.ndarray:
    x = np.asarray(x, float)
    bw = bw or 1.06 * x.std() * len(x) ** -0.2 or 1.0
    return np.exp(-0.5 * ((grid[:, None] - x[None, :]) / bw) ** 2).sum(1) / (len(x) * bw * np.sqrt(2 * np.pi))


# ------------------------------------------------------------------ cohort
def cohort_overview(cohort: pd.DataFrame, out: Path | None = None):
    """Cohort fingerprint: age ridgelines, MoCA x PRMQ landscape with density
    contours, and a standardised metadata heat-strip per diagnosis."""
    fig = plt.figure(figsize=(14, 4.4))
    gs = fig.add_gridspec(1, 3, width_ratios=[1, 1.15, 1.25], wspace=0.35)

    ax = fig.add_subplot(gs[0])
    grid = np.linspace(15, 100, 300)
    for i, dx in enumerate(DX_ORDER[::-1]):
        g = cohort[cohort.diagnosis == dx]
        y = _kde(g.age.to_numpy(), grid)
        y = y / y.max() * 0.9 + i
        ax.fill_between(grid, i, y, color=DX_COLORS[dx], alpha=0.35, lw=0)
        ax.plot(grid, y, color=DX_COLORS[dx], lw=2)
        med = g.age.median()
        ax.plot([med, med], [i, i + 0.9], color=INK, lw=1, ls=":")
        ax.text(16 if med > 60 else 72, i + 0.55, f"{DX_LABELS[dx]}\nn={len(g)}, median {med:.0f}", fontsize=8,
                color=INK2)
    ax.set(yticks=[], xlabel="Age, years", title="Age by diagnosis (ridgelines)")
    ax.grid(axis="y", visible=False)

    ax = fig.add_subplot(gs[1])
    jit = np.random.default_rng(0)
    for dx in DX_ORDER:
        g = cohort[cohort.diagnosis == dx]
        xm, ym = g.moca.to_numpy(float), g.prmq_prospective.to_numpy(float)
        xx, yy = np.meshgrid(np.linspace(8, 31, 80), np.linspace(8, 41, 80))
        bx, by = 1.06 * xm.std() * len(xm) ** -0.2, 1.06 * ym.std() * len(ym) ** -0.2
        zz = np.exp(-0.5 * (((xx[..., None] - xm) / bx) ** 2 + ((yy[..., None] - ym) / by) ** 2)).sum(-1)
        ax.contour(xx, yy, zz, levels=[zz.max() * 0.35, zz.max() * 0.7], colors=DX_COLORS[dx], linewidths=[1, 2])
        ax.scatter(xm + jit.uniform(-.3, .3, len(xm)), ym + jit.uniform(-.3, .3, len(ym)), s=10, alpha=0.45,
                   color=DX_COLORS[dx], edgecolors="none", label=DX_LABELS[dx])
    ax.axvspan(26, 31, color="#e9e8e4", alpha=0.6, lw=0)
    ax.text(26.3, 39, "MoCA ≥ 26\n(normal range)", fontsize=7.5, color=INK2, va="top")
    ax.set(xlim=(8, 31), ylim=(8, 41), xlabel="MoCA (0–30, higher = better)",
           ylabel="PRMQ prospective (higher = more failures)", title="Cognitive landscape")
    ax.legend(loc="lower left", fontsize=8, markerscale=2)

    ax = fig.add_subplot(gs[2])
    cols = {"age": "Age", "moca": "MoCA", "prmq_prospective": "PRMQ-P", "prmq_retrospective": "PRMQ-R",
            "education_years": "Education", "digital_literacy": "Digital literacy", "lives_alone": "Lives alone",
            "has_trusted_person": "Trusted person", "sensors_connected": "Sensors", "uses_voice": "Voice"}
    c = cohort[list(cols)].astype(float)
    z = (c.groupby(cohort.diagnosis).mean() - c.mean()) / c.std()
    z = z.reindex(DX_ORDER)
    im = ax.imshow(z.to_numpy(), cmap=DIVERGE, vmin=-1.2, vmax=1.2, aspect="auto")
    for (i, j), v in np.ndenumerate(z.to_numpy()):
        ax.text(j, i, f"{v:+.1f}", ha="center", va="center", fontsize=8, color=INK)
    ax.set_xticks(range(len(cols)), list(cols.values()), rotation=40, ha="right")
    ax.set_yticks(range(3), ["MCI", "Mild\ndementia", "ABI"])
    ax.grid(False)
    ax.set_title("Metadata fingerprint (z-score vs cohort)")
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02, label="SD from cohort mean")
    return _save(fig, out, "fig1_cohort.png")


# ------------------------------------------------------------- conditions
RADAR_AXES = [  # (metric, label, transform to "higher is better" in [0, 1])
    ("TSR", "Task success", lambda v: v),
    ("FPR", "1 − false prompts", lambda v: 1 - v),
    ("independence", "Independence\n(L0–L1)", lambda v: v),
    ("invented_outcome_rate", "No invented\noutcomes", lambda v: 1 - v),
    ("F_ext", "Recall\nfaithfulness", lambda v: v),
    ("coverage", "Answer\ncoverage", lambda v: v),
    ("overstated_per_100", "No overstated\nclaims", lambda v: 1 - min(v, 100) / 100),
    ("appropriate_behaviour", "Appropriate\nbehaviour", lambda v: v),
]


def condition_radar(summary: pd.DataFrame, out: Path | None = None, name: str = "fig2_radar.png"):
    """Polar profile of all headline indicators with bootstrap-CI bands; every
    axis is oriented so that the outer ring is the desirable end."""
    ang = np.linspace(0, 2 * np.pi, len(RADAR_AXES), endpoint=False)
    fig, ax = plt.subplots(figsize=(7.2, 6.4), subplot_kw=dict(polar=True))
    ax.set_theta_offset(np.pi / 2)
    ax.set_theta_direction(-1)
    for c in COND_ORDER:
        vals, lo, hi, undefined = [], [], [], []
        for k, (m, _, f) in enumerate(RADAR_AXES):
            row = summary[m].loc[c]
            if pd.isna(row.estimate):
                vals.append(0.0); lo.append(0.0); hi.append(0.0); undefined.append(k)
                continue
            a, b = sorted([f(row.ci_low), f(row.ci_high)])
            vals.append(f(row.estimate)); lo.append(a); hi.append(b)
        close = lambda v: np.r_[v, v[:1]]
        th = close(ang)
        ax.fill_between(th, close(np.array(lo)), close(np.array(hi)), color=COND_COLORS[c], alpha=0.25, lw=0)
        ax.plot(th, close(np.array(vals)), color=COND_COLORS[c], lw=2, label=COND_LABELS[c])
        ax.scatter(ang, vals, s=28, color=COND_COLORS[c], edgecolor=SURFACE, linewidth=1.5, zorder=3)
        for k in undefined:
            ax.scatter(ang[k], 0.04, marker="x", s=40, color=COND_COLORS[c], zorder=4)
    ax.set_xticks(ang, [lbl for _, lbl, _ in RADAR_AXES], fontsize=8.5)
    ax.tick_params(axis="x", pad=14)
    ax.set_rlabel_position(22.5)
    ax.set_ylim(0, 1.02)
    ax.set_yticks([0.25, 0.5, 0.75, 1.0], ["0.25", "0.50", "0.75", "1.00"], fontsize=7, color=MUTED)
    ax.spines["polar"].set_visible(False)
    ax.set_title("Condition profiles — outer ring is better\n(bands: 95% cluster-bootstrap CI; × = undefined)",
                 loc="center", pad=22)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=8.5)
    return _save(fig, out, name)


def condition_dots(summary: pd.DataFrame, metrics: list[str], out: Path | None = None,
                   name: str = "fig2b_dots.png"):
    """Dot-and-whisker small multiples (estimate + 95% CI); replaces bar charts
    so that intervals, not bar areas, carry the comparison."""
    fig, axes = plt.subplots(1, len(metrics), figsize=(3.1 * len(metrics), 2.9), sharey=True)
    for ax, m in zip(np.atleast_1d(axes), metrics):
        s = summary[m].reindex(COND_ORDER)
        for i, c in enumerate(COND_ORDER):
            e, lo, hi = s.loc[c]
            if pd.isna(e):
                ax.text(0.02, i, "undefined", va="center", fontsize=8, color=MUTED, transform=ax.get_yaxis_transform())
                continue
            ax.plot([lo, hi], [i, i], color=COND_COLORS[c], lw=2, solid_capstyle="round")
            ax.scatter([e], [i], s=60, color=COND_COLORS[c], edgecolor=SURFACE, linewidth=2, zorder=3)
            ax.annotate(f"{e:.2f}", (e, i), xytext=(0, 8), textcoords="offset points", ha="center", fontsize=8,
                        color=INK2)
        ax.set_title(m, fontsize=10)
        ax.set_ylim(-0.6, 2.6)
        ax.grid(axis="y", visible=False)
    np.atleast_1d(axes)[0].set_yticks(range(3), [COND_LABELS[c] for c in COND_ORDER])
    return _save(fig, out, name)


def paired_forest(paired: pd.DataFrame, out: Path | None = None):
    """Forest plot of per-participant paired differences (proposed − baseline)."""
    d = paired.iloc[::-1].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(8, 0.42 * len(d) + 1.2))
    for i, r in d.iterrows():
        base = r.comparison.split("− ")[-1]
        col = COND_COLORS.get(base, INK2)
        ax.plot([r.ci_low, r.ci_high], [i, i], color=col, lw=2.2, solid_capstyle="round")
        ax.scatter([r.mean_diff], [i], marker="D", s=40, color=col, edgecolor=SURFACE, lw=1.5, zorder=3)
        ax.text(1.02, i, f"{r.mean_diff:+.3f}  [{r.ci_low:+.3f}, {r.ci_high:+.3f}]", va="center", fontsize=8,
                color=INK2, transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(range(len(d)), [f"{r.metric}  vs {COND_LABELS[r.comparison.split('− ')[-1]]}"
                                  for _, r in d.iterrows()], fontsize=8.5)
    ax.grid(axis="y", visible=False)
    ax.set(xlabel="Mean paired difference, proposed − baseline (95% bootstrap CI)",
           title="Paired differences per participant")
    return _save(fig, out, "fig3_forest.png")


# --------------------------------------------------------- people x outcome
def tsr_raincloud(pm: pd.DataFrame, cohort: pd.DataFrame, out: Path | None = None):
    """Raincloud plots (half-violin + box + jittered rain) of participant TSR,
    and the MoCA–independence relation with a LOWESS-like binned trend."""
    d = pm.merge(cohort[["participant_id", "diagnosis", "moca"]], on="participant_id")
    fig, ax = plt.subplots(1, 2, figsize=(13, 4.4), gridspec_kw=dict(width_ratios=[1.6, 1]))
    rng = np.random.default_rng(1)
    w = 0.27
    for i, dx in enumerate(DX_ORDER):
        for j, c in enumerate(COND_ORDER):
            v = d[(d.condition == c) & (d.diagnosis == dx)].TSR.dropna().to_numpy()
            x0 = i + (j - 1) * w
            grid = np.linspace(v.min() - .02, v.max() + .02, 120)
            k = _kde(v, grid)
            k = k / k.max() * w * 0.45
            ax[0].fill_betweenx(grid, x0, x0 + k, color=COND_COLORS[c], alpha=0.45, lw=0)
            ax[0].boxplot([v], positions=[x0], widths=w * 0.18, showfliers=False, patch_artist=True,
                          boxprops=dict(facecolor=SURFACE, edgecolor=INK2), medianprops=dict(color=INK, lw=1.5),
                          whiskerprops=dict(color=INK2), capprops=dict(color=INK2))
            ax[0].scatter(x0 - w * 0.25 + rng.uniform(-w * .12, w * .12, len(v)), v, s=6, alpha=0.5,
                          color=COND_COLORS[c], edgecolors="none")
    ax[0].set_xticks(range(3), [DX_LABELS[d] for d in DX_ORDER])
    ax[0].set(ylabel="Participant TSR", title="Task success by diagnosis and condition (raincloud)")
    ax[0].legend(handles=[Patch(color=COND_COLORS[c], label=COND_LABELS[c]) for c in COND_ORDER],
                 loc="lower right", fontsize=8, ncol=1)
    ax[0].grid(axis="x", visible=False)

    p = d[d.condition == "proposed"]
    for dx in DX_ORDER:
        g = p[p.diagnosis == dx]
        ax[1].scatter(g.moca + rng.uniform(-.25, .25, len(g)), g.independence, s=14, alpha=0.6,
                      color=DX_COLORS[dx], edgecolors="none", label=DX_LABELS[dx])
    b = p.groupby(p.moca.clip(12, 30)).independence.mean()
    ax[1].plot(b.index, b.rolling(3, center=True, min_periods=1).mean(), color=INK, lw=2, label="Binned trend")
    ax[1].set(xlabel="MoCA", ylabel="Share of completions at L0–L1",
              title="Independence vs MoCA (proposed)")
    ax[1].legend(fontsize=8, loc="lower right")
    return _save(fig, out, "fig4_raincloud.png")


# ------------------------------------------------------------------ recall
def recall_heatmap(strata: pd.DataFrame, out: Path | None = None):
    """Strata x condition matrix: colour = share of reference behaviour; the
    cell text adds the invariant violations hidden behind that share."""
    piv = strata.pivot(index="stratum", columns="condition", values="appropriate").reindex(columns=COND_ORDER)
    order = piv.mean(axis=1).sort_values().index
    piv = piv.loc[order]
    st = strata.set_index(["stratum", "condition"])
    fig, ax = plt.subplots(figsize=(8.6, 0.5 * len(piv) + 1.6))
    ax.imshow(piv.to_numpy(), cmap=BLUES, vmin=0, vmax=1, aspect="auto")
    for (i, j), v in np.ndenumerate(piv.to_numpy()):
        r = st.loc[(piv.index[i], piv.columns[j])]
        flags = [f"{int(r[k])} {lbl}" for k, lbl in [("fabricated", "fab"), ("overstated", "over"),
                                                       ("consent_violations", "consent"), ("stale", "stale"),
                                                       ("wrong_event", "wrong-ev")] if r[k] > 0]
        ax.text(j, i - 0.12, f"{v:.0%}", ha="center", va="center", fontsize=9.5, fontweight="bold",
                color="white" if v > 0.6 else INK)
        ax.text(j, i + 0.22, "✗ " + ", ".join(flags) if flags else "✓ no violations", ha="center", va="center",
                fontsize=7, color="white" if v > 0.6 else INK2)
    ax.set_xticks(range(3), [COND_LABELS[c] for c in COND_ORDER])
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(piv)), [s.replace("_", " ") for s in piv.index])
    ax.grid(False)
    ax.set_title("Recall: share of reference behaviour and invariant violations per stratum", pad=28)
    return _save(fig, out, "fig5_recall_heatmap.png")


def invariant_scoreboard(ep: pd.DataFrame, rc: pd.DataFrame, out: Path | None = None):
    """One row per invariant counter; zero cells get a tick, non-zero cells a
    red intensity proportional to log(count) and the exact number."""
    e = ep.groupby("condition")[["unauthorised_contact", "wrong_failure", "invented_outcome"]].sum()
    r = rc.groupby("condition")[["consent_violation", "overstated", "stale_used", "fabricated"]].sum()
    tab = e.join(r).reindex(COND_ORDER)
    labels = {"unauthorised_contact": "I1 contact after consent withdrawal",
              "consent_violation": "I1 disclosure outside consent scope",
              "overstated": "I2 claim stronger than its record",
              "fabricated": "I2 fabricated recollection",
              "invented_outcome": "I3 outcome inferred from silence",
              "wrong_failure": "I3 completed task logged as missed",
              "stale_used": "I4 answer from superseded version"}
    tab = tab[list(labels)].T
    applicable = pd.DataFrame(True, index=tab.index, columns=tab.columns)
    applicable.loc[["consent_violation", "overstated", "fabricated", "stale_used"], "reminder"] = False
    applicable.loc["unauthorised_contact", "reminder"] = False
    z = np.log1p(tab.to_numpy(float))
    fig, ax = plt.subplots(figsize=(8.6, 4.0))
    ax.imshow(np.where(applicable & (tab.to_numpy() > 0), z, np.nan), cmap=REDS, vmin=0, vmax=max(z.max(), 1), aspect="auto")
    for (i, j), v in np.ndenumerate(tab.to_numpy()):
        if not applicable.iloc[i, j]:
            txt, col = "n/a", MUTED
        elif v == 0:
            txt, col = "✓ 0", "#008300"
        else:
            txt, col = f"✗ {int(v)}", "white" if z[i, j] > 0.6 * z.max() else INK
        ax.text(j, i, txt, ha="center", va="center", fontsize=9.5, fontweight="bold", color=col)
    ax.set_xticks(range(3), [COND_LABELS[c] for c in COND_ORDER])
    ax.xaxis.tick_top()
    ax.set_yticks(range(len(tab)), [labels[k] for k in tab.index])
    ax.grid(False)
    ax.set_title("Invariant scoreboard (counts over all episodes and questions)", pad=28)
    return _save(fig, out, "fig6_invariants.png")


def risk_coverage(curve: pd.DataFrame, theta_low: float, theta_high: float, out: Path | None = None,
                  calibrated: dict | None = None):
    """Selective-answering curve: what the release rule (Eq. 5) trades as
    theta_low moves. The current operating point and the calibrated point
    (dev split -> held-out split) are marked."""
    fig, ax = plt.subplots(1, 2, figsize=(12, 4.0))
    c = curve.dropna()
    ax[0].plot(c.coverage, c.F_ext, color=COND_COLORS["proposed"], lw=2)
    sc = ax[0].scatter(c.coverage, c.F_ext, c=c.theta_low, cmap=BLUES, s=14, zorder=3, edgecolors="none")
    pt = curve.loc[(curve.theta_low - theta_low).abs().idxmin()]
    ax[0].scatter([pt.coverage], [pt.F_ext], s=140, facecolor="none", edgecolor=INK, lw=1.5, zorder=4)
    ax[0].annotate(f"θ_low = {theta_low:.2f}\nC = {pt.coverage:.3f}, F_ext = {pt.F_ext:.3f}",
                   (pt.coverage, pt.F_ext), xytext=(-170, 60), textcoords="offset points", fontsize=8,
                   arrowprops=dict(arrowstyle="-", color=INK2))
    if calibrated:
        t = calibrated["test"]
        ax[0].scatter([t["coverage"]], [t["F_ext"]], marker="*", s=180, color="#eda100", edgecolor=INK, zorder=5,
                      label=f"calibrated θ_low={calibrated['theta_low']:.2f} (held-out)")
        ax[0].legend(fontsize=8, loc="lower left")
    fig.colorbar(sc, ax=ax[0], label="θ_low")
    ax[0].set(xlabel="Answer coverage C", ylabel="Recall faithfulness F_ext",
              title="Risk–coverage curve of the release rule")
    ax[1].plot(curve.theta_low, curve.coverage, color=COND_COLORS["proposed"], lw=2, label="coverage C")
    ax[1].plot(curve.theta_low, curve.F_ext, color=INK, lw=2, ls="--", label="F_ext")
    ax[1].axvspan(0, theta_low, color="#f2a3a2", alpha=0.25, lw=0)
    ax[1].axvspan(theta_low, theta_high, color="#f6d58a", alpha=0.3, lw=0)
    ax[1].axvspan(theta_high, 1, color="#9cc2ee", alpha=0.3, lw=0)
    for x, t in [(theta_low / 2, "abstain"), ((theta_low + theta_high) / 2, "answer with\nuncertainty"),
                 ((theta_high + 1) / 2, "answer with\nsource")]:
        ax[1].text(x, 0.06, t, ha="center", fontsize=8, color=INK2)
    ax[1].set(xlabel="θ_low", ylim=(0, 1.04), title="Equation (5) zones over the support score")
    ax[1].legend(fontsize=8, loc="center left", bbox_to_anchor=(0.0, 0.72))
    return _save(fig, out, "fig7_risk_coverage.png")


# ------------------------------------------------------------- assistance
def level_distribution(ep: pd.DataFrame, out: Path | None = None):
    """Diverging stacked bars: completions at L0–L1 extend right, at L2–L4
    left, non-completions are reported separately — so 'more help' and
    'independent' read as opposite directions."""
    d = ep.copy()
    d["lvl"] = np.where(d.completed_true, d.completion_level.fillna(-1).astype(int), -1)
    tab = pd.crosstab(d.condition, d.lvl, normalize="index").reindex(COND_ORDER).fillna(0)
    for k in [-1, 0, 1, 2, 3, 4]:
        if k not in tab:
            tab[k] = 0.0
    colors = {0: "#123f78", 1: "#2a78d6", 2: "#eda100", 3: "#eb6834", 4: "#b43a14"}
    fig, ax = plt.subplots(figsize=(10, 3.2))
    y = np.arange(len(tab))
    left = np.zeros(len(tab))
    for k in (0, 1):
        ax.barh(y, tab[k], left=left, color=colors[k], edgecolor=SURFACE, lw=2, height=0.6, label=f"L{k}")
        left += tab[k].to_numpy()
    right = np.zeros(len(tab))
    for k in (2, 3, 4):
        ax.barh(y, -tab[k], left=-right, color=colors[k], edgecolor=SURFACE, lw=2, height=0.6, label=f"L{k}")
        right += tab[k].to_numpy()
    for i, c in enumerate(tab.index):
        ax.text(left[i] + 0.01, i, f"{left[i]:.0%} at L0–L1", va="center", fontsize=8, color=INK2)
        ax.text(-right[i] - 0.01, i, f"{right[i]:.0%}", va="center", ha="right", fontsize=8, color=INK2)
        ax.text(1.02, i, f"not completed {tab.loc[c, -1]:.0%}", va="center", fontsize=8, color=MUTED,
                transform=ax.get_yaxis_transform())
    ax.axvline(0, color=INK, lw=0.8)
    ax.set_yticks(y, [COND_LABELS[c] for c in tab.index])
    ax.set_xlim(-0.45, 1.0)
    ax.set_xticks([-0.4, -0.2, 0, 0.2, 0.4, 0.6, 0.8], ["40%", "20%", "0", "20%", "40%", "60%", "80%"])
    ax.grid(axis="y", visible=False)
    ax.set(title="Assistance level at completion  ◀ more help · independent ▶", xlabel="share of episodes")
    ax.legend(ncol=5, fontsize=8, loc="upper center", bbox_to_anchor=(0.5, -0.25))
    return _save(fig, out, "fig8_levels.png")


def adaptation_over_time(ep: pd.DataFrame, out: Path | None = None):
    """Equation (3) at work: mean starting level per day in the proposed
    condition for non-safety-critical tasks, with the share of escalations."""
    p = ep[(ep.condition == "proposed")]
    fig, ax = plt.subplots(1, 2, figsize=(12, 3.6))
    task_colors = {"daily_walk": "#2a78d6", "call_family": "#eb6834", "appointment_prep": "#1baf7a",
                   "bill_payment": "#eda100", "medication_morning": "#8a8984"}
    flat = []
    for task, g in p.groupby("task_type"):
        s = g.groupby("day").start_level.mean()
        if s.nunique() == 1:
            flat.append(task.replace("_", " "))
            ax[0].plot(s.index, s.values, lw=2, color=MUTED, ls="--" if task == "medication_morning" else ":")
            continue
        ax[0].plot(s.index, s.values, lw=2, color=task_colors.get(task, INK2))
        ax[0].text(s.index[-1] + 0.4, s.values[-1], task.replace("_", " "), fontsize=8, va="center", color=INK2)
    if flat:
        ax[0].text(p.day.max() + 0.4, s.values[0] if s.nunique() == 1 else 1.0, "unchanged:\n" + "\n".join(flat),
                   fontsize=7.5, va="top", color=MUTED)
    ax[0].set(xlabel="day", ylabel="mean starting level", xlim=(0, p.day.max() + 7),
              title="Starting level adapts down (Eq. 3); safety-critical stays fixed")
    for c in COND_ORDER:
        s = ep[ep.condition == c].groupby("day").escalations.mean()
        ax[1].plot(s.index, s.rolling(3, min_periods=1).mean(), lw=2, color=COND_COLORS[c], label=COND_LABELS[c])
    ax[1].set(xlabel="day", ylabel="escalations per episode (3-day mean)", title="Escalation load over time")
    ax[1].legend(fontsize=8, loc="upper right", bbox_to_anchor=(1.0, 0.72))
    return _save(fig, out, "fig9_adaptation.png")


def entailment_heatmap(mat: pd.DataFrame, title: str, out: Path | None = None, name: str = "fig10_nli.png"):
    """Premise x hypothesis entailment probabilities from the NLI model."""
    fig, ax = plt.subplots(figsize=(1.6 * mat.shape[1] + 4, 0.55 * mat.shape[0] + 1.8))
    ax.imshow(mat.to_numpy(), cmap=BLUES, vmin=0, vmax=1, aspect="auto")
    for (i, j), v in np.ndenumerate(mat.to_numpy()):
        ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=9, color="white" if v > 0.6 else INK)
    ax.set_xticks(range(mat.shape[1]), [_wrap(c, 22) for c in mat.columns], fontsize=8)
    ax.xaxis.tick_top()
    ax.set_yticks(range(mat.shape[0]), [_wrap(r, 48) for r in mat.index], fontsize=8)
    ax.grid(False)
    ax.set_title(title, pad=40)
    return _save(fig, out, name)


def _wrap(s: str, n: int) -> str:
    words, lines, cur = str(s).split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > n and cur:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    return "\n".join(lines + [cur])
