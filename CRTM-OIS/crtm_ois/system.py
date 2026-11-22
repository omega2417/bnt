"""Structural model of the CRTM-OIS system: blocks B0-B8, control unit CU, buses.

Each block is a pure function that receives and returns the record of a bus
(Table 3 of the manuscript). `assess` is the control unit together with the
report-and-trace register B8: it calls the stages in order, stops the chain on
a failure code E1-E4 and returns the result record with the full bus trace.
"""
from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import numpy as np

from . import levels as lv
from .core import aggregate_action, normalize
from .model import Configuration

SOFTWARE_VERSION = "CRTM-OIS 1.0"

FAILURE_CODES = {
    "E1": "inadmissible rules (weights off the simplex, theta outside (0,1], goal without actions)",
    "E2": "non-monotone anchors or non-numeric value",
    "E3": "core metric missing",
    "E4": "zero completeness of a basic action",
}

# Bus name -> (source block, destination blocks, description)
BUSES = {
    "X": ("B0", "B1", "physical values x and missing-value flags"),
    "XiWK": ("B1", "B2", "class tables, polarity, weights, core set, thresholds"),
    "O": ("B2", "B3,B4", "observation mask and completeness"),
    "M": ("B3", "B4,B7", "normalized scores and their levels"),
    "A": ("B4", "B5", "action records S, c, mu, L, U, flags"),
    "G": ("B5", "B6", "goal scores (mean, min) and enclosures"),
    "R": ("B6", "B8", "integral index, level, weakest link, enclosure, flags"),
    "P": ("B7", "B8", "robustness statistics and level shares"),
    "C": ("CU", "B0-B8", "control signals, status, configuration version"),
}

BLOCKS = {
    "B0": "Input interface", "B1": "Scenario and configuration",
    "B2": "Verification and completeness", "B3": "Normalizer",
    "B4": "Action aggregator", "B5": "Goal roll-up",
    "B6": "Integral index and classifier", "B7": "Robustness analyzer",
    "B8": "Report and trace register", "CU": "Control unit",
}


class AssessmentError(Exception):
    """Failure code raised by block B2 and propagated by the control unit."""

    def __init__(self, code: str, detail: str):
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {FAILURE_CODES[code]} -- {detail}")


@dataclass
class Trace:
    """Bus-trace register (B8)."""
    config_version: str
    seed: int
    records: list = field(default_factory=list)

    def write(self, bus: str, block: str, payload: Any, status: str = "OK") -> None:
        self.records.append({"bus": bus, "block": block, "status": status, "payload": payload})

    def bus(self, name: str):
        for r in reversed(self.records):
            if r["bus"] == name:
                return r["payload"]
        raise KeyError(name)


# --------------------------------------------------------------------------- B0
def stage0_input(raw: dict) -> dict:
    """B0: accept measurements (numbers, strings, None, 'n.r.') -> bus X."""
    X = {}
    for k, v in raw.items():
        if v is None or (isinstance(v, str) and v.strip().lower() in ("", "n.r.", "nr", "na", "none")):
            X[k] = None
        elif isinstance(v, str):
            try:
                X[k] = float(v.replace(",", "."))
            except ValueError as e:
                raise AssessmentError("E2", f"value {v!r} of {k} is not numeric") from e
        else:
            X[k] = float(v)
    return X


# --------------------------------------------------------------------------- B1
def stage1_form(cfg: Configuration, X: dict) -> dict:
    """B1 / Stage 1: projection of the hierarchy, metric tuples, anchors, policy."""
    tree = {g: [a.code for a in cfg.actions_of(g)] for g in cfg.goals}
    metrics = {}
    for a in cfg.actions:
        for m in a.metrics:
            metrics[(a.code, m.code)] = {
                "xi": m.xi, "eta": m.anchors, "sigma": m.sigma, "w": m.weight,
                "core": m.core, "x": X.get((a.code, m.code))}
    return {"tree": tree, "metrics": metrics, "theta": cfg.theta, "operator": cfg.operator,
            "goal_weights": dict(cfg.goal_weights), "version": cfg.version}


