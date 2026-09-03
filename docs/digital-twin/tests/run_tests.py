#!/usr/bin/env python3
"""Zero-dependency test suite for the UMSF digital twin.

Run with ``python3 tests/run_tests.py`` (or ``make test``). The suite covers
the eight families required by Appendix G: unit, property, contract,
determinism, safety, integration, calibration and performance.
"""

from __future__ import annotations

import json
import random
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from umsf_twin.adapters.bms_mqtt import parse_bms_payload
from umsf_twin.core.bus import EventBus
from umsf_twin.core.clock import Phase
from umsf_twin.core.contracts import TELEMETRY_FIELDS, validate_record, validate_strict_json
from umsf_twin.core.errors import (ContractError, InvariantViolation,
                                   ParameterError, SafetyViolation)
from umsf_twin.core.events import ScenarioEvent
from umsf_twin.core.parameters import Parameter, ParameterRegistry
from umsf_twin.core.provenance import canonical_hash
from umsf_twin.core.rng import RngHub, derived_seed
from umsf_twin.core.safety import SafetyPolicy
from umsf_twin.experiment.calibration import abc_rejection, fidelity, nelder_mead
from umsf_twin.experiment.doe import Factor, design_matrix, to_overrides
from umsf_twin.experiment.metrics import detection_metrics
from umsf_twin.experiment.montecarlo import rare_event_probability, run_monte_carlo
from umsf_twin.experiment.runner import run_experiment, run_replicate
from umsf_twin.experiment.scenario import load_scenario
from umsf_twin.experiment.stats import mcnemar, mean_ci, wilson_interval
from umsf_twin.federates.detection.rules import RuleEngine
from umsf_twin.federates.network.queue import FluidQueue
from umsf_twin.federates.network.router import MultiWanRouter
from umsf_twin.federates.network.wan import WanLink
from umsf_twin.federates.power.load_manager import LoadManager
from umsf_twin.federates.power.pack import BatteryPack, solve_discharge_current
from umsf_twin.federates.threats.kill_chain import KillChain
from umsf_twin.federates.wifi.ap import AccessPoint
from umsf_twin.pipelines.labeling import label_rows
from umsf_twin.pipelines.validation import DEFAULT_GATES, run_gates

CONFIG = ROOT / "umsf_twin" / "config" / "inventory" / "demo.json"
SHORT = {"duration_s": 180, "events": [
    {"event_id": "e-wan", "type": "wan_down", "start_s": 30, "end_s": 90,
     "targets": ["site_a"], "params": {"link_id": "A-WAN-1"}},
    {"event_id": "e-recon", "type": "recon_burst", "start_s": 60, "end_s": 120,
     "targets": ["site_b"], "params": {"scan_rate_pps": 24}},
    {"event_id": "e-gap", "type": "telemetry_loss", "start_s": 100, "end_s": 130,
     "targets": ["site_a"], "params": {}},
    {"event_id": "e-mains", "type": "mains_loss", "start_s": 40, "end_s": 150,
     "targets": ["site_a"], "params": {}},
]}

TESTS: list = []


def test(family: str):
    def decorator(function):
        TESTS.append((family, function.__name__, function))
        return function
    return decorator


def short_scenario(**overrides):
    payload = dict(SHORT)
    payload.update(overrides)
    return load_scenario(CONFIG, overrides=payload)


# --------------------------------------------------------------- unit ----
@test("unit")
def test_queue_conservation():
    queue = FluidQueue()
    out = queue.step(offered_mbps=800.0, capacity_mbps=1000.0, dt_s=1.0)
    assert abs(out["throughput_mbps"] - 800.0) < 1e-6, out
    assert out["queue_delay_ms"] == 0.0
    out = queue.step(offered_mbps=2000.0, capacity_mbps=1000.0, dt_s=1.0)
    assert out["throughput_mbps"] <= 1000.0 + 1e-9
    assert out["queue_delay_ms"] > 0.0
    assert queue.backlog_mb > 0.0


@test("unit")
def test_zero_capacity_marks_path_unavailable():
    out = FluidQueue().step(500.0, 0.0, 1.0)
    assert out["path_available"] is False and out["throughput_mbps"] == 0.0


