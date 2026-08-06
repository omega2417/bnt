"""Composite multi-panel dashboard and a one-call figure pack."""
from __future__ import annotations

import os
from typing import Dict, List

import matplotlib.pyplot as plt

from . import plots as P
from .style import set_style


def mission_dashboard(result, save=None):
    """A single-figure field-trial dashboard for one mission."""
    set_style()
    fig = plt.figure(figsize=(15, 11))
    gs = fig.add_gridspec(3, 3, hspace=0.42, wspace=0.28)

    ax_top = fig.add_subplot(gs[0:2, 0:2])
    P.plot_topdown(result, mode="ust_fuse", ax=ax_top)

    ax_err = fig.add_subplot(gs[0, 2])
    P.plot_error_over_time(result, ax=ax_err)

    ax_ospa = fig.add_subplot(gs[1, 2])
    P.plot_ospa_over_time(result, ax=ax_ospa)

    ax_roc = fig.add_subplot(gs[2, 0])
    P.plot_roc(result, ax=ax_roc)

    ax_rel = fig.add_subplot(gs[2, 1])
    P.plot_reliability_diagram(result, mode="ust_fuse", ax=ax_rel)

    ax_pd = fig.add_subplot(gs[2, 2])
    P.plot_pd_bars(result, ax=ax_pd)

    fig.suptitle(
        f"UST-Fuse mission dashboard — {result.config.scenario.title}\n"
        f"experiment {result.manifest.experiment_id} · seed {result.config.seed}",
        fontsize=13, fontweight="bold",
    )
    if save:
        fig.savefig(save, bbox_inches="tight")
    return fig


def figure_pack(result, out_dir: str, prefix: str = "fig") -> Dict[str, str]:
    """Render the full figure set for one mission to ``out_dir``; return paths."""
    os.makedirs(out_dir, exist_ok=True)
    paths: Dict[str, str] = {}

    def _p(name):
        return os.path.join(out_dir, f"{prefix}_{name}.png")

    jobs = {
        "coverage": lambda: P.plot_sensor_coverage(result.raw.range_cfg, save=_p("coverage")),
        "topdown_ustfuse": lambda: P.plot_topdown(result, "ust_fuse", save=_p("topdown_ustfuse")),
        "topdown_reference": lambda: P.plot_topdown(result, "reference", save=_p("topdown_reference")),
        "traj3d": lambda: P.plot_trajectories_3d(result, "ust_fuse", save=_p("traj3d")),
        "detections": lambda: P.plot_detections(result, save=_p("detections")),
        "error_time": lambda: P.plot_error_over_time(result, save=_p("error_time")),
        "ospa_time": lambda: P.plot_ospa_over_time(result, save=_p("ospa_time")),
        "roc": lambda: P.plot_roc(result, save=_p("roc")),
        "pd_bars": lambda: P.plot_pd_bars(result, save=_p("pd_bars")),
        "reliability": lambda: P.plot_reliability_diagram(result, "ust_fuse", save=_p("reliability")),
        "selective_risk": lambda: P.plot_selective_risk(result, save=_p("selective_risk")),
        "clock": lambda: P.plot_clock_desync(result, save=_p("clock")),
        "metric_cmp": lambda: P.plot_metric_comparison(result, save=_p("metric_cmp")),
        "confidence": lambda: P.plot_track_confidence(result, "ust_fuse", save=_p("confidence")),
        "fault_timeline": lambda: P.plot_fault_timeline(result, save=_p("fault_timeline")),
        "dashboard": lambda: mission_dashboard(result, save=_p("dashboard")),
    }
    for name, fn in jobs.items():
        try:
            fig = fn()
            paths[name] = _p(name)
            plt.close(fig)
        except Exception as e:  # keep going; a single bad panel shouldn't stop the pack
            paths[name] = f"ERROR: {e}"
    return paths
