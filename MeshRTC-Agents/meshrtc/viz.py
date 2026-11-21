"""
Figures and schematic diagrams for the notebook (matplotlib only).

Colours: categorical slots of a colour-vision-deficiency checked palette, used in a fixed
order; S3 (proposed) is always blue, S1 orange, S2 aqua.
"""
from __future__ import annotations

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Circle
from matplotlib.lines import Line2D

from . import protocol as pr
from .world import World, norm_cdf, RADIO

C = dict(blue="#2a78d6", orange="#eb6834", aqua="#1baf7a", yellow="#eda100", magenta="#e87ba4",
         green="#008300", violet="#6250d6", red="#e34948", ink="#0b0b0b", ink2="#52514e",
         muted="#8a8984", grid="#e4e3df", surface="#fcfcfb", water="#cfe3f5")
STRAT_COLOR = {"S1": C["orange"], "S2": C["aqua"], "S3": C["blue"], "S3N": C["violet"], "NNP": C["magenta"],
               "C": C["orange"], "A": C["blue"]}
ROBOT_COLORS = [C["blue"], C["orange"], C["aqua"], C["violet"], C["magenta"], C["green"], C["yellow"], C["red"]]


def setup_style():
    plt.rcParams.update({
        "figure.facecolor": C["surface"], "axes.facecolor": C["surface"], "savefig.facecolor": C["surface"],
        "axes.edgecolor": C["muted"], "axes.labelcolor": C["ink"], "text.color": C["ink"],
        "xtick.color": C["ink2"], "ytick.color": C["ink2"], "axes.grid": True, "grid.color": C["grid"],
        "grid.linewidth": 0.6, "axes.spines.top": False, "axes.spines.right": False,
        "font.size": 10, "axes.titlesize": 11, "axes.titleweight": "bold", "legend.frameon": False,
        "figure.dpi": 110, "savefig.dpi": 200, "savefig.bbox": "tight",
    })


# =========================================================================== maps
def plot_town(w: World, ax=None, value=None, cmap="RdYlGn", vlabel="", repeaters=None, sites=True,
              alpha_streets=1.0, blocked=None, legend=True):
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 6))
    X, Y = w.size
    a, b = w.shore_ab
    xs = np.array([-300, X + 300])
    ax.fill_between(xs, a + b * xs - 60, Y + 400, color=C["water"], zorder=0, lw=0)
    ax.text(250, Y - 150, "reservoir", color="#4a7aa8", style="italic", fontsize=9)
    cols = ["#3a3a38", "#9a9994", "#c49a6c"]
    lws = [2.2, 1.0, 1.0]
    for (u, v), c in zip(w.edges, w.ecls):
        ax.plot(*w.xy[[u, v]].T, color=cols[c], lw=lws[c], alpha=alpha_streets, zorder=1, solid_capstyle="round")
    if blocked is not None:
        for e in np.where(blocked)[0]:
            u, v = w.edges[e]
            ax.plot(*w.xy[[u, v]].T, color=C["red"], lw=2.5, zorder=2)
            m = w.xy[[u, v]].mean(0)
            ax.plot(*m, marker="x", color=C["red"], ms=6, mew=2, zorder=3)
    if value is not None:
        sc = ax.scatter(*w.xy.T, c=value, cmap=cmap, s=16, zorder=3, vmin=0, vmax=1, edgecolors="none")
        cb = plt.colorbar(sc, ax=ax, shrink=0.75, pad=0.01)
        cb.set_label(vlabel)
    if repeaters is not None:
        for i, n in enumerate(repeaters):
            ax.plot(*w.xy[n], marker="^", ms=11, color=C["violet"], mec="white", mew=1.2, zorder=5)
            ax.annotate(f"RP{i + 1}", w.xy[n], xytext=(5, 5), textcoords="offset points", fontsize=8,
                        color=C["violet"])
    if sites:
        for k, s in w.sites.items():
            mk, col = {"depot": ("s", C["ink"]), "recipient": ("o", C["orange"]),
                       "recovery": ("P", C["green"])}[s.kind]
            ax.plot(*w.xy[s.node], marker=mk, ms=10 if s.kind != "depot" else 12, color=col, mec="white",
                    mew=1.5, zorder=6)
            ax.annotate(k if k != "H0" else "H0 depot+CC", w.xy[s.node], xytext=(6, -11),
                        textcoords="offset points", fontsize=9, weight="bold", color=C["ink"], zorder=7)
    if legend:
        h = [Line2D([], [], color=cols[0], lw=2.2, label="arterial"), Line2D([], [], color=cols[1], lw=1, label="local"),
             Line2D([], [], color=cols[2], lw=1, label="unpaved"),
             Line2D([], [], marker="s", ls="", color=C["ink"], label="depot / CC gateway"),
             Line2D([], [], marker="o", ls="", color=C["orange"], label="recipient site R"),
             Line2D([], [], marker="P", ls="", color=C["green"], label="recovery point P")]
        if repeaters is not None:
            h.append(Line2D([], [], marker="^", ls="", color=C["violet"], label="solar repeater"))
        ax.legend(handles=h, loc="lower left", fontsize=8, ncol=2, framealpha=0.9, frameon=True)
    ax.set_xlim(-200, X + 100)
    ax.set_ylim(-250, Y + 50)
    ax.set_aspect("equal")
    ax.grid(False)
    ax.set_xticks([])
    ax.set_yticks([])
    for s in ax.spines.values():
        s.set_visible(False)
    return ax


