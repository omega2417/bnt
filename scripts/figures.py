"""Figure generation for the tvbnet Data Descriptor (300 DPI, Palatino-compatible serif)."""
import json
import os
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager as fm
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Polygon
import numpy as np
import pandas as pd

sys.path.insert(0, "src")
from tvbnet import engine as E
from tvbnet.generate import build_network, generate_scenario, CLASSES, TOPOLOGY_SPEC, AFFINITY
from tvbnet.pipeline import load_config

for f in ["texgyrepagella-regular.otf", "texgyrepagella-bold.otf", "texgyrepagella-italic.otf", "texgyrepagella-bolditalic.otf"]:
    fm.fontManager.addfont(f"/usr/share/texmf/fonts/opentype/public/tex-gyre/{f}")
plt.rcParams.update({"font.family": "TeX Gyre Pagella", "font.size": 8.5, "axes.titlesize": 9,
                     "axes.labelsize": 8.5, "legend.fontsize": 7.5, "xtick.labelsize": 7.5, "ytick.labelsize": 7.5,
                     "axes.spines.top": False, "axes.spines.right": False, "axes.edgecolor": "#52514e",
                     "axes.linewidth": 0.6, "xtick.color": "#52514e", "ytick.color": "#52514e",
                     "axes.grid": False, "savefig.dpi": 300, "mathtext.fontset": "stix"})
PAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]
INK, INK2, MUTED, GRID = "#0b0b0b", "#52514e", "#9a9893", "#e4e3df"
SEQ = ["#eef4fc", "#c9dcf5", "#94bbec", "#5f98df", "#2a78d6", "#1d5aa6", "#123d73"]
OUT = "figures"; os.makedirs(OUT, exist_ok=True)
cfg = load_config("config/pipeline.yaml")
T = {t: pd.read_parquet(f"build/dataset/tables/{t}.parquet") for t in
     ["scenarios", "configurations", "frontier", "barriers", "threats", "assets", "vulnerabilities"]}
rep = json.load(open("build/report/validation_report.json"))
sc, cf = T["scenarios"], T["configurations"]
from matplotlib.colors import LinearSegmentedColormap
CMAP = LinearSegmentedColormap.from_list("seq", SEQ)


def save(fig, name):
    fig.savefig(f"{OUT}/{name}.png", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def box(ax, x, y, w, h, text, fc="#f4f3f0", ec=INK2, fs=7.5, bold=False, tc=INK, lw=0.7, style="round,pad=0.02,rounding_size=0.04"):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=style, fc=fc, ec=ec, lw=lw))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, color=tc,
            fontweight="bold" if bold else "normal", linespacing=1.15)


def arrow(ax, p, q, color=INK2, lw=0.8, style="-|>", rad=0.0, ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=8, color=color, lw=lw,
                                 connectionstyle=f"arc3,rad={rad}", linestyle=ls, shrinkA=1, shrinkB=1))


def example_scenario():
    d = sc[(sc.depth == 5) & (sc.topology == "segmented_dmz") & (sc.family == "intrusion") & (sc.budget_fraction == 0.30)]
    return d.iloc[0].to_dict()


# ------------------------------------------------------------------ Figure 1: pipeline
def fig_pipeline():
    fig, ax = plt.subplots(figsize=(6.9, 3.25)); ax.set_xlim(0, 100); ax.set_ylim(0, 47); ax.axis("off")
    stages = [("G1", "Design", "6×6×4 structural\ncrossing × L9(3$^4$)"), ("G2", "Generate", "networks, assets,\nthreats, barriers"),
              ("G3", "Perturb", "reliability-$\\rho$\nestimates"), ("G4", "Enumerate &\nselect", "2$^m$ subsets,\n7 methods"),
              ("G5", "Derive", "coverage, risk,\ncost, ROSI, regret")]
    stages2 = [("Q1", "Inject", "7 defect classes\n(raw delivery)"), ("V1–V5", "Phase-1\nvalidation", "schema, range,\nkeys, references"),
               ("Q2", "Quarantine &\nredeliver", "deterministic\nby primary key"), ("V6–V8", "Phase-2\nvalidation", "recompute,\nmonotonicity"),
               ("S/P", "Split &\npackage", "5 manifests,\nPROV-O, RO-Crate")]
    w, h, gap = 16.2, 13.5, 3.75
    for row, (ys, items, col) in enumerate([(30, stages, "#e8f0fb"), (6, stages2, "#fdf0e9")]):
        for i, (code, name, sub) in enumerate(items):
            x = 1 + i * (w + gap)
            ax.add_patch(FancyBboxPatch((x, ys), w, h, boxstyle="round,pad=0.02,rounding_size=0.8", fc=col, ec=INK2, lw=0.7))
            ax.text(x + 1.0, ys + h - 1.5, code, fontsize=6.8, color=INK2, va="top", fontweight="bold")
            ax.text(x + w / 2, ys + h * 0.60, name, ha="center", va="center", fontsize=8, fontweight="bold", color=INK)
            ax.text(x + w / 2, ys + h * 0.22, sub, ha="center", va="center", fontsize=6.5, color=INK2, linespacing=1.1)
            if i < 4:
                arrow(ax, (x + w, ys + h / 2), (x + w + gap, ys + h / 2))
    # wrap connector G5 -> Q1 (routed around the text)
    x5 = 1 + 4 * (w + gap) + w / 2; x1 = 1 + w / 2
    ax.plot([x5, x5, x1, x1], [30, 24.6, 24.6, 21.2], color=INK2, lw=0.8)
    arrow(ax, (x1, 21.4), (x1, 19.6))
    ax.text(50, 26.2, "reference tables (fixed seed 20261107)  →  copy with injected defects", ha="center", fontsize=6.6,
            color=INK2, style="italic")
    ax.text(50, 1.2, "Release gates: 17 rules evaluated on the raw delivery and on the release; object-level lineage (prov:used / prov:generated, SHA-256) at every stage",
            ha="center", fontsize=6.6, color=INK2)
    save(fig, "fig01_pipeline")


