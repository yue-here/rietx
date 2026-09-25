// rxplot: the chart module rietx's browser pages draw with (WP-1461, D3).
//
// Two halves. The pure half touches no DOM and no uPlot, and
// `tests/rxplot.test.mjs` runs it under `node --test`. The drawing half stacks
// uPlot panes on one shared x, and `tests/test_rxplot_browser.py` drives it in
// chromium.
//
// uPlot is passed in, never imported. The GUI bundles it, and the Python pages
// serve the copy vendored beside this file (`uPlot.iife.min.js`), so the module
// runs under either without knowing which.

// ---------------------------------------------------------------- pure half

/** The first index whose value is at least `v`, in an ascending array. */
export function lower(xs, v) {
  let lo = 0, hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < v) lo = mid + 1; else hi = mid;
  }
  return lo;
}

/** The first index whose value is past `v`, in an ascending array. */
export function upper(xs, v) {
  let lo = 0, hi = xs.length;
  while (lo < hi) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] <= v) lo = mid + 1; else hi = mid;
  }
  return lo;
}

/**
 * `rows` under a header of `names`, tab-separated, a row a line. A number is
 * written in full, so a pasted value is the one drawn. A gap, and a value that
 * is not a finite number, is an empty cell.
 */
export function tsv(names, rows) {
  const cell = (v) => (v == null || (typeof v === "number" && !Number.isFinite(v)) ? "" : String(v));
  return [names.join("\t"), ...rows.map((row) => row.map(cell).join("\t"))].join("\n");
}

/**
 * The index of the entry nearest `v`, or -1 when none is within `radius`.
 * Distance is measured in pixels through `toPx`, since a pointer's reach is a
 * screen distance at every zoom.
 */
export function nearest(xs, v, toPx, radius) {
  const i = lower(xs, v), at = toPx(v);
  let best = -1, dist = Infinity;
  for (const j of [i - 1, i]) {
    if (j < 0 || j >= xs.length) continue;
    const d = Math.abs(toPx(xs[j]) - at);
    if (d < dist) { dist = d; best = j; }
  }
  return dist <= radius ? best : -1;
}

/**
 * The index of the point nearest `(left, top)` in the plane, or -1 when none is
 * within `radius`. `xs` and `ys` are pixel positions, null where a point has no
 * value. For a figure whose x is not sorted, as a trajectory's chain is not.
 */
export function nearestXY(xs, ys, left, top, radius) {
  let best = -1, dist = radius * radius;
  for (let i = 0; i < xs.length; i++) {
    if (xs[i] == null || ys[i] == null) continue;
    const d = (xs[i] - left) ** 2 + (ys[i] - top) ** 2;
    if (d <= dist) { dist = d; best = i; }
  }
  return best;
}

/**
 * Ticks for a √ axis, evenly spaced in √ space and rounded to half a decade
 * of the gap to the next tick. uPlot spaces ticks in value space, which on a √
 * scale printed one label for the whole axis (finding 2). Rounding to the
 * value's own decade did the same inside a narrow zoom: 1000 to 1010 all
 * rounded to 1000.
 */
export function sqrtSplits(min, max, n = 6) {
  const a = Math.sqrt(Math.max(min, 0)), b = Math.sqrt(Math.max(max, 0)), out = [];
  if (!(b > a)) return out;
  const at = (k) => (a + (b - a) * k / n) ** 2;
  for (let k = 0; k <= n; k++) {
    const v = at(k), half = 10 ** Math.floor(Math.log10(at(k + 1) - v)) / 2;
    const t = Math.round(v / half) * half;
    if (t >= min && t <= max) out.push(t);
  }
  return [...new Set(out)];
}

/** The smallest gap between neighbouring ticks, skipping the nulls uPlot filters out. */
function tickStep(splits) {
  const ticks = splits.filter((v) => v != null);
  let step = Infinity;
  for (let i = 1; i < ticks.length; i++) {
    const gap = Math.abs(ticks[i] - ticks[i - 1]);
    if (gap > 0 && gap < step) step = gap;
  }
  return step;
}

/**
 * How many decimals neighbouring ticks need to read differently. uPlot's
 * default follows the magnitude of the values, so a refined cell edge spanning
 * 1e-4 Å printed `10.251` five times (finding 3). This follows the step, and
 * then every tick, since a √ axis's ticks are not multiples of the smallest gap
 * and 1003.5 printed as `1004` beside a step of 2.
 */
export function tickDecimals(splits) {
  const step = tickStep(splits);
  if (!Number.isFinite(step)) return 0;
  const values = [step, ...splits.filter((v) => v != null)];
  let d = Math.max(0, -Math.floor(Math.log10(step)));
  // a step of 0.25 needs two decimals where its magnitude says one
  while (d < 15) {
    const f = 10 ** d, slack = 1e-6 * step * f;
    if (values.every((v) => Math.abs(Math.round(v * f) - v * f) <= slack)) break;
    d++;
  }
  return d;
}

/** Labels for `splits` at the precision their step needs. */
export function tickLabels(splits) {
  const d = tickDecimals(splits), step = tickStep(splits);
  // a tick that should be zero can arrive as 1e-17, and would print as "-0.000"
  const zero = Number.isFinite(step) ? step * 1e-9 : 0;
  return splits.map((v) => (v == null ? "" : (Math.abs(v) <= zero ? 0 : v).toFixed(d)));
}

/**
 * A Miller index as a reader writes one: `(1 0 −1)`, spaced, with U+2212 in
 * front of the digit. `watch-core.mjs`'s `hklLabel` and the GUI's `formatHkl`
 * are its twins, and `plot.test.ts` holds all three equal over one table.
 * `watch-core.mjs` cannot import this file under `node --test`, which runs it
 * from another directory.
 */
export function hklLabel(hkl) {
  if (!Array.isArray(hkl) || hkl.length !== 3) return "";
  return `(${hkl.map((v) => (v < 0 ? `−${Math.abs(v)}` : String(v))).join(" ")})`;
}

/**
 * `a − b`, channel for channel. Two arrays of different lengths are two sets
 * of channels, which no subtraction compares, so they throw.
 */
export function difference(a, b) {
  if (a.length !== b.length) {
    throw new Error(`rxplot: ${a.length} channels against ${b.length}; a difference needs one grid`);
  }
  const out = new Float64Array(a.length);
  for (let i = 0; i < a.length; i++) out[i] = a[i] - b[i];
  return out;
}

/**
 * `values` placed at `index` in an array of `n` nulls.
 *
 * A uPlot chart has one x array (finding 10), so every series is drawn over
 * the pattern's own channel list. The fit's arrays cover only the channels it
 * kept, and `index` says which those are. A null is a gap uPlot does not draw.
 */
export function scatter(n, index, values) {
  const out = new Array(n).fill(null);
  for (let q = 0; q < index.length; q++) out[index[q]] = values[q];
  return out;
}

/**
 * What a cumulative χ² has summed before the view starts at `lo`: `cum` at the
 * last channel of `xs` under `lo`, or 0 when none is. The server sums Σχ² over
 * every fitted channel once, and a view shows `cum − chi2Base`, so the curve
 * starts at zero at the view's left edge and ends at the view's own χ².
 */
export function chi2Base(cum, xs, lo) {
  const i = lower(xs, lo) - 1;
  return i >= 0 ? cum[i] : 0;
}

/**
 * `y` split in two over the same channels: the ones `index` names, and the
 * rest. Each is null where the other is drawn, so the observed pattern draws
 * as the fitted points and the masked ones in two styles on one x.
 */
export function partition(y, index) {
  const inside = new Array(y.length).fill(null), outside = Array.from(y);
  for (let q = 0; q < index.length; q++) {
    const i = index[q];
    inside[i] = y[i];
    outside[i] = null;
  }
  return [inside, outside];
}