def plot_coverage_panels(w: World, ks=(0, 2, 4, 8)):
    from .world import RadioFabric
    fig, axs = plt.subplots(1, len(ks), figsize=(4.2 * len(ks), 3.4))
    for ax, k in zip(axs, ks):
        fab = RadioFabric(w, k)
        p = fab.contact_probability()
        plot_town(w, ax, sites=False, legend=False, alpha_streets=0.35)
        sc = ax.scatter(*w.xy.T, c=p, cmap="RdYlGn", vmin=0, vmax=1, s=9, zorder=3)
        for n in fab.repeaters:
            ax.plot(*w.xy[n], "^", color=C["violet"], ms=8, mec="white", zorder=5)
        ax.set_title(f"k = {k} repeaters: {(p > 0.5).mean():.0%} nodes with P>0.5", fontsize=10)
    fig.colorbar(sc, ax=axs, shrink=0.8, label="P(mesh contact)")
    return fig


def plot_mission(sim, ax=None, title=None, show_blocked=True, annotate=True):
    w = sim.w
    if ax is None:
        _, ax = plt.subplots(figsize=(9, 6))
    plot_town(w, ax, sites=True, legend=False, alpha_streets=0.45,
              blocked=sim.sc.blocked if show_blocked else None,
              repeaters=sim.sc.fab.repeaters)
    for i, r in enumerate(sim.robots):
        col = C["green"] if r.is_relay else ROBOT_COLORS[i % len(ROBOT_COLORS)]
        nodes = [w.depot] + [x[1] for x in r.trace]
        if len(nodes) > 1:
            pts = w.xy[nodes]
            ax.plot(*pts.T, color=col, lw=3.0, alpha=0.85, zorder=8, label=f"{r.name} ({r.strategy})" if not r.is_relay else "relay UGV")
            lost = [x[4] for x in r.trace]
            nc = [k for k, c in enumerate(lost) if not c]
            if nc:
                ax.scatter(*w.xy[[r.trace[k][1] for k in nc]].T, s=22, facecolor="white", edgecolor=col, zorder=9, lw=1.2)
            ax.plot(*pts[-1], marker="*", ms=16, color=col, mec="white", zorder=10)
        if annotate:
            for (t, node, code, info, soc) in r.decisions:
                if code in ("HANDOVER", "RTG", "RET", "BLK", "BEACON-STOP", "DCL", "DRP", "HOLD", "CAUTIOUS",
                            "WRONG-TURN", "MAST-UP", "DEPLETED", "RECOVERED", "SHIELD", "HOLD-CMD", "WAIT"):
                    ax.annotate(f"{code} {info}\nt={t:.0f}′ SoC {soc:.0%}", w.xy[node], xytext=(8, 8),
                                textcoords="offset points", fontsize=7.5, color=C["ink"], zorder=11,
                                bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=col, lw=0.8, alpha=0.9))
    if sim.relay_node is not None:
        ax.add_patch(Circle(w.xy[sim.relay_node], 900, fc=C["green"], alpha=0.08, zorder=0))
    if ax.get_legend_handles_labels()[0]:
        ax.legend(loc="lower left", fontsize=8, frameon=True)
    if title:
        ax.set_title(title)
    return ax


