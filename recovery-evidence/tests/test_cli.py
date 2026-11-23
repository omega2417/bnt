import json

from recovery_evidence.cli import main


def test_example(capsys):
    assert main(["example"]) == 0
    out = capsys.readouterr().out
    assert "P3 priorities : (16, 22, 10, 9, 30, 6, 6, 20) -> selects E" in out


def test_checks_writes_report(tmp_path, capsys):
    target = tmp_path / "control_checks.txt"
    assert main(["checks", "-o", str(target)]) == 0
    assert "27 of 27 checks passed." in target.read_text()


def test_params(capsys):
    assert main(["params"]) == 0
    doc = json.loads(capsys.readouterr().out)
    assert len(doc["conditions"]) == 13 and doc["root_entropy"] == 20261123


def test_run_analyze_hash_verify(tmp_path, capsys):
    out = str(tmp_path)
    assert main(["run", "-o", out, "-c", "C0", "-r", "6", "-j", "1"]) == 0
    assert main(["analyze", "-o", out]) == 0
    assert main(["hash", "-o", out]) == 0
    assert main(["verify", "-o", out]) == 0
    (tmp_path / "tables" / "policy_summary.csv").write_text("tampered")
    assert main(["verify", "-o", out]) == 1
