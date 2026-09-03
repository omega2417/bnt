const fs = require('fs');
const dx = require('docx');
const {
  Document, Packer, Paragraph, TextRun, AlignmentType, HeadingLevel,
  Table, TableRow, TableCell, WidthType, BorderStyle, PageBreak,
  Header, Footer, PageNumber, LevelFormat, ShadingType,
} = dx;

const D = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const OUT = process.argv[3];

/* MDPI-like page: A4, narrow margins, Palatino Linotype 10 pt */
const FONT = 'Palatino Linotype';
const CW = 9922;                       // A4 (11906) − 2 × 992 DXA margins
const NONE = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const RULE = (sz) => ({ style: BorderStyle.SINGLE, size: sz, color: '000000' });

const fmt = (v) => (v === null || v === undefined) ? '—'
  : (typeof v === 'boolean' ? (v ? 'yes' : 'no') : String(v));

/* ---------------------------------------------------------------- inline */
const t  = (s, o = {}) => new TextRun({ text: s, font: FONT, size: o.size ?? 20,
  bold: o.bold, italics: o.italics, color: o.color, superScript: o.sup });
const m  = (s, o = {}) => new TextRun({ text: s, font: 'Consolas', size: o.size ?? 18, color: o.color });
const bd = (s, o = {}) => t(s, { ...o, bold: true });
const it = (s, o = {}) => t(s, { ...o, italics: true });

/* ------------------------------------------------------------- structure */
function par(runs, o = {}) {
  return new Paragraph({
    alignment: o.align ?? AlignmentType.JUSTIFIED,
    spacing: { before: o.before ?? 0, after: o.after ?? 120, line: o.line ?? 240 },
    indent: o.indent,
    children: Array.isArray(runs) ? runs : [typeof runs === 'string' ? t(runs, o) : runs],
  });
}
/** MDPI headings: bold, same size as body; level 3 bold italic */
function head(text, lvl) {
  const runs = lvl >= 3
    ? [t(text, { bold: true, italics: true })]
    : [t(text, { bold: true, size: lvl === 1 ? 22 : 20 })];
  return new Paragraph({
    heading: lvl === 1 ? HeadingLevel.HEADING_1 : lvl === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
    alignment: AlignmentType.LEFT,
    spacing: { before: lvl === 1 ? 260 : 200, after: 100, line: 240 },
    children: runs,
  });
}

/* MDPI table: horizontal rules only, no fill, 9 pt */
function tcell(content, w, o = {}) {
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    margins: { top: 50, bottom: 50, left: 70, right: 70 },
    verticalAlign: 'center',
    borders: {
      top: o.topRule ? RULE(o.topRule) : NONE,
      bottom: o.botRule ? RULE(o.botRule) : NONE,
      left: NONE, right: NONE,
    },
    children: [new Paragraph({
      alignment: o.align ?? AlignmentType.LEFT,
      spacing: { before: 0, after: 0, line: 220 },
      children: Array.isArray(content) ? content
        : [new TextRun({ text: String(content), font: o.mono ? 'Consolas' : FONT,
                         size: o.size ?? 18, bold: o.bold, italics: o.italics })],
    })],
  });
}
function mtable(headers, rows, widths, o = {}) {
  const aligns = o.aligns || [];
  const mono = o.mono || [];
  const trs = [new TableRow({
    tableHeader: true,
    children: headers.map((h, i) => tcell(h, widths[i], {
      bold: true, align: aligns[i] || AlignmentType.LEFT,
      size: o.hsize ?? 17, topRule: 10, botRule: 6,
    })),
  })];
  rows.forEach((r, ri) => {
    const last = ri === rows.length - 1;
    trs.push(new TableRow({
      children: r.map((c, i) => tcell(c, widths[i], {
        align: aligns[i] || AlignmentType.LEFT, mono: mono.includes(i),
        size: o.size ?? 17, botRule: last ? 10 : 0,
      })),
    }));
  });
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE,
               insideHorizontal: NONE, insideVertical: NONE },
    rows: trs,
  });
}
/** MDPI caption above tables, below figures; 9 pt, bold label */
function tcap(label, text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 180, after: 70, line: 220 },
    children: [t(label + ' ', { size: 18, bold: true }), t(text, { size: 18 })],
  });
}
function tnote(text) {
  return new Paragraph({
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 60, after: 180, line: 220 },
    children: [t(text, { size: 17 })],
  });
}
function bullets(items) {
  return items.map((i, ix) => new Paragraph({
    numbering: { reference: 'mdpi-bul', level: 0 },
    alignment: AlignmentType.JUSTIFIED,
    spacing: { before: ix === 0 ? 140 : 0, after: 80, line: 240 },
    children: Array.isArray(i) ? i : [t(i)],
  }));
}
function statement(label, text) {
  return par([bd(label + ': '), t(text)], { after: 100, size: 18 });
}

const R = AlignmentType.RIGHT, C = AlignmentType.CENTER, J = AlignmentType.JUSTIFIED;

/* ------------------------------------------------------------------ data */
const SC = D.scenarios;
const ord = ['baseline-quiet', 'wan-failover', 'cyber-campaign', 'power-outage', 'compound-challenge'];
const ag = s => SC[s].summary.aggregate;
const net = (s, k) => ag(s).network[k];
const pw = s => ag(s).power;
const de = s => ag(s).detection;
const mc = D.mc, iv = mc.interval, ev = D.validate.evidence, dm = D.demo.summary;

const scRows = ord.reduce((a, s) => a + ag(s).rows, 0);
const doeRows = D.doe.reduce((a, p) => a + p.summary.rows, 0);
const allRows = scRows + dm.aggregate.rows + doeRows;

const ch = [];

