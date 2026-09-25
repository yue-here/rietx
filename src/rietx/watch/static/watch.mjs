// The `rietx watch` page, the half that owns the document (WP-1430).
//
// A module script, so nothing here is a global. The functions that touch no
// DOM are next door in `watch-core.mjs`, where the suite can call them. The
// picture is drawn by `rxplot.mjs`, the chart module every browser page draws
// with (WP-1461), over the uPlot `index.html` loads before this.
import {LAYOUT_DEFAULT, ago, axisOf, clampSize, clock, curvesOf, deltaRange,
        deltaTitle, dragged, esc, guiReason, hasBackground, intensityRange,
        legendOf, nextLayout, num, parseLayout, pct, rowName, sizeField,
        paletteFrom, runLabel, runTitle, tickText} from './watch-core.mjs';
import {exportButtons, nearest, pattern} from './rxplot.mjs';

const $ = id => document.getElementById(id);
let SINGLE = null;          // set when the served directory is itself a run
let CAN_CANCEL = false;     // false under --read-only: no button is drawn
let CAN_OPEN_GUI = false;   // the same, for the launch verb (WP-1428)
// what the strip says after a stop was asked for, or after one was refused.
// A fit does not stop the instant the button is clicked — a cadence plus the
// residual evaluation in flight, which on a large pattern is the larger term —
// and a page that showed nothing in between would read as one that had missed
// the click
let notice = null;
let timer = null;
let tail = {offset: 0, inode: null, id: null, skipped: 0, cold: true,
            above: false};
// what the run panel was built for: the run, which kind of picture it has
// ('json', a legacy 'html' page, or 'none'), and which write we have drawn
let shell = {id: null, kind: null, mtime: null};
// the last list the server sent, by id: the run panel reads its run from
// here rather than fetching it again
let rows = new Map();
let newest = null;
// The figure on screen, and the run and stage it shows (`drawSnapshot`).
let chart = null;
// What this build is called, read off the first `api/runs` (WP-1430). It was
// a `@TOKEN@` substitution into the page's text while the page was a python
// string; a file cannot carry one, and a literal here would be a second
// authority for a fact `_about.py` already owns.
let DIST = '';              // the distribution name
// The theme *choice* stored in `settings.json`, as it was last applied here.
// The page never writes it: the GUI owns the setting, this page follows it,
// and `null` is "nothing applied yet" rather than a choice.
let THEME = null;
// the console is a tail and not an archive; the log on disk is the archive.
// It is also what the route is asked to cap at (`pumpEvents`): the pane's
// length is the one authority for how many lines are worth sending, and a
// second copy of the number in python would be a second answer to that.
const MAX_LINES = 2000;
//: WP-1423's `{runs, run}`, read once at boot and then removed: the shape
//: WP-1425 stores is not that one, so it takes a name of its own rather than
//: a version field.
const PANELS_KEY = 'rietx-watch-panels';
const LAYOUT_KEY = 'rietx-watch-layout';

// ------------------------------------------------------------- stopwatch
// What one poll costs, on the page's own timeline (WP-1427).
//
// `performance.measure` with an explicit start is the browser's documented way
// to name a span, it costs about a microsecond, and it lands in the profiler's
// User Timing track where a human debugging a slow poll would already be
// looking. The suite reads the same entries through `getEntriesByType`, which
// is why the names are stable strings: `net` is the wire, `parse` is JSON, and
// everything after those two is this page's own work.
//
// The timeline is cleared every `MARK_CAP` spans. Nothing else here clears it,
// and a page left open overnight would otherwise grow one entry per span per
// poll for as long as the fit runs. About a minute of history is what a reader
// or a test ever asks for.
const MARK_CAP = 400;
let marks = 0;
function since(name, t0) {
  try {
    performance.measure(name, {start: t0});
    if (++marks > MARK_CAP) { performance.clearMeasures(); marks = 0; }
  } catch { /* no timeline here, and the page is no worse for it */ }
}

// text is written only when it changed: assigning the same string still
// replaces the node, and a replaced node is a layout
function setText(el, s) {
  if (el.textContent !== s) el.textContent = s;
}
function setAttr(el, name, value) {
  if (value === null || value === undefined) {
    if (el.hasAttribute(name)) el.removeAttribute(name);
  } else if (el.getAttribute(name) !== String(value)) {
    el.setAttribute(name, value);
  }
}
function setPill(el, live) {
  setText(el, live.state);
  setAttr(el, 'class', 'state ' + live.state);
  setAttr(el, 'title', live.evidence);
}

// ---------------------------------------------------------------- list
function makeRow(run) {
  const tr = document.createElement('tr');
  tr.className = 'run';
  tr.dataset.id = run.run_id;
  tr.innerHTML = '<td><span class="state"></span></td><td></td>' +
    '<td class="c-stage"></td>' +
    '<td class="num"></td><td class="num"></td>' +
    '<td class="muted c-started"><time></time></td>' +
    '<td class="gui"><button hidden>open</button>' +
    '<span class="why muted" hidden>\u2014</span></td>';
  tr.onclick = () => { location.hash = '#/run/' + run.run_id; };
  // The button is inside the row, and the row navigates on click. The handler
  // stops that one rather than adding to it, because `openGui` selects the run
  // itself and for a reason: its notice has nowhere to appear otherwise. One
  // place decides, and it is the one that knows why.
  tr.lastElementChild.firstElementChild.onclick = ev => {
    ev.stopPropagation();
    openGui(run.run_id);
  };
  return tr;
}

// Three cells hold a name somebody else chose — the label, the series label
// it now carries, and the stage — so each declares a `title` and is allowed
// to run out of column. The three the page fills itself are sized to fit in
// `watch.css`, and the browser test measures that they do.
function fillRow(tr, run) {
  const st = run.status || {};
  const td = tr.children;
  setPill(td[0].firstElementChild, run.liveness);
  setText(td[1], rowName(run));
  setAttr(td[1], 'title', runTitle(run));
  setText(td[2], st.stage || '—');
  setAttr(td[2], 'title', st.stage || null);
  setText(td[3], pct(st.rwp, 2));
  setText(td[4], num(st.gof, 2));
  // Drawn for a run that is inside a project, which is what `gui_command`
  // being non-null means, and only where this watcher performs the verb at
  // all. A run recorded by a bare `fit()` has no project to copy (WP-1428).
  const gui = td[6].firstElementChild;
  gui.hidden = !(CAN_OPEN_GUI && run.gui_command);
  setAttr(gui, 'title', run.gui_command
    ? 'Open a copy of this project in the ' + DIST + ' GUI. The copy is '
      + 'frozen at the click and does not follow the fit, and the project '
      + 'this run is writing is not touched.'
    : null);
  // and where there is no button, why there is none
  const why = guiReason(run, CAN_OPEN_GUI);
  const dash = td[6].lastElementChild;
  dash.hidden = !why;
  setAttr(dash, 'title', why);
  const when = td[5].firstElementChild;
  setText(when, clock(run.created));
  setAttr(when, 'datetime', run.created
    ? new Date(run.created * 1000).toISOString() : null);
  setAttr(when, 'title', run.created
    ? new Date(run.created * 1000).toLocaleString() + ' · ' + ago(run.created)
    : null);
}

