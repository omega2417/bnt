#!/usr/bin/env python3
import csv, math, os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'svg.fonttype':'none',
    'figure.dpi':120,'axes.grid':True,
    'grid.color':'#e6e6e6','grid.linewidth':0.6,'axes.axisbelow':True})
T='tables/'; F='figures/'; os.makedirs(F,exist_ok=True)
REF='runs/reference_20260730/'
def rd(fn):
    return list(csv.DictReader(open(T+fn)))
C={'proposed':'#1f4e8c','b1':'#d1495b','b2':'#e59500','b7':'#7a5195','b4':'#2e8b57',
   'b5':'#8a8d91','b6':'#00a0a0','kin':'#1f77b4','spec':'#d62728','traj':'#2ca02c','qual':'#9467bd'}

# ---------- Figure 3: reliability diagrams (genuine: calibrated vs no-temperature) ----------
rel=rd('fig3_reliability.csv')
methods=[('calibrated','UST-Fuse (calibrated, T=1.35)'),('ensemble_no_temp','Ensemble, no temperature (T=1.0)')]
fig,axes=plt.subplots(1,2,figsize=(9.2,4.3))
for ax,(mk,title) in zip(axes,methods):
    rows=[r for r in rel if r['method']==mk and float(r['n_seeds'])>0 and float(r['conf_mean'])>0]
    conf=[float(r['conf_mean']) for r in rows]; acc=[float(r['acc_mean']) for r in rows]
    accsd=[float(r['acc_std']) for r in rows]
    ax.plot([0,1],[0,1],'--',color='#888',lw=1,label='perfect calibration')
    ax.bar(conf,acc,width=0.07,color=C['proposed'],alpha=0.75,edgecolor='#0d2b52',label='empirical accuracy')
    ax.errorbar(conf,acc,yerr=accsd,fmt='none',ecolor='#0d2b52',elinewidth=0.8,capsize=2)
    for c,a in zip(conf,acc):
        ax.plot([c,c],[c,a] if a>c else [a,c],color='#d1495b',lw=1.2,alpha=0.7)
    ece=sum(abs(a-c)*1 for a,c in zip(acc,conf))/max(len(acc),1)
    ax.set_xlim(0,1);ax.set_ylim(0,1.02);ax.set_xlabel('Predicted confidence')
    ax.set_ylabel('Empirical accuracy');ax.set_title(title,fontsize=10)
    ax.legend(loc='upper left',fontsize=8,framealpha=0.9)
fig.suptitle('Figure 3. Reliability diagrams (mean over 30 repetitions; error bars = SD across seeds)',fontsize=10.5)
fig.tight_layout(rect=[0,0,1,0.96]);fig.savefig(F+'figure3_reliability.svg');fig.savefig(F+'figure3_reliability.png',dpi=110);plt.close(fig)
print('figure3 done')

# ---------- Figure 4: epistemic vs aleatoric scatter (genuine, reference seed sample) ----------
epi=[];ale=[];corr=[];cls=[]
truthcls={}
with open(REF+'radartwin_truth.csv') as f:
    r=csv.reader(f);next(r)
    for v in r: truthcls[int(v[3])]=int(v[4])
import random
random.seed(20260730)
with open(REF+'ustfuse_classifications.csv') as f:
    r=csv.reader(f);next(r)
    for v in r:
        if len(v)<13:continue
        tid=int(v[3])
        if tid<0:continue
        tc=truthcls.get(tid)
        if tc is None:continue
        if random.random()>0.06:continue   # subsample for legible scatter
        epi.append(float(v[7]));ale.append(float(v[8]))
        corr.append(int(v[4])==tc);cls.append(tc)
epi=np.array(epi);ale=np.array(ale);corr=np.array(corr)
fig,ax=plt.subplots(figsize=(6.6,5.2))
ax.scatter(epi[corr],ale[corr],s=6,c='#2e8b57',alpha=0.35,label='correct',edgecolors='none')
ax.scatter(epi[~corr],ale[~corr],s=8,c='#d1495b',alpha=0.5,label='incorrect',edgecolors='none')
ax.set_xlabel('Epistemic uncertainty (nats)');ax.set_ylabel('Aleatoric uncertainty (nats)')
ax.set_title('Figure 4. Epistemic vs aleatoric uncertainty by classification correctness\n(reference corpus, seed 20260730; 6% sample)',fontsize=10)
ax.legend(loc='upper right',fontsize=9)
# marginal means
ax.axhline(ale[corr].mean(),color='#2e8b57',ls=':',lw=1);ax.axhline(ale[~corr].mean(),color='#d1495b',ls=':',lw=1)
fig.tight_layout();fig.savefig(F+'figure4_uncertainty.svg');fig.savefig(F+'figure4_uncertainty.png',dpi=110);plt.close(fig)
print('figure4 done')

