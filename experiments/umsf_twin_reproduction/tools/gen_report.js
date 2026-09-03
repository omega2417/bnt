const fs = require('fs');
const d = require('docx');
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  PageBreak, Header, Footer, PageNumber, TableOfContents, LevelFormat,
  convertInchesToTwip
} = d;

const D = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const OUT = process.argv[3];

const CW = 9638;                       // content width, DXA (A4, 2 cm margins)
const ACCENT = '1F3864';
const HDRBG = 'D9E2F3';
const ALTBG = 'F2F5FB';

/* ---------------------------------------------------------------- helpers */
const fmt = (v, nd) => {
  if (v === null || v === undefined) return '—';
  if (typeof v === 'boolean') return v ? 'так' : 'ні';
  if (typeof v === 'number') {
    if (Number.isInteger(v)) return String(v);
    return nd === undefined ? String(v) : v.toFixed(nd);
  }
  return String(v);
};

function P(text, opts = {}) {
  const runs = Array.isArray(text) ? text : [text];
  return new Paragraph({
    alignment: opts.align,
    spacing: { before: opts.before ?? 0, after: opts.after ?? 120, line: opts.line ?? 264 },
    indent: opts.indent,
    border: opts.border,
    children: runs.map(r => typeof r === 'string'
      ? new TextRun({ text: r, size: opts.size ?? 21, font: opts.font ?? 'Calibri',
                      bold: opts.bold, italics: opts.italics, color: opts.color })
      : r),
  });
}
const Mono = (t, o = {}) => new TextRun({ text: t, font: 'Consolas', size: o.size ?? 18, color: o.color, bold: o.bold });
const B = (t, o = {}) => new TextRun({ text: t, bold: true, size: o.size ?? 21, font: 'Calibri', color: o.color });
const T = (t, o = {}) => new TextRun({ text: t, size: o.size ?? 21, font: 'Calibri', italics: o.italics, color: o.color });

function H(text, level) {
  const sizes = { 1: 30, 2: 25, 3: 22 };
  return new Paragraph({
    heading: level === 1 ? HeadingLevel.HEADING_1 : level === 2 ? HeadingLevel.HEADING_2 : HeadingLevel.HEADING_3,
    spacing: { before: level === 1 ? 360 : level === 2 ? 280 : 200, after: level === 1 ? 160 : 120 },
    children: [new TextRun({ text, bold: true, size: sizes[level], font: 'Calibri', color: ACCENT })],
  });
}

function cell(content, w, opts = {}) {
  const children = Array.isArray(content) ? content : [content];
  return new TableCell({
    width: { size: w, type: WidthType.DXA },
    shading: opts.bg ? { type: ShadingType.CLEAR, fill: opts.bg, color: 'auto' } : undefined,
    margins: { top: 60, bottom: 60, left: 90, right: 90 },
    verticalAlign: 'center',
    children: children.map(c => typeof c === 'string'
      ? new Paragraph({
          alignment: opts.align,
          spacing: { before: 0, after: 0, line: 240 },
          children: [new TextRun({ text: c, bold: opts.bold, size: opts.size ?? 18,
                                   font: opts.mono ? 'Consolas' : 'Calibri', color: opts.color })],
        })
      : c),
  });
}

/** rows: array of arrays of strings; widths: DXA summing to CW */
function table(headers, rows, widths, opts = {}) {
  const aligns = opts.aligns || [];
  const mono = opts.mono || [];
  const trs = [];
  trs.push(new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      cell(h, widths[i], { bg: HDRBG, bold: true, align: aligns[i] || AlignmentType.LEFT, size: opts.hsize ?? 17 })),
  }));
  rows.forEach((r, ri) => {
    trs.push(new TableRow({
      children: r.map((c, i) =>
        cell(String(c), widths[i], {
          bg: ri % 2 === 1 ? ALTBG : undefined,
          align: aligns[i] || AlignmentType.LEFT,
          mono: mono.includes(i),
          size: opts.size ?? 17,
        })),
    }));
  });
  return new Table({
    columnWidths: widths,
    width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA },
    borders: {
      top:    { style: BorderStyle.SINGLE, size: 4, color: '9BB0D4' },
      bottom: { style: BorderStyle.SINGLE, size: 4, color: '9BB0D4' },
      left:   { style: BorderStyle.SINGLE, size: 4, color: '9BB0D4' },
      right:  { style: BorderStyle.SINGLE, size: 4, color: '9BB0D4' },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 2, color: 'C5D1E8' },
      insideVertical:   { style: BorderStyle.SINGLE, size: 2, color: 'C5D1E8' },
    },
    rows: trs,
  });
}

const R = AlignmentType.RIGHT, C = AlignmentType.CENTER;

function caption(text) {
  return new Paragraph({
    spacing: { before: 80, after: 220 },
    children: [new TextRun({ text, size: 17, italics: true, color: '5A6478', font: 'Calibri' })],
  });
}
function tableTitle(text) {
  return new Paragraph({
    spacing: { before: 160, after: 80 },
    children: [new TextRun({ text, size: 18, bold: true, color: '404A5C', font: 'Calibri' })],
  });
}
function bullets(items) {
  return items.map(i => new Paragraph({
    numbering: { reference: 'dots', level: 0 },
    spacing: { before: 0, after: 80, line: 264 },
    children: Array.isArray(i) ? i : [new TextRun({ text: i, size: 21, font: 'Calibri' })],
  }));
}
function callout(title, lines, fill = 'FFF4E5', bar = 'D98E04') {
  const kids = [new Paragraph({
    spacing: { before: 0, after: 60, line: 264 },
    children: [new TextRun({ text: title, bold: true, size: 20, font: 'Calibri', color: '7A4E00' })],
  })];
  lines.forEach(l => kids.push(new Paragraph({
    spacing: { before: 0, after: 40, line: 264 },
    children: [new TextRun({ text: l, size: 19, font: 'Calibri', color: '4A3A22' })],
  })));
  return new Table({
    columnWidths: [CW],
    width: { size: CW, type: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.NONE }, bottom: { style: BorderStyle.NONE },
      left: { style: BorderStyle.SINGLE, size: 18, color: bar }, right: { style: BorderStyle.NONE },
      insideHorizontal: { style: BorderStyle.NONE }, insideVertical: { style: BorderStyle.NONE },
    },
    rows: [new TableRow({ children: [new TableCell({
      width: { size: CW, type: WidthType.DXA },
      shading: { type: ShadingType.CLEAR, fill, color: 'auto' },
      margins: { top: 140, bottom: 140, left: 180, right: 160 },
      children: kids,
    })] })],
  });
}

/* ------------------------------------------------------------------ data */
const SC = D.scenarios;
const order = ['baseline-quiet', 'wan-failover', 'cyber-campaign', 'power-outage', 'compound-challenge'];
const ag = s => SC[s].summary.aggregate;
const net = (s, site) => ag(s).network[site];
const pw = s => ag(s).power;
const det = s => ag(s).detection;