// The highlight is the one thing on the list that follows the *URL* rather
// than the files, so it has one authority of its own and `patchList` is not
// it. A click changes nothing on disk, so the poll after it is a 304 and the
// patch never runs — in a directory of finished runs nothing would move the
// highlight off the row the reader just left, ever.
function markSelected() {
  const id = currentId();
  for (const tr of $('rows').children) {
    tr.classList.toggle('selected', tr.dataset.id === id);
  }
}

// Patched, never rebuilt: a row is keyed by its run id and moved into the
// server's order, so a list longer than the window keeps its scroll and a
// row the pointer is on keeps its hover. Rebuilding the table on every poll
// threw both away twenty-one times in a 25 s probe (WP-1423).
// The first row the reader can still see, or null when the list is at its top.
// Chosen by rectangle, which is what "on screen" means, and reported as an
// `offsetTop`, which is a position in the flow and so survives the scrolling
// this is about to do.
function visibleAnchor(tbody, box) {
  if (box.scrollTop <= 0) return null;
  const top = box.getBoundingClientRect().top;
  return [...tbody.children].find(tr =>
    tr.getBoundingClientRect().bottom > top) || null;
}

function patchList(runs) {
  const tbody = $('rows');
  const box = $('runs');
  // Hold the reader's place across an arrival. A new run is prepended, so
  // every row below it moves down a row's height and the whole list shifts
  // under the eye: one arrival on a scrolled list scored 0.0134 of layout
  // shift across four rows (WP-1426). The chat-log answer is to anchor on a
  // row the reader can see and move the scroll by however far that row moved.
  // Insertions above it are then compensated exactly, and an insertion below
  // it, which moves it not at all, is left alone. A list already at its top is
  // also left alone: there the arriving run is the thing being watched for,
  // and holding the viewport would scroll it straight out of sight.
  const anchor = visibleAnchor(tbody, box);
  const was = anchor ? anchor.offsetTop : 0;
  const want = new Set(runs.map(r => r.run_id));
  for (const tr of [...tbody.children]) {
    if (!want.has(tr.dataset.id)) tr.remove();
  }
  runs.forEach((run, i) => {
    let tr = tbody.querySelector(`tr[data-id="${run.run_id}"]`);
    if (!tr) tr = makeRow(run);
    const at = tbody.children[i] || null;
    if (at !== tr) tbody.insertBefore(tr, at);
    fillRow(tr, run);
  });
  $('empty').hidden = runs.length > 0;
  markSelected();
  // a row the walk dropped cannot say where it went, and the reader has lost
  // that place whatever we do
  if (anchor && anchor.isConnected && anchor.offsetTop !== was) {
    box.scrollTop += anchor.offsetTop - was;
  }
}

// -------------------------------------------------------------- run
function pictureKind(run) {
  if (run.has_snapshot) return 'json';
  if (run.has_legacy_snapshot) return 'html';
  return 'none';
}

// The picture alone. A run that had no snapshot when it was opened grows one
// at its first stage boundary, and the kind changing from 'none' to 'json' is
// what brings us back here.
function buildPicture(run, kind) {
  const picture = $('picture');
  // the figure's ResizeObserver outlives its div unless it is let go
  destroyChart();
  picture.innerHTML = kind === 'json'
    ? '<div id="plot"></div>'
    : kind === 'html'
      ? `<iframe id="plot" src="${legacySrc(run)}"></iframe>`
      : '<div id="noplot">no picture here — this run wrote only its log</div>';
  $('run').classList.toggle('full', kind === 'none');
  // mtime null, never the run's: the shell is empty until something draws
  // into it, and carrying the run's write time here would say it had
  shell = {id: run.run_id, kind: kind, mtime: null};
  setText($('s-where'), whereOf(run));
  setAttr($('s-where'), 'title', whereOf(run) || null);
}

// The console belongs to the run, not to the picture, so a tail is reset when
// the log it is following changes and not when the picture is rebuilt. The two
// shared a builder until WP-1426: a run opened before its first snapshot had
// its console wiped and re-fetched from offset 0 at that first stage boundary,
// 121 lines out and 121 back for no change, and a reader who had scrolled up
// to read was dropped at the bottom. The other reset is the route's, in
// `pumpEvents`, where a log that is a different file says so.
function resetTail(id) {
  // `cold` is the *first* ask for this run's log, which the route answers from
  // the end of the file rather than from the start (WP-1438). A log viewer
  // opens at the newest line — `kubectl logs --tail`, `less +G` — and this one
  // used to walk forward 4 MB a poll, so opening a job that had been running a
  // while showed events minutes old until the walk caught up.
  tail = {offset: 0, inode: null, id: id, skipped: 0, cold: true,
          above: false};
  $('console').textContent = '';
}

// the mtime is in the URL rather than a cache-buster of its own: the same
// page keeps the same src, so the frame reloads exactly when the file was
// rewritten and not once a second
function legacySrc(run) {
  return `api/run/${run.run_id}/legacy?t=` + (run.snapshot_mtime || 0);
}

// The colours as they are *now*, off the root element's custom properties
// (WP-1429). A theme change restyles the page by CSS alone, and a canvas keeps
// whatever it was painted with, so they are read again whenever the theme
// moves (`retheme`), and never held from boot.
function hues() {
  const style = getComputedStyle(document.documentElement);
  return paletteFrom(name => style.getPropertyValue(name));
}

// Follow the GUI's stored choice: stamp an explicit one on the root, and let
// `system` fall through to the `prefers-color-scheme` block `tokens.css`
// declares — no server can see the machine the page is open on, and CSS
// answers that question correctly without being asked. Returns whether the
// stamp moved, which is what tells the caller to repaint the canvas.
function applyTheme(choice) {
  if (choice === THEME) return false;
  THEME = choice;
  const root = document.documentElement;
  if (choice === 'light' || choice === 'dark') root.dataset.theme = choice;
  else delete root.dataset.theme;
  for (const button of document.querySelectorAll('#theme button')) {
    button.setAttribute('aria-pressed', String(button.dataset.choice === choice));
  }
  return true;
}

// ------------------------------------------------------------- picture
// The pattern is the GUI's own figure (`rxplot.pattern`): the observed points
// over the model, a band of reflection ticks, and Δ/σ under both, with the
// GUI's gestures. A drag zooms, the wheel zooms about the pointer, shift-wheel
// and alt-drag pan, and a double-click goes back to the whole pattern. What
// only this page has is laid over the figure: the ±3σ band, a legend, the
// count of points drawn, and the reflection under the pointer.
//
// A stage of the run on screen is new numbers for the same figure, so the
// reader's zoom and the curves they hid survive it, which is the whole reason
// the picture stopped being a page that reloads (WP-1402). Another run is a
// new figure.

