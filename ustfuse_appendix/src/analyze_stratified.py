#!/usr/bin/env python3
"""Genuine stratified analyses on one seed's real S1+S2 CSVs.
Usage: analyze_stratified.py <dir_with_csvs> <seed> <out_dir>
Appends small per-bin CSV fragments (seed column first) for later aggregation.
Every value is a deterministic function of the real corpus."""
import csv, math, sys, os
from collections import defaultdict

d, seed, outd = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(outd, exist_ok=True)
def P(f): return os.path.join(d, f)
CN = {0:'UAV',1:'BIRD',2:'OTHER'}
def clampd(v,lo,hi): return lo if v<lo else (hi if v>hi else v)

# ---------- load ----------
meas={}; meas_all=[]
with open(P('radartwin_measurements.csv')) as f:
    r=csv.reader(f); next(r)
    for v in r:
        if len(v)<13: continue
        sc=int(v[0]); tk=int(v[1]); tid=int(v[3])
        rec=dict(az=float(v[5]),el=float(v[6]),rv=float(v[7]),snr=float(v[8]),
                 clut=float(v[9]),comp=float(v[10]),md=float(v[11]),q=float(v[12]))
        if tid>=0: meas[(sc,tk,tid)]=rec
        meas_all.append((tid,rec))
truthcls={}; truth_ticks=defaultdict(set); truth_rows=[]
with open(P('radartwin_truth.csv')) as f:
    r=csv.reader(f); next(r)
    for v in r:
        if len(v)<8: continue
        sc=int(v[0]); tk=int(v[1]); tid=int(v[3]); cls=int(v[4])
        truthcls[tid]=cls; truth_ticks[tid].add(tk)
        truth_rows.append((sc,tk,tid,cls,float(v[5]),float(v[6]),float(v[7])))
cls_rows=[]
with open(P('ustfuse_classifications.csv')) as f:
    r=csv.reader(f); next(r)
    for v in r:
        if len(v)<13: continue
        cls_rows.append((int(v[0]),int(v[1]),int(v[3]),int(v[4]),float(v[5]),float(v[6]),
                         float(v[7]),float(v[8]),float(v[9]),float(v[10]),float(v[11]),float(v[12])))
track_rows=[]
with open(P('ustfuse_tracks.csv')) as f:
    r=csv.reader(f); next(r)
    for v in r:
        if len(v)<9: continue
        track_rows.append((int(v[0]),int(v[1]),int(v[3]),int(v[4]),float(v[6]),float(v[7]),float(v[8])))

def macro_f1(conf):
    f1s=[]
    for c in range(3):
        tp=conf[c][c]; fp=sum(conf[k][c] for k in range(3) if k!=c); fn=sum(conf[c][k] for k in range(3) if k!=c)
        prec=tp/(tp+fp) if tp+fp else 0.0; rec=tp/(tp+fn) if tp+fn else 0.0
        f1s.append(2*prec*rec/(prec+rec) if prec+rec else 0.0)
    return sum(f1s)/3

snr_bins=[(-5,0),(0,5),(5,10),(10,15),(15,20),(20,30)]

# A) macro-F1 vs SNR (real SNR from measurements)
sc_conf={i:[[0]*3 for _ in range(3)] for i in range(len(snr_bins))}
for (sc,tk,tid,pred,*rest) in cls_rows:
    if tid<0: continue
    m=meas.get((sc,tk,tid)); tc=truthcls.get(tid)
    if m is None or tc is None: continue
    for i,(lo,hi) in enumerate(snr_bins):
        if lo<=m['snr']<hi: sc_conf[i][tc][pred]+=1; break
with open(os.path.join(outd,'f1_vs_snr.csv'),'a',newline='') as f:
    w=csv.writer(f)
    for i,(lo,hi) in enumerate(snr_bins):
        n=sum(sum(rw) for rw in sc_conf[i])
        w.writerow([seed,f'{lo}..{hi}',(lo+hi)/2,f'{macro_f1(sc_conf[i]):.5f}',n])

# C) cross-feature attention vs SNR (replicates S2 crossFeatureAttention)
def attention(m):
    spec0=clampd(m['md']/6.0,0,1); spec1=clampd((m['snr']+5.0)/40.0,0,1)
    base=[1.0,1.4,0.8,0.6]; se=0.5*(spec0+spec1)
    base[1]*=(0.5+se); base[3]*=(0.5+clampd(m['q'],0,1))
    mx=max(base); ex=[math.exp(b-mx) for b in base]; s=sum(ex)
    return [e/s*4.0 for e in ex]
att={i:[0.0,0.0,0.0,0.0,0] for i in range(len(snr_bins))}
for tid,m in meas_all:
    if tid<0: continue
    for i,(lo,hi) in enumerate(snr_bins):
        if lo<=m['snr']<hi:
            w=attention(m)
            for j in range(4): att[i][j]+=w[j]
            att[i][4]+=1; break
with open(os.path.join(outd,'attention_vs_snr.csv'),'a',newline='') as f:
    ww=csv.writer(f)
    for i,(lo,hi) in enumerate(snr_bins):
        n=att[i][4]
        if n==0: ww.writerow([seed,f'{lo}..{hi}',(lo+hi)/2,0,0,0,0,0]); continue
        ww.writerow([seed,f'{lo}..{hi}',(lo+hi)/2]+[f'{att[i][j]/n:.5f}' for j in range(4)]+[n])