# --------------------------------------------------------------------------- B2
def stage2_verify(cfg: Configuration, conf: dict) -> dict:
    """B2 / Stage 2: four checks (E1-E4), observation mask O and completeness kappa."""
    if not (0.0 < cfg.theta <= 1.0):
        raise AssessmentError("E1", f"theta = {cfg.theta}")
    gw = cfg.goal_weights
    if any(gw.get(g, 0) < 0 for g in cfg.goals) or not math.isclose(sum(gw[g] for g in cfg.goals), 1.0, abs_tol=1e-9):
        raise AssessmentError("E1", "goal weights are not on the simplex")
    for g, acts in conf["tree"].items():
        if not acts:
            raise AssessmentError("E1", f"goal {g} has no actions")
    O, kappa = {}, {}
    for a in cfg.actions:
        ws = np.array([m.weight for m in a.metrics])
        if np.any(ws < 0) or not math.isclose(ws.sum(), 1.0, abs_tol=1e-9):
            raise AssessmentError("E1", f"weights of {a.code} are not on the simplex")
        mask = []
        for m in a.metrics:
            eta = m.anchors
            if not (eta[0] <= eta[1] < eta[2] < eta[3] < eta[4] <= eta[5]):
                raise AssessmentError("E2", f"anchors of {a.code}.{m.code} are not monotone: {eta}")
            x = conf["metrics"][(a.code, m.code)]["x"]
            if x is not None and not np.isfinite(x):
                raise AssessmentError("E2", f"value of {a.code}.{m.code} is not finite")
            if m.core and x is None:
                raise AssessmentError("E3", f"core metric {a.code}.{m.code} is missing")
            mask.append(x is not None)
        k = float(ws[np.array(mask)].sum())
        if k <= 0:
            raise AssessmentError("E4", f"no observed metric in {a.code}")
        O[a.code], kappa[a.code] = mask, k
    return {"O": O, "kappa": kappa}


# --------------------------------------------------------------------------- B3
def stage3_normalize(cfg: Configuration, conf: dict, obs: dict) -> dict:
    """B3 / Stage 3: anchored normalization (4) and metric levels (1)."""
    M, Lam = {}, {}
    for a in cfg.actions:
        for m, seen in zip(a.metrics, obs["O"][a.code]):
            key = (a.code, m.code)
            if seen:
                s = normalize(conf["metrics"][key]["x"], m.anchors, m.sigma, cfg.breakpoints)
                M[key], Lam[key] = s, lv.level(s, cfg.breakpoints)
            else:
                M[key], Lam[key] = None, None
    return {"M": M, "Lambda": Lam}


# --------------------------------------------------------------------------- B4
def stage4_aggregate(cfg: Configuration, obs: dict, norm: dict) -> dict:
    """B4 / Stage 4: renormalized mean, cap, capped score, enclosure (5)-(7)."""
    A = {}
    for a in cfg.actions:
        m = np.array([norm["M"][(a.code, x.code)] if norm["M"][(a.code, x.code)] is not None else 0.0
                      for x in a.metrics])
        rec = aggregate_action(m, [x.weight for x in a.metrics], obs["O"][a.code],
                               [x.core for x in a.metrics], cfg.theta, cfg.operator)
        rec["level"] = lv.level(rec["mu"], cfg.breakpoints)
        rec["goal"] = a.goal
        A[a.code] = rec
    return A


# --------------------------------------------------------------------------- B5
def stage5_rollup(cfg: Configuration, A: dict) -> dict:
    """B5 / Stage 5: mean and minimum roll-up to goals (8) -> profile pi_theta."""
    G = {}
    for g in cfg.goals:
        acts = [a.code for a in cfg.actions_of(g)]
        mus = np.array([A[c]["mu"] for c in acts])
        G[g] = {"mean": float(mus.mean()), "min": float(mus.min()),
                "L": float(np.mean([A[c]["L"] for c in acts])),
                "U": float(np.mean([A[c]["U"] for c in acts])),
                "weakest_action": acts[int(np.argmin(mus))], "actions": acts}
    return G


# --------------------------------------------------------------------------- B6
def stage6_integral(cfg: Configuration, A: dict, G: dict) -> dict:
    """B6 / Stage 6: integral index R, weakest link R_min (9), enclosure (10), flags."""
    w = cfg.goal_weights
    R = float(sum(w[g] * G[g]["mean"] for g in cfg.goals))
    RL = float(sum(w[g] * G[g]["L"] for g in cfg.goals))
    RU = float(sum(w[g] * G[g]["U"] for g in cfg.goals))
    Rmin = float(min(G[g]["min"] for g in cfg.goals))
    weakest_goal = min(cfg.goals, key=lambda g: G[g]["mean"])
    weakest_action = min(A, key=lambda c: A[c]["mu"])
    lam = lv.level(R, cfg.breakpoints)
    return {"R": R, "level": lam, "level_code": lv.code(lam), "level_name": lv.name(lam),
            "R_min": Rmin, "level_min": lv.level(Rmin, cfg.breakpoints),
            "R_L": RL, "R_U": RU,
            "stable_missing": lv.level(RL, cfg.breakpoints) == lv.level(RU, cfg.breakpoints),
            "weakest_goal": weakest_goal, "weakest_action": weakest_action,
            "vetoed": [c for c in A if A[c]["veto"]],
            "capped": [c for c in A if A[c]["cap_active"]],
            "incomplete": [c for c in A if A[c]["kappa"] < 1.0 - 1e-9]}