const TYPED = { "<f8": Float64Array, "<i4": Int32Array };

/**
 * A packed body as `{ header, arrays }`, the format `rietx.viz.packed` writes
 * (D4): a little-endian uint32 header length, the JSON header, then 8-aligned
 * arrays the header lists. Each array is a view on `buffer`, never a copy.
 */
export function unpack(buffer) {
  const n = new DataView(buffer).getUint32(0, true);
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 4, n)));
  const arrays = {};
  for (const { name, dtype, offset, length } of header.arrays) {
    const Typed = TYPED[dtype];
    if (!Typed) throw new Error(`rxplot: ${name} is ${dtype}, which no typed array reads`);
    arrays[name] = new Typed(buffer, 4 + n + offset, length);
  }
  delete header.arrays;
  return { header, arrays };
}

// ---------------------------------------------------------------- drawing half

/** A CSS custom property's value on `el`, read at the moment of the call. */
export function token(name, el = document.documentElement) {
  return getComputedStyle(el).getPropertyValue(name).trim();
}

/** The drag threshold, in CSS pixels, below which a box zoom becomes one axis. plotly's is 20. */
export const UNI = 20;

/**
 * The distance, in CSS pixels, a press must travel to be a drag. plotly's is 8.
 * Below `UNI` uPlot forces a drag onto one axis and spans the other, so without
 * this a click that moved one pixel zoomed x to a one-pixel window.
 */
export const CLICK = 8;

/** The least height, in CSS px, a pane sized by a `share` is given. */
const MIN_PANE = 60;

const TYPES = ["lin", "sqrt", "log"];

function yScale(uPlot, kind, pinned, fixed, own) {
  // a band of rows, like the reflection ticks, has a range of its own and no zoom
  if (fixed) return { range: () => fixed };
  if (!TYPES.includes(kind)) throw new Error(`rxplot: no y scale "${kind}"; one of ${TYPES.join(", ")}`);
  const auto = own ?? (kind === "log"
    ? (u, min, max) => uPlot.rangeLog(min, max, 10, true)
    : (u, min, max) => uPlot.rangeNum(min, max, 0.1, true));
  // a y range the reader zoomed to is held across every x zoom until a reset
  const range = (u, min, max) => pinned() ?? auto(u, min, max);
  if (kind === "log") return { distr: 3, log: 10, range };
  if (kind === "sqrt") {
    return { distr: 100, range,
             fwd: (v) => Math.sign(v) * Math.sqrt(Math.abs(v)),
             bwd: (v) => Math.sign(v) * v * v };
  }
  return { range };
}

/** The width of a y axis title, the same on every pane so their plot areas align. */
const TITLE = 18;

/** An x axis's height in CSS px, bare and with its tick labels. A title adds `TITLE`. */
const X_BARE = 6, X_LABELS = 24;

/** Axis type, at the size the pages' own controls are set in. uPlot's titles are bold by default. */
const FONT = '11px system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif';

function axes(spec, gutter) {
  const ink = () => token("--fg"), line = () => token("--line");
  const text = { font: FONT, labelFont: FONT };
  const x = { ...text, stroke: ink, grid: { stroke: line, width: 1 }, ticks: { stroke: line } };
  if (!spec.xLabels) Object.assign(x, { values: (u, s) => s.map(() => ""), size: X_BARE });
  else Object.assign(x, { size: X_LABELS, values: (u, s) => tickLabels(s) },
                     spec.xLabel == null ? {} : { label: spec.xLabel, labelSize: TITLE });
  const y = { ...text, stroke: ink, grid: { stroke: line, width: 1 }, ticks: { stroke: line }, size: gutter,
              label: spec.label ?? "", labelSize: TITLE };
  if (spec.yLabels === false) {
    // a band, like the reflection ticks, whose y means nothing and whose grid would cross every row
    return [{ ...x, grid: { show: false } },
            { ...y, values: (u, s) => s.map(() => ""), grid: { show: false }, ticks: { show: false } }];
  }
  if (spec.y === "sqrt") {
    y.splits = (u, i, min, max) => sqrtSplits(min, max);
    // uPlot filters labels for a log axis on `distr >= 3`, which a √ scale's 100
    // is, so without this every label but a power of ten printed blank
    y.filter = (u, splits) => splits;
  }
  if (spec.y !== "log") y.values = (u, splits) => tickLabels(splits);
  return [x, y];
}

/**
 * Panes stacked in `host`, sharing one x.
 *
 * `spec.x` is the one x array. Each of `spec.panes` is `{ key, series, data }`
 * plus optional:
 *
 * - `height` in CSS px, or `share`, a share of the host's height left over by
 *   the panes with a `height`, so the group fills a host whose height the page
 *   decides;
 * - `y` ("lin", "sqrt" or "log"), or `range`, a fixed y range no drag zooms;
 * - `auto`, `(u, min, max) => [lo, hi]`, the y range while the reader has not
 *   chosen one, in place of the data's padded extent. uPlot calls it at every
 *   x range, with `u.series[0].idxs` the channels in view;
 * - `label`, the y axis title, a string or a function uPlot reads at each draw;
 *   `yLabels: false` for a band whose y means nothing;
 * - `xLabels`, and `xLabel` the x axis title under them;
 * - `hooks`, merged into uPlot's.
 *
 * `series` and `data` leave out the x, which the group supplies.
 *
 * The group answers the gestures every page shares:
 *
 * - A drag zooms the pane it starts in: x only when it is flat, y only when it
 *   is narrow, both when it is a box. A y range the reader chose holds across x
 *   zooms until a double-click resets every pane.
 * - The wheel zooms x around the pointer. Shift-wheel and alt-drag pan.
 * - In "select" mode a drag calls `onSelect(lo, hi, key)` once, from the pane it
 *   started in, and zooms nothing.
 * - The pointer calls `onCursor({ key, idx, x, left, top })`, or `onCursor(null)`
 *   as it leaves. Only the pane under the pointer calls it.
 * - A `ResizeObserver` on `host` resizes every pane in the frame the host changed.
 *
 * The panes share their cursor through uPlot's sync, and nothing else: a drag's
 * mousedown and mouseup stay in their own pane. Synced, a drag selected in every
 * pane at once, and a select handler ran once per pane (finding 1). The x range
 * is copied by value rather than by sync, and never onto a pane already at it,
 * because every `setScale` repaints its pane (finding 12).
 */
