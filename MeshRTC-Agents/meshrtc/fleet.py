"""
Fleet-level agent logic for one blackout shift.

Policies
  C  centralized: the CC dispatches robots from the depot (up to 2 requests per robot);
     requests reach the CC through the mesh or out of band.
  A  agentic: in addition robots carry spare units, pick up requests from recipient
     nodes they pass (store-carry-forward, DTN), exchange them peer-to-peer and allocate
     them in field auctions (BID -> LSE) while keeping the SFC feasibility predicate true.
"""
from __future__ import annotations

import numpy as np

from . import protocol as pr
from .sim import CLOCK0, ROBOT
from .world import RADIO

CHARGERS = 2
P_CHARGE = 350.0
DEADLINE = 120.0
P2P_M = 600.0


class FleetLogic:
    def __init__(self, sim):
        self.sim, self.w = sim, sim.w
        self.created = set()
        self.picked = set()
        self.site_margin = {}
        for k, s in self.w.sites.items():
            if s.kind == "recipient":
                self.site_margin[k] = sim.sc.fab.margin_from(s.node, RADIO["h_fac"]) + sim.sc.shadow[-1] * 0.5
        self.agentic = sim.cfg.policy == "A"
        for r in sim.robots:
            r.phase = "idle"

    # ---------------------------------------------------------------- helpers
    def site_online(self, site, t):
        sim = self.sim
        node = self.w.sites[site].node
        return sim.sc.site_node_ok(site) and not sim.jammed(t) and sim.sc.best_margin[node] + 10 > 0

    def step(self, t, dt):
        sim = self.sim
        reqs = sim.sc.requests
        # 1. new requests
        for r in reqs:
            if r["t_c"] <= t and r["id"] not in self.created:
                self.created.add(r["id"])
                if self.site_online(r["site"], t):
                    p = sim.new_packet(t, "N" + r["site"], "CC", pr.REQ(int(r["site"][1:]), 1, r["cargo"], 1, r["id"]))
                    sim.deliver(p, t, "mesh", int(sim.sc.best_hops[self.w.sites[r["site"]].node]))
                    r["cc_known"] = p.t_recv
        for r in reqs:
            if r["cc_known"] == np.inf and t >= r["oob"]:
                r["cc_known"] = r["oob"]
        # 2. charging
        idle = [rb for rb in sim.robots if rb.phase == "idle" and not rb.is_relay]
        idle.sort(key=lambda rb: rb.E)
        for i, rb in enumerate(idle):
            if i < CHARGERS and rb.E < 0.95 * rb.cap:
                rb.E = min(0.95 * rb.cap, rb.E + P_CHARGE * dt / 60.0 * 0.92)
        # 3. dispatch from depot
        if int(round(t / dt)) % 4 == 0:
            self.dispatch(t)
        # 4. agentic field logic (every minute)
        if self.agentic and int(round(t / dt)) % 4 == 0:
            self.field(t)

    def dispatch(self, t):
        sim = self.sim
        pend = [r for r in sim.sc.requests if r["cc_known"] <= t and r["assigned"] is None
                and r["t_del"] == np.inf and not r["cc_dispatched"]]
        pend.sort(key=lambda r: r["t_c"])
        for rb in sorted([rb for rb in sim.robots if rb.phase == "idle" and not rb.is_relay], key=lambda rb: -rb.E):
            if not pend:
                break
            first = pend[0]
            chosen = [first]
            if len(pend) > 1:
                d = [np.linalg.norm(self.w.xy[self.w.sites[r["site"]].node] - self.w.xy[self.w.sites[first["site"]].node])
                     for r in pend[1:]]
                chosen.append(pend[1 + int(np.argmin(d))])
            for ch in (chosen, chosen[:1]):
                nodes = [self.w.sites[r["site"]].node for r in ch]
                ok, _ = rb.planner.F_D(rb.node, nodes, 1.0)
                if ok:
                    for r in ch:
                        r["assigned"] = rb.uid
                        r["cc_dispatched"] = True
                        pend.remove(r)
                        sim.cc_send(t, pr.TSK(r["id"], int(r["site"][1:]), int(sim.nearest_open(r["site"], t)[1:]),
                                              CLOCK0 + r["t_c"] + DEADLINE, rb.z), dst=rb.name)
                    rb.comm(t, force_path="local")
                    rb.units = sim.cfg.capacity_units if self.agentic else len(ch)
                    rb.spare = rb.units - len(ch)
                    rb.ever_moved = False
                    rb.phase = "outbound"
                    rb.trip_start = t
                    rb.epoch(t)
                    break

    def eta(self, rb, stops, idx, t):
        """Arrival time at stops[idx] along energy-shortest legs."""
        P = rb.planner
        cur, T = rb.node, t
        for j, s in enumerate(stops[: idx + 1]):
            arcs = P.route(cur, s["node"], rb.kappa)
            if not arcs and cur != s["node"]:
                return np.inf
            T += float(self.w.arc_time(arcs, rb.kappa).sum()) + (ROBOT["dwell"] if j < idx else 0)
            cur = s["node"]
        return T

    def bid(self, rb, r, t):
        if rb.spare <= 0 or rb.phase != "outbound" or rb.terminal:
            return None
        open_ = rb._open_stops()
        new = dict(task=r["id"], site=r["site"], alt=None, node=self.w.sites[r["site"]].node,
                   deadline=r["t_c"] + DEADLINE, delivered=False)
        best = None
        for pos in range(len(open_) + 1):
            cand = open_[:pos] + [new] + open_[pos:]
            ok, _ = rb.planner.F_D(rb.node, [s["node"] for s in cand], rb.kappa)
            if not ok:
                continue
            e = self.eta(rb, cand, pos, t)
            if e <= r["t_c"] + DEADLINE + 30 and (best is None or e < best[0]):
                best = (e, pos, new)
        return best

    def field(self, t):
        sim, w = self.sim, self.w
        act = [rb for rb in sim.robots if rb.phase in ("outbound", "return", "dwell") and not rb.is_relay]
        for rb in act:
            # DTN pickup from recipient nodes in radio range (or when at the site)
            for site, m in self.site_margin.items():
                if not sim.sc.site_node_ok(site):
                    heard = rb.node == w.sites[site].node
                else:
                    heard = m[rb.node] + sim.rng.normal(0, RADIO["fading"]) > 0 or rb.node == w.sites[site].node
                if not heard:
                    continue
                for r in sim.sc.requests:
                    if r["site"] == site and r["t_c"] <= t and r["t_del"] == np.inf and (r["id"], rb.uid) not in self.picked:
                        self.picked.add((r["id"], rb.uid))
                        rb.known_reqs.add(r["id"])
                        r["rob_known"] = min(r["rob_known"], t)
                        p = sim.new_packet(t, "N" + site, rb.name, pr.REQ(int(site[1:]), 1, r["cargo"], 1, r["id"]), False, "RELIABLE")
                        sim.deliver(p, t, "p2p", 1)
                        # carry it to the CC (store-carry-forward)
                        rb.send(t, pr.REQ(int(site[1:]), 1, r["cargo"], 1, r["id"]))
            if rb.contact:
                for r in sim.sc.requests:
                    if r["cc_known"] <= t and r["assigned"] is None and r["t_del"] == np.inf:
                        rb.known_reqs.add(r["id"])
        # peer-to-peer exchange of known requests
        for i in range(len(act)):
            for j in range(i + 1, len(act)):
                a, b = act[i], act[j]
                if np.linalg.norm(w.xy[a.node] - w.xy[b.node]) < P2P_M:
                    u = a.known_reqs | b.known_reqs
                    if u != a.known_reqs or u != b.known_reqs:
                        a.known_reqs, b.known_reqs = set(u), set(u)
                        for rid in u:
                            sim.req_by_id[rid]["rob_known"] = min(sim.req_by_id[rid]["rob_known"], t)
        # in-field auction
        for rb in act:
            if rb.spare <= 0:
                continue
            for rid in sorted(rb.known_reqs, key=lambda k: sim.req_by_id[k]["t_c"]):
                r = sim.req_by_id[rid]
                if r["assigned"] is not None or r["t_del"] < np.inf or r["t_c"] > t:
                    continue
                mine = self.bid(rb, r, t)
                if mine is None:
                    continue
                pb = sim.new_packet(t, rb.name, "^robots", pr.BID(rid, rb.uid, CLOCK0 + mine[0]), False, "DEFAULT")
                sim.deliver(pb, t, "p2p", 1)
                better = False
                for o in act:
                    if o is rb or np.linalg.norm(w.xy[o.node] - w.xy[rb.node]) >= P2P_M:
                        continue
                    ob = self.bid(o, r, t)
                    if ob is not None:
                        po = sim.new_packet(t, o.name, "^robots", pr.BID(rid, o.uid, CLOCK0 + ob[0]), False, "DEFAULT")
                        sim.deliver(po, t, "p2p", 1)
                        if ob[0] < mine[0] - 1e-6:
                            better = True
                if better:
                    continue
                e, pos, new = mine
                r["assigned"] = rb.uid
                open_ = rb._open_stops()
                done = [s for s in rb.stops if s["delivered"]]
                rb.stops = done + open_[:pos] + [new] + open_[pos:]
                rb.spare -= 1
                rb.log_decision(t, "LEASE", f"T{rid} {r['site']}")
                rb.send(t, pr.LSE(rid, rb.uid, 30), dst="^all")
                if rb.spare <= 0:
                    break

    # ---------------------------------------------------------------- metrics
    @staticmethod
    def metrics(sim):
        R = sim.sc.requests
        n = len(R)
        on_time = [r["t_del"] <= r["t_c"] + DEADLINE for r in R]
        aware = [min(r["cc_known"], r["rob_known"]) - r["t_c"] for r in R]
        lat = [r["t_rec"] - r["t_del"] for r in R if r["t_del"] < np.inf]
        deliv = sum(r["t_del"] < np.inf for r in R)
        km = sum(rb.dist for rb in sim.robots) / 1000.0
        return dict(policy=sim.cfg.policy, n=n, service=float(np.mean(on_time)) if n else np.nan,
                    delivered=deliv / max(n, 1), aware_med=float(np.median(aware)) if n else np.nan,
                    lat_med=float(np.median(lat)) if lat else np.nan, km_per=km / max(deliv, 1),
                    stranded=sum(rb.terminal in ("depleted",) for rb in sim.robots),
                    dups=sum(r["dup"] for r in R), packets=len(sim.packets),
                    gw_air=sum(s for _, s, _ in sim.gw_tx))