# ------------------------------------------------------------------ Figure 2: logical model
def fig_model():
    fig, ax = plt.subplots(figsize=(6.9, 3.75)); ax.set_xlim(0, 100); ax.set_ylim(0, 55.5); ax.axis("off")
    ent = {
        "scenarios": (40, 36, "scenarios", "scenario_id · cell_id\ndesign factors · B · R(0)"),
        "networks": (4, 38, "networks", "network_id · topology\nnodes / links"),
        "assets": (4, 18, "assets", "asset_id · segment · hops\nT, E, S indicators · r · V"),
        "vulnerabilities": (4, 0.5, "vulnerabilities", "vuln_id · asset_id\np$_v$ · class mask"),
        "threats": (40, 13, "threats", "threat_id · class · origin\n$\\lambda$, s, $\\hat\\lambda$, $\\hat s$"),
        "barriers": (76, 36, "barriers", "barrier_id · layer · tier\ne, c, scope, $\\hat e$, $\\hat c$"),
        "configurations": (76, 15, "configurations", "config_id · method · bits\nR, C, $\\kappa$, ROSI, gap"),
        "frontier": (76, 0.5, "frontier", "(scenario_id, point)\nC, R, bits"),
    }
    W, H = 21, 12
    for k, (x, y, name, attrs) in ent.items():
        derived = k in ("configurations", "frontier")
        ax.add_patch(FancyBboxPatch((x, y), W, H, boxstyle="round,pad=0.02,rounding_size=0.6",
                                    fc="#fdf0e9" if derived else "#e8f0fb", ec=INK2, lw=0.7))
        ax.add_patch(Rectangle((x, y + H - 3.6), W, 3.6, fc=PAL[1] if derived else PAL[0], ec="none", alpha=0.9))
        ax.text(x + W / 2, y + H - 1.8, name, ha="center", va="center", color="white", fontsize=7.6, fontweight="bold")
        ax.text(x + W / 2, y + (H - 3.6) / 2, attrs, ha="center", va="center", fontsize=6.4, color=INK, linespacing=1.15)
    def link(a, b, lab, pa=None, pb=None, f=0.5):
        xa, ya = ent[a][0], ent[a][1]; xb, yb = ent[b][0], ent[b][1]
        p = pa or (xa + W / 2, ya + H / 2); q = pb or (xb + W / 2, yb + H / 2)
        ax.plot([p[0], q[0]], [p[1], q[1]], color=MUTED, lw=0.8, zorder=0)
        ax.text(p[0] + f * (q[0] - p[0]), p[1] + f * (q[1] - p[1]), lab, fontsize=6, color=INK2, ha="center", va="center",
                bbox=dict(fc="white", ec="none", pad=0.4))
    link("scenarios", "networks", "1:1", (40, 42), (25, 44))
    link("scenarios", "assets", "1:N", (40, 39), (25, 24))
    link("assets", "vulnerabilities", "1:N", (14.5, 18), (14.5, 12.5))
    link("scenarios", "threats", "1:N", (50.5, 36), (50.5, 25))
    link("scenarios", "barriers", "1:N", (61, 42), (76, 42))
    link("scenarios", "configurations", "1:9", (61, 38), (76, 23), 0.25)
    link("configurations", "frontier", "", (86.5, 15), (86.5, 12.5))
    ax.text(88, 13.6, "1:K", fontsize=6, color=INK2)
    ax.annotate("", xy=(40, 17), xytext=(25, 9), arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, ls=(0, (2, 2))))
    ax.text(30, 15.2, "class match\n(exploits)", fontsize=5.8, color=INK2, ha="center")
    ax.annotate("", xy=(61, 21), xytext=(76, 40), arrowprops=dict(arrowstyle="-", color=MUTED, lw=0.8, ls=(0, (2, 2))))
    ax.text(70.5, 33.0, "mitigates\n$m_{bta}$", fontsize=5.8, color=INK2, ha="center")
    ax.text(50, 54.3, "Blue: model inputs (G1–G3)    Orange: model-derived outputs (G4–G5)    Dashed: computed relations, not stored keys",
            ha="center", fontsize=6.4, color=INK2)
    save(fig, "fig02_logical_model")


