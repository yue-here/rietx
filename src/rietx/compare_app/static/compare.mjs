// The `rietx compare` page (WP-1461). The figure is the chart module's
// `overlay`: every variant's cumulative Δχ² against the reference, its
// (obs − calc)/σ, and its calculated pattern over the observed points, on one
// x with the gestures every rietx chart shares. A drag zooms, the wheel zooms
// about the pointer, shift-wheel and alt-drag pan, and a double-click goes back
// to the whole pattern. `compare-core.mjs` is the half that touches no DOM.
//
// The poll carries each variant's statistics and never its curves. Those are
// fetched once per variant, packed, when the variant lands (`fetchCurves`).

import {exportButtons, hklLabel, nearest, overlay, token, unpack} from './rxplot.mjs';
import {diagnosticsHtml, esc, paramsHtml, sameGrid, statsHtml, usable,
        valueText} from './compare-core.mjs';

// One variant, one hue — a categorical set of ten, which is the one palette
// on these three pages the GUI has nothing to lend: its only categorical set
// is the history graph's five lanes, and ten hues at one lightness cannot
// clear the separability floor five at 72 degrees were chosen for. So these
// stay literals, and WP-1429 says so rather than inventing a palette nobody
// asked for. What is *not* here are the observed points, the zero line and
// the tick rows, which are Rietveld roles the GUI does answer.
const COLORS = ["#1f5fa8","#c23b22","#2e8b57","#8a5cc4","#c98a17","#0f8f9c",
                "#b3487e","#6b7280","#4b7f1f","#a1421f"];

let CATALOG = null, RECORDS = {}, POLL = null;
// The variants the last Run asked for. A poll waits for these alone: one
// ticked while a run is in flight was never requested, so waiting on it held
// Run disabled for good.
let REQUESTED = new Set();
// Each variant's unpacked curves, for the standard on screen: a Map rather
// than an object, since a later fetch never re-orders what has landed.
const CURVES = new Map();
const FETCHING = new Set();
// Variants whose channels are not the others', which no subtraction compares.
const MISMATCH = new Set();
// The figure, and the variants it was built over.
let FIG = null, FIG_KEYS = '';
// Bumped by `forget`, so a fetch answered after it draws nothing.
let GENERATION = 0;
// The tokens as they are now. The page is stamped with a theme at load, and
// the system's scheme can move under a page that follows it (`retheme`).
let PALETTE = null;

const $ = (id) => document.getElementById(id);
const chosenVariants = () =>
  [...document.querySelectorAll('#variants input:checked')].map(el => el.value);
const color = (k) => COLORS[CATALOG.variants.findIndex(v => v.key === k) % COLORS.length];
const title = (k) => (CATALOG.variants.find(v => v.key === k) || {}).title || k;

function retheme() {
  if (!CATALOG) return;
  PALETTE = {obs: token('--plot-obs'), zero: token('--plot-zero'),
             phase: [0, 1, 2, 3].map(n => token('--phase-' + n)).filter(Boolean),
             fits: {}};
  for (const v of CATALOG.variants) PALETTE.fits[v.key] = color(v.key);
  if (FIG) FIG.redraw();
}
window.matchMedia?.('(prefers-color-scheme: dark)')
  .addEventListener?.('change', () => retheme());

async function boot() {
  CATALOG = await (await fetch('/api/catalog')).json();
  retheme();
  const sel = $('standard');
  for (const s of CATALOG.standards) {
    const opt = document.createElement('option');
    opt.value = s.key;
    opt.textContent = s.available ? s.title : s.title + '  (data missing)';
    opt.disabled = !s.available;
    sel.appendChild(opt);
  }
  const first = CATALOG.standards.find(s => s.available);
  if (first) sel.value = first.key;
  // A poll waits for the variants it asked about, and the new standard's have
  // not been asked for, so it would hold Run disabled for good. The server
  // finishes the old queue and keeps it cached.
  sel.onchange = () => { stopPolling(); forget(); renderVariants(); draw(); };
  $('run').onclick = run;
  $('clear').onclick = () => { forget(); draw(); };
  $('reference').onchange = draw;
  // the figure's four exports (D6), each on what is drawn and in view now
  const exports = exportButtons(() => {
    if (!FIG) throw new Error('nothing is drawn yet');
    return FIG;
  }, {
    name: () => `compare-${$('standard').value}`,
    svgcanvas: () => import('./svgcanvas.esm.js'),
    say: text => { $('export-said').textContent = text; },
  });
  for (const b of exports) b.className = 'ghost';
  $('exports').append(...exports);
  renderVariants();
  draw();
}

