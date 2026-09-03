"""Deterministic, namespaced randomness.

Every stochastic component draws from its own stream derived from
``(root_seed, replicate_id, namespace)``. Adding a component therefore cannot
shift the numbers produced by an existing one, which is what makes replicates
comparable across code versions.
"""

from __future__ import annotations

import hashlib
import math
import random

__all__ = ["derived_seed", "RngHub"]


def derived_seed(root_seed: int, replicate_id: int, namespace: str) -> int:
    digest = hashlib.blake2b(
        f"{int(root_seed)}|{int(replicate_id)}|{namespace}".encode("utf-8"),
        digest_size=8,
    ).digest()
    return int.from_bytes(digest, "big")


class RngHub:
    """Lazily created ``random.Random`` per namespace."""

    def __init__(self, root_seed: int, replicate_id: int = 0) -> None:
        self.root_seed = int(root_seed)
        self.replicate_id = int(replicate_id)
        self._streams: dict[str, random.Random] = {}

    def stream(self, namespace: str) -> random.Random:
        if namespace not in self._streams:
            self._streams[namespace] = random.Random(
                derived_seed(self.root_seed, self.replicate_id, namespace)
            )
        return self._streams[namespace]

    # -- distributions used across the twin -----------------------------
    def normal(self, namespace: str, mu: float, sigma: float) -> float:
        return self.stream(namespace).gauss(mu, sigma)

    def poisson(self, namespace: str, mean: float) -> int:
        """Knuth for small means, normal approximation above 30."""

        rng = self.stream(namespace)
        if mean <= 0:
            return 0
        if mean > 30:
            return max(0, int(round(rng.gauss(mean, math.sqrt(mean)))))
        limit = math.exp(-mean)
        k, product = 0, rng.random()
        while product > limit and k < 10_000:
            k += 1
            product *= rng.random()
        return k

    def negative_binomial(self, namespace: str, mean: float, dispersion: float) -> int:
        """Gamma-Poisson mixture; ``dispersion`` is the NB size parameter."""

        if mean <= 0:
            return 0
        if dispersion <= 0:
            return self.poisson(namespace, mean)
        rng = self.stream(namespace)
        rate = rng.gammavariate(dispersion, mean / dispersion)
        return self.poisson(namespace, rate)

    def lognormal(self, namespace: str, median: float, sigma: float) -> float:
        if median <= 0:
            return 0.0
        return float(self.stream(namespace).lognormvariate(math.log(median), sigma))

    def bernoulli(self, namespace: str, probability: float) -> bool:
        return self.stream(namespace).random() < probability

    def choice(self, namespace: str, items):
        return self.stream(namespace).choice(list(items))

    def uniform(self, namespace: str, low: float, high: float) -> float:
        return self.stream(namespace).uniform(low, high)
