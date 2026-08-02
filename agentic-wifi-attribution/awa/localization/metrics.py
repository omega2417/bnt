"""Uncertainty, HPD, zone and calibration metrics (prompt Modules 8 & 14)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import numpy as np

from ..site import Site
from .grid import Grid


def posterior_map(grid: Grid, posterior: np.ndarray) -> np.ndarray:
    """MAP coordinate (2,) = cell centre of maximum posterior mass."""
    idx = int(np.argmax(posterior))
    return np.array([grid.xs[idx], grid.ys[idx]])


def posterior_mean(grid: Grid, posterior: np.ndarray) -> np.ndarray:
    return np.array(
        [np.sum(posterior * grid.xs), np.sum(posterior * grid.ys)]
    )


def entropy(posterior: np.ndarray) -> float:
    """Shannon entropy in nats (higher = more uncertain)."""
    p = posterior[posterior > 0]
    return float(-np.sum(p * np.log(p)))


def sharpness(grid: Grid, posterior: np.ndarray) -> float:
    """Posterior std of position (metres); smaller = sharper."""
    mu = posterior_mean(grid, posterior)
    var = np.sum(posterior * ((grid.xs - mu[0]) ** 2 + (grid.ys - mu[1]) ** 2))
    return float(np.sqrt(var))


def hpd_region(
    grid: Grid, posterior: np.ndarray, mass: float = 0.95
) -> Tuple[np.ndarray, float, float]:
    """Highest-posterior-density region.

    Returns (boolean mask over cells, achieved mass, area in m^2).
    """
    order = np.argsort(posterior)[::-1]
    cum = np.cumsum(posterior[order])
    k = int(np.searchsorted(cum, mass) + 1)
    k = min(k, posterior.size)
    mask = np.zeros(posterior.size, dtype=bool)
    mask[order[:k]] = True
    achieved = float(posterior[mask].sum())
    area = float(mask.sum() * grid.cell_area)
    return mask, achieved, area


def hpd_overlap(
    grid: Grid, p: np.ndarray, q: np.ndarray, mass: float = 0.95
) -> float:
    """Overlap coefficient of two HPD regions (Szymkiewicz-Simpson).

    ``|A ∩ B| / min(|A|, |B|)`` : 0 = disjoint, 1 = one region nested in the
    other.  This is a robust, spread-insensitive consistency signal — a tight
    FTM region sitting inside a broad RSSI region scores ~1 (they agree on a
    location), whereas raw Jensen-Shannon divergence would flag the sharpness
    difference as disagreement.
    """
    mp, _, _ = hpd_region(grid, p, mass)
    mq, _, _ = hpd_region(grid, q, mass)
    inter = np.count_nonzero(mp & mq)
    smaller = min(np.count_nonzero(mp), np.count_nonzero(mq))
    return float(inter / smaller) if smaller else 0.0


def zone_posterior(
    grid: Grid, posterior: np.ndarray, site: Site
) -> Dict[str, float]:
    """Probability mass in each named zone (and 'unzoned' remainder)."""
    out: Dict[str, float] = {}
    assigned = np.zeros(grid.n_cells, dtype=bool)
    for z in site.zones:
        m = z.contains(grid.xs, grid.ys)
        out[z.zone_id] = float(posterior[m].sum())
        assigned |= m
    out["unzoned"] = float(posterior[~assigned].sum())
    return out


def count_modes(
    grid: Grid, posterior: np.ndarray, rel_threshold: float = 0.5
) -> int:
    """Count spatial modes: local maxima above ``rel_threshold`` * global max.

    A simple 4-neighbour local-maximum test on the 2-D posterior image.
    """
    img = grid.as_image(posterior)
    gmax = img.max()
    if gmax <= 0:
        return 0
    thr = rel_threshold * gmax
    modes = 0
    ny, nx = img.shape
    for i in range(ny):
        for j in range(nx):
            v = img[i, j]
            if v < thr:
                continue
            neigh = []
            if i > 0:
                neigh.append(img[i - 1, j])
            if i < ny - 1:
                neigh.append(img[i + 1, j])
            if j > 0:
                neigh.append(img[i, j - 1])
            if j < nx - 1:
                neigh.append(img[i, j + 1])
            if all(v >= n for n in neigh):
                modes += 1
    return modes


def jensen_shannon(p: np.ndarray, q: np.ndarray) -> float:
    """Jensen-Shannon divergence (nats) between two posteriors."""
    p = np.clip(p, 1e-12, None)
    q = np.clip(q, 1e-12, None)
    p = p / p.sum()
    q = q / q.sum()
    m = 0.5 * (p + q)
    kl = lambda a, b: np.sum(a * np.log(a / b))
    return float(0.5 * kl(p, m) + 0.5 * kl(q, m))


@dataclass
class UncertaintySummary:
    map_xy: List[float]
    mean_xy: List[float]
    entropy_nats: float
    sharpness_m: float
    hpd_mass: float
    hpd_area_m2: float
    n_modes: int
    zone_posterior: Dict[str, float]

    def to_dict(self) -> dict:
        return {
            "MAP": self.map_xy,
            "mean": self.mean_xy,
            "entropy_nats": self.entropy_nats,
            "sharpness_m": self.sharpness_m,
            "HPD_mass": self.hpd_mass,
            "HPD_area_m2": self.hpd_area_m2,
            "multimodality_modes": self.n_modes,
            "zone_posterior": self.zone_posterior,
        }


def summarise(
    grid: Grid,
    posterior: np.ndarray,
    site: Site,
    hpd_mass: float = 0.95,
    rel_threshold: float = 0.5,
) -> UncertaintySummary:
    _, achieved, area = hpd_region(grid, posterior, hpd_mass)
    return UncertaintySummary(
        map_xy=posterior_map(grid, posterior).tolist(),
        mean_xy=posterior_mean(grid, posterior).tolist(),
        entropy_nats=entropy(posterior),
        sharpness_m=sharpness(grid, posterior),
        hpd_mass=achieved,
        hpd_area_m2=area,
        n_modes=count_modes(grid, posterior, rel_threshold),
        zone_posterior=zone_posterior(grid, posterior, site),
    )