export function panes(uPlot, host, spec) {
  const gutter = spec.gutter ?? 64, sync = spec.sync ?? `rx-${Math.random().toString(36).slice(2)}`;
  const group = { panes: {}, mode: "zoom", onSelect: null, onCursor: null };
  const pins = {}, divs = {}, specs = {};
  let pointer = null;

  group.setX = (lo, hi) => {
    for (const u of Object.values(group.panes)) {
      if (u.scales.x.min !== lo || u.scales.x.max !== hi) u.setScale("x", { min: lo, max: hi });
    }
  };

  function zoom(u, key) {
    const s = u.select, w = u.over.clientWidth, h = u.over.clientHeight;
    const xs = !(s.left <= 0 && s.width >= w - 0.5);
    const ys = !(s.top <= 0 && s.height >= h - 0.5) && !specs[key].range;
    if (ys) {
      const lo = u.posToVal(s.top + s.height, "y"), hi = u.posToVal(s.top, "y");
      pins[key] = [lo, hi];
      u.setScale("y", { min: lo, max: hi });
    }
    if (xs) group.setX(u.posToVal(s.left, "x"), u.posToVal(s.left + s.width, "x"));
  }

  function onSelect(u) {
    const key = u.__rxKey, s = u.select;
    if (group.mode === "select") {
      group.onSelect?.(u.posToVal(s.left, "x"), u.posToVal(s.left + s.width, "x"), key);
    } else {
      zoom(u, key);
    }
    u.setSelect({ left: 0, top: 0, width: 0, height: 0 }, false);
  }

  function onCursor(u) {
    if (u.__rxKey !== pointer || !group.onCursor) return;
    const { left, top, idx } = u.cursor;
    if (left == null || left < 0 || idx == null) { group.onCursor(null); return; }
    group.onCursor({ key: u.__rxKey, idx, x: u.posToVal(left, "x"), left, top });
  }

  function gestures(u, key) {
    u.over.addEventListener("wheel", (e) => {
      e.preventDefault();
      const { min, max } = u.scales.x;
      if (e.shiftKey || Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        const d = (max - min) * (e.deltaX || e.deltaY) / 1000;
        group.setX(min + d, max + d);
      } else {
        const x = u.posToVal(e.offsetX, "x"), f = Math.exp(e.deltaY * 0.002);
        group.setX(x - (x - min) * f, x + (max - x) * f);
      }
    }, { passive: false });
    // alt-drag pans; in the capture phase, so uPlot never starts a select
    u.root.addEventListener("mousedown", (e) => {
      if (!e.altKey) return;
      e.stopPropagation();
      e.preventDefault();
      const x0 = e.clientX, { min, max } = u.scales.x, perPx = (max - min) / u.over.clientWidth;
      const move = (ev) => { const d = (ev.clientX - x0) * perPx; group.setX(min - d, max - d); };
      const up = () => { removeEventListener("mousemove", move); removeEventListener("mouseup", up); };
      addEventListener("mousemove", move);
      addEventListener("mouseup", up);
    }, true);
    u.over.addEventListener("dblclick", () => group.reset());
    u.over.addEventListener("mouseenter", () => { pointer = key; });
    u.over.addEventListener("mouseleave", () => { pointer = null; group.onCursor?.(null); });
  }

  /**
   * The options pane `p` is built with. `copy`, when given, is the live pane
   * an export redraws (`svg`): the same pane at its size, its view and its
   * shown series, in no sync group and answering no gesture. Synced, its first
   * `setScale` redrew the live panes while `Path2D` was swapped (finding 6).
   */
  function options(p, copy) {
    const key = p.key;
    const hooks = { ...(p.hooks ?? {}) };
    const extend = (name, fn) => { hooks[name] = [...(hooks[name] ?? []), fn]; };
    if (!copy) {
      extend("setScale", (u, k) => { if (k === "x") group.setX(u.scales.x.min, u.scales.x.max); });
      extend("setSelect", onSelect);
      extend("setCursor", onCursor);
    }
    const view = copy && [copy.scales.y.min, copy.scales.y.max];
    const series = p.series.map((s, i) => ({ points: { show: false }, ...s, ...(copy ? { show: copy.series[i + 1].show } : {}) }));
    const common = {
      width: copy ? copy.width : host.clientWidth, height: copy ? copy.height : heights()[key], legend: { show: false },
      scales: { x: copy ? { time: false, range: () => [copy.scales.x.min, copy.scales.x.max] } : { time: false },
                y: yScale(uPlot, p.y ?? "lin", copy ? () => view : () => pins[key] ?? null, p.range, p.auto) },
      axes: axes(p, gutter),
      // A band has no y labels for uPlot's automatic top padding to make room
      // for, and that padding took 17 px of a one-phase band's 22.
      ...(p.yLabels === false ? { padding: [0, null, null, null] } : {}),
      // A line is a line. uPlot rings every point of a series whose points sit
      // far enough apart, which a zoom always reaches, and a ringed calculated
      // curve reads as observed points. A series that wants marks says so.
      series: [{}, ...series],
      hooks,
    };
    if (copy) return { ...common, cursor: { show: false, drag: { x: false, y: false } } };
    return { ...common,
      cursor: {
        sync: { key: sync, setSeries: false, scales: ["x", null],
                filters: { pub: (type) => type !== "mousedown" && type !== "mouseup" && type !== "dblclick" } },
        drag: { x: true, y: group.mode === "zoom", uni: UNI, dist: CLICK, setScale: false },
        // The cursor's own index for every series. uPlot's default walks each
        // series left and right from the pointer to its nearest non-null value,
        // on every move, in every pane; a fit's arrays are null over every
        // masked channel and the tick band's series is null throughout, and no
        // page reads a series' own index (finding 17).
        dataIdx: (self, seriesIdx, idx) => idx,
        bind: { dblclick: () => null },
        points: { show: false }, y: false, focus: { prox: -1 },
      },
    };
  }

  function build(p) {
    const key = p.key;
    const u = new uPlot(options(p), [spec.x, ...p.data], divs[key]);
    // The pointer's line carries no quantity, so it is chrome: solid, in
    // `--fg`, the one ink no plot colour is near (WP-1213). uPlot's own is
    // dashed grey-blue, which reads as the dotted edge an excluded region
    // leaves. Inline and through the token, so every page takes it and a theme
    // switch restyles it. A rule in each page's stylesheet had to outrank
    // uPlot's own, and one page of four had none.
    u.root.querySelector(".u-cursor-x")?.style.setProperty("border-right", "1px solid var(--fg)");
    u.__rxKey = key;
    group.panes[key] = u;
    gestures(u, key);
    return u;
  }

  /** Each pane's height: its own, or its share of what the fixed ones leave. */
  function heights() {
    const all = Object.values(specs), out = {};
    const fixed = all.reduce((sum, p) => sum + (p.share ? 0 : p.height ?? 200), 0);
    const shares = all.reduce((sum, p) => sum + (p.share ?? 0), 0);
    const room = host.clientHeight - fixed;
    for (const p of all) {
      out[p.key] = p.share ? Math.max(MIN_PANE, Math.floor(room * p.share / shares)) : p.height ?? 200;
    }
    // A floor raised a pane past its share, so the panes overrun the host and
    // a host that clips cuts the last axis off. The largest shared pane gives
    // the excess back, down to its own floor.
    const over = Object.values(out).reduce((sum, h) => sum + h, 0) - host.clientHeight;
    const big = all.filter((p) => p.share).sort((a, b) => out[b.key] - out[a.key])[0];
    if (over > 0 && big) out[big.key] = Math.max(MIN_PANE, out[big.key] - over);
    return out;
  }

  // every spec first, so the first pane built knows what the others take
  for (const p of spec.panes) specs[p.key] = p;
  for (const p of spec.panes) {
    divs[p.key] = host.appendChild(document.createElement("div"));
    build(p);
  }

  /** "zoom" or "select"; a select drag is x only. */
  group.setMode = (mode) => {
    group.mode = mode;
    for (const u of Object.values(group.panes)) u.cursor.drag.y = mode === "zoom";
  };

  /** Every pane back to the whole x range, and every y range back to its data. */
  group.reset = () => {
    for (const k of Object.keys(pins)) delete pins[k];
    for (const u of Object.values(group.panes)) u.setData(u.data, true);
  };

  /**
   * New numbers for one pane, the reader's zoom kept. `setData(…, false)`
   * re-ranges nothing, so an unzoomed y kept the old numbers' range. Setting x
   * at itself re-ranges y through its range function, which holds a pinned y.
   */
  group.setData = (key, data) => {
    const u = group.panes[key];
    u.setData([spec.x, ...data], false);
    u.setScale("x", { min: u.scales.x.min, max: u.scales.x.max });
  };

  /**
   * A new x and new numbers for every pane, as a new payload brings. `keep`
   * holds the reader's x range and every y they chose, as `setData` does for
   * one pane. Otherwise every pane shows the whole of the new x, as a reset
   * does. `data` is keyed by pane, and a pane it leaves out keeps its series.
   */
  group.load = (x, data, keep = false) => {
    const first = Object.values(group.panes)[0];
    const lo = first.scales.x.min, hi = first.scales.x.max;
    if (!keep) for (const k of Object.keys(pins)) delete pins[k];
    spec.x = x;
    for (const [key, u] of Object.entries(group.panes)) {
      u.setData([x, ...(data[key] ?? u.data.slice(1))], !keep);
      if (keep) u.setScale("x", { min: lo, max: hi });
    }
  };

  /** Forget the y range the reader chose on `key`, or on every pane, so the next x range fits y to the data. */
  group.unpin = (key) => { for (const k of key ? [key] : Object.keys(pins)) delete pins[k]; };

  /** Repaint every pane. Colours are functions read at each draw, so this is a theme switch (finding 5). */
  group.redraw = () => { for (const u of Object.values(group.panes)) u.redraw(false, true); };

  /**
   * A pane rebuilt on another y scale. uPlot takes its scales at construction
   * (finding 5), so a scale switch is a new pane, placed where the old one was
   * and shown at the same x. `data` replaces its series' numbers, which a log
   * scale needs, since it cannot place a value at or under zero.
   */
  group.setY = (key, kind, data) => {
    const old = group.panes[key], lo = old.scales.x.min, hi = old.scales.x.max;
    specs[key] = { ...specs[key], y: kind, data: data ?? old.data.slice(1) };
    old.destroy();
    delete pins[key];
    build(specs[key]);
    group.setX(lo, hi);
  };

  /** Give one pane a new height; the panes with a `share` split what is left. */
  group.setHeight = (key, height) => {
    specs[key] = { ...specs[key], height };
    fit();
  };

  // uPlot has no autosize. A ResizeObserver runs after layout and before paint,
  // and setSize commits in the microtask after it, so a new size shows in the
  // same frame, with no timer.
  function fit() {
    const h = heights(), w = host.clientWidth;
    for (const [key, u] of Object.entries(group.panes)) {
      if (u.width !== w || u.height !== h[key]) u.setSize({ width: w, height: h[key] });
    }
  }
  const observer = new ResizeObserver(fit);
  observer.observe(host);

  // ------------------------------------------------------------ exports (D6)

  /** The indices of `spec.x` in view, as [i0, i1). Both ends are in the view. */
  group.inView = () => {
    const { min, max } = Object.values(group.panes)[0].scales.x;
    return [lower(spec.x, min), upper(spec.x, max)];
  };

  /**
   * The panes as one canvas, top to bottom, at the device's resolution. uPlot
   * leaves its canvas transparent (finding 8), so the ground is filled first.
   */
  group.image = () => {
    const canvases = Object.values(group.panes).map((u) => u.ctx.canvas);
    const out = document.createElement("canvas");
    out.width = Math.max(...canvases.map((c) => c.width));
    out.height = canvases.reduce((sum, c) => sum + c.height, 0);
    const g = out.getContext("2d");
    g.fillStyle = groundOf(host);
    g.fillRect(0, 0, out.width, out.height);
    let y = 0;
    for (const c of canvases) { g.drawImage(c, 0, y); y += c.height; }
    return out;
  };

  /** The panes as a PNG blob. */
  group.png = () => new Promise((resolve, reject) => group.image().toBlob(
    (blob) => (blob ? resolve(blob) : reject(new Error("the browser made no PNG"))), "image/png"));

  /**
   * The panes as a PNG on the clipboard. The item takes the blob's promise,
   * so the write starts inside the press: Safari refuses a write made after
   * an await has spent the user's activation.
   */
  group.copyImage = async () => {
    const blob = group.png();
    await navigator.clipboard.write([new ClipboardItem({ "image/png": blob })]);
    return blob;
  };

  /**
   * The panes as one SVG document, each pane redrawn once into svgcanvas
   * (finding 6). `load` resolves to the svgcanvas module, so a page that never
   * exports never loads it. Each pane is a nested `<svg>` in device pixels,
   * scaled to its CSS size by its `viewBox`, as uPlot draws at the device's
   * resolution and the module's hooks do too.
   */
  group.svg = async (load) => {
    const { Context } = await load();
    const r = devicePixelRatio, parts = [];
    let top = 0, width = 0;
    for (const [key, live] of Object.entries(group.panes)) {
      const w = live.width, h = live.height;
      const el = await record(Context, w * r, h * r,
                              (div) => new uPlot(options(specs[key], live), live.data, div));
      for (const [name, value] of [["x", 0], ["y", top], ["width", w], ["height", h],
                                   ["viewBox", `0 0 ${w * r} ${h * r}`]]) el.setAttribute(name, value);
      parts.push(new XMLSerializer().serializeToString(el));
      top += h;
      width = Math.max(width, w);
    }
    return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${top}" `
      + `viewBox="0 0 ${width} ${top}"><rect width="100%" height="100%" fill="${groundOf(host)}"/>`
      + `${parts.join("")}</svg>`;
  };

  /**
   * What the figure holds in view, as tab-separated text a spreadsheet
   * pastes. A figure says what its columns are by setting `group.table` to a
   * function returning `{ names, rows }`.
   */
  group.tsv = () => {
    if (!group.table) throw new Error("rxplot: this figure has no table");
    const { names, rows } = group.table();
    return tsv(names, rows);
  };

  group.destroy = () => {
    observer.disconnect();
    for (const u of Object.values(group.panes)) u.destroy();
    for (const d of Object.values(divs)) d.remove();
  };
  return group;
}

