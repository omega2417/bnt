"""Builds notebooks/MeshRTC_Agents_Colab.ipynb (run from the project root)."""
import os
import nbformat as nbf

nb = nbf.v4.new_notebook()
cells = []


def md(s):
    cells.append(nbf.v4.new_markdown_cell(s.strip("\n")))


def code(s):
    cells.append(nbf.v4.new_code_cell(s.strip("\n")))


# =============================================================================== 0
md(r"""
# MeshRTC-Agents: Software Agents for Robotic Transport Platforms Coordinated by Short Meshtastic Commands

**A synthetic-data digital twin of a robotic transport complex for emergency deliveries during deep blackouts**

[![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/)
&nbsp; Version 1.1.0 (English edition) · code: MIT licence; text and figures: CC BY 4.0 · all data are **synthetic**

---

**Abstract:** During prolonged power outages, a ground robot that carries medicines or drinking water may lose contact with its dispatcher halfway through a journey. This notebook accompanies the study *Agentic Supervisory Control of a Robotic Transport Complex for Emergency Deliveries during Deep Blackouts* (D. Prokopovych-Tkachenko, University of Customs and Finance, Dnipro, Ukraine), prepared for the Special Issue "Advanced Control Topics on Robotic Vehicles, 2nd Edition" of *Information* (MDPI). It implements a society of software agents (a crisis-coordination orchestrator, a comms steward, onboard robot agents, recipient nodes and a relay unmanned ground vehicle) that exchange short commands over a Meshtastic LoRa mesh. The notebook presents the command protocol and its airtime budget, a synthetic town with a radio model, the Supervisory Feasibility Controller (SFC), ten transport scenarios, paired Monte Carlo experiments and four neural modules that operate under a runtime-assurance shield.

**Keywords:** Meshtastic; LoRa; ground delivery robot; multi-agent systems; supervisory control; delay-tolerant networking; chance constraints; digital twin; neural networks; runtime assurance

**Table 1.** Structure of the notebook.

| Section | Content |
|---|---|
| 1 | Installation in Google Colab |
| 2 | Concept: four levels of the robotic transport complex, agent society, migration of decision authority |
| 3 | **Short-command protocol over Meshtastic**: catalogue, text and binary encodings, LoRa airtime, 1% duty-cycle budget |
| 4 | Synthetic town, radio model and mesh coverage |
| 5 | Robot agent: Supervisory Feasibility Controller, energy model and chance constraints |
| 6 | **Ten transport scenarios S01–S10** with route maps and message sequence charts |
| 7 | Paired Monte Carlo experiment: S1 (stop-on-loss), S2 (fixed-route), S3 (SFC); risk dial *z* |
| 8 | Fleet level: centralized versus agentic coordination (DTN and BID/LSE auction) |
| 9 | **Neural modules N1–N4**: energy ensemble, shielded neural policy, coverage predictor, operator intent parser |
| 10 | Limitations, reproducibility, data availability and citation |

> **Note.** All quantitative results are simulation outputs obtained on synthetic data. The town is only *inspired by* the planning grid of Verkhnodniprovsk, Ukraine, and is not a map of it. The results establish conditional feasibility and identify mechanisms; they do not establish operational readiness.
""")

# =============================================================================== 1
md(r"""
## 1. Installation

The `meshrtc` package requires only `numpy`, `pandas` and `matplotlib`, all of which are preinstalled in Colab. The cell below locates the package as follows:

1. if the notebook is opened from the unpacked archive, the local copy is used;
2. if `MeshRTC-Agents-v1.1.0.zip` is present in `/content`, it is unpacked;
3. if `ZENODO_ZIP_URL` is set, the archive is downloaded from Zenodo;
4. otherwise, Colab prompts the user to upload the zip file.
""")
code(r"""
import os, sys, glob, zipfile, urllib.request

ZENODO_ZIP_URL = ""   # after publication: https://zenodo.org/records/<ID>/files/MeshRTC-Agents-v1.1.0.zip?download=1

def find_root():
    for cand in [".", "..", "/content/MeshRTC-Agents-v1.1.0", "/content/MeshRTC-Agents"]:
        if os.path.isdir(os.path.join(cand, "meshrtc")):
            return os.path.abspath(cand)
    return None

ROOT = find_root()
if ROOT is None:
    zips = sorted(glob.glob("/content/MeshRTC-Agents*.zip") + glob.glob("MeshRTC-Agents*.zip"))
    if not zips and ZENODO_ZIP_URL:
        urllib.request.urlretrieve(ZENODO_ZIP_URL, "/content/MeshRTC-Agents-v1.1.0.zip")
        zips = ["/content/MeshRTC-Agents-v1.1.0.zip"]
    if not zips and "google.colab" in sys.modules:
        from google.colab import files
        print("Please upload MeshRTC-Agents-v1.1.0.zip ...")
        zips = [k for k in files.upload() if k.endswith(".zip")]
    with zipfile.ZipFile(zips[0]) as z:
        z.extractall("/content")
    ROOT = find_root()
sys.path.insert(0, ROOT)
print("project root:", ROOT)
""")
code(r"""
import numpy as np, pandas as pd, matplotlib.pyplot as plt, time
import meshrtc
from meshrtc import protocol as pr, viz, experiments as ex
from meshrtc.world import World, RadioFabric, ROBOT, RADIO, dijkstra
from meshrtc.sim import Config, Sim, run_paired, STRAT_NAMES
from meshrtc.scenarios import SCENARIOS, run_scenario, run_scenario_paired, get
from meshrtc.fleet import FleetLogic
from meshrtc import neural as nn

viz.setup_style()
pd.set_option("display.width", 160); pd.set_option("display.max_colwidth", 60)
FIG = os.path.join(ROOT, "figures"); os.makedirs(FIG, exist_ok=True)
def save(fig, name):
    fig.savefig(os.path.join(FIG, name)); plt.show()
print("meshrtc", meshrtc.__version__)
""")

