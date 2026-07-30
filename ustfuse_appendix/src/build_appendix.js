const fs=require('fs');
const h=require('./docx_helpers.js');
const {D,Paragraph,TextRun,HeadingLevel,AlignmentType,PageBreak,H,P,bullet,noteBox,table,tableFromCSV,figure,caption,runs,FONT}=h;
const R=JSON.parse(fs.readFileSync('tables/results.json','utf8'));
const FIG='figures/';
const el=[];

// ---------- Title block ----------
el.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:60},children:[new TextRun({text:'COMPUTATIONAL APPENDIX',font:FONT,size:26,bold:true,color:'1F4E8C'})]}));
el.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:40},children:[new TextRun({text:'Uncertainty-Aware Spatiotemporal Radar Data Fusion for Intelligent Detection and Multi-Target Tracking of Small Unmanned Aerial Vehicles',font:FONT,size:22,bold:true})]}));
el.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:40},children:[new TextRun({text:'Reproducible computational experiment with RadarTwin-UAV (S1), UST-Fuse Engine (S2) and FuseMetrics Lab (S3)',font:FONT,size:18,italics:true})]}));
el.push(new Paragraph({alignment:AlignmentType.CENTER,spacing:{after:200},children:[new TextRun({text:'Prepared for Zenodo deposition · Experiment date 2026-07-30 · 30 repetitions (seeds 20260730–20260759)',font:FONT,size:16,color:'555555'})]}));

// ---------- Executive integrity note (front and centre) ----------
el.push(noteBox([
  new Paragraph({spacing:{after:80},children:[new TextRun({text:'Integrity and validity statement (read first)',font:FONT,size:20,bold:true,color:'8A6D00'})]}),
  P([runs('This appendix separates ',{}),runs('measured',{bold:true}),runs(' results from ',{}),runs('emulated',{bold:true}),runs(' results, because the released software realises them differently.',{})]),
  bullet([runs('Measured (genuine). ',{bold:true}),runs('All UST-Fuse (proposed) metrics, the corpus and configuration tables, every ablation row (obtained by real component toggles in S2), the per-SNR / per-completeness / attention analyses, the calibration diagrams, the identity-switch breakdown, the sensitivity sweeps, and the per-tick wall-clock latency. These are deterministic outputs of the released code over 30 fixed-seed repetitions.',{})]),
  bullet([runs('Emulated (provisional). ',{bold:true}),runs('The architecturally distinct baselines B1 (CNN), B2 (LSTM), B3 (Kalman+NN), B5 (SORT) and B6 (DeepSORT) are produced by the documented degradation model inside FuseMetrics Lab v1, not by independent re-implementations. Per the task specification (§7), such figures are valid for pipeline verification but must be replaced with genuine baseline runs before scientific publication. Baselines B4 (kinematic-only JPDA) and B7 (proposed without uncertainty) are NOT emulated — they are measured via genuine S2 toggles.',{})]),
  P([runs('Every emulated cell is labelled “emulated”. The abstract’s false-alarm and fragmentation reductions are computed against the emulated strongest baseline and are therefore provisional. Section 17 gives the full disclosure and the discrepancies between the released reference implementation and the idealised architecture of the manuscript.',{it:true})]),
],'FFF3CD'));

el.push(new Paragraph({children:[new PageBreak()]}));

// ---------- 1. Purpose ----------
el.push(H('1. Purpose and scope',HeadingLevel.HEADING_1));
el.push(P('This document is the complete computational record supporting the manuscript “Uncertainty-Aware Spatiotemporal Radar Data Fusion for Intelligent Detection and Multi-Target Tracking of Small Unmanned Aerial Vehicles”. It was produced by executing the three released C++17 software artefacts on a single, reproducible synthetic corpus and by aggregating the outputs over thirty independent repetitions. Its objectives are: (i) to generate a reproducible synthetic radar corpus; (ii) to perform uncertainty-aware spatiotemporal fusion; (iii) to quantify detection, classification, calibration and multi-target tracking accuracy with confidence intervals and non-parametric significance tests; and (iv) to supply every numerical value required to complete the manuscript’s abstract, Tables 2–8, results interpretations and conclusion.'));
el.push(P('The pipeline is deterministic given a seed. Each repetition runs RadarTwin-UAV (S1) to synthesise a labelled corpus, UST-Fuse Engine (S2) to produce classifications and tracks, and FuseMetrics Lab (S3) to compute metrics. All analysis code, intermediate CSVs, figures and this document are archived together.'));

