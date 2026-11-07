"""Stages V1-V8: two-phase technical validation, quarantine/redelivery and release gates."""
from __future__ import annotations

import numpy as np
import pandas as pd

from . import engine as E

SCHEMA = {
    # table: (primary key, {column: (dtype kind, required, (lo, hi) or None)}, {fk column: parent table})
    "scenarios": ("scenario_id", {
        "scenario_id": ("O", True, None), "cell_id": ("O", True, None), "topology": ("O", True, None),
        "family": ("O", True, None), "depth": ("i", True, (2, 5)), "l9_row": ("i", True, (1, 9)),
        "replicate": ("i", True, (1, 99)), "effectiveness_mean": ("f", True, (0, 1)),
        "input_reliability": ("f", True, (0, 1)), "impact_multiplier": ("f", True, (0, 10)),
        "budget_fraction": ("f", True, (0, 1)), "baseline_risk_kcu": ("f", True, (0, None)),
        "budget_kcu": ("f", True, (0, None)), "input_digest": ("O", True, None)}, {}),
    "networks": ("network_id", {"network_id": ("O", True, None), "scenario_id": ("O", True, None),
                                "n_nodes": ("i", True, (1, None)), "n_links": ("i", True, (1, None)),
                                "n_segments": ("i", True, (1, None))}, {"scenario_id": "scenarios"}),
    "nodes": ("node_id", {"node_id": ("O", True, None), "network_id": ("O", True, None), "role": ("O", True, None)},
              {"network_id": "networks"}),
    "links": ("link_id", {"link_id": ("O", True, None), "network_id": ("O", True, None), "u": ("O", True, None),
                          "v": ("O", True, None)}, {"network_id": "networks", "u": "nodes", "v": "nodes"}),
    "assets": ("asset_id", {
        "asset_id": ("O", True, None), "scenario_id": ("O", True, None), "segment": ("i", True, (0, None)),
        "hops": ("i", True, (1, None)), "ind_technical": ("f", True, (0, 1)), "ind_economic": ("f", True, (0, 1)),
        "ind_security": ("f", True, (0, 1)), "info_reliability": ("f", True, (0, 1)),
        "info_value_kcu": ("f", True, (0, None))}, {"scenario_id": "scenarios"}),
    "vulnerabilities": ("vuln_id", {"vuln_id": ("O", True, None), "scenario_id": ("O", True, None),
                                    "asset_id": ("O", True, None), "exploitability": ("f", True, (0, 1)),
                                    "class_mask": ("O", True, None)},
                        {"scenario_id": "scenarios", "asset_id": "assets"}),
    "threats": ("threat_id", {"threat_id": ("O", True, None), "scenario_id": ("O", True, None),
                              "threat_class": ("O", True, None), "rate_per_year": ("f", True, (0, None)),
                              "severity": ("f", True, (0, 1)), "rate_est": ("f", True, (0, None)),
                              "severity_est": ("f", True, (0, 1))}, {"scenario_id": "scenarios"}),
    "barriers": ("barrier_id", {"barrier_id": ("O", True, None), "scenario_id": ("O", True, None),
                                "layer_index": ("i", True, (1, 5)), "effectiveness": ("f", True, (0, 1)),
                                "annual_cost_kcu": ("f", True, (0, None)), "effectiveness_est": ("f", True, (0, 1)),
                                "cost_est": ("f", True, (0, None)), "scope_mask": ("O", True, None)},
                 {"scenario_id": "scenarios"}),
    "configurations": ("config_id", {
        "config_id": ("O", True, None), "scenario_id": ("O", True, None), "method": ("O", True, None),
        "selection_bits": ("O", True, None), "budget_kcu": ("f", True, (0, None)), "feasible": ("b", True, None),
        "residual_risk_kcu": ("f", True, (0, None)), "cost_kcu": ("f", True, (0, None)),
        "ch_coverage": ("f", False, (0, 1)), "mean_threat_coverage": ("f", False, (0, 1)),
        "relative_residual_risk": ("f", True, (0, 1)), "derived_from_digest": ("O", True, None)},
        {"scenario_id": "scenarios"}),
    "frontier": (("scenario_id", "point"), {"scenario_id": ("O", True, None), "point": ("i", True, (0, None)),
                                            "cost_kcu": ("f", True, (0, None)),
                                            "residual_risk_kcu": ("f", True, (0, None))}, {"scenario_id": "scenarios"}),
}
INPUT_TABLES = ["scenarios", "networks", "nodes", "links", "assets", "vulnerabilities", "threats", "barriers"]
DERIVED_TABLES = ["configurations", "frontier"]


def _key(df: pd.DataFrame, pk) -> pd.Series:
    if isinstance(pk, tuple):
        return df[list(pk)].astype(str).agg("|".join, axis=1)
    return df[pk].astype(str)


