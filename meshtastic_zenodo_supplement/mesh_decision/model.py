"""Train a grouped MLP and export numerical arrays without pickle."""
import copy
import hashlib
import json
import platform
from pathlib import Path
import numpy as np
from .schema import FEATURES, TARGET, read_csv, validate_row, write_csv

def dump_json(path, obj):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')

def metrics(y, probability):
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, brier_score_loss, log_loss, roc_auc_score, confusion_matrix
    pred=(probability >= .5).astype(int)
    return {"n":len(y),"accuracy":float(accuracy_score(y,pred)),
        "balanced_accuracy":float(balanced_accuracy_score(y,pred)),
        "brier_score":float(brier_score_loss(y,probability)),
        "log_loss":float(log_loss(y,probability,labels=[0,1])),
        "roc_auc":float(roc_auc_score(y,probability)) if len(set(y))==2 else None,
        "confusion_matrix_rows_true_0_1":confusion_matrix(y,pred,labels=[0,1]).tolist()}

def split_indices(groups, seed):
    from sklearn.model_selection import GroupShuffleSplit
    groups=np.asarray(groups)
    if len(set(groups))<12:
        raise ValueError("at least 12 independent group_id values are required for the research split")
    rest,test=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=seed).split(groups,groups=groups))
    tr,va=next(GroupShuffleSplit(n_splits=1,test_size=.25,random_state=seed+1).split(rest,groups=groups[rest]))
    return {"train":rest[tr],"validation":rest[va],"test":test}

class NeuralModel:
    def __init__(self, path):
        with np.load(path,allow_pickle=False) as z:
            self.meta=json.loads(str(z['metadata_json'].item()))
            if self.meta.get('features') != FEATURES or self.meta.get('format_version') != 1:
                raise ValueError('incompatible model schema')
            if self.meta.get('training_provenance') not in {'synthetic','measured'}:
                raise ValueError('invalid model provenance')
            self.mean=z['mean'].copy();self.scale=z['scale'].copy()
            self.low=z['training_min'].copy();self.high=z['training_max'].copy()
            self.weights=[z[f'w{i}'].copy() for i in range(3)]
            self.biases=[z[f'b{i}'].copy() for i in range(3)]
        n=len(FEATURES)
        if any(v.shape != (n,) for v in [self.mean,self.scale,self.low,self.high]):
            raise ValueError('invalid normalization dimensions')
        expected=[(n,16),(16,8),(8,1)]
        for w,b,shape in zip(self.weights,self.biases,expected):
            if w.shape!=shape or b.shape!=(shape[1],):raise ValueError('invalid layer dimensions')
        arrays=[self.mean,self.scale,self.low,self.high]+self.weights+self.biases
        if any(not np.isfinite(a).all() for a in arrays) or (self.scale<=0).any():
            raise ValueError('model arrays must be finite with positive scales')

    def scores(self, x):
        x=np.asarray(x,dtype=float)
        if x.ndim!=2 or x.shape[1]!=len(FEATURES) or not np.isfinite(x).all():
            raise ValueError('invalid feature matrix')
        a=(x-self.mean)/self.scale
        for w,b in zip(self.weights[:-1],self.biases[:-1]):a=np.maximum(a@w+b,0)
        logits=np.clip(a@self.weights[-1]+self.biases[-1],-709,709)
        return (1/(1+np.exp(-logits))).ravel()

    def outside_training_range(self,x):
        # Simple marginal range screen, not a general detector of distribution shift.
        return [name for name,v,lo,hi in zip(FEATURES,x,self.low,self.high) if v<lo or v>hi]

