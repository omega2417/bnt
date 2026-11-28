"""Human-reviewed recommendations, not radio or vehicle control."""
import numpy as np
from .schema import FEATURES, validate_row, read_csv, write_csv
from .model import NeuralModel
from . import SYNTHETIC_NOTICE

def recommend(row, model):
    result={'event_id':row.get('event_id',''),'run_id':row.get('run_id',''),
        'provenance':row.get('provenance',''),'model_provenance':model.meta['training_provenance'],
        'neural_score':'','decision':'','reason':'','human_review_required':True,
        'evidence_status':SYNTHETIC_NOTICE if model.meta['training_provenance']=='synthetic'
            else 'model trained on rows labelled measured: exploratory, not independently validated'}
    def done(decision,reason):
        result.update(decision=decision,reason=reason);return result
    try:r=validate_row(row)
    except (ValueError,TypeError) as exc:return done('INPUT_REVIEW',str(exc))
    if r['deadline_remaining_s']<=0:return done('EXPIRED','Original deadline has elapsed; do not replay as a current command.')
    if not r['terminal_available']:return done('RESTORE_DISPATCH','Operator terminal is unavailable.')
    if not r['s0_available']:return done('RESTORE_STATION','Stationary radio is unavailable.')
    if r['battery_pct']<15 or r['backup_minutes']<5:
        return done('RESTORE_POWER','Battery below 15% or estimated required-path backup below 5 min.')
    if r['aoi_s']>120 or r['snapshot_age_s']>120:
        return done('REFRESH_DATA','Status or feature snapshot is older than the proposed 120 s limit.')
    if model.meta['training_provenance']=='synthetic' and r['provenance']=='measured':
        return done('MODEL_NOT_VALIDATED','Synthetic demonstration model cannot advise on measured data; train and validate a field model.')
    x=[r[f] for f in FEATURES];outside=model.outside_training_range(x)
    if outside:return done('OUT_OF_DISTRIBUTION','Outside training feature ranges: '+', '.join(outside))
    score=float(model.scores(np.array([x]))[0]);result['neural_score']=round(score,8)
    if .45<=score<=.55:return done('MANUAL_REVIEW','Neural score is close to the classification boundary.')
    if score<.75:return done('CHECK_LINK_OR_ALTERNATIVE','Score below 0.75; inspect coverage, queue and feasible alternate contact.')
    return done('CONTINUE_WITH_MONITORING','Score at least 0.75 and explicit availability checks passed; operator confirmation remains required.')

def predict(data, model_path, output):
    model=NeuralModel(model_path)
    rows=read_csv(data,strict=False)
    results=[recommend(row,model) for row in rows]
    write_csv(output,results,list(results[0]));return results
