"""The command-line interface and the figure generator."""

import json
import os

import pytest

from evoproto import cli, figures


def test_info_command_reports_the_pre_registered_constants(tmp_path, capsys):
    assert cli.main(["info"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["retrieval_weights_eq8"] == {"w_F": 0.4, "w_M": 0.3, "w_C": 0.15, "w_U": 0.4}
    assert payload["transfer_weights_eq9"] == {"alpha": 0.35, "beta": 0.35, "gamma": 0.30}
    assert payload["gate_thresholds_eq14"]["tau_U"] == 0.5
    assert "blake2b" in payload["seed_derivation"]
    assert payload["mode"].startswith("SYNTHETIC")


def test_dry_run_command_writes_json(tmp_path):
    out = tmp_path / "dry-run.json"
    assert cli.main(["dry-run", "--replicates", "3", "--population", "12",
                     "--generations", "4", "--out", str(out)]) == 0
    payload = json.loads(out.read_text())
    assert len(payload["cells"]) == 9
    assert payload["tag"] == "SYNTHETIC"


def test_case_study_command_prints_a_decision(capsys):
    assert cli.main(["case-study", "--population", "16", "--generations", "6"]) == 0
    output = capsys.readouterr().out
    assert "traceability chain" in output
    assert any(word in output for word in ("RECOMMEND", "ABSTAIN", "REJECT"))
    assert "engineer approval" in output


def test_verify_dois_offline_lists_every_reference(capsys):
    assert cli.main(["verify-dois"]) == 0
    output = capsys.readouterr().out
    assert "references" in output
    assert "would query CrossRef" in output


def test_every_figure_of_the_paper_is_generated(tmp_path):
    assert set(figures.FIGURES) == {
        "fig1_architecture", "fig2_kg_schema", "fig3_phylogenetic_context",
        "fig4_traceability_chain", "fig5_case_study", "fig6_experimental_design",
        "fig7_dry_run", "fig8_decision_map",
    }
    path = figures.generate("fig2_kg_schema", outdir=str(tmp_path))
    assert os.path.getsize(path) > 1000


def test_unknown_figure_is_refused(tmp_path):
    with pytest.raises(KeyError):
        figures.generate("fig9_does_not_exist", outdir=str(tmp_path))