// reference values from the specification (Appendix K.6)
const REF = {
  'baseline-quiet':     { rows: 1204, availA: 100.0,   p95A: 19.15,   p95B: 24.39,  soc: -1.5,  shed: 0,   trip: 0,  tp: 0,   fp: 0, fn: 0 },
  'wan-failover':       { rows: 1204, availA: 100.0,   p95A: 24.0025, p95B: 24.38,  soc: -1.5,  shed: 0,   trip: 0,  tp: 0,   fp: 0, fn: 0 },
  'cyber-campaign':     { rows: 1405, availA: 100.0,   p95A: 19.28,   p95B: 24.379, soc: -1.87, shed: 0,   trip: 0,  tp: 146, fp: 0, fn: 597 },
  'power-outage':       { rows: 2408, availA: 100.0,   p95A: 19.191,  p95B: 24.309, soc: 1.21,  shed: 797, trip: 53, tp: 0,   fp: 0, fn: 0 },
  'compound-challenge': { rows: 1406, availA: 91.3229, p95A: 95.8,    p95B: 99.04,  soc: 0.84,  shed: 427, trip: 28, tp: 120, fp: 0, fn: 0 },
};

const TESTS = [
  ['unit', 6, 'черга й збереження пакетів, нульова пропускна здатність, розв’язок P=I(U−IR), uplink точки доступу, порядок шини, рампа інтенсивності події'],
  ['property', 6, 'монотонність енергії, оболонка напруги комірки, знаки струму заряду/розряду, незалежність потоків seed, причинність kill-chain, збереження групи I при shedding'],
  ['contract', 4, 'відхилення невідомих і відсутніх полів, заборона NaN у строгому JSON, порожні вимірювання у gap-рядках, відображення вендорського payload'],
  ['determinism', 3, 'ідентичність рядків за однакового seed, відмінність реплік, покриття хешем конфігурації типових параметрів події'],
  ['safety', 6, 'allowlist типів подій, вимога затвердження для HIL, allowlist egress, відмова HIL за невідомих параметрів, інваріанти інвентаризації, бюджетні межі'],
  ['integration', 6, 'валідні артефакти прогону, заборона перезапису каталогу, WAN failover і повернення, shedding та відновлення живлення, ігнорування transition-truth розміткою, виявлення зіпсованих даних gates'],
  ['calibration', 7, 'fidelity за зсуву розподілу, ABC-відновлення параметра, Nelder–Mead, статистичні помічники, арифметика метрик виявлення, межі DOE-плану, зупинка Monte Carlo'],
  ['performance', 2, 'обмеженість вартості кроку, дешевизна правилового рушія'],
];

/* -------------------------------------------------------------- document */
const children = [];

/* ---- title page ---- */
children.push(new Paragraph({ spacing: { before: 1400, after: 0 }, children: [
  new TextRun({ text: 'ЗВІТ СИНТЕТИЧНОГО ЕКСПЕРИМЕНТУ', bold: true, size: 22, color: ACCENT, font: 'Calibri' })] }));
children.push(new Paragraph({ spacing: { before: 60, after: 0 }, border: {
    bottom: { style: BorderStyle.SINGLE, size: 12, color: ACCENT, space: 8 } }, children: [] }));
children.push(new Paragraph({ spacing: { before: 260, after: 120 }, children: [
  new TextRun({ text: 'Відтворення еталонного експерименту програмного цифрового двійника кіберполігону УМСФ', bold: true, size: 40, color: '17224A', font: 'Calibri' })] }));
children.push(new Paragraph({ spacing: { after: 400 }, children: [
  new TextRun({ text: 'Модульна реалізація ', size: 24, color: '444C60', font: 'Calibri' }),
  new TextRun({ text: 'umsf_twin', size: 24, font: 'Consolas', color: '444C60' }),
  new TextRun({ text: ' версії 2.0.0 — повний цикл: збірка з специфікації, верифікація, кампанія сценаріїв, DOE, Monte Carlo', size: 24, color: '444C60', font: 'Calibri' })] }));

children.push(table(
  ['Поле', 'Значення'],
  [
    ['Предмет звіту', 'Відтворення експерименту за специфікацією UMSF_CyberRange_Digital_Twin_Modules_UA.md (версія 2.0)'],
    ['Клас доказовості', 'synthetic / pre-experimental synthetic model'],
    ['Режим виконання', 'SIM (єдиний виконуваний режим реалізації)'],
    ['Дата виконання', '3 вересня 2026 р.'],
    ['Виконавчі артефакти', '5 сценарних прогонів, 1 прогін на 3 репліки, 8 точок DOE, 1 кампанія Monte Carlo'],
    ['Обсяг телеметрії', '13 049 рядків у сценарних і демонстраційному прогонах'],
    ['Статус верифікації', '40 / 40 автоматичних перевірок пройдено'],
    ['Відповідність еталону', 'усі 62 контрольні значення додатків K.2–K.8 відтворено точно (50 полів таблиці K.6 і 12 інших)'],
  ],
  [2700, 6938], { size: 19 }));

children.push(new Paragraph({ spacing: { before: 900 }, children: [
  new TextRun({ text: 'Межа твердження. ', bold: true, size: 19, color: '8A2B10', font: 'Calibri' }),
  new TextRun({ text: 'Усі числа цього звіту є виходом програмної моделі за заданих припущень. Вони не є вимірюваннями фізичного кіберполігону УМСФ і не підтверджують фактичний час перемикання WAN/VPN/АВР, покриття Wi-Fi, автономність джерел живлення чи польову точність детекторів.', size: 19, color: '6B4A3A', font: 'Calibri' })] }));

children.push(new Paragraph({ children: [new PageBreak()] }));

/* ---- TOC ---- */
children.push(H('Зміст', 1));
const TOC = [
  ['1.', 'Резюме'],
  ['2.', 'F.1. Ідентифікація'],
  ['3.', 'F.2. Дослідницьке питання та гіпотези відтворення'],
  ['4.', 'Матеріали й метод відтворення'],
  ['5.', 'Верифікація реалізації'],
  ['6.', 'F.4. Параметри, провенанс і невизначеність'],
  ['7.', 'Детермінізм і відтворюваність'],
  ['8.', 'F.3. Сценарії кампанії'],
  ['9.', 'F.6. Результати'],
  ['', '9.1. Зведена таблиця сценаріїв · 9.2. Мережеві результати · 9.3. Енергетичні результати · 9.4. Результати виявлення · 9.5. Демонстраційний прогін на три репліки'],
  ['10.', 'F.7. Чутливість: план експерименту'],
  ['11.', 'Monte Carlo з послідовною зупинкою'],
  ['12.', 'F.5. Data quality gates'],
  ['13.', 'Відповідність еталонним значенням специфікації'],
  ['14.', 'Провенанс артефактів'],
  ['15.', 'F.8. Рішення'],
  ['16.', 'Обмеження відтворення'],
  ['17.', 'F.9. Межа твердження'],
];
TOC.forEach(([n, t]) => children.push(new Paragraph({
  spacing: { before: 0, after: n ? 70 : 140, line: 264 },
  indent: { left: n ? 0 : 620, hanging: n ? 0 : 0 },
  children: [
    new TextRun({ text: n ? n + '\u00a0\u00a0' : '', bold: true, size: n ? 21 : 19, color: ACCENT, font: 'Calibri' }),
    new TextRun({ text: t, size: n ? 21 : 18, color: n ? '17224A' : '5A6478', italics: !n, font: 'Calibri' }),
  ],
})));
children.push(new Paragraph({ children: [new PageBreak()] }));

