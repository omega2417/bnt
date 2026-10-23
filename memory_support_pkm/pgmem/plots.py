"""Figures for the report.  One neutral palette, conditions keep fixed colours."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

COND_COLORS = {"reminder": "#9AA0A6", "single_agent": "#E8A33D", "proposed": "#2F6FB0"}
COND_LABELS = {"reminder": "Нагадування", "single_agent": "Один агент + RAG", "proposed": "Запропонована рамка"}
DX_COLORS = {"MCI": "#2F6FB0", "mild_dementia": "#C2553A", "ABI": "#3E9B6E"}

plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "axes.spines.right": False,
                     "axes.grid": True, "grid.alpha": 0.25, "font.size": 10})


def _save(fig, out: Path | None, name: str):
    fig.tight_layout()
    if out is not None:
        fig.savefig(Path(out) / name, bbox_inches="tight")
    return fig


def cohort_overview(cohort: pd.DataFrame, out: Path | None = None):
    fig, ax = plt.subplots(1, 3, figsize=(13, 3.8))
    for dx, g in cohort.groupby("diagnosis"):
        ax[0].hist(g.age, bins=range(15, 100, 5), alpha=0.6, label=dx, color=DX_COLORS[dx])
        ax[1].hist(g.moca, bins=range(8, 32, 1), alpha=0.6, label=dx, color=DX_COLORS[dx])
        ax[2].scatter(g.moca + np.random.default_rng(0).uniform(-.3, .3, len(g)), g.prmq_prospective,
                      s=12, alpha=0.6, color=DX_COLORS[dx], label=dx)
    ax[0].set(title="Вік за діагнозом", xlabel="років", ylabel="учасників")
    ax[1].set(title="MoCA за діагнозом", xlabel="бал (0–30)")
    ax[1].axvline(26, ls="--", c="k", lw=0.8)
    ax[2].set(title="MoCA vs PRMQ (проспективна)", xlabel="MoCA", ylabel="PRMQ-P (більше = гірше)")
    ax[0].legend(frameon=False)
    return _save(fig, out, "fig1_cohort.png")


def condition_bars(summary: pd.DataFrame, metrics: list[str], out: Path | None = None,
                   name: str = "fig2_conditions.png"):
    """summary: index = condition, columns MultiIndex (metric, estimate/ci_low/ci_high)."""
    fig, axes = plt.subplots(1, len(metrics), figsize=(3.3 * len(metrics), 3.6))
    for ax, m in zip(np.atleast_1d(axes), metrics):
        s = summary[m].reindex(list(COND_COLORS)).dropna(how="all")
        y = s.estimate.to_numpy()
        err = np.vstack([y - s.ci_low.to_numpy(), s.ci_high.to_numpy() - y])
        ax.bar([COND_LABELS[c] for c in s.index], y, yerr=np.nan_to_num(err), capsize=3,
               color=[COND_COLORS[c] for c in s.index])
        ax.set_title(m)
        ax.tick_params(axis="x", rotation=25)
    return _save(fig, out, name)


def tsr_by_diagnosis(pm: pd.DataFrame, cohort: pd.DataFrame, out: Path | None = None):
    d = pm.merge(cohort[["participant_id", "diagnosis", "moca"]], on="participant_id")
    fig, ax = plt.subplots(1, 2, figsize=(11, 3.8))
    dxs = ["MCI", "mild_dementia", "ABI"]
    w = 0.26
    for j, c in enumerate(COND_COLORS):
        vals = [d[(d.condition == c) & (d.diagnosis == dx)].TSR for dx in dxs]
        pos = np.arange(len(dxs)) + (j - 1) * w
        bp = ax[0].boxplot(vals, positions=pos, widths=w * 0.9, patch_artist=True, showfliers=False)
        for b in bp["boxes"]:
            b.set(facecolor=COND_COLORS[c], alpha=0.8)
        ax[0].plot([], [], color=COND_COLORS[c], lw=6, label=COND_LABELS[c])
    ax[0].set_xticks(range(len(dxs)), dxs)
    ax[0].set(title="TSR учасника за діагнозом", ylabel="TSR")
    ax[0].legend(frameon=False, fontsize=8)
    p = d[d.condition == "proposed"]
    ax[1].scatter(p.moca, p.independence, s=14, alpha=0.6, color=COND_COLORS["proposed"])
    ax[1].set(title="Незалежність (L0–L1) vs MoCA — рамка", xlabel="MoCA", ylabel="частка виконань на L0–L1")
    return _save(fig, out, "fig3_tsr_diagnosis.png")


def recall_strata(strata: pd.DataFrame, out: Path | None = None):
    piv = strata.pivot(index="stratum", columns="condition", values="appropriate").reindex(columns=list(COND_COLORS))
    fig, ax = plt.subplots(figsize=(10, 4))
    w = 0.26
    x = np.arange(len(piv))
    for j, c in enumerate(piv.columns):
        ax.bar(x + (j - 1) * w, piv[c], w, color=COND_COLORS[c], label=COND_LABELS[c])
    ax.set_xticks(x, piv.index, rotation=25)
    ax.set(title="Частка відповідей з еталонною поведінкою за стратами", ylabel="частка", ylim=(0, 1.05))
    ax.legend(frameon=False, fontsize=8, ncol=3)
    return _save(fig, out, "fig4_recall_strata.png")


def level_distribution(ep: pd.DataFrame, out: Path | None = None):
    d = ep[ep.completed_true].copy()
    d["lvl"] = d.completion_level.fillna(-1).astype(int)
    tab = pd.crosstab(d.condition, d.lvl, normalize="index").reindex(list(COND_COLORS))
    fig, ax = plt.subplots(figsize=(8, 3.2))
    left = np.zeros(len(tab))
    shades = ["#DCE6F2", "#A9C4E4", "#6E9ED3", "#3B73B9", "#1B4A82"]
    for i, lvl in enumerate(tab.columns):
        ax.barh([COND_LABELS[c] for c in tab.index], tab[lvl], left=left, color=shades[i % 5], label=f"L{lvl}")
        left += tab[lvl].to_numpy()
    ax.set(title="Рівень підтримки, на якому завдання виконано", xlabel="частка виконаних")
    ax.legend(frameon=False, ncol=5, fontsize=8, loc="lower right")
    return _save(fig, out, "fig5_levels.png")
