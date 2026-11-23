"""Sections 4.5-4.6: the analysis is independent of the simulator and deterministic."""
import ast
from pathlib import Path

import numpy as np
import pytest

import recovery_evidence.analysis as analysis
from recovery_evidence.conditions import get_condition
from recovery_evidence.experiment import run_experiment


def test_analysis_does_not_import_the_simulator():
    tree = ast.parse(Path(analysis.__file__).read_text(encoding="utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "analysis.py must not use relative (package) imports"
            imported.add(node.module.split(".")[0])
    assert "recovery_evidence" not in imported
    assert imported <= {"__future__", "csv", "gzip", "json", "collections", "pathlib", "typing", "numpy"}


def test_bootstrap_is_seeded_and_resamples_whole_trajectories():
    idx = analysis.bootstrap_indices(300)
    assert idx.shape == (10_000, 300) and (idx == analysis.bootstrap_indices(300)).all()
    assert idx.min() == 0 and idx.max() == 299


def test_paired_stats_on_known_values():
    diff = np.array([-2.0, -1.0, 0.0, 1.0])
    st = analysis.paired_stats(diff, analysis.bootstrap_indices(4))
    assert st["mean"] == -0.5 and st["median"] == -0.5
    assert st["sd"] == pytest.approx(np.std(diff, ddof=1)) and st["mcse"] == pytest.approx(st["sd"] / 2)
    assert (st["share_negative"], st["share_zero"], st["share_positive"]) == (0.5, 0.25, 0.25)
    assert st["ci_low"] <= st["mean"] <= st["ci_high"]


def test_ratio_records_na_for_zero_denominator():
    out = analysis.ratio(np.array([1.0, 0.0]), np.array([4.0, 0.0]))
    assert out[0] == 0.25 and np.isnan(out[1])


@pytest.fixture(scope="module")
def small_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("run")
    run_experiment(out, ["C0", "C3"], replicates=12, jobs=1, quiet=True)
    return out, analysis.analyse(out, quiet=True)


def test_recomputation_agrees_with_evaluator(small_run):
    out, res = small_run
    assert res["integrity"]["verdict"] == "ALL COMPARISONS AGREED"
    report = (out / "tables" / "integrity_report.txt").read_text()
    assert report.count("-> AGREE") == 2 and "DISAGREE" not in report


def test_tampered_verdict_log_is_detected(small_run, tmp_path):
    import gzip
    import shutil

    out, _ = small_run
    copy = tmp_path / "copy"
    shutil.copytree(out, copy)
    path = copy / "logs" / "C0" / "verdicts.csv.gz"
    lines = gzip.open(path, "rt").read().splitlines()
    rep, pol, day, svc, vh, y = lines[1].split(",")
    lines[1] = ",".join((rep, pol, day, svc, str(1 - int(vh)), y))
    with gzip.open(path, "wt") as fh:
        fh.write("\n".join(lines) + "\n")
    res = analysis.analyse(copy, quiet=True)
    assert res["integrity"]["verdict"] == "DISAGREEMENT FOUND"


def test_tables_and_allocation(small_run):
    out, res = small_run
    for name in ("policy_summary.csv", "paired_results.csv", "paired_differences.csv", "allocation.csv",
                 "recheck_delay.csv", "table5_primary.md", "table6_contrasts.md", "table7_allocation.md",
                 "table8_conditions.md", "analysis.json"):
        assert (out / "tables" / name).exists(), name
    c0 = res["conditions"]["C0"]
    p0 = [a for a in c0["allocation"] if a["policy"] == "P0"]
    assert [round(a["mean_checks_per_trajectory"], 1) for a in p0] == [23.0] * 4 + [22.0] * 4
    assert sum(a["mean_checks_per_trajectory"] for a in p0) == pytest.approx(get_condition("C0").T)
    assert res["conditions"]["C3"]["policies"]["P3"]["checks_per_trajectory"] == 720
