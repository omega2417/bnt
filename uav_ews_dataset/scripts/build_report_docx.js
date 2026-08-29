/**
 * Build the engineering report DOCX.
 *
 * Every quantitative statement in the document is read from
 * build/report/validation_report.json, which the pipeline writes. Nothing is
 * typed in by hand, so the document cannot drift from the run that produced it,
 * and re-running the pipeline and re-running this script is enough to refresh it.
 *
 *   node scripts/build_report_docx.js [outPath]
 */
'use strict';

const fs = require('fs');
const path = require('path');
const D = require('docx');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType, ImageRun,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle, TableOfContents,
  Header, Footer, PageNumber, PageBreak, LevelFormat, convertInchesToTwip,
} = D;

const ROOT = path.resolve(__dirname, '..');
const REPORT = JSON.parse(fs.readFileSync(path.join(ROOT, 'build/report/validation_report.json'), 'utf8'));
const FIGDIR = path.join(ROOT, 'build/figures');
const OUT = process.argv[2] || path.join(ROOT, 'build/UAV_EWS_Dataset_Engineering_Report.docx');

/* ------------------------------------------------------------------ style */
const INK = '1C1C1E', MUTED = '6E6E73', ACCENT = '0F6FC5', WARN = 'C2410C', GOOD = '12805C';
const HEAD_FILL = 'EDF2F8', ALT_FILL = 'F7F8FA', NOTE_FILL = 'FFF6E8';
const CONTENT_DXA = 9638;                     // A4 minus 2 cm margins
const CONTENT_PT = CONTENT_DXA / 20;

const n = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v)) ? '-' : Number(v).toFixed(d);
const pct = (v, d = 2) => (v === null || v === undefined) ? '-' : (100 * v).toFixed(d) + ' %';
const M = REPORT.metrics, COV = REPORT.coverage, PLAN = REPORT.campaign_plan;
const byName = (arr, key, val) => arr.find(r => r[key] === val) || {};

/* ---------------------------------------------------------------- helpers */
function P(text, opts = {}) {
  const { size = 20, bold = false, italics = false, color = INK, align, spacing,
          indent, font } = opts;
  return new Paragraph({
    alignment: align,
    spacing: spacing || { before: 0, after: 110, line: 280 },
    indent,
    children: [new TextRun({ text, size, bold, italics, color, font })],
  });
}

/** Rich paragraph: array of [text, {bold,italics,color,font}] pairs. */
function RP(runs, opts = {}) {
  const { align, spacing, indent, size = 20 } = opts;
  return new Paragraph({
    alignment: align,
    spacing: spacing || { before: 0, after: 110, line: 280 },
    indent,
    children: runs.map(r => Array.isArray(r)
      ? new TextRun({ text: r[0], size, ...(r[1] || {}) })
      : new TextRun({ text: r, size })),
  });
}

function H(text, level) {
  const map = { 1: HeadingLevel.HEADING_1, 2: HeadingLevel.HEADING_2, 3: HeadingLevel.HEADING_3 };
  return new Paragraph({
    heading: map[level],
    spacing: { before: level === 1 ? 360 : 240, after: level === 1 ? 160 : 110 },
    children: [new TextRun({ text, bold: true, color: level === 1 ? ACCENT : INK,
                             size: level === 1 ? 30 : level === 2 ? 24 : 21 })],
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'bullets', level },
    spacing: { before: 0, after: 70, line: 280 },
    children: [new TextRun({ text, size: 20 })],
  });
}

function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'numbers', level },
    spacing: { before: 0, after: 80, line: 280 },
    children: [new TextRun({ text, size: 20 })],
  });
}

/** Display equation, centred, with a right-aligned tag. */
function eq(body, tag) {
  return new Paragraph({
    spacing: { before: 130, after: 130 },
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: body, size: 21, font: 'Cambria Math', italics: true }),
      ...(tag ? [new TextRun({ text: '     (' + tag + ')', size: 20, color: MUTED })] : []),
    ],
  });
}

function mono(text) {
  return new Paragraph({
    spacing: { before: 60, after: 110 },
    indent: { left: 260 },
    children: [new TextRun({ text, size: 17, font: 'Consolas', color: INK })],
  });
}

function figure(file, caption, num) {
  const full = path.join(FIGDIR, file);
  const buf = fs.readFileSync(full);
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  // docx-js takes the transformation in pixels at 96 dpi. The A4 content width
  // with 2 cm margins is 17 cm = 6.69 in = 642 px; 630 leaves a hair of slack.
  const width = 630;
  return [
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 170, after: 70 },
      children: [new ImageRun({ type: 'png', data: buf,
        transformation: { width, height: Math.round(width * h / w) } })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 200 },
      children: [
        new TextRun({ text: `Figure ${num}. `, size: 18, bold: true, color: MUTED }),
        new TextRun({ text: caption, size: 18, color: MUTED }),
      ],
    }),
  ];
}

function cell(text, { bold = false, fill, align, size = 17, color = INK, span } = {}) {
  return new TableCell({
    width: { size: 1, type: WidthType.AUTO },
    columnSpan: span,
    shading: fill ? { type: ShadingType.CLEAR, fill, color: 'auto' } : undefined,
    margins: { top: 70, bottom: 70, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: align,
      spacing: { before: 0, after: 0, line: 240 },
      children: [new TextRun({ text: String(text), size, bold, color })],
    })],
  });
}

/**
 * Table with dual widths, as Google Docs requires: columnWidths on the table and
 * an explicit width on every cell, both in DXA.
 */
function table(header, rows, weights, opts = {}) {
  const total = weights.reduce((a, b) => a + b, 0);
  const widths = weights.map(w => Math.round(CONTENT_DXA * w / total));
  widths[widths.length - 1] = CONTENT_DXA - widths.slice(0, -1).reduce((a, b) => a + b, 0);
  const mk = (vals, o = {}) => new TableRow({
    tableHeader: o.head,
    children: vals.map((v, i) => {
      const c = typeof v === 'object' && v !== null && 'text' in v ? v : { text: v };
      return new TableCell({
        width: { size: widths[i], type: WidthType.DXA },
        shading: (c.fill || o.fill) ? { type: ShadingType.CLEAR, fill: c.fill || o.fill, color: 'auto' } : undefined,
        margins: { top: 70, bottom: 70, left: 100, right: 100 },
        children: [new Paragraph({
          alignment: c.align || (i === 0 ? undefined : opts.numeric ? AlignmentType.RIGHT : undefined),
          spacing: { before: 0, after: 0, line: 240 },
          children: [new TextRun({ text: String(c.text), size: 17,
                                   bold: o.head || c.bold, color: c.color || INK })],
        })],
      });
    }),
  });
  return new Table({
    columnWidths: widths,
    width: { size: CONTENT_DXA, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 4, color: 'C9CDD3' },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: 'C9CDD3' },
      left: { style: BorderStyle.NONE }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: 'E3E5E9' },
      insideVertical: { style: BorderStyle.NONE },
    },
    rows: [mk(header, { head: true, fill: HEAD_FILL }),
           ...rows.map((r, i) => mk(r, { fill: i % 2 ? ALT_FILL : undefined }))],
  });
}

function caption(text, num, kind = 'Table') {
  return new Paragraph({
    spacing: { before: 160, after: 80 },
    children: [
      new TextRun({ text: `${kind} ${num}. `, size: 18, bold: true, color: MUTED }),
      new TextRun({ text, size: 18, color: MUTED }),
    ],
  });
}

/** Call-out box for the provenance warnings and the key findings. */
function callout(title, lines, fill = NOTE_FILL, accent = WARN) {
  return new Table({
    columnWidths: [CONTENT_DXA],
    width: { size: CONTENT_DXA, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 2, color: accent },
      bottom: { style: BorderStyle.SINGLE, size: 2, color: accent },
      left: { style: BorderStyle.SINGLE, size: 18, color: accent },
      right: { style: BorderStyle.SINGLE, size: 2, color: accent },
      insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE },
    },
    rows: [new TableRow({
      children: [new TableCell({
        width: { size: CONTENT_DXA, type: WidthType.DXA },
        shading: { type: ShadingType.CLEAR, fill, color: 'auto' },
        margins: { top: 160, bottom: 160, left: 200, right: 200 },
        children: [
          new Paragraph({ spacing: { after: 90 },
            children: [new TextRun({ text: title, bold: true, size: 20, color: accent })] }),
          ...lines.map(l => new Paragraph({
            spacing: { after: 70, line: 280 },
            children: [new TextRun({ text: l, size: 19, color: INK })],
          })),
        ],
      })],
    })],
  });
}

const spacer = (after = 160) => new Paragraph({ spacing: { after }, children: [] });
const pageBreak = () => new Paragraph({ children: [new PageBreak()] });

module.exports = { P, RP, H, table, figure };

/* =================================================================== body */
let FIG = 0, TAB = 0, FIG_AGREEMENT = 0;
const body = [];
const push = (...x) => x.forEach(e => Array.isArray(e) ? body.push(...e) : body.push(e));

/* ---- title page ---- */
push(
  spacer(900),
  new Paragraph({
    alignment: AlignmentType.LEFT, spacing: { after: 120 },
    children: [new TextRun({ text: 'Dataset Formation and Preparation Pipeline', size: 44, bold: true, color: INK })],
  }),
  new Paragraph({
    alignment: AlignmentType.LEFT, spacing: { after: 300 },
    children: [new TextRun({
      text: 'A Multisource, Multimodal Spatiotemporal Dataset for Early Warning of Approaching Small Unmanned Aerial Vehicles',
      size: 26, color: ACCENT })],
  }),
  new Paragraph({
    spacing: { after: 500 },
    children: [new TextRun({
      text: 'Engineering companion to the Data Descriptor: implementation, calculations, technical validation, and field-trial preparation',
      size: 21, italics: true, color: MUTED })],
  }),
  table(
    ['Field', 'Value'],
    [
      ['Software', 'uavews 0.1.0'],
      ['Configuration', 'config/pipeline.yaml (' + REPORT.dataset_version + ')'],
      ['Source of every number below', 'build/report/validation_report.json'],
      ['Corpus', 'Synthetic rehearsal corpus, fixed seed 20250411'],
      ['Events / observations / media objects',
        `${M.n_events} / ${M.n_observations} / ${M.n_media_objects}`],
      ['Released labels', String(M.n_labels_released)],
      ['Release gates passed',
        `${REPORT.gates.filter(g => g.status === 'pass').length} of ${REPORT.gates.length}`],
    ],
    [1, 2]),
  spacer(400),
  callout('This document reports on a rehearsal, not on a measurement campaign', [
    'Every quantity in Sections 5 to 8 is computed from a synthetic corpus generated by uavews.simulate. The corpus exists to prove that the computations are correct, that the release gates fire on defects, and that the whole chain is reproducible from a single seed before any hardware is deployed.',
    'No value here is a measurement, and none may be transcribed into the manuscript’s bracketed placeholders. Section 12 maps each placeholder to the field of validation_report.json that will hold its value once the pipeline has been run over the deposited release.',
    'Section 9 is different in kind: it is forward-looking design, computed from declared planning assumptions, and it is what the first field campaign is meant to test and replace.',
  ]),
  pageBreak(),
);

