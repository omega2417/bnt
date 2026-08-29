"""Field-trial design: detectability geometry, warning-time budget, and sizing.

This module is the forward-looking half of the project. The rest of the package
prepares data that already exists; this part answers the questions that have to
be settled *before* a campaign is flown:

* how far away can each modality plausibly detect each platform class,
* how much lead time that range buys at a given closing speed,
* whether that lead time clears the operational decision budget,
* how many runs each cell of the flight matrix needs to support a claim,
* and how many flying days that implies.

Every constant it uses is a declared planning assumption from
``config/pipeline.yaml``. The outputs are design targets, not measurements: the
first calibration campaign replaces the assumptions and the curves are recomputed.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from itertools import product
from typing import Dict, List

import numpy as np
import pandas as pd


# --------------------------------------------------------------------------- #
# Normal quantiles without a SciPy dependency
# --------------------------------------------------------------------------- #
def norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation).

    Accurate to about 1.15e-9 over the open unit interval, which is far beyond
    what a sample-size calculation needs, and avoids adding SciPy to the release
    environment for a single function.
    """
    if not 0.0 < p < 1.0:
        raise ValueError("p must lie in (0, 1)")
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00]
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
               ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / \
                ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / \
           (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


# --------------------------------------------------------------------------- #
# Acoustic detectability
# --------------------------------------------------------------------------- #
def acoustic_snr_db(distance_m, source_level_db: float, ambient_db: float,
                    alpha_db_per_m: float, ref_m: float = 1.0):
    """In-band SNR at range r under spherical spreading plus absorption.

        L(r) = L_ref - 20 log10(r / r_ref) - alpha (r - r_ref)
        SNR   = L(r) - L_ambient

    Spherical spreading is the free-field idealization; real sites add ground
    reflection, screening, and wind noise, all of which reduce the achievable
    range. The curve is therefore an optimistic bound used to *place* sensors,
    and the measured SNR recorded in ``media_manifest`` is what the release
    reports.
    """
    r = np.maximum(np.asarray(distance_m, dtype=np.float64), ref_m)
    level = source_level_db - 20.0 * np.log10(r / ref_m) - alpha_db_per_m * (r - ref_m)
    return level - ambient_db


def acoustic_detection_range_m(source_level_db: float, ambient_db: float,
                               alpha_db_per_m: float, detection_snr_db: float,
                               ref_m: float = 1.0, r_max: float = 20000.0,
                               processing_gain_db: float = 0.0) -> float:
    """Largest r with SNR(r) + G >= threshold.

    ``processing_gain_db`` is the gain of the acoustic front end. It is separated
    from the threshold so that the physical propagation term and the detector
    term can be recalibrated independently: propagation is a property of the
    site and the weather, the gain is a property of the algorithm.

    The equation is transcendental in r (a logarithm plus a linear term), so it
    is solved by bisection on the monotonically decreasing SNR curve rather than
    inverted in closed form.
    """
    def f(r: float) -> float:
        return float(acoustic_snr_db(r, source_level_db, ambient_db,
                                     alpha_db_per_m, ref_m)) \
            + processing_gain_db - detection_snr_db
    lo, hi = ref_m, r_max
    if f(lo) < 0:
        return 0.0
    if f(hi) > 0:
        return r_max
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) >= 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------- #
# Visual detectability
# --------------------------------------------------------------------------- #
def focal_length_px(sensor_width_px: int, hfov_deg: float) -> float:
    """Pinhole focal length in pixels implied by the sensor width and field of view."""
    return sensor_width_px / (2.0 * math.tan(math.radians(hfov_deg) / 2.0))


def apparent_size_px(distance_m, span_m: float, f_px: float):
    """Apparent extent p = f_px * S / r of a target of span S at range r."""
    r = np.maximum(np.asarray(distance_m, dtype=np.float64), 1e-6)
    return f_px * span_m / r


def visual_range_m(span_m: float, f_px: float, min_px: float) -> float:
    """Range at which the apparent extent falls to ``min_px``: r = f_px S / p_min."""
    return f_px * span_m / min_px


