"""Tests for the five agents and the RSA utility/safety logic."""

from __future__ import annotations

from aegis_uav.agents.pea import PolicyEnforcementAgent
from aegis_uav.agents.rsa import RESPONSES, ResponseSelectionAgent
from aegis_uav.schemas import PEAConfig, RSAConfig


def test_rsa_escalates_below_confidence_floor():
    rsa = ResponseSelectionAgent(RSAConfig(pi_min=0.6))
    out = rsa.select("T3", confidence=0.4)
    assert out["selected"] == "escalate"
    assert out["reason"] == "below_confidence_floor"


def test_rsa_selects_utility_maximiser():
    rsa = ResponseSelectionAgent(RSAConfig(pi_min=0.5))
    out = rsa.select("T3", confidence=0.9)
    assert out["selected"] in RESPONSES
    utils = {r: t["utility"] for r, t in out["utility_terms"].items()}
    assert out["selected"] == max(utils, key=utils.get)
    assert out["runner_up"] != out["selected"]


def test_rsa_safe_mask_removes_forbidden():
    rsa = ResponseSelectionAgent(RSAConfig())
    masked = rsa.safe_actions("T3", use_mask=True)
    unmasked = rsa.safe_actions("T3", use_mask=False)
    assert set(masked).issubset(set(unmasked))


def test_pea_escalate_is_noop_success():
    pea = PolicyEnforcementAgent(PEAConfig(), seed=0)
    r = pea.enforce("escalate", "INC-1")
    assert r["status"] == "escalation"
    assert r["post_condition_ok"]


def test_pea_reports_latency_and_status():
    pea = PolicyEnforcementAgent(PEAConfig(max_retries=1), seed=0)
    r = pea.enforce("traffic_isolation", "INC-2")
    assert r["status"] in {"success", "escalation"}
    assert r["latency_ms"] > 0


def test_ada_and_tca_pipeline(tiny_scenario, ada_cfg):
    from aegis_uav.agents.ada import AnomalyDetectionAgent
    from aegis_uav.agents.tca import ThreatCorrelationAgent
    from aegis_uav.features.pipeline import FeaturePipeline, build_windows
    from aegis_uav.schemas import AttackConfig, TCAConfig
    from aegis_uav.simulation.scenario_engine import simulate_mission

    train = [simulate_mission(tiny_scenario, None, seed=s, mission_index=s, split="train")
             for s in range(2)]
    test = [simulate_mission(tiny_scenario, AttackConfig(id="T3", onset_s=10, duration_s=30,
                                                         intensity=0.9, target_uavs=[0]),
                             seed=9, mission_index=9, split="test")]
    tr = build_windows(train, tiny_scenario, ada_cfg)
    te = build_windows(test, tiny_scenario, ada_cfg)
    pipe = FeaturePipeline().fit(tr, benign_only=True)
    ada = AnomalyDetectionAgent(ada_cfg, seed=0).fit(tr, pipe)
    det = ada.detect(te)
    assert {"tel_score", "net_score", "beh_score", "any_flag"}.issubset(det.columns)
    assert det["net_score"].max() >= det["net_score"].min()
    tca = ThreatCorrelationAgent(TCAConfig(severity_floor=0.2, min_peak_severity=0.5))
    incidents = tca.correlate(det)
    for inc in incidents:
        assert 0.0 <= inc.fused_score <= 1.0
        assert inc.affected_entities
