"""Centralised, seeded randomness.

Every stochastic operation in the pipeline draws from a :class:`SeededRng`
derived from a single master seed, so a run is fully reproducible from
(config, seed).  Independent, reproducible substreams are obtained with
:meth:`SeededRng.spawn` (which uses ``numpy`` ``SeedSequence`` spawning) so that,
e.g., the telemetry simulator and the attack engine never share draws.
"""

from __future__ import annotations

import hashlib

import numpy as np

__all__ = ["SeededRng", "seed_from_label"]


def seed_from_label(label: str, base_seed: int) -> int:
    """Deterministically derive a 32-bit seed from a string label + base seed.

    Used to give each named component (modality, agent, experiment cell) a
    stable, independent seed without threading counters through the call graph.
    """
    h = hashlib.sha256(f"{base_seed}:{label}".encode()).hexdigest()
    return int(h[:8], 16)


class SeededRng:
    """Thin wrapper over ``numpy.random.Generator`` with named substreams."""

    def __init__(self, seed: int) -> None:
        self.seed = int(seed)
        self._seq = np.random.SeedSequence(self.seed)
        self.generator = np.random.default_rng(self._seq)

    def spawn(self, label: str) -> SeededRng:
        """Create an independent substream keyed by ``label``.

        The same label always maps to the same substream for a given parent
        seed, which keeps per-component randomness stable across code changes
        elsewhere in the pipeline.
        """
        child_seed = seed_from_label(label, self.seed)
        return SeededRng(child_seed)

    # Convenience pass-throughs -------------------------------------------------
    def normal(self, *args, **kwargs) -> np.ndarray:
        return self.generator.normal(*args, **kwargs)

    def uniform(self, *args, **kwargs) -> np.ndarray:
        return self.generator.uniform(*args, **kwargs)

    def integers(self, *args, **kwargs) -> np.ndarray:
        return self.generator.integers(*args, **kwargs)

    def choice(self, *args, **kwargs):
        return self.generator.choice(*args, **kwargs)

    def poisson(self, *args, **kwargs):
        return self.generator.poisson(*args, **kwargs)

    def __repr__(self) -> str:  # pragma: no cover - trivial
        return f"SeededRng(seed={self.seed})"
