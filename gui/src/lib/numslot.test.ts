import { describe, expect, it } from "vitest";
import { editText, expWidth, numParts, slotWidth, slotsFor, wantsSci } from "./numslot";

describe("number slots (WP-2126)", () => {
  it("writes scientific below 0.01 and from 10 000 up, plain between", () => {
    expect(wantsSci(0.0099)).toBe(true);
    expect(wantsSci(0.01)).toBe(false);
    expect(wantsSci(9999)).toBe(false);
    expect(wantsSci(10_000)).toBe(true);
    expect(wantsSci(0)).toBe(false);
  });

  it("splits a value at its point and keeps the esd in the last place", () => {
    expect(numParts(10.25143, 0.00002)).toEqual({ int: "10", frac: "25143", tail: "(2)", exp: null });
    expect(numParts(-0.5, null)).toEqual({ int: "−0", frac: "5", tail: "", exp: null });
    // an esd in the exponent's frame: 1.52(3)×10⁻³
    expect(numParts(0.00152, 0.00003)).toEqual({ int: "1", frac: "52", tail: "(3)", exp: -3 });
    expect(numParts(25000, 300)).toEqual({ int: "2", frac: "50", tail: "(3)", exp: 4 });
  });

  it("writes a swallowing esd in the exponent's frame, since the ×10ⁿ follows it", () => {
    // 0.005 ± 2 is 5 ± 2000 ×10⁻³, never 5 ± 2 ×10⁻³
    expect(numParts(0.005, 2)).toMatchObject({ int: "5", tail: " ±2000", exp: -3 });
    expect(numParts(20000, 30000)).toMatchObject({ int: "2", tail: " ±3", exp: 4 });
  });

  it("renormalises a mantissa that rounds up to ten", () => {
    expect(numParts(0.0099996, 0.0001)).toMatchObject({ int: "1", frac: "00", exp: -2 });
  });

  it("writes plain when asked, as the atom table always is", () => {
    expect(numParts(0.001913, null, false)).toEqual({ int: "0", frac: "001913", tail: "", exp: null });
  });

  it("reserves an exponent slot near a switch point, so crossing it moves nothing", () => {
    const plainNear = slotsFor([{ value: 0.05, esd: null }]);
    const crossed = slotsFor([{ value: 0.005, esd: null }]);
    expect(plainNear.exp).toBe(expWidth(-3));
    expect(crossed.exp).toBe(expWidth(-3));
    // far from both thresholds there is no slot to reserve
    expect(slotsFor([{ value: 9.37, esd: 0.001 }]).exp).toBe(0);
  });

  it("aligns a column on the point: the widest integer and the widest fraction", () => {
    const slots = slotsFor([{ value: 9.371724, esd: 0.00002 }, { value: 120.5, esd: null }]);
    expect(slots).toEqual({ int: 3, frac: 8, exp: 0 });   // "37172(2)" is the widest fraction
    expect(slotWidth(slots)).toBe(12);
  });

  it("opens the editor on the number as drawn, so a click in and out changes nothing", () => {
    expect(editText(4.15678, 0.0002)).toBe("4.1568");
    expect(editText(0.00152, 0.00003)).toBe("1.52e-3");
    expect(Number(editText(0.00152, 0.00003))).toBeCloseTo(0.00152, 12);
  });
});