# =============================================================================== 2
md(r"""
## 2. Concept of the Robotic Transport Complex

During a prolonged power outage, a ground robot that carries medicines or drinking water may lose contact with its dispatcher halfway through a journey. The robotic transport complex (RTC) is therefore organized as a **society of agents with bounded autonomy** across four levels (Figure 1):

* **L1, physical transport:** a depot with generator-backed chargers, delivery unmanned ground vehicles (UGVs) with an offline street graph and obstacle sensing, a relay UGV with a 10 m telescopic mast, recipient sites R1–R8 and recovery points P1–P3.
* **L2, degrading communication fabric:** cellular service that fades as base-station reserves are exhausted; the **Meshtastic** mesh (crisis-coordination centre (CC) gateway in the CLIENT_MUTE role, solar repeaters in the ROUTER_LATE role, facility nodes); peer-to-peer exchange and delay-tolerant store-carry-forward (DTN).
* **L3, agentic control plane:** the orchestrator, the comms steward, the fleet market, the onboard robot agent (SFC) and the safety monitor.
* **L4, human on the loop:** the operator, an advisory intent parser (N4) whose output is checked by a deterministic validator, and an audit log.

The central design choice is that **authority is a function of connectivity** (Figure 3). When the CC is reachable, it assigns tasks and may veto an abort; under intermittent contact, the fleet market allocates requests under leases; when isolated, the robot acts on a *contingent task contract* (TSK) received earlier. The safety monitor always retains the authority to stop.
""")
code(r"""
save(viz.architecture_diagram(), "concept_architecture.png")
save(viz.agent_society_diagram(), "concept_agent_society.png")
save(viz.authority_diagram(), "concept_authority.png")
""")
md(r"""
**Figure 1.** Concept of the robotic transport complex: four levels with bounded autonomy and a digital twin alongside. **Figure 2.** Agent society and the short Meshtastic commands exchanged between agents; solid lines denote mesh or cellular messages, dashed lines peer-to-peer or store-carry-forward exchange. **Figure 3.** Illustrative share of decision authority in each connectivity regime.
""")
md(r"""
**Table 2.** Connectivity regimes and the corresponding behaviour of the robotic transport complex.

| Regime | Situation | Behaviour |
|---|---|---|
| C0 full | Grid down; cellular and mesh available | The CC assigns tasks and may veto; the robot runs on its battery and checks the energy for the trip and the return |
| C1 mesh only | Cellular lost; mesh nodes with autonomous power | The robot navigates on its stored graph; short Meshtastic messages carry closures, blockages and receipts |
| C2 intermittent | Mesh contact in pockets | Robots exchange requests and receipts peer-to-peer and by store-carry-forward; the fleet market allocates spare units |
| C3 isolated | All external links lost | The robot executes its last accepted contract: it continues if the recipient and a recovery point are reachable, returns if only the recovery point is reachable, and otherwise performs a controlled beacon-stop |
""")

# =============================================================================== 3
md(r"""
## 3. Short-Command Protocol over Meshtastic

LoRa airtime is the scarce resource: in the 868 MHz band, the CC gateway may transmit only **1% of the time, i.e., 36 s per hour**. Agents therefore exchange **decisions and contracts** rather than telemetry, using short fixed templates. Every command has two equivalent encodings:

* **text**, readable on any Meshtastic handset (port `TEXT_MESSAGE_APP`), e.g., `TSK T17 R3 FB R5 DL1420 Z128 OW0`;
* **binary**, consisting of an opcode, fixed-length fields and a CRC-16 (port `PRIVATE_APP`), which is two to four times shorter.

The catalogue (Table 3) extends Table 4 of the companion article with fleet-level commands.
""")
code(r"""
cat = pd.DataFrame(pr.CATALOGUE, columns=["op", "direction", "ACK", "priority", "meaning", "meaning_ua"]).drop(columns="meaning_ua")
examples = {"TSK": pr.TSK(17, 3, 5, 14*60+20), "RS": pr.RS(3, 217, 0.41, 182, 2), "DEC": pr.DEC(3, "RET", "P1", 0.27),
            "BLK": pr.BLK(3, 447), "RCP": pr.RCP(17, 3, 13*60+42, 3), "CLS": pr.CLS(3, 5), "REQ": pr.REQ(4, 1, 2, 1, 21),
            "BID": pr.BID(21, 2, 14*60+5), "LSE": pr.LSE(21, 2, 30), "RTB": pr.RTB(3, 1), "RLY": pr.RLY(9, 133),
            "ZSET": pr.ZSET(2.33), "RPT": pr.RPT(0), "ACK": pr.ACK(77), "HLD": pr.HLD(3, 30)}
cat["example (text)"] = cat.op.map(lambda o: examples[o].text())
cat["text, B"] = cat.op.map(lambda o: len(examples[o].text()))
cat["binary, B"] = cat.op.map(lambda o: len(examples[o].binary()))
cat["hex"] = cat.op.map(lambda o: examples[o].binary().hex(" "))
cat
""")
md(r"""
**Table 3.** Command catalogue with payload sizes (the 16-byte Meshtastic header is excluded) and binary frames in hexadecimal notation.

**Encoding, decoding and validation.** Any command produced by a neural network or a language model passes the deterministic validator `pr.validate()` before transmission. A binary frame with a corrupted byte is rejected by the CRC check.
""")
code(r"""
c = pr.TSK(task=17, site=3, alt=5, deadline=14*60+20, z=1.28, oneway=False)
t, b = c.text(), c.binary()
print("text  :", t, f"({len(t)} B)")
print("binary:", b.hex(" "), f"({len(b)} B)")
print("decode text  ->", pr.decode_text(t).f)
print("decode binary->", pr.decode_binary(b).f)
bad = bytearray(b); bad[3] ^= 0x40
try:
    pr.decode_binary(bytes(bad))
except ValueError as e:
    print("corrupted frame rejected:", e)
print("validator:", pr.validate(pr.TSK(18, 3, 3, 900)), "|", pr.validate(pr.RTB(2, 1)))
""")
md(r"""
### 3.1. LoRa Airtime

The time on air of a frame with a payload of $PL$ bytes follows the Semtech design guide (Equation (1) of the companion article):

$$T_{air} = (n_{pre}+4.25)\,T_s + \Big[8+\max\Big(\Big\lceil \tfrac{8PL-4SF+28+16\,CRC-20\,IH}{4(SF-2DE)}\Big\rceil (CR+4),\,0\Big)\Big]T_s,\qquad T_s=\frac{2^{SF}}{BW} \quad (1)$$

with a 16-symbol preamble, explicit header, CRC, coding rate 4/5 and $BW = 250$ kHz for the SHORT_FAST (SF 7), MEDIUM_FAST (SF 9) and LONG_FAST (SF 11) presets. As a check, a routing acknowledgement (ACK) takes 37.5, 130 and 477 ms, respectively, in agreement with the article.
""")
code(r"""
for p in ["SHORT_TURBO", "SHORT_FAST", "MEDIUM_FAST", "LONG_FAST", "LONG_SLOW"]:
    print(f"{p:12s} ACK {pr.lora_airtime(pr.ACK_FRAME_B, p)*1000:7.1f} ms   TSK text {pr.frame_airtime(32, p)*1000:7.1f} ms"
          f"   TSK binary {pr.frame_airtime(11, p)*1000:7.1f} ms")
save(viz.protocol_size_figure(), "protocol_sizes_airtime.png")
""")
md(r"""
**Figure 4.** Payload size of each command in the text and binary encodings (**left**) and the corresponding LoRa time on air for three modem presets (**right**, logarithmic scale).
""")
md(r"""
### 3.2. Duty-Cycle Budget of the CC Gateway

The utilization of the gateway with $N_r$ robots is

$$U = U_0 + \frac{N_r\,\tau_r}{3600\,\delta}\times 100\%, \quad (2)$$

where $U_0$ is the background load of critical-infrastructure facilities (29.5% during a surge), $\tau_r$ is the gateway airtime per robot and hour, and $\delta = 0.01$.

* **Periodic reporting** (status every minute, acknowledged) exhausts a shared SHORT_FAST gateway at about 30 robots and a dedicated MEDIUM_FAST gateway at about 4 robots.
* **Event-driven reporting** (unacknowledged beacon; only contracts, receipts, blockages and decisions are acknowledged) allows a dedicated gateway to serve about 60 robots at MEDIUM_FAST and more than 100 at SHORT_FAST.

The comms steward therefore enforces event-driven reporting with the command `RPT 0` (scenario S09).
""")
code(r"""
save(viz.airtime_budget_figure(), "airtime_budget.png")
for p in ["SHORT_FAST", "MEDIUM_FAST", "LONG_FAST"]:
    for pol in ["periodic", "event"]:
        tau = pr.tau_per_robot(p, pol)
        print(f"{p:12s} {pol:8s} tau_r = {tau:6.3f} s/h -> max robots on dedicated gateway: {int(36/tau)}")
""")
md(r"""
**Figure 5.** Airtime budget of the Meshtastic gateway as a function of the number of delivery robots: (**a**) gateway shared with facility traffic (SHORT_FAST, surge load 29.5% of the budget); (**b**) dedicated robot-operations gateway for three presets and two reporting policies.
""")

