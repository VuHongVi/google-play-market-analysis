// Shared PBIR helpers for the portfolio reports (adapted from the Flood-It generator).
// Layout: 1920 x 1080 canvas, 12 x 12 grid, margin 32, gutter 24, snap 8.
'use strict';
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const W = 1920, H = 1080, MARGIN = 32, GUTTER = 24, SNAP = 8, COLS = 12, ROWS = 12;
const C = {
  bg: '#FCFCFB', text: '#0B0B0B', muted: '#52514E', card: '#FFFFFF', line: '#E6E4DF',
  blue: '#2A78D6', orange: '#EB6834', aqua: '#1BAF7A', heatLo: '#CDE2FB', heatHi: '#0D366B',
  blueTint: '#EEF4FC', orangeTint: '#FDF0EA', ciBlue: '#8DB8EC', grey: '#9A9893',
};
const SCHEMA = {
  page: 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/page/2.1.0/schema.json',
  visual: 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/visualContainer/2.14.0/schema.json',
  pages: 'https://developer.microsoft.com/json-schemas/fabric/item/report/definition/pagesMetadata/1.1.0/schema.json',
};
const M = '_Measures';

// deterministic ids so re-running produces stable diffs
const hid = (s, n = 20) => crypto.createHash('sha1').update(s).digest('hex').slice(0, n);
const filterId = (s) => 'Filter' + hid('f:' + s, 24);

// ---------------------------------------------------------------- literal helpers
const lit = (v) => ({ expr: { Literal: { Value: v } } });
const str = (s) => lit(`'${String(s).replace(/'/g, "''")}'`);
const num = (n) => lit(`${n}D`);
const int = (n) => lit(`${n}L`);
const bool = (b) => lit(b ? 'true' : 'false');
const color = (hex) => ({ solid: { color: str(hex) } });

// ---------------------------------------------------------------- field helpers
const measure = (m, t = M) => ({ field: { Measure: { Expression: { SourceRef: { Entity: t } }, Property: m } }, queryRef: `${t}.${m}`, nativeQueryRef: m });
const column = (t, c) => ({ field: { Column: { Expression: { SourceRef: { Entity: t } }, Property: c } }, queryRef: `${t}.${c}`, nativeQueryRef: c });
const AGG = { Sum: 0, Avg: 1, Min: 3, Max: 4 };
const agg = (t, c, fn) => ({ field: { Aggregation: { Expression: { Column: { Expression: { SourceRef: { Entity: t } }, Property: c } }, Function: AGG[fn] } }, queryRef: `${fn}(${t}.${c})`, nativeQueryRef: `${fn === 'Avg' ? 'Average' : fn} of ${c}` });
const colRef = (t, c) => ({ Column: { Expression: { SourceRef: { Entity: t } }, Property: c } });

// ---------------------------------------------------------------- filters (visual level)
function catFilter(key, t, c, valueLiteral) {
  return {
    name: filterId(key), field: colRef(t, c), type: 'Categorical',
    filter: { Version: 2, From: [{ Name: 'f', Entity: t, Type: 0 }],
      Where: [{ Condition: { In: { Expressions: [{ Column: { Expression: { SourceRef: { Source: 'f' } }, Property: c } }], Values: [[{ Literal: { Value: valueLiteral } }]] } } }] },
    howCreated: 'User',
  };
}
function betweenFilter(key, t, c, lo, hi) {
  return {
    name: filterId(key), field: colRef(t, c), type: 'Advanced',
    filter: { Version: 2, From: [{ Name: 'f', Entity: t, Type: 0 }],
      Where: [{ Condition: { Between: { Expression: { Column: { Expression: { SourceRef: { Source: 'f' } }, Property: c } }, LowerBound: { Literal: { Value: lo } }, UpperBound: { Literal: { Value: hi } } } } }] },
    howCreated: 'User',
  };
}
function topNFilter(key, t, c, orderCol, n) {
  return {
    name: filterId(key), field: colRef(t, c), type: 'TopN',
    filter: { Version: 2,
      From: [
        { Name: 'subquery', Expression: { Subquery: { Query: { Version: 2, From: [{ Name: 'f', Entity: t, Type: 0 }],
          Select: [{ Column: { Expression: { SourceRef: { Source: 'f' } }, Property: c }, Name: 'field' }],
          OrderBy: [{ Direction: 2, Expression: { Aggregation: { Expression: { Column: { Expression: { SourceRef: { Source: 'f' } }, Property: orderCol } }, Function: 0 } } }],
          Top: n } } }, Type: 2 },
        { Name: 'g', Entity: t, Type: 0 },
      ],
      Where: [{ Condition: { In: { Expressions: [{ Column: { Expression: { SourceRef: { Source: 'g' } }, Property: c } }], Table: { SourceRef: { Source: 'subquery' } } } } }] },
    howCreated: 'User',
  };
}