@test("unit")
def test_constant_power_solution():
    ocv, resistance, power = 51.2, 0.09, 240.0
    current = solve_discharge_current(power, ocv, resistance)
    assert current is not None
    terminal = ocv - current * resistance
    assert abs(terminal * current - power) < 1e-6
    assert solve_discharge_current(1e7, ocv, resistance) is None


@test("unit")
def test_ap_capacity_uses_unknown_uplink_flag():
    known = AccessPoint("A-1", "site_a", uplink_mbps=1000.0)
    unknown = AccessPoint("A-2", "site_a")
    rng = random.Random(0)
    assert known.step(rng, clients=10)["quality_flag"] == "OK"
    assert unknown.step(rng, clients=10)["quality_flag"] == "UNKNOWN_UPLINK"
    assert unknown.effective_capacity_mbps() <= 100.0


@test("unit")
def test_bus_orders_by_phase_then_source():
    bus = EventBus()
    bus.publish(0, Phase.FLOWS, "z", "late")
    bus.publish(0, Phase.SCENARIO, "a", "early")
    bus.publish(0, Phase.SCENARIO, "b", "early2")
    kinds = [message.kind for message in bus.drain_until(0)]
    assert kinds == ["early", "early2", "late"], kinds


@test("unit")
def test_ramped_event_intensity():
    event = ScenarioEvent.from_dict(
        {"event_id": "e", "type": "wan_degrade", "start_s": 10, "end_s": 40,
         "targets": ["site_a"], "params": {"latency_add_ms": 100.0},
         "ramp": "linear", "ramp_s": 10}, 100)
    assert event.scaled("latency_add_ms", 10) == 0.0
    assert abs(event.scaled("latency_add_ms", 15) - 50.0) < 1e-9
    assert abs(event.scaled("latency_add_ms", 25) - 100.0) < 1e-9


# ----------------------------------------------------------- property ----
@test("property")
def test_battery_energy_monotonic_under_discharge():
    pack = BatteryPack()
    previous = pack.soc_pct
    for _ in range(120):
        pack.discharge(200.0, 1.0)
        assert pack.soc_pct <= previous + 1e-9
        previous = pack.soc_pct


@test("property")
def test_voltage_within_cell_envelope():
    pack = BatteryPack()
    for load in (0.0, 100.0, 400.0, 900.0):
        report = pack.discharge(load, 1.0)
        assert (13 * report["cell_min_v"] - 1e-9 <= report["pack_voltage_v"]
                <= 13 * report["cell_max_v"] + 1e-9), report


@test("property")
def test_charge_and_discharge_current_signs():
    pack = BatteryPack()
    discharge = pack.discharge(300.0, 1.0)
    charge = pack.charge(400.0, 1.0, 4.0, 4.25)
    assert discharge["pack_current_a"] > 0.0
    assert charge["pack_current_a"] < 0.0


@test("property")
def test_seed_streams_are_independent():
    a = derived_seed(1, 0, "network:site_a")
    b = derived_seed(1, 0, "network:site_b")
    c = derived_seed(1, 1, "network:site_a")
    assert len({a, b, c}) == 3
    hub = RngHub(42)
    assert hub.stream("x") is hub.stream("x")


@test("property")
def test_kill_chain_is_causal():
    chain = KillChain("c", "site_b")
    rng = random.Random(11)
    order = []
    for t in range(900):
        stage = chain.step(t, 1.0, rng, True)["stage"]
        if not order or order[-1] != stage:
            order.append(stage)
    assert order[0] == "DORMANT"
    assert "LATERAL" not in order or order.index("RECON") < order.index("LATERAL")


@test("property")
def test_load_shedding_order_preserves_group_one():
    manager = LoadManager()
    row = manager.update(soc_pct=18.0, autonomy_min=40.0, on_battery=True)
    assert row["shed_groups"] == [3]
    row = manager.update(soc_pct=10.0, autonomy_min=8.0, on_battery=True)
    assert row["shed_groups"] == [2, 3] and row["group1_preserved"]


# ----------------------------------------------------------- contract ----
@test("contract")
def test_record_rejects_unknown_and_missing_fields():
    row = {name: "" for name in TELEMETRY_FIELDS}
    validate_record(row, TELEMETRY_FIELDS)
    try:
        validate_record({**row, "surprise": 1}, TELEMETRY_FIELDS)
    except ContractError:
        pass
    else:
        raise AssertionError("unknown field accepted")


