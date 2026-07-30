#!/usr/bin/env python3
import csv, statistics
from scipy import stats as sps
from collections import defaultdict

abl=list(csv.DictReader(open('runs/ablation/ablation_agg.csv')))
by=defaultdict(lambda: defaultdict(dict))   # config -> metric -> seed->val
for r in abl:
    for k in ('macro_f1','ece','fragmentation','id_switches','mota','idf1'):
        by[r['config']][k][r['seed']]=float(r[k])
seeds=sorted({r['seed'] for r in abl})

def paired(cfgA,cfgB,metric):
    a=[by[cfgA][metric][s] for s in seeds]; b=[by[cfgB][metric][s] for s in seeds]
    diff=[x-y for x,y in zip(a,b)]
    if all(abs(d)<1e-12 for d in diff):
        return 1.0, statistics.mean(a)-statistics.mean(b), 0.0
    try:
        w,p=sps.wilcoxon(a,b,zero_method='wilcox',correction=False,alternative='two-sided')
    except Exception:
        p=1.0
    absdiff=statistics.mean(a)-statistics.mean(b)
    reldiff=100*absdiff/statistics.mean(b) if statistics.mean(b)!=0 else 0.0
    return p, absdiff, reldiff

def holm(pairs):
    # pairs: list of (name, p, absdiff, reldiff)
    idx=sorted(range(len(pairs)), key=lambda i:pairs[i][1])
    m=len(pairs); adj=[0]*m; prev=0
    for rank,i in enumerate(idx):
        a=min(1.0,(m-rank)*pairs[i][1]); a=max(a,prev); adj[i]=a; prev=a
    return adj

# Comparison of full UST-Fuse vs component-toggle configurations, macro_f1
rows=[]
compare=[('B7 (no uncertainty)','no_uncertainty'),('B4 (no semantic)','no_semantic'),
         ('- quality','no_quality'),('- cross-feature attn','no_cross_attn'),
         ('- ensemble','no_ensemble'),('- temperature','no_temp'),('- covariance inflation','no_covinfl')]
outcsv=[['comparison','metric','test','raw_p','holm_adjusted_p','significant_0.05','abs_diff','rel_diff_pct']]
for metric in ['macro_f1','ece','id_switches','mota']:
    triples=[]
    for name,cfg in compare:
        p,ad,rd=paired('full',cfg,metric); triples.append((f'UST-Fuse vs {name}',p,ad,rd))
    adj=holm([(t[0],t[1]) for t in triples])
    for (nm,p,ad,rd),pa in zip(triples,adj):
        outcsv.append([nm,metric,'wilcoxon_signed_rank',f'{p:.4g}',f'{pa:.4g}','yes' if pa<0.05 else 'no',f'{ad:+.4f}',f'{rd:+.2f}'])
with open('tables/table_significance.csv','w',newline='') as f: csv.writer(f).writerows(outcsv)
# print macro_f1 block
print("Significance (paired Wilcoxon over 30 seeds, Holm-corrected):")
for r in outcsv:
    if r[1]=='macro_f1' or r[0]=='comparison': print('  ',r[0],r[1],'rawp=',r[3],'holm=',r[4],r[5],'Δ=',r[6])
print("---- id_switches ----")
for r in outcsv:
    if r[1]=='id_switches': print('  ',r[0],'holm=',r[4],r[5],'Δ=',r[6])