# ------------------------------------------------------------------ Figure 3: six network configurations
def fig_topologies():
    fig, axs = plt.subplots(1, 6, figsize=(6.9, 1.85))
    for ax, top in zip(axs, TOPOLOGY_SPEC):
        nodes, links, assets, dist, nseg = build_network(top)
        # layered layout by hop distance
        layers = {}
        for n, r, s in nodes:
            layers.setdefault(dist[n], []).append((n, r, s))
        pos = {}
        for dd, items in layers.items():
            items = sorted(items, key=lambda z: (z[2], z[0]))
            for i, (n, r, s) in enumerate(items):
                pos[n] = ((i + 1) / (len(items) + 1), 1 - dd / (max(layers) + 0.6))
        for u, v, k in links:
            ax.plot([pos[u][0], pos[v][0]], [pos[u][1], pos[v][1]], color=MUTED, lw=0.6,
                    ls=(0, (2, 1.5)) if k == "wan" else "-", zorder=1)
        for n, r, s in nodes:
            x, y = pos[n]
            if r == "host":
                ax.scatter(x, y, s=16, c=PAL[s % 8], edgecolors="white", linewidths=0.6, zorder=3)
            elif r == "gateway":
                ax.scatter(x, y, s=34, marker="D", c=INK, zorder=3)
            elif r == "firewall":
                ax.scatter(x, y, s=34, marker="s", c=PAL[7], zorder=3)
            else:
                ax.scatter(x, y, s=20, marker="s", c="white", edgecolors=INK2, linewidths=0.7, zorder=3)
        ax.set_title(top.replace("_", " "), fontsize=7.8)
        ax.text(0.5, -0.08, f"{len(nodes)} nodes · {len(links)} links\n{nseg} segment{'s' if nseg > 1 else ''} · {len(assets)} assets",
                transform=ax.transAxes, ha="center", va="top", fontsize=6.2, color=INK2)
        ax.set_xlim(-0.02, 1.02); ax.set_ylim(-0.05, 1.05); ax.axis("off")
    save(fig, "fig03_topologies")


# ------------------------------------------------------------------ Figure 4: attenuation cascade + mitigation matrix
def fig_cascade():
    r = example_scenario()
    s = generate_scenario(r, cfg); I = E.Instance(s, r, cfg)
    R, C = E.enumerate_all(I); k = E.exact(R, C, I.budget)
    x = E.bits_to_vec(E.mask_to_bits(k, I.m))
    cas = I.layer_cascade(x); full = I.layer_cascade(np.ones(I.m))
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.9, 2.75), gridspec_kw={"width_ratios": [1.15, 1]})
    xs = np.arange(6)
    present = [c for c in range(6) if cas[0, c] > 0]
    bottom = np.zeros(6)
    for c in present:
        a1.fill_between(xs, bottom, bottom + cas[:, c], color=PAL[c], alpha=0.85, lw=0, step=None)
        a1.plot(xs, bottom + cas[:, c], color="white", lw=1.0)
        bottom += cas[:, c]
    a1.plot(xs, full.sum(1), color=INK, lw=1.0, ls=(0, (3, 2)), label="all 15 barriers (cost-unconstrained)")
    for i in xs:
        a1.text(i, bottom[i] + 4, f"{bottom[i]:.0f}", ha="center", fontsize=6.5, color=INK2)
    a1.set_xticks(xs, ["none", "+L1\nperimeter", "+L2\nnetwork", "+L3\nchannel", "+L4\nhost", "+L5\ndata"])
    a1.set_ylabel("Residual expected loss (kCU yr$^{-1}$)")
    hand = [Rectangle((0, 0), 1, 1, fc=PAL[c]) for c in present]
    l1 = a1.legend(hand, [CLASSES[c] for c in present], ncol=3, frameon=False, loc="upper right", fontsize=6.6, title="threat class", title_fontsize=6.6)
    a1.add_artist(l1); a1.legend(loc="center right", frameon=False, fontsize=6.4, bbox_to_anchor=(1.0, 0.52))
    a1.set_title("(a) Risk attenuation cascade, optimal selection at $B$", loc="left")
    a1.set_ylim(0, bottom[0] * 1.32)
    # (b) mitigation matrix aggregated over assets: max_a m_bta
    Mbt = I.M.max(2)
    im = a2.imshow(Mbt, cmap=CMAP, vmin=0, vmax=1, aspect="auto")
    sel = np.flatnonzero(x > 0.5)
    for b in sel:
        a2.add_patch(Rectangle((-0.5, b - 0.5), I.T, 1, fill=False, ec=PAL[7], lw=1.3))
    ylab = [f"L{L}-{t[0].upper()}" for L, t in zip(I.layer, [b["tier"] for b in s["barriers"]])]
    a2.set_yticks(range(I.m), ylab, fontsize=6.2)
    a2.set_xticks(range(I.T), [CLASSES[c] for c in I.cls], fontsize=6.2, rotation=0)
    a2.tick_params(length=0)
    for sp in a2.spines.values():
        sp.set_visible(False)
    cb = fig.colorbar(im, ax=a2, fraction=0.05, pad=0.02); cb.ax.tick_params(labelsize=6.2); cb.outline.set_visible(False)
    cb.set_label("max$_a$ $m_{bta}$", fontsize=6.8)
    a2.set_title("(b) Barrier–threat mitigation (red: selected)", loc="left")
    fig.tight_layout(w_pad=1.5)
    save(fig, "fig04_cascade")
    return {"scenario_id": r["scenario_id"], "R0": float(I.R0), "R_exact": float(R[k]), "budget": float(I.budget),
            "cost_exact": float(C[k]), "n_sel": int(x.sum()), "full_R": float(R[-1]), "full_C": float(C[-1]),
            "cascade_total": cas.sum(1).tolist(), "m": I.m}