/** The colour behind `el`: its nearest ancestor's background that is not transparent. */
function groundOf(el) {
  for (let e = el; e; e = e.parentElement) {
    const c = getComputedStyle(e).backgroundColor;
    if (c && c !== "transparent" && !/^rgba\(.*,\s*0\)$/.test(c)) return c;
  }
  return "#ffffff";
}

/**
 * A `Path2D` that records what is drawn into it, for svgcanvas to replay.
 * svgcanvas cannot read a native one, and uPlot strokes every series through
 * one (finding 6).
 */
class Recorded {
  constructor(from) { this.ops = from instanceof Recorded ? from.ops.slice() : []; }
  addPath(p) { if (p instanceof Recorded) this.ops.push(...p.ops); }
}
for (const op of ["moveTo", "lineTo", "rect", "arc", "arcTo", "ellipse", "bezierCurveTo",
                  "quadraticCurveTo", "closePath"]) {
  Recorded.prototype[op] = function (...args) { this.ops.push([op, args]); };
}

/**
 * One chart built by `make` into svgcanvas's context, as that context's SVG
 * element. For the draw uPlot commits a microtask after construction,
 * `Path2D` is the recording class and the first 2D context asked for is
 * svgcanvas's. Both are put back before this returns, whatever happens.
 */
async function record(Context, width, height, make) {
  const native = window.Path2D, get = HTMLCanvasElement.prototype.getContext;
  let svg = null, u = null, taken = false;
  HTMLCanvasElement.prototype.getContext = function (type, ...rest) {
    // taken before the context is made: svgcanvas's constructor asks for a
    // native 2D context of its own, which re-entered here without end
    if (taken || type !== "2d") return get.call(this, type, ...rest);
    taken = true;
    svg = new Context({ width, height });
    for (const m of ["stroke", "fill", "clip"]) {
      const own = svg[m].bind(svg);
      svg[m] = (path, ...more) => {
        if (!(path instanceof Recorded)) return own(path, ...more);
        svg.beginPath();
        for (const [op, args] of path.ops) svg[op](...args);
        return own(...more);
      };
    }
    return svg;
  };
  const div = document.body.appendChild(document.createElement("div"));
  div.style.cssText = "position:fixed;left:-100000px;top:0";
  window.Path2D = Recorded;
  try {
    u = make(div);
    await Promise.resolve();
    await Promise.resolve();
  } finally {
    HTMLCanvasElement.prototype.getContext = get;
    window.Path2D = native;
    u?.destroy();
    div.remove();
  }
  return svg.getSvg();
}