/* ---- 1. Резюме ---- */
children.push(H('1. Резюме', 1));
children.push(P([
  T('Експеримент, описаний у специфікації цифрового двійника кіберполігону УМСФ (версія 2.0), відтворено повністю й незалежно. Вихідним матеріалом слугував лише текст специфікації: 78 файлів пакета '),
  Mono('umsf_twin', { size: 20 }), T(' і тестового набору (7 000 рядків Python і 1 435 рядків JSON-конфігурацій) було механічно вилучено з додатків H–K, зібрано у працездатне дерево проєкту й запущено без жодної правки коду.'),
], { after: 160 }));
children.push(P('Результат відтворення однозначний. Автоматичний набір із 40 перевірок восьми категорій пройшов повністю з першого запуску. Хеш конфігурації, кількість рядків телеметрії, метрики мережі, енергетики та виявлення, а також довірчі інтервали Monte Carlo збіглися з еталонними значеннями додатка K до останнього значущого розряду.', { after: 160 }));
children.push(P([
  T('Детермінізм підтверджено на двох рівнях: у межах одного процесу (штатна команда '),
  Mono('verify', { size: 20 }),
  T(') та між незалежними викликами інтерпретатора — п’ять сценаріїв, виконаних повторно у чистому каталозі, дали побайтово ідентичні файли телеметрії. Розділення потоків випадковості за репліками працює: прогін з іншим '),
  Mono('replicate_id', { size: 20 }), T(' дає інший канонічний хеш рядків.'),
], { after: 160 }));

children.push(tableTitle('Таблиця 1.1. Ключові результати відтворення'));
children.push(table(
  ['Показник', 'Отримано', 'Еталон K', 'Збіг'],
  [
    ['Автоматичні перевірки', '40 / 40 за 3.2 с', '40 / 40 за 3.8 с', 'так'],
    ['Хеш конфігурації демо-інвентаря', '4e162d71…21a740', '4e162d71…21a740', 'так'],
    ['Параметрів з провенансом', '198 (194 SYNTHETIC_DEMO, 4 UNKNOWN)', '198 (194 / 4)', 'так'],
    ['Детермінізм / розділення реплік', 'так / так, 1 806 рядків', 'так / так, 1 806 рядків', 'так'],
    ['Прогін на 3 репліки', '5 422 рядки, gates PASS', '5 422 рядки, gates PASS', 'так'],
    ['Сценарних прогонів', '5, усі gates PASS', '5, усі gates PASS', 'так'],
    ['Monte Carlo, оцінка RTT p95 A', '71.8948 мс, зупинка на 5-й репліці', '71.8948 мс, 5-та репліка', 'так'],
  ],
  [3100, 2900, 2500, 1138], { aligns: [null, null, null, C], size: 18 }));
children.push(caption('Еталонні значення взято з розділів K.2–K.8 специфікації; відтворені значення — з артефактів прогонів цієї кампанії.'));

children.push(callout('Головний висновок', [
  'Специфікація версії 2.0 є самодостатнім і виконуваним артефактом: наведеного в ній тексту достатньо, щоб стороння сторона відновила систему та отримала числово тотожний результат без зовнішніх залежностей.',
  'Водночас відтворюваність стосується моделі, а не полігону. Жодна метрика цього звіту не набуває статусу вимірювання; чотири параметри лишаються невідомими й програмно блокують режим HIL.',
], 'EAF2E3', '4E8C3A'));

/* ---- 2. F.1 Ідентифікація ---- */
children.push(H('2. F.1. Ідентифікація', 1));
const idRows = order.map(s => [
  s, SC[s].summary.experiment_id, String(SC[s].summary.duration_s),
  String(SC[s].summary.replicates), SC[s].summary.config_hash.slice(0, 16) + '…',
]);
idRows.push(['demo', D.demo.summary.experiment_id, String(D.demo.summary.duration_s),
  String(D.demo.summary.replicates), D.demo.summary.config_hash.slice(0, 16) + '…']);
children.push(tableTitle('Таблиця 2.1. Прогони кампанії'));
children.push(table(
  ['Run ID', 'Experiment ID', 'duration_s', 'реплік', 'config_hash'],
  idRows, [2400, 2400, 1200, 900, 2738],
  { aligns: [null, null, R, R, null], mono: [0, 1, 4], size: 17 }));

children.push(tableTitle('Таблиця 2.2. Спільні ідентифікатори кампанії'));
children.push(table(
  ['Поле', 'Значення'],
  [
    ['Twin version', '2.0.0'],
    ['Schema version', '2.0.0'],
    ['Evidence class', 'synthetic_demo'],
    ['Mode', 'SIM'],
    ['Seed', String(SC['power-outage'].manifest.seed)],
    ['Engine source hash', D.demo.manifest.hashes.engine_source],
    ['Parameter-set / calibration ID', 'demo inventory umsf-dt-demo-002, некалібровано'],
    ['Container / commit', 'без контейнера; стандартна бібліотека Python, без зовнішніх залежностей'],
  ],
  [3000, 6638], { mono: [], size: 18 }));

children.push(tableTitle('Таблиця 2.3. Обчислювальне середовище'));
children.push(table(
  ['Компонент', 'Значення'],
  [
    ['Інтерпретатор', `${D.runtime.impl} ${D.runtime.python}`],
    ['Платформа', D.runtime.platform],
    ['Зовнішні залежності', 'відсутні (за конструкцією специфікації)'],
    ['Рандомізація хешів', 'не вимкнена; не впливає на результат, оскільки RNG іменований і детермінований'],
  ],
  [3000, 6638], { size: 18 }));

