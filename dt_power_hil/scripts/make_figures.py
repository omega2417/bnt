#!/usr/bin/env python3
"""Publication figures (PNG 300 dpi + vector PDF) from results/*.json only."""
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
FIG.mkdir(exist_ok=True)

POL = {"C0": "#2a78d6", "C1": "#eb6834", "C2": "#1baf7a", "C_oracle": "#8a8985"}
LBL = {"C0": "C0 розклад", "C1": "C1 поріг SOC", "C2": "C2 прогнозне правило", "C_oracle": "C_oracle (інф. межа)"}
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.6,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "lines.linewidth": 1.6})

S = json.load(open(RES / "summary.json"))
SER = json.load(open(RES / "series_selected.json"))


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def panel(ax, letter):
    ax.text(-0.08, 1.04, letter, transform=ax.transAxes, fontsize=10, fontweight="bold", color=INK)


# ---- Fig 1: architecture -------------------------------------------------
def fig_arch():
    fig, ax = plt.subplots(figsize=(7.2, 3.9))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 56)
    ax.axis("off")

    def box(x, y, w, h, t, fc="#f4f3f0", ec=MUTED, fs=7.2, bold=False):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.4,rounding_size=1.2", fc=fc, ec=ec, lw=0.9))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=fs, color=INK, fontweight="bold" if bold else None)

    def arr(x0, y0, x1, y1, c=INK, ls="-", lw=1.1):
        ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=8, color=c, lw=lw, ls=ls))

    ax.text(1, 55, "АПАРАТНА ЧАСТИНА (реальні елементи / емуляція)", fontsize=7, color=MUTED, fontweight="bold")
    ax.text(63, 55, "ПРОГРАМНА ЧАСТИНА (dtpower, ПК)", fontsize=7, color=MUTED, fontweight="bold")
    ax.plot([59.5, 59.5], [1, 55], color=GRID, lw=1.2)
    box(1, 43, 17, 8, "RD6018 + LTC4359\nG1: PV-еквівалент", "#dbe8fa")
    box(1, 29, 17, 9, "LiFePO₄ 12,8 В\n40 А·год + BMS", "#dbe8fa")
    box(24, 24, 7, 30, "DC\nшина\n10–14,6 В", "#efeee9", bold=True)
    box(35, 43, 22, 8, "M2 → DDR-60G-12 → M3 →\nhAP ac² + KEL103 (18 Вт)", "#fde4d8", fs=6.8)
    box(35, 29, 22, 9, "Реле Bosch (NO) → M4 →\nDDR-60G-12 → M5 →\nLED 30 Вт", "#fde4d8", fs=6.8)
    box(1, 15, 17, 8, "REF: INA228 + FL-2\nRPi4 (незалежний)", "#d8f1e6")
    box(24, 8, 33, 10, "ESP32-S3 edge_guard:\n10 Гц INA226 ×6, watchdog 5 с,\nконтракт команд, OFF за замовч.", "#fbecc8", fs=6.8)
    box(33, 1.5, 24, 4.5, "N1: HTTP-проба вузла, 1 Гц", "#efeee9", fs=6.6)
    arr(18, 47, 24, 47)
    arr(18, 33.5, 24, 33.5)
    arr(24, 33.5, 18, 33.5)
    arr(31, 47, 35, 47)
    arr(31, 33.5, 35, 33.5)
    ax.text(19, 39.5, "M0", fontsize=6.5, color=MUTED)
    ax.text(19, 30, "M1", fontsize=6.5, color=MUTED)
    arr(9.5, 29, 9.5, 23, c=MUTED, ls="--")
    arr(40, 18, 42, 29, c="#b06d00")
    ax.text(43, 21.5, "GPIO→PC817→\nULN2003A", fontsize=6.2, color="#b06d00")
    box(63, 40, 35, 11, "twin: валідація телеметрії,\nSOC prior/posterior (EKF),\nенергобаланс r_P", "#dbe8fa", fs=6.8)
    box(63, 26, 35, 10, "EMS: C0 / C1 / C2,\nкоманди з TTL, run_id, boot_id", "#d8f1e6", fs=6.8)
    box(63, 13, 35, 9, "logger + analysis: raw CSV, SHA-256,\nметрики, BCa, sign-flip, Holm", "#efeee9", fs=6.8)
    box(63, 2, 35, 7.5, "scenario_runner: E01–E11\n(EMS не бачить майбутнього)", "#efeee9", fs=6.8)
    arr(57, 15, 63, 44, c="#2a78d6")
    ax.text(59.8, 37, "MQTT\n1 Гц", fontsize=6.2, color="#2a78d6", ha="left")
    arr(63, 29, 57, 11, c="#1baf7a")
    ax.text(58.5, 20.5, "cmd/\nACK", fontsize=6.2, color="#1baf7a")
    arr(80.5, 40, 80.5, 36)
    arr(80.5, 26, 80.5, 22)
    save(fig, "fig01_architecture")