/* =========================== FRONT MATTER =========================== */
ch.push(par([t('Article', { bold: true, size: 22 })], { align: AlignmentType.LEFT, after: 160 }));
ch.push(par([t('Specification-Embedded Reproducibility of a Cyber-Range Digital Twin: Rebuilding and Re-Executing a Reference Experiment from Its Text Alone',
  { bold: true, size: 32 })], { align: AlignmentType.LEFT, after: 160, line: 300 }));
ch.push(par([t('Dmytro Prokopovych-Tkachenko', { size: 22 }), t(' *', { size: 22, sup: true })],
  { align: AlignmentType.LEFT, after: 80 }));
ch.push(par([t('Department of Cybersecurity and Information Technologies, University of Customs and Finance, Dnipro, Ukraine; ORCID 0000-0002-6590-3898', { size: 18 })], { after: 60 }));
ch.push(par([t('* Correspondence: omega2417@umsf.edu.ua', { size: 18 })], { after: 200 }));

ch.push(par([bd('Abstract: ', { size: 18 }), t('Digital twins of critical infrastructure are increasingly specified in documents that embed their own executable reference implementation, yet whether such a document is genuinely self-sufficient is rarely tested. This article reports an independent reproduction of the reference experiment of the UMSF cyber-range digital twin, version 2.0, in which the specification text was the only input. All 78 files of the ' , { size: 18 }),
  m('umsf_twin', { size: 17 }),
  t(' package, its test suite and its configurations — 7,000 lines of Python and 1,435 lines of JSON — were mechanically extracted from the document appendices and executed without a single edit. The built-in verification suite passed 40 of 40 checks on the first attempt in 3.2 s. A campaign of five scenarios, a three-replicate demonstration run, an eight-point Latin-hypercube factor screening and a Monte Carlo campaign with sequential stopping produced ' + allRows.toLocaleString('en-US') + ' rows of telemetry. All 62 control values published in the specification were reproduced exactly, including configuration hashes, telemetry row counts, network, power and detection aggregates, and the Monte Carlo confidence interval (71.8948 ms, stopped at the fifth replicate). Determinism was confirmed beyond the built-in check: an independent interpreter invocation in a clean directory produced byte-identical telemetry for all five scenarios. The single divergence was the engine source hash, an expected consequence of recovering source files from Markdown rather than copying them. The reproduction establishes that the specification is a self-sufficient executable artifact; it does not convert any synthetic quantity into a measurement of the physical range, and four uninventoried parameters continue to block hardware-in-the-loop execution by construction.', { size: 18 })],
  { after: 140 }));
ch.push(par([bd('Keywords: ', { size: 18 }), t('reproducibility; digital twin; cyber range; executable specification; deterministic simulation; provenance; data-quality gates; design of experiments; Monte Carlo; synthetic evidence', { size: 18 })], { after: 220 }));

/* =============================== 1 ================================= */
ch.push(head('1. Introduction', 1));
ch.push(par('Computational results are reproducible when an independent party can obtain them again from the materials the authors provide [1,2]. In simulation-based engineering the bar is higher than in data analysis: the artifact under scrutiny is not a script applied to a fixed dataset but a model that generates its own data, so a reproduction must recover the model, its parameterisation, its random-number discipline and its acceptance criteria together. Verification and validation practice separates these concerns explicitly — verification asks whether the model was built as specified, validation whether the specified model represents the referent [3,4] — and only the former is decidable from a document.'));
ch.push(par([t('The specification of the UMSF cyber-range digital twin, version 2.0 [5], makes an unusually strong claim of the first kind. Rather than describing an implementation, it contains one: appendices H through K carry the complete source of a modular reference twin, its configurations, its test suite and a set of control values that the document asserts the implementation will produce. The design is deliberate — the twin depends on no third-party package, so its results cannot drift with an upstream release — and it invites a test that most specifications cannot support: rebuild the system from the prose and check whether the published numbers come back.')]));
ch.push(par('This article reports that test. The contribution is not a new model, a new metric or a new experimental finding about the cyber range. It is an assessment of a document as an executable artifact, together with a re-executed campaign whose artifacts and hashes are released so that the assessment can itself be repeated. Three questions are addressed. First, is the specification text sufficient to reconstruct a working system without recourse to any other source? Second, do the reconstructed system and the published one agree numerically, and where they do not, why? Third, what does such agreement license one to claim, and what does it deliberately not license?'));
ch.push(par('The third question matters because the object of study is a synthetic model of infrastructure that also exists physically. The specification carries an evidence discipline in code: every parameter holds a provenance status, unmeasured parameters block the hardware-coupled execution mode, and telemetry rows are labelled by origin so that synthetic and measured values cannot be pooled. A reproduction that ignored this discipline would produce numbers that look like measurements of a real facility. The present study preserves it and states the resulting claim boundary explicitly in Section 4.4.'));

/* =============================== 2 ================================= */
ch.push(head('2. Materials and Methods', 1));

ch.push(head('2.1. Source Artifact and Extraction Procedure', 2));
ch.push(par([t('The sole input was the specification document [5]: 14,542 lines, 619,550 bytes of Markdown. Files were recovered by a 40-line parser. A heading of the form '), m('#### `path`'), t(' names a target path, and the next fenced block holds its content; the parser tracks fence state so that comment lines inside code are not mistaken for headings. Extraction yielded 78 files: 66 Python modules of the package, the test suite, 8 JSON configurations (a demonstration inventory, a safety policy, a factor definition and five scenarios), a Makefile, a README and a project descriptor.')]));
ch.push(par('No line of recovered code was added, removed or altered, and no missing file was supplied from elsewhere. Package directories were left without initialisation files, as the document leaves them; the implementation resolves correctly as namespace packages. Execution followed the order encoded in the recovered Makefile: test, validate, verify, run, scenarios, doe, mc.'));