// ---------- 2. Software artefacts ----------
el.push(H('2. Software artefacts and build',HeadingLevel.HEADING_1));
el.push(P([runs('S1 — RadarTwin-UAV. ',{bold:true}),runs('Synthetic radar scenario and digital-twin generator. Models UAV / bird / other kinematics, an ENU monostatic radar (1/R⁴ SNR, Swerling-like detection, Poisson clutter, missed detections, measurement noise) and emits range, azimuth, elevation, radial velocity, SNR, clutter, completeness and a micro-Doppler descriptor, with exact ground truth. DOI 10.5281/zenodo.21699894.',{})]));
el.push(P([runs('S2 — UST-Fuse Engine. ',{bold:true}),runs('Reference fusion engine: feature normalisation, cross-feature attention gated by measurement quality, an ensemble classifier with temperature calibration and epistemic/aleatoric decomposition, and a constant-velocity Kalman tracker with quality-driven covariance inflation and a semantic association factor tempered by epistemic uncertainty. DOI 10.5281/zenodo.21699946.',{})]));
el.push(P([runs('S3 — FuseMetrics Lab. ',{bold:true}),runs('Analytics and reproducibility platform: leak-free scenario-level splits, detection/classification/calibration/tracking metrics, bootstrap confidence intervals, baseline comparison, component ablation and Wilcoxon+Holm testing, exporting CSV, LaTeX and SVG. DOI 10.5281/zenodo.21699827.',{})]));
el.push(P('Build commands (identical optimisation for the three artefacts):'));
el.push(new Paragraph({spacing:{after:120},shading:{type:D.ShadingType.CLEAR,fill:'F2F2F2'},children:[new TextRun({text:'g++ -std=c++17 -O2 -o radartwin  main_s1.cpp',font:'Consolas',size:18}),new TextRun({text:'\n',break:1}),new TextRun({text:'g++ -std=c++17 -O2 -o ustfuse    main_s2.cpp',font:'Consolas',size:18,break:1}),new TextRun({text:'g++ -std=c++17 -O2 -o fusemetrics main_s3.cpp',font:'Consolas',size:18,break:1})]}));
el.push(P([runs('Two auxiliary builds were derived from the S2 source for genuine measurements only: ',{}),runs('ustfuse_ablate',{bold:true}),runs(' (adds runtime component-toggle and ζ/γ parameters for the ablation and sensitivity studies) and ',{}),runs('ustfuse_timed',{bold:true}),runs(' (adds per-section std::chrono timers for latency). Neither changes the fusion result of the unmodified engine; the toggles are strictly additive and default to the released behaviour.',{})]));

// ---------- 3. Environment ----------
el.push(H('3. Computational environment',HeadingLevel.HEADING_1));
el.push(P('All experiments were executed on a single machine with no competing user processes during latency measurement.'));
el.push(tableFromCSV('tables/table_environment.csv',{widths:[3,7]}));
el.push(caption('Table E1. Software and hardware environment.'));

// ---------- 4. Corpus ----------
el.push(H('4. Corpus generation (Table 3)',HeadingLevel.HEADING_1));
el.push(P([runs('Command per repetition: ',{}),runs('./radartwin <seed> 400',{bold:true}),runs('. Four scenario families (individual, simultaneous, sequential, combined) are generated in equal proportion. Table 3 reports the reference corpus (seed 20260730); counts vary by <2% across the 30 seeds (mean measurement rows 203,125 ± 2,910).',{})]));
el.push(tableFromCSV('tables/table3_corpus.csv',{widths:[4,6]}));
el.push(caption('Table 3. Composition of the RadarTwin-UAV corpus and controlled-factor ranges.'));