// The ink of every mark about the data (`hues`), and the chart's `colors()`.
// Held, because the chart asks for it once per curve per paint; read again
// whenever the theme moves (`retheme`).
let hue = null;
let palette = null;
function retheme() {
  hue = hues();
  // the masked arm is empty here: a snapshot holds the fitted channels only
  palette = {...hue, masked: hue.obs};
  if (chart) chart.fig.redraw();
}
// "Follow the system" is answered by CSS, which repaints the chrome and not
// the canvas, so the canvas is repainted when the system's answer moves.
window.matchMedia?.('(prefers-color-scheme: dark)')
  .addEventListener?.('change', () => retheme());

// The picture's four exports (D6), behind one word in the bar, which keeps
// its one row at the narrowest window. Each acts on the stage on screen, at
// the reader's zoom.
function armExports() {
  const said = document.createElement('output');
  $('export-menu').append(...exportButtons(() => {
    if (!chart) throw new Error('no picture on screen');
    return chart.fig;
  }, {
    name: () => `rietx-${chart ? chart.id : 'run'}`,
    svgcanvas: () => import('./svgcanvas.esm.js'),
    say: text => { said.textContent = text; },
  }), said);
}

function destroyChart() {
  if (chart) chart.fig.destroy();
  chart = null;
}

// An element laid over the figure, in the plot's own coordinates.
function overlay(div, name) {
  const el = document.createElement('div');
  el.className = name;
  div.appendChild(el);
  return el;
}

// The curves not drawn: the ones the reader hid, and a background the stage
// has not got (`hasBackground`), which has no legend entry to bring it back.
function hiddenOf(state) {
  const hidden = [...state.hidden];
  if (!hasBackground(state.snap)) hidden.push('bkg');
  return hidden;
}

// The residual's ±3σ band, under the grid. Δ/σ has expectation 1 under a
// correct model, so the band puts the residual on an absolute statistical
// scale (Toby 2024), and it is the band `viz/html.py` draws.
function drawBand(u) {
  const {ctx} = u, {left, top, width, height} = u.bbox;
  const upper = Math.max(top, u.valToPos(3, 'y', true));
  const lower = Math.min(top + height, u.valToPos(-3, 'y', true));
  if (!(lower > upper)) return;
  ctx.save();
  ctx.globalAlpha = 0.15;
  ctx.fillStyle = palette.band;
  ctx.fillRect(left, upper, width, lower - upper);
  ctx.restore();
}

// The legend sits inside the plot area at its top left, never above it. A
// legend in the flow takes its rows out of the picture, and the picture then
// moves whenever the legend gains a row (WP-1426 measured both ways it gains
// one: the window narrows and the row wraps, or a stage frees the background
// and adds an entry). Its width is the plot area's, so it wraps inside the
// picture rather than past it. Placed from the pane's own plot box at every
// paint, and written only when that box moved.
function placeLegend(state, u) {
  const r = devicePixelRatio, box = state.legend.style;
  const left = `${u.bbox.left / r}px`, top = `${u.bbox.top / r}px`;
  const width = `${u.bbox.width / r}px`;
  if (box.left !== left) box.left = left;
  if (box.top !== top) box.top = top;
  if (box.maxWidth !== width) box.maxWidth = width;
}

function legendEntry(state, entry) {
  const button = document.createElement('button');
  button.type = 'button';
  button.className = entry.mark;
  button.dataset.id = entry.id;
  // a property and not its value, so a theme switch restyles the swatch
  button.style.setProperty('--ink', `var(${entry.ink})`);
  button.title = `show or hide ${entry.label}`;
  button.append(document.createElement('i'), entry.label);
  button.onclick = () => {
    if (!state.hidden.delete(entry.id)) state.hidden.add(entry.id);
    state.fig.setHidden(hiddenOf(state));
    fillOverlays(state);
  };
  return button;
}

// The legend and the caption for the stage on screen. The legend is rebuilt
// only when its entries changed, since a poll rebuilds nothing (WP-1423).
function fillOverlays(state) {
  const entries = legendOf(state.snap);
  const key = JSON.stringify(entries);
  if (key !== state.legendKey) {
    state.legendKey = key;
    state.legend.replaceChildren(...entries.map(e => legendEntry(state, e)));
  }
  for (const button of state.legend.children) {
    setAttr(button, 'aria-pressed', String(!state.hidden.has(button.dataset.id)));
  }
  // How much of the pattern is on screen, under the axis it is a fact about.
  // It sat in the status strip until WP-1424, and at the picture's top right
  // until WP-1438, which is where the legend's first row ends.
  setText(state.caption,
          `${state.snap.n_drawn} of ${state.snap.n_points} pts drawn`);
}

// The pointer's reach onto a tick, in CSS px.
const PICK = 6;

// Which reflection is under the pointer in the tick band (WP-1438): the row
// the pointer's height falls in, then that row's nearest tick within reach.
// A DOM label over the canvas, so pointing paints no pattern.
function hoverTick(state, at) {
  const tip = state.tip;
  const names = Object.keys(state.snap.ticks || {});
  if (!at || at.key !== 'ticks' || !names.length) {
    tip.hidden = true;
    return;
  }
  const u = state.fig.panes.ticks;
  const band = u.over.clientHeight / names.length;
  const r = Math.min(names.length - 1, Math.max(0, Math.floor(at.top / band)));
  const row = state.snap.ticks[names[r]];
  const j = state.hidden.has(`ticks:${names[r]}`) ? -1
    : nearest(row.two_theta, at.x, v => u.valToPos(v, 'x'), PICK);
  if (j < 0) {
    tip.hidden = true;
    return;
  }
  setText(tip, tickText(row, j));
  const over = u.over.getBoundingClientRect();
  const plot = state.div.getBoundingClientRect();
  tip.style.left = `${over.left - plot.left + u.valToPos(row.two_theta[j], 'x')}px`;
  tip.style.top = `${over.top - plot.top + r * band}px`;
  tip.hidden = false;
}

function makeChart(id, snap) {
  const div = $('plot');
  // an empty host: a figure given up on can have left its overlays behind
  div.replaceChildren();
  if (!palette) retheme();
  const state = {id: id, div: div, snap: snap, hidden: new Set(),
                 ladder: deltaRange(snap.delta), legendKey: null};
  state.legend = overlay(div, 'legend');
  state.caption = overlay(div, 'caption');
  state.tip = overlay(div, 'tip');
  state.tip.hidden = true;
  state.fig = pattern(window.uPlot, div, curvesOf(snap), {
    colors: () => palette,
    hidden: hiddenOf(state),
    labels: {y: () => 'intensity',
             resid: () => deltaTitle(state.snap.weighted)},
    // Both y ranges are this page's (`watch-core.mjs`): the intensity is the
    // observed points' in view, and Δ/σ is a ladder rung for the stage. A
    // range the reader drags still holds over either until a double-click.
    ranges: {
      main: u => {
        const obs = u.data[1], idxs = u.series[0].idxs;
        const i0 = idxs?.[0] ?? 0, i1 = idxs?.[1] ?? obs.length - 1;
        return intensityRange(obs.slice(i0, i1 + 1));
      },
      resid: () => state.ladder,
    },
    layers: {main: {over: [u => placeLegend(state, u)]},
             resid: {under: [drawBand]}},
  });
  state.fig.onCursor = at => hoverTick(state, at);
  fillOverlays(state);
  // the suite's handle on what was drawn (`tests/test_watch_browser.py`):
  // uPlot's scales are the ranges the axes were painted with
  div.__rx = state.fig;
  return state;
}

