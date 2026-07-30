#!/usr/bin/env python3
"""Cross-seed aggregation: mean, std, and bootstrap 95% CI for every metric,
computed over the 30 repetitions (seeds 20260730..20260759)."""
import csv, math, statistics

# deterministic LCG so bootstrap is reproducible without external RNG seeds
class LCG:
    def __init__(self, s): self.s=s & 0xFFFFFFFFFFFFFFFF
    def next(self):
        self.s=(6364136223846793005*self.s+1442695040888963407)&0xFFFFFFFFFFFFFFFF
        return self.s
    def randint(self,n): return self.next()%n

def bootstrap_ci(vals, B=10000, seed=20260730):
    rng=LCG(seed); n=len(vals); means=[]
    for _ in range(B):
        s=0.0
        for _ in range(n): s+=vals[rng.randint(n)]
        means.append(s/n)
    means.sort()
    lo=means[int(0.025*B)]; hi=means[int(0.975*B)]
    return lo, hi

rows=list(csv.DictReader(open('runs/aggregate_summary.csv')))
metrics=['pd','far','precision','recall','macro_f1','ece','mce','brier',
         'mota','motp','idf1','fragmentation','id_switches','rmse','lat_mean','lat_p95']
labels={'pd':'Probability of detection Pd','far':'False-alarm rate (per dwell)',
 'precision':'Precision (macro)','recall':'Recall (macro)','macro_f1':'Macro-F1',
 'ece':'ECE','mce':'MCE','brier':'Brier score','mota':'MOTA','motp':'MOTP (m)',
 'idf1':'IDF1','fragmentation':'Fragmentation (count)','id_switches':'ID switches (count)',
 'rmse':'RMSE (m)','lat_mean':'Latency mean (ms, modelled)','lat_p95':'Latency p95 (ms, modelled)'}

out=[]
with open('tables/agg_metrics.csv','w',newline='') as f:
    w=csv.writer(f)
    w.writerow(['metric','label','mean','std','ci95_low','ci95_high','min','max','n'])
    for m in metrics:
        vals=[float(r[m]) for r in rows]
        mean=statistics.mean(vals); sd=statistics.stdev(vals)
        lo,hi=bootstrap_ci(vals)
        w.writerow([m,labels[m],f'{mean:.4f}',f'{sd:.4f}',f'{lo:.4f}',f'{hi:.4f}',
                    f'{min(vals):.4f}',f'{max(vals):.4f}',len(vals)])
        out.append((m,mean,sd,lo,hi))
        print(f'{labels[m]:34s} {mean:9.4f} ± {sd:7.4f}  [95% CI {lo:.4f}, {hi:.4f}]')
print('\nwrote tables/agg_metrics.csv')
