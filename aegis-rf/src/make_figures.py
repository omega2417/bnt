"""Побудова рисунків AEGIS-RF (inline, matplotlib).

Figure generation for the AEGIS-RF reproducibility package.

Кожна функція повертає :class:`matplotlib.figure.Figure`; за переданого ``save``
рисунок зберігається (320 dpi). Модуль не викликає ``plt.show()`` — це лишено
ноутбуку, тож функції придатні для тестів у безголовому режимі.
"""

from __future__ import annotations

import matplotlib.pyplot as plt
import numpy as np

from . import environment as env
from .localization import localize
from .sensing import Observations

METHOD_TITLES = {
    "rssi": "Лише RSSI",
    "ftm": "Лише FTM/RTT",
    "fusion": "Наївне злиття",
    "robust": "Робастне злиття",
}
METHOD_COLORS = {
    "rssi": "#777777",
    "ftm": "#6ACC65",
    "fusion": "#EE854A",
    "robust": "#4878CF",
}
SCENARIO_TITLES = {
    "clean": "Без атак",
    "evil_twin": "Evil twin",
    "deceptive_ranging": "Deceptive ranging",
    "deauth": "Deauth",
}


def setup_matplotlib() -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 110, "savefig.dpi": 320, "font.size": 10,
            "axes.grid": True, "grid.alpha": 0.3,
            "axes.spines.top": False, "axes.spines.right": False,
        }
    )


def _save(fig, save):
    if save:
        fig.savefig(save, bbox_inches="tight")


def _draw_room(ax):
    """Намалювати контур приміщення, критичну зону та точки доступу."""
    ax.add_patch(plt.Rectangle((0, 0), env.AREA_W, env.AREA_H, fill=False, ec="#333", lw=1.2))
    ax.add_patch(
        plt.Rectangle(
            (env.CRIT_X0, env.CRIT_Y0), env.CRIT_X1 - env.CRIT_X0, env.CRIT_Y1 - env.CRIT_Y0,
            fc="#D65F5F", ec="#D65F5F", alpha=0.15, lw=1.2, label="критична зона",
        )
    )
    for i, (x, y) in enumerate(env.AP_POSITIONS):
        marker = "^" if env.FTM_CAPABLE[i] else "s"
        ax.plot(x, y, marker, ms=11, color="#1f3b73", mec="k", zorder=5)
        ax.annotate(f"AP{i}", (x, y), textcoords="offset points", xytext=(6, 5), fontsize=8)
    ax.set_xlim(-1, env.AREA_W + 1)
    ax.set_ylim(-1, env.AREA_H + 1)
    ax.set_aspect("equal")
    ax.set_xlabel("x, м")
    ax.set_ylabel("y, м")


