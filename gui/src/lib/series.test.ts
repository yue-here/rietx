import { describe, expect, it } from "vitest";

import {
  asRequest,
  axisTitle,
  memberLegend,
  moveBy,
  pointText,
  largestStep,
  markedFlags,
  markOf,
  esdText,
  gapLine,
  rankTrajectories,
  rejectedBecause,
  rungNote,
  sortByX,
  stepTo,
  traceData,
  traceKey,
  traceText,
  stepCells,
  stepRows,
  topGapPath,
  trajectoryLegend,
  trajectoryMarks,
  trajectoryNote,
  unrecoveredFlags,
  type DirectionGap,
  type GapAt,
  type LegendEntry,
  type SeriesEntry,
  type SeriesStep,
  type SeriesPattern,
  type Trace,
  type Trajectory,
} from "./series";

/** A served trace (`rietx.gui.series.trace`): a reseed at 1, a failure at 2,
 *  a pattern unrecovered at 3 that also carries a code no row names. */
const trace = (): Trace => ({
  x_label: "T",
  points: [
    { index: 0, label: "T300", x: 300, status: "converged", rwp: 0.05, marks: [], findings: [] },
    { index: 1, label: "T310", x: 310, status: "converged", rwp: 0.051,
      marks: ["SEQUENTIAL_RESEED"],
      findings: [{ code: "BOUND_HIT", level: "warning" },
                 { code: "HIGH_CORRELATION", level: "warning" }] },
    { index: 2, label: "T320", x: null, status: "failed", rwp: null,
      marks: ["SERIES_PATTERN_FAILED"], findings: [] },
    { index: 3, label: "T330", x: 330, status: "converged", rwp: 0.2,
      marks: ["SEQUENTIAL_UNRECOVERED", "SOME_FUTURE_CODE"],
      findings: [{ code: "PHASE_UNCONSTRAINED", level: "warning" }] },
  ],
  largest_steps: { "phases.0.cell.a": { indices: [2, 3], size_esd: 40, cold_ratio: null } },
  vocabulary: [
    ["SERIES_PATTERN_FAILED", "bar", "failed"], ["SEQUENTIAL_UNRECOVERED", "cross", "unrecovered"],
    ["SEQUENTIAL_RESEED", "ring", "reseeded"],
    ["findings", "count", "findings"], ["largest_step", "band", "largest step"],
  ].map(([key, mark, label]) => ({ key, mark, label, source: "", means: "" })),
  other_mark: "tick",
});

const member = (over: Partial<SeriesPattern> = {}): SeriesPattern => ({
  upload: "tok", filename: "p.xye", label: "p", x: null, reader: "xy",
  reader_options: {}, n_points: 10, two_theta_range: [3, 24], has_sigma: true, ...over,
});

const traj = (over: Partial<Trajectory> = {}): Trajectory => ({
  path: "phases.0.cell.a", x: [300, 400, 500], x_label: "T",
  value: [4.1, 4.2, 4.3], stderr: [1e-4, null, 1e-4],
  labels: ["a", "b", "c"], backward: null, n_sigma: null, gap_at: null, ...over,
});

/** A gap's place, with both chains on the same rung unless the test says not. */
const at = (over: Partial<GapAt> = {}): GapAt => ({
  label: "b", index: 1, forward_rung: "warm", backward_rung: "warm", ...over,
});


