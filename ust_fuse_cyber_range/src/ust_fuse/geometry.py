"""Coordinate geometry helpers (local ENU frame, in metres).

The whole twin lives in a flat local East-North-Up (ENU) frame whose origin is
the range reference point.  This is sufficient for a small training range and
keeps the mathematics transparent for students (see ЛР-1 / ЛР-3).
"""
from __future__ import annotations

import numpy as np


def cart_to_spherical(rel: np.ndarray) -> np.ndarray:
    """Convert relative ENU position(s) to (range, azimuth, elevation).

    Azimuth is measured clockwise from North (+Y) in radians, elevation from the
    horizontal plane.  ``rel`` may be shape (3,) or (N, 3).
    """
    rel = np.atleast_2d(rel).astype(float)
    x, y, z = rel[:, 0], rel[:, 1], rel[:, 2]
    rng = np.sqrt(x * x + y * y + z * z)
    az = np.arctan2(x, y)  # 0 = North, +pi/2 = East
    ground = np.sqrt(x * x + y * y)
    el = np.arctan2(z, np.maximum(ground, 1e-9))
    out = np.stack([rng, az, el], axis=1)
    return out[0] if out.shape[0] == 1 else out


def spherical_to_cart(rng: float, az: float, el: float) -> np.ndarray:
    """Inverse of :func:`cart_to_spherical` for a single measurement."""
    ground = rng * np.cos(el)
    x = ground * np.sin(az)
    y = ground * np.cos(az)
    z = rng * np.sin(el)
    return np.array([x, y, z], dtype=float)


def wrap_angle(a: np.ndarray | float) -> np.ndarray | float:
    """Wrap angle(s) to (-pi, pi]."""
    return (np.asarray(a) + np.pi) % (2 * np.pi) - np.pi


def spherical_measurement_covariance(
    rng: float,
    az: float,
    el: float,
    sigma_r: float,
    sigma_az: float,
    sigma_el: float,
) -> np.ndarray:
    """Propagate a (range, az, el) measurement covariance into ENU Cartesian.

    Uses the unscented-free linearisation (Jacobian) of ``spherical_to_cart``.
    Bearing-only sensors are modelled by passing a very large ``sigma_r``; the
    resulting 3x3 covariance is then strongly elongated along the line of sight,
    exactly as a real bearing sensor behaves.
    """
    ce, se = np.cos(el), np.sin(el)
    ca, sa = np.cos(az), np.sin(az)
    # p = [ r*cos(el)*sin(az), r*cos(el)*cos(az), r*sin(el) ]
    J = np.array(
        [
            [ce * sa, rng * ce * ca, -rng * se * sa],
            [ce * ca, -rng * ce * sa, -rng * se * ca],
            [se, 0.0, rng * ce],
        ]
    )
    S = np.diag([sigma_r ** 2, sigma_az ** 2, sigma_el ** 2])
    R = J @ S @ J.T
    # numerical hygiene: symmetrise and floor eigenvalues
    R = 0.5 * (R + R.T)
    R += np.eye(3) * 1e-6
    return R


def great_ellipse_distance(a: np.ndarray, b: np.ndarray) -> float:
    """Plain Euclidean distance in the local frame (metres)."""
    return float(np.linalg.norm(np.asarray(a) - np.asarray(b)))
