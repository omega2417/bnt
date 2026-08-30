"""dtcr - reference implementation of the digital-twin-enabled cyber-resilience framework.

Modules
-------
audit         Probabilistic block-audit model (Eq. 4-5).
trust         Dynamic provenance-aware trust (Eq. 2-3).
anomaly       Mahalanobis anomaly scoring and chi-square calibration (Eq. 6-7, corrected).
risk          Local risk and dependency-graph propagation (Eq. 8-11).
orchestration Policy-constrained action selection (Eq. 12-13, Algorithm 1).
resilience    Availability, recovery time and NRI (Eq. 15, 18-19).
stats         Statistical estimators used for all reported effects (Eq. 23 and extensions).
"""

__version__ = "1.0.0"

from . import audit, trust, anomaly, risk, orchestration, resilience, stats  # noqa: F401

__all__ = ["audit", "trust", "anomaly", "risk", "orchestration", "resilience", "stats"]