describe("the staged list", () => {
  it("sends the coordinate only when there is one", () => {
    const sent = asRequest([member({ upload: "a", x: 300 }),
                            member({ upload: "b", x: null })]);
    // a missing key is the server's "the index is the axis"; sending `null`
    // would be a coordinate whose value is null, which is a different claim
    expect(sent[0]).toEqual({ upload: "a", label: "p", x: 300 });
    expect(sent[1]).toEqual({ upload: "b", label: "p" });
  });

  it("returns the same array when a member cannot move", () => {
    const list = [member({ upload: "a" }), member({ upload: "b" })];
    // identity, not equality: the caller skips the PUT on it, and a PUT that
    // rewrote the server's list to what it already holds would re-read every
    // file to prove nothing
    expect(moveBy(list, 0, -1)).toBe(list);
    expect(moveBy(list, 1, 1)).toBe(list);
    expect(moveBy(list, 9, -1)).toBe(list);
    expect(moveBy(list, 1, -1).map((m) => m.upload)).toEqual(["b", "a"]);
    expect(moveBy(list, 0, 1).map((m) => m.upload)).toEqual(["b", "a"]);
    expect(list.map((m) => m.upload)).toEqual(["a", "b"]);   // not mutated
  });

  it("sorts by the coordinate and leaves the uncoordinated at the end", () => {
    const list = [member({ upload: "c", x: 500 }), member({ upload: "none" }),
                  member({ upload: "a", x: 300 }), member({ upload: "b", x: 400 })];
    // inventing a coordinate for the member that has none is exactly what `null`
    // refuses, so it keeps its place rather than sorting as 0
    expect(sortByX(list).map((m) => m.upload)).toEqual(["a", "b", "c", "none"]);
  });
});

describe("ranking trajectories", () => {
  it("ranks by the gap, largest first, with no threshold", () => {
    // a 0.4 esd gap is listed in its place and a 5.2 esd one is not "flagged":
    // the record states the number for every parameter (WP-2003, C5)
    const rows = [
      traj({ path: "small", n_sigma: 0.4 }),
      traj({ path: "big", n_sigma: 11.2 }),
      traj({ path: "middle", n_sigma: 3.4 }),
    ];
    expect(rankTrajectories(rows).map((t) => t.path)).toEqual(
      ["big", "middle", "small"]);
    // the input is untouched: the panel's select and its plot read the same list
    expect(rows.map((t) => t.path)).toEqual(["small", "big", "middle"]);
  });

  it("does not rank a null gap as agreement", () => {
    // `n_sigma: null` is where the record has no gap in esds (a chain gave no
    // esd, or the path is relative), so it must neither outrank a measured
    // small gap nor be taken for a large one
    const rows = [traj({ path: "unknown", n_sigma: null }),
                  traj({ path: "measured", n_sigma: 0.2 }),
                  traj({ path: "agrees", n_sigma: 0 })];
    expect(rankTrajectories(rows).map((t) => t.path)).toEqual(
      ["measured", "agrees", "unknown"]);
  });

  it("keeps the series' own order among equal gaps and among the absent", () => {
    // The record writes a gap under the trajectory's noise floor as exactly 0,
    // so a clean ramp's parameters tie and the cell edge stays where the
    // series put it, which ranking by noise did not (found in a browser).
    const rows = [
      traj({ path: "phases.0.cell.a", n_sigma: 0 }),
      traj({ path: "phases.0.scale", n_sigma: 0 }),
      traj({ path: "instrument.zero_shift", n_sigma: 0 }),
      traj({ path: "qpa.LaB6", n_sigma: null }),
      traj({ path: "qpa.CaF2", n_sigma: null }),
    ];
    expect(rankTrajectories(rows).map((t) => t.path)).toEqual(
      ["phases.0.cell.a", "phases.0.scale", "instrument.zero_shift",
       "qpa.LaB6", "qpa.CaF2"]);
    // …and one with a size comes ahead of the ties from wherever it was
    rows[2] = traj({ path: "instrument.zero_shift", n_sigma: 5.2 });
    expect(rankTrajectories(rows)[0].path).toBe("instrument.zero_shift");
  });
});