ch.push(head('2.2. Computational Environment', 2));
ch.push(tcap('Table 1.', 'Computational environment of the reproduction.'));
ch.push(mtable(['Component', 'Value'], [
  ['Interpreter', `${D.runtime.impl} ${D.runtime.python}`],
  ['Platform', D.runtime.platform],
  ['Third-party dependencies', 'none, by design of the specification'],
  ['Execution mode', 'SIM (the only mode the reference implementation executes)'],
  ['Random seed', String(SC['power-outage'].manifest.seed)],
], [2600, 7322], { size: 17 }));
ch.push(tnote('The implementation opens no network sockets, emits no traffic and performs no hardware writes; these restrictions are enforced by the recovered safety policy rather than by the environment.'));

ch.push(head('2.3. Reference Implementation Under Test', 2));
ch.push(par('The recovered twin is a federated model in which every element of the range is a separate module sharing one federate contract: WAN links, multi-WAN routers and a VPN tunnel; access points and their controllers; managed assets including workstations; six service workloads; a semi-Markov attack-stage chain; a 13-cell battery stack with its management system, transfer switch, charger and three portable power stations; sensors with an explicit measurement-defect model; three detectors and six response playbooks operating in shadow mode. Above these sit a normalisation, feature and labelling pipeline, executable data-quality gates, and an experiment layer providing scenario compilation, factor screening, Monte Carlo with sequential stopping and calibration routines.'));
ch.push(par([t('Two properties of the design bear on reproducibility. Randomness is drawn from named, namespaced streams keyed by replicate identifier, so replicates are independent while a given replicate is reproducible. Each run closes itself with a manifest recording the configuration hash, the engine source hash, a runtime fingerprint, the parameter provenance histogram and the SHA-256 of every artifact, which makes any later comparison exact rather than approximate.')]));

ch.push(head('2.4. Campaign Design', 2));
ch.push(tcap('Table 2.', 'Composition of the reproduced experimental campaign.'));
ch.push(mtable(['Component', 'Runs', 'Telemetry rows', 'Purpose'], [
  ['Scenario suite', '5', scRows.toLocaleString('en-US'), 'baseline, transport failover, attack chain, power loss, compound disruption'],
  ['Demonstration run', '1 × 3 replicates', dm.aggregate.rows.toLocaleString('en-US'), 'replicate independence under an unchanged causal schedule'],
  ['Latin-hypercube screening', '8', doeRows.toLocaleString('en-US'), 'influence of five factors on network, power and detection responses'],
  ['Monte Carlo campaign', '5 of 10 permitted', '—', 'interval estimation with sequential stopping'],
], [2100, 1500, 1500, 4822], { aligns: [null, C, R, null], size: 17 }));
ch.push(tnote('The Monte Carlo campaign reuses the demonstration configuration and reports a run-level metric, so its telemetry is not counted again in the row totals.'));

ch.push(par([t('The five scenarios differ in the events injected into an otherwise identical topology. '), m('baseline-quiet'), t(' injects nothing and serves as a false-alarm control; '), m('wan-failover'), t(' disables the primary uplink twice and then degrades it; '), m('cyber-campaign'), t(' advances a five-stage chain from reconnaissance through lateral movement, low-rate command and control, a Wi-Fi authentication burst and a rogue access-point signal; '), m('power-outage'), t(' removes mains power at 60 s and injects cell imbalance at 300 s over a 1,200-s horizon; '), m('compound-challenge'), t(' combines mains loss, an uplink failure, VPN degradation, reconnaissance, telemetry loss and clock skew within 240 s.')]));

ch.push(head('2.5. Verification and Determinism Protocol', 2));
ch.push(par([t('Verification used the recovered test suite unmodified: 40 checks in eight categories (unit, property, contract, determinism, safety, integration, calibration and performance). Determinism was assessed at two levels. The built-in check compares the canonical row hash of two runs sharing a replicate identifier and confirms that a different identifier yields a different hash. Beyond that, the entire scenario suite was re-executed in a clean output directory by a separate interpreter invocation, and the resulting '), m('telemetry.csv'), t(' files were compared byte for byte against the first campaign. The second level is not part of the published protocol; it was added here to exclude any dependence on process state.')]));

ch.push(head('2.6. Outcome Measures and Comparison Criteria', 2));
ch.push(par('The primary outcome is the proportion of the specification’s control values reproduced exactly. Sixty-two such values were identified: fifty numeric fields of the scenario summary table and twelve further quantities covering the test tally, the configuration hash and parameter provenance of the demonstration inventory, the determinism result, the demonstration run size, the Monte Carlo estimate, its interval bounds and per-replicate values, and the configuration hash and power block of the longest scenario. Comparison is exact — any disagreement in a digit printed by the specification counts as a failure — so no statistical test applies.'));
ch.push(par('Secondary outcomes are the pass status of all data-quality gates, the two levels of determinism, and preservation of the parameter provenance histogram. Reported quantities follow the specification’s own definitions: network availability, mean and tail round-trip time, loss, throughput and goodput ratio per site; state of charge, autonomy, load-shedding and protection-trip step counts for the power subsystem; and confusion counts with derived precision, recall and F1 for detection, with Wilson intervals for recall [6] and cluster bootstrap intervals for run-level Monte Carlo estimates [7].'));

/* =============================== 3 ================================= */
ch.push(head('3. Results', 1));
ch.push(par([it('Provenance statement. '), t('Every value in this section was computed from artifacts of the reproduction campaign, each of which carries a SHA-256 recorded in its run manifest. All values are synthetic model output.')]));