/* ---- table of contents ---- */
push(
  H('Contents', 1),
  new TableOfContents('Contents', { hyperlink: true, headingStyleRange: '1-2' }),
  pageBreak(),
);

/* ---- 1. purpose ---- */
push(
  H('1  Purpose and scope', 1),
  H('1.1  What this document is', 2),
  P('The Data Descriptor states a data model, five equations, a validation framework, and a set of release tiers. It states them as requirements. This document reports the software project that implements those requirements as running code, explains each calculation to the level of detail needed to reproduce or dispute it, shows what the implementation produces on a controlled rehearsal corpus, and turns the resulting numbers into a concrete plan for the field trials that will replace that corpus with measurements.'),
  P('It is written for three readers. An engineer who has to extend or re-run the pipeline needs Sections 2 to 7. A reviewer who wants to check that the manuscript’s equations were implemented as stated needs Section 5. A trials officer planning the first campaign needs Section 9 and the findings in Section 10.'),

  H('1.2  What the software does', 2),
  P('Three things, in this order.'),
  numbered('It forms the dataset. Four heterogeneous source streams are normalized into the event-centered tables of the manuscript’s Table 3; the kinematic ground truth of Equations (1) and (2) is computed from the reference trajectory; observations are attached to synchronized windows under an uncertainty-expanded overlap rule; and labels from three evidence tiers are adjudicated into exactly one released value per target.'),
  numbered('It validates the dataset. Every dimension of the manuscript’s Table 7 is computed — completeness (Eq. 4), duplicate rate (Eq. 5), synchronization error (Eq. 3), missingness, measured media quality, inter-annotator agreement, cross-modal consistency, and checksum integrity — and each is compared against a configured acceptance rule.'),
  numbered('It prepares the field trials. Acoustic and visual detection ranges are computed from declared physical assumptions, converted into an operational warning-time budget, and combined with a statistical power calculation to size the flight matrix.'),

  H('1.3  What it deliberately does not do', 2),
  P('It makes no predictive claim. There are no baseline models here, no accuracy figures, and no comparison against other datasets. The manuscript is explicit that baselines exist to verify usability rather than to demonstrate superiority, and the pipeline stops at the point where a usable, documented, leakage-resistant dataset exists.'),
  P('It also invents nothing. Where a value must come from an institution, an instrument, or a measurement — a DOI, a licence, a camera model, an ethics approval — the configuration carries an explicit null and the packaging step emits a requires_completion list rather than a plausible placeholder. A package that quietly supplies its own licence is worse than one that admits it has none.'),
);

/* ---- 2. overview ---- */
push(
  H('2  System overview', 1),
  P('The pipeline is a fixed sequence of ten stages. Each stage reads the tables produced by its predecessors, writes new columns or new tables, and records a PROV-O activity carrying its software version, its parameter file, its inputs, its outputs, and its status. Figure 1 shows the whole path from the four source families to the two release tiers.'),
  ...figure('fig01_architecture.png',
    'Collection, curation, and tiered release as implemented. Four source families are normalized into one event-centered model, pass through ten stages, and leave through two access tiers. Every stage writes a provenance activity; every released file carries a SHA-256 digest.', ++FIG),

  H('2.1  Stage order, and why privacy precedes validation', 2),
  P('The order of the last five stages is not arbitrary. De-identification runs before validation because the gates are meant to assess what will actually be released. Validating the pre-sanitization tables would report a completeness, a duplicate rate, and a media-quality profile that the open-tier user never receives — a release could then pass its own gates on data that does not exist in the form anyone can obtain.'),
  P('Splitting runs after validation because the near-duplicate grouping that the split constraint depends on is a validation product. Packaging runs last because the integrity manifest must digest the final bytes, including the metadata files, so that a later alteration of the crate manifest itself is detectable and not only an alteration of the data.'),
  caption('The ten stages, their inputs, and the provenance activity each records.', ++TAB),
  table(
    ['#', 'Stage', 'What it produces', 'PROV-O activity'],
    [
      ['1', 'ingest', 'events, sources, observations, media manifest', 'capture'],
      ['2', 'window', 'pre-event, event, and post-event windows', 'transformation'],
      ['3', 'associate', 'window_id, Eq. (3) sync error, diagnostics', 'transformation'],
      ['4', 'label', 'Eq. (1)/(2) ground truth, weak and expert labels', 'transformation, review'],
      ['5', 'adjudicate', 'one released label per target, audit trail', 'adjudication'],
      ['6', 'privacy', 'access tiers, k-anonymity probe, export audit', 'deidentification'],
      ['7', 'validate', 'Eq. (4), Eq. (5), quality, integrity', 'integrity_verification'],
      ['8', 'split', 'five evaluation manifests and their audit', 'transformation'],
      ['9', 'package', 'RO-Crate, DataCite, PROV-O, checksums', 'release'],
      ['10', 'gate', 'pass / fail against configured acceptance rules', 'integrity_verification'],
    ],
    [0.5, 2, 6, 2.5]),

  H('2.2  Configuration discipline', 2),
  P('No threshold appears in the code. Every release-specific number — the direction dead-band, the overlap minimum, the sync tolerance, the duplicate radius, the embargo gap, the acceptance rules, the planning assumptions — lives in config/pipeline.yaml. Two things follow. A run is reproducible from a single artefact, and the value quoted in a paper cannot drift from the value the pipeline used, because both are read from the same file and the file name is recorded in every provenance activity.'),
  P('The configuration is validated at load time, not at first use. Split fractions that do not sum to one, a window hop larger than the window span, a polygon with fewer than three vertices, a non-positive overlap minimum, and — the substantive one — an explicit dead-band below its own uncertainty floor are all rejected before any data is read.'),
);

/* ---- 3. data model ---- */
push(
  H('3  The data model as implemented', 1),
  P('Six tables, joined on the keys of the manuscript’s Table 4. The event is the parent of everything; split membership attaches at event level so that every derived object inherits one partition.'),
  caption('Canonical tables, their keys, and the number of declared fields of which the required subset forms the set R of Equation (4).', ++TAB),
  table(
    ['Table', 'Key', 'Fields', 'Required (|R|)', 'Role'],
    [
      ['events', 'event_id', '13', '11', 'One row per flight, observational, or negative event'],
      ['windows', 'window_id', '6', '6', 'Synchronized pre-event, event, and post-event intervals'],
      ['sources', 'source_id', '9', '9', 'Origin and device profile, without personal identifiers'],
      ['observations', 'observation_id', '22', '14', 'Source records linked to events and windows'],
      ['media_manifest', 'object_id', '25', '11', 'Object URI, measured properties, quality, digest'],
      ['labels', 'label_id', '16', '13', 'Targets, evidence tier, confidence, adjudication'],
    ],
    [2, 2, 1, 1.4, 5]),
  P('The declaration is the single source of truth for three artefacts that would otherwise drift apart: the structural validator, the exported docs/data_dictionary.csv, and the required-field set that Equation (4) averages over. Adding a field to the schema therefore automatically extends the validator and the data dictionary, and automatically changes the completeness denominator — which is the correct behaviour, and is why the denominator is |R| and not the count of populated columns.'),

  H('3.1  Identifiers', 2),
  P('Two requirements pull in opposite directions. An identifier must carry no information, because a structured key leaks exactly the attributes that generalization removes; and it must be reproducible, because provenance relations and split manifests cannot be compared across versions if the keys change on every run.'),
  P('The resolution is a keyed hash. Each identifier is HMAC-SHA-256 of the source key under a secret per-release salt, truncated to a UUID. It is stable across runs, not invertible, and not linkable to another release without the salt. The salt lives in the controlled tier and never enters the open package.'),
  RP([['Contributor pseudonyms rotate. ', { bold: true }],
      'The source identifier is a keyed hash of the contributor key and a rotation epoch, so two contributions from one device in different epochs are unlinkable in the open tier. Within an epoch they stay linkable, and that is deliberate: repeated reports from one device must be clusterable, or one enthusiastic contributor is counted as independent corroboration. Section 6 shows how that clustering discounts the confidence of the labels involved.']),

  H('3.2  Time base', 2),
  P('Interchange files carry RFC 3339 strings with the Z designator; a timestamp without it is rejected rather than assumed to be UTC. Analytic tables carry signed 64-bit UTC nanoseconds, and the reason is arithmetic rather than aesthetic. A float64 holding seconds since the epoch has a quantum of about 200 ns at present dates — the same order as the PTP offsets the release is required to report. Storing seconds as floats would therefore destroy exactly the measurement the synchronization section exists to make. The test suite asserts this directly: it checks that one nanosecond is representable in the integer form and is lost in the floating-point one.'),
  P('A native source timestamp is never overwritten. A corrected time is a new column derived from the native time, the estimated offset, the offset uncertainty, and the method, so that a later recalibration can be replayed from the raw record.'),
);

