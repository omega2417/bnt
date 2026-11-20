"""Visual system: palette, provenance colours, typography, text helpers, export."""
from __future__ import annotations

import os

import matplotlib

matplotlib.use("Agg")  # headless: works on servers, CI and iPad apps alike
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

# ------------------------------------------------------------------ palette
INK = "#1B1B1F"
MUTED = "#5F5E5A"
FAINT = "#9A988F"
RULE = "#D3D1C7"
PANEL = "#F1F0EC"
PAPER = "#FFFFFF"

# Provenance tags keep the same colour in every figure.
PROV = {
    "L": "#2A6FDB",   # legal act
    "EC": "#E8613C",  # European Commission
    "A": "#14A37A",   # authors' assessment
    "P": "#4A4A4A",   # authors' proposal
}
PROV_LABEL = {
    "L": "legal act",
    "EC": "Commission",
    "A": "authors' assessment",
    "P": "authors' proposal",
}

# Criterion states (Figure 4): sequential blue for "met" family, neutral for
# partly, red for not met; n/a is hatched, never coloured.
STATE = {
    "met":         ("#2A6FDB", "#FFFFFF", "Met"),
    "largely_met": ("#82B1F0", INK, "Largely met"),
    "met_in_form": ("#BFD6F6", INK, "Met in form"),
    "met_exposed": ("#BFD6F6", INK, "Met, but exposed"),
    "partly_met":  ("#EEEDE9", INK, "Partly met"),
    "not_met":     ("#E04848", "#FFFFFF", "Not met"),
    "na":          ("#FFFFFF", FAINT, "n/a"),
}
RATING = {
    "aligned":        ("#2A6FDB", "Aligned"),
    "partly_aligned": ("#F2A900", "Partly aligned"),
    "misaligned":     ("#E04848", "Misaligned by\nderogation"),
}

# Mechanism types (Figures 6-7) and alluvial problem colours.
MECH = {
    "institutional": "#2A6FDB",
    "legal": "#E8613C",
    "financial": "#14A37A",
    "procedural": "#E9A100",
}
SERIES = ["#2A6FDB", "#E8613C", "#14A37A", "#E9A100", "#7B5CD6", "#C0447E"]

LANE = {
    "eu": "#6A4FD8",
    "general": "#2A6FDB",
    "derogation": "#E04848",
    "recovery": "#14A37A",
}

FONT = "DejaVu Sans"  # ships with matplotlib everywhere -> identical layout on every device


def setup():
    plt.rcdefaults()
    rc = {
        "font.family": "sans-serif",
        "font.sans-serif": [FONT],
        "font.size": 9,
        "text.color": INK,
        "axes.edgecolor": RULE,
        "axes.labelcolor": INK,
        "xtick.color": MUTED,
        "ytick.color": MUTED,
        "figure.facecolor": PAPER,
        "savefig.facecolor": PAPER,
        "hatch.color": "#B9B7AE",
        "hatch.linewidth": 0.8,
        "pdf.fonttype": 42,        # embed TrueType fonts
        "svg.fonttype": "path",    # text as outlines: no font needed to view
        "svg.hashsalt": "lexviz",  # deterministic SVG ids
        "path.simplify": False,
    }
    for k, v in rc.items():  # one by one: older matplotlib (iPad apps) may lack some keys
        try:
            plt.rcParams[k] = v
        except (KeyError, ValueError):
            pass


def new_figure(w, h):
    setup()
    fig = plt.figure(figsize=(w, h))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, w)
    ax.set_ylim(h, 0)  # y grows downwards: easier to lay out schematics
    ax.axis("off")
    return fig, ax


# ------------------------------------------------------------- measurement
_PT = 1.0 / 72.0


def _renderer(fig):
    try:
        return fig.canvas.get_renderer()
    except AttributeError:  # very old matplotlib
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        return FigureCanvasAgg(fig).get_renderer()