describe("the gap in words", () => {
  const gap = (over: Partial<DirectionGap> = {}): DirectionGap => ({
    path: "phases.0.cell.a", label: "T500", index: 2, forward: 4.16,
    backward: 4.161, gap: -0.001, gap_esd: -4.2, forward_rung: "warm",
    backward_rung: "warm", ...over,
  });

  it("prints a size in esds without rounding a real gap to nothing", () => {
    expect(esdText(4.23)).toBe("4.2");
    expect(esdText(-4.23)).toBe("4.2");
    expect(esdText(0)).toBe("0");
    expect(esdText(0.04)).toBe("<0.1");
  });

  it("states the gap as a number with its place and asserts no verdict", () => {
    const note = trajectoryNote(traj({ backward: [1, 2, 3], n_sigma: 4.2,
                                       gap_at: at({ label: "c" }) }));
    expect(note).toContain("differ by 4.2 esd at c");
    expect(note).not.toMatch(/path-dependent|artefact|agree/i);
  });

  it("says nothing where no chain ran, and says what is missing where one did", () => {
    expect(trajectoryNote(traj())).toBe("");
    expect(trajectoryNote(traj({ backward: [1, 2, 3] })))
      .toContain("no gap in esds for this parameter");
  });

  it("says the gap measures the ladder where the two chains kept different rungs", () => {
    expect(rungNote(at())).toBe("");
    expect(rungNote(null)).toBe("");
    const differ = at({ label: "T500", forward_rung: "warm", backward_rung: "cold" });
    expect(rungNote(differ)).toContain("forward chain kept the warm attempt");
    expect(rungNote(differ)).toContain("backward chain the cold one");
    expect(rungNote(differ)).toContain("escalation ladder");
    // and it reaches the caption and the panel's line, not only the helper
    const note = trajectoryNote(traj({ backward: [1, 2, 3], n_sigma: 4.2, gap_at: differ }));
    expect(note).toContain("escalation ladder");
    expect(gapLine([gap({ forward_rung: "warm_staged", backward_rung: "cold" })]))
      .toContain("escalation ladder");
    expect(gapLine([gap()])).not.toContain("ladder");
  });

  it("opens the panel's line with the largest gap in the record", () => {
    // the record lists the largest first; `None` sorts after every number
    const rows = [gap({ path: "phases.0.scale", gap_esd: null }),
                  gap({ gap_esd: -4.2 }), gap({ path: "x", gap_esd: 1 })];
    expect(gapLine(rows)).toContain("differ by 4.2 esd at most, in phases.0.cell.a at T500");
    expect(topGapPath(rows)).toBe("phases.0.cell.a");
  });

  it("is silent where the comparison did not run, and explains where it ran blind", () => {
    expect(gapLine(null)).toBe("");
    expect(gapLine(undefined)).toBe("");
    expect(topGapPath(null)).toBeNull();
    expect(gapLine([gap({ gap_esd: null })])).toContain("no gap could be put in esds");
    expect(topGapPath([gap({ gap_esd: null })])).toBeNull();
  });

});

describe("the steps between neighbouring patterns", () => {
  const step = (over: Partial<SeriesStep> = {}): SeriesStep => ({
    path: "phases.0.cell.a", labels: ["T300", "T400"], indices: [0, 1],
    step: 0.0021, size_esd: 21, cold_ratio: null, ...over,
  });
  // the record's order: largest |size_esd| first, no size last
  const record = [
    step({ size_esd: -40, step: -0.004 }),
    step({ path: "phases.0.scale", size_esd: 9 }),
    step({ labels: ["T400", "T500"], indices: [1, 2], size_esd: 2 }),
    step({ labels: ["T500", "T600"], indices: [2, 3], size_esd: null }),
  ];

  it("keeps the record's order and filters to a parameter", () => {
    // largest first is the record's own order; a second sort here could disagree
    expect(stepRows(record, "phases.0.cell.a").rows.map((s) => s.size_esd))
      .toEqual([-40, 2, null]);
    expect(stepRows(record, null).rows.map((s) => s.path))
      .toEqual(["phases.0.cell.a", "phases.0.scale", "phases.0.cell.a", "phases.0.cell.a"]);
  });

  it("caps the rows and says how many there were", () => {
    const { rows, total } = stepRows(record, null, 2);
    expect(rows.length).toBe(2);
    expect(total).toBe(4);
    expect(stepRows(null, null)).toEqual({ rows: [], total: 0 });
    expect(stepRows(undefined, "x")).toEqual({ rows: [], total: 0 });
  });

  it("prints a signed step and size, and a dash where there is no esd", () => {
    expect(stepCells(record[0])).toEqual({
      between: "T300 → T400", step: "−0.004", esd: "−40.0", cold: "—" });
    expect(stepCells(record[1]).esd).toBe("+9.0");
    // no esd, no size: 0 would read as one
    expect(stepCells(record[3]).esd).toBe("—");
    expect(stepCells(step({ cold_ratio: 0.9876 })).cold).toBe("0.99");
    expect(stepCells(step({ cold_ratio: -0.3 })).cold).toBe("-0.30");
  });
});