# =============================================================================== 4
md(r"""
## 4. Synthetic Town and Radio Model

The twin generates a riverside town of about 7 km × 4.75 km on the south-eastern bank of a reservoir. It has a jittered 250 m street lattice with arterial, local and unpaved segments (rolling-resistance coefficients 0.018, 0.025 and 0.045; speeds 1.8, 1.6 and 1.2 m s⁻¹), terrain that rises away from the shore, and two ravines.

The margin of the link between a robot at node $x$ and an infrastructure node $j$ (Okumura–Hata model at 868 MHz) is

$$M_{xj} = P_{EIRP} - L_H(d_{xj}, h_j, h_r) + G - \ell - L_{ex} + \xi_x + \zeta_{xj} - P_{thr}, \quad (3)$$

with $P_{EIRP} = 15$ dBm and $P_{thr} = -118$ dBm; $\xi$ is a spatially smooth clutter field and $\zeta \sim N(0, 6^2)$ dB is scenario shadowing. A contact check succeeds if $\max_j M_{xj} + \nu > 0$ with fast fading $\nu \sim N(0, 4^2)$ dB. Repeaters are placed greedily, and packets may be relayed at most `hop_limit = 3` times.
""")
code(r"""
w = World()
print(f"street nodes {w.n}, segments {len(w.edges)}, network length {w.elen.sum()/1000:.0f} km")
fab = RadioFabric(w, k=4)
fig, ax = plt.subplots(figsize=(11, 7.2))
viz.plot_town(w, ax, value=fab.contact_probability(), vlabel="P(mesh contact), k = 4", repeaters=fab.repeaters)
ax.set_title("Synthetic riverside town: streets, sites and mesh contact probability (k = 4 repeaters)")
save(fig, "town_coverage_k4.png")
save(viz.plot_coverage_panels(w), "coverage_vs_repeaters.png")
""")
md(r"""
**Figure 6.** Synthetic town used by the digital twin: street graph by class, recipient sites R, recovery points P, the depot with the CC gateway (H0) and greedily placed solar repeaters; colour shows the robot-level probability of mesh contact for $k = 4$ repeaters. **Figure 7.** Probability of mesh contact at each street node for $k$ = 0, 2, 4 and 8 repeaters. The layout is synthetic and inspired by, but not a map of, Verkhnodniprovsk.
""")

# =============================================================================== 5
md(r"""
## 5. Robot Agent: Supervisory Feasibility Controller

**Arc energy.** The energy (Wh) needed to traverse arc $a$ of length $L_a$, rise $\Delta z_a$ and rolling-resistance coefficient $c_a$, with snow factor $s$ and speed factor $\kappa$, is

$$e_a(s,\kappa)=\frac{1}{3600}\Big[\psi\big(mg(c_a s L_a+\Delta z_a)\big)+\frac{P_{aux}L_a}{\kappa v_a}\Big],\quad \psi(W)=\begin{cases}W/\eta_d,&W\ge 0\\ \eta_r W,&W<0\end{cases} \quad (4)$$

**Online calibration.** The forecast is calibrated with the shrinkage ratio $\hat r_t = \dfrac{w_0+\sum_{a\in\mathcal H_t} e_a}{w_0+\sum_{a\in\mathcal H_t}\hat e_a}$ over the traversed arcs $\mathcal H_t$, with prior weight $w_0 = 20$ Wh. (5)

**Chance-constrained energy requirement.** For a path $\pi$ with predicted energy $\mu_\pi$,

$$N(\pi)=\hat r_t\mu_\pi+z\sqrt{\sum_{a\in\pi}(\sigma_e\hat e_a)^2+(\sigma_r\hat r_t\mu_\pi)^2}+\epsilon\,C(T). \quad (6)$$

**Feasibility predicates.** $F_D$: the robot can deliver and then reach a recovery point; $F_R$: it can reach a recovery point now; $F_H$: it can at least reach the recipient (relevant only if one-way delivery is authorized).

The true consumption in the twin contains effects that the planner's physics model **does not include**: a surface-dependent response to snow, reduced drive efficiency in frost and a heating load. The calibration ratio $\hat r_t$ and the neural ensemble N1 (Section 9) compensate for this model error.
""")
code(r"""
save(viz.statechart_diagram(), "sfc_statechart.png")
pd.DataFrame([("loaded mass, kg", ROBOT["mass"]), ("battery C0, Wh", ROBOT["cap"]), ("cut-off / reserve", "8 % / 3 % of C(T)"),
              ("eta_d / eta_r", f"{ROBOT['eta_d']} / {ROBOT['eta_r']}"), ("P_aux move / idle / beacon, W", "70 / 38 / 15"),
              ("risk level z (default)", ROBOT["z"]), ("sigma_e", ROBOT["sigma_e"]), ("cautious kappa", ROBOT["kappa_c"]),
              ("EIRP / threshold, dBm", "15 / -118"), ("shadowing / fading, dB", "6 / 4")], columns=["parameter", "value"])
""")
md(r"""
**Figure 8.** Statechart of the Supervisory Feasibility Controller. Region A (connectivity mode) determines information and authority; Region B (mission mode) is evaluated at every decision epoch, with guards given by the feasibility predicates. **Table 4.** Main model parameters of the digital twin (all values assumed for the synthetic study).
""")
md(r"""
**Decision landscape of the SFC.** For a robot at the depot, the available energy is compared with the requirement $N$ for each recipient site over a range of initial charges. Where $A_t \ge N(\pi_{x\to d}\oplus\pi_{d\to\rho^*})$, the SFC accepts the task; otherwise it declines (DCL) and hands the task back to the orchestrator (Figure 9).
""")
code(r"""
cfg = Config(soc0=0.5, snow=1.4, temp=-8, b=0.0, p_close=0, gnss_denied=False)
sim = Sim(w, cfg, seed=1); rob = sim.robots[0]
socs = np.linspace(0.1, 1.0, 46); sites = [f"R{i}" for i in range(1, 9)]
M = np.zeros((len(sites), len(socs)))
for i, s in enumerate(sites):
    mu, var = rob.planner.chain(w.depot, [w.sites[s].node], 1.0)
    for j, soc in enumerate(socs):
        rob.E = soc * rob.cap
        M[i, j] = rob.avail() - rob.planner.need(mu, var)
fig, ax = plt.subplots(figsize=(10, 3.6))
im = ax.imshow(M, aspect="auto", cmap="RdBu", vmin=-400, vmax=400, extent=[socs[0]*100, socs[-1]*100, len(sites)-0.5, -0.5])
ax.contour(socs*100, np.arange(len(sites)), M, levels=[0], colors="k", linewidths=1.5)
ax.set_yticks(range(len(sites)), sites); ax.set_xlabel("state of charge at depot, %"); ax.grid(False)
plt.colorbar(im, label="A_t - N(pi), Wh  (>0: accept)"); ax.set_title("SFC acceptance landscape at the depot (z = 1.28, snow 1.4, -8 °C)")
save(fig, "sfc_landscape.png")
""")
md(r"""
**Figure 9.** Acceptance landscape of the SFC at the depot ($z = 1.28$, snow factor 1.4, −8 °C). Positive values (blue) indicate an energy surplus over the chance-constrained requirement; the black contour marks the acceptance boundary.
""")

