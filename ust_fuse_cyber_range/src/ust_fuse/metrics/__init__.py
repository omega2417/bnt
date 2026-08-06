"""Metrics engine: detection, tracking, calibration and paired statistics."""
from __future__ import annotations

from .detection import detection_metrics, roc_curve
from .tracking import evaluate_tracks, TrackingMetrics
from .calibration import calibration_metrics, CalibrationResult
from .stats import (
    paired_comparison,
    bootstrap_ci,
    cohens_d,
    power_analysis,
    PairedResult,
)

__all__ = [
    "detection_metrics",
    "roc_curve",
    "evaluate_tracks",
    "TrackingMetrics",
    "calibration_metrics",
    "CalibrationResult",
    "paired_comparison",
    "bootstrap_ci",
    "cohens_d",
    "power_analysis",
    "PairedResult",
]
