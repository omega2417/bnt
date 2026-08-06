"""Visualisation suite for the UST-Fuse twin.

Every function returns a Matplotlib ``Figure`` and, if given ``save=<path>``,
writes a PNG.  The functions are grouped by lab work so a notebook can build a
field-trial style figure pack with one call (:func:`figure_pack`).
"""
from __future__ import annotations

from .style import set_style, PALETTE
from .plots import (
    plot_topdown,
    plot_trajectories_3d,
    plot_sensor_coverage,
    plot_detections,
    plot_error_over_time,
    plot_ospa_over_time,
    plot_roc,
    plot_pd_bars,
    plot_reliability_diagram,
    plot_selective_risk,
    plot_clock_desync,
    plot_metric_comparison,
    plot_paired_forest,
    plot_campaign_box,
    plot_scenario_heatmap,
    plot_track_confidence,
    plot_fault_timeline,
)
from .dashboard import mission_dashboard, figure_pack

__all__ = [
    "set_style",
    "PALETTE",
    "plot_topdown",
    "plot_trajectories_3d",
    "plot_sensor_coverage",
    "plot_detections",
    "plot_error_over_time",
    "plot_ospa_over_time",
    "plot_roc",
    "plot_pd_bars",
    "plot_reliability_diagram",
    "plot_selective_risk",
    "plot_clock_desync",
    "plot_metric_comparison",
    "plot_paired_forest",
    "plot_campaign_box",
    "plot_scenario_heatmap",
    "plot_track_confidence",
    "plot_fault_timeline",
    "mission_dashboard",
    "figure_pack",
]
