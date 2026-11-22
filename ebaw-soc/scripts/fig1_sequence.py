"""Figure 1 - UML sequence diagram (message sequence chart) of the EBAW protocol."""
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Rectangle

from figstyle import FAINT, INK, MUTED, OI, save, setup

setup()
fig, ax = plt.subplots(figsize=(10.6, 8.4))
ax.set_xlim(-1.5, 101.5)
ax.set_ylim(-0.5, 100)
ax.axis("off")
FS = 13.0

parts = [
    ("LLM agent\n(proposer)", 5.5, OI["purple"]),
    ("EBAW\ngateway", 20.5, OI["blue"]),
    ("Ledger\nquorum", 39.5, OI["green"]),
    ("Policy\nstore", 54.0, OI["orange"]),
    ("Orchestrator\n(SOAR)", 68.0, OI["sky"]),
    ("Enforcement\npoint (PEP)", 83.0, OI["verm"]),
    ("SOC\nanalyst", 96.0, "#7f7f7f"),
]
TOP, BOT = 96.0, 2.0
xs = []
for name, x, col in parts:
    w = max(9.4, 2.0 + 1.0 * max(len(t) for t in name.split("\n")))
    ax.add_patch(FancyBboxPatch((x - w / 2, TOP - 3.3), w, 6.6, boxstyle="round,pad=0.2,rounding_size=0.8",
                                fc="white", ec=col, lw=2.8, zorder=3))
    ax.text(x, TOP, name, ha="center", va="center", fontsize=12.4, zorder=4, linespacing=1.05)
    ax.plot([x, x], [BOT, TOP - 3.6], color=MUTED, lw=1.5, ls=(0, (5, 4)), zorder=1)
    xs.append(x)
xa, xg, xl, xp, xo, xe, xh = xs


def act(x, y0, y1, col):
    ax.add_patch(Rectangle((x - 0.8, y1), 1.6, y0 - y1, fc=col, ec=INK, lw=1.2, zorder=4))


def msg(x0, x1, y, text, dashed=False, async_=False, fs=FS, col=INK, tx=None, ha="center"):
    sgn = 1 if x1 > x0 else -1
    ax.annotate("", xy=(x1 - sgn * 0.9, y), xytext=(x0 + sgn * 0.9, y),
                arrowprops=dict(arrowstyle="->" if async_ else "-|>", lw=2.1, color=col,
                                ls=(0, (4, 3)) if dashed else "-", mutation_scale=17, shrinkA=0, shrinkB=0),
                zorder=5)
    if tx is None:
        tx = (x0 + x1) / 2
    ax.text(tx, y + 0.8, text, ha=ha, va="bottom", fontsize=fs, zorder=6, color=INK,
            bbox=dict(fc="white", ec="none", pad=0.12))


def self_msg(x, y, text, h=3.0, side="right", fs=FS):
    ax.annotate("", xy=(x + 0.9, y - h), xytext=(x + 0.9, y),
                arrowprops=dict(arrowstyle="-|>", lw=2.0, color=INK, mutation_scale=16,
                                connectionstyle="bar,fraction=-0.6", shrinkA=0, shrinkB=0), zorder=5)
    if side == "right":
        ax.text(x + 3.8, y - h / 2, text, ha="left", va="center", fontsize=fs, zorder=6,
                bbox=dict(fc="white", ec="none", pad=0.12))
    else:
        ax.text(x - 1.6, y - h / 2, text, ha="right", va="center", fontsize=fs, zorder=6,
                bbox=dict(fc="white", ec="none", pad=0.12))


act(xg, 88.0, 57.5, OI["blue"])
act(xl, 83.5, 79.0, OI["green"])
act(xp, 73.5, 69.0, OI["orange"])
act(xo, 57.5, 41.0, OI["sky"])
act(xg, 42.0, 33.5, OI["blue"])

