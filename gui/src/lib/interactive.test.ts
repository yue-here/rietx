import { describe, expect, it } from "vitest";

import {
  buildSliders, channelIndex, defaults, editText, fixFormat, formatParts, parseTyped,
  posFrac, PreviewQueue, STEPS, valueAt,
} from "./interactive";

const CTX = { fwhm: 0.1, thetaMaxDeg: 60 };
const OPEN: [number, number] = [-Infinity, Infinity];

function row(path: string, value: number, extra: Record<string, unknown> = {}): any {
  return { path, value, vary: false, lo: -Infinity, hi: Infinity, tie: null, locked: false,
           held: false, esd: null, mode_fixed: false, needs_held_cell: false,
           refinable: true, held_because: "", help_key: null, ...extra };
}

describe("the range a slider opens on (WP-2128)", () => {
  it("halves and doubles a scale on a logarithmic track", () => {
    expect(defaults("scale", 3, [0, Infinity], CTX)).toEqual({ lo: 1.5, hi: 6, track: "log" });
  });

  it("moves a zero shift two peak widths either way", () => {
    const r = defaults("zero", 0.01, OPEN, CTX);
    expect(r.lo).toBeCloseTo(-0.19, 12);
    expect(r.hi).toBeCloseTo(0.21, 12);
    expect(r.track).toBe("lin");
  });

  it("gives a cell length the change that moves the last peak two widths", () => {
    // Δ2θ = 2 tanθ · Δd/d, so 2 × 0.1° at θ = 60° is this share of a
    const share = (0.2 * Math.PI / 180) / (2 * Math.tan(Math.PI / 3));
    const r = defaults("cell", 10, OPEN, CTX);
    expect(r.hi / 10 - 1).toBeCloseTo(share, 12);
    expect(1 - r.lo / 10).toBeCloseTo(share, 12);
  });

  it("scales a width term by its own power of the peak width", () => {
    // U, V, W are deg², so half to double the width is a quarter to four times
    expect(defaults("gauss", 0.01, [0, Infinity], CTX)).toEqual({ lo: 0.0025, hi: 0.04, track: "log" });
    expect(defaults("lor", 0.02, [0, Infinity], CTX)).toEqual({ lo: 0.01, hi: 0.04, track: "log" });
  });

  it("opens a width term at zero on a linear track a width's worth wide", () => {
    const r = defaults("lor", 0, [0, Infinity], CTX);
    expect(r).toEqual({ lo: 0, hi: 0.1, track: "lin" });
  });

  it("stays inside the row's bounds, and turns linear where a log track would reach zero", () => {
    const r = defaults("zero", 0, [-0.05, 0.05], CTX);
    expect([r.lo, r.hi]).toEqual([-0.05, 0.05]);
    const s = defaults("scale", 0, [0, Infinity], CTX);
    expect(s.track).toBe("lin");
  });
});

describe("the number's one format", () => {
  it("is fixed by the range, so no drag inside it changes the digits' layout", () => {
    const f = fixFormat(1.5, 6, 3);
    expect(f).toEqual({ exp: null, decimals: 4 });
    // the same four decimals at both ends: nothing shifts while dragging
    expect(formatParts(f, 1.5)).toEqual({ int: "1", frac: ".5000", exp: "" });
    expect(formatParts(f, 5.99999)).toEqual({ int: "6", frac: ".0000", exp: "" });
  });

  it("goes scientific under 0.01 and from 10 000 up, at the last fit's exponent", () => {
    const f = fixFormat(0.0005, 0.008, 0.002);
    expect(f).toEqual({ exp: -3, decimals: 4 });
    expect(formatParts(f, 0.0031)).toEqual({ int: "3", frac: ".1000", exp: "−3" });
    // a range reaching 0.04 is plain, with the decimals five figures need
    expect(fixFormat(0.0025, 0.04, 0.01)).toEqual({ exp: null, decimals: 6 });
    expect(fixFormat(5e3, 2e4, 1e4).exp).toBe(4);
  });

  it("writes a negative value with a typographic minus, and never −0", () => {
    const f = { exp: null, decimals: 3 };
    expect(formatParts(f, -0.0123).int).toBe("−0");
    expect(formatParts(f, -0.00001).int).toBe("0");
  });

  it("types back without slots and refuses what the row cannot hold", () => {
    expect(editText(0.1 + 0.2)).toBe("0.3");
    expect(parseTyped({ bound: [0, 1] }, "0.25")).toEqual({ value: 0.25 });
    expect(parseTyped({ bound: [0, 1] }, "−0.5")).toEqual({ why: "below the lower bound 0" });
    expect(parseTyped({ bound: [0, 1] }, "2")).toEqual({ why: "above the upper bound 1" });
    expect(parseTyped({ bound: [0, 1] }, "x")).toEqual({ why: "not a number" });
  });
});