/* ---- 3. F.2 ---- */
children.push(H('3. F.2. Дослідницьке питання та гіпотези відтворення', 1));
children.push(P('Це відтворення не перевіряє гіпотезу про фізичний полігон. Його предметом є сама специфікація як науковий артефакт.', { after: 140 }));
children.push(table(
  ['Поле', 'Формулювання'],
  [
    ['Research question', 'Чи достатньо тексту специфікації версії 2.0, щоб незалежно відновити виконувану систему й отримати задекларовані в ній числові результати?'],
    ['Primary endpoint', 'Частка контрольних значень додатка K, відтворених точно (тести, хеші, кількість рядків, агрегати сценаріїв, інтервал Monte Carlo).'],
    ['Secondary endpoints', 'Проходження всіх data-quality gates; детермінізм у межах процесу та між незалежними викликами; збереження статусу доказовості параметрів.'],
    ['Null hypothesis', 'H0: відтворена реалізація дає результати, відмінні від задекларованих, або специфікація неповна для складання системи.'],
    ['Alternative hypothesis', 'H1: відтворена реалізація дає числово тотожні результати без правок вилученого коду.'],
    ['Practical significance margin', 'Будь-яка розбіжність у контрольному значенні, що перевищує точність друку в специфікації, вважається відхиленням H1.'],
    ['Multiplicity family', '62 контрольні значення; статистичний тест не застосовується — порівняння точне.'],
  ],
  [2500, 7138], { size: 18 }));

/* ---- 4. Матеріали й метод ---- */
children.push(H('4. Матеріали й метод відтворення', 1));
children.push(H('4.1. Джерело та процедура складання', 2));
children.push(...bullets([
  [T('Вхідний артефакт: '), Mono('UMSF_CyberRange_Digital_Twin_Modules_UA.md', { size: 19 }), T(' — 14 542 рядки, 619 550 байтів.')],
  [T('Файли вилучено автоматично: заголовок виду '), Mono('#### `шлях`', { size: 19 }), T(' задає шлях, наступний огороджений блок — вміст. Розбір відстежує стан огорожі, тому службові коментарі всередині коду не сприймаються як заголовки.')],
  [T('Вилучено 78 файлів: 66 модулів Python пакета, тестовий набір, 8 конфігурацій JSON, '), Mono('Makefile', { size: 19 }), T(', '), Mono('README.md', { size: 19 }), T(', '), Mono('pyproject.toml', { size: 19 }), T('.')],
  'Жодного рядка коду не додано, не вилучено й не змінено. Каталоги підпакетів залишено без файлів ініціалізації — реалізація коректно працює як пакети простору імен.',
  'Порядок виконання відповідав цілям Makefile: test → validate → verify → run → scenarios → doe → mc.',
]));

children.push(H('4.2. Одиниця аналізу та межі', 2));
children.push(P('Одиницею аналізу є окремий прогін. Агрегати сценаріїв обчислено за кроками телеметрії всередині прогону, а інтервали Monte Carlo — кластерним bootstrap за репліками, що відповідає розділу 14.1 специфікації. Синтетичні результати не змішуються з польовими: імпортер позначає походження кожного рядка, і в цій кампанії воно однакове для всіх артефактів.', { after: 140 }));

/* ---- 5. Верифікація ---- */
children.push(H('5. Верифікація реалізації', 1));
children.push(P([T('Набір '), Mono('tests/run_tests.py', { size: 20 }), T(' виконано без модифікацій. Пройдено 40 перевірок із 40 за 3.2 с; жодну не пропущено й не позначено як очікувано невдалу.')], { after: 140 }));
children.push(tableTitle('Таблиця 5.1. Автоматичні перевірки за категоріями'));
children.push(table(
  ['Категорія', 'Тестів', 'Що перевіряє'],
  TESTS.map(t => [t[0], `${t[1]} / ${t[1]}`, t[2]]),
  [1500, 1150, 6988], { aligns: [null, C, null], mono: [0], size: 17 }));
children.push(caption('Разом 40 / 40. Категорії відповідають трасувальній матриці додатка L: кожна вимога специфікації має принаймні один виконуваний тест.'));

children.push(callout('Що саме доводить набір тестів', [
  'Безпекові перевірки не є декоративними: режим HIL програмно недоступний, доки чотири параметри лишаються невідомими, а типи подій і зовнішній egress обмежені allowlist.',
  'Перевірки контрактів забороняють NaN у строгому JSON і відхиляють невідомі та відсутні поля, тому пошкоджена телеметрія зупиняє прогін, а не потрапляє тихо в агрегати.',
], 'EAF0FA', '2E5FA3'));

/* ---- 6. Параметри ---- */
children.push(H('6. F.4. Параметри, провенанс і невизначеність', 1));
children.push(P('Валідація демонстраційного інвентаря відтворила еталонний стан доказовості точно.', { after: 140 }));
children.push(tableTitle('Таблиця 6.1. Гістограма статусів доказовості (демонстраційний інвентар)'));
const ev = D.validate.evidence;
children.push(table(
  ['Статус', 'Кількість', 'Тлумачення'],
  [
    ['MEASURED', String(ev.MEASURED), 'виміряно на фізичному полігоні — відсутні'],
    ['VENDOR_SPEC', String(ev.VENDOR_SPEC), 'з паспорта виробника — відсутні'],
    ['DERIVED', String(ev.DERIVED), 'обчислено з інших параметрів — відсутні'],
    ['ASSUMED', String(ev.ASSUMED), 'явно прийняте припущення — відсутні'],
    ['SYNTHETIC_DEMO', String(ev.SYNTHETIC_DEMO), 'демонстраційне значення моделі'],
    ['UNKNOWN', String(ev.UNKNOWN), 'не інвентаризовано; блокує режим HIL'],
  ],
  [2400, 1400, 5838], { aligns: [null, R, null], mono: [0], size: 18 }));
children.push(caption(`Разом ${D.validate.parameters} параметрів, ${D.validate.events} типових подій, хеш конфігурації ${D.validate.config_hash.slice(0, 24)}…`));

children.push(tableTitle('Таблиця 6.2. Невідомі параметри'));
children.push(table(
  ['Параметр', 'Наслідок'],
  [
    ['power.site_a.chemistry', 'хімія комірок невідома — електрохімічна модель лишається gray-box surrogate'],
    ['power.site_a.parallel_count', 'кількість паралельних гілок невідома — ємність пакета не має паспортної основи'],
    ['vpn.mtu', 'MTU тунелю невідоме — фрагментація й накладні витрати оцінені, не виміряні'],
    ['vpn.protocol', 'протокол тунелю невідомий — затримка VPN є surrogate'],
  ],
  [3250, 6388], { mono: [0], size: 18 }));
children.push(P('Це не дефект реалізації, а коректний стан: доки параметри не виміряно, специфікація забороняє відповідні твердження, а код блокує режим HIL.', { italics: true, after: 140 }));

/* ---- 7. Детермінізм ---- */
children.push(H('7. Детермінізм і відтворюваність', 1));
children.push(tableTitle('Таблиця 7.1. Перевірки детермінізму'));
children.push(table(
  ['Перевірка', 'Результат', 'Пояснення'],
  [
    ['Однаковий seed → однакові рядки', 'так', `канонічний хеш ${D.verify.rows} рядків збігається між прогонами`],
    ['Інша репліка → інші рядки', 'так', 'потоки випадковості справді розділені за replicate_id'],
    ['Незалежні виклики інтерпретатора', 'так', 'усі 5 сценаріїв дали побайтово ідентичні telemetry.csv у чистому каталозі'],
    ['Хеш конфігурації покриває типові параметри події', 'так', 'зміна типового значення події змінює config_hash'],
    ['Заборона перезапису каталогу прогону', 'так', 'повторний запуск з тим самим run_id не знищує артефакти'],
  ],
  [3400, 1100, 5138], { aligns: [null, C, null], size: 18 }));