msg(xa, xg, 88.0, r"1  propose$(\alpha, x, \varepsilon, \hat c)$", tx=1.5, ha="left")
msg(xg, xl, 83.5, r"2  quorum read $H(\varepsilon)$", tx=xg + 1.6, ha="left")
msg(xl, xg, 79.0, r"3  $f{+}1$ final, $t_{obs}$", dashed=True, tx=xg + 1.6, ha="left")
msg(xg, xp, 73.5, r"4  get policy $\pi_v(\alpha, x)$", tx=xg + 1.6, ha="left")
msg(xp, xg, 69.0, r"5  $v$, $\theta_\rho$, $\Phi_\alpha$, $D_\alpha$", dashed=True, tx=xg + 1.6, ha="left")
self_msg(xg, 65.5, r"6  check $P_1 \wedge P_2 \wedge P_3 \wedge P_4 \wedge P_5$;   $c = g(s)$")
msg(xg, xo, 57.5, r"7  warrant $w = \mathrm{Sig}_G(\alpha, x, H(\varepsilon), v, t_{exp}, \nu)$", tx=xg + 1.6,
    ha="left")
msg(xg, xl, 53.0, r"anchor $H(w)$", async_=True, col=MUTED, tx=xg + 1.6, ha="left")

ax.annotate("", xy=(xo + 2.6, 41.4), xytext=(xo + 2.6, 57.1),
            arrowprops=dict(arrowstyle="<->", lw=1.9, color=MUTED, shrinkA=0, shrinkB=0))
ax.text(xo + 3.6, 49.3, "check-to-act\nwindow $W$", ha="left", va="center", fontsize=FS, linespacing=1.1,
        bbox=dict(fc="white", ec="none", pad=0.12), zorder=6)

msg(xo, xg, 42.0, r"8  revalidate$(w)$ at $t_{ready}$", tx=xg + 1.6, ha="left")
self_msg(xg, 38.8, r"9  re-check $P_1,\ldots,P_5$; nonce $\nu$ unused", h=3.0)

FR_X0, FR_X1, FR_Y1, FR_Y0 = xg - 4.8, xh + 4.6, 31.0, 0.2
ax.add_patch(Rectangle((FR_X0, FR_Y0), FR_X1 - FR_X0, FR_Y1 - FR_Y0, fc="none", ec=INK, lw=1.9, zorder=2))
ax.add_patch(Rectangle((FR_X0, FR_Y1 - 3.4), 5.4, 3.4, fc=FAINT, ec=INK, lw=1.6, zorder=2))
ax.text(FR_X0 + 2.7, FR_Y1 - 1.7, "alt", ha="center", va="center", fontsize=FS, zorder=3)
ax.text(FR_X0 + 6.4, FR_Y1 - 1.7, r"[ all predicates hold at $t_{ready}$ ]", ha="left", va="center", fontsize=FS,
        bbox=dict(fc="white", ec="none", pad=0.12), zorder=6)
ax.plot([FR_X0, FR_X1], [11.6, 11.6], color=INK, lw=1.5, ls=(0, (6, 4)), zorder=2)
ax.text(FR_X0 + 1.0, 10.9, "[ else ]", ha="left", va="top", fontsize=FS, bbox=dict(fc="white", ec="none", pad=0.12),
        zorder=6)

act(xe, 23.0, 16.6, OI["verm"])
msg(xg, xe, 23.0, r"10  EXECUTE$(w)$, committed within $\delta_c$", tx=xg + 1.6, ha="left")
self_msg(xe, 21.4, "11  verify $w$;\nact ($\\tau_\\alpha$)", h=3.4)
msg(xe, xl, 14.6, r"12  consume $\nu$; anchor receipt", async_=True, col=MUTED, tx=xl + 1.6, ha="left")

msg(xg, xh, 6.6, r"13  re-verify  |  escalate  |  reject   (fail-closed)", tx=xg + 6.0, ha="left")
msg(xh, xg, 2.2, r"14  human attestation $\rightarrow$ new warrant (step 7)", dashed=True, tx=xg + 6.0, ha="left")

save(fig, "fig1_sequence")
print("ok")
