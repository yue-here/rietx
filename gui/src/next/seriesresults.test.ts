// The series workflow's Results step helpers (WP-2243, task 4): the record's
// numbers read in its own order, the values at one pattern, the names.
import { describe, expect, it } from "vitest";

import type { SeriesEntry, Trajectory } from "../lib/series";
import {
  answerOf, countText, groupOfPath, largestGap, pathName, seriesWarnings, sizedSteps,
  valueGroups, warningsOf,
} from "./seriesresults";

const entry = (index: number, rwp: number | null, diagnostics: SeriesEntry["diagnostics"] = []): SeriesEntry => ({
  index, label: `T${index}`, x: 300 + 100 * index, status: "converged",
  statistics: rwp === null ? null : { rwp, gof: 1.5 + index / 10 }, n_iterations: 10,
  reseeded: false, rwp_warm: null, rung: index ? "warm" : "cold", rungs_tried: [],
  node_id: null, tree_id: null, diagnostics,
});

const traj = (path: string, labels: string[], value: number[], stderr: number[]): Trajectory => ({
  path, x: labels.map((_, i) => i), x_label: "T (K)", value, stderr, labels,
  backward: null, n_sigma: null, gap_at: null,
});

const payload = {
  result: {
    entries: [entry(0, 0.0419), entry(1, 0.0434, [
      { level: "warning", code: "BOUND_HIT", message: "a hit its bound" },
      { level: "info", code: "NOTE", message: "an aside" }])],
    steps: [
      { path: "instrument.zero_shift", labels: ["T0", "T1"], indices: [0, 1], step: 0.01,
        size_esd: null, cold_ratio: null },
      { path: "phases.0.cell.a", labels: ["T0", "T1"], indices: [0, 1], step: 0.0021,
        size_esd: 4.26, cold_ratio: null },
    ],
    direction_gaps: [
      { path: "phases.0.atoms.1.biso", label: "T1", index: 1, forward: 0.5, backward: 0.4,
        gap: 0.1, gap_esd: null, forward_rung: "warm", backward_rung: "warm" },
      { path: "phases.0.cell.a", label: "T1", index: 1, forward: 4.1, backward: 4.1,
        gap: 1e-4, gap_esd: -0.83, forward_rung: "warm", backward_rung: "warm" },
    ],
    code_counts: [
      { code: "BOUND_HIT", path: "phases.0.cell.a", count: 1, n_patterns: 2, level: "warning" },
      { code: "NOTE", path: null, count: 2, n_patterns: 2, level: "info" },
      { code: "FLAT_DIRECTION", path: null, count: 2, n_patterns: 2, level: "warning" },
    ],
    phase_names: ["LaB6"],
    atom_labels: [["La1", "B1"]],
  },
  trajectories: [
    traj("phases.0.cell.a", ["T0", "T1"], [4.15692, 4.15901], [0.00002, 0.00003]),
    traj("phases.0.atoms.1.biso", ["T1"], [0.41], [0.05]),
    traj("qpa.LaB6", ["T0", "T1"], [100, 100], [0, 0]),
  ],
};

describe("the Results step's helpers", () => {
  const a = answerOf(payload);

  it("takes the record's largest gap and step with a size, in the record's order", () => {
    expect(largestGap(a.gaps)?.path).toBe("phases.0.cell.a");
    expect(sizedSteps(a.steps).map((s) => s.path)).toEqual(["phases.0.cell.a"]);
    expect(largestGap(null)).toBeNull();
  });

  it("names a path by its phase, its atom and its leaf", () => {
    expect(pathName("phases.0.cell.a", a)).toBe("LaB6 cell.a");
    expect(pathName("phases.0.atoms.1.biso", a)).toBe("LaB6 B1 biso");
    expect(pathName("instrument.zero_shift", a)).toBe("instrument zero_shift");
    expect(groupOfPath("qpa.LaB6")).toBe("qpa");
    expect(pathName("qpa.LaB6", a)).toBe("qpa LaB6");
  });

  it("lists every value at the selected pattern, the statistics first, and counts a partial one", () => {
    const groups = valueGroups(a, 0);
    expect(groups.map((g) => g.title)).toEqual(["Fit", "LaB6", "LaB6 B1", "qpa"]);
    expect(groups[0].rows.map((r) => [r.name, r.value])).toEqual([["Rwp (%)", "4.19"], ["GoF", "1.50"]]);
    expect(groups[1].rows[0]).toMatchObject({ name: "cell.a", value: "4.15692", count: 2, n: 2 });
    // refined on one pattern of two, with no point at the first
    expect(groups[2].rows[0]).toMatchObject({ name: "biso", value: "", count: 1, n: 2 });
    expect(valueGroups(a, 1)[2].rows[0].value).toBe("0.41");
  });

  it("counts a pattern's warnings and the series' non-info codes", () => {
    expect(warningsOf(a.entries[1]).map((d) => d.code)).toEqual(["BOUND_HIT"]);
    expect(warningsOf(a.entries[0])).toEqual([]);
    expect(seriesWarnings(a.codes).map((c) => [c.code, countText(c)]))
      .toEqual([["BOUND_HIT", "1 of 2"], ["FLAT_DIRECTION", "every pattern"]]);
  });
});
