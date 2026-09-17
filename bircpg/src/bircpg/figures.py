"""Figure 3 of the manuscript, regenerated from the code rather than redrawn.

Panel (a) shows welfare ``W(a)``, potential ``Phi(a)`` and the unilateral Nash
gap for the four active profiles of Section 6.  Panel (b) traces the Equation
(12) stationary law across temperatures: as ``tau`` decreases the mass
concentrates on the potential maximiser ``(A, B)``, whereas at larger ``tau``
every profile -- including the two non-equilibria -- retains appreciable
probability.

Both panels are an exact arithmetic illustration, not a simulation and not a
measurement.  Every plotted number comes from :mod:`bircpg.section6`, and
:func:`write_figure_data` writes the same numbers to CSV so the figure always
has a table view beside it.

``matplotlib`` is an optional dependency; importing this module without it
raises a clear error instead of failing at draw time.
"""

from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from .section6 import format_table2, stationary_by_temperature, table2

__all__ = ["PALETTE", "figure3", "write_figure_data", "default_temperatures"]

#: Categorical slots 1-4 in fixed order (blue, orange, aqua, yellow), light and
#: dark steps.  Hues are assigned by series identity and never cycled or
#: reassigned by rank.  The aqua and yellow slots sit below 3:1 contrast on the
#: light surface, so both panels carry visible direct labels.
PALETTE: Dict[str, Dict[str, object]] = {
    "light": {
        "surface": "#fcfcfb",
        "text": "#0b0b0b",
        "muted": "#52514e",
        "grid": "#e3e2dd",
        "series": ("#2a78d6", "#eb6834", "#1baf7a", "#eda100"),
    },
    "dark": {
        "surface": "#1a1a19",
        "text": "#ffffff",
        "muted": "#c3c2b7",
        "grid": "#333330",
        "series": ("#3987e5", "#d95926", "#199e70", "#c98500"),
    },
}


def default_temperatures(count: int = 60) -> List[float]:
    """Logarithmically spaced temperatures spanning Table 3's ``tau`` levels."""
    lo, hi = math.log10(0.02), math.log10(5.0)
    return [10 ** (lo + (hi - lo) * k / (count - 1)) for k in range(count)]


def _require_matplotlib():
    try:
        import matplotlib
        import matplotlib.pyplot as plt
    except ImportError as exc:  # pragma: no cover - environment dependent
        raise ImportError(
            "figure generation needs matplotlib; install it with "
            "`pip install matplotlib` or use bircpg.section6 for the numbers alone"
        ) from exc
    return matplotlib, plt