function updateChart(state, snap) {
  state.snap = snap;
  state.ladder = deltaRange(snap.delta);
  state.tip.hidden = true;
  state.fig.setCurves(curvesOf(snap), true);
  state.fig.setHidden(hiddenOf(state));
  fillOverlays(state);
}

// True when this write is dealt with — drawn, or deliberately given up on
// (the reader moved on). False is "not drawn yet", and the caller leaves the
// write uncommitted so the next poll tries again: a dropped fetch on the last
// stage of a fit would otherwise leave the previous stage's picture up for
// good, there being no later write to notice.
async function drawSnapshot(id) {
  // a poll can reach here before the first `api/runs` has answered, and an
  // undrawn write is what `false` already means: the next poll draws it,
  // rather than this one painting before the stored theme is applied
  if (!DIST) return false;
  if (!$('plot') || currentId() !== id) return true;
  let snap;
  try {
    const t0 = performance.now();
    const r = await fetch(`api/run/${id}/snapshot`, {cache: 'no-store'});
    if (!r.ok) return false;
    since('snap:net', t0);
    const t1 = performance.now();
    snap = await r.json();
    since('snap:parse', t1);
  } catch (err) {
    return false;                      // the console tail is not the plot's
  }
  if (currentId() !== id || !$('plot')) return true;
  const drawn = performance.now();
  try {
    if (chart && chart.id === id && chart.div === $('plot')) {
      updateChart(chart, snap);
    } else {
      destroyChart();
      chart = makeChart(id, snap);
    }
  } catch (err) {
    // A picture that cannot be drawn is given up on for this write, never
    // let through: thrown, it would skip `pumpEvents` and stop the console.
    console.error(err);
    return true;
  }
  since('snap:draw', drawn);
  setText($('s-where'), whereOf(rows.get(id)));
  setAttr($('s-where'), 'title', whereOf(rows.get(id)) || null);
  return true;
}

// The one thing in this slot a reader would type. The path it used to carry
// is the label's tooltip, where it is not competing for a track, and the
// point count it used to share the slot with is on the picture, which is
// what the count is about (WP-1424).
function whereOf(run) {
  return (run && run.gui_command) || '';
}

// Every slot that can be cut names itself in a `title`, because the width
// the strip has is the run panel's and the reader did not choose it. The
// slots the page fills itself are declared wide enough in `watch.css` and
// are never dropped.
function fillStrip(run) {
  const st = run.status || {};
  setPill($('s-state'), run.liveness);
  setText($('s-label'), runLabel(run));
  setAttr($('s-label'), 'title', runTitle(run));
  const series = st.series_index != null
    ? `pattern ${st.series_index + 1}/${st.series_n || '?'} ` +
      `${st.series_label || ''} ${st.series_pass || ''}`.trim()
    : '';
  setText($('s-series'), series);
  setAttr($('s-series'), 'title', series || null);
  const stage = st.stage
    ? (st.index != null ? `stage ${st.index}/${st.n_stages || '?'} ` : 'stage ')
      + st.stage
    : '';
  setText($('s-stage'), stage);
  setAttr($('s-stage'), 'title', stage || null);
  setText($('s-rwp'), st.rwp != null ? 'Rwp ' + pct(st.rwp, 2) : '');
  setText($('s-gof'), st.gof != null ? 'GoF ' + num(st.gof, 2) : '');
  setText($('s-free'), st.n_free != null ? st.n_free + ' free' : '');
  setText($('s-notice'), notice ? notice.text : '');
  // Drawn only for a run being written *here*: a terminal one has nothing
  // to stop, and 'unknown' covers both another host and a writer that keeps
  // no lock, where a request would sit in the directory doing nothing. The
  // route refuses the same set, so this is the courtesy and not the check.
  // Hidden while the *stop* flow has something to say — a request in flight,
  // or a refusal still on screen. Not for every notice: the GUI launch puts
  // one up for as long as a python interpreter takes to start (WP-1428), and
  // it has nothing to do with whether this fit can still be stopped.
  $('stop').hidden = !(CAN_CANCEL && !(notice && notice.kind === 'stop')
                       && run.liveness.state === 'running');
}

function clearStrip() {
  setPill($('s-state'), {state: 'unknown', evidence: 'no run'});
  for (const id of ['s-label', 's-series', 's-stage', 's-rwp', 's-gof',
                    's-free', 's-where', 's-notice']) {
    setText($(id), '');
    // the tooltip goes with the text it was explaining, or the strip keeps
    // answering questions about a run it is no longer showing
    setAttr($(id), 'title', null);
  }
  setText($('s-label'), 'no run');
  $('stop').hidden = true;
  if (shell.id !== null) {
    destroyChart();
    $('picture').innerHTML = '';
    shell = {id: null, kind: null, mtime: null};
    // the tail goes with the console it was filling, or a reader who came
    // back to this run would meet an empty console no poll ever refilled
    resetTail(null);
  }
}

async function drawRun(id) {
  const run = rows.get(id);
  if (!run) {                          // gone from the walk, or never in it
    if (location.hash) location.hash = '';
    clearStrip();
    return;
  }
  // a notice belongs to one run and one moment: the stop one stands until the
  // fit stops, a refusal clears on its own clock, and neither follows the
  // reader to another run
  if (notice && (notice.id !== id || Date.now() > notice.expires
                 || (notice.stop && run.liveness.state !== 'running'))) {
    notice = null;
  }
  // a running fit rewrites its snapshot per stage, and a run that had none
  // when it was opened grows one at its first
  const kind = pictureKind(run);
  if (tail.id !== id) resetTail(id);
  if (shell.id !== id || shell.kind !== kind) buildPicture(run, kind);
  fillStrip(run);
  // the write is recorded once it is on the page, never before: a draw that
  // did not happen must stay outstanding for the next poll
  if (kind !== 'none' && run.snapshot_mtime !== shell.mtime) {
    if (kind === 'json') {
      if (await drawSnapshot(id)) shell.mtime = run.snapshot_mtime;
    } else {
      shell.mtime = run.snapshot_mtime;
      const frame = $('plot');
      if (frame) frame.src = legacySrc(run);
    }
  }
  await pumpEvents(id);
}