@test("contract")
def test_strict_json_rejects_nan():
    try:
        validate_strict_json({"x": float("nan")})
    except ContractError:
        return
    raise AssertionError("NaN accepted")


@test("contract")
def test_gap_rows_blank_measurements():
    scenario = short_scenario()
    result = run_replicate(scenario, 0, "gap-test")
    gaps = [row for row in result["rows"] if row["telemetry_gap_marker"] == 1]
    assert gaps, "expected at least one telemetry gap row"
    for row in gaps:
        assert row["rtt_ms"] == "" and row["detector_score"] == ""
        assert row["site_id"] and row["timestamp_utc"]


@test("contract")
def test_adapter_maps_vendor_payload():
    row = parse_bms_payload({"soc": 80, "soh": 95, "pack_v": 50.1, "pack_a": 3.2,
                             "temp_c": 24, "cells_v": [3.85, 3.9], "faults": []})
    assert abs(row["cell_imbalance_mv"] - 50.0) < 1e-6
    assert row["quality_flags"] == "OK"


# -------------------------------------------------------- determinism ----
@test("determinism")
def test_same_seed_same_rows():
    scenario = short_scenario()
    first = run_replicate(scenario, 0, "det")
    second = run_replicate(scenario, 0, "det")
    assert canonical_hash(first["rows"]) == canonical_hash(second["rows"])


@test("determinism")
def test_replicates_differ():
    scenario = short_scenario()
    first = run_replicate(scenario, 0, "det")
    other = run_replicate(scenario, 1, "det")
    assert canonical_hash(first["rows"]) != canonical_hash(other["rows"])


@test("determinism")
def test_config_hash_covers_event_defaults():
    a = short_scenario()
    events = json.loads(json.dumps(SHORT["events"]))
    events[1]["params"]["unique_ports"] = 999
    b = short_scenario(events=events)
    assert a.config_hash != b.config_hash


# ------------------------------------------------------------- safety ----
@test("safety")
def test_event_allowlist():
    policy = SafetyPolicy()
    try:
        policy.check_event_type("exfiltrate_real_data")
    except SafetyViolation:
        pass
    else:
        raise AssertionError("unlisted event type accepted")


@test("safety")
def test_hil_requires_approval():
    try:
        SafetyPolicy(mode="HIL").check_mode()
    except SafetyViolation:
        pass
    else:
        raise AssertionError("HIL ran without approval")


@test("safety")
def test_egress_requires_allowlist():
    try:
        SafetyPolicy(allow_external_egress=True).check_mode()
    except SafetyViolation:
        pass
    else:
        raise AssertionError("egress accepted without allowlist")


@test("safety")
def test_hil_refuses_unknown_parameters():
    registry = ParameterRegistry()
    registry.register(Parameter("vpn.mtu", "UNINVENTORIED", evidence="UNKNOWN"))
    registry.assert_mode_ready("SIM")
    try:
        registry.assert_mode_ready("HIL")
    except ParameterError:
        return
    raise AssertionError("HIL accepted an uninventoried parameter")


@test("safety")
def test_inventory_invariants_enforced():
    broken = {"sites": {"site_a": {"ap_count": 12}}}
    try:
        load_scenario(CONFIG, overrides=broken)
    except InvariantViolation:
        return
    raise AssertionError("wrong AP count accepted")


@test("safety")
def test_budget_limits():
    policy = SafetyPolicy(max_events=2)
    try:
        policy.check_budget(100, 5, 1)
    except SafetyViolation:
        return
    raise AssertionError("event budget not enforced")


# -------------------------------------------------------- integration ----
@test("integration")
def test_run_produces_valid_artifacts():
    scenario = short_scenario()
    output = Path(tempfile.mkdtemp())
    try:
        result = run_experiment(scenario, output, replicates=2, run_id="integration")
        run_dir = Path(result["run_dir"])
        for name in ("telemetry.csv", "ground_truth.csv", "summary.json",
                     "manifest.json", "parameters.json", "scenario.resolved.json"):
            assert (run_dir / name).exists(), name
        manifest = json.loads((run_dir / "manifest.json").read_text())
        assert manifest["hashes"]["config"] == scenario.config_hash
        assert manifest["artifacts"]["telemetry.csv"]["sha256"]
        assert result["summary"]["gates"]["passed"], result["summary"]["gates"]
    finally:
        shutil.rmtree(output, ignore_errors=True)