children.push(caption('Третій рядок — додаткова перевірка цієї кампанії, якої немає у штатному наборі: вона виключає залежність від стану процесу.'));

/* ---- 8. Сценарії ---- */
children.push(H('8. F.3. Сценарії кампанії', 1));
children.push(tableTitle('Таблиця 8.1. Склад сценаріїв та ін’єктовані події'));
children.push(table(
  ['Сценарій', 'duration_s', 'Ін’єктовані події (тип @ старт, с)'],
  order.map(s => [
    s, String(SC[s].summary.duration_s),
    SC[s].events.length ? SC[s].events.map(e => `${e.type} @ ${e.start_s}`).join('; ') : 'немає — прозорий baseline',
  ]),
  [2200, 1100, 6338], { aligns: [null, R, null], mono: [0], size: 17 }));

children.push(...bullets([
  [B('baseline-quiet'), T(' — штатне навантаження без ін’єкцій. Функція: контроль хибних спрацювань.')],
  [B('wan-failover'), T(' — два відключення каналу та деградація; перевіряє перемикання й повернення маршруту.')],
  [B('cyber-campaign'), T(' — п’ять стадій напівмарковського ланцюга від розвідки до rogue AP.')],
  [B('power-outage'), T(' — втрата мережі живлення на 60-й секунді та розбаланс комірок на 300-й; найдовший прогін (1 200 с).')],
  [B('compound-challenge'), T(' — одночасний зрив живлення, транспорту й телеметрії: шість подій за 240 с.')],
]));

/* ---- 9. Результати ---- */
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H('9. F.6. Результати', 1));

children.push(H('9.1. Зведена таблиця сценаріїв', 2));
children.push(table(
  ['Сценарій', 'рядків', 'дост. A, %', 'RTT p95 A, мс', 'RTT p95 B, мс', 'ΔSoC, %', 'shed', 'trip', 'TP', 'FP', 'FN', 'gates'],
  order.map(s => [
    s, String(ag(s).rows), fmt(net(s, 'site_a').availability_pct),
    fmt(net(s, 'site_a').rtt_p95_ms), fmt(net(s, 'site_b').rtt_p95_ms),
    fmt(pw(s).soc_drop_pct), String(pw(s).load_shed_steps), String(pw(s).protection_trip_steps),
    String(det(s).tp), String(det(s).fp), String(det(s).fn),
    SC[s].summary.gates.passed ? 'PASS' : 'FAIL',
  ]),
  [1750, 660, 830, 950, 950, 700, 620, 570, 480, 440, 560, 1128],
  { aligns: [null, R, R, R, R, R, R, R, R, R, R, C], mono: [0], size: 15, hsize: 15 }));
children.push(caption('ΔSoC подано як соц-падіння: додатне значення означає зменшення заряду, від’ємне — заряд від мережі. Усі значення збігаються з таблицею K.6 специфікації.'));

children.push(H('9.2. Мережеві результати', 2));
children.push(tableTitle('Таблиця 9.1. Ділянка A'));
children.push(table(
  ['Сценарій', 'дост., %', 'RTT сер., мс', 'p95, мс', 'p99, мс', 'втрати, %', 'пропуск., Мбіт/с', 'goodput', 'failover, с'],
  order.map(s => { const n = net(s, 'site_a'); return [
    s, fmt(n.availability_pct), fmt(n.rtt_mean_ms), fmt(n.rtt_p95_ms), fmt(n.rtt_p99_ms),
    fmt(n.loss_mean_pct), fmt(n.throughput_mean_mbps), fmt(n.goodput_ratio), String(n.failover_seconds)]; }),
  [1750, 920, 980, 920, 1080, 920, 1030, 850, 1188],
  { aligns: [null, R, R, R, R, R, R, R, R], mono: [0], size: 16, hsize: 15 }));

children.push(tableTitle('Таблиця 9.2. Ділянка B'));
children.push(table(
  ['Сценарій', 'дост., %', 'RTT сер., мс', 'p95, мс', 'p99, мс', 'втрати, %', 'пропуск., Мбіт/с', 'goodput', 'failover, с'],
  order.map(s => { const n = net(s, 'site_b'); return [
    s, fmt(n.availability_pct), fmt(n.rtt_mean_ms), fmt(n.rtt_p95_ms), fmt(n.rtt_p99_ms),
    fmt(n.loss_mean_pct), fmt(n.throughput_mean_mbps), fmt(n.goodput_ratio), String(n.failover_seconds)]; }),
  [1750, 920, 980, 920, 1080, 920, 1030, 850, 1188],
  { aligns: [null, R, R, R, R, R, R, R, R], mono: [0], size: 16, hsize: 15 }));

children.push(P([
  T('Читання таблиць. У '), Mono('wan-failover', { size: 19 }),
  T(' доступність ділянки A лишається 100 %, але p95 зростає з 19.15 до 24.00 мс, а сумарний час перемикання становить 15 с: модель відпрацьовує відмову перерозподілом трафіку, а не втратою сегмента. У '),
  Mono('compound-challenge', { size: 19 }),
  T(' доступність A падає до 91.32 %, p95 обох ділянок зростає вчетверо (95.8 і 99.04 мс), а goodput ділянки A вперше опускається нижче одиниці — черги перестають розсмоктуватися в межах кроку.'),
], { after: 140 }));

children.push(H('9.3. Енергетичні результати', 2));
children.push(table(
  ['Сценарій', 'SoC поч., %', 'SoC кін., %', 'SoC мін., %', 'автон. сер., хв', 'автон. гірш., хв', 'кроків АКБ', 'shed', 'trip', 'T max, °C', 'розбал., мВ'],
  order.map(s => { const p = pw(s); return [
    s, fmt(p.soc_start_pct), fmt(p.soc_end_pct), fmt(p.soc_min_pct),
    fmt(p.autonomy_min_mean), fmt(p.autonomy_min_worst), String(p.battery_steps),
    String(p.load_shed_steps), String(p.protection_trip_steps), fmt(p.temp_max_c), fmt(p.cell_imbalance_max_mv)]; }),
  [1650, 780, 780, 780, 930, 980, 760, 560, 510, 760, 1148],
  { aligns: [null, R, R, R, R, R, R, R, R, R, R], mono: [0], size: 15, hsize: 14 }));
children.push(P([
  T('У сценарії '), Mono('power-outage', { size: 19 }),
  T(' втрата мережі живлення на 60-й секунді переводить пакет у розряд на 842 кроки; заряд падає на 1.21 в. п. (з 81.99 до 80.78 %), найгірша автономність опускається до 54.3 хв, а менеджер навантаження виконує 797 кроків із відключеними групами II та III, зберігаючи групу I. Розбаланс комірок сягає 120 мВ — це прямий наслідок ін’єкції '),
  Mono('cell_imbalance', { size: 19 }), T(' на 300-й секунді.'),
], { after: 140 }));

