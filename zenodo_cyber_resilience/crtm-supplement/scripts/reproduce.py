#!/usr/bin/env python3
"""Reproduce every number, table and figure of the illustrative application.

Usage:  python scripts/reproduce.py [--out results] [--no-figures] [--fast]

Writes
  results/results.json            all computed quantities (Data S1)
  results/checks.csv              computed vs published values
  results/tables/*.csv            Tables 5, 6 and A1
  results/figures/*.{png,svg,pdf} supplementary figures
and exits with status 1 if any published value is not reproduced.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import crtm  # noqa: E402
from crtm import aggregation as agg  # noqa: E402
from crtm import sensitivity as sens  # noqa: E402
from crtm import uncertainty as unc  # noqa: E402
from crtm.hierarchy import jaccard_index, poset_size  # noqa: E402
from crtm.normalization import grid_check  # noqa: E402

CHECKS: list[dict] = []


def check(name: str, computed, published, tol: float, where: str = ""):
    """Record a comparison with a value printed in the article."""
    ok = abs(float(computed) - float(published)) <= tol
    CHECKS.append({"quantity": name, "computed": float(computed), "published": float(published),
                   "tolerance": tol, "ok": ok, "where": where})
    return ok


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if math.isnan(o) else float(o)
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, np.ndarray):
        return jsonable(o.tolist())
    return o


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "results"))
    ap.add_argument("--no-figures", action="store_true")
    ap.add_argument("--fast", action="store_true", help="20,000 instead of 200,000 Monte Carlo samples")
    args = ap.parse_args(argv)
    out = Path(args.out)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    n_mc = 20_000 if args.fast else unc.N_SAMPLES
    mc_tol = 0.01 if args.fast else 0.003

    actions = crtm.load_metrics()
    scen = crtm.load_scenarios()
    R: dict = {"version": crtm.__version__, "seed": unc.SEED, "mc_samples": n_mc}

    # ---------------------------------------------------- Section 3.5: lattice
    cat = scen["catalog"]
    P, Q = scen["projections"]["DDoS"], scen["projections"]["phishing"]
    J, M = P | Q, P & Q
    R["projections"] = {
        "admissible": {k: v.is_admissible(cat) for k, v in scen["projections"].items()},
        "sizes": {"DDoS": len(P.actions), "phishing": len(Q.actions)},
        "meet": sorted(M.actions), "join_size": len(J.actions),
        "jaccard_actions": jaccard_index(P.actions, Q.actions),
        "downset_sizes": [len(P.downset()), len(Q.downset())],
        "downset_meet": len(P.downset() & Q.downset()), "downset_join": len(P.downset() | Q.downset()),
        "jaccard_downset": jaccard_index(P.downset(), Q.downset()),
        "poset_size_local_catalog": poset_size(cat),
    }
    pr = R["projections"]
    check("|P_DDoS|", pr["sizes"]["DDoS"], 9, 0, "Sec. 3.5")
    check("|P_phish|", pr["sizes"]["phishing"], 7, 0, "Sec. 3.5")
    check("|meet|", len(pr["meet"]), 4, 0, "Sec. 3.5")
    check("|join|", pr["join_size"], 12, 0, "Sec. 3.5")
    check("Jaccard index (actions)", pr["jaccard_actions"], 1 / 3, 1e-12, "Sec. 3.5")
    check("|E(P_DDoS)|", pr["downset_sizes"][0], 26, 0, "Sec. 3.5")
    check("|E(P_phish)|", pr["downset_sizes"][1], 23, 0, "Sec. 3.5")
    check("|E meet|", pr["downset_meet"], 13, 0, "Sec. 3.5")
    check("|E join|", pr["downset_join"], 36, 0, "Sec. 3.5")
    check("Jaccard index (down-sets)", pr["jaccard_downset"], 0.361, 5e-4, "Sec. 3.5")

    # ------------------------------------------ Section 5: normalization theory
    un = actions["UN.S1.A1"]
    t3 = un.metrics[2].table
    c1 = t3.corollary1_interval()
    R["corollary1_UN.S1.A1_M3"] = c1
    check("Cor.1 interval length (M3)", c1["length"], 17, 1e-9, "Sec. 5.2")
    check("Cor.1 upper end (M3, min)", c1["x_interval"]["to"], 27, 1e-9, "Sec. 5.2")
    check("n_ch(4 sharing events)", un.metrics[4].normalized("linear"), 0.444, 5e-4, "Sec. 5.2")
    R["affine_consistent_exists"] = {f"{b}/M{p + 1}": mt.table.affine_consistent()[0]
                                     for b, a in actions.items() for p, mt in enumerate(a.metrics)}

    # consistency on all observed metrics (Fig. 6)
    bad_lin = bad_anc = n_obs = 0
    per_action = {}
    for b, a in actions.items():
        k = 0
        for mt in a.metrics:
            if not mt.observed:
                continue
            n_obs += 1
            r = mt.tabulated_level()
            if crtm.level(mt.normalized("linear")) != r:
                bad_lin += 1
                k += 1
            if crtm.level(mt.normalized("anchored")) != r:
                bad_anc += 1
        per_action[b] = k
    R["consistency"] = {"observed": n_obs, "inconsistent_linear": bad_lin,
                        "inconsistent_anchored": bad_anc, "per_action_linear": per_action}
    check("observed metrics", n_obs, 38, 0, "Sec. 5.3 / Fig. 6")
    check("inconsistent linear scores", bad_lin, 9, 0, "Abstract / Fig. 6")
    check("inconsistent anchored scores", bad_anc, 0, 0, "Theorem 2(a)")
    for b, v in zip(actions, (2, 1, 2, 2, 2, 0, 0)):
        check(f"inconsistent linear in {b}", per_action[b], v, 0, "Table 6")

    # grid check (Sec. 7.1)
    grid = [grid_check(mt.table, "anchored") for a in actions.values() for mt in a.metrics]
    R["grid_check"] = {"tables": len(grid), "points_per_table": grid[0]["points"],
                       "violations": sum(g["violations"] for g in grid)}
    check("grid-check violations (anchored)", R["grid_check"]["violations"], 0, 0, "Sec. 7.1")

    # ------------------------------------------------------ Table 5 / Sec. 7.2
    w = un.w()
    rows5 = []
    for p, mt in enumerate(un.metrics):
        rows5.append({"q": p + 1, "metric": mt.name, "unit": mt.unit, "value": mt.value,
                      "xi": " ".join(f"{v:g}" for v in mt.table.xi),
                      "n_ch": mt.normalized("linear"), "lvl_lin": crtm.level_abbr(mt.normalized("linear")),
                      "nu": mt.normalized("anchored"), "lvl_anc": crtm.level_abbr(mt.normalized("anchored")),
                      "w": w[p], "w_n": w[p] * mt.normalized("linear"), "w_nu": w[p] * mt.normalized("anchored"),
                      "core": int(mt.core)})
    lin, anc = un.vector("linear"), un.vector("anchored")
    eq = np.full(un.q, 1 / un.q)
    m0l, m0a = lin.copy(), anc.copy()
    m0l[0] = m0a[0] = 0.0
    t5 = {"gate_linear": agg.hard_gate(lin, w, un.core), "gate_anchored": agg.hard_gate(anc, w, un.core),
          "equal_linear": agg.additive(lin, eq), "equal_anchored": agg.additive(anc, eq),
          "no_source_additive_linear": agg.additive(m0l, w), "no_source_additive_anchored": agg.additive(m0a, w),
          "no_source_gate": agg.hard_gate(m0l, w, un.core), "no_source_power": agg.power(m0l, w, un.core),
          "no_source_capped": agg.capped(m0l, w, un.core, 0.5)}
    contrib_loss = {f"M{p + 1}": float(w[p] * (anc[p] - lin[p])) for p in range(un.q)}
    R["table5"] = {"rows": rows5, **t5, "contribution_change_anchored_minus_linear": contrib_loss}
    check("UN.S1.A1 gated linear", t5["gate_linear"], 0.9035, 5e-5, "Table 5")
    check("UN.S1.A1 gated anchored", t5["gate_anchored"], 0.8558, 5e-5, "Table 5")
    check("UN.S1.A1 equal weights linear", t5["equal_linear"], 0.8371, 5e-5, "Table 5")
    check("UN.S1.A1 equal weights anchored", t5["equal_anchored"], 0.8361, 5e-5, "Table 5")
    check("UN.S1.A1 additive, M1 = 0, linear", t5["no_source_additive_linear"], 0.6535, 5e-5, "Table 5")
    check("UN.S1.A1 additive, M1 = 0, anchored", t5["no_source_additive_anchored"], 0.6058, 5e-5, "Table 5")
    check("non-compensatory operators, M1 = 0", max(t5["no_source_gate"], t5["no_source_power"],
                                                    t5["no_source_capped"]), 0, 0, "Sec. 7.3")
    check("difference linear - anchored", t5["gate_linear"] - t5["gate_anchored"], 0.0477, 5e-5, "Sec. 7.2")
    check("loss of contribution M3", -contrib_loss["M3"], 0.0404, 5e-5, "Sec. 7.2")
    check("loss of contribution M4", -contrib_loss["M4"], 0.0200, 5e-5, "Sec. 7.2")
    check("gain of contribution M5", contrib_loss["M5"], 0.0128, 5e-5, "Sec. 7.2")

    # ------------------------------------------------------ Sec. 6 / 7.3: knockout
    ko = {}
    for meth in ("linear", "anchored"):
        m1 = un.vector(meth)
        m1[0] = float(un.metrics[0].table.normalize(1, meth))
        ko[meth] = {"one_source_m1": m1[0], "gate": agg.hard_gate(m1, w, un.core),
                    "power_g1": agg.power(m1, w, un.core, 1.0), "capped_0.5": agg.capped(m1, w, un.core, 0.5),
                    "four_sources_capped_0.5": agg.capped(un.vector(meth), w, un.core, 0.5)}
    ko["C_rest_linear"] = float(w[1:] @ lin[1:])
    ko["compensation_capacity_additive"] = agg.compensation_capacity_additive(w, 0)
    R["knockout"] = ko
    check("C = sum_{q>=2} w_q m_q", ko["C_rest_linear"], 0.6535, 5e-5, "Fig. 7")
    check("C_1(S_w)", ko["compensation_capacity_additive"], 0.75, 1e-12, "Sec. 6.1")
    check("one source, gate, linear", ko["linear"]["gate"], 0.716, 5e-4, "Sec. 7.3 / Table 4")
    check("one source, gate, anchored", ko["anchored"]["gate"], 0.656, 5e-4, "Sec. 7.3")
    check("one source, power γ=1, linear", ko["linear"]["power_g1"], 0.179, 5e-4, "Sec. 6.2 / Table 4")
    check("one source, power γ=1, anchored", ko["anchored"]["power_g1"], 0.131, 5e-4, "Sec. 7.3")
    check("one source, capped ϑ=0.5, linear", ko["linear"]["capped_0.5"], 0.500, 5e-4, "Table 4")
    check("one source, capped ϑ=0.5, anchored", ko["anchored"]["capped_0.5"], 0.400, 5e-4, "Sec. 7.3")
    check("four sources, capped ϑ=0.5, linear", ko["linear"]["four_sources_capped_0.5"], 0.9035, 5e-5, "Sec. 8.1")

    # operator properties (Table 4 / Corollary 2) — numerical probes
    K = un.core
    ops = {"additive": lambda m: agg.additive(m, w), "hard_gate": lambda m: agg.hard_gate(m, w, K),
           "power": lambda m: agg.power(m, w, K, 1.0), "capped": lambda m: agg.capped(m, w, K, 0.5)}
    R["operator_properties"] = {
        k: {"idempotent": agg.is_idempotent(f, un.q), "veto": agg.has_veto(f, un.q, 0),
            "jump_at_core_zero": agg.max_jump_at(f, lin, 0)} for k, f in ops.items()}

    # ------------------------------------------------------ Sec. 7.4: sensitivity
    S = {}
    for meth in ("linear", "anchored"):
        _, _, Z = sens.grid(un, 2, 3, (0, 200), (0, 260), meth)
        S[meth] = {"min": float(Z.min()), "max": float(Z.max())}
        S[meth + "_Z"] = Z
    S["max_abs_diff"] = float(np.abs(S["anchored_Z"] - S["linear_Z"]).max())
    S["margin_linear"] = t5["gate_linear"] - 0.9
    S["linear_tau4_threshold"] = sens.threshold(un, 3, 0.9, "linear", 45, 120)
    S["linear_tau3_threshold"] = sens.threshold(un, 2, 0.9, "linear", 25, 90)
    S["anchored_tau3_threshold_at_tau4_45"] = sens.threshold(un, 2, 0.9, "anchored", 1e-6, 24.99)
    S["anchored_tau4_threshold_at_tau3_10"] = sens.threshold(un, 3, 0.9, "anchored", 15.0001, 44.99, {2: 10})
    del S["linear_Z"], S["anchored_Z"]
    R["sensitivity"] = S
    check("grid min, linear", S["linear"]["min"], 0.502, 5e-4, "Sec. 7.4")
    check("grid max, linear", S["linear"]["max"], 0.952, 5e-4, "Sec. 7.4")
    check("grid min, anchored", S["anchored"]["min"], 0.515, 5e-4, "Sec. 7.4")
    check("grid max, anchored", S["anchored"]["max"], 0.965, 5e-4, "Sec. 7.4")
    check("max |anchored - linear|", S["max_abs_diff"], 0.100, 5e-4, "Sec. 7.4")
    check("margin above 0.9 (linear)", S["margin_linear"], 0.0035, 5e-5, "Sec. 7.4")
    check("τ4 threshold, linear", S["linear_tau4_threshold"], 48.9, 0.05, "Sec. 7.4")
    check("τ3 threshold, linear", S["linear_tau3_threshold"], 27.4, 0.05, "Sec. 7.4")
    check("τ3 threshold, anchored (τ4 = 45)", S["anchored_tau3_threshold_at_tau4_45"], 7.3, 0.05, "Sec. 7.4")
    check("τ4 threshold, anchored (τ3 = 10)", S["anchored_tau4_threshold_at_tau3_10"], 37.5, 0.05, "Sec. 7.4")

    # ------------------------------------------------------ Sec. 7.5: weights
    D = {}
    for meth, m in (("linear", lin), ("anchored", anc)):
        for a in (1, 4):
            D[f"{meth}_alpha{a}"] = unc.summary(m, a, n_mc)
    R["dirichlet"] = D
    check("exact mean, linear", D["linear_alpha1"]["exact_mean"], 0.8371, 5e-5, "Sec. 7.5")
    check("exact sd, linear (α=1)", D["linear_alpha1"]["exact_sd"], 0.0716, 5e-5, "Sec. 7.5")
    check("exact mean, anchored", D["anchored_alpha1"]["exact_mean"], 0.8361, 5e-5, "Sec. 7.5")
    check("exact sd, anchored (α=1)", D["anchored_alpha1"]["exact_sd"], 0.0452, 5e-5, "Sec. 7.5")
    for k in ("linear_alpha1", "anchored_alpha1"):
        check(f"MC vs exact mean ({k})", D[k]["mc_mean"], D[k]["exact_mean"], 2e-4 if not args.fast else 1e-3, "Sec. 7.5")
        check(f"MC vs exact sd ({k})", D[k]["mc_sd"], D[k]["exact_sd"], 2e-4 if not args.fast else 1e-3, "Sec. 7.5")
    check("P(high), linear, α=1", D["linear_alpha1"]["p_high"], 0.185, mc_tol, "Sec. 7.5")
    check("P(high), anchored, α=1", D["anchored_alpha1"]["p_high"], 0.095, mc_tol, "Sec. 7.5")
    check("P(high), linear, α=4", D["linear_alpha4"]["p_high"], 0.029, mc_tol, "Sec. 7.5")
    check("P(high), anchored, α=4", D["anchored_alpha4"]["p_high"], 0.005, mc_tol, "Sec. 7.5")
    check("P(<0.7), linear, α=1", D["linear_alpha1"]["p_below_0.7"], 0.050, mc_tol, "Sec. 7.5")
    check("P(<0.7), anchored, α=1", D["anchored_alpha1"]["p_below_0.7"], 0.0, 0, "Prop. 3")

    # ------------------------------------------------------ Table 6 / Sec. 7.6
    sc = {m: crtm.evaluate_scenario(actions, method=m) for m in ("linear", "anchored")}
    pub6 = {"UN.S1.A1": (0.9035, 0.8558), "UN.S2.A1": (0.6437, 0.6702), "CN.S1.A1": (0.5905, 0.5885),
            "CN.S2.A1": (0.6173, 0.5989), "RE.S1.A2": (0.7639, 0.7192), "TR.S1.A1": (0.6967, 0.6817),
            "TR.S2.A2": (0.8036, 0.7533)}
    for b, (pl, pa) in pub6.items():
        check(f"{b} linear", sc["linear"]["actions"][b].score, pl, 5e-5, "Table 6")
        check(f"{b} anchored", sc["anchored"]["actions"][b].score, pa, 5e-5, "Table 6")
    c2 = {m: sc[m]["actions"]["CN.S2.A1"] for m in sc}
    check("CN.S2.A1 κ", c2["anchored"].kappa, 0.9, 1e-12, "Table 6")
    check("CN.S2.A1 enclosure low, linear", c2["linear"].lower, 0.556, 5e-4, "Table 6")
    check("CN.S2.A1 enclosure high, linear", c2["linear"].upper, 0.656, 5e-4, "Table 6")
    check("CN.S2.A1 enclosure low, anchored", c2["anchored"].lower, 0.539, 5e-4, "Table 6")
    check("CN.S2.A1 enclosure high, anchored", c2["anchored"].upper, 0.639, 5e-4, "Table 6")
    pub_goal = {"linear": {"ANT": (0.774, 0.644), "WITH": (0.604, 0.591), "REC": (0.764, 0.764), "AD": (0.750, 0.697)},
                "anchored": {"ANT": (0.763, 0.670), "WITH": (0.594, 0.588), "REC": (0.719, 0.719), "AD": (0.718, 0.682)}}
    for m, gs in pub_goal.items():
        for g, (mean, mn) in gs.items():
            check(f"goal {g} mean, {m}", sc[m]["profile"][g]["mean"], mean, 5e-4, "Table 6")
            check(f"goal {g} min, {m}", sc[m]["profile"][g]["min"], mn, 5e-4, "Table 6")
    check("linear profile dominates anchored", int(crtm.dominates(sc["linear"]["profile"], sc["anchored"]["profile"])),
          1, 0, "Sec. 7.6")
    for m in sc:
        capped_sc = crtm.evaluate_scenario(actions, method=m, operator="capped", theta=0.5)["actions"]
        binds = sum(not math.isclose(capped_sc[b].score, sc[m]["actions"][b].score) for b in actions)
        check(f"actions where cap ϑ=0.5 binds ({m})", binds, 0, 0, "Sec. 7.6")
    R["scenario"] = {m: {"actions": {b: r.as_dict() for b, r in sc[m]["actions"].items()},
                         "profile": sc[m]["profile"], "N_theta": sc[m]["N_theta"]} for m in sc}
    check("N_theta (metrics in scenario)", sc["anchored"]["N_theta"], 39, 0, "Sec. 7.1")

    # ------------------------------------------------------------- write files
    with open(out / "tables" / "TableA1_phishing_metrics.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["action", "p", "code", "metric", "unit", "printed_classes", "xi", "sigma", "value",
                     "tab_level", "n_ch", "lvl_lin", "nu", "lvl_anc", "consistent_linear", "w", "core"])
        for b, a in actions.items():
            for p, mt in enumerate(a.metrics):
                nl, na = mt.normalized("linear"), mt.normalized("anchored")
                wr.writerow([b, p + 1, mt.code, mt.name, mt.unit, mt.printed_classes,
                             " ".join(f"{v:g}" for v in mt.table.xi), mt.sigma,
                             "" if not mt.observed else f"{mt.value:g}",
                             crtm.LEVEL_ABBR[mt.tabulated_level() - 1] if mt.observed else "n.r.",
                             "" if math.isnan(nl) else f"{nl:.4f}", crtm.level_abbr(nl),
                             "" if math.isnan(na) else f"{na:.4f}", crtm.level_abbr(na),
                             "" if not mt.observed else int(crtm.level(nl) == mt.tabulated_level()),
                             f"{a.w()[p]:.4f}", int(mt.core)])
    with open(out / "tables" / "Table5_UN.S1.A1.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(rows5[0]))
        wr.writeheader()
        wr.writerows(rows5)
    with open(out / "tables" / "Table6_scenario.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.writer(fh)
        wr.writerow(["action", "goal", "q", "core", "kappa", "linear", "lvl_lin", "lin_low", "lin_high",
                     "anchored", "lvl_anc", "anc_low", "anc_high", "inconsistent_linear"])
        for b, a in actions.items():
            rl, ra = sc["linear"]["actions"][b], sc["anchored"]["actions"][b]
            wr.writerow([b, a.goal, a.q, "/".join(a.metrics[k].code for k in a.core) or "—",
                         f"{ra.kappa:.2f}", f"{rl.score:.4f}", crtm.level_abbr(rl.score), f"{rl.lower:.4f}",
                         f"{rl.upper:.4f}", f"{ra.score:.4f}", crtm.level_abbr(ra.score), f"{ra.lower:.4f}",
                         f"{ra.upper:.4f}", len(rl.inconsistent)])
        for g in sc["anchored"]["profile"]:
            pl, pa = sc["linear"]["profile"][g], sc["anchored"]["profile"][g]
            wr.writerow([f"goal {g} (mean/min)", g, "", "", "", f"{pl['mean']:.3f}/{pl['min']:.3f}", "", "", "",
                         f"{pa['mean']:.3f}/{pa['min']:.3f}", "", "", "", ""])

    R["checks"] = CHECKS
    with open(out / "results.json", "w", encoding="utf-8") as fh:
        json.dump(jsonable(R), fh, indent=2, ensure_ascii=False)
    with open(out / "checks.csv", "w", newline="", encoding="utf-8") as fh:
        wr = csv.DictWriter(fh, fieldnames=list(CHECKS[0]))
        wr.writeheader()
        wr.writerows(CHECKS)

    if not args.no_figures:
        import matplotlib
        if "ipykernel" not in sys.modules:
            matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from crtm import figures as F
        fdir = out / "figures"
        fdir.mkdir(exist_ok=True)
        for name, (arg, fn) in F.ALL.items():
            obj = scen if arg == "scen" else actions if arg == "actions" else actions[arg]
            fig = fn(obj)
            for ext in ("png", "svg", "pdf"):
                fig.savefig(fdir / f"{name}.{ext}", bbox_inches="tight", dpi=300)
            plt.close(fig)
            print(f"  figure  {name}")

    n_bad = sum(not c["ok"] for c in CHECKS)
    width = max(len(c["quantity"]) for c in CHECKS)
    for c in CHECKS:
        flag = "OK " if c["ok"] else "FAIL"
        print(f"  [{flag}] {c['quantity']:<{width}}  computed {c['computed']:>10.4f}   "
              f"published {c['published']:>10.4f}   ({c['where']})")
    print(f"\n{len(CHECKS) - n_bad}/{len(CHECKS)} published values reproduced; results in {out}")
    return 1 if n_bad else 0


if __name__ == "__main__":
    sys.exit(main())
