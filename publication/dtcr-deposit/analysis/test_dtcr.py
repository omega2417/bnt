#!/usr/bin/env python3
"""Unit tests for the dtcr reference library.

These lock the reference implementation to the worked examples printed in the
manuscript, so a regression in the maths is caught before it reaches a figure.

Run:  python analysis/test_dtcr.py      (no pytest dependency required)
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dtcr import audit, trust, anomaly, risk, orchestration, resilience, stats


def approx(a, b, tol=1e-3):
    return abs(a - b) <= tol


def test_audit_matches_worked_example():
    # Section 2.3: l=10000, d=500, eta=0.95 -> r_min=59; bound 0.9515, exact 0.9519.
    assert audit.r_min(0.05, 0.95) == 59
    assert approx(audit.p_detect_bound(0.05, 59), 0.9515, 1e-3)
    assert approx(audit.p_detect_exact(10000, 500, 59), 0.9519, 1e-3)
    # Table 5 spot checks.
    assert audit.r_min(0.01, 0.95) == 299
    assert audit.r_min(0.10, 0.95) == 29
    assert audit.r_min(0.20, 0.99) == 21


def test_trust_matches_worked_example():
    # Section 2.3: T_inst = 0.895; with prev 0.92, rho 0.6 -> T = 0.910.
    inst = trust.instantaneous_trust(0.95, 0.90, 0.80)
    assert approx(inst, 0.895)
    assert approx(trust.smooth_trust(0.92, inst, 0.60), 0.910)


def test_risk_propagation_matches_worked_example():
    # Section 3.5: chain with weights 0.7,0.8,0.4,0.6; R0=[.6,.1,.05,.02]; lam=0.45
    # -> [0.600, 0.289, 0.154, 0.114], kappa = 1.502.
    W = np.zeros((4, 4))
    W[0, 1], W[1, 2], W[1, 3], W[2, 3] = 0.70, 0.80, 0.40, 0.60
    R = np.array([0.60, 0.10, 0.05, 0.02])
    Rt = risk.propagate(R, W, 0.45)
    assert np.allclose(Rt, [0.600, 0.289, 0.154, 0.114], atol=1e-3)
    assert approx(risk.amplification(R, Rt), 1.502, 1e-3)
    # closed form and iteration agree
    assert np.allclose(Rt, risk.propagate_iterative(R, W, 0.45), atol=1e-6)


def test_risk_edge_cases():
    W = np.zeros((2, 2)); W[0, 1] = 0.5
    assert risk.amplification([0, 0], [0, 0]) == 1.0          # zero local risk
    # divergence guard
    Wc = np.array([[0.0, 1.0], [1.0, 0.0]])
    try:
        risk.propagate([1, 1], Wc, 1.5)
        assert False, "expected divergence error"
    except ValueError:
        pass


def test_anomaly_mappings():
    X = np.random.default_rng(0).normal(size=(500, 4))
    m = anomaly.BaselineModel(X, shrinkage=0.05)
    d2 = m.distance_sq(np.zeros(4))
    assert d2 >= 0
    # chi2 mapping is a probability; legacy mapping is a bounded score
    assert 0 <= anomaly.score_chi2(5.0, 4) <= 1
    assert 0 <= anomaly.score_legacy(5.0) <= 1
    # chi2 CDF is monotone in d2
    assert anomaly.score_chi2(10, 4) > anomaly.score_chi2(2, 4)


def test_orchestration_rejects_inadmissible_and_argmins():
    nodes = {
        "cloud-01": orchestration.Node("cloud-01",
            orchestration.ResourceVector(8, 16000, 200000, 1000000),
            security_label=3, trust=0.9, domain="d0"),
        "edge-04": orchestration.Node("edge-04",
            orchestration.ResourceVector(4, 8000, 60000, 100000),
            security_label=1, trust=0.6, domain="d2"),
    }
    workloads = {"analytics-core": orchestration.Workload("analytics-core",
        orchestration.ResourceVector(2, 4000, 20000, 40000),
        security_label=3, min_host_trust=0.75, allowed_domains=("d0",))}
    good = orchestration.Candidate("migrate_cloud", 0.31, 0.42, 0.20, 0.30,
                                   {"analytics-core": "cloud-01"})
    bad = orchestration.Candidate("migrate_edge", 0.10, 0.05, 0.05, 0.05,
                                  {"analytics-core": "edge-04"})  # label+trust+domain viol
    res = orchestration.select_action([good, bad], nodes, workloads)
    assert res["selected"].action == "migrate_cloud"
    assert any("migrate_edge" == r["action"] for r in res["rejected"])


def test_orchestration_worked_example():
    # Section 2.5: post-action risks 0.42,0.31,0.55; overheads 0.18,0.42,0.10;
    # single mu=0.35 -> 0.483,0.457,0.585; migration wins.
    obj = orchestration.Objective(mu1=0.35, mu2=0.0, mu3=0.0)
    cands = [orchestration.Candidate("isolation", 0.42, 0.18, 0, 0),
             orchestration.Candidate("migration", 0.31, 0.42, 0, 0),
             orchestration.Candidate("rate_limit", 0.55, 0.10, 0, 0)]
    vals = {c.action: obj.value(c) for c in cands}
    assert approx(vals["isolation"], 0.483)
    assert approx(vals["migration"], 0.457)
    assert approx(vals["rate_limit"], 0.585)
    assert min(vals, key=vals.get) == "migration"


def test_nri_perfect_and_window():
    cfg = resilience.NRIConfig(rto=100, a_min=0.95, a_max=1.0, hold=10, sampling_interval=1.0)
    t = np.arange(0, 400.0)
    a = np.ones_like(t)
    assert approx(resilience.nri(t, a, 50.0, cfg), 1.0, 1e-6)
    # a trace that ends before the window raises
    try:
        resilience.nri(t, a, 300.0, cfg)
        assert False
    except ValueError:
        pass


def test_stats_wilson_and_effect():
    lo, hi = stats.wilson_ci(98, 100)
    assert lo < 0.98 < hi and hi <= 1.0
    g = stats.hedges_g([10, 11, 12, 13], [1, 2, 3, 4])
    assert g > 1.0
    d = stats.cliffs_delta([10, 11, 12], [1, 2, 3])
    assert approx(d, 1.0)


def test_classification_metrics_consistency():
    m = stats.classification_metrics(90, 900, 10, 10)
    assert approx(m["accuracy"], 990 / 1010, 1e-6)
    assert approx(m["recall"], 0.9)
    assert approx(m["specificity"], 900 / 910, 1e-6)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS {t.__name__}")
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  FAIL {t.__name__}: {exc}")
    print(f"\n{len(tests) - failed}/{len(tests)} tests passed")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
