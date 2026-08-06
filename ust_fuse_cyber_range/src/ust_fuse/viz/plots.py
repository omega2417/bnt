"""The individual plot functions.

Each takes the objects it needs (an :class:`ExperimentResult`, a
:class:`CampaignResult`, or lower-level pieces) plus an optional ``save`` path
and ``ax``.  All return a Matplotlib ``Figure``.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import Circle

from .style import PALETTE, SENSOR_COLORS, MODE_LABELS, mode_color, set_style


def _save(fig, save: Optional[str]):
    if save:
        fig.savefig(save, bbox_inches="tight")
    return fig


def _truth_xy(truths):
    return [(gt.pos[:, 0], gt.pos[:, 1]) for gt in truths]


# --------------------------------------------------------------------------- #
# Geometry / world
# --------------------------------------------------------------------------- #
def plot_topdown(result, mode: str = "ust_fuse", save=None, ax=None, show_dets=True):
    """Top-down (East-North) view: sensors, ground truth, tracks, detections."""
    set_style()
    own_fig = ax is None
    fig, ax = (plt.subplots(figsize=(7.2, 6.6)) if own_fig else (ax.figure, ax))
    raw = result.raw

    # sensors + coverage
    for s in raw.range_cfg.enabled_sensors():
        col = SENSOR_COLORS.get(s.sensor_type, "#555")
        ax.add_patch(Circle((s.position[0], s.position[1]), s.max_range,
                            fill=False, ls="--", lw=0.8, ec=col, alpha=0.35))
        ax.scatter([s.position[0]], [s.position[1]], marker="^", s=90, color=col,
                   edgecolor="k", zorder=5, label=f"{s.sensor_id} ({s.sensor_type})")

    # detections
    if show_dets:
        md = result.modes.get(mode)
        dets = raw.detections
        cl = np.array([[d.z[0], d.z[1]] for d in dets if d.is_clutter])
        tr = np.array([[d.z[0], d.z[1]] for d in dets if not d.is_clutter])
        if len(cl):
            ax.scatter(cl[:, 0], cl[:, 1], s=4, c=PALETTE["clutter"], alpha=0.35,
                       label="clutter/false alarms")
        if len(tr):
            ax.scatter(tr[:, 0], tr[:, 1], s=4, c="#4a90d9", alpha=0.25,
                       label="target detections")

    # ground truth
    for i, gt in enumerate(raw.truths):
        ax.plot(gt.pos[:, 0], gt.pos[:, 1], color=PALETTE["truth"], lw=2.0,
                label="ground truth" if i == 0 else None, zorder=4)
        ax.scatter([gt.pos[0, 0]], [gt.pos[0, 1]], marker="o", s=25,
                   color=PALETTE["truth"], zorder=4)

    # tracks
    md = result.modes.get(mode)
    if md:
        col = mode_color(mode)
        first = True
        for trk in md.fusion.tracks:
            if not trk.was_confirmed or len(trk.history) < 3:
                continue
            pts = np.array([s.mean[:2] for s in trk.history if s.t >= trk.t_confirmed])
            if len(pts) < 2:
                continue
            ax.plot(pts[:, 0], pts[:, 1], color=col, lw=1.1, alpha=0.85,
                    label=MODE_LABELS.get(mode, mode) + " tracks" if first else None)
            first = False

    ext = raw.range_cfg.site_extent_m
    ax.set_xlim(-ext, ext)
    ax.set_ylim(-ext, ext)
    ax.set_aspect("equal")
    ax.set_xlabel("East (m)")
    ax.set_ylabel("North (m)")
    ax.set_title(f"Top-down view — {result.config.scenario.title}\n{MODE_LABELS.get(mode, mode)}")
    ax.legend(loc="upper right", fontsize=7, ncol=1)
    if own_fig:
        fig.tight_layout()
    return _save(fig, save)


def plot_trajectories_3d(result, mode="ust_fuse", save=None):
    """3-D ground truth vs estimated tracks."""
    set_style()
    fig = plt.figure(figsize=(7.5, 6.4))
    ax = fig.add_subplot(111, projection="3d")
    raw = result.raw
    for i, gt in enumerate(raw.truths):
        ax.plot(gt.pos[:, 0], gt.pos[:, 1], gt.pos[:, 2], color=PALETTE["truth"],
                lw=2, label="ground truth" if i == 0 else None)
    md = result.modes.get(mode)
    if md:
        col = mode_color(mode)
        first = True
        for trk in md.fusion.tracks:
            if not trk.was_confirmed:
                continue
            pts = np.array([s.mean[:3] for s in trk.history if s.t >= trk.t_confirmed])
            if len(pts) < 2:
                continue
            ax.plot(pts[:, 0], pts[:, 1], pts[:, 2], color=col, lw=1.0, alpha=0.8,
                    label=MODE_LABELS.get(mode, mode) if first else None)
            first = False
    for s in raw.range_cfg.enabled_sensors():
        ax.scatter([s.position[0]], [s.position[1]], [s.position[2]], marker="^",
                   s=60, color=SENSOR_COLORS.get(s.sensor_type, "#555"), edgecolor="k")
    ax.set_xlabel("East (m)"); ax.set_ylabel("North (m)"); ax.set_zlabel("Up (m)")
    ax.set_title(f"3-D trajectories — {MODE_LABELS.get(mode, mode)}")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    return _save(fig, save)


def plot_sensor_coverage(range_cfg, save=None):
    """Sensor coverage footprints and detection-probability rings."""
    set_style()
    fig, ax = plt.subplots(figsize=(6.8, 6.4))
    for s in range_cfg.enabled_sensors():
        col = SENSOR_COLORS.get(s.sensor_type, "#555")
        for frac, a in [(1.0, 0.06), (0.6, 0.10), (0.3, 0.16)]:
            ax.add_patch(Circle((s.position[0], s.position[1]), s.max_range * frac,
                                color=col, alpha=a, lw=0))
        ax.scatter([s.position[0]], [s.position[1]], marker="^", s=110, color=col,
                   edgecolor="k", zorder=5, label=f"{s.sensor_id} · {s.sensor_type} · {int(s.max_range)} m")
    ext = range_cfg.site_extent_m
    ax.set_xlim(-ext, ext); ax.set_ylim(-ext, ext); ax.set_aspect("equal")
    ax.set_xlabel("East (m)"); ax.set_ylabel("North (m)")
    ax.set_title("Sensor coverage — budget MVP suite")
    ax.legend(loc="upper right", fontsize=8)
    fig.tight_layout()
    return _save(fig, save)


def plot_detections(result, save=None):
    """Detection timeline: range-from-origin vs time, coloured by sensor."""
    set_style()
    fig, ax = plt.subplots(figsize=(9, 4.2))
    for s in result.raw.range_cfg.enabled_sensors():
        ds = [d for d in result.raw.detections if d.sensor_id == s.sensor_id]
        if not ds:
            continue
        t = [d.t_true for d in ds]
        rng = [np.linalg.norm(d.z[:2]) for d in ds]
        ax.scatter(t, rng, s=6, alpha=0.5, color=SENSOR_COLORS.get(s.sensor_type, "#555"),
                   label=s.sensor_id)
    ax.set_xlabel("time (s)"); ax.set_ylabel("ground range from origin (m)")
    ax.set_title("RAW detections by sensor")
    ax.legend(loc="upper right", ncol=4, fontsize=8)
    fig.tight_layout()
    return _save(fig, save)


# --------------------------------------------------------------------------- #
# Tracking metrics
# --------------------------------------------------------------------------- #
def plot_error_over_time(result, save=None, ax=None):
    """Position error vs time for each mode, with fault windows shaded."""
    set_style()
    own = ax is None
    fig, ax = (plt.subplots(figsize=(9, 4.0)) if own else (ax.figure, ax))
    for mode, md in result.modes.items():
        es = md.tracking.err_series
        if not es:
            continue
        t = [e[0] for e in es]; y = [e[1] for e in es]
        ax.plot(t, y, color=mode_color(mode), lw=1.4, label=MODE_LABELS.get(mode, mode))
    for f in result.config.scenario.faults:
        t0, t1 = f.get("t0"), f.get("t1")
        if t0 is not None and t1 is not None:
            ax.axvspan(t0, t1, color=PALETTE["warn"], alpha=0.12)
            ax.text((t0 + t1) / 2, ax.get_ylim()[1] * 0.95, f.get("kind", "fault"),
                    ha="center", va="top", fontsize=7, color=PALETTE["warn"])
    ax.set_xlabel("time (s)"); ax.set_ylabel("mean position error (m)")
    ax.set_title("Tracking error over time")
    ax.legend(loc="upper right")
    if own:
        fig.tight_layout()
    return _save(fig, save)


def plot_ospa_over_time(result, save=None, ax=None):
    set_style()
    own = ax is None
    fig, ax = (plt.subplots(figsize=(9, 4.0)) if own else (ax.figure, ax))
    for mode, md in result.modes.items():
        s = md.tracking.ospa_series
        if not s:
            continue
        t = np.linspace(0, result.config.scenario.duration_s, len(s))
        ax.plot(t, s, color=mode_color(mode), lw=1.3, label=MODE_LABELS.get(mode, mode))
    ax.set_xlabel("time (s)"); ax.set_ylabel("OSPA distance (m)")
    ax.set_title("OSPA over time (lower = better)")
    ax.legend(loc="upper right")
    if own:
        fig.tight_layout()
    return _save(fig, save)


def plot_track_confidence(result, mode="ust_fuse", save=None):
    """Existence-probability tracks over time (feeds ЛР-7 calibration)."""
    set_style()
    fig, ax = plt.subplots(figsize=(9, 3.8))
    md = result.modes.get(mode)
    if md:
        for trk in md.fusion.tracks:
            if not trk.history:
                continue
            t = [s.t for s in trk.history]; c = [s.confidence for s in trk.history]
            ax.plot(t, c, lw=0.8, alpha=0.6,
                    color=PALETTE["ok"] if trk.was_confirmed else PALETTE["clutter"])
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("time (s)"); ax.set_ylabel("track existence probability")
    ax.set_title(f"Track confidence — {MODE_LABELS.get(mode, mode)}\n(green=confirmed, grey=tentative)")
    fig.tight_layout()
    return _save(fig, save)


# --------------------------------------------------------------------------- #
# Detection metrics
# --------------------------------------------------------------------------- #
def plot_roc(result, save=None, ax=None):
    set_style()
    own = ax is None
    fig, ax = (plt.subplots(figsize=(5.4, 5.0)) if own else (ax.figure, ax))
    roc = result.roc
    if len(roc.get("pfa", [])):
        ax.plot(roc["pfa"], roc["pd"], color=PALETTE["accent"], lw=2, marker="o", ms=3)
    ax.plot([0, 1], [0, 1], ls="--", color="#999", lw=1)
    ax.set_xlabel("false-alarm fraction"); ax.set_ylabel("detection fraction (Pd)")
    ax.set_title("Detection ROC (SNR threshold sweep)")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
    if own:
        fig.tight_layout()
    return _save(fig, save)


def plot_pd_bars(result, save=None, ax=None):
    set_style()
    own = ax is None
    fig, ax = (plt.subplots(figsize=(6.4, 4.0)) if own else (ax.figure, ax))
    det = result.detection
    ids = list(det)
    pd = [det[s]["pd_empirical"] for s in ids]
    cols = [SENSOR_COLORS.get(det[s]["sensor_type"], "#555") for s in ids]
    ax.bar(ids, pd, color=cols)
    for i, v in enumerate(pd):
        ax.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)
    ax.set_ylim(0, 1.1); ax.set_ylabel("empirical Pd")
    ax.set_title("Per-sensor detection probability")
    if own:
        fig.tight_layout()
    return _save(fig, save)


# --------------------------------------------------------------------------- #
# Calibration (ЛР-7)
# --------------------------------------------------------------------------- #
def plot_reliability_diagram(result, mode="ust_fuse", save=None, ax=None):
    set_style()
    own = ax is None
    fig, ax = (plt.subplots(figsize=(5.2, 5.0)) if own else (ax.figure, ax))
    md = result.modes.get(mode)
    cal = md.calibration if md else None
    ax.plot([0, 1], [0, 1], ls="--", color="#999", lw=1, label="perfect calibration")
    if cal and cal.bin_conf:
        conf = np.array(cal.bin_conf); acc = np.array(cal.bin_acc)
        m = ~np.isnan(acc)
        ax.plot(conf[m], acc[m], marker="o", color=mode_color(mode), lw=1.8,
                label=f"{MODE_LABELS.get(mode, mode)} (ECE={cal.ece:.3f})")
        ax.bar(conf[m], acc[m], width=0.08, alpha=0.15, color=mode_color(mode))
    ax.set_xlabel("predicted existence probability"); ax.set_ylabel("empirical accuracy")
    ax.set_title("Reliability diagram")
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02); ax.legend(loc="upper left", fontsize=8)
    if own:
        fig.tight_layout()
    return _save(fig, save)


def plot_selective_risk(result, save=None, ax=None):
    set_style()
    own = ax is None
    fig, ax = (plt.subplots(figsize=(5.6, 4.2)) if own else (ax.figure, ax))
    for mode, md in result.modes.items():
        rc = md.calibration.risk_coverage
        if not rc:
            continue
        cov = [x[0] for x in rc]; risk = [x[1] for x in rc]
        ax.plot(cov, risk, marker="o", ms=3, color=mode_color(mode),
                label=MODE_LABELS.get(mode, mode))
    ax.set_xlabel("coverage (fraction of most-confident tracks)")
    ax.set_ylabel("risk (error rate)")
    ax.set_title("Selective risk–coverage")
    ax.legend(loc="upper left", fontsize=8)
    if own:
        fig.tight_layout()
    return _save(fig, save)


# --------------------------------------------------------------------------- #
# Clock (ЛР-1)
# --------------------------------------------------------------------------- #
def plot_clock_desync(result, save=None):
    set_style()
    est = result.manifest.extra.get("clock_estimates", {})
    ids = list(est)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2))
    offs = [est[s]["offset_est_ms"] for s in ids]
    drifts = [est[s]["drift_est_ppm"] for s in ids]
    axes[0].bar(ids, offs, color=PALETTE["accent"])
    axes[0].set_ylabel("estimated clock offset (ms)")
    axes[0].set_title("Clock offset per sensor (ЛР-1)")
    axes[1].bar(ids, drifts, color=PALETTE["warn"])
    axes[1].set_ylabel("estimated drift (ppm)")
    axes[1].set_title("Clock drift per sensor")
    for ax in axes:
        ax.axhline(0, color="k", lw=0.6)
    fig.tight_layout()
    return _save(fig, save)


# --------------------------------------------------------------------------- #
# Comparison / campaign
# --------------------------------------------------------------------------- #
def plot_metric_comparison(result, metrics=None, save=None):
    """Grouped bars comparing modes on the headline tracking metrics."""
    set_style()
    metrics = metrics or ["rmse_pos", "ospa_mean", "mota", "id_switches",
                          "track_completeness", "ece"]
    modes = list(result.modes)
    fig, ax = plt.subplots(figsize=(9.5, 4.4))
    x = np.arange(len(metrics))
    w = 0.8 / max(len(modes), 1)
    for k, mode in enumerate(modes):
        summ = result.modes[mode].summary()
        vals = [summ.get(m, np.nan) for m in metrics]
        ax.bar(x + k * w, vals, w, label=MODE_LABELS.get(mode, mode),
               color=mode_color(mode))
    ax.set_xticks(x + w * (len(modes) - 1) / 2)
    ax.set_xticklabels(metrics, rotation=20, ha="right")
    ax.set_title("Reference vs Full UST-Fuse — headline metrics")
    ax.legend()
    fig.tight_layout()
    return _save(fig, save)


def plot_paired_forest(campaign, save=None):
    """Forest plot of paired mean differences with 95% CI (B − A)."""
    set_style()
    t = campaign.paired_table()
    metrics = list(t["metric"])
    diffs = t["mean_diff"].to_numpy()
    lo = t["ci_low"].to_numpy(); hi = t["ci_high"].to_numpy()
    y = np.arange(len(metrics))
    fig, ax = plt.subplots(figsize=(8.5, 0.5 * len(metrics) + 1.5))
    colors = [PALETTE["ok"] if b == "B" else PALETTE["warn"] for b in t["better"]]
    ax.errorbar(diffs, y, xerr=[diffs - lo, hi - diffs], fmt="o", color="k",
                ecolor="#888", capsize=3, ms=5)
    for i, c in enumerate(colors):
        ax.plot(diffs[i], y[i], "o", color=c, ms=8)
    ax.axvline(0, color="#999", ls="--")
    ax.set_yticks(y); ax.set_yticklabels(metrics)
    ax.set_xlabel("paired mean difference  (UST-Fuse − Reference), 95% CI")
    ax.set_title(f"Paired comparison — {campaign.scenario_id}  (n={campaign.n_missions})")
    fig.tight_layout()
    return _save(fig, save)


def plot_campaign_box(campaign, metric="mota", save=None, ax=None):
    set_style()
    own = ax is None
    fig, ax = (plt.subplots(figsize=(5.6, 4.4)) if own else (ax.figure, ax))
    df = campaign.per_mission
    data, labels, colors = [], [], []
    for mode in df["mode"].unique():
        data.append(df[df["mode"] == mode][metric].dropna().to_numpy())
        labels.append(MODE_LABELS.get(mode, mode))
        colors.append(mode_color(mode))
    bp = ax.boxplot(data, patch_artist=True, showmeans=True)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels)
    for patch, c in zip(bp["boxes"], colors):
        patch.set_facecolor(c); patch.set_alpha(0.5)
    ax.set_ylabel(metric)
    ax.set_title(f"{metric} across {campaign.n_missions} missions")
    if own:
        fig.tight_layout()
    return _save(fig, save)


def plot_scenario_heatmap(matrix_df, metric="mota", save=None):
    """Heatmap of a metric across scenarios (rows) × modes (cols)."""
    set_style()
    piv = matrix_df.pivot_table(index="scn", columns="mode", values=metric)
    fig, ax = plt.subplots(figsize=(5.6, 0.5 * len(piv) + 1.6))
    im = ax.imshow(piv.to_numpy(), aspect="auto", cmap="viridis")
    ax.set_xticks(range(len(piv.columns)))
    ax.set_xticklabels([MODE_LABELS.get(c, c) for c in piv.columns], rotation=15, ha="right")
    ax.set_yticks(range(len(piv.index)))
    ax.set_yticklabels(piv.index, fontsize=8)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.to_numpy()[i, j]
            ax.text(j, i, f"{v:.2f}", ha="center", va="center", color="w", fontsize=8)
    ax.set_title(f"{metric} by scenario × mode")
    fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    fig.tight_layout()
    return _save(fig, save)


def plot_fault_timeline(result, save=None):
    """Gantt-style timeline of injected faults / red-team events."""
    set_style()
    faults = result.config.scenario.faults
    fig, ax = plt.subplots(figsize=(9, max(1.6, 0.5 * len(faults) + 1)))
    if not faults:
        ax.text(0.5, 0.5, "no faults injected in this scenario",
                ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        return _save(fig, save)
    for i, f in enumerate(faults):
        t0 = f.get("t0", 0.0); t1 = f.get("t1", result.config.scenario.duration_s)
        ax.barh(i, t1 - t0, left=t0, color=PALETTE["warn"], alpha=0.7)
        ax.text(t0, i, f" {f.get('kind')} ({f.get('sensor', '*')})", va="center", fontsize=8)
    ax.set_yticks(range(len(faults)))
    ax.set_yticklabels([f.get("kind") for f in faults])
    ax.set_xlabel("time (s)")
    ax.set_xlim(0, result.config.scenario.duration_s)
    ax.set_title("Fault / red-team timeline (ЛР-5)")
    fig.tight_layout()
    return _save(fig, save)
