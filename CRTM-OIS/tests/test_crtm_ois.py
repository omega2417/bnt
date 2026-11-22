import math

import numpy as np
import pytest

from crtm_ois import AssessmentError, assess, bnk_pay, e1_values, five_states, level
from crtm_ois import experiments as ex
from crtm_ois.agents.blocks import build_block_team
from crtm_ois.agents.bus import MessageBus
from crtm_ois.agents.llm import OfflineAnalyst, ResilienceToolbox
from crtm_ois.core import normalize
from crtm_ois.fast import BatchEvaluator
from crtm_ois.scenarios import EXPECTED_LEVELS, compare_rule_with_table


@pytest.fixture(scope="module")
def cfg():
    return bnk_pay()


def test_level_map():
    assert [level(s) for s in (0, 0.199, 0.2, 0.4, 0.699, 0.7, 0.9, 1.0)] == [1, 1, 2, 3, 3, 4, 5, 5]


def test_normalization_matches_class_table(cfg):
    m = cfg.action("UN.S1.A1").metrics[2]          # 25 min -> 0.75 (AA)
    assert math.isclose(normalize(25, m.anchors, m.sigma), 0.75)
    m4 = cfg.action("UN.S1.A1").metrics[3]
    assert math.isclose(normalize(45, m4.anchors, m4.sigma), 0.7 + 0.2 * 15 / 45)
    # level of the score equals the tabulated class for every value of every metric
    for a in cfg.actions:
        for mm in a.metrics:
            for r in range(1, 5):
                x = mm.xi[r]
                assert level(normalize(x, mm.anchors, mm.sigma)) == r + 1


def test_reproduction_15_values(cfg):
    rep = ex.reproduction(cfg)
    assert rep["n"] == 15 and rep["n_ok"] == 15
    assert rep["enclosure"]["ok"]
    assert rep["integral_ok"]


def test_five_states(cfg):
    adq = ex.adequacy(cfg, n=20_000)
    for e, lev in EXPECTED_LEVELS.items():
        assert adq[e]["level"] == lev, e
    assert adq["_order_ok"]
    assert abs(adq["E1"]["R"] - 0.698) < 5e-4 and abs(adq["E2"]["R"] - 0.364) < 6e-4
    assert abs(adq["E3"]["R"] - 0.858) < 5e-4
    assert set(adq["E4"]["vetoed"]) == {"UN.S1.A1", "CN.S1.A1", "CN.S2.A1"}
    assert not adq["E1"]["stable_missing"]
    assert abs(adq["E5"]["R_L"] - 0.9875) < 1e-9


def test_weight_robustness_E1(cfg):
    r = assess(cfg, e1_values(), n=200_000)
    assert abs(r.P["shares"]["A"] - 0.544) < 0.005
    assert abs(r.P["mean"] - 0.696) < 5e-4 and abs(r.P["sd"] - 0.028) < 5e-4


def test_sweep_monotone_and_crossings(cfg):
    sw = ex.sweep(cfg)
    assert sw["monotone_R"] and sw["monotone_Rmin"]
    assert abs(sw["crossings"][0.4] + 0.42) < 0.01
    assert abs(sw["crossings"][0.7] - 0.005) < 0.005
    assert abs(sw["crossings"][0.9] - 0.645) < 0.01


def test_non_compensation(cfg):
    nc = ex.non_compensation(cfg)
    assert abs(nc["additive"]["action"][0] - 0.606) < 5e-4
    assert nc["hard"]["action"][0] == 0 and nc["capped"]["action"][0] == 0
    assert abs(nc["hard"]["action"][1] - 0.656) < 5e-4
    assert abs(nc["capped"]["action"][1] - 0.400) < 1e-9
    assert abs(nc["capped"]["R"][0] - 0.591) < 6e-4 and nc["capped"]["R_min"][0] == 0


@pytest.mark.parametrize("mutate,code", [
    (lambda c, x: (c.replace(theta=1.5), x), "E1"),
    (lambda c, x: (c, {**x, ("UN.S1.A1", "M2"): "abc"}), "E2"),
    (lambda c, x: (c, {**x, ("UN.S1.A1", "M1"): None}), "E3"),
    (lambda c, x: (c, {**x, ("TR.S1.A1", "M1"): None, ("TR.S1.A1", "M2"): None}), "E4"),
])
def test_failure_codes(cfg, mutate, code):
    c, x = mutate(cfg, e1_values())
    with pytest.raises(AssessmentError) as ei:
        assess(c, x, robust=False)
    assert ei.value.code == code


def test_trace_contains_all_buses(cfg):
    r = assess(cfg, e1_values(), n=1000)
    assert [t["bus"] for t in r.trace.records] == ["C", "X", "XiWK", "O", "M", "A", "G", "R", "P", "C"]
    assert r.trace.config_version == cfg.version


def test_batch_evaluator_equals_reference(cfg):
    be = BatchEvaluator(cfg)
    st = five_states(cfg)
    X, M = be.to_matrix(list(st.values()))
    out = be.evaluate(X, M)
    ref = [assess(cfg, s, robust=False).R for s in st.values()]
    assert np.allclose(out["R"], [r["R"] for r in ref], atol=1e-12)
    assert np.allclose(out["R_L"], [r["R_L"] for r in ref], atol=1e-12)


def test_rule_vs_published_table(cfg):
    d = compare_rule_with_table(cfg)
    assert {(x["state"], x["metric"]) for x in d} == {("E2", "M3"), ("E2", "M4")}


def test_agent_team_equals_control_unit(cfg):
    bus = MessageBus()
    reports = []
    bus.subscribe("report", lambda m: reports.append(m.payload))
    _, cu, _ = build_block_team(bus, cfg, mc_samples=2000)
    for e, x in five_states(cfg).items():
        cu.start(x)
        assert math.isclose(reports[-1]["R"], assess(cfg, x, robust=False).R["R"], abs_tol=1e-12)
    bad = {**e1_values(), ("UN.S1.A1", "M1"): None}
    c = cu.start(bad)
    assert cu.failures[c]["status"] == "E3"
    assert len(reports) == 5


def test_toolbox_and_offline_analyst(cfg):
    tb = ResilienceToolbox(cfg, mc_samples=2000)
    v = tb.assess_current()
    assert v["level"] == "A" and v["stable_wrt_missing_data"] is False
    w = tb.what_if("CN.S1.A1", "AM-DA-1", 90)
    assert "CN.S2.A1.AM-DA-1" in w["shared_with"]
    assert "Вердикт" in OfflineAnalyst(tb).report("E2")
    assert {s["name"] for s in tb.schemas()} == set(tb.TOOL_SPECS)


def test_monotone_surrogate_has_no_violations(cfg):
    from crtm_ois.neural.models import NeuralSurrogate
    s = NeuralSurrogate(cfg, hidden=(16,), monotone=True).fit(n=3000, epochs=15)
    assert s.monotonicity_violations(n=500) == 0.0
