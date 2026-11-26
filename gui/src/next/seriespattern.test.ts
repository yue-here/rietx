// The series' selected pattern as pure functions (WP-2243 task 5): which list
// and place the graph draws, the title's words, and the retry that waits for
// a fit the run's events say has landed.
import { describe, expect, it, vi } from "vitest";

import type { SeriesPattern } from "../lib/series";
import { drawnPlace, loadMember, markedIn, sameMembers, stepped, subText } from "./seriespattern";

const p = (upload: string): SeriesPattern => ({
  upload, filename: `${upload}.xye`, label: upload, x: null, reader: "xye", reader_options: {},
  n_points: 10, two_theta_range: [5, 50], has_sigma: true,
});

const packed = (fitted: boolean) => {
  const head = new TextEncoder().encode(JSON.stringify({ fitted, arrays: [] }));
  const buffer = new ArrayBuffer(4 + head.length);
  new DataView(buffer).setUint32(0, head.length, true);
  new Uint8Array(buffer, 4).set(head);
  return buffer;
};

describe("the selected pattern", () => {
  it("draws the first pattern of the list there is, until one is chosen", () => {
    expect(drawnPlace(null, false, true, 0, 3)).toEqual({ of: "staged", index: 0 });
    expect(drawnPlace(null, true, true, 3, 3)).toEqual({ of: "run", index: 0 });
    expect(drawnPlace(null, false, true, 0, 0)).toBeNull();
  });

  it("draws a staged choice from the run's list while the lists hold the same files", () => {
    expect(drawnPlace({ of: "staged", index: 1 }, true, true, 3, 3)).toEqual({ of: "run", index: 1 });
    // after a removal the staged list is not the one the run fitted
    expect(drawnPlace({ of: "staged", index: 1 }, true, false, 3, 2)).toEqual({ of: "staged", index: 1 });
    // a choice on the run's list stays there whatever the staged list does
    expect(drawnPlace({ of: "run", index: 2 }, true, false, 3, 2)).toEqual({ of: "run", index: 2 });
    // a run that failed leaves no run's list
    expect(drawnPlace({ of: "run", index: 2 }, false, true, 0, 3)).toEqual({ of: "staged", index: 2 });
  });

  it("marks a row only on the list the place is in, or on both while they are the same", () => {
    expect(markedIn({ of: "run", index: 2 }, "staged", false)).toBeNull();
    expect(markedIn({ of: "run", index: 2 }, "staged", true)).toBe(2);
    expect(markedIn({ of: "run", index: 2 }, "run", false)).toBe(2);
  });

  it("knows two lists by their files and places, never by their coordinates", () => {
    const a = [p("a"), p("b")];
    expect(sameMembers(a, [{ ...a[0], x: 300 }, a[1]])).toBe(true);
    expect(sameMembers(a, [a[1], a[0]])).toBe(false);
    expect(sameMembers(a, [a[0]])).toBe(false);
  });

  it("steps held at the ends, and says the prototype's words", () => {
    expect([stepped(0, -1, 3), stepped(1, 1, 3), stepped(2, 1, 3)]).toEqual([0, 2, 2]);
    expect(subText(300, 4, 17, 0.04313, false)).toBe("300 · 5 of 17 · Rwp 4.31 %");
    expect(subText(null, 0, 2, null, true)).toBe("1 of 2 · fitting…");
    expect(subText(null, 0, 2, undefined, false)).toBe("1 of 2 · not fitted");
  });

  it("asks again while an expected fit has not reached the route", async () => {
    const get = vi.fn().mockResolvedValueOnce(packed(false)).mockResolvedValue(packed(true));
    await loadMember(get, true, 4, 0);
    expect(get).toHaveBeenCalledTimes(2);
    const once = vi.fn().mockResolvedValue(packed(false));
    await loadMember(once, false, 4, 0);
    expect(once).toHaveBeenCalledTimes(1);
    const never = vi.fn().mockResolvedValue(packed(false));
    await loadMember(never, true, 3, 0);
    expect(never).toHaveBeenCalledTimes(3);
  });
});
