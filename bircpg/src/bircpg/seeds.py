"""Deterministic seed derivation.

Section 7.6 asks for seeds to be released so that every table can be
reproduced.  That only works if a seed means the same thing in every process,
so seeds are derived with a stable hash.  Python's built-in ``hash`` of a string
or tuple is randomised per process unless ``PYTHONHASHSEED`` is fixed, which
would make "seed 7" silently denote a different instance on every run.
"""

from __future__ import annotations

import hashlib
import random

__all__ = ["derive_seed", "stream"]


def derive_seed(*parts: object) -> int:
    """A stable 64-bit seed from any labelled parts.

    ``derive_seed("environment", 3, 10)`` returns the same integer in every
    process, on every platform, in every Python version with SHA-256.
    """
    key = "|".join(str(part) for part in parts).encode("utf-8")
    return int.from_bytes(hashlib.sha256(key).digest()[:8], "big")


def stream(*parts: object) -> random.Random:
    """A named random stream.

    Streams are separated by role -- environment, estimator, method -- so that a
    method's control flow cannot change the environment it faces (Section 7.2).
    """
    return random.Random(derive_seed(*parts))
