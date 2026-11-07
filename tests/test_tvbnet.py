import numpy as np
import pandas as pd
import pytest

from tvbnet import engine as E
from tvbnet import release as Q
from tvbnet import validate as V
from tvbnet.design import L9, build_design, l9_balance
from tvbnet.generate import generate_scenario, build_network, TOPOLOGY_SPEC
from tvbnet.pipeline import load_config, run_one

CFG = load_config("config/pipeline.yaml")
DESIGN = build_design(CFG)


def pick(depth=3, **kw):
    d = DESIGN[DESIGN.depth == depth]
    for k, v in kw.items():
        d = d[d[k] == v]
    return d.iloc[0].to_dict()


def inst(row, basis="true"):
    return E.Instance(generate_scenario(row, CFG), row, CFG, basis)


def test_l9_is_pairwise_balanced():
    assert l9_balance(L9)


def test_design_size_and_unique_ids():
    assert len(DESIGN) == 6 * 6 * 4 * 9 * CFG["replicates"]
    assert DESIGN.scenario_id.is_unique and DESIGN.cell_id.nunique() == 1296


@pytest.mark.parametrize("top", list(TOPOLOGY_SPEC))
def test_topology_connected_and_assets_reachable(top):
    nodes, links, assets, dist, nseg = build_network(top)
    assert all(n in dist for n, _, _ in nodes)
    assert len(assets) == sum(TOPOLOGY_SPEC[top])


def test_generation_is_deterministic():
    r = pick()
    a, b = generate_scenario(r, CFG), generate_scenario(r, CFG)
    assert a["barriers"] == b["barriers"] and a["threats"] == b["threats"]


def test_empty_selection_equals_baseline_and_full_is_minimum():
    I = inst(pick(depth=4))
    R, C = E.enumerate_all(I)
    assert np.isclose(R[0], I.R0)
    assert R[-1] <= R.min() + 1e-12


def test_adding_a_barrier_never_increases_risk():
    I = inst(pick(depth=4))
    R, _ = E.enumerate_all(I)
    for b in range(I.m):
        without = np.array([k for k in range(len(R)) if not (k >> b) & 1])
        assert np.all(R[without | (1 << b)] <= R[without] + 1e-12)


def test_exact_is_feasible_and_optimal():
    I = inst(pick(depth=3))
    R, C = E.enumerate_all(I)
    k = E.exact(R, C, I.budget)
    assert C[k] <= I.budget + 1e-12
    assert R[k] <= R[C <= I.budget].min() + 1e-12


def test_greedy_and_heuristics_respect_budget():
    I = inst(pick(depth=5))
    R, C = E.enumerate_all(I)
    for k in (E.greedy(R, I.cost, I.budget), E.layer_uniform(I.layer, I.cost, I.budget)):
        assert C[k] <= I.budget + 1e-9


def test_frontier_monotone():
    I = inst(pick(depth=4))
    R, C = E.enumerate_all(I)
    fr = E.frontier(R, C)
    assert np.all(np.diff(C[fr]) >= 0) and np.all(np.diff(R[fr]) < 0)


def test_frontier_contains_exact_solution_value():
    I = inst(pick(depth=3))
    R, C = E.enumerate_all(I)
    fr = E.frontier(R, C)
    k = E.exact(R, C, I.budget)
    best = R[fr][C[fr] <= I.budget].min()
    assert np.isclose(best, R[k])


def test_internal_threats_bypass_perimeter():
    I = inst(pick(depth=2, family="insider"))
    ins = np.array([c == 4 for c in I.cls])
    if ins.any():
        assert np.all(I.M[I.layer == 1][:, ins, :] == 0)


def test_impact_scaling_invariance():
    r = pick(depth=4)
    a = inst(r)
    r2 = dict(r); r2["impact_multiplier"] *= 2
    b = E.Instance(generate_scenario(r, CFG), r2, CFG)
    Ra, Ca = E.enumerate_all(a); Rb, _ = E.enumerate_all(b)
    assert np.allclose(Rb, 2 * Ra) and E.exact(Ra, Ca, a.budget) == E.exact(Rb, Ca, a.budget)


def test_perfect_reliability_has_no_estimation_noise():
    cfg = dict(CFG)
    r = pick(); r["input_reliability"] = 1.0
    sc = generate_scenario(r, cfg)
    assert all(np.isclose(t["rate_est"], t["rate_per_year"]) for t in sc["threats"])


def test_indicators_ranges():
    I = inst(pick(depth=5))
    ind = I.indicators(np.ones(I.m), CFG["coverage_threshold"])
    assert 0 <= ind["ch_coverage"] <= 1 and 0 <= ind["mean_threat_coverage"] <= 1
    assert ind["n_layers_used"] == 5


def test_layer_cascade_non_increasing():
    I = inst(pick(depth=5))
    cas = I.layer_cascade(np.ones(I.m)).sum(1)
    assert np.all(np.diff(cas) <= 1e-12) and np.isclose(cas[0], I.R0)


@pytest.fixture(scope="module")
def small_tables():
    rows = DESIGN[(DESIGN.topology.isin(["star", "tree"])) & (DESIGN.depth <= 3)].to_dict("records")
    out = {k: [] for k in ("scenarios", "networks", "nodes", "links", "assets", "vulnerabilities",
                           "threats", "barriers", "configurations", "frontier")}
    for r in rows:
        s, sc, cf, fr, _ = run_one((r, CFG))
        out["scenarios"].append(s); out["networks"].append(sc["network"])
        out["nodes"] += sc["nodes"]; out["links"] += sc["links"]
        for k in ("assets", "vulnerabilities", "threats", "barriers"):
            out[k] += sc[k]
        out["configurations"] += cf; out["frontier"] += fr
    return {k: pd.DataFrame(v) for k, v in out.items()}


def test_clean_tables_pass_structural_checks(small_tables):
    s = V.structural_checks(small_tables)
    assert all(not fl for fl in s["flags"].values())


def test_recompute_consistency(small_tables):
    c = V.consistency_checks(small_tables, CFG)
    assert c["max_rel_err"] <= 1e-9 and c["monotonicity_violations"] == 0


def test_every_injected_defect_detected_without_false_positives(small_tables):
    cfg = dict(CFG); cfg["defects"] = {k: 5 for k in CFG["defects"]}
    raw, log = Q.inject(small_tables, cfg)
    q = Q.quarantine_and_redeliver(raw, small_tables, cfg)
    det = Q.detection_metrics(log, q)
    assert all(v["recall"] == 1.0 for k, v in det.items() if k != "false_positive_flags")
    assert det["false_positive_flags"] == 0


def test_redelivery_restores_reference(small_tables):
    cfg = dict(CFG); cfg["defects"] = {k: 5 for k in CFG["defects"]}
    raw, _ = Q.inject(small_tables, cfg)
    rel = Q.quarantine_and_redeliver(raw, small_tables, cfg)["tables"]
    for t in small_tables:
        pk = V.SCHEMA[t][0]; by = list(pk) if isinstance(pk, tuple) else [pk]
        a = small_tables[t].sort_values(by)[small_tables[t].columns]
        b = rel[t].sort_values(by)[small_tables[t].columns]
        assert Q.table_digest(a) == Q.table_digest(b)


def test_manifests_have_no_leakage_or_empty_partitions():
    scen = DESIGN.copy()
    man = Q.manifests(scen, CFG)
    aud = Q.audit_manifests(scen, man, CFG)
    assert all(v["violations"] == 0 and v["empty_partitions"] == 0 for v in aud.values())
