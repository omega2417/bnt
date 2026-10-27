"""Five-level linguistic scale (Definition 5).

Score breakpoints y = (0, 0.2, 0.4, 0.7, 0.9, 1) define the bands
Y_r = [y_{r-1}, y_r) for r = 1..4 and Y_5 = [y_4, y_5], named
critical, below average, average, above average and high.
"""
from __future__ import annotations

import numpy as np

#: score breakpoints y_0 .. y_5
Y = np.array([0.0, 0.2, 0.4, 0.7, 0.9, 1.0])

#: level names, index r - 1 for r = 1..5
LEVEL_NAMES = ("critical", "below average", "average", "above average", "high")

#: abbreviations used in the article tables
LEVEL_ABBR = ("C", "BA", "A", "AA", "H")


def level(s):
    """Level map lambda: [0, 1] -> {1, ..., 5} (vectorised).

    Returns an int (scalar input) or an int array. NaN maps to 0
    ("not computed").
    """
    s_arr = np.asarray(s, dtype=float)
    r = np.searchsorted(Y[1:5], s_arr, side="right") + 1
    r = np.where(np.isnan(s_arr), 0, r)
    if r.ndim == 0:
        return int(r)
    return r.astype(int)


def level_abbr(s) -> str:
    """Abbreviated level name of a single score, '—' for NaN."""
    r = level(s)
    return "—" if r == 0 else LEVEL_ABBR[r - 1]


def level_name(s) -> str:
    """Full level name of a single score."""
    r = level(s)
    return "not computed" if r == 0 else LEVEL_NAMES[r - 1]


def band(r: int) -> tuple[float, float]:
    """Score band (y_{r-1}, y_r) of level r."""
    if not 1 <= r <= 5:
        raise ValueError("level must be in 1..5")
    return float(Y[r - 1]), float(Y[r])