# =============================================================================== 6
md(r"""
## 6. Ten Transport Scenarios

Each scenario is a declarative `Config` (Table 5). Each run shows the **route** (white circles mark nodes without contact; red crosses mark blocked segments), the **decision log** of the agents and a **message sequence chart** of the short commands transmitted over Meshtastic (`mesh`), the cellular network (`cell`), peer-to-peer links (`p2p`) or uploaded at a recovery point (`dock`).
""")
code(r"""
pd.DataFrame([(k, v["cfg"].title, v["en"]) for k, v in SCENARIOS.items()], columns=["ID", "title", "description"])
""")
md(r"""
**Table 5.** Transport scenarios S01–S10.
""")
code(r"""
def show(sim, sid, seq_msgs=22, t_max=None):
    fig, ax = plt.subplots(figsize=(12, 7.4))
    viz.plot_mission(sim, ax, title=f"{sid}: {sim.cfg.title}")
    save(fig, f"scenario_{sid}_map.png")
    ax = viz.sequence_diagram(sim, max_msgs=seq_msgs, t_max=t_max)
    ax.set_title(f"{sid}: short commands over the air (status beacons RS omitted)")
    save(ax.figure, f"scenario_{sid}_sequence.png")
    if not sim.cfg.fleet:
        display(pd.DataFrame(sim.mission_metrics())[["robot", "strategy", "terminal", "valid", "on_time", "soc_end",
                                                      "dist_km", "lat", "n_packets", "airtime_s"]].round(2))
    rows = [(r.name, f"{t:.1f}", n, code, info, f"{soc:.0%}") for r in sim.robots for (t, n, code, info, soc) in r.decisions]
    display(pd.DataFrame(rows, columns=["agent", "t, min", "node", "decision", "info", "SoC"]).head(25))
""")
md(r"""
### 6.1. S01: Medicine Delivery with Full Connectivity (C0)
The CC sends the task contract `TSK`; the robot acknowledges with `ACK`, periodically broadcasts the status beacon `RS` and, after handover, sends the receipt `RCP ... PIN+` co-signed with the recipient's PIN.
""")
code(r"""show(run_scenario(w, "S01"), "S01")""")
md(r"""
### 6.2. S02: Site Closure and Re-Targeting over the Mesh (C1)
Cellular service is unavailable. Site R2 closes at minute 12, and the CC broadcasts `CLS R2 ALT R7`. The SFC checks $F_D$ for the alternative site and replies `DEC U1 RTG R7`.
""")
code(r"""show(run_scenario(w, "S02"), "S02")""")
md(r"""
### 6.3. S03: Unknown Blockages: Sense, Report, Detour
Fifteen per cent of segments are blocked in clusters. The CC is initially unaware of them; it learns of each blockage after a delay of ~Exp(40 min) and broadcasts `BLK U0 E…`. The robot senses blockages with its onboard sensors, sends `BLK U1 E…` and replans its route.
""")
code(r"""show(run_scenario(w, "S03"), "S03", seq_msgs=18)""")
md(r"""
### 6.4. S04: Isolated Robot with Low Charge (C3): S1 versus S2 versus S3
The mesh is jammed, cellular service is absent, the charge is 42%, snowfall is heavy and the temperature is −12 °C. The three strategies are run on the **same** scenario with common random numbers:
* **S1 Stop-on-loss** stops when contact is lost and waits, depleting its battery while idle;
* **S2 Fixed-route** delivers but has no reserve for the return;
* **S3 SFC** declines at the depot (`DEC U1 DCL H0`), and the task returns to the orchestrator for a better-charged robot;
* **S3 with one-way authorization** (`OW1`) departs with the intention of remaining at the site (`ONEWAY`), but after a few segments the online calibration $\hat r_t$ shows that even $F_H$ no longer holds, and the robot returns (`DEC RET`), illustrating how calibration corrects an optimistic forecast.
""")
code(r"""
out = run_scenario_paired(w, "S04")
out["S3 one-way"] = run_scenario(w, "S04", oneway=True)
fig, axs = plt.subplots(2, 2, figsize=(15, 10))
for ax, (s, sim) in zip(axs.ravel(), out.items()):
    viz.plot_mission(sim, ax, title=f"S04 · {s}")
save(fig, "scenario_S04_paired.png")
fig, ax = plt.subplots(figsize=(8, 3.6)); viz.plot_energy({k: v for k, v in out.items() if k != "S3 one-way"}, ax)
ax.set_title("S04: state of charge, paired runs"); save(fig, "scenario_S04_soc.png")
pd.DataFrame([dict(strategy=k, **{c: v.mission_metrics()[0][c] for c in ["terminal", "valid", "soc_end", "dist_km", "stranded"]})
              for k, v in out.items()]).round(2)
""")
md(r"""
### 6.5. S05: GNSS Denied: Localization Guard
Position uncertainty grows with odometric drift, $\sigma_{j+1}^2=\sigma_j^2+(\delta_o L_a)^2$, and is reset by map matching at junctions. When $\sigma > 5$ m, the SFC slows to $\kappa = 0.6$ (decision `CAUTIOUS`), which raises the probability of map matching and lowers the risk of a wrong turn.
""")
code(r"""
sim = run_scenario(w, "S05")
show(sim, "S05", seq_msgs=12)
r = sim.robots[0]
fig, ax = plt.subplots(figsize=(9, 3))
ax.step([x[0] for x in r.trace], [x[5] for x in r.trace], where="post", color=viz.C["blue"], lw=2, label="σ, m")
ax.axhline(5, color=viz.C["red"], ls="--", lw=1); ax.text(1, 5.3, "σ_c = 5 m → cautious", color=viz.C["red"], fontsize=8)
ax.set_xlabel("time, min"); ax.set_ylabel("position σ, m"); ax.set_title("S05: localisation uncertainty along the route")
save(fig, "scenario_S05_sigma.png")
""")
md(r"""
### 6.6. S06: Fleet Shift with Intermittent Contact (C2)
Four robots operate for 8 h and receive `REQ` messages from recipient sites (Poisson process, 2.4 h⁻¹). The **centralized** policy assigns requests only at the depot. The **agentic** policy adds spare units of standard goods, pickup of requests from site nodes passed en route (DTN), peer-to-peer exchange and a `BID → LSE` auction.
""")
code(r"""
res = {}
for pol in ["C", "A"]:
    res[pol] = run_scenario(w, "S06", policy=pol)
fig, axs = plt.subplots(1, 2, figsize=(17, 6.4))
for ax, pol in zip(axs, ["C", "A"]):
    viz.plot_mission(res[pol], ax, title=("Centralized" if pol == "C" else "Agentic") + " fleet", annotate=False)
save(fig, "scenario_S06_fleet_maps.png")
display(pd.DataFrame([FleetLogic.metrics(res[p]) for p in ["C", "A"]]).round(2))
ax = viz.sequence_diagram(res["A"], max_msgs=26, skip_ops=("RS", "ACK", "BLK"))
ax.set_title("S06 agentic: requests, auction bids and leases"); save(ax.figure, "scenario_S06_sequence.png")
""")
md(r"""
### 6.7. S07: Relay UGV Raises a Mast
Neither cellular service nor repeaters are available. The twin planner selects the node that most improves coverage near the current recipient and sends `RLY U9 N…`. The relay UGV drives there and raises a 10 m telescopic mast (`MAST-UP`), through which the delivery receipt reaches the CC.
""")
code(r"""
sim7 = run_scenario(w, "S07"); show(sim7, "S07", seq_msgs=14)
base = run_scenario(w, "S07", relay=False)
share = lambda s: np.mean([x[4] for x in s.robots[0].trace])
print("receipt latency with relay: %.1f min, without: %.1f min" % (sim7.mission_metrics()[0]["lat"], base.mission_metrics()[0]["lat"]))
print("share of route nodes with contact: with relay %.0f %%, without %.0f %%" % (100 * share(sim7), 100 * share(base)))
""")
md(r"""
### 6.8. S08: Water Multi-Drop to Three Sites
The payload is 30 kg, the temperature is −14 °C and snow is present. The robot receives `TSK` contracts for three sites. The SFC checks the whole chain $x\to d_1\to d_2\to d_3\to\rho^*$; if it is infeasible, the last stop is dropped (`DEC U1 DRP R3`) and the CC is informed so that the task can be reassigned.
""")
code(r"""show(run_scenario(w, "S08"), "S08", seq_msgs=16)""")
md(r"""
### 6.9. S09: Airtime Surge: Periodic versus Event-Driven Reporting
Six robots on MEDIUM_FAST send acknowledged status reports every minute, and the CC gateway approaches its limit of 36 s h⁻¹. At minute 60, the comms steward broadcasts `RPT 0`; the robots switch to event-driven reporting and the gateway load falls (Figure 10).
""")
code(r"""
sim9 = run_scenario(w, "S09")
tt = np.arange(0, 121, 5)
use = [sim9.gw_budget_used(t, 60.0) for t in tt]
fig, ax = plt.subplots(figsize=(9, 3.6))
ax.plot(tt, use, color=viz.C["blue"], lw=2, label="gateway TX airtime, last 60 min")
ax.axhline(36, color=viz.C["red"], lw=1.2); ax.text(2, 37, "1 % duty cycle = 36 s/h", color=viz.C["red"], fontsize=8)
ax.axvline(60, color=viz.C["ink2"], ls="--", lw=1); ax.text(61, 5, "RPT 0 (event-driven)", fontsize=8)
ax.set_xlabel("time, min"); ax.set_ylabel("s per hour"); ax.set_title("S09: comms steward protects the gateway budget"); ax.legend()
save(fig, "scenario_S09_airtime.png")  # Figure 10
pd.Series({op: round(sum(s for _, s, o in sim9.gw_tx if o == op), 2) for op in sorted(set(o for _, _, o in sim9.gw_tx))},
          name="gateway airtime by message, s")
""")
md(r"""
### 6.10. S10: Human on the Loop: Risk Dial, Hold and Recall
The operator raises the risk level with `ZSET 233` ($z = 2.33$, more conservative), temporarily holds the robot with `HLD U1 MIN10` and then recalls it with `RTB U1 P1`. The robot complies when the command arrives; the safety monitor retains its authority to stop.
""")
code(r"""show(run_scenario(w, "S10"), "S10", seq_msgs=16)""")