// ---------- 5. Reproducibility protocol ----------
el.push(H('5. Independent samples and reproducibility protocol',HeadingLevel.HEADING_1));
el.push(P('Scenarios (not individual measurements) were partitioned at the scenario level into train / calibration / validation / test folds in a 60 / 10 / 10 / 20 ratio by a deterministic hash of (seed, scenario_id). No scenario appears in two folds; normalisation statistics are drawn from the training fold only. The split for all 30 seeds is recorded in manifest/split_manifest.json and verified leak-free (all folds pairwise disjoint).'));
el.push(P('The full S1→S2→S3 cycle was repeated 30 times with seeds 20260730…20260759. For every run the seed, generator configuration, engine configuration, scenario count, file row counts and MD5 checksums of all inputs and outputs were logged (runs/checksums.csv, 150 file records; all 30 measurement checksums distinct). Metrics were pooled only after integrity verification.'));
el.push(tableFromCSV('tables/split_summary_head.csv',{widths:[2,2,2,2,2,2,2],size:15}));
el.push(caption('Table R1. Scenario-level split sizes for the first six repetitions (leak-free; full table in the manifest).'));

// ---------- 6. Configuration (Table 2) ----------
el.push(H('6. Reference configuration (Table 2)',HeadingLevel.HEADING_1));
el.push(P('Table 2 lists the hyperparameters actually realised in the released S2 source. Constants were read directly from the code; italic notes mark parameters that the reference implementation realises differently from the idealised neural architecture described in Section 3 of the manuscript (for example, the reference classifier uses fixed analytical prototype logits rather than a trained network, and processes each dwell independently rather than over a sliding window).'));
el.push(tableFromCSV('tables/table2_hyperparameters.csv',{widths:[1.4,4.2,6.4],size:15}));
el.push(caption('Table 2. Hyperparameter configuration of the reference UST-Fuse implementation.'));

// ---------- 7. Headline results ----------
el.push(H('7. Headline metrics with confidence intervals',HeadingLevel.HEADING_1));
el.push(P('All values below are means over 30 repetitions with standard deviation and a 10,000-resample bootstrap 95% confidence interval on the across-seed mean. Latency here is the S3 analytical model; genuine wall-clock latency is reported in Section 14.'));
el.push(tableFromCSV('tables/agg_metrics_doc.csv',{widths:[4.2,2,1.4,2.4],size:15}));
el.push(caption('Table 7a. Aggregate UST-Fuse performance (measured, 30 repetitions).'));
el.push(P([runs('Headline: detection probability ',{}),runs(R.pd_pct+'%',{bold:true}),runs(', macro-F1 ',{}),runs(R.macro_f1.toFixed(3),{bold:true}),runs(' ± '+R.macro_f1_sd.toFixed(3)+', ECE ',{}),runs(R.ece.toFixed(3),{bold:true}),runs(', MOTA '+R.mota_pct+'%, IDF1 '+R.idf1_pct+'%, RMSE '+R.rmse+' m.',{})]));

el.push(new Paragraph({children:[new PageBreak()]}));

// ---------- 8. Detection & classification (Table 4) ----------
el.push(H('8. Detection and classification (Table 4)',HeadingLevel.HEADING_1));
el.push(tableFromCSV('tables/table4_doc.csv',{widths:[3.4,1.3,1.6,1.3,1.2,1.2],size:15}));
el.push(caption('Table 4. Detection and classification on the test partition. UST-Fuse and B7 measured; B1/B2/B6 emulated (provisional).'));
el.push(P([runs('Interpretation. ',{bold:true}),runs('The nested comparison B2→B7→UST-Fuse isolates the sources of the classification gain. The measured step from B7 (proposed without uncertainty) to the full framework raises macro-F1 by '+R.dF1_uncertainty.toFixed(3)+' (0.800→'+R.macro_f1.toFixed(3)+'; paired Wilcoxon p<10⁻⁸, Holm-corrected), attributable to the five-member ensemble. Against the emulated CNN and LSTM the macro-F1 advantage is +0.099 and +0.041 respectively; these two rows are model-defined and provisional. The false-alarm rate of the reference engine is '+R.far.toFixed(3)+' per dwell; note that removing uncertainty (B7) leaves detection and false alarms essentially unchanged, since the detection front-end is shared.',{})]));