def write_figure_data(directory: str | Path) -> Dict[str, Path]:
    """Write the table view of both panels: one CSV each, plus Table 2 as text."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    rows = table2()
    panel_a = directory / "figure3a_data.csv"
    with panel_a.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["profile", "u_1", "u_2", "welfare", "potential", "nash_gap", "pure_nash"])
        for r in rows:
            writer.writerow(
                [
                    r["profile"],
                    r["u_1"],
                    r["u_2"],
                    r["welfare"],
                    r["potential"],
                    r["nash_gap"],
                    "yes" if r["is_pne"] else "no",
                ]
            )
    taus = default_temperatures()
    series = stationary_by_temperature(taus)
    panel_b = directory / "figure3b_data.csv"
    with panel_b.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["tau"] + list(series.keys()))
        for k, tau in enumerate(taus):
            writer.writerow([f"{tau:.6f}"] + [f"{series[name][k]:.9f}" for name in series])
    table_txt = directory / "table2.txt"
    table_txt.write_text(format_table2() + "\n")
    return {"figure3a_data": panel_a, "figure3b_data": panel_b, "table2": table_txt}


def figure3(
    path: Optional[str | Path] = None,
    theme: str = "light",
    taus: Optional[Sequence[float]] = None,
    dpi: int = 300,
):
    """Draw Figure 3 (panels a and b).  Returns the matplotlib figure.

    Parameters
    ----------
    path:
        When given, the figure is saved there (the extension chooses the format;
        PDF or SVG for print).
    theme:
        ``"light"`` (default, print) or ``"dark"``.  The dark steps are selected
        for the dark surface, not an automatic inversion of the light ones.
    """
    _, plt = _require_matplotlib()
    if theme not in PALETTE:
        raise ValueError(f"theme must be one of {sorted(PALETTE)}")
    pal = PALETTE[theme]
    series_colors: Tuple[str, ...] = pal["series"]  # type: ignore[assignment]
    text, muted, grid, surface = pal["text"], pal["muted"], pal["grid"], pal["surface"]

    taus = list(taus) if taus is not None else default_temperatures()
    rows = table2()
    labels = [r["profile"] for r in rows]
    measures = (
        ("Welfare $W(a)$", [float(r["welfare"]) for r in rows], series_colors[0]),
        ("Potential $\\Phi(a)$", [float(r["potential"]) for r in rows], series_colors[1]),
        ("Nash gap", [float(r["nash_gap"]) for r in rows], series_colors[2]),
    )

    fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(11.0, 4.3), dpi=dpi)
    fig.patch.set_facecolor(surface)

    # ---------------- panel (a): magnitude comparison, grouped bars ----------
    ax_a.set_facecolor(surface)
    width = 0.26
    gap = 0.02  # 2px-equivalent surface gap between adjacent bars
    positions = range(len(labels))
    for k, (name, values, color) in enumerate(measures):
        offset = (k - 1) * (width + gap)
        xs = [p + offset for p in positions]
        ax_a.bar(xs, values, width=width, color=color, label=name, linewidth=0)
        for x, v in zip(xs, values):
            ax_a.annotate(
                f"{v:g}",
                (x, v),
                textcoords="offset points",
                xytext=(0, 3),
                ha="center",
                fontsize=8,
                color=text,
            )
    ax_a.set_xticks(list(positions))
    # Equilibrium status is carried by the tick label, not by colour alone.
    ax_a.set_xticklabels(
        [f"{r['profile']}\npure NE" if r["is_pne"] else r["profile"] for r in rows],
        color=text,
    )
    ax_a.set_title("(a) Exact enumeration of the four active profiles", color=text, fontsize=10, loc="left")
    ax_a.set_ylabel("utility units (hypothetical)", color=muted, fontsize=9)
    ax_a.set_ylim(0, 14)
    ax_a.tick_params(colors=muted, labelsize=9)
    ax_a.spines["top"].set_visible(False)
    ax_a.spines["right"].set_visible(False)
    for spine in ("left", "bottom"):
        ax_a.spines[spine].set_color(grid)
    ax_a.legend(frameon=False, fontsize=8, labelcolor=text, ncol=3, loc="upper left")

    # ---------------- panel (b): stationary law across temperatures ---------
    ax_b.set_facecolor(surface)
    series = stationary_by_temperature(taus)
    pne = {r["profile"] for r in rows if r["is_pne"]}
    end_labels = []
    for k, (name, probs) in enumerate(series.items()):
        color = series_colors[k % len(series_colors)]
        ax_b.plot(
            taus,
            probs,
            color=color,
            linewidth=2.0,
            label=f"{name}{' (NE)' if name in pne else ''}",
        )
        end_labels.append((probs[-1], name))
    # Push overlapping end labels apart so no two collide.
    end_labels.sort()
    minimum_spacing = 0.055
    placed: List[float] = []
    for value, _ in end_labels:
        y = value if not placed else max(value, placed[-1] + minimum_spacing)
        placed.append(y)
    for (value, name), y in zip(end_labels, placed):
        ax_b.annotate(
            name,
            (taus[-1], value),
            xytext=(taus[-1] * 1.25, y),
            fontsize=8,
            color=text,
            va="center",
            arrowprops=dict(arrowstyle="-", color=grid, linewidth=0.6, shrinkA=0, shrinkB=2),
        )
    ax_b.set_xscale("log")
    ax_b.set_xlim(min(taus), max(taus) * 2.6)
    ax_b.set_ylim(0, 1.02)
    ax_b.set_xlabel(r"temperature $\tau$ (behavioural, log scale)", color=muted, fontsize=9)
    ax_b.set_ylabel(r"stationary probability $\pi_\tau(a)$", color=muted, fontsize=9)
    ax_b.set_title("(b) Equation (12) with uniform references", color=text, fontsize=10, loc="left")
    ax_b.tick_params(colors=muted, labelsize=9)
    ax_b.grid(axis="y", color=grid, linewidth=0.6)
    ax_b.set_axisbelow(True)
    ax_b.spines["top"].set_visible(False)
    ax_b.spines["right"].set_visible(False)
    for spine in ("left", "bottom"):
        ax_b.spines[spine].set_color(grid)
    ax_b.legend(frameon=False, fontsize=8, labelcolor=text, loc="center left")

    fig.suptitle(
        "Constructed two-agent example: equilibrium is not collective optimality",
        color=text,
        fontsize=11,
        x=0.01,
        ha="left",
    )
    fig.text(
        0.01,
        0.015,
        "Exact arithmetic illustration, not a simulation or a measurement. "
        r"$V_A=8$, $V_B=6$; $d_1(A)=1$, $d_1(B)=2$, $d_2(A)=2$, $d_2(B)=1$.",
        color=muted,
        fontsize=8,
    )
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    if path is not None:
        fig.savefig(path, facecolor=surface, dpi=dpi, bbox_inches="tight")
    return fig
