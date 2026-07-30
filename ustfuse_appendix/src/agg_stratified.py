import csv, statistics
from collections import defaultdict
S='runs/strat/'; T='tables/'

def agg(infile, keycols, valcols, outfile, header):
    rows=list(csv.reader(open(S+infile)))
    groups=defaultdict(lambda: defaultdict(list))
    for r in rows:
        key=tuple(r[i] for i in keycols)
        for vi in valcols: groups[key][vi].append(float(r[vi]))
    with open(T+outfile,'w',newline='') as f:
        w=csv.writer(f); w.writerow(header)
        for key in groups:
            out=list(key)
            for vi in valcols:
                vals=groups[key][vi]
                out.append(f'{statistics.mean(vals):.5f}')
                out.append(f'{statistics.stdev(vals):.5f}' if len(vals)>1 else '0')
            out.append(len(groups[key][valcols[0]]))
            w.writerow(out)
    return groups

# F1 vs SNR: cols seed,bin,center,f1,n
agg('f1_vs_snr.csv',[1,2],[3],'fig5_f1_vs_snr.csv',['snr_bin','snr_center','f1_mean','f1_std','n_seeds'])
# attention vs snr: seed,bin,center,w0,w1,w2,w3,n
agg('attention_vs_snr.csv',[1,2],[3,4,5,6],'fig7_attention_vs_snr.csv',
    ['snr_bin','snr_center','kin_mean','kin_std','spec_mean','spec_std','traj_mean','traj_std','qual_mean','qual_std','n_seeds'])
# frag vs completeness: seed,label,frag_per_truth,frag_sum,n_truth
agg('frag_vs_completeness.csv',[1],[2],'fig6_frag_vs_completeness.csv',['completeness','frag_per_truth_mean','frag_per_truth_std','n_seeds'])
# reliability: seed,method,bin,conf,acc,n
agg('reliability.csv',[1,2],[3,4],'fig3_reliability.csv',['method','conf_bin','conf_mean','conf_std','acc_mean','acc_std','n_seeds'])
# uncertainty by correct: seed,cat,epi,ale,n
agg('uncertainty_by_correct.csv',[1],[2,3],'fig4_uncertainty.csv',['category','epistemic_mean','epistemic_std','aleatoric_mean','aleatoric_std','n_seeds'])
# idsw by crossing: seed,pair,count
agg('idsw_by_crossing.csv',[1],[2],'idsw_by_crossing.csv',['crossing','count_mean','count_std','n_seeds'])
print("aggregated. Preview:")
for fn in ['fig5_f1_vs_snr.csv','fig7_attention_vs_snr.csv','fig6_frag_vs_completeness.csv','fig4_uncertainty.csv','idsw_by_crossing.csv']:
    print('---',fn,'---')
    print(open(T+fn).read().strip())
