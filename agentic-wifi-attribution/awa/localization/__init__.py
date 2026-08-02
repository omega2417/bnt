"""Explainable Bayesian localisation core (prompt Modules 4-8, 14)."""

from .grid import Grid
from .radiomap import RadioMap, log_distance_rssi
from .fusion import (
    PosteriorResult,
    rssi_log_likelihood,
    ftm_log_likelihood,
    sensing_log_prior,
    fuse,
)
from .metrics import (
    entropy,
    sharpness,
    hpd_region,
    hpd_overlap,
    zone_posterior,
    count_modes,
    jensen_shannon,
    posterior_map,
)

__all__ = [
    "Grid",
    "RadioMap",
    "log_distance_rssi",
    "PosteriorResult",
    "rssi_log_likelihood",
    "ftm_log_likelihood",
    "sensing_log_prior",
    "fuse",
    "entropy",
    "sharpness",
    "hpd_region",
    "hpd_overlap",
    "zone_posterior",
    "count_modes",
    "jensen_shannon",
    "posterior_map",
]
