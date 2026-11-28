import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { DEFAULT_TERMS, LAMBDA_STOPS, heldWith, kindEcho, knots, lambdaStop,
         pendingHolds, switchKind, termsEcho, withTerms } from "./background";

/** `BackgroundPSpline.for_range`'s answers, written by `tests/test_gui_background.py`. */
const corpus: { cases: Array<{ lo: number; hi: number; breakpoints: number[]; n_coefficients: number;
                               lambda_smooth: number; lambda_units: string }> } = JSON.parse(
  readFileSync(fileURLToPath(new URL("../../../tests/data/gui/background_cases.json", import.meta.url)),
               "utf-8"));

const cheb = (n: number) => ({
  geometry: { kind: "bragg_brentano" },
  background: { kind: "chebyshev",
                coefficients: Array.from({ length: n }, (_, k) => ({ value: k + 1, vary: true })) },
});

describe("the rebuilt Background graph's controls (WP-2218)", () => {
  it("cuts or extends the Chebyshev, keeping the terms it has", () => {
    const ins = cheb(4);
    const more = withTerms(ins, 6);
    expect(more.background.coefficients.map((c: any) => c.value)).toEqual([1, 2, 3, 4, 0, 0]);
    expect(more.background.coefficients[5].vary).toBe(true);
    expect(withTerms(ins, 2).background.coefficients.map((c: any) => c.value)).toEqual([1, 2]);
    // a copy: the instrument handed in is not edited
    expect(ins.background.coefficients).toHaveLength(4);
  });

  it("places the P-spline's knots as for_range does", () => {
    // BackgroundPSpline.for_range(15, 130): round(115 / 5) + 1 = 24 knots
    const k = knots(15, 130);
    expect(k).toHaveLength(24);
    expect(k[0]).toBe(15);
    expect(k[23]).toBeCloseTo(130, 12);
    expect(knots(10, 11)).toEqual([10, 11]);
    // a half rounds to even, as Python's round does: round(2.5) = 2
    expect(knots(10, 22.5)).toHaveLength(3);
    expect(knots(10, 27.5)).toHaveLength(5);
  });

  it("switches type to a fresh background of the other kind", () => {
    const spline = switchKind(cheb(6), "pspline", 15, 130);
    expect(spline.background.kind).toBe("pspline");
    expect(spline.background.coefficients).toHaveLength(spline.background.breakpoints.length + 2);
    expect(spline.background.lambda_smooth).toBe(1);
    expect(spline.geometry.kind).toBe("bragg_brentano");
    const back = switchKind(spline, "chebyshev", 15, 130);
    expect(back.background).toEqual({
      kind: "chebyshev",
      coefficients: Array.from({ length: DEFAULT_TERMS }, () => ({ value: 0, vary: true })) });
  });

  it("puts any λ on the nearest stop", () => {
    expect(LAMBDA_STOPS[lambdaStop(1)]).toBe(1);
    expect(LAMBDA_STOPS[lambdaStop(30)]).toBe(1e2);
    expect(LAMBDA_STOPS[lambdaStop(5e6)]).toBe(1e6);
    expect(lambdaStop(0)).toBe(0);
  });

  it("fetches the band with every pending hold, globs and other parameters' too", () => {
    const holds = new Map([
      ["instrument.background.c3", true],
      ["instrument.background.c1", true],
      ["instrument.background.c2", false],
      ["phases.0.cell.a", true],
      ["phases.0.atoms.1.dof.*", true],
    ]);
    expect(pendingHolds(holds)).toEqual(["instrument.background.c1", "instrument.background.c3",
                                         "phases.0.atoms.1.dof.*", "phases.0.cell.a"]);
  });

  it("reads a chip held through a pending glob, its own entry first", () => {
    const holds = new Map([["instrument.background.*", true], ["instrument.background.c2", false]]);
    expect(heldWith("instrument.background.c4", false, holds)).toBe(true);
    expect(heldWith("instrument.background.c2", true, holds)).toBe(false);
    expect(heldWith("instrument.background.c4", true, new Map())).toBe(true);
  });

  it("builds the P-spline for_range builds, case for case", () => {
    expect(corpus.cases.length).toBeGreaterThan(5);
    for (const c of corpus.cases) {
      expect(knots(c.lo, c.hi)).toEqual(c.breakpoints);
      const bg = switchKind(cheb(6), "pspline", c.lo, c.hi).background;
      expect(bg.breakpoints).toEqual(c.breakpoints);
      expect(bg.coefficients).toHaveLength(c.n_coefficients);
      expect([bg.lambda_smooth, bg.lambda_units]).toEqual([c.lambda_smooth, c.lambda_units]);
    }
  });

  it("echoes the Python each edit runs, the kept values and the bounds sent", () => {
    expect(termsEcho(6, 4)).toBe("instrument.background.coefficients = instrument.background.coefficients[:4]");
    expect(termsEcho(6, 8)).toBe(
      "instrument.background.coefficients += [Parameter(value=0.0, vary=True) for _ in range(2)]");
    expect(kindEcho("pspline", 5.0012345678, 130)).toBe(
      "instrument.background = BackgroundPSpline.for_range(5.0012345678, 130.0)");
    expect(kindEcho("chebyshev", 5, 130)).toBe(`instrument.background = BackgroundChebyshev.with_terms(${DEFAULT_TERMS})`);
  });
});
