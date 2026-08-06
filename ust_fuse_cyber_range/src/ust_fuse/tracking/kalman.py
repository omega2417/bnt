"""Constant-velocity Kalman filter in 3-D (state = [x,y,z,vx,vy,vz]).

The measurement is a 3-D ENU position with a full 3x3 covariance, so a single
filter transparently fuses heterogeneous sensors: a radar contributes a compact
``R``; a bearing-only camera contributes a needle-shaped ``R`` that mostly
sharpens the cross-range.  This is the mathematical heart of "UST-Fuse".
"""
from __future__ import annotations

import numpy as np

H = np.zeros((3, 6))
H[0, 0] = H[1, 1] = H[2, 2] = 1.0


def _F(dt: float) -> np.ndarray:
    F = np.eye(6)
    F[0, 3] = F[1, 4] = F[2, 5] = dt
    return F


def _Q(dt: float, q: float) -> np.ndarray:
    """Discrete white-noise-acceleration process covariance."""
    dt2 = dt * dt
    dt3 = dt2 * dt
    dt4 = dt3 * dt
    q11 = dt4 / 4.0
    q12 = dt3 / 2.0
    q22 = dt2
    Q = np.zeros((6, 6))
    for i in range(3):
        Q[i, i] = q11
        Q[i, i + 3] = q12
        Q[i + 3, i] = q12
        Q[i + 3, i + 3] = q22
    return Q * q


class KalmanCV:
    """A single-target constant-velocity Kalman filter."""

    def __init__(self, mean: np.ndarray, cov: np.ndarray, q: float = 4.0):
        self.mean = np.asarray(mean, dtype=float)
        self.cov = np.asarray(cov, dtype=float)
        self.q = q

    def predict(self, dt: float) -> None:
        if dt <= 0:
            return
        F = _F(dt)
        self.mean = F @ self.mean
        self.cov = F @ self.cov @ F.T + _Q(dt, self.q)
        self.cov = 0.5 * (self.cov + self.cov.T)

    def innovation(self, z: np.ndarray):
        y = np.asarray(z) - H @ self.mean
        return y

    def innovation_cov(self, R: np.ndarray) -> np.ndarray:
        return H @ self.cov @ H.T + R

    def mahalanobis2(self, z: np.ndarray, R: np.ndarray) -> float:
        y = self.innovation(z)
        S = self.innovation_cov(R)
        try:
            return float(y @ np.linalg.solve(S, y))
        except np.linalg.LinAlgError:
            return float("inf")

    def update(self, z: np.ndarray, R: np.ndarray) -> None:
        S = self.innovation_cov(R)
        K = self.cov @ H.T @ np.linalg.inv(S)
        y = self.innovation(z)
        self.mean = self.mean + K @ y
        I = np.eye(6)
        self.cov = (I - K @ H) @ self.cov
        self.cov = 0.5 * (self.cov + self.cov.T)

    def likelihood(self, z: np.ndarray, R: np.ndarray) -> float:
        y = self.innovation(z)
        S = self.innovation_cov(R)
        try:
            det = np.linalg.det(S)
            if det <= 0:
                return 1e-12
            m2 = y @ np.linalg.solve(S, y)
            return float(np.exp(-0.5 * m2) / np.sqrt(((2 * np.pi) ** 3) * det))
        except np.linalg.LinAlgError:
            return 1e-12

    def position(self) -> np.ndarray:
        return self.mean[:3].copy()
