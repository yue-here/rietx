import { describe, expect, it } from "vitest";
import { type Draft, RecoveryWriter, combine, offerText, readDraft } from "./recovery";

const PARAMS = { edits: { "phases.0.cell.a": "5.4312" }, vary: {}, hold: {}, limits: {},
                 restraints: {}, positions: {} };
const DRAFT: Draft = { count: 1, params: PARAMS, interactive: null, plan: null };

/** Timers a test fires by hand. */
function manual() {
  const due: Array<{ fn: () => void; id: number }> = [];
  let id = 0;
  return {
    timers: {
      set: (fn: () => void) => { due.push({ fn, id: ++id }); return id; },
      clear: (h: unknown) => {
        const i = due.findIndex((d) => d.id === h);
        if (i >= 0) due.splice(i, 1);
      },
    },
    fire() { due.splice(0).forEach((d) => d.fn()); },
    get pending() { return due.length; },
  };
}

function writer() {
  const calls: Array<[string, string | null, Draft | null]> = [];
  const clock = manual();
  const w = new RecoveryWriter(async (p, h, d) => { calls.push([p, h, d]); }, 500, clock.timers);
  return { w, calls, clock };
}

describe("the draft", () => {
  it("is null when no panel holds an edit", () => {
    expect(combine(0, null, null, null)).toBeNull();
    expect(combine(1, PARAMS, null, null)).toEqual(DRAFT);
  });

  it("reads back only the shape it writes", () => {
    expect(readDraft(DRAFT)).toEqual(DRAFT);
    expect(readDraft(null)).toBeNull();
    expect(readDraft("x")).toBeNull();
    expect(readDraft({ count: 3 })).toBeNull();
    expect(readDraft({ params: PARAMS })).toEqual({ ...DRAFT, count: 0 });
  });

  it("says how many edits and when", () => {
    expect(offerText({ ...DRAFT, count: 3 }, "2026-11-10T09:05:00+00:00", "en-GB"))
      .toMatch(/^3 edits from .*2026.*, not applied when the project closed\.$/);
    expect(offerText(DRAFT, null)).toBe("1 edit not applied when the project closed.");
    expect(offerText({ ...DRAFT, count: 0 }, "not a date")).toMatch(/^1 edit not applied/);
  });
});

describe("the writer", () => {
  it("writes nothing until armed, and only for the project it is armed for", async () => {
    const { w, calls, clock } = writer();
    w.schedule("/a.rex", "n1", DRAFT);
    expect(clock.pending).toBe(0);
    w.arm("/a.rex");
    w.schedule("/b.rex", "n1", DRAFT);
    expect(clock.pending).toBe(0);
    w.schedule("/a.rex", "n1", DRAFT);
    clock.fire();
    await w.flush();
    expect(calls).toEqual([["/a.rex", "n1", DRAFT]]);
  });

  it("sends the last draft of a burst once", async () => {
    const { w, calls, clock } = writer();
    w.arm("/a.rex");
    w.schedule("/a.rex", "n1", { ...DRAFT, count: 1 });
    w.schedule("/a.rex", "n1", { ...DRAFT, count: 2 });
    expect(clock.pending).toBe(1);
    clock.fire();
    await w.flush();
    expect(calls.map((c) => c[2]?.count)).toEqual([2]);
  });

  it("does not resend what the server holds", async () => {
    const { w, calls, clock } = writer();
    w.arm("/a.rex", DRAFT);
    w.schedule("/a.rex", "n1", DRAFT);
    clock.fire();
    await w.flush();
    expect(calls).toEqual([]);
    // an empty draft deletes the copy, once
    w.schedule("/a.rex", "n1", null);
    clock.fire();
    w.schedule("/a.rex", "n1", null);
    clock.fire();
    await w.flush();
    expect(calls).toEqual([["/a.rex", "n1", null]]);
  });

  it("flushes a scheduled write at once, and disarming drops it", async () => {
    const { w, calls } = writer();
    w.arm("/a.rex");
    w.schedule("/a.rex", "n1", DRAFT);
    expect(w.unsent()).toEqual({ project: "/a.rex", head: "n1", draft: DRAFT });
    await w.flush();
    expect(calls).toHaveLength(1);
    expect(w.unsent()).toBeNull();
    w.schedule("/a.rex", "n1", null);
    w.disarm();
    await w.flush();
    expect(calls).toHaveLength(1);
    expect(w.armedFor).toBeNull();
  });

  it("hands a closing page its unsent write once", async () => {
    const { w, calls } = writer();
    w.arm("/a.rex");
    w.schedule("/a.rex", "n1", DRAFT);
    expect(w.takeUnsent()).toEqual({ project: "/a.rex", head: "n1", draft: DRAFT });
    expect(w.takeUnsent()).toBeNull();
    // the page came back from the back-forward cache: nothing is sent again
    await w.flush();
    expect(calls).toEqual([]);
  });

  it("follows a renamed project", async () => {
    const { w, calls, clock } = writer();
    w.arm("/a.rex");
    w.follow("/b.rex");
    w.schedule("/b.rex", "n1", DRAFT);
    clock.fire();
    await w.flush();
    expect(calls[0][0]).toBe("/b.rex");
  });

  it("tries again after a refused write", async () => {
    const clock = manual();
    let refuse = true;
    const calls: number[] = [];
    const w = new RecoveryWriter(async (_p, _h, d) => {
      calls.push(d?.count ?? 0);
      if (refuse) throw new Error("refused");
    }, 500, clock.timers);
    w.arm("/a.rex");
    w.schedule("/a.rex", null, DRAFT);
    await w.flush();
    refuse = false;
    w.schedule("/a.rex", null, DRAFT);
    await w.flush();
    expect(calls).toEqual([1, 1]);
  });
});
