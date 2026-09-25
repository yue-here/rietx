// The page `rietx.viz.html.write_html` writes (WP-1461): one fit, drawn by the
// chart module, from a file with no server and no network.
//
// `html.py` inlines uPlot, the chart module, this script and the fit's numbers
// into one document. It answers the import below by putting the module's text
// before this script's in the same <script>. This script goes inside a block
// there, which is a scope of its own in a module, so a name declared here can
// never collide with one the module declares.
//
// Every choice a reader could argue with is made in Python and arrives in
// `#spec`: the title, the palette, the axis titles, the legend and which
// residual is drawn. What is left here is the DOM.

import {exportButtons, hklLabel, nearest, pattern, unpack} from '../static/rxplot.mjs';

const spec = JSON.parse(document.getElementById('spec').textContent);

/** The fit's curves, a packed body (`rietx.viz.packed`) sent as base64. */
function readCurves() {
  const text = atob(document.getElementById('curves').textContent.trim());
  const bytes = new Uint8Array(text.length);
  for (let i = 0; i < text.length; i++) bytes[i] = text.charCodeAt(i);
  const c = unpack(bytes.buffer);
  // A result carries only the channels it fitted, so both indices are every
  // channel. They are built here rather than sent.
  const every = Int32Array.from({length: c.arrays.two_theta.length}, (_, i) => i);
  c.arrays.kept = every;
  c.arrays.fitted = every;
  return c;
}

// The residual's ±3σ band, under the grid. Δ/σ has expectation 1 under a
// correct model, so the band puts the residual on an absolute statistical
// scale (Toby 2024). The watcher draws the same band.
function drawBand(u) {
  const {ctx} = u, {left, top, width, height} = u.bbox;
  const upper = Math.max(top, u.valToPos(3, 'y', true));
  const lower = Math.min(top + height, u.valToPos(-3, 'y', true));
  if (!(lower > upper)) return;
  ctx.save();
  ctx.globalAlpha = 0.15;
  ctx.fillStyle = spec.colors.band;
  ctx.fillRect(left, upper, width, lower - upper);
  ctx.restore();
}

// The legend sits inside the plot area at its top left, as the watcher's does,
// so a row it gains when the window narrows does not move the picture. Placed
// from the pane's own plot box at every paint.
function placeLegend(legend, u) {
  const r = devicePixelRatio, box = legend.style;
  const left = `${u.bbox.left / r}px`, top = `${u.bbox.top / r}px`;
  const width = `${u.bbox.width / r}px`;
  if (box.left !== left) box.left = left;
  if (box.top !== top) box.top = top;
  if (box.maxWidth !== width) box.maxWidth = width;
}

/** A number as the readout prints it, or a dash for a gap. */
function num(v, digits) {
  return v == null || !Number.isFinite(v) ? '–' : v.toFixed(digits);
}

const host = document.getElementById('plot');
const readout = document.getElementById('readout');
const legend = host.appendChild(document.createElement('div'));
legend.className = 'legend';

const curves = readCurves();
const hidden = new Set();
const residKey = spec.residual === 'weighted' ? 'delta' : 'delta_raw';

const fig = pattern(window.uPlot, host, curves, {
  colors: () => spec.colors,
  residual: spec.residual,
  labels: {y: () => spec.labels.y, resid: () => spec.labels.resid},
  layers: {main: {over: [(u) => placeLegend(legend, u)]},
           resid: {under: spec.band ? [drawBand] : []}},
});

for (const entry of spec.legend) {
  const button = legend.appendChild(document.createElement('button'));
  button.type = 'button';
  button.className = entry.mark;
  button.dataset.id = entry.id;
  button.style.setProperty('--ink', entry.ink);
  button.title = `show or hide ${entry.label}`;
  button.setAttribute('aria-pressed', 'true');
  button.append(document.createElement('i'), entry.label);
  button.onclick = () => {
    if (!hidden.delete(entry.id)) hidden.add(entry.id);
    button.setAttribute('aria-pressed', String(!hidden.has(entry.id)));
    fig.setHidden([...hidden]);
  };
}

// The pointer's reach onto a tick, in CSS px.
const PICK = 6;

/** What the readout says with the pointer over the tick band: the reflection under it. */
function tickText(at) {
  const names = Object.keys(curves.header.ticks ?? {});
  if (!names.length) return '';
  const u = fig.panes.ticks, band = u.over.clientHeight / names.length;
  const name = names[Math.min(names.length - 1, Math.max(0, Math.floor(at.top / band)))];
  if (hidden.has(`ticks:${name}`)) return '';
  const row = curves.header.ticks[name];
  const j = nearest(row, at.x, (v) => u.valToPos(v, 'x'), PICK);
  if (j < 0) return '';
  const hkl = curves.header.tick_hkl?.[name]?.[j];
  return `${name}  ${hkl ? `${hklLabel(hkl)}  ` : ''}2θ ${num(row[j], 4)}°`;
}

fig.onCursor = (at) => {
  if (!at) { readout.textContent = ''; return; }
  if (at.key === 'ticks') { readout.textContent = tickText(at); return; }
  const a = curves.arrays, i = at.idx;
  readout.textContent = `2θ ${num(a.two_theta[i], 4)}°   obs ${num(a.y_obs[i], 1)}   `
    + `calc ${num(a.y_calc?.[i], 1)}   ${spec.labels.resid} ${num(a[residKey]?.[i], 2)}`;
};

// The four exports (D6). svgcanvas is inlined in a module of its own, which
// leaves its `Context` on the window, and the file is named after itself.
document.getElementById('exports').append(...exportButtons(() => fig, {
  name: () => decodeURIComponent(location.pathname.split('/').pop()).replace(/\.html?$/i, '') || 'figure',
  svgcanvas: async () => window.rxSvgcanvas,
  say: (text) => { readout.textContent = text; },
}));

// the suite's handle on what was drawn (`tests/test_html_browser.py`)
host.__rx = fig;
