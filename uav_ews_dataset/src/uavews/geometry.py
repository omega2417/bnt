"""Warning-zone geometry: Equations (1) and (2), and the direction rule.

Everything here operates in a local East-North metric frame in metres. Converting
to that frame is deliberately the last step of the controlled-tier transformation
and the first step of every public computation: once positions are expressed
relative to an undisclosed origin, distances and directions remain exact while
the absolute location does not leave the controlled tier.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence, Tuple

import numpy as np


# --------------------------------------------------------------------------- #
# Point-to-polygon distance
# --------------------------------------------------------------------------- #
def _segment_distance(px: np.ndarray, py: np.ndarray,
                      ax: float, ay: float, bx: float, by: float) -> np.ndarray:
    """Distance from points to the segment AB, vectorized over the points."""
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    if denom == 0.0:
        return np.hypot(px - ax, py - ay)
    t = ((px - ax) * vx + (py - ay) * vy) / denom
    t = np.clip(t, 0.0, 1.0)
    return np.hypot(px - (ax + t * vx), py - (ay + t * vy))


def _point_in_polygon(px: np.ndarray, py: np.ndarray,
                      poly: np.ndarray) -> np.ndarray:
    """Even-odd ray casting; returns True for points strictly inside."""
    inside = np.zeros(px.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        ax, ay = poly[i]
        bx, by = poly[(i + 1) % n]
        crosses = (ay > py) != (by > py)
        with np.errstate(divide="ignore", invalid="ignore"):
            x_at = ax + (py - ay) * (bx - ax) / np.where(by - ay == 0, np.nan, by - ay)
        hit = crosses & (px < x_at)
        inside ^= np.nan_to_num(hit, nan=False).astype(bool)
    return inside


@dataclass(frozen=True)
class WarningZone:
    """A generalized warning zone, as a simple polygon in the local frame."""

    name: str
    polygon: np.ndarray  # (n, 2) East-North metres

    @classmethod
    def from_config(cls, cfg) -> "WarningZone":
        return cls(name=cfg["zone"]["name"],
                   polygon=np.asarray(cfg.zone_polygon, dtype=np.float64))

    # -- Equation (1) ------------------------------------------------------- #
    def boundary_distance(self, x: np.ndarray) -> np.ndarray:
        """Equation (1): d(t) = min{ dist(x(t), z) : z in dZ }.

        The minimum is taken over the *boundary* dZ, not over the filled region,
        so d is zero exactly on the boundary and positive both outside and
        inside. Only the horizontal components are used: the zone is a
        ground-referenced area, and mixing altitude into the boundary distance
        would make a high overflight look far away from a zone it is directly
        above.
        """
        pts = np.atleast_2d(np.asarray(x, dtype=np.float64))
        px, py = pts[:, 0], pts[:, 1]
        n = len(self.polygon)
        dists = np.full(px.shape, np.inf)
        for i in range(n):
            ax, ay = self.polygon[i]
            bx, by = self.polygon[(i + 1) % n]
            dists = np.minimum(dists, _segment_distance(px, py, ax, ay, bx, by))
        return dists

    def signed_boundary_distance(self, x: np.ndarray) -> np.ndarray:
        """Negative inside the zone, positive outside.

        Equation (1) is unsigned; the sign is carried as a separate ``inside``
        flag in the tables. The signed form exists only for plotting and for
        detecting the boundary crossing in Equation (2), where an unsigned
        distance would touch zero and bounce back without a sign change.
        """
        pts = np.atleast_2d(np.asarray(x, dtype=np.float64))
        d = self.boundary_distance(pts)
        inside = _point_in_polygon(pts[:, 0], pts[:, 1], self.polygon)
        return np.where(inside, -d, d)


# --------------------------------------------------------------------------- #
# Direction labelling
# --------------------------------------------------------------------------- #
def direction_labels(t_s: np.ndarray, d_m: np.ndarray, delta_t_s: float,
                     epsilon_m: float) -> np.ndarray:
    """Label movement over a stride delta_t using the dead-band epsilon.

    For each t with t + delta_t inside the track:

        d(t + dt) - d(t) < -eps   -> approaching
        d(t + dt) - d(t) >  +eps  -> receding
        |d(t + dt) - d(t)| <= eps -> lateral_stationary

    Samples whose partner falls outside the track are ``uncertain`` rather than
    extrapolated. The dead-band is what keeps positional noise from producing a
    direction: with eps set to k*sqrt(2)*sigma_h, a stationary target is labelled
    ``approaching`` only when the noise exceeds a k-sigma excursion.
    """
    t_s = np.asarray(t_s, dtype=np.float64)
    d_m = np.asarray(d_m, dtype=np.float64)
    out = np.full(t_s.shape, "uncertain", dtype=object)
    partner = np.searchsorted(t_s, t_s + delta_t_s)
    for i in range(t_s.size):
        j = partner[i]
        if j >= t_s.size:
            continue
        # Accept the partner sample only if it really is ~delta_t away.
        if abs((t_s[j] - t_s[i]) - delta_t_s) > 0.5 * delta_t_s:
            continue
        diff = d_m[j] - d_m[i]
        if diff < -epsilon_m:
            out[i] = "approaching"
        elif diff > epsilon_m:
            out[i] = "receding"
        else:
            out[i] = "lateral_stationary"
    return out


# --------------------------------------------------------------------------- #
# Equation (2)
# --------------------------------------------------------------------------- #
def crossing_time(t_s: np.ndarray, signed_d_m: np.ndarray) -> float | None:
    """First time the signed distance changes from positive to non-positive.

    The crossing is refined by linear interpolation between the bracketing
    samples, which removes the 1/rate quantization: at 5 Hz ground truth the
    unrefined crossing is biased by up to 200 ms, and the release reports
    warning time in seconds to one decimal.

    Returns ``None`` when the track never enters the zone; such an event is
    marked censored, never extrapolated.
    """
    t_s = np.asarray(t_s, dtype=np.float64)
    d = np.asarray(signed_d_m, dtype=np.float64)
    for i in range(1, t_s.size):
        if d[i - 1] > 0.0 >= d[i]:
            span = d[i - 1] - d[i]
            frac = d[i - 1] / span if span > 0 else 0.0
            return float(t_s[i - 1] + frac * (t_s[i] - t_s[i - 1]))
    return None


def warning_time(t_s: np.ndarray, t_cross_s: float | None) -> np.ndarray:
    """Equation (2): T(t) = t_cross - t.

    When there is no verified crossing the whole track is censored and returned
    as NaN; the caller records ``time_to_zone = censored`` rather than a number.
    """
    t_s = np.asarray(t_s, dtype=np.float64)
    if t_cross_s is None:
        return np.full(t_s.shape, np.nan)
    return t_cross_s - t_s


def closest_point_of_approach(t_s: np.ndarray, d_m: np.ndarray) -> Tuple[float, float]:
    """Time and value of the minimum boundary distance along a track."""
    i = int(np.argmin(np.asarray(d_m)))
    return float(np.asarray(t_s)[i]), float(np.asarray(d_m)[i])


def radial_speed(t_s: np.ndarray, d_m: np.ndarray) -> np.ndarray:
    """dd/dt by central differences: the closing rate towards the boundary."""
    return np.gradient(np.asarray(d_m, dtype=np.float64),
                       np.asarray(t_s, dtype=np.float64))
