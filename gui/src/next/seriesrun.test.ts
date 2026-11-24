// The series workflow's pure helpers (WP-2243): the Patterns step's span,
// order and axis word, and the Run step's fold of the run's own events.
import { describe, expect, it } from "vitest";

import type { SeriesEntry, SeriesPattern } from "../lib/series";
import type { EngineEvent } from "../lib/stream";
import {
  axisWord, emptyProgress, fitsDone, fold, inOrder, merged, rwpText, secondWalkDone, spanOf,
  startedFrom,
} from "./seriesrun";

const pattern = (x: number | null, lo = 5, hi = 50): SeriesPattern => ({
  upload: `u${x}`, filename: `T${x}.xye`, label: `T${x}`, x, reader: "xye",
  reader_options: {}, n_points: 2000, two_theta_range: [lo, hi], has_sigma: true,
});

let seq = 0;
const ev = (kind: string, data: Record<string, unknown>): EngineEvent =>
  ({ seq: ++seq, kind, t: seq, data });
const stamp = (index: number, pass = "forward", extra: Record<string, unknown> = {}) =>
  ({ series_index: index, series_label: `T${index}`, series_n: 3, series_pass: pass, ...extra });

describe("the Patterns step's helpers", () => {
  it("spans every member's range", () => {
    expect(spanOf([])).toBeNull();
    expect(spanOf([pattern(1, 5, 40), pattern(2, 7, 49.9)])).toEqual([5, 49.9]);
  });

  it("calls a list in order when Sort by would change nothing", () => {
    expect(inOrder([pattern(null), pattern(null)])).toBe(true);
    expect(inOrder([pattern(10), pattern(20), pattern(null)])).toBe(true);
    expect(inOrder([pattern(20), pattern(10)])).toBe(false);
    // a member with no coordinate goes after every one with a coordinate
    expect(inOrder([pattern(null), pattern(10)])).toBe(false);
  });

  it("sorts by the axis's name without its unit", () => {
    expect(axisWord("T (K)")).toBe("T");
    expect(axisWord("  ")).toBe("index");
  });
});

describe("the Run step's fold", () => {
  it("takes each walk's fits as they land, the first from the model", () => {
    let p = emptyProgress();
    p = fold(p, ev("fit_start", stamp(0)));
    expect(p.current).toEqual({ index: 0, label: "T0", pass: "forward" });
    expect(p.n).toBe(3);
    p = fold(p, ev("eval", stamp(0)));
    p = fold(p, ev("fit_end", stamp(0, "forward", { rwp: 0.2241, gof: 1.9, status: "converged" })));
    expect(p.current).toBeNull();
    expect(p.fits.forward[0]).toEqual({ rwp: 0.2241, gof: 1.9, status: "converged", rung: "cold" });
    p = fold(p, ev("fit_start", stamp(1)));
    p = fold(p, ev("fit_end", stamp(1, "forward", { rwp: 0.22, gof: 1.8, status: "converged" })));
    expect(p.fits.forward[1].rung).toBe("warm");
    // a restart on the ladder names its rung
    p = fold(p, ev("fit_start", stamp(2)));
    p = fold(p, ev("fit_start", stamp(2, "forward", { series_rung: "warm_staged" })));
    p = fold(p, ev("fit_end", stamp(2, "forward", { rwp: 0.23, gof: 2, status: "converged" })));
    expect(p.fits.forward[2].rung).toBe("warm_staged");
    // the second walk starts from the model again
    p = fold(p, ev("fit_start", stamp(2, "backward")));
    expect(p.passes).toEqual(["forward", "backward"]);
    expect(p.rungs.backward[2]).toBe("cold");
    expect(fitsDone(p)).toBe(3);
  });

  it("ignores an event that is not a series pattern's, and a verify refit", () => {
    const p = emptyProgress();
    expect(fold(p, ev("fit_start", {}))).toBe(p);
    expect(fold(p, ev("fit_start", stamp(0, "verify")))).toBe(p);
  });

  it("gives way to the record's entries once the run has ended", () => {
    let p = fold(emptyProgress(), ev("fit_start", stamp(0)));
    const entries = [{ index: 0, statistics: { rwp: 0.25, gof: 2 }, status: "converged",
                       rung: "cold" }] as unknown as SeriesEntry[];
    p = merged(p, entries, "forward");
    expect(p.current).toBeNull();
    expect(p.fits.forward[0].rwp).toBe(0.25);
    expect(merged(p, null, "forward")).toBe(p);
  });

  it("reads the second walk's patterns off the record, by label, for a page that did not follow", () => {
    const entries = [{ index: 0, label: "T0" }, { index: 2, label: "T2" }] as SeriesEntry[];
    // pattern 1 failed and has no entry; the second walk left T2 without a value
    expect([...secondWalkDone(entries, { labels: ["T0", "T2"], backward: [4.1, NaN] })]).toEqual([0]);
    expect(secondWalkDone(entries, { labels: ["T0", "T2"], backward: null }).size).toBe(0);
    expect(secondWalkDone(entries, null).size).toBe(0);
  });

  it("words the rungs and the Rwp as the tables print them", () => {
    expect(["cold", "warm", "warm_staged", null].map(startedFrom))
      .toEqual(["model", "previous", "previous, whole plan", ""]);
    expect(rwpText(0.22414)).toBe("22.41");
    expect(rwpText(null)).toBe("");
  });
});
