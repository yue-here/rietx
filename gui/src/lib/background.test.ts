import { describe, expect, it } from "vitest";

import {
  BAND_LEVEL,
  backgroundTitle,
  bandSize,
  bandTitle,
  coefficientTerms,
  columnExtremes,
  frame,
  halfWidth,
  holdDelta,
  holdEcho,
  holdable,
  holdsApply,
  niceTicks,
  parseLambda,
  termIndex,
  withLambda,
  type BackgroundHeader,
  type Term,
} from "./background";

const term = (path: string, over: Partial<Term> = {}): Term => ({
  path, value: 1, esd: null, vary: true, held: false, refinable: true,
  held_because: null, ...over,
});

const header = (over: Partial<BackgroundHeader> = {}): BackgroundHeader => ({
  head: "n1", kind: "chebyshev", terms: [], n_free: 9, n_background_free: 6,
  n_other_free: 3, chi2_red: 1.2, esd_inflation: 1.0, band_absent: null, ...over,
});

describe("which terms a hold reaches", () => {
  it("offers holds on the two Chebyshev kinds only", () => {
    expect(holdsApply("chebyshev")).toBe(true);
    expect(holdsApply("fixed_plus_chebyshev")).toBe(true);
    expect(holdsApply("pspline")).toBe(false);
  });

  it("lists the coefficients in order and leaves a multiplier out", () => {
    const got = coefficientTerms([
      term("instrument.background.c10"), term("instrument.background.scale"),
      term("instrument.background.c2"), term("instrument.background.c0"),
    ]).map((t) => termIndex(t.path));
    expect(got).toEqual([0, 2, 10]);
  });

  it("can press a held or refinable term and never a locked one", () => {
    expect(holdable(term("x.c0"))).toBe(true);
    expect(holdable(term("x.c0", { refinable: false, held: true }))).toBe(true);
    expect(holdable(term("x.c0", { refinable: false, held_because: "tied" }))).toBe(false);
  });

  it("sends the hold verb's body and echoes the python it stands for", () => {
    expect(holdDelta("instrument.background.c3", true))
      .toEqual({ hold: { "instrument.background.c3": true } });
    expect(holdEcho("instrument.background.c3", true))
      .toBe('ref.hold("instrument.background.c3")');
    expect(holdEcho("instrument.background.c3", false))
      .toBe('ref.unhold("instrument.background.c3")');
  });
});

describe("drawing", () => {
  it("frames the curve so it fills the view and the peaks run off the top", () => {
    const [lo, hi] = frame([100, 200, 150]);
    expect(lo).toBeCloseTo(70);
    expect(hi).toBeCloseTo(230);
    expect(frame([])).toEqual([0, 1]);
    expect(frame([0, 0])).toEqual([-1, 1]);
  });

  it("paints each pixel column's extremes, and NaN where no point falls", () => {
    const { lo, hi } = columnExtremes([0, 0.1, 0.2, 0.9], [5, 1, 3, 7], 0, 1, 4);
    expect(Array.from(lo.slice(0, 1))).toEqual([1]);
    expect(Array.from(hi.slice(0, 1))).toEqual([5]);
    expect(Number.isNaN(lo[1])).toBe(true);
    expect(hi[3]).toBe(7);
  });

  it("puts the point at the right edge in the last column", () => {
    const { lo } = columnExtremes([0, 1], [2, 9], 0, 1, 4);
    expect(lo[3]).toBe(9);
  });

  it("draws the band at the level times the multiplier", () => {
    expect(Array.from(halfWidth([1, 2], 5))).toEqual([BAND_LEVEL * 5, BAND_LEVEL * 10]);
  });

  it("picks round ticks within the range", () => {
    expect(niceTicks(0, 10, 5)).toEqual([0, 2, 4, 6, 8, 10]);
    expect(niceTicks(52, 575, 6)).toEqual([100, 200, 300, 400, 500]);
    expect(niceTicks(1, 1, 3)).toEqual([]);
  });
});

describe("what the band says about itself", () => {
  it("states the level, the size and the free set, and that ×N only exaggerates", () => {
    expect(bandSize([1, 2, 3])).toEqual({ typical: 6, largest: 9 });
    const text = bandTitle(header({ n_other_free: 1 }), [1, 2, 3]);
    expect(text).toContain("±3 esd");
    expect(text).toContain("6 background and 1 other parameter free");
    expect(text).toContain("exaggerates the drawing only");
  });

  it("says why there is no band rather than drawing a zero one", () => {
    expect(bandTitle(header({ band_absent: "no free background term" }), null))
      .toMatch(/no background term is free/);
    expect(bandTitle(header({ band_absent: "unmeasured" }), null))
      .toMatch(/data do not constrain/);
  });

  it("titles the graph by what state it shows", () => {
    expect(backgroundTitle(false)).toBe("Background at the current values");
    expect(backgroundTitle(true)).toBe("Background, refining");
  });
});

describe("the smoothness field", () => {
  it("takes a number at or above zero and refuses the rest with a reason", () => {
    expect(parseLambda(" 1e4 ")).toBe(1e4);
    expect(parseLambda("0")).toBe(0);
    expect(parseLambda("")).toBe("λ is a number");
    expect(parseLambda("abc")).toBe("λ is a number");
    expect(parseLambda("-1")).toBe("λ is zero or more");
  });

  it("edits a copy, never the model the panel holds", () => {
    const instrument = { background: { kind: "pspline", lambda_smooth: 1 } };
    const next = withLambda(instrument, 100);
    expect(next.background.lambda_smooth).toBe(100);
    expect(instrument.background.lambda_smooth).toBe(1);
  });
});