// ---------------------------------------------------------------- layout
const cw = (W - 2 * MARGIN - (COLS - 1) * GUTTER) / COLS;
const rh = (H - 2 * MARGIN - (ROWS - 1) * GUTTER) / ROWS;
const snap = (v) => Math.round(v / SNAP) * SNAP;
function rect([c1, r1, c2, r2]) {
  const x = snap(MARGIN + (c1 - 1) * (cw + GUTTER));
  const y = snap(MARGIN + (r1 - 1) * (rh + GUTTER));
  const x2 = snap(MARGIN + (c2 - 1) * (cw + GUTTER) - GUTTER);
  const y2 = snap(MARGIN + (r2 - 1) * (rh + GUTTER) - GUTTER);
  return { x, y, width: x2 - x, height: y2 - y };
}
function slot(r, i, of) { // split along the longer axis
  if (r.width >= r.height) { const w = (r.width - (of - 1) * GUTTER) / of; return { ...r, x: snap(r.x + i * (w + GUTTER)), width: snap(w) }; }
  const h = (r.height - (of - 1) * GUTTER) / of; return { ...r, y: snap(r.y + i * (h + GUTTER)), height: snap(h) };
}

// ---------------------------------------------------------------- container styling
function chrome({ title, subtitle, alt, bg = C.card, border = true, pad = [12, 12, 16, 16] }) {
  const v = {
    background: [{ properties: { show: bool(true), color: color(bg), transparency: num(0) } }],
    border: [{ properties: { show: bool(border), color: color(C.line), radius: num(8), width: num(1) } }],
    padding: [{ properties: { top: num(pad[0]), bottom: num(pad[1]), left: num(pad[2]), right: num(pad[3]) } }],
    dropShadow: [{ properties: { show: bool(false) } }],
    title: [{ properties: title ? { show: bool(true), text: str(title), fontFamily: str('Segoe UI Semibold'), fontSize: num(14), fontColor: color(C.text), titleWrap: bool(true) } : { show: bool(false) } }],
    subTitle: [{ properties: subtitle ? { show: bool(true), text: str(subtitle), fontFamily: str('Segoe UI'), fontSize: num(11), fontColor: color(C.muted), titleWrap: bool(true) } : { show: bool(false) } }],
  };
  if (alt) v.general = [{ properties: { altText: str(alt) } }];
  return v;
}

