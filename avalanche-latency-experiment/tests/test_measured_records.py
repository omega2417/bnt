"""The analysis must not care where a record came from.

These tests feed the pipeline hand-built ``MEASURED`` records — the shape
``alp.client`` writes in the field — and check that every downstream stage
behaves exactly as it does on reference-model output.
"""

import gzip
import json

import numpy as np
import pandas as pd
import pytest

from alp import analyze
from alp.config import POLL_S


def make_measured_run(run_id, config_name, n=400, base_ms=300.0, spread_ms=40.0,
                      seed=0):
    """A minimal but complete MEASURED run in the campaign schema."""
    rng = np.random.default_rng(seed)
    t_send = np.arange(n, dtype=np.int64) * 50_000_000  # 20 tx/s
    visible = base_ms + rng.exponential(spread_ms, n)
    t_receipt = t_send + ((visible - 20.0) * 1e6).astype(np.int64)
    t_r1 = t_send + (visible * 1e6).astype(np.int64)
    t_r2 = t_r1 + int(POLL_S * 1e9)
    return pd.DataFrame(
        {
            "run_id": run_id,
            "config": config_name,
            "topology": "T1_vpn",
            "load_tps": 20,
            "repeat": 1,
            "trace_id": "L20-R01",
            "client_id": "K00",
            "account_token": "0f0f0f0f",
            "seq": np.arange(1, n + 1),
            "key_hex": "0x" + "ab" * 32,
            "tx_hash": "0x" + "cd" * 32,
            "t_send_ns": t_send,
            "t_hash_ns": t_send + 1_000_000,
            "t_receipt_ns": t_receipt,
            "t_read_R1_ns": t_r1,
            "t_read_R2_ns": t_r2,
            "t_visible_first_ms": (np.minimum(t_r1, t_r2) - t_send) / 1e6,
            "t_visible_all_ms": (np.maximum(t_r1, t_r2) - t_send) / 1e6,
            "t_convergence_ms": np.abs(t_r2 - t_r1) / 1e6,
            "block_number": np.arange(n) // 8,
            "block_time_ms": (np.arange(n) // 8) * 500.0,
            "status": "success",
            "error_class": "",
            "payload_bytes": 132,
            "gas_used": 46_000,
            "provenance": "MEASURED",
        }
    )


def write_run(root, records):
    (root / "tx").mkdir(parents=True, exist_ok=True)
    path = root / "tx" / f"{records.run_id.iloc[0]}.jsonl.gz"
    with gzip.open(path, "wt", encoding="utf-8") as fh:
        for row in records.to_dict(orient="records"):
            fh.write(json.dumps(row) + "\n")
    return path


def test_summarize_run_handles_measured_records():
    records = make_measured_run("RUN-9001", "C3")
    row = analyze.summarize_run(records)
    assert row["provenance"] == "MEASURED"
    assert row["availability_pct"] == pytest.approx(100.0)
    assert row["consistency_pct"] == pytest.approx(100.0)
    assert row["p50_ms"] < row["p95_ms"] < row["p99_ms"]
    # The block series is absent here, so the interval comes from the records.
    assert row["observed_block_interval_ms"] == pytest.approx(500.0)


def test_read_mismatch_counts_against_consistency():
    records = make_measured_run("RUN-9002", "C3")
    records.loc[:9, "error_class"] = "read_mismatch"
    row = analyze.summarize_run(records)
    assert row["consistency_pct"] == pytest.approx(100.0 * (400 - 10) / 400)


def test_timeouts_stay_in_the_denominator():
    records = make_measured_run("RUN-9003", "C3")
    records.loc[:19, "status"] = "timeout"
    row = analyze.summarize_run(records)
    assert row["n_submitted"] == 400
    assert row["n_success"] == 380
    assert row["availability_pct"] == pytest.approx(95.0)
    assert row["availability_pct"] < 99.5  # fails the pre-registered rule


def test_measured_dataset_flows_through_the_whole_pipeline(tmp_path):
    for repeat, (name, base) in enumerate(
        [("C0", 900.0), ("C3", 380.0)], start=1
    ):
        for r in range(1, 4):
            records = make_measured_run(f"RUN-90{repeat}{r}", name, base_ms=base,
                                        seed=repeat * 10 + r)
            records["repeat"] = r
            records["trace_id"] = f"L20-R0{r}"
            write_run(tmp_path, records)

    assert analyze.dataset_provenance(tmp_path) == "MEASURED"
    summary = analyze.summarize_dataset(tmp_path, progress=False)
    assert len(summary) == 6

    effects = analyze.all_effects(summary, metrics=("p99_ms",))
    assert len(effects) == 1
    row = effects.iloc[0]
    assert row.profile == "C3" and row.baseline == "C0"
    assert row.delta_improvement_ms > 0
    assert row.n_pairs == 3


def test_mixed_provenance_is_reported_not_guessed(tmp_path):
    write_run(tmp_path, make_measured_run("RUN-9101", "C3"))
    simulated = make_measured_run("RUN-9102", "C3")
    simulated["provenance"] = "SIMULATED"
    write_run(tmp_path, simulated)
    label = analyze.dataset_provenance(tmp_path)
    assert label.startswith("MIXED(")
    assert "MEASURED" in label and "SIMULATED" in label
