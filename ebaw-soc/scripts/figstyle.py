"""Shared figure style: TeX Gyre Pagella (Palatino-compatible, matches the MDPI body
font), bold text, thick strokes, Okabe-Ito colour-blind-safe palette, decimal points."""
import os

import matplotlib as mpl
import matplotlib.font_manager as fm

# TeX Gyre Pagella is searched in the usual TeX Live / Debian / Homebrew locations; if it is not
# installed, matplotlib falls back to its default font (the numbers are unaffected).
_PAGELLA_DIRS = ("/usr/share/texmf/fonts/opentype/public/tex-gyre/",
                 "/usr/share/fonts/opentype/tex-gyre/",
                 "/usr/share/texlive/texmf-dist/fonts/opentype/public/tex-gyre/",
                 "/usr/local/share/fonts/", os.path.expanduser("~/Library/Fonts/"),
                 os.path.expanduser("~/.fonts/"))
for _d in _PAGELLA_DIRS:
    for _f in ("regular", "bold", "italic", "bolditalic"):
        _p = os.path.join(_d, f"texgyrepagella-{_f}.otf")
        if os.path.exists(_p):
            fm.fontManager.addfont(_p)

OI = dict(blue="#0072B2", orange="#E69F00", green="#009E73", sky="#56B4E9", verm="#D55E00",
          purple="#CC79A7", yellow="#F0E442", black="#000000")
INK, MUTED, GRID, FAINT = "#1a1a1a", "#555555", "#d4d4d4", "#efefef"

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGDIR = os.path.join(ROOT, "figures")
RESDIR = os.path.join(ROOT, "results")
os.makedirs(FIGDIR, exist_ok=True)


def setup():
    mpl.rcParams.update({
        "font.family": "TeX Gyre Pagella", "font.weight": "bold", "font.size": 14,
        "axes.labelweight": "bold", "axes.titleweight": "bold", "axes.titlesize": 15.5, "axes.labelsize": 15,
        "xtick.labelsize": 13.5, "ytick.labelsize": 13.5, "legend.fontsize": 13.5,
        "axes.linewidth": 1.6, "lines.linewidth": 2.6, "xtick.major.width": 1.5, "ytick.major.width": 1.5,
        "xtick.major.size": 5, "ytick.major.size": 5,
        "axes.edgecolor": INK, "text.color": INK, "axes.labelcolor": INK, "xtick.color": INK, "ytick.color": INK,
        "mathtext.fontset": "custom", "mathtext.rm": "TeX Gyre Pagella", "mathtext.it": "TeX Gyre Pagella:italic",
        "mathtext.bf": "TeX Gyre Pagella:bold", "mathtext.default": "it",
        "axes.grid": False, "legend.frameon": False, "axes.spines.top": False, "axes.spines.right": False,
        "pdf.fonttype": 42, "svg.fonttype": "none", "hatch.linewidth": 1.4,
    })


def save(fig, name, dpi=400):
    path = os.path.join(FIGDIR, f"{name}.png")
    fig.savefig(path, dpi=dpi, bbox_inches="tight", pad_inches=0.08, facecolor="white")
    return path