describe("a trajectory's axis title", () => {
  it("titles a QPA trajectory as a weight percentage", () => {
    expect(axisTitle(traj({ path: "qpa.corundum" }))).toBe("corundum (wt %)");
  });

  it("names the residual on an agreement trajectory, keeping the two apart", () => {
    // gui/series.py serves `r_bragg.<phase>`/`r_f.<phase>` rows.  Stripped to
    // the leaf both would read `LaB6` — no unit, a residual disguised as a
    // parameter named after the phase, and identical between the two metrics.
    expect(axisTitle(traj({ path: "r_bragg.LaB6" }))).toBe("LaB6 R_Bragg");
    expect(axisTitle(traj({ path: "r_f.LaB6" }))).toBe("LaB6 R_F");
    expect(axisTitle(traj({ path: "r_bragg.LaB6" })))
      .not.toBe(axisTitle(traj({ path: "r_f.LaB6" })));
  });

  it("titles the y axis with the leaf, because the margin is what clips", () => {
    // Measured in a browser: a *rotated* title shares the fixed left margin with
    // the tick labels, so `phases.0.cell.a` — fifteen characters, under
    // matplotlib's 24-character cut — came out as `aes.0.cell.a`.  The full path
    // is the heading above the plot.
    expect(axisTitle(traj({ path: "phases.0.cell.a" }))).toBe("a");
    expect(axisTitle(traj({ path: "phases.0.atoms.3.adp.2" }))).toBe("2");
    expect(axisTitle(traj({ path: "instrument.background.c11" }))).toBe("c11");
  });
});

describe("the legend", () => {
  const ids = (rows: LegendEntry[]) => rows.map((e) => e.id);

  it("offers a whisker only where some point has an esd to draw", () => {
    // a point with no esd has no whisker at all (`rxplot.trajectory`); a
    // zero-length one would claim it was measured exactly
    expect(ids(trajectoryLegend(traj()))).toEqual(["forward", "esd"]);
    expect(ids(trajectoryLegend(traj({ stderr: [null, null, null] }))))
      .toEqual(["forward"]);
  });

  it("draws the forward chain in one ink whatever its gap is", () => {
    // no parameter is called path-dependent, so none wears a warning ink
    for (const n_sigma of [null, 0, 40]) {
      const [forward] = trajectoryLegend(traj({ n_sigma }));
      expect(forward).toEqual({ id: "forward", label: "forward", ink: "--plot-diff",
                                mark: "line" });
    }
  });

  it("offers the backward chain only when there is one", () => {
    expect(ids(trajectoryLegend(traj({ backward: [4.11, 4.21, 4.31] }))))
      .toEqual(["forward", "esd", "backward"]);
  });

  it("rings and crosses are offered where the flags put one", () => {
    // a ring is a good fit reached from a different starting model; a cross is
    // a fit that diverged on every rung, so its value is not a measurement at
    // all (WP-1051) — the same mark for both would collapse the two into "odd"
    const rows = trajectoryLegend(traj(), { rings: [false, true, false],
                                            crosses: [false, false, true] });
    expect(rows.slice(-2).map((e) => [e.id, e.label, e.mark]))
      .toEqual([["rings", "reseeded", "ring"], ["crosses", "unrecovered", "cross"]]);
    expect(ids(trajectoryLegend(traj(), { rings: [false, false, false],
                                          crosses: [false, false, false] })))
      .toEqual(["forward", "esd"]);
  });

  it("offers a member's masked points only when the protocol masked any", () => {
    expect(ids(memberLegend(false))).toEqual(["obs", "calc", "bkg", "diff"]);
    expect(ids(memberLegend(true))).toEqual(["obs", "masked", "calc", "bkg", "diff"]);
  });

  it("keeps a missing background listed, disabled and saying why", () => {
    const bkg = memberLegend(false, false).find((e) => e.id === "bkg");
    expect(bkg?.absent).toMatch(/no background/);
    expect(memberLegend(false).find((e) => e.id === "bkg")?.absent).toBeUndefined();
  });
});

