"""Fixed-seed generation of network configurations, assets, vulnerabilities, threats and barriers."""
from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd

from .design import stable_id

CLASSES = ["EAV", "DOS", "INT", "MAL", "INS", "TAM"]
FAMILY_DOMINANT = {"confidentiality": "EAV", "availability": "DOS", "intrusion": "INT",
                   "malware": "MAL", "insider": "INS", "integrity": "TAM"}
# Layer-by-class affinity: share of a barrier's effectiveness that applies to a threat class.
AFFINITY = np.array([
    # EAV  DOS  INT  MAL  INS  TAM
    [0.2, 0.8, 0.9, 0.6, 0.0, 0.2],   # L1 perimeter
    [0.3, 0.6, 0.8, 0.7, 0.4, 0.3],   # L2 network (segmentation, IDS)
    [1.0, 0.1, 0.2, 0.1, 0.2, 0.9],   # L3 channel (link/transport cryptography)
    [0.1, 0.3, 0.7, 0.9, 0.6, 0.5],   # L4 host (hardening, endpoint detection)
    [0.9, 0.0, 0.3, 0.3, 0.8, 0.9],   # L5 data (encryption at rest, access control, integrity)
])
LAYER_BASE_COST = np.array([18.0, 14.0, 10.0, 12.0, 9.0])   # kCU per year, before scope scaling
TIER = [("basic", -0.12, 0.6), ("standard", 0.0, 1.0), ("advanced", 0.08, 1.8)]
ASSET_TYPES = ["server", "database", "workstation", "storage", "controller"]

# topology -> (assets per segment list, builder kind)
TOPOLOGY_SPEC = {
    "star": [6],
    "tree": [3, 3, 3],
    "partial_mesh": [3, 3, 2, 2],
    "ring": [2, 2, 2, 2],
    "hub_spoke": [3, 3, 2, 2],
    "segmented_dmz": [3, 3, 3],
}


def scenario_rng(seed: int, scenario_id: str) -> np.random.Generator:
    return np.random.default_rng([seed, int(scenario_id.split("-")[1], 16) % (2**32)])


def build_network(topology: str):
    """Return nodes, links and asset placement for a topology family (deterministic)."""
    seg_sizes = TOPOLOGY_SPEC[topology]
    nodes, links = [("gw", "gateway", -1)], []
    sw = [f"sw{s}" for s in range(len(seg_sizes))]
    if topology == "star":
        nodes.append(("sw0", "switch", 0)); links.append(("gw", "sw0", "uplink"))
    elif topology == "tree":
        nodes += [("core", "router", -1), ("d0", "router", -1), ("d1", "router", -1)]
        links += [("gw", "core", "uplink"), ("core", "d0", "trunk"), ("core", "d1", "trunk")]
        for s, parent in zip(range(3), ["d0", "d0", "d1"]):
            nodes.append((sw[s], "switch", s)); links.append((parent, sw[s], "trunk"))
    elif topology == "partial_mesh":
        r = [f"r{i}" for i in range(4)]
        nodes += [(x, "router", -1) for x in r]
        links += [("gw", "r0", "uplink"), ("r0", "r1", "mesh"), ("r1", "r2", "mesh"),
                  ("r2", "r3", "mesh"), ("r3", "r0", "mesh"), ("r0", "r2", "mesh")]
        for s in range(4):
            nodes.append((sw[s], "switch", s)); links.append((r[s], sw[s], "access"))
    elif topology == "ring":
        for s in range(4):
            nodes.append((sw[s], "switch", s))
        links += [("gw", "sw0", "uplink")] + [(sw[i], sw[(i + 1) % 4], "ring") for i in range(4)]
    elif topology == "hub_spoke":
        nodes.append(("hub", "router", -1)); links.append(("gw", "hub", "uplink"))
        for s in range(4):
            nodes += [(f"cpe{s}", "router", -1), (sw[s], "switch", s)]
            links += [("hub", f"cpe{s}", "wan"), (f"cpe{s}", sw[s], "access")]
    elif topology == "segmented_dmz":
        nodes += [("sw0", "switch", 0), ("ifw", "firewall", -1), ("core", "router", -1),
                  ("sw1", "switch", 1), ("sw2", "switch", 2)]
        links += [("gw", "sw0", "uplink"), ("gw", "ifw", "trunk"), ("ifw", "core", "trunk"),
                  ("core", "sw1", "access"), ("core", "sw2", "access")]
    else:
        raise ValueError(topology)
    assets = []
    k = 0
    for s, n in enumerate(seg_sizes):
        for _ in range(n):
            nodes.append((f"h{k}", "host", s)); links.append((sw[s], f"h{k}", "access"))
            assets.append((f"h{k}", s)); k += 1
    # hop count from gateway (BFS)
    adj = {}
    for u, v, _ in links:
        adj.setdefault(u, []).append(v); adj.setdefault(v, []).append(u)
    dist, q = {"gw": 0}, deque(["gw"])
    while q:
        u = q.popleft()
        for v in adj.get(u, []):
            if v not in dist:
                dist[v] = dist[u] + 1; q.append(v)
    return nodes, links, assets, dist, len(seg_sizes)