// ---------------------------------------------------------------- visual builders
let z = 0;
function container(name, pos, visual, extra = {}) {
  z += 1000;
  return { $schema: SCHEMA.visual, name, position: { x: pos.x, y: pos.y, z, height: pos.height, width: pos.width, tabOrder: z }, visual, ...extra };
}
const run = (value, size, { font = 'Segoe UI', col = C.text, italic = false } = {}) => ({ value, textStyle: { fontFamily: font, fontSize: `${size}pt`, color: col, ...(italic ? { fontStyle: 'italic' } : {}) } });
function textbox(name, pos, paragraphs, { bg = null, alt = null } = {}) {
  const vco = {
    background: [{ properties: bg ? { show: bool(true), color: color(bg), transparency: num(0) } : { show: bool(false) } }],
    border: [{ properties: { show: bool(false) } }],
    padding: [{ properties: bg ? { top: num(14), bottom: num(14), left: num(18), right: num(18) } : { top: num(0), bottom: num(0), left: num(0), right: num(0) } }],
    dropShadow: [{ properties: { show: bool(false) } }],
  };
  if (alt) vco.general = [{ properties: { altText: str(alt) } }];
  return container(name, pos, { visualType: 'textbox', objects: { general: [{ properties: { paragraphs } }] }, visualContainerObjects: vco });
}
function accent(name, pos, hex) {
  return container(name, pos, {
    visualType: 'shape',
    objects: {
      shape: [{ properties: { tileShape: str('rectangle') }, selector: { id: 'default' } }],
      fill: [{ properties: { show: bool(true), fillColor: color(hex), transparency: num(0) }, selector: { id: 'default' } }],
      outline: [{ properties: { show: bool(false) }, selector: { id: 'default' } }],
    },
    visualContainerObjects: { background: [{ properties: { show: bool(false) } }], border: [{ properties: { show: bool(false) } }], padding: [{ properties: { top: num(0), bottom: num(0), left: num(0), right: num(0) } }], dropShadow: [{ properties: { show: bool(false) } }] },
  });
}
// insight card = accent bar + tinted textbox (insight sentence, then grey Source line)
function insight(key, r, text, source, hex = C.blue) {
  const tint = hex === C.orange ? C.orangeTint : C.blueTint;
  const bar = { ...r, width: 8 };
  const box = { ...r, x: r.x + 8, width: r.width - 8 };
  return [
    accent(hid(key + ':bar'), bar, hex),
    textbox(hid(key + ':txt'), box, [
      { textRuns: [run('What it shows', 10, { font: 'Segoe UI Semibold', col: hex })] },
      { textRuns: [run(text, r.width < 900 ? 13 : 14)] },
      { textRuns: [run(' ', 6)] },
      { textRuns: [run('Source: ' + source, 10, { col: C.muted, italic: true })] },
    ], { bg: tint, alt: text }),
  ];
}
function headline(pageKey, r, kicker, title) {
  return textbox(hid(pageKey + ':title'), r, [
    { textRuns: [run(kicker.toUpperCase(), 11, { font: 'Segoe UI Semibold', col: C.blue })] },
    { textRuns: [run(title, 22, { font: 'Segoe UI Semibold' })] },
  ]);
}
function navigator(pageKey, r) {
  const st = (state, fill, txt, bold) => ({ fill, txt, bold, state });
  const states = [st('default', C.card, C.muted, false), st('hover', C.blueTint, C.text, false), st('selected', C.blue, '#FFFFFF', true)];
  return container(hid(pageKey + ':nav'), r, {
    visualType: 'pageNavigator',
    objects: {
      layout: [{ properties: { orientation: num(0), rowCount: int(2), columnCount: int(5), cellPadding: int(2) } }],
      shape: [{ properties: { tileShape: str('rectangleRounded'), rectangleRoundedCurve: int(6) } }],
      fill: states.map((s) => ({ properties: { show: bool(true), fillColor: color(s.fill), transparency: num(0) }, selector: { id: s.state } })),
      text: states.map((s) => ({ properties: { fontFamily: str('Segoe UI'), fontSize: num(9), bold: bool(s.bold), fontColor: color(s.txt), topMargin: int(0), bottomMargin: int(0), leftMargin: int(4), rightMargin: int(4) }, selector: { id: s.state } })),
      outline: states.map((s) => ({ properties: { show: bool(true), lineColor: color(s.state === 'selected' ? C.blue : C.line), weight: num(1), transparency: num(0) }, selector: { id: s.state } })),
    },
    visualContainerObjects: { background: [{ properties: { show: bool(false) } }], border: [{ properties: { show: bool(false) } }], padding: [{ properties: { top: num(0), bottom: num(0), left: num(0), right: num(0) } }], dropShadow: [{ properties: { show: bool(false) } }], title: [{ properties: { show: bool(false) } }] },
  });
}
function kpiCard(key, r, label, measureName, definition, valueSize = 34) {
  return container(hid(key), r, {
    visualType: 'cardVisual',
    query: { queryState: { Data: { projections: [measure(measureName)] } } },
    objects: {
      value: [{ properties: { fontFamily: str('Segoe UI Semibold'), fontSize: num(valueSize), fontColor: color(C.text), labelDisplayUnits: str('1') }, selector: { id: 'default' } }],
      label: [{ properties: { show: bool(false) }, selector: { id: 'default' } }],
      accentBar: [{ properties: { show: bool(true), position: str('Left'), color: color(C.blue), width: num(6) }, selector: { id: 'default' } }],
      outline: [{ properties: { show: bool(false) }, selector: { id: 'default' } }],
    },
    visualContainerObjects: chrome({ title: label, subtitle: definition, alt: `${label}: ${definition}`, pad: [14, 14, 18, 18] }),
  });
}
const axisFont = { fontFamily: str('Segoe UI'), fontSize: num(10), labelColor: color(C.muted) };
const gridY = { gridlineShow: bool(true), gridlineStyle: str('dotted'), gridlineColor: color(C.line) };

