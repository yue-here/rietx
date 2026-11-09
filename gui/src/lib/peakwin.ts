/**
 * The single-peak windows (WP-2128): which reflections they frame, how wide,
 * and the y range each is drawn on.
 *
 * The design is the maintainer's (ruled 2026-11-07, third review: the
 * single-peak comparison plots are liked): each window shows the strongest
 * reflection in its part of the pattern, ‹ and › step to the next one, and the
 * scale stays at the last fit, so a preview that grows a peak runs off the top
 * rather than rescaling the comparison (fourth review).
 *
 * Everything here reads the last fit's curves payload, never the preview's:
 * that is what keeps the comparison still while a slider moves.
 */

import type { Curves } from "rxplot";

/** How many equal 2θ bins the pattern is cut into, one window candidate each. */
export const BINS = 12;
/** How many windows show at once. */
export const SHOWN = 3;
/** A window spans the peak's FWHM this many times on each side. */
export const HALF_WIDTHS = 5;

export interface PeakWindow {
  /** the reflection's 2θ, from the last fit's ticks */
  center: number;
  lo: number;
  hi: number;
  /** the peak's FWHM measured on the last fit's curve, in degrees */
  fwhm: number;
  phase: string;
  hkl: number[] | null;
  /** the last fit's height over its background at the centre: the ranking */
  height: number;
}

/** The nearest index of `xs` (ascending) to `x`, or −1 for an empty array. */
function nearest(xs: ArrayLike<number>, x: number): number {
  let lo = 0, hi = xs.length - 1;
  if (hi < 0) return -1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < x) lo = mid; else hi = mid;
  }
  return Math.abs(xs[lo] - x) <= Math.abs(xs[hi] - x) ? lo : hi;
}

/** The fitted channels' 2θ and the model over its background there. */
function netModel(c: Curves): { tt: Float64Array; net: Float64Array } | null {
  const { arrays, header } = c;
  if (!header.fit || !arrays.fitted || !arrays.y_calc) return null;
  const at = arrays.fitted, calc = arrays.y_calc, bkg = arrays.y_background;
  const tt = new Float64Array(at.length), net = new Float64Array(at.length);
  for (let q = 0; q < at.length; q++) {
    tt[q] = arrays.two_theta[at[q]];
    net[q] = calc[q] - (bkg ? bkg[q] : 0);
  }
  return { tt, net };
}

/** The full width at half the net height around channel `k`, by walking out to half. */
function widthAt(tt: Float64Array, net: Float64Array, k: number): number {
  const half = net[k] / 2;
  let a = k, b = k;
  while (a > 0 && net[a] > half) a--;
  while (b < net.length - 1 && net[b] > half) b++;
  const w = tt[b] - tt[a];
  return w > 0 ? w : Math.max(tt[Math.min(k + 1, tt.length - 1)] - tt[Math.max(k - 1, 0)], 0.01);
}

/**
 * The window candidates: the strongest reflection in each of `BINS` equal bins
 * of the fitted range, ranked by the last fit's net height at its position.
 * Every emission line's ticks are read, so a window may centre on a Kα2 line
 * only where that line is the strongest thing in its bin. Empty before a fit.
 */
export function peakWindows(c: Curves, bins = BINS): PeakWindow[] {
  const model = netModel(c);
  if (!model || model.tt.length < 3) return [];
  const { tt, net } = model, t0 = tt[0], t1 = tt[tt.length - 1];
  const best: (PeakWindow | null)[] = new Array(bins).fill(null);
  const ticks: Record<string, number[]> = c.header.ticks ?? {};
  const hkls: Record<string, number[][]> = c.header.tick_hkl ?? {};
  for (const [phase, row] of Object.entries(ticks)) {
    row.forEach((center, i) => {
      if (!(center >= t0 && center <= t1)) return;
      const b = Math.min(bins - 1, Math.floor(((center - t0) / (t1 - t0)) * bins));
      const k = nearest(tt, center), height = net[k];
      if (!(height > 0) || (best[b] && best[b]!.height >= height)) return;
      const fwhm = widthAt(tt, net, k);
      best[b] = { center, fwhm, phase, height, hkl: hkls[phase]?.[i] ?? null,
                  lo: center - HALF_WIDTHS * fwhm, hi: center + HALF_WIDTHS * fwhm };
    });
  }
  return best.filter((w): w is PeakWindow => !!w);
}

/** The windows shown first: one low, one in the middle and one high, as the prototype did. */
export function firstPicks(n: number): number[] {
  if (n <= SHOWN) return Array.from({ length: n }, (_, i) => i);
  // at four, the prototype's [1, n/2, n − 2] names the third window twice
  if (n === SHOWN + 1) return [0, Math.floor(n / 2), n - 1];
  return [1, Math.floor(n / 2), n - 2];
}

/** The widest window peak, which the sliders' default ranges are measured in. */
export function widestFwhm(windows: readonly PeakWindow[]): number {
  return Math.max(0, ...windows.map((w) => w.fwhm));
}

/**
 * The y range a window is drawn on: the data and the last fit inside it, with a
 * tenth of headroom, and never the preview (ruled 2026-11-07).
 */
export function windowRange(xs: ArrayLike<number>, obs: ArrayLike<number>,
                            fit: ArrayLike<number | null>, lo: number, hi: number): [number, number] {
  let top = 0, bottom = Infinity;
  for (let i = 0; i < xs.length; i++) {
    if (xs[i] < lo || xs[i] > hi) continue;
    top = Math.max(top, obs[i], fit[i] ?? -Infinity);
    bottom = Math.min(bottom, obs[i], fit[i] ?? Infinity);
  }
  if (!Number.isFinite(bottom)) return [0, 1];
  const base = Math.min(0, bottom);
  return [base, top + (top - base) * 0.1 || 1];
}
