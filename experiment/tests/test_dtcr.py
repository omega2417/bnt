"""Unit tests for the reference implementation.

These are the checks that turned up the defects catalogued in
docs/manuscript_corrections.md; several of them fail against the manuscript's
printed equations, which is the point.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import stats as sps

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dtcr import anomaly, audit, graph_risk, orchestrator as orch, resilience, stats, trust

FAILED: list[str] = []


def check(name, cond, detail=""):
    print(f"  [{'ok  ' if cond else 'FAIL'}] {name}" + (f"  {detail}" if detail else ""))
    if not cond:
        FAILED.append(name)


def test_audit():
    # reproduces the manuscript's own worked example exactly
    check("audit.r_min(10000, 500, 0.95) == 59", audit.r_min(10_000, 500, 0.95) == 59)
    check("bound == 0.9515", abs(audit.p_detect_lower_bound(10_000, 500, 59) - 0.9515) < 5e-5)
    check("exact == 0.9519", abs(audit.p_detect_exact(10_000, 500, 59) - 0.9519) < 5e-5)
    check("exact >= bound (bound is conservative)",
          all(audit.p_detect_exact(10_000, int(p * 10_000), audit.r_min(10_000, int(p * 10_000), 0.95))
              >= audit.p_detect_lower_bound(10_000, int(p * 10_000),
                                            audit.r_min(10_000, int(p * 10_000), 0.95)) - 1e-12
              for p in (0.01, 0.05, 0.10, 0.20)))
    check("Table 5 column reproduces (299, 59, 29, 14)",
          [audit.r_min(10_000, int(p * 10_000), 0.95) for p in (0.01, 0.05, 0.10, 0.20)]
          == [299, 59, 29, 14])


def test_trust():
    p = trust.TrustParams()
    inst = trust.instantaneous_trust(0.95, 0.90, 0.80, p)
    check("Eq. (2) worked example = 0.895", abs(inst - 0.895) < 1e-12)
    t = trust.TrustTracker(p, initial=0.92)
    check("Eq. (3) worked example = 0.910", abs(t.update(0.95, 0.90, 0.80) - 0.910) < 1e-12)
    try:
        trust.TrustParams(alpha=0.5, beta=0.3, gamma=0.3)
        check("weights must sum to one", False)
    except ValueError:
        check("weights must sum to one", True)


def test_anomaly_dimension():
    rng = np.random.default_rng(0)
    p = 9
    z = rng.multivariate_normal(np.zeros(p), np.eye(p), size=4000)
    m = anomaly.fit_baseline(z, threshold_fpr=0.01, shrinkage=0.10)
    d2 = m.d2(z)
    check("E[d^2] approximates p", abs(d2.mean() - p) < 1.0, f"E[d^2]={d2.mean():.2f}, p={p}")
    check("threshold uses df = p", abs(m.d2_threshold - sps.chi2.ppf(0.99, p)) < 1e-9)
    # C1: the p = 2 threshold would be catastrophically anti-conservative
    fpr_wrong = float(1 - sps.chi2.cdf(sps.chi2.ppf(0.99, 2), p))
    check("p=2 threshold on p=9 data gives FPR > 0.4", fpr_wrong > 0.4, f"{fpr_wrong:.3f}")
    # C2: Eq. (7) saturates
    med = sps.chi2.ppf(0.5, p)
    check("printed Eq. (7) scores a median healthy asset > 0.98",
          anomaly.anomaly_likelihood(med) > 0.98, f"{anomaly.anomaly_likelihood(med):.4f}")
    check("corrected transform scores it 0.5",
          abs(anomaly.anomaly_likelihood_chi2(med, p) - 0.5) < 1e-9)
    # heterogeneous units must not break the estimator (C8)
    scale = np.array([1e3, 1e2, 1e1, 1, 1, 1, 1e-1, 1e-2, 1e-3])
    m2 = anomaly.fit_baseline(z * scale, threshold_fpr=0.01, shrinkage=0.10)
    check("scale invariance under heterogeneous units",
          abs(m2.d2(z * scale).mean() - p) < 1.0, f"E[d^2]={m2.d2(z*scale).mean():.2f}")


def test_graph_risk():
    W = np.zeros((4, 4))
    W[0, 1], W[1, 2], W[1, 3], W[2, 3] = 0.70, 0.80, 0.40, 0.60
    R = np.array([0.60, 0.10, 0.05, 0.02])
    raw = graph_risk.propagate(R, W, 0.45, normalize=False)
    check("Man-V3 Table 6 is the UN-normalised computation",
          np.allclose(raw.R_prop, [0.600, 0.289, 0.154, 0.1136], atol=1e-3)
          and abs(raw.kappa - 1.502) < 1e-3, f"kappa={raw.kappa:.4f}")
    norm = graph_risk.propagate(R, W, 0.45, normalize=True)
    check("column-normalised result differs from Table 6",
          not np.allclose(norm.R_prop, raw.R_prop, atol=1e-3),
          f"normalised kappa={norm.kappa:.4f}")
    # zero-in-degree columns stay zero
    Wn = graph_risk.column_normalize(W)
    check("zero column (in-degree 0) left at zero", np.allclose(Wn[:, 0], 0.0))
    check("non-zero columns sum to one",
          np.allclose(Wn[:, 1:].sum(axis=0), 1.0))
    # divergence must raise, not silently return
    Wc = np.array([[0.0, 1.0], [1.0, 0.0]])
    try:
        graph_risk.propagate(np.array([1.0, 1.0]), Wc, 1.5)
        check("divergent lambda raises", False)
    except ValueError:
        check("divergent lambda raises", True)
    check("local risk is multiplicative, as printed in Eq. (8)",
          abs(graph_risk.local_risk(np.array([0.8]), np.array([0.4]), np.array([0.5]))[0]
              - 0.8 * 0.6 * 0.5) < 1e-12)


def test_orchestrator():
    n_ok = orch.Node("ok", np.array([100., 100., 100.]), np.array([10., 10., 10.]), 2, 0.9)
    n_small = orch.Node("small", np.array([100., 100., 100.]), np.array([95., 95., 95.]), 2, 0.9)
    n_low = orch.Node("low", np.array([100., 100., 100.]), np.array([10., 10., 10.]), 2, 0.2)
    n_lab = orch.Node("lab", np.array([100., 100., 100.]), np.array([10., 10., 10.]), 1, 0.9)
    w = orch.Workload("w", np.array([20., 20., 20.]), security_label=2, min_host_trust=0.6)
    full = orch.Orchestrator()
    for node, why in [(n_ok, ""), (n_small, "capacity"), (n_low, "host_trust"), (n_lab, "security_label")]:
        ok, reason = full.placement_admissible(w, node)
        check(f"Eq. (13) rejects on {why or 'nothing'}", (reason == why), f"got {reason!r}")
    # vector capacity: a single tight dimension must reject
    n_net = orch.Node("net", np.array([100., 100., 25.]), np.array([0., 0., 10.]), 2, 0.9)
    check("capacity is a vector, not a scalar",
          full.placement_admissible(w, n_net)[1] == "capacity")
    # ablation: an unimplemented dimension cannot reject
    weak = orch.Orchestrator(constraints=("capacity",))
    check("ablated constraint cannot reject", weak.placement_admissible(w, n_low)[0])
    # hard constraint removes the candidate rather than penalising it
    acts = [orch.Action("bad", "migrate", target_node="low", overhead=np.zeros(3)),
            orch.Action("good", "rate_limit", overhead=np.zeros(3))]
    dec = full.evaluate(acts, lambda a: 0.0 if a.name == "bad" else 1.0,
                        workload=w, nodes={"low": n_low})
    check("inadmissible candidate is removed, not penalised",
          dec.action.name == "good" and dec.rejected == {"bad": "host_trust"})


def test_resilience():
    t = np.arange(0, 601, 1.0)
    A = np.ones_like(t); A[100:200] = 0.4
    rt = resilience.recovery_time(t, A, 100.0, 0.95, 30.0)
    check("Eq. (15) finds the restoration instant", abs(rt - 100.0) < 1.5, f"{rt}")
    A2 = np.ones_like(t); A2[100:] = 0.4
    check("no restoration -> NaN (censored, not zero)",
          np.isnan(resilience.recovery_time(t, A2, 100.0, 0.95, 30.0)))
    check("NRI of a perfect trace is 1", abs(resilience.nri(t, np.ones_like(t), 100, 200) - 1) < 1e-9)
    check("NRI is bounded by the trace", 0 <= resilience.nri(t, A, 100, 200) <= 1)


def test_stats():
    rng = np.random.default_rng(1)
    x = rng.normal(10, 2, 400); y = rng.normal(8, 2, 400)
    check("Hedges g recovers a known effect", abs(stats.hedges_g(x, y) - 1.0) < 0.2,
          f"{stats.hedges_g(x, y):.3f}")
    check("Cliff delta is bounded and signed", 0.4 < stats.cliffs_delta(x, y) < 0.9)
    lo, hi = stats.wilson_ci(0, 54)
    check("Wilson CI handles a zero count", lo == 0.0 and 0 < hi < 0.1, f"[{lo}, {hi:.3f}]")
    adj = stats.holm([0.01, 0.04, 0.03], ["a", "b", "c"])
    check("Holm is monotone and >= raw",
          adj["a"] >= 0.01 and adj["b"] >= adj["c"] >= adj["a"])
    check("bootstrap CI brackets the mean",
          (lambda ci: ci[0] < x.mean() < ci[1])(stats.bootstrap_ci(x, boot=2000)))
    check("paired test on identical vectors is not significant",
          stats.paired_test(x, x)["p"] == 1.0)


def main():
    for fn in (test_audit, test_trust, test_anomaly_dimension, test_graph_risk,
               test_orchestrator, test_resilience, test_stats):
        print(f"\n{fn.__name__}:")
        fn()
    print()
    if FAILED:
        print(f"FAILED: {len(FAILED)} check(s): {FAILED}")
        return 1
    print("all unit checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
