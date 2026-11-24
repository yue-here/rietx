// The series' Trends rules (WP-2243 task 6): what each value draws, which
// values share a panel, the y span, the walks' gap per panel, the axis and the
// default set. What the canvases paint is `tests/test_gui_series_browser.py`'s.
import { describe, expect, it } from "vitest";

import type { HelpCorpus } from "../lib/help";
import type { SeriesAnswer } from "./seriesresults";
import {
  defaultPlotted, hasCoordinates, nearestPattern, panelGap, panelsOf, plotGroups, powerOf,
  spanOf, tickText, ticks, trendOf, unitOf, unitText, xValues, type Trend,
} from "./seriestrends";

const entry = (index: number, x: number | null, rwp = 0.05) => ({
  index, label: `T${index}`, x, status: "converged", statistics: { rwp, gof: 1.5 },
  n_iterations: 5, reseeded: false, rwp_warm: null, rung: "warm", rungs_tried: [],
  node_id: null, tree_id: null, diagnostics: [],
});
const traj = (path: string, labels: string[], value: number[], over: Record<string, unknown> = {}) => ({
  path, x: labels.map((_, k) => k), x_label: "T (K)", value, stderr: value.map(() => 0.001),
  labels, backward: null, n_sigma: null, gap_at: null, ...over,
});
const answerOf = (trajectories: any[], xs: Array<number | null> = [100, 200, 300]): SeriesAnswer => ({
  entries: xs.map((x, i) => entry(i, x, 0.05 + 0.01 * i)) as any,
  trajectories: trajectories as any, steps: null, gaps: null, codes: null,
  phaseNames: ["Cu", "CuO"], atomLabels: [[], []],
});
const corpus = { parameters: [
  { title: "Lattice parameter a, b, c", unit: "Å", paths: ["phases.*.cell.a", "phases.*.cell.b", "phases.*.cell.c"] },
  { title: "Phase scale", unit: null, paths: ["phases.*.scale"] },
  { title: "Zero-point shift", unit: "deg 2θ", paths: ["instrument.zero_shift"] },
] } as unknown as HelpCorpus;

const trend = (path: string, unit: string | null, values: number[], group = "phases.0"): Trend => ({
  path, name: path, group, groupTitle: group, unit, n: values.length, count: values.length, gap: null,
  points: values.map((value, index) => ({ index, value, esd: 0.001, back: null })),
});

describe("a value across the series", () => {
  it("reads the fit statistics off the entries, Rwp in percent", () => {
    const t = trendOf(answerOf([]), "rwp", null)!;
    expect(t.points.map((p) => Number(p.value.toFixed(9)))).toEqual([5, 6, 7]);
    expect([t.name, t.unit, t.groupTitle, t.count, t.n]).toEqual(["Rwp", "%", "Fit", 3, 3]);
    expect(trendOf(answerOf([]), "gof", null)!.unit).toBeNull();
  });

  it("lands a sparse value on its own patterns only (call 22), with its second walk", () => {
    const a = answerOf([traj("phases.1.cell.a", ["T0", "T2"], [4.68, 4.69],
                             { backward: [4.681, 4.692], n_sigma: 3.1 })]);
    const t = trendOf(a, "phases.1.cell.a", corpus)!;
    expect(t.points).toEqual([{ index: 0, value: 4.68, esd: 0.001, back: 4.681 },
                              { index: 2, value: 4.69, esd: 0.001, back: 4.692 }]);
    expect([t.count, t.n, t.unit, t.groupTitle, t.name, t.gap]).toEqual([2, 3, "Å", "CuO", "cell.a", 3.1]);
  });

  it("matches a label two files share to each in turn", () => {
    const a = answerOf([traj("phases.0.scale", ["T0", "T0"], [1, 2])]);
    a.entries[1] = { ...a.entries[1], label: "T0" };
    expect(trendOf(a, "phases.0.scale", corpus)!.points.map((p) => p.index)).toEqual([0, 1]);
  });

  it("takes each unit from the help corpus's family glob; QPA is percent; others none", () => {
    expect(unitOf("phases.3.cell.c", corpus)).toBe("Å");
    expect(unitOf("instrument.zero_shift", corpus)).toBe("deg 2θ");
    expect(unitOf("phases.0.scale", corpus)).toBeNull();
    expect(unitOf("qpa.CuO", corpus)).toBe("%");
    expect(unitOf("r_bragg.CuO", corpus)).toBeNull();
    expect(unitOf("phases.0.cell.a", null)).toBeNull();
  });

  it("plots Rwp and the first phase's a, b and c by default, as far as the record has them (call 12)", () => {
    const a = answerOf([traj("phases.0.cell.a", ["T0"], [1]), traj("phases.0.cell.c", ["T0"], [1]),
                        traj("phases.1.cell.a", ["T0"], [1])]);
    expect(defaultPlotted(a)).toEqual(["rwp", "phases.0.cell.a", "phases.0.cell.c"]);
  });

  it("offers every value in the menu, the fit first, then each group in the record's order", () => {
    const a = answerOf([traj("phases.1.scale", ["T0"], [1]), traj("instrument.zero_shift", ["T0"], [0]),
                        traj("phases.1.cell.a", ["T0"], [1])]);
    expect(plotGroups(a)).toEqual([
      { key: "#fit", title: "Fit", paths: ["rwp", "gof"] },
      { key: "phases.1", title: "CuO", paths: ["phases.1.scale", "phases.1.cell.a"] },
      { key: "instrument", title: "instrument", paths: ["instrument.zero_shift"] },
    ]);
  });
});