describe("what the pointer says", () => {
  it("names the pattern, its coordinate and the value with its esd", () => {
    expect(pointText(traj(), 0, "forward")).toBe("a · 300: 4.1 ± 0.0001");
    // no esd, no ±: the fit estimated nothing, so nothing is claimed
    expect(pointText(traj(), 1, "forward")).toBe("b · 400: 4.2");
  });

  it("names a backward point as the backward chain's", () => {
    const both = traj({ backward: [4.11, 4.21, 4.31] });
    expect(pointText(both, 2, "backward")).toBe("c · 500: 4.31 (backward)");
  });

  it("gives the value six significant figures and its esd two", () => {
    // six as the hover did under plotly; two as an esd is quoted, where six
    // printed `± 0.0000889554` in a browser
    expect(pointText(traj({ value: [4.123456789, 0, 0],
                            stderr: [0.0000889554, null, null] }), 0, "forward"))
      .toBe("a · 300: 4.12346 ± 0.000089");
  });
});

describe("the trace", () => {
  it("draws each verdict with its vocabulary row's glyph, and an unknown code too", () => {
    // the codes are an open vocabulary: a new fence is drawn, never dropped
    const d = traceData(trace());
    expect(d.index).toEqual([0, 1, 2, 3]);
    expect(d.marks).toEqual([[], ["ring"], ["bar"], ["cross", "tick"]]);
    expect(d.findings).toEqual([0, 2, 0, 1]);
    expect(d.y).toEqual([300, 310, null, 330]);
    expect(markOf(trace(), "SOME_FUTURE_CODE")).toBe("tick");
  });

  it("draws a series with no coordinate on its index alone", () => {
    const t = trace();
    t.points = t.points.map((p) => ({ ...p, x: null }));
    expect(traceData(t).y).toBeNull();
  });

  it("keys only what this series uses, an unknown code named by itself", () => {
    const keys = (path: string | null) => traceKey(trace(), path).map((r) => r.key);
    expect(keys(null)).toEqual(["SERIES_PATTERN_FAILED", "SEQUENTIAL_UNRECOVERED",
                                "SEQUENTIAL_RESEED", "findings", "SOME_FUTURE_CODE"]);
    // the band belongs to the parameter on show, so it is keyed only with one
    expect(keys("phases.0.cell.a")).toContain("largest_step");
    expect(keys("phases.0.scale")).not.toContain("largest_step");
  });

  it("shades the largest step of the parameter on show, and nothing for another", () => {
    expect(largestStep(trace(), "phases.0.cell.a")).toEqual([2, 3]);
    expect(largestStep(trace(), "phases.0.scale")).toBeNull();
    expect(largestStep(trace(), null)).toBeNull();
  });

  it("names a pattern by its coordinate, its verdicts' labels and its findings", () => {
    expect(traceText(trace(), 1)).toBe(
      "T310 · T 310 · Rwp 5.10% · reseeded · 2 findings: BOUND_HIT, HIGH_CORRELATION");
    expect(traceText(trace(), 2)).toBe("T320 · #2 · no fit · failed");
    expect(traceText(trace(), 9)).toBe("");
  });

  it("steps by one and stops at the ends", () => {
    expect(stepTo(trace(), 1, 1)).toBe(2);
    expect(stepTo(trace(), 3, 1)).toBe(3);
    expect(stepTo(trace(), 0, -1)).toBe(0);
    expect(stepTo(trace(), null, 1)).toBe(0);
    expect(stepTo(trace(), null, -1)).toBe(3);
    expect(stepTo({ ...trace(), points: [] }, null, 1)).toBe(-1);
  });

  it("puts the trajectory's marks where the trace's verdicts are, by label", () => {
    // `SeriesResult.trajectory` does not fill gaps: a parameter absent from
    // the first pattern starts the trajectory at the second, so index
    // alignment would ring the wrong point
    const partial = traj({ labels: ["T310", "T330"], x: [310, 330],
                           value: [4.2, 4.3], stderr: [null, null] });
    const row = (label: string, index: number): SeriesEntry => ({
      index, label, x: null, status: "converged", statistics: { rwp: 0.1, gof: 1 },
      n_iterations: 1, reseeded: false, rwp_warm: null, rung: "warm",
      rungs_tried: ["warm"], node_id: null, tree_id: null, diagnostics: [] });
    // rings come from the trace's verdicts, crosses from the server's `rejected`
    // by position (T300, T310, T330 have entries; T320 failed)
    const rows = [row("T300", 0), row("T310", 1), row("T330", 3)];
    expect(trajectoryMarks(partial, trace(), rows, [false, false, true])).toEqual({
      rings: [true, false], crosses: [false, true] });
    expect(markedFlags(partial, null, "SEQUENTIAL_RESEED")).toEqual([false, false]);
  });
});

