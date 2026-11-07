"""Stages G1-G4: design -> generate -> evaluate/optimize -> derive. Produces canonical tables."""
from __future__ import annotations

import hashlib
import json
import os
from concurrent.futures import ProcessPoolExecutor

import numpy as np
import pandas as pd
import yaml

from . import engine as E
from .design import build_design, stable_id
from .generate import generate_scenario

METHODS = ["none", "full", "exact", "greedy", "layer_uniform", "max_effect", "random", "exact_est", "greedy_est"]


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def input_digest(sc: dict) -> str:
    payload = {k: sc[k] for k in ("assets", "vulnerabilities", "threats", "barriers")}
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=float).encode()).hexdigest()


def run_one(args):
    srow, cfg = args
    sc = generate_scenario(srow, cfg)
    tru = E.Instance(sc, srow, cfg, "true")
    est = E.Instance(sc, srow, cfg, "est")
    R, C = E.enumerate_all(tru)
    Re, Ce = E.enumerate_all(est)
    B, m = tru.budget, tru.m
    rng = np.random.default_rng([cfg["seed"], 7, int(srow["scenario_id"].split("-")[1], 16) % 2**32])
    masks = {
        "none": 0, "full": 2 ** m - 1,
        "exact": E.exact(R, C, B),
        "greedy": E.greedy(R, tru.cost, B),
        "layer_uniform": E.layer_uniform(tru.layer, tru.cost, B),
        "max_effect": E.by_order(np.argsort(-np.array([b["effectiveness"] for b in sc["barriers"]]), kind="stable"), tru.cost, B),
        "random": E.by_order(rng.permutation(m), tru.cost, B),
        "exact_est": E.exact(Re, Ce, B),
        "greedy_est": E.greedy(Re, est.cost, B),
    }
    rand_exp = float(np.mean([R[E.by_order(rng.permutation(m), tru.cost, B)] for _ in range(32)]))
    digest = input_digest(sc)
    Rx = R[masks["exact"]]
    configs = []
    for meth in METHODS:
        mk = masks[meth]
        x = E.bits_to_vec(E.mask_to_bits(mk, m))
        ind = tru.indicators(x, cfg["coverage_threshold"])
        configs.append({
            "config_id": stable_id("cfg", srow["scenario_id"], meth), "scenario_id": srow["scenario_id"],
            "method": meth, "basis": "estimated" if meth.endswith("_est") else "true",
            "selection_bits": E.mask_to_bits(mk, m), "budget_kcu": B,
            "feasible": bool(C[mk] <= B + 1e-9), "residual_risk_est_kcu": float(Re[mk]),
            **ind,
            "relative_residual_risk": ind["residual_risk_kcu"] / tru.R0,
            "optimality_gap": (ind["residual_risk_kcu"] - Rx) / tru.R0,
            "derived_from_digest": digest,
        })
    fr = E.frontier(R, C)
    frontier = [{"scenario_id": srow["scenario_id"], "point": i, "cost_kcu": float(C[k]),
                 "residual_risk_kcu": float(R[k]), "selection_bits": E.mask_to_bits(int(k), m)}
                for i, k in enumerate(fr)]
    summary = {**srow, "network_id": sc["network"]["network_id"], "n_assets": tru.A, "n_threats": tru.T,
               "n_barriers": m, "n_subsets": 2 ** m, "baseline_risk_kcu": tru.R0,
               "full_cost_kcu": float(tru.cost_true.sum()), "full_residual_risk_kcu": float(R[-1]),
               "budget_kcu": B, "frontier_size": len(fr), "random_expected_risk_kcu": rand_exp,
               "input_digest": digest}
    cascade = tru.layer_cascade(E.bits_to_vec(E.mask_to_bits(masks["exact"], m))).tolist()
    return summary, sc, configs, frontier, cascade


def run(cfg: dict, workers: int | None = None) -> dict:
    design = build_design(cfg)
    rows = design.to_dict("records")
    workers = workers or max(1, (os.cpu_count() or 2) - 0)
    out = {k: [] for k in ("scenarios", "networks", "nodes", "links", "assets", "vulnerabilities",
                           "threats", "barriers", "configurations", "frontier")}
    cascades = {}
    with ProcessPoolExecutor(max_workers=workers) as ex:
        for summary, sc, configs, fr, cas in ex.map(run_one, [(r, cfg) for r in rows], chunksize=16):
            out["scenarios"].append(summary)
            out["networks"].append(sc["network"]); out["nodes"] += sc["nodes"]; out["links"] += sc["links"]
            for k in ("assets", "vulnerabilities", "threats", "barriers"):
                out[k] += sc[k]
            out["configurations"] += configs; out["frontier"] += fr
            cascades[summary["scenario_id"]] = cas
    tables = {k: pd.DataFrame(v) for k, v in out.items()}
    return {"tables": tables, "cascades": cascades}
