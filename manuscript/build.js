// MDPI-style DOCX builder: parses manuscript.txt (light markup) and assembles the Data Descriptor.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, BorderStyle,
  AlignmentType, Header, Footer, PageNumber, TabStopType, LevelFormat, VerticalAlign, ShadingType, PageBreak,
} = require("docx");

const FONT = "Palatino Linotype";
const BODY = 20, SMALL = 18, TINY = 16;              // half-points
const PAGE_W = 11906, MARG = 1134;                    // A4, 2.0 cm margins
const TW = PAGE_W - 2 * MARG;                         // 9638 dxa text width
const FIGDIR = path.join(__dirname, "..", "figures");

// ---------------------------------------------------------------- inline markup tokenizer
// **bold**  *italic*  _{sub}  ^{sup}  `mono`  [@key,@key2] citations
let citeOrder = [];
function citeNums(keys) {
  const nums = keys.map(k => {
    if (!REFS[k]) throw new Error("unknown ref " + k);
    let i = citeOrder.indexOf(k);
    if (i < 0) { citeOrder.push(k); i = citeOrder.length - 1; }
    return i + 1;
  }).sort((a, b) => a - b);
  const parts = []; let s = 0;
  for (let i = 1; i <= nums.length; i++) {
    if (i === nums.length || nums[i] !== nums[i - 1] + 1) {
      const a = nums[s], b = nums[i - 1];
      parts.push(b - a >= 2 ? `${a}–${b}` : (b === a ? `${a}` : `${a},${b}`));
      s = i;
    }
  }
  return "[" + parts.join(",") + "]";
}
function runs(text, base = {}) {
  text = text.replace(/\[(@[^\]]+)\]/g, (_, g) => citeNums(g.split(/[,;]\s*/).map(x => x.trim().replace(/^@/, ""))));
  const out = []; let buf = "", b = false, i_ = false, mono = false;
  const st = { size: base.size || BODY, font: base.font || FONT, color: base.color };
  const flush = (extra = {}) => {
    if (!buf) return;
    out.push(new TextRun({ text: buf, bold: b || base.bold, italics: i_ || base.italics, size: st.size,
      font: mono ? "Courier New" : st.font, color: st.color, ...extra }));
    buf = "";
  };
  for (let k = 0; k < text.length; k++) {
    const c = text[k], n = text[k + 1];
    if (c === "\\" && n) { buf += n; k++; continue; }
    if (c === "`") { flush(); mono = !mono; continue; }
    if (mono) { buf += c; continue; }
    if (c === "*" && n === "*") { flush(); b = !b; k++; continue; }
    if (c === "*") { flush(); i_ = !i_; continue; }
    if ((c === "_" || c === "^") && n === "{") {
      flush();
      let depth = 1, j = k + 2, inner = "";
      while (j < text.length && depth) { if (text[j] === "{") depth++; if (text[j] === "}") depth--; if (depth) inner += text[j]; j++; }
      const sub = c === "_";
      // nested italic inside sub/sup
      let it = i_;
      for (const part of inner.split(/(\*)/)) {
        if (part === "*") { it = !it; continue; }
        if (part) out.push(new TextRun({ text: part, subScript: sub, superScript: !sub, italics: it || base.italics,
          bold: b || base.bold, size: st.size, font: st.font, color: st.color }));
      }
      k = j - 1; continue;
    }
    buf += c;
  }
  flush();
  return out;
}

// ---------------------------------------------------------------- block helpers
const P = (text, o = {}) => new Paragraph({
  children: runs(text, o.run || {}), alignment: o.align ?? AlignmentType.JUSTIFIED,
  indent: o.indent ?? { firstLine: 425 }, spacing: { after: o.after ?? 0, before: o.before ?? 0, line: o.line ?? 260 },
  keepNext: o.keepNext, style: o.style,
});
const H = (text, level) => new Paragraph({
  children: runs(text, { bold: level < 3, italics: level === 3, size: BODY }),
  spacing: { before: level === 1 ? 240 : 160, after: 80, line: 260 }, keepNext: true,
});
const border0 = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const NB = { top: border0, bottom: border0, left: border0, right: border0 };
const rule = { style: BorderStyle.SINGLE, size: 6, color: "000000" };