// ----------------------------------------------------------------- stop
// Two clicks, and no keyboard shortcut of any kind: nothing takes focus when
// this opens, and neither Enter nor Escape reaches either button. Confirming
// raises an exception in a process the reader cannot see, and a stray
// keystroke must not be able to do that.
function openConfirm(run) {
  const st = run.status || {};
  const box = $('confirm');
  $('box-what').textContent =
    'Stop ' + run.label + (st.stage ? ', in stage ' + st.stage : '')
    + ', in the process that is running it?';
  $('box-no').onclick = () => { box.hidden = true; };
  $('box-yes').onclick = () => {
    box.hidden = true;
    stopRun(run.run_id);
  };
  box.hidden = false;
}

// The runs a launch is outstanding for. A second click while the first is in
// flight is a second GUI, a second scratch copy and a second port, and a
// python interpreter takes long enough to start that the second click is the
// ordinary thing to do rather than the careless one.
const launching = new Set();

// The launch takes about a second, most of it a python interpreter starting
// (WP-1428 measured 0.58-0.89 s). So the notice goes up first: without it the
// click looks like it did nothing.
async function openGui(id) {
  if (launching.has(id)) return;
  launching.add(id);
  // Select the run first. A notice belongs to one run and `drawRun` drops one
  // that is not the run on screen, so a launch from a row the reader is not
  // looking at would report neither its progress nor its refusal.
  if (currentId() !== id) location.hash = '#/run/' + id;
  try {
    setNotice({id: id, kind: 'gui',
               text: 'opening a copy in the ' + DIST + ' GUI …',
               stop: false, expires: Date.now() + 90000});
    let payload = null, ok = false;
    try {
      const r = await fetch(`api/run/${id}/gui`, {method: 'POST'});
      ok = r.ok;
      payload = await r.json();
    } catch (err) {
      payload = {error: String(err)};
    }
    if (ok && payload && payload.url) {
      // a new tab, and the url stays in the strip: a popup blocker eats this
      // silently, and a reader with no tab and no url has nothing to go on
      window.open(payload.url, '_blank', 'noopener');
      setNotice({id: id, kind: 'gui',
                 text: 'a frozen copy is open at ' + payload.url,
                 stop: false, expires: Date.now() + 20000});
    } else {
      setNotice({id: id, kind: 'gui',
                 text: (payload && payload.error) || 'the GUI was refused',
                 stop: false, expires: Date.now() + 8000});
    }
  } finally {
    launching.delete(id);
  }
}

// A notice is drawn now, not on the next poll. `refresh` returns without doing
// anything while a poll is already in flight, so a notice that only asked for
// one could sit unseen for the length of that poll — which is exactly the wait
// it exists to explain. The poll is still asked for, because a notice is not
// the only thing that moved.
function setNotice(next) {
  notice = next;
  const run = rows.get(currentId());
  if (run) fillStrip(run);
  refresh();
}

async function stopRun(id) {
  let payload = null, ok = false;
  try {
    const r = await fetch(`api/run/${id}/cancel`, {method: 'POST'});
    ok = r.ok;
    payload = await r.json();
  } catch (err) {
    payload = {error: String(err)};
  }
  setNotice(ok
    ? {id: id, kind: 'stop', text: 'stopping at the next evaluation …',
       stop: true, expires: Infinity}
    : {id: id, kind: 'stop',
       text: (payload && payload.error) || 'the stop was refused',
       stop: false, expires: Date.now() + 8000});
}

// The class on the one element in the console that is not a line of the log.
const GAP = 'gap';

// A note about the pane rather than a line in it, so it does not count against
// the pane's length and is never what the trim cuts. Cumulative, because two
// capped polls skipped two batches and the reader wants the total.
//
// Two shapes, and which one is a question about what the page can count. A
// poll that read the whole log and dropped the oldest of it knows exactly how
// many. A *cold open* seeked to the end instead (WP-1438), so lines above the
// seek were never read: the count it does have is of the window alone and
// would be a number smaller than the truth, stated as the truth. It says the
// fact without the figure instead.
function noteGap(pane) {
  if (!tail.skipped && !tail.above) return;
  const text = tail.above
    ? '… earlier lines are in the log and not in this pane'
    : `… ${tail.skipped.toLocaleString()} earlier lines are in the `
      + `log and not in this pane`;
  const first = pane.firstElementChild;
  if (first && first.classList.contains(GAP)) { setText(first, text); return; }
  const note = document.createElement('div');
  note.className = `line muted ${GAP}`;
  note.textContent = text;
  pane.insertBefore(note, first);
}

// One removal at a time is right for a poll's worth of arrivals and wrong for
// a pane being replaced wholesale, which is what a capped batch is.
function trimConsole(pane) {
  const gap = pane.firstElementChild?.classList.contains(GAP) ? 1 : 0;
  const cap = MAX_LINES + gap;
  if (pane.childElementCount - cap > MAX_LINES / 2) {
    const keep = [...pane.children].slice(-MAX_LINES);
    pane.replaceChildren(...(gap ? [pane.firstElementChild, ...keep] : keep));
    return;
  }
  while (pane.childElementCount > cap) {
    (gap ? pane.children[1] : pane.firstElementChild).remove();
  }
}

// The log is read by one fetch at a time and a second ask *waits* rather
// than racing: two in flight would take the same `tail.offset` and append
// the same lines twice. Nothing could race before WP-1438, `refreshing`
// being one poll at a time; the boot asking for a pinned run's log before
// the walk is what made two possible.
let pumping = Promise.resolve();
function pumpEvents(id) {
  const next = pumping.then(() => pumpTail(id), () => pumpTail(id));
  // the chain never latches on a rejection, so one failed poll does not stop
  // the log for the life of the page
  pumping = next.catch(() => {});
  return next;
}

async function pumpTail(id) {
  // re-asked on the way in as well as after the fetch: a queued pump for a
  // run the reader has already left should not spend the round trip
  if (tail.id !== id || currentId() !== id) return;
  // `limit` is the pane's own length. Without it a reader clicking a job that
  // has been running a few minutes gets every event of it in one response:
  // 60 000 lines parsed and built into `<div>`s to keep the last 2000, which
  // was 997 ms of frozen main thread and three long tasks (WP-1427). The
  // server drops the oldest of the slice and says how many in `skipped`.
  const q = new URLSearchParams({offset: tail.offset, limit: MAX_LINES});
  if (tail.inode !== null) q.set('inode', tail.inode);
  if (tail.cold) q.set('end', '1');
  const t0 = performance.now();
  const r = await fetch(`api/run/${id}/events?` + q, {cache: 'no-store'});
  if (!r.ok) return;
  since('tail:net', t0);
  const t1 = performance.now();
  const payload = await r.json();
  since('tail:parse', t1);
  // an in-flight tail of the run we just left must not renumber this one
  if (tail.id !== id || currentId() !== id) return;
  const pane = $('console');
  // a different log; do not renumber, and do not carry its gap over
  if (payload.reset) {
    pane.textContent = '';
    tail.skipped = 0;
    tail.above = false;
  }
  tail.offset = payload.offset;
  tail.inode = payload.inode;
  tail.cold = false;          // one seek a run, and the rest are ordinary polls
  if (payload.skipped_bytes > 0) tail.above = true;
  tail.skipped += payload.skipped || 0;
  if (!payload.events.length) return;
  // the tail follows the log only while the reader is at its end; a reader
  // who scrolled up to read is left where they are
  const atBottom = pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 30;
  const t2 = performance.now();
  const html = payload.events.map(e => {
    const t = new Date(e.t * 1000).toLocaleTimeString();
    const data = Object.entries(e.data || {}).map(([k, v]) =>
      `${k}=${typeof v === 'number' ? +v.toPrecision(6)
              : Array.isArray(v) ? `[${v.length}]` : JSON.stringify(v)}`
    ).join(' ');
    return `<div class="line"><span class="ev">${t}</span> <span class="k">${esc(
      String(e.kind).padEnd(11))}</span> ${esc(data)}</div>`;
  }).join('');
  // append, never re-serialize: `innerHTML +=` reparses every line already
  // there, so a fit emitting an event per residual evaluation would pay for
  // its whole history on every poll
  pane.insertAdjacentHTML('beforeend', html);
  trimConsole(pane);
  noteGap(pane);
  if (atBottom) pane.scrollTop = pane.scrollHeight;
  since('tail:render', t2);
}

