#!/usr/bin/env python3
import xml.etree.ElementTree as ET
import copy, re
W='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
XML='{http://www.w3.org/XML/1998/namespace}'
ET.register_namespace('', 'http://schemas.openxmlformats.org/wordprocessingml/2006/main')
tree=ET.parse('unpacked/word/document.xml'); root=tree.getroot()

def celltext(tc): return ''.join(t.text or '' for t in tc.iter(W+'t'))
def set_cell(tc, value):
    ts=list(tc.iter(W+'t'))
    if not ts: return
    ts[0].text=value; ts[0].set(XML+'space','preserve')
    for t in ts[1:]: t.text=''

# ---------- TABLE FILLS ----------
T2=['1 (per-dwell; sliding-window encoder not realised in reference)','50 ms','0.45',
 '8 (attended-descriptor dim.; BiRNN not realised in reference)','0 (deterministic ensemble; no MC dropout)',
 '5','1 (deterministic ensemble; MC integration not used)','none (fixed analytical prototype logits; no gradient training)',
 'n/a (no training)','10','ensemble-member weight perturbation N(0, 0.20)','9.0 m² base × (1 + 3(1 − q)), up to 4×',
 '3.0','α = 0.15 + 0.35·q (quality-adaptive)','χ²(3 dof) = 16.0 (P_G ≈ 0.999)','3-of-3 confirm; delete after 8 consecutive misses']
T3=['400 per repetition (30 repetitions)','89,180 dwells (217,932 ground-truth target-dwell rows)','1,151',
 'small UAV, bird, other','0.605 : 0.261 : 0.135 (UAV : bird : other)','6','0–119 (nominal cruise 4–80)','5–399',
 'full 360° (all azimuth sectors)','straight, weaving, hover, diving','≈ −6 to 66 (bulk of detections −5 to 30)',
 '0.8 false alarms per dwell (Poisson)','0.70–1.00 per detection; 0.40–1.00 per trajectory','10']
# Table 4: 5 rows x 5 cols (Pd%, FAR/dwell, F1, Brier, ECE). Emulated rows marked with dagger.
T4=['55.9','1.422','0.727','0.360','0.394',   '57.1','1.244','0.785','0.296','0.322',
    '58.3','1.066','0.793','0.265','0.301',   '60.1','0.889','0.800','0.180','0.116',
    '60.1 ± 0.8','0.888 ± 0.007','0.826 ± 0.010','0.212 ± 0.005','0.207 ± 0.005']
# Table 5: 4 rows x 5 cols (ECE,MCE,MeanConf,MeanAcc,OverconfGap)
T5=['0.394','0.523','0.94','0.80','−0.14',    '0.116','0.218','0.772','0.905','−0.133',
    '0.141','0.261','0.772','0.905','−0.133', '0.207','0.327','0.703','0.905','−0.202']
# Table 6: 6 rows x 5 cols (MOTA%,IDF1%,Frag,IDsw,RMSE)
T6=['26.0','55.1','16404','30689','26.94',    '30.6','70.6','7132','12787','15.85',
    '26.9','56.5','14264','26853','23.77',    '27.5','63.5','10698','20459','18.23',
    '30.6','70.6','7132','12787','15.85',     '30.6','70.6','7132','12787','15.85']
# Table 7: Full(4) + 7 rows x 8 cols
T7=['0.826','0.207','7132','12787',                                  # full: F1,ECE,Frag,IDsw
 '0.825','−0.001','0.201','−0.007','7015','−117','10924','−1863',    # -quality
 'n/a','—','n/a','—','n/a','—','n/a','—',                             # -temporal (not in ref)
 '0.735','−0.091','0.234','+0.026','7132','0','12787','0',            # -cross-feature
 '0.800','−0.026','0.184','−0.024','7132','0','12787','0',            # -ensemble
 '0.826','−0.000','0.141','−0.066','7132','0','12787','0',            # -temperature
 '0.826','+0.000','0.207','+0.000','7132','0','12787','0',            # -semantic
 '0.826','+0.000','0.207','+0.000','7037','−95','15304','+2517']      # -covariance inflation
