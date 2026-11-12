// The status bar's hover readout as ruled on 2026-11-11 ("try b", WP-2216):
// the legend's words, three decimals for 2θ, d and an offset, whole counts,
// the weighted difference to one decimal in σ, a typographic minus, and a
// narrow window dropping the reflections first and Background next.
import { describe, expect, it } from "vitest";

import type { Window } from "../lib/plot";
import { dropsFor, signed, statusReadout } from "./readout";
import { CURVE_WORDS, shortTitle, unitText } from "./words";

const W: Window = {
  two_theta: [31.85, 31.86, 31.87],
  y_obs: [18000.4, 19693.2, 18500],
  y_calc: [18100, 20306.9, 18400],
  y_background: [175.2, 174.975, 174.8],
  delta: [-0.8, -4.3765, 0.7],
  delta_raw: [-99.6, -613.7, 100],
  cumulative_chi2: [0.64, 19.8, 20.3],
  weighted: true,
  ticks: { fluorapatite: [31.84, 31.872] },
  tick_hkl: { fluorapatite: [[2, 1, 1], [3, -1, 1]] },
};
const LAM = 1.5406;

const read = (x: number, extra: Partial<Parameters<typeof statusReadout>[2]> = {}) =>
  statusReadout(W, x, { kind: "weighted", wavelengths: [LAM], ...extra })!;
const text = (r: ReturnType<typeof read>) => r.items.map((i) => `${i.label} ${i.value}`).join("   ");

describe("the status bar's hover readout", () => {
  it("reads as the maintainer's mock-up", () => {
    const d = LAM / (2 * Math.sin((31.86 * Math.PI) / 360));
    expect(text(read(31.861))).toBe(
      `2θ 31.860°   d ${d.toFixed(3)} Å   Observed 19693   Last fit 20307   Background 175   `
      + "Difference −4.4σ   fluorapatite (3 −1 1) +0.012°");
  });

  it("labels each curve with the legend's own word", () => {
    const labels = read(31.86).items.map((i) => i.label);
    for (const id of ["obs", "calc", "bkg", "diff"]) expect(labels).toContain(CURVE_WORDS[id]);
  });

  it("names only the curves drawn", () => {
    const ids = read(31.86, { hidden: ["bkg", "ticks:fluorapatite"] }).items.map((i) => i.id);
    expect(ids).toEqual(["pos", "d", "obs", "calc", "diff"]);
  });

  it("reads the difference the plot draws: counts whole, cumulative χ² from the view's edge", () => {
    const diff = (kind: "delta" | "cumulative") =>
      read(31.86, { kind, chi2Base: 0.5 }).items.find((i) => i.id === "diff")!.value;
    expect(diff("delta")).toBe("−614");
    expect(diff("cumulative")).toBe("19.3");
  });

  it("signs an offset always, and never prints −0", () => {
    expect(signed(-0.0004, 3, true)).toBe("+0.000");
    expect(signed(-0.0123, 3, true)).toBe("−0.012");
    expect(signed(-0.4, 0)).toBe("0");
  });

  it("is null off the plot, so the findings count comes back", () => {
    expect(statusReadout(W, null, { kind: "weighted" })).toBeNull();
  });

  it("sizes each curve's slot from its own payload, so a sweep moves no label", () => {
    const slots = Object.fromEntries(read(31.85).items.map((i) => [i.id, i.slot]));
    expect([slots.obs, slots.calc, slots.bkg, slots.diff]).toEqual([5, 5, 3, 5]);
  });
});

describe("a narrow status bar", () => {
  const ids = ["pos", "d", "obs", "calc", "bkg", "diff", "ticks:a", "ticks:b"];
  const widths = new Map(ids.map((id) => [id, 100]));
  const order = ["ticks:b", "ticks:a", "bkg"];

  it("drops nothing while the ink fits", () => {
    expect([...dropsFor(ids, widths, 10, 870, order)]).toEqual([]);
  });

  it("drops the reflections from the right first, then Background", () => {
    expect([...dropsFor(ids, widths, 10, 860, order)]).toEqual(["ticks:b"]);
    expect([...dropsFor(ids, widths, 10, 650, order)]).toEqual(["ticks:b", "ticks:a"]);
    expect([...dropsFor(ids, widths, 10, 540, order)]).toEqual(["ticks:b", "ticks:a", "bkg"]);
    expect([...dropsFor(ids, widths, 10, 100, order)]).toEqual(["ticks:b", "ticks:a", "bkg"]);
  });
});

describe("the rebuild's words for the Parameters panel", () => {
  it("writes the degree sign, never deg", () => {
    expect(unitText("deg 2θ")).toBe("° 2θ");
    expect(unitText("deg² 2θ")).toBe("°² 2θ");
    expect(unitText("deg")).toBe("°");
    expect(unitText("counts·deg 2θ")).toBe("counts·° 2θ");
    expect(unitText("Å²")).toBe("Å²");
  });

  it("names the broadening rows in two words", () => {
    expect(shortTitle("Lorentzian size broadening")).toBe("Lorentzian size");
    expect(shortTitle("Gaussian strain broadening")).toBe("Gaussian strain");
    expect(shortTitle("Phase scale")).toBe("Phase scale");
  });
});