function figure(file, caption, widthCm = 16.5) {
  const buf = fs.readFileSync(path.join(FIGDIR, file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);
  const wpx = Math.round(widthCm / 2.54 * 96), hpx = Math.round(wpx * h / w);
  return [
    new Paragraph({ children: [new ImageRun({ data: buf, type: "png", transformation: { width: wpx, height: hpx },
      altText: { title: file, description: caption.slice(0, 120), name: file } })],
      alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 }, keepNext: true }),
    new Paragraph({ children: runs(caption, { size: SMALL }), alignment: AlignmentType.JUSTIFIED,
      spacing: { after: 160, line: 228 }, indent: { left: 284, right: 284 } }),
  ];
}

function table(caption, rows, widths, opts = {}) {
  const tot = widths.reduce((a, b) => a + b, 0);
  const cw = widths.map(w => Math.round(w / tot * TW));
  cw[cw.length - 1] += TW - cw.reduce((a, b) => a + b, 0);
  const nH = opts.headerRows ?? 1;
  const trs = rows.map((r, ri) => new TableRow({
    tableHeader: ri < nH && rows.length > 12,
    cantSplit: true,
    children: r.map((cell, ci) => new TableCell({
      width: { size: cw[ci], type: WidthType.DXA },
      margins: { top: 30, bottom: 30, left: 70, right: 70 },
      verticalAlign: VerticalAlign.CENTER,
      borders: {
        top: ri === 0 ? rule : border0,
        bottom: (ri === nH - 1 || ri === rows.length - 1) ? rule : border0,
        left: border0, right: border0,
      },
      children: String(cell).split("\n").map(line => new Paragraph({
        children: runs(line, { size: opts.size || SMALL, bold: ri < nH }),
        alignment: (ci === 0 || opts.alignLeft) ? AlignmentType.LEFT : AlignmentType.CENTER,
        spacing: { line: 220 }, keepNext: rows.length <= 14 && ri < rows.length - 1,
      })),
    })),
  }));
  const out = [new Paragraph({ children: runs(caption, { size: SMALL }), alignment: AlignmentType.JUSTIFIED,
    spacing: { before: 160, after: 60, line: 228 }, keepNext: true })];
  out.push(new Table({ width: { size: TW, type: WidthType.DXA }, columnWidths: cw, rows: trs }));
  if (opts.footer) out.push(new Paragraph({ children: runs(opts.footer, { size: TINY }), spacing: { before: 40, after: 160 } }));
  else out.push(new Paragraph({ children: [], spacing: { after: 100 } }));
  return out;
}

function equation(expr, num) {
  const w1 = TW - 900;
  return new Table({
    width: { size: TW, type: WidthType.DXA }, columnWidths: [w1, 900],
    rows: [new TableRow({ children: [
      new TableCell({ width: { size: w1, type: WidthType.DXA }, borders: NB, verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ children: runs(expr), alignment: AlignmentType.CENTER, spacing: { before: 60, after: 60 } })] }),
      new TableCell({ width: { size: 900, type: WidthType.DXA }, borders: NB, verticalAlign: VerticalAlign.CENTER,
        children: [new Paragraph({ children: runs(`(${num})`), alignment: AlignmentType.RIGHT })] }),
    ] })],
  });
}

function code(lines) {
  return lines.map((l, i) => new Paragraph({
    children: [new TextRun({ text: l || " ", font: "Courier New", size: 17 })],
    shading: { type: ShadingType.CLEAR, fill: "F3F3F1", color: "auto" },
    spacing: { before: i === 0 ? 80 : 0, after: i === lines.length - 1 ? 100 : 0, line: 240 },
    indent: { left: 425 },
  }));
}

