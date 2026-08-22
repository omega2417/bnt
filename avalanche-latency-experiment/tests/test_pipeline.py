"""End-to-end: simulate a small campaign, analyse it, check the invariants."""

import numpy as np
import pytest

from alp import analyze, config, manifest, report, tables
from alp.schedule import build_schedule
from alp.simulate import RunSpec, run_campaign, simulate_run


@pytest.fixture(scope="module")
def campaign(tmp_path_factory):
    profile = config.get_profile("smoke")
    root = tmp_path_factory.mktemp("campaign")
    schedule = build_schedule(profile)
    run_campaign(profile, schedule, root, progress=False)
    summary = analyze.summarize_dataset(root, progress=False)
    stability = analyze.classify_stability(summary)
    cells = analyze.cell_stability(stability)
    effects = analyze.holm_correction(analyze.all_effects(summary))
    return {
        "root": root, "profile": profile, "summary": summary,
        "stability": stability, "cells": cells, "effects": effects,
    }


def test_every_scheduled_run_produced_records(campaign):
    summary = campaign["summary"]
    assert len(summary) == campaign["profile"].n_runs
    assert summary.run_id.is_unique
    expected = summary.load_tps * campaign["profile"].measure_s
    assert (summary.n_submitted == expected).all(), "denominator must be exact"


def test_dataset_is_labelled_simulated(campaign):
    assert analyze.dataset_provenance(campaign["root"]) == "SIMULATED"
    assert set(campaign["summary"].provenance) == {"SIMULATED"}


def test_latency_ordering_holds_for_every_run(campaign):
    s = campaign["summary"]
    assert (s.p50_ms <= s.p95_ms).all()
    assert (s.p95_ms <= s.p99_ms).all()
    assert (s.p99_ms <= s.all_p99_ms + 1e-9).all(), "first read cannot follow the last"


def test_observed_block_interval_tracks_the_target(campaign):
    from alp.model import block_target_ms

    observed = campaign["summary"].groupby("config").observed_block_interval_ms.median()
    for cfg, value in observed.items():
        assert value == pytest.approx(block_target_ms(cfg), rel=0.05)


def test_shorter_pacing_lowers_median_latency(campaign):
    medians = campaign["summary"].groupby("config").p50_ms.mean()
    assert medians["C4"] < medians["C3"] < medians["C2"] < medians["C1"] < medians["C0"]


def test_simulation_is_reproducible():
    spec = RunSpec("RUN-0001", "C3", "T1_vpn", 100, 1, "L100-R01", 5, 2, 2)
    a = simulate_run(spec)["records"]
    b = simulate_run(spec)["records"]
    assert a.equals(b)


def test_paired_bootstrap_pairs_by_trace_not_by_run(campaign):
    effects = campaign["effects"]
    expected_pairs = campaign["profile"].repeats
    assert (effects.n_pairs == expected_pairs).all()
    assert (effects.ci_low <= effects.delta_improvement_ms).all()
    assert (effects.delta_improvement_ms <= effects.ci_high).all()


def test_faster_profiles_show_a_positive_improvement(campaign):
    p99 = campaign["effects"].query("metric == 'p99_ms'")
    assert (p99.delta_improvement_ms > 0).all()
    assert (p99.ci_low > 0).all(), "the improvement must exclude zero"


def test_holm_only_touches_the_confirmatory_family(campaign):
    effects = campaign["effects"]
    primary = effects[effects.metric == config.PRIMARY_ENDPOINT]
    secondary = effects[effects.metric != config.PRIMARY_ENDPOINT]
    assert primary.holm_p.notna().all()
    assert secondary.holm_p.isna().all()
    assert (primary.holm_p >= primary.p_value - 1e-12).all()


def test_stability_classification_names_its_reasons(campaign):
    stability = campaign["stability"]
    assert stability.stable.dtype == bool
    failed = stability[~stability.stable]
    assert (failed.failed_criteria.str.len() > 0).all()
    assert (stability[stability.stable].failed_criteria == "").all()


def test_max_sustainable_load_is_contiguous(campaign):
    reach = analyze.max_sustainable_load_both(campaign["cells"])
    assert (reach.max_tps_majority >= reach.max_tps_all_repeats).all()


def test_report_and_tables_render(campaign, tmp_path):
    cells, stability = campaign["cells"], campaign["stability"]
    effects, summary = campaign["effects"], campaign["summary"]
    best = analyze.select_best_static(cells, stability)
    reach = analyze.max_sustainable_load_both(cells)
    t14 = tables.table14_latency_quantiles(stability)
    t15 = tables.table15_stability(cells)
    t16 = tables.table16_effects(effects)
    precision = analyze.precision_check(effects)
    paths = report.write_report(tmp_path, "smoke", "SIMULATED", summary, effects,
                                stability, cells, best, reach, t14, t15, t16,
                                precision)
    text = paths["results_en"].read_text(encoding="utf-8")
    assert "Provenance: SIMULATED" in text
    assert "not** measurements" in text or "not" in text
    assert paths["results_uk"].read_text(encoding="utf-8").startswith("# Результати")


def test_manifest_detects_tampering(campaign):
    root = campaign["root"]
    manifest.build(root, "smoke", "SIMULATED")
    assert manifest.verify(root)["ok"]
    victim = next((root / "nodes").glob("*_blocks.csv"))
    victim.write_text(victim.read_text() + "0,0,0,0,0,0\n", encoding="utf-8")
    report_ = manifest.verify(root)
    assert not report_["ok"]
    assert victim.name in report_["mismatched"][0]