def train(data, output, seed=42, epochs=250, patience=25):
    import sklearn
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import log_loss
    if epochs<1 or patience<1:raise ValueError('epochs and patience must be positive')
    raw=read_csv(data,training=True)
    rows=[validate_row(r,True) for r in raw]
    provenance={r['provenance'] for r in rows}
    if len(provenance)!=1:raise ValueError('do not mix synthetic and measured rows in one training run')
    # Retransmissions of an event cannot silently receive independent group labels.
    group_for_run={}
    for r in rows:
        if r['run_id'] in group_for_run and group_for_run[r['run_id']]!=r['group_id']:
            raise ValueError('one run_id cannot belong to multiple groups')
        group_for_run[r['run_id']]=r['group_id']
    x=np.array([[r[f] for f in FEATURES] for r in rows]);y=np.array([r[TARGET] for r in rows])
    groups=np.array([r['group_id'] for r in rows]);splits=split_indices(groups,seed)
    for name,ix in splits.items():
        if set(y[ix])!={0,1}:raise ValueError(f'{name} needs both outcomes; collect more independent groups')
    tr,va,te=(splits[k] for k in ['train','validation','test'])
    scaler=StandardScaler().fit(x[tr]);xs=scaler.transform(x)
    clf=MLPClassifier(hidden_layer_sizes=(16,8),activation='relu',solver='adam',
        learning_rate_init=.003,alpha=.01,random_state=seed,batch_size=min(128,len(tr)),
        shuffle=True,early_stopping=False,max_iter=1)
    best=None;best_loss=float('inf');stale=0;history=[];best_epoch=0
    for epoch in range(1,epochs+1):
        clf.partial_fit(xs[tr],y[tr],classes=np.array([0,1]))
        loss=float(log_loss(y[va],clf.predict_proba(xs[va])[:,1],labels=[0,1]))
        history.append({'epoch':epoch,'training_loss':float(clf.loss_),'validation_log_loss':loss})
        if loss < best_loss-1e-6:
            best_loss=loss;best=copy.deepcopy(clf);best_epoch=epoch;stale=0
        else:stale+=1
        if stale>=patience:break
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    meta={'format_version':1,'features':FEATURES,'architecture':[len(FEATURES),16,8,1],
        'target':TARGET,'seed':seed,'training_provenance':next(iter(provenance)),
        'score_status':'uncalibrated research score; synthetic models are demonstration only',
        'best_epoch':best_epoch,'data_sha256':hashlib.sha256(Path(data).read_bytes()).hexdigest(),
        'versions':{'python':platform.python_version(),'numpy':np.__version__,'scikit_learn':sklearn.__version__}}
    arrays={'metadata_json':np.array(json.dumps(meta)),'mean':scaler.mean_,'scale':scaler.scale_,
            'training_min':x[tr].min(axis=0),'training_max':x[tr].max(axis=0)}
    arrays.update({f'w{i}':w for i,w in enumerate(best.coefs_)})
    arrays.update({f'b{i}':b for i,b in enumerate(best.intercepts_)})
    model_path=output/'neural_model.npz';np.savez_compressed(model_path,**arrays)
    exported=NeuralModel(model_path)
    export_error=float(np.max(np.abs(exported.scores(x)-best.predict_proba(xs)[:,1])))
    if export_error>1e-10:raise RuntimeError('exported model does not reproduce training-library inference')
    logistic=LogisticRegression(max_iter=1000,random_state=seed).fit(xs[tr],y[tr])
    scores=exported.scores(x[te]);baseline=logistic.predict_proba(xs[te])[:,1]
    split_groups={k:sorted(set(groups[ix])) for k,ix in splits.items()}
    synthetic=provenance=={'synthetic'}
    report={'status':'synthetic demonstration' if synthetic else 'exploratory measured-data evaluation',
        'evidence_status':('SOFTWARE SELF-CONSISTENCY CHECK ON SYNTHETIC DATA. The scores below show how well the '
            'networks recover the invented formula in mesh_decision/demo.py that generated the labels. They are '
            'NOT predictive accuracy for any real Meshtastic network; no such accuracy has been measured.')
            if synthetic else
            ('Exploratory evaluation on user-supplied rows labelled as measured. A random group split is not an '
             'independent field validation; calibration and a separate deployment test are still required.'),
        'metadata':meta,'split_rows':{k:len(ix) for k,ix in splits.items()},'split_groups':split_groups,
        'neural_test':metrics(y[te],scores),'logistic_baseline_test':metrics(y[te],baseline),
        'constant_prevalence_baseline_test':metrics(y[te],np.full(len(te),y[tr].mean())),
        'export_max_abs_error':export_error,'epochs_run':len(history),
        'threshold_for_metrics':.5,'advice_threshold':.75,
        'limitations':['Test scores are not evidence of field performance when trained on synthetic data.',
            'On synthetic data the labels come from a logistic formula, so a logistic baseline is expected to do at least as well as the network.',
            'Scores are not calibrated probabilities.','Random group split does not test future deployments.',
            'This package does not reproduce the manuscript economic and propagation models.']}
    dump_json(output/'evaluation.json',report);dump_json(output/'model_metadata.json',meta)
    write_csv(output/'training_history.csv',history,['epoch','training_loss','validation_log_loss'])
    predictions=[dict(event_id=rows[i]['event_id'],group_id=rows[i]['group_id'],
                    completed_on_time=int(y[i]),neural_score=float(s),logistic_score=float(b))
                 for i,s,b in zip(te,scores,baseline)]
    write_csv(output/'heldout_predictions.csv',predictions,list(predictions[0]))
    splitrows=[{'event_id':rows[i]['event_id'],'group_id':rows[i]['group_id'],'partition':name}
               for name,ix in splits.items() for i in ix]
    write_csv(output/'split_manifest.csv',splitrows,['event_id','group_id','partition'])
    return report