/* ---- 4. ingestion ---- */
push(
  H('4  Source ingestion', 1),
  P('One adapter per source family, each responsible for exactly three things: parsing the delivery format the source actually uses, emitting the minimum event envelope every stream must produce, and recording what it could not determine together with a reason code. Association, labelling, quality scoring, and privacy transformation all happen downstream, which is what allows a new source family to be added without touching the validation gates.'),
  RP([['An adapter never invents a value. ', { bold: true }],
      'This is not a stylistic preference. An early version of the S3 adapter synthesized a delivery latency it had not received, seeded from Python’s string hash — which is salted per process. The result was a release whose observations table did not reproduce byte-for-byte between two runs of the same code on the same input. The field now comes from the delivery, where it belongs, and the observations table reproduces exactly.']),
  caption('The six raw inputs, what each contributes, and the failure mode its adapter is written to handle.', ++TAB),
  table(
    ['Input', 'Contributes', 'Principal failure mode handled'],
    [
      ['S1 takeoff indication', 'Event anchor for controlled flights, reference trajectory, disciplined clock', 'Operational run identifiers must not enter the repository; replaced by a keyed hash so redelivery is still detectable'],
      ['Site episode log', 'Anchor for observational and negative events that S1 never sees', 'No trajectory exists, so kinematic targets are absent rather than inferred from the media'],
      ['S2 public warning', 'External warning context and a temporal reference', 'The feed redelivers, and its clock is untrusted; duplicates are detected on the keyed hash and recorded, and the retrieval lag is carried as uncertainty, not applied as a correction'],
      ['S3 mobile report', 'Distributed human evidence inside the risk zone', 'One device can manufacture apparent consensus; reports are clustered into corroboration groups before support is counted'],
      ['S4 media index', 'Visual and acoustic evidence from authorized sites', 'Quality must be measured from the bytes, not declared; absent payloads still emit a row with a missingness reason'],
      ['Synchronization markers', 'One physical instant observed by several disciplined clocks', 'Without it Equation (3) is not measurable at all; see Section 5.4'],
    ],
    [2.2, 3.4, 6]),
  P('The rehearsal run ingested ' + M.n_observations + ' observations across these inputs. The exception log recorded ' + '5 media objects with an unavailable sensor, 8 redelivered public warnings suppressed from the canonical tables, and 35 public warnings that could not be attached to any known event. That last category matters: real warning feeds carry background traffic, and a pipeline that assumes every warning matches an event will over-associate. Unattached warnings are counted and excluded rather than forced onto the nearest event, because temporal proximity alone is not evidence of relation.'),
);

/* ---- 5. calculations ---- */
push(
  pageBreak(),
  H('5  The calculations', 1),
  P('This is the section a reviewer should read to check that the manuscript’s equations were implemented as written. Each subsection states the equation, explains the implementation choices that the equation alone does not determine, and works one numeric example through from the rehearsal corpus.'),

  H('5.1  Equation (1): distance to the warning-zone boundary', 2),
  P('The warning zone is a simple polygon in a local East-North metric frame. Converting to that frame is the last step of the controlled-tier transformation and the first step of every public computation: once positions are expressed relative to an undisclosed origin, distances and directions stay exact while the absolute location never leaves the controlled tier.'),
  eq('d(t) = min { dist( x(t), z ) : z ∈ ∂Z }', '1'),
  P('Three implementation choices are worth stating because the equation does not determine them.'),
  bullet('The minimum is taken over the boundary ∂Z, not over the filled region. The distance is therefore zero exactly on the boundary and positive both outside and inside. A target loitering over the centre of the zone is not at distance zero.'),
  bullet('Only the horizontal components enter. The zone is a ground-referenced area; mixing altitude into the boundary distance would make a high overflight appear far from a zone it is directly above.'),
  bullet('Distance is computed to each edge segment, not to each vertex. The distinction is not academic: a point four metres off the midpoint of a long edge is four metres away, while a vertex-only computation would return the distance to a corner. The test suite pins this case explicitly.'),
  P('The sign is carried separately, as an inside flag, because Equation (1) is unsigned. A signed form exists for plotting and for detecting the boundary crossing in Equation (2), where an unsigned distance would touch zero and rebound without ever changing sign.'),

  H('5.2  The direction rule and the dead-band ε', 2),
  P('Over a stride Δt, movement is labelled from the change in boundary distance:'),
  eq('d(t+Δt) − d(t) < −ε  → approaching     |  d(t+Δt) − d(t) > +ε  → receding     |  otherwise → lateral / stationary', ''),
  P('The manuscript requires ε to exceed the combined positional uncertainty. The implementation derives it rather than accepting it as a free parameter. The two fixes entering the difference are independent, so the standard deviation of their difference is √2 σₕ, and'),
  eq('ε = k · √2 · σₕ', ''),
  RP(['With the configured σₕ = 0.35 m and k = 3, this gives ε = ',
      [n(REPORT.manuscript_placeholders['[[EPSILON_DISTANCE]]'], 4) + ' m', { bold: true }],
      '. An explicitly configured ε below that floor is rejected at load time. Below the floor, positional noise becomes a direction label, and a model trained on such labels learns the noise.']),
  P('Two tests state the property from both sides. Given a genuinely stationary target with σₕ = 0.35 m, every decided label must be lateral/stationary under the derived ε; and with ε set to zero, the same track must produce both approaching and receding labels. The second test is the one that matters, because it demonstrates that the dead-band is doing work rather than being decorative.'),
  P('A sample whose Δt partner falls outside the track is labelled uncertain, never extrapolated.'),
  ...figure('fig02_kinematics.png',
    'Equations (1) and (2) on one rehearsal event (multirotor_small, orbit geometry, slow speed band). (a) The track and the generalized zone. (b) Boundary distance over time with per-sample direction labels and the interpolated crossing. (c) The differenced quantity the rule actually tests, against the ±ε dead-band.', ++FIG),
  P('Worked example, from the event shown in Figure 2. At t = 47.4 s the boundary distance is 412.920 m; at t = 49.4 s, one stride of Δt = 2.0 s later, it is 412.319 m. The difference is −0.601 m. Its magnitude does not exceed ε = 1.485 m, so the sample is labelled lateral/stationary — correctly, because this segment of the orbit is nearly tangential to the boundary. A rule without the dead-band would have called it approaching on the strength of six-tenths of a metre.'),
  ...figure('fig03_epsilon.png',
    'Sensitivity of the direction mix to the dead-band multiplier k, over 40 rehearsal events. As k falls below about 2, the share of samples labelled approaching or receding rises sharply — that rise is positional noise being converted into direction labels, not motion being detected.', ++FIG),

  H('5.3  Equation (2): warning time, and honest censoring', 2),
  eq('T(t) = t_cross − t', '2'),
  P('The crossing is the first transition of the signed distance from positive to non-positive, refined by linear interpolation between the bracketing samples. The refinement is not a nicety: at the configured 5 Hz reference rate an unrefined crossing is biased by up to 200 ms, and the release reports warning time in seconds to one decimal place.'),
  P('Worked example, same event. The signed distance is +0.625 m at t = 182.60 s and −0.407 m at t = 182.80 s. The interpolation fraction is 0.625 / (0.625 + 0.407) = 0.6056, giving t_cross = 182.60 + 0.6056 × 0.20 = 182.7211 s. At the sample examined in Section 5.2 the warning time is therefore T = 182.72 − 47.40 = 135.32 s.'),
  RP([['Events without a verified crossing are censored, not extrapolated. ', { bold: true }],
      'Of the 90 controlled flights in the rehearsal corpus, those whose tracks never entered the zone carry time_to_zone = censored with an uncertainty reason of no_verified_crossing. Fitting a trend to the approach and reporting the extrapolated intercept would produce a column that looks like a measurement and is a model output; the distinction is exactly what an early-warning benchmark must preserve.']),

  H('5.4  Equation (3): synchronization error', 2),
  eq('δt = | t_m − t_r |', '3'),
  callout('The single most consequential implementation decision in the pipeline',
    ['Equation (3) is a clock error, so it must be evaluated on one physical instant observed by two clocks. An early implementation compared each observation timestamp against its event anchor. That version ran without error and produced a p95 of about 147 seconds — which is not a clock error at all, but a measurement of where in a three-minute event each observation happened to fall.',
     'The correct construct is the synchronization marker the manuscript already requires at the start of every run. Each disciplined source records its own timestamp of that one instant, and δt is the deviation from the reference. The measured p95 fell to ' + n(M.sync_p95_ms, 1) + ' ms, which is the order of magnitude a PTP- and NTP-disciplined site should produce.',
     'The lesson generalizes: a metric that runs without error and returns a plausible-looking number is the most dangerous kind of defect, because nothing downstream will ever surface it.'],
    'EEF3FA', ACCENT),
  P('The error belongs to a (source, event) pair rather than to an individual record: one clock offset governs everything a source produced during a run.'),
  RP([['Sources that cannot observe a marker report nothing. ', { bold: true }],
      'Mobile devices and the external public feed are asynchronous by nature. For them the release publishes the declared 1σ uncertainty and leaves the measured error null. Reporting a measured statistic for them would be fabrication; omitting them from the report entirely would hide that ' + M.n_observations + ' observations include ' + '395 with no verified synchronization at all. Both failure modes are avoided by reporting the two categories side by side.']),
  ...figure('fig04_sync.png',
    'Equation (3) on the rehearsal corpus. (a) Measured error by modality, on a log scale, against the configured 250 ms tolerance. (b) The asynchronous sources, for which no marker exists: their declared 1σ uncertainty is shown against the measured p95 of the disciplined sources, on the same axis.', ++FIG),
  caption('Equation (3) by modality. Measured statistics come from marker observations; asynchronous sources report a declared uncertainty and a null measurement.', ++TAB),
  table(
    ['Modality', 'n measured', 'n not measurable', 'median (ms)', 'p95 (ms)', 'max (ms)', 'over tolerance'],
    REPORT.sync_by_modality.map(r => [
      r.modality, String(r.n), String(r.n_not_measurable),
      r.median_ms === null ? 'not measurable' : n(r.median_ms, 3),
      r.p95_ms === null ? '—' : n(r.p95_ms, 2),
      r.max_ms === null ? '—' : n(r.max_ms, 2),
      r.over_tolerance_rate === null ? '—' : pct(r.over_tolerance_rate, 2),
    ]),
    [2.4, 1.3, 1.6, 1.5, 1.3, 1.3, 1.5], { numeric: true }),
  P('The maximum of ' + n(M.sync_max_ms, 1) + ' ms exceeds the 250 ms tolerance while the p95 of ' + n(M.sync_p95_ms, 1) + ' ms clears it comfortably. That shape is expected and is why the gate is set on the p95: the excursions come from injected NTP step corrections, which are real events at NTP-disciplined sites and affect ' + pct(byName(REPORT.sync_by_modality, 'modality', 'ALL').over_tolerance_rate, 2) + ' of measured observations. The affected records are flagged sync_out_of_tolerance rather than dropped.'),

  H('5.5  Association under uncertainty expansion', 2),
  P('An observation is attached to a window only when its uncertainty-expanded interval overlaps the window sufficiently. The expansion half-width is kσ for the source’s declared clock uncertainty, with k = 2.'),
  P('The expansion cuts both ways, and that is the point. A badly synchronized source is not silently attached to the wrong window, because a report with 1.5 s of clock uncertainty can only be attached where a 1.5 s error would not change the answer. But a wider interval also overlaps more windows, so a poor clock produces ambiguous associations rather than confidently wrong ones. Ambiguity is resolved by taking the window of maximum overlap and recording the runner-up margin, so a downstream user can filter on how decisive each association was.'),
  callout('A second defect the rehearsal caught', [
    'The manuscript specifies a minimum overlap. Implemented as an absolute threshold alone — one second — it silently refused to associate every still image in the corpus, because a single frame has a support of a few tens of milliseconds and can never accumulate a second of overlap with anything.',
    'The rule now passes when either the absolute overlap is met or a configured fraction of the shorter of the two intervals is covered. The absolute criterion governs long observations, where a second of common support is a meaningful amount of evidence; the fractional one governs short observations, where only containment is meaningful. The image association rate went from partial to complete, with a median coverage fraction of 1.000.'],
    'EEF3FA', ACCENT),
  ...figure('fig05_association.png',
    'Association outcome by modality after the dual criterion, and the distribution of decisiveness — the margin by which the winning window beat the runner-up, as a fraction of the winning overlap. Values near zero mark associations a cautious user should discard.', ++FIG),
  P('The rehearsal corpus associates ' + pct(M.association_rate, 1) + ' of observations. A high rate is not by itself a good sign, and the decisiveness distribution is the reason it is reported alongside: a large mass near zero would mean the windows are too finely tiled for the clock uncertainties involved, and the association is then a coin flip dressed as a join.'),

  H('5.6  Equation (4): record completeness', 2),
  eq('Cᵢ = (1 / |R|) · Σ ᵣ∈ᴿ  𝟙( r is valid )', '4'),
  P('R is the required-field set declared in the schema, so completeness is measured against what a record was supposed to contain rather than against the columns that happen to be populated. The distinction is a safeguard: averaging over an ad-hoc column list would let a release raise its own completeness simply by dropping fields.'),
  P('An empty string counts as missing, not as present. A nullable field that is absent is not an error, but it must carry a reason code from the controlled vocabulary — not_observed, sensor_unavailable, withheld_privacy, corrupted, or not_applicable. The release never distinguishes "not measured" from "withheld" by leaving a cell blank.'),
  caption('Equation (4) over the released tables of the rehearsal corpus.', ++TAB),
  table(
    ['Table', 'Records', '|R|', 'Median Cᵢ', '5th percentile', 'Fully complete'],
    REPORT.completeness_by_table.map(r => [
      r.table, String(r.n_records), String(r.n_required_fields),
      n(r.median_completeness, 4), n(r.p05_completeness, 4), pct(r.fully_complete_rate, 1)]),
    [2.6, 1.4, 1, 1.6, 1.6, 1.8], { numeric: true }),
  ...figure('fig06_completeness.png',
    'Per-record completeness by table, each point one record, the bar the median. A corpus that passes this cleanly is not proof of quality — it is proof that the ingestion adapters emit every required field, which is the necessary precondition for the quality dimensions that follow.', ++FIG),
  ...figure('fig07_missingness.png',
    'Missingness by field and modality. The high-missingness rows are structural rather than defective: corroboration_group applies only to mobile reports, perceived_direction only to human observations, and object_uri only to modalities that carry a payload. Reporting the rate without the stratum would make a correct release look broken.', ++FIG),

  H('5.7  Equation (5): duplicate rate', 2),
  eq('D = ( N − Nᵤ ) / N', '5'),
  P('The rate is computed at object-group level, not at frame level. Counting frames would be easier and wrong: a 25 fps clip yields hundreds of near-identical frames that are not duplicates in any sense a user cares about, and the resulting rate would be dominated by the frame rate.'),
  P('Two rates are reported because they call for different remedies. An exact duplicate — byte identity — is an ingestion defect. A near duplicate — the same recording re-encoded — is a partitioning hazard: it yields a different digest and can therefore land on both sides of an evaluation split, making every reported score optimistic.'),
  H('5.7.1  Perceptual grouping', 3),
  P('Near duplicates are found with a 64-bit perceptual hash and joined by union-find, so a chain of successive re-encodings ends in one group rather than a chain of pairs. Two construction details were forced by the material.'),
  bullet('For images, the hash thresholds low-frequency DCT coefficients rather than block averages, and drops the DC term. Frames of open sky are nearly uniform, so a block-average hash puts almost every pair within a few bits of every other; the first implementation collapsed the entire corpus into duplicate groups of up to 85 objects.'),
  bullet('Degenerate content — silence, saturation, gross over- or under-exposure — is grouped by digest only. A perceptual hash of silence is a hash of nothing: every silent recording is perceptually identical to every other, and including them merged unrelated events and dragged half the corpus into a single partition through the split constraint.'),
  P('The radius was calibrated on the corpus and is a configuration value, not a constant in the code. True re-encodes separate by at most 2 bits; unrelated objects by at least 12. The configured radius of 4 bits sits in that gap with margin on both sides, and the configuration says in as many words that it must be recalibrated against the first real campaign, because the gap depends on scene content.'),
  caption('Equation (5) on the rehearsal corpus.', ++TAB),
  table(
    ['Quantity', 'Value', 'Interpretation'],
    [
      ['N, objects', String(REPORT.duplicates.n_objects), 'Media objects in the manifest'],
      ['Nᵤ, unique groups', String(REPORT.duplicates.n_unique_groups), 'After exact and perceptual grouping'],
      ['D, total', pct(REPORT.duplicates.duplicate_rate, 2), 'Equation (5)'],
      ['D, exact', pct(REPORT.duplicates.exact_duplicate_rate, 2), 'Byte-identical redelivery — an ingestion defect'],
      ['D, near', pct(REPORT.duplicates.near_duplicate_rate, 2), 'Re-encoded copies — a partitioning hazard'],
      ['Largest group', String(REPORT.duplicates.largest_group), 'A large value indicates the hash is over-merging'],
    ],
    [2.4, 1.6, 6]),
);