# ------------------------------------------------------------------ Figure 5: Pareto
def fig_pareto():
    r = example_scenario()
    s = generate_scenario(r, cfg); I = E.Instance(s, r, cfg)
    R, C = E.enumerate_all(I); fr = E.frontier(R, C)
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.9, 2.75))
    a1.scatter(C, R, s=1.2, c=MUTED, alpha=0.25, lw=0, rasterized=True, label=f"all $2^{{{I.m}}}$ = {2**I.m} subsets")
    a1.step(C[fr], R[fr], where="post", color=INK, lw=1.1, label=f"Pareto frontier ({len(fr)} points)")
    a1.axvline(I.budget, color=INK2, lw=0.7, ls=(0, (3, 2)))
    a1.text(I.budget * 1.03, R.max() * 0.97, "budget $B$", fontsize=6.6, color=INK2, va="top")
    cc = cf[cf.scenario_id == r["scenario_id"]].set_index("method")
    mk = {"exact": ("o", INK), "greedy": ("s", PAL[0]), "layer_uniform": ("^", PAL[1]), "max_effect": ("v", PAL[2]),
          "random": ("D", PAL[6]), "exact_est": ("P", PAL[7])}
    for mth, (m, col) in mk.items():
        a1.scatter(cc.at[mth, "cost_kcu"], cc.at[mth, "residual_risk_kcu"], marker=m, s=34, c=col,
                   edgecolors="white", linewidths=0.8, zorder=5, label=mth.replace("_", "-"))
    a1.set_xlabel("Annual protection cost $C(x)$ (kCU)"); a1.set_ylabel("Residual risk $R(x)$ (kCU yr$^{-1}$)")
    a1.legend(frameon=False, fontsize=6.0, loc="upper right", markerscale=0.8, handletextpad=0.3, labelspacing=0.3)
    a1.set_title("(a) Exhaustive cost–risk space, example scenario", loc="left")
    # (b) normalized frontier envelopes by depth
    F = T["frontier"].merge(sc[["scenario_id", "depth", "baseline_risk_kcu", "full_cost_kcu"]], on="scenario_id")
    F["cn"] = F.cost_kcu / F.full_cost_kcu; F["rn"] = F.residual_risk_kcu / F.baseline_risk_kcu
    grid = np.linspace(0, 1, 41)
    for i, D in enumerate([2, 3, 4, 5]):
        curves = []
        for sid, g in F[F.depth == D].groupby("scenario_id"):
            idx = np.searchsorted(g.cn.to_numpy(), grid, side="right") - 1
            curves.append(g.rn.to_numpy()[np.clip(idx, 0, None)])
        curves = np.array(curves)
        med, lo, hi = np.median(curves, 0), np.quantile(curves, 0.25, 0), np.quantile(curves, 0.75, 0)
        a2.fill_between(grid, lo, hi, color=PAL[i], alpha=0.15, lw=0)
        a2.plot(grid, med, color=PAL[i], lw=1.6)
        a2.text(0.74 + 0.0 * i, med[30] + 0.012, f"D = {D}", color=INK, fontsize=6.8, va="bottom")
    for b in cfg["l9_factors"]["budget_fraction"]:
        a2.axvline(b, color=GRID, lw=0.8, zorder=0)
    a2.set_xlabel("Normalized cost $C/\\sum_b c_b$"); a2.set_ylabel("Relative residual risk $R/R(0)$")
    a2.set_ylim(0, 1.02); a2.set_xlim(0, 1)
    a2.set_title("(b) Frontier medians and IQR by layer depth", loc="left")
    fig.tight_layout(w_pad=1.6)
    save(fig, "fig05_pareto")


