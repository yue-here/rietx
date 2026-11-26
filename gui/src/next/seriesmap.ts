/**
 * The Map graph's arithmetic (WP-2243 task 7), apart from its drawing so a
 * vitest can hold it.
 *
 * The route (`GET /api/series/map`, `rietx.gui.series.map_payload`) sends
 * every staged pattern as a row of cells on one 2θ grid: `obs`, the mean count
 * in each cell, and `diff`, the mean Δ/σ over the channels each fit kept, NaN
 * where a cell has none. The Map reduces those cells to its pixel columns. A
 * pixel of the counts is the highest cell under it, so a peak narrower than a
 * pixel keeps its height, and a pixel of the difference is the mean of the
 * cells under it (round 12, calls 8 and 24).
 *
 * The colours are the WP's: cividis for the counts on a log scale, and red to
 * blue through the plot's ground at ±5 esd for the difference, red where the
 * model is too low. The cividis stops are matplotlib's `cividis` sampled at
 * nine points (Nuñez, Anderton & Renslow 2018, PLoS ONE 13, e0199239); the
 * two ends of the diverging scale are ColorBrewer's RdBu at 0.1 and 0.9, the
 * prototype's (round 12).
 */

export type Rgb = readonly [number, number, number];

/** matplotlib's `cividis` at 0, 1/8, … 1. */
export const CIVIDIS: readonly Rgb[] = [
  [0, 34, 78], [26, 56, 111], [67, 78, 108], [97, 101, 111], [125, 124, 120],
  [155, 148, 118], [188, 174, 108], [222, 201, 88], [254, 232, 56],
];

/** The difference's two ends: obs above calc, and obs below it. */
export const DIFF_HIGH: Rgb = [178, 24, 43];
export const DIFF_LOW: Rgb = [33, 102, 172];

/** The difference the scale saturates at, in esd (call 24). */
export const DIFF_LIMIT = 5;

/** The cut's averaging width a map opens with, in degrees 2θ (the prototype's). */
export const CUT_WIDTH = 0.02;

/** The colour at `f` in [0, 1] on cividis. */
export function cividis(f: number): Rgb {
  const t = Math.min(1, Math.max(0, Number.isFinite(f) ? f : 0)) * (CIVIDIS.length - 1);
  const k = Math.min(CIVIDIS.length - 2, Math.floor(t)), u = t - k;
  const a = CIVIDIS[k], b = CIVIDIS[k + 1];
  return [0, 1, 2].map((j) => Math.round(a[j] + (b[j] - a[j]) * u)) as unknown as Rgb;
}

/** The colour of a difference `v` in esd, through `mid` at zero. */
export function diverging(v: number, mid: Rgb): Rgb {
  const f = Math.min(1, Math.max(-1, v / DIFF_LIMIT));
  const end = f < 0 ? DIFF_LOW : DIFF_HIGH, u = Math.abs(f);
  return [0, 1, 2].map((j) => Math.round(mid[j] + (end[j] - mid[j]) * u)) as unknown as Rgb;
}

/** Where a count `v` sits on the log scale that ends at `top`. */
export function logFraction(v: number, top: number): number {
  if (!(top > 0)) return 0;
  return Math.log10(1 + Math.max(0, v)) / Math.log10(1 + top);
}

/** A token's `#rrggbb` (or `#rgb`) as numbers; grey for anything else. */
export function hexRgb(css: string): Rgb {
  let h = css.trim().replace(/^#/, "");
  if (h.length === 3) h = [...h].map((c) => c + c).join("");
  if (!/^[0-9a-f]{6}/i.test(h)) return [128, 128, 128];
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as unknown as Rgb;
}

/** The first index whose value is at least `v`, in ascending `a`. */
export function lowerBound(a: ArrayLike<number>, v: number): number {
  let lo = 0, hi = a.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    if (a[m] < v) lo = m + 1;
    else hi = m;
  }
  return lo;
}

/** The index of the cell whose 2θ is nearest `v`, in ascending `a`. */
export function nearest(a: ArrayLike<number>, v: number): number {
  const j = lowerBound(a, v);
  if (j >= a.length) return a.length - 1;
  return j > 0 && v - a[j - 1] <= a[j] - v ? j - 1 : j;
}

/** The cells under each of `width` pixel columns across [t0, t1], as
 *  half-open index ranges into the grid, the last column closed at `t1`; a
 *  column narrower than a cell takes the cell nearest its middle. */
