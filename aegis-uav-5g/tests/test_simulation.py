"""Tests for the simulator, attack engine and determinism."""

from __future__ import annotations

import numpy as np

from aegis_uav.config import load_attack
from aegis_uav.schemas import AttackConfig
from aegis_uav.simulation.scenario_engine import simulate_mission


def test_benign_mission_has_no_attacks(tiny_scenario):
    m = simulate_mission(tiny_scenario, None, seed=0, mission_index=0)
    assert not m.frame["is_attack"].any()
    assert (m.frame["attack_label"] == "benign").all()
    assert m.attack_label == "benign"


def test_mission_is_deterministic(tiny_scenario):
    a = simulate_mission(tiny_scenario, None, seed=3, mission_index=1)
    b = simulate_mission(tiny_scenario, None, seed=3, mission_index=1)
    assert np.allclose(a.frame["packets_per_second"], b.frame["packets_per_second"])


def test_different_seeds_differ(tiny_scenario):
    a = simulate_mission(tiny_scenario, None, seed=1, mission_index=0)
    b = simulate_mission(tiny_scenario, None, seed=2, mission_index=0)
    assert not np.allclose(a.frame["packets_per_second"], b.frame["packets_per_second"])


def test_gps_spoofing_increases_disagreement(tiny_scenario):
    attack = AttackConfig(id="T1", onset_s=10, duration_s=30, intensity=0.7,
                          target_uavs=[1], profile="sudden")
    m = simulate_mission(tiny_scenario, attack, seed=0, mission_index=0)
    tgt = m.frame[m.frame["uav_index"] == 1]
    att = tgt[tgt["is_attack"]]
    ben = tgt[~tgt["is_attack"]]
    dis_att = np.hypot(att["position_x"] - att["gnss_reported_x"],
                       att["position_y"] - att["gnss_reported_y"]).mean()
    dis_ben = np.hypot(ben["position_x"] - ben["gnss_reported_x"],
                       ben["position_y"] - ben["gnss_reported_y"]).mean()
    assert dis_att > 5 * dis_ben


def test_dos_increases_packet_rate(tiny_scenario):
    attack = AttackConfig(id="T3", onset_s=10, duration_s=30, intensity=0.8,
                          target_uavs=[0], profile="sudden")
    m = simulate_mission(tiny_scenario, attack, seed=0, mission_index=0)
    tgt = m.frame[m.frame["uav_index"] == 0]
    assert tgt[tgt["is_attack"]]["packets_per_second"].mean() > \
        tgt[~tgt["is_attack"]]["packets_per_second"].mean()


def test_all_attack_configs_load():
    for tid in ("T1", "T2", "T3", "T4", "T5", "T6"):
        a = load_attack(f"configs/attacks/{tid}.yaml")
        assert a.id == tid
        assert a.enabled
