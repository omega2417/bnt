"""The released files are what this code produces, digit for digit."""
import csv
import json

import pytest

from recovery_evidence.claims import build_register
from recovery_evidence.conditions import get_condition, load_conditions
from recovery_evidence.experiment import SUMMARY_COLUMNS, run_condition
from recovery_evidence.integrity import read_manifest, verify


def _released_summary(released, name):
    with open(released / "logs" / name / "trace_summary.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def _fresh_summary(tmp_path, name):
    rows = run_condition(get_condition(name), tmp_path, write_logs=False)
    return [{k: str(r[k]) for k in SUMMARY_COLUMNS} for r in rows]


def test_primary_condition_regenerates_exactly(released, tmp_path):
    assert _fresh_summary(tmp_path, "C0") == _released_summary(released, "C0")


@pytest.mark.slow
@pytest.mark.parametrize("name", [c.name for c in load_conditions()[1:]])
def test_secondary_conditions_regenerate_exactly(released, tmp_path, name):
    assert _fresh_summary(tmp_path, name) == _released_summary(released, name)


def test_released_files_match_their_hashes(released):
    ok, bad, _absent = verify(released)
    assert not bad and len(ok) >= 20


def test_manifest_covers_every_condition(released):
    names = read_manifest(released)
    for c in load_conditions():
        for f in ("hidden_states.csv.gz", "notices.csv.gz", "checks.csv.gz", "verdicts.csv.gz", "trace_summary.csv"):
            assert f"logs/{c.name}/{f}" in names


def test_headline_numbers(released):
    c0 = json.loads((released / "tables" / "analysis.json").read_text())["conditions"]["C0"]
    primary = c0["contrasts"]["P3-P1:FASD"]
    assert primary["mean"] < 0 and primary["ci_high"] < 0          # H1
    assert c0["contrasts"]["P3-P1:FUSD"]["ci_high"] < 0            # no trade-off (RQ2)
    static = c0["contrasts"]["P3-P2:FASD"]
    assert static["ci_low"] < 0 < static["ci_high"]                # RQ3: interval includes zero
    assert round(c0["policies"]["P0"]["FASD_mean"], 2) == 10.15


def test_register_is_consistent_with_released_tables(released):
    rows = build_register(released)
    with open(released / "tables" / "claims_register.csv", newline="") as fh:
        assert list(csv.DictReader(fh)) == rows
    # values that do not depend on the notice streams are reproduced digit for digit
    by_q = {r["quantity"]: r["status"] for r in rows if r["location"] in ("Table 5", "Table 8")}
    for q in ("C0 P0 FASD mean", "C0 P0 FUSD mean", "C1 P1 FASD mean", "C10 P1 FASD mean",
              "C10 P3 FASD mean", "C10 P3-P1:FASD mean", "C10 P3-P1:FUSD mean"):
        assert by_q[q] == "identical", q
