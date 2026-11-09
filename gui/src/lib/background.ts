/** The Background graph's logic (WP-2129), as pure functions.
 *
 * `GET /api/background` sends the observed pattern, the background curve at
 * the working state's values and `band_esd`, the curve's esd at each fitted
 * channel through the whole covariance of the free parameters (the server's
 * `gui/background.py` has the derivation). Everything here is drawing: the
 * band's level and multiplier, the y frame, the per-pixel extremes of the
 * data, and which terms a hold can reach.
 *
 * The maintainer's rulings this follows (restated in WP-2129): the background
 * is one group with a preview of "greyed data, the curve, and a shaded band for
 * how it might move with the active parameters refining" (2026-11-06); the
 * band "may be exaggerated" (2026-11-07); a held Chebyshev term keeps its value
 * from the previous cycle, which is `Refinement.hold` (2026-11-07).
 */

/** The band is drawn at this many esds, before any exaggeration. The
 *  prototype's level, and the pattern residual's own ±3 band. */
export const BAND_LEVEL = 3;

/** The multipliers the person can draw the band at. An exaggeration is not a
 *  probability (`gui/CLAUDE.md`, WP-1029), so the level and the multiplier are
 *  stated apart wherever the band is described. */
export const BAND_MULTIPLIERS = [1, 5, 20] as const;
export type Multiplier = (typeof BAND_MULTIPLIERS)[number];

export interface Term {
  path: string;
  value: number;
  esd: number | null;
  vary: boolean;
  held: boolean;
  refinable: boolean;
  held_because: string | null;
}

export interface BackgroundHeader {
  head: string | null;
  kind: string;
  lambda_smooth?: number;
  lambda_units?: string;
  terms: Term[];
  n_free: number;
  n_background_free: number;
  n_other_free: number;
  chi2_red: number | null;
  esd_inflation: number | null;
  band_absent: string | null;
}

/** Whether the per-term holds apply: the two Chebyshev kinds. A P-spline's
 *  coefficients are local, and the ruling names Chebyshev terms alone. */
export function holdsApply(kind: string): boolean {
  return kind === "chebyshev" || kind === "fixed_plus_chebyshev";
}

/** The coefficient terms a hold is offered on: `c0`, `c1`, … in order. A
 *  fixed-plus-Chebyshev's `scale` is a multiplier on the curve, not a term. */
export function coefficientTerms(terms: readonly Term[]): Term[] {
  return terms.filter((t) => /\.c\d+$/.test(t.path))
    .sort((a, b) => termIndex(a.path) - termIndex(b.path));
}

export function termIndex(path: string): number {
  const m = /\.c(\d+)$/.exec(path);
  return m ? Number(m[1]) : -1;
}

/** A hold can be pressed on a term the hold verb accepts: one already held,
 *  or one the table could free. A locked or tied term says why instead. */
export function holdable(term: Term): boolean {
  return term.held || term.refinable;
}

/** The `PATCH /api/params` body a hold box sends. */
export function holdDelta(path: string, held: boolean): { hold: Record<string, boolean> } {
  return { hold: { [path]: held } };
}

/** The console line for the same press, in the python it stands for. */
export function holdEcho(path: string, held: boolean): string {
  return `ref.${held ? "hold" : "unhold"}(${JSON.stringify(path)})`;
}

/** The y range: framed on the background curve, so the peaks run off the top
 *  and the curve fills the view (the prototype's framing, 0.7× its lowest
 *  point to 1.15× its highest). A flat or zero curve gets a unit-wide frame. */
export function frame(y: ArrayLike<number>): [number, number] {
  let lo = Infinity, hi = -Infinity;
  for (let i = 0; i < y.length; i++) {
    if (!Number.isFinite(y[i])) continue;
    if (y[i] < lo) lo = y[i];
    if (y[i] > hi) hi = y[i];
  }
  if (!Number.isFinite(lo)) return [0, 1];
  const a = lo - 0.3 * Math.abs(lo), b = hi + 0.15 * Math.abs(hi);
  return b - a > 1e-12 ? [a, b] : [a - 1, b + 1];
}

/** Per pixel column, the lowest and highest observed point in it, so dense
 *  data draws as one vertical stroke a column, as the pattern chart paints
 *  each column's extremes (WP-1461, D5). Columns with no point are NaN. */
