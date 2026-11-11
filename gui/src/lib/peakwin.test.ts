import { describe, expect, it } from "vitest";

import { BINS, firstPicks, HALF_WIDTHS, peakWindows, widestFwhm, windowRange } from "./peakwin";

/** A fitted payload: Gaussians of FWHM `w` at `centres` with `heights`, on 10 counts of background. */
function curves(centres: number[], heights: number[], w = 0.1, fit = true): any {
  const n = 4001, tt = new Float64Array(n), calc = new Float64Array(n), bkg = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    tt[i] = 10 + i * 0.01;
    bkg[i] = 10;
    calc[i] = 10 + centres.reduce((s, c, k) =>
      s + heights[k] * Math.exp(-4 * Math.LN2 * ((tt[i] - c) / w) ** 2), 0);
  }
  const fitted = Int32Array.from({ length: n }, (_, i) => i);
  return { header: { fit, ticks: { apatite: centres }, tick_hkl: { apatite: centres.map((_, k) => [k, 0, 1]) } },
           arrays: { two_theta: tt, y_obs: calc, fitted, y_calc: calc, y_background: bkg } };
}

describe("the single-peak windows (WP-2128)", () => {
  it("frames the strongest reflection of each bin, measured on the last fit", () => {
    // 10-50°, so a bin is 40/12 ≈ 3.3° wide; 12° and 12.5° share the first one
    const w = peakWindows(curves([12, 12.5, 30, 45], [100, 400, 50, 80]));
    expect(w.map((x) => x.center)).toEqual([12.5, 30, 45]);
    expect(w[0].hkl).toEqual([1, 0, 1]);
    expect(w[0].phase).toBe("apatite");
    // the half-maximum walk lands within a channel of the true FWHM
    expect(w[0].fwhm).toBeGreaterThan(0.08);
    expect(w[0].fwhm).toBeLessThan(0.13);
    expect(w[0].hi - w[0].lo).toBeCloseTo(2 * HALF_WIDTHS * w[0].fwhm, 12);
    expect(widestFwhm(w)).toBe(Math.max(...w.map((x) => x.fwhm)));
  });

  it("frames nothing before a fit", () => {
    expect(peakWindows(curves([12], [100], 0.1, false))).toEqual([]);
    expect(widestFwhm([])).toBe(0);
  });

  it("opens on a low, a middle and a high window", () => {
    expect(firstPicks(BINS)).toEqual([1, 6, 10]);
    expect(firstPicks(2)).toEqual([0, 1]);
    // four windows: three distinct ones, never the third named twice
    expect(firstPicks(4)).toEqual([0, 2, 3]);
  });

  it("draws a window from zero to a tenth above the last fit, whatever a preview does", () => {
    const xs = [1, 2, 3, 4], obs = [10, 50, 100, 20], fit = [12, 48, 90, null];
    const [lo, hi] = windowRange(xs, obs, fit, 1.5, 3.5);
    expect(lo).toBe(0);
    expect(hi).toBeCloseTo(110, 12);
  });
});