# ------------------------------------------------------------------
# Рис. 1. Карта середовища КІІ
# ------------------------------------------------------------------
def fig_environment(exp, save=None):
    fig, ax = plt.subplots(figsize=(7.2, 6))
    _draw_room(ax)
    pos = exp.base_obs.pos
    ax.scatter(pos[:, 0], pos[:, 1], s=6, alpha=0.25, color="#4878CF", label="події (джерела)")
    ax.set_title("Рис. 1. Середовище КІІ: AP (▲ = FTM), критична зона, події")
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 2. CDF похибки локалізації (сценарій clean)
# ------------------------------------------------------------------
def fig_error_cdf(exp, scenario="clean", save=None):
    obs = exp.scenarios[scenario]
    fig = plt.figure(figsize=(7, 4.2))
    for method in ("rssi", "ftm", "fusion", "robust"):
        err = np.sort(localize(obs, exp.radiomap, method).error)
        cdf = np.linspace(0, 1, len(err))
        plt.plot(err, cdf, color=METHOD_COLORS[method], label=METHOD_TITLES[method])
    plt.xlim(0, 12)
    plt.xlabel("Похибка локалізації, м")
    plt.ylabel("F(x)")
    plt.title(f"Рис. 2. CDF похибки локалізації ({SCENARIO_TITLES[scenario]})")
    plt.legend()
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 3. Медіанна похибка за сценаріями та методами
# ------------------------------------------------------------------
def fig_error_bars(table, save=None):
    scenarios = list(SCENARIO_TITLES)
    methods = ["rssi", "ftm", "fusion", "robust"]
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    width = 0.2
    xs = np.arange(len(scenarios))
    for j, method in enumerate(methods):
        vals, los, his = [], [], []
        for sc in scenarios:
            row = table[(table.scenario == sc) & (table.method == method)].iloc[0]
            vals.append(row.median_err_m)
            los.append(row.median_err_m - row.median_ci_lo)
            his.append(row.median_ci_hi - row.median_err_m)
        ax.bar(xs + (j - 1.5) * width, vals, width, yerr=[los, his], capsize=3,
               color=METHOD_COLORS[method], label=METHOD_TITLES[method], alpha=0.9)
    ax.set_xticks(xs)
    ax.set_xticklabels([SCENARIO_TITLES[s] for s in scenarios])
    ax.set_ylabel("Медіанна похибка, м (95 % CI)")
    ax.set_title("Рис. 3. Точність локалізації за сценаріями атак")
    ax.legend(ncol=4, fontsize=8)
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 4. Стійкість атрибуції: Pd / FAR критичної зони
# ------------------------------------------------------------------
def fig_attribution(table, save=None):
    scenarios = list(SCENARIO_TITLES)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for ax, (col, ttl) in zip(axes, [("crit_pd", "Pd критичної зони"),
                                     ("crit_far", "FAR критичної зони")]):
        xs = np.arange(len(scenarios))
        width = 0.2
        for j, method in enumerate(["rssi", "ftm", "fusion", "robust"]):
            vals = [table[(table.scenario == sc) & (table.method == method)].iloc[0][col]
                    for sc in scenarios]
            ax.bar(xs + (j - 1.5) * width, vals, width,
                   color=METHOD_COLORS[method], label=METHOD_TITLES[method], alpha=0.9)
        ax.set_xticks(xs)
        ax.set_xticklabels([SCENARIO_TITLES[s] for s in scenarios], rotation=15)
        ax.set_ylim(0, 1.02)
        ax.set_title(ttl)
    axes[0].legend(ncol=2, fontsize=8)
    fig.suptitle("Рис. 4. Зонова атрибуція: виявлення критичної зони під атаками", y=1.03)
    fig.tight_layout()
    _save(fig, save)
    return fig


# ------------------------------------------------------------------
# Рис. 5. Просторовий ефект атаки: зміщення оцінок (evil twin)
# ------------------------------------------------------------------
def fig_attack_shift(exp, scenario="evil_twin", n_show=120, save=None):
    obs = exp.scenarios[scenario]
    naive = localize(obs, exp.radiomap, "fusion").est
    robust = localize(obs, exp.radiomap, "robust").est
    true = obs.pos
    rng_idx = np.linspace(0, len(true) - 1, min(n_show, len(true))).astype(int)

    fig, axes = plt.subplots(1, 2, figsize=(13, 6))
    for ax, est, ttl in [(axes[0], naive, "Наївне злиття"), (axes[1], robust, "Робастне злиття")]:
        _draw_room(ax)
        for i in rng_idx:
            ax.plot([true[i, 0], est[i, 0]], [true[i, 1], est[i, 1]],
                    "-", color="#999999", lw=0.4, alpha=0.6)
        ax.scatter(true[rng_idx, 0], true[rng_idx, 1], s=10, color="#4878CF", label="істина", zorder=4)
        ax.scatter(est[rng_idx, 0], est[rng_idx, 1], s=10, color="#D65F5F", label="оцінка", zorder=4)
        ax.set_title(ttl)
        ax.legend(loc="upper left", fontsize=8)
    fig.suptitle(f"Рис. 5. Ефект атаки «{SCENARIO_TITLES[scenario]}»: наївне vs робастне злиття", y=1.02)
    fig.tight_layout()
    _save(fig, save)
    return fig
