"""Shared figure style (palette and typography of the article's figures)."""
import matplotlib as mpl
from matplotlib import font_manager as fm
import glob

BLUE, ORANGE, PURPLE, AMBER, RED, GREEN = "#2a78d6", "#eb6834", "#6250d6", "#eda100", "#e34948", "#1baf7a"
INK, INK2, GRID, NAVY = "#0b0b0b", "#52514e", "#d9d8d4", "#0b2a56"
PANEL = "#f6f6f4"

def apply():
    for f in glob.glob("/usr/share/texmf/fonts/opentype/public/tex-gyre/texgyrepagella-*.otf"):
        fm.fontManager.addfont(f)
    mpl.rcParams.update({
        "font.family": "TeX Gyre Pagella", "font.size": 9, "axes.titlesize": 9.5, "axes.labelsize": 9.5,
        "xtick.labelsize": 8.5, "ytick.labelsize": 8.5, "legend.fontsize": 8, "axes.edgecolor": INK2,
        "axes.linewidth": 0.7, "xtick.color": INK2, "ytick.color": INK2, "axes.labelcolor": INK,
        "text.color": INK, "axes.spines.top": False, "axes.spines.right": False, "grid.color": GRID,
        "grid.linewidth": 0.5, "savefig.dpi": 300, "figure.dpi": 100, "mathtext.fontset": "custom",
        "mathtext.rm": "TeX Gyre Pagella", "mathtext.it": "TeX Gyre Pagella:italic", "mathtext.bf": "TeX Gyre Pagella:bold",
        "axes.titleweight": "bold", "axes.titlelocation": "left", "legend.frameon": False,
    })
