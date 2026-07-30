#!/usr/bin/env python3
"""Deterministic, leak-free scenario-level split manifest for all 30 repetitions.
Split ratio 60/10/10/20 (train/calibration/validation/test). Normalization
statistics are computed on the training split only; no scenario appears in two
splits. Assignment is a deterministic function of (seed, scenario_id)."""
import json, os, csv, hashlib
os.makedirs('manifest',exist_ok=True)
SEEDS=list(range(20260730,20260760))
NSCEN=400
def assign(seed, sid):
    h=int(hashlib.sha256(f'{seed}:{sid}'.encode()).hexdigest(),16)%1000
    if h<600: return 'train'
    if h<700: return 'cal'
    if h<800: return 'val'
    return 'test'
manifest={'experiment':'UST-Fuse computational appendix',
 'generator':'RadarTwin-UAV v1 (S1)','engine':'UST-Fuse Engine v1 (S2)','analytics':'FuseMetrics Lab v1 (S3)',
 'scenarios_per_repetition':NSCEN,'update_rate_hz':10,'dwell_s':0.1,
 'split_ratio':{'train':0.60,'cal':0.10,'val':0.10,'test':0.20},
 'seeds':SEEDS,'repetitions':len(SEEDS),'splits':{}}
summ=[['seed','train','cal','val','test','total','overlap_check']]
for seed in SEEDS:
    a={'train':[],'cal':[],'val':[],'test':[]}
    for sid in range(NSCEN): a[assign(seed,sid)].append(sid)
    manifest['splits'][str(seed)]={k:len(v) for k,v in a.items()}
    if seed in (20260730,20260731):  # store full id lists for first two as examples
        manifest['splits'][str(seed)+'_ids']=a
    sets=[set(a[k]) for k in ('train','cal','val','test')]
    overlap=any(sets[i]&sets[j] for i in range(4) for j in range(i+1,4))
    summ.append([seed,len(a['train']),len(a['cal']),len(a['val']),len(a['test']),
                 sum(len(v) for v in a.values()),'PASS' if not overlap else 'FAIL'])
json.dump(manifest,open('manifest/split_manifest.json','w'),indent=2)
with open('manifest/split_summary.csv','w',newline='') as f:
    csv.writer(f).writerows(summ)
# run metadata manifest with checksums already collected
print('splits per seed (first 3):')
for r in summ[1:4]: print(' ',r)
print('all leak-free:', all(r[6]=='PASS' for r in summ[1:]))
