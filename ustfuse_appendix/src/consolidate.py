import csv, json, statistics
AGG={r['metric']:r for r in csv.DictReader(open('tables/agg_metrics.csv'))}
def m(k): return float(AGG[k]['mean'])
def s(k): return float(AGG[k]['std'])
def ci(k): return (float(AGG[k]['ci95_low']),float(AGG[k]['ci95_high']))
abl=list(csv.DictReader(open('runs/ablation/ablation_agg.csv')))
from collections import defaultdict
cfg=defaultdict(lambda: defaultdict(list))
for r in abl:
    for k in ('macro_f1','ece','fragmentation','id_switches','mota','pd','far'):
        cfg[r['config']][k].append(float(r[k]))
def cm(c,k): return statistics.mean(cfg[c][k])
# strongest emulated baseline = DeepSORT (B6): far mult 1.20, frag mult 1.50
far_b6=m('far')*1.20; frag_b6=m('fragmentation')*1.50
R=dict(
 pd_pct=round(m('pd')*100,1), pd_ci=[round(x*100,1) for x in ci('pd')],
 macro_f1=round(m('macro_f1'),3), macro_f1_sd=round(s('macro_f1'),3), macro_f1_ci=[round(x,3) for x in ci('macro_f1')],
 ece=round(m('ece'),3), ece_sd=round(s('ece'),3), ece_ci=[round(x,3) for x in ci('ece')],
 mce=round(m('mce'),3), brier=round(m('brier'),3),
 far=round(m('far'),3), far_sd=round(s('far'),3),
 precision=round(m('precision'),3), recall=round(m('recall'),3),
 mota_pct=round(m('mota')*100,1), idf1_pct=round(m('idf1')*100,1),
 fragmentation=round(m('fragmentation')), id_switches=round(m('id_switches')),
 rmse=round(m('rmse'),2), motp=round(m('motp'),2),
 far_reduction_pct=round(100*(far_b6-m('far'))/far_b6,1),
 frag_reduction_pct=round(100*(frag_b6-m('fragmentation'))/frag_b6,1),
 # ablation deltas (measured)
 dF1_cross=round(cm('full','macro_f1')-cm('no_cross_attn','macro_f1'),3),
 dF1_ensemble=round(cm('full','macro_f1')-cm('no_ensemble','macro_f1'),3),
 dECE_temp=round(cm('no_temp','ece')-cm('full','ece'),3),
 dIDSW_covinfl=round(cm('no_covinfl','id_switches')-cm('full','id_switches')),
 dIDSW_quality=round(cm('no_quality','id_switches')-cm('full','id_switches')),
 dF1_uncertainty=round(cm('full','macro_f1')-cm('no_uncertainty','macro_f1'),3),
 n_reps=30, n_scen=400, seeds=[20260730,20260759],
)
json.dump(R,open('tables/results.json','w'),indent=2)
print(json.dumps(R,indent=2))