// ------------------------------------------------------------- splitters
// The two seams, and everything true of both (WP-1425).
//
// Each seam sizes one pane and leaves its neighbour a floor. Every number
// here was measured on this page rather than chosen, and each is quoted
// beside the constant it set.
const SEAMS = {
  // The list. Its six declared columns are 66ch, and that is exactly the
  // table's whole min-content. The run column takes the remainder, so it
  // absorbs every narrowing on its own and reaches 0 px with the table
  // overflowing the panel. `run` as a heading inks 36 px, so 66 + 5 is the
  // width below which a column cannot show its own name. In `ch`, because the
  // columns it is made of are.
  //
  // It was 58 + 5 until WP-1428 gave the list a seventh column, the 8ch the
  // launch button needs. That column is the whole of the 8ch difference, and
  // the default width went 72ch → 80ch with it so the run names keep the room
  // they had.
  list: {
    pane: 'runs', grip: 'grip-list', grow: 'right', prop: '--list',
    minCh: 71,
    // What the run pane keeps. A horizontal legend wraps *inside* the paper
    // (WP-1426), so a narrow pane loses picture instead of gaining height:
    // measured at 1400x900, the legend holds three rows down to a 340 px
    // pane and collapses to six rows and 124 px — a quarter of the 503 px
    // plot — by 300. The chart's own legend (WP-1461) is three rows and
    // 58 px at 340, 15 % of the plot.
    keep: 340,
    of: el => el.getBoundingClientRect().width,
    // the floor above is a width of *columns*, and the pane is sized
    // border-box, so its own border and scrollbar gutter are on top. Measured
    // rather than added as a constant: at the floor the run column came out
    // 35 px against the 36 its heading inks, one pixel of border.
    chrome: el => el.offsetWidth - el.clientWidth,
    // The same seam under the stylesheet's `--stacked` (WP-1438). Every
    // number is a different number, which is the whole reason this is a
    // second entry and not a flag: the floor is a heading and two rows
    // (26.5 + 2×27, measured) rather than 71 columns, and what the pane next
    // door keeps is the picture's declared 180 px min-height plus the
    // console's own 51 px floor plus the strip and the console's grip, not
    // 340 px of plot width.
    stacked: {
      grow: 'down', prop: '--list-h', min: 82, keep: 265, minCh: undefined,
      of: el => el.getBoundingClientRect().height,
      chrome: el => el.offsetHeight - el.clientHeight,
    },
  },
  // The log. Three lines of 13 px plus the pane's 12 px of padding, against
  // `#picture`'s own declared `min-height`, which is this page's existing
  // answer to how short a picture may be.
  console: {
    pane: 'console', grip: 'grip-console', grow: 'up', prop: '--console',
    min: 51, keep: 180,
    of: el => el.getBoundingClientRect().height,
  },
};

//: An arrow key moves the seam by this much, Shift by ten times it.
const STEP = 16;

// Are the two panes stacked? The breakpoint is the stylesheet's and is asked
// for rather than repeated here (WP-1438): `watch.css` sets `--stacked` in a
// media query, so the number lives once and the page reads the *answer*.
// Nothing caches it — a window is resized between one draw and the next, and
// `applyLayout` already runs on every resize.
function isStacked() {
  return getComputedStyle(document.documentElement)
    .getPropertyValue('--stacked').trim() === '1';
}

// A seam as it is right now. Only the list has a second arrangement, and
// merging is right rather than branching at each use: everything the wide
// seam declares that the stacked one does not — the pane, the grip, the
// element it measures — is true of both.
function seamOf(which) {
  const seam = SEAMS[which];
  return (seam.stacked && isStacked()) ? {...seam, ...seam.stacked} : seam;
}

let layout = LAYOUT_DEFAULT;

function readLayout() {
  let raw = null;
  let legacy = null;
  // reading can throw as well as come back empty (a private window, site data
  // blocked), and both mean the same thing: no choice stored
  try {
    raw = localStorage.getItem(LAYOUT_KEY);
    legacy = localStorage.getItem(PANELS_KEY);
  } catch (err) {}
  const parsed = parseLayout(raw, legacy);
  // The old key has given up the one bit it had, so it stops sitting in
  // storage looking like state. Written before it is dropped, and not only on
  // the reader's next verb: nothing else stores a layout, so removing the old
  // key first spends the migrated bit on one render and the list comes back
  // open on the reload after it.
  if (legacy !== null) {
    try {
      localStorage.setItem(LAYOUT_KEY, JSON.stringify(parsed));
      localStorage.removeItem(PANELS_KEY);
    } catch (err) {}
  }
  return parsed;
}

function storeLayout() {
  try { localStorage.setItem(LAYOUT_KEY, JSON.stringify(layout)); } catch (err) {}
}

// One `ch` of the page's own font, measured rather than assumed: the list's
// floor is declared in `ch` because the columns it is made of are.
//
// Measured once and kept: the probe is a DOM write and a forced reflow, and
// `floorOf` is asked four times a pointer move. What moves the answer is the
// page's font size, which moves when the window or the zoom does, so the
// window's own `resize` is what drops it.
let CH = null;
function oneCh() {
  if (CH !== null) return CH;
  const probe = document.createElement('span');
  probe.style.cssText = 'position:absolute;visibility:hidden;font:inherit';
  probe.textContent = '0'.repeat(100);
  document.body.appendChild(probe);
  const ch = probe.getBoundingClientRect().width / 100;
  probe.remove();
  // an unmeasurable page is not an answer worth keeping, so only a real one
  // is cached and the fallback is re-asked next time
  if (ch > 0) CH = ch;
  return ch || 7;
}