# ---------- Figure 5: macro-F1 vs SNR ----------
f5=rd('fig5_f1_vs_snr.csv')
x=[float(r['snr_center']) for r in f5];m=[float(r['f1_mean']) for r in f5];sd=[float(r['f1_std']) for r in f5]
# genuine ablation curves (reference seed)
abl={}
for r in csv.reader(open('runs/strat_abl/f1_vs_snr.csv')):
    abl.setdefault(r[0],[]).append((float(r[2]),float(r[3])))
import sys as _s;_s.path.insert(0,'src');import emulation_model as EM
fig,ax=plt.subplots(figsize=(7.2,5.0))
ax.errorbar(x,m,yerr=sd,fmt='-o',color=C['proposed'],lw=2,capsize=3,label='UST-Fuse (proposed) — measured, 30 seeds',zorder=5)
if 'no_uncertainty' in abl:
    xa=[p[0] for p in abl['no_uncertainty']];ya=[p[1] for p in abl['no_uncertainty']]
    ax.plot(xa,ya,'-s',color=C['b7'],lw=1.6,label='B7 = proposed w/o uncertainty — measured (toggle)')
# emulated CNN / LSTM
for name,key,col in [('B1 — CNN [9] (emulated)','B1 - CNN on Doppler [9]',C['b1']),
                     ('B2 — LSTM [15] (emulated)','B2 - LSTM sequence [15]',C['b2'])]:
    mult=EM.BASELINES_EMULATED[key]['f1']
    ax.plot(x,[v*mult for v in m],'--',color=col,lw=1.4,label=name,alpha=0.85)
ax.axvspan(5,20,color='#f0f4fa',alpha=0.6,zorder=0,label='operational SNR band')
ax.set_xlabel('Signal-to-noise ratio (dB)');ax.set_ylabel('Macro-averaged F1')
ax.set_title('Figure 5. Macro-F1 vs SNR (solid = measured; dashed = emulated baseline)',fontsize=10)
ax.legend(fontsize=8,loc='lower right');ax.set_ylim(0,0.85)
fig.tight_layout();fig.savefig(F+'figure5_f1_vs_snr.svg');fig.savefig(F+'figure5_f1_vs_snr.png',dpi=110);plt.close(fig)
print('figure5 done')

# ---------- Figure 6: fragmentation vs completeness ----------
f6=rd('fig6_frag_vs_completeness.csv')
xc=[float(r['completeness']) for r in f6];fm=[float(r['frag_per_truth_mean']) for r in f6];fs=[float(r['frag_per_truth_std']) for r in f6]
fig,ax=plt.subplots(figsize=(7.2,5.0))
ax.errorbar(xc,fm,yerr=fs,fmt='-o',color=C['proposed'],lw=2,capsize=3,label='UST-Fuse (proposed) — measured, 30 seeds',zorder=5)
for name,key,col in [('B4 — JPDA [12] (emulated)','B4 - JPDA','x'),
                     ('B5 — SORT [36] (emulated)','B5 - SORT [36]',C['b5']),
                     ('B6 — DeepSORT [37] (emulated)','B6 - DeepSORT [37]',C['b6'])]:
    if key=='B4 - JPDA': mult=1.8; col=C['b4']
    else: mult=EM.BASELINES_EMULATED[key]['frag']
    ax.plot(xc,[v*mult for v in fm],'--',color=col,lw=1.4,label=name,alpha=0.85)
ax.set_xlabel('Observation completeness ρ');ax.set_ylabel('Track fragmentation (per trajectory)')
ax.set_title('Figure 6. Fragmentation vs observation completeness\n(solid = measured; dashed = emulated baseline)',fontsize=10)
ax.legend(fontsize=8,loc='upper right')
fig.tight_layout();fig.savefig(F+'figure6_frag_vs_completeness.svg');fig.savefig(F+'figure6_frag_vs_completeness.png',dpi=110);plt.close(fig)
print('figure6 done')

