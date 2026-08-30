"""Generative model of the testbed environment used by the software-in-the-loop runs.

IMPORTANT PROVENANCE NOTE
-------------------------
This module generates a *modelled* telemetry stream. Every run produced with it is
tagged data_origin="simulation" and is excluded by analysis/audit_provenance.py from
any confirmatory table that makes a claim about the physical UMSF cyber range.
It exists to (a) exercise and validate the dtcr implementation end to end and
(b) provide the pilot variance estimates needed for the power analysis of the
physical campaign. It is NOT a substitute for the physical campaign.

All distributional constants below are declared parameters frozen in
protocol/preregistration.yaml before any result was inspected.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# 9 telemetry features - the dimension p used by the Mahalanobis detector.
FEATURES = (
    "pkt_in_rate", "bytes_in_rate", "conn_new_rate",      # network  (visible to IDS)
    "cpu_util", "mem_util", "iowait",                     # resource (twin only)
    "msg_jitter", "seq_gap_rate", "app_latency",          # timing/application
)
P = len(FEATURES)
IDS_FEATURES = (0, 1, 2)          # a traffic-only detector sees these three

NODE_TYPES = {
    "sensor": dict(mean=[120., 900., 2.0, 8., 22., 0.5, 3.0, 0.02, 12.],
                   sd=[10., 90., 0.4, 1.5, 2.0, 0.15, 0.6, 0.01, 2.0]),
    "edge":   dict(mean=[900., 7200., 18., 34., 51., 3.1, 2.2, 0.01, 21.],
                   sd=[70., 600., 2.5, 5.0, 4.0, 0.8, 0.5, 0.006, 3.5]),
    "cloud":  dict(mean=[1500., 12000., 42., 28., 46., 2.2, 1.8, 0.008, 17.],
                   sd=[120., 950., 5.0, 4.5, 3.5, 0.6, 0.4, 0.005, 2.8]),
    "service": dict(mean=[400., 3100., 26., 22., 39., 1.4, 1.6, 0.007, 30.],
                    sd=[35., 260., 3.0, 3.5, 3.0, 0.4, 0.35, 0.004, 5.0]),
}

# Correlation between features: network block, resource block, timing block.
_BLOCKS = [(0, 1, 2), (3, 4, 5), (6, 7, 8)]
_WITHIN, _BETWEEN = 0.55, 0.15


def _corr() -> np.ndarray:
    C = np.full((P, P), _BETWEEN)
    for blk in _BLOCKS:
        for i in blk:
            for j in blk:
                C[i, j] = _WITHIN
    np.fill_diagonal(C, 1.0)
    return C


CORR = _corr()


@dataclass(frozen=True)
class Asset:
    node_id: str
    kind: str
    criticality: float      # s_i in Eq. (8)


def build_assets() -> list[Asset]:
    assets = [Asset(f"s{i:02d}", "sensor", 0.30) for i in range(12)]
    assets += [Asset("e0", "edge", 0.85),      # broker
               Asset("e1", "edge", 0.70),      # analytics
               Asset("e2", "edge", 0.55),      # workload host
               Asset("e3", "edge", 0.55)]      # workload host
    assets += [Asset("c0", "cloud", 0.75),     # data store
               Asset("c1", "cloud", 0.65),     # regional analytics
               Asset("c2", "cloud", 0.60)]     # twin core
    assets += [Asset("svc", "service", 1.00)]  # civil service
    return assets


def build_dependency_matrix(assets: list[Asset]) -> np.ndarray:
    """W[i,j] > 0 means asset j depends on asset i (Eq. 9 convention)."""
    idx = {a.node_id: i for i, a in enumerate(assets)}
    n = len(assets)
    W = np.zeros((n, n))
    for i in range(12):
        W[idx[f"s{i:02d}"], idx["e0"]] = 1.0      # sensors feed the broker
    W[idx["e0"], idx["e1"]] = 0.80
    W[idx["e0"], idx["c0"]] = 0.70
    W[idx["e1"], idx["svc"]] = 0.60
    W[idx["c0"], idx["c1"]] = 0.50
    W[idx["c1"], idx["svc"]] = 0.40
    W[idx["e2"], idx["svc"]] = 0.30
    W[idx["e3"], idx["svc"]] = 0.30
    W[idx["c2"], idx["svc"]] = 0.10
    return W


def node_moments(kind: str, rng: np.random.Generator) -> tuple[np.ndarray, np.ndarray]:
    """True (unknown to the detector) mean and covariance for one node instance."""
    spec = NODE_TYPES[kind]
    mean = np.asarray(spec["mean"], dtype=float)
    sd = np.asarray(spec["sd"], dtype=float)
    # per-instance heterogeneity: +-10% on the mean, +-15% on the scale
    mean = mean * rng.uniform(0.90, 1.10, size=P)
    sd = sd * rng.uniform(0.85, 1.15, size=P)
    cov = np.outer(sd, sd) * CORR
    return mean, cov


def sample_stream(mean: np.ndarray, cov: np.ndarray, n: int, rng: np.random.Generator) -> np.ndarray:
    return rng.multivariate_normal(mean, cov, size=n, method="cholesky")