def plot_energy(sims: dict, ax=None):
    """State of charge over time for several strategies (paired runs)."""
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 3.6))
    for s, sim in sims.items():
        r = sim.robots[0]
        tt = [0] + [x[0] for x in r.trace]
        ee = [r.cap * sim.cfg.soc0] + [x[2] for x in r.trace]
        ax.plot(tt, np.array(ee) / r.cap * 100, color=STRAT_COLOR.get(s, C["ink"]), lw=2, label=s)
        m = sim.mission_metrics()[0]
        ax.annotate(m["terminal"], (tt[-1], ee[-1] / r.cap * 100), xytext=(4, 0), textcoords="offset points",
                    fontsize=8, color=C["ink2"])
    ax.axhline(8, color=C["red"], lw=1, ls="--")
    ax.text(1, 9, "cut-off 8 %", fontsize=8, color=C["red"])
    ax.set_xlabel("time, min")
    ax.set_ylabel("state of charge, %")
    ax.legend()
    return ax


# =========================================================================== sequence diagram
def sequence_diagram(sim, max_msgs=28, ax=None, lanes=None, t_max=None, skip_ops=("RS",)):
    pk = [p for p in sim.packets if p.cmd.op not in skip_ops and (t_max is None or p.t_send <= t_max)]
    pk = sorted(pk, key=lambda p: p.t_send)[:max_msgs]
    if lanes is None:
        names = []
        for p in pk:
            for n in (p.src, p.dst):
                if n not in names and not n.startswith("^"):
                    names.append(n)
        order = ["CC"] + sorted([n for n in names if n.startswith("U")]) + sorted([n for n in names if n.startswith("N")])
        lanes = [n for n in order if n in names] or ["CC"]
    lanes = lanes + ["all"]
    x = {n: i for i, n in enumerate(lanes)}
    if ax is None:
        _, ax = plt.subplots(figsize=(1.9 * len(lanes) + 3, 0.36 * len(pk) + 1.4))
    H = len(pk) + 1
    for n, i in x.items():
        ax.plot([i, i], [0.3, H], color=C["muted"], lw=1, zorder=0)
        ax.text(i, H + 0.25, n if n != "CC" else "CC (gateway)", ha="center", va="bottom", weight="bold",
                bbox=dict(boxstyle="round", fc=C["grid"], ec="none"))
    path_col = {"mesh": C["blue"], "cell": C["ink2"], "p2p": C["violet"], "dock": C["green"],
                "local": C["muted"], "": C["red"], "dtn": C["orange"]}
    for k, p in enumerate(pk):
        y = H - k - 0.6
        src = p.src if p.src in x else ("all" if p.src.startswith("^") else lanes[0])
        dst = "all" if p.dst.startswith("^") else (p.dst if p.dst in x else "CC")
        col = path_col.get(p.path, C["ink2"])
        delivered = np.isfinite(p.t_recv)
        ax.annotate("", xy=(x[dst], y), xytext=(x[src], y),
                    arrowprops=dict(arrowstyle="-|>", color=col, lw=1.6, ls="-" if delivered else ":"))
        lat = f"{p.latency:.1f}′" if delivered else "not delivered"
        mid = (x[src] + x[dst]) / 2 if src != dst else x[src] + 0.3
        ax.text(mid, y + 0.12, p.cmd.text(), ha="center", va="bottom", fontsize=7.6, family="monospace")
        ax.text(-0.6, y, f"t={p.t_send:5.1f}′", ha="right", va="center", fontsize=7.5, color=C["ink2"])
        ax.text(len(lanes) - 0.4, y, f"{p.path or '-'} · {p.size} B · {lat}", ha="left", va="center",
                fontsize=7.2, color=col)
    ax.set_xlim(-1.6, len(lanes) + 1.4)
    ax.set_ylim(0, H + 1)
    ax.axis("off")
    hs = [Line2D([], [], color=v, lw=2, label=k) for k, v in path_col.items() if k and any(p.path == k for p in pk)]
    ax.legend(handles=hs, loc="lower right", fontsize=8, ncol=len(hs), title="channel", title_fontsize=8)
    return ax


