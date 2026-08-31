"""CLI surface and the claims-boundary banner."""

import json

import pytest

from acp_sme.cli import build_parser, main


def test_selftest_passes():
    assert main(["selftest"]) == 0


def test_selftest_prints_the_claims_boundary(capsys):
    main(["selftest"])
    out = capsys.readouterr().out
    assert "synthetic model output only" in out
    assert "do not demonstrate" in out


def test_demo_runs_end_to_end(capsys):
    assert main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "REJECTED" in out          # guard fails closed
    assert "BLOCKED" in out           # role separation holds
    assert "chain verifies: True" in out


def test_params_dump_is_valid_json(capsys):
    main(["params"])
    payload = json.loads(capsys.readouterr().out)
    assert len(payload["capabilities"]) == 14
    assert len(payload["archetypes"]) == 3
    assert payload["simulation"]["primary_seed"] == 27012026
    assert payload["packs"]["capability"]


def test_experiment_writes_its_outputs(tmp_path, capsys):
    assert main(["experiment", "-r", "2", "-o", str(tmp_path)]) == 0
    assert (tmp_path / "trace_outcomes.csv").exists()
    summary = json.loads((tmp_path / "primary_summary.json").read_text())
    assert summary["design"]["traces"] == 6


def test_sensitivity_writes_its_grid(tmp_path):
    assert main(["sensitivity", "-r", "1", "-o", str(tmp_path)]) == 0
    text = (tmp_path / "sensitivity.csv").read_text()
    assert "budget_factor" in text and "expected_false_alerts" in text


def test_reproduce_without_figures(tmp_path):
    assert main(["reproduce", "-r", "2", "-o", str(tmp_path), "--no-figures"]) == 0
    for name in ("trace_outcomes.csv", "primary_summary.json", "sensitivity.csv",
                 "run_environment.json"):
        assert (tmp_path / name).exists()


def test_unknown_command_is_rejected():
    with pytest.raises(SystemExit):
        build_parser().parse_args(["nope"])
