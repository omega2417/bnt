import csv, statistics
from collections import defaultdict
def rd(fn): return list(csv.reader(open('tables/'+fn)))
def wr(fn,rows):
    with open('tables/'+fn,'w',newline='') as f: csv.writer(f).writerows(rows)

# agg_metrics_doc: label, mean±std, ci, unit
am=list(csv.DictReader(open('tables/agg_metrics.csv')))
rows=[['Metric','Mean ± SD','95% CI (bootstrap)','Notes']]
notemap={'lat_mean':'analytical model','lat_p95':'analytical model'}
for r in am:
    mean=float(r['mean']);sd=float(r['std'])
    d=3 if abs(mean)<10 else (0 if abs(mean)>100 else 2)
    rows.append([r['label'],f'{mean:.{d}f} ± {sd:.{d}f}',f'[{float(r["ci95_low"]):.{d}f}, {float(r["ci95_high"]):.{d}f}]',notemap.get(r['metric'],'measured')])
wr('agg_metrics_doc.csv',rows)

# table4_doc: drop provenance into method label suffix
def doc_from(src,dst,provcol=-1):
    rows=rd(src); out=[rows[0][:provcol]]
    for r in rows[1:]:
        label=r[0]
        if 'emulated' in r[provcol]: label+=' †'
        out.append([label]+r[1:provcol])
    wr(dst,out)
doc_from('table4_detection_classification.csv','table4_doc.csv')
doc_from('table5_calibration.csv','table5_doc.csv')
doc_from('table6_tracking.csv','table6_doc.csv')
# table7 doc: drop provenance
r7=rd('table7_ablation.csv'); out=[r7[0][:-1]]
for r in r7[1:]: out.append(r[:-1])
wr('table7_doc.csv',out)
# table8 doc
r8=rd('table8_latency.csv'); wr('table8_doc.csv',r8)
# idsw doc
ri=rd('idsw_by_crossing.csv')
out=[['Crossing type','Mean count','SD']]
for r in ri[1:]: out.append([r[0],f'{float(r[1]):.0f}',f'{float(r[2]):.0f}'])
wr('idsw_by_crossing_doc.csv',out)
# significance doc: macro_f1 + id_switches rows
rs=list(csv.DictReader(open('tables/table_significance.csv')))
out=[['Comparison','Metric','raw p','Holm p','sig.','abs Δ','rel Δ%']]
for r in rs:
    if r['metric'] in ('macro_f1','id_switches'):
        out.append([r['comparison'].replace('UST-Fuse vs ',''),r['metric'],r['raw_p'],r['holm_adjusted_p'],r['significant_0.05'],r['abs_diff'],r['rel_diff_pct']])
wr('significance_doc.csv',out)
# split summary head (first 6)
ss=rd('../manifest/split_summary.csv') if False else list(csv.reader(open('manifest/split_summary.csv')))
wr('split_summary_head.csv',ss[:7])
print("doc tables prepared:")
import os
for f in ['agg_metrics_doc','table4_doc','table5_doc','table6_doc','table7_doc','table8_doc','idsw_by_crossing_doc','significance_doc','split_summary_head']:
    print('  ',f, '->', open('tables/'+f+'.csv').readline().strip()[:70])