// ---------------------------------------------------------------- references
const REFS = JSON.parse(fs.readFileSync(path.join(__dirname, "refs.json"), "utf8"));

// ---------------------------------------------------------------- parse manuscript
let srcText = fs.readFileSync(process.env.MS || path.join(__dirname, "manuscript.txt"), "utf8");
const figNum = {}; let fn = 0;
for (const l of srcText.split(/\r?\n/)) { const m = l.startsWith("FIG:") && l.match(/\{F:(\w+)\}/); if (m && !(m[1] in figNum)) figNum[m[1]] = ++fn; }
srcText = srcText.replace(/\{F:(\w+)\}/g, (_, k) => { if (!(k in figNum)) throw new Error("fig key " + k); return String(figNum[k]); });
const src = srcText.split(/\r?\n/);
const body = [];
let para = [], i = 0;
const flushPara = (opts) => { if (para.length) { body.push(P(para.join(" "), opts)); para = []; } };
let front = {}, firstAfterHeading = false;
while (i < src.length) {
  const line = src[i];
  if (line.startsWith("%")) { i++; continue; }
  if (/^@@(\w+):\s?(.*)$/.test(line)) { const [, k, v] = line.match(/^@@(\w+):\s?(.*)$/); front[k] = v; i++; continue; }
  if (line.trim() === "") { flushPara(firstAfterHeading ? { indent: { firstLine: 0 } } : {}); firstAfterHeading = false; i++; continue; }
  if (line.startsWith("### ")) { flushPara(); body.push(H(line.slice(4), 3)); firstAfterHeading = false; i++; continue; }
  if (line.startsWith("## ")) { flushPara(); body.push(H(line.slice(3), 2)); i++; continue; }
  if (line.startsWith("# ")) { flushPara(); body.push(H(line.slice(2), 1)); i++; continue; }
  if (line.startsWith("FIG:")) {
    flushPara();
    const [f, w, ...cap] = line.slice(4).split("|").map(s => s.trim());
    body.push(...figure(f, cap.join("|"), parseFloat(w))); i++; continue;
  }
  if (line.startsWith("EQ:")) {
    flushPara();
    const [e, n] = line.slice(3).split("||").map(s => s.trim());
    body.push(equation(e, n)); i++; continue;
  }
  if (line.startsWith("BUL:")) { flushPara(); body.push(new Paragraph({ children: runs(line.slice(4).trim()), numbering: { reference: "bul", level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { line: 260 } })); i++; continue; }
  if (line.startsWith("NUM:")) { flushPara(); body.push(new Paragraph({ children: runs(line.slice(4).trim()), numbering: { reference: "num", level: 0 }, alignment: AlignmentType.JUSTIFIED, spacing: { line: 260 } })); i++; continue; }
  if (line.startsWith("CODE")) {
    flushPara(); const lines = []; i++;
    while (!src[i].startsWith("ENDCODE")) lines.push(src[i++]);
    body.push(...code(lines)); i++; continue;
  }
  if (line.startsWith("BACK:")) {
    flushPara();
    const m = line.slice(5).trim().match(/^([^:]+):\s*(.*)$/);
    body.push(new Paragraph({ children: [...runs(`**${m[1]}:** `, { size: SMALL }), ...runs(m[2], { size: SMALL })],
      alignment: AlignmentType.JUSTIFIED, spacing: { after: 80, line: 228 } }));
    i++; continue;
  }
  if (line.startsWith("PAGEBREAK")) { flushPara(); body.push(new Paragraph({ children: [new PageBreak()] })); i++; continue; }
  if (line.startsWith("TABLE")) {
    flushPara();
    const caption = line.replace(/^TABLE\s*/, ""); i++;
    let widths = null, footer = null, opts = {};
    const rows = [];
    while (!src[i].startsWith("ENDTABLE")) {
      const l = src[i];
      if (l.startsWith("WIDTHS:")) widths = l.slice(7).split(",").map(Number);
      else if (l.startsWith("FOOTER:")) footer = l.slice(7).trim();
      else if (l.startsWith("OPTS:")) opts = JSON.parse(l.slice(5));
      else if (l.trim()) rows.push(l.split(" | ").map(s => s.trim().replace(/\\n/g, "\n")));
      i++;
    }
    i++;
    body.push(...table(caption, rows, widths || rows[0].map(() => 1), { ...opts, footer }));
    continue;
  }
  para.push(line.trim()); i++;
}
flushPara();

// references list (order of first citation; uncited refs appended would be an error)
const uncited = Object.keys(REFS).filter(k => !citeOrder.includes(k));
if (uncited.length) console.warn("UNCITED:", uncited.join(", "));
const refParas = [H("References", 1)].concat(citeOrder.map((k, n) => new Paragraph({
  children: runs(REFS[k], { size: SMALL }), numbering: { reference: "refs", level: 0 },
  alignment: AlignmentType.LEFT, spacing: { after: 30, line: 228 },
})));

// ---------------------------------------------------------------- front matter
const fm = [];
fm.push(new Paragraph({ children: runs(front.type, { size: SMALL, italics: true }), spacing: { after: 120 } }));
fm.push(new Paragraph({ children: runs(front.title, { size: 34, bold: true }), spacing: { after: 160, line: 380 } }));
fm.push(new Paragraph({ children: runs(front.authors, { size: BODY, bold: true }), spacing: { after: 120 } }));
for (const a of front.affil.split(" ;; ")) fm.push(new Paragraph({ children: runs(a, { size: TINY }), spacing: { after: 20 }, indent: { left: 284, hanging: 284 } }));
fm.push(new Paragraph({ children: runs(front.corr, { size: TINY }), spacing: { after: 160 }, indent: { left: 284, hanging: 284 } }));
fm.push(new Paragraph({ children: [...runs("**Abstract:** ", { size: SMALL }), ...runs(front.abstract, { size: SMALL })], alignment: AlignmentType.JUSTIFIED, spacing: { after: 100, line: 240 } }));
fm.push(new Paragraph({ children: [...runs("**Dataset:** ", { size: SMALL }), ...runs(front.dataset, { size: SMALL })], alignment: AlignmentType.JUSTIFIED, spacing: { after: 60, line: 240 } }));
fm.push(new Paragraph({ children: [...runs("**Dataset License:** ", { size: SMALL }), ...runs(front.license, { size: SMALL })], spacing: { after: 60 } }));
fm.push(new Paragraph({ children: [...runs("**Keywords:** ", { size: SMALL }), ...runs(front.keywords, { size: SMALL })], alignment: AlignmentType.JUSTIFIED, spacing: { after: 200, line: 240 } }));

// ---------------------------------------------------------------- document
const doc = new Document({
  creator: "tvbnet manuscript builder", title: front.title.replace(/[*_^{}]/g, ""),
  styles: { default: { document: { run: { font: FONT, size: BODY } } } },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 709, hanging: 284 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 709, hanging: 340 } } } }] },
    { reference: "refs", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 454, hanging: 454 } }, run: { size: SMALL } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: PAGE_W, height: 16838 }, margin: { top: 1134, bottom: 1134, left: MARG, right: MARG, header: 567, footer: 567 } } },
    headers: { default: new Header({ children: [new Paragraph({
      children: [new TextRun({ text: front.header, size: TINY, font: FONT, italics: true }),
        new TextRun({ children: ["\t", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], size: TINY, font: FONT })],
      tabStops: [{ type: TabStopType.RIGHT, position: TW }],
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "999999", space: 2 } } })] }) },
    children: [...fm, ...body, ...refParas],
  }],
});
Packer.toBuffer(doc).then(b => {
  const out = process.argv[2] || path.join(__dirname, "manuscript.docx");
  fs.writeFileSync(out, b);
  console.log("wrote", out, "refs cited:", citeOrder.length);
});
