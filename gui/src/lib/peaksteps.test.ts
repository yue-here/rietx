/**
 * WP-2202 — the Peaks tab's four steps, as pure functions.
 */
import { describe, expect, it } from "vitest";

import {
  LOOK_CHI2_RED,
  PEAK_STEPS,
  absentOf,
  candidateRelation,
  cellLine,
  clock,
  filterPeaks,
  groupRows,
  unindexedOf,
  type Candidate,
  type GroupCurve,
  type PeakRow,
} from "./peaks";

const row = (index: number, two_theta: number, over: Partial<PeakRow> = {}): PeakRow => ({
  index, two_theta, two_theta_esd: 0.001, d: 1, intensity: 100, fwhm: 0.1,
  group: 0, n_in_group: 1, chi2_red: 1, flags: [], origin: "fitted", usable: true,
  ...over,
});

const cand = (over: Partial<Candidate> = {}): Candidate => ({
  cell: [9.375, 9.375, 6.89, 90, 90, 120], cell_esd: [3e-4, 3e-4, 2e-4, 0, 0, 0],
  system: "hexagonal", centring: "P", lattice_group: "P 6/m m m", volume: 524.4,
  n_indexed: 18, n_lines: 20, fom: [], found_by: ["svd"], confidence: "low",
  confidence_caveats: [], ambiguity: [], lebail: null, diagnostics: [],
  ...over,
});

describe("the steps", () => {
  it("are the four the maintainer named, in order", () => {
    expect([...PEAK_STEPS]).toEqual(["Pick peaks", "Fit peaks", "Index", "Judge"]);
  });
});

describe("filterPeaks", () => {
  const rows = [row(0, 30), row(1, 20, { usable: false }), row(2, 10)];
  it("sorts by 2θ and filters by use", () => {
    expect(filterPeaks(rows, "all").map((p) => p.index)).toEqual([2, 1, 0]);
    expect(filterPeaks(rows, "used").map((p) => p.index)).toEqual([2, 0]);
    expect(filterPeaks(rows, "unused").map((p) => p.index)).toEqual([1]);
  });
  it("keeps a row ticked since the filter was chosen", () => {
    expect(filterPeaks(rows, "unused", new Set([0])).map((p) => p.index)).toEqual([1, 0]);
  });
});

describe("groupRows", () => {
  const curve = (group: number, lo: number, chi2: number): GroupCurve => ({
    group, two_theta: [lo, lo + 0.5], y_fit: [0, 0], y_env: [0, 0], delta: [0, 0],
    chi2_red: chi2, n_components: 1,
  });
  it("marks a group by its χ²ᵣ or a fit flag, never by asymmetry alone", () => {
    const rows = [row(0, 20, { group: 1, flags: ["asymmetry_unmodelled"] }),
                  row(1, 10, { group: 2, flags: ["unresolved_shoulder"] })];
    const out = groupRows([curve(1, 20, 2), curve(2, 10, 2), curve(3, 30, LOOK_CHI2_RED + 1)], rows);
    expect(out.map((g) => [g.group, g.look])).toEqual([[2, true], [1, false], [3, true]]);
  });
});

describe("the candidate columns", () => {
  it("write only the free cell parameters, with esds on request", () => {
    expect(cellLine(cand())).toBe("a = 9.3750, c = 6.8900 Å");
    expect(cellLine(cand(), true)).toBe("a = 9.3750(3), c = 6.8900(2) Å");
    expect(cellLine(cand({ system: "cubic", cell: [4.1568, 4.1568, 4.1568, 90, 90, 90] })))
      .toBe("a = 4.1568 Å");
  });
  it("count the unindexed lines and the absent share", () => {
    expect(unindexedOf(cand())).toBe(2);
    expect(absentOf(cand())).toBeNull();
    expect(absentOf(cand({ lebail: { rwp: 0.18, predicted_but_absent: 34, n_reflections: 400,
      status: "converged", absent_source: "line_screen", n_lines_screened: 189 } })))
      .toEqual({ absent: 34, of: 189 });
  });
  it("mark a repeated cell and a supercell rietx checked, and nothing else", () => {
    const base = cand();
    const twin = cand({ system: "trigonal" });
    const big = cand({ cell: [9.375, 9.375, 13.78, 90, 90, 120], supercell_checks: [
      { parent_cell: base.cell, index: 2, verdict: "undecided" }] });
    const list = [big, base, twin];
    expect(candidateRelation(list, 0)).toBe("#2 with 2× the volume");
    expect(candidateRelation(list, 1)).toBe("");
    expect(candidateRelation(list, 2)).toBe("same cell as #2");
  });
  it("write the clock as m:ss", () => {
    expect(clock(109.4)).toBe("1:49");
    expect(clock(-3)).toBe("0:00");
  });
});