# ---- Fig 2: E05 time series (block 0) --------------------------------------
def fig_e05_series():
    fig, (a1, a2) = plt.subplots(2, 1, figsize=(7.2, 4.6), sharex=True, gridspec_kw={"height_ratios": [2.2, 1]})
    for p in ("C0", "C1", "C2", "C_oracle"):
        s = SER[f"20260929_E05_{p}_R00_EMU"]
        t = np.asarray(s["t"]) / 3600
        a1.plot(t, s["soc_ref"], color=POL[p], ls="--" if p == "C_oracle" else "-", label=LBL[p], lw=1.4 if p == "C_oracle" else 1.8)
    a1.axhline(0.20, color=MUTED, lw=0.9, ls=":")
    a1.text(0.05, 0.207, "межа завершення SOC_ref = 0,20", fontsize=7, color=MUTED)
    a1.axhline(0.30, color=MUTED, lw=0.6, ls=":")
    a1.text(0.05, 0.307, "резерв C1/C2 = 0,30", fontsize=7, color=MUTED)
    a1.set_ylabel("SOC_ref (незалежний REF)")
    a1.legend(loc="upper right", ncol=2, fontsize=7.2)
    panel(a1, "A")
    s = SER["20260929_E05_C_oracle_R00_EMU"]
    t = np.asarray(s["t"]) / 3600
    a2.fill_between(t, 0, s["p_gen_avail"], step="post", color="#cde2fb", label="доступна генерація")
    for j, p in enumerate(("C0", "C1", "C2", "C_oracle")):
        s = SER[f"20260929_E05_{p}_R00_EMU"]
        tt = np.asarray(s["t"]) / 3600
        a2.step(tt, np.asarray(s["relay"]) * 6 + 42 + j * 7, where="post", color=POL[p], lw=1.4)
        a2.text(6.05, 42 + j * 7, p, fontsize=6.8, color=INK, va="bottom")
    a2.set_ylabel("Pген, Вт")
    a2.text(0.02, 66, "стан LED (крок = ON):", fontsize=6.8, color=MUTED)
    a2.set_xlabel("час запуску, год")
    a2.set_ylim(0, 78)
    a2.set_xlim(0, 6.4)
    panel(a2, "B")
    save(fig, "fig02_e05_timeseries")


# ---- Fig 3: E05 paired results ------------------------------------------------
def fig_e05_paired():
    runs = [r for r in S["runs"] if r["scenario_id"] == "E05"]
    fig, axs = plt.subplots(1, 3, figsize=(7.2, 2.7))
    for ax, (k, lab), letter in zip(axs, (("time_to_limit_h", "Час до SOC_ref = 0,20, год\n(6 год = цензуровано)"),
                                          ("aux_served_wh", "Доставлено освітлення, Вт·год"),
                                          ("min_soc_ref", "Мінімальний SOC_ref")), "ABC"):
        pols = ["C0", "C1", "C2", "C_oracle"]
        vals = {p: [r[k] for r in sorted(runs, key=lambda r: r["repeat"]) if r["policy"] == p] for p in pols}
        for b in range(len(vals["C0"])):
            ax.plot(range(4), [vals[p][b] for p in pols], color=GRID, lw=0.8, zorder=1)
        for x, p in enumerate(pols):
            jit = (np.arange(len(vals[p])) - 4.5) * 0.02
            ax.scatter(x + jit, vals[p], s=16, color=POL[p], edgecolor="white", linewidth=0.6, zorder=3)
            ax.plot([x - 0.22, x + 0.22], [np.mean(vals[p])] * 2, color=INK, lw=1.4, zorder=4)
        ax.set_xticks(range(4), ["C0", "C1", "C2", "Or."])
        ax.set_ylabel(lab, fontsize=7.5)
        panel(ax, letter)
    fig.tight_layout()
    save(fig, "fig03_e05_paired")