ch.push(head('3.1. Implementation Verification', 2));
ch.push(par('The recovered test suite passed 40 of 40 checks in 3.2 s at the first attempt, with none skipped or marked as expected failures. Table 3 lists the categories.'));
ch.push(tcap('Table 3.', 'Automated verification checks by category.'));
ch.push(mtable(['Category', 'Passed', 'Scope'], [
  ['unit', '6/6', 'queue conservation, zero-capacity path, constant-power solution, access-point uplink flag, bus ordering, ramped event intensity'],
  ['property', '6/6', 'energy monotonicity, cell-voltage envelope, charge and discharge current signs, seed-stream independence, kill-chain causality, priority-group preservation under shedding'],
  ['contract', '4/4', 'rejection of unknown and missing fields, strict JSON without NaN, blank measurements in gap rows, vendor payload mapping'],
  ['determinism', '3/3', 'identical rows for one seed, differing replicates, configuration hash covering event defaults'],
  ['safety', '6/6', 'event-type allowlist, approval requirement for hardware-in-the-loop, egress allowlist, refusal under unknown parameters, inventory invariants, budget limits'],
  ['integration', '6/6', 'valid run artifacts, no directory overwrite, failover and return, shedding and recovery, label isolation from transition truth, corrupted-data detection'],
  ['calibration', '7/7', 'fidelity under distribution shift, approximate Bayesian recovery of a known parameter, simplex minimisation [8], statistical helpers, detection-metric arithmetic, design bounds, Monte Carlo stopping'],
  ['performance', '2/2', 'bounded step cost, inexpensive rule engine'],
], [1400, 900, 7622], { aligns: [null, C, null], mono: [0], size: 16 }));
ch.push(tnote('The safety category is functional rather than declarative: the hardware-in-the-loop mode is refused programmatically while any parameter remains uninventoried.'));

ch.push(head('3.2. Parameter Provenance', 2));
ch.push(par([t('Validation of the demonstration inventory reproduced the published provenance state exactly: ' + D.validate.parameters + ' parameters and ' + D.validate.events + ' event defaults under configuration hash '), m(D.validate.config_hash.slice(0, 16) + '…'), t('. Of these, ' + ev.SYNTHETIC_DEMO + ' carry synthetic demonstration status and ' + ev.UNKNOWN + ' remain unknown; no parameter is measured, vendor-specified, derived or explicitly assumed. The four unknown parameters are the cell chemistry and parallel-branch count of the site A battery and the maximum transmission unit and protocol of the inter-site tunnel. Their status is not a defect: it blocks the hardware-coupled mode in code and confines the battery and tunnel models to acknowledged surrogates.')]));

ch.push(head('3.3. Determinism', 2));
ch.push(par([t('The built-in check reported deterministic rows, differing replicates and a canonical extent of ' + D.verify.rows.toLocaleString('en-US') + ' rows, matching the published result. The additional cross-invocation test passed for every scenario: re-executing the suite in a clean directory from a separate interpreter process produced byte-identical telemetry, so the model carries no dependence on process state, wall-clock time or directory history.')]));

ch.push(head('3.4. Scenario Campaign', 2));
ch.push(tcap('Table 4.', 'Aggregate outcomes of the five scenarios. All data-quality gates passed in every run.'));
ch.push(mtable(
  ['Scenario', 'Rows', 'Avail. A (%)', 'p95 A (ms)', 'p95 B (ms)', 'ΔSoC (pp)', 'Shed', 'Trip', 'TP', 'FP', 'FN'],
  ord.map(s => [s, String(ag(s).rows), fmt(net(s, 'site_a').availability_pct),
    fmt(net(s, 'site_a').rtt_p95_ms), fmt(net(s, 'site_b').rtt_p95_ms), fmt(pw(s).soc_drop_pct),
    String(pw(s).load_shed_steps), String(pw(s).protection_trip_steps),
    String(de(s).tp), String(de(s).fp), String(de(s).fn)]),
  [1850, 700, 950, 900, 900, 900, 620, 580, 520, 480, 522],
  { aligns: [null, R, R, R, R, R, R, R, R, R, R], mono: [0], size: 16, hsize: 15 }));
ch.push(tnote('ΔSoC is the drop in state of charge in percentage points; a negative value denotes net charging from mains. Shed and Trip count simulation steps with load groups disconnected and with protection tripped, respectively.'));

ch.push(head('3.5. Network Outcomes', 2));
ch.push(tcap('Table 5.', 'Network outcomes at site A (main building) and site B (branch).'));
ch.push(mtable(
  ['Scenario', 'Site', 'Avail. (%)', 'RTT mean (ms)', 'p95 (ms)', 'p99 (ms)', 'Loss (%)', 'Thr. (Mbit/s)', 'Goodput', 'Failover (s)'],
  ord.flatMap(s => ['site_a', 'site_b'].map((k, j) => { const n = net(s, k); return [
    j === 0 ? s : '', k === 'site_a' ? 'A' : 'B', fmt(n.availability_pct), fmt(n.rtt_mean_ms),
    fmt(n.rtt_p95_ms), fmt(n.rtt_p99_ms), fmt(n.loss_mean_pct), fmt(n.throughput_mean_mbps),
    fmt(n.goodput_ratio), String(n.failover_seconds)]; })),
  [1700, 520, 900, 1080, 850, 900, 800, 1120, 900, 1152],
  { aligns: [null, C, R, R, R, R, R, R, R, R], mono: [0], size: 15, hsize: 14 }));