# ------------------------------------------------------------------ Figure 6: heatmaps
def fig_heatmaps():
    ex = cf[cf.method == "exact"].merge(sc, on="scenario_id")
    fig, axs = plt.subplots(1, 2, figsize=(6.9, 2.45), gridspec_kw={"width_ratios": [1, 1.45]})
    p1 = ex.pivot_table(index="depth", columns="budget_fraction", values="relative_residual_risk", aggfunc="median")
    p2 = ex.pivot_table(index="effectiveness_mean", columns="topology", values="relative_residual_risk", aggfunc="median")
    p2 = p2[list(TOPOLOGY_SPEC)]
    for ax, p, xl, yl, tt in [(axs[0], p1, "Budget fraction $\\beta$", "Layer depth $D$", "(a) Depth × budget"),
                              (axs[1], p2, "Network configuration", "Mean effectiveness $\\bar e$", "(b) Effectiveness × topology")]:
        im = ax.imshow(p.values, cmap=CMAP.reversed(), vmin=0.1, vmax=0.75, aspect="auto", origin="lower")
        for i in range(p.shape[0]):
            for j in range(p.shape[1]):
                v = p.values[i, j]
                ax.text(j, i, f"{v:.2f}", ha="center", va="center", fontsize=6.8, color="white" if v < 0.33 else INK)
        ax.set_xticks(range(p.shape[1]), [str(c).replace("_", "\n") for c in p.columns], fontsize=6.4)
        ax.set_yticks(range(p.shape[0]), [str(c) for c in p.index])
        ax.set_xlabel(xl); ax.set_ylabel(yl); ax.set_title(tt, loc="left"); ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
    cb = fig.colorbar(im, ax=axs, fraction=0.025, pad=0.02); cb.outline.set_visible(False)
    cb.set_label("median $R(x^*)/R(0)$", fontsize=7); cb.ax.tick_params(labelsize=6.4)
    save(fig, "fig06_heatmaps")


# ------------------------------------------------------------------ Figure 7: method ECDFs
def fig_methods():
    fig, ax = plt.subplots(figsize=(4.4, 2.6))
    order = [("greedy", PAL[0]), ("layer_uniform", PAL[1]), ("max_effect", PAL[2]), ("random", PAL[6]),
             ("exact_est", PAL[7]), ("greedy_est", PAL[3])]
    for mth, col in order:
        g = np.sort(cf.loc[cf.method == mth, "optimality_gap"].to_numpy())
        y = np.arange(1, len(g) + 1) / len(g)
        ax.plot(np.clip(g, -0.1, None) * 100, y, color=col, lw=1.4, label=mth.replace("_", "-"))
    ax.legend(frameon=False, loc="lower right", fontsize=6.8)
    ax.axvline(0, color=INK2, lw=0.6)
    ax.set_xlim(-6, 50); ax.set_ylim(0, 1.01)
    ax.set_xlabel("Optimality gap $[R(\\hat x)-R(x^*)]/R(0)$ (%)"); ax.set_ylabel("Share of scenarios (ECDF)")
    ax.grid(axis="y", color=GRID, lw=0.5)
    save(fig, "fig07_methods")