# --------------------------------------------------------------------------- #
# Warning-time budget
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class WarningBudget:
    detection_range_m: float
    closing_speed_ms: float
    lead_time_s: float          # r_det / v
    decision_s: float
    dissemination_s: float
    actionable_s: float         # lead - decision - dissemination
    required_s: float
    margin_s: float             # actionable - required
    feasible: bool


def warning_budget(detection_range_m: float, closing_speed_ms: float,
                   decision_s: float, dissemination_s: float,
                   required_s: float) -> WarningBudget:
    """Turn a detection range into an operational lead-time margin.

    A detection at range r against a target closing at v gives a raw lead time
    r / v before boundary crossing. The operator decision and the dissemination
    of the alert both consume part of it, so the time actually available to the
    protected population is

        T_actionable = r / v - T_decide - T_disseminate

    and the sensing geometry is feasible only when that clears the required
    actionable lead. Expressed the other way round, the range the trial must
    demonstrate is

        r_required = v (T_required + T_decide + T_disseminate)

    which is the number that drives sensor placement and the choice of the
    largest approach radius in the flight matrix.
    """
    lead = detection_range_m / max(closing_speed_ms, 1e-9)
    actionable = lead - decision_s - dissemination_s
    return WarningBudget(
        detection_range_m=detection_range_m,
        closing_speed_ms=closing_speed_ms,
        lead_time_s=lead,
        decision_s=decision_s,
        dissemination_s=dissemination_s,
        actionable_s=actionable,
        required_s=required_s,
        margin_s=actionable - required_s,
        feasible=actionable >= required_s,
    )


def required_detection_range_m(closing_speed_ms: float, required_s: float,
                               decision_s: float, dissemination_s: float) -> float:
    """r_required = v (T_required + T_decide + T_disseminate)."""
    return closing_speed_ms * (required_s + decision_s + dissemination_s)


# --------------------------------------------------------------------------- #
# Sample size
# --------------------------------------------------------------------------- #
def sample_size_one_proportion(p0: float, p1: float, alpha: float,
                               power: float, one_sided: bool = True) -> int:
    """Runs needed to show a detection rate of p1 against a null of p0.

        n = ( z_{1-a} sqrt(p0(1-p0)) + z_{1-b} sqrt(p1(1-p1)) )^2 / (p1 - p0)^2

    This is the normal approximation with separate variances under the null and
    the alternative, which is the usual form for a one-sided acceptance test of
    a detection rate. It is a per-cell figure: the flight matrix multiplies it.
    """
    if not 0 < p0 < p1 < 1:
        raise ValueError("require 0 < p0 < p1 < 1")
    z_a = norm_ppf(1 - alpha) if one_sided else norm_ppf(1 - alpha / 2)
    z_b = norm_ppf(power)
    num = (z_a * math.sqrt(p0 * (1 - p0)) + z_b * math.sqrt(p1 * (1 - p1))) ** 2
    return int(math.ceil(num / (p1 - p0) ** 2))


def inflate_for_loss(n: int, loss_rate: float) -> int:
    """Plan for runs voided by weather, safety abort, or sensor fault."""
    if not 0 <= loss_rate < 1:
        raise ValueError("loss_rate must lie in [0, 1)")
    return int(math.ceil(n / (1.0 - loss_rate)))