export function columnRanges(tt: ArrayLike<number>, t0: number, t1: number,
                             width: number): Int32Array {
  const w = Math.max(0, Math.floor(width)), out = new Int32Array(2 * w);
  if (!w || !tt.length) return out;
  for (let c = 0; c < w; c++) {
    const x0 = t0 + (c / w) * (t1 - t0), x1 = t0 + ((c + 1) / w) * (t1 - t0);
    const a = lowerBound(tt, x0);
    // the last column keeps a cell sitting exactly on the view's right end
    let b = lowerBound(tt, x1);
    if (c === w - 1) while (b < tt.length && tt[b] <= x1) b += 1;
    if (b > a) {
      out[2 * c] = a;
      out[2 * c + 1] = b;
    } else {
      const j = nearest(tt, (x0 + x1) / 2);
      out[2 * c] = j;
      out[2 * c + 1] = j + 1;
    }
  }
  return out;
}

/** One row's value in each pixel column: the highest count under it, or the
 *  mean difference. NaN where every cell under it is. */
export function rowColumns(cells: ArrayLike<number>, offset: number, ranges: Int32Array,
                           diff: boolean): Float64Array {
  const w = ranges.length / 2, out = new Float64Array(w);
  for (let c = 0; c < w; c++) {
    let best = NaN, sum = 0, n = 0;
    for (let j = ranges[2 * c]; j < ranges[2 * c + 1]; j++) {
      const v = cells[offset + j];
      if (Number.isNaN(v)) continue;
      if (diff) {
        sum += v;
        n += 1;
      } else if (!(v <= best)) best = v;
    }
    out[c] = diff ? (n ? sum / n : NaN) : best;
  }
  return out;
}

/** The mean of one row's cells across [cut − width/2, cut + width/2], at
 *  least the one cell nearest the cut. NaN where every cell is. */
export function cutValue(cells: ArrayLike<number>, offset: number, tt: ArrayLike<number>,
                         cut: number, width: number): number {
  if (!tt.length) return NaN;
  let j0 = lowerBound(tt, cut - width / 2), j1 = lowerBound(tt, cut + width / 2);
  if (j1 <= j0) {
    j0 = nearest(tt, cut);
    j1 = j0 + 1;
  }
  let sum = 0, n = 0;
  for (let j = j0; j < j1; j++) {
    const v = cells[offset + j];
    if (Number.isNaN(v)) continue;
    sum += v;
    n += 1;
  }
  return n ? sum / n : NaN;
}

/** The rows shown, top first: every pattern, or the window a vertical drag
 *  chose (from one series index to another), and bottom first when flipped. */
export function shownRows(n: number, window: readonly [number, number] | null,
                          flip: boolean): number[] {
  let rows = Array.from({ length: n }, (_, i) => i);
  if (window) {
    const a = Math.max(0, Math.min(...window)), b = Math.min(n - 1, Math.max(...window));
    if (b >= a) rows = rows.slice(a, b + 1);
  }
  return flip ? rows.reverse() : rows;
}

/** The rows the profile under the map averages: every row between a
 *  shift-click's two, or the selected pattern alone. */
export function bandRows(band: readonly [number, number] | null, selected: number): number[] {
  if (!band) return [selected];
  const a = Math.min(...band), b = Math.max(...band);
  return Array.from({ length: b - a + 1 }, (_, k) => a + k);
}

/** Which part of the averaging bar [a, b] (in px) a press at `x` takes: an
 *  edge within `grip` px, the bar itself to move it, or a new bar. */
export function barPart(x: number, a: number, b: number,
                        grip = 5): "left" | "right" | "move" | "new" {
  if (Math.abs(x - a) <= grip) return "left";
  if (Math.abs(x - b) <= grip) return "right";
  return x > a && x < b ? "move" : "new";
}

/** A typed or dragged width as the field shows it: three figures, never
 *  under one grid `step`. */
export function roundWidth(v: number, step: number): number {
  return Number(Math.max(step, v).toPrecision(3));
}

/** The 2θ labels' step for a span drawn across `px` pixels, at most one
 *  label per 70 px (the prototype's). */
export function labelStep(span: number, px: number): number {
  const steps = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 20];
  return steps.find((s) => span / s <= px / 70) ?? 20;
}

/** A count for an axis label: whole below 10 000, else in thousands. */
export function countLabel(v: number): string {
  if (!Number.isFinite(v)) return "";
  if (Math.abs(v) < 1e4) return String(Math.round(v));
  return `${Number((v / 1e3).toPrecision(2))}k`;
}