# ------------------------------------------------------------------ Figure 8: reliability
def fig_reliability():
    p = cf.pivot_table(index="scenario_id", columns="method", values=["optimality_gap", "feasible", "cost_kcu"], aggfunc="first")
    d = sc.set_index("scenario_id")
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.9, 2.6))
    rhos = cfg["l9_factors"]["input_reliability"]
    for j, (mth, col) in enumerate([("exact_est", PAL[7]), ("greedy_est", PAL[3])]):
        data = [p["optimality_gap"][mth][d.input_reliability == r].to_numpy() * 100 for r in rhos]
        pos = np.arange(3) + (j - 0.5) * 0.32
        bp = a1.boxplot(data, positions=pos, widths=0.26, patch_artist=True, showfliers=False,
                        medianprops=dict(color=INK, lw=1.0), whiskerprops=dict(color=INK2, lw=0.6),
                        capprops=dict(color=INK2, lw=0.6), boxprops=dict(lw=0.6, ec=INK2))
        for b in bp["boxes"]:
            b.set_facecolor(col); b.set_alpha(0.75)
        for k, arr in enumerate(data):
            a1.scatter(pos[k], arr.mean(), marker="D", s=12, c="white", edgecolors=INK, lw=0.6, zorder=5)
    a1.axhline(0, color=INK2, lw=0.6)
    a1.set_xticks(range(3), [f"$\\rho$ = {r}" for r in rhos]); a1.set_ylabel("Regret vs. $x^*$ (% of $R(0)$)")
    a1.legend([Rectangle((0, 0), 1, 1, fc=PAL[7], alpha=0.75), Rectangle((0, 0), 1, 1, fc=PAL[3], alpha=0.75)],
              ["exact on estimates", "greedy on estimates"], frameon=False, fontsize=6.6, loc="upper right")
    a1.set_title("(a) Selection regret under input reliability", loc="left")
    for j, (mth, col) in enumerate([("exact_est", PAL[7]), ("greedy_est", PAL[3])]):
        viol = [1 - p["feasible"][mth][d.input_reliability == r].astype(bool).mean() for r in rhos]
        over = []
        for r in rhos:
            m = d.input_reliability == r
            cst = p["cost_kcu"][mth][m]; bud = d.budget_kcu[m]
            o = (cst - bud)[cst > bud + 1e-9] / bud[cst > bud + 1e-9]
            over.append(np.median(o) * 100 if len(o) else 0)
        xx = np.arange(3) + (j - 0.5) * 0.32
        a2.bar(xx, np.array(viol) * 100, width=0.28, color=col, alpha=0.8)
        for xi, v, o in zip(xx, viol, over):
            a2.text(xi, v * 100 + 1.2, f"{v*100:.0f}%\n(+{o:.0f}%)", ha="center", fontsize=6.0, color=INK2)
    a2.set_xticks(range(3), [f"$\\rho$ = {r}" for r in rhos]); a2.set_ylabel("True budget overrun rate (%)")
    a2.set_ylim(0, 60)
    a2.set_title("(b) Overrun rate (median overspend)", loc="left")
    fig.tight_layout(w_pad=1.6)
    save(fig, "fig08_reliability")


# ------------------------------------------------------------------ Figure 9: sensitivity
def fig_sensitivity():
    lab = {"topology": "network configuration", "family": "scenario family", "depth": "layer depth $D$",
           "effectiveness_mean": "effectiveness $\\bar e$", "input_reliability": "input reliability $\\rho$",
           "impact_multiplier": "impact multiplier $k_I$", "budget_fraction": "budget fraction $\\beta$"}
    e1, e2 = rep["eta2_log_rrr"], rep["eta2_regret"]
    keys = sorted(e1, key=lambda k: e1[k])
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.9, 2.3), sharey=True)
    for ax, e, col, tt in [(a1, e1, PAL[0], "(a) log$_{10}$ relative residual risk"), (a2, e2, PAL[7], "(b) regret of exact-on-estimates")]:
        v = [e[k] for k in keys]
        ax.barh(range(len(keys)), v, color=col, height=0.6)
        for i, x in enumerate(v):
            ax.text(x + max(v) * 0.02, i, f"{x:.3f}", va="center", fontsize=6.5, color=INK2)
        ax.set_xlim(0, max(v) * 1.25); ax.set_title(tt, loc="left"); ax.set_xlabel("main-effect share $\\eta^2$")
    a1.set_yticks(range(len(keys)), [lab[k] for k in keys])
    fig.tight_layout(w_pad=1.2)
    save(fig, "fig09_sensitivity")


