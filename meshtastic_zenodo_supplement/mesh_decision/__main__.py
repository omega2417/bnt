import argparse
import json
import sys
from pathlib import Path
from .schema import read_csv
from .demo import generate
from .model import train
from .decisions import predict

def main():
    parser=argparse.ArgumentParser(description='Offline exploratory decision-support prototype (bundled model: synthetic training data only, no measured accuracy)')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('generate-demo');p.add_argument('--output',default='data');p.add_argument('--seed',type=int,default=42)
    p=sub.add_parser('validate');p.add_argument('--data',required=True);p.add_argument('--training',action='store_true')
    p=sub.add_parser('train');p.add_argument('--data',required=True);p.add_argument('--output',required=True);p.add_argument('--seed',type=int,default=42);p.add_argument('--epochs',type=int,default=250)
    p=sub.add_parser('predict');p.add_argument('--data',required=True);p.add_argument('--model',required=True);p.add_argument('--output',required=True)
    a=parser.parse_args()
    try:
        # Input files must never be replaced by generated decisions or model output.
        if a.command=='predict' and Path(a.output).resolve() in {Path(a.data).resolve(),Path(a.model).resolve()}:
            raise ValueError('output must differ from both input and model')
        if a.command=='generate-demo':print(json.dumps({'synthetic_rows':generate(a.output,a.seed)}))
        elif a.command=='validate':print(json.dumps({'valid_rows':len(read_csv(a.data,training=a.training))}))
        elif a.command=='train':
            r=train(a.data,a.output,a.seed,a.epochs)
            print(json.dumps({'status':r['status'],'evidence_status':r['evidence_status'],'test':r['neural_test']}))
        else:print(json.dumps({'recommendations':len(predict(a.data,a.model,a.output))}))
    except (ValueError,OSError,KeyError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2
    return 0

if __name__=='__main__':sys.exit(main())
