"""Tests for the new v2.0.0 modules: finitekey, opa, network, telemetry, features, models."""
import numpy as np
import pytest
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from satqkd_sentinel.linkmodel import Link
from satqkd_sentinel.finitekey import finite_key_pass, finite_key_length
from satqkd_sentinel.opa import (steering_range, beam_width, phase_error_loss_db,
                                  sidelobe_level_db, array_factor_1d, far_field_divergence)
from satqkd_sentinel.network import (key_per_pass, key_per_day, daily_key_budget,
                                      relay_key_consumption, network_availability, key_store_model)
from satqkd_sentinel.telemetry import generate_pass, generate_dataset, STATES, GROUPS
from satqkd_sentinel.features import extract_features, FEATURE_NAMES, feature_dictionary
from satqkd_sentinel.models import (train_classifier, predict, evaluate_classifier,
                                     train_novelty_detector, novelty_predict)


class TestFiniteKey:
    def test_finite_key_positive(self):
        lk = Link()
        for deg in [25, 30, 40, 60, 90]:
            k = finite_key_pass(lk, np.radians(deg))
            assert k > 0, f"finite key should be positive at {deg}°, got {k}"

    def test_finite_less_than_asymptotic(self):
        lk = Link()
        from satqkd_sentinel.linkmodel import pass_profile
        for deg in [30, 60, 90]:
            k_fin = finite_key_pass(lk, np.radians(deg))
            t, el, L, az = pass_profile(np.radians(deg))
            r, _ = lk.rate(lk.eta(L, el))
            dt = t[1] - t[0]
            k_asym = r.sum() * dt
            assert k_fin < k_asym, f"finite key should be less than asymptotic at {deg}°"

    def test_finite_key_monotonic(self):
        lk = Link()
        keys = [finite_key_pass(lk, np.radians(d)) for d in [25, 30, 40, 60, 90]]
        for i in range(len(keys) - 1):
            assert keys[i] < keys[i+1], "finite key should increase with elevation"


class TestOPA:
    def test_steering_range(self):
        sr = np.degrees(steering_range())
        assert abs(sr - 22.8) < 1.0, f"steering range should be ~22.8°, got {sr:.1f}°"

    def test_beam_width(self):
        bw = beam_width()
        assert 100e-6 < bw < 300e-6, f"beam width should be ~189 µrad, got {bw*1e6:.0f} µrad"

    def test_phase_error_loss(self):
        loss_04 = phase_error_loss_db(0.4)
        loss_10 = phase_error_loss_db(1.0)
        assert 0.3 < loss_04 < 1.5, f"phase error loss at 0.4 rad: {loss_04:.2f} dB"
        assert 3.0 < loss_10 < 6.0, f"phase error loss at 1.0 rad: {loss_10:.2f} dB"

    def test_sidelobe(self):
        sl = sidelobe_level_db()
        assert -15 < sl < -10, f"sidelobe level should be ~-13 dB, got {sl:.1f} dB"

    def test_broadside_peak(self):
        af = array_factor_1d(np.array([0.0]), 0.0)
        assert abs(af[0] - 1.0) < 1e-6


class TestNetwork:
    def test_key_per_pass_positive(self):
        lk = Link()
        k = key_per_pass(lk, np.radians(40))
        assert k > 1e6, f"key per pass should be >1 Mbit, got {k/1e6:.2f} Mbit"

    def test_daily_budget(self):
        budget = daily_key_budget()
        assert 1 in budget and 8 in budget
        assert budget[8] > budget[1]

    def test_relay_consumption(self):
        c = relay_key_consumption(3, 1024)
        assert c == 3 * 1024

    def test_network_availability(self):
        a = network_availability(4, 0.95)
        assert 0.99 < a < 1.0

    def test_key_store_model(self):
        result = key_store_model(5000, 1000, 1e9, days=7)
        assert 't_hours' in result
        assert len(result['store']) > 0


class TestTelemetry:
    def test_generate_nominal_pass(self):
        lk = Link()
        df = generate_pass(lk, np.radians(40), state='nominal', seed=42)
        assert len(df) > 10
        assert 'qber' in df.columns
        assert 'label' in df.columns
        assert (df['label'] == 'nominal').all()

    def test_generate_anomalous_pass(self):
        lk = Link()
        df = generate_pass(lk, np.radians(40), state='optical_jamming',
                           severity=0.7, onset_fraction=0.3, seed=42)
        assert (df['label'] == 'optical_jamming').any()
        assert (df['label'] == 'nominal').any()

    def test_generate_dataset(self):
        lk = Link()
        df = generate_dataset(lk, 20, seed=42)
        assert len(df) > 100
        assert 'pass_id' in df.columns
        labels = df['label'].unique()
        assert len(labels) >= 5

    def test_all_states_valid(self):
        for s in STATES:
            assert s in GROUPS


class TestFeatures:
    def test_feature_count(self):
        assert len(FEATURE_NAMES) == 24

    def test_extract_features_shape(self):
        lk = Link()
        df = generate_dataset(lk, 10, seed=42)
        X = extract_features(df, lk)
        assert X.shape == (len(df), 24)
        assert np.isfinite(X).all()

    def test_feature_dictionary(self):
        fd = feature_dictionary()
        assert len(fd) == 24
        assert 'name' in fd.columns


class TestModels:
    @pytest.fixture
    def train_data(self):
        lk = Link()
        df = generate_dataset(lk, 30, seed=42)
        X = extract_features(df, lk)
        y = df['label'].values
        return X, y

    def test_gradient_boosting(self, train_data):
        X, y = train_data
        model = train_classifier(X, y, method='gradient_boosting', seed=42)
        preds = predict(model, X)
        assert len(preds) == len(y)

    def test_random_forest(self, train_data):
        X, y = train_data
        model = train_classifier(X, y, method='random_forest', seed=42)
        metrics = evaluate_classifier(model, X, y)
        assert metrics['macro_f1'] > 0.5

    def test_novelty_detector(self, train_data):
        X, y = train_data
        nom_mask = y == 'nominal'
        det = train_novelty_detector(X[nom_mask], method='isolation_forest', seed=42)
        is_anom = novelty_predict(det, X)
        assert len(is_anom) == len(y)