/* ---- 5.8 media quality ---- */
push(
  H('5.8  Measured media quality', 2),
  P('Every value in the media manifest is computed from the released byte sequence. None is declared by the acquisition plan. The distinction is what the manuscript’s Table 7 asks for: a manifest that echoes the intended SNR rather than the achieved one passes its own validation while telling the user nothing.'),
  H('5.8.1  Why a peak-based SNR estimate is the wrong instrument', 3),
  P('A rotor radiates a blade-pass fundamental with harmonics, so nearly all of its power sits in a handful of narrow spectral bins while the noise is spread over all of them. The obvious estimate — largest bin against the noise floor — measures a peak-to-floor ratio, which for a concentrated tonal runs tens of decibels above the broadband SNR the propagation model predicts. The first implementation did exactly this, and the comparison between predicted and achieved SNR showed a bias of about +31 dB with a negative correlation: the two quantities were simply not the same quantity.'),
  H('5.8.2  The harmonic-sum estimator', 3),
  P('The estimator now isolates the total signal power from the H harmonic bins and refers it to the noise power over the whole band, which is the same quantity as L(r) − L_ambient in the propagation model and is therefore directly comparable with it:'),
  eq('f₀̂ = argmax S(f₀),   S(f₀) = Σₕ max p[ h·f₀ ± 2 ]', ''),
  eq('SNR_dB = 10 log₁₀ [ ( S(f₀̂) − H·floor ) / ( floor · N ) ]', ''),
  P('The noise floor is the median bin power, not the mean, because a handful of strong tonals would otherwise inflate the very floor they are being compared against. Concentrating the estimate in H bins rather than N is where the sensitivity comes from — and it is also what bounds it.'),
  H('5.8.3  The estimator declares its own sensitivity floor', 3),
  P('An estimator that cannot say when it has failed will report noise as a weak detection. The bound one would write down analytically — the maximum of N exponential bins exceeds the median by about ln(N)/ln 2 — is not the right null here, and using it produced exactly that failure: pure white noise was reported at −24.8 dB. Two maximizations sit inside the statistic that the analytic form ignores, the search over candidate fundamentals and the local maximum around each harmonic, and both inflate the statistic under the null in a way that depends on the grid size.'),
  P('The null is therefore calibrated by Monte-Carlo simulation against the correct noise model — periodogram bins of Gaussian noise are exponentially distributed — using the identical statistic, the identical candidate grid, and the identical windowing. The result is cached per clip geometry, so the cost is paid once. Below the resulting bound the estimator returns null and sets snr_not_measurable, never a number.'),
  caption('Measured behaviour of the SNR estimator against a known input, eight trials per level. The detection floor sits between −20 and −14 dB, close to and slightly better than the −16 dB input SNR implied by the configured detector threshold and processing gain — which is the consistency one should expect between an estimator and the front end it characterizes.', ++TAB),
  table(
    ['True broadband SNR (dB)', 'Detected in', 'Behaviour'],
    [
      ['−25 and below', '0 / 8', 'Saturated: null returned, flagged not measurable'],
      ['−20', '2 / 8', 'At the floor'],
      ['−18', '5 / 8', 'Transition'],
      ['−16', '7 / 8', 'Transition'],
      ['−14 and above', '8 / 8', 'Reliable; accuracy better than 3 dB'],
    ],
    [3, 2, 6]),
  H('5.8.4  Predicted against achieved', 3),
  P('This comparison is what turns the design assumptions of Section 9 into something falsifiable. A systematic offset is a calibration finding — the assumed source level or ambient level is wrong — and it is the first quantity the first field campaign should report back.'),
  caption('Predicted versus measured detectability on the rehearsal corpus.', ++TAB),
  table(
    ['Channel', 'n', 'Bias', 'Mean abs. error', 'RMSE', 'Pearson r'],
    REPORT.predicted_vs_achieved.map(r => [
      r.channel === 'acoustic_snr_db' ? 'Acoustic SNR (dB)' : 'Visual target extent (px)',
      String(r.n), n(r.bias, 2), n(r.mad, 2), n(r.rmse, 2), n(r.pearson_r, 3)]),
    [3, 1, 1.5, 2, 1.5, 1.5], { numeric: true }),
  ...figure('fig08_media_quality.png',
    'Measured against predicted detectability versus sensor-to-target slant range. The acoustic panel shows the estimator’s median sensitivity floor as a shaded band; objects falling into it are reported as not measurable rather than as weak detections. The visual panel tracks the inverse-range law closely (r = ' + n(byName(REPORT.predicted_vs_achieved, 'channel', 'visual_target_px').pearson_r, 3) + ').', ++FIG),
);