# =========================================================================== schematic diagrams
def _box(ax, x, y, w, h, text, fc, ec=None, fs=9, weight="normal", tc=None):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.08", fc=fc,
                                ec=ec or "none", lw=1.2, zorder=2))
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center", fontsize=fs, weight=weight, zorder=3,
            color=tc or C["ink"], wrap=True)


def _arrow(ax, p, q, col=None, ls="-", lw=1.4, both=False, rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle="<|-|>" if both else "-|>", mutation_scale=12, color=col or C["ink2"],
                                 lw=lw, ls=ls, zorder=1, connectionstyle=f"arc3,rad={rad}"))


def architecture_diagram():
    fig, ax = plt.subplots(figsize=(12, 6.6))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 7)
    ax.axis("off")
    levels = [
        ("L4  Human on the loop", "#f3e9f7", ["Operator console", "Intent parser N4\n(advisory, validated)",
                                              "Audit log: signed\nreceipts & decisions"]),
        ("L3  Agentic control plane", "#e6f0fb", ["Orchestrator\n(TSK, CLS, RTB)", "Comms steward\n(1 % duty, RPT)",
                                                  "Fleet market\n(BID / LSE)", "Robot agent SFC\n+ safety monitor"]),
        ("L2  Degrading comm fabric", "#e8f6ef", ["Cellular\n(fades with outage age)", "Meshtastic LoRa mesh\nGW · repeaters · nodes",
                                                  "Peer-to-peer / DTN\nstore-carry-forward"]),
        ("L1  Physical transport", "#fdf0e6", ["Depot + chargers", "Delivery UGVs\n(offline graph)", "Relay UGV\n10 m mast",
                                               "Recipient sites R\n& recovery points P"]),
    ]
    for i, (name, fc, items) in enumerate(levels):
        y = 5.4 - i * 1.55
        ax.add_patch(FancyBboxPatch((0.1, y - 0.1), 9.6, 1.35, boxstyle="round,pad=0.02,rounding_size=0.12",
                                    fc=fc, ec="none", zorder=0))
        ax.text(0.25, y + 1.08, name, fontsize=10, weight="bold", va="center")
        n = len(items)
        bw = (9.2 - 0.25 * (n - 1)) / n
        for j, it in enumerate(items):
            _box(ax, 0.3 + j * (bw + 0.25), y, bw, 0.85, it, "white", ec=C["muted"], fs=8.5)
    _box(ax, 10.0, 0.25, 1.85, 6.4, "DIGITAL\nTWIN\n\nsynthetic town\nradio model\nenergy model\nscenarios S01-S10\n\nplans relay,\nsets risk z,\nexplains", "#fff6dc",
         ec=C["yellow"], fs=8.5)
    for i in range(3):
        y = 5.4 - i * 1.55
        _arrow(ax, (3.0, y - 0.1), (3.0, y - 0.45), C["blue"])
        _arrow(ax, (6.5, y - 0.45), (6.5, y - 0.1), C["orange"])
    ax.text(3.1, 0.02, "plans · contracts · risk settings ↓", color=C["blue"], fontsize=8.5)
    ax.text(6.0, 0.02, "↑ telemetry · receipts · decisions", color=C["orange"], fontsize=8.5)
    ax.set_title("Robotic transport complex: four levels with bounded autonomy and a digital twin")
    return fig