def structural_checks(tables: dict) -> dict:
    """Phase 1: schema, completeness, range, primary-key uniqueness, referential integrity."""
    flags, metrics = {}, {"schema": {}, "completeness": {}}
    keysets = {t: set(_key(tables[t], SCHEMA[t][0])) for t in tables}
    for t, (pk, cols, fks) in SCHEMA.items():
        df = tables[t]
        key = _key(df, pk)
        fl = {}
        missing_cols = [c for c in cols if c not in df.columns]
        metrics["schema"][t] = 0.0 if missing_cols else 1.0
        req = [c for c, (_, r, _) in cols.items() if r and c in df.columns]
        valid = pd.DataFrame(index=df.index)
        for c in req:
            valid[c] = df[c].notna()
        comp = valid.mean(axis=1)
        metrics["completeness"][t] = {"median": float(comp.median()), "p05": float(comp.quantile(0.05)),
                                      "min": float(comp.min())}
        for i in df.index[comp < 1.0]:
            fl.setdefault(key[i], set()).add("V2_completeness")
        for c, (_, _, rng) in cols.items():
            if rng is None or c not in df.columns:
                continue
            lo, hi = rng
            x = pd.to_numeric(df[c], errors="coerce")
            bad = pd.Series(False, index=df.index)
            if lo is not None:
                bad |= x < lo
            if hi is not None:
                bad |= x > hi
            for i in df.index[bad]:
                fl.setdefault(key[i], set()).add("V3_range")
        dup = key.duplicated(keep="first")
        for i in df.index[dup]:
            fl.setdefault(key[i] + "#dup" + str(i), set()).add("V4_primary_key")
        for c, parent in fks.items():
            bad = ~df[c].astype(str).isin(keysets[parent])
            for i in df.index[bad]:
                fl.setdefault(key[i], set()).add("V5_referential")
        flags[t] = fl
    return {"flags": flags, "metrics": metrics}


def rebuild_scenarios(tables: dict) -> dict:
    """Group input tables back into per-scenario dicts consumable by engine.Instance."""
    out = {}
    g = {t: dict(tuple(tables[t].groupby("scenario_id"))) for t in ("assets", "vulnerabilities", "threats", "barriers")}
    for _, s in tables["scenarios"].iterrows():
        sid = s["scenario_id"]
        out[sid] = ({t: g[t][sid].to_dict("records") for t in g}, s.to_dict())
    return out


def consistency_checks(tables: dict, cfg: dict, tol: float = 1e-9) -> dict:
    """Phase 2: recompute derived indicators from inputs; monotonicity of frontiers."""
    scen = rebuild_scenarios(tables)
    flags, max_rel_err, n_checked = {}, 0.0, 0
    cfgs = tables["configurations"]
    for sid, grp in cfgs.groupby("scenario_id"):
        sc, srow = scen[sid]
        try:
            inst = E.Instance(sc, srow, cfg, "true")
            X = np.array([E.bits_to_vec(b) for b in grp["selection_bits"]])
            R = inst.risk(X)
            C = X @ inst.cost_true
        except (ValueError, IndexError, KeyError):
            max_rel_err = np.inf; n_checked += len(grp)
            for cid in grp["config_id"]:
                flags.setdefault(cid, set()).add("V6_unrecomputable")
            continue
        rel = np.abs(R - grp["residual_risk_kcu"].to_numpy()) / max(inst.R0, 1e-12)
        relc = np.abs(C - grp["cost_kcu"].to_numpy()) / max(inst.cost_true.sum(), 1e-12)
        rel = np.nan_to_num(rel, nan=np.inf); relc = np.nan_to_num(relc, nan=np.inf)
        feas = C <= grp["budget_kcu"].to_numpy() + 1e-9
        max_rel_err = max(max_rel_err, float(rel.max()), float(relc.max()))
        n_checked += len(grp)
        for cid, r, rc, f, f0 in zip(grp["config_id"], rel, relc, feas, grp["feasible"].to_numpy()):
            if r > tol or rc > tol:
                flags.setdefault(cid, set()).add("V6_recompute")
            if bool(f) != bool(f0):
                flags.setdefault(cid, set()).add("V6_feasibility")
    mono_viol = 0
    for sid, fr in tables["frontier"].groupby("scenario_id"):
        fr = fr.sort_values("point")
        mono_viol += int((np.diff(fr["cost_kcu"]) < -1e-12).sum() + (np.diff(fr["residual_risk_kcu"]) > 1e-12).sum())
    # dominance: full selection never riskier than any other configuration of the same scenario
    piv = cfgs.pivot_table(index="scenario_id", columns="method", values="residual_risk_kcu")
    dom_viol = int((piv.drop(columns=["full"]).min(axis=1) < piv["full"] - 1e-9).sum()
                   + (piv.drop(columns=["none"]).max(axis=1) > piv["none"] + 1e-9).sum())
    return {"flags": {"configurations": flags}, "max_rel_err": max_rel_err, "n_checked": n_checked,
            "monotonicity_violations": mono_viol, "dominance_violations": dom_viol}


def invariance_check(tables: dict, cfg: dict, n: int = 120, seed: int = 1) -> dict:
    """Scaling the impact multiplier by 2 must double R(x) and leave x* unchanged (Eq. 5-6)."""
    scen = rebuild_scenarios(tables)
    rng = np.random.default_rng(seed)
    ids = rng.choice(sorted(scen), size=min(n, len(scen)), replace=False)
    worst, changed = 0.0, 0
    for sid in ids:
        sc, srow = scen[sid]
        a = E.Instance(sc, srow, cfg, "true")
        s2 = dict(srow); s2["impact_multiplier"] = 2 * srow["impact_multiplier"]
        b = E.Instance(sc, s2, cfg, "true")
        Ra, Ca = E.enumerate_all(a); Rb, _ = E.enumerate_all(b)
        worst = max(worst, float(np.max(np.abs(Rb - 2 * Ra)) / max(a.R0, 1e-12)))
        changed += int(E.exact(Ra, Ca, a.budget) != E.exact(Rb, Ca, a.budget))
    return {"n": int(len(ids)), "max_rel_dev": worst, "argmin_changes": changed}