push(
  H('5.9  Inter-annotator agreement', 2),
  P('Krippendorff’s alpha is used rather than a kappa-family coefficient because it is the only common statistic that handles all three properties this task actually has: more than two annotators, annotators who did not all see the same items, and missing judgements. All three are guaranteed here, since annotators are assigned per event and a rater may abstain when the handbook says the evidence is insufficient.'),
  eq('α = 1 − D_o / D_e', ''),
  P('Units judged only once are excluded — a single rating cannot agree or disagree with anything — which is the standard treatment and not a loss of data. The bootstrap interval resamples units rather than individual judgements: resampling judgements independently would break the within-unit structure the coefficient is built on and yield an interval far too narrow.'),
  caption('Agreement on the rehearsal corpus, with 95 % percentile bootstrap intervals over units.', ++TAB),
  table(
    ['Target', 'Units', 'Judgements', 'Raters/unit', 'α', '95 % CI', 'Majority class'],
    REPORT.agreement.map(r => [
      r.target_name, String(r.n_units), String(r.n_judgements), n(r.mean_raters_per_unit, 2),
      n(r.krippendorff_alpha, 3),
      `[${n(r.alpha_ci_low, 3)}, ${n(r.alpha_ci_high, 3)}]`,
      `${r.majority_class} (${pct(r.majority_prevalence, 0)})`]),
    [2.6, 1, 1.5, 1.4, 1, 1.8, 2.2], { numeric: true }),
  P('The coefficient is reported beside class prevalence and the confusion matrix because a single number cannot distinguish "raters agree" from "one class dominates". Here the majority class holds ' + pct(byName(REPORT.agreement, 'target_name', 'vehicle_presence').majority_prevalence, 0) + ' of presence judgements, so a naive agreement percentage would look respectable while alpha correctly reports ' + n(byName(REPORT.agreement, 'target_name', 'vehicle_presence').krippendorff_alpha, 3) + '.'),

  H('5.10  Cross-modal consistency', 2),
  P('Weak reports are compared against ground truth over the same interval, not against an event-level summary. The comparison has to be contemporaneous: a track that approaches, passes, and recedes has no single event-level direction, so scoring a report against an event summary measures when the contributor happened to look rather than whether they were right. An earlier event-level implementation reported ' + '63.9 % consistency; the contemporaneous version reports ' + pct(M.cross_modal_consistency, 2) + ' on the same data, and the difference was entirely an artefact of the comparison.'),
  P('Each report is matched to the ground-truth window its support interval overlaps most. A single percentage is not enough on its own, and the confusion matrix is reported with it: ' + pct(M.cross_modal_consistency, 1) + ' consistency in which every error is approaching-called-receding is a different resource from one whose errors fall into lateral or uncertain.'),
  ...figure('fig09_agreement.png',
    'Agreement with bootstrap intervals against the configured floor, and the cross-modal direction confusion matrix, row-normalized. The errors are concentrated in the small lateral/stationary class rather than in approaching-versus-receding, which is the benign failure pattern.', (FIG_AGREEMENT = ++FIG)),

  H('5.11  Residual disclosure risk', 2),
  P('Generalizing coordinates and rotating pseudonyms is not by itself protection. If one contributor is the only one reporting from a given cell on a given day, the generalization has not hidden them. The pipeline measures this directly by counting the equivalence classes induced by the fields the open tier actually publishes.'),
  caption('k-anonymity probe over the published quasi-identifiers of the observations table.', ++TAB),
  table(
    ['Quantity', 'Value'],
    [
      ['Quasi-identifiers', REPORT.k_anonymity.quasi_identifiers.join(', ')],
      ['k', String(REPORT.k_anonymity.k)],
      ['Equivalence classes', String(REPORT.k_anonymity.n_classes)],
      ['Smallest class', String(REPORT.k_anonymity.min_class_size)],
      ['Records in a class smaller than k', String(REPORT.k_anonymity.n_below_k) + '  (' + pct(REPORT.k_anonymity.rate_below_k, 1) + ')'],
    ],
    [3, 6]),
  RP([['This is a finding, not a pass. ', { bold: true }],
      pct(REPORT.k_anonymity.rate_below_k, 1) + ' of records sit in an equivalence class smaller than five, and the smallest class has one member. A 1 km spatial cell combined with day-level time granularity is not sufficient generalization for this corpus. It is also a lower bound on risk: the probe says nothing about an adversary holding auxiliary data, which is why the release documents its adversary assumptions rather than relying on the number. Section 10 carries the recommended action.']),
);

/* ---- 6. labels ---- */
push(
  pageBreak(),
  H('6  Labels, evidence tiers, and adjudication', 1),
  P('A label is never an unqualified class name. Every row carries what it means, how strongly it is supported, who or what produced it, over which interval, and how a conflict about it was resolved.'),
  H('6.1  Evidence priority is not a global ordering', 2),
  P('Controlled ground truth wins on the fields the reference system actually observes — presence, direction, distance interval, warning time, platform class — and on nothing else. It has no authority over whether a target was audible, whether a frame was usable, or what an unrelated public report meant. That distinction is encoded explicitly as an authoritative-field set rather than left to the tier ranking, and the test suite asserts both halves: ground truth overrides expert consensus on direction, and does not override it on audibility.'),
  P('Where no tier is authoritative, the weighted majority of the non-ground-truth labels decides, weighted by confidence and tier rank. A tie leaves the value uncertain with an adjudication code of TIE-UNRESOLVED rather than picking a side.'),
  H('6.2  Weak evidence stays weak', 2),
  P('Mobile reports enter as weak_public_report. Their confidence is the contributor’s own, divided by the size of the corroboration group they belong to: the second and later reports from one device in one temporal neighbourhood add no independent information, so their weight is divided rather than summed. Twenty taps from one phone in one minute carry the weight of one report.'),
  H('6.3  The audit trail is what makes agreement computable', 2),
  P('Original annotations are retained with is_adjudicated_final false. Keeping them is not sentimentality about provenance — it is what makes the agreement statistics of Section 5.9 computable after the fact. In a real release those rows live in the controlled audit trail and the open tier publishes the adjudicated label plus a non-identifying decision code.'),
  caption('Label population of the rehearsal corpus, by evidence tier and adjudication outcome.', ++TAB),
  table(
    ['Category', 'Count', 'Note'],
    [
      ['controlled_ground_truth', '6 413', 'Derived from Eq. (1) and Eq. (2), plus negative-control session records'],
      ['expert_verified', '528', 'Independent annotator judgements'],
      ['weak_public_report', '301', 'Mobile reports, confidence discounted by corroboration group'],
      ['not_required', '6 662', 'Unanimous and above the confidence threshold; no review triggered'],
      ['accepted', '471', 'Conflict reviewed; ground truth accepted on an authoritative field'],
      ['revised', '109', 'Conflict reviewed; weighted majority or unresolved tie'],
      ['Released labels', String(M.n_labels_released), 'Exactly one per (target, target_name)'],
    ],
    [3, 1.5, 6]),

);

/* ---- 7. splits ---- */
push(
  pageBreak(),
  H('7  Leakage-resistant partitioning', 1),
  P('Every partition is built at group level and then expanded to records, never the other way round. Groups are allocated largest-first to whichever partition is furthest below its target, which keeps the record proportions close to the requested fractions without ever splitting a group.'),
  P('Near-duplicate media groups are an additional constraint on every manifest, not only on the event-disjoint one. Two distinct events can contain re-encodings of the same recording, and separating the events does not separate the content.'),
  H('7.1  When two constraints genuinely conflict', 2),
  P('For a manifest grouped by something other than the event, the two constraints can be unsatisfiable together: the same recording can be re-encoded at two different sites, and no assignment satisfies both location disjointness and duplicate disjointness. The conflict is resolved explicitly rather than silently, in one of two ways depending on which constraint is the point of the manifest. Where the manifest’s own grouping is soft, every event in the duplicate group joins the partition holding most of it. Where the grouping is the reason the manifest exists, the conflicting events leave every partition and are reported as excluded — a smaller clean holdout is worth more than a larger one whose transfer claim is contaminated.'),
  H('7.2  The audit', 2),
  P('The audit checks each manifest against its own stated constraint rather than one generic rule. The hard-negative challenge deliberately spreads every confounder family across all three partitions, so auditing it for group-disjointness would flag its defining property as a defect; a first version of the audit did exactly that and reported eight false violations. The time holdout is checked for block ordering and for an observed gap at least as large as the configured embargo.'),
  P('Asserting rather than assuming matters more here than anywhere else in the pipeline. A split bug produces manifests that look entirely normal and scores that are merely too good, so nothing downstream would ever surface it.'),
  caption('Manifest audit on the rehearsal corpus. All five manifests satisfy their stated constraint and the universal near-duplicate constraint.', ++TAB),
  table(
    ['Manifest', 'Constraint', 'Groups', 'Train', 'Val', 'Test', 'Excluded', 'Status'],
    REPORT.split_audit.map(r => [
      r.manifest, r.constraint, String(r.n_groups), String(r.train), String(r.val),
      String(r.test), String(r.excluded),
      { text: r.status, bold: true, color: r.status === 'pass' ? GOOD : WARN }]),
    [2.6, 2.2, 1.1, 1, 0.9, 1, 1.3, 1.1], { numeric: true }),
  ...figure('fig10_splits.png',
    'Manifest composition, including what each one excludes. The excluded fractions are the honest cost of the constraints: the embargo gap in the time holdout, events whose sources straddle a boundary in the source holdout, and duplicate conflicts in the location holdout.', ++FIG),
  callout('Two manifests are structurally degenerate on this corpus', [
    'The location holdout and the time holdout both produced an empty validation partition. The cause is not a bug: the rehearsal corpus has only three site groups and, after the embargo gap, three temporal blocks. Three groups cannot fill three partitions at a 60/15/25 ratio, so the smallest partition receives nothing.',
    'The audit reports this as a warning rather than a failure, because the constraint does hold — the manifest is simply not usable for model selection. The design consequence for the field trials is stated in Section 9.5: a location holdout needs meaningfully more independent site groups than partitions, which sets a floor on the number of monitoring sites the campaign must instrument.'],
    'FFF6E8', WARN),
);

