"""
Synthetic riverside town, energy model, radio model and graph search.

Everything is synthetic. The layout (reservoir to the north-west, a riverside town on a
250 m street lattice, recipient and recovery sites) is only *inspired by* the planning
grid of Verkhnodniprovsk; it is not a map of the real town.

Equations refer to the companion article (Prokopovych-Tkachenko, RTC blackout study):
  Eq. 3  arc energy           Eq. 4  online calibration      Eq. 5  chance-constrained need
  Eq. 11 link margin (Okumura-Hata at 868 MHz)
"""
from __future__ import annotations

import heapq
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import numpy as np

G = 9.81
CLASSES = ("arterial", "local", "unpaved")
C_ROLL = np.array([0.018, 0.025, 0.045])          # rolling-resistance coefficient
V_NOM = np.array([1.8, 1.6, 1.2])                 # m/s

ROBOT = dict(
    mass=140.0, cap=900.0, eta_d=0.72, eta_r=0.25,
    p_move=70.0, p_idle=38.0, p_beacon=15.0,
    cutoff=0.08, reserve=0.03, w0=20.0, sigma_e=0.10, z=1.28,
    snow_hat=1.35, lam=0.6, kappa_c=0.6, dwell=3.0,
)

RADIO = dict(eirp=15.0, gain_loss=4.0, excess=12.0, thr=-118.0, shadow=6.0, fading=4.0,
             h_robot=0.8, h_gw=15.0, h_rep=25.0, h_fac=10.0, h_mast=10.0, f_mhz=868.0)


# --------------------------------------------------------------------------- radio
def hata_loss(d_km, hb, hm, f=868.0):
    """Okumura-Hata urban path loss (dB), small/medium city correction."""
    d_km = np.maximum(np.asarray(d_km, float), 0.02)
    lf = math.log10(f)
    a_hm = (1.1 * lf - 0.7) * hm - (1.56 * lf - 0.8)
    hb = max(hb, 1.0)
    return 69.55 + 26.16 * lf - 13.82 * math.log10(hb) - a_hm + (44.9 - 6.55 * math.log10(hb)) * np.log10(d_km)


def link_margin(d_m, h_tx, h_rx=RADIO["h_robot"]):
    """Deterministic link margin (dB) before clutter, shadowing and fading (Eq. 11)."""
    hb, hm = max(h_tx, h_rx), min(min(h_tx, h_rx), 10.0)
    L = hata_loss(np.asarray(d_m) / 1000.0, hb, hm)
    return RADIO["eirp"] - L + RADIO["gain_loss"] - RADIO["excess"] * (hm < 2) - RADIO["thr"]


def norm_cdf(x):
    return 0.5 * (1.0 + np.vectorize(math.erf)(np.asarray(x, float) / math.sqrt(2.0)))


# --------------------------------------------------------------------------- town
@dataclass
class Site:
    name: str
    node: int
    kind: str          # depot / recipient / recovery / cell / repeater