def agent_society_diagram():
    fig, ax = plt.subplots(figsize=(11, 6.2))
    ax.set_xlim(0, 11)
    ax.set_ylim(0, 6.4)
    ax.axis("off")
    P = {"CC": (4.6, 5.2), "U1": (1.2, 2.6), "U2": (4.6, 2.2), "U3": (8.0, 2.6), "R": (8.6, 5.0),
         "Relay": (1.0, 5.0), "Twin": (8.4, 0.5)}
    labels = {"CC": "Orchestrator +\nComms steward\n(CC gateway)", "U1": "Robot U1\nSFC", "U2": "Robot U2\nSFC",
              "U3": "Robot U3\nSFC", "R": "Recipient node\n(site R)", "Relay": "Relay UGV\n(mast)",
              "Twin": "Digital twin\nplanner"}
    fcs = {"CC": "#e6f0fb", "R": "#fdf0e6", "Relay": "#e8f6ef", "Twin": "#fff6dc"}
    for k, (x, y) in P.items():
        _box(ax, x - 0.85, y - 0.45, 1.7, 0.9, labels[k], fcs.get(k, "white"), ec=C["muted"], fs=8.5)
    def lab(p, q, text, col, ls="-", rad=0.0, off=(0, 0.12)):
        _arrow(ax, p, q, col, ls, rad=rad)
        m = ((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1])
        ax.text(*m, text, fontsize=7.8, family="monospace", ha="center", color=col,
                bbox=dict(fc=C["surface"], ec="none", pad=0.5))
    lab((4.0, 4.75), (1.6, 3.05), "TSK · CLS · BLK U0\nZSET · RTB · HLD", C["blue"], off=(-0.5, 0.1))
    lab((1.9, 3.05), (4.2, 4.75), "DEC · BLK · RCP · RS", C["orange"], rad=0.25, off=(0.4, -0.2))
    lab((4.6, 4.75), (4.6, 2.65), "TSK / ACK", C["blue"], off=(0.45, 0))
    lab((8.0, 4.55), (5.45, 5.0), "REQ · RCP copy", C["orange"], off=(0.1, 0.15))
    lab((5.3, 4.8), (7.6, 3.05), "TSK", C["blue"])
    lab((3.7, 5.2), (1.85, 5.1), "RLY", C["blue"])
    lab((2.05, 2.5), (3.75, 2.25), "BID · LSE (p2p)", C["violet"], ls="--")
    lab((5.45, 2.25), (7.15, 2.5), "BID · LSE (p2p)", C["violet"], ls="--")
    lab((8.25, 3.05), (8.55, 4.55), "REQ pickup (DTN)", C["violet"], ls="--", off=(0.75, 0))
    lab((7.6, 0.6), (5.0, 4.75), "relay node, risk z", C["green"], ls=":", rad=-0.2, off=(0.3, -0.6))
    h = [Line2D([], [], color=C["blue"], lw=2, label="downlink: CC → robots (mesh / cellular)"),
         Line2D([], [], color=C["orange"], lw=2, label="uplink: robots / sites → CC"),
         Line2D([], [], color=C["violet"], lw=2, ls="--", label="peer-to-peer, store-carry-forward"),
         Line2D([], [], color=C["green"], lw=2, ls=":", label="twin planning")]
    ax.legend(handles=h, loc="lower left", fontsize=8.5)
    ax.set_title("Agent society and the short Meshtastic commands they exchange")
    return fig


def authority_diagram():
    fig, ax = plt.subplots(figsize=(9, 3.6))
    regimes = ["C0 full", "C1 mesh only", "C2 intermittent", "C3 isolated"]
    cc = np.array([0.75, 0.55, 0.25, 0.0])
    market = np.array([0.0, 0.15, 0.35, 0.0])
    robot = 1 - cc - market
    x = np.arange(4)
    ax.bar(x, cc, color=C["blue"], width=0.6, label="CC orchestrator (assign, veto)", edgecolor=C["surface"], lw=2)
    ax.bar(x, market, bottom=cc, color=C["violet"], width=0.6, label="fleet market (leases)", edgecolor=C["surface"], lw=2)
    ax.bar(x, robot, bottom=cc + market, color=C["orange"], width=0.6, label="robot SFC (contract)", edgecolor=C["surface"], lw=2)
    ax.set_xticks(x, regimes)
    ax.set_ylabel("share of decision authority\n(illustrative)")
    ax.set_ylim(0, 1.05)
    ax.legend(loc="upper left", bbox_to_anchor=(1.0, 1.0))
    ax.set_title("Authority migrates to the robot as connectivity degrades;\nthe safety monitor may always stop")
    return fig


