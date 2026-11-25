/**
 * WP-2240 — the peaks-and-indexing workflow's four steps, as pure functions.
 */
import { describe, expect, it } from "vitest";

import {
  LOOK_CHI2_RED,
  absentOf,
  candidateRelation,
  coverageLine,
  limitWord,
  cellColumns,
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
  it("split the cell into six columns, marking what symmetry sets", () => {
    const show = (c: Parameters<typeof cellColumns>[0]) =>
      cellColumns(c).map((x) => `${x.value}${x.pad ? `[${x.pad}]` : ""}${x.fixed ? "*" : ""}`);
    // a set angle is written whole, its `.00` kept as room (the third look)
    expect(show(cand())).toEqual(
      ["9.3750", "9.3750*", "6.8900", "90[.00]*", "90[.00]*", "120[.00]*"]);
    expect(show(cand({ system: "monoclinic", cell: [5.1, 6.2, 7.3, 90, 101.25, 90] })))
      .toEqual(["5.1000", "6.2000", "7.3000", "90[.00]*", "101.25", "90[.00]*"]);
    // rhombohedral axes: b and c follow a, β and γ follow α
    expect(show(cand({ system: "trigonal", cell: [5.2, 5.2, 5.2, 55.3, 55.3, 55.3] })))
      .toEqual(["5.2000", "5.2000*", "5.2000*", "55.30", "55.30*", "55.30*"]);
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
    // the index counts primitive cells, which the V column does not
    expect(candidateRelation(list, 0)).toEqual(
      { mark: "2×", of: 2, kind: "sublattice", key: "cell_relations:sublattice",
        text: "Supercell of #2, twice its primitive cell" });
    expect(candidateRelation(list, 1)).toBeNull();
    expect(candidateRelation(list, 2)).toEqual(
      { mark: "≡", of: 2, kind: "same_cell", key: "cell_relations:same_cell",
        text: "Same cell as #2, another lattice label" });
    // a containment pair has no index: its number is 0, never a volume ratio
    const dense = cand({ cell: [16.24, 16.24, 7.92, 90, 90, 120], supercell_checks: [
      { parent_cell: base.cell, index: 0, relation: "containment", verdict: "undecided" }] });
    expect(candidateRelation([base, dense], 1)).toEqual(
      { mark: "⊇", of: 1, kind: "containment", key: "cell_relations:containment",
        text: "Indexes every line #1 does, and predicts more" });
    const triple = cand({ cell: [16.24, 16.24, 6.888, 90, 90, 120], supercell_checks: [
      { parent_cell: base.cell, index: 3, verdict: "refuted" }] });
    expect(candidateRelation([base, triple], 1)?.text)
      .toBe("Supercell of #1, three times its primitive cell");
  });
  it("write the clock as m:ss", () => {
    expect(clock(109.4)).toBe("1:49");
    expect(clock(-3)).toBe("0:00");
  });
});

describe("the Index step's coverage line", () => {
  it("names what the ceiling left unreached or truncated, and the ceiling", () => {
    const line = coverageLine({
      systems_searched: ["cubic", "hexagonal", "orthorhombic"],
      search_complete: { cubic: true, hexagonal: true, orthorhombic: false },
      diagnostics: [{ code: "INDEX_BUDGET_EXHAUSTED",
        message: "The run hit its declared ceiling of 120 s, so the answer covers what was reached.",
        where: ["truncated: orthorhombic", "not reached: monoclinic, triclinic"] }],
    }, ["cubic", "hexagonal", "orthorhombic", "monoclinic", "triclinic"]);
    expect(line).toEqual({ notSearched: ["monoclinic", "triclinic"],
                           stopped: ["orthorhombic"], ceiling: 120 });
    expect(limitWord(line.ceiling)).toBe("2 minutes");
    expect(limitWord(null)).toBe("None");
  });

  it("says a system a person's Stop left unsearched, and nothing for a full search", () => {
    expect(coverageLine({ systems_searched: ["cubic"], search_complete: { cubic: true } },
                        ["cubic", "tetragonal"]))
      .toEqual({ notSearched: ["tetragonal"], stopped: [], ceiling: null });
    expect(coverageLine({ systems_searched: ["cubic"], search_complete: { cubic: true } },
                        ["cubic"]))
      .toEqual({ notSearched: [], stopped: [], ceiling: null });
  });
});