# =============================================================================== 7
md(r"""
## 7. Paired Monte Carlo Experiment: S1, S2 and S3

The factorial design (reduced for Colab) comprises initial state of charge $SoC_0 \in \{30, 50, 70, 90\}\%$ × outage age $H \in \{6, 72\}$ h × number of repeaters $k \in \{0, 4\}$ × 8 replications. The blocked fraction, destination, weather, GNSS state and site closures are random but **common to all strategies** (paired design). Increase `reps` to obtain publication-grade confidence intervals. Proportions are reported with normal-approximation 95% confidence intervals and paired differences with 1000-sample bootstrap intervals.
""")
code(r"""
t0 = time.time()
dfA = ex.single_missions(w, reps=8)
print(f"{len(dfA)} missions in {time.time()-t0:.0f} s")
display(ex.summary_table(dfA))
save(ex.plot_single(dfA), "mc_single_missions.png")
save(ex.outcome_mix(dfA), "mc_outcomes.png")
""")
md(r"""
**Table 6.** Summary of single-mission outcomes by strategy. **Figure 11.** On-time delivery, stranding and recovery by initial state of charge (error bars: 95% confidence intervals). **Figure 12.** Distribution of mission end states by strategy.
""")
code(r"""
# paired difference S3 - S1 / S3 - S2 in on-time delivery, bootstrap CI
piv = dfA.pivot_table(index=["seed", "H", "k"], columns="strategy", values="on_time")
rng = np.random.default_rng(0)
for base in ["S1", "S2"]:
    d = (piv["S3"] - piv[base]).values
    bs = [rng.choice(d, len(d)).mean() for _ in range(1000)]
    print(f"on-time S3 - {base}: {100*d.mean():+.1f} pp  (95% CI {100*np.percentile(bs, 2.5):+.1f} .. {100*np.percentile(bs, 97.5):+.1f})")
print("\nby outage age H and repeaters k (on-time %, stranded %):")
display((100 * dfA.groupby(["strategy", "H", "k"])[["on_time", "stranded"]].mean()).round(0).unstack("strategy"))
""")
md(r"""
### 7.1. Risk Dial $z$
A larger $z$ implies a larger energy reserve and fewer accepted missions. Authorizing one-way delivery adds deliveries at the cost of the robot possibly remaining at the recipient site. In this twin, even $z = 0$ produces almost no stranding, because online calibration $\hat r_t$, the fixed reserve $\epsilon$ and the check at every node cover the remaining risk; the dial therefore mainly changes the share of declined missions (Figure 13).
""")
code(r"""
dfB = ex.risk_dial(w, reps=10)
save(ex.plot_risk_dial(dfB), "mc_risk_dial.png")  # Figure 13
(100 * dfB.groupby(["oneway", "z"])[["on_time", "stranded"]].mean()).round(1).unstack("oneway")
""")