def statechart_diagram():
    fig, ax = plt.subplots(figsize=(12, 5.4))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 5.6)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch((0.1, 3.7), 11.8, 1.7, boxstyle="round,pad=0.02", fc="#eef4fb", ec="none"))
    ax.text(0.25, 5.15, "Region A: connectivity mode (who holds authority)", weight="bold", fontsize=9.5)
    xs = [1.0, 3.9, 6.8, 9.7]
    for x, t in zip(xs, ["C0 / C1\nconnected", "C2\nintermittent", "C3\nisolated", "lost (σ↑)\ncautious κ=0.6"]):
        _box(ax, x, 3.9, 1.8, 0.9, t, "white", ec=C["blue"], fs=8.5)
    for a, b in zip(xs[:-1], xs[1:]):
        _arrow(ax, (a + 1.8, 4.45), (b, 4.45), C["blue"], both=True)
    ax.add_patch(FancyBboxPatch((0.1, 0.1), 11.8, 3.4, boxstyle="round,pad=0.02", fc="#fdf3ea", ec="none"))
    ax.text(0.25, 3.25, "Region B: mission mode (evaluated at every decision epoch)", weight="bold", fontsize=9.5)
    S = {"OUT": (0.4, 1.6, "OUTBOUND\nfollow π(x→d)"), "RTG": (3.1, 2.35, "RE-TARGET\nd ← d_alt"),
         "HAND": (3.1, 0.35, "HANDOVER\nRCP + PIN"), "RET": (6.0, 1.6, "RETURN\nρ*(x), comm-aware"),
         "HOLD": (6.0, 0.25, "HOLD at site\n(one-way)"), "STOP": (8.9, 2.35, "BEACON-STOP\n15 W, best coverage"),
         "REC": (8.9, 0.35, "RECOVERED\nupload receipts")}
    for k, (x, y, t) in S.items():
        col = {"STOP": C["red"], "REC": C["green"], "HOLD": C["yellow"]}.get(k, C["orange"])
        _box(ax, x, y, 2.1, 0.8, t, "white", ec=col, fs=8.3)
    def tr(a, b, txt, rad=0.0, off=(0, 0.1)):
        xa, ya, _ = S[a]
        xb, yb, _ = S[b]
        p = (xa + 2.1, ya + 0.4) if xb > xa else (xa + 1.05, ya + (0.8 if yb > ya else 0))
        q = (xb, yb + 0.4) if xb > xa else (xb + 1.05, yb + (0 if yb > ya else 0.8))
        _arrow(ax, p, q, C["ink2"], rad=rad)
        ax.text((p[0] + q[0]) / 2 + off[0], (p[1] + q[1]) / 2 + off[1], txt, fontsize=7.6, ha="center",
                color=C["ink"], bbox=dict(fc="#fdf3ea", ec="none", pad=0.3))
    tr("OUT", "RTG", "CLS ∧ F_D(alt)", off=(-0.1, 0.15))
    tr("OUT", "HAND", "at d", off=(-0.1, -0.2))
    tr("OUT", "RET", "¬F_D ∧ F_R  (DEC RET)", off=(0, 0.12))
    tr("RET", "STOP", "¬F_R  (DEC STP)", off=(0, 0.12))
    tr("RET", "REC", "at ρ*", off=(0.2, -0.25))
    tr("HAND", "HOLD", "one-way ∧ ¬F_R", off=(0, -0.25))
    ax.text(0.3, 0.02, "F_D: A_t ≥ N(π_x→d ⊕ π_d→ρ*)   F_R: A_t ≥ N(π_x→ρ*)   F_H: A_t ≥ N(π_x→d)   "
            "N(π) = r̂μ + z·√(Σ(σ_e ê)² + (σ_r r̂ μ)²) + εC", fontsize=8.4, family="monospace")
    ax.set_title("Supervisory Feasibility Controller (SFC) as a statechart")
    return fig