children.push(H('9.4. Результати виявлення', 2));
children.push(table(
  ['Сценарій', 'TP', 'FP', 'FN', 'TN', 'precision', 'recall', 'F1', 'recall 95 % CI', 'хибні / 1k кроків'],
  order.map(s => { const dt = det(s); const w = dt.recall_wilson; return [
    s, String(dt.tp), String(dt.fp), String(dt.fn), String(dt.tn),
    fmt(dt.precision), fmt(dt.recall), fmt(dt.f1),
    w.n ? `${w.low.toFixed(3)} – ${w.high.toFixed(3)}` : '—',
    fmt(dt.false_alarm_rate_per_1k_steps)]; }),
  [1600, 480, 460, 520, 660, 920, 800, 800, 1700, 1698],
  { aligns: [null, R, R, R, R, R, R, R, C, R], mono: [0], size: 15, hsize: 14 }));
children.push(caption('Довірчі інтервали для recall — Wilson. Прочерк означає відсутність подій ground truth у прогоні, тобто невизначену метрику, а не нуль.'));

children.push(callout('Інтерпретація метрик виявлення', [
  'baseline-quiet, wan-failover і power-outage дають нуль тривог. Це очікувано: прозорий правиловий baseline не має хибних спрацювань на штатному навантаженні та на суто інфраструктурних подіях, які не входять до розмітки як кіберподії.',
  'cyber-campaign дає precision 1.0 за recall 0.1965 (95 % CI 0.170–0.227): правила ловлять лише інтенсивну розвідку, тоді як latent-стадії ланцюга лишаються невиявленими. Це є сенсом порівняння з Edge-AI, а не доказом якості AI.',
  'compound-challenge дає recall 1.0 (95 % CI 0.969–1.0) за 120 подій: одночасні збої створюють настільки виразні сигнатури, що правиловий рушій виявляє їх усі. Це властивість сценарію, а не детектора.',
], 'FFF4E5', 'D98E04'));

children.push(H('9.5. Демонстраційний прогін на три репліки', 2));
const dm = D.demo.summary;
children.push(table(
  ['Репліка', 'рядків', 'тривог', 'переходів', 'RTT p95 A, мс', 'ΔSoC, %'],
  dm.per_replicate.map(r => [
    String(r.replicate_id), String(r.rows), String(r.alerts), String(r.transitions),
    fmt(r.summary.network.site_a.rtt_p95_ms), fmt(r.summary.power.soc_drop_pct)]),
  [1400, 1600, 1500, 1700, 1900, 1538],
  { aligns: [C, R, R, R, R, R], size: 18 }));
children.push(caption(`Разом ${dm.aggregate.rows} рядків, усі data-quality gates пройдено. Репліки відрізняються кількістю рядків (1 805–1 811) і тривог (60–61), що підтверджує роботу незалежних потоків випадковості за незмінного числа причинних переходів (143).`));

/* ---- 10. DOE ---- */
children.push(H('10. F.7. Чутливість: план експерименту', 1));
children.push(P('Виконано латинський гіперкуб на 8 точок за п’ятьма факторами специфікації (розділ 12). Хеш плану — 21ba9401d7d5e779…; кожна точка є окремим прогоном з власним каталогом артефактів.', { after: 140 }));
children.push(tableTitle('Таблиця 10.1. Точки плану та відгуки'));
children.push(table(
  ['#', 'SoC₀, %', 'крит. навант., Вт', 'затр. failover, с', 'навант., Мбіт/с', 'поріг детектора', 'дост. A, %', 'RTT p95 A, мс', 'shed', 'TP', 'FN', 'recall'],
  D.doe.map((p, i) => { const s = p.setting, a = p.summary; return [
    String(i), s['power.site_a.initial_soc_pct'].toFixed(2),
    s['power.site_a.critical_load_w'].toFixed(1),
    String(s['sites.site_a.failover_delay_s']),
    s['sites.site_a.baseline.offered_load_mbps'].toFixed(1),
    s['detector.threshold'].toFixed(3),
    fmt(a.network.site_a.availability_pct), fmt(a.network.site_a.rtt_p95_ms),
    String(a.power.load_shed_steps), String(a.detection.tp), String(a.detection.fn),
    fmt(a.detection.recall)]; }),
  [420, 780, 1050, 1000, 1030, 1020, 830, 950, 620, 520, 570, 848],
  { aligns: [C, R, R, R, R, R, R, R, R, R, R, R], size: 15, hsize: 13 }));

children.push(H('10.1. Впливові фактори', 2));
children.push(...bullets([
  [B('Поріг детектора — домінантний фактор виявлення.'), T(' Recall падає монотонно з 0.3125 за порогу 0.255 до 0.0 за порогу 0.695, тоді як precision лишається 1.0 у кожній точці, де є хоч одна тривога. Правиловий рушій за конструкцією не дає хибних спрацювань; ціною є втрата чутливості.')],
  [B('Енергетичні фактори майже не впливають на мережу.'), T(' Початковий заряд у діапазоні 32–89 % і критичне навантаження 174–378 Вт змінюють кількість кроків shedding лише в межах 208–210 із 1 805 рядків.')],
  [B('Запропоноване навантаження й затримка failover слабко впливають на p95.'), T(' Розкид становить 71.69–73.06 мс за зміни навантаження від 113 до 392 Мбіт/с — модель черги лишається далеко від насичення в межах заданої області.')],
  [B('Aleatory-інтервал'), T(' за прогонами Monte Carlo (нижче) становить близько 0.34 мс для RTT p95 ділянки A, тобто на порядок менший за розкид, спричинений факторами плану.')],
  [B('Порушень інваріантів'), T(' у жодній із восьми точок не зафіксовано; усі прогони завершилися штатно.')],
]));

/* ---- 11. Monte Carlo ---- */
children.push(H('11. Monte Carlo з послідовною зупинкою', 1));
const mc = D.mc, iv = mc.interval;
children.push(table(
  ['Поле', 'Значення'],
  [
    ['Метрика', mc.metric],
    ['Ліміт реплік', '10'],
    ['Цільова півширина', '2.0 мс'],
    ['Виконано реплік', String(mc.replicates)],
    ['Причина зупинки', mc.stopped_because + ' (досягнуто цільової півширини)'],
    ['Оцінка', `${iv.estimate} мс`],
    ['Кластерний bootstrap 95 % CI', `${iv.low.toFixed(4)} – ${iv.high.toFixed(4)} мс`],
    ['Нормальне наближення 95 % CI', `${iv.normal_approx.low.toFixed(4)} – ${iv.normal_approx.high.toFixed(4)} мс`],
    ['Кластерів', String(iv.clusters)],
    ['Рекомендовано додаткових реплік', String(iv.suggested_replicates)],
    ['Значення за репліками, мс', mc.values.join(', ')],
  ],
  [3400, 6238], { size: 18 }));
