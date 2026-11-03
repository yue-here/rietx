import { describe, expect, it } from "vitest";

import {
  asRequest,
  axisTitle,
  memberLegend,
  moveBy,
  pointText,
  esdText,
  gapLine,
  rankTrajectories,
  reseededFlags,
  rungNote,
  sortByX,
  topGapPath,
  trajectoryLegend,
  trajectoryNote,
  unrecoveredFlags,
  type DirectionGap,
  type GapAt,
  type LegendEntry,
  type SeriesEntry,
  type SeriesPattern,
  type Trajectory,
} from "./series";

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
    const rows = trajectoryLegend(traj(), [false, true, false], [false, false, true]);
    expect(rows.slice(-2).map((e) => [e.id, e.label, e.mark]))
      .toEqual([["rings", "reseeded", "ring"], ["crosses", "unrecovered", "cross"]]);
    expect(ids(trajectoryLegend(traj(), [false, false, false], [false, false, false])))
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

describe("matching the reseed flags to a trajectory", () => {
  const entries = (over: Array<Partial<SeriesEntry>>): SeriesEntry[] =>
    over.map((o, i) => ({
      index: i, label: `p${i}`, x: null, status: "converged",
      statistics: { rwp: 0.1, gof: 1 }, n_iterations: 1, reseeded: false,
      rwp_warm: null, rung: "warm", rungs_tried: ["warm"], node_id: null,
      tree_id: null, diagnostics: [], ...o,
    }));

  it("matches on the label, because a trajectory skips the patterns it misses", () => {
    // `SeriesResult.trajectory` does not fill gaps: a parameter absent from
    // pattern 0 makes the trajectory start at pattern 1, so index alignment
    // would ring the wrong point
    const rows = entries([{ label: "p0" }, { label: "p1", reseeded: true },
                          { label: "p2" }]);
    const partial = traj({ labels: ["p1", "p2"], x: [400, 500],
                           value: [4.2, 4.3], stderr: [null, null] });
    expect(reseededFlags(partial, rows)).toEqual([true, false]);
    const whole = traj({ labels: ["p0", "p1", "p2"] });
    expect(reseededFlags(whole, rows)).toEqual([false, true, false]);
  });

  it("reads unrecovered off the status, not off a flag of its own", () => {
    // "diverged after the last rung" and "diverged" are the same statement once
    // the chain has run, so a second field could only disagree with this one
    const rows = entries([{}, { status: "diverged", reseeded: false },
                          { status: "max_iter" }]);
    expect(unrecoveredFlags(traj({ labels: ["p0", "p1", "p2"] }), rows))
      .toEqual([false, true, false]);
  });
});
