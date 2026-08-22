"""The schedule and the workload traces: determinism and pairing."""

import pytest

from alp import config
from alp.schedule import build_schedule
from alp.traces import TraceSpec, build_trace, build_all_traces, trace_sha256


def test_schedule_size_matches_equation_one():
    schedule = build_schedule("full")
    assert len(schedule) == 750
    assert schedule.run_id.is_unique
    assert set(schedule.config) == set(config.CONFIGS)
    assert set(schedule.topology) == set(config.TOPOLOGIES)


def test_schedule_is_deterministic():
    assert build_schedule("full").equals(build_schedule("full"))


def test_schedule_covers_every_cell_exactly_once_per_repeat():
    schedule = build_schedule("demo")
    counts = schedule.groupby(["config", "topology", "load_tps"]).size()
    assert set(counts.unique()) == {config.DEMO.repeats}


def test_configurations_are_randomised_inside_each_block():
    schedule = build_schedule("full")
    # Within a topology x load block the configuration order must not be the
    # plain product order; otherwise time-of-day confounds the comparison.
    block = schedule[schedule.block == schedule.block.iloc[0]]
    assert list(block.config) != sorted(block.config)


def test_the_design_is_paired_by_trace_id():
    schedule = build_schedule("demo")
    for (topology, load, repeat), group in schedule.groupby(
        ["topology", "load_tps", "repeat"]
    ):
        assert group.trace_id.nunique() == 1, "one trace per stratum"
        assert set(group.config) == set(config.DEMO.configs)


def test_trace_is_deterministic_and_exact_in_size():
    spec = TraceSpec(100, 3, 300)
    a, b = build_trace(spec), build_trace(spec)
    assert trace_sha256(a) == trace_sha256(b)
    assert len(a) == 100 * 300


def test_trace_keys_never_collide_between_clients():
    trace = build_trace(TraceSpec(50, 1, 60))
    per_client = trace.groupby("client_id").key_hex.nunique()
    assert set(per_client.unique()) == {1}
    assert trace.key_hex.nunique() == trace.client_id.nunique()


def test_sequence_numbers_are_monotonic_per_key():
    trace = build_trace(TraceSpec(50, 1, 60))
    for _, group in trace.groupby("key_hex"):
        seq = group.seq.tolist()
        assert seq == sorted(seq) and len(set(seq)) == len(seq)


def test_arrivals_stay_inside_the_window():
    trace = build_trace(TraceSpec(200, 5, 120))
    assert trace.t_offset_s.min() >= 0
    assert trace.t_offset_s.max() <= 120 + 1e-9


def test_trace_registry_covers_every_load_and_repeat():
    registry = build_all_traces(config.DEMO)
    assert len(registry) == len(config.DEMO.loads_tps) * config.DEMO.repeats
    assert registry.sha256.is_unique