ch.push(par([t('Two rows carry the interpretive weight. Under '), m('wan-failover'), t(' availability at site A remains 100% while the 95th percentile rises from 19.15 to 24.00 ms and 15 s of failover accumulate: the model absorbs the uplink loss by redistributing traffic rather than losing the segment. Under '), m('compound-challenge'), t(' availability falls to 91.32%, tail latency at both sites roughly quadruples, and the goodput ratio at site A drops below unity for the only time in the campaign, indicating queues that no longer drain within a step.')]));

ch.push(head('3.6. Power Outcomes', 2));
ch.push(tcap('Table 6.', 'Power-subsystem outcomes.'));
ch.push(mtable(
  ['Scenario', 'SoC start (%)', 'SoC end (%)', 'SoC min (%)', 'Autonomy mean (min)', 'Autonomy worst (min)', 'Battery steps', 'Shed', 'Trip', 'Imbalance (mV)'],
  ord.map(s => { const p = pw(s); return [s, fmt(p.soc_start_pct), fmt(p.soc_end_pct), fmt(p.soc_min_pct),
    fmt(p.autonomy_min_mean), fmt(p.autonomy_min_worst), String(p.battery_steps),
    String(p.load_shed_steps), String(p.protection_trip_steps), fmt(p.cell_imbalance_max_mv)]; }),
  [1700, 900, 880, 880, 1180, 1180, 900, 620, 570, 1112],
  { aligns: [null, R, R, R, R, R, R, R, R, R], mono: [0], size: 15, hsize: 14 }));
ch.push(par([t('In '), m('power-outage'), t(' the loss of mains at 60 s places the pack on discharge for 842 steps; charge falls by 1.21 pp, worst-case autonomy reaches 54.3 min, and the load manager performs 797 steps with groups II and III disconnected while group I is preserved throughout — the ordering property asserted by the specification and checked by one of the property tests. Peak cell imbalance of 120 mV traces directly to the imbalance injection at 300 s.')]));

ch.push(head('3.7. Detection Outcomes', 2));
ch.push(tcap('Table 7.', 'Detection outcomes of the transparent rule baseline, with Wilson intervals for recall.'));
ch.push(mtable(
  ['Scenario', 'TP', 'FP', 'FN', 'TN', 'Precision', 'Recall', 'F1', 'Recall 95% CI', 'FA per 1k steps'],
  ord.map(s => { const d = de(s), w = d.recall_wilson; return [s, String(d.tp), String(d.fp), String(d.fn),
    String(d.tn), fmt(d.precision), fmt(d.recall), fmt(d.f1),
    w.n ? `${w.low.toFixed(3)}–${w.high.toFixed(3)}` : '—', fmt(d.false_alarm_rate_per_1k_steps)]; }),
  [1700, 520, 480, 560, 700, 950, 800, 700, 1500, 2012],
  { aligns: [null, R, R, R, R, R, R, R, C, R], mono: [0], size: 16, hsize: 14 }));
ch.push(tnote('A dash denotes an undefined metric because the run contains no ground-truth events, not a value of zero.'));
ch.push(par([t('These numbers characterise a deliberately transparent rule baseline and must not be read as detector quality. Three scenarios raise no alarm at all, which is the intended behaviour: a rule set with no false positives under nominal load also stays silent during purely infrastructural events that the labelling does not class as cyber events. In '), m('cyber-campaign'), t(' precision is 1.0 at a recall of 0.1965 (95% CI 0.170–0.227), because the rules capture intensive reconnaissance while latent stages of the chain pass unnoticed — precisely the gap the specification intends to expose by comparison with an edge-AI arm. In '), m('compound-challenge'), t(' recall reaches 1.0 over 120 events (95% CI 0.969–1.000) because six simultaneous disruptions produce signatures too coarse to miss; this is a property of the scenario, not of the detector.')]));

ch.push(head('3.8. Replicate Variability', 2));
ch.push(tcap('Table 8.', 'Three replicates of the demonstration configuration.'));
ch.push(mtable(['Replicate', 'Rows', 'Alerts', 'Causal transitions', 'p95 A (ms)', 'ΔSoC (pp)'],
  dm.per_replicate.map(r => [String(r.replicate_id), String(r.rows), String(r.alerts),
    String(r.transitions), fmt(r.summary.network.site_a.rtt_p95_ms), fmt(r.summary.power.soc_drop_pct)]),
  [1500, 1600, 1500, 2000, 1700, 1622], { aligns: [C, R, R, R, R, R], size: 17 }));
ch.push(par('Row counts (1,805–1,811) and alert counts (60–61) vary across replicates while the number of causal transitions is identical at 143. Stochastic streams therefore differ as intended without perturbing the scenario schedule that defines ground truth — the separation on which unbiased labelling depends.'));

ch.push(head('3.9. Factor Screening', 2));
ch.push(par([t('An eight-point Latin hypercube [9] over five factors was executed under design hash '), m('21ba9401d7d5e779…'), t('. Table 9 reports the settings and responses.')]));
ch.push(tcap('Table 9.', 'Latin-hypercube design points and responses.'));
ch.push(mtable(
  ['#', 'SoC₀ (%)', 'Crit. load (W)', 'Failover delay (s)', 'Offered (Mbit/s)', 'Threshold', 'Avail. A (%)', 'p95 A (ms)', 'Shed', 'TP', 'FN', 'Recall'],
  D.doe.map((p, i) => { const s = p.setting, a = p.summary; return [String(i),
    s['power.site_a.initial_soc_pct'].toFixed(2), s['power.site_a.critical_load_w'].toFixed(1),
    String(s['sites.site_a.failover_delay_s']), s['sites.site_a.baseline.offered_load_mbps'].toFixed(1),
    s['detector.threshold'].toFixed(3), fmt(a.network.site_a.availability_pct),
    fmt(a.network.site_a.rtt_p95_ms), String(a.power.load_shed_steps),
    String(a.detection.tp), String(a.detection.fn), fmt(a.detection.recall)]; }),
  [420, 850, 1100, 1150, 1150, 950, 900, 900, 620, 520, 570, 792],
  { aligns: [C, R, R, R, R, R, R, R, R, R, R, R], size: 15, hsize: 13 }));
