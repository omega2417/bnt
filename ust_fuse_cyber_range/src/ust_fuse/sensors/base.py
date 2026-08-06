"""Base sensor model.

A sensor turns the ground-truth world into a stream of :class:`Detection`
objects.  The base class implements everything that is common to all archetypes:

* geometric visibility (range, field of view, line of sight),
* a range-dependent detection probability with an SNR model,
* Gaussian measurement noise in (range, azimuth, elevation),
* Poisson clutter / false alarms,
* clock stamping (offset + drift + jitter) — see ЛР-1,
* weather / domain scaling hooks — see ЛР-6.

Concrete subclasses (radar, EO-IR, RF-SDR, acoustic) only customise the
measurement covariance and class-label behaviour.
"""
from __future__ import annotations

from typing import List, Optional

import numpy as np

from ..config import SensorConfig
from ..datatypes import Detection, GroundTruth
from ..geometry import (
    cart_to_spherical,
    spherical_to_cart,
    spherical_measurement_covariance,
    wrap_angle,
)
from ..rng import RNGHub


class Sensor:
    """Common behaviour for every sensor archetype."""

    archetype = "generic"

    def __init__(self, cfg: SensorConfig):
        self.cfg = cfg
        self.pos = np.asarray(cfg.position, dtype=float)

    # -- detection probability -------------------------------------------- #
    def detection_probability(self, rng_m: float, env_scale: float):
        """Range-dependent Pd via a simple SNR / range^4-ish falloff.

        Returns ``(pd, snr_db)``.  ``env_scale`` folds in weather (ЛР-6) and
        per-sensor degradation faults (ЛР-5).  The functional form keeps
        Pd ~= ``pd_ref`` at ``ref_range`` and decays smoothly to zero at
        ``max_range``.
        """
        cfg = self.cfg
        if rng_m > cfg.max_range:
            return 0.0, -np.inf
        # SNR (dB) decays 40*log10(range) for active, ~22*log10 for passive.
        exponent = 40.0 if cfg.provides_range else 22.0
        snr_db = cfg.snr0_db - exponent * np.log10(max(rng_m, 1.0) / cfg.ref_range)
        # logistic mapping SNR -> Pd, anchored so Pd(ref_range) ~= pd_ref
        k = 0.35
        pd = 1.0 / (1.0 + np.exp(-k * (snr_db - 6.0)))
        pd = pd * cfg.pd_ref / (1.0 / (1.0 + np.exp(-k * (cfg.snr0_db - 6.0))))
        pd *= env_scale
        return float(np.clip(pd, 0.0, 0.999)), float(snr_db)

    # -- geometry --------------------------------------------------------- #
    def in_fov(self, rel: np.ndarray) -> bool:
        rng, az, el = cart_to_spherical(rel)
        if rng > self.cfg.max_range:
            return False
        half_az = np.radians(self.cfg.fov_az_deg) / 2.0
        half_el = np.radians(self.cfg.fov_el_deg) / 2.0
        # azimuth FOV centred on North for simplicity of the training range
        if self.cfg.fov_az_deg < 360.0 and abs(wrap_angle(az)) > half_az:
            return False
        if el > half_el or el < -np.radians(5):
            return False
        return True

    # -- measurement ------------------------------------------------------ #
    def _measure_covariance(self, rng, az, el):
        """Return the ENU 3x3 covariance for one detection (overridable)."""
        return spherical_measurement_covariance(
            rng,
            az,
            el,
            sigma_r=self.cfg.sigma_range,
            sigma_az=np.radians(self.cfg.sigma_az_deg),
            sigma_el=np.radians(self.cfg.sigma_el_deg),
        )

    def _class_label(self, gt: GroundTruth, rng_stream) -> str:
        """Class label a classifying sensor emits (overridable)."""
        return "unknown"

    def _target_visible(self, gt: GroundTruth, t: float) -> bool:
        return True

    # -- clock (ЛР-1) ----------------------------------------------------- #
    def stamp_time(self, t_true: float, rng_stream) -> float:
        cfg = self.cfg
        offset = cfg.clock_offset_ms * 1e-3
        drift = cfg.clock_drift_ppm * 1e-6 * t_true
        jitter = rng_stream.normal(0.0, cfg.clock_jitter_ms * 1e-3)
        return t_true + offset + drift + jitter

    # -- main scan -------------------------------------------------------- #
    def scan(
        self,
        t: float,
        truths: List[GroundTruth],
        rng_hub: RNGHub,
        env_scale: float = 1.0,
        clutter_scale: float = 1.0,
    ) -> List[Detection]:
        """Produce detections for one scan at true time ``t``."""
        cfg = self.cfg
        rng_det = rng_hub.stream(f"det.{cfg.sensor_id}")
        rng_clk = rng_hub.stream(f"clk.{cfg.sensor_id}")
        dets: List[Detection] = []

        for gt in truths:
            p = gt.position_at(t)
            if p is None or not self._target_visible(gt, t):
                continue
            rel = p - self.pos
            if not self.in_fov(rel):
                continue
            rng_m, az, el = cart_to_spherical(rel)
            pd, snr_db = self.detection_probability(rng_m, env_scale)
            if rng_det.random() > pd:
                continue
            # noisy spherical measurement
            az_meas = az + rng_det.normal(0.0, np.radians(cfg.sigma_az_deg))
            el_meas = el + rng_det.normal(0.0, np.radians(cfg.sigma_el_deg))
            if cfg.provides_range:
                r_meas = rng_m + rng_det.normal(0.0, cfg.sigma_range)
            else:
                # bearing-only: place the pseudo-point at a nominal range and let
                # the large along-LOS sigma make it a *cross-range-only* constraint.
                r_meas = min(cfg.ref_range, cfg.max_range * 0.6)
            z_enu = self.pos + spherical_to_cart(r_meas, az_meas, el_meas)
            # covariance is computed at the *placement* range so the ENU ellipse
            # is geometrically consistent with where the point actually sits.
            R = self._measure_covariance(max(r_meas, 1.0), az_meas, el_meas)
            label = self._class_label(gt, rng_det) if cfg.can_classify else "unknown"
            t_stamp = self.stamp_time(t, rng_clk)
            dets.append(
                Detection(
                    t_true=t,
                    t_stamp=t_stamp,
                    t_arrive=t,  # network layer fills this in later
                    sensor_id=cfg.sensor_id,
                    sensor_type=cfg.sensor_type,
                    z=z_enu,
                    R=R,
                    snr_db=snr_db,
                    truth_id=gt.truth_id,
                    detected_class=label,
                    provides_range=cfg.provides_range,
                    meta={"true_range": rng_m},
                )
            )

        # clutter / false alarms (Poisson)
        lam = cfg.false_alarm_rate * clutter_scale
        n_fa = rng_det.poisson(lam)
        for _ in range(int(n_fa)):
            r_fa = rng_det.uniform(0.1 * cfg.max_range, cfg.max_range)
            az_fa = rng_det.uniform(-np.pi, np.pi)
            el_fa = rng_det.uniform(0.0, np.radians(min(cfg.fov_el_deg, 60)))
            z_enu = self.pos + spherical_to_cart(r_fa, az_fa, el_fa)
            R = self._measure_covariance(r_fa, az_fa, el_fa)
            t_stamp = self.stamp_time(t, rng_clk)
            dets.append(
                Detection(
                    t_true=t,
                    t_stamp=t_stamp,
                    t_arrive=t,
                    sensor_id=cfg.sensor_id,
                    sensor_type=cfg.sensor_type,
                    z=z_enu,
                    R=R,
                    snr_db=rng_det.uniform(3.0, 10.0),
                    truth_id=-1,
                    detected_class="unknown",
                    provides_range=cfg.provides_range,
                    meta={"clutter": True},
                )
            )
        return dets

    def scan_times(self, duration_s: float) -> np.ndarray:
        return np.arange(0.0, duration_s + 1e-9, 1.0 / self.cfg.scan_rate_hz)