# =============================================================================== 8
md(r"""
## 8. Fleet Level: Centralized versus Agentic Coordination

Each run is one 8 h shift with four robots, an outage age of 72 h (most base stations have exhausted their reserves) and $k \in \{0, 4, 8\}$ repeaters. The metrics are the share of requests served on time (deadline 120 min), the median time until any agent of the system knows of a request, and the latency of delivery confirmation (Figure 14).
""")
code(r"""
t0 = time.time()
dfF = ex.fleet_experiment(w, reps=10)
print(f"{len(dfF)} shifts in {time.time()-t0:.0f} s")
save(ex.plot_fleet(dfF), "fleet_policies.png")  # Figure 14
dfF.groupby(["policy", "k"])[["service", "delivered", "aware_med", "lat_med", "km_per", "dups", "packets", "gw_air"]].mean().round(2)
""")

# =============================================================================== 9
md(r"""
## 9. Neural Modules

Four small neural networks (multilayer perceptrons implemented in plain NumPy and trained with the Adam optimizer) complement, but **do not replace**, the verifiable rules (Table 7, Figures 15 and 16).

**Table 7.** Neural modules of the robotic transport complex.

| Module | Input | Output | Use |
|---|---|---|---|
| **N1 EnergyEnsemble** | segment features (length, rise, surface class, snow forecast, temperature, κ, payload, physics forecast) | mean and σ of the true-to-physics energy ratio (5 networks, Gaussian negative log-likelihood) | replaces the physics forecast in the chance constraint of the SFC (strategy **S3N**) |
| **N2 PolicyNet** | 13 state features at a decision epoch | CONTINUE / RETURN / STOP | neural policy under a **shield** built from the SFC predicates (strategy **NNP**) |
| **N3 ContactNet** | node geometry relative to the infrastructure | P(mesh contact) | coverage maps, beacon-stop placement, communication-aware routing |
| **N4 IntentNet** | free operator text (Ukrainian or English) | intent and slots → short command | operator advisor; every command passes the validator |

The governing principle is **runtime assurance (Simplex)**: the network proposes, and the verified shield decides.
""")
code(r"""
save(viz.neural_overview_figure(), "neural_architectures.png")
save(viz.shield_pipeline_figure(), "neural_shield_pipeline.png")
""")
md(r"""
**Figure 15.** Architectures of the neural modules N1–N4 (input features in orange, hidden units in blue, outputs in green). **Figure 16.** Runtime-assurance pipeline: the neural proposal is verified by the shield before a short command is issued.
""")
md(r"""
### 9.1. N1: Deep Ensemble for Energy Prediction
The training data are "telemetry" from 160 synthetic shifts; the target is the ratio of the true energy to the physics forecast. An ensemble of five bootstrapped networks provides **aleatoric** (noise σ) and **epistemic** (spread between members) uncertainty, whose sum replaces $\sigma_e\hat e_a$ in Equation (6) (Figure 17).
""")
code(r"""
t0 = time.time()
Xe, ye = nn.make_energy_dataset(w, n_scen=160)
Xe_t, ye_t = nn.make_energy_dataset(w, n_scen=30, seed=5)
ens = nn.EnergyEnsemble().fit(Xe, ye, epochs=30)
mu, sd, epi = ens.predict_ratio(Xe_t)
print(f"trained in {time.time()-t0:.0f} s; parameters per member: {ens.members[0].n_params()}")
print(f"RMSE of energy ratio: physics {np.sqrt(((1-ye_t)**2).mean()):.3f} -> ensemble {np.sqrt(((mu-ye_t)**2).mean()):.3f}"
      f" (noise floor ~0.10); share inside ±1σ: {(abs(mu-ye_t) < sd).mean():.0%}, ±2σ: {(abs(mu-ye_t) < 2*sd).mean():.0%}")
fig, axs = plt.subplots(1, 3, figsize=(16, 4))
for m in ens.members:
    h = np.array(m.history); axs[0].plot(h[:, 0], h[:, 2], color=viz.C["blue"], alpha=0.6)
axs[0].set_title("validation Gaussian NLL (5 members)"); axs[0].set_xlabel("epoch")
cls = Xe_t[:, 2:5].argmax(1)
for c, (name, col) in enumerate(zip(["arterial", "local", "unpaved"], [viz.C["blue"], viz.C["orange"], viz.C["aqua"]])):
    k = cls == c
    axs[1].scatter(Xe_t[k, 6], ye_t[k], s=3, alpha=0.25, color=col)
    o = np.argsort(Xe_t[k, 6]); axs[1].plot(Xe_t[k, 6][o], mu[k][o], color=col, lw=1.5, label=name)
axs[1].axhline(1, color=viz.C["ink2"], ls="--", lw=1); axs[1].set_xlabel("temperature, °C"); axs[1].set_ylabel("true / physics")
axs[1].set_title("what the ensemble learned"); axs[1].legend(fontsize=8)
q = np.linspace(0.05, 0.95, 10); from math import erf
z = (ye_t - mu) / sd; emp = [(z < np.quantile(np.random.default_rng(0).standard_normal(100000), qq)).mean() for qq in q]
axs[2].plot(q, emp, "o-", color=viz.C["blue"]); axs[2].plot([0, 1], [0, 1], "--", color=viz.C["ink2"])
axs[2].set_xlabel("nominal quantile"); axs[2].set_ylabel("empirical"); axs[2].set_title("calibration of predictive σ")
save(fig, "nn_energy_ensemble.png")  # Figure 17
""")
md(r"""
### 9.2. N2: Neural Policy Cloned from the SFC, under a Shield
Pairs of epoch features and SFC decisions are collected from 300 random missions (only epochs with an open delivery, where the decision "continue or return" is actually taken). A classifier is trained on these pairs and then deployed as the controller. The shield blocks CONTINUE if $F_D$ is false and RETURN if $F_R$ is false (Figure 18).
""")
code(r"""
t0 = time.time()
Xp, yp = nn.collect_sfc_epochs(w, n=300)
idx = np.random.default_rng(0).permutation(len(Xp)); ntr = int(0.8 * len(Xp))
pol = nn.PolicyNet().fit(Xp[idx[:ntr]], yp[idx[:ntr]], epochs=80)
pred = pol.proba(Xp[idx[ntr:]]).argmax(1); yt = yp[idx[ntr:]]
print(f"{len(Xp)} decision epochs, classes {dict(zip(nn.ACTIONS_NN, np.bincount(yp, minlength=3)))}; trained in {time.time()-t0:.0f} s")
print(f"held-out accuracy {np.mean(pred == yt):.3f}")
cm = pd.crosstab(pd.Series([nn.ACTIONS_NN[i] for i in yt], name="SFC"), pd.Series([nn.ACTIONS_NN[i] for i in pred], name="PolicyNet"))
display(cm)
# decision map over (available energy, predicted need), other features at their median
f0 = np.median(Xp, axis=0); A = np.linspace(0, 0.9, 150); Nd = np.linspace(0, 0.6, 150)
aa, nd = np.meshgrid(A, Nd); grid = np.tile(f0, (aa.size, 1))
grid[:, 0] = aa.ravel(); grid[:, 1] = nd.ravel(); grid[:, 2] = 0.55 * nd.ravel(); grid[:, 4] = 0.06 * nd.ravel()
P = pol.proba(grid)[:, 0].reshape(aa.shape)
fig, ax = plt.subplots(figsize=(7, 5))
cs = ax.contourf(aa, nd, P, levels=np.linspace(0, 1, 11), cmap="RdBu")
ax.contour(aa, nd, P, levels=[0.5], colors="k", linewidths=1.5)
ax.plot([0, 0.6], [0, 0.6], color=viz.C["ink2"], lw=1, ls="--"); ax.text(0.45, 0.47, "A = μ", rotation=33, fontsize=8)
for c, col, lab in ((0, "white", "SFC: CONTINUE"), (1, "black", "SFC: RETURN")):
    k = yp == c; ax.scatter(Xp[k, 0], Xp[k, 1], s=5, color=col, alpha=0.5, label=lab, edgecolors="none")
plt.colorbar(cs, label="P(CONTINUE)"); ax.set_xlabel("available energy A_t / C"); ax.set_ylabel("predicted need μ_D / C (to site and recovery)")
ax.set_xlim(0, 0.9); ax.set_ylim(0, 0.6); ax.legend(loc="upper left", fontsize=8, frameon=True)
ax.set_title("N2: learned CONTINUE / RETURN boundary (black line: P = 0.5)"); save(fig, "nn_policy_boundary.png")  # Figure 18
""")
md(r"""
### 9.3. Comparison of S3, S3N (SFC with N1) and NNP (N2 with shield)
Figure 19 and the table below compare the three controllers on paired missions with an outage age of 24 h, two repeaters and 10% blocked segments.
""")
code(r"""
t0 = time.time()
dfN, shield = ex.neural_comparison(w, ens, pol, reps=20)
print(f"{len(dfN)} missions in {time.time()-t0:.0f} s; shield interventions: {len(shield)}")
display((100 * dfN.groupby(["strategy", "soc0"])[["on_time", "stranded", "mid_abort"]].mean()).round(0).unstack("strategy"))
save(ex.plot_single(dfN), "nn_strategy_comparison.png")  # Figure 19
if shield:
    display(pd.DataFrame(shield, columns=["t", "robot", "proposed", "executed"]).head(10))
""")
md(r"""
**Stress test of the shield.** What happens if the network is wrong? Two deliberately flawed policies are considered: (a) an "overconfident" version of N2 that returns only if P(RETURN) > 0.97, and (b) a **faulty** network that always outputs CONTINUE. Both are run with and without the shield on missions with an initial charge of 30–50% (Table 8).
""")
code(r"""
class Overconfident:
    def __init__(self, base): self.base = base
    def act(self, f): return "RETURN" if self.base.proba(f)[0, 1] > 0.97 else "CONTINUE"
class Faulty:
    def act(self, f): return "CONTINUE"
rows = []
for name, model in (("overconfident N2", Overconfident(pol)), ("faulty: always CONTINUE", Faulty())):
    for shield_on in (True, False):
        for soc in (0.3, 0.4, 0.5):
            for r in range(15):
                cfg = Config(soc0=soc, H=24, k=2, b=0.1, policy_model=model, shield=shield_on)
                sim_ = Sim(w, cfg, seed=90_000 + r + int(soc * 100), strategy="NNP").run()
                m = sim_.mission_metrics()[0]
                rows.append(dict(network=name, shield="on" if shield_on else "off", terminal=m["terminal"],
                                 on_time=m["on_time"], overrides=len(sim_.shield_events)))
dfS = pd.DataFrame(rows)
tab = pd.crosstab([dfS.network, dfS.shield], dfS.terminal)
tab["on-time %"] = (100 * dfS.groupby(["network", "shield"]).on_time.mean()).round(0)
tab["shield overrides"] = dfS.groupby(["network", "shield"]).overrides.sum()
tab
""")
md(r"""
**Table 8.** End states of missions controlled by flawed neural policies with and without the shield.

Without the shield, the faulty network delivers more often, but about half of the robots **deplete their batteries en route or stop with a beacon** far from a recovery point. With the shield, no robot is lost: unsafe CONTINUE proposals are replaced by RETURN (or by a decline at the depot). This is the purpose of runtime assurance: the quality of the neural network affects efficiency but not safety.
""")
md(r"""
### 9.4. N3: Neural Prediction of Mesh Coverage
ContactNet is trained on simulated contact checks across outage ages and repeater configurations; Figure 20 compares its prediction with the simulated contact probability and shows a reliability diagram.
""")
code(r"""
Xc, yc = nn.make_contact_dataset(w, n_scen=50)
Xc_t, yc_t = nn.make_contact_dataset(w, n_scen=12, seed=3)
cnet = nn.ContactNet().fit(Xc, yc, epochs=20)
pc = cnet.proba(Xc_t)
print(f"Brier score: constant {((yc_t.mean()-yc_t)**2).mean():.3f} -> ContactNet {((pc-yc_t)**2).mean():.3f}; accuracy {((pc>0.5)==yc_t).mean():.3f}")
from meshrtc.sim import Scenario
fig, axs = plt.subplots(1, 3, figsize=(18, 4.4))
sc = Scenario(w, Config(H=48, k=2, b=0), 31_000)
emp = np.mean([sc.best_margin + np.random.default_rng(i).normal(0, 4, w.n) > 0 for i in range(200)], axis=0)
pred = cnet.proba(nn.contact_features(w, sc.fab, sc.alive, 48))
for ax, v, t in ((axs[0], emp, "simulated P(contact), H = 48 h, k = 2"), (axs[1], pred, "ContactNet prediction")):
    viz.plot_town(w, ax, sites=False, legend=False, alpha_streets=0.3)
    s = ax.scatter(*w.xy.T, c=v, cmap="RdYlGn", vmin=0, vmax=1, s=10, zorder=3); ax.set_title(t)
bins = np.linspace(0, 1, 11); b = np.digitize(pc, bins) - 1
axs[2].plot([(pc[b == i]).mean() for i in range(10) if (b == i).any()], [(yc_t[b == i]).mean() for i in range(10) if (b == i).any()], "o-", color=viz.C["blue"])
axs[2].plot([0, 1], [0, 1], "--", color=viz.C["ink2"]); axs[2].set_xlabel("predicted"); axs[2].set_ylabel("observed"); axs[2].set_title("reliability diagram")
save(fig, "nn_contact.png")  # Figure 20
""")
md(r"""
### 9.5. N4: From Free Operator Text to a Short Command
Synthetic operator requests in Ukrainian and English (50% with typing errors) are mapped to hashed character n-grams, then to an intent by an MLP; slots (sites, units, time, z) are extracted by rules, and the resulting command passes the validator. If confidence is low or a slot is missing, the command is **not transmitted** and the operator is asked to confirm (Table 9). Ukrainian inputs are kept intentionally, since the parser is designed for bilingual operation; English glosses are given in the code comments.
""")
code(r"""
tr, te = nn.make_intent_dataset()
inet = nn.IntentNet(2048, (128,)).fit(tr, epochs=30)
pt = inet.proba([s for s, _ in te]).argmax(1); yt = np.array([c for _, c in te])
print(f"train {len(tr)}, test {len(te)}, test accuracy {np.mean(pt == yt):.3f}")
rows = []
# Ukrainian inputs (English glosses): "urgent insulin to R4, fallback R2, by 13:30"; "site R6 closed, deliver to R1";
# "U2 wait 15 minutes"; "set risk 2.33"; "event-driven reports only"
for s in ["Терміново інсулін до R4, резерв R2, до 13:30", "Пункт R6 закрито, везіть на R1", "recall U3 to P2",
          "U2 зачекати 15 хвилин", "встановити ризик 2.33", "deploy relay U9 at node 133", "звіти тільки за подіями"] + nn.UNSEEN:
    it, conf, cmd, errs = inet.to_command(s)
    rows.append(dict(operator_text=s, intent=it, confidence=round(conf, 2), command=cmd.text() if cmd else "—",
                     bytes=len(cmd.binary()) if cmd else None, send="yes" if not errs else "ask operator: " + "; ".join(errs)))
pd.DataFrame(rows)
""")
md(r"""
**Table 9.** Operator text, recognized intent, confidence, generated command, binary size and transmission decision. The last rows contain phrasings that were not seen during training.
""")