// Everything drawn for the standard on screen. The server keeps its cache, so
// pressing Run again brings the same fits back without refining anything.
function forget() {
  GENERATION += 1;
  RECORDS = {};
  CURVES.clear();
  MISMATCH.clear();
  if (FIG) FIG.destroy();
  FIG = null;
  FIG_KEYS = '';
}

function currentStandard() {
  return CATALOG.standards.find(s => s.key === $('standard').value);
}

// The variant list is the figure's legend too: each carries the swatch it is
// drawn in, and unticking one hides it in every pane at once.
function renderVariants() {
  const std = currentStandard();
  $('standard-desc').textContent = std ? std.description : '';
  const box = $('variants');
  box.replaceChildren();
  for (const v of CATALOG.variants) {
    if (std && !std.variants.includes(v.key)) continue;
    const lab = document.createElement('label');
    lab.className = 'row';
    lab.innerHTML =
      `<input type="checkbox" value="${esc(v.key)}" ${v.key === 'baseline' ? 'checked' : ''}>` +
      `<span><b><span class="swatch" style="background:${color(v.key)}"></span>` +
      `${esc(v.title)}</b><span class="desc">${esc(v.description)}</span></span>`;
    lab.querySelector('input').onchange = () => { syncReference(); draw(); };
    box.appendChild(lab);
  }
  syncReference();
}

function syncReference() {
  const ref = $('reference'), previous = ref.value;
  ref.replaceChildren();
  for (const key of chosenVariants()) {
    const opt = document.createElement('option');
    opt.value = key;
    opt.textContent = title(key);
    ref.appendChild(opt);
  }
  ref.value = [...ref.options].some(o => o.value === previous)
    ? previous : (ref.options[0] ? ref.options[0].value : '');
}

async function run() {
  const standard = $('standard').value, variants = chosenVariants();
  if (!variants.length) return;
  $('run').disabled = true;
  await fetch('/api/run', {method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({standard, variants})});
  // the reader left this standard while the request was out, and its
  // `onchange` has already stopped the poll and re-enabled Run
  if ($('standard').value !== standard) return;
  REQUESTED = new Set(variants);
  if (POLL) clearInterval(POLL);
  POLL = setInterval(poll, 700);
  poll();
}

async function poll() {
  const standard = $('standard').value, variants = chosenVariants();
  const q = new URLSearchParams({standard, variants: variants.join(',')});
  const s = await (await fetch('/api/state?' + q)).json();
  if ($('standard').value !== standard) return;
  // merged, so a variant unticked while its fit ran is still there to tick again
  RECORDS = {...RECORDS, ...s.records};
  $('log').textContent = s.log.join('\n');
  $('log').scrollTop = $('log').scrollHeight;
  for (const [key, record] of Object.entries(s.records)) {
    if (usable(record)) fetchCurves(standard, key);
  }
  draw();
  const outstanding = variants.some(v => REQUESTED.has(v) && !(v in RECORDS));
  if (!outstanding && !s.busy) stopPolling();
}

function stopPolling() {
  if (POLL) clearInterval(POLL);
  POLL = null;
  $('run').disabled = false;
}

// One variant's curves, once: every channel, packed (D4). A fetch answered
// after the reader left the standard or cleared the plots is dropped.
async function fetchCurves(standard, key) {
  if (CURVES.has(key) || FETCHING.has(key) || MISMATCH.has(key)) return;
  const generation = GENERATION;
  FETCHING.add(key);
  try {
    const q = new URLSearchParams({standard, variant: key});
    const response = await fetch('/api/curves?' + q);
    if (!response.ok) return;
    const payload = unpack(await response.arrayBuffer());
    if (generation !== GENERATION) return;
    const other = CURVES.values().next().value;
    if (other && !sameGrid(other.arrays.two_theta, payload.arrays.two_theta)) {
      MISMATCH.add(key);
    } else {
      CURVES.set(key, payload);
    }
    draw();
  } finally {
    FETCHING.delete(key);
  }
}

function draw() {
  const variants = chosenVariants();
  drawFigure(variants, $('reference').value);
  $('stats').innerHTML = statsHtml(variants, RECORDS, title, color);
  $('diagnostics').innerHTML = diagnosticsHtml(variants, RECORDS, title);
  $('params').innerHTML = paramsHtml(variants, RECORDS, title);
}

