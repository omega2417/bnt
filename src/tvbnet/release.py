"""Stages Q1-Q3: defect injection (raw delivery), quarantine with deterministic redelivery,
leakage-resistant manifests and release gates."""
from __future__ import annotations

import hashlib

import numpy as np
import pandas as pd

from . import validate as V

DEFECT_CHECK = {"D1_range": "V3_range", "D2_negative_cost": "V3_range", "D3_orphan_fk": "V5_referential",
                "D4_duplicate_pk": "V4_primary_key", "D5_missing_required": "V2_completeness",
                "D6_derived_tamper": "V6_recompute", "D7_budget_flag": "V6_feasibility"}


def table_digest(df: pd.DataFrame) -> str:
    h = pd.util.hash_pandas_object(df.reset_index(drop=True), index=False).values
    return hashlib.sha256(h.tobytes() + ",".join(df.columns).encode()).hexdigest()


def inject(tables: dict, cfg: dict) -> tuple[dict, list]:
    rng = np.random.default_rng([cfg["seed"], 99])
    raw = {k: v.copy() for k, v in tables.items()}
    log = []
    n = cfg["defects"]

    def pick(t, k, mask=None):
        idx = raw[t].index if mask is None else raw[t].index[mask]
        return rng.choice(idx, size=k, replace=False)

    used = set()
    def fresh(t, k, mask=None):
        out = []
        cand = list(raw[t].index if mask is None else raw[t].index[mask])
        rng.shuffle(cand)
        for i in cand:
            if (t, i) not in used:
                out.append(i); used.add((t, i))
            if len(out) == k:
                break
        return out

    for i in fresh("barriers", n["D1_range"]):
        raw["barriers"].at[i, "effectiveness"] = float(rng.choice([1.2, -0.1]))
        log.append(("D1_range", "barriers", raw["barriers"].at[i, "barrier_id"]))
    for i in fresh("barriers", n["D2_negative_cost"]):
        raw["barriers"].at[i, "annual_cost_kcu"] = -abs(raw["barriers"].at[i, "annual_cost_kcu"])
        log.append(("D2_negative_cost", "barriers", raw["barriers"].at[i, "barrier_id"]))
    for i in fresh("threats", n["D3_orphan_fk"]):
        raw["threats"].at[i, "scenario_id"] = "scn-" + "%012x" % rng.integers(2**47)
        log.append(("D3_orphan_fk", "threats", raw["threats"].at[i, "threat_id"]))
    for i in fresh("vulnerabilities", n["D5_missing_required"]):
        raw["vulnerabilities"].at[i, "exploitability"] = np.nan
        log.append(("D5_missing_required", "vulnerabilities", raw["vulnerabilities"].at[i, "vuln_id"]))
    real = raw["configurations"]["method"].isin(["exact", "greedy", "layer_uniform"]).to_numpy()
    for i in fresh("configurations", n["D6_derived_tamper"], real):
        raw["configurations"].at[i, "residual_risk_kcu"] *= 1.05
        log.append(("D6_derived_tamper", "configurations", raw["configurations"].at[i, "config_id"]))
    infeas = (~raw["configurations"]["feasible"]).to_numpy() & (raw["configurations"]["method"] != "full").to_numpy()
    for i in fresh("configurations", n["D7_budget_flag"], infeas):
        raw["configurations"].at[i, "feasible"] = True
        log.append(("D7_budget_flag", "configurations", raw["configurations"].at[i, "config_id"]))
    src = pick("assets", n["D4_duplicate_pk"])
    dup = raw["assets"].loc[src].copy()
    start = raw["assets"].index.max() + 1
    dup.index = range(start, start + len(dup))
    raw["assets"] = pd.concat([raw["assets"], dup])
    for i in dup.index:
        log.append(("D4_duplicate_pk", "assets", f"{dup.at[i, 'asset_id']}#dup{i}"))
    return raw, log