/** `blob` saved as a file named `name`, as a download link does. */
export function download(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // late, not at once: Firefox and Safari read the URL after the click
  // returns, and a revoked one saves nothing
  setTimeout(() => URL.revokeObjectURL(a.href), 60_000);
}

/**
 * The four exports (D6) as buttons, for a page with no framework of its own to
 * place in its controls. `name()` is the file name without its extension,
 * `svgcanvas` loads that module (`group.svg`), and `say(text)` reports what
 * happened, a failure included, since a clipboard can refuse.
 */
export function exportButtons(figure, { name, svgcanvas, say }) {
  const act = (label, title, run) => {
    const b = document.createElement("button");
    b.type = "button";
    b.textContent = label;
    b.title = title;
    b.onclick = async () => {
      try { say(await run()); } catch (e) { say(`${label} failed: ${e.message}`); }
    };
    return b;
  };
  return [
    act("PNG", "save the figure as a PNG, as drawn", async () => {
      download(await figure().png(), `${name()}.png`);
      return "saved a PNG";
    }),
    act("SVG", "save the figure as an SVG, redrawn as vectors", async () => {
      const text = await figure().svg(svgcanvas);
      download(new Blob([text], { type: "image/svg+xml" }), `${name()}.svg`);
      return "saved an SVG";
    }),
    act("copy image", "copy the figure to the clipboard as a PNG", async () => {
      await figure().copyImage();
      return "copied the figure";
    }),
    act("copy data", "copy what is in view as tab-separated columns", async () => {
      const text = figure().tsv();
      await navigator.clipboard.writeText(text);
      return `copied ${text.split("\n").length - 1} rows`;
    }),
  ];
}

// ---------------------------------------------------------------- the pattern

/** `values` with every entry at or under zero made a gap, which a log scale needs. */
export function positive(values) {
  return Array.from(values, (v) => (v != null && v > 0 ? v : null));
}

/** The tick band's height in CSS px for `rows` phases, its bare x axis included. */
export function tickHeight(rows) {
  return 6 + X_BARE + 16 * rows;
}

/**
 * The ink of tick row `row` of `count`. A single row takes the observed points'
 * neutral: colour tells rows apart, and one row has nothing to be told from.
 */
export function phaseInk(colors, row, count) {
  return count <= 1 ? colors.obs : colors.phase[row % colors.phase.length];
}

/** One stroke per device-pixel column for each of `xs` in view, `top` and `height` in canvas px. */
export function vlines(u, xs, top, height, color) {
  // [min, max], both ends in: a line at the view's edge is in the view
  const { ctx } = u, max = u.scales.x.max, i0 = lower(xs, u.scales.x.min);
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1;
  // uPlot leaves the last series' dash on the context, into the next frame too
  ctx.setLineDash([]);
  ctx.beginPath();
  let last = NaN;
  for (let i = i0; i < xs.length && xs[i] <= max; i++) {
    const p = Math.round(u.valToPos(xs[i], "x", true)) + 0.5;
    if (p === last) continue;
    last = p;
    ctx.moveTo(p, top);
    ctx.lineTo(p, top + height);
  }
  ctx.stroke();
  ctx.restore();
}

/** One row of `vlines` per phase of `ticks` across the band `u`, but for the phases `skip` names. */
function tickRows(u, ticks, colors, skip) {
  const phases = Object.keys(ticks);
  if (!phases.length) return;
  const { top, height } = u.bbox, row = height / phases.length, pad = row / 4;
  phases.forEach((phase, r) => {
    if (skip(phase)) return;
    vlines(u, ticks[phase], top + r * row + pad, row - 2 * pad, phaseInk(colors, r, phases.length));
  });
}

/** A line across the plot area at y = 0, when zero is in view. */
function zeroLine(u, color) {
  const y = Math.round(u.valToPos(0, "y", true)) + 0.5, { top, height, left, width } = u.bbox;
  if (y < top || y > top + height) return;
  const { ctx } = u;
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = devicePixelRatio;
  ctx.setLineDash([]);
  ctx.beginPath();
  ctx.moveTo(left, y);
  ctx.lineTo(left + width, y);
  ctx.stroke();
  ctx.restore();
}

/**
 * A uPlot `paths` builder drawing one square marker at each device-pixel
 * column's lowest and highest point (D5). The pilot measured every marker
 * against this on the real panel: every marker made long frames of 50-127 ms
 * at 132 992 channels in chromium, and of 166-258 ms at 59 498 in Firefox and
 * WebKit, where this made none in chromium at either size. Which points a
 * payload carries is still the server's to decide; this decides which of them
 * are painted, and a hit test or the readout still reads every one.
 */
function thinMarkers(size) {
  return (u, si, i0, i1) => {
    const xs = u.data[0], ys = u.data[si], d = size * devicePixelRatio, h = d / 2, p = new Path2D();
    let col = NaN, lo = 0, hi = 0, loY = 0, hiY = 0;
    const flush = () => {
      if (Number.isNaN(col)) return;
      p.rect(col - h, loY - h, d, d);
      if (hiY !== loY) p.rect(col - h, hiY - h, d, d);
    };
    for (let i = i0; i <= i1; i++) {
      const y = ys[i];
      if (y == null) continue;
      const X = Math.round(u.valToPos(xs[i], "x", true)), Y = u.valToPos(y, "y", true);
      if (X !== col) { flush(); col = X; lo = hi = y; loY = hiY = Y; }
      else if (y < lo) { lo = y; loY = Y; }
      else if (y > hi) { hi = y; hiY = Y; }
    }
    flush();
    return { stroke: null, fill: p, clip: null, band: null, gaps: null, flags: 0 };
  };
}

/** The main pane's curves, in series order, by the ids `hidden` uses. */
const MAIN = ["obs", "masked", "calc", "bkg"];

/** Which of a curves payload's arrays each residual is. */
const RESIDUALS = { weighted: "delta", delta: "delta_raw", cumulative: "cumulative_chi2" };

/** Each residual's column name in a table. The cumulative χ² is re-based as drawn. */
const RESIDUAL_COLUMNS = { weighted: "delta_over_sigma", delta: "obs_minus_calc",
                           cumulative: "cumulative_chi2_in_view" };

/**
 * The diffraction pattern (D3): observed points over the model, a band of
 * reflection ticks, and the residual under both, on the pattern's own channels.
 *
 * `curves` is an unpacked curves payload (D4, `unpack`): every channel's
 * `two_theta` and `y_obs`, `kept` for the channels the protocol fits, and with
 * a fit, `fitted` and the model arrays on the channels it kept. The observed
 * points split by `kept` into the fitted and the masked, and the model lands on
 * the grid through `fitted`, null elsewhere (finding 10).
 *
 * `spec`:
 *
 * - `colors()`: `{ obs, masked, calc, bkg, diff, zero, phase }`, read at every
 *   draw, so a theme switch is a `redraw`. `phase` is one ink per tick row.
 * - The observed points are painted as each pixel column's lowest and
 *   highest (D5, `thinMarkers`).
 * - `y`: the intensity scale, "lin", "sqrt" or "log". `residual`: "weighted",
 *   "delta" or "cumulative".
 * - `hidden`: the curves not drawn, as "obs", "masked", "calc", "bkg", "diff"
 *   and "ticks:<phase>".
 * - `labels`: `{ y, resid }`, the two y axis titles, as functions.
 * - `layers`: per pane key ("main", "ticks", "resid"), `{ under, over }` lists
 *   of `(u) => void`, run before the grid and after the series.
 * - `rawResidual()`: the residual pane's values over the pattern's channels
 *   when the payload carries no fit, or null for none. The GUI draws its peak
 *   groups' own residual there.
 * - `ranges`: `{ main, resid }`, each that pane's `auto` (`panes`), for a
 *   page whose y ranges are its own. The watcher holds the intensity to the
 *   observed points and the residual to a ladder of rungs, so neither moves
 *   while the fit does.
 *
 * A cumulative χ² is re-based at every x zoom (`chi2Base`), so it starts at
 * zero at the view's left edge, as the window route's did.
 *
 * The figure is the pane group (`panes`) with six more verbs: `setCurves`,
 * `setY`, `setResidual`, `setHidden`, `refreshResidual`, and `chi2Base`, the
 * Σχ² the drawn curve has subtracted.
 */