# =============================================================================== 10
md(r"""
## 10. Limitations, Reproducibility and Data Availability

**Limitations.** The town, radio coverage, demand and energy consumption are synthetic. The radio model does not represent collisions or the Meshtastic rebroadcast rules in detail (rebroadcast delay is modelled as random). The neural networks are trained on data from the same twin, so their advantage is an advantage over the *simplified* physics model of this twin. Before a field pilot, radio coverage and energy consumption on real surfaces must be measured, and routes must be verified on the ground.

**Reproducibility.** All generators use fixed seeds, and strategies are compared on common random numbers. Full run: `python scripts/run_all.py` (figures are written to `figures/`); tests: `python -m pytest tests`.

**Table 10.** Structure of the `meshrtc` package.

| Module | Purpose |
|---|---|
| `meshrtc/protocol.py` | command catalogue, text and binary codecs, CRC-16, validator, LoRa airtime, duty cycle |
| `meshrtc/world.py` | synthetic town, energy model (Equation (4)), Dijkstra search with variance accumulation, Okumura–Hata radio model |
| `meshrtc/sim.py` | agents (CC, robots S1/S2/S3/S3N/NNP), Meshtastic message bus, scenario ground truth |
| `meshrtc/fleet.py` | dispatch, DTN, peer-to-peer exchange, BID/LSE auction |
| `meshrtc/scenarios.py` | ten transport scenarios |
| `meshrtc/neural.py` | neural modules N1–N4 in NumPy |
| `meshrtc/experiments.py`, `viz.py` | experiments and figures |

**Data Availability Statement.** All data are generated by the code in this package; no external data are used. The package is deposited on Zenodo; see `CITATION.cff` for the citation and add the DOI after publication.

**Abbreviations.** CC, crisis-coordination centre; CRC, cyclic redundancy check; DTN, delay-tolerant networking; GNSS, global navigation satellite system; LoRa, long range (radio modulation); MLP, multilayer perceptron; RTC, robotic transport complex; SFC, Supervisory Feasibility Controller; SoC, state of charge; UGV, unmanned ground vehicle.
""")
code(r"""
print("figures written:", len(os.listdir(FIG)))
sorted(os.listdir(FIG))[:60]
""")

nb["cells"] = cells
nb["metadata"] = {"kernelspec": {"name": "python3", "display_name": "Python 3"},
                  "language_info": {"name": "python"}, "colab": {"provenance": [], "toc_visible": True}}
os.makedirs("notebooks", exist_ok=True)
nbf.write(nb, "notebooks/MeshRTC_Agents_Colab.ipynb")
print("written", len(cells), "cells")
