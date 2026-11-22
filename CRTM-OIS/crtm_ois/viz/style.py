"""Shared visual style: chrome, level colors (diverging red-gray-blue), series colors."""
from __future__ import annotations

import matplotlib.pyplot as plt

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"

# Categorical slots (fixed order, never cycled)
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
GOAL_COLORS = {"ANT": SERIES[0], "WITH": SERIES[1], "REC": SERIES[2], "AD": SERIES[3]}

# Five ordered levels: diverging pair red <-> blue with a neutral gray midpoint
LEVEL_COLORS = {"C": "#b8322f", "BA": "#ec8f88", "A": "#b9b8b0", "AA": "#86b6ef", "H": "#1c5cab"}
LEVEL_TEXT = {"C": "#ffffff", "BA": INK, "A": INK, "AA": INK, "H": "#ffffff"}
STATUS = {"good": "#0ca30c", "warning": "#fab219", "serious": "#ec835a", "critical": "#d03b3b", "info": "#2a78d6"}


def apply():
    plt.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.edgecolor": AXIS, "axes.labelcolor": INK2, "axes.titlecolor": INK,
        "axes.titlesize": 11, "axes.titleweight": "bold", "axes.titlelocation": "left",
        "axes.labelsize": 9.5, "xtick.color": MUTED, "ytick.color": MUTED,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "axes.grid": True,
        "grid.color": GRID, "grid.linewidth": 0.6, "axes.axisbelow": True,
        "axes.spines.top": False, "axes.spines.right": False,
        "font.family": "DejaVu Sans", "font.size": 9, "legend.frameon": False,
        "legend.fontsize": 8.5, "lines.linewidth": 2.0, "figure.dpi": 110, "savefig.dpi": 200,
        "savefig.bbox": "tight",
    })


def level_bands(ax, orient: str = "h", alpha: float = 0.13, labels: bool = True, y=(0, .2, .4, .7, .9, 1.0)):
    """Background bands of the five levels."""
    codes = list(LEVEL_COLORS)
    for i, c in enumerate(codes):
        if orient == "h":
            ax.axhspan(y[i], y[i + 1], color=LEVEL_COLORS[c], alpha=alpha, lw=0, zorder=0)
            if labels:
                ax.text(1.005, (y[i] + y[i + 1]) / 2, c, transform=ax.get_yaxis_transform(),
                        va="center", ha="left", fontsize=8, color=INK2)
        else:
            ax.axvspan(y[i], y[i + 1], color=LEVEL_COLORS[c], alpha=alpha, lw=0, zorder=0)
            if labels:
                ax.text((y[i] + y[i + 1]) / 2, 1.01, c, transform=ax.get_xaxis_transform(),
                        va="bottom", ha="center", fontsize=8, color=INK2)


def level_color(score: float) -> str:
    from ..levels import code, level
    return LEVEL_COLORS[code(level(score))]


apply()