def text_size(fig, s, size=9, weight="normal", style="normal"):
    """Width and height of a text in inches (exact, via the renderer)."""
    t = fig.text(0, 0, s, fontsize=size, fontweight=weight, fontstyle=style)
    bb = t.get_window_extent(renderer=_renderer(fig))
    t.remove()
    return bb.width / fig.dpi, bb.height / fig.dpi


def wrap(fig, s, width_in, size=9, weight="normal"):
    """Greedy word wrap to a width in inches; keeps explicit newlines."""
    out = []
    for para in str(s).split("\n"):
        line = ""
        for word in para.split():
            trial = word if not line else line + " " + word
            if line and text_size(fig, trial, size, weight)[0] > width_in:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return "\n".join(out)


def line_height(size):
    return size * 1.25 * _PT


# ------------------------------------------------------------------ drawing
def box(ax, x, y, w, h, fc=PAPER, ec=RULE, lw=1.2, r=0.06, ls="-", hatch=None, z=2):
    p = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=%g" % r,
                       fc=fc, ec=ec, lw=lw, ls=ls, hatch=hatch, zorder=z)
    ax.add_patch(p)
    return p


def tag_chip(ax, x, y, tag, size=8, h=0.2, z=5):
    """Filled provenance chip centred on (x, y)."""
    w = 0.16 if len(tag) == 1 else 0.24
    box(ax, x - w / 2, y - h / 2, w, h, fc=PROV[tag], ec=PROV[tag], lw=0, r=0.03, z=z)
    ax.text(x, y, tag, ha="center", va="center", color="white", fontsize=size,
            fontweight="bold", zorder=z + 1)
    return w


def arrow(ax, p0, p1, color=MUTED, lw=1.4, head=True, ls="-", z=3, mutation=10):
    ax.annotate("", xy=p1, xytext=p0, zorder=z,
                arrowprops=dict(arrowstyle="-|>" if head else "-", color=color, lw=lw,
                                ls=ls, shrinkA=0, shrinkB=0, mutation_scale=mutation))


def polyline(ax, pts, color=MUTED, lw=1.4, ls="-", head=True, z=3):
    """Orthogonal or free polyline; an arrow head on the last segment if ``head``."""
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    if head:
        ax.plot(xs[:-1], ys[:-1], color=color, lw=lw, ls=ls, zorder=z, solid_joinstyle="miter")
        arrow(ax, pts[-2], pts[-1], color=color, lw=lw, ls=ls, z=z)
    else:
        ax.plot(xs, ys, color=color, lw=lw, ls=ls, zorder=z, solid_joinstyle="miter")


def tag_label(tag):
    return "[%s]" % tag


# ------------------------------------------------------------------- export
FORMATS = ("png", "pdf", "svg")


def _png_to_rgb(path, dpi):
    """MDPI asks for RGB images: drop the alpha channel when Pillow is available."""
    try:
        from PIL import Image
    except ImportError:
        return
    im = Image.open(path)
    if im.mode != "RGB":
        bg = Image.new("RGB", im.size, (255, 255, 255))
        bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
        bg.save(path, dpi=(dpi, dpi), optimize=True)


def save(fig, outdir, name, dpi=600, formats=FORMATS):
    """Save a figure for the publisher; returns the list of written paths."""
    os.makedirs(outdir, exist_ok=True)
    paths = []
    for fmt in formats:
        p = os.path.join(outdir, "%s.%s" % (name, fmt))
        kw = {}
        if fmt == "png":
            kw["dpi"] = dpi
            kw["metadata"] = {"Software": "LexViz"}
        elif fmt == "pdf":
            kw["metadata"] = {"Creator": "LexViz", "Producer": "LexViz", "CreationDate": None}
        elif fmt == "svg":
            kw["metadata"] = {"Creator": "LexViz", "Date": None}
        try:
            fig.savefig(p, format=fmt, **kw)
        except TypeError:  # very old matplotlib without metadata support
            kw.pop("metadata", None)
            fig.savefig(p, format=fmt, **kw)
        if fmt == "png":
            _png_to_rgb(p, dpi)
        paths.append(p)
    plt.close(fig)
    return paths