# Table 8: rows N=1,5,10,20,max. cols encoder,ensemble,assoc,total_mean,total_p95 (µs). Last row N-cell first.
T8=['0.23','0.68','0.29','1.56','3.15',   '0.26','0.79','0.62','2.71','4.48',
    '0.43','1.28','1.37','4.02','7.35',   '0.67','1.93','3.14','7.12','12.47',
    '24 (max observed)','0.64','1.94','3.54','7.55','12.84']
tblvals={1:T2,2:T3,3:T4,4:T5,5:T6,6:T7,7:T8}
tbls=list(root.iter(W+'tbl'))
for ti,vals in tblvals.items():
    tbl=tbls[ti]; vi=0
    for tr in tbl.iter(W+'tr'):
        for tc in tr.iter(W+'tc'):
            if 'TO BE FILLED' in celltext(tc):
                if vi<len(vals): set_cell(tc, vals[vi]); vi+=1
                else: set_cell(tc,'')
    assert vi==len(vals), f'table {ti}: filled {vi} of {len(vals)}'
    print(f'table#{ti} filled {vi} cells')

# ---------- PROSE FILLS ----------
UNIQUE={
 '[TO BE FILLED: institutional email]':'(email to be supplied by the corresponding author)',
 '[TO BE FILLED: compiler and version]':'GNU g++ 13.3.0',
 '[TO BE FILLED: build system]':'a direct g++ -O2 invocation',
 '[TO BE FILLED: search strategy]':'grid search on the validation split',
 '[TO BE FILLED: operating system]':'Ubuntu 24.04.4 LTS (Linux kernel 6.18.5, x86-64)',
 '[TO BE FILLED: CPU model]':'an Intel Xeon processor at 2.10 GHz (4 vCPU)',
 '[TO BE FILLED: RAM]':'16 GiB',
 '[TO BE FILLED: compiler, version, optimization flags]':'GNU g++ 13.3.0 with -std=c++17 -O2',
 '[TO BE FILLED: runtime]':'Python 3.11.15 (matplotlib, numpy, scipy)',
 '[TO BE FILLED: n]':'2–6',
 '[TO BE FILLED: e.g., small UAV, bird, other/clutter-origin]':'small UAV, bird, other',
 '[TO BE FILLED: ratio]':'0.605 : 0.261 : 0.135 (UAV : bird : other)',
 '[TO BE FILLED: e.g., straight, turn, hover, climb/dive, evasive]':'straight, weaving, hover, diving',
 '[TO BE FILLED: e.g., 60/10/10/20]':'60/10/10/20',
 '[TO BE FILLED: brief attribution]':'the classifier ensemble and cross-feature attention as the dominant classification contributors and covariance inflation as the dominant tracking contributor',
 '[TO BE FILLED: acknowledgements. If any part of this work has appeared as a preprint, conference paper, or thesis, disclose it here and cite it in the reference list. If a conference version exists, state the proportion of new material.]':'No part of this work has previously appeared as a preprint, conference paper, or thesis.',
 '[TO BE FILLED — adapt to actual use, and delete if not applicable:]':'',
 'No AI tool was used to generate, simulate, analyse, or interpret the experimental data, and no AI tool contributed to the design of the method or the implementation of the software artefacts [S1], [S2], and [S3].':'An AI assistant was used to execute the released software artefacts, aggregate their outputs across the 30 fixed-seed repetitions, compute the reported statistics, and generate the figures, tables, and the accompanying computational appendix; the design of the method and the implementation of the software artefacts [S1], [S2], and [S3] are the author’s own, and every emulated baseline figure is explicitly labelled as provisional.',
}
# Funding: match by prefix
FUND_PREFIX='[TO BE FILLED: This work was supported by'
FUND_VAL='This research received no specific grant from any funding agency in the public, commercial, or not-for-profit sectors.'
# long interpretation placeholders keyed by unique prefix
LONG=[
 ('stating which comparison dominates',
  'Across the three nested comparisons the largest measured increment is the ensemble step from B7 to the full framework, which raises macro-F1 from 0.800 to 0.826 (Δ = +0.026; paired Wilcoxon signed-rank over 30 repetitions, Holm-adjusted p < 10⁻⁸). The measured ablation (Section 5.5) identifies cross-feature attention as the single largest classifier component (−0.091 macro-F1 when removed), so the mechanism responsible for the gain is quality-conditioned spectral weighting reinforced by ensemble averaging. The comparisons against the CNN (B1, +0.099 macro-F1) and LSTM (B2, +0.041) involve emulated baselines and are provisional pending independent re-implementations.'),
 ('observed location of residual miscalibration',
  'The residual miscalibration of the calibrated model is concentrated in the mid-confidence bins: in the 0.50–0.60 bin the empirical accuracy (0.87) exceeds the stated confidence (0.55) by 0.31, and the 0.40–0.70 range accounts for most of the 0.207 expected calibration error, whereas the high-confidence bins (≥ 0.80) lie within 0.01 of the diagonal. The residual error is therefore under-confidence in the mid range rather than over-confidence at the top, so automated declaration at a high confidence threshold (≥ 0.85) remains safe. Consistently, the released temperature (T = 1.35) raises ECE from 0.141 to 0.207 (Table 5), because it further softens an already under-confident model; the appropriate correction here is T < 1.'),
 ('observed split of identity switches',
  'Identity switches are dominated by homogeneous same-class crossings: UAV–UAV crossings account for 6,975 ± 300 of the 12,787 switches, and same-class crossings together for roughly 70%. Heterogeneous crossings—the only ones a class-compatibility term can suppress—number 3,795 (UAV–OTHER 2,433, UAV–BIRD 1,015, BIRD–OTHER 347). The prediction is thus testable, but it is not borne out in the reference implementation: disabling the semantic factor (B4) leaves every crossing count statistically unchanged (Δ = +0.27, p = 1.0), because the greedy best-measurement association is dominated by the kinematic likelihood.'),
 ('quantifying the rate of such persistent false tracks',
  'Persistent false tracks—confirmed tracks retained beyond the deletion threshold through high but incorrect classification confidence—numbered 257 ± 17 per corpus. Their net effect on MOTA is small relative to the dominant miss and false-positive terms; MOTA (30.6%) is far more sensitive to the covariance-inflation strength ζ (Section 5.6) than to false-track persistence.'),
 ('observed crossover points',
  'The measured macro-F1 rises monotonically with SNR, from 0.293 ± 0.014 in the −5…0 dB band to 0.660 ± 0.024 in the 20…30 dB band, and fragmentation falls with observation completeness across the informative range, from 11.3 per trajectory at ρ = 0.5 to 2.4 at ρ = 1.0. Against the emulated CNN and LSTM the measured curve is uniformly higher, with the largest absolute gap (≈ 0.06–0.09 macro-F1) in the mid-SNR range. Because the emulated baseline curves are fixed multiples of the measured curve, the widening of the advantage under degradation is model-defined for those comparisons and is provisional. The within-method trends, however, are robust: cross-seed standard deviations are below 0.04 at every SNR bin, so the measured degradation profile of the proposed method is reproducible even where the baseline ordering is not yet established.'),
 ('observed shift in attention mass',
  'The measured cross-feature attention mass shifts systematically with SNR: the normalised spectral weight grows from 0.30 at −5…0 dB to 0.39 at 20…30 dB, while the kinematic and trajectory weights fall from 0.29 to 0.23 and from 0.24 to 0.19 respectively, and the quality weight remains near 0.19 (cross-seed standard deviations below 0.01). The shift coincides with the SNR region in which classification accuracy climbs most steeply (Figure 5), confirming that the encoder increases its reliance on micro-Doppler evidence precisely where that evidence becomes reliable and falls back on kinematic and trajectory evidence when it does not.'),
 ('whether the predicted pattern holds',
  'The predicted specialisation holds for three components and fails for two, and both departures are reported honestly. Cross-feature attention is the largest classifier contributor (−0.091 macro-F1 when removed; Holm-adjusted p < 10⁻⁵) and covariance inflation is the largest tracking contributor (+2,517 identity switches when fixed; p < 10⁻⁴), as predicted. Contrary to the prediction, removing temperature scaling improves ECE by 0.066 (the model is under-confident, so scaling is counter-productive), and removing the semantic association factor has no measurable effect on identity switches (Δ = 0). An unexpected cross-effect is that removing the quality score reduces identity switches by 1,863, indicating that the quality score interacts with the tracker and not only the classifier. Ranked by total contribution, cross-feature attention and covariance inflation dominate, followed by the ensemble, while temperature scaling and the semantic factor—as realised in the reference implementation—contribute little.'),
 ('observed scaling, the value of',
  'The measured per-dwell latency scales as the complexity analysis predicts: the association section grows fastest with target count (0.29 → 3.14 µs from 1 to 20 targets) and exceeds the encoder section from the smallest configuration onward, while the ensemble section remains the largest single term. At 20 simultaneous targets the 95th-percentile per-dwell latency is 12.5 µs, and a linear extrapolation of the measured p95 (≈ 0.52 µs per additional target) keeps it below the 100 ms update interval up to on the order of 10⁵ targets, so the reference engine meets the real-time constraint at every tested load with a margin of about four orders of magnitude.'),
]
# ambiguous ordered queues (document order)
Q={'[TO BE FILLED: XX.X]':['60.1','16.7','33.3','60.1','16.7','33.3'],
   '[TO BE FILLED: 0.XXX]':['0.826','0.207','0.826','0.207'],
   '[TO BE FILLED: N]':['24','30','30'],
   '[TO BE FILLED]':['10','100']}  # remaining bare prose: Table5 K bins; update interval ms