# --------------------------------------------------------------------------- B7
def stage7_robust(cfg: Configuration, obs: dict, norm: dict, n: Optional[int] = None,
                  rho: Optional[float] = None, seed: Optional[int] = None) -> dict:
    """B7 / Stage 7: Dirichlet weight model, closed-form moments (11), Monte Carlo shares."""
    n = cfg.n_samples if n is None else n
    rho = cfg.rho if rho is None else rho
    seed = cfg.seed if seed is None else seed
    rng = np.random.default_rng(seed)
    mu_samples, moments = {}, {}
    for a in cfg.actions:
        mask = np.array(obs["O"][a.code])
        m = np.array([norm["M"][(a.code, x.code)] or 0.0 for x in a.metrics])
        core = np.array([x.core for x in a.metrics]) & mask
        W = rng.dirichlet(np.full(a.q, rho), size=n)
        Wo = W[:, mask]
        S = (Wo @ m[mask]) / Wo.sum(axis=1)
        if cfg.operator == "capped":
            c = np.min(m[core] / cfg.theta) if core.any() else np.inf
            mu = np.minimum(S, c)
        elif cfg.operator == "hard":
            mu = S * (0.0 if (core.any() and np.any(m[core] <= 0)) else 1.0)
        else:
            mu = S
        mu_samples[a.code] = mu
        mo = m[mask]
        moments[a.code] = {"E_S": float(mo.mean()),
                           "Var_S": float(mo.var() / (mo.size * rho + 1.0))}
    R = np.zeros(n)
    for g in cfg.goals:
        R += cfg.goal_weights[g] * np.mean([mu_samples[a.code] for a in cfg.actions_of(g)], axis=0)
    lev = lv.levels(R, cfg.breakpoints)
    shares = {lv.code(r): float(np.mean(lev == r)) for r in range(1, 6)}
    return {"mean": float(R.mean()), "sd": float(R.std()),
            "q05": float(np.quantile(R, 0.05)), "q95": float(np.quantile(R, 0.95)),
            "shares": shares, "n": n, "rho": rho, "seed": seed, "moments": moments,
            "samples": R}


# --------------------------------------------------------------------------- CU + B8
@dataclass
class Result:
    config: Configuration
    X: dict
    conf: dict
    obs: dict
    norm: dict
    A: dict
    G: dict
    R: dict
    P: Optional[dict]
    trace: Trace
    elapsed_ms: float

    @property
    def index(self) -> float:
        return self.R["R"]

    def summary(self) -> dict:
        d = {k: v for k, v in self.R.items()}
        d["goals_mean"] = {g: self.G[g]["mean"] for g in self.G}
        d["goals_min"] = {g: self.G[g]["min"] for g in self.G}
        d["actions"] = {c: self.A[c]["mu"] for c in self.A}
        if self.P:
            d["robustness"] = {k: v for k, v in self.P.items() if k not in ("samples", "moments")}
        d["config_version"] = self.config.version
        return d


def assess(cfg: Configuration, raw: dict, robust: bool = True, n: Optional[int] = None,
           rho: Optional[float] = None, seed: Optional[int] = None) -> Result:
    """Control unit CU: run B0-B8 in order; a failure code stops the chain."""
    t0 = time.perf_counter()
    trace = Trace(cfg.version, cfg.seed if seed is None else seed)
    trace.write("C", "CU", {"command": "start", "version": cfg.version, "software": SOFTWARE_VERSION})
    try:
        X = stage0_input(raw)
        trace.write("X", "B0", X)
        conf = stage1_form(cfg, X)
        trace.write("XiWK", "B1", {"tree": conf["tree"], "theta": conf["theta"], "operator": conf["operator"]})
        obs = stage2_verify(cfg, conf)
        trace.write("O", "B2", obs)
    except AssessmentError as e:
        trace.write("C", "CU", {"command": "stop", "status": e.code, "detail": e.detail}, status=e.code)
        raise
    norm = stage3_normalize(cfg, conf, obs)
    trace.write("M", "B3", norm)
    A = stage4_aggregate(cfg, obs, norm)
    trace.write("A", "B4", A)
    G = stage5_rollup(cfg, A)
    trace.write("G", "B5", G)
    R = stage6_integral(cfg, A, G)
    trace.write("R", "B6", R)
    P = None
    if robust:
        P = stage7_robust(cfg, obs, norm, n=n, rho=rho, seed=seed)
        trace.write("P", "B7", {k: v for k, v in P.items() if k != "samples"})
    elapsed = (time.perf_counter() - t0) * 1e3
    trace.write("C", "CU", {"command": "stop", "status": "OK", "elapsed_ms": elapsed})
    return Result(cfg, X, conf, obs, norm, A, G, R, P, trace, elapsed)