# ---- Fig 4: twin accuracy --------------------------------------------------
def fig_twin():
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.8))
    for rid, c in (("20260929_E03_C2_R00_EMU", POL["C2"]), ("20260929_E04_C0_R00_EMU", POL["C0"])):
        s = SER[rid]
        t = np.asarray(s["t"]) / 60
        a1.plot(t, s["soc_ref"], color=c, lw=1.8, label=f"{rid.split('_')[1]} SOC_ref")
        a1.plot(t, s["soc_post"], color=INK, lw=0.9, ls="--")
        a2.plot(t, (np.asarray(s["soc_post"]) - np.asarray(s["soc_ref"])) * 100, color=c, lw=1.2, label=rid.split("_")[1])
    a1.plot([], [], color=INK, ls="--", lw=0.9, label="posterior двійника")
    a1.set_xlabel("час, хв")
    a1.set_ylabel("SOC")
    a1.legend(fontsize=7)
    a2.axhspan(-3, 3, color="#eef6f2", zorder=0)
    a2.text(2, 2.4, "критерій MAE ≤ 3 в.п.", fontsize=6.8, color=MUTED)
    a2.set_xlabel("час, хв")
    a2.set_ylabel("SOC_posterior − SOC_ref, в.п.")
    a2.legend(fontsize=7)
    panel(a1, "A")
    panel(a2, "B")
    fig.tight_layout()
    save(fig, "fig04_twin_accuracy")


# ---- Fig 5: E06 timeline ------------------------------------------------------
def fig_e06():
    s = SER["20260929_E06_C1_R00_EMU"]
    t = np.asarray(s["t"])
    fig, ax = plt.subplots(figsize=(7.2, 2.4))
    ax.axvspan(600, 630, color="#fde4d8", label="втрата телеметрії (uplink)")
    ax.axvspan(900, 930, color="#fbecc8", label="втрата зв’язку в обидва боки")
    ax.step(t, np.asarray(s["aux_cmd"]), where="post", color=POL["C1"], lw=1.6, label="вихід ESP32 (aux_out)")
    ax.step(t, np.asarray(s["relay"]) * 0.9, where="post", color=POL["C0"], lw=1.2, ls="--", label="фактичний стан реле ×0,9")
    ax.axvline(1200, color=INK, lw=0.8, ls=":")
    ax.text(1205, 0.45, "застаріла команда ON\nі команда з чужим run_id\n→ відхилено", fontsize=6.8, color=INK)
    ax.set_yticks([0, 1], ["OFF", "ON"])
    ax.set_xlabel("час запуску, с")
    ax.set_xlim(0, 1800)
    ax.legend(fontsize=6.8, loc="center left", bbox_to_anchor=(0.01, 0.5), ncol=1)
    save(fig, "fig05_e06_link_loss")


# ---- Fig 6: E11 -----------------------------------------------------------------
def fig_e11():
    e = S["e11"]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.9), gridspec_kw={"width_ratios": [1.7, 1]})
    cols = {"S1": "#2a78d6", "S2": "#eb6834", "S3": "#1baf7a"}
    for sname in ("S1", "S3"):
        soc = e["sil"][sname]["soc"]
        a1.plot(np.arange(1, len(soc) + 1) / 24, soc, color=cols[sname], lw=1.3, label=f"{sname} SIL (S2 ≡ S1)" if sname == "S1" else sname)
    for p, ls in (("C0", "-"),):
        soc = e["controller_replay"][p]["soc"]
        a1.plot(np.arange(1, len(soc) + 1) / 24, soc, color=MUTED, lw=1.0, ls="--", label="S1 з 12,8 В/100 А·год, C0")
    a1.axhline(0.15, color=MUTED, lw=0.8, ls=":")
    a1.axvspan(10, 14, color="#f4f3f0", zorder=0)
    a1.text(10.2, 0.93, "PSH 0,9/0,4", fontsize=6.8, color=MUTED)
    a1.set_xlabel("доба моделі")
    a1.set_ylabel("z_E (частка енергії)")
    a1.legend(fontsize=6.8, loc="lower left")
    panel(a1, "A")
    ps = ["C0", "C1", "C2"]
    crit = [e["controller_replay"][p]["e_unserved_critical_wh"] for p in ps]
    aux = [e["controller_replay"][p]["aux_demand_wh"] - e["controller_replay"][p]["aux_served_wh"] for p in ps]
    x = np.arange(3)
    a2.bar(x - 0.19, crit, 0.36, color=[POL[p] for p in ps], label="критична недопоставка")
    a2.bar(x + 0.19, aux, 0.36, color=[POL[p] for p in ps], alpha=0.45, hatch="////", edgecolor="white", label="недопоставка освітлення")
    for xi, v in zip(x, crit):
        a2.text(xi - 0.19, v + 8, f"{v:.0f}", ha="center", fontsize=6.8, color=INK)
    for xi, v in zip(x, aux):
        a2.text(xi + 0.19, v + 8, f"{v:.0f}", ha="center", fontsize=6.8, color=INK)
    a2.set_xticks(x, ps)
    a2.set_ylabel("Вт·год за 336 год")
    a2.legend(fontsize=6.6, loc="upper left")
    panel(a2, "B")
    fig.tight_layout()
    save(fig, "fig06_e11_14day")