# ---------- Figure 7: attention weights vs SNR (stacked area) ----------
f7=rd('fig7_attention_vs_snr.csv')
xs=[float(r['snr_center']) for r in f7]
kin=[float(r['kin_mean']) for r in f7];spec=[float(r['spec_mean']) for r in f7]
traj=[float(r['traj_mean']) for r in f7];qual=[float(r['qual_mean']) for r in f7]
# normalize to sum=1 for stacked composition
tot=[k+s+t+q for k,s,t,q in zip(kin,spec,traj,qual)]
kin=[k/t for k,t in zip(kin,tot)];spec=[s/t for s,t in zip(spec,tot)]
traj=[t2/t for t2,t in zip(traj,tot)];qual=[q/t for q,t in zip(qual,tot)]
fig,ax=plt.subplots(figsize=(7.2,5.0))
ax.stackplot(xs,kin,spec,traj,qual,labels=['kinematic','spectral','trajectory','quality'],
             colors=[C['kin'],C['spec'],C['traj'],C['qual']],alpha=0.85)
ax.set_xlim(min(xs),max(xs));ax.set_ylim(0,1)
ax.set_xlabel('Signal-to-noise ratio (dB)');ax.set_ylabel('Normalized cross-feature attention weight')
ax.set_title('Figure 7. Cross-feature attention composition vs SNR (measured, 30 seeds)',fontsize=10)
ax.legend(loc='upper center',ncol=4,fontsize=8,framealpha=0.9)
fig.tight_layout();fig.savefig(F+'figure7_attention_vs_snr.svg');fig.savefig(F+'figure7_attention_vs_snr.png',dpi=110);plt.close(fig)
print('figure7 done')

# ---------- Figure 8: sensitivity to zeta and gamma ----------
s8=rd('fig8_sensitivity.csv')
z=[r for r in s8 if r['param']=='zeta'];g=[r for r in s8 if r['param']=='gamma']
fig,(a1,a2)=plt.subplots(1,2,figsize=(9.6,4.4))
zx=[float(r['value']) for r in z];zf1=[float(r['macro_f1']) for r in z];zfr=[float(r['id_switches']) for r in z];zmota=[float(r['mota']) for r in z]
a1.set_xscale('log');a1b=a1.twinx()
l1,=a1.plot(zx,zf1,'-o',color=C['proposed'],label='Macro-F1')
l2,=a1b.plot(zx,zmota,'-s',color=C['b1'],label='MOTA')
l3,=a1b.plot(zx,[v/max(zfr) for v in zfr],'-^',color=C['b2'],label='ID switches (norm.)')
a1.axvline(9,ls='--',color='#888',lw=1);a1.set_xlabel('Covariance inflation ζ (log scale)')
a1.set_ylabel('Macro-F1');a1b.set_ylabel('MOTA / normalized ID switches')
a1.set_title('Sensitivity to ζ');a1.legend(handles=[l1,l2,l3],fontsize=8,loc='center left')
gx=[float(r['value']) for r in g];gf1=[float(r['macro_f1']) for r in g];gidsw=[float(r['id_switches']) for r in g]
a2.plot(gx,gf1,'-o',color=C['proposed'],label='Macro-F1')
a2b=a2.twinx();a2b.plot(gx,gidsw,'-^',color=C['b2'],label='ID switches')
a2.axvline(3,ls='--',color='#888',lw=1);a2.set_xlabel('Uncertainty tempering γ')
a2.set_ylabel('Macro-F1');a2b.set_ylabel('ID switches')
a2.set_title('Sensitivity to γ (note: γ inert — semantic factor near-inert)')
a2.legend(fontsize=8,loc='center right')
fig.suptitle('Figure 8. Sensitivity to ζ and γ (measured, reference corpus)',fontsize=10.5)
fig.tight_layout(rect=[0,0,1,0.95]);fig.savefig(F+'figure8_sensitivity.svg');fig.savefig(F+'figure8_sensitivity.png',dpi=110);plt.close(fig)
print('figure8 done')
print('ALL FIGURES DONE')