// ---------- 9. Calibration (Table 5, Figures 3-4) ----------
el.push(H('9. Confidence calibration (Table 5, Figures 3–4)',HeadingLevel.HEADING_1));
el.push(tableFromCSV('tables/table5_doc.csv',{widths:[3.6,1.1,1.1,1.5,1.4,1.6],size:15}));
el.push(caption('Table 5. Calibration (B=10 bins). Proposed rows measured; B1 emulated.'));
el.push(figure(FIG+'figure3_reliability.png',560));
el.push(caption('Figure 3. Reliability diagrams (mean over 30 repetitions; error bars = SD across seeds).'));
el.push(P([runs('Interpretation. ',{bold:true}),runs('The reference model is systematically ',{}),runs('under-confident',{bold:true}),runs(': its mean confidence (0.703) is far below its mean accuracy (0.905), an overconfidence gap of −0.202. The residual miscalibration is concentrated in the mid-confidence bins (0.4–0.7), where empirical accuracy exceeds stated confidence by up to 0.31 (bin 0.5–0.6: confidence 0.55, accuracy 0.87); the high-confidence bins (≥0.8) are well calibrated. Because the miscalibration is under-confidence in the mid range rather than over-confidence at the top, it is operationally benign — automated declaration at a high threshold remains safe. A direct consequence, visible in Table 5 and confirmed by ablation, is that the released temperature (T=1.35) ',{}),runs('increases',{it:true}),runs(' ECE (0.141→0.207): temperature scaling softens an already under-confident model. The correct calibration action here is T<1.0.',{})]));
el.push(figure(FIG+'figure4_uncertainty.png',430));
el.push(caption('Figure 4. Epistemic vs aleatoric uncertainty by classification correctness (reference corpus).'));
el.push(P([runs('The uncertainty decomposition is informative: misclassified windows carry higher aleatoric uncertainty (0.255 vs 0.176 nats) and higher epistemic uncertainty (0.0168 vs 0.0129 nats) than correct ones (both differences significant across seeds). Aleatoric uncertainty is the stronger discriminator of error, consistent with degraded observations — rather than unfamiliar objects — driving most mistakes in this corpus.',{})]));

el.push(new Paragraph({children:[new PageBreak()]}));

// ---------- 10. Tracking (Table 6) ----------
el.push(H('10. Tracking continuity and identity (Table 6)',HeadingLevel.HEADING_1));
el.push(tableFromCSV('tables/table6_doc.csv',{widths:[3.6,1.3,1.3,1.7,1.5,1.3],size:15}));
el.push(caption('Table 6. Multi-target tracking on the test partition. UST-Fuse / B4 / B7 measured; B3 / B5 / B6 emulated.'));
el.push(P([runs('Interpretation. ',{bold:true}),runs('UST-Fuse attains MOTA '+R.mota_pct+'%, IDF1 '+R.idf1_pct+'%, RMSE '+R.rmse+' m, with '+R.fragmentation+' fragmentations and '+R.id_switches+' identity switches over the corpus. A notable measured finding: B4 (kinematic-only JPDA, obtained by disabling the semantic factor) is statistically indistinguishable from the full engine on every tracking metric (Δ ID switches = +0.27, p=1.0). In the released reference implementation the semantic association factor is therefore ',{}),runs('near-inert',{bold:true}),runs(': the greedy best-measurement association is dominated by the kinematic likelihood, so the class-compatibility term rarely changes the chosen assignment. This is an honest null result that the emulated baselines (B3/B5/B6, which are worse by construction) would otherwise obscure. Section 15 revisits the mechanism through the ζ/γ sensitivity analysis.',{})]));

// ---------- 11. Robustness (Figures 5-7) ----------
el.push(H('11. Robustness under degradation (Figures 5–7)',HeadingLevel.HEADING_1));
el.push(figure(FIG+'figure5_f1_vs_snr.png',500));
el.push(caption('Figure 5. Macro-F1 vs SNR (solid = measured; dashed = emulated baseline).'));
el.push(figure(FIG+'figure6_frag_vs_completeness.png',500));
el.push(caption('Figure 6. Fragmentation vs observation completeness (solid = measured; dashed = emulated).'));
el.push(P([runs('Interpretation. ',{bold:true}),runs('Macro-F1 rises monotonically with SNR, from 0.293 ± 0.014 in the −5…0 dB band to 0.660 ± 0.024 in the 20…30 dB band. Fragmentation falls with observation completeness across the informative range (11.3 per trajectory at ρ=0.5 down to 2.4 at ρ=1.0); the very-low-completeness bin (ρ=0.4) is lower only because such trajectories are barely tracked at all. Against the emulated baselines the measured curve is uniformly superior, but that ordering is model-defined and provisional for the dashed lines.',{})]));
el.push(figure(FIG+'figure7_attention_vs_snr.png',500));
el.push(caption('Figure 7. Cross-feature attention composition vs SNR (measured, 30 seeds).'));
el.push(P([runs('The cross-feature attention mechanism behaves exactly as predicted and provides a mechanistic account of the SNR dependence. As SNR rises the spectral group’s normalised weight grows from 0.30 to 0.39 while the kinematic and trajectory groups contract (0.29→0.23 and 0.24→0.19); the quality group is roughly constant. At low SNR — where micro-Doppler extraction is unreliable — the model shifts mass onto the more graceful kinematic and trajectory evidence. Cross-seed standard deviations are below 0.01 at every bin.',{})]));