# ---- Fig 7: sensitivity heatmap ---------------------------------------------
def fig_sens():
    g = S["sensitivity_grid"]
    wp = np.asarray(g["wp"])
    fig, ax = plt.subplots(figsize=(4.6, 3.3))
    im = ax.imshow(wp, origin="lower", cmap="Blues", aspect="auto", extent=[g["psh"][0], g["psh"][-1], g["eta"][0], g["eta"][-1]])
    cs = ax.contour(g["psh"], g["eta"], wp, levels=[400, 500, 600, 800, 1000], colors=INK, linewidths=0.7)
    ax.clabel(cs, fmt="%d Wp", fontsize=6.5)
    ax.scatter([1.8], [0.90], s=30, color="#eb6834", edgecolor="white", zorder=5)
    ax.text(1.83, 0.905, "S1: 604 Wp", fontsize=7, color=INK)
    ax.set_xlabel("PSH, год/добу")
    ax.set_ylabel("η_dc")
    ax.grid(False)
    fig.colorbar(im, ax=ax, label="потрібна PV-потужність, Wp")
    save(fig, "fig07_sensitivity")


# ---- Fig 8: timing ------------------------------------------------------------
def fig_timing():
    rtt, eff = [], []
    import csv
    for d in (RES / "raw").iterdir():
        with open(d / "commands.csv") as f:
            for r in csv.DictReader(f):
                if r["reason"].startswith("E06_"):
                    continue
                if r["ack_s"]:
                    rtt.append((float(r["ack_s"]) - float(r["sent_s"])) * 1000)
                if r["effect_s"] and r["effect_kind"] == "edge":
                    eff.append((float(r["effect_s"]) - float(r["sent_s"])) * 1000)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.2, 2.5))
    a1.hist(rtt, bins=25, color=POL["C0"], edgecolor="white", linewidth=0.6)
    a1.axvline(np.percentile(rtt, 95), color=INK, lw=0.9, ls="--")
    a1.text(np.percentile(rtt, 95) + 1, a1.get_ylim()[1] * 0.85, f"p95 = {np.percentile(rtt, 95):.0f} мс", fontsize=7)
    a1.set_xlabel("RTT команда → ACK, мс")
    a1.set_ylabel("кількість команд")
    a2.hist(eff, bins=np.arange(0, 400, 25), color=POL["C2"], edgecolor="white", linewidth=0.6)
    a2.set_xlabel("рішення → фронт M4 (10 Гц), мс")
    panel(a1, "A")
    panel(a2, "B")
    fig.tight_layout()
    save(fig, "fig08_timing")


# ---- Fig 9: calibration ---------------------------------------------------------
def fig_cal():
    cal = json.load(open(RES / "calibration" / "E00_calibration.json"))
    fig, ax = plt.subplots(figsize=(7.2, 2.6))
    chans = list(cal.keys())
    for j, ch in enumerate(chans):
        lv = cal[ch]["levels"]
        for k, r in enumerate(lv):
            fit = k in (0, 2, 4)
            ax.scatter(j + (k - 2) * 0.08, r["residual_rel"] * 100, s=18, marker="o" if fit else "D",
                       color=POL["C0"] if fit else POL["C1"], edgecolor="white", linewidth=0.5, zorder=3)
    ax.axhspan(-1, 1, color="#eef6f2", zorder=0)
    ax.axhline(0, color=MUTED, lw=0.7)
    ax.set_xticks(range(len(chans)), chans)
    ax.set_ylabel("залишок після калібрування, % показу")
    ax.set_ylim(-0.25, 0.25)
    ax.scatter([], [], color=POL["C0"], label="рівні для оцінки a, b")
    ax.scatter([], [], color=POL["C1"], marker="D", label="контрольні рівні (верифікація)")
    ax.legend(fontsize=7, loc="upper right", ncol=2)
    ax.text(-0.4, 0.2, "ціль ±1 % показу (поза масштабом)", fontsize=6.8, color=MUTED)
    save(fig, "fig09_calibration")


if __name__ == "__main__":
    for f in (fig_arch, fig_e05_series, fig_e05_paired, fig_twin, fig_e06, fig_e11, fig_sens, fig_timing, fig_cal):
        f()
    print("figures:", sorted(p.name for p in FIG.glob("*.png")))
