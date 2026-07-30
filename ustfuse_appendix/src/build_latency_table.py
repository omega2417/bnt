import csv, statistics
from collections import defaultdict
rows=list(csv.DictReader(open('work/ustfuse_timing.csv')))
byN=defaultdict(lambda: defaultdict(list))
for r in rows:
    n=int(r['n_tracks'])
    for k in ('encode_us','ensemble_us','assoc_us','total_us'):
        byN[n][k].append(float(r[k]))
targets=[1,5,10,20]
out=[['n_targets','encoder_us','ensemble_us','association_us','total_mean_us','total_p95_us','n_samples']]
def stat(v): 
    v=sorted(v); return statistics.mean(v), v[min(len(v)-1,int(0.95*len(v)))]
for n in targets:
    if n not in byN: continue
    enc=statistics.mean(byN[n]['encode_us']); ens=statistics.mean(byN[n]['ensemble_us'])
    asc=statistics.mean(byN[n]['assoc_us']); tm,tp=stat(byN[n]['total_us'])
    out.append([n,f'{enc:.3f}',f'{ens:.3f}',f'{asc:.3f}',f'{tm:.3f}',f'{tp:.3f}',len(byN[n]['total_us'])])
# max supported: highest N with >=20 samples
maxN=max(n for n in byN if len(byN[n]['total_us'])>=20)
em=statistics.mean(byN[maxN]['encode_us']); en=statistics.mean(byN[maxN]['ensemble_us'])
am=statistics.mean(byN[maxN]['assoc_us']); tm,tp=stat(byN[maxN]['total_us'])
out.append([f'{maxN} (max observed)',f'{em:.3f}',f'{en:.3f}',f'{am:.3f}',f'{tm:.3f}',f'{tp:.3f}',len(byN[maxN]['total_us'])])
with open('tables/table8_latency.csv','w',newline='') as f: csv.writer(f).writerows(out)
# association overtakes encoder at:
cross=None
for n in sorted(byN):
    if len(byN[n]['total_us'])<20: continue
    if statistics.mean(byN[n]['assoc_us'])>statistics.mean(byN[n]['encode_us']):
        cross=n; break
# extrapolate max targets under 100ms p95: measured p95 grows ~linear; fit
ns=[n for n in sorted(byN) if len(byN[n]['total_us'])>=20]
p95s=[stat(byN[n]['total_us'])[1] for n in ns]
# linear fit p95 = a*n + b
import statistics as st
mn=st.mean(ns); mp=st.mean(p95s)
a=sum((n-mn)*(p-mp) for n,p in zip(ns,p95s))/sum((n-mn)**2 for n in ns); b=mp-a*mn
max_rt=int((100000-b)/a)  # 100 ms = 100000 us
print("Table 8 (latency, MEASURED wall-clock, microseconds):")
for r in out: print('  ',r)
print(f"\nassociation overtakes encoder at N={cross}")
print(f"p95 linear fit: {a:.3f} us/target + {b:.3f}; extrapolated max targets with p95<100ms: ~{max_rt}")
open('tables/latency_notes.txt','w').write(
 f"association_overtakes_encoder_at_N={cross}\n"
 f"p95_slope_us_per_target={a:.4f}\np95_intercept_us={b:.4f}\n"
 f"extrapolated_max_targets_p95_under_100ms={max_rt}\n"
 f"update_interval_ms=100\nmeasured_max_targets_observed={maxN}\n")