// ---------------------------------------------------------------- extra helpers
const tableObjects = (fontSize = 12) => ({
  columnHeaders: [{ properties: { autoSizeColumnWidth: bool(true), columnAdjustment: str('growToFit'), fontFamily: str('Segoe UI Semibold'), fontSize: num(11), fontColor: color(C.text), backColor: color('#F3F2EF'), wordWrap: bool(true) } }],
  values: [{ properties: { fontFamily: str('Segoe UI'), fontSize: num(fontSize), backColorPrimary: color(C.card), backColorSecondary: color('#F9F8F6'), wordWrap: bool(true) } }],
});
// conditional colour per data point: hex when MAX(t[c]) = 1, else base
function flagColor(t, c, hex, base) {
  const cond = (v, col) => ({ Condition: { Comparison: { ComparisonKind: 0, Left: { Aggregation: { Expression: colRef(t, c), Function: 4 } }, Right: { Literal: { Value: `${v}L` } } } }, Value: { Literal: { Value: `'${col}'` } } });
  return { properties: { fill: { solid: { color: { expr: { Conditional: { Cases: [cond(1, hex), cond(0, base)], DefaultValue: { Literal: { Value: `'${base}'` } } } } } } } },
    selector: { data: [{ dataViewWildcard: { matchingOption: 1 } }] } };
}
function slicer(key, r, t, c, headerText) {
  return container(hid(key), r, {
    visualType: 'slicer',
    query: { queryState: { Values: { projections: [column(t, c)] } } },
    objects: {
      data: [{ properties: { mode: str('Dropdown') } }],
      header: [{ properties: { show: bool(true), text: str(headerText), fontFamily: str('Segoe UI Semibold'), textSize: num(10), fontColor: color(C.muted) } }],
      items: [{ properties: { fontFamily: str('Segoe UI'), textSize: num(11), fontColor: color(C.text) } }],
    },
    visualContainerObjects: { background: [{ properties: { show: bool(false) } }], border: [{ properties: { show: bool(false) } }], padding: [{ properties: { top: num(0), bottom: num(0), left: num(0), right: num(0) } }], dropShadow: [{ properties: { show: bool(false) } }], title: [{ properties: { show: bool(false) } }] },
  });
}

// ---------------------------------------------------------------- report assembly
function createReport(totalPages) {
  const pages = [];
  function page(key, displayName, kicker, title, visualsFn, { headerCols = 9 } = {}) {
    z = 0;
    const id = hid('page:' + key);
    const k = `${String(pages.length + 1).padStart(2, '0')} / ${String(totalPages).padStart(2, '0')} · ${kicker}`;
    const hdr = rect([1, 1, headerCols, 2]);
    const navR = rect([9, 1, 13, 2]);
    const nav = { ...navR, y: navR.y - 8, height: navR.height + 16 };
    const visuals = [headline(key, hdr, k, title), navigator(key, nav), ...visualsFn()];
    pages.push({ id, displayName, visuals });
  }
  return { pages, page };
}