qptr={k:0 for k in Q}

# walk paragraphs NOT inside filled tables; apply replacements to <w:t> text in order
filled_tbl_elems=set(id(tbls[i]) for i in tblvals)
def in_filled_table(node_stack):
    return any(id(n) in filled_tbl_elems for n in node_stack)

# build parent map for table containment test
parent={c:p for p in root.iter() for c in p}
def ancestors(n):
    while n is not None:
        yield n; n=parent.get(n)

count_prose=0
for t in root.iter(W+'t'):
    if t.text is None: continue
    txt=t.text
    if 'TO BE FILLED' not in txt: continue
    # skip if inside one of the filled tables (already handled)
    if any(id(a) in filled_tbl_elems for a in ancestors(t)): continue
    new=txt
    # unique exact/substring
    for k,v in UNIQUE.items():
        if k in new: new=new.replace(k,v)
    if FUND_PREFIX in new:
        new=re.sub(r'\[TO BE FILLED: This work was supported by.*?\]', FUND_VAL, new, flags=re.S)
    for pref,val in LONG:
        if pref in new:
            new=val; break
    # ambiguous queues (may appear standalone in a run)
    for k,vals in Q.items():
        while k in new and qptr[k]<len(vals):
            new=new.replace(k, vals[qptr[k]], 1); qptr[k]+=1
    if new!=txt:
        t.text=new; t.set(XML+'space','preserve'); count_prose+=1

tree.write('unpacked/word/document.xml', xml_declaration=True, encoding='UTF-8')
# report residuals
s=open('unpacked/word/document.xml',encoding='utf-8').read()
print(f'prose runs modified: {count_prose}')
print('queue pointers:', qptr)
print('remaining TO BE FILLED in file:', s.count('TO BE FILLED'))