@test("integration")
def test_run_directory_is_not_overwritten():
    scenario = short_scenario()
    output = Path(tempfile.mkdtemp())
    try:
        run_experiment(scenario, output, run_id="once")
        try:
            run_experiment(scenario, output, run_id="once")
        except FileExistsError:
            return
        raise AssertionError("silent overwrite of an existing run")
    finally:
        shutil.rmtree(output, ignore_errors=True)


@test("integration")
def test_wan_failover_and_return():
    links = [WanLink.from_config(
        {"id": f"L{i}", "capacity_mbps": 1000, "base_rtt_ms": 10 + i,
         "base_loss_pct": 0.1, "priority": i}, "site_a") for i in (1, 2)]
    router = MultiWanRouter("r", "site_a", links, failover_delay_s=2, hysteresis_s=5)
    rng = random.Random(3)

    def tick(t):
        for link in links:
            link.step(t, rng, 0.3)
        return router.step(t, rng)

    for t in range(5):
        row = tick(t)
    assert row["active_wan_id"] == "L1"
    links[0].apply_scenario(down=True)
    for t in range(5, 15):
        row = tick(t)
    assert row["active_wan_id"] == "L2" and router.failover_count == 1
    links[0].apply_scenario(down=False)
    for t in range(15, 60):
        row = tick(t)
    assert row["active_wan_id"] == "L1"


@test("integration")
def test_power_outage_drives_shedding_and_recovery():
    scenario = short_scenario()
    result = run_replicate(scenario, 0, "power-test")
    states = {row["power_state_end"] for row in result["rows"]
              if row["site_id"] == "site_a"}
    assert "BATTERY" in states or "LOAD_SHED" in states, states
    transitions = [row for row in result["truth"] if row["kind"] == "transition"]
    assert transitions, "transition ground truth is empty"


@test("integration")
def test_labels_ignore_transition_truth():
    rows = [{"site_id": "site_a", "step": 5}]
    truth = [{"kind": "transition", "site_id": "site_a", "stage": "recon_burst",
              "onset_step": 0, "end_step": 10, "truth_id": "t"}]
    labeled = label_rows(rows, truth)
    assert labeled[0]["label_attack"] == 0


@test("integration")
def test_gates_detect_corrupted_data():
    scenario = short_scenario()
    result = run_replicate(scenario, 0, "gate-test")
    rows = result["rows"]
    assert run_gates(rows, DEFAULT_GATES)["passed"]
    corrupted = [dict(row) for row in rows]
    for row in corrupted:
        if row["site_id"] == "site_a" and row["pack_voltage_v"] not in ("", None):
            row["pack_voltage_v"] = 999.0
            break
    verdict = run_gates(corrupted, DEFAULT_GATES)
    assert not verdict["passed"] and "voltage_consistency" in verdict["failed_blocking"]


# -------------------------------------------------------- calibration ----
@test("calibration")
def test_fidelity_detects_distribution_shift():
    rng = random.Random(5)
    a = [rng.gauss(14, 2) for _ in range(400)]
    b = [rng.gauss(14.1, 2) for _ in range(400)]
    far = [rng.gauss(30, 2) for _ in range(400)]
    assert fidelity("rtt", a, b).passed
    assert not fidelity("rtt", a, far).passed


@test("calibration")
def test_abc_recovers_known_parameter():
    rng = random.Random(9)
    observed = {"m": [rng.gauss(5.0, 1.0) for _ in range(150)]}

    def simulate(theta):
        local = random.Random(int(theta["mu"] * 1000))
        return {"m": [local.gauss(theta["mu"], 1.0) for _ in range(150)]}

    posterior = abc_rejection(simulate, observed, {"mu": (0.0, 10.0)}, draws=250)
    assert abs(posterior["posterior"]["mu"]["mean"] - 5.0) < 1.0