# ------------------------------------------------------------------ Figure 10: split manifests
def fig_splits():
    names = ["family_holdout", "network_holdout", "compound_holdout", "cell_disjoint", "budget_extrapolation"]
    col = {"train": PAL[0], "validation": PAL[3], "test": PAL[1], "excluded": "#eceae6"}
    fams, tops = cfg["families"], list(TOPOLOGY_SPEC)
    fig, axs = plt.subplots(1, 5, figsize=(6.9, 1.95))
    for ax, n in zip(axs, names):
        m = pd.read_csv(f"build/dataset/splits/{n}.csv").merge(sc, on="scenario_id")
        for i, f in enumerate(fams):
            for j, t in enumerate(tops):
                g = m[(m.family == f) & (m.topology == t)]["partition"].value_counts(normalize=True)
                x0 = j
                for pname in ["train", "validation", "test", "excluded"]:
                    w = g.get(pname, 0)
                    if w > 0:
                        ax.add_patch(Rectangle((x0, i), w * 0.92, 0.92, fc=col[pname], ec="none"))
                        x0 += w * 0.92
        ax.set_xlim(-0.1, 6); ax.set_ylim(-0.1, 6); ax.invert_yaxis(); ax.set_aspect("equal")
        ax.set_xticks(np.arange(6) + 0.46, ["star", "tree", "mesh", "ring", "hub", "dmz"], fontsize=5.4, rotation=90)
        ax.set_yticks(np.arange(6) + 0.46, fams if n == names[0] else [], fontsize=5.6)
        ax.tick_params(length=0)
        for sp in ax.spines.values():
            sp.set_visible(False)
        a = rep["manifests"][n]
        ax.set_title(n.replace("_", " "), fontsize=6.9)
        ax.text(3, 6.9 + 1.6, f"{a['train']}/{a['validation']}/{a['test']}" + (f" (+{a['excluded']} excl.)" if a["excluded"] else ""),
                ha="center", fontsize=5.9, color=INK2)
    fig.legend([Rectangle((0, 0), 1, 1, fc=col[k]) for k in col], list(col), ncol=4, frameon=False,
               loc="lower center", bbox_to_anchor=(0.5, -0.14), fontsize=6.6)
    save(fig, "fig10_splits")


# ------------------------------------------------------------------ Figure 11: validation
def fig_validation():
    det = rep["defect_detection"]
    defects = [k for k in det if k != "false_positive_flags"]
    checks = ["V2_completeness", "V3_range", "V4_primary_key", "V5_referential", "V6_recompute", "V6_feasibility"]
    from tvbnet.release import DEFECT_CHECK
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(6.9, 3.0), gridspec_kw={"width_ratios": [1, 1.25]})
    Mx = np.zeros((len(defects), len(checks)))
    for i, d in enumerate(defects):
        Mx[i, checks.index(DEFECT_CHECK[d])] = det[d]["recall"]
    a1.imshow(Mx, cmap=CMAP, vmin=0, vmax=1, aspect="auto")
    for i, d in enumerate(defects):
        j = checks.index(DEFECT_CHECK[d])
        a1.text(j, i, f"{det[d]['detected']}/{det[d]['injected']}", ha="center", va="center", fontsize=6.6, color="white")
    a1.set_xticks(range(len(checks)), ["V2\ncompl.", "V3\nrange", "V4\nPK", "V5\nFK", "V6\nrecomp.", "V6\nfeas."], fontsize=6.0)
    a1.set_yticks(range(len(defects)), [d.replace("_", " ", 1).replace("_", "-") for d in defects], fontsize=6.4)
    a1.tick_params(length=0)
    for sp in a1.spines.values():
        sp.set_visible(False)
    a1.set_title(f"(a) Injected defects × detecting check\n(false-positive flags: {det['false_positive_flags']})", loc="left")
    gr, gl = rep["gates_raw"], rep["gates_release"]
    names = [g["gate"] for g in gl]
    rawst = {g["gate"]: g["status"] for g in gr}
    for i, n in enumerate(names):
        for j, st in enumerate([rawst.get(n), next(g["status"] for g in gl if g["gate"] == n)]):
            if st is None:
                a2.add_patch(Rectangle((j, i), 0.9, 0.82, fc="#f4f3f0", ec="none"))
                a2.text(j + 0.45, i + 0.41, "n/a", ha="center", va="center", fontsize=5.8, color=MUTED)
                continue
            c = "#008300" if st == "Pass" else PAL[7]
            a2.add_patch(Rectangle((j, i), 0.9, 0.82, fc=c, ec="none", alpha=0.85))
            a2.text(j + 0.45, i + 0.41, ("✓ " if st == "Pass" else "✗ ") + st, ha="center", va="center", fontsize=5.8, color="white",
                    fontfamily="DejaVu Sans")
        a2.text(-0.08, i + 0.41, n, ha="right", va="center", fontsize=5.9, color=INK)
    a2.set_xlim(-0.05, 1.95); a2.set_ylim(len(names), -0.3); a2.axis("off")
    a2.text(0.45, -0.55, "raw delivery", ha="center", fontsize=6.8, fontweight="bold")
    a2.text(1.45, -0.55, "release", ha="center", fontsize=6.8, fontweight="bold")
    a2.text(-1.9, -0.55, "(b) Release gates", fontsize=9)
    fig.tight_layout(w_pad=0.5)
    save(fig, "fig11_validation")


