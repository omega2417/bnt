"""Software acceptance checks required before any hardware run (protocol 18.3)."""
import numpy as np
import pytest

from dtpower import bench, config, energy_sim, profiles, scenarios, sizing, stats
from dtpower.config import ConfigError, validate_run_config
from dtpower.edge_guard import EdgeGuard
from dtpower.forecast import CausalGenForecaster
from dtpower.twin import DataValidator

CFG = config.load("article_scenarios.json")
HW = config.load("hardware_bench_12v.json")
PC = config.load("policies.json")


def test_integral_10w_1h_is_10wh():
    r = energy_sim.simulate(np.zeros(3600), np.full(3600, 10.0), np.zeros(3600), e_eff_wh=1000, eta_dc=1, eta_ch=1,
                            eta_dis=1, soc0=0.5, soc_min=0, step_h=1 / 3600)
    assert (0.5 - r.soc[-1]) * 1000 == pytest.approx(10.0, rel=1e-9)


def test_sign_convention_discharge_positive():
    from dtpower.battery import BatteryPlant, draw_truth
    p = BatteryPlant(draw_truth(HW, np.random.default_rng(0)), z=0.5)
    i, _ = p.solve_current(+50.0)
    assert i > 0
    z0 = p.z
    p.step(i, 60)
    assert p.z < z0


def test_clipping_cannot_create_energy_and_unserved_is_booked():
    r = energy_sim.simulate(np.zeros(10), np.full(10, 100.0), np.zeros(10), e_eff_wh=100, eta_dc=1, eta_ch=1, eta_dis=1,
                            soc0=0.3, soc_min=0.15)
    m = r.metrics()
    assert r.soc.min() >= 0.15 - 1e-12
    assert m["e_unserved_bus_wh"] == pytest.approx(1000 - 15, rel=1e-9)


def test_curtailment_booked_when_full():
    r = energy_sim.simulate(np.full(5, 100.0), np.zeros(5), np.zeros(5), e_eff_wh=100, eta_dc=1, eta_ch=1, eta_dis=1, soc0=1.0)
    assert r.metrics()["e_curtailed_wh"] == pytest.approx(500)


def test_night_generation_is_zero():
    a = profiles.pv_shape()
    assert a[:6].sum() == 0 and a[16:].sum() == 0 and a.sum() == pytest.approx(1)


def test_article_sizing_reproduced():
    s1 = sizing.size_scenario(CFG["scenarios"]["S1"], CFG["common"])
    s3 = sizing.size_scenario(CFG["scenarios"]["S3"], CFG["common"])
    assert s1["e_batt_req"] == pytest.approx(1772.9, abs=0.1)
    assert s1["c_ah"] == pytest.approx(147.7, abs=0.1)
    assert s3["e_batt_req"] == pytest.approx(7991.4, abs=0.1)
    assert s1["p_pv"] == pytest.approx(604.4, abs=0.1)


def _eg():
    g = EdgeGuard("R", "B", "sil", 0.0, 0.015)
    g.self_test()
    g.start(0)
    return g


BASE = {"schema_version": "1.0", "mode": "sil", "source": "ems", "run_id": "R", "boot_id_target": "B"}


def test_stale_command_rejected():
    g = _eg()
    ack = g.handle_command(10.0, {**BASE, "command_id": "x", "action": "SET_AUX_ON", "expires_at_utc": 9.0})
    assert not ack["accepted"] and ack["reject_reason"] == "expired" and not g.aux_out


def test_duplicate_is_idempotent():
    g = _eg()
    g.handle_command(1, {**BASE, "command_id": "a", "action": "SET_AUX_ON", "expires_at_utc": 3})
    n = len(g.log)
    ack = g.handle_command(1.2, {**BASE, "command_id": "a", "action": "SET_AUX_ON", "expires_at_utc": 3})
    assert ack["duplicate"] and len(g.log) == n


def test_restart_new_boot_rejects_old_commands():
    g = EdgeGuard("R", "B2", "sil", 0, 0.015)
    g.self_test()
    g.start(0)
    ack = g.handle_command(1, {**BASE, "command_id": "a", "action": "SET_AUX_ON", "expires_at_utc": 3})
    assert not ack["accepted"] and ack["reject_reason"] == "boot_id"


def test_forecaster_has_no_future_access():
    f = CausalGenForecaster()
    assert not hasattr(f, "profile")
    for _ in range(120):
        f.observe(40.0)
    assert np.allclose(f.forecast(10), 40.0)


def test_validator_flags_faults():
    v = DataValidator()
    good = {"seq": 1, "v_batt_v": 13.2, "i_batt_a": 1.0, "p_gen_bus_w": 10, "p_crit_bus_w": 20, "p_aux_bus_w": 3.55,
            "temp_batt_c": 22}
    assert v.check(dict(good))[0]
    assert v.check({**good, "v_batt_v": 99})[1] == "impossible_voltage"
    assert v.check({**good, "p_gen_bus_w": None})[1].startswith("missing")


def test_config_validation():
    with pytest.raises(ConfigError):
        validate_run_config({"mode": "physical", "acceleration": 60})
    with pytest.raises(ConfigError):
        validate_run_config({"mode": "sil", "control": {"aux_off_soc": 0.4, "aux_on_soc": 0.3}})
    with pytest.raises(ConfigError):
        validate_run_config({"mode": "physical", "battery": {}})


def test_sign_flip_exact_and_holm():
    assert stats.sign_flip_p([1, 1, 1, 1, 1]) == pytest.approx(2 / 32)
    h = stats.holm({"a": 0.01, "b": 0.04})
    assert h["a"] == pytest.approx(0.02) and h["b"] == pytest.approx(0.04)


def test_short_bench_run_end_to_end():
    inst, cal, cap = bench.build_bench(HW, 3)
    assert all(c["pass_current"] for c in cal.values())
    sc = scenarios.e02()
    m = bench.run(inst, sc, "C0", PC, seed=1, keep_series=False)
    assert m["commands_accepted"] == m["commands_effect_confirmed"] >= 3
    assert m["coverage_pct"] > 99 and m["mae_soc_pp"] < 3
