"""Uncertainty in the weights (Section 6.5, Proposition 7)."""
from __future__ import annotations

import numpy as np

from .scale import Y, level

SEED = 20261027          # fixed seed used in the article
N_SAMPLES = 200_000      # weight vectors per configuration


def dirichlet_moments(m, alpha: float) -> tuple[float, float]:
    """Exact mean and standard deviation of S_w(m) for w ~ Dirichlet(alpha 1_q) (eq. 19)."""
    m = np.asarray(m, dtype=float)
    q = m.size
    s2 = np.mean((m - m.mean()) ** 2)
    return float(m.mean()), float(np.sqrt(s2 / (q * alpha + 1)))


def sample_scores(m, alpha: float, n: int = N_SAMPLES, seed: int = SEED) -> np.ndarray:
    """Monte Carlo sample of S_w(m) under symmetric Dirichlet weights."""
    m = np.asarray(m, dtype=float)
    rng = np.random.default_rng(seed)
    w = rng.dirichlet(np.full(m.size, alpha), size=n)
    return w @ m


def level_probabilities(scores) -> dict[int, float]:
    """Empirical Pr[lambda(S) = r], r = 1..5."""
    lv = level(scores)
    return {r: float(np.mean(lv == r)) for r in range(1, 6)}


def summary(m, alpha: float, n: int = N_SAMPLES, seed: int = SEED) -> dict:
    s = sample_scores(m, alpha, n, seed)
    mean, sd = dirichlet_moments(m, alpha)
    return {"alpha": alpha, "exact_mean": mean, "exact_sd": sd,
            "mc_mean": float(s.mean()), "mc_sd": float(s.std()),
            "p_high": float(np.mean(s >= Y[4])), "p_below_0.7": float(np.mean(s < Y[3])),
            "levels": level_probabilities(s)}