# ------------------------------------------------------------------ Figure 12: software architecture (proposal)
def fig_architecture():
    fig, ax = plt.subplots(figsize=(6.9, 3.9)); ax.set_xlim(0, 100); ax.set_ylim(0, 58); ax.axis("off")
    tiers = [(46, "Presentation", "#f3eefc", [("Decision dashboard\n(Pareto explorer, cascades)", 22), ("Notebook &\nreport templates", 18), ("CLI\ntvbnet …", 12), ("REST/OpenAPI\nclient SDK", 16)]),
             (33, "Services", "#e8f0fb", [("Scenario service\n(design, generation)", 19), ("Risk engine\n(Eq. 1–9, vectorized)", 19), ("Optimizer service\nexact · MILP · NSGA-II", 21), ("Validation &\ngates service", 15)]),
             (20, "Data &\nprovenance", "#e9f7f0", [("Canonical store\nParquet / DuckDB", 18), ("Provenance graph\nPROV-O, object-level", 19), ("Packaging\nRO-Crate, DataCite", 17), ("Integrity\nSHA-256, signing", 16)]),
             (7, "Calibration\ninputs\n(v0.3+)", "#fdf0e9", [("Incident & loss\nrecords", 16), ("Vulnerability feeds\n(scored exposure)", 19), ("Control test\nresults", 15), ("Cost ledgers\n(CAPEX/OPEX)", 16)])]
    for y, name, fc, items in tiers:
        ax.add_patch(FancyBboxPatch((0.5, y - 1.2), 99, 11.5, boxstyle="round,pad=0.02,rounding_size=0.8", fc=fc, ec="none"))
        ax.text(1.8, y + 3.8, name, fontsize=7.2, fontweight="bold", color=INK2, va="center", linespacing=1.1)
        tot = sum(w for _, w in items); gap = (84 - tot) / (len(items) - 1) if len(items) > 1 else 0
        x = 14
        for t, w in items:
            box(ax, x, y, w, 7.6, t, fc="white", fs=6.5)
            x += w + gap
    for xa in (25, 47, 69, 90):
        arrow(ax, (xa, 18.8), (xa, 20), color=MUTED)
        arrow(ax, (xa, 31.8), (xa, 33), color=MUTED)
        arrow(ax, (xa, 44.8), (xa, 46), color=MUTED)
    ax.text(50, 56.5, "Proposed layered architecture; the v0.1 prototype implements the service core, data/provenance layer and CLI",
            ha="center", fontsize=6.6, color=INK2)
    save(fig, "fig12_architecture")


# ------------------------------------------------------------------ Figure 13: roadmap
def fig_roadmap():
    wps = [("WP1 Core engine & generator (v0.1, done)", 0, 2, PAL[0]), ("WP2 Validation, gates, packaging (v0.1, done)", 1, 3, PAL[0]),
           ("WP3 MILP & NSGA-II optimizers; dependent barriers", 3, 7, PAL[2]), ("WP4 Service API, DuckDB store, dashboard", 5, 10, PAL[2]),
           ("WP5 Calibration interfaces (incident, exposure, cost)", 8, 14, PAL[1]), ("WP6 Empirical pilot record (separate DOI)", 12, 18, PAL[1]),
           ("WP7 Benchmark challenge & documentation", 15, 20, PAL[6])]
    ms = [(3, "M1 v0.1.0\nrehearsal"), (7, "M2 v0.2.0"), (10, "M3 service\nbeta"), (14, "M4 v0.3.0\ncalibrated"), (20, "M5 v1.0")]
    fig, ax = plt.subplots(figsize=(6.9, 2.5))
    for i, (n, s, e, c) in enumerate(wps):
        ax.add_patch(FancyBboxPatch((s, i - 0.32), e - s, 0.64, boxstyle="round,pad=0,rounding_size=0.15", fc=c, ec="none", alpha=0.85))
        ax.text(-0.3, i, n, ha="right", va="center", fontsize=6.6, color=INK)
    for m, lab in ms:
        ax.axvline(m, color=INK2, lw=0.6, ls=(0, (2, 2)))
        ax.scatter(m, -0.8, marker="D", s=18, c=INK, clip_on=False, zorder=4)
        ax.text(m, -1.2, lab, ha="center", va="bottom", fontsize=5.9, color=INK2, bbox=dict(fc="white", ec="none", pad=0.6), zorder=5)
    ax.set_xlim(0, 20.5); ax.set_ylim(len(wps) - 0.4, -2.3)
    ax.set_yticks([]); ax.set_xticks(range(0, 21, 2), [f"M{m}" if m else "M0" for m in range(0, 21, 2)])
    ax.set_xlabel("Project month"); ax.spines["left"].set_visible(False)
    save(fig, "fig13_roadmap")


if __name__ == "__main__":
    fig_pipeline(); fig_model(); fig_topologies()
    ex = fig_cascade(); fig_pareto(); fig_heatmaps(); fig_methods(); fig_reliability()
    fig_sensitivity(); fig_splits(); fig_validation(); fig_architecture(); fig_roadmap()
    json.dump(ex, open("build/report/example_scenario.json", "w"), indent=1)
    print(ex)