el.push(new Paragraph({children:[new PageBreak()]}));

// ---------- 12. Ablation (Table 7) ----------
el.push(H('12. Ablation study (Table 7)',HeadingLevel.HEADING_1));
el.push(P('Each row removes exactly one component from the full engine by a genuine runtime toggle in S2 and re-evaluates over the 30 repetitions. Temporal attention is not present in the reference implementation (it processes each dwell independently) and is marked accordingly.'));
el.push(tableFromCSV('tables/table7_doc.csv',{widths:[3.4,1,1,1,1,1.3,1.1,1.2,1.1],size:14}));
el.push(caption('Table 7. Component ablation (measured, means over 30 repetitions).'));
el.push(P([runs('Interpretation. ',{bold:true}),runs('The measured contributions are: cross-feature attention is the dominant classifier component (removing it costs 0.091 macro-F1 and raises ECE by 0.026); the ensemble contributes 0.026 macro-F1; covariance inflation is the dominant tracking component (removing it adds '+R.dIDSW_covinfl+' identity switches). Two predicted specialisations are ',{}),runs('not',{bold:true}),runs(' borne out by the reference implementation and are reported honestly: (i) removing temperature scaling ',{}),runs('improves',{it:true}),runs(' ECE by 0.066 (the model is under-confident, so scaling hurts); (ii) removing the semantic association factor has no measurable effect on identity switches (Δ=0). Removing the quality score paradoxically reduces identity switches by '+Math.abs(R.dIDSW_quality)+', an unintended interaction. These divergences characterise the released proxy, whose association is greedy and whose classifier is untrained; they are the principal items to address before the manuscript’s mechanism claims can be considered empirically supported.',{})]));

// ---------- 13. ID-switch crossings ----------
el.push(H('13. Identity-switch analysis by crossing type',HeadingLevel.HEADING_1));
el.push(tableFromCSV('tables/idsw_by_crossing_doc.csv',{widths:[4,3,3],size:16}));
el.push(caption('Table 13a. Identity switches by class-pair of the crossing (means over 30 repetitions).'));
el.push(P([runs('Most switches (about 70%) are homogeneous same-class crossings, overwhelmingly UAV–UAV (6,975 ± 300), which a class-compatibility term cannot help by construction. Heterogeneous crossings — the only ones a semantic factor could suppress — account for roughly 30% (UAV–OTHER 2,433, UAV–BIRD 1,015, BIRD–OTHER 347). The manuscript’s prediction that semantic association concentrates its benefit on heterogeneous crossings is testable here, but because the semantic factor is near-inert in the reference engine (Section 12), no reduction is observed. Persistent false tracks retained beyond the deletion threshold through high-but-wrong confidence numbered '+257+' ± 17 per corpus (the “spurious/new-track” category).',{})]));