function floorOf(seam) {
  const base = seam.min !== undefined ? seam.min
                                      : Math.round(seam.minCh * oneCh());
  return base + (seam.chrome ? seam.chrome($(seam.pane)) : 0);
}

// The extent the two panes share, which is what a stored size is re-clamped
// against. Read off the page, so the grip's own 5 px are already out of it.
function extentOf(which) {
  if (which === 'list') {
    const main = $('main').getBoundingClientRect();
    const grip = $('grip-list').getBoundingClientRect();
    // the grip's own 5 px come out of whichever extent the panes share, and
    // which that is is the arrangement's answer, not this function's
    return isStacked() ? main.height - grip.height : main.width - grip.width;
  }
  return $('run').getBoundingClientRect().height
         - $('strip').getBoundingClientRect().height
         - $('grip-console').getBoundingClientRect().height;
}

// A size for the pane, or `null` for "no choice made" — which leaves the
// stylesheet's own `80ch`/`30%` in force rather than freezing a px number
// over a size that is font- and window-relative on purpose.
//
// A stored size is not a settled size (WP-1029): a drag clamps against the
// extent it happened in, and nothing clamps a size that outlives its window,
// so this runs at *render* and not only at the end of a drag.
function sizeOf(which) {
  const stored = layout[which][sizeField(which, isStacked())];
  if (stored === null || stored === undefined) return null;
  const seam = seamOf(which);
  return clampSize(stored, floorOf(seam), seam.keep, extentOf(which));
}

function applyLayout() {
  document.body.dataset.list = layout.list.open ? 'open' : 'closed';
  // The collapse is "give the list the window", so it means nothing where
  // there is no list: under `data-single` the stylesheet already hides `#runs`
  // *and* the button that would undo this, so a stored `false` carried in from
  // another directory on the same origin drew a page with nothing on it and no
  // control to bring anything back. The choice is kept, not cleared — a reader
  // who collapsed the run pane on a directory of runs still finds it collapsed
  // when they go back to one.
  const runOpen = layout.run.open || Boolean(SINGLE);
  document.body.dataset.run = runOpen ? 'open' : 'closed';
  const toggle = $('toggle-run');
  if (toggle) toggle.setAttribute('aria-pressed', String(!runOpen));
  $('run').dataset.console = layout.console.open ? 'open' : 'closed';
  for (const which of Object.keys(SEAMS)) {
    const seam = seamOf(which);
    const size = sizeOf(which);
    if (size === null) document.body.style.removeProperty(seam.prop);
    else document.body.style.setProperty(seam.prop, size + 'px');
    const grip = $(seam.grip);
    grip.classList.toggle('closed', !layout[which].open);
    // a separator says which way it moves, and stacking turns this one
    grip.setAttribute('aria-orientation',
                      axisOf(seam.grow) === 'x' ? 'vertical' : 'horizontal');
    const floor = floorOf(seam);
    const ceiling = Math.max(floor, extentOf(which) - seam.keep);
    // the ARIA window splitter's numbers. A collapsed pane sits at its own
    // minimum, which is how the pattern says "collapsed" without inventing a
    // second attribute for it.
    grip.setAttribute('aria-valuemin', String(Math.round(floor)));
    grip.setAttribute('aria-valuemax', String(Math.round(ceiling)));
    grip.setAttribute('aria-valuenow', String(Math.round(
      layout[which].open ? (seam.of($(seam.pane)) || size || floor) : floor)));
  }
  // nothing to tell the picture: its ResizeObserver sizes it in the frame the
  // pane changed (`rxplot.panes`), where plotly needed a call and a timer
}

function setSize(which, size, {store = true} = {}) {
  layout = nextLayout(layout, which, {
    [sizeField(which, isStacked())]: Math.round(size), open: true});
  if (store) storeLayout();
  applyLayout();
}

// Collapse and restore. The pane comes back at the size it had, and at the
// declared default when it never had one.
//
// `run` travels through here too and is not a seam: the button beside the
// title is its whole control, because no grip sizes the run pane and a
// splitter's collapse belongs to the pane its grip sizes (WP-1425). What
// WP-1438 restored is the *command* — a collapsible pane that can only be
// collapsed by a gesture on a focused 5 px separator is one nobody finds.
function toggleSeam(which) {
  layout = nextLayout(layout, which, {open: !layout[which].open});
  storeLayout();
  applyLayout();
}

function armGrip(which) {
  const grip = $(SEAMS[which].grip);
  const pane = $(SEAMS[which].pane);
  // read at the event and never held: the list's seam turns when the window
  // does, and a grip armed once at boot would keep dragging along the axis
  // the page was in then (WP-1438)
  const across = () => axisOf(seamOf(which).grow) === 'x';

  grip.addEventListener('pointerdown', ev => {
    if (ev.button !== 0) return;
    if (!layout[which].open) return;     // collapsed: the verb is the toggle
    ev.preventDefault();
    const seam = seamOf(which);
    const horizontal = across();
    const from = horizontal ? ev.clientX : ev.clientY;
    const start = seam.of(pane);
    grip.setPointerCapture(ev.pointerId);
    grip.classList.add('dragging');
    const move = e => {
      const at = horizontal ? e.clientX : e.clientY;
      // report a size, never write one (WP-1029): `dragged` says what was
      // asked for, `clampSize` what is allowed, and the owner writes it
      setSize(which, clampSize(dragged(start, from, at, seam.grow),
                               floorOf(seam), seam.keep, extentOf(which)),
              {store: false});
    };
    const up = () => {
      grip.classList.remove('dragging');
      grip.removeEventListener('pointermove', move);
      grip.removeEventListener('pointerup', up);
      grip.removeEventListener('pointercancel', up);
      storeLayout();              // persisted on the verb, not per pixel
    };
    grip.addEventListener('pointermove', move);
    grip.addEventListener('pointerup', up);
    grip.addEventListener('pointercancel', up);
  });

  grip.addEventListener('dblclick', () => toggleSeam(which));

  // The WAI-ARIA window splitter's keyboard, so nobody has to invent one: the
  // arrows move the separator, Home and End take it to its stops, and Enter
  // collapses and restores. An arrow names a direction *on screen*; which way
  // that grows this pane is `grow`'s business, which is why the sign is not
  // spelled twice.
  grip.addEventListener('keydown', ev => {
    if (ev.key === 'Enter') { ev.preventDefault(); toggleSeam(which); return; }
    if (!layout[which].open) return;
    const seam = seamOf(which);
    const horizontal = across();
    const back = horizontal ? 'ArrowLeft' : 'ArrowUp';
    const forward = horizontal ? 'ArrowRight' : 'ArrowDown';
    const extent = extentOf(which);
    const floor = floorOf(seam);
    const step = ev.shiftKey ? STEP * 10 : STEP;
    const now = seam.of(pane);
    let next;
    if (ev.key === back) next = dragged(now, 0, -step, seam.grow);
    else if (ev.key === forward) next = dragged(now, 0, step, seam.grow);
    else if (ev.key === 'Home') next = floor;
    else if (ev.key === 'End') next = Math.max(floor, extent - seam.keep);
    else return;
    ev.preventDefault();
    setSize(which, clampSize(next, floor, seam.keep, extent));
  });
}