def quarantine_and_redeliver(raw: dict, clean: dict, cfg: dict) -> dict:
    """Phase 1 on inputs -> quarantine -> redeliver by key; Phase 2 on derived -> quarantine -> redeliver."""
    p1 = V.structural_checks(raw)
    tables = {k: v.copy() for k, v in raw.items()}
    quarantined = {}
    for t, fl in p1["flags"].items():
        if not fl:
            continue
        pk = V.SCHEMA[t][0]
        key = V._key(tables[t], pk)
        drop = []
        for k in fl:
            if "#dup" in k:
                drop.append(int(k.split("#dup")[1]))
            else:
                drop += list(tables[t].index[key == k])
        quarantined[t] = sorted(set(fl))
        keep = tables[t].drop(index=drop)
        keys_fixed = {k for k in fl if "#dup" not in k}
        ckey = V._key(clean[t], pk)
        redelivered = clean[t][ckey.isin(keys_fixed)]
        tables[t] = pd.concat([keep, redelivered]).sort_index()
    p2 = V.consistency_checks(tables, cfg)
    fl2 = p2["flags"]["configurations"]
    if fl2:
        c = tables["configurations"]
        tables["configurations"] = pd.concat([c[~c["config_id"].isin(fl2)],
                                              clean["configurations"][clean["configurations"]["config_id"].isin(fl2)]]
                                             ).sort_index()
    return {"tables": tables, "phase1": p1, "phase2": p2,
            "flags": {**{t: set(v) for t, v in p1["flags"].items()},
                      "configurations": set(p1["flags"]["configurations"]) | set(fl2)},
            "flag_detail": {**p1["flags"], "configurations_phase2": fl2}}


def detection_metrics(log: list, q: dict) -> dict:
    res = {}
    injected_keys = {}
    for d, t, k in log:
        injected_keys.setdefault(t, set()).add(k)
    detail = q["flag_detail"]
    for d in DEFECT_CHECK:
        items = [(t, k) for dd, t, k in log if dd == d]
        hit = 0
        for t, k in items:
            checks = set()
            for src in (t, "configurations_phase2" if t == "configurations" else None):
                if src and k in detail.get(src, {}):
                    checks |= detail[src][k]
            hit += int(DEFECT_CHECK[d] in checks)
        res[d] = {"injected": len(items), "detected": hit, "recall": hit / len(items) if items else None}
    fp = 0
    for t, fl in q["flags"].items():
        fp += len(set(fl) - injected_keys.get(t, set()))
    res["false_positive_flags"] = fp
    return res


# ---------------------------------------------------------------- leakage-resistant manifests
def manifests(scen: pd.DataFrame, cfg: dict) -> dict:
    rng = np.random.default_rng([cfg["seed"], 5])
    fams, tops = list(cfg["families"]), list(cfg["topologies"])
    rng.shuffle(fams); rng.shuffle(tops)
    out = {}
    part = lambda m, test, val: np.where(m.isin(test), "test", np.where(m.isin(val), "validation", "train"))
    out["family_holdout"] = part(scen["family"], fams[:1], fams[1:2])
    out["network_holdout"] = part(scen["topology"], tops[:1], tops[1:2])
    ft, fv, tt, tv = fams[2:4], fams[4:5], tops[2:4], tops[4:5]
    f, t = scen["family"], scen["topology"]
    comp = np.full(len(scen), "excluded", dtype=object)
    comp[(f.isin(ft) & t.isin(tt)).to_numpy()] = "test"
    comp[(f.isin(fv) & t.isin(tv)).to_numpy()] = "validation"
    comp[(~f.isin(ft + fv) & ~t.isin(tt + tv)).to_numpy()] = "train"
    out["compound_holdout"] = comp
    cells = np.array(sorted(scen["cell_id"].unique()), dtype=object); rng.shuffle(cells)
    a, b = int(0.60 * len(cells)), int(0.75 * len(cells))
    cmap = {c: ("train" if i < a else "validation" if i < b else "test") for i, c in enumerate(cells)}
    out["cell_disjoint"] = scen["cell_id"].map(cmap).to_numpy()
    hi = scen["budget_fraction"] == max(cfg["l9_factors"]["budget_fraction"])
    lowcells = np.array(sorted(scen.loc[~hi, "cell_id"].unique()), dtype=object); rng.shuffle(lowcells)
    vset = set(lowcells[: int(0.2 * len(lowcells))])
    out["budget_extrapolation"] = np.where(hi, "test", np.where(scen["cell_id"].isin(vset), "validation", "train"))
    return {k: pd.DataFrame({"scenario_id": scen["scenario_id"], "partition": v}) for k, v in out.items()}


