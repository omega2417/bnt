"""Tests for the parts of the pipeline whose failures would be silent.

The emphasis is deliberate. A crash is found by running the pipeline once; what
these tests target is the class of defect that produces plausible output: an
equation evaluated with the wrong sign, a split that leaks, a duplicate detector
that groups everything, an SNR estimator that reports noise as signal.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from uavews import (agreement, config, geometry, ids, labeling, media_qc,
                    schema, timebase as tb, trialdesign, validation)
from uavews.ingest.common import generalize_cell


@pytest.fixture(scope="module")
def cfg():
    return config.load()


# --------------------------------------------------------------------------- #
# Time base
# --------------------------------------------------------------------------- #
def test_rfc3339_roundtrip_preserves_milliseconds():
    for s in ("2025-04-11T08:15:03.250Z", "2025-01-01T00:00:00.000Z",
              "2025-12-31T23:59:59.999Z"):
        assert tb.ns_to_rfc3339(tb.rfc3339_to_ns(s)) == s


def test_rfc3339_rejects_missing_utc_designator():
    with pytest.raises(ValueError):
        tb.rfc3339_to_ns("2025-04-11T08:15:03")


def test_nanosecond_resolution_survives_the_epoch_offset():
    """The reason analytic tables use int64 ns and not float seconds."""
    base = tb.rfc3339_to_ns("2025-04-11T08:15:03.000Z")
    assert (base + 1) - base == 1                      # 1 ns is representable
    as_float = float(base) / tb.NS
    assert (as_float + 1e-9) == as_float               # ... and float64 loses it


def test_tile_windows_anchors_the_last_window_to_the_event_end():
    wins = tb.tile_windows(0, tb.seconds_to_ns(23), 10.0, 5.0)
    assert wins[-1][1] == tb.seconds_to_ns(23)
    assert all(b - a == tb.seconds_to_ns(10) for a, b in wins)


def test_iou_and_overlap_are_consistent():
    a = (0, 100)
    assert tb.overlap_ns(a, (50, 150)) == 50
    assert tb.overlap_ns(a, (200, 300)) == 0
    assert tb.iou(a, a) == pytest.approx(1.0)
    assert tb.iou(a, (100, 200)) == 0.0


# --------------------------------------------------------------------------- #
# Equation (1): boundary distance
# --------------------------------------------------------------------------- #
@pytest.fixture
def unit_square():
    return geometry.WarningZone("SQ", np.array([[0.0, 0.0], [10.0, 0.0],
                                                [10.0, 10.0], [0.0, 10.0]]))


def test_boundary_distance_is_zero_on_the_boundary(unit_square):
    on = np.array([[0.0, 5.0], [10.0, 5.0], [5.0, 0.0], [5.0, 10.0], [0.0, 0.0]])
    assert np.allclose(unit_square.boundary_distance(on), 0.0, atol=1e-9)


def test_boundary_distance_is_positive_inside_and_outside(unit_square):
    """Eq. (1) is a distance to the boundary, not to the region."""
    assert unit_square.boundary_distance(np.array([[5.0, 5.0]]))[0] == pytest.approx(5.0)
    assert unit_square.boundary_distance(np.array([[-3.0, 5.0]]))[0] == pytest.approx(3.0)


def test_signed_distance_changes_sign_across_the_boundary(unit_square):
    assert unit_square.signed_boundary_distance(np.array([[5.0, 5.0]]))[0] < 0
    assert unit_square.signed_boundary_distance(np.array([[-1.0, 5.0]]))[0] > 0


def test_boundary_distance_uses_the_nearest_edge_not_the_nearest_vertex(unit_square):
    """A point off an edge midpoint must not be measured to a corner."""
    d = unit_square.boundary_distance(np.array([[5.0, -4.0]]))[0]
    assert d == pytest.approx(4.0)


# --------------------------------------------------------------------------- #
# Direction rule and Equation (2)
# --------------------------------------------------------------------------- #
def test_direction_labels_follow_the_sign_of_the_difference():
    t = np.arange(0.0, 10.0, 0.5)
    approaching = geometry.direction_labels(t, 100.0 - 10.0 * t, 1.0, 1.0)
    receding = geometry.direction_labels(t, 10.0 * t, 1.0, 1.0)
    assert set(approaching[:-4]) == {"approaching"}
    assert set(receding[:-4]) == {"receding"}


def test_dead_band_suppresses_motion_smaller_than_epsilon():
    """The property epsilon exists for: noise must not become a direction."""
    t = np.arange(0.0, 10.0, 0.5)
    rng = np.random.default_rng(0)
    d = 500.0 + rng.normal(0, 0.35, t.size)          # stationary, sigma_h = 0.35 m
    eps = 3.0 * math.sqrt(2.0) * 0.35
    labels = geometry.direction_labels(t, d, 1.0, eps)
    decided = [x for x in labels if x != "uncertain"]
    assert all(x == "lateral_stationary" for x in decided)


def test_zero_dead_band_would_turn_noise_into_directions():
    """The complement of the test above: without epsilon the label is noise."""
    t = np.arange(0.0, 10.0, 0.5)
    rng = np.random.default_rng(0)
    d = 500.0 + rng.normal(0, 0.35, t.size)
    labels = geometry.direction_labels(t, d, 1.0, 0.0)
    assert {"approaching", "receding"} <= set(labels)


def test_crossing_time_is_interpolated_between_samples():
    t = np.array([0.0, 1.0, 2.0])
    signed = np.array([10.0, 2.0, -2.0])             # crosses at t = 1.5
    assert geometry.crossing_time(t, signed) == pytest.approx(1.5)


def test_warning_time_is_censored_when_there_is_no_crossing():
    t = np.arange(0.0, 5.0)
    signed = np.full(5, 30.0)
    assert geometry.crossing_time(t, signed) is None
    assert np.all(np.isnan(geometry.warning_time(t, None)))


def test_warning_time_decreases_to_zero_at_the_crossing():
    t = np.arange(0.0, 10.0, 1.0)
    T = geometry.warning_time(t, 7.0)
    assert T[0] == pytest.approx(7.0)
    assert T[7] == pytest.approx(0.0)
    assert np.all(np.diff(T) < 0)


# --------------------------------------------------------------------------- #
# Configuration invariants
# --------------------------------------------------------------------------- #
def test_epsilon_never_falls_below_the_uncertainty_floor(cfg):
    assert cfg.epsilon_m >= cfg.epsilon_floor_m - 1e-12


def test_explicit_epsilon_below_the_floor_is_rejected(cfg):
    raw = {k: (dict(v) if isinstance(v, dict) else v) for k, v in cfg.raw.items()}
    raw["kinematics"] = dict(raw["kinematics"])
    raw["kinematics"]["epsilon_m"] = 0.01
    bad = config.Config(raw=raw, vocab=cfg.vocab, source_path=cfg.source_path)
    with pytest.raises(config.ConfigError):
        _ = bad.epsilon_m


def test_split_fractions_must_sum_to_one(cfg, tmp_path):
    import yaml
    raw = yaml.safe_load(cfg.source_path.read_text(encoding="utf-8"))
    raw["splits"]["test"] = 0.5
    p = tmp_path / "bad.yaml"
    p.write_text(yaml.safe_dump(raw), encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.load(p)


# --------------------------------------------------------------------------- #
# Identifiers
# --------------------------------------------------------------------------- #
def test_identifiers_are_deterministic_and_salt_dependent():
    a, b = ids.release_salt("one"), ids.release_salt("two")
    assert ids.event_id(a, "C", 1) == ids.event_id(a, "C", 1)
    assert ids.event_id(a, "C", 1) != ids.event_id(b, "C", 1)
    assert ids.event_id(a, "C", 1) != ids.event_id(a, "C", 2)


def test_pseudonyms_rotate_between_epochs_and_are_stable_within_one():
    s = ids.release_salt("x")
    assert ids.rotating_source_id(s, "dev", 0) == ids.rotating_source_id(s, "dev", 0)
    assert ids.rotating_source_id(s, "dev", 0) != ids.rotating_source_id(s, "dev", 1)


def test_generalized_cell_partitions_the_plane():
    """Truncation, not rounding: adjacent cells must not overlap."""
    assert generalize_cell(999.0, 0.0, 1000.0) == generalize_cell(1.0, 0.0, 1000.0)
    assert generalize_cell(1001.0, 0.0, 1000.0) != generalize_cell(999.0, 0.0, 1000.0)
    assert generalize_cell(-1.0, 0.0, 1000.0) != generalize_cell(1.0, 0.0, 1000.0)


# --------------------------------------------------------------------------- #
# Equations (4) and (5)
# --------------------------------------------------------------------------- #
def test_completeness_counts_against_the_declared_required_set():
    table = schema.Table("t", "id", [
        schema.Field("id", "string", required=True),
        schema.Field("a", "string", required=True),
        schema.Field("b", "string", required=True),
        schema.Field("c", "string", required=False),
    ])
    df = pd.DataFrame({"id": ["1", "2"], "a": ["x", None], "b": ["y", "z"],
                       "c": [None, None]})
    c = validation.record_completeness(df, table)
    assert c.iloc[0] == pytest.approx(1.0)
    assert c.iloc[1] == pytest.approx(2 / 3)


def test_empty_string_counts_as_missing():
    table = schema.Table("t", "id", [schema.Field("id", "string", required=True)])
    df = pd.DataFrame({"id": ["a", ""]})
    assert validation.record_completeness(df, table).tolist() == [1.0, 0.0]


def test_duplicate_rate_is_computed_over_groups_not_rows():
    media = pd.DataFrame({
        "duplicate_group": ["g1", "g1", "g2", "g3"],
        "sha256": ["a" * 64, "b" * 64, "c" * 64, "d" * 64],
    })
    d = validation.duplicate_rate(media)
    assert d["duplicate_rate"] == pytest.approx((4 - 3) / 4)
    assert d["exact_duplicate_rate"] == 0.0
    assert d["near_duplicate_rate"] == pytest.approx(0.25)


def test_exact_and_near_duplicate_rates_separate():
    media = pd.DataFrame({"duplicate_group": ["g", "g"], "sha256": ["a" * 64] * 2})
    d = validation.duplicate_rate(media)
    assert d["exact_duplicate_rate"] == pytest.approx(0.5)
    assert d["near_duplicate_rate"] == pytest.approx(0.0)


# --------------------------------------------------------------------------- #
# Schema validation
# --------------------------------------------------------------------------- #
def test_vocabulary_violations_are_reported(cfg):
    df = pd.DataFrame({"event_kind": ["controlled_flight", "not_a_kind"]})
    table = schema.Table("t", "event_kind", [
        schema.Field("event_kind", "string", vocab="event_kind")])
    issues = schema.validate_table(df, table, cfg.vocab)
    assert any(i["kind"] == "vocabulary_violation" for i in issues)


def test_orphan_references_are_detected():
    tables = {
        "events": pd.DataFrame({"event_id": ["e1"]}),
        "windows": pd.DataFrame({"window_id": ["w1"], "event_id": ["e-missing"]}),
    }
    issues = schema.check_referential_integrity(tables)
    assert any(i["kind"] == "orphan_reference" for i in issues)


def test_data_dictionary_covers_every_declared_field():
    dd = schema.data_dictionary()
    for name, table in schema.TABLES.items():
        assert set(dd[dd.table == name]["field"]) == set(table.columns())


# --------------------------------------------------------------------------- #
# Agreement
# --------------------------------------------------------------------------- #
def test_alpha_is_one_for_perfect_agreement():
    units = {i: ["a"] * 3 if i % 2 else ["b"] * 3 for i in range(8)}
    assert agreement.krippendorff_alpha_nominal(units) == pytest.approx(1.0)


def test_alpha_is_about_zero_for_random_judgements():
    rng = np.random.default_rng(4)
    units = {i: list(rng.choice(["a", "b", "c"], 3)) for i in range(600)}
    assert abs(agreement.krippendorff_alpha_nominal(units)) < 0.1


def test_alpha_is_negative_for_systematic_disagreement():
    units = {i: ["a", "b"] if i % 2 else ["b", "a"] for i in range(10)}
    assert agreement.krippendorff_alpha_nominal(units) < 0


def test_single_rating_units_are_excluded_not_counted_as_agreement():
    both = {0: ["a", "a"], 1: ["b", "b"], 2: ["c"]}
    only_pairs = {0: ["a", "a"], 1: ["b", "b"]}
    assert agreement.krippendorff_alpha_nominal(both) == pytest.approx(
        agreement.krippendorff_alpha_nominal(only_pairs))


# --------------------------------------------------------------------------- #
# Adjudication
# --------------------------------------------------------------------------- #
def _label(salt, target, name, value, tier, annotator, conf=0.9):
    return labeling._row(salt, "event", target, target, name, value, tier,
                         annotator, conf, "m", (0, tb.NS), final=False)


def test_ground_truth_wins_on_a_field_it_observes(cfg):
    salt = ids.release_salt("t")
    df = pd.DataFrame([
        _label(salt, "e1", "movement_direction", "approaching",
               "controlled_ground_truth", "rule", 1.0),
        _label(salt, "e1", "movement_direction", "receding", "expert_verified", "a1"),
        _label(salt, "e1", "movement_direction", "receding", "expert_verified", "a2"),
    ])
    out = labeling.released_labels(labeling.adjudicate(df, cfg, salt))
    assert out["value"].iloc[0] == "approaching"


def test_ground_truth_does_not_win_outside_its_authority(cfg):
    """A flight log knows where the aircraft was, not whether it was audible."""
    assert "audibility" not in labeling.AUTHORITATIVE_FIELDS
    salt = ids.release_salt("t")
    df = pd.DataFrame([
        _label(salt, "e1", "audibility", "audible", "controlled_ground_truth",
               "rule", 1.0),
        _label(salt, "e1", "audibility", "inaudible", "expert_verified", "a1"),
        _label(salt, "e1", "audibility", "inaudible", "expert_verified", "a2"),
    ])
    out = labeling.released_labels(labeling.adjudicate(df, cfg, salt))
    assert out["value"].iloc[0] == "inaudible"


def test_a_tie_stays_uncertain_rather_than_picking_a_side(cfg):
    salt = ids.release_salt("t")
    df = pd.DataFrame([
        _label(salt, "e1", "platform_class", "multirotor_small", "expert_verified",
               "a1", 0.8),
        _label(salt, "e1", "platform_class", "fixed_wing_small", "expert_verified",
               "a2", 0.8),
    ])
    out = labeling.released_labels(labeling.adjudicate(df, cfg, salt))
    assert out["value"].iloc[0] == "uncertain"
    assert out["adjudication_code"].iloc[0] == "TIE-UNRESOLVED"


def test_unanimous_high_confidence_labels_skip_adjudication(cfg):
    salt = ids.release_salt("t")
    df = pd.DataFrame([
        _label(salt, "e1", "vehicle_presence", "present", "expert_verified", "a1", 0.95),
        _label(salt, "e1", "vehicle_presence", "present", "expert_verified", "a2", 0.95),
    ])
    out = labeling.adjudicate(df, cfg, salt)
    assert set(out["adjudication_status"]) == {"not_required"}


def test_exactly_one_released_label_per_target(cfg):
    salt = ids.release_salt("t")
    df = pd.DataFrame([
        _label(salt, "e1", "vehicle_presence", "present", "expert_verified", "a1", 0.9),
        _label(salt, "e1", "vehicle_presence", "absent", "expert_verified", "a2", 0.9),
        _label(salt, "e1", "vehicle_presence", "present", "expert_verified", "a3", 0.9),
    ])
    out = labeling.released_labels(labeling.adjudicate(df, cfg, salt))
    assert len(out) == 1


def test_distance_bins_cover_the_line_without_gaps():
    for d, expected in ((0.0, "0-100"), (99.9, "0-100"), (100.0, "100-300"),
                        (1500.0, "1500+"), (99999.0, "1500+")):
        assert labeling.distance_bin(d) == expected
    assert labeling.distance_bin(float("nan")) == "unknown"


# --------------------------------------------------------------------------- #
# Media quality
# --------------------------------------------------------------------------- #
def _tone(path, snr_db, sr=16000, dur=2.0, f0=140.0, seed=0):
    rng = np.random.default_rng(seed)
    t = np.arange(int(sr * dur)) / sr
    sig = sum((0.7 ** k) * np.sin(2 * math.pi * f0 * (k + 1) * t)
              for k in range(4))
    sig /= np.sqrt(np.mean(sig ** 2))          # unit RMS: SNR is a power ratio
    y = (10 ** (snr_db / 20.0) * sig + rng.normal(0, 1.0, t.size)) * 0.02
    from uavews.simulate import write_wav
    write_wav(path, y, sr)


def test_snr_estimator_tracks_a_known_input_snr(tmp_path):
    """Accuracy above the sensitivity floor, which the next test pins down."""
    targets = (-14.0, -8.0, 0.0, 8.0, 16.0)
    measured = []
    for target in targets:
        p = tmp_path / f"t{target}.wav"
        _tone(p, target)
        m = media_qc.audio_metrics(p)
        assert m["snr_measurable"], f"estimator saturated at {target} dB"
        measured.append(m["snr_db"])
    assert all(b > a for a, b in zip(measured, measured[1:])), "not monotone"
    assert max(abs(m - t) for m, t in zip(measured, targets)) < 3.0


def test_snr_estimator_sensitivity_floor_is_where_it_is_declared(tmp_path):
    """The estimator must not claim reach it does not have, in either direction.

    Well above the declared floor it should essentially always detect; well below
    it should essentially never. Getting this wrong in the optimistic direction
    publishes noise as signal; in the pessimistic direction it discards usable
    recordings and understates the acoustic channel.
    """
    def hit_rate(target, n=8):
        hits = 0
        for seed in range(n):
            p = tmp_path / f"s{target}_{seed}.wav"
            _tone(p, target, seed=seed)
            hits += bool(media_qc.audio_metrics(p)["snr_measurable"])
        return hits / n

    floor = media_qc.audio_metrics(tmp_path / "s-4_0.wav") if False else None
    _tone(tmp_path / "ref.wav", 0.0)
    declared = media_qc.audio_metrics(tmp_path / "ref.wav")["snr_estimator_floor_db"]
    assert -30.0 < declared < -12.0, declared
    assert hit_rate(declared + 6.0) >= 0.85
    assert hit_rate(declared - 8.0) <= 0.15


def test_snr_estimator_reports_saturation_on_pure_noise(tmp_path):
    """The defect this guards against: noise reported as a weak detection."""
    from uavews.simulate import write_wav
    rng = np.random.default_rng(1)
    p = tmp_path / "noise.wav"
    write_wav(p, rng.normal(0, 1.0, 32000) * 0.02, 16000)
    m = media_qc.audio_metrics(p)
    assert m["snr_db"] is None
    assert "snr_not_measurable" in m["quality_flags"]


def test_clipping_is_detected(tmp_path):
    from uavews.simulate import write_wav
    t = np.arange(16000) / 16000
    write_wav(tmp_path / "c.wav", 3.0 * np.sin(2 * math.pi * 200 * t), 16000)
    assert "clipping" in media_qc.audio_metrics(tmp_path / "c.wav")["quality_flags"]


def test_perceptual_hash_survives_re_encoding_but_separates_content(tmp_path):
    from uavews.simulate import write_wav
    rng = np.random.default_rng(2)
    base = rng.normal(0, 0.2, 32000)
    write_wav(tmp_path / "a.wav", base, 16000)
    write_wav(tmp_path / "a2.wav", np.round(base * 1.05 * 2048) / 2048, 16000)
    write_wav(tmp_path / "b.wav", rng.normal(0, 0.2, 32000), 16000)
    h = {n: media_qc.perceptual_hash(tmp_path / f"{n}.wav", "audio")
         for n in ("a", "a2", "b")}
    assert media_qc.hamming(h["a"], h["a2"]) <= 4
    assert media_qc.hamming(h["a"], h["b"]) > 8


def test_png_roundtrip_is_lossless(tmp_path):
    from uavews.simulate import write_png_gray
    rng = np.random.default_rng(3)
    img = rng.integers(0, 256, (40, 55)).astype(np.uint8)
    write_png_gray(tmp_path / "i.png", img)
    assert np.array_equal(media_qc.read_png_gray(tmp_path / "i.png"), img)


# --------------------------------------------------------------------------- #
# Field-trial design
# --------------------------------------------------------------------------- #
def test_norm_ppf_matches_known_quantiles():
    for p, z in ((0.5, 0.0), (0.95, 1.6448536), (0.975, 1.959964), (0.99, 2.326348)):
        assert trialdesign.norm_ppf(p) == pytest.approx(z, abs=1e-5)


def test_sample_size_grows_as_the_effect_shrinks():
    n_small = trialdesign.sample_size_one_proportion(0.75, 0.95, 0.05, 0.8)
    n_large = trialdesign.sample_size_one_proportion(0.75, 0.80, 0.05, 0.8)
    assert n_large > n_small > 0


def test_sample_size_grows_with_power():
    assert (trialdesign.sample_size_one_proportion(0.75, 0.90, 0.05, 0.95)
            > trialdesign.sample_size_one_proportion(0.75, 0.90, 0.05, 0.80))


def test_loss_inflation_is_an_increase():
    assert trialdesign.inflate_for_loss(42, 0.15) == 50
    assert trialdesign.inflate_for_loss(42, 0.0) == 42


def test_wilson_interval_stays_inside_the_unit_interval_at_the_boundary():
    lo, hi = trialdesign.wilson_interval(10, 10)
    assert 0.0 < lo < 1.0 and hi == pytest.approx(1.0, abs=1e-9)
    assert lo < 1.0, "a Wald interval would collapse to zero width here"


def test_acoustic_range_shrinks_as_ambient_noise_rises(cfg):
    ac = cfg["detectability"]["acoustic"]
    quiet = trialdesign.acoustic_detection_range_m(
        75.0, 30.0, ac["atmospheric_absorption_db_per_m"], 6.0,
        processing_gain_db=ac["detector_processing_gain_db"])
    loud = trialdesign.acoustic_detection_range_m(
        75.0, 55.0, ac["atmospheric_absorption_db_per_m"], 6.0,
        processing_gain_db=ac["detector_processing_gain_db"])
    assert quiet > loud > 0


def test_acoustic_range_is_the_point_where_snr_meets_the_threshold(cfg):
    ac = cfg["detectability"]["acoustic"]
    gain = ac["detector_processing_gain_db"]
    r = trialdesign.acoustic_detection_range_m(
        75.0, 40.0, ac["atmospheric_absorption_db_per_m"], 6.0,
        processing_gain_db=gain)
    snr = float(trialdesign.acoustic_snr_db(
        r, 75.0, 40.0, ac["atmospheric_absorption_db_per_m"])) + gain
    assert snr == pytest.approx(6.0, abs=0.05)


def test_visual_range_and_apparent_size_are_inverses():
    f_px = trialdesign.focal_length_px(1920, 12.0)
    r = trialdesign.visual_range_m(0.55, f_px, 3.0)
    assert trialdesign.apparent_size_px(r, 0.55, f_px) == pytest.approx(3.0)


def test_warning_budget_subtracts_both_latencies():
    b = trialdesign.warning_budget(300.0, 15.0, 4.0, 6.0, 30.0)
    assert b.lead_time_s == pytest.approx(20.0)
    assert b.actionable_s == pytest.approx(10.0)
    assert not b.feasible


def test_required_range_is_the_inverse_of_the_budget():
    r = trialdesign.required_detection_range_m(15.0, 30.0, 4.0, 6.0)
    b = trialdesign.warning_budget(r, 15.0, 4.0, 6.0, 30.0)
    assert b.margin_s == pytest.approx(0.0, abs=1e-9)
