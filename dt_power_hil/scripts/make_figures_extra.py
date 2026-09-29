#!/usr/bin/env python3
"""Additional figures for the experiment-content document (fig10–fig13)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "results"
FIG = RES / "figures"
S = json.load(open(RES / "summary.json"))
SER = json.load(open(RES / "series_selected.json"))
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BLUE, ORANGE, AQUA, GREY, YEL = "#2a78d6", "#eb6834", "#1baf7a", "#8a8985", "#eda100"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "lines.linewidth": 1.5})


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def canvas(w, h, xmax=100, ymax=60):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.set_xlim(0, xmax)
    ax.set_ylim(0, ymax)
    ax.axis("off")
    return fig, ax


def box(ax, x, y, w, h, t, fc="#f4f3f0", fs=6.2, bold=False, ec=MUTED, ls="-"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.3,rounding_size=0.8", fc=fc, ec=ec, lw=0.9, ls=ls))
    ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=INK, fontweight="bold" if bold else None)


def arr(ax, x0, y0, x1, y1, c=INK, ls="-", lw=1.1, style="-|>"):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle=style, mutation_scale=8, color=c, lw=lw, ls=ls))


# ---- fig10: detailed bench wiring -------------------------------------------------
def fig_wiring():
    fig, ax = canvas(10.5, 6.2, 102, 62)
    PW, SG = "#c23b3b", "#2a78d6"
    # power path, generation
    box(ax, 0.5, 50, 10, 7, "Mean Well\nRSP-750-48\n230 V AC→48 V", "#efeee9")
    box(ax, 13, 50, 10, 7, "RIDEN RD6018\nCV 14.2 V\nCC = P_avail/V", "#dbe8fa")
    box(ax, 25.5, 50, 8, 7, "LTC4359\nideal diode", "#efeee9")
    box(ax, 36, 51, 6, 5, "ATO\n25 A", "#fbecc8")
    box(ax, 44.5, 51, 7, 5, "M0\nFL-2 30 A\nINA226", "#fde4d8", fs=6)
    for a, b in ((10.5, 13), (23, 25.5), (33.5, 36), (42, 44.5)):
        arr(ax, a, 53.5, b, 53.5, c=PW)
    # bus
    ax.add_patch(FancyBboxPatch((54, 8), 4.5, 50, boxstyle="round,pad=0.2", fc="#e8e7e3", ec=INK, lw=1.2))
    ax.text(56.25, 33, "DC BUS  10.0–14.6 V", rotation=90, ha="center", va="center", fontsize=7.5, fontweight="bold")
    arr(ax, 51.5, 53.5, 54, 53.5, c=PW)
    # battery branch
    box(ax, 0.5, 30, 12, 9, "LiFePO₄ 4S\n12.8 V / 40 Ah\n+ DALY BMS 40 A", "#dbe8fa")
    box(ax, 15, 31.5, 7, 6, "MIDI\n40 A", "#fbecc8")
    box(ax, 24.5, 31.5, 8, 6, "Blue Sea\n6006\nE-stop", "#fbecc8", fs=6.3)
    box(ax, 35, 36, 8, 5, "M1  FL-2 50 A\nINA226", "#fde4d8", fs=6)
    box(ax, 35, 28, 8, 5, "REF FL-2 50 A\nINA228", "#d8f1e6", fs=6)
    for a, b in ((12.5, 15), (22, 24.5)):
        arr(ax, a, 34.5, b, 34.5, c=PW, style="<|-|>")
    ax.plot([32.5, 34, 34], [34.5, 34.5, 38.5], color=PW, lw=1.1)
    ax.plot([43, 45, 45, 43], [38.5, 38.5, 30.5, 30.5], color=PW, lw=1.1)
    ax.plot([34, 35], [30.5, 30.5], color=PW, lw=1.1)
    ax.plot([34, 34], [34.5, 30.5], color=PW, lw=1.1)
    ax.text(38.5, 42.2, "shunts in series in battery −", fontsize=5.8, color=MUTED, ha="center")
    arr(ax, 45, 34.5, 54, 34.5, c=PW, style="<|-|>")
    # critical branch
    y = 46
    box(ax, 61, y, 6, 5, "ATO\n5 A", "#fbecc8")
    box(ax, 69, y, 6, 5, "M2\nINA226", "#fde4d8", fs=6)
    box(ax, 77, y - 0.5, 8, 6, "DDR-60G-12\n9–36→12 V", "#efeee9", fs=6.2)
    box(ax, 87, y, 5, 5, "M3", "#fde4d8", fs=6)
    box(ax, 93.5, y - 3, 6.5, 11, "hAP ac²\n+\nKEL103\nCP\n18 W", "#fde4d8", fs=6)
    for a, b in ((58.5, 61), (67, 69), (75, 77), (85, 87), (92, 93.5)):
        arr(ax, a, y + 2.5, b, y + 2.5, c=PW)
    ax.text(79, y + 7.5, "CRITICAL BRANCH (never switched by EMS)", fontsize=6.2, color=MUTED, ha="center")
    # aux branch
    y = 26
    box(ax, 61, y, 6, 5, "ATO\n7.5 A", "#fbecc8")
    box(ax, 69, y - 0.5, 7, 6, "Bosch relay\n12 V/30 A NO", "#fbecc8", fs=5.8)
    box(ax, 78, y, 5, 5, "M4", "#fde4d8", fs=6)
    box(ax, 84.5, y - 0.5, 8, 6, "DDR-60G-12", "#efeee9", fs=6.2)
    box(ax, 94, y, 6, 5, "M5 →\nLED 30 W", "#fde4d8", fs=5.8)
    for a, b in ((58.5, 61), (67, 69), (76, 78), (83, 84.5), (92.5, 94)):
        arr(ax, a, y + 2.5, b, y + 2.5, c=PW)
    ax.text(79, y + 7.5, "AUXILIARY BRANCH (switched, OFF by default)", fontsize=6.2, color=MUTED, ha="center")
    # control
    box(ax, 62, 5, 22, 10, "ESP32-S3-DevKitC-1  edge_guard\nI²C (ADuM1250) ← INA226 ×6 @10 Hz\nGPIO10 → PC817 → ULN2003A → coil", "#fbecc8", fs=6.2)
    arr(ax, 72.5, 15, 72.5, 25.5, c="#b06d00")
    box(ax, 86, 5, 14, 10, "PC (UPS)\nMosquitto + dtpower\ntwin · EMS · logger", "#dbe8fa", fs=6.2)
    arr(ax, 84, 11, 86, 11, c=SG, style="<|-|>")
    ax.text(85, 12.5, "Wi-Fi", fontsize=5.8, color=SG, ha="center")
    box(ax, 12, 10, 22, 10, "Raspberry Pi 4 (mains)\nREF logger (INA228) · DS18B20 ×2\nN1: HTTP probe of hAP ac² @1 Hz", "#d8f1e6", fs=6.2)
    arr(ax, 39, 28, 30, 20, c=SG, ls="--")
    ax.text(0.5, 3, "Red: power path (arrows = energy flow)   Blue/dashed: signal   Orange: actuation", fontsize=6, color=MUTED)
    save(fig, "fig10_bench_wiring")


# ---- fig11: scenario small multiples -----------------------------------------------
def fig_scenarios():
    runs = [("20260929_E02_C0_R00_EMU", "E02 step load (C0)"), ("20260929_E03_C1_R00_EMU", "E03 generation drop (C1)"),
            ("20260929_E04_C0_R00_EMU", "E04 source loss (C0)"), ("20260929_E08_C1_R00_EMU", "E08 recovery (C1)")]
    fig, axs = plt.subplots(3, 4, figsize=(7.4, 5.2), sharex="col")
    for j, (rid, title) in enumerate(runs):
        s = SER[rid]
        t = np.asarray(s["t"]) / 60
        a = axs[0, j]
        a.fill_between(t, 0, s["p_gen_avail"], step="post", color="#cde2fb", label="available gen.")
        a.plot(t, s["p_gen"], color=BLUE, lw=1.1, label="accepted gen.")
        a.plot(t, s["p_crit_term"], color=GREY, lw=0.9, label="critical load")
        a.step(t, s["p_aux_term"], where="post", color=ORANGE, lw=1.1, label="lighting")
        a.set_title(title, fontsize=7.5)
        b = axs[1, j]
        b.plot(t, s["i_batt"], color=AQUA, lw=1.0)
        b.axhline(0, color=MUTED, lw=0.6)
        c = axs[2, j]
        c.plot(t, s["soc_ref"], color=BLUE, lw=1.5, label="SOC_ref (REF)")
        c.plot(t, s["soc_post"], color=INK, lw=0.9, ls="--", label="twin posterior")
        c.set_xlabel("time, min")
        if j == 0:
            a.set_ylabel("power, W")
            b.set_ylabel("I_batt, A\n(+ = discharge)")
            c.set_ylabel("SOC")
    axs[0, 0].legend(fontsize=5.8, loc="upper left", ncol=1)
    axs[2, 0].legend(fontsize=5.8, loc="lower left")
    for a in axs.flat:
        a.tick_params(labelsize=6.5)
    fig.tight_layout()
    save(fig, "fig11_scenarios")


# ---- fig12: uncertainty budget ----------------------------------------------------------
def fig_uncertainty():
    U = S["uncertainty"]
    labels, comps = [], {}
    names = ["standard_I", "calibration_fit_residual", "quantisation", "noise_1s_mean", "shunt_tcr", "residual_offset_after_zero"]
    for ch, rows in U.items():
        for r in rows:
            labels.append(f"{ch} @ {r['i_op_a']:+.0f} A")
            for n in names:
                comps.setdefault(n, []).append(r["components_i"][n] ** 2)
    tot = np.sum([comps[n] for n in names], axis=0)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.4, 3.1), gridspec_kw={"width_ratios": [1.5, 1]})
    left = np.zeros(len(labels))
    cols = [BLUE, ORANGE, AQUA, YEL, "#e87ba4", "#4a3aa7"]
    y = np.arange(len(labels))
    for n, c in zip(names, cols):
        share = np.asarray(comps[n]) / tot * 100
        a1.barh(y, share, left=left, color=c, height=0.7, edgecolor="white", linewidth=0.8, label=n.replace("_", " "))
        left += share
    a1.set_yticks(y, labels, fontsize=6.5)
    a1.set_xlabel("share of variance u_I², %")
    a1.invert_yaxis()
    a1.legend(fontsize=5.8, loc="upper center", bbox_to_anchor=(0.5, -0.18), ncol=3)
    uk2 = [r["U_i_a_k2"] * 1e3 for rows in U.values() for r in rows]
    a2.barh(y, uk2, color=BLUE, height=0.6)
    for yi, v in zip(y, uk2):
        a2.text(v + 0.3, yi + 0.2, f"{v:.1f}", fontsize=6.3)
    a2.set_yticks(y, [""] * len(y))
    a2.invert_yaxis()
    a2.set_xlabel("expanded U_I (k = 2), mA")
    fig.tight_layout()
    save(fig, "fig12_uncertainty_budget")


# ---- fig13: data pipeline -------------------------------------------------------------------
def fig_pipeline():
    fig, ax = canvas(10.5, 4.4, 100, 44)
    box(ax, 0.5, 30, 17, 11, "configs/\nhardware_bench_12v.json\npolicies.json\narticle_scenarios.json", "#efeee9", fs=6.2)
    box(ax, 22, 30, 18, 11, "scripts/run_campaign.py\n(dtpower: bench, twin,\nems, stats, replay)", "#dbe8fa", fs=6.4, bold=True)
    box(ax, 45, 33, 22, 8, "results/summary.json · metrics_runs.csv\nmanifest.json · checksums.sha256", "#d8f1e6", fs=6.1)
    box(ax, 45, 22, 22, 8, "results/raw/<run_id>/  (51 runs)\ntelemetry · events · commands · edge_log", "#d8f1e6", fs=6.1)
    box(ax, 45, 11, 22, 8, "results/protocols/<run_id>.txt\nresults/calibration/*.json", "#d8f1e6", fs=6.1)
    arr(ax, 17.5, 35.5, 22, 35.5)
    for yy in (37, 26, 15):
        arr(ax, 40, 35.5, 45, yy)
    outs = [("make_figures.py\nmake_figures_extra.py", "results/figures/\nfig01–fig13 (PNG+PDF)", 35),
            ("make_protocols.py", "hardware/measurement_\nprotocols.md", 24.5),
            ("make_report.py\nmake_experiment_book.py", "report/*.docx", 14),
            ("make_web.py", "web/index.html", 3.5)]
    for s_, o, yy in outs:
        box(ax, 71, yy, 13, 7.5, s_, "#dbe8fa", fs=5.8)
        box(ax, 87, yy, 12.5, 7.5, o, "#fbecc8", fs=5.8)
        arr(ax, 67, 30, 71, yy + 3.75, c=MUTED, lw=0.8)
        arr(ax, 84, yy + 3.75, 87, yy + 3.75)
    box(ax, 0.5, 8, 17, 14, "tests/test_acceptance.py\n14 checks (§18.3)\nfirmware/esp32_edge_guard\n(ESP-IDF, mirror of\ndtpower/edge_guard.py)", "#efeee9", fs=6)
    arr(ax, 9, 22, 9, 30, c=MUTED, ls="--")
    save(fig, "fig13_data_pipeline")


if __name__ == "__main__":
    for fn in (fig_wiring, fig_scenarios, fig_uncertainty, fig_pipeline):
        fn()
    print("extra figures done")