ch.push(...bullets([
  [bd('The detector threshold dominates detection. '), t('Recall falls monotonically from 0.3125 at a threshold of 0.255 to zero at 0.695, while precision remains 1.0 wherever any alarm is raised. The rule engine trades sensitivity for a clean alarm stream by construction.')],
  [bd('Power factors barely reach the network. '), t('Initial charge between 32% and 89% and critical load between 174 and 378 W move the shedding step count only within 208–210 out of roughly 1,805 steps.')],
  [bd('Offered load and failover delay are weak within the domain. '), t('Tail latency spans 71.69–73.06 ms while offered load varies from 113 to 392 Mbit/s, so the queue model remains far from saturation over the screened region.')],
  [bd('Aleatory variation is an order of magnitude smaller. '), t('The Monte Carlo spread of the same response is about 0.34 ms, against a 1.4 ms range attributable to the design factors. No invariant violation occurred at any design point.')],
]));

ch.push(head('3.10. Monte Carlo with Sequential Stopping', 2));
ch.push(tcap('Table 10.', 'Monte Carlo campaign for the site A tail-latency response.'));
ch.push(mtable(['Field', 'Value'], [
  ['Response', mc.metric],
  ['Replicate budget', '10'],
  ['Target half-width', '2.0 ms'],
  ['Replicates executed', String(mc.replicates)],
  ['Stopping reason', mc.stopped_because + ' (target half-width attained)'],
  ['Point estimate', `${iv.estimate} ms`],
  ['Cluster bootstrap 95% CI', `${iv.low.toFixed(4)}–${iv.high.toFixed(4)} ms`],
  ['Normal-approximation 95% CI', `${iv.normal_approx.low.toFixed(4)}–${iv.normal_approx.high.toFixed(4)} ms`],
  ['Per-replicate values (ms)', mc.values.join(', ')],
], [3000, 6922], { size: 17 }));
ch.push(par('The campaign stopped at the fifth of ten permitted replicates once the interval half-width met its target. Because the unit of analysis is the run, the interval is constructed by cluster bootstrap [7]; the attained half-width of 0.17 ms is an order of magnitude below the target, indicating low dispersion at a fixed configuration.'));

ch.push(head('3.11. Data-Quality Gates', 2));
ch.push(tcap('Table 11.', 'Data-quality gate outcomes, reported as value / threshold. All 35 evaluations passed.'));
ch.push(mtable(['Gate', 'baseline', 'wan', 'cyber', 'power', 'compound'],
  SC['power-outage'].summary.gates.results.map(g => [g.gate, ...ord.map(s => {
    const r = SC[s].summary.gates.results.find(x => x.gate === g.gate);
    return `${fmt(r.value)} / ${fmt(r.threshold)}`; })]),
  [2200, 1550, 1550, 1550, 1550, 1522], { aligns: [null, C, C, C, C, C], mono: [0], size: 16, hsize: 15 }));
ch.push(par([t('The completeness row is the informative one. Under '), m('compound-challenge'), t(' completeness falls to 95.66% against a 90% threshold because the telemetry-loss injection at 300 s creates genuine gaps, while the gap-blanking gate simultaneously reports zero: the gaps are marked as gaps rather than filled with invented measurements. Reduced completeness with preserved labelling honesty is the expected outcome, and it is the combination the gates exist to distinguish.')]));

ch.push(head('3.12. Fidelity to the Published Control Values', 2));
ch.push(par('Fifty numeric fields of the scenario summary table matched exactly, as did the twelve further control quantities listed in Table 12: 62 of 62 in total.'));
ch.push(tcap('Table 12.', 'Control values beyond the scenario summary table.'));
ch.push(mtable(['Source', 'Quantity', 'Published', 'Reproduced'], [
  ['K.2', 'automated checks', '40/40', '40/40'],
  ['K.3', 'configuration hash, demonstration inventory', '4e162d71…21a740', D.validate.config_hash.slice(0, 8) + '…' + D.validate.config_hash.slice(-6)],
  ['K.3', 'parameters / event defaults', '198 / 10', `${D.validate.parameters} / ${D.validate.events}`],
  ['K.3', 'provenance histogram', '4 unknown, 194 synthetic', `${ev.UNKNOWN} unknown, ${ev.SYNTHETIC_DEMO} synthetic`],
  ['K.3', 'identity of unknown parameters', 'chemistry, parallel count, VPN MTU, VPN protocol', 'identical set'],
  ['K.4', 'determinism / replicates / rows', 'yes / yes / 1,806', `${fmt(D.verify.deterministic)} / ${fmt(D.verify.replicates_differ)} / ${D.verify.rows.toLocaleString('en-US')}`],
  ['K.5', 'demonstration run', '5,422 rows, gates passed', `${dm.aggregate.rows.toLocaleString('en-US')} rows, gates ${dm.gates.passed ? 'passed' : 'failed'}`],
  ['K.7', 'Monte Carlo estimate', '71.8948 ms', `${iv.estimate} ms`],
  ['K.7', 'cluster interval bounds', '71.7355–72.0784 ms', `${iv.low.toFixed(4)}–${iv.high.toFixed(4)} ms`],
  ['K.7', 'per-replicate values', '71.725; 71.68; 72.2515; 71.905; 71.9125', mc.values.join('; ')],
  ['K.8', 'configuration hash, longest scenario', 'e2dbbb72…101088', SC['power-outage'].summary.config_hash.slice(0, 8) + '…' + SC['power-outage'].summary.config_hash.slice(-6)],
  ['K.8', 'power block of that scenario', 'SoC 81.99→80.78, shed 797, trip 53', `SoC ${pw('power-outage').soc_start_pct}→${pw('power-outage').soc_end_pct}, shed ${pw('power-outage').load_shed_steps}, trip ${pw('power-outage').protection_trip_steps}`],
], [900, 2900, 3050, 3072], { aligns: [C, null, null, null], size: 16 }));
ch.push(tnote('Section labels refer to the reproduction appendix of the specification [5]. Every pair agrees exactly.'));

