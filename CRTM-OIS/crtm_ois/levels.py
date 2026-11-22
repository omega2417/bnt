"""Five-level scale of the metric model (eq. 1).

Breakpoints y = (0, 0.2, 0.4, 0.7, 0.9, 1); levels C, BA, A, AA, H.
"""
from __future__ import annotations

import numpy as np

BREAKPOINTS: tuple[float, ...] = (0.0, 0.2, 0.4, 0.7, 0.9, 1.0)
LEVEL_CODES: tuple[str, ...] = ("C", "BA", "A", "AA", "H")
LEVEL_NAMES: tuple[str, ...] = (
    "critical", "below average", "average", "above average", "high")
LEVEL_NAMES_UA: tuple[str, ...] = (
    "критичний", "нижче середнього", "середній", "вище середнього", "високий")


def level(s: float, y: tuple[float, ...] = BREAKPOINTS) -> int:
    """Level map lambda(s) -> r in 1..5 (eq. 1).

    Y_r = [y_{r-1}, y_r) for r = 1..4 and Y_5 = [y_4, y_5].
    """
    if not np.isfinite(s):
        raise ValueError(f"score is not finite: {s}")
    for r in range(1, 5):
        if s < y[r]:
            return r
    return 5


def levels(s: np.ndarray, y: tuple[float, ...] = BREAKPOINTS) -> np.ndarray:
    """Vectorised level map for arrays of scores (returns 1..5)."""
    s = np.asarray(s, dtype=float)
    return np.searchsorted(np.asarray(y[1:5]), s, side="right") + 1


def code(r: int) -> str:
    return LEVEL_CODES[r - 1]


def name(r: int, lang: str = "en") -> str:
    return (LEVEL_NAMES_UA if lang == "ua" else LEVEL_NAMES)[r - 1]
