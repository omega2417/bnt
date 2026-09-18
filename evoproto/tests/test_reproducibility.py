"""End-to-end reproducibility guarantees and the CLI (Section 5, Section 7.8)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from evoproto import __version__
from evoproto.cli import main as cli_main
from evoproto.data import Tag
from evoproto.experiment import run_cell, run_protocol


def test_two_runs_of_the_protocol_agree_exactly():
    first = run_protocol(replicates=3, population=16, generations=5, n_resamples=100)
    second = run_protocol(replicates=3, population=16, generations=5, n_resamples=100)
    assert [c.metrics for c in first.cells] == [c.metrics for c in second.cells]
    assert first.statistics["T1"][0]["p_value"] == second.statistics["T1"][0]["p_value"]


def test_every_result_carries_a_provenance_tag():
    result = run_protocol(replicates=2, population=12, generations=4, n_resamples=100)
    assert all(cell.tag == Tag.SYNTHETIC.value for cell in result.cells)
    assert result.configuration["provenance_tag"] == Tag.SYNTHETIC.value
    assert result.configuration["specification"]["provenance_tag"] == Tag.MODELED.value


def test_environment_is_recorded_with_the_results():
    result = run_protocol(replicates=2, population=12, generations=4, n_resamples=100)
    assert result.environment["evoproto"] == __version__
    assert result.environment["python"]


def test_cell_metrics_are_finite_and_in_range():
    cell = run_cell("T1", "C", 0, population=16, generations=5)
    assert 0.0 <= cell.metrics["FSR"] <= 1.0
    assert 0.0 <= cell.metrics["HV"] <= 1.0
    assert 0.0 <= cell.metrics["D"] <= 1.0
    assert 1 <= cell.metrics["ITS"] <= 5


def test_cli_dryrun_writes_results(tmp_path):
    code = cli_main(["dryrun", "--replicates", "3", "--population", "12",
                     "--generations", "4", "--output", str(tmp_path)])
    assert code == 0
    payload = json.loads((tmp_path / "results.json").read_text())
    assert len(payload["cells"]) == 9
    assert (tmp_path / "cells.csv").exists()


def test_cli_demo_and_env_run():
    assert cli_main(["demo"]) == 0
    assert cli_main(["env"]) == 0


def test_cli_verify_dois_offline():
    references = Path(__file__).resolve().parents[1] / "docs/references/references.json"
    if not references.exists():                    # not shipped in the wheel
        pytest.skip("reference list not available")
    assert cli_main(["verify-dois", "--offline", "--references", str(references)]) == 0


def test_package_is_importable_as_a_module_entry_point():
    completed = subprocess.run(
        [sys.executable, "-m", "evoproto.cli", "env"],
        capture_output=True, text=True, check=False,
    )
    assert completed.returncode == 0
    assert "evoproto" in completed.stdout
