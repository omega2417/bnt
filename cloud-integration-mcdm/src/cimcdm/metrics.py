"""Quality indicators: hypervolume, IGD+, spacing and exact-front coverage.

All indicators assume minimization. Hypervolume is *larger is better*; IGD+ and
spacing are *smaller is better*.
"""

from __future__ import annotations

import numpy as np


def hypervolume(F: np.ndarray, reference: tuple[float, ...] | np.ndarray) -> float:
    """Hypervolume dominated by ``F`` and bounded by ``reference``.

    Exact for two and three objectives via dimension sweeping, which is all this
    benchmark needs. Points that do not strictly dominate the reference point
    contribute nothing and are discarded first.
    """
    F = np.atleast_2d(np.asarray(F, dtype=float))
    ref = np.asarray(reference, dtype=float)
    if F.size == 0:
        return 0.0
    F = F[np.all(F < ref, axis=1)]
    if len(F) == 0:
        return 0.0

    if F.shape[1] == 2:
        return _hv2(F, ref)
    if F.shape[1] == 3:
        return _hv3(F, ref)
    raise NotImplementedError("Exact sweeping is implemented for 2 and 3 objectives")


def _hv2(F: np.ndarray, ref: np.ndarray) -> float:
    """Area dominated in two dimensions, by sweeping along the first objective."""
    ordered = F[np.argsort(F[:, 0], kind="stable")]
    area, best_y = 0.0, ref[1]
    for x, y in ordered:
        if y < best_y:
            area += (ref[0] - x) * (best_y - y)
            best_y = y
    return float(area)


def _hv3(F: np.ndarray, ref: np.ndarray) -> float:
    """Volume dominated in three dimensions.

    Sweeps along the third objective and accumulates the 2-D dominated area of
    every prefix of points, weighted by the height of the slab it spans.
    """
    ordered = F[np.argsort(F[:, 2], kind="stable")]
    z = np.append(ordered[:, 2], ref[2])
    volume = 0.0
    for i in range(len(ordered)):
        height = z[i + 1] - z[i]
        if height > 0.0:
            volume += _hv2(ordered[: i + 1, :2], ref) * height
    return float(volume)


def igd_plus(F: np.ndarray, reference_front: np.ndarray) -> float:
    """Modified inverted generational distance IGD+ (Ishibuchi et al., 2015).

    For every reference point, only the objective-wise *shortfall* of the
    approximation counts, which makes the indicator weakly Pareto compliant.
    """
    F = np.atleast_2d(np.asarray(F, dtype=float))
    R = np.atleast_2d(np.asarray(reference_front, dtype=float))
    if F.size == 0:
        return float("inf")
    shortfall = np.maximum(F[None, :, :] - R[:, None, :], 0.0)
    distances = np.sqrt((shortfall ** 2).sum(axis=2))
    return float(distances.min(axis=1).mean())


def spacing(F: np.ndarray) -> float:
    """Spacing: sample standard deviation of the nearest-neighbour distances.

    Distances are Euclidean, and the sum of squared deviations is divided by
    ``N - 1``. This is the convention the article uses: it is what reproduces the
    published WSM spacing of 0.016338 exactly on the (deterministic, and
    otherwise exactly reproduced) 29-point weighted-sum front. Schott's original
    formulation uses the Manhattan distance instead, which on that same front
    gives 0.022544 - so the two conventions are not interchangeable when
    comparing against the published tables.
    """
    F = np.atleast_2d(np.asarray(F, dtype=float))
    if len(F) < 2:
        return 0.0
    difference = F[:, None, :] - F[None, :, :]
    distance = np.sqrt((difference ** 2).sum(axis=2))
    np.fill_diagonal(distance, np.inf)
    nearest = distance.min(axis=1)
    return float(np.sqrt(((nearest.mean() - nearest) ** 2).sum() / (len(nearest) - 1)))


def exact_front_coverage(
    F: np.ndarray, exact_front: np.ndarray, decimals: int = 10
) -> float:
    """Fraction of exact-front objective vectors reproduced by ``F``.

    Vectors are matched after rounding to ``decimals`` decimal places, as in the
    article. The result is in [0, 1].
    """
    F = np.atleast_2d(np.asarray(F, dtype=float))
    exact = np.atleast_2d(np.asarray(exact_front, dtype=float))
    if exact.size == 0:
        return 0.0
    found = {tuple(row) for row in np.round(F, decimals)}
    hits = sum(tuple(row) in found for row in np.round(exact, decimals))
    return hits / len(exact)


def evaluate_front(
    F: np.ndarray,
    exact_front: np.ndarray,
    reference_point: tuple[float, ...] | np.ndarray,
) -> dict[str, float]:
    """All four indicators for one approximation front."""
    return {
        "hypervolume": hypervolume(F, reference_point),
        "igd_plus": igd_plus(F, exact_front),
        "spacing": spacing(F),
        "coverage": exact_front_coverage(F, exact_front),
        "front_size": float(len(np.atleast_2d(F))),
    }