@test("calibration")
def test_nelder_mead_finds_minimum():
    result = nelder_mead(lambda x: (x[0] - 2.0) ** 2 + (x[1] + 3.0) ** 2, [0.0, 0.0])
    assert abs(result["x"][0] - 2.0) < 1e-2 and abs(result["x"][1] + 3.0) < 1e-2


@test("calibration")
def test_statistics_helpers():
    interval = mean_ci([10, 11, 12, 13, 14])
    assert interval["low"] < interval["mean"] < interval["high"]
    wilson = wilson_interval(9, 10)
    assert 0.0 <= wilson["low"] <= wilson["p"] <= wilson["high"] <= 1.0
    assert mcnemar(20, 5)["p_value"] < 0.05
    rare = rare_event_probability([True, False, False, False], [0.1, 1.0, 1.0, 1.0])
    assert 0.0 < rare["probability"] < 0.05


@test("calibration")
def test_detection_metrics_arithmetic():
    rows = [{"label_attack": 1, "detector_alert": "1", "step": 1, "site_id": "a",
             "label_truth_ids": "t"},
            {"label_attack": 1, "detector_alert": "0", "step": 2, "site_id": "a",
             "label_truth_ids": "t"},
            {"label_attack": 0, "detector_alert": "1", "step": 3, "site_id": "a",
             "label_truth_ids": ""},
            {"label_attack": 0, "detector_alert": "0", "step": 4, "site_id": "a",
             "label_truth_ids": ""}]
    metrics = detection_metrics(rows)
    assert metrics["tp"] == 1 and metrics["fn"] == 1
    assert abs(metrics["precision"] - 0.5) < 1e-9


@test("calibration")
def test_doe_design_is_within_bounds():
    factors = [Factor("power.site_a.initial_soc_pct", low=30.0, high=90.0),
               Factor("sites.site_a.failover_delay_s", levels=(2, 5, 10))]
    design = design_matrix(factors, 12, "lhs", seed=3)
    assert len(design) == 12
    for setting in design:
        assert 30.0 <= setting["power.site_a.initial_soc_pct"] <= 90.0
        assert setting["sites.site_a.failover_delay_s"] in (2, 5, 10)
    nested = to_overrides(design[0])
    assert "power" in nested and "site_a" in nested["power"]


@test("calibration")
def test_monte_carlo_stops_on_target():
    scenario = short_scenario(duration_s=60, events=[])
    result = run_monte_carlo(scenario, "network.site_a.rtt_mean_ms",
                             max_replicates=6, target_half_width=1e6,
                             min_replicates=2, run_id="mc-test")
    assert result.stopped_because == "target_half_width"
    assert result.replicates >= 2


# -------------------------------------------------------- performance ----
@test("performance")
def test_step_cost_is_bounded():
    scenario = short_scenario(duration_s=300, events=[])
    started = time.perf_counter()
    result = run_replicate(scenario, 0, "perf")
    elapsed = time.perf_counter() - started
    per_step_ms = 1000.0 * elapsed / 300.0
    assert per_step_ms < 100.0, f"{per_step_ms:.1f} ms per step is too slow"
    assert len(result["rows"]) >= 600


@test("performance")
def test_rule_engine_is_cheap():
    engine = RuleEngine()
    row = {"scan_rate_pps": 20, "auth_failures": 2, "lateral_events": 0,
           "c2_beacons": 0, "rogue_ap_count": 0, "loss_pct": 0.2,
           "queue_delay_ms": 1.0}
    started = time.perf_counter()
    for _ in range(20_000):
        engine.score(row)
    assert time.perf_counter() - started < 5.0


def main() -> int:
    failures = []
    started = time.perf_counter()
    for family, name, function in TESTS:
        try:
            function()
            print(f"  ok   [{family}] {name}")
        except Exception as error:                      # noqa: BLE001 - report all
            failures.append((family, name, error))
            print(f"  FAIL [{family}] {name}: {type(error).__name__}: {error}")
    elapsed = time.perf_counter() - started
    print(f"\n{len(TESTS) - len(failures)}/{len(TESTS)} passed in {elapsed:.1f}s")
    for family, name, error in failures:
        print(f"  - [{family}] {name}: {error}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