// The figure is built over every variant with curves, in the catalogue's
// order, and hides the ones not ticked, so ticking one keeps the reader's
// zoom. A variant landing is a new series, which uPlot takes only at
// construction, so the figure is rebuilt then, at the x range it had.
function drawFigure(variants, refKey) {
  const keys = CATALOG.variants.map(v => v.key).filter(k => CURVES.has(k));
  const hidden = keys.filter(k => !variants.includes(k));
  const mismatch = [...MISMATCH].filter(k => variants.includes(k));
  $('mismatch').hidden = !mismatch.length;
  $('mismatch').textContent = mismatch.length
    ? `Not drawn: ${mismatch.map(title).join(', ')} fitted other channels than `
      + 'the variants drawn, so no Δχ² between them is a subtraction.' : '';
  $('figure').classList.toggle('empty', !keys.length);
  if (!keys.length) return;
  const signature = keys.join(',');
  if (signature !== FIG_KEYS) {
    const view = FIG && [FIG.panes.cum.scales.x.min, FIG.panes.cum.scales.x.max];
    if (FIG) FIG.destroy();
    FIG = build(keys, refKey, hidden);
    FIG_KEYS = signature;
    if (view) FIG.setX(...view);
    return;
  }
  FIG.setReference(CURVES.has(refKey) ? refKey : null);
  FIG.setHidden(hidden);
}

function build(keys, refKey, hidden) {
  const first = CURVES.get(keys[0]);
  const fits = keys.map(key => {
    const a = CURVES.get(key).arrays;
    return {key, calc: a.y_calc, delta: a.delta, cum: a.cumulative_chi2};
  });
  const fig = overlay(window.uPlot, $('figure'), {
    x: first.arrays.two_theta, obs: first.arrays.y_obs,
    ticks: first.header.ticks || {}, fits,
  }, {
    colors: () => PALETTE,
    reference: CURVES.has(refKey) ? refKey : null,
    hidden,
    labels: {cum: () => 'Δχ² vs ' + title($('reference').value),
             diff: () => '(obs − calc)/σ', fit: () => 'intensity'},
  });
  // each heading in front of the pane it explains
  for (const key of ['cum', 'diff', 'fit']) {
    fig.panes[key].root.parentElement.before($('head-' + key));
  }
  fig.onCursor = at => point(fig, first, keys, at);
  // the suite's handle on what was drawn (`tests/test_compare_browser.py`)
  $('figure').__rx = fig;
  return fig;
}

// The pointer's reach onto a tick, in CSS px.
const PICK = 6;

// What the pointer is over: each drawn variant's value in the pane under it,
// read off the numbers that pane drew, or the reflection under it in the tick
// band (WP-1438). DOM text over the canvas, so pointing paints no pattern.
function point(fig, first, keys, at) {
  const out = $('readout'), tip = $('tip');
  tip.hidden = true;
  if (!at) { out.replaceChildren(); return; }
  const u = fig.panes[at.key], at2t = document.createElement('span');
  at2t.className = 'at';
  // the channel the values are read at, and in the band the pointer itself
  const x = at.key === 'ticks' ? at.x : u.data[0][at.idx];
  at2t.textContent = `2θ ${x.toFixed(4)}°`;
  if (at.key === 'ticks') {
    out.replaceChildren(at2t);
    tick(fig, first, at, tip);
    return;
  }
  const parts = [at2t];
  const offset = at.key === 'fit' ? 2 : 1;
  if (at.key === 'fit') parts.push(entry(PALETTE.obs, 'observed', u.data[1][at.idx]));
  keys.forEach((key, i) => {
    if (u.series[offset + i].show) parts.push(entry(color(key), title(key), u.data[offset + i][at.idx]));
  });
  out.replaceChildren(...parts);
}

function entry(ink, name, value) {
  const span = document.createElement('span');
  span.innerHTML = `<span class="swatch" style="background:${ink}"></span>`;
  span.append(`${name} ${valueText(value)}`);
  return span;
}

function tick(fig, first, at, tip) {
  const ticks = first.header.ticks || {}, names = Object.keys(ticks);
  if (!names.length) return;
  const u = fig.panes.ticks, band = u.over.clientHeight / names.length;
  const r = Math.min(names.length - 1, Math.max(0, Math.floor(at.top / band)));
  const row = ticks[names[r]], j = nearest(row, at.x, v => u.valToPos(v, 'x'), PICK);
  if (j < 0) return;
  const hkl = (first.header.tick_hkl || {})[names[r]];
  const paired = Array.isArray(hkl) && hkl.length === row.length;
  tip.textContent = [names[r], paired ? hklLabel(hkl[j]) : null,
                     `${row[j].toFixed(4)}°`].filter(Boolean).join('\n');
  const over = u.over.getBoundingClientRect(), host = $('figure').getBoundingClientRect();
  tip.style.left = `${over.left - host.left + u.valToPos(row[j], 'x')}px`;
  tip.style.top = `${over.top - host.top + r * band}px`;
  tip.hidden = false;
}

boot();