export function columnExtremes(x: ArrayLike<number>, y: ArrayLike<number>,
                               x0: number, x1: number, width: number
                               ): { lo: Float64Array; hi: Float64Array } {
  const n = Math.max(0, Math.floor(width));
  const lo = new Float64Array(n).fill(NaN), hi = new Float64Array(n).fill(NaN);
  if (!n || !(x1 > x0)) return { lo, hi };
  for (let i = 0; i < x.length; i++) {
    // x1 itself is the last column's right edge, not a column past it
    const c = x[i] === x1 ? n - 1 : Math.floor(((x[i] - x0) / (x1 - x0)) * n);
    if (c < 0 || c >= n || !Number.isFinite(y[i])) continue;
    if (!(y[i] >= lo[c])) lo[c] = y[i];
    if (!(y[i] <= hi[c])) hi[c] = y[i];
  }
  return { lo, hi };
}

/** The band's half-width at each channel, in counts: level × multiplier × esd. */
export function halfWidth(esd: ArrayLike<number>, multiplier: number): Float64Array {
  const out = new Float64Array(esd.length);
  for (let i = 0; i < esd.length; i++) out[i] = BAND_LEVEL * multiplier * esd[i];
  return out;
}

/** The band's size as the tooltip states it: the typical (median) and largest
 *  half-width at the level, undrawn by any multiplier. */
export function bandSize(esd: ArrayLike<number>): { typical: number; largest: number } {
  const sorted = Array.from(esd).filter(Number.isFinite).sort((a, b) => a - b);
  if (!sorted.length) return { typical: 0, largest: 0 };
  return { typical: BAND_LEVEL * sorted[sorted.length >> 1],
           largest: BAND_LEVEL * sorted[sorted.length - 1] };
}

/** The tooltip on the band's control: what the band is, at what level, and how
 *  big, so no line under the plot has to say it (sixth review, 2026-11-07). */
export function bandTitle(header: BackgroundHeader, esd: ArrayLike<number> | null): string {
  if (!esd) return header.band_absent === "unmeasured"
    ? "No band: a free parameter the background depends on is one the data do not constrain"
    : "No band: no background term is free, so the curve cannot move";
  const { typical, largest } = bandSize(esd);
  const others = header.n_other_free;
  return `Where the curve may move when the free parameters refine: ±${BAND_LEVEL} esd, `
    + `±${typical.toPrecision(2)} counts typically and ±${largest.toPrecision(2)} at most, `
    + `with ${header.n_background_free} background and ${others} other parameter`
    + `${others === 1 ? "" : "s"} free. Linearised at the current values. `
    + "A multiplier above ×1 exaggerates the drawing only.";
}

/** The graph's title (WP-2123 design 2: every graph says what it shows). The
 *  curve is at the working values, the ones the next run starts from: whether a
 *  result is held does not date them, since an edit or a checkout moves them
 *  without a fit. */
export function backgroundTitle(busy: boolean): string {
  return busy ? "Background, refining" : "Background at the current values";
}

/** λ as typed: a finite number ≥ 0, or the reason it is refused. */
export function parseLambda(text: string): number | string {
  const v = Number(text.trim());
  if (!text.trim() || !Number.isFinite(v)) return "λ is a number";
  if (v < 0) return "λ is zero or more";
  return v;
}

/** The instrument with its P-spline's λ replaced, for `PATCH /api/instrument`.
 *  A copy: the panel's own model is not edited before the server agrees. */
export function withLambda(instrument: any, lambda: number): any {
  const next = JSON.parse(JSON.stringify(instrument));
  next.background.lambda_smooth = lambda;
  return next;
}

/** Round tick values over [lo, hi], at most about `count` of them: a step of
 *  1, 2 or 5 times a power of ten, as a plotting library picks one. */
export function niceTicks(lo: number, hi: number, count: number): number[] {
  if (!(hi > lo) || count < 1) return [];
  const raw = (hi - lo) / count;
  const mag = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag;
  const out: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    out.push(Math.abs(v) < step * 1e-9 ? 0 : Number(v.toPrecision(12)));
  }
  return out;
}
