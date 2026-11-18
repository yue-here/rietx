import { describe, expect, it } from "vitest";

import { DEFAULT_TERMS, LAMBDA_STOPS, knots, lambdaStop, pendingBackgroundHolds,
         switchKind, withTerms } from "./background";

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

  it("fetches the band with the background's pending holds alone", () => {
    const holds = new Map([
      ["instrument.background.c3", true],
      ["instrument.background.c1", true],
      ["instrument.background.c2", false],
      ["phases.0.cell.a", true],
      ["phases.0.atoms.1.dof.*", true],
    ]);
    expect(pendingBackgroundHolds(holds)).toEqual(
      ["instrument.background.c1", "instrument.background.c3"]);
  });
});