# tracking core (mirrors S3 greedy gated association)
truthByFrame=defaultdict(list); trackByFrame=defaultdict(list)
for (sc,tk,tid,cls,x,y,z) in truth_rows: truthByFrame[(sc,tk)].append((tid,cls,x,y,z))
for (sc,tk,trk,pc,x,y,z) in track_rows: trackByFrame[(sc,tk)].append((trk,pc,x,y,z))
gate=60.0
truth2track={}; truthActive={}; truthFrag=defaultdict(int)
track_owner={}; idsw_pair=defaultdict(int)
for fr in sorted(truthByFrame.keys()):
    gts=truthByFrame[fr]; trks=list(trackByFrame.get(fr,[]))
    used=[False]*len(trks)
    for (tid,cls,x,y,z) in gts:
        best=gate; bj=-1
        for j,(trk,pc,tx,ty,tz) in enumerate(trks):
            if used[j]: continue
            dd=math.sqrt((tx-x)**2+(ty-y)**2+(tz-z)**2)
            if dd<best: best=dd; bj=j
        if bj>=0:
            used[bj]=True; trk=trks[bj][0]; prev=truth2track.get(tid)
            if prev is not None and prev!=trk:
                other=track_owner.get(trk)
                oc=truthcls.get(other) if other is not None else None
                if oc is None: pair='spurious/new-track'
                else: pair='-'.join(sorted([CN[cls],CN[oc]]))
                idsw_pair[pair]+=1
            if prev is None or not truthActive.get(tid,False): truthFrag[tid]+=1
            truth2track[tid]=trk; truthActive[tid]=True; track_owner[trk]=tid
        else:
            if tid in truthActive: truthActive[tid]=False

# B) fragmentation vs observation completeness (per-truth)
# completeness = detected measurement ticks / existence ticks
comp_bins=[0.40,0.50,0.60,0.70,0.80,0.90,1.001]
comp_labels=['0.40','0.50','0.60','0.70','0.80','0.90','1.00']
det_ticks=defaultdict(set)
for (sc,tk,tid) in meas.keys(): det_ticks[tid].add(tk)
bin_frag=defaultdict(lambda:[0,0])  # binidx -> [frag_sum, n_truth]
for tid,ticks in truth_ticks.items():
    if not ticks: continue
    comp=len(det_ticks.get(tid,set()))/len(ticks)
    frag=max(0, truthFrag.get(tid,0)-1)
    bi=0
    for i,ub in enumerate(comp_bins):
        if comp<=ub: bi=i; break
    bin_frag[bi][0]+=frag; bin_frag[bi][1]+=1
with open(os.path.join(outd,'frag_vs_completeness.csv'),'a',newline='') as f:
    w=csv.writer(f)
    for i,lab in enumerate(comp_labels):
        s,n=bin_frag.get(i,[0,0])
        w.writerow([seed,lab,f'{(s/n if n else 0):.5f}',s,n])

# ID switches by crossing type
with open(os.path.join(outd,'idsw_by_crossing.csv'),'a',newline='') as f:
    w=csv.writer(f)
    for pair in ['UAV-UAV','BIRD-UAV','OTHER-UAV','BIRD-OTHER','BIRD-BIRD','OTHER-OTHER','spurious/new-track']:
        w.writerow([seed,pair,idsw_pair.get(pair,0)])

# D) reliability bins: calibrated (from CSV) + uncalibrated (recovered p^T, T=1.35)
T=1.35
def reliability(rows, use_uncal):
    binC=[0.0]*10; binA=[0.0]*10; binN=[0]*10
    for (sc,tk,tid,pred,conf,ent,epi,ale,q,p0,p1,p2) in rows:
        if tid<0: continue
        tc=truthcls.get(tid)
        if tc is None: continue
        probs=[p0,p1,p2]
        if use_uncal:
            pw=[p**T for p in probs]; s=sum(pw); probs=[x/s for x in pw]
            pr=probs.index(max(probs)); cf=probs[pr]
        else:
            pr=pred; cf=conf
        b=min(9,int(cf*10)); binC[b]+=cf; binA[b]+=1.0 if pr==tc else 0.0; binN[b]+=1
    return binC,binA,binN
for name,uncal in [('calibrated',False),('ensemble_no_temp',True)]:
    binC,binA,binN=reliability(cls_rows,uncal)
    with open(os.path.join(outd,'reliability.csv'),'a',newline='') as f:
        w=csv.writer(f)
        for b in range(10):
            if binN[b]==0: 
                w.writerow([seed,name,f'{b/10:.1f}-{(b+1)/10:.1f}',0,0,0]); continue
            w.writerow([seed,name,f'{b/10:.1f}-{(b+1)/10:.1f}',
                        f'{binC[b]/binN[b]:.5f}',f'{binA[b]/binN[b]:.5f}',binN[b]])

# E) epistemic/aleatoric by correctness (nats), plus overall means
sums={'correct':[0.0,0.0,0],'incorrect':[0.0,0.0,0]}
for (sc,tk,tid,pred,conf,ent,epi,ale,q,p0,p1,p2) in cls_rows:
    if tid<0: continue
    tc=truthcls.get(tid)
    if tc is None: continue
    k='correct' if pred==tc else 'incorrect'
    sums[k][0]+=epi; sums[k][1]+=ale; sums[k][2]+=1
with open(os.path.join(outd,'uncertainty_by_correct.csv'),'a',newline='') as f:
    w=csv.writer(f)
    for k in ('correct','incorrect'):
        e,a,n=sums[k]
        w.writerow([seed,k,f'{(e/n if n else 0):.5f}',f'{(a/n if n else 0):.5f}',n])
print(f'seed {seed} stratified analysis done')
