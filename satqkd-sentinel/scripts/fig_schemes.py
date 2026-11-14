"""Signature matrix of the simulated link states and the federated analytics scheme."""
import sys, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle, FancyArrowPatch
from matplotlib.lines import Line2D
from satqkd_sentinel import style as S
S.apply(); outdir = sys.argv[1]

# ------------------------------------------------------------------ signature matrix
cols = [("channel loss", "q"), ("QBER", "q"), ("vacuum-decoy rate", "q"), ("decoy ratio ρ", "q"), ("basis ratio", "q"),
        ("downlink beacon", "t"), ("uplink beacon", "t"), ("pointing residual", "t"), ("scintillation", "t"),
        ("out-of-gate rate", "r"), ("double clicks", "r"), ("pol. reference", "r")]
C = {c[0]: i for i, c in enumerate(cols)}
rows = [("Cloud attenuation", "F", {"channel loss": "+", "QBER": "+", "downlink beacon": "-", "uplink beacon": "-"}),
        ("Pointing degradation", "F", {"channel loss": "+", "pointing residual": "+", "scintillation": "+"}),
        ("OPA phase drift", "F", {"channel loss": "+", "uplink beacon": "0", "pointing residual": "0"}),
        ("Natural background", "F", {"vacuum-decoy rate": "+", "out-of-gate rate": "+"}),
        ("Polarization drift", "F", {"QBER": "+", "pol. reference": "+"}),
        ("Optical jamming", "A", {"channel loss": "0", "QBER": "+", "vacuum-decoy rate": "+", "out-of-gate rate": "+", "double clicks": "+"}),
        ("Intercept-resend", "A", {"channel loss": "0", "QBER": "+", "pol. reference": "0"}),
        ("Yield manipulation", "A", {"channel loss": "0", "QBER": "0", "decoy ratio ρ": "-"}),
        ("Detector control", "A", {"QBER": "-", "vacuum-decoy rate": "-", "basis ratio": "x", "out-of-gate rate": "-", "double clicks": "-"})]
fig = plt.figure(figsize=(6.25, 3.75)); ax = fig.add_axes([0.25, 0.125, 0.665, 0.64])
nr, nc = len(rows), len(cols)
ax.set_xlim(-0.5, nc - 0.5); ax.set_ylim(nr - 0.5, -0.5)
for j in range(nc):
    for i in range(nr):
        ax.add_patch(Rectangle((j - 0.46, i - 0.44), 0.92, 0.88, fc="#f6f6f4", ec="none", zorder=1))
for i, (name, grp, sig) in enumerate(rows):
    for k, v in sig.items():
        j = C[k]
        if v == "+":
            ax.add_patch(Rectangle((j - 0.46, i - 0.44), 0.92, 0.88, fc=S.ORANGE, ec="none", zorder=2))
            ax.plot(j, i, marker="^", ms=7, mfc="white", mec="white", zorder=3)
        elif v == "-":
            ax.add_patch(Rectangle((j - 0.46, i - 0.44), 0.92, 0.88, fc=S.BLUE, ec="none", zorder=2))
            ax.plot(j, i, marker="v", ms=7, mfc="white", mec="white", zorder=3)
        elif v == "0":
            ax.add_patch(Rectangle((j - 0.46, i - 0.44), 0.92, 0.88, fc="#f6f6f4", ec=S.INK2, lw=0.9, zorder=2))
            ax.plot(j, i, marker="o", ms=6.5, mfc="none", mec=S.INK2, mew=1.2, zorder=3)
        elif v == "x":
            ax.add_patch(Rectangle((j - 0.46, i - 0.44), 0.92, 0.88, fc=S.PURPLE, ec="none", zorder=2))
            ax.plot(j, i - 0.14, marker="^", ms=5, mfc="white", mec="white", zorder=3); ax.plot(j, i + 0.16, marker="v", ms=5, mfc="white", mec="white", zorder=3)
ax.set_yticks(range(nr)); ax.set_yticklabels([r[0] for r in rows], fontsize=8.4, color=S.INK)
ax.set_xticks(range(nc)); ax.set_xticklabels([c[0] for c in cols], rotation=38, ha="left", rotation_mode="anchor", fontsize=8.2, color=S.INK)
ax.xaxis.tick_top(); ax.tick_params(length=0, pad=3)
for sp in ax.spines.values(): sp.set_visible(False)
ax.axhline(4.5, color=S.INK2, lw=0.8); 
for x in (4.5, 8.5): ax.axvline(x, color="white", lw=4, zorder=4); ax.axvline(x, color=S.INK2, lw=0.8, zorder=5)
tr = ax.get_yaxis_transform()
ax.text(-0.335, 2.0, "faults (F)", rotation=90, transform=tr, ha="center", va="center", fontsize=8.4, fontweight="bold", color=S.INK2)
ax.text(-0.335, 6.5, "attacks (A)", rotation=90, transform=tr, ha="center", va="center", fontsize=8.4, fontweight="bold", color=S.INK2)
for x0, x1, lab in ((-0.46, 4.46, "(a) public QKD statistics"), (4.54, 8.46, "(b) terminal telemetry"), (8.54, 11.46, "(c) receiver monitors")):
    ax.plot([x0, x1], [nr - 0.32, nr - 0.32], color=S.INK2, lw=0.8, clip_on=False)
    ax.text(0.5 * (x0 + x1), nr - 0.12, lab, ha="center", va="top", fontsize=8.2, fontweight="bold", color=S.INK2, clip_on=False)