# =========================================================================== protocol figures
def protocol_size_figure():
    ex = {"TSK": pr.TSK(17, 3, 5, 860), "RS": pr.RS(3, 217, 0.41, 182, 2), "DEC": pr.DEC(3, "RET", "P1", 0.27),
          "BLK": pr.BLK(3, 447), "RCP": pr.RCP(17, 3, 822, 3), "CLS": pr.CLS(3, 5), "REQ": pr.REQ(4, 1, 2, 1, 21),
          "BID": pr.BID(21, 2, 845), "LSE": pr.LSE(21, 2), "RTB": pr.RTB(3, 1), "RLY": pr.RLY(9, 133),
          "ZSET": pr.ZSET(2.33), "HLD": pr.HLD(3, 30), "ACK": pr.ACK(77)}
    ops = list(ex)
    tb = [len(ex[o].text()) for o in ops]
    bb = [len(ex[o].binary()) for o in ops]
    fig, axs = plt.subplots(1, 2, figsize=(13, 3.8))
    x = np.arange(len(ops))
    axs[0].bar(x - 0.2, tb, 0.38, color=C["blue"], label="text template")
    axs[0].bar(x + 0.2, bb, 0.38, color=C["orange"], label="binary + CRC-16")
    axs[0].set_xticks(x, ops, rotation=0, fontsize=8)
    axs[0].set_ylabel("payload, bytes")
    axs[0].set_title("Payload size of each command (+16 B Meshtastic header)")
    axs[0].legend()
    presets = ["SHORT_FAST", "MEDIUM_FAST", "LONG_FAST"]
    for i, (p, col) in enumerate(zip(presets, [C["blue"], C["orange"], C["aqua"]])):
        axs[1].plot(x, [pr.frame_airtime(n, p) * 1000 for n in tb], "-o", color=col, ms=4, lw=2, label=f"{p} text")
        axs[1].plot(x, [pr.frame_airtime(n, p) * 1000 for n in bb], "--", color=col, lw=1.5, label=f"{p} binary")
    axs[1].set_yscale("log")
    axs[1].set_xticks(x, ops, fontsize=8)
    axs[1].set_ylabel("airtime per frame, ms (log)")
    axs[1].set_title("LoRa time on air (Eq. 1)")
    axs[1].legend(fontsize=7.5, ncol=3, loc="upper center", bbox_to_anchor=(0.5, -0.12))
    return fig


def airtime_budget_figure(u0=29.5, n_max=120):
    n = np.arange(0, n_max + 1)
    fig, axs = plt.subplots(1, 2, figsize=(12, 4))
    for pol, ls in (("periodic", "-"), ("event", "--")):
        tau = pr.tau_per_robot("SHORT_FAST", pol)
        axs[0].plot(n, pr.gateway_utilisation(n, tau, u0), ls, color=C["blue"], lw=2,
                    label=f"{pol}: τ = {tau:.2f} s/h per robot")
    axs[0].axhline(100, color=C["red"], lw=1.2)
    axs[0].text(2, 103, "1 % duty-cycle budget = 36 s/h", color=C["red"], fontsize=8.5)
    axs[0].set_ylim(0, 160)
    axs[0].set_title(f"(a) Gateway shared with facility traffic (U₀ = {u0} %), SHORT_FAST")
    axs[0].set_xlabel("number of robots")
    axs[0].set_ylabel("gateway utilisation, % of budget")
    axs[0].legend()
    for p, col in zip(["SHORT_FAST", "MEDIUM_FAST", "LONG_FAST"], [C["blue"], C["orange"], C["aqua"]]):
        for pol, ls in (("periodic", "-"), ("event", "--")):
            tau = pr.tau_per_robot(p, pol)
            axs[1].plot(n, pr.gateway_utilisation(n, tau), ls, color=col, lw=2, label=f"{p} {pol}")
    axs[1].axhline(100, color=C["red"], lw=1.2)
    axs[1].set_ylim(0, 160)
    axs[1].set_title("(b) Dedicated robot-operations gateway")
    axs[1].set_xlabel("number of robots")
    axs[1].legend(fontsize=8, ncol=2)
    return fig