// ---------- 14. Latency (Table 8) ----------
el.push(H('14. Latency and scalability (Table 8, measured)',HeadingLevel.HEADING_1));
el.push(P('Latency was measured as wall-clock time per dwell inside the S2 engine using std::chrono, decomposed into encoder, ensemble and association sections. The first 100 dwells were discarded as warm-up; samples were bucketed by the number of active tracks. Values are microseconds.'));
el.push(tableFromCSV('tables/table8_doc.csv',{widths:[2.2,1.5,1.5,1.7,1.7,1.7,1.4],size:15}));
el.push(caption('Table 8. Measured per-dwell latency (μs) vs simultaneous targets.'));
el.push(P([runs('Interpretation. ',{bold:true}),runs('The association section grows fastest with target count (0.29→3.14 μs from 1 to 20 targets, consistent with its O(K²) worst case) and overtakes the encoder immediately; the ensemble section is the largest single term. At 20 simultaneous targets the 95th-percentile per-dwell latency is 12.5 μs — about four orders of magnitude below the 100 ms budget of a 10 Hz revisit. Extrapolating the measured p95 (≈0.52 μs per additional target) the real-time bound (p95 < 100 ms) is not reached until on the order of 10⁵ targets. The reference engine is therefore real-time by a very large margin; because it is a lightweight analytical proxy rather than the trained neural architecture of Section 3, these figures should be read as a lower bound on the latency of a production system, not as its expected cost.',{})]));

// ---------- 15. Sensitivity (Figure 8) ----------
el.push(H('15. Sensitivity to ζ and γ (Figure 8)',HeadingLevel.HEADING_1));
el.push(figure(FIG+'figure8_sensitivity.png',560));
el.push(caption('Figure 8. Sensitivity to covariance inflation ζ and uncertainty tempering γ (measured).'));
el.push(P([runs('The covariance-inflation strength ζ is the single most consequential tracking hyperparameter: sweeping ζ over {1,3,9,27,81} moves MOTA from 0.07 to 0.81 and identity switches from 18,699 to 790, while classification metrics are untouched (ζ affects only the filter). The released default ζ=9 (MOTA 0.32) is conservative; larger inflation stabilises association markedly. By contrast the uncertainty-tempering coefficient γ has no measurable effect on any metric, because it only modulates the near-inert semantic factor. Both findings are genuine and directly actionable: they identify ζ as the knob to tune and the semantic-association pathway as the component to redesign.',{})]));

el.push(new Paragraph({children:[new PageBreak()]}));

// ---------- 16. Statistical testing ----------
el.push(H('16. Statistical significance',HeadingLevel.HEADING_1));
el.push(P('Differences between the full engine and each measured toggle configuration were assessed with the two-sided Wilcoxon signed-rank test over the 30 paired per-seed scores, with Holm correction across the family of comparisons at α=0.05. Emulated baselines (B1/B2/B3/B5/B6) are not independently sampled and are excluded from significance testing; the comparison against them is model-defined.'));
el.push(tableFromCSV('tables/significance_doc.csv',{widths:[3.6,1.6,1.4,1.4,1,1.4,1.4],size:14}));
el.push(caption('Table 16a. Paired Wilcoxon signed-rank tests (Holm-corrected), macro-F1 and ID switches.'));
el.push(P('The uncertainty ensemble (B7), cross-feature attention and covariance inflation produce statistically significant, correctly-signed effects. The semantic factor (B4) shows no significant effect, consistent with Sections 10, 12 and 15.'));

// ---------- 17. Validity disclosure ----------
el.push(H('17. Validity, limitations and integrity disclosure',HeadingLevel.HEADING_1));
el.push(noteBox([
  new Paragraph({spacing:{after:80},children:[new TextRun({text:'What is measured vs emulated',font:FONT,size:19,bold:true,color:'8A6D00'})]}),
  bullet('Emulated (provisional): baselines B1 (CNN), B2 (LSTM), B3 (Kalman+NN), B5 (SORT), B6 (DeepSORT). These come from documented degradation multipliers relative to UST-Fuse, extended from the FuseMetrics Lab v1 kBaselines table. They are NOT independent implementations and must be replaced before publication (task §7). The abstract’s false-alarm reduction (16.7%) and fragmentation reduction (33.3%) are computed against the emulated strongest baseline (DeepSORT) and are therefore provisional.'),
  bullet('Measured (genuine): all UST-Fuse metrics; baselines B4 and B7 (S2 toggles); the full ablation; per-SNR, per-completeness, attention, calibration, uncertainty, ID-switch and latency analyses; and the ζ/γ sensitivity sweeps.'),
],'FFF3CD'));
el.push(P([runs('Reference-implementation vs idealised architecture. ',{bold:true}),runs('The released S2 engine is a compact analytical proxy of the architecture described in Section 3, not a trained neural network. It uses fixed prototype logits (no gradient training, no dropout, no Monte-Carlo integration), classifies each dwell independently (no sliding-window temporal attention), and associates greedily. Three consequences were measured and must be disclosed: (i) the classifier is under-confident, so temperature scaling raises rather than lowers ECE; (ii) the semantic association factor and the tempering coefficient γ are near-inert; (iii) covariance inflation ζ, not semantics, is the dominant tracking mechanism. The manuscript’s mechanism narrative should either be qualified accordingly or supported by an upgraded implementation.',{})]));
el.push(P([runs('Simulation-to-reality gap. ',{bold:true}),runs('All results are obtained in the digital twin; absolute figures are an upper bound and the transferable content is the relative ordering. Labels are exact by construction (no label-noise robustness demonstrated), and the paired tests, though multiplicity-corrected, are computed over one generative model, so the effective number of independent samples is smaller than the nominal scenario count.',{})]));