class World:
    """Street graph of a synthetic riverside town (~6 x 4 km)."""

    def __init__(self, seed: int = 7, nx: int = 29, ny: int = 19, step: float = 250.0):
        rng = np.random.default_rng(seed)
        self.seed = seed
        xs, ys = np.meshgrid(np.arange(nx) * step, np.arange(ny) * step)
        xy = np.c_[xs.ravel(), ys.ravel()].astype(float)
        X, Y = nx * step, ny * step
        # reservoir in the north-west corner: shoreline y = a + b * x
        self.shore_ab = (0.55 * Y, Y / X)
        a_, b_ = self.shore_ab
        shore = a_ + b_ * xy[:, 0]
        keep = xy[:, 1] < shore - 120
        idx = -np.ones(len(xy), int)
        idx[keep] = np.arange(keep.sum())
        self.xy = xy[keep] + rng.normal(0, 28, (keep.sum(), 2))
        self.n = len(self.xy)
        self.size = (X, Y)
        gi = np.c_[np.tile(np.arange(nx), ny), np.repeat(np.arange(ny), nx)][keep]
        # terrain: rises away from the shore, two ravines
        dshore = (shore[keep] - xy[keep, 1]) / math.sqrt(1 + b_ ** 2)
        z = 50.0 * (1 - np.exp(-dshore / 1800.0))
        for cx, w in ((2300.0, 160.0), (4300.0, 200.0)):
            z -= 14.0 * np.exp(-((self.xy[:, 0] - cx) ** 2) / (2 * w ** 2)) * (dshore > 300)
        self.z = z + rng.normal(0, 0.8, self.n)
        # edges on the lattice (4-neighbour) + few diagonals
        lut = {(int(a), int(b)): i for i, (a, b) in enumerate(gi)}
        edges, cls = [], []
        for i, (a, b) in enumerate(gi):
            for da, db in ((1, 0), (0, 1)):
                j = lut.get((a + da, b + db))
                if j is None or rng.random() < 0.10:
                    continue
                arterial = (b % 4 == 0 and db == 0) or (a % 5 == 0 and da == 0)
                outskirts = b >= ny - 3 or a <= 1 or a >= nx - 2
                c = 0 if arterial else (2 if (outskirts and rng.random() < 0.7) or rng.random() < 0.12 else 1)
                edges.append((i, j))
                cls.append(c)
            j = lut.get((a + 1, b + 1))
            if j is not None and rng.random() < 0.06:
                edges.append((i, j))
                cls.append(1)
        E = np.array(edges)
        self.edges = E
        self.ecls = np.array(cls)
        self.elen = np.linalg.norm(self.xy[E[:, 0]] - self.xy[E[:, 1]], axis=1) * rng.uniform(1.05, 1.25, len(E))
        self._keep_largest_component()
        # directed arcs (u -> v) for both directions
        E = self.edges
        self.arc_u = np.r_[E[:, 0], E[:, 1]]
        self.arc_v = np.r_[E[:, 1], E[:, 0]]
        self.arc_e = np.r_[np.arange(len(E)), np.arange(len(E))]
        self.arc_L = self.elen[self.arc_e]
        self.arc_dz = self.z[self.arc_v] - self.z[self.arc_u]
        self.arc_cls = self.ecls[self.arc_e]
        self.adj: List[List[int]] = [[] for _ in range(self.n)]
        for a, u in enumerate(self.arc_u):
            self.adj[u].append(a)
        self.arc_index = {(int(u), int(v)): a for a, (u, v) in enumerate(zip(self.arc_u, self.arc_v))}
        self.dshore = (a_ + b_ * self.xy[:, 0] - self.xy[:, 1]) / math.sqrt(1 + b_ ** 2)
        self._place_sites(rng)
        self.clutter = self._clutter(rng)

    # ------------------------------------------------------------------ helpers
    def _keep_largest_component(self):
        parent = list(range(self.n))

        def find(a):
            while parent[a] != a:
                parent[a] = parent[parent[a]]
                a = parent[a]
            return a
        for u, v in self.edges:
            parent[find(u)] = find(v)
        roots = np.array([find(i) for i in range(self.n)])
        big = np.bincount(roots).argmax()
        keep = roots == big
        remap = -np.ones(self.n, int)
        remap[keep] = np.arange(keep.sum())
        m = keep[self.edges[:, 0]] & keep[self.edges[:, 1]]
        self.edges = remap[self.edges[m]]
        self.ecls, self.elen = self.ecls[m], self.elen[m]
        self.xy, self.z = self.xy[keep], self.z[keep]
        self.n = int(keep.sum())

    def nearest(self, x, y) -> int:
        return int(np.argmin(np.hypot(self.xy[:, 0] - x, self.xy[:, 1] - y)))

    def _place_sites(self, rng):
        X, Y = self.size
        P = lambda fx, fy: self.nearest(fx * X, fy * Y)
        self.depot = P(0.80, 0.18)
        self.sites: Dict[str, Site] = {"H0": Site("H0", self.depot, "depot")}
        rec = [(0.30, 0.20), (0.55, 0.45), (0.18, 0.48), (0.92, 0.55), (0.62, 0.10), (0.42, 0.62),
               (0.75, 0.80), (0.08, 0.15)]
        for i, (fx, fy) in enumerate(rec, 1):
            self.sites[f"R{i}"] = Site(f"R{i}", P(fx, fy), "recipient")
        for i, (fx, fy) in enumerate([(0.35, 0.40), (0.60, 0.70), (0.12, 0.30)], 1):
            self.sites[f"P{i}"] = Site(f"P{i}", P(fx, fy), "recovery")
        self.recipients = [s.node for k, s in self.sites.items() if s.kind == "recipient"]
        self.recovery = [self.depot] + [s.node for s in self.sites.values() if s.kind == "recovery"]
        self.recovery_names = ["H0", "P1", "P2", "P3"]
        # cellular sites
        cells = [(0.15, 0.25), (0.45, 0.25), (0.75, 0.25), (0.30, 0.55), (0.60, 0.55), (0.90, 0.45),
                 (0.50, 0.80), (0.85, 0.80), (0.10, 0.60)]
        self.cell_xy = np.array([[fx * X, fy * Y] for fx, fy in cells])
        self.cell_of = np.argmin(np.linalg.norm(self.xy[:, None, :] - self.cell_xy[None], axis=2), axis=1)
        # repeater candidates: high, inland nodes (greedy order computed in radio)
        cand = np.argsort(-self.z)[: self.n // 3][::4]
        self.rep_candidates = cand

    def _clutter(self, rng):
        """Spatially smooth clutter field (dB) - buildings, trees, terrain shading."""
        K = 30
        c = rng.normal(0, 1, K)
        cx = rng.uniform(0, self.size[0], K)
        cy = rng.uniform(0, self.size[1], K)
        f = np.zeros(self.n)
        for k in range(K):
            f += c[k] * np.exp(-((self.xy[:, 0] - cx[k]) ** 2 + (self.xy[:, 1] - cy[k]) ** 2) / (2 * 450.0 ** 2))
        return 5.0 * f / (f.std() + 1e-9)

    def site_name(self, node: int) -> Optional[str]:
        for k, s in self.sites.items():
            if s.node == node:
                return k
        return None

    def recipient_index(self, name: str) -> int:
        return int(name[1:])

    # ------------------------------------------------------------------ energy (Eq. 3)
    def arc_energy(self, arcs, snow, kappa=1.0, mass=None, temp=-5.0, p_aux=None):
        """Energy (Wh) per arc for a snow factor and speed factor kappa (Eq. 3)."""
        arcs = np.asarray(arcs)
        m = ROBOT["mass"] if mass is None else mass
        p_aux = ROBOT["p_move"] if p_aux is None else p_aux
        L, dz, c = self.arc_L[arcs], self.arc_dz[arcs], C_ROLL[self.arc_cls[arcs]]
        snow = np.broadcast_to(np.asarray(snow, float), L.shape) if np.ndim(snow) else snow
        W = m * G * (c * snow * L + dz)
        W = np.where(W >= 0, W / ROBOT["eta_d"], ROBOT["eta_r"] * W)
        v = V_NOM[self.arc_cls[arcs]] * kappa
        return (W + p_aux * L / v) / 3600.0

    def arc_time(self, arcs, kappa=1.0):
        arcs = np.asarray(arcs, dtype=int)
        return self.arc_L[arcs] / (V_NOM[self.arc_cls[arcs]] * kappa) / 60.0   # minutes

    @staticmethod
    def capacity(temp):
        return ROBOT["cap"] * (1 - 0.015 * max(0.0, -temp))


# --------------------------------------------------------------------------- search
def dijkstra(world: World, w: np.ndarray, src, reverse: bool = False, w2: Optional[np.ndarray] = None):
    """Shortest paths on arc weights ``w`` (inf = blocked) from one or several sources.

    reverse=True computes distances *to* ``src`` (one target, many origins); then
    ``via[x]`` is the next arc to take from x. ``var`` accumulates ``w2`` along the
    chosen path (used for the chance constraint) and ``root`` tells which source won."""
    n = world.n
    dist = np.full(n, np.inf)
    var = np.zeros(n)
    via = -np.ones(n, int)
    root = -np.ones(n, int)
    srcs = [src] if np.isscalar(src) else list(src)
    pq = []
    for s in srcs:
        dist[s] = 0.0
        root[s] = s
        pq.append((0.0, int(s)))
    heapq.heapify(pq)
    if reverse:
        inc = getattr(world, "_inc", None)
        if inc is None:
            inc = [[] for _ in range(n)]
            for a, v in enumerate(world.arc_v):
                inc[v].append(a)
            world._inc = inc
    au, av = world.arc_u, world.arc_v
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for a in (inc[u] if reverse else world.adj[u]):
            wa = w[a]
            if wa == np.inf:
                continue
            v = au[a] if reverse else av[a]
            nd = d + wa
            if nd < dist[v] - 1e-12:
                dist[v] = nd
                var[v] = var[u] + (0.0 if w2 is None else w2[a])
                via[v] = a
                root[v] = root[u]
                heapq.heappush(pq, (nd, int(v)))
    return dist, var, via, root


def path_arcs(world: World, via: np.ndarray, src: int, dst: int, reverse: bool = False) -> List[int]:
    """Arc list from src to dst. For reverse trees ``via[x]`` is the next arc from x."""
    out = []
    if reverse:            # tree rooted at dst
        x = src
        while x != dst:
            a = via[x]
            if a < 0:
                return []
            out.append(int(a))
            x = int(world.arc_v[a])
        return out
    x = dst
    while x != src:
        a = via[x]
        if a < 0:
            return []
        out.append(int(a))
        x = int(world.arc_u[a])
    return out[::-1]


# --------------------------------------------------------------------------- radio fabric
class RadioFabric:
    """Static radio geometry: which street nodes can hear which infrastructure node.

    Infrastructure: CC gateway at the depot, k solar repeaters (greedy placement),
    facility nodes at recipient sites and recovery points, optional relay-UGV mast."""

    def __init__(self, world: World, k: int = 4, seed: int = 0):
        self.w = world
        self.k = k
        self.clutter_gain = 1.0
        rng = np.random.default_rng(seed + 101)
        self.shadow_cache: Dict[int, np.ndarray] = {}
        infra = [("GW", world.depot, RADIO["h_gw"])]
        for name, s in world.sites.items():
            if s.kind in ("recipient", "recovery"):
                infra.append((f"F{name}", s.node, RADIO["h_fac"]))
        self.base_infra = infra
        self.repeaters = self.greedy_repeaters(k)
        self.infra = infra + [(f"RP{i + 1}", n, RADIO["h_rep"]) for i, n in enumerate(self.repeaters)]

    def margin_from(self, node: int, h: float) -> np.ndarray:
        d = np.linalg.norm(self.w.xy - self.w.xy[node], axis=1)
        return link_margin(d, h) + self.w.clutter * self.clutter_gain

    def greedy_repeaters(self, k: int) -> List[int]:
        base = np.max([self.margin_from(n, h) for _, n, h in self.base_infra], axis=0)
        chosen = []
        cur = base.copy()
        for _ in range(k):
            best, gain = None, -1
            for c in self.w.rep_candidates:
                if c in chosen:
                    continue
                m = self.margin_from(c, RADIO["h_rep"])
                g = np.sum(norm_cdf(np.maximum(cur, m) / RADIO["fading"]) - norm_cdf(cur / RADIO["fading"]))
                if g > gain:
                    best, gain = int(c), g
            chosen.append(best)
            cur = np.maximum(cur, self.margin_from(best, RADIO["h_rep"]))
        return chosen

    def infra_graph(self, alive: np.ndarray):
        """Hop count of each infrastructure node to the gateway over rooftop links."""
        m = len(self.infra)
        xy = self.w.xy[[n for _, n, _ in self.infra]]
        hop = np.full(m, np.inf)
        hop[0] = 0 if alive[0] else np.inf
        frontier = [0] if alive[0] else []
        while frontier:
            nxt = []
            for i in frontier:
                for j in range(m):
                    if alive[j] and not np.isfinite(hop[j]):
                        d = np.linalg.norm(xy[i] - xy[j])
                        mm = link_margin(d, self.infra[i][2], self.infra[j][2])
                        if mm > 6.0:
                            hop[j] = hop[i] + 1
                            nxt.append(j)
            frontier = nxt
        return hop

    def node_margins(self, alive: np.ndarray, extra: Optional[List[Tuple[int, float]]] = None):
        """Matrix (infra x street nodes) of mean margins, alive nodes only."""
        rows = []
        for i, (_, n, h) in enumerate(self.infra):
            rows.append(self.margin_from(n, h) if alive[i] else np.full(self.w.n, -99.0))
        for n, h in (extra or []):
            rows.append(self.margin_from(n, h))
        return np.array(rows)

    def contact_probability(self, alive=None, hop_limit=3, extra=None):
        """P(mesh contact with the CC) at every street node (fast fading only)."""
        if alive is None:
            alive = np.ones(len(self.infra), bool)
        hop = self.infra_graph(alive)
        M = self.node_margins(alive, extra)
        hop_all = np.r_[hop, np.ones(len(extra or [])) * 1]
        ok = hop_all <= hop_limit
        M = np.where(ok[:, None], M, -99.0)
        return 1 - np.prod(1 - norm_cdf(M / RADIO["fading"]), axis=0)
