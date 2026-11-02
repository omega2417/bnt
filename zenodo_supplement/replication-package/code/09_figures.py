"""Step 9 - Figures 1-5 (PDF and PNG at 300 dpi) in output/figures/."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lib.common import CFG, get_logger, load_crosswalk, load_panel, read_csv  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MaxNLocator  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402

log = get_logger("09_figures")
# Okabe-Ito colour-blind-safe palette
C = ["#0072B2", "#E69F00", "#009E73", "#CC79A7", "#56B4E9", "#D55E00", "#F0E442", "#000000", "#999999"]
CHANNELS = [("permits", "Work permits"), ("declarations", "Employer declarations"),
            ("seasonal", "Seasonal work permits"), ("notifications", "Notifications")]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42})


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(Path(CFG.FIGURES) / f"{name}.{ext}", dpi=CFG.FIG_DPI, bbox_inches="tight",
                    metadata={"Author": None, "Creator": None} if ext == "pdf" else None)
    plt.close(fig)
    log.info("saved %s", name)


def vlines(ax, xs, **kw):
    for x in xs:
        ax.axvline(x, color="#666666", lw=0.8, ls="--", zorder=0, **kw)


def figure1(p):
    a = p.groupby("year")[[c for c, _ in CHANNELS]].sum(min_count=1).fillna(0) / 1e6
    fig, ax = plt.subplots(figsize=(6.8, 3.4))
    bottom = np.zeros(len(a))
    for (c, lab), col in zip(CHANNELS, C):
        ax.bar(a.index, a[c], bottom=bottom, color=col, label=lab, width=0.8)
        bottom += a[c].to_numpy()
    ax.set_ylabel("Documents issued (millions)")
    z = Path(CFG.DERIVED) / "zus_stock.csv"
    if z.exists():
        zs = read_csv(z).dropna(subset=["insured_foreigners"])
        ax.plot(zs.year, zs.insured_foreigners / 1e6, color="black", marker="o", ms=3,
                label="Foreigners insured in ZUS (end of year)")
    vlines(ax, [2017.5, 2021.5, 2024.92])
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax.set_xticks(a.index[::2])
    save(fig, "figure1")


def region_groups(cw):
    rc = Path(CFG.RAW) / "restcountries" / "restcountries_all.json"
    reg = cw.set_index("iso3")[["un_region", "un_subregion"]].copy()
    if rc.exists():
        js = json.loads(rc.read_text(encoding="utf-8"))
        r = pd.DataFrame([{"iso3": x["cca3"], "un_region": x.get("region"),
                           "un_subregion": x.get("subregion")} for x in js]).set_index("iso3")
        reg.update(r)
    def grp(iso):
        if iso == "UKR":
            return "Ukraine"
        if iso in CFG.DECL6:
            return "Other declaration countries"
        sub, region = reg.at[iso, "un_subregion"], reg.at[iso, "un_region"]
        if sub == "Central Asia":
            return "Central Asia"
        if region == "Asia":
            return "Other Asia"
        if region == "Americas":
            return "Americas"
        if region == "Africa":
            return "Africa"
        return "Europe and other"
    return {i: grp(i) for i in reg.index}


def figure2(p, cw):
    g = region_groups(cw)
    d = p.assign(group=p.iso3.map(g)).groupby(["year", "group"])["permits"].sum().unstack().fillna(0)
    order = ["Ukraine", "Other declaration countries", "Central Asia", "Other Asia", "Americas",
             "Africa", "Europe and other"]
    d = d.reindex(columns=[o for o in order if o in d]).div(d.sum(axis=1), axis=0) * 100
    fig, ax = plt.subplots(figsize=(6.8, 3.96))
    ax.stackplot(d.index, d.T.to_numpy(), labels=d.columns, colors=C[:len(d.columns)])
    ax.set_ylabel("Share of work permits (%)"); ax.set_ylim(0, 100); ax.set_xlim(d.index.min(), d.index.max())
    ax.legend(frameon=False, fontsize=7, bbox_to_anchor=(1.01, 1), loc="upper left")
    save(fig, "figure2")


def figure3():
    s = read_csv(Path(CFG.TABLES) / "concentration_series.csv")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.8, 2.9), sharey=True)
    h = s[s.measure == "permits_halfyear"]
    a1.plot(h.t, h.effective_number, color=C[0], marker="o", ms=2)
    a1.set_title("(a) Work permits, half-years", fontsize=9)
    labs = {"permits": "Work permits", "excl_notifications": "All documents excl. notifications",
            "excl_notifications_decl_persons": "Excl. notifications, declaration persons",
            "all_documents": "All documents"}
    for (m, lab), col in zip(labs.items(), C):
        d = s[s.measure == m]
        a2.plot(d.t, d.effective_number, color=col, marker="o", ms=2, label=lab)
    a2.set_title("(b) Annual totals", fontsize=9)
    for ax in (a1, a2):
        ax.set_yscale("log"); vlines(ax, [2018, 2022])
    a1.set_ylabel("Effective number of origins (1/HHI)")
    a2.legend(frameon=False, fontsize=6.5)
    save(fig, "figure3")


def figure4():
    e = read_csv(Path(CFG.TABLES) / "event_study_plotdata.csv")
    cases = list(CFG.EVENT_CASES)
    outs = ["Work permits", "All documents excl. notifications"]
    fig, axes = plt.subplots(len(outs), len(cases), figsize=(6.8, 3.75), sharex=False)
    for j, case in enumerate(cases):
        for i, o in enumerate(outs):
            ax = axes[i, j]
            d = e[(e.case == case) & (e.outcome == o)].sort_values("event_time")
            d = pd.concat([d, pd.DataFrame([{"event_time": -1, "coef": 0, "placebo_p2_5": 0,
                                             "placebo_p97_5": 0}])]).sort_values("event_time")
            ax.fill_between(d.event_time, d.placebo_p2_5, d.placebo_p97_5, color="#cccccc", lw=0)
            ax.plot(d.event_time, d.coef, color=C[0], marker="o", ms=2.5)
            ax.axhline(0, color="black", lw=0.6); ax.axvline(-0.5, color="#666666", lw=0.6, ls="--")
            if i == 0:
                iso, e0, _ = CFG.EVENT_CASES[case]
                verb = "excluded" if iso == "RUS" else "enters"
                ax.set_title(f"{iso} {verb}\n(event year 0 = {e0})", fontsize=7)
            if j == 0:
                ax.set_ylabel(o if len(o) < 15 else "Docs excl. notif.", fontsize=7)
            ax.tick_params(labelsize=6)
            ax.xaxis.set_major_locator(MaxNLocator(integer=True))
            if i == len(outs) - 1:
                ax.set_xlabel("Event time (years)", fontsize=7)
    fig.tight_layout()
    save(fig, "figure4")


def figure5():
    n = read_csv(Path(CFG.DERIVED) / "monthly_national.csv")
    n = n[(n.ym >= "2021-01") & (n.ym <= "2025-12")].copy()
    n["date"] = pd.PeriodIndex(n.ym, freq="M").to_timestamp()
    n["all"] = n[["permits", "declarations", "seasonal"]].sum(axis=1, min_count=3) + n.notifications.fillna(0)
    panels = [("permits", "(a) Work permits"), ("declarations", "(b) Employer declarations"),
              ("seasonal", "(c) Seasonal work permits"), ("notifications", "(d) Notifications"),
              ("all", "(e) All documents (log scale)")]
    fig, axes = plt.subplots(3, 2, figsize=(6.8, 6.0))
    axes = axes.ravel()
    lines = [pd.Timestamp("2022-03-01"), pd.Timestamp("2025-06-01"), pd.Timestamp("2025-12-01")]
    for ax, (c, t), col in zip(axes, panels, C):
        ax.plot(n.date, n[c] / 1000, color=col, lw=1.2)
        ax.set_title(t, fontsize=8); ax.set_ylabel("thousands", fontsize=7)
        for x in lines:
            ax.axvline(x, color="#666666", lw=0.7, ls="--")
        if c == "all":
            ax.set_yscale("log")
        ax.tick_params(labelsize=6)
    axes[-1].axis("off")
    fig.tight_layout()
    save(fig, "figure5")


def main():
    p = load_panel()
    cw = load_crosswalk()
    figure1(p); figure2(p, cw); figure3(); figure4(); figure5()


if __name__ == "__main__":
    main()