export function pattern(uPlot, host, curves, spec) {
  const state = { y: spec.y ?? "lin", residual: spec.residual ?? "weighted",
                  hidden: new Set(spec.hidden ?? []), c: null, base: 0 };
  const ink = (key) => () => spec.colors()[key];
  const size = { obs: 4, masked: 3 };

  function prepare(payload) {
    const { header, arrays } = payload, n = arrays.two_theta.length;
    const [obs, masked] = partition(arrays.y_obs, arrays.kept);
    const on = (a) => (header.fit && a ? scatter(n, arrays.fitted, a) : new Array(n).fill(null));
    // the fitted channels' 2θ, which a Σχ² base is looked up on
    const fitTT = header.fit ? Float64Array.from(arrays.fitted, (i) => arrays.two_theta[i]) : null;
    return { header, arrays, n, obs, masked, calc: on(arrays.y_calc), bkg: on(arrays.y_background),
             on, fitTT, resid: {}, ticks: header.ticks ?? {} };
  }

  const cumulative = () => state.residual === "cumulative" && !!state.c.fitTT;
  const baseAt = (lo) => (cumulative() ? chi2Base(state.c.arrays.cumulative_chi2, state.c.fitTT, lo) : 0);

  const scaled = (values) => (state.y === "log" ? positive(values) : values);
  const mainData = () => [state.c.obs, state.c.masked, state.c.calc, state.c.bkg].map(scaled);
  const nulls = () => [new Array(state.c.n).fill(null)];
  const residData = () => {
    const c = state.c, key = RESIDUALS[state.residual];
    if (!key) throw new Error(`rxplot: no residual "${state.residual}"; one of ${Object.keys(RESIDUALS).join(", ")}`);
    if (!c.header.fit) return [spec.rawResidual?.() ?? nulls()[0]];
    if (cumulative()) {
      // re-based in place: a wheel zoom moves the base on nearly every event,
      // and a fresh pair of channel-length arrays each time is garbage per tick
      const cum = c.arrays.cumulative_chi2, at = c.arrays.fitted, b = state.base;
      const out = (c.resid.rebased ??= new Array(c.n).fill(null));
      for (let q = 0; q < at.length; q++) out[at[q]] = cum[q] - b;
      return [out];
    }
    c.resid[key] ??= c.on(c.arrays[key]);
    return [c.resid[key]];
  };
  /** The residual pane's curve is drawn. Before a fit it is the page's
   *  `rawResidual`, whose own toggle is the page's, so "diff" does not hide it. */
  const residShown = () => !(state.c.header.fit && state.hidden.has("diff"));

  function markers(key) {
    return { show: !state.hidden.has(key), stroke: ink(key), fill: ink(key),
             alpha: key === "masked" ? 0.45 : 1, paths: thinMarkers(size[key]), points: { show: false } };
  }

  const drawTicks = (u) => tickRows(u, state.c.ticks, spec.colors(), (phase) => state.hidden.has(`ticks:${phase}`));

  function drawZero(u) {
    if (state.residual !== "cumulative") zeroLine(u, spec.colors().zero);
  }

  function hooks(key, own = {}) {
    const layer = spec.layers?.[key] ?? {};
    return { drawClear: [...(layer.under ?? [])], drawAxes: own.drawAxes ?? [],
             draw: [...(own.draw ?? []), ...(layer.over ?? [])] };
  }

  state.c = prepare(curves);
  const group = panes(uPlot, host, {
    x: curves.arrays.two_theta,
    panes: [
      { key: "main", share: 0.76, y: state.y, auto: spec.ranges?.main, label: () => spec.labels?.y?.() ?? "",
        series: [markers("obs"), markers("masked"),
                 { show: !state.hidden.has("calc"), stroke: ink("calc"), width: 1.2 },
                 { show: !state.hidden.has("bkg"), stroke: ink("bkg"), width: 1, dash: [3, 3] }],
        data: mainData(), hooks: hooks("main") },
      { key: "ticks", height: tickHeight(Object.keys(state.c.ticks).length), range: [0, 1], yLabels: false,
        series: [{ show: false }], data: nulls(), hooks: hooks("ticks", { draw: [drawTicks] }) },
      { key: "resid", share: 0.24, xLabels: true, xLabel: "2θ (°)", auto: spec.ranges?.resid,
        label: () => spec.labels?.resid?.() ?? "",
        series: [{ show: residShown(), stroke: ink("diff"), width: 1 }],
        data: residData(), hooks: hooks("resid", { drawAxes: [drawZero] }) },
    ],
  });

  /**
   * Every x zoom re-bases a cumulative Σχ² before the panes move, so the new
   * numbers and the new range reach the residual pane in one paint. uPlot's
   * echo of the range comes back through here at the same base and does nothing.
   */
  const setX = group.setX;
  group.setX = (lo, hi) => {
    const b = baseAt(lo);
    if (b !== state.base) {
      state.base = b;
      group.setData("resid", residData());
    }
    setX(lo, hi);
  };

  /** The Σχ² the drawn cumulative curve has subtracted, 0 under any other residual. */
  group.chi2Base = () => (cumulative() ? state.base : 0);

  /** Every channel in view: the observed point, whether it is excluded, and the model and residual as drawn. */
  group.table = () => {
    const [i0, i1] = group.inView(), c = state.c, resid = residData()[0], rows = [];
    for (let i = i0; i < i1; i++) {
      rows.push([c.arrays.two_theta[i], c.arrays.y_obs[i], c.masked[i] == null ? 0 : 1,
                 c.calc[i], c.bkg[i], resid[i]]);
    }
    // before a fit the pane is the page's `rawResidual`, whatever residual is chosen
    const residName = c.header.fit ? RESIDUAL_COLUMNS[state.residual] : "residual";
    return { names: ["two_theta", "y_obs", "excluded", "y_calc", "y_background", residName], rows };
  };

  /** A new payload. `keep` holds the reader's view, as a run landing should. */
  group.setCurves = (payload, keep = false) => {
    state.c = prepare(payload);
    state.base = keep ? baseAt(group.panes.main.scales.x.min) : 0;
    const rows = tickHeight(Object.keys(state.c.ticks).length);
    if (group.panes.ticks.height !== rows) group.setHeight("ticks", rows);
    group.load(payload.arrays.two_theta, { main: mainData(), ticks: nulls(), resid: residData() }, keep);
    // a fit arriving or leaving changes what "diff" governs (`residShown`)
    const resid = group.panes.resid, show = residShown();
    if (resid.series[1].show !== show) resid.setSeries(1, { show });
  };

  /** Another intensity scale, the x range kept. The rebuilt pane takes its
   *  series from the spec, whose `show` is the construction's, so the curves
   *  hidden since are hidden again. */
  const rebuild = group.setY;
  group.setY = (kind) => {
    state.y = kind;
    rebuild("main", kind, mainData());
    group.setHidden([...state.hidden]);
  };

  /** Another residual. A y range chosen on the old one means nothing on this one. */
  group.setResidual = (kind) => {
    state.residual = kind;
    state.base = baseAt(group.panes.resid.scales.x.min);
    group.unpin("resid");
    group.setData("resid", residData());
  };

  /** The residual pane's values again, its y range kept: `rawResidual` has new numbers. */
  group.refreshResidual = () => group.setData("resid", residData());

  /** Draw every curve but `ids`. */
  group.setHidden = (ids) => {
    state.hidden = new Set(ids);
    const { main, resid, ticks } = group.panes;
    main.batch(() => MAIN.forEach((id, i) => {
      const show = !state.hidden.has(id);
      if (main.series[i + 1].show !== show) main.setSeries(i + 1, { show });
    }));
    const diff = residShown();
    if (resid.series[1].show !== diff) resid.setSeries(1, { show: diff });
    ticks.redraw(false, false);
  };

  return group;
}