describe("matching the rejection flags to a trajectory", () => {
  const entries = (over: Array<Partial<SeriesEntry>>): SeriesEntry[] =>
    over.map((o, i) => ({
      index: i, label: `p${i}`, x: null, status: "converged",
      statistics: { rwp: 0.1, gof: 1 }, n_iterations: 1, reseeded: false,
      rwp_warm: null, rung: "warm", rungs_tried: ["warm"], node_id: null,
      tree_id: null, diagnostics: [], ...o,
    }));

  it("marks what the library rejected, not only what diverged", () => {
    // `rejected` is the server's answer from the chain's own quarantine test:
    // diverged, or carrying an error-level code. A fit that converged under
    // MODEL_FAR_FROM_DATA is quarantined and must be marked, and a status read
    // would have missed it (WP-2003, C2 q5).
    const error = { level: "error", code: "MODEL_FAR_FROM_DATA", message: "far" };
    const rows = entries([{}, { status: "diverged" },
                          { status: "converged", diagnostics: [error] }]);
    const rejected = [false, true, true];
    expect(unrecoveredFlags(traj({ labels: ["p0", "p1", "p2"] }), rows, rejected))
      .toEqual([false, true, true]);
    // the panel derives nothing: a diverged status the server did not reject
    // (no `rejected` row) is not marked here
    expect(unrecoveredFlags(traj({ labels: ["p0", "p1", "p2"] }), rows, []))
      .toEqual([false, false, false]);
  });

  it("matches the rejection on the entry's index when a trajectory skips patterns", () => {
    const rows = entries([{ label: "p0" }, { label: "p1" }, { label: "p2" }]);
    const partial = traj({ labels: ["p1", "p2"], x: [400, 500], value: [4.2, 4.3],
                           stderr: [null, null] });
    expect(unrecoveredFlags(partial, rows, [true, false, true])).toEqual([false, true]);
  });

  it("reads `rejected` by position when a pattern that raised left no entry", () => {
    // pattern 1 raised, so the entries are indices 0 and 2 and the server's
    // `rejected` has two rows; reading it by index would look past the end
    const rows = entries([{ label: "p0" }, { label: "p2" }]);
    rows[1].index = 2;
    expect(unrecoveredFlags(traj({ labels: ["p0", "p2"] }), rows, [false, true]))
      .toEqual([false, true]);
  });

  it("names what made the library reject a fit, from the entry's own fields", () => {
    const error = (code: string) => ({ level: "error", code, message: "m" });
    const warn = { level: "warning", code: "BOUND_HIT", message: "m" };
    expect(rejectedBecause(entries([{ status: "diverged" }])[0]))
      .toBe("the solver diverged");
    expect(rejectedBecause(entries([{ diagnostics: [warn, error("MODEL_FAR_FROM_DATA")] }])[0]))
      .toBe("it carries the error-level code MODEL_FAR_FROM_DATA");
    expect(rejectedBecause(entries([{ status: "diverged",
      diagnostics: [error("A"), error("B"), error("A")] }])[0]))
      .toBe("the solver diverged and it carries the error-level codes A, B");
    expect(rejectedBecause(entries([{}])[0])).toBe("");
  });
});
