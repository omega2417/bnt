"""Побудова всіх рисунків статті засобами matplotlib (inline).

Figure generation for the reproducibility package.

Кожна функція приймає вже обчислені дані (об'єкт симуляції або датафрейм метрик)
і повертає :class:`matplotlib.figure.Figure`. За переданого ``save`` рисунок також
зберігається у файл (320 dpi). Модуль не викликає ``plt.show()`` — це залишено
ноутбуку, щоб функції були придатні для тестів у безголовому режимі.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from .asf_simulation import (
    ARCH_COLORS,
    ARCH_NAMES,
    ARCH_TITLES,
    CONDS,
    MODALITIES,
    SimulationData,
)


def setup_matplotlib() -> None:
    """Уніфіковані параметри оформлення рисунків."""
    plt.rcParams.update(
        {
            "figure.dpi": 110,
            "savefig.dpi": 320,
            "font.size": 10,
            "axes.grid": True,
            "grid.alpha": 0.3,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )


def _save(fig, save: str | None) -> None:
    if save:
        fig.savefig(save, bbox_inches="tight")


# ------------------------------------------------------------------
# Рис. 1. Візуальний огляд датасету
# ------------------------------------------------------------------
def fig_dataset_overview(sim: SimulationData, save: str | None = None):
    df_dist, df_cond = sim.dist, sim.cond
    fig, axes = plt.subplots(2, 3, figsize=(13, 6.5))

    axes[0, 0].hist(df_dist, bins=40, color="#4878CF", alpha=0.85)
    axes[0, 0].set_title("(a) Дальність подій")
    axes[0, 0].set_xlabel("км")

    vc = np.array([(df_cond == c).sum() for c in CONDS])
    axes[0, 1].bar(CONDS, vc, color="#6ACC65")
    axes[0, 1].set_title("(b) Умови спостереження")
    axes[0, 1].tick_params(axis="x", rotation=30)

    av = [sim.avail[m].mean() * 100 for m in MODALITIES]
    axes[0, 2].bar(MODALITIES, av, color="#D65F5F")
    axes[0, 2].set_ylim(85, 100)
    axes[0, 2].set_title("(c) Доступність сенсорів, %")

    for ax, m in zip(axes[1], MODALITIES[:3]):
        ax.hist(sim.scores[m][sim.y == 0], bins=50, alpha=0.6, label="фон",
                color="#777777", density=True)
        ax.hist(sim.scores[m][sim.y == 1], bins=50, alpha=0.6, label="БпЛА",
                color="#EE854A", density=True)
        ax.set_title(f"Оцінка агента: {m}")
        ax.legend()
    fig.tight_layout()
    _save(fig, save)
    return fig


def fig_optical_scores(sim: SimulationData, save: str | None = None):
    """Розподіл оцінок оптики (не вміщається у сітку 2×3 рис. 1)."""
    fig = plt.figure(figsize=(4.4, 2.9))
    plt.hist(sim.scores["optical"][sim.y == 0], bins=50, alpha=0.6, label="фон",
             color="#777777", density=True)
    plt.hist(sim.scores["optical"][sim.y == 1], bins=50, alpha=0.6, label="БпЛА",
             color="#EE854A", density=True)
    plt.title("Оцінка агента: optical")
    plt.legend()
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 2. Розділюваність класів за архітектурами
# ------------------------------------------------------------------
def fig_score_separability(sim: SimulationData, save: str | None = None):
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.6))
    for ax, a in zip(axes, ARCH_NAMES):
        s = sim.arch[a]
        ax.hist(s[sim.y == 0], bins=60, alpha=0.6, density=True, label="фон", color="#777777")
        ax.hist(s[sim.y == 1], bins=60, alpha=0.6, density=True, label="БпЛА", color="#4878CF")
        ax.set_title(ARCH_TITLES[a])
        ax.set_xlabel("оцінка впевненості")
        ax.legend()
    axes[0].set_ylabel("щільність")
    fig.suptitle("Що менше перекриття розподілів — то краща розділюваність", y=1.04)
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. до Таблиці 4. Pd і FAR з довірчими інтервалами
# ------------------------------------------------------------------
def fig_metrics_bars(metrics, save: str | None = None):
    fig, axes = plt.subplots(1, 2, figsize=(10.5, 3.6))
    xs = np.arange(len(metrics))
    labels = ["Радар", "Статичне", "Агентне"]
    specs = [
        ("pd", "pd_ci_lo", "pd_ci_hi", "Ймовірність виявлення Pd", "#4878CF"),
        ("far", "far_ci_lo", "far_ci_hi", "Рівень хибних тривог FAR", "#D65F5F"),
    ]
    for ax, (col, lo, hi, ttl, clr) in zip(axes, specs):
        err = np.vstack([metrics[col] - metrics[lo], metrics[hi] - metrics[col]])
        ax.bar(xs, metrics[col], yerr=err, capsize=5, color=clr, alpha=0.85)
        ax.set_xticks(xs)
        ax.set_xticklabels(labels)
        ax.set_title(ttl + " (95 % CI)")
        for x, v in zip(xs, metrics[col]):
            ax.text(x, v, f" {v:.3f}", ha="center", va="bottom", fontsize=9)
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 3. Pd за дальністю
# ------------------------------------------------------------------
def fig_pd_by_distance(dist_tab, save: str | None = None):
    fig = plt.figure(figsize=(7.5, 4))
    for a in ARCH_NAMES:
        t = dist_tab[dist_tab.architecture == a]
        plt.plot(t.bin_center, t.pd, "o-", color=ARCH_COLORS[a], label=ARCH_TITLES[a])
    plt.xlabel("Дальність, км")
    plt.ylabel("Pd")
    plt.ylim(0, 1.02)
    plt.title("Рис. 3. Ймовірність виявлення за дальністю (тестова частина)")
    plt.legend()
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 4. ROC-криві та робочі точки
# ------------------------------------------------------------------
def fig_roc(sim: SimulationData, metrics, save: str | None = None):
    from sklearn.metrics import roc_auc_score, roc_curve

    y_te = sim.y_test
    fig = plt.figure(figsize=(6.2, 5))
    for a in ARCH_NAMES:
        s_te = sim.arch[a][sim.test_mask]
        fpr, tpr, _ = roc_curve(y_te, s_te)
        auc = roc_auc_score(y_te, s_te)
        plt.plot(fpr, tpr, color=ARCH_COLORS[a], label=f"{ARCH_TITLES[a]} (AUC={auc:.3f})")
        row = metrics[metrics.architecture == a].iloc[0]
        plt.plot(row.far, row.pd, "o", ms=9, mec="k", color=ARCH_COLORS[a])
    plt.plot([0, 1], [0, 1], "k--", lw=0.8, alpha=0.5)
    plt.xlim(0, 0.25)
    plt.ylim(0.4, 1.005)
    plt.xlabel("FAR")
    plt.ylabel("Pd")
    plt.title("Рис. 4. Компроміс FAR–Pd; маркери — робочі точки з Таблиці 4")
    plt.legend(loc="lower right")
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 5а. Теплокарта Pd за умовами
# ------------------------------------------------------------------
def fig_pd_by_condition(cond_tab, save: str | None = None):
    piv = cond_tab.pivot(index="cond", columns="architecture", values="pd").reindex(CONDS)
    fig, ax = plt.subplots(figsize=(6.4, 3.4))
    im = ax.imshow(piv[ARCH_NAMES].values, cmap="RdYlGn", vmin=0.3, vmax=1.0, aspect="auto")
    ax.set_xticks(range(3))
    ax.set_xticklabels(["Радар", "Статичне", "Агентне"])
    ax.set_yticks(range(len(CONDS)))
    ax.set_yticklabels(CONDS)
    for i in range(len(CONDS)):
        for j, col in enumerate(ARCH_NAMES):
            ax.text(j, i, f"{piv[col].iloc[i]:.2f}", ha="center", va="center", fontsize=9)
    fig.colorbar(im, ax=ax, label="Pd")
    ax.set_title("Pd за умовами спостереження")
    ax.grid(False)
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 5. Абляційний аналіз
# ------------------------------------------------------------------
def fig_ablation(abl, save: str | None = None):
    fig = plt.figure(figsize=(7, 3.6))
    colors = ["#4878CF"] + ["#D65F5F"] * 4
    bars = plt.barh(abl.config[::-1], abl.f1[::-1], color=colors[::-1], alpha=0.9)
    plt.xlabel("F1 (цільовий FAR = 3,5 %)")
    plt.xlim(0.8, 1.0)
    plt.title("Рис. 5. Абляційний аналіз агентного злиття")
    for b, v in zip(bars, abl.f1[::-1]):
        plt.text(v, b.get_y() + b.get_height() / 2, f" {v:.3f}", va="center", fontsize=9)
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 6. Boxplot латентностей
# ------------------------------------------------------------------
def fig_latency_boxplot(sim: SimulationData, save: str | None = None):
    lat_data = [sim.latency[a][sim.test_mask] for a in ARCH_NAMES]
    fig = plt.figure(figsize=(7, 4))
    bp = plt.boxplot(lat_data, tick_labels=["Радар", "Статичне", "Агентне"],
                     showfliers=False, patch_artist=True, widths=0.55)
    for patch, a in zip(bp["boxes"], ARCH_NAMES):
        patch.set_facecolor(ARCH_COLORS[a])
        patch.set_alpha(0.7)
    for i, a in enumerate(ARCH_NAMES):
        med = np.median(sim.latency[a][sim.test_mask])
        plt.text(i + 1, med, f"  медіана {med:.2f} с", va="center", fontsize=9)
    plt.ylabel("Латентність рішення, с")
    plt.title("Рис. 6. Розподіл латентності за архітектурами (без викидів)")
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 7. Часовий резерв
# ------------------------------------------------------------------
def fig_time_margin(tm, save: str | None = None):
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.8))
    axes[0].hist(tm.margin_after_machine_s, bins=60, alpha=0.65, label="після машини", color="#4878CF")
    axes[0].hist(tm.margin_after_human_s, bins=60, alpha=0.65, label="після людини", color="#EE854A")
    axes[0].set_xlabel("Часовий резерв, с")
    axes[0].set_ylabel("К-сть подій")
    axes[0].set_title("Гістограма часового резерву")
    axes[0].legend()

    for col, lbl, c in [
        ("margin_after_machine_s", "після машини", "#4878CF"),
        ("margin_after_human_s", "після людини", "#EE854A"),
    ]:
        xs = np.sort(tm[col])
        axes[1].plot(xs, np.linspace(0, 1, len(xs)), color=c, label=lbl)
    axes[1].set_xlabel("Часовий резерв, с")
    axes[1].set_ylabel("F(x)")
    axes[1].set_title("Емпірична функція розподілу (CDF)")
    axes[1].legend()
    fig.tight_layout()
    _save(fig, save)
    return fig