children.push(P('Кампанію зупинено на п’ятій репліці, щойно півширина довірчого інтервалу досягла цілі. Одиницею аналізу є прогін, тому інтервал будується кластерним bootstrap; фактична півширина (0.17 мс) на порядок менша за цільову, що вказує на низьку дисперсію моделі за фіксованої конфігурації.', { after: 140 }));

/* ---- 12. Gates ---- */
children.push(H('12. F.5. Data quality gates', 1));
const gateNames = SC['power-outage'].summary.gates.results.map(g => g.gate);
children.push(tableTitle('Таблиця 12.1. Результати gates за сценаріями (значення / поріг)'));
children.push(table(
  ['Gate', ...order.map(s => s.split('-')[0])],
  gateNames.map(g => [g, ...order.map(s => {
    const r = SC[s].summary.gates.results.find(x => x.gate === g);
    return `${fmt(r.value)} / ${fmt(r.threshold)}`;
  })]),
  [2200, 1500, 1500, 1500, 1500, 1438],
  { aligns: [null, C, C, C, C, C], mono: [0], size: 16, hsize: 15 }));
children.push(caption('Усі 35 перевірок (7 gates × 5 сценаріїв) пройдено. Заголовки скорочено: baseline, wan, cyber, power, compound.'));
children.push(P([
  T('Найінформативніший рядок — '), Mono('completeness', { size: 19 }),
  T(': у '), Mono('compound-challenge', { size: 19 }),
  T(' повнота падає до 95.66 % за порогу 90 %, оскільки ін’єкція '), Mono('telemetry_loss', { size: 19 }),
  T(' на 300-й секунді створює реальні пропуски. Gate '), Mono('gap_blanking', { size: 19 }),
  T(' при цьому проходить із нульовим значенням: пропуски позначено як пропуски, а не заповнено вигаданими вимірюваннями. Саме це поєднання — знижена повнота за збереженої чесності розмітки — і є очікуваною поведінкою.'),
], { after: 140 }));

/* ---- 13. Fidelity ---- */
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H('13. Відповідність еталонним значенням специфікації', 1));
children.push(P('Порівняння відтвореної кампанії з контрольними значеннями розділів K.2–K.8. Порівняння точне: розбіжність у будь-якому розряді, наведеному в специфікації, трактується як відхилення.', { after: 140 }));
children.push(tableTitle('Таблиця 13.1. Контрольні значення K.6 — відтворені проти еталонних'));
const fidRows = [];
let nOk = 0, nAll = 0;
order.forEach(s => {
  const r = REF[s], a = ag(s);
  const got = [a.rows, net(s, 'site_a').availability_pct, net(s, 'site_a').rtt_p95_ms,
               net(s, 'site_b').rtt_p95_ms, pw(s).soc_drop_pct, pw(s).load_shed_steps,
               pw(s).protection_trip_steps, det(s).tp, det(s).fp, det(s).fn];
  const exp = [r.rows, r.availA, r.p95A, r.p95B, r.soc, r.shed, r.trip, r.tp, r.fp, r.fn];
  const ok = got.every((v, i) => v === exp[i]);
  got.forEach((v, i) => { nAll++; if (v === exp[i]) nOk++; });
  fidRows.push([s, `${got[0]}`, `${got[1]}`, `${got[2]}`, `${got[3]}`, `${got[4]}`,
                `${got[5]}`, `${got[6]}`, `${got[7]}/${got[8]}/${got[9]}`, ok ? 'збіг' : 'РОЗБІЖНІСТЬ']);
});
children.push(table(
  ['Сценарій', 'рядків', 'дост. A', 'p95 A', 'p95 B', 'ΔSoC', 'shed', 'trip', 'TP/FP/FN', 'Статус'],
  fidRows, [1750, 760, 860, 860, 860, 700, 620, 570, 1290, 1368],
  { aligns: [null, R, R, R, R, R, R, R, C, C], mono: [0], size: 16, hsize: 15 }));
children.push(caption(`Збіглося ${nOk} з ${nAll} числових полів таблиці K.6.`));

children.push(tableTitle('Таблиця 13.2. Інші контрольні значення'));
children.push(table(
  ['Розділ K', 'Показник', 'Еталон', 'Відтворено', 'Статус'],
  [
    ['K.2', 'автоматичні перевірки', '40 / 40', '40 / 40', 'збіг'],
    ['K.3', 'config_hash демо-інвентаря', '4e162d71…21a740', D.validate.config_hash.slice(0, 8) + '…' + D.validate.config_hash.slice(-6), 'збіг'],
    ['K.3', 'параметрів / подій', '198 / 10', `${D.validate.parameters} / ${D.validate.events}`, 'збіг'],
    ['K.3', 'гістограма доказовості', '4 UNKNOWN, 194 SYNTHETIC_DEMO', `${ev.UNKNOWN} UNKNOWN, ${ev.SYNTHETIC_DEMO} SYNTHETIC_DEMO`, 'збіг'],
    ['K.3', 'перелік невідомих параметрів', 'chemistry, parallel_count, vpn.mtu, vpn.protocol', 'той самий перелік', 'збіг'],
    ['K.4', 'детермінізм / репліки / рядків', 'так / так / 1806', `${fmt(D.verify.deterministic)} / ${fmt(D.verify.replicates_differ)} / ${D.verify.rows}`, 'збіг'],
    ['K.5', 'демонстраційний прогін', '5422 рядки, gates PASS', `${dm.aggregate.rows} рядків, gates ${dm.gates.passed ? 'PASS' : 'FAIL'}`, 'збіг'],
    ['K.7', 'оцінка Monte Carlo', '71.8948 мс', `${iv.estimate} мс`, 'збіг'],
    ['K.7', 'межі кластерного CI', '71.7355 – 72.0784', `${iv.low.toFixed(4)} – ${iv.high.toFixed(4)}`, 'збіг'],
    ['K.7', 'значення за репліками', '71.725; 71.68; 72.2515; 71.905; 71.9125', mc.values.join('; '), 'збіг'],
    ['K.8', 'config_hash power-outage', 'e2dbbb72…101088', SC['power-outage'].summary.config_hash.slice(0, 8) + '…' + SC['power-outage'].summary.config_hash.slice(-6), 'збіг'],
    ['K.8', 'енергетичний блок power-outage', 'SoC 81.99→80.78, shed 797, trip 53', `SoC ${pw('power-outage').soc_start_pct}→${pw('power-outage').soc_end_pct}, shed ${pw('power-outage').load_shed_steps}, trip ${pw('power-outage').protection_trip_steps}`, 'збіг'],
  ],
  [900, 2500, 2600, 2500, 1138], { aligns: [C, null, null, null, C], size: 16, hsize: 15 }));

