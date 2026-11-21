"""
Multi-agent digital twin of a robotic transport complex that is coordinated by short
commands over a Meshtastic mesh.

Agents
  Orchestrator (CC)   issues task contracts (TSK), closures (CLS), blockage news (BLK U0),
                      recalls (RTB), risk dial (ZSET), relay orders (RLY); dispatches the fleet
  Comms steward       part of the CC; enforces the 1 % duty-cycle budget of the gateway and
                      the reporting policy (RPT)
  Robot agent         onboard controller: S1 stop-on-loss, S2 fixed-route or
                      S3 Supervisory Feasibility Controller (SFC); optional neural modules
  Recipient node      Meshtastic node at a relief site: emits requests (REQ), co-signs receipts
  Relay UGV           robot with a 10 m telescopic mast that extends the mesh when ordered by RLY

Time unit: minutes. Energy: Wh. All data synthetic.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

import numpy as np

from . import protocol as pr
from .world import (ROBOT, RADIO, World, RadioFabric, dijkstra, path_arcs, link_margin,
                    norm_cdf, C_ROLL)

CLOCK0 = 8 * 60          # missions start at 08:00
STRATS = ("S1", "S2", "S3")
STRAT_NAMES = {"S1": "S1 Stop-on-loss", "S2": "S2 Fixed-route", "S3": "S3 SFC",
               "S3N": "S3N SFC + neural energy", "NNP": "Neural policy + shield"}


# =========================================================================== config
@dataclass
class Config:
    """Declarative description of one transport scenario."""
    name: str = "custom"
    title: str = ""
    H: float = 24.0                 # outage age at mission start (h)
    k: int = 4                      # autonomous repeaters
    b: float = 0.05                 # blocked fraction of street segments
    soc0: float = 0.7               # initial state of charge
    tasks: List[dict] = field(default_factory=lambda: [dict(site="R3", alt="R5")])
    n_robots: int = 1
    strategy: str = "S3"
    z: float = ROBOT["z"]
    oneway: bool = False
    snow: Optional[float] = None    # None -> random U(1.0, 1.8)
    temp: Optional[float] = None    # None -> random U(-15, 0)
    payload_kg: float = 20.0
    gnss_denied: Optional[bool] = None   # None -> random (p = 0.35)
    p_close: float = 0.12
    closures: List[dict] = field(default_factory=list)   # [{t, site, alt}]
    blocked_edges: Optional[List[int]] = None            # force specific blocked edges
    cc_known_frac: float = 0.5
    jam_mesh: bool = False          # all mesh infrastructure silent
    cell_off: bool = False          # cellular network gone
    hop_limit: int = pr.DEFAULT_HOP_LIMIT
    preset: str = "SHORT_FAST"
    encoding: str = "text"          # text | binary
    reporting: str = "event"        # event | periodic
    status_period: float = 10.0     # min (event) - periodic uses 1 min
    dual_receipt: bool = False      # recipient node forwards a co-signed receipt copy
    events: List[dict] = field(default_factory=list)     # scripted CC commands
    horizon: float = 360.0
    # fleet
    fleet: bool = False
    policy: str = "C"               # C centralized / A agentic (spare + auction + DTN)
    req_rate: float = 2.4           # requests per hour
    shift: float = 480.0
    capacity_units: int = 2
    relay: bool = False             # relay UGV deployed by twin planner at t = 0
    energy_model: Optional[Callable] = None      # neural energy model (mean, std per arc)
    policy_model: Optional[Callable] = None      # neural supervisory policy (+ shield)
    shield: bool = True                          # runtime-assurance shield for the neural policy
    seed: int = 1


# =========================================================================== scenario truth
class Scenario:
    """Common random numbers for paired runs: everything nature decides."""

    def __init__(self, world: World, cfg: Config, seed: int):
        self.w, self.cfg, self.seed = world, cfg, seed
        rng = np.random.default_rng(seed)
        w = world
        nE = len(w.edges)
        self.snow = cfg.snow if cfg.snow is not None else float(rng.uniform(1.0, 1.8))
        self.temp = cfg.temp if cfg.temp is not None else float(rng.uniform(-15, 0))
        self.snow_fc = float(np.clip(self.snow + rng.normal(0, 0.2), 1.0, 2.0))
        self.gnss_denied = cfg.gnss_denied if cfg.gnss_denied is not None else bool(rng.random() < 0.35)
        self.cap = World.capacity(self.temp)
        # blockages in spatial clusters
        blocked = np.zeros(nE, bool)
        if cfg.blocked_edges is not None:
            blocked[list(cfg.blocked_edges)] = True
        elif cfg.b > 0:
            mid = (w.xy[w.edges[:, 0]] + w.xy[w.edges[:, 1]]) / 2
            protect = set()
            for s in w.sites.values():
                protect.update(a for a in w.adj[s.node])
            target = int(cfg.b * nE)
            while blocked.sum() < target:
                c = mid[rng.integers(nE)]
                d = np.linalg.norm(mid - c, axis=1)
                for e in np.argsort(d)[: rng.integers(2, 6)]:
                    blocked[e] = True
            for a in protect:
                blocked[w.arc_e[a]] = False
        self.blocked = blocked
        known = blocked & (rng.random(nE) < cfg.cc_known_frac)
        self.cc_known0 = known
        self.reveal = np.where(blocked & ~known, rng.exponential(40.0, nE), np.inf)
        # radio fabric and node survival
        self.fab = RadioFabric(w, cfg.k, seed=0)
        m = len(self.fab.infra)
        alive = np.ones(m, bool)
        for i, (name, _, _) in enumerate(self.fab.infra):
            if name.startswith("RP"):
                alive[i] = rng.random() < 0.99
            elif name.startswith("FP"):
                alive[i] = rng.random() < 0.95
            elif name.startswith("FR"):
                alive[i] = rng.random() < 0.5 + 0.5 * math.exp(-cfg.H / 30.0)
        if cfg.jam_mesh:
            alive[:] = False
        self.alive = alive
        self.shadow = rng.normal(0, RADIO["shadow"], (m + 1, w.n))
        self._margins(None)
        # cellular
        ncell = len(w.cell_xy)
        gen = rng.random(ncell) < 0.67
        self.cell_aut = np.where(gen, 8.0 + rng.exponential(60.0, ncell), rng.uniform(1, 8, ncell))
        self.cell_bh = rng.random(ncell) < 0.85
        if cfg.cell_off:
            self.cell_aut[:] = 0.0
        # true energy: physics + effects the planner does not model
        self.arc_noise = np.exp(rng.normal(0, ROBOT["sigma_e"], len(w.arc_u)) - 0.005)
        # closures
        self.closures = {}
        for c in cfg.closures:
            self.closures[c["site"]] = (c["t"], c.get("alt"))
        names = [f"R{i}" for i in range(1, 9)]
        self.random_close = {n: (float(rng.uniform(5, 90)) if rng.random() < cfg.p_close else np.inf)
                             for n in names}
        # fleet requests (Poisson) - common to policies
        rr = np.random.default_rng(seed + 999)
        self.requests = []
        if cfg.fleet:
            t = 0.0
            while True:
                t += rr.exponential(60.0 / cfg.req_rate)
                if t > cfg.shift:
                    break
                site = names[rr.integers(len(names))]
                self.requests.append(dict(id=len(self.requests) + 1, site=site, t_c=t,
                                          oob=t + rr.uniform(45, 120), cargo=int(rr.integers(1, 4))))

    # ---------------------------------------------------------------- radio
    def _margins(self, relay_node):
        fab, w = self.fab, self.w
        alive = self.alive.copy()
        hop = fab.infra_graph(alive)
        rows = fab.node_margins(alive)
        hops = list(hop)
        if relay_node is not None and alive.any():
            # relay mast is connected if it reaches a connected infra node over a rooftop link
            xy = w.xy[relay_node]
            best = np.inf
            for i, (_, n, h) in enumerate(fab.infra):
                if alive[i] and np.isfinite(hop[i]):
                    if link_margin(np.linalg.norm(w.xy[n] - xy), h, RADIO["h_mast"]) + w.clutter[relay_node] * 0.5 > 3.0:
                        best = min(best, hop[i] + 1)
            rows = np.vstack([rows, fab.margin_from(relay_node, RADIO["h_mast"])])
            hops.append(best)
        hops = np.array(hops)
        M = rows + self.shadow[: len(rows)]
        ok = hops <= self.cfg.hop_limit
        M = np.where(ok[:, None], M, -99.0)
        self.best_margin = M.max(axis=0)
        self.best_hops = hops[np.argmax(M, axis=0)] + 1
        self.prior_pc = 1 - (1 - norm_cdf(np.where(ok[:, None], rows, -99.0).max(axis=0) / 6.0)) * (1 - 0.6)

    def deploy_relay(self, node):
        self._margins(node)

    def site_closed(self, site, t):
        tc = min(self.closures.get(site, (np.inf, None))[0], self.random_close.get(site, np.inf)
                 if self.cfg.p_close > 0 and not self.cfg.fleet else np.inf)
        return t >= tc

    def site_node_ok(self, site):
        names = [n for n, _, _ in self.fab.infra]
        return bool(self.alive[names.index("F" + site)])

    def true_energy(self, arcs, kappa, payload_kg):
        """Ground-truth consumption (Wh). Unknown to the planner: class-dependent snow
        response, cold-reduced drive efficiency and heating load."""
        w = self.w
        arcs = np.asarray(arcs)
        cls = w.arc_cls[arcs]
        s_eff = 1 + (self.snow - 1) * np.array([0.7, 1.0, 1.6])[cls]
        cold = max(0.0, -self.temp)
        m = 120.0 + payload_kg
        L, dz, c = w.arc_L[arcs], w.arc_dz[arcs], C_ROLL[cls]
        W = m * 9.81 * (c * s_eff * L + dz)
        eta = ROBOT["eta_d"] * (1 - 0.006 * cold)
        W = np.where(W >= 0, W / eta, ROBOT["eta_r"] * W)
        v = np.array([1.8, 1.6, 1.2])[cls] * kappa
        p_aux = ROBOT["p_move"] + 1.5 * cold
        return (W + p_aux * L / v) / 3600.0 * self.arc_noise[arcs]


# =========================================================================== planner
class Planner:
    """Energy-shortest paths with chance-constrained requirements (Eq. 5)."""

    def __init__(self, sim, robot):
        self.sim, self.w, self.r = sim, sim.w, robot
        sc, cfg = sim.sc, sim.cfg
        arcs = np.arange(len(self.w.arc_u))
        self.base = {}
        for kap in (1.0, ROBOT["kappa_c"]):
            if robot.energy_model is not None:
                mu, sd = robot.energy_model(self.w, arcs, kap, sc.snow_fc, sc.temp, cfg.payload_kg)
            else:
                mu = self.w.arc_energy(arcs, sc.snow_fc, kap, mass=120 + cfg.payload_kg, temp=sc.temp)
                sd = ROBOT["sigma_e"] * mu
            self.base[kap] = (np.asarray(mu, float), np.asarray(sd, float) ** 2)
        self.cache = {}
        self.kv = -1

    def weights(self, kap, comm_aware=False):
        key = ("w", kap, comm_aware, self.r.kv)
        if key not in self.cache:
            mu, var = self.base[kap]
            w = mu.copy()
            w[self.r.known_arc_block] = np.inf
            if comm_aware:
                pc = self.sim.sc.prior_pc[self.w.arc_v]
                w = w * (1 + ROBOT["lam"] * (1 - pc))
            self.cache[key] = (w, var)
        return self.cache[key]

    def tree_to(self, target, kap, comm_aware=False):
        key = ("t", target if np.isscalar(target) else tuple(target), kap, comm_aware, self.r.kv)
        if key not in self.cache:
            w, var = self.weights(kap, comm_aware)
            if comm_aware:   # comm-aware tree for routing, but keep true predicted energy for checks
                mu, _ = self.weights(kap)
                d, v, via, root = dijkstra(self.w, w, target, reverse=True, w2=var)
                e = self._sum_along(mu, via, root)
                self.cache[key] = (e, v, via, root)
            else:
                self.cache[key] = dijkstra(self.w, w, target, reverse=True, w2=var)
        return self.cache[key]

    def _sum_along(self, mu, via, root):
        n = self.w.n
        out = np.full(n, np.inf)
        for x in range(n):
            if root[x] < 0:
                continue
            s, y, k = 0.0, x, 0
            while via[y] >= 0 and k < n:
                s += mu[via[y]]
                y = int(self.w.arc_v[via[y]])
                k += 1
            out[x] = s
        return out

    def need(self, mu, var):
        r = self.r
        if not np.isfinite(mu):
            return np.inf
        rh = r.r_hat()
        sr = r.sigma_r0 / math.sqrt(1 + r.n_arcs / 5.0)
        return rh * mu + r.z * math.sqrt(var + (sr * rh * mu) ** 2) + ROBOT["reserve"] * r.cap

    def chain(self, x, nodes, kap, to_recovery=True):
        """Predicted energy and variance along x -> nodes[0] -> ... -> recovery."""
        mu, var, cur = 0.0, 0.0, x
        for n in nodes:
            d, v, _, _ = self.tree_to(n, kap)
            mu += d[cur]
            var += v[cur]
            cur = n
        if to_recovery:
            d, v, _, _ = self.tree_to(tuple(self.sim.recovery), kap)
            mu += d[cur]
            var += v[cur]
        return mu, var

    def F_D(self, x, nodes, kap):
        mu, var = self.chain(x, nodes, kap, True)
        need = self.need(mu, var)
        return self.r.avail() >= need, need

    def F_H(self, x, nodes, kap):
        mu, var = self.chain(x, nodes, kap, False)
        need = self.need(mu, var)
        return self.r.avail() >= need, need

    def F_R(self, x, kap, point=None):
        tgt = tuple(self.sim.recovery) if point is None else point
        d, v, _, _ = self.tree_to(tgt, kap)
        need = self.need(d[x], v[x])
        return self.r.avail() >= need, need

    def route(self, x, target, kap, comm_aware=False):
        d, v, via, root = self.tree_to(target, kap, comm_aware)
        if not np.isfinite(d[x]):
            return []
        dst = root[x] if not np.isscalar(target) else target
        return path_arcs(self.w, via, x, int(dst), reverse=True)


# =========================================================================== agents
class Robot:
    def __init__(self, sim, uid: int, node: int, soc0: float, strategy: str, relay: bool = False):
        self.sim, self.w = sim, sim.w
        self.uid, self.name = uid, f"U{uid}"
        self.node, self.strategy, self.is_relay = node, strategy, relay
        cfg = sim.cfg
        self.cap = sim.sc.cap
        self.E = soc0 * self.cap
        self.Emin = ROBOT["cutoff"] * self.cap
        self.z, self.oneway = cfg.z, cfg.oneway
        self.energy_model = cfg.energy_model if strategy in ("S3N",) else None
        # residual uncertainty of the calibration ratio: the learned model already explains
        # the systematic (temperature / surface) part of the forecast error
        self.sigma_r0 = 0.03 if self.energy_model is not None else 0.10
        self.policy_model = cfg.policy_model if strategy == "NNP" else None
        self.known_arc_block = np.zeros(len(self.w.arc_u), bool)
        self.kv = 0
        self.planner = Planner(sim, self)
        self.rng = np.random.default_rng(sim.seed * 7 + 11 + uid)
        self.stops: List[dict] = []     # each: task, site, alt, node, deadline, delivered
        self.arcs: List[int] = []
        self.pos = 0.0
        self.phase = "idle"             # idle / outbound / return / wait / dwell / beacon / done
        self.terminal = None
        self.wait = 0.0
        self.target = None
        self.sum_true = self.sum_pred = 0.0
        self.n_arcs = 0
        self.sigma = 2.5
        self.lost = 0
        self.kappa = 1.0
        self.outbox: List[pr.Packet] = []
        self.contact = True
        self.dist = 0.0
        self.trace = []
        self.decisions = []
        self.last_status = -1e9
        self.spare = 0
        self.units = 0
        self.known_reqs = set()
        self.pending_hold = False
        self.ever_moved = False
        self.recall = None

    # ---------------------------------------------------------------- energy helpers
    def avail(self):
        return self.E - self.Emin

    def soc(self):
        return max(self.E, 0.0) / self.cap

    def r_hat(self):
        w0 = ROBOT["w0"]
        return (w0 + self.sum_true) / (w0 + self.sum_pred)

    def learn_block(self, edge):
        if not self.known_arc_block[self.w.arc_e == edge].any():
            self.known_arc_block[self.w.arc_e == edge] = True
            self.kv += 1
            return True
        return False

    # ---------------------------------------------------------------- messaging
    def send(self, t, cmd, dst="CC", want_ack=True, prio="RELIABLE"):
        p = self.sim.new_packet(t, self.name, dst, cmd, want_ack, prio)
        self.outbox.append(p)
        return p

    def log_decision(self, t, code, info=""):
        self.decisions.append((t, self.node, code, info, round(self.soc(), 3)))

    def report(self, t, code, target):
        self.log_decision(t, code, target)
        self.send(t, pr.DEC(self.uid, code, target, self.soc()))

    def handle(self, t, cmd: pr.Command):
        """React to a command received over the mesh."""
        op, f = cmd.op, cmd.f
        if op == "TSK":
            site = f"R{f['site']}"
            self.stops.append(dict(task=f["task"], site=site, alt=f"R{f['alt']}", node=self.w.sites[site].node,
                                   deadline=f["deadline"] - CLOCK0 if f["deadline"] >= CLOCK0 else f["deadline"] + 1440 - CLOCK0,
                                   delivered=False))
            self.z, self.oneway = f["z"] / 100.0, bool(f["oneway"])
        elif op == "CLS":
            if self.strategy == "S2":
                return                         # fixed-route ignores in-mission updates
            for s in self.stops:
                if not s["delivered"] and s["site"] == f"R{f['site']}":
                    s["closed"] = f"R{f['alt']}"
        elif op == "BLK":
            if self.strategy != "S2" and self.learn_block(f["edge"]):
                pass
        elif op == "ZSET":
            self.z = f["z"] / 100.0
        elif op == "RTB" and f["unit"] == self.uid:
            self.recall = pr.POINT_NAMES[f["point"]]
        elif op == "HLD" and f["unit"] == self.uid:
            if self.phase in ("outbound", "return"):
                self.wait = max(self.wait, f["minutes"])
                self.phase_after = self.phase
                self.phase = "wait"
                self.log_decision(t, "HOLD-CMD", f"{f['minutes']} min")
        elif op == "RLY" and f["unit"] == self.uid:
            self.stops = [dict(task=0, site="RLY", alt=None, node=f["node"], deadline=np.inf,
                               delivered=False, relay=True)]
            self.phase = "outbound"
        elif op == "LSE":
            r = self.sim.req_by_id.get(f["task"])
            if r is not None and r.get("assigned") is None:
                r["assigned"] = f["unit"]
        elif op == "RPT":
            self.sim.cfg.reporting = "event" if f["period"] == 0 else "periodic"

    def comm(self, t, force_path=None):
        """One contact check: flush outbox, fetch downlink."""
        ok, path, hops = (True, force_path, 0) if force_path else self.sim.check_contact(self.node, t)
        self.contact = ok
        if not ok:
            return False
        sim = self.sim
        for p in self.outbox:
            sim.deliver(p, t, path, hops)
        self.outbox = [p for p in self.outbox if not np.isfinite(p.t_recv)]
        for p in sim.fetch_downlink(self, t, path, hops):
            self.handle(t, p.cmd)
        return True

    # ---------------------------------------------------------------- dynamics
    def step(self, t, dt):
        sim, cfg = self.sim, self.sim.cfg
        if self.terminal in ("recovered", "depleted", "declined") and not cfg.fleet:
            return
        if self.phase in ("done",):
            return
        # periodic status beacon (heartbeat)
        period = 1.0 if cfg.reporting == "periodic" else cfg.status_period
        if t - self.last_status >= period and self.phase not in ("idle",):
            self.last_status = t
            ok, path, hops = sim.check_contact(self.node, t)
            if ok:
                p = sim.new_packet(t, self.name, "^all", pr.RS(self.uid % 256, self.node, self.soc(),
                                   max(self.avail(), 0), sim.regime(self.node, t)),
                                   want_ack=cfg.reporting == "periodic", prio="BACKGROUND")
                sim.deliver(p, t, path, hops)
        if self.phase in ("wait", "dwell", "beacon", "held"):
            p_idle = ROBOT["p_beacon"] if self.phase == "beacon" else ROBOT["p_idle"]
            self.E -= p_idle * dt / 60.0
            if self.E <= self.Emin:
                self._deplete(t)
                return
            if self.phase in ("beacon", "held"):
                if int(t / dt) % int(2.0 / dt) == 0:
                    self.comm(t)
                return
            self.wait -= dt
            if self.phase == "wait" and self.strategy == "S1" and self.wait <= 0:
                if self.comm(t):
                    self.phase = "outbound" if any(not s["delivered"] for s in self.stops) else "return"
                    self.epoch(t)
                else:
                    self.wait = 1.0
                return
            if self.wait <= 0:
                self.phase = getattr(self, "phase_after", "outbound")
                self.epoch(t)
            return
        if self.phase not in ("outbound", "return"):
            return
        budget = dt
        while budget > 1e-9 and self.phase in ("outbound", "return"):
            if not self.arcs:
                self.epoch(t + dt - budget)
                if not self.arcs:
                    break
                continue
            a = self.arcs[0]
            tt = self.w.arc_time([a], self.kappa)[0]
            rem = tt * (1 - self.pos)
            e_true = sim.sc.true_energy([a], self.kappa, cfg.payload_kg)[0]
            if rem <= budget:
                budget -= rem
                self.E -= e_true * (1 - self.pos)
                self.dist += self.w.arc_L[a] * (1 - self.pos)
                self.sum_true += e_true
                self.sum_pred += self.planner.base[self.kappa][0][a]
                self.n_arcs += 1
                self.pos = 0.0
                self.arcs.pop(0)
                self.node = int(self.w.arc_v[a])
                self.ever_moved = True
                self._localize(a)
                self.trace.append((t + dt - budget, self.node, self.E, self.phase, self.contact, self.sigma, self.kappa))
                if self.E <= self.Emin:
                    self._deplete(t + dt - budget)
                    return
                self.epoch(t + dt - budget)
            else:
                frac = budget / tt
                self.pos += frac
                self.E -= e_true * frac
                self.dist += self.w.arc_L[a] * frac
                budget = 0.0

    def _deplete(self, t):
        if self.node in self.sim.recovery:
            self.terminal = "recovered"
        else:
            self.terminal = "depleted"
        self.phase = "done"
        self.t_end = t
        self.log_decision(t, "DEPLETED")

    def _localize(self, a):
        if not self.sim.sc.gnss_denied:
            self.sigma = 2.5
            return
        self.sigma = math.sqrt(self.sigma ** 2 + (0.03 * self.w.arc_L[a]) ** 2)
        p_mm = 0.85 if self.kappa < 1 else 0.55
        if self.rng.random() < p_mm:
            self.sigma = 3.0
            self.lost = 0
        elif self.lost:
            self.lost += 1

    # ---------------------------------------------------------------- decision epoch
    def epoch(self, t):
        sim, w = self.sim, self.w
        self.comm(t)
        if self.phase not in ("outbound", "return"):
            return
        # sensed blockage on the next arc
        if self.arcs:
            a = self.arcs[0]
            if sim.sc.blocked[w.arc_e[a]] and int(w.arc_u[a]) == self.node:
                if self.learn_block(int(w.arc_e[a])):
                    self.send(t, pr.BLK(self.uid, int(w.arc_e[a])))
                    self.log_decision(t, "BLK", f"E{int(w.arc_e[a])}")
                self.arcs = []
        # arrival at a stop
        if self.phase == "outbound":
            for s in self.stops:
                if not s["delivered"] and s["node"] == self.node and self.lost == 0:
                    self._handover(t, s)
                    return
        if self.phase == "return" and self.node in sim.recovery and self.lost == 0 \
                and (self.target is None or self.node == self.target):
            self._recover(t)
            return
        # localisation guard
        if self.strategy in ("S3", "S3N", "NNP"):
            k_new = ROBOT["kappa_c"] if self.sigma > 5.0 else 1.0
            if k_new != self.kappa:
                self.log_decision(t, "CAUTIOUS" if k_new < 1 else "NOMINAL", f"sigma={self.sigma:.1f} m")
            self.kappa = k_new
            if self.lost >= 3:
                self._beacon_stop(t, "lost")
                return
        if self.lost:
            self._wander(t)
            return
        # S1: stop when contact is lost
        if self.strategy == "S1" and not self.contact and self.ever_moved:
            self.phase_after = self.phase
            self.phase = "wait"
            self.wait = 1.0
            self.log_decision(t, "WAIT")
            return
        if self.strategy == "S2":
            self._fixed_route(t)
        elif self.strategy == "S1":
            self._simple(t)
        elif self.strategy == "NNP" and self.policy_model is not None:
            self._neural(t)
        else:
            f = self.features(t) if self.sim.log_epochs else None
            self._sfc(t)
            if f is not None:
                lab = ("STOP" if self.phase == "beacon" else
                       "CONTINUE" if (self.phase == "outbound" and self.arcs) else "RETURN")
                self.sim.epoch_log.append((f, lab))
        if self.arcs:
            self._maybe_wrong_turn(t)

    def _open_stops(self):
        return [s for s in self.stops if not s["delivered"]]

    def _apply_closures(self, t, check=True):
        """Re-target to the alternative site if the recipient closed (CLS received)."""
        for s in self._open_stops():
            alt = s.pop("closed", None)
            if alt:
                old = s["site"]
                s["site"], s["node"] = alt, w_node(self.w, alt)
                self.report(t, "RTG", alt)
                self.decisions[-1] = self.decisions[-1][:3] + (f"{old}->{alt}",) + self.decisions[-1][4:]

    def _simple(self, t):
        """S1 while connected: shortest path, re-target on closures, no feasibility check."""
        self._apply_closures(t)
        stops = self._open_stops()
        if self.phase == "outbound" and stops:
            self.arcs = self.planner.route(self.node, stops[0]["node"], 1.0)
            if not self.arcs:
                self.phase = "return"
        if self.phase == "return" or not stops:
            self.phase = "return"
            self.target = self.sim.w.depot
            self.arcs = self.planner.route(self.node, self.target, 1.0)

    def _fixed_route(self, t):
        stops = self._open_stops()
        if self.phase == "outbound" and stops:
            self.arcs = self.planner.route(self.node, stops[0]["node"], 1.0)
            if not self.arcs:
                self.phase = "return"
        if self.phase == "return" or not stops:
            self.phase = "return"
            self.target = self.sim.w.depot
            self.arcs = self.planner.route(self.node, self.target, 1.0)

    def features(self, t):
        """Observation vector used by the neural policy (see neural.py)."""
        P = self.planner
        stops = self._open_stops()
        nodes = [s["node"] for s in stops]
        kap = self.kappa
        muD, varD = P.chain(self.node, nodes, kap, True) if nodes else (0.0, 0.0)
        muH, _ = P.chain(self.node, nodes, kap, False) if nodes else (0.0, 0.0)
        d, v, _, _ = P.tree_to(tuple(self.sim.recovery), kap)
        cap = self.cap
        f = np.array([self.avail() / cap, min(muD, 3 * cap) / cap, min(muH, 3 * cap) / cap,
                      min(d[self.node], 3 * cap) / cap, math.sqrt(varD) / cap if np.isfinite(varD) else 3.0,
                      self.z / 2.33, float(self.oneway), self.r_hat() - 1.0, min(self.sigma, 30) / 30.0,
                      float(self.contact), float(any("closed" in s for s in stops)), float(len(stops) > 0),
                      float(self.node in self.sim.recovery)])
        return f

    def _sfc(self, t):
        """Supervisory Feasibility Controller (Algorithm 1 of the article)."""
        P, sim = self.planner, self.sim
        kap = self.kappa
        if self.recall is not None and self.phase == "outbound":
            self.phase = "return"
            self.report(t, "RET", self.recall)
            self.target = w_node(self.w, self.recall)
        if self.phase == "outbound":
            # re-target on closure if the alternative is feasible
            for s in self._open_stops():
                alt = s.get("closed")
                if alt:
                    ok, _ = P.F_D(self.node, [w_node(self.w, alt)], kap)
                    s.pop("closed")
                    if ok:
                        old = s["site"]
                        s["site"], s["node"] = alt, w_node(self.w, alt)
                        self.report(t, "RTG", alt)
                        self.decisions[-1] = self.decisions[-1][:3] + (f"{old}->{alt}",) + self.decisions[-1][4:]
                    else:
                        s["delivered"] = True
                        s["dropped"] = True
                        self.report(t, "DRP", s["site"])
            stops = self._open_stops()
            while stops:
                nodes = [s["node"] for s in stops]
                ok, need = P.F_D(self.node, nodes, kap)
                if ok:
                    self.arcs = P.route(self.node, nodes[0], kap)
                    if self.arcs:
                        return
                    ok = False
                if self.oneway and len(stops) == 1:
                    okh, _ = P.F_H(self.node, nodes, kap)
                    if okh:
                        self.arcs = P.route(self.node, nodes[0], kap)
                        if self.arcs:
                            self.pending_hold = True
                            if not getattr(self, "_ow_logged", False):
                                self.log_decision(t, "ONEWAY", stops[0]["site"])
                                self._ow_logged = True
                            return
                if len(stops) > 1:           # multi-drop: drop the last stop and retry
                    stops[-1]["delivered"] = True
                    stops[-1]["dropped"] = True
                    self.report(t, "DRP", stops[-1]["site"])
                    stops = self._open_stops()
                    continue
                break
            # abort: decline at depot, otherwise return
            for s in self._open_stops():
                s["delivered"] = True
                s["dropped"] = True
            if not self.ever_moved and self.node == sim.w.depot:
                self.report(t, "DCL", "H0")
                self.terminal = "declined"
                self.phase = "done"
                self.t_end = t
                return
            self.phase = "return"
            self.target = None
            self.report(t, "RET", self._best_recovery_name(kap) or "H0")
        if self.phase == "return":
            self._return(t, kap)

    def _best_recovery(self, kap):
        P, sim = self.planner, self.sim
        pending = any(p.cmd.op == "RCP" for p in self.outbox)
        best, bc = None, np.inf
        if self.recall is not None:
            cands = [w_node(self.w, self.recall)]
        elif self.sim.cfg.fleet:
            if P.F_R(self.node, kap, sim.w.depot)[0]:
                return sim.w.depot
            cands = sim.recovery
        else:
            cands = sim.recovery
        for r in cands:
            ok, need = P.F_R(self.node, kap, r)
            if not ok:
                continue
            d, _, _, _ = P.tree_to(r, kap, comm_aware=pending)
            cost = d[self.node] * (0.7 if (sim.cfg.fleet and r == sim.w.depot) else 1.0)
            if cost < bc:
                best, bc = r, cost
        return best

    def _best_recovery_name(self, kap):
        b = self._best_recovery(kap)
        return None if b is None else self.w.site_name(b)

    def _return(self, t, kap):
        P = self.planner
        best = self._best_recovery(kap)
        if best is None:
            if self.pending_hold:
                return
            self._beacon_stop(t, "no feasible recovery")
            return
        self.target = best
        pending = any(p.cmd.op == "RCP" for p in self.outbox)
        self.arcs = P.route(self.node, best, kap, comm_aware=pending)
        if not self.arcs and self.node != best:
            self._beacon_stop(t, "no path")

    def _neural(self, t):
        """Neural supervisory policy proposes, the SFC predicates act as a shield
        (runtime assurance in the Simplex spirit): CONTINUE needs F_D, RETURN needs F_R."""
        P = self.planner
        kap = self.kappa
        self._apply_closures(t)
        stops = self._open_stops()
        if self.phase == "outbound" and stops:
            f = self.features(t)
            act = self.policy_model.act(f)
            nodes = [s["node"] for s in stops]
            okD, _ = P.F_D(self.node, nodes, kap)
            okR, _ = P.F_R(self.node, kap)
            shielded = act
            if not self.sim.cfg.shield:
                pass
            elif act == "CONTINUE" and not okD:
                shielded = "RETURN" if okR else "STOP"
            elif act == "RETURN" and not okR:
                shielded = "STOP"
            if shielded != act:
                self.sim.shield_events.append((t, self.name, act, shielded))
                self.log_decision(t, "SHIELD", f"{act}->{shielded}")
            self.sim.nn_actions.append((act, shielded, okD))
            if shielded == "CONTINUE":
                self.arcs = P.route(self.node, nodes[0], kap)
                if self.arcs:
                    return
            if shielded == "STOP":
                self._beacon_stop(t, "neural/shield")
                return
            for s in stops:
                s["delivered"] = True
                s["dropped"] = True
            if not self.ever_moved and self.node == self.sim.w.depot:
                self.report(t, "DCL", "H0")
                self.terminal, self.phase, self.t_end = "declined", "done", t
                return
            self.phase = "return"
            self.report(t, "RET", self._best_recovery_name(kap) or "H0")
        if self.phase == "return" or not stops:
            self.phase = "return"
            self._return(t, kap)

    def _beacon_stop(self, t, why):
        # move to the best-covered node within two hops if affordable
        w, sc = self.w, self.sim.sc
        best, bp = self.node, sc.prior_pc[self.node]
        for a in w.adj[self.node]:
            v = int(w.arc_v[a])
            for a2 in [a] + list(w.adj[v]):
                u = int(w.arc_v[a2])
                if sc.prior_pc[u] > bp + 0.15 and not self.known_arc_block[a] and not self.known_arc_block[a2]:
                    best, bp = u, sc.prior_pc[u]
        self.report(t, "STP", self.w.site_name(best) or "H0")
        self.log_decision(t, "BEACON-STOP", why)
        self.phase = "beacon"
        self.terminal = "stopped"
        self.t_end = t
        self.arcs = []

    def _wander(self, t):
        w = self.w
        opts = [a for a in w.adj[self.node] if not self.sim.sc.blocked[w.arc_e[a]]]
        self.arcs = [int(self.rng.choice(opts))] if opts else []
        self.lost += 0

    def _maybe_wrong_turn(self, t):
        if not self.sim.sc.gnss_denied:
            return
        chi = 0.3 if self.strategy in ("S3", "S3N", "NNP") else 1.0
        p = chi * min(0.6, max(0.0, (self.sigma - 6.0) / 25.0))
        if self.rng.random() < p:
            w = self.w
            opts = [a for a in w.adj[self.node] if a != self.arcs[0] and not self.sim.sc.blocked[w.arc_e[a]]]
            if opts:
                self.arcs = [int(self.rng.choice(opts))]
                self.lost = 1
                self.log_decision(t, "WRONG-TURN")

    def _handover(self, t, s):
        sim = self.sim
        if s.get("relay"):
            s["delivered"] = True
            sim.sc.deploy_relay(self.node)
            sim.relay_node = self.node
            self.log_decision(t, "MAST-UP", f"N{self.node}")
            self.phase, self.terminal, self.t_end = "held", "relay", t
            return
        s["delivered"] = True
        s["t_hand"] = t + ROBOT["dwell"]
        s["valid"] = not sim.sc.site_closed(s["site"], t)
        self.units = max(0, self.units - 1)
        sim.on_handover(self, s, t + ROBOT["dwell"])
        self.send(t + ROBOT["dwell"], pr.RCP(s["task"], int(s["site"][1:]), CLOCK0 + t + ROBOT["dwell"], self.uid,
                                             pin=s["valid"]))
        self.log_decision(t, "HANDOVER", s["site"] + ("" if s["valid"] else " (closed!)"))
        self.phase = "dwell"
        self.wait = ROBOT["dwell"]
        self.arcs = []
        if self.pending_hold and not self._open_stops():
            # one-way delivery: stay at the staffed recipient site
            okR, _ = self.planner.F_R(self.node, self.kappa)
            if not okR:
                self.phase_after = "held"
                self.terminal = "held"
                self.t_end = t
                self.log_decision(t, "HOLD", s["site"])
                self.report(t, "HLD", s["site"])
                self.phase = "held"
                return
        self.phase_after = "outbound" if self._open_stops() else "return"

    def _recover(self, t):
        self.comm(t, force_path="dock")
        self.terminal = "recovered"
        self.t_end = t
        self.log_decision(t, "RECOVERED", self.w.site_name(self.node) or "")
        if self.sim.cfg.fleet and self.node == self.sim.w.depot:
            self.phase = "idle"
            self.terminal = None
            self.stops = []
            self.ever_moved = False
            self.recall = None
            self.pending_hold = False
        else:
            self.phase = "done"


def w_node(world, name):
    return world.sites[name].node


# =========================================================================== simulation
class Sim:
    """Discrete-time (15 s) multi-agent simulation with a Meshtastic message bus."""

    def __init__(self, world: World, cfg: Config, seed: Optional[int] = None, strategy: Optional[str] = None,
                 log_epochs: bool = False):
        self.w, self.cfg = world, cfg
        self.seed = cfg.seed if seed is None else seed
        self.sc = Scenario(world, cfg, self.seed)
        self.rng = np.random.default_rng(self.seed * 31 + 3)
        self.recovery = list(world.recovery)
        self.packets: List[pr.Packet] = []
        self.downlink: List[pr.Packet] = []
        self.gw_tx: List[tuple] = []      # (t, seconds, op)
        self.cc_known = self.sc.cc_known0.copy()
        self.cc_sent_blk = set()
        self.receipts: Dict[int, float] = {}
        self.handovers: Dict[int, float] = {}
        self.shield_events = []
        self.epoch_log = []
        self.nn_actions = []
        self.log_epochs = log_epochs
        self.relay_node = None
        self.t = 0.0
        self.strategy = strategy or cfg.strategy
        self._pid = 0
        self.robots: List[Robot] = []
        for i in range(cfg.n_robots):
            soc = cfg.soc0 if not cfg.fleet else float(np.random.default_rng(self.seed + i).uniform(0.6, 0.95))
            r = Robot(self, i + 1, world.depot, soc, self.strategy)
            r.known_arc_block[np.isin(world.arc_e, np.where(self.cc_known)[0])] = True
            r.kv += 1
            self.robots.append(r)
        self.events = sorted(cfg.events, key=lambda e: e["t"])
        self.req_by_id = {r["id"]: r for r in self.sc.requests}
        for r in self.sc.requests:
            r.update(cc_known=np.inf, rob_known=np.inf, assigned=None, t_del=np.inf, t_rec=np.inf,
                     dup=0, cc_dispatched=False, valid=None)
        if cfg.relay:
            rel = Robot(self, 9, world.depot, 0.9, "S3", relay=True)
            self.robots.append(rel)
            self.cc_send(0.0, pr.RLY(9, self.plan_relay()), dst=rel.name)
            rel.comm(0.0, force_path="local")
            rel.send(0.0, pr.ACK(self._pid))
            rel.epoch(0.0)
        if not cfg.fleet:
            self._dispatch_single()

    # ---------------------------------------------------------------- packets
    def new_packet(self, t, src, dst, cmd, want_ack=True, prio="RELIABLE"):
        self._pid += 1
        p = pr.Packet(self._pid, t, src, dst, cmd, want_ack, prio, encoding=self.cfg.encoding)
        self.packets.append(p)
        return p

    def mesh_latency(self, p, hops):
        at = pr.frame_airtime(p.size, self.cfg.preset)
        lat = 0.0
        for _ in range(max(hops, 1)):
            lat += at + self.rng.uniform(0.3, 3.0) + (self.rng.exponential(8.0) if self.rng.random() < 0.15 else 0)
        return lat / 60.0, at * max(hops, 1)

    def deliver(self, p, t, path, hops):
        """Mark a packet as delivered over ``path`` at time t (+ channel latency)."""
        if path == "mesh":
            lat, air = self.mesh_latency(p, hops)
            ack = pr.lora_airtime(pr.ACK_FRAME_B, self.cfg.preset) if p.want_ack else 0.0
            p.airtime += air + ack * max(hops, 1)
            if p.want_ack and (p.dst in ("CC",) or p.dst == "^all"):
                self.gw_tx.append((t, ack, "ACK"))
            p.hops = hops
        elif path == "cell":
            lat = self.rng.uniform(0.02, 0.15)
        elif path == "dock":
            lat = 0.5
        elif path == "p2p":
            lat, air = self.mesh_latency(p, 1)
            p.airtime += air
        else:
            lat = 0.05
        p.t_recv = max(t, p.t_send) + lat
        p.path = path
        p.attempts += 1
        if p.dst in ("CC", "^all") and p.src != "CC":
            self.cc_receive(p)

    def check_contact(self, node, t):
        """Contact with the CC from a street node: cellular first, then mesh."""
        sc, cfg = self.sc, self.cfg
        s = self.w.cell_of[node]
        if (not cfg.cell_off) and (cfg.H + t / 60.0 < sc.cell_aut[s]) and sc.cell_bh[s] and self.rng.random() > 0.03:
            return True, "cell", 0
        if self.jammed(t):
            return False, None, 0
        if sc.best_margin[node] + self.rng.normal(0, RADIO["fading"]) > 0:
            return True, "mesh", int(sc.best_hops[node])
        return False, None, 0

    def jammed(self, t):
        j = self.cfg.jam_mesh
        for e in self.events:
            if e["kind"] == "jam" and t >= e["t"]:
                j = e.get("on", True)
        return j

    def regime(self, node, t):
        sc, cfg = self.sc, self.cfg
        s = self.w.cell_of[node]
        cell = (not cfg.cell_off) and (cfg.H + t / 60.0 < sc.cell_aut[s]) and sc.cell_bh[s]
        if cell:
            return 0
        if self.jammed(t):
            return 3
        pc = norm_cdf(sc.best_margin[node] / RADIO["fading"])
        return 1 if pc > 0.8 else (2 if pc > 0.1 else 3)

    def cc_send(self, t, cmd, dst="^all", want_ack=None, prio=None):
        meta = pr.CATALOGUE_BY_OP[cmd.op]
        want_ack = meta[2] if want_ack is None else want_ack
        p = self.new_packet(t, "CC", dst, cmd, want_ack, prio or meta[3])
        p.seen = set()
        self.downlink.append(p)
        return p

    def gw_budget_used(self, t, window=60.0):
        return sum(s for (tt, s, _) in self.gw_tx if t - window < tt <= t)

    def fetch_downlink(self, robot, t, path, hops):
        out = []
        budget = 36.0
        for p in self.downlink:
            if p.t_send > t or robot.name in p.seen:
                continue
            if p.dst not in ("^all", robot.name):
                continue
            if path == "mesh":
                at = pr.frame_airtime(p.size, self.cfg.preset)
                used = self.gw_budget_used(t)
                if used + at > budget and pr.PRIORITY[p.priority] < pr.PRIORITY["RELIABLE"]:
                    continue        # comms steward defers low-priority downlink
                self.gw_tx.append((t, at, p.cmd.op))
                p.airtime += at * max(hops, 1)
                lat, _ = self.mesh_latency(p, hops)
            else:
                lat = 0.05 if path in ("local", "dock") else 0.1
            p.seen.add(robot.name)
            if not np.isfinite(p.t_recv):
                p.t_recv = t + lat
                p.path = path
                p.hops = hops
            out.append(p)
        return out

    # ---------------------------------------------------------------- CC logic
    def cc_receive(self, p):
        cmd = p.cmd
        if cmd.op == "RCP":
            tid = cmd.f["task"]
            self.receipts[tid] = min(self.receipts.get(tid, np.inf), p.t_recv)
            r = self.req_by_id.get(tid)
            if r is not None:
                r["t_rec"] = min(r["t_rec"], p.t_recv)
        elif cmd.op == "BLK" and cmd.f["unit"] != 0:
            e = cmd.f["edge"]
            if not self.cc_known[e]:
                self.cc_known[e] = True
                if self.cfg.n_robots > 1 or self.cfg.fleet:
                    self.cc_send(p.t_recv, pr.BLK(0, e))
                    self.cc_sent_blk.add(e)
        elif cmd.op == "LSE":
            r = self.req_by_id.get(cmd.f["task"])
            if r is not None and r["assigned"] is None:
                r["assigned"] = cmd.f["unit"]
        elif cmd.op == "REQ":
            r = self.req_by_id.get(cmd.f["task"])
            if r is not None:
                r["cc_known"] = min(r["cc_known"], p.t_recv)

    def _dispatch_single(self):
        w = self.w
        tasks = self.cfg.tasks
        # nominal travel time on the true graph -> deadline
        tw = w.arc_time(np.arange(len(w.arc_u)))
        tw = np.where(self.sc.blocked[w.arc_e], np.inf, tw)
        for i, rob in enumerate(self.robots):
            if rob.is_relay:
                continue
            prev = w.depot
            tnom = 0.0
            for j, task in enumerate(tasks if self.cfg.n_robots == 1 else [tasks[i % len(tasks)]]):
                node = w.sites[task["site"]].node
                d, _, _, _ = dijkstra(w, tw, node, reverse=True)
                tnom += d[prev] + (ROBOT["dwell"] if j else 0)
                prev = node
                dl = task.get("deadline", 1.5 * tnom + 10.0)
                tid = task.get("task", 10 * rob.uid + j + 1)
                cmd = pr.TSK(tid, int(task["site"][1:]), int(task.get("alt", "R5")[1:]),
                             CLOCK0 + dl, self.cfg.z, self.cfg.oneway)
                self.cc_send(0.0, cmd, dst=rob.name)
            rob.comm(0.0, force_path="local")
            rob.send(0.0, pr.ACK(self._pid))
            rob.phase = "outbound"
            rob.epoch(0.0)

    def plan_relay(self):
        """Twin planner: park the relay where it adds most coverage near recipient sites."""
        w, sc = self.w, self.sc
        base = sc.best_margin
        best, bg = w.depot, -1
        focus = [w.sites[t["site"]].node for t in self.cfg.tasks] if not self.cfg.fleet else []
        hop = sc.fab.infra_graph(sc.alive)
        anchors = [(n, h) for i, (_, n, h) in enumerate(sc.fab.infra) if sc.alive[i] and hop[i] < self.cfg.hop_limit]
        for c in range(0, w.n, 2):
            # the mast must reach a connected infrastructure node over a rooftop link
            if not any(link_margin(np.linalg.norm(w.xy[n] - w.xy[c]), h, RADIO["h_mast"]) + w.clutter[c] * 0.5 > 3.0
                       for n, h in anchors):
                continue
            m = sc.fab.margin_from(c, RADIO["h_mast"])
            g = np.sum(norm_cdf(np.maximum(base, m) / 4) - norm_cdf(base / 4))
            g += 4 * sum(norm_cdf(np.maximum(base[n], m[n]) / 4) - norm_cdf(base[n] / 4) for n in w.recipients)
            # mission-aware: the sites of the current task contracts matter most
            g += 25 * sum(norm_cdf(np.maximum(base[n], m[n]) / 4) - norm_cdf(base[n] / 4) for n in focus)
            if g > bg:
                best, bg = c, g
        return int(best)

    def on_handover(self, robot, stop, t):
        tid = stop["task"]
        self.handovers[tid] = t
        r = self.req_by_id.get(tid)
        if r is not None:
            if r["t_del"] < np.inf:
                r["dup"] += 1
            else:
                r["t_del"] = t
                r["valid"] = stop["valid"]
        # dual-path receipt via the recipient node
        if (self.cfg.dual_receipt or (self.cfg.fleet and self.cfg.policy == "A")) and stop["site"].startswith("R"):
            if self.sc.site_node_ok(stop["site"]) and not self.jammed(t):
                p = self.new_packet(t, "N" + stop["site"], "CC",
                                    pr.RCP(tid, int(stop["site"][1:]), CLOCK0 + t, robot.uid), True, "RELIABLE")
                hops = int(self.sc.best_hops[self.w.sites[stop["site"]].node])
                if self.sc.best_margin[self.w.sites[stop["site"]].node] + 10 > 0:
                    self.deliver(p, t, "mesh", max(hops, 1))

    def scripted(self, t, dt):
        for e in self.events:
            if t - dt < e["t"] <= t or (e["t"] == 0 and t == 0):
                if e.get("done"):
                    continue
                e["done"] = True
                k = e["kind"]
                if k == "close":
                    self.sc.closures[e["site"]] = (e["t"], e["alt"])
                elif k == "cmd":
                    self.cc_send(t, e["cmd"], dst=e.get("dst", "^all"))
                elif k == "relay":
                    self.cc_send(t, pr.RLY(9, e["node"]), dst="U9")

    def cc_step(self, t, dt):
        sc = self.sc
        # CC learns about blockages and closures; broadcasts short news
        newly = (sc.reveal <= t) & ~self.cc_known
        for e in np.where(newly)[0]:
            self.cc_known[e] = True
            self.cc_send(t, pr.BLK(0, int(e)))
        for site in [f"R{i}" for i in range(1, 9)]:
            if sc.site_closed(site, t) and site not in getattr(self, "_cls_sent", set()):
                self._cls_sent = getattr(self, "_cls_sent", set()) | {site}
                alt = sc.closures.get(site, (None, None))[1] or self.nearest_open(site, t)
                self.cc_send(t, pr.CLS(int(site[1:]), int(alt[1:])))

    def nearest_open(self, site, t):
        w = self.w
        n0 = w.sites[site].node
        best, bd = None, np.inf
        for k, s in w.sites.items():
            if s.kind == "recipient" and k != site and not self.sc.site_closed(k, t):
                d = np.linalg.norm(w.xy[s.node] - w.xy[n0])
                if d < bd:
                    best, bd = k, d
        return best or "R1"

    # ---------------------------------------------------------------- run
    def run(self, dt=0.25):
        cfg = self.cfg
        horizon = cfg.horizon if not cfg.fleet else cfg.shift + 180.0
        steps = int(horizon / dt)
        from .fleet import FleetLogic
        fl = FleetLogic(self) if cfg.fleet else None
        for i in range(steps + 1):
            t = i * dt
            self.t = t
            self.scripted(t, dt)
            self.cc_step(t, dt)
            if fl:
                fl.step(t, dt)
            for r in self.robots:
                r.step(t, dt)
            if not cfg.fleet and all(r.phase in ("done", "beacon", "held") for r in self.robots if not r.is_relay) \
                    and all(not r.outbox for r in self.robots):
                break
        self.t_final = t
        return self

    # ---------------------------------------------------------------- metrics
    def mission_metrics(self):
        out = []
        for r in self.robots:
            if r.is_relay:
                continue
            term = r.terminal or ("stuck" if r.phase == "wait" else "travelling")
            if r.phase == "beacon":
                term = "stopped"
            st = [s for s in r.stops]
            valid = [s for s in st if s.get("valid")]
            on_time = [s for s in valid if s["t_hand"] <= s["deadline"]]
            lats = [self.receipts.get(s["task"], np.inf) - s["t_hand"] for s in st if "t_hand" in s]
            out.append(dict(robot=r.name, strategy=r.strategy, terminal=term,
                            delivered=len([s for s in st if "t_hand" in s]), valid=len(valid),
                            on_time=len(on_time), n_tasks=len(st),
                            soc_end=r.soc(), stranded=term in ("depleted", "stuck", "travelling"),
                            recovered=term == "recovered", dist_km=r.dist / 1000.0,
                            lat=float(np.min(lats)) if lats else np.nan, t_end=getattr(r, "t_end", self.t_final),
                            snow=self.sc.snow, temp=self.sc.temp, gnss_denied=self.sc.gnss_denied,
                            n_packets=len([p for p in self.packets if p.src == r.name]),
                            airtime_s=sum(p.airtime for p in self.packets if p.src == r.name)))
        return out

    def packet_table(self):
        rows = []
        for p in self.packets:
            rows.append(dict(id=p.pid, t_send=round(p.t_send, 2),
                             t_recv=round(p.t_recv, 2) if np.isfinite(p.t_recv) else None,
                             src=p.src, dst=p.dst, text=p.cmd.text(), bytes=p.size, path=p.path or "-",
                             hops=p.hops, airtime_ms=round(p.airtime * 1000, 1)))
        return rows


def run(world, cfg: Config, strategy=None, seed=None):
    return Sim(world, cfg, seed=seed, strategy=strategy).run()


def run_paired(world, cfg: Config, strategies=STRATS, seed=None):
    """Run the same scenario (common random numbers) under several strategies."""
    out = {}
    for s in strategies:
        out[s] = Sim(world, cfg, seed=seed, strategy=s).run()
    return out