/* =============================== 4 ================================= */
ch.push(head('4. Discussion', 1));

ch.push(head('4.1. Principal Findings', 2));
ch.push(par('The specification is a self-sufficient executable artifact. Its text alone was enough to rebuild a system that passes its own verification suite at the first attempt and returns every published control value unchanged. This is a stronger result than the usual reproducibility claim, in which authors supply a repository and a reader re-runs it: here the repository was reconstituted from prose, so the document rather than an archive carries the reproducibility.'));
ch.push(par('The determinism result explains why this is possible. A model whose randomness is drawn from named streams keyed by replicate identifier, whose configuration is hashed, and which depends on no third-party package has no channel through which environment drift can enter. The cross-invocation test makes that concrete: byte-identical telemetry from a separate process is a property most simulation codebases cannot demonstrate, and it is what allows exact rather than tolerance-based comparison of 62 control values.'));

ch.push(head('4.2. The Single Divergence', 2));
ch.push(par([t('One published value did not match. The engine source hash is '), m('2136f8f4…'), t(' in this reproduction against '), m('925c24c6…'), t(' in the specification. The quantity is a digest over the bytes of the implementation’s source files, and recovery from Markdown restores those files only up to trailing-newline conventions inside fenced blocks. Every quantity derived from behaviour — configuration hashes, row counts, aggregates, gate values, intervals — agrees exactly, so what was recovered is the semantics of the implementation rather than a byte-wise copy of its file tree. The divergence is therefore diagnostic rather than adverse: it marks precisely the boundary of what a document can transport, and it argues for publishing a source manifest alongside an embedded implementation if byte-level identity is also intended.')]));

ch.push(head('4.3. Implications for Specification Practice', 2));
ch.push(par('Three design choices did the work and transfer to other projects. Embedding the implementation in the specification removes the possibility that document and code diverge. Refusing third-party dependencies removes the largest source of environment drift, at the acknowledged cost of forgoing packet-level networking and electrochemical battery backends. Encoding the evidence discipline in code — provenance status per parameter, a hardware mode that refuses to run while parameters are uninventoried, origin labels on telemetry rows — means the boundary between synthetic and measured survives reproduction by a third party who has no stake in respecting it.'));
ch.push(par('The last point deserves emphasis. In this reproduction the discipline was tested adversarially in the mildest possible sense: the reproducer had every practical incentive to produce complete-looking results and none to preserve four inconvenient unknown parameters. The parameters survived because the code, not the prose, enforces them.'));

ch.push(head('4.4. Claim Boundary and Limitations', 2));
ch.push(par('What this study establishes is bounded. Reproducibility here concerns the specification as an artifact: its text yields an identical executable system. It transfers no quantity from the synthetic category to the measured one. None of the reported values is a measurement of the physical UMSF cyber range, and none confirms actual WAN, VPN or transfer-switch switching times, Wi-Fi coverage or capacity, power-source autonomy, battery thermal behaviour or field detector accuracy.'));
ch.push(...bullets([
  'Only the SIM execution mode was exercised. Emulation and hardware-in-the-loop modes are not implemented, and the replay pipeline exists without real data to replay.',
  'There is no packet-level or radio-frequency backend, so Wi-Fi and queueing remain aggregated and no claim about coverage or radio planning is made.',
  'The battery remains a gray-box surrogate without electrochemistry; synthetic electrical limits are not an authorisation for any current or voltage.',
  'Detectors are uncalibrated, so the reported precision of 1.0 reflects a transparent rule baseline rather than field performance.',
  'The reproduction used a single platform and interpreter version; cross-platform invariance of floating-point arithmetic was not tested and is a plausible failure mode for exact-comparison protocols.',
  'The screening design comprises eight points and is intended to exercise the design mechanism, not to estimate global sensitivity indices, which would require a substantially larger sample.',
]));

/* =============================== 5 ================================= */
ch.push(head('5. Conclusions', 1));
ch.push(par('An independent reproduction of the UMSF cyber-range digital twin experiment was carried out with the specification text as the only input. All 78 files of the reference implementation were mechanically recovered from the document, the built-in suite passed 40 of 40 checks at the first attempt, and a campaign of five scenarios, a three-replicate demonstration, an eight-point screening design and a Monte Carlo run with sequential stopping reproduced all 62 published control values exactly. Determinism held both within a process and across independent interpreter invocations, the latter yielding byte-identical telemetry. The sole divergence, the engine source hash, is an expected artifact of recovering source from Markdown and does not affect any behavioural quantity.'));
ch.push(par('The specification therefore qualifies as a self-sufficient executable artifact, and the practices that make it so — an embedded implementation, no third-party dependencies, named random streams, hashed configurations, per-run manifests and an evidence discipline enforced in code — are transferable to other infrastructure digital twins. The reproduction changes nothing about the epistemic status of the model’s outputs: they remain synthetic, four parameters remain uninventoried, and hardware-coupled execution remains blocked by construction until physical inventory and an approved protocol exist. Recalibrating the twin against field telemetry, and extending the reproduction protocol across platforms and interpreter versions, are the natural next steps.'));