// ---------------------------------------------------------------- the overlay

/**
 * Several fits of one pattern over each other (D3): the `rietx compare` figure.
 *
 * `data`:
 *
 * - `x`, the fitted channels' 2θ. Every fit shares it, since a variant changes
 *   the model and never the channels (D8).
 * - `obs`, the observed points on `x`.
 * - `ticks`, `{ phase: [2θ] }`, one row of the tick band each.
 * - `fits`, `[{ key, calc, delta, cum }]`, each array on `x`: the calculated
 *   pattern, (obs − calc)/σ and the cumulative χ².
 *
 * Three panes and the tick band, in the order the page explains them:
 *
 * - `cum`, each fit's cumulative χ² less the reference's, a subtraction on the
 *   one grid. The reference is drawn too, flat at zero, so every pane has the
 *   same series and a new reference is new numbers for one pane.
 * - `diff`, each fit's (obs − calc)/σ.
 * - `fit`, the observed points under every calculated curve, and the tick band
 *   under it, carrying its x axis.
 *
 * `spec`:
 *
 * - `colors()`: `{ obs, zero, phase, fits }`, read at every draw. `fits` maps
 *   each key to its ink and `phase` has one ink per tick row.
 * - `reference`: the key the Δχ² is taken against. A key no fit has leaves
 *   the `cum` pane empty.
 * - `hidden`: the keys of the fits not drawn.
 * - `labels`: `{ cum, diff, fit }`, the y axis titles, as functions.
 * - `height`: each pane's height in CSS px, 300 by default.
 *
 * The figure is the pane group (`panes`) with `setReference` and `setHidden`.
 */
export function overlay(uPlot, host, data, spec) {
  const state = { reference: spec.reference, hidden: new Set(spec.hidden ?? []) };
  const height = spec.height ?? 300, xLabel = "2θ (°)";
  // a reference with no fit here draws nothing, rather than a Δχ² against another fit
  const cumData = () => {
    const ref = data.fits.find((f) => f.key === state.reference)?.cum;
    return data.fits.map((f) => (ref ? difference(f.cum, ref) : new Array(data.x.length).fill(null)));
  };
  const line = (f, width) => ({ show: !state.hidden.has(f.key), stroke: () => spec.colors().fits[f.key], width });
  const lines = (width) => data.fits.map((f) => line(f, width));
  const label = (key) => () => spec.labels?.[key]?.() ?? "";
  const zero = (u) => zeroLine(u, spec.colors().zero);
  const obs = () => spec.colors().obs;
  const rows = Object.keys(data.ticks).length;

  const group = panes(uPlot, host, {
    x: data.x,
    panes: [
      { key: "cum", height, xLabels: true, xLabel, label: label("cum"), series: lines(1.6),
        data: cumData(), hooks: { drawAxes: [zero] } },
      { key: "diff", height, xLabels: true, xLabel, label: label("diff"), series: lines(1),
        data: data.fits.map((f) => f.delta), hooks: { drawAxes: [zero] } },
      { key: "fit", height, label: label("fit"),
        series: [{ stroke: obs, fill: obs, paths: thinMarkers(3), points: { show: false } }, ...lines(1.1)],
        data: [data.obs, ...data.fits.map((f) => f.calc)] },
      // the band carries the x axis the pattern above it leaves out
      { key: "ticks", height: tickHeight(rows) - X_BARE + X_LABELS + TITLE, range: [0, 1], yLabels: false,
        xLabels: true, xLabel, series: [{ show: false }], data: [new Array(data.x.length).fill(null)],
        hooks: { draw: [(u) => tickRows(u, data.ticks, spec.colors(), () => false)] } },
    ],
  });

  /** Take the Δχ² against another fit. The same one again recomputes nothing. */
  group.setReference = (key) => {
    if (key === state.reference) return;
    state.reference = key;
    group.setData("cum", cumData());
  };

  /** Every channel in view: the observed point, then each fit drawn, as its three panes draw it. */
  group.table = () => {
    const [i0, i1] = group.inView(), { cum, diff, fit } = group.panes, rows = [];
    const shown = data.fits.map((f, i) => [f, i]).filter(([f]) => !state.hidden.has(f.key));
    for (let i = i0; i < i1; i++) {
      const row = [data.x[i], data.obs[i]];
      for (const [, j] of shown) row.push(fit.data[2 + j][i], diff.data[1 + j][i], cum.data[1 + j][i]);
      rows.push(row);
    }
    const names = ["two_theta", "y_obs"];
    for (const [f] of shown) names.push(`${f.key}:y_calc`, `${f.key}:delta_over_sigma`, `${f.key}:delta_chi2`);
    return { names, rows };
  };

  /** Draw every fit but `keys`, in every pane. */
  group.setHidden = (keys) => {
    state.hidden = new Set(keys);
    for (const key of ["cum", "diff", "fit"]) {
      const u = group.panes[key], first = key === "fit" ? 2 : 1;
      u.batch(() => data.fits.forEach((f, i) => {
        const show = !state.hidden.has(f.key);
        if (u.series[first + i].show !== show) u.setSeries(first + i, { show });
      }));
    }
  };

  return group;
}

// ---------------------------------------------------------------- the trajectory

/** `v` when it is a finite number, else null: a value or an esd a fit did not give. */
const finite = (v) => (typeof v === "number" && Number.isFinite(v) ? v : null);

/** The marks a trajectory can hide by id, as `setHidden` takes them. */
const TRAJECTORY_MARKS = ["forward", "esd", "backward", "rings", "crosses"];

/** The distance, in CSS pixels, within which the pointer names a point. */
const REACH = 8;

/**
 * A parameter across a series (D3, D8): its value at each pattern's
 * coordinate, joined in chain order, with its esd as a whisker.
 *
 * Chain order is not x order. A heat-then-cool series comes back along its own
 * x, while uPlot draws a series over one ascending x. So the figure paints its
 * marks in a draw hook, over one pane whose single series only sets the x
 * extent, and uPlot keeps the axes, the grid and the gestures.
 *
 * `traj`: `{ x, value, stderr, backward }` in chain order. `stderr` and
 * `backward` may be absent, and a null anywhere is a point with no value.
 *
 * `spec`:
 *
 * - `colors()`: `{ tone, warn, muted }`, read at every draw. `tone` is the
 *   forward chain's, `warn` the rings' and crosses', `muted` the backward
 *   chain's.
 * - `dashed`: the forward chain is drawn dashed, as a path-dependent
 *   parameter's is.
 * - `rings`, `crosses`: one boolean per point. A ring marks a point the
 *   chain reseeded, and a cross a point no rung recovered. Both points stay
 *   in the chain: a gap reads as data nobody collected.
 * - `hidden`: the marks not drawn, from "forward", "esd", "backward",
 *   "rings" and "crosses".
 * - `xLabel`, `yLabel`: the axis titles.
 *
 * A point with no esd has no whisker at all. A whisker of zero length would
 * claim the value was measured exactly.
 *
 * The figure is the pane group (`panes`) with `setHidden`, and `onPoint`,
 * which the page sets: it is called with `{ i, chain, left, top }` for the
 * point nearest the pointer within reach, `chain` "forward" or "backward" and
 * `left`, `top` its CSS px in the plot area, or with null.
 */