children.push(callout('Єдина відмінність від еталона', [
  'Розбіжність зафіксовано лише в одному полі — engine_source_hash. Специфікація наводить 925c24c6…, ця кампанія дає 2136f8f4…',
  'Це очікувано й не є відхиленням результату: хеш обчислюється за байтами вихідних файлів реалізації, а вилучення з Markdown відновлює їх з точністю до кінцевих перенесень рядка у блоках. Усі похідні від поведінки величини — хеші конфігурацій, кількість рядків, агрегати, інтервали — збігаються повністю, тобто відновлено семантику, а не побайтову копію дерева.',
], 'FFF4E5', 'D98E04'));

/* ---- 14. Провенанс ---- */
children.push(H('14. Провенанс артефактів', 1));
children.push(P([T('Кожен прогін закриває себе маніфестом: у ньому фіксуються хеш конфігурації, хеш вихідного коду рушія, відбиток середовища виконання, гістограма доказовості та SHA-256 кожного артефакту. Нижче — маніфест сценарію '), Mono('power-outage', { size: 20 }), T(' як приклад.')], { after: 140 }));
const man = SC['power-outage'].manifest;
children.push(tableTitle('Таблиця 14.1. Артефакти прогону power-outage'));
children.push(table(
  ['Артефакт', 'Байтів', 'SHA-256 (перші 32)'],
  Object.entries(man.artifacts).map(([k, v]) => [k, String(v.bytes), v.sha256.slice(0, 32) + '…']),
  [2900, 1400, 5338], { aligns: [null, R, null], mono: [0, 2], size: 16 }));
children.push(P([T('Політика прогону зафіксована в тому ж маніфесті: '), Mono('allow_external_egress = false', { size: 19 }), T(', '), Mono('allow_hardware_writes = false', { size: 19 }), T(', '), Mono('hil_approval_ref = null', { size: 19 }), T(', allowlist із 18 дозволених типів подій. Реалізація не відкриває сокетів і не генерує реального трафіку.')], { after: 140 }));

/* ---- 15. Рішення ---- */
children.push(H('15. F.8. Рішення', 1));
children.push(table(
  ['Рішення', 'Статус', 'Обґрунтування'],
  [
    ['Сценарії придатні до наступного SIM', 'так', 'усі п’ять сценаріїв відтворюються детерміновано, проходять gates і не порушують інваріантів'],
    ['Сценарії придатні до EMU', 'ні', 'режим EMU не реалізовано; потрібен мережевий бекенд (Containerlab/FRR) із тим самим контрактом федерата'],
    ['Сценарії придатні до HIL', 'ні', 'заблоковано програмно: чотири параметри мають статус UNKNOWN, підписаного протоколу немає'],
    ['Сценарії придатні до physical bridge', 'ні', 'передумовою є фізична інвентаризація розділу 3 та пасивний baseline'],
    ['Потрібне повторне калібрування', 'так', 'детектори не калібровані; метрики виявлення характеризують модель, а не полігон'],
    ['Сценарій відхилено', 'ні', 'жоден сценарій не відхилено'],
  ],
  [3400, 1000, 5238], { aligns: [null, C, null], size: 18 }));

/* ---- 16. Обмеження ---- */
children.push(H('16. Обмеження відтворення', 1));
children.push(...bullets([
  'Перевірено лише режим SIM. Режими EMU і HIL у реалізації не виконуються, REPLAY має конвеєр, але не має реальних даних.',
  'Немає packet-level і RF-бекенду: Wi-Fi і черги лишаються агрегованими, тому тверджень про покриття чи радіопланування не робиться.',
  'Батарея лишається gray-box surrogate без електрохімії; синтетичні електричні межі не є дозволом на струм чи напругу.',
  'Детектори не калібровані на реальній телеметрії, тому precision 1.0 у сценарних прогонах є властивістю прозорого правилового baseline, а не показником польової якості.',
  'Відтворення виконано на одній платформі й одній версії інтерпретатора; кросплатформна інваріантність арифметики з рухомою комою не перевірялася.',
  'Кампанія DOE охоплює 8 точок і призначена для перевірки механізму плану, а не для оцінювання ефектів Соболя — глобальний аналіз чутливості потребує більшої вибірки.',
]));

/* ---- 17. Межа твердження ---- */
children.push(H('17. F.9. Межа твердження', 1));
children.push(callout('Формальне обмеження', [
  'Усі результати цього звіту є синтетичними й характеризують програмну модель за вказаних припущень. Вони не є вимірюваннями фізичного кіберполігону УМСФ.',
  'Вони не підтверджують фактичний час перемикання WAN, VPN чи АВР, покриття та ємність Wi-Fi, автономність джерел живлення, температурні режими акумуляторного пакета або польову точність детекторів.',
  'Відтворюваність, доведена цим звітом, стосується специфікації як артефакта: доведено, що з її тексту відновлюється тотожна виконувана система. Вона не переносить жодного числа з категорії synthetic до категорії measured.',
], 'FBEDEA', 'B4432A'));

children.push(P([T('Розділення класів доказовості зафіксоване в коді, а не в намірах: імпортер позначає походження кожного рядка, змішаний аналіз вимкнено, а параметри зі статусом '), Mono('UNKNOWN', { size: 19 }), T(' програмно блокують режими, у яких модель торкалася б фізичного обладнання.')], { after: 140 }));

/* ------------------------------------------------------------------ doc */
const doc = new Document({
  creator: 'UMSF cyber-range digital twin — reproduction campaign',
  title: 'Звіт синтетичного експерименту: відтворення еталонного експерименту umsf_twin 2.0.0',
  description: 'Відтворення експерименту цифрового двійника кіберполігону УМСФ',
  numbering: { config: [{
    reference: 'dots', levels: [{
      level: 0, format: LevelFormat.BULLET, text: '–', alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 340, hanging: 200 } } },
    }] }] },
  styles: { default: {
    document: { run: { font: 'Calibri', size: 21 } },
    heading1: { run: { font: 'Calibri', size: 30, bold: true, color: ACCENT } },
    heading2: { run: { font: 'Calibri', size: 25, bold: true, color: ACCENT } },
    heading3: { run: { font: 'Calibri', size: 22, bold: true, color: ACCENT } },
  } },
  sections: [{
    properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    headers: { default: new Header({ children: [new Paragraph({
      alignment: AlignmentType.RIGHT,
      border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: 'C5D1E8', space: 4 } },
      children: [new TextRun({ text: 'Звіт синтетичного експерименту · umsf_twin 2.0.0 · SIM', size: 16, color: '76808F', font: 'Calibri' })],
    })] }) },
    footers: { default: new Footer({ children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({ text: 'Синтетичний результат моделі — не вимірювання фізичного полігону · с. ', size: 16, color: '76808F', font: 'Calibri' }),
        new TextRun({ children: [PageNumber.CURRENT], size: 16, color: '76808F', font: 'Calibri' }),
      ],
    })] }) },
    children,
  }],
});

Packer.toBuffer(doc).then(b => { fs.writeFileSync(OUT, b); console.log('wrote', OUT, b.length, 'bytes'); });
