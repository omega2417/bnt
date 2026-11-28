"""Run from any directory: python /path/to/run_demo.py [--output /new/folder]."""
import argparse
from pathlib import Path
from mesh_decision.demo import generate
from mesh_decision.model import train
from mesh_decision.decisions import predict

def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=Path(__file__).resolve().parent/'demo_output')
    args=p.parse_args();dest=args.output.resolve()
    if dest.exists():p.error('output already exists; choose a new directory to preserve prior results')
    generate(dest/'data')
    report=train(dest/'data/synthetic_training.csv',dest/'models')
    predict(dest/'data/inference_examples.csv',dest/'models/neural_model.npz',dest/'decisions.csv')
    print('Synthetic demonstration only. Outputs:',dest)
    print('Software self-consistency check on synthetic hold-out (NOT predictive accuracy):')
    print('  ROC AUC neural %.4f, logistic baseline %.4f'%(report['neural_test']['roc_auc'],report['logistic_baseline_test']['roc_auc']))
    print('  Labels come from the invented formula in mesh_decision/demo.py; no field data exist.')
    print('No devices or external services were contacted.')
if __name__=='__main__':main()