describe("the track", () => {
  it("maps the middle of a logarithmic track to the geometric mean", () => {
    const s = { lo: 1, hi: 4, track: "log" as const };
    expect(valueAt(s, 0.5)).toBeCloseTo(2, 12);
    expect(posFrac(s, 2)).toBeCloseTo(0.5, 12);
    // every step of the input lands back on itself
    for (const k of [0, 1, 250, 999, STEPS]) {
      expect(Math.round(posFrac(s, valueAt(s, k / STEPS)) * STEPS)).toBe(k);
    }
  });

  it("clamps a value outside the range to the ends", () => {
    const s = { lo: 0, hi: 1, track: "lin" as const };
    expect(posFrac(s, 2)).toBe(1);
    expect(posFrac(s, -1)).toBe(0);
  });
});

describe("which parameters get a slider", () => {
  it("takes refinable rows of the families, instrument first, and names each group", () => {
    const rows = [
      row("phases.0.cell.a", 9.4), row("phases.0.cell.b", 9.4, { refinable: false }),
      row("phases.0.scale", 2), row("instrument.profile.u", 0.01),
      row("phases.0.atoms.0.biso", 0.5), row("instrument.zero_shift", 0),
    ];
    const s = buildSliders(rows, null, CTX, ["fluorapatite"]);
    expect(s.map((x) => x.path)).toEqual([
      "instrument.profile.u", "instrument.zero_shift", "phases.0.scale", "phases.0.cell.a"]);
    expect(s.at(-1)?.group).toBe("fluorapatite");
    // one corpus entry covers a, b and c, so a cell slider is named by its edge
    expect(s.at(-1)?.name).toBe("Lattice parameter a");
  });

  it("keeps a range the person set across a rebuild, and rebases the rest", () => {
    const first = buildSliders([row("phases.0.scale", 2)], null, CTX);
    const mine = new Map([[first[0].path, { ...first[0], lo: 0.1, hi: 10, custom: true }]]);
    const kept = buildSliders([row("phases.0.scale", 4)], null, CTX, [], mine);
    expect([kept[0].lo, kept[0].hi, kept[0].custom]).toEqual([0.1, 10, true]);
    const rebased = buildSliders([row("phases.0.scale", 4)], null, CTX, [], new Map([[first[0].path, first[0]]]));
    expect([rebased[0].lo, rebased[0].hi]).toEqual([2, 8]);
  });
});

describe("the preview queue", () => {
  function deferred<T>() {
    let resolve!: (v: T) => void;
    const promise = new Promise<T>((r) => (resolve = r));
    return { promise, resolve };
  }

  it("keeps one request in flight and sends only the newest values next", async () => {
    const sent: Record<string, number>[] = [], landed: number[] = [];
    const replies: ReturnType<typeof deferred<number>>[] = [];
    const q = new PreviewQueue<number>(
      (v) => { sent.push(v); const d = deferred<number>(); replies.push(d); return d.promise; },
      (a) => landed.push(a), () => {}, () => 0);
    q.push({ x: 1 });
    q.push({ x: 2 });
    q.push({ x: 3 });
    expect(sent).toEqual([{ x: 1 }]);
    replies[0].resolve(1);
    await Promise.resolve(); await Promise.resolve();
    // the drag's middle value was never sent: the route sets the pace
    expect(sent).toEqual([{ x: 1 }, { x: 3 }]);
    replies[1].resolve(3);
    await Promise.resolve(); await Promise.resolve();
    expect(landed).toEqual([1, 3]);
  });

  it("drops an answer whose values were reverted while it was out", async () => {
    const landed: number[] = [];
    const d = deferred<number>();
    const q = new PreviewQueue<number>(() => d.promise, (a) => landed.push(a), () => {}, () => 0);
    q.push({ x: 1 });
    q.clear();
    d.resolve(1);
    await Promise.resolve(); await Promise.resolve();
    expect(landed).toEqual([]);
  });
});

describe("finding the preview's channels in a decimated payload", () => {
  it("matches equal 2θ and marks what the payload dropped", () => {
    const grid = [10, 10.02, 10.04, 10.06];
    expect([...channelIndex(grid, [10.02, 10.03, 10.06])]).toEqual([1, -1, 3]);
  });
});