function writeReport(REPORT, pages, themeName = 'PortfolioEditorial') {
  const DEF = path.join(REPORT, 'definition');
  if (!fs.existsSync(path.join(DEF, 'report.json'))) throw new Error('Not a .Report folder: ' + REPORT);
  const themeFile = `${themeName}-${hid(themeName + '-v1', 8)}.json`;
  const theme = {
    name: themeFile,
    dataColors: [C.blue, C.orange, C.aqua, '#0D366B', '#8DB8EC', '#52514E'],
    foreground: C.text, foregroundNeutralSecondary: C.muted, background: C.bg, backgroundLight: C.card, tableAccent: C.blue,
    maximum: C.heatHi, minimum: C.heatLo, center: '#6D9BD8', good: C.aqua, neutral: '#D9B300', bad: C.orange,
    textClasses: {
      callout: { fontSize: 34, fontFace: 'Segoe UI Semibold', color: C.text },
      title: { fontSize: 12, fontFace: 'Segoe UI Semibold', color: C.text },
      header: { fontSize: 12, fontFace: 'Segoe UI Semibold', color: C.text },
      label: { fontSize: 10, fontFace: 'Segoe UI', color: C.text },
    },
    visualStyles: {
      '*': { '*': {
        dropShadow: [{ show: false }],
        categoryAxis: [{ gridlineStyle: 'dotted', gridlineColor: { solid: { color: C.line } } }],
        valueAxis: [{ gridlineStyle: 'dotted', gridlineColor: { solid: { color: C.line } } }],
      } },
      page: { '*': { background: [{ color: { solid: { color: C.bg } }, transparency: 0 }], outspace: [{ color: { solid: { color: C.bg } } }] } },
    },
  };
  const pagesDir = path.join(DEF, 'pages');
  for (const d of fs.readdirSync(pagesDir)) { const p = path.join(pagesDir, d); if (fs.statSync(p).isDirectory()) fs.rmSync(p, { recursive: true, force: true }); }
  const write = (f, o) => { fs.mkdirSync(path.dirname(f), { recursive: true }); fs.writeFileSync(f, JSON.stringify(o, null, 2) + '\n', 'utf8'); };
  let visualCount = 0;
  for (const p of pages) {
    write(path.join(pagesDir, p.id, 'page.json'), {
      $schema: SCHEMA.page, name: p.id, displayName: p.displayName, displayOption: 'FitToPage', height: H, width: W,
      objects: { background: [{ properties: { color: color(C.bg), transparency: num(0) } }], outspace: [{ properties: { color: color(C.bg), transparency: num(0) } }] },
    });
    for (const v of p.visuals) { write(path.join(pagesDir, p.id, 'visuals', v.name, 'visual.json'), v); visualCount++; }
  }
  write(path.join(pagesDir, 'pages.json'), { $schema: SCHEMA.pages, pageOrder: pages.map((p) => p.id), activePageName: pages[0].id });
  const regDir = path.join(REPORT, 'StaticResources', 'RegisteredResources');
  fs.mkdirSync(regDir, { recursive: true });
  for (const f of fs.readdirSync(regDir)) if (f.startsWith(themeName + '-')) fs.rmSync(path.join(regDir, f));
  write(path.join(regDir, themeFile), theme);
  const reportJson = JSON.parse(fs.readFileSync(path.join(DEF, 'report.json'), 'utf8'));
  const base = reportJson.themeCollection.baseTheme;
  reportJson.themeCollection.customTheme = { name: themeFile, reportVersionAtImport: base.reportVersionAtImport, type: 'RegisteredResources' };
  reportJson.resourcePackages = (reportJson.resourcePackages || []).filter((r) => r.type !== 'RegisteredResources');
  reportJson.resourcePackages.push({ name: 'RegisteredResources', type: 'RegisteredResources', items: [{ name: themeFile, path: themeFile, type: 'CustomTheme' }] });
  write(path.join(DEF, 'report.json'), reportJson);
  console.log(JSON.stringify({ report: REPORT, pages: pages.length, visuals: visualCount, theme: themeFile }));
}

module.exports = {
  W, H, GUTTER, C, M, hid, lit, str, num, int, bool, color, measure, column, agg, colRef,
  catFilter, betweenFilter, topNFilter, rect, slot, chrome, container, run, textbox, accent, insight,
  headline, navigator, kpiCard, axisFont, gridY, tableObjects, flagColor, slicer, createReport, writeReport,
};