describe("the panels", () => {
  it("puts two values in one panel when group and unit agree and the ranges overlap (call 3)", () => {
    const b = trend("b", "Å", [5.80, 5.81]), c = trend("c", "Å", [5.805, 5.82]);
    const a = trend("a", "Å", [8.2, 8.3]), s = trend("s", null, [1, 2]), s2 = trend("s2", null, [1, 2]);
    const other = trend("b1", "Å", [5.80, 5.81], "phases.1");
    expect(panelsOf([b, a, c, s, s2, other]).map((p) => p.trends.map((t) => t.path)))
      .toEqual([["b", "c"], ["a"], ["s"], ["s2"], ["b1"]]);
  });

  it("holds at most four values in a panel", () => {
    const ts = [0, 1, 2, 3, 4].map((k) => trend(`v${k}`, "Å", [1, 2]));
    expect(panelsOf(ts).map((p) => p.trends.length)).toEqual([4, 1]);
  });

  it("spans the values and their bars, but at most one value-spread past the values (call 23)", () => {
    const t = trend("v", "Å", [1, 2]);
    // short bars: the span is the bars' reach, plus the margin
    t.points[0].esd = 0.1;
    let [lo, hi] = spanOf([t])!;
    expect(lo).toBeCloseTo(0.9 - 1.101 * 0.06, 9);
    expect(hi).toBeCloseTo(2.001 + 1.101 * 0.06, 9);
    // a bar longer than the spread is cut one spread past the values
    t.points[0].esd = 50;
    [lo, hi] = spanOf([t])!;
    expect(lo).toBeCloseTo(0 - 0.18, 9);
    expect(hi).toBeCloseTo(3 + 0.18, 9);
    expect(spanOf([trend("none", null, [])])).toBeNull();
  });

  it("names the largest of the record's walk gaps over a panel's values (call 4)", () => {
    const b = { ...trend("b", "Å", [1]), gap: 1.2 }, c = { ...trend("c", "Å", [1]), gap: 5.8 };
    expect(panelGap({ trends: [b, c], unit: "Å" })).toBe(5.8);
    expect(panelGap({ trends: [trend("a", "Å", [1])], unit: "Å" })).toBeNull();
  });
});

describe("the axes", () => {
  it("reads the coordinate, or the pattern number when a pattern has none (call 21)", () => {
    expect([...xValues(answerOf([]), "x").values()]).toEqual([100, 200, 300]);
    expect([...xValues(answerOf([]), "n").values()]).toEqual([1, 2, 3]);
    const bare = answerOf([], [100, null, 300]);
    expect(hasCoordinates(bare)).toBe(false);
    expect([...xValues(bare, "x").values()]).toEqual([1, 2, 3]);
  });

  it("ticks at 1, 2, 2.5 or 5 times a power of ten, labelled at the step's decimals", () => {
    expect(ticks(0, 1, 4)).toEqual({ values: [0, 0.25, 0.5, 0.75, 1], step: 0.25 });
    expect(tickText(-0.25, 0.25, 0)).toBe("−0.25");
    expect(tickText(3e-7, 1e-7, powerOf(1e-7, 5e-7))).toBe("3");
    expect(unitText(null, -7)).toBe("×10⁻⁷");
    expect(unitText("Å", 0)).toBe("Å");
  });

  it("finds the pattern nearest the pointer within reach", () => {
    const xs = new Map([[0, 100], [1, 200]]);
    expect(nearestPattern(xs, 190)).toBe(1);
    expect(nearestPattern(xs, 150)).toBeNull();
  });
});