# =========================================================================== neural figures
def draw_mlp(ax, sizes, in_labels=None, out_labels=None, title="", max_show=10, color=C["blue"]):
    ax.axis("off")
    L = len(sizes)
    xs = np.linspace(0.08, 0.92, L)
    pos = []
    for li, (x, n) in enumerate(zip(xs, sizes)):
        show = min(n, max_show)
        ys = np.linspace(0.88, 0.12, show) if show > 1 else [0.5]
        pos.append([(x, y) for y in ys])
        for k, (xx, yy) in enumerate(pos[-1]):
            fc = C["orange"] if li == 0 else (C["aqua"] if li == L - 1 else color)
            ax.add_patch(Circle((xx, yy), 0.018, fc=fc, ec="white", lw=0.8, zorder=3))
        if n > max_show:
            ax.text(x, 0.04, f"{n} units", ha="center", fontsize=8, color=C["ink2"])
        else:
            ax.text(x, 0.04, f"{n}", ha="center", fontsize=8, color=C["ink2"])
    for a, b in zip(pos[:-1], pos[1:]):
        for p in a:
            for q in b:
                ax.plot([p[0], q[0]], [p[1], q[1]], color=C["muted"], lw=0.25, alpha=0.6, zorder=1)
    if in_labels:
        for (x, y), t in zip(pos[0], in_labels[:max_show]):
            ax.text(x - 0.03, y, t, ha="right", va="center", fontsize=7.4)
    if out_labels:
        for (x, y), t in zip(pos[-1], out_labels[:max_show]):
            ax.text(x + 0.03, y, t, ha="left", va="center", fontsize=7.8)
    ax.set_xlim(-0.25, 1.25)
    ax.set_ylim(0, 1)
    ax.set_title(title, fontsize=10)


def neural_overview_figure():
    from .neural import ENERGY_FEATURES, POLICY_FEATURES, CONTACT_FEATURES, INTENTS, ACTIONS_NN
    fig, axs = plt.subplots(2, 2, figsize=(14, 9))
    draw_mlp(axs[0, 0], [10, 32, 32, 2], ENERGY_FEATURES, ["μ ratio", "log σ²"],
             "N1 EnergyEnsemble (×5 members, Gaussian NLL)")
    draw_mlp(axs[0, 1], [13, 64, 32, 3], POLICY_FEATURES, ACTIONS_NN, "N2 PolicyNet (behaviour cloning of SFC)")
    draw_mlp(axs[1, 0], [8, 32, 16, 2], CONTACT_FEATURES, ["no contact", "contact"], "N3 ContactNet (mesh coverage)")
    draw_mlp(axs[1, 1], [2048, 128, 7], ["hashed char", "3-4-grams", "+ words"], INTENTS,
             "N4 IntentNet (operator text → command)")
    fig.suptitle("Neural modules of the robotic transport complex (NumPy MLPs)", weight="bold")
    return fig


def shield_pipeline_figure():
    fig, ax = plt.subplots(figsize=(13, 3.6))
    ax.set_xlim(0, 13)
    ax.set_ylim(0, 3.6)
    ax.axis("off")
    items = [(0.1, "Observation\nSoC, energy needs,\nσ, contact, z", "#fdf0e6"),
             (2.7, "Neural proposal\nN2 PolicyNet\n(N1 energy μ, σ)", "#e6f0fb"),
             (5.3, "Shield (verified)\nF_D, F_R, F_H\nchance constraint", "#e8f6ef"),
             (7.9, "Action\nCONTINUE / RETURN\n/ STOP", "white"),
             (10.5, "Short command\nDEC U3 RET P1 S27\n→ Meshtastic", "#fff6dc")]
    for x, t, fc in items:
        _box(ax, x, 1.2, 2.3, 1.4, t, fc, ec=C["muted"], fs=9)
    for (x, _, _), (x2, _, _) in zip(items[:-1], items[1:]):
        _arrow(ax, (x + 2.3, 1.9), (x2, 1.9), C["ink2"])
    _arrow(ax, (6.45, 1.2), (3.85, 1.2), C["red"], rad=-0.4)
    ax.text(5.15, 0.25, "override if unsafe (logged as SHIELD)", color=C["red"], ha="center", fontsize=8.5)
    ax.text(0.1, 3.25, "Runtime assurance (Simplex): the network may be wrong, the shield keeps the robot recoverable; "
            "operator text passes N4 → validator → command in the same way.", fontsize=9)
    return fig