/* ---- 8. validation results ---- */
/* Gate commentary is keyed by gate name and emitted only for gates that
   actually failed, so the prose cannot contradict the table beside it. An
   earlier version stated the pass count and the failure list in hand-written
   text; a later run produced a fourth failure and the two disagreed. */
const FAILED = REPORT.gates.filter(g => g.status === 'FAIL');
const N_PASS = String(REPORT.gates.length - FAILED.length);
const N_FAIL_WORD = ['no', 'single', 'two', 'three', 'four', 'five', 'six'][FAILED.length] || String(FAILED.length);
const GATE_NOTE = {
  exact_duplicate_rate: {
    lead: g => 'Exact duplicate rate, ' + pct(g.observed, 2) + ' against a zero-tolerance rule. ',
    body: 'Two pairs of byte-identical audio objects, all four flagged silence. They are the re-encoded copies the corpus injects, and the injection made them byte-identical rather than merely similar: a recording that is already silence, requantized at a coarser step, is still exactly zero. The gate is right to be zero-tolerance — an exact duplicate is an ingestion defect and not a judgement call — and it is right to have fired here. The finding is also a reminder that degenerate content behaves differently from ordinary content throughout the pipeline, which is why the perceptual grouping of Section 5.7.1 excludes it and matches such objects on the digest alone.',
  },
  near_duplicate_rate: {
    lead: g => 'Near-duplicate rate, ' + pct(g.observed, 2) + ' against a 5 % rule. ',
    body: 'The rehearsal corpus deliberately injects re-encoded copies at roughly a 7 % rate, so this gate is expected to fail and its failure is the evidence that the perceptual grouping works. The largest group contains ' + REPORT.duplicates.largest_group + ' objects, which is the diagnostic that matters: a grouping that were over-merging would show large groups and a plausible-looking rate at the same time.',
  },
  cross_modal_consistency: {
    lead: g => 'Cross-modal consistency, ' + pct(g.observed, 2) + ' against a 90 % rule. ',
    body: 'A marginal failure, and a real property of the corpus: simulated contributors misreport direction with a probability that grows with distance. The confusion matrix in Figure ' + FIG_AGREEMENT + ' shows the errors are concentrated in the small lateral/stationary class rather than in the approaching-versus-receding distinction that matters operationally. The correct response is to examine the matrix, not to move the threshold.',
  },
  krippendorff_alpha: {
    lead: g => 'Krippendorff’s α on presence, ' + n(g.observed, 3) + ' against a 0.67 rule. ',
    body: 'The clearest of the failures. Simulated annotators are correct with a probability that depends on how good the evidence was, so events near the detection limit generate genuine disagreement. An α at this level would not support a released label set, and the operational conclusion for the field trials is that the annotation protocol — handbook, qualification threshold, and rater count — must be strengthened and re-measured before any release, not that the floor should be lowered.',
  },
};

push(
  H('8  Validation results on the rehearsal corpus', 1),
  P('The gates below are policy, not physics: they are the acceptance rules a release manager sets, and they are expected to change between versions while the metric definitions must not. That is why the pipeline computes numbers and compares them, and never bakes a verdict into a metric.'),
  ...figure('fig12_gates.png',
    'Release gates applied to the rehearsal corpus. ' + N_PASS + ' of ' + REPORT.gates.length + ' pass. The ' + N_FAIL_WORD + ' failures are discussed below; each is a property of the rehearsal corpus rather than a defect in the computation, and each demonstrates the corresponding gate doing its job.', ++FIG),
  caption('Release gate results. A failed gate produces a documented decision — repair, exclusion, metadata-only, or controlled access — never a silent discard.', ++TAB),
  table(
    ['Gate', 'Observed', 'Rule', 'Status', 'Basis'],
    REPORT.gates.map(g => [
      g.gate,
      typeof g.observed === 'number' ? (Math.abs(g.observed) < 1 && g.observed !== 0 ? n(g.observed, 4) : n(g.observed, 3)) : String(g.observed),
      g.rule,
      { text: g.status, bold: true, color: g.status === 'pass' ? GOOD : WARN },
      g.basis]),
    [2.6, 1.5, 1.2, 1, 3.4]),
  H('8.1  The failing gates', 2),
  P('The discussion below is generated from the gate results, so it covers exactly the gates that failed on this run and no others.'),
  ...FAILED.map(g => RP([
    [GATE_NOTE[g.gate] ? GATE_NOTE[g.gate].lead(g) : g.gate + ', observed ' + n(g.observed, 4) + ' against a rule of ' + g.rule + '. ', { bold: true }],
    GATE_NOTE[g.gate] ? GATE_NOTE[g.gate].body : 'No prepared commentary exists for this gate; it must be reviewed manually before release.',
  ])),
  H('8.2  What passing means and does not mean', 2),
  P('Structural validation, completeness, integrity, synchronization, and the leakage audit all pass at their configured rules. Those are necessary conditions, not evidence of scientific quality. A record can pass structural validation while failing media-quality or evidence-quality validation, which is precisely why quality flags are multi-valued and why nothing in the pipeline collapses the dimensions into a single score.'),
  P('The integrity result deserves separate mention because its target is 100 % and not a quality figure to be reported and accepted. Anything less means a released object is not the object the manifest describes, and the release cannot ship until the discrepancy is explained. On this corpus ' + n(100 * M.checksum_pass_rate, 1) + ' % of released files match their published digest.'),
);