export function trajectory(uPlot, host, traj, spec) {
  const t = traj, n = t.x.length;
  const hidden = new Set(spec.hidden ?? []);
  const shown = (id) => !hidden.has(id);
  const value = (i) => finite(t.value[i]), esd = (i) => finite(t.stderr?.[i]);
  const back = (i) => (t.backward ? finite(t.backward[i]) : null);

  // uPlot's one x must ascend, so its series is the chain sorted by x
  const order = Array.from({ length: n }, (_, i) => i).sort((a, b) => t.x[a] - t.x[b]);
  const xs = Float64Array.from(order, (i) => t.x[i]);

  /** The y range: every chain and every whisker's two ends, over the x in view. */
  function extent(u) {
    const idxs = u.series[0].idxs;
    const lo = idxs?.length ? xs[idxs[0]] : -Infinity, hi = idxs?.length ? xs[idxs[1]] : Infinity;
    let min = Infinity, max = -Infinity;
    const take = (v) => { if (v != null) { min = Math.min(min, v); max = Math.max(max, v); } };
    for (let i = 0; i < n; i++) {
      if (!(t.x[i] >= lo && t.x[i] <= hi)) continue;
      const v = value(i), e = esd(i);
      take(v);
      take(back(i));
      if (v != null && e != null) { take(v - e); take(v + e); }
    }
    return Number.isFinite(min) ? uPlot.rangeNum(min, max, 0.1, true) : [0, 1];
  }

  /** A line through `at(i)` in chain order, broken where a point has no value. */
  function chain(u, at, color, width, dash) {
    const { ctx } = u;
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.setLineDash(dash);
    ctx.beginPath();
    let open = false;
    for (let i = 0; i < n; i++) {
      const v = at(i);
      if (v == null) { open = false; continue; }
      const X = u.valToPos(t.x[i], "x", true), Y = u.valToPos(v, "y", true);
      if (open) ctx.lineTo(X, Y); else ctx.moveTo(X, Y);
      open = true;
    }
    ctx.stroke();
  }

  /** `mark(ctx, X, Y)` at every point `at` gives a value and `where` allows, then one stroke or fill. */
  function each(u, at, where, mark, paint) {
    const { ctx } = u;
    ctx.setLineDash([]);
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const v = at(i);
      if (v == null || !where(i)) continue;
      mark(ctx, u.valToPos(t.x[i], "x", true), u.valToPos(v, "y", true), i);
    }
    ctx[paint]();
  }

  function draw(u) {
    const c = spec.colors(), r = devicePixelRatio, { ctx } = u, { left, top, width, height } = u.bbox;
    const all = () => true;
    ctx.save();
    ctx.beginPath();
    ctx.rect(left, top, width, height);
    ctx.clip();
    if (t.backward && shown("backward")) {
      chain(u, back, c.muted, r, [r, 3 * r]);
      ctx.lineWidth = r;
      ctx.strokeStyle = c.muted;
      const d = 3 * r;
      each(u, back, all, (g, X, Y) => {
        g.moveTo(X, Y - d); g.lineTo(X + d, Y); g.lineTo(X, Y + d); g.lineTo(X - d, Y); g.closePath();
      }, "stroke");
    }
    if (shown("esd")) {
      ctx.lineWidth = r;
      ctx.strokeStyle = c.tone;
      const cap = 3 * r;
      each(u, value, (i) => esd(i) != null, (g, X, Y, i) => {
        const lo = u.valToPos(value(i) - esd(i), "y", true), hi = u.valToPos(value(i) + esd(i), "y", true);
        g.moveTo(X, lo); g.lineTo(X, hi);
        g.moveTo(X - cap, lo); g.lineTo(X + cap, lo);
        g.moveTo(X - cap, hi); g.lineTo(X + cap, hi);
      }, "stroke");
    }
    if (shown("forward")) {
      chain(u, value, c.tone, 1.4 * r, spec.dashed ? [6 * r, 4 * r] : []);
      ctx.fillStyle = c.tone;
      each(u, value, all, (g, X, Y) => { g.moveTo(X + 3 * r, Y); g.arc(X, Y, 3 * r, 0, 2 * Math.PI); }, "fill");
    }
    ctx.strokeStyle = c.warn;
    if (spec.rings && shown("rings")) {
      ctx.lineWidth = 1.4 * r;
      each(u, value, (i) => spec.rings[i], (g, X, Y) => {
        g.moveTo(X + 6.5 * r, Y); g.arc(X, Y, 6.5 * r, 0, 2 * Math.PI);
      }, "stroke");
    }
    if (spec.crosses && shown("crosses")) {
      ctx.lineWidth = 2.2 * r;
      const d = 5 * r;
      each(u, value, (i) => spec.crosses[i], (g, X, Y) => {
        g.moveTo(X - d, Y - d); g.lineTo(X + d, Y + d); g.moveTo(X - d, Y + d); g.lineTo(X + d, Y - d);
      }, "stroke");
    }
    ctx.restore();
  }

  // a series that paints nothing: the chain is the hook's to draw
  const none = () => ({ stroke: null, fill: null, clip: null, band: null, gaps: null, flags: 0 });
  const group = panes(uPlot, host, {
    x: xs,
    panes: [{ key: "traj", share: 1, xLabels: true, xLabel: spec.xLabel ?? "", label: spec.yLabel ?? "",
              auto: extent, series: [{ paths: none, points: { show: false } }],
              data: [Array.from(order, (i) => value(i))], hooks: { draw: [draw] } }],
  });

  group.onPoint = null;
  group.onCursor = (hit) => {
    if (!group.onPoint) return;
    if (!hit) { group.onPoint(null); return; }
    const u = group.panes.traj;
    const X = t.x.map((x) => u.valToPos(x, "x"));
    const Y = (at) => Array.from({ length: n }, (_, i) => (at(i) == null ? null : u.valToPos(at(i), "y")));
    const chains = [["forward", value], ["backward", back]].filter(([id]) => shown(id));
    let best = null;
    for (const [id, at] of chains) {
      const ys = Y(at), i = nearestXY(X, ys, hit.left, hit.top, REACH);
      if (i < 0) continue;
      const d = (X[i] - hit.left) ** 2 + (ys[i] - hit.top) ** 2;
      if (!best || d < best.d) best = { i, chain: id, left: X[i], top: ys[i], d };
    }
    group.onPoint(best && { i: best.i, chain: best.chain, left: best.left, top: best.top });
  };

  /** Draw every mark but `ids`. */
  group.setHidden = (ids) => {
    hidden.clear();
    for (const id of ids) {
      if (!TRAJECTORY_MARKS.includes(id)) throw new Error(`rxplot: no trajectory mark "${id}"; one of ${TRAJECTORY_MARKS.join(", ")}`);
      hidden.add(id);
    }
    group.redraw();
  };

  /** Each pattern in view, in chain order: its place in the chain, its x, and the value with its esd. */
  group.table = () => {
    const { min, max } = group.panes.traj.scales.x, rows = [];
    for (let i = 0; i < n; i++) {
      if (!(t.x[i] >= min && t.x[i] <= max)) continue;
      rows.push(t.backward ? [i, t.x[i], value(i), esd(i), back(i)] : [i, t.x[i], value(i), esd(i)]);
    }
    return { names: ["pattern", "x", "value", "esd", ...(t.backward ? ["backward"] : [])], rows };
  };

  return group;
}
