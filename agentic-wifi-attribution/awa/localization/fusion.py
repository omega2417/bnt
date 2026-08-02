"""Bayesian multi-modality fusion on the grid (prompt Modules 5-8).

The log-posterior over grid cells x is::

    log p(x | z) = log prior(x)
                 + sum_i  w_i^rssi   * log p(r_i | x)     [RSSI]
                 + sum_j  w_j^ftm    * log p(d_j | x)     [FTM/RTT]
                 + log p_sensing(x)                       [802.11bf context]

Key design invariants (prompt Module 22):

* the returned posterior is normalised to 1;
* a *missing* modality contributes a flat (neutral) term, never zeros;
* per-measurement weights ``w`` down-weight low-quality / low-provenance
  inputs and are recorded for explainability (sensor / modality contribution).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np
from scipy.special import logsumexp
from scipy.stats import t as student_t

from ..config import (
    FtmLikelihoodConfig,
    RssiLikelihoodConfig,
    SensingConfig,
    SPEED_OF_LIGHT,
)
from ..site import Sensor
from .grid import Grid
from .radiomap import RadioMap


# --------------------------------------------------------------------------- #
# Per-modality log-likelihoods
# --------------------------------------------------------------------------- #
def rssi_log_likelihood(
    grid: Grid,
    radiomap: RadioMap,
    observed: Dict[str, float],
    cfg: RssiLikelihoodConfig,
    weights: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """Sum of per-sensor RSSI log-likelihoods over all grid cells.

    ``observed`` maps sensor_id -> measured RSSI (dBm).  Sensors absent from
    ``observed`` are simply skipped (missing-mask semantics).
    """
    weights = weights or {}
    ll = np.zeros(grid.n_cells)
    for sid, r in observed.items():
        if sid not in radiomap.sensor_ids:
            continue
        idx = radiomap.sensor_ids.index(sid)
        mu = radiomap.mean_rssi[idx]
        w = float(weights.get(sid, 1.0))
        if w <= 0.0:
            continue
        resid = (r - mu) / cfg.sigma_db
        if cfg.use_student_t:
            comp = student_t.logpdf(resid, df=cfg.student_t_dof) - np.log(
                cfg.sigma_db
            )
        else:  # Gaussian
            comp = -0.5 * resid ** 2 - np.log(
                cfg.sigma_db * np.sqrt(2 * np.pi)
            )
        # Contamination floor keeps a single wild outlier from vetoing a cell.
        if cfg.contamination_eps > 0:
            floor = np.log(cfg.contamination_eps / (radiomap.path_loss.p0_dbm
                                                    - radiomap.path_loss.min_rssi_dbm + 1e-9))
            comp = np.logaddexp(np.log1p(-cfg.contamination_eps) + comp, floor)
        ll += w * comp
    return ll


def ftm_log_likelihood(
    grid: Grid,
    sensors: Dict[str, Sensor],
    observed_rtt_s: Dict[str, float],
    cfg: FtmLikelihoodConfig,
    weights: Optional[Dict[str, float]] = None,
) -> np.ndarray:
    """FTM/RTT log-likelihood with a LOS / NLOS Gaussian mixture.

    ``observed_rtt_s`` maps anchor_id -> round-trip time (seconds).  Pseudo
    range d = c * RTT / 2.  NLOS adds a *positive* bias (prompt Module 5).
    """
    weights = weights or {}
    ll = np.zeros(grid.n_cells)
    for aid, rtt in observed_rtt_s.items():
        s = sensors.get(aid)
        if s is None or not s.supports_ftm:
            continue
        w = float(weights.get(aid, 1.0))
        if w <= 0.0:
            continue
        rng = SPEED_OF_LIGHT * rtt / 2.0
        if rng > cfg.max_range_m:  # physically implausible -> reject
            continue
        true_d = grid.distances_to(s.position)
        los = -0.5 * ((rng - true_d) / cfg.sigma_los_m) ** 2 - np.log(
            cfg.sigma_los_m * np.sqrt(2 * np.pi)
        )
        nlos = -0.5 * (
            (rng - (true_d + cfg.nlos_bias_m)) / cfg.sigma_nlos_m
        ) ** 2 - np.log(cfg.sigma_nlos_m * np.sqrt(2 * np.pi))
        mix = np.logaddexp(
            np.log1p(-cfg.nlos_prob) + los, np.log(cfg.nlos_prob) + nlos
        )
        ll += w * mix
    return ll


def sensing_log_prior(
    grid: Grid,
    motion_centre: Optional[np.ndarray],
    motion_radius_m: float,
    cfg: SensingConfig,
    provenance: float = 1.0,
) -> np.ndarray:
    """802.11bf WLAN-sensing *context* term (soft prior over location).

    Sensing never asserts identity; it reshapes the spatial prior toward
    regions where motion/presence was detected.  If provenance is below the
    configured floor the term is muted (returns zeros).
    """
    if motion_centre is None or provenance < cfg.provenance_floor:
        return np.zeros(grid.n_cells)
    d = grid.distances_to(motion_centre)
    # Soft radial bump; strength scaled by motion weight and provenance.
    bump = -0.5 * (d / max(motion_radius_m, 1e-3)) ** 2
    return cfg.motion_weight * provenance * bump


# --------------------------------------------------------------------------- #
# Fusion
# --------------------------------------------------------------------------- #
@dataclass
class PosteriorResult:
    """Full localisation output (prompt Module 8)."""

    posterior: np.ndarray            # (n_cells,), sums to 1
    log_prior: np.ndarray
    modality_loglik: Dict[str, np.ndarray] = field(default_factory=dict)
    used_modalities: List[str] = field(default_factory=list)
    missing_modalities: List[str] = field(default_factory=list)
    grid: Optional[Grid] = None

    def normalised(self) -> np.ndarray:
        return self.posterior


def _normalise_from_logs(log_unnorm: np.ndarray) -> np.ndarray:
    log_unnorm = log_unnorm - np.max(log_unnorm)
    p = np.exp(log_unnorm - logsumexp(log_unnorm))
    p = np.maximum(p, 0.0)
    total = p.sum()
    return p / total if total > 0 else np.full_like(p, 1.0 / p.size)


def fuse(
    grid: Grid,
    log_prior: Optional[np.ndarray] = None,
    rssi_ll: Optional[np.ndarray] = None,
    ftm_ll: Optional[np.ndarray] = None,
    sensing_ll: Optional[np.ndarray] = None,
) -> PosteriorResult:
    """Combine available modality log-likelihoods into one posterior.

    Any ``None`` modality is treated as *missing* -> contributes nothing
    (a flat, neutral term), and is recorded in ``missing_modalities``.
    """
    if log_prior is None:
        log_prior = np.zeros(grid.n_cells)  # uniform prior over the floor
    log_unnorm = log_prior.copy()

    modality_loglik: Dict[str, np.ndarray] = {}
    used, missing = [], []
    for name, ll in (("rssi", rssi_ll), ("ftm", ftm_ll), ("sensing", sensing_ll)):
        if ll is None:
            missing.append(name)
            continue
        modality_loglik[name] = ll
        log_unnorm = log_unnorm + ll
        used.append(name)

    posterior = _normalise_from_logs(log_unnorm)
    return PosteriorResult(
        posterior=posterior,
        log_prior=log_prior,
        modality_loglik=modality_loglik,
        used_modalities=used,
        missing_modalities=missing,
        grid=grid,
    )
