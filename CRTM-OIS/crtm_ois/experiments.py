"""Experiments of Section 3: reproduction check, five adequacy states, sweep,
weight robustness, non-compensation control and computational cost."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from . import levels as lv
from .model import Configuration
from .scenarios import (EXPECTED_LEVELS, REFERENCE_E1, STATES, bnk_pay, e1_values,
                        five_states, generate_state)
from .system import assess

TOL = 0.0005


def reproduction(cfg: Configuration | None = None) -> dict:
    """Compare the system output for E1 with the 15 published values of CRTM (Table 5)."""
    cfg = cfg or bnk_pay()
    r = assess(cfg, e1_values(), robust=False)
    rows = []
    for c, ref in REFERENCE_E1["actions"].items():
        rows.append({"element": c, "kind": "action", "published": ref, "system": r.A[c]["mu"],
                     "kappa": r.A[c]["kappa"], "level": lv.code(r.A[c]["level"])})
    for g in REFERENCE_E1["goals_mean"]:
        for op in ("mean", "min"):
            ref = REFERENCE_E1[f"goals_{op}"][g]
            rows.append({"element": f"Goal {g} ({op})", "kind": "goal", "published": ref,
                         "system": r.G[g][op], "kappa": None, "level": lv.code(lv.level(r.G[g][op]))})
    for row in rows:
        row["abs_diff"] = abs(row["system"] - row["published"])
        row["ok"] = row["abs_diff"] <= TOL + 1e-12
    L, U = REFERENCE_E1["enclosure"]["CN.S2.A1"]
    enc = {"published": (L, U), "system": (r.A["CN.S2.A1"]["L"], r.A["CN.S2.A1"]["U"])}
    enc["ok"] = abs(enc["system"][0] - L) <= TOL and abs(enc["system"][1] - U) <= TOL
    hand = sum(REFERENCE_E1["goals_mean"].values()) / 4
    return {"rows": rows, "n": len(rows), "n_ok": sum(r_["ok"] for r_ in rows),
            "max_abs_diff": max(r_["abs_diff"] for r_ in rows), "enclosure": enc,
            "integral_hand": hand, "integral_system": r.R["R"],
            "integral_ok": abs(hand - r.R["R"]) <= TOL}


def adequacy(cfg: Configuration | None = None, n: int = 200_000, rho: float = 1.0,
             source: str = "table") -> dict:
    """Five adequacy experiments E1-E5 (Table 7)."""
    cfg = cfg or bnk_pay()
    out = {}
    for e, x in five_states(cfg, source).items():
        r = assess(cfg, x, n=n, rho=rho)
        out[e] = {"t": STATES[e], "R": r.R["R"], "level": r.R["level"], "level_code": r.R["level_code"],
                  "expected": EXPECTED_LEVELS[e], "ok": r.R["level"] == EXPECTED_LEVELS[e],
                  "R_min": r.R["R_min"], "R_L": r.R["R_L"], "R_U": r.R["R_U"],
                  "stable_missing": r.R["stable_missing"],
                  "goals_mean": {g: r.G[g]["mean"] for g in r.G},
                  "goals_min": {g: r.G[g]["min"] for g in r.G},
                  "actions": {c: r.A[c]["mu"] for c in r.A},
                  "action_levels": {c: r.A[c]["level"] for c in r.A},
                  "vetoed": r.R["vetoed"], "weakest_goal": r.R["weakest_goal"],
                  "mc": {k: v for k, v in r.P.items() if k not in ("samples", "moments")},
                  "samples": r.P["samples"]}
    order = ["E4", "E2", "E1", "E3", "E5"]
    Rs = [out[e]["R"] for e in order]
    out["_order_ok"] = bool(all(a < b for a, b in zip(Rs, Rs[1:])))
    return out


def sweep(cfg: Configuration | None = None, n_points: int = 81) -> dict:
    """Continuous sweep of the state parameter t in [-1, 1] (Figure 6b)."""
    cfg = cfg or bnk_pay()
    base = e1_values()
    ts = np.linspace(-1, 1, n_points)
    R, Rmin = [], []
    for t in ts:
        r = assess(cfg, generate_state(cfg, base, float(t)), robust=False)
        R.append(r.R["R"])
        Rmin.append(r.R["R_min"])
    R, Rmin = np.array(R), np.array(Rmin)
    crossings = {}
    for b in (0.2, 0.4, 0.7, 0.9):
        idx = np.where((R[:-1] < b) & (R[1:] >= b))[0]
        if idx.size:
            i = idx[0]
            crossings[b] = float(ts[i] + (b - R[i]) * (ts[i + 1] - ts[i]) / (R[i + 1] - R[i]))
    return {"t": ts, "R": R, "R_min": Rmin,
            "monotone_R": bool(np.all(np.diff(R) >= -1e-12)),
            "monotone_Rmin": bool(np.all(np.diff(Rmin) >= -1e-12)),
            "crossings": crossings}


def non_compensation(cfg: Configuration | None = None) -> dict:
    """Vary the number of TI sources 0..4 with all other inputs at E1 (Figure 7b)."""
    cfg = cfg or bnk_pay()
    res = {op: {"action": [], "R": [], "R_min": []} for op in ("additive", "hard", "capped")}
    for k in range(5):
        x = e1_values()
        x[("UN.S1.A1", "M1")] = float(k)
        for op in res:
            r = assess(cfg.replace(operator=op), x, robust=False)
            res[op]["action"].append(r.A["UN.S1.A1"]["mu"])
            res[op]["R"].append(r.R["R"])
            res[op]["R_min"].append(r.R["R_min"])
    res["sources"] = list(range(5))
    return res


def robustness_rho(cfg: Configuration | None = None, rhos=(1.0, 4.0), n: int = 200_000) -> dict:
    cfg = cfg or bnk_pay()
    st = five_states(cfg)
    out = {}
    for rho in rhos:
        out[rho] = {}
        for e in ("E1", "E2", "E3"):
            r = assess(cfg, st[e], n=n, rho=rho)
            out[rho][e] = {k: v for k, v in r.P.items() if k not in ("samples", "moments")}
    return out


def timing(cfg: Configuration | None = None, runs: int = 2000) -> dict:
    cfg = cfg or bnk_pay()
    st = five_states(cfg)
    out = {}
    for e, x in st.items():
        t0 = time.perf_counter()
        for _ in range(runs):
            assess(cfg, x, robust=False)
        out[e] = (time.perf_counter() - t0) / runs * 1e3
    t0 = time.perf_counter()
    assess(cfg, st["E1"], n=200_000)
    out["stage7_200k_s"] = time.perf_counter() - t0
    return out


def _jsonable(o):
    if isinstance(o, dict):
        return {str(k): _jsonable(v) for k, v in o.items() if k != "samples"}
    if isinstance(o, (list, tuple)):
        return [_jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer, np.bool_)):
        return o.item()
    return o


def run_all(out: str | Path | None = None, n: int = 200_000, runs: int = 2000) -> dict:
    cfg = bnk_pay()
    res = {"config_version": cfg.version, "seed": cfg.seed,
           "reproduction": reproduction(cfg), "adequacy": adequacy(cfg, n=n),
           "sweep": sweep(cfg), "non_compensation": non_compensation(cfg),
           "robustness": robustness_rho(cfg, n=n), "timing_ms": timing(cfg, runs=runs)}
    if out:
        Path(out).write_text(json.dumps(_jsonable(res), indent=2))
    return res