h = [Line2D([], [], marker="s", ls="", ms=9, mfc=S.ORANGE, mec="none", label="rises"), Line2D([], [], marker="s", ls="", ms=9, mfc=S.BLUE, mec="none", label="falls"),
     Line2D([], [], marker="s", ls="", ms=9, mfc=S.PURPLE, mec="none", label="shifts, either sign"),
     Line2D([], [], marker="o", ls="", ms=6.5, mfc="none", mec=S.INK2, mew=1.2, label="stays nominal (discriminating)")]
fig.legend(handles=h, loc="lower left", bbox_to_anchor=(0.20, -0.005), ncol=4, fontsize=7.8, handletextpad=0.3, columnspacing=1.3)
fig.savefig(f"{outdir}/fig_signatures.png", dpi=300); plt.close(fig)

# ------------------------------------------------------------------ federated analytics scheme
fig = plt.figure(figsize=(6.25, 4.5)); ax = fig.add_axes([0, 0, 1, 1]); ax.set_xlim(0, 100); ax.set_ylim(-4.8, 67.2); ax.axis("off")
def box(x, y, w, h, title, body, col, fs=7.4, fc="white", tfs=8.2):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=1.2", fc=fc, ec=col, lw=1.5, zorder=3))
    ax.text(x + w / 2, y + h - 2.6, title, ha="center", va="center", fontsize=tfs, fontweight="bold", zorder=4)
    ax.text(x + w / 2, y + (h - 4.4) / 2 + 0.3, body, ha="center", va="center", fontsize=fs, color=S.INK2, linespacing=1.18, zorder=4)
def arrow(p, q, col, ls="-", lw=1.4, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="-|>", mutation_scale=9, color=col, lw=lw, ls=ls, connectionstyle=f"arc3,rad={rad}", zorder=2, shrinkA=0, shrinkB=0))
# tier bands
ax.add_patch(Rectangle((0, 45.5), 100, 21.7, fc="#f1f4fa", ec="none")); ax.add_patch(Rectangle((0, 0), 100, 44.5, fc="#f1f7f1", ec="none"))
ax.text(1.6, 56.3, "backbone (GEO)", rotation=90, ha="center", va="center", fontsize=8, color=S.INK2)
ax.text(1.6, 24.5, "ground segment", rotation=90, ha="center", va="center", fontsize=8, color=S.INK2)
box(24, 48.2, 50, 16.4, "Backbone node: aggregator", "secure aggregation: only the sum of masked updates is visible\nglobal model = mean of clipped updates + noise\nsigns and distributes the model; holds no telemetry, no keys", S.BLUE, fs=7.2)
box(78, 48.2, 20, 16.4, "Other backbone\nnodes", "model replica;\nnetwork-level\ncorrelation of alarms", S.BLUE, tfs=7.8)
arrow((74, 56.4), (78, 56.4), S.BLUE); arrow((78, 53.6), (74, 53.6), S.BLUE)
xs = [4.5, 36.5, 68.5]; names = ["Ground station 1", "Ground station 2", "Ground station U"]
for x, nm in zip(xs, names):
    ax.add_patch(FancyBboxPatch((x, 2.0), 27, 38.6, boxstyle="round,pad=0,rounding_size=1.2", fc="white", ec=S.RED, lw=1.2, ls=(0, (4, 2.5)), zorder=2))
    ax.text(x + 13.5, 38.2, nm, ha="center", va="center", fontsize=8.2, fontweight="bold", zorder=4)
    box(x + 1.5, 25.6, 24, 10.2, "Local telemetry", "1-s windows, 24 features\nnever leaves the station", S.INK2, fs=7.1, fc=S.PANEL, tfs=7.6)
    box(x + 1.5, 13.6, 24, 10.2, "Local training", "update Δ$_u$; personal\nnominal baseline kept", S.GREEN, fs=7.1, tfs=7.6)
    box(x + 1.5, 3.4, 24, 8.4, "Inference and triage", "nominal / fault / attack", S.ORANGE, fs=7.1, tfs=7.6)
    arrow((x + 13.5, 25.6), (x + 13.5, 23.8), S.INK2, lw=1.0); arrow((x + 13.5, 13.6), (x + 13.5, 11.8), S.INK2, lw=1.0)
ax.text(66.0, 21.5, "…", fontsize=14, ha="center", va="center", color=S.INK2)
for x, tx in zip(xs, (36, 50, 64)):
    arrow((x + 9, 40.6), (tx - 2, 48.2), S.ORANGE, ls=(0, (1, 1.6)), lw=1.5)
    arrow((tx + 2, 48.2), (x + 18, 40.6), S.BLUE, lw=1.3)
ax.text(12.5, 46.9, "clipped, masked update", fontsize=7.2, color=S.ORANGE, ha="center", va="center", rotation=0, bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9), zorder=5)
ax.text(88.5, 46.0, "signed global model", fontsize=7.2, color=S.BLUE, ha="center", va="center", bbox=dict(fc="white", ec="none", pad=0.6, alpha=0.9), zorder=5)
h = [Line2D([], [], color=S.RED, lw=1.2, ls=(0, (4, 2.5)), label="privacy boundary of raw telemetry"),
     Line2D([], [], color=S.ORANGE, lw=1.5, ls=(0, (1, 1.6)), label="authenticated service channel (update)"),
     Line2D([], [], color=S.BLUE, lw=1.3, label="model distribution")]
ax.legend(handles=h, loc="lower center", bbox_to_anchor=(0.5, -0.005), ncol=3, fontsize=7.6, handlelength=2.4, columnspacing=1.6)
fig.savefig(f"{outdir}/fig_federated.png", dpi=300); plt.close(fig)