// ---------- 18. Manuscript fill map ----------
el.push(H('18. Values transferred to the manuscript',HeadingLevel.HEADING_1));
el.push(P('The following values (identical in abstract, Section 5, conclusion and the corresponding tables) were written into the manuscript in place of the [TO BE FILLED] markers:'));
el.push(table([
  ['Field','Value','Provenance'],
  ['Detection probability',R.pd_pct+'%','measured'],
  ['Macro-F1',R.macro_f1.toFixed(3)+' ± '+R.macro_f1_sd.toFixed(3),'measured'],
  ['ECE',R.ece.toFixed(3),'measured'],
  ['False-alarm reduction vs strongest baseline',R.far_reduction_pct+'%','emulated (provisional)'],
  ['Fragmentation reduction vs strongest baseline',R.frag_reduction_pct+'%','emulated (provisional)'],
  ['MOTA / IDF1',R.mota_pct+'% / '+R.idf1_pct+'%','measured'],
  ['RMSE',R.rmse+' m','measured'],
  ['Max simultaneous targets (real-time)','≥24 measured; ~10⁵ extrapolated','measured'],
],{widths:[5,3,3],size:15}));
el.push(caption('Table 18a. Headline values and their provenance.'));

// ---------- 19. Reproducibility checklist ----------
el.push(H('19. Reproducibility checklist (task §17)',HeadingLevel.HEADING_1));
[['No demo/fallback data','PASS — S3 reported “input: S1+S2 result files” on every run; fallback path never taken.'],
 ['No scenario leakage between folds','PASS — hash split verified pairwise-disjoint for all 30 seeds.'],
 ['Row-count consistency S1/S2/S3','PASS — measurements = classifications rows each seed; truth and track rows logged.'],
 ['Identical seeds in manifest','PASS — 20260730–20260759 recorded in manifest and checksums.'],
 ['Reproducible with fixed configuration','PASS — deterministic given seed; 30 checksummed corpora.'],
 ['relative-improvement formula correct','PASS — (baseline−ours)/baseline×100; provisional where baseline emulated.'],
 ['Metrics identical across CSV / LaTeX / manuscript','PASS — all derived from tables/results.json.'],
 ['No hand-invented numbers','PASS for measured cells; emulated cells traceable to the documented model and labelled.'],
].forEach(([k,v])=>el.push(bullet([runs(k+': ',{bold:true}),runs(v,{})])));

el.push(H('20. Archive contents',HeadingLevel.HEADING_1));
el.push(P('src/ (S1–S3 sources, ablation/timed variants, analysis scripts); build/ (binaries); runs/ (reference corpus, per-seed metric files, aggregate, checksums, stratified data); tables/ (all CSV + LaTeX); figures/ (SVG + PNG for Figures 3–8); manifest/ (split manifest, checksums); manuscript/ (filled manuscript). This appendix and results.json make every number regenerable by re-running the pipeline with the recorded seeds.'));

// ---------- assemble ----------
const doc=new D.Document({styles:{default:{document:{run:{font:FONT,size:20}}}},
  sections:[{properties:{page:{margin:{top:1080,bottom:1080,left:1200,right:1200}}},children:el}]});
D.Packer.toBuffer(doc).then(b=>{fs.writeFileSync('UST-Fuse_Computational_Appendix.docx',b);console.log('WROTE UST-Fuse_Computational_Appendix.docx',b.length,'bytes');});
