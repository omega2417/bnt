"""Shared plotting style and colour palette."""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt

# colour-blind-friendly palette (Okabe-Ito derived)
PALETTE = {
    "reference": "#E69F00",   # orange
    "ust_fuse": "#0072B2",    # blue
    "truth": "#111111",
    "radar": "#D55E00",
    "eo_ir": "#009E73",
    "rf_sdr": "#CC79A7",
    "acoustic": "#56B4E9",
    "spoof": "#7f0000",
    "clutter": "#bbbbbb",
    "grid": "#dddddd",
    "accent": "#0072B2",
    "warn": "#D55E00",
    "ok": "#009E73",
}

SENSOR_COLORS = {
    "radar": PALETTE["radar"],
    "eo_ir": PALETTE["eo_ir"],
    "rf_sdr": PALETTE["rf_sdr"],
    "acoustic": PALETTE["acoustic"],
    "spoof": PALETTE["spoof"],
}

MODE_LABELS = {
    "reference": "Reference (radar-only)",
    "ust_fuse": "Full UST-Fuse",
}


def set_style() -> None:
    """Apply a clean, publication-friendly Matplotlib style."""
    mpl.rcParams.update({
        "figure.dpi": 110,
        "savefig.dpi": 130,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#333333",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": PALETTE["grid"],
        "grid.linewidth": 0.6,
        "axes.titlesize": 11,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "legend.fontsize": 8.5,
        "legend.frameon": True,
        "legend.framealpha": 0.9,
        "font.size": 9.5,
        "figure.autolayout": False,
    })


def mode_color(mode: str) -> str:
    return PALETTE.get(mode, "#444444")