/* ============================ BACK MATTER ========================== */
ch.push(par([t('')], { after: 120 }));
ch.push(statement('Author Contributions', 'Conceptualization, methodology, software, validation, formal analysis, investigation, data curation, writing—original draft preparation, writing—review and editing, and visualization were performed by the sole author, who has read and agreed to the submitted version of the manuscript.'));
ch.push(statement('Funding', 'This research received no external funding. Computational infrastructure was provided by the University of Customs and Finance.'));
ch.push(statement('Institutional Review Board Statement', 'Not applicable. The study involved no human participants, no personal data and no physical infrastructure.'));
ch.push(statement('Informed Consent Statement', 'Not applicable.'));
ch.push(statement('Data Availability Statement', 'The recovered implementation, the extraction tool, the report generator, the run manifests, summaries and generated per-run reports of every run in this campaign are archived in the project repository under experiments/umsf_twin_reproduction. Telemetry and ground-truth tables are not archived because they are regenerated deterministically by the documented commands; the SHA-256 of each is recorded in the corresponding run manifest, so any regeneration can be verified against the campaign reported here.'));
ch.push(statement('Acknowledgments', 'The author thanks the IT service of the University of Customs and Finance for maintaining the documented range inventory on which the demonstration configuration is based.'));
ch.push(statement('Conflicts of Interest', 'The author declares no conflict of interest.'));
ch.push(statement('Declaration of Generative AI', 'Generative AI assisted with source extraction tooling, document structure and language editing. The author remains responsible for the design, execution, verification and interpretation of the reproduction. No generated value is presented as a measurement, and AI is not credited as an author.'));

ch.push(head('References', 1));
const REFS = [
  'Peng, R.D. Reproducible research in computational science. Science 2011, 334, 1226–1227.',
  'Association for Computing Machinery. Artifact Review and Badging, Version 2.0; ACM: New York, NY, USA, 2020.',
  'Sargent, R.G. Verification and validation of simulation models. J. Simul. 2013, 7, 12–24.',
  'Kleijnen, J.P.C. Verification and validation of simulation models. Eur. J. Oper. Res. 1995, 82, 145–162.',
  'Prokopovych-Tkachenko, D. Software Digital Twin of the UMSF Cyber Range: Extended Technical Specification and Executable Reference Prototype, version 2.0; internal technical document; University of Customs and Finance: Dnipro, Ukraine, 2026.',
  'Wilson, E.B. Probable inference, the law of succession, and statistical inference. J. Am. Stat. Assoc. 1927, 22, 209–212.',
  'Efron, B. Bootstrap methods: another look at the jackknife. Ann. Stat. 1979, 7, 1–26.',
  'Nelder, J.A.; Mead, R. A simplex method for function minimization. Comput. J. 1965, 7, 308–313.',
  'McKay, M.D.; Beckman, R.J.; Conover, W.J. A comparison of three methods for selecting values of input variables in the analysis of output from a computer code. Technometrics 1979, 21, 239–245.',
  'Wilkinson, M.D.; Dumontier, M.; Aalbersberg, I.J.; Appleton, G.; Axton, M.; Baak, A.; et al. The FAIR Guiding Principles for scientific data management and stewardship. Sci. Data 2016, 3, 160018.',
  'National Institute of Standards and Technology. Guide to Operational Technology (OT) Security; NIST SP 800-82 Rev. 3; NIST: Gaithersburg, MD, USA, 2023.',
  'Bodeau, D.J.; Graubart, R.D.; Fabius-Greene, J.; Laderman, R. Cyber Resiliency Engineering Aid—The Updated Cyber Resiliency Engineering Framework and Guidance on Applying Cyber Resiliency Techniques; MITRE: Bedford, MA, USA, 2015.',
  'Prokopovych-Tkachenko, D. Field evaluation of provenance-aware blockchain-assisted sensing (BIoT-STDM) on the UMSF distributed cyber range: a matched four-mode experiment. Technical report; University of Customs and Finance: Dnipro, Ukraine, 2026.',
];
REFS.forEach((r, i) => ch.push(new Paragraph({
  alignment: AlignmentType.JUSTIFIED,
  spacing: { before: 0, after: 60, line: 220 },
  indent: { left: 420, hanging: 420 },
  children: [t(`${i + 1}. `, { size: 18 }), t(r, { size: 18 })],
})));

ch.push(par([it('Disclaimer: All quantitative results reported in this article are synthetic model output produced under the stated assumptions. They are not measurements of the physical UMSF cyber range.', { size: 17 })], { before: 200 }));

/* ------------------------------------------------------------------ doc */
const doc = new Document({
  creator: 'Dmytro Prokopovych-Tkachenko',
  title: 'Specification-Embedded Reproducibility of a Cyber-Range Digital Twin',
  description: 'MDPI-style manuscript reporting an independent reproduction of the UMSF cyber-range digital twin reference experiment',
  numbering: { config: [{ reference: 'mdpi-bul', levels: [{
    level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
    style: { paragraph: { indent: { left: 420, hanging: 220 } } } }] }] },
  styles: { default: {
    document: { run: { font: FONT, size: 20 }, paragraph: { spacing: { line: 240 } } },
    heading1: { run: { font: FONT, size: 22, bold: true, color: '000000' } },
    heading2: { run: { font: FONT, size: 20, bold: true, color: '000000' } },
    heading3: { run: { font: FONT, size: 20, bold: true, italics: true, color: '000000' } },
  } },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 992, right: 992 } } },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [t('', { size: 16 }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 16 })],
    })] }) },
    children: ch,
  }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log('wrote', OUT, b.length); });