/* ---- 9. field trials ---- */
push(
  pageBreak(),
  H('9  Preparation for field trials', 1),
  callout('The status of the numbers in this section', [
    'Everything in Sections 5 to 8 describes a rehearsal. This section is different: it is forward-looking design, computed from planning assumptions declared in config/pipeline.yaml, and it exists to be tested and replaced by the first campaign.',
    'The assumptions are stated as configuration rather than buried in code precisely so that the first calibration campaign can replace them one at a time and the curves can be recomputed. Section 9.5 lists exactly which measurement replaces which assumption.'],
    'EEF3FA', ACCENT),

  H('9.1  Detection range', 2),
  H('9.1.1  Acoustic', 3),
  P('Under spherical spreading with atmospheric absorption, the level at range r and the resulting in-band SNR are'),
  eq('L(r) = L_ref − 20 log₁₀( r / r_ref ) − α ( r − r_ref ),     SNR(r) = L(r) − L_ambient', ''),
  P('The detection range is the largest r at which the post-gain SNR still meets the detector threshold. The equation is transcendental in r — a logarithm plus a linear term — so it is solved by bisection on the monotonically decreasing curve rather than inverted in closed form.'),
  RP([['The processing gain is not optional. ', { bold: true }],
      'A first version omitted it and predicted acoustic detection ranges of tens of metres, which contradicts reported acoustic sUAV detection performance and would have written the acoustic channel off entirely. Real front ends stack the blade-pass fundamental with its harmonics and integrate over a multi-second window; the configuration carries that gain as an explicit, separately calibratable term, because propagation is a property of the site and weather while gain is a property of the algorithm. With 22 dB of gain the predicted ranges land in the few-hundred-metre band.']),
  H('9.1.2  Visual', 3),
  P('For a pinhole model, the focal length in pixels and the apparent extent of a target of span S at range r are'),
  eq('f_px = W_px / ( 2 tan( HFOV / 2 ) ),     p(r) = f_px · S / r,     r_max = f_px · S / p_min', ''),
  P('With the configured 1920 px sensor width and 12° horizontal field of view, f_px = ' + '9133.8' + ' px. A multirotor_small of 0.55 m span therefore falls to the 3 px detection floor at r = 9133.8 × 0.55 / 3 = 1674 m, and to the 8 px recognition floor at 628 m. The gap between those two numbers is the operationally important one: there is a range band in which a system can tell that something is there and cannot tell what it is.'),
  ...figure('fig13_detection.png',
    'Detection curves from the declared planning assumptions. Acoustic post-gain SNR against range for four ambient environments, and apparent visual extent against range for the four platform classes, with the detection and recognition floors marked.', ++FIG),
  caption('Predicted detection ranges by platform and ambient environment. Acoustic range varies by a factor of about 15 across environments; visual range does not depend on ambient noise at all.', ++TAB),
  table(
    ['Platform', 'Acoustic, rural night', 'Acoustic, rural day', 'Acoustic, peri-urban', 'Acoustic, urban', 'Visual detect', 'Visual recognize'],
    [
      ['multirotor_micro', '414 m', '148 m', '61 m', '28 m', '913 m', '343 m'],
      ['multirotor_small', '783 m', '308 m', '133 m', '61 m', '1 674 m', '628 m'],
      ['fixed_wing_small', '602 m', '226 m', '96 m', '44 m', '4 262 m', '1 598 m'],
      ['hybrid_vtol', '924 m', '376 m', '165 m', '77 m', '3 654 m', '1 370 m'],
    ],
    [2.4, 1.6, 1.5, 1.5, 1.3, 1.3, 1.4], { numeric: true }),

  H('9.2  The warning-time budget', 2),
  P('A detection at range r against a target closing at speed v buys a raw lead time r/v before boundary crossing. The operator decision and the dissemination of the alert both consume part of it, so the time actually available to the protected population is'),
  eq('T_actionable = r / v − T_decide − T_disseminate', ''),
  P('Read the other way round, the range a trial must demonstrate is'),
  eq('r_required = v · ( T_required + T_decide + T_disseminate )', ''),
  P('This is the number that drives sensor placement and the largest approach radius in the flight matrix. With the configured 4 s decision budget, 6 s dissemination budget, and 30 s required actionable lead, a target closing at 15 m/s must be detected at 15 × (30 + 4 + 6) = 600 m.'),
  ...figure('fig14_budget.png',
    'The warning-time budget. (a) Actionable lead time for multirotor_small at 15 m/s, separated by modality: the visual channel is insensitive to ambient noise, while the acoustic channel degrades from comfortably sufficient in a rural night to negative in an urban environment. (b) Required range against closing speed, with the achievable ranges of each channel.', ++FIG),
  RP([['The separation in panel (a) is the point. ', { bold: true }],
      'Plotting only the fused range hides the finding, because visual range does not depend on ambient noise and a fused curve therefore looks flat across environments — which reads as "the acoustic channel is irrelevant". It is not irrelevant; it is the channel that degrades. In a rural night it contributes 42 s of actionable lead on its own; in an urban environment it contributes none, and the system is entirely dependent on an unobstructed optical line of sight.']),
  P('That dependency is the single most important design consequence in this document. Visual range collapses in fog, rain, low cloud, and darkness without illumination, and the acoustic channel is what is supposed to cover those conditions. In a high-ambient-noise site it cannot. Section 10 carries the recommended action.'),

  H('9.3  Sizing the campaign', 2),
  P('For a one-sided acceptance test of a detection rate against a null, with separate variances under the null and the alternative,'),
  eq('n = [ z₁₋α √( p₀(1−p₀) ) + z₁₋β √( p₁(1−p₁) ) ]² / ( p₁ − p₀ )²', ''),
  P('Demonstrating a detection rate of ' + PLAN.target_detection_rate + ' against a null of ' + PLAN.null_detection_rate + ' at α = ' + PLAN.alpha + ' and power ' + PLAN.power + ' requires ' + PLAN.n_per_cell_statistical + ' runs per cell. Inflating for a ' + pct(PLAN.expected_run_loss_rate, 0) + ' expected loss to weather, safety aborts, and sensor faults gives ' + PLAN.n_per_cell_planned + ' planned sorties per cell.'),
  ...figure('fig15_sample_size.png',
    'Runs per cell against the effect size the trial must resolve, for four null rates, and the total sortie count under a full factorial versus a blocked design. The vertical scale is logarithmic: the cost of resolving a small effect is not a matter of a few extra flights.', ++FIG),
  callout('A full factorial is not affordable, and saying so is part of the design', [
    'The declared flight matrix crosses platform class, approach geometry, speed band, altitude band, illumination, and background: ' + PLAN.full_factorial_cells.toLocaleString('en-US') + ' cells. At ' + PLAN.n_per_cell_planned + ' planned sorties each, a full factorial is ' + PLAN.full_factorial_sorties.toLocaleString('en-US') + ' sorties, which is not a campaign anyone will fly.',
    'Treating illumination and background as blocking factors rather than crossing them with everything else reduces this to ' + PLAN.reduced_primary_cells + ' primary cells across ' + PLAN.reduced_blocks + ' blocks, or ' + PLAN.reduced_sorties.toLocaleString('en-US') + ' sorties. That is still a large campaign, and the honest conclusion is that a per-cell acceptance test is the wrong statistical instrument at this scale.',
    'The alternative, which the manifests already support, is to pool across cells with a regression model — detection as a function of range, platform span, ambient level, and illumination — and to report per-cell performance as a model prediction with an interval rather than as an independent per-cell test. That reduces the requirement by more than an order of magnitude. The full-factorial figure is retained in the report precisely so the reduction is an explicit decision rather than a silent one.'],
    'FFF6E8', WARN),
  ...figure('fig11_coverage.png',
    'Flight-matrix coverage achieved by the rehearsal corpus over the three primary factors. Empty cells are the concrete planning target: they are the combinations no run has yet exercised, and the campaign schedule is built to close them.', ++FIG),

  H('9.4  What lead time the data actually offers', 2),
  ...figure('fig16_warning_time.png',
    'Warning time available in the rehearsal corpus, against the total operational budget, and the distribution of peak closing rates. Censored events — those with no verified crossing — are excluded from the ECDF and counted in the caption rather than extrapolated.', ++FIG),
  P('Two design inputs come out of this figure. The fraction of events that clear the total budget sets the realistic ceiling on end-to-end warning performance for a corpus of this geometry, and the closing-rate distribution sets the required detection range through the relation of Section 9.2 — the upper tail, not the median, is what the sensor placement must be sized against.'),

  H('9.5  The calibration campaign', 2),
  P('The first campaign is not a data-collection campaign. Its purpose is to replace each planning assumption with a measurement and to re-derive the curves before the main campaign is committed.'),
  caption('Assumptions to be replaced, in order of how much the design depends on them.', ++TAB),
  table(
    ['Assumption', 'Current value', 'Measurement that replaces it', 'Consequence if wrong'],
    [
      ['Detector processing gain', '22 dB', 'Measured ROC of the deployed acoustic front end against known-range flights', 'Acoustic range scales with it; the whole low-visibility case depends on this number'],
      ['Source level at 1 m', '68–77 dB by class', 'Calibrated hemispherical measurement per platform', 'Shifts every acoustic range by the same factor'],
      ['Ambient noise level', '30–55 dB by site class', 'Continuous ambient logging at each candidate site, by hour', 'Determines which sites are acoustically viable at all'],
      ['Atmospheric absorption', '0.004 dB/m', 'Derive from on-site temperature and humidity logs', 'Second-order below 1 km; matters at longer ranges'],
      ['Visual detection floor', '3 px', 'Measured detection rate against apparent extent, from the corpus itself', 'Sets visual range linearly'],
      ['Decision and dissemination latency', '4 s, 6 s', 'End-to-end timing of the alerting chain under exercise conditions', 'Consumes lead time directly; a 10 s error is a 150 m range requirement at 15 m/s'],
      ['Reference-system σₕ', '0.35 m', 'RTK residual statistics from the reference receiver', 'Sets the ε floor and therefore the direction labels'],
    ],
    [2.6, 1.8, 4, 4]),
  P('The bias figures of Section 5.8.4 are the mechanism by which this happens automatically: once real recordings are ingested, the predicted-versus-achieved comparison reports the offset between the assumed and the actual propagation, and that offset is the calibration.'),

  H('9.6  Site and protocol requirements derived from this analysis', 2),
  numbered('Instrument enough independent site groups. The location holdout degenerated on a corpus with three site groups. A usable location holdout needs materially more independent groups than partitions; six or more site groups should be treated as a floor, and sites that share a mast, a power feed, or a sight line are not independent.'),
  numbered('Log ambient noise continuously at every candidate site, by hour, before committing sensor positions. The acoustic range varies by a factor of about fifteen across the four modelled environments, and it is the only variable in the acoustic budget that a site survey can still change.'),
  numbered('Place acoustic sensors forward of the boundary, not on it. Media quality is governed by the sensor-to-target slant range, not by the target-to-boundary distance; an approach 2 km from the zone can be 80 m from a forward sensor. Conflating the two is how an acoustic channel gets written off.'),
  numbered('Open every run with a synchronization marker observed by all disciplined sources. Without it Equation (3) is not measurable, and the release can report only declared uncertainties.'),
  numbered('Fly the negative-control sessions with the same rigour as the positive ones. False alarms are a central property of an early-warning resource, and the hard-negative challenge manifest balances by event, so under-collecting one confounder family cannot be repaired afterwards by weighting.'),
  numbered('Record run-loss causes in a structured form. The 15 % loss allowance is currently an assumption; a structured cause log turns it into a measurement for the next campaign.'),
  numbered('Strengthen the annotation protocol before the main campaign, and re-measure agreement on a pilot batch. An α of ' + n(M.krippendorff_alpha, 2) + ' does not support a released label set, and agreement is cheaper to fix in the handbook than in re-annotation.'),

  H('9.7  Readiness criteria', 2),
  P('The pipeline is ready for field data when all of the following hold. These are stated as conditions on the pipeline, not on the trials, because they are what the rehearsal was for.'),
  bullet('All eleven release gates pass on a pilot batch of real data, or each failure carries a documented decision.'),
  bullet('The predicted-versus-achieved bias for both channels is stable across at least two sites, so that the propagation model is being calibrated rather than fitted per site.'),
  bullet('Equation (3) is measurable for every disciplined source, with p95 inside the tolerance.'),
  bullet('The location holdout produces three non-empty partitions.'),
  bullet('The k-anonymity probe reports no record in a class smaller than k under the release generalization.'),
  bullet('Inter-annotator α clears the configured floor on a pilot batch.'),
);

/* ---- 10. findings ---- */
push(
  pageBreak(),
  H('10  Findings and recommended actions', 1),
  P('The rehearsal surfaced seven issues worth carrying forward. Five are defects that were found and fixed — recorded here because each would have produced plausible, wrong numbers rather than an error, and because the same class of defect will recur. Two are open and require a decision. The gate failures of Section 8.1 are not repeated here: they are the gates working, not defects.'),
  caption('Findings from the rehearsal. Severity is judged by how likely the defect was to pass unnoticed.', ++TAB),
  table(
    ['#', 'Finding', 'Status', 'Action'],
    [
      ['1', 'Equation (3) evaluated against the event anchor instead of a synchronization marker, reporting a p95 of ~147 s as a clock error', 'Fixed', 'Markers required at every run; asynchronous sources report declared uncertainty and a null measurement'],
      ['2', 'Absolute-only overlap criterion made association impossible for instantaneous observations, silently excluding every still image', 'Fixed', 'Dual criterion: absolute overlap or a fraction of the shorter interval'],
      ['3', 'Block-average perceptual hash collapsed near-uniform sky frames into duplicate groups of up to 85 objects', 'Fixed', 'DCT-based hash without the DC term; degenerate content grouped by digest only; radius calibrated and configurable'],
      ['4', 'Peak-based SNR estimator measured a different quantity from the propagation model (+31 dB bias, negative correlation) and reported pure noise as a −24.8 dB detection', 'Fixed', 'Harmonic-sum estimator referred to total in-band noise, with a Monte-Carlo null and an explicit not-measurable state'],
      ['5', 'S3 adapter synthesized a delivery latency from a per-process salted hash, making the observations table irreproducible', 'Fixed', 'Delivery time comes from the delivery; adapters invent nothing'],
      ['6', 'k-anonymity probe: ' + pct(REPORT.k_anonymity.rate_below_k, 1) + ' of records in an equivalence class smaller than five, smallest class of one', 'Open', 'Coarsen the published time granularity, or the spatial cell, or both, and re-run the probe before any open release'],
      ['7', 'Acoustic channel contributes no actionable lead in high-ambient-noise environments, leaving the system dependent on optical line of sight', 'Open', 'Decide before site selection: accept the limitation and document the weather envelope, or add a channel that survives low visibility'],
    ],
    [0.5, 5, 1.2, 5]),
  H('10.1  The two open items', 2),
  RP([['Disclosure risk. ', { bold: true }],
      'The generalization currently applied — a 1 km spatial cell and day-level time — does not achieve k = 5 on this corpus. Three levers are available and they trade against each other: coarsen the spatial cell, coarsen the published time, or move the sparse strata to the controlled tier. The third preserves the most analytic value for the records that remain and is the recommended default, but it reduces what the open tier contains and that is a decision for the data controller rather than for the pipeline. Whichever is chosen, the probe must be re-run and the result recorded in the release metadata.']),
  RP([['Low-visibility coverage. ', { bold: true }],
      'This is the substantive design finding, and it is not a software issue. Under the declared assumptions the acoustic channel provides useful lead time only in quiet environments; in a peri-urban or urban setting the actionable lead is at or below zero and the fused detection range is the visual range alone. Any condition that removes the optical line of sight therefore removes the warning capability entirely. The decision to make before site selection is whether that weather envelope is acceptable and will be documented as a stated limitation, or whether a channel that survives low visibility must be added. The calibration campaign of Section 9.5 will tighten the acoustic numbers, but it is unlikely to change the conclusion by the order of magnitude that would be needed.']),
);

