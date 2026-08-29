"""Figures for the engineering report.

Every figure is produced from the pipeline's own outputs; none is drawn by hand
and none is illustrative. Where a figure shows rehearsal data, its title says so,
because a plot is the easiest place for a synthetic number to be mistaken for a
measurement.

House style: one accent colour per semantic role rather than per series index,
grey for context, direct labelling in preference to legends where a legend would
force the reader to look away from the mark.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Dict, List

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Polygon as MplPolygon

from . import geometry, timebase as tb, trialdesign
from .config import Config

INK = "#1c1c1e"
MUTED = "#8a8a8e"
GRID = "#e3e3e6"
ACCENT = "#0f6fc5"        # primary / measured
WARN = "#c2410c"          # failure, exceedance, hazard
GOOD = "#12805c"          # pass, ground truth
ALT = "#7c3aed"           # secondary series
SAND = "#b08900"

plt.rcParams.update({
    "figure.dpi": 170, "savefig.dpi": 170, "font.size": 8.5,
    "axes.edgecolor": MUTED, "axes.labelcolor": INK, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.titlesize": 9.5,
    "axes.titleweight": "bold", "axes.grid": True, "grid.color": GRID,
    "grid.linewidth": 0.6, "axes.axisbelow": True, "legend.frameon": False,
    "figure.facecolor": "white", "axes.facecolor": "white",
})


def _finish(fig, path: Path) -> Path:
    for ax in fig.axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, bbox_inches="tight")
    plt.close(fig)
    return path


# --------------------------------------------------------------------------- #
# 1. Pipeline architecture
# --------------------------------------------------------------------------- #
def fig_architecture(path: Path) -> Path:
    """The ten pipeline stages, the four source families, and the two tiers."""
    fig, ax = plt.subplots(figsize=(7.4, 3.6))
    ax.set_axis_off()
    ax.set_xlim(0, 100); ax.set_ylim(0, 52)

    sources = [("S1 takeoff\nindication", GOOD), ("S2 public\nwarning", SAND),
               ("S3 mobile\nreport", ALT), ("S4 visual /\nacoustic", ACCENT)]
    for i, (name, col) in enumerate(sources):
        y = 42 - i * 10
        ax.add_patch(plt.Rectangle((1, y - 3.4), 16, 7.2, facecolor=col, alpha=0.12,
                                   edgecolor=col, linewidth=1.1))
        ax.text(9, y, name, ha="center", va="center", fontsize=7.4, color=INK)
        ax.annotate("", xy=(21, 26), xytext=(17.4, y),
                    arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8))

    stages = ["ingest", "window", "associate\nEq. (3)", "label\nEq. (1)(2)",
              "adjudicate", "privacy", "validate\nEq. (4)(5)", "split", "package"]
    for i, s in enumerate(stages):
        x = 21 + i * 8.3
        ax.add_patch(plt.Rectangle((x, 22), 7.3, 8.4, facecolor="white",
                                   edgecolor=ACCENT, linewidth=1.1))
        ax.text(x + 3.65, 26.2, s, ha="center", va="center", fontsize=6.6, color=INK)
        if i < len(stages) - 1:
            ax.annotate("", xy=(x + 8.3, 26.2), xytext=(x + 7.3, 26.2),
                        arrowprops=dict(arrowstyle="->", color=MUTED, lw=0.8))

    ax.add_patch(plt.Rectangle((78, 6), 20, 8, facecolor=GOOD, alpha=0.12,
                               edgecolor=GOOD, linewidth=1.1))
    ax.text(88, 10, "open tier\nsanitized + manifests", ha="center", va="center",
            fontsize=7, color=INK)
    ax.add_patch(plt.Rectangle((78, 38), 20, 8, facecolor=WARN, alpha=0.12,
                               edgecolor=WARN, linewidth=1.1))
    ax.text(88, 42, "controlled tier\nraw + audit trail", ha="center", va="center",
            fontsize=7, color=INK)
    ax.annotate("", xy=(88, 14), xytext=(88, 22), arrowprops=dict(
        arrowstyle="<-", color=MUTED, lw=0.8))
    ax.annotate("", xy=(88, 38), xytext=(88, 30.4), arrowprops=dict(
        arrowstyle="<-", color=MUTED, lw=0.8))
    ax.text(50, 48, "Every stage writes a PROV-O activity; every released file "
                    "carries a SHA-256 digest",
            ha="center", fontsize=7, color=MUTED, style="italic")
    ax.text(50, 16.5, "release gates decide: repair | exclude | metadata-only | "
                      "controlled access",
            ha="center", fontsize=7, color=MUTED, style="italic")
    return _finish(fig, path)


# --------------------------------------------------------------------------- #
# 2. Equations 1 and 2 on a single event
# --------------------------------------------------------------------------- #
def fig_kinematics(kin: dict, cfg: Config, path: Path) -> Path:
    """Boundary distance, the epsilon dead-band, direction labels, warning time."""
    zone = geometry.WarningZone.from_config(cfg)
    t, d, sd = kin["t_s"], kin["d_m"], kin["signed_d_m"]
    eps, dt = cfg.epsilon_m, cfg.delta_t_s
    direction = kin["direction"]
    t_cross = kin["t_cross_s"]

    fig = plt.figure(figsize=(9.2, 3.2))
    gs = fig.add_gridspec(1, 3, width_ratios=[0.95, 1.45, 1.0], wspace=0.42)

    ax0 = fig.add_subplot(gs[0])
    ax0.add_patch(MplPolygon(zone.polygon / 1000.0, closed=True, facecolor=WARN,
                             alpha=0.10, edgecolor=WARN, lw=1.2))
    ax0.plot(kin["xy"][:, 0] / 1000.0, kin["xy"][:, 1] / 1000.0, color=ACCENT, lw=1.4)
    ax0.plot(kin["xy"][0, 0] / 1000.0, kin["xy"][0, 1] / 1000.0, "o", color=ACCENT, ms=4)
    ax0.set_xlabel("east (km)"); ax0.set_ylabel("north (km)")
    ax0.set_title("(a) track and zone", loc="left")
    ax0.set_aspect("equal")

    ax1 = fig.add_subplot(gs[1])
    ax1.plot(t, d, color=INK, lw=1.4, label="d(t), Eq. (1)")
    colours = {"approaching": WARN, "receding": GOOD,
               "lateral_stationary": MUTED, "uncertain": "#c9c9cf"}
    for lab, col in colours.items():
        m = np.array([x == lab for x in direction])
        if m.any():
            ax1.scatter(t[m], d[m], s=4, color=col, label=lab, zorder=3)
    if t_cross is not None:
        ax1.axvline(t_cross, color=ALT, lw=1.0, ls="--")
        ax1.annotate("$t_{cross}$", xy=(t_cross, 0), xytext=(6, 26),
                     textcoords="offset points", color=ALT, fontsize=7.5)
    ax1.axhline(0, color=WARN, lw=0.9)
    ax1.set_xlabel("time since track start (s)")
    ax1.set_ylabel("distance to boundary (m)")
    ax1.set_title(f"(b) $d(t)$ and direction, $\\varepsilon$={eps:.2f} m, "
                  f"$\\Delta t$={dt:g} s", loc="left", fontsize=8.5)
    ax1.legend(fontsize=6.0, ncol=1, loc="upper right", handletextpad=0.3,
               borderpad=0.2, labelspacing=0.3)

    ax2 = fig.add_subplot(gs[2])
    diff = np.full_like(d, np.nan)
    partner = np.searchsorted(t, t + dt)
    ok = partner < t.size
    diff[np.where(ok)[0]] = d[partner[ok]] - d[ok]
    ax2.plot(t, diff, color=ACCENT, lw=1.2)
    ax2.axhspan(-eps, eps, color=MUTED, alpha=0.20)
    ax2.axhline(0, color=MUTED, lw=0.7)
    ax2.text(t[-1], eps, " $+\\varepsilon$", color=INK, fontsize=6.8, va="bottom")
    ax2.text(t[-1], -eps, " $-\\varepsilon$", color=INK, fontsize=6.8, va="top")
    ax2.set_xlabel("time (s)")
    ax2.set_ylabel("$d(t+\\Delta t)-d(t)$  (m)")
    ax2.set_title("(c) dead-band decides the label", loc="left", fontsize=8.5)
    return _finish(fig, path)


def fig_epsilon_sensitivity(kinematics: Dict[str, dict], cfg: Config,
                            path: Path) -> Path:
    """How the direction mix moves as epsilon sweeps through its uncertainty floor."""
    ks = np.linspace(0.5, 8.0, 22)
    sigma = float(cfg["kinematics"]["groundtruth_sigma_h_m"])
    dt = cfg.delta_t_s
    shares = {"approaching": [], "receding": [], "lateral_stationary": [], "uncertain": []}
    sample = list(kinematics.values())[:40]
    for k in ks:
        eps = k * math.sqrt(2.0) * sigma
        counts = {key: 0 for key in shares}
        total = 0
        for kin in sample:
            lab = geometry.direction_labels(kin["t_s"], kin["d_m"], dt, eps)
            for x in lab:
                counts[str(x)] = counts.get(str(x), 0) + 1
                total += 1
        for key in shares:
            shares[key].append(counts[key] / max(total, 1))

    fig, ax = plt.subplots(figsize=(4.6, 2.9))
    for key, col in (("approaching", WARN), ("receding", GOOD),
                     ("lateral_stationary", MUTED), ("uncertain", "#c9c9cf")):
        ax.plot(ks, shares[key], color=col, lw=1.5, label=key)
    ax.axvline(float(cfg["kinematics"]["epsilon_sigma_multiplier"]), color=ALT,
               ls="--", lw=1.0)
    ax.text(float(cfg["kinematics"]["epsilon_sigma_multiplier"]), 0.92,
            " configured k", color=ALT, fontsize=7)
    ax.set_xlabel("k  in  $\\varepsilon = k\\sqrt{2}\\,\\sigma_h$")
    ax.set_ylabel("share of samples")
    ax.set_title("direction mix vs the dead-band multiplier", loc="left")
    ax.legend(fontsize=6.6, ncol=2)
    return _finish(fig, path)


# --------------------------------------------------------------------------- #
# 3. Synchronization
# --------------------------------------------------------------------------- #
def fig_sync(sync: pd.DataFrame, observations: pd.DataFrame, cfg: Config,
             path: Path) -> Path:
    tol = float(cfg["synchronization"]["sync_tolerance_ms"])
    meas = sync[(sync.modality != "ALL") & (sync["n"] > 0)]
    unmeas = sync[(sync.modality != "ALL") & (sync["n"] == 0)]

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(8.4, 2.9),
                                   gridspec_kw={"width_ratios": [1.5, 1.0]})
    data, labels = [], []
    for m in meas["modality"]:
        e = observations[observations["modality"] == m]["sync_error_ns"].dropna()
        if len(e):
            data.append(np.asarray(e, dtype=float) / 1e6)
            labels.append(m)
    if data:
        bp = ax0.boxplot(data, vert=False, tick_labels=labels, widths=0.55,
                         showfliers=True, patch_artist=True,
                         flierprops=dict(marker=".", markersize=2.4,
                                         markerfacecolor=MUTED, markeredgecolor="none"))
        for b in bp["boxes"]:
            b.set(facecolor=ACCENT, alpha=0.22, edgecolor=ACCENT, linewidth=1.0)
        for med in bp["medians"]:
            med.set(color=INK, linewidth=1.2)
    ax0.axvline(tol, color=WARN, lw=1.1, ls="--")
    ax0.text(tol, ax0.get_ylim()[1], f" tolerance {tol:g} ms", color=WARN,
             fontsize=7, va="top")
    ax0.set_xscale("log")
    ax0.set_xlabel("$\\delta t$ = $|t_m - t_r|$  (ms, log scale)")
    ax0.set_title("(a) Eq. (3) on synchronization markers", loc="left")

    if len(unmeas):
        y = np.arange(len(unmeas))
        vals = unmeas["declared_sigma_ms"].to_numpy(dtype=float)
        # A bar on a log axis has no meaningful baseline, so the declared sigma is
        # shown as a point on a stem anchored at the measured p95 of the
        # disciplined sources - which is the scale the reader should compare it to.
        anchor = float(meas["p95_ms"].max()) if len(meas) else 1.0
        ax1.hlines(y, anchor, vals, color=SAND, lw=1.6, alpha=0.7)
        ax1.scatter(vals, y, s=34, color=SAND, zorder=3)
        ax1.axvline(anchor, color=ACCENT, lw=1.0, ls="--")
        ax1.text(anchor, len(unmeas) - 0.35,
                 f" measured p95\n {anchor:.0f} ms", color=ACCENT, fontsize=6.6,
                 va="top")
        ax1.set_yticks(y); ax1.set_yticklabels(unmeas["modality"], fontsize=7.5)
        ax1.set_ylim(-0.6, len(unmeas) - 0.2)
        ax1.set_xscale("log")
        ax1.set_xticks([100, 1000, 10000, 100000])
        ax1.set_xticklabels(["0.1 s", "1 s", "10 s", "100 s"], fontsize=7)
        ax1.set_xlim(anchor * 0.6, float(vals.max()) * 3)
        for i, (v, n) in enumerate(zip(vals, unmeas["n_not_measurable"])):
            ax1.text(v * 1.25, i, f"n={int(n)}", va="center", fontsize=6.8, color=MUTED)
    ax1.set_xlabel("declared 1$\\sigma$ clock uncertainty (log scale)")
    ax1.set_title("(b) asynchronous sources: not measurable", loc="left")
    return _finish(fig, path)


def fig_association(diag: pd.DataFrame, path: Path) -> Path:
    """Association outcome and how decisive each association was."""
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.0, 2.7))
    tab = (diag.groupby(["modality", "reason"]).size().unstack(fill_value=0))
    order = [c for c in ("associated", "overlap_below_minimum", "no_window_overlap")
             if c in tab.columns]
    cols = {"associated": GOOD, "overlap_below_minimum": SAND,
            "no_window_overlap": WARN}
    bottom = np.zeros(len(tab))
    for c in order:
        ax0.bar(tab.index, tab[c], bottom=bottom, color=cols[c], alpha=0.8, label=c)
        bottom += tab[c].to_numpy()
    ax0.set_ylabel("observations")
    ax0.set_title("association outcome by modality", loc="left")
    ax0.legend(fontsize=6.4)
    ax0.tick_params(axis="x", rotation=30)
    for lab in ax0.get_xticklabels():
        lab.set_ha("right")

    ok = diag[diag["associated"]]
    ax1.hist(ok["decisiveness"], bins=24, color=ACCENT, alpha=0.75)
    ax1.set_xlabel("decisiveness  (best - runner-up) / best overlap")
    ax1.set_ylabel("observations")
    ax1.set_title("how clear-cut the winning window was", loc="left")
    return _finish(fig, path)


# --------------------------------------------------------------------------- #
# 4. Quality
# --------------------------------------------------------------------------- #
def fig_completeness(open_tables: Dict[str, pd.DataFrame], path: Path) -> Path:
    from . import schema, validation
    fig, ax = plt.subplots(figsize=(5.2, 2.9))
    for i, (name, table) in enumerate(schema.TABLES.items()):
        if name not in open_tables or open_tables[name].empty:
            continue
        c = validation.record_completeness(open_tables[name], table)
        ax.scatter(np.full(len(c), i) + np.random.default_rng(i).normal(0, 0.06, len(c)),
                   c, s=3, alpha=0.35, color=ACCENT)
        ax.plot([i - 0.28, i + 0.28], [np.median(c)] * 2, color=INK, lw=1.6)
    ax.set_xticks(range(len(schema.TABLES)))
    ax.set_xticklabels(list(schema.TABLES), rotation=30, ha="right", fontsize=7)
    ax.set_ylabel("$C_i$, Eq. (4)")
    ax.set_ylim(0, 1.04)
    ax.set_title("record completeness against the declared required-field set", loc="left")
    return _finish(fig, path)


def fig_missingness(miss: pd.DataFrame, path: Path) -> Path:
    piv = miss.pivot_table(index="field", columns="modality", values="missing_rate")
    piv = piv.loc[piv.max(axis=1).sort_values(ascending=False).index]
    piv = piv.head(16)
    fig, ax = plt.subplots(figsize=(6.4, 4.0))
    im = ax.imshow(piv.to_numpy(), cmap="RdYlGn_r", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(len(piv.columns)))
    ax.set_xticklabels(piv.columns, rotation=30, ha="right", fontsize=7)
    ax.set_yticks(range(len(piv.index)))
    ax.set_yticklabels(piv.index, fontsize=7)
    for i in range(piv.shape[0]):
        for j in range(piv.shape[1]):
            v = piv.iat[i, j]
            if np.isfinite(v) and v > 0.005:
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=5.8,
                        color="white" if v > 0.55 else INK)
    ax.grid(False)
    fig.colorbar(im, ax=ax, shrink=0.7, label="missing rate")
    ax.set_title("missingness by field and modality", loc="left")
    return _finish(fig, path)


def fig_media_quality(media: pd.DataFrame, cfg: Config, path: Path) -> Path:
    """Measured SNR and target extent against range, with the design thresholds."""
    ac = cfg["detectability"]["acoustic"]
    gain = float(ac.get("detector_processing_gain_db", 0.0))
    thr_in = float(ac["detection_snr_db"]) - gain
    min_px = float(cfg["detectability"]["visual"]["detection_min_px"])

    aud_all = media[(media.media_type == "audio") & media["_slant_range_m"].notna()]
    aud = aud_all[aud_all["snr_db"].notna()]
    n_sat = int(len(aud_all) - len(aud))
    vis = media[(media.media_type != "audio") & media["_slant_range_m"].notna()]

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.4, 2.9))
    ax0.scatter(aud["_slant_range_m"], aud["snr_db"], s=6, alpha=0.45, color=ACCENT,
                label="measured")
    ax0.scatter(aud["_slant_range_m"], aud["_predicted_snr_db"], s=5, alpha=0.35,
                color=MUTED, label="predicted")
    ax0.axhline(thr_in, color=WARN, lw=1.1, ls="--")
    ax0.text(ax0.get_xlim()[1], thr_in, f"detector threshold {thr_in:.0f} dB ",
             ha="right", va="bottom", color=WARN, fontsize=6.8)
    floors = aud_all["snr_estimator_floor_db"].dropna()
    if len(floors):
        fl = float(floors.median())
        ax0.axhspan(ax0.get_ylim()[0], fl, color=MUTED, alpha=0.16)
        ax0.text(ax0.get_xlim()[0], fl, f" median estimator floor {fl:.0f} dB"
                 + (f" - {n_sat} saturated" if n_sat else ""),
                 va="top", color=MUTED, fontsize=6.6)
    ax0.set_xscale("log"); ax0.set_xlabel("sensor-to-target slant range (m)")
    ax0.set_ylabel("in-band SNR (dB)")
    ax0.set_title("acoustic: measured vs predicted", loc="left")
    ax0.legend(fontsize=6.6)

    ax1.scatter(vis["_slant_range_m"], vis["target_px"], s=6, alpha=0.45, color=ACCENT,
                label="measured")
    ax1.scatter(vis["_slant_range_m"], vis["_predicted_target_px"], s=5, alpha=0.35,
                color=MUTED, label="predicted")
    ax1.axhline(min_px, color=WARN, lw=1.1, ls="--")
    ax1.text(ax1.get_xlim()[1], min_px, f"detection floor {min_px:g} px ",
             ha="right", va="bottom", color=WARN, fontsize=6.8)
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.set_xlabel("sensor-to-target slant range (m)")
    ax1.set_ylabel("apparent target extent (px)")
    ax1.set_title("visual: measured vs predicted", loc="left")
    ax1.legend(fontsize=6.6)
    return _finish(fig, path)


def fig_agreement(agree: pd.DataFrame, units_confusion: pd.DataFrame,
                  cfg: Config, path: Path) -> Path:
    floor = float(cfg["quality_gates"]["krippendorff_alpha_min"])
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.0, 2.8),
                                   gridspec_kw={"width_ratios": [1.0, 1.2]})
    y = np.arange(len(agree))
    ax0.barh(y, agree["krippendorff_alpha"], color=ACCENT, alpha=0.7, height=0.45)
    ax0.errorbar(agree["krippendorff_alpha"], y,
                 xerr=[agree["krippendorff_alpha"] - agree["alpha_ci_low"],
                       agree["alpha_ci_high"] - agree["krippendorff_alpha"]],
                 fmt="none", ecolor=INK, elinewidth=1.0, capsize=3)
    ax0.axvline(floor, color=WARN, lw=1.1, ls="--")
    ax0.text(floor, len(agree) - 0.4, f" gate {floor}", color=WARN, fontsize=7)
    ax0.set_yticks(y); ax0.set_yticklabels(agree["target_name"], fontsize=7.5)
    ax0.set_xlabel("Krippendorff's $\\alpha$  (95 % bootstrap)")
    ax0.set_title("agreement with interval", loc="left")

    if units_confusion is not None and not units_confusion.empty:
        m = units_confusion.to_numpy(dtype=float)
        m = m / np.maximum(m.sum(axis=1, keepdims=True), 1)
        im = ax1.imshow(m, cmap="Blues", vmin=0, vmax=1)
        ax1.set_xticks(range(m.shape[1]))
        ax1.set_xticklabels(units_confusion.columns, rotation=25, ha="right", fontsize=7)
        ax1.set_yticks(range(m.shape[0]))
        ax1.set_yticklabels(units_confusion.index, fontsize=7)
        for i in range(m.shape[0]):
            for j in range(m.shape[1]):
                ax1.text(j, i, f"{m[i, j]:.2f}", ha="center", va="center", fontsize=6.4,
                         color="white" if m[i, j] > 0.55 else INK)
        ax1.grid(False)
        ax1.set_xlabel("reported"); ax1.set_ylabel("ground truth")
    ax1.set_title("cross-modal direction confusion", loc="left")
    return _finish(fig, path)


# --------------------------------------------------------------------------- #
# 5. Splits, coverage, and gates
# --------------------------------------------------------------------------- #
def fig_splits(manifests: Dict[str, pd.DataFrame], audit: pd.DataFrame,
               path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(7.2, 3.0))
    names = list(manifests)
    cols = {"train": ACCENT, "val": SAND, "test": GOOD,
            "embargo": MUTED, "ambiguous": "#c9c9cf", "duplicate_conflict": WARN}
    bottom = np.zeros(len(names))
    for key, col in cols.items():
        vals = np.array([int((manifests[n]["partition"] == key).sum()) for n in names])
        if vals.sum() == 0:
            continue
        ax.bar(names, vals, bottom=bottom, color=col, alpha=0.85, label=key)
        bottom += vals
    ax.set_ylabel("events")
    ax.tick_params(axis="x", rotation=20)
    for lab in ax.get_xticklabels():
        lab.set_ha("right")
    ax.set_ylim(0, bottom.max() * 1.30)
    ax.legend(fontsize=6.4, ncol=6, loc="upper center",
              bbox_to_anchor=(0.5, 1.02), columnspacing=1.0, handlelength=1.2)
    ax.set_title("evaluation manifests: composition and what each excludes",
                 loc="left")
    for i, n in enumerate(names):
        row = audit[audit["manifest"] == n]
        if len(row) and row["status"].iloc[0] != "pass":
            ax.text(i, bottom[i] * 1.02, "FAIL", ha="center", color=WARN, fontsize=7,
                    weight="bold")
    return _finish(fig, path)


def fig_coverage(events: pd.DataFrame, kinematics: Dict[str, dict],
                 cfg: Config, path: Path) -> Path:
    """Flight-matrix coverage: which design cells the corpus actually populates."""
    rows = []
    for eid, k in kinematics.items():
        rows.append({"platform_class": k["platform_class"],
                     "approach_geometry": k["approach_geometry"],
                     "speed_band": k["speed_band"]})
    df = pd.DataFrame(rows)
    if df.empty:
        fig, ax = plt.subplots(figsize=(5, 2.5)); ax.set_axis_off()
        return _finish(fig, path)
    piv = df.pivot_table(index="platform_class",
                         columns=["approach_geometry", "speed_band"],
                         aggfunc="size", fill_value=0)
    fig, ax = plt.subplots(figsize=(7.4, 2.6))
    m = piv.to_numpy(dtype=float)
    im = ax.imshow(m, cmap="YlGnBu", aspect="auto", vmin=0)
    ax.set_yticks(range(piv.shape[0])); ax.set_yticklabels(piv.index, fontsize=7)
    ax.set_xticks(range(piv.shape[1]))
    ax.set_xticklabels([f"{a}\n{b}" for a, b in piv.columns], fontsize=5.6)
    for i in range(m.shape[0]):
        for j in range(m.shape[1]):
            ax.text(j, i, int(m[i, j]), ha="center", va="center", fontsize=6,
                    color="white" if m[i, j] > m.max() * 0.6 else INK)
    ax.grid(False)
    n_empty = int((m == 0).sum())
    ax.set_title(f"flight-matrix coverage - {n_empty} of {m.size} cells empty",
                 loc="left")
    fig.colorbar(im, ax=ax, shrink=0.8, label="runs")
    return _finish(fig, path)


def fig_gates(gates: pd.DataFrame, path: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6.0, 3.2))
    y = np.arange(len(gates))[::-1]
    colors = [GOOD if s == "pass" else (WARN if s == "FAIL" else MUTED)
              for s in gates["status"]]
    ax.barh(y, [1] * len(gates), color=colors, alpha=0.22, height=0.7)
    for i, (_, r) in zip(y, gates.iterrows()):
        ax.text(0.02, i, r["gate"], va="center", fontsize=7.4, color=INK)
        obs = r["observed"]
        txt = "-" if obs is None else (f"{obs:.4g}" if isinstance(obs, float) else str(obs))
        ax.text(0.62, i, f"{txt}   {r['rule']}", va="center", fontsize=7, color=MUTED)
        ax.text(0.98, i, r["status"], va="center", ha="right", fontsize=7.4,
                color=GOOD if r["status"] == "pass" else
                (WARN if r["status"] == "FAIL" else MUTED), weight="bold")
    ax.set_xlim(0, 1); ax.set_ylim(-0.6, len(gates) - 0.4)
    ax.set_axis_off()
    ax.set_title("release gates on the rehearsal corpus", loc="left")
    return _finish(fig, path)


# --------------------------------------------------------------------------- #
# 6. Field-trial planning
# --------------------------------------------------------------------------- #
def fig_detection_curves(cfg: Config, path: Path) -> Path:
    """Detection range against range, per modality, with the design thresholds."""
    det = cfg["detectability"]
    ac, vi = det["acoustic"], det["visual"]
    gain = float(ac.get("detector_processing_gain_db", 0.0))
    f_px = trialdesign.focal_length_px(vi["sensor_width_px"], vi["horizontal_fov_deg"])
    r = np.geomspace(10, 5000, 300)

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.4, 2.9))
    for (env, amb), col in zip(ac["ambient_noise_db"].items(),
                               (GOOD, ACCENT, SAND, WARN)):
        snr = trialdesign.acoustic_snr_db(
            r, ac["source_level_db_at_ref"]["multirotor_small"], amb,
            ac["atmospheric_absorption_db_per_m"]) + gain
        ax0.plot(r, snr, color=col, lw=1.4, label=f"{env} ({amb:.0f} dB)")
    ax0.axhline(ac["detection_snr_db"], color=INK, ls="--", lw=1.0)
    ax0.text(11, ac["detection_snr_db"], f" detection {ac['detection_snr_db']:g} dB",
             fontsize=6.8, va="bottom", color=INK)
    ax0.set_xscale("log"); ax0.set_xlabel("range (m)")
    ax0.set_ylabel("post-gain SNR (dB)")
    ax0.set_ylim(-30, 90)
    ax0.set_title("acoustic, multirotor_small", loc="left")
    ax0.legend(fontsize=6.2)

    for (platform, span), col in zip(vi["target_span_m"].items(),
                                     (GOOD, ACCENT, SAND, ALT)):
        ax1.plot(r, trialdesign.apparent_size_px(r, span, f_px), color=col, lw=1.4,
                 label=platform)
    ax1.axhline(vi["detection_min_px"], color=INK, ls="--", lw=1.0)
    ax1.axhline(vi["recognition_min_px"], color=MUTED, ls=":", lw=1.0)
    ax1.text(11, vi["detection_min_px"], " detection", fontsize=6.8, va="bottom")
    ax1.text(11, vi["recognition_min_px"], " recognition", fontsize=6.8, va="bottom",
             color=MUTED)
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.set_xlabel("range (m)"); ax1.set_ylabel("apparent extent (px)")
    ax1.set_title(f"visual, {vi['horizontal_fov_deg']:g}$\\degree$ HFOV, "
                  f"{vi['sensor_width_px']} px", loc="left")
    ax1.legend(fontsize=6.2)
    return _finish(fig, path)


def fig_warning_budget(cfg: Config, path: Path) -> Path:
    """Where the lead time goes, and the range each closing speed demands.

    The left panel separates the modalities deliberately. Plotting only the fused
    range hides the finding that matters: visual range does not depend on ambient
    noise, so a fused curve looks flat across environments and suggests the
    acoustic channel is irrelevant. It is not - it is the channel that degrades,
    and in an urban environment it degrades to the point of contributing nothing.
    """
    ft = cfg["field_trial"]
    det = cfg["detectability"]
    ac, vi = det["acoustic"], det["visual"]
    platform = "multirotor_small"
    v = det["kinematics_planning"]["closing_speed_ms"]["nominal"]
    required = ft["required_actionable_lead_s"]
    overhead = ft["decision_latency_s"] + ft["dissemination_latency_s"]

    f_px = trialdesign.focal_length_px(vi["sensor_width_px"], vi["horizontal_fov_deg"])
    r_vis = trialdesign.visual_range_m(vi["target_span_m"][platform], f_px,
                                       vi["detection_min_px"])

    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(8.6, 3.0))
    envs = list(ac["ambient_noise_db"])
    x = np.arange(len(envs))
    width = 0.26
    series = []
    for env in envs:
        r_ac = trialdesign.acoustic_detection_range_m(
            ac["source_level_db_at_ref"][platform], ac["ambient_noise_db"][env],
            ac["atmospheric_absorption_db_per_m"], ac["detection_snr_db"],
            processing_gain_db=ac.get("detector_processing_gain_db", 0.0))
        series.append((r_ac / v - overhead, r_vis / v - overhead,
                       max(r_ac, r_vis) / v - overhead))
    for i, (label, col) in enumerate((("acoustic only", SAND),
                                      ("visual only", ALT),
                                      ("fused", ACCENT))):
        vals = [row[i] for row in series]
        ax0.bar(x + (i - 1) * width, vals, width, color=col, alpha=0.8, label=label)
    ax0.axhline(required, color=WARN, lw=1.2, ls="--")
    ax0.text(len(envs) - 0.5, required, f" required {required:g} s", color=WARN,
             fontsize=6.8, va="bottom", ha="right")
    ax0.set_xticks(x)
    ax0.set_xticklabels([f"{e}\n{ac['ambient_noise_db'][e]:.0f} dB" for e in envs],
                        fontsize=6.8)
    ax0.set_ylabel("actionable lead time (s)")
    ax0.set_title(f"(a) {platform} at {v:g} m/s", loc="left")
    ax0.legend(fontsize=6.4)

    vv = np.linspace(5, 35, 200)
    req = trialdesign.required_detection_range_m(
        vv, required, ft["decision_latency_s"], ft["dissemination_latency_s"])
    ax1.plot(vv, req, color=INK, lw=1.8, label="required range $r_{req}$")
    ax1.axhline(r_vis, color=ALT, lw=1.3)
    ax1.text(5.4, r_vis, " visual", fontsize=6.8, color=ALT, va="bottom")
    for (env, amb), col, dy in zip(ac["ambient_noise_db"].items(),
                                   (GOOD, ACCENT, SAND, WARN), (0, 0, 0, 0)):
        r = trialdesign.acoustic_detection_range_m(
            ac["source_level_db_at_ref"][platform], amb,
            ac["atmospheric_absorption_db_per_m"], ac["detection_snr_db"],
            processing_gain_db=ac.get("detector_processing_gain_db", 0.0))
        ax1.axhline(r, color=col, lw=1.0, ls=":")
        ax1.text(35, r, f"{env} ", fontsize=6.2, color=col, va="bottom", ha="right")
    ax1.set_xlabel("closing speed $v$ (m/s)")
    ax1.set_ylabel("range (m)")
    ax1.set_ylim(0, max(r_vis, float(req.max())) * 1.12)
    ax1.set_title("(b) $r_{req}=v\\,(T_{req}+T_{dec}+T_{dis})$ vs achievable",
                  loc="left")
    ax1.legend(fontsize=6.4, loc="upper left")
    return _finish(fig, path)


def fig_sample_size(cfg: Config, path: Path) -> Path:
    """Runs per cell against the effect size the trial must resolve."""
    ft = cfg["field_trial"]
    p1s = np.linspace(0.80, 0.98, 60)
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.4, 2.9))
    for p0, col in ((0.70, GOOD), (0.75, ACCENT), (0.80, SAND), (0.85, WARN)):
        n = []
        for p1 in p1s:
            if p1 <= p0 + 1e-6:
                n.append(np.nan); continue
            n.append(trialdesign.sample_size_one_proportion(
                p0, float(p1), ft["alpha"], ft["power"]))
        ax0.plot(p1s, n, color=col, lw=1.5, label=f"$p_0$ = {p0:.2f}")
    ax0.axvline(ft["target_detection_rate"], color=INK, ls="--", lw=1.0)
    ax0.set_yscale("log")
    ax0.set_xlabel("$p_1$, detection rate to demonstrate")
    ax0.set_ylabel("runs per cell (log scale)")
    ax0.set_title(f"one-sided, $\\alpha$ = {ft['alpha']}, power = {ft['power']}",
                  loc="left")
    ax0.legend(fontsize=6.4)

    plan = trialdesign.campaign_plan(cfg)
    labels = ["full factorial", "blocked design"]
    vals = [plan["full_factorial_sorties"], plan["reduced_sorties"]]
    bars = ax1.bar(labels, vals, color=[WARN, GOOD], alpha=0.75, width=0.5)
    for b, v in zip(bars, vals):
        ax1.text(b.get_x() + b.get_width() / 2, v, f"{v:,}", ha="center",
                 va="bottom", fontsize=7.4)
    ax1.set_yscale("log")
    ax1.set_ylabel("sorties (log scale)")
    ax1.set_title(f"{plan['n_per_cell_planned']} runs/cell after "
                  f"{plan['expected_run_loss_rate']:.0%} loss allowance", loc="left")
    return _finish(fig, path)


def fig_warning_time_distribution(kinematics: Dict[str, dict], cfg: Config,
                                  path: Path) -> Path:
    """The lead time the corpus actually offers, against the operational budget."""
    ft = cfg["field_trial"]
    leads, censored = [], 0
    for k in kinematics.values():
        if k["t_cross_s"] is None:
            censored += 1
        else:
            leads.append(float(k["t_cross_s"]))
    fig, (ax0, ax1) = plt.subplots(1, 2, figsize=(7.4, 2.8))
    if leads:
        xs = np.sort(leads)
        ys = np.arange(1, len(xs) + 1) / len(xs)
        ax0.step(xs, ys, color=ACCENT, lw=1.6, where="post")
        budget = ft["decision_latency_s"] + ft["dissemination_latency_s"] + \
            ft["required_actionable_lead_s"]
        ax0.axvline(budget, color=WARN, lw=1.2, ls="--")
        ax0.text(budget, 0.06, f" total budget {budget:g} s", color=WARN, fontsize=7)
        frac = float(np.mean(np.asarray(leads) >= budget))
        ax0.text(0.98, 0.5, f"{frac:.0%} of events\nclear the budget",
                 transform=ax0.transAxes, ha="right", fontsize=7.4, color=INK)
    ax0.set_xlabel("$T(t_0) = t_{cross} - t_0$  (s)")
    ax0.set_ylabel("empirical CDF")
    ax0.set_title(f"warning time, Eq. (2); {censored} censored events", loc="left")

    speeds = [k["closing_speed_ms"] for k in kinematics.values()
              if np.isfinite(k["closing_speed_ms"])]
    ax1.hist(speeds, bins=22, color=ALT, alpha=0.7)
    ax1.set_xlabel("peak closing rate $-\\min\\,\\dot d$  (m/s)")
    ax1.set_ylabel("events")
    ax1.set_title("closing rate drives the required range", loc="left")
    return _finish(fig, path)


def render_all(result, cfg: Config, out_dir: Path) -> Dict[str, Path]:
    """Produce every figure the report uses, and return their paths."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = result
    figs: Dict[str, Path] = {}

    figs["architecture"] = fig_architecture(out_dir / "fig01_architecture.png")

    # Pick an event that actually crosses the zone, so Eq. (2) is illustrated on a
    # track where the crossing exists rather than on a censored one.
    crossing = [k for k in r.kinematics.values() if k["t_cross_s"] is not None]
    example = max(crossing, key=lambda k: k["t_cross_s"]) if crossing \
        else list(r.kinematics.values())[0]
    figs["kinematics"] = fig_kinematics(example, cfg, out_dir / "fig02_kinematics.png")
    figs["epsilon"] = fig_epsilon_sensitivity(r.kinematics, cfg,
                                              out_dir / "fig03_epsilon.png")
    figs["sync"] = fig_sync(r.reports["sync"], r.tables["observations"], cfg,
                            out_dir / "fig04_sync.png")
    figs["association"] = fig_association(r.reports["association"],
                                          out_dir / "fig05_association.png")
    figs["completeness"] = fig_completeness(r.tables, out_dir / "fig06_completeness.png")
    figs["missingness"] = fig_missingness(r.reports["missingness"],
                                          out_dir / "fig07_missingness.png")
    figs["media_quality"] = fig_media_quality(r.reports["media_full"], cfg,
                                              out_dir / "fig08_media_quality.png")
    figs["agreement"] = fig_agreement(r.reports["agreement"],
                                      r.reports["cross_modal"]["confusion"], cfg,
                                      out_dir / "fig09_agreement.png")
    figs["splits"] = fig_splits(r.manifests, r.reports["split_audit"],
                                out_dir / "fig10_splits.png")
    figs["coverage"] = fig_coverage(r.tables["events"], r.kinematics, cfg,
                                    out_dir / "fig11_coverage.png")
    figs["gates"] = fig_gates(r.gates, out_dir / "fig12_gates.png")
    figs["detection"] = fig_detection_curves(cfg, out_dir / "fig13_detection.png")
    figs["budget"] = fig_warning_budget(cfg, out_dir / "fig14_budget.png")
    figs["sample_size"] = fig_sample_size(cfg, out_dir / "fig15_sample_size.png")
    figs["warning_time"] = fig_warning_time_distribution(
        r.kinematics, cfg, out_dir / "fig16_warning_time.png")
    return figs
