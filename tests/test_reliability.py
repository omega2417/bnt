"""Public-behavior regressions for data isolation and boundary cases."""
import numpy as np
import pandas as pd
import pytest
from satqkd_sentinel.linkmodel import Link, pass_profile
from satqkd_sentinel.telemetry import generate_dataset, generate_pass
from satqkd_sentinel.features import extract_features
from satqkd_sentinel.models import train_novelty_detector, novelty_predict
from satqkd_sentinel.finitekey import finite_key_pass
from satqkd_sentinel.geo import coverage_stats

@pytest.mark.parametrize('n', [1, 7, 20, 31])
def test_exact_pass_count(n):
    assert generate_dataset(Link(), n, seed=7).pass_id.nunique() == n

def test_zero_weight_class_not_generated():
    d = generate_dataset(Link(), 3, {'nominal': 1, 'optical_jamming': 0})
    assert set(d.label) == {'nominal'}

def test_onset_at_end_has_no_anomaly():
    d = generate_pass(Link(), np.radians(25), state='optical_jamming', onset_fraction=1)
    assert set(d.label) == {'nominal'}

def test_features_ignore_labels():
    d = generate_pass(Link(), np.radians(25), state='optical_jamming', seed=7)
    np.testing.assert_allclose(extract_features(d), extract_features(d.drop(columns=['label','group'])))

def test_features_do_not_look_into_future_or_other_passes():
    a = generate_pass(Link(), np.radians(25), seed=1).assign(pass_id=0)
    b = generate_pass(Link(), np.radians(40), state='optical_jamming', seed=2).assign(pass_id=1)
    combined = extract_features(pd.concat([a,b],ignore_index=True))
    np.testing.assert_allclose(combined[len(a):],extract_features(b))
    np.testing.assert_allclose(extract_features(a.iloc[:20]),extract_features(a)[:20])

def test_single_row_and_empty_features():
    d = generate_pass(Link(), np.radians(25), seed=1)
    assert extract_features(d.iloc[:1]).shape == (1,24)
    assert extract_features(d.iloc[:0]).shape == (0,24)

def test_mahalanobis_threshold_independent_of_prediction_batch():
    rng = np.random.default_rng(7)
    det = train_novelty_detector(rng.normal(size=(1000,3)),method='mahalanobis')
    point = np.array([[20.,20.,20.]])
    assert novelty_predict(det,point)[0]
    assert novelty_predict(det,point)[0] == novelty_predict(det,np.vstack([point,np.zeros((100,3))]))[0]

def test_finite_key_block_size_is_respected():
    l=Link(); e=np.radians(40)
    assert finite_key_pass(l,e,block_size_s=10) < finite_key_pass(l,e)

@pytest.mark.parametrize('e,dt', [(10,1),(91,1),(40,0),(40,-1)])
def test_invalid_pass_parameters(e,dt):
    with pytest.raises(ValueError): pass_profile(np.radians(e),dt=dt)

def test_one_geo_node_has_no_continuous_latitude_band():
    assert np.isnan(coverage_stats(1,nlat=31,nlon=61)['lat_cont'])

@pytest.mark.parametrize('kwargs', [{'sigma_j':-1},{'p_x':2},{'d_tx':0},{'e_d':.8}])
def test_invalid_link_configuration(kwargs):
    with pytest.raises(ValueError): Link(**kwargs)

def test_all_states_represented_when_budget_permits():
    from satqkd_sentinel.telemetry import STATES
    assert set(generate_dataset(Link(),10).label) == set(STATES)

def test_anomaly_reduces_model_key_yield():
    l=Link();e=np.radians(25)
    nominal=generate_pass(l,e,seed=42)
    jam=generate_pass(l,e,state='optical_jamming',severity=1,onset_fraction=0,seed=42)
    cloud=generate_pass(l,e,state='cloud_attenuation',severity=1,onset_fraction=0,seed=42)
    assert jam.key_bits.sum() < nominal.key_bits.sum()
    assert cloud.key_bits.sum() < nominal.key_bits.sum()
    np.testing.assert_allclose(cloud.eta,10**(-cloud.loss_db/10))

def test_nominal_signal_is_detection_gain():
    l=Link();d=generate_pass(l,np.radians(25),seed=1)
    np.testing.assert_allclose(d.signal_count,l.y0()-np.expm1(-d.eta*l.mu))

def test_static_baseline_requires_training_calibration():
    from satqkd_sentinel.evaluation import static_threshold_baseline
    with pytest.raises(ValueError):
        static_threshold_baseline(np.zeros((3,2)),np.array(['nominal']*3))
    m=static_threshold_baseline(np.array([[0.,0.],[10.,10.]]),np.array(['nominal','optical_jamming']),X_nominal_train=np.zeros((10,2)))
    assert m['detection_rate']==1 and m['false_positive_rate']==0

def test_explicit_finite_key_no_data_and_invalid_counts():
    from satqkd_sentinel.finitekey import finite_key_length
    assert finite_key_length(0,0,0,0,0,0,0)==0
    with pytest.raises(ValueError): finite_key_length(20,1,1,.01,10,10,10)

def test_no_light_no_background_has_zero_rate():
    rate,qber=Link(p_dc=0,h_b=0).rate(0)
    assert rate==0 and np.isfinite(qber)

def test_geometry_empty_sites_and_invalid_time_step():
    from satqkd_sentinel.geo import contact_plan
    cp=contact_plan(4,[],hours=1,dt=10)
    assert cp['site'].shape==(0,len(cp['t']))
    with pytest.raises(ValueError): contact_plan(4,[],dt=0)

def test_availability_impossible_redundancy():
    from satqkd_sentinel.network import network_availability,key_store_model
    assert network_availability(2,.95,redundancy=3)==0
    assert network_availability(2,.95,redundancy=0)==1
    with pytest.raises(ValueError): key_store_model(10,1,100,dt_hours=0)


def test_saved_model_predicts_unlabeled_data_and_cli_errors(tmp_path):
    import json,subprocess,sys,joblib
    from satqkd_sentinel.cli import run_demo
    result=run_demo(tmp_path,n_train=10,n_test=10,seed=11)
    assert result['selection_basis']=='independent validation passes'
    assert result['train_passes']==10 and result['test_passes']==10
    assert 0 <= result['macro_f1'] <= 1
    bundle=joblib.load(tmp_path/'model.joblib')
    d=pd.read_csv(tmp_path/'telemetry.csv').drop(columns=['label','group','severity','onset_s'])
    d.to_csv(tmp_path/'unlabeled.csv',index=False)
    command=[sys.executable,'-m','satqkd_sentinel','predict','--model',str(tmp_path/'model.joblib'),'--input',str(tmp_path/'unlabeled.csv'),'--output',str(tmp_path/'inference.csv')]
    subprocess.run(command,check=True,capture_output=True,text=True)
    expected=pd.read_csv(tmp_path/'predictions.csv').prediction
    actual=pd.read_csv(tmp_path/'inference.csv').prediction
    assert expected.tolist()==actual.tolist()
    assert '<html lang="uk">' in (tmp_path/'report.html').read_text(encoding='utf-8')
    json.loads((tmp_path/'summary.json').read_text())
    failed=subprocess.run([sys.executable,'-m','satqkd_sentinel','demo','--train','1'],capture_output=True,text=True)
    assert failed.returncode==2 and 'at least 10' in failed.stderr