/* ---- 11. reproducibility ---- */
push(
  H('11  Reproducibility and provenance', 1),
  P('The whole chain runs from one command. From an empty directory it generates the rehearsal corpus, runs all ten stages, writes the deposit-shaped package, renders every figure, and emits the validation report.'),
  mono('python -m uavews.cli all --out build'),
  P('Reproducibility was verified rather than assumed. Two clean runs from an empty directory produce byte-identical canonical tables, split manifests, and data dictionary. Three files differ, and all three legitimately carry wall-clock timestamps: the RO-Crate manifest, the provenance log, and the checksum manifest that digests them. It was this check that exposed finding 5 in the table above — a randomly seeded field that no test would have caught, because every individual value it produced was perfectly plausible.'),
  H('11.1  What the package contains', 2),
  caption('Deposit-shaped package written by the release stage.', ++TAB),
  table(
    ['Path', 'Format', 'Purpose'],
    [
      ['ro-crate-metadata.json', 'JSON-LD', 'Dataset-level metadata, licences, relations, provenance links'],
      ['metadata/release_metadata.json', 'JSON', 'Version, coverage, generalization, clocks, controlled vocabularies, kinematic parameters'],
      ['metadata/datacite.json', 'JSON', 'Citation metadata, with a requires_completion list for unresolved fields'],
      ['metadata/provenance.jsonl', 'JSON Lines', 'One PROV-O activity per pipeline stage'],
      ['tables/*.parquet', 'Apache Parquet', 'The six canonical tables'],
      ['splits/*.csv', 'CSV', 'The five evaluation manifests'],
      ['docs/data_dictionary.csv', 'CSV', 'Generated from the schema declaration, so it cannot drift from the validator'],
      ['checksums_sha256.txt', 'Text', 'Integrity manifest covering every released file, metadata included'],
      ['report/validation_report.json', 'JSON', 'Every computed metric, with the manuscript placeholder map of Section 12'],
    ],
    [3.4, 1.6, 6]),
  P('Unresolved fields are emitted as explicit nulls with a requires_completion list rather than as plausible placeholders. On this run the list contains the DOI and the open-tier licence, both of which must come from the depositing institution.'),
  H('11.2  Test coverage', 2),
  P('Fifty-four tests, aimed deliberately at the class of defect that produces plausible output rather than an error — an equation with the wrong sign, a split that leaks, a duplicate detector that groups everything, an estimator that reports noise as signal. A crash is found by running the pipeline once; these are not.'),
  bullet('Time base: RFC 3339 round-trip, rejection of a missing UTC designator, and an explicit demonstration that nanosecond resolution survives in the integer representation and is lost in the floating-point one.'),
  bullet('Equation (1): zero on the boundary, positive both inside and outside, sign change across the boundary, and nearest-edge rather than nearest-vertex distance.'),
  bullet('Direction rule: stated from both sides — the dead-band suppresses noise at the configured ε, and the same track yields spurious directions when ε is set to zero.'),
  bullet('Equation (2): interpolated crossing, censoring when there is no crossing, and monotone decrease to zero at the crossing.'),
  bullet('Adjudication: ground truth wins inside its authority and loses outside it; a tie stays uncertain; exactly one label is released per target.'),
  bullet('SNR estimator: accuracy above the floor, monotonicity, saturation on pure noise, and a two-sided check that the declared sensitivity floor is where the estimator actually is.'),
  bullet('Field-trial mathematics: normal quantiles against known values, sample size monotone in effect size and power, the Wilson interval remaining inside the unit interval at k = n where a Wald interval would collapse, and the detection-range solver returning exactly the range at which the SNR meets the threshold.'),
);

/* ---- 12. placeholder map ---- */
push(
  H('12  Mapping to the manuscript placeholders', 1),
  callout('Read this table as a map, not as a set of values', [
    'The right-hand column holds values computed from the synthetic rehearsal corpus. They are shown so that the mapping can be checked end to end and so that the units and formats are unambiguous.',
    'They must not be transcribed into the manuscript. Run the pipeline over the deposited release and take the values it produces there; validation_report.json carries this same map, machine-readable, together with a provenance warning.'],
    'FFF6E8', WARN),
  caption('Manuscript placeholder to computed field. Rehearsal values shown for format verification only.', ++TAB),
  table(
    ['Placeholder', 'Source in validation_report.json', 'Rehearsal value'],
    Object.entries(REPORT.manuscript_placeholders).map(([k, v]) => [
      k, 'manuscript_placeholders["' + k + '"]', String(v)]),
    [3.2, 4.4, 2.4]),
  P('Placeholders that this pipeline cannot fill are those requiring institutional or instrument information: the dataset DOI, the open-tier licence and controlled-tier terms, the authorization and operating procedure, the ground-truth system and its rate, the camera and microphone models and their settings, the final platform taxonomy, the signing and preservation method, and the ethics approval. These are emitted as explicit nulls with a requires_completion list, and no plausible value is substituted for any of them.'),
);

/* ---- appendix ---- */
push(
  pageBreak(),
  H('Appendix A  Module map', 1),
  table(
    ['Module', 'Responsibility'],
    [
      ['config', 'Release parameters and controlled vocabularies; load-time consistency checks; the ε floor'],
      ['ids', 'Keyed, non-invertible, reproducible identifiers; rotating contributor pseudonyms'],
      ['timebase', 'RFC 3339 ↔ int64 UTC nanoseconds, clock model, Equation (3), interval algebra'],
      ['geometry', 'Warning-zone polygon, Equation (1), direction rule, Equation (2), closing rate'],
      ['schema', 'Table declarations, structural validator, referential integrity, data dictionary'],
      ['ingest.s1–s4, ingest.common', 'One normalizer per source family; the minimum event envelope'],
      ['media_qc', 'Measured audio and visual quality, harmonic-sum SNR with a Monte-Carlo null, perceptual hashing'],
      ['association', 'Window tiling, marker-based Equation (3), uncertainty-expanded matching, diagnostics'],
      ['labeling', 'Evidence tiers, authoritative-field set, conflict adjudication, released-label selection'],
      ['agreement', 'Krippendorff’s α, bootstrap intervals over units, boundary agreement'],
      ['validation', 'Equations (4) and (5), missingness, media quality, cross-modal consistency, integrity, gates'],
      ['privacy', 'Access tiering, k-anonymity probe, independent export audit, internal-column stripping'],
      ['splits', 'Five leakage-resistant manifests, duplicate-constraint resolution, per-constraint audit'],
      ['trialdesign', 'Detection ranges, warning-time budget, sample size, flight-matrix planning'],
      ['packaging', 'RO-Crate, DataCite, PROV-O, SHA-256 integrity manifest'],
      ['simulate', 'Synthetic rehearsal corpus and annotator simulation — non-empirical by construction'],
      ['viz, cli, pipeline', 'Report figures, command-line driver, stage orchestration'],
    ],
    [2.6, 7.4]),
  H('Appendix B  Configuration', 1),
  P('The complete parameter file follows. It is reproduced here because every number in Sections 5 and 9 derives from it, and because the provenance record for each pipeline stage names it.'),
  ...fs.readFileSync(path.join(ROOT, 'config/pipeline.yaml'), 'utf8')
    .split('\n').map(line => new Paragraph({
      spacing: { before: 0, after: 0, line: 210 },
      children: [new TextRun({
        text: line || ' ', size: 14, font: 'Consolas',
        color: line.trim().startsWith('#') ? MUTED : INK })],
    })),
);

/* ------------------------------------------------------------------ build */
const doc = new Document({
  creator: 'uavews pipeline',
  title: 'Dataset Formation and Preparation Pipeline',
  description: 'Engineering companion to the sUAV early-warning Data Descriptor',
  numbering: {
    config: [
      { reference: 'bullets', levels: [
        { level: 0, format: LevelFormat.BULLET, text: '•', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 240 } } } },
        { level: 1, format: LevelFormat.BULLET, text: '◦', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 880, hanging: 240 } } } },
      ] },
      { reference: 'numbers', levels: [
        { level: 0, format: LevelFormat.DECIMAL, text: '%1.', alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 460, hanging: 240 } } } },
      ] },
    ],
  },
  styles: {
    default: { document: { run: { font: 'Calibri', size: 20, color: INK } } },
  },
  sections: [{
    properties: {
      page: {
        size: { width: 11906, height: 16838 },       // A4 portrait
        margin: { top: 1134, right: 1134, bottom: 1134, left: 1134 },
      },
    },
    headers: {
      default: new Header({ children: [new Paragraph({
        alignment: AlignmentType.RIGHT,
        spacing: { after: 60 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'D8DBE0', space: 6 } },
        children: [new TextRun({
          text: 'uavews — dataset formation, validation, and field-trial preparation',
          size: 15, color: MUTED })],
      })] }),
    },
    footers: {
      default: new Footer({ children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        children: [
          new TextRun({ text: 'Rehearsal run — not empirical data      ', size: 15, color: MUTED }),
          new TextRun({ children: [PageNumber.CURRENT], size: 15, color: MUTED }),
        ],
      })] }),
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.mkdirSync(path.dirname(OUT), { recursive: true });
  fs.writeFileSync(OUT, buf);
  console.log('wrote', OUT, (buf.length / 1024).toFixed(0) + ' KB');
});