def generate_scenario(srow: dict, cfg: dict) -> dict:
    sid = srow["scenario_id"]
    rng = scenario_rng(cfg["seed"], sid)
    nodes, links, placement, dist, n_seg = build_network(srow["topology"])
    net_id = stable_id("net", sid)

    # ---- assets with information value from technical, economic and security indicators
    w = cfg["value_weights"]
    assets = []
    for node, seg in placement:
        atype = ASSET_TYPES[rng.integers(len(ASSET_TYPES))]
        tech, econ, sec = rng.beta(2.5, 2.0), rng.beta(2.0, 2.5), rng.beta(2.2, 2.2)
        if atype in ("database", "storage"):
            sec = min(1.0, sec + 0.15)
        rel = rng.uniform(0.70, 1.00)
        value = cfg["asset_value_scale_kcu"] * rel * (w["technical"] * tech + w["economic"] * econ + w["security"] * sec)
        assets.append({"asset_id": stable_id("ast", sid, node), "scenario_id": sid, "node": node,
                       "segment": seg, "asset_type": atype, "hops": dist[node],
                       "ind_technical": tech, "ind_economic": econ, "ind_security": sec,
                       "info_reliability": rel, "info_value_kcu": value})
    A = len(assets)

    # ---- vulnerabilities (1-3 per asset), class mask
    vulns = []
    for a in assets:
        for j in range(rng.integers(1, 4)):
            mask = rng.random(6) < 0.45
            mask[rng.integers(6)] = True
            vulns.append({"vuln_id": stable_id("vul", a["asset_id"], j), "scenario_id": sid,
                          "asset_id": a["asset_id"], "exploitability": rng.uniform(0.05, 0.60),
                          "class_mask": "".join("1" if m else "0" for m in mask)})

    # ---- threats drawn by family profile
    dom = CLASSES.index(FAMILY_DOMINANT[srow["family"]])
    pw = np.full(6, 0.5 / 5); pw[dom] = 0.5
    threats = []
    for j in range(cfg["threats_per_scenario"]):
        c = rng.choice(6, p=pw)
        threats.append({"threat_id": stable_id("thr", sid, j), "scenario_id": sid, "threat_class": CLASSES[c],
                        "origin": "internal" if CLASSES[c] == "INS" else "external",
                        "rate_per_year": float(rng.lognormal(np.log(1.5), 0.6)),
                        "severity": float(rng.beta(2.0, 3.0))})

    # ---- barriers: first `depth` layers, three tiers per layer, scope depends on layer and topology
    layers = cfg["layers"][: srow["depth"]]
    seg_of = np.array([a["segment"] for a in assets])
    barriers = []
    for li, lname in enumerate(layers):
        for tname, de, cm in TIER:
            if li == 0:
                scope = np.ones(A, bool)
            elif li in (1, 2):
                scope = seg_of == rng.integers(n_seg)
                if li == 1 and rng.random() < 0.4:        # some network barriers span two segments
                    scope |= seg_of == rng.integers(n_seg)
            else:
                scope = rng.random(A) < 0.5
                scope[rng.integers(A)] = True
            e = float(np.clip(srow["effectiveness_mean"] + de + rng.normal(0, 0.04), 0.05, 0.97))
            cost = float(LAYER_BASE_COST[li] * cm * rng.lognormal(0, 0.15) * (0.5 + 0.5 * scope.mean()))
            barriers.append({"barrier_id": stable_id("bar", sid, lname, tname), "scenario_id": sid,
                             "layer": lname, "layer_index": li + 1, "tier": tname,
                             "effectiveness": e, "annual_cost_kcu": cost,
                             "scope_mask": "".join("1" if s else "0" for s in scope)})

    # ---- estimated parameters under input-information reliability rho
    s = cfg["reliability_noise_gain"] * (1.0 - srow["input_reliability"])
    for t in threats:
        t["rate_est"] = t["rate_per_year"] * float(np.exp(rng.normal(0, s) - s * s / 2))
        t["severity_est"] = float(np.clip(t["severity"] * np.exp(rng.normal(0, s / 2)), 0.01, 1.0))
    for b in barriers:
        lg = np.log(b["effectiveness"] / (1 - b["effectiveness"])) + rng.normal(0, s)
        b["effectiveness_est"] = float(1 / (1 + np.exp(-lg)))
        b["cost_est"] = b["annual_cost_kcu"] * float(np.exp(rng.normal(0, s * cfg["cost_noise_ratio"])))

    network = {"network_id": net_id, "scenario_id": sid, "topology": srow["topology"],
               "n_nodes": len(nodes), "n_links": len(links), "n_segments": n_seg, "n_assets": A,
               "max_hops": max(a["hops"] for a in assets)}
    node_rows = [{"network_id": net_id, "node_id": f"{net_id}:{n}", "role": r, "segment": sg} for n, r, sg in nodes]
    link_rows = [{"network_id": net_id, "link_id": f"{net_id}:{u}-{v}", "u": f"{net_id}:{u}",
                  "v": f"{net_id}:{v}", "link_kind": k} for u, v, k in links]
    return {"network": network, "nodes": node_rows, "links": link_rows, "assets": assets,
            "vulnerabilities": vulns, "threats": threats, "barriers": barriers}
