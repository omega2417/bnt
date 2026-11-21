# MeshRTC-Agents 1.0.0

**Software agents for robotic transport platforms coordinated by short commands over a Meshtastic LoRa mesh** — a synthetic digital twin, ten transport scenarios, a Supervisory Feasibility Controller, fleet-level market and store-carry-forward logic, and four neural modules, with a Google Colab notebook full of visualisations, explanations and schematic diagrams.

> All data are **synthetic**. The town is only inspired by the planning grid of Verkhnodniprovsk (Ukraine) and is not a map of it. Results establish conditional feasibility and mechanisms, not operational readiness.

Software supplement to: D. Prokopovych-Tkachenko, *Agentic Supervisory Control of a Robotic Transport Complex for Emergency Deliveries during Deep Blackouts: A Synthetic-Data Digital-Twin Study with Offline Maps and Meshtastic Backup Communication* (University of Customs and Finance, Dnipro).

## Quick start

**Google Colab.** Upload `notebooks/MeshRTC_Agents_Colab.ipynb` to Colab and run all cells. The first cell finds the package; if it is missing, it asks you to upload this zip file (or set `ZENODO_ZIP_URL` once the record is published). Runtime is about 3 minutes on a standard Colab CPU.

**Local.**

```bash
pip install -r requirements.txt
python -m pytest tests            # 8 fast tests
jupyter notebook notebooks/MeshRTC_Agents_Colab.ipynb
python scripts/run_all.py         # re-executes the notebook, writes figures/
```

```python
from meshrtc.world import World
from meshrtc.scenarios import run_scenario
from meshrtc import protocol as pr

w = World()
sim = run_scenario(w, "S02")                  # site closure -> CLS -> re-target
for row in sim.packet_table()[:6]:
    print(row["t_send"], row["src"], "->", row["dst"], row["text"], row["path"])
print(pr.TSK(17, 3, 5, 14*60+20).text())      # TSK T17 R3 FB R5 DL1420 Z128 OW0
print(pr.TSK(17, 3, 5, 14*60+20).binary().hex(" "))   # 11 bytes incl. CRC-16
```

## What is inside

| Path | Content |
|---|---|
| `meshrtc/protocol.py` | 15 short commands (TSK, RS, DEC, BLK, RCP, CLS, REQ, BID, LSE, RTB, RLY, ZSET, RPT, ACK, HLD), text and binary/CRC-16 codecs, validator, LoRa airtime (Semtech), duty-cycle budget |
| `meshrtc/world.py` | synthetic riverside town (490 nodes, 254 km of streets), energy model, Dijkstra with variance, Okumura–Hata radio fabric, greedy repeaters |
| `meshrtc/sim.py` | agents: orchestrator and comms steward (CC), robot agents (S1 stop-on-loss, S2 fixed-route, S3 SFC, S3N SFC + neural energy, NNP neural policy + shield), recipient nodes, relay UGV; Meshtastic/cellular/P2P/dock message bus |
| `meshrtc/fleet.py` | centralized dispatch vs agentic fleet (spare stock, DTN pickup, P2P exchange, BID/LSE auction) |
| `meshrtc/scenarios.py` | ten transport scenarios S01–S10 |
| `meshrtc/neural.py` | NumPy MLPs: N1 energy deep ensemble, N2 behaviour-cloned policy, N3 mesh-contact predictor, N4 operator intent parser |
| `meshrtc/experiments.py`, `meshrtc/viz.py` | paired Monte-Carlo experiments, figures, schematic diagrams |
| `notebooks/MeshRTC_Agents_Colab.ipynb` | executed notebook (Ukrainian text) |
| `figures/` | 39 figures produced by the notebook |
| `docs/PROTOCOL.md` | protocol specification |

### Transport scenarios

| ID | Scenario | Commands shown |
|---|---|---|
| S01 | Medicine delivery, full connectivity (C0) | TSK, ACK, RS, RCP |
| S02 | Site closure and re-targeting over the mesh (C1) | CLS, DEC RTG |
| S03 | Unknown blockages: sense, report, detour | BLK |
| S04 | Isolated robot with low charge (C3): S1 vs S2 vs S3 | DEC DCL, ONEWAY |
| S05 | GNSS denied: localisation guard, cautious mode | CAUTIOUS |
| S06 | Fleet shift with intermittent contact: centralized vs agentic | REQ, BID, LSE |
| S07 | Relay UGV with a 10 m telescopic mast | RLY, MAST-UP |
| S08 | Water multi-drop with heavy load | DEC DRP |
| S09 | Airtime surge: periodic vs event-driven reporting | RPT 0 |
| S10 | Operator recall and risk dial | ZSET, HLD, RTB |

## Headline results (synthetic, as produced by the notebook)

* **Protocol.** Binary encoding is 2–4× shorter than text (TSK: 11 B vs 32 B). A routing ACK costs 37.5 / 130 / 477 ms at SHORT_FAST / MEDIUM_FAST / LONG_FAST. With event-driven reporting a dedicated gateway serves ≈60 robots at MEDIUM_FAST, against 4 with acknowledged 1-min reports.
* **Single missions** (384 paired runs): on-time delivery / robot stranded — S1 35 % / 72 %, S2 83 % / 34 %, **S3 SFC 73 % / 0 %**.
* **Fleet** (8-h shift, 4 robots, outage age 72 h): the agentic policy raises on-time service from ≈46 % to ≈56 % and halves the time until a request becomes known (≈23 → ≈12 min).
* **Relay UGV** (S07): receipt latency 11 → 0 min, share of the route with contact 30 → 50 %.
* **Neural modules.** N1 cuts the RMSE of the energy forecast ratio from 0.19 to 0.14 with calibrated uncertainty (68 % / 95 % inside ±1σ / ±2σ). N2 reproduces SFC decisions with 99.5 % accuracy. In a stress test, a faulty network that always says CONTINUE loses 21 of 45 robots without the shield and none with it. N3 lowers the Brier score of contact prediction from 0.24 to 0.14. N4 maps Ukrainian/English operator text to validated commands and refuses to send when slots are missing or confidence is low.

## Українською

Пакет і Colab-ноутбук з програмними агентами роботизованих транспортних платформ, які доставляють ліки й воду під час тривалих знеструмлень і координуються **короткими командами через mesh-мережу Meshtastic**. Усередині: протокол із 15 команд (текстове й бінарне кодування, CRC-16, валідатор, ефірний час LoRa, бюджет duty cycle 1 %), синтетичне місто з радіомоделлю, агенти (координаційний центр, комунікаційний агент, роботи зі стратегіями S1/S2/S3, пункти видачі, робот-ретранслятор), флот з аукціоном і DTN, десять транспортних сценаріїв, чотири нейромодулі (енергетичний ансамбль, нейрополітика під щитом, прогноз покриття, розбір команд оператора) і парні експерименти Монте-Карло. Пояснення в ноутбуці — українською; рисунки й код — англійською. Усі дані синтетичні.

## Citation and license

See `CITATION.cff` and `.zenodo.json`. Code: MIT. Text and figures: CC BY 4.0.
Related records: BlackoutMesh-Twin 1.0.0 (doi:10.5281/zenodo.23460212); Verkhnodniprovsk spatial data (doi:10.5281/zenodo.23298497) and concept plan (doi:10.5281/zenodo.23298550).
