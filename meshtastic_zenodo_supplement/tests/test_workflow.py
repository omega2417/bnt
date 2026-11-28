import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
import numpy as np
from mesh_decision.demo import generate
from mesh_decision.schema import FEATURES, COLUMNS, TARGET, read_csv, validate_row, write_csv
from mesh_decision.model import NeuralModel, train
from mesh_decision.decisions import predict, recommend

class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();cls.root=Path(cls.temp.name)
        generate(cls.root/'data',groups=30,per_group=12)
        cls.training=cls.root/'data/synthetic_training.csv'
        cls.report=train(cls.training,cls.root/'model',epochs=25)
        cls.model=NeuralModel(cls.root/'model/neural_model.npz')
        cls.rows=read_csv(cls.training,training=True)
        cls.base=cls.rows[0].copy()
        cls.base.update(aoi_s='30',battery_pct='80',backup_minutes='120',terminal_available='1',
                        s0_available='1',deadline_remaining_s='290')
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def test_complete_training_and_export_equivalence(self):
        self.assertEqual(sum(self.report['split_rows'].values()),360)
        self.assertLess(self.report['export_max_abs_error'],1e-10)
        self.assertGreaterEqual(self.report['neural_test']['roc_auc'],0)
        self.assertLessEqual(self.report['neural_test']['roc_auc'],1)

    def test_synthetic_outputs_carry_evidence_status(self):
        self.assertIn('NOT predictive accuracy',self.report['evidence_status'])
        v=recommend(self.base,self.model)
        self.assertIn('no measured predictive accuracy',v['evidence_status'])
        out=predict(self.root/'data/inference_examples.csv',self.root/'model/neural_model.npz',self.root/'ev.csv')
        self.assertTrue(all('synthetic demonstration' in r['evidence_status'] for r in out))
        with open(self.root/'ev.csv',encoding='utf-8') as f:self.assertIn('evidence_status',f.readline())

    def test_independent_groups_and_training_only_scaler(self):
        g=self.report['split_groups'];sets=[set(g[k]) for k in ['train','validation','test']]
        for i in range(3):
            for j in range(i):self.assertFalse(sets[i]&sets[j])
        train_rows=[validate_row(r,True) for r in self.rows if r['group_id'] in sets[0]]
        expected=np.array([[r[f] for f in FEATURES] for r in train_rows]).mean(axis=0)
        np.testing.assert_allclose(self.model.mean,expected)

    def test_fixed_seed_reproducibility(self):
        generate(self.root/'again',groups=30,per_group=12)
        self.assertEqual(self.training.read_bytes(),(self.root/'again/synthetic_training.csv').read_bytes())
        train(self.training,self.root/'model_again',epochs=25)
        other=NeuralModel(self.root/'model_again/neural_model.npz')
        x=np.array([[float(r[f]) for f in FEATURES] for r in self.rows])
        np.testing.assert_allclose(self.model.scores(x),other.scores(x),rtol=0,atol=1e-12)

    def test_guard_precedence_and_human_review(self):
        cases=[({'deadline_remaining_s':0},'EXPIRED'),({'terminal_available':0},'RESTORE_DISPATCH'),
               ({'s0_available':0},'RESTORE_STATION'),({'battery_pct':14.9},'RESTORE_POWER'),
               ({'backup_minutes':4.9},'RESTORE_POWER'),({'aoi_s':121},'REFRESH_DATA'),
               ({'provenance':'measured'},'MODEL_NOT_VALIDATED'),({'snr_db':'NaN'},'INPUT_REVIEW'),
               ({'pdr_5m':1.1},'INPUT_REVIEW'),({'rssi_dbm':''},'INPUT_REVIEW')]
        for changes,expected in cases:
            with self.subTest(changes=changes):
                r=self.base.copy();r.update(changes);v=recommend(r,self.model)
                self.assertEqual(v['decision'],expected);self.assertIs(v['human_review_required'],True)

    def test_future_features_and_early_outcomes_rejected(self):
        r=self.base.copy();r['feature_window_end']='2030-01-01T00:00:00Z'
        with self.assertRaisesRegex(ValueError,'future'):validate_row(r)
        r=self.base.copy();r['outcome_observed_at']=r['decision_time']
        with self.assertRaisesRegex(ValueError,'finalized'):validate_row(r,True)

    def test_duplicates_not_independent_events(self):
        f=self.root/'duplicate.csv';write_csv(f,[self.rows[0],self.rows[0]],COLUMNS+[TARGET,'outcome_observed_at'])
        with self.assertRaisesRegex(ValueError,'duplicate'):read_csv(f,True)

    def test_mixed_data_rejected(self):
        rows=[r.copy() for r in self.rows];rows[0]['provenance']='measured'
        f=self.root/'mixed.csv';write_csv(f,rows,COLUMNS+[TARGET,'outcome_observed_at'])
        with self.assertRaisesRegex(ValueError,'mix'):train(f,self.root/'badmodel')

    def test_outside_range_and_prediction_input_unchanged(self):
        r=self.base.copy();r['rssi_dbm']=-150
        self.assertEqual(recommend(r,self.model)['decision'],'OUT_OF_DISTRIBUTION')
        source=self.root/'data/inference_examples.csv';before=hashlib.sha256(source.read_bytes()).hexdigest()
        out=predict(source,self.root/'model/neural_model.npz',self.root/'predictions.csv')
        self.assertEqual(len(out),8);self.assertEqual(out[-1]['decision'],'INPUT_REVIEW')
        self.assertEqual(before,hashlib.sha256(source.read_bytes()).hexdigest())

    def test_public_cli_rejects_overwrite(self):
        p=subprocess.run([sys.executable,'-m','mesh_decision','predict','--data',str(self.training),
          '--model',str(self.root/'model/neural_model.npz'),'--output',str(self.training)],capture_output=True,text=True)
        self.assertEqual(p.returncode,2);self.assertIn('output must differ',p.stderr)

    def test_header_only_template_is_not_a_dataset(self):
        f=self.root/'empty.csv';write_csv(f,[],COLUMNS)
        with self.assertRaisesRegex(ValueError,'no observations'):read_csv(f)

    def test_score_policy_at_declared_boundaries(self):
        class FixedScore:
            meta={'training_provenance':'synthetic'}
            def outside_training_range(self,x):return []
            def scores(self,x):return np.array([self.value])
        stub=FixedScore()
        for value,action in [(0.5,'MANUAL_REVIEW'),(.74,'CHECK_LINK_OR_ALTERNATIVE'),(.75,'CONTINUE_WITH_MONITORING')]:
            stub.value=value
            self.assertEqual(recommend(self.base,stub)['decision'],action)

if __name__=='__main__':unittest.main()
