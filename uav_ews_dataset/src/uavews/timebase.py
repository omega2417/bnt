"""Time representation, clock modelling, and Equation (3).

Interchange files carry RFC 3339 strings with the Z designator. Analytic tables
carry signed 64-bit UTC nanoseconds, because floating-point seconds lose
sub-millisecond resolution once the epoch offset is large: a float64 holding
seconds since 1970 has ~200 ns of quantum in 2025, which is the same order as
the PTP offsets the release is supposed to report.

The module never overwrites a native source timestamp. A corrected time is
always a new column derived from (native time, estimated offset, offset
uncertainty, method), so that a later recalibration can be replayed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Sequence, Tuple

import numpy as np

NS = 1_000_000_000
EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Conversions
# --------------------------------------------------------------------------- #
def rfc3339_to_ns(value: str) -> int:
    """Parse an RFC 3339 UTC timestamp into int64 nanoseconds."""
    text = value.strip()
    if not text.endswith(("Z", "z")):
        raise ValueError(f"interchange timestamps must end with Z: {value!r}")
    text = text[:-1]
    if "." in text:
        head, frac = text.split(".", 1)
        frac = (frac + "000000000")[:9]
    else:
        head, frac = text, "000000000"
    dt = datetime.strptime(head, "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    return int((dt - EPOCH).total_seconds()) * NS + int(frac)


def ns_to_rfc3339(value: int, digits: int = 3) -> str:
    """Render int64 nanoseconds as an RFC 3339 UTC timestamp."""
    value = int(value)
    sec, rem = divmod(value, NS)
    dt = datetime.fromtimestamp(sec, tz=timezone.utc)
    if digits == 0:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    frac = f"{rem:09d}"[:digits]
    return dt.strftime("%Y-%m-%dT%H:%M:%S") + "." + frac + "Z"


def seconds_to_ns(seconds: float) -> int:
    return int(round(float(seconds) * NS))


def ns_to_seconds(value) -> float | np.ndarray:
    return np.asarray(value, dtype=np.float64) / NS


# --------------------------------------------------------------------------- #
# Clock model
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ClockProfile:
    """Offset model for one source class.

    ``method`` is the synchronization mechanism declared by the source, and
    ``sigma_s`` the 1-sigma uncertainty of the estimated offset to the site
    reference. External public feeds are declared asynchronous and receive a
    deliberately wide sigma; nothing downstream is allowed to treat them as if
    they were disciplined clocks.
    """

    source_class: str
    method: str
    sigma_s: float

    def half_width_ns(self, k: float) -> int:
        return seconds_to_ns(k * self.sigma_s)


def corrected_ns(native_ns, offset_ns) -> np.ndarray:
    """Apply an estimated offset without discarding the native value."""
    return np.asarray(native_ns, dtype=np.int64) - np.asarray(offset_ns, dtype=np.int64)


def sync_error_ns(t_m_ns, t_r_ns) -> np.ndarray:
    """Equation (3): absolute synchronization error dt = |t_m - t_r|."""
    return np.abs(
        np.asarray(t_m_ns, dtype=np.int64) - np.asarray(t_r_ns, dtype=np.int64)
    )


def sync_summary(errors_ns: Sequence[int]) -> dict:
    """Median / p95 / max of Eq. (3), in milliseconds, as Table 7 requires."""
    arr = np.asarray(list(errors_ns), dtype=np.float64)
    if arr.size == 0:
        return {"n": 0, "median_ms": None, "p95_ms": None, "max_ms": None}
    ms = arr / 1e6
    return {
        "n": int(arr.size),
        "median_ms": float(np.median(ms)),
        "p95_ms": float(np.percentile(ms, 95)),
        "max_ms": float(np.max(ms)),
        "mean_ms": float(np.mean(ms)),
    }


# --------------------------------------------------------------------------- #
# Interval algebra
# --------------------------------------------------------------------------- #
def expand(start_ns: int, end_ns: int, half_width_ns: int) -> Tuple[int, int]:
    """Uncertainty-expanded interval [t0 - h, t1 + h]."""
    return int(start_ns) - int(half_width_ns), int(end_ns) + int(half_width_ns)


def overlap_ns(a: Tuple[int, int], b: Tuple[int, int]) -> int:
    """Length of the intersection of two intervals; 0 when they are disjoint."""
    lo = max(a[0], b[0])
    hi = min(a[1], b[1])
    return max(0, hi - lo)


def iou(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    """Temporal intersection-over-union, used for boundary agreement."""
    inter = overlap_ns(a, b)
    union = (max(a[1], b[1]) - min(a[0], b[0]))
    return float(inter) / float(union) if union > 0 else 0.0


def tile_windows(t_start_ns: int, t_end_ns: int, span_s: float,
                 hop_s: float) -> list[Tuple[int, int]]:
    """Tile an event interval with overlapping analysis windows.

    The last window is anchored to the event end rather than truncated, so that
    the final seconds before zone entry - the operationally interesting part -
    are covered at full span.
    """
    span = seconds_to_ns(span_s)
    hop = seconds_to_ns(hop_s)
    if t_end_ns - t_start_ns <= span:
        return [(int(t_start_ns), int(t_end_ns))]
    out: list[Tuple[int, int]] = []
    cur = int(t_start_ns)
    while cur + span <= t_end_ns:
        out.append((cur, cur + span))
        cur += hop
    if out[-1][1] < t_end_ns:
        out.append((int(t_end_ns) - span, int(t_end_ns)))
    return out