// A stored size outlives the window it was chosen in, so the clamp is redone
// whenever the window changes — the render-time half of WP-1029's rule.
window.addEventListener('resize', () => { CH = null; applyLayout(); });

// ------------------------------------------------------------- routing
// A run named in the URL is pinned. With none the page follows the newest,
// so opening `rietx watch` beside an agent's job shows what is happening
// now, and the row the reader clicks is the one that stays.
function currentId() {
  const m = location.hash.match(/^#\/run\/([0-9a-f]+)$/);
  return m ? m[1] : (SINGLE || newest);
}
// The page's constants, off whichever `api/runs` answers first — every poll
// carries them, so a failed boot fetch costs nothing the next poll does not
// repair. The name and the suffix are read once; the *theme* is read every
// poll, because it is the one thing here a person can change while the page is
// open, and a change reaches this tab through the payload it already fetches
// rather than through a reload (WP-1429).
function readPage(payload) {
  if (!payload.page) return false;
  if (!DIST) {
    DIST = payload.page.dist;
    setText($('empty-suffix'), payload.page.suffix);
    buildThemeControl(payload.page.themes);
    // read here rather than in a fetch of their own (WP-1438). The boot used
    // to ask `api/runs` for these and the first poll asked again, the same
    // request twice about 85 ms apart, with the log's fetch queued behind
    // both. They are read once because none of them can move while the page
    // is open; the theme below is read every poll because it can.
    SINGLE = payload.single_run_id;
    CAN_CANCEL = payload.can_cancel === true;
    CAN_OPEN_GUI = payload.can_open_gui === true;
    if (SINGLE) document.body.dataset.single = '';
  }
  return applyTheme(payload.page.theme);
}

// The control, drawn from the server's list rather than from three literals
// here (WP-1438). The glyphs and the sentences are `viz/theme.py`'s and the
// GUI's alike, so the two pages a reader has open say the same thing.
//
// Built once, on the first payload that carries them: they cannot move while
// the page is open, and a control rebuilt per poll would drop the focus of
// anyone operating it from the keyboard.
function buildThemeControl(themes) {
  const bar = $('theme');
  if (!bar || !Array.isArray(themes) || !themes.length) return;
  for (const entry of themes) {
    const button = document.createElement('button');
    button.type = 'button';
    button.dataset.choice = entry.choice;
    button.textContent = entry.glyph;
    button.setAttribute('aria-label', entry.choice);
    button.setAttribute('aria-pressed', 'false');
    button.title = entry.title;
    button.addEventListener('click', () => chooseTheme(entry.choice));
    bar.appendChild(button);
  }
}

// The choice is applied here and *then* stored, which is the GUI's order and
// for its reason: a theme that waited on a round trip flickers, and one that
// snapped back on a failure would be the page arguing with the reader. A
// refusal is left to the next poll, which reads the stored choice and is the
// authority either way.
async function chooseTheme(choice) {
  // the picture is the one thing on this page a stylesheet does not reach,
  // so a theme that moved is a canvas to repaint
  if (applyTheme(choice)) retheme();
  try {
    await fetch('api/theme', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({theme: choice}),
    });
  } catch (err) {}
}

let refreshing = false;
// What the last `/api/runs` answered with, sent back on the next one. A poll
// where nothing changed is then two header lines instead of the whole list
// (WP-1427): 229 kB a poll on a batch of 200 finished runs, which is what a
// tab left open overnight spends on a directory nobody is writing to.
let etag = null;
async function refresh() {
  if (refreshing) return;              // a slow poll is not two polls
  refreshing = true;
  try {
    const t0 = performance.now();
    const r = await fetch('api/runs', {
      cache: 'no-store',
      headers: etag ? {'If-None-Match': etag} : {},
    });
    // 304: the list is the one already on the page, so there is nothing to
    // parse and nothing to patch. The run panel still gets its poll, because
    // a snapshot and a log move without the list moving, and the highlight
    // still gets its own, because the reader's click moved the URL and not
    // the files.
    if (r.status === 304) {
      since('runs:net', t0);
      markSelected();
      const id = currentId();
      if (id) await drawRun(id);
      return;
    }
    if (!r.ok) return;
    since('runs:net', t0);
    const t1 = performance.now();
    const payload = await r.json();
    since('runs:parse', t1);
    // a theme that moved repaints the canvas, which CSS cannot do for it:
    // the picture is the one thing on this page a stylesheet does not reach.
    // The chart only: a legacy run's picture is a self-contained page that
    // takes no colour from here, and re-pointing its frame would refetch the
    // megabytes WP-1402 measured and lose the reader's place inside it.
    if (readPage(payload)) retheme();
    setText($('root'), 'scanned ' + payload.root);
    rows = new Map(payload.runs.map(run => [run.run_id, run]));
    newest = payload.runs.length ? payload.runs[0].run_id : null;
    const t2 = performance.now();
    patchList(payload.runs);
    since('runs:patch', t2);
    // the tag is committed once the list it describes is on the page. Set
    // before the parse, a truncated body or a patch that threw would leave
    // every later poll answered 304 against a list the page never drew, and
    // nothing on disk could ever shake it loose again.
    etag = r.headers.get('ETag');
    const id = currentId();
    if (id) await drawRun(id); else clearStrip();
  } finally {
    refreshing = false;
  }
}
function schedule() {
  if (timer) clearInterval(timer);
  // polling stops when nobody is looking: a hidden tab costs the fit nothing
  timer = setInterval(() => { if (!document.hidden) refresh(); }, 1200);
}
window.addEventListener('hashchange', () => refresh());
document.addEventListener('visibilitychange', () => {
  if (!document.hidden) refresh();
});
$('stop').onclick = () => {
  const run = rows.get(currentId());
  if (run) openConfirm(run);
};

(async () => {
  // The log does not queue behind the walk. A run named in the URL is known
  // before anything is fetched, so its tail is asked for here, in parallel
  // with the poll — measured on a reload, the console filled 141 ms after
  // the list it belongs beside, and the reader saw the page come back
  // without its log and then the log arrive (WP-1438).
  //
  // A *named* run only. With no run in the URL the page does not yet know
  // which log it wants: `newest` is what the walk is for.
  const pinned = currentId();
  if (pinned) {
    resetTail(pinned);
    // floating on purpose — the walk behind it draws the same run, and its
    // own `pumpEvents` waits on this one and reports whatever it did not
    pumpEvents(pinned).catch(() => {});
  }
  layout = readLayout();
  armGrip('list');
  armGrip('console');
  // the run pane's collapse is a button, not a grip: nothing sizes that pane
  $('toggle-run').addEventListener('click', () => toggleSeam('run'));
  armExports();
  applyLayout();
  await refresh();
  // `data-single` arrives with the walk now, and it is a layout the page has
  // already applied once
  applyLayout();
  schedule();
})();