def audit_manifests(scen: pd.DataFrame, man: dict, cfg: dict) -> dict:
    """Each manifest is audited against its own claim: (column, partition pairs that must not share a value)."""
    ALL = [("train", "validation"), ("train", "test"), ("validation", "test")]
    TEST = [("train", "test"), ("validation", "test")]
    claim = {"family_holdout": [("family", ALL), ("cell_id", ALL)],
             "network_holdout": [("topology", ALL), ("cell_id", ALL)],
             "compound_holdout": [("family", ALL), ("topology", ALL), ("cell_id", ALL)],
             "cell_disjoint": [("cell_id", ALL)],
             "budget_extrapolation": [("budget_fraction", TEST), ("cell_id", ALL)]}
    res = {}
    for name, m in man.items():
        d = scen.merge(m, on="scenario_id")
        viol = 0
        for col, pairs in claim[name]:
            vals = {p: set(d.loc[d.partition == p, col]) for p in ("train", "validation", "test")}
            viol += sum(len(vals[x] & vals[y]) for x, y in pairs)
        counts = d["partition"].value_counts().to_dict()
        groups = d[d.partition != "excluded"].groupby(["family", "topology"]).ngroups
        res[name] = {"train": int(counts.get("train", 0)), "validation": int(counts.get("validation", 0)),
                     "test": int(counts.get("test", 0)), "excluded": int(counts.get("excluded", 0)),
                     "groups_used": int(groups), "violations": int(viol),
                     "empty_partitions": int(sum(counts.get(p, 0) == 0 for p in ("train", "validation", "test")))}
    return res


def gates(struct: dict, cons: dict, det: dict | None, man_audit: dict, inv: dict, checksum_ok: float,
          equiv: float | None) -> list:
    sch = min(struct["metrics"]["schema"].values())
    comp = struct["metrics"]["completeness"]
    med = min(v["median"] for v in comp.values()); p05 = min(v["p05"] for v in comp.values())
    n_flag = {t: len(v) for t, v in struct["flags"].items()}
    rng_ok = sum(1 for t, fl in struct["flags"].items() for k, c in fl.items() if "V3_range" in c)
    ref = sum(1 for t, fl in struct["flags"].items() for k, c in fl.items() if "V5_referential" in c)
    inc = sum(1 for t, fl in struct["flags"].items() for k, c in fl.items() if "V2_completeness" in c)
    pkd = sum(1 for t, fl in struct["flags"].items() for k, c in fl.items() if "V4_primary_key" in c)
    g = [
        ("Schema pass rate", sch, ">=1.000", sch >= 1.0),
        ("Median record completeness", med, ">=0.950", med >= 0.95),
        ("Fifth-percentile completeness", p05, ">=0.800", p05 >= 0.80),
        ("Incomplete required records", inc, "<=0", inc <= 0),
        ("Admissible-range violations", rng_ok, "<=0", rng_ok <= 0),
        ("Primary-key duplicates", pkd, "<=0", pkd <= 0),
        ("Referential-integrity violations", ref, "<=0", ref <= 0),
        ("Max relative recomputation error", cons["max_rel_err"], "<=1e-9", cons["max_rel_err"] <= 1e-9),
        ("Feasibility-flag mismatches", sum(1 for c in cons["flags"]["configurations"].values() if "V6_feasibility" in c),
         "<=0", not any("V6_feasibility" in c for c in cons["flags"]["configurations"].values())),
        ("Frontier/dominance violations", cons["monotonicity_violations"] + cons["dominance_violations"], "<=0",
         cons["monotonicity_violations"] + cons["dominance_violations"] == 0),
        ("Impact-scaling invariance deviation", inv["max_rel_dev"], "<=1e-9", inv["max_rel_dev"] <= 1e-9 and inv["argmin_changes"] == 0),
        ("Manifest leakage violations", sum(v["violations"] for v in man_audit.values()), "<=0",
         sum(v["violations"] for v in man_audit.values()) == 0),
        ("Empty evaluation partitions", sum(v["empty_partitions"] for v in man_audit.values()), "<=0",
         sum(v["empty_partitions"] for v in man_audit.values()) == 0),
        ("Checksum pass rate", checksum_ok, ">=1.000", checksum_ok >= 1.0),
    ]
    if det is not None:
        rec = min(v["recall"] for k, v in det.items() if k != "false_positive_flags")
        g.append(("Injected-defect recall", rec, ">=1.000", rec >= 1.0))
        g.append(("False-positive quarantine flags", det["false_positive_flags"], "<=0", det["false_positive_flags"] == 0))
    if equiv is not None:
        g.append(("Release equivalence to reference digest", equiv, ">=1.000", equiv >= 1.0))
    return [{"gate": a, "observed": float(b), "rule": c, "status": "Pass" if d else "Fail"} for a, b, c, d in g]