def wilson_interval(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Wilson score interval for an observed detection rate.

    Preferred over the Wald interval because trial cells are small and observed
    rates sit near 1, where the Wald interval leaves the unit interval and
    collapses to zero width at k = n.
    """
    if n == 0:
        return (0.0, 1.0)
    z = norm_ppf(1 - alpha / 2)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


# --------------------------------------------------------------------------- #
# Flight matrix
# --------------------------------------------------------------------------- #
def flight_matrix(cfg) -> pd.DataFrame:
    """Enumerate the full factorial of the declared flight-matrix factors."""
    fm = cfg["flight_matrix"]
    names = list(fm.keys())
    rows = [dict(zip(names, combo)) for combo in product(*(fm[n] for n in names))]
    return pd.DataFrame(rows)


def campaign_plan(cfg) -> Dict[str, object]:
    """Size the controlled-flight campaign from the configuration.

    Reports the full-factorial cell count, the per-cell run requirement, the
    total sortie count, and - because a full factorial is almost never
    affordable - the reduced plan obtained by treating illumination and
    background as blocking factors rather than crossing them with everything
    else. Both figures are given so that the reduction is an explicit decision
    rather than a silent one.
    """
    ft = cfg["field_trial"]
    n_per_cell = sample_size_one_proportion(
        ft["null_detection_rate"], ft["target_detection_rate"],
        ft["alpha"], ft["power"])
    n_planned = inflate_for_loss(n_per_cell, ft["expected_run_loss_rate"])

    fm = cfg["flight_matrix"]
    full_cells = 1
    for v in fm.values():
        full_cells *= len(v)

    primary = ["platform_class", "approach_geometry", "speed_band"]
    reduced_cells = 1
    for k in primary:
        reduced_cells *= len(fm[k])
    blocks = len(fm["illumination"])       # each primary cell is repeated per block

    return {
        "n_per_cell_statistical": n_per_cell,
        "n_per_cell_planned": n_planned,
        "full_factorial_cells": full_cells,
        "full_factorial_sorties": full_cells * n_planned,
        "reduced_primary_cells": reduced_cells,
        "reduced_blocks": blocks,
        "reduced_sorties": reduced_cells * blocks * n_planned,
        "null_detection_rate": ft["null_detection_rate"],
        "target_detection_rate": ft["target_detection_rate"],
        "alpha": ft["alpha"],
        "power": ft["power"],
        "expected_run_loss_rate": ft["expected_run_loss_rate"],
    }


def detectability_table(cfg) -> pd.DataFrame:
    """Per-platform detection ranges and lead-time margins for each modality."""
    det = cfg["detectability"]
    ac, vi = det["acoustic"], det["visual"]
    ft = cfg["field_trial"]
    f_px = focal_length_px(vi["sensor_width_px"], vi["horizontal_fov_deg"])

    rows: List[dict] = []
    for platform, src_db in ac["source_level_db_at_ref"].items():
        span = vi["target_span_m"][platform]
        r_vis_det = visual_range_m(span, f_px, vi["detection_min_px"])
        r_vis_rec = visual_range_m(span, f_px, vi["recognition_min_px"])
        for env, amb in ac["ambient_noise_db"].items():
            r_ac = acoustic_detection_range_m(
                src_db, amb, ac["atmospheric_absorption_db_per_m"],
                ac["detection_snr_db"], ac["reference_distance_m"],
                processing_gain_db=ac.get("detector_processing_gain_db", 0.0))
            for band, v in det["kinematics_planning"]["closing_speed_ms"].items():
                fused = max(r_ac, r_vis_det)   # first modality to see it wins
                b = warning_budget(fused, v, ft["decision_latency_s"],
                                   ft["dissemination_latency_s"],
                                   ft["required_actionable_lead_s"])
                rows.append({
                    "platform_class": platform,
                    "ambient_env": env,
                    "speed_band": band,
                    "closing_speed_ms": v,
                    "acoustic_range_m": round(r_ac, 1),
                    "visual_detect_range_m": round(r_vis_det, 1),
                    "visual_recognize_range_m": round(r_vis_rec, 1),
                    "fused_first_detection_m": round(fused, 1),
                    "lead_time_s": round(b.lead_time_s, 1),
                    "actionable_s": round(b.actionable_s, 1),
                    "required_range_m": round(required_detection_range_m(
                        v, ft["required_actionable_lead_s"],
                        ft["decision_latency_s"], ft["dissemination_latency_s"]), 1),
                    "margin_s": round(b.margin_s, 1),
                    "feasible": b.feasible,
                })
    return pd.DataFrame(rows)
