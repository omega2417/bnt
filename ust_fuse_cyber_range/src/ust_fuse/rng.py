"""Reproducible random-number management.

Every stochastic component in the twin draws from a :class:`numpy.random.Generator`
seeded from a single master seed plus a *stream name*.  This guarantees that

* re-running an experiment with the same seed yields identical RAW data, and
* independent components (sensor noise, clutter, network, faults) do not
  accidentally correlate because they share a stream.

This mirrors the proposal's requirement of reproducible, versioned, checksummed
experiments (see ЛР-8. MLOps і відтворюваність).
"""
from __future__ import annotations

import hashlib
from typing import Dict

import numpy as np


def _stream_seed(master_seed: int, stream: str) -> int:
    """Derive a stable 63-bit sub-seed from a master seed and a stream name."""
    h = hashlib.sha256(f"{master_seed}:{stream}".encode("utf-8")).hexdigest()
    return int(h[:16], 16) & ((1 << 63) - 1)


class RNGHub:
    """A registry of named, independent, reproducible RNG streams."""

    def __init__(self, master_seed: int = 20260101):
        self.master_seed = int(master_seed)
        self._streams: Dict[str, np.random.Generator] = {}

    def stream(self, name: str) -> np.random.Generator:
        """Return (creating on first use) the generator for ``name``."""
        if name not in self._streams:
            self._streams[name] = np.random.default_rng(
                _stream_seed(self.master_seed, name)
            )
        return self._streams[name]

    def spawn(self, name: str, index: int) -> np.random.Generator:
        """Return an independent generator for a numbered sub-stream."""
        return self.stream(f"{name}#{index}")

    def reset(self) -> None:
        self._streams.clear()

    def __repr__(self) -> str:  # pragma: no cover - cosmetic
        return f"RNGHub(master_seed={self.master_seed}, streams={list(self._streams)})"
