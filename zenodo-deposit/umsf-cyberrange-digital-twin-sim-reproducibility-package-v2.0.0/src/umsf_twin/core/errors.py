"""Typed errors of the twin kernel.

Every failure mode that can invalidate an experiment gets its own class so
that gates, tests and the CLI can distinguish a configuration mistake from a
safety violation or a broken invariant.
"""

from __future__ import annotations


class TwinError(Exception):
    """Base class for every error raised by the twin."""


class ConfigError(TwinError):
    """Malformed inventory, scenario or policy document."""


class ParameterError(TwinError):
    """Missing parameter, or use of a parameter whose evidence is too weak."""


class SafetyViolation(TwinError):
    """An action forbidden by the active safety policy was attempted."""


class InvariantViolation(TwinError):
    """A documented physical or logical invariant was broken during a run."""


class ContractError(TwinError):
    """A record does not satisfy its data contract."""


class GateFailure(TwinError):
    """A data-quality, fidelity or readiness gate rejected the run."""
