import { describe, expect, it } from "vitest";
import { type Draft, RecoveryWriter, combine, keptParts, movedText, offerText, readDraft, restoredText } from "./recovery";

const PARAMS = { edits: { "phases.0.cell.a": "5.4312" }, vary: {}, hold: {}, limits: {},
                 restraints: {}, positions: {} };
const DRAFT: Draft = { count: 1, params: PARAMS, interactive: null, plan: null, text: null,
                       model: null };
const TEXT = { buffer: 'rxt 1\nproject "lab6"\n# my note\n', revision: "r1" };
const MODEL = { count: 2, edits: { "phases.0.cell.a": "4.2" }, params: {}, positions: {},
                vary: { "phases.0.cell.a": true }, atom: null };

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
    expect(combine(0, {})).toBeNull();
    expect(combine(1, { params: PARAMS })).toEqual(DRAFT);
  });

  it("keeps the Text buffer and the Model forms as arms of their own (WP-2213)", () => {
    // neither is counted by the action bar, so either alone is still a copy
    expect(combine(0, { text: TEXT })).toEqual({ ...DRAFT, count: 0, params: null, text: TEXT });
    expect(combine(0, { model: MODEL })?.model).toEqual(MODEL);
    const both = { ...DRAFT, text: TEXT, model: MODEL };
    expect(readDraft(JSON.parse(JSON.stringify(both)))).toEqual(both);
    // a copy written before the two arms existed reads with neither
    expect(readDraft({ count: 1, params: PARAMS, interactive: null, plan: null })).toEqual(DRAFT);
    // a Text arm restores into an editor, so a malformed one is no arm
    expect(readDraft({ count: 0, text: { buffer: 3, revision: "r1" } })).toBeNull();
    expect(readDraft({ count: 1, params: PARAMS, text: { buffer: "x" } })).toEqual(DRAFT);
  });

  it("reads back only the shape it writes", () => {
    expect(readDraft(DRAFT)).toEqual(DRAFT);
    expect(readDraft(null)).toBeNull();
    expect(readDraft("x")).toBeNull();
    expect(readDraft({ count: 3 })).toBeNull();
    expect(readDraft({ params: PARAMS })).toEqual({ ...DRAFT, count: 0 });
  });

  it("says when the project closed, then what was kept", () => {
    expect(offerText({ ...DRAFT, count: 3 }, "2026-11-10T09:05:00+00:00", "en-US"))
      .toMatch(/^Not applied when the project closed on Nov 10, 2026, \d{1,2}:05 [AP]M: 3 edits waiting at Apply\.$/);
    expect(offerText(DRAFT, null)).toBe("Not applied when the project closed: 1 edit waiting at Apply.");
    expect(offerText({ ...DRAFT, count: 0 }, "not a date"))
      .toBe("Not applied when the project closed: 1 edit waiting at Apply.");
  });

  it("names each part by where it lives, in one sentence", () => {
    const at = "2026-11-17T00:44:00+00:00";
    const one = { ...DRAFT, params: null, count: 0 };
    // one part alone, singular and plural
    expect(keptParts(DRAFT)).toBe("1 edit waiting at Apply");
    expect(keptParts({ ...DRAFT, count: 2 })).toBe("2 edits waiting at Apply");
    expect(offerText({ ...one, text: TEXT }, null))
      .toBe("Not applied when the project closed: the Text document.");
    expect(offerText({ ...one, model: { ...MODEL, count: 1 } }, null))
      .toBe("Not applied when the project closed: 1 edit in the Model forms.");
    expect(offerText({ ...one, model: MODEL }, null))
      .toBe("Not applied when the project closed: 2 edits in the Model forms.");
    // two parts join with "and" and no comma
    expect(keptParts({ ...DRAFT, count: 2, model: { ...MODEL, count: 3 } }))
      .toBe("2 edits waiting at Apply and 3 edits in the Model forms");
    expect(keptParts({ ...DRAFT, text: TEXT })).toBe("1 edit waiting at Apply and the Text document");
    expect(keptParts({ ...one, model: MODEL, text: TEXT })).toBe("2 edits in the Model forms and the Text document");
    // three parts take the serial comma
    const three = { ...DRAFT, text: TEXT, model: { ...MODEL, count: 1 } };
    expect(keptParts(three)).toBe("1 edit waiting at Apply, 1 edit in the Model forms, and the Text document");
    expect(offerText(three, at, "en-US")).toMatch(new RegExp(
      "^Not applied when the project closed on Nov 1[67], 2026, \\d{1,2}:44 [AP]M: "
      + "1 edit waiting at Apply, 1 edit in the Model forms, and the Text document\\.$"));
  });

  it("restates the offer's parts in the console line", () => {
    const three = { ...DRAFT, text: TEXT, model: { ...MODEL, count: 1 } };
    expect(restoredText(three))
      .toBe("# Restored: 1 edit waiting at Apply, 1 edit in the Model forms, and the Text document.");
    expect(restoredText({ ...DRAFT, count: 2 })).toBe("# Restored: 2 edits waiting at Apply.");
  });

  it("says what a moved project does to each arm", () => {
    const moved = "The project has been refined or edited since.";
    const values = "Restored values will replace the current ones.";
    const stale = "The Text document comes back marked out of date. Copy what you need from it, then re-read.";
    expect(movedText(DRAFT)).toBe(`${moved} ${values}`);
    expect(movedText({ ...DRAFT, params: null, count: 0, model: MODEL })).toBe(`${moved} ${values}`);
    // a Text arm alone has no values to replace
    expect(movedText({ ...DRAFT, params: null, count: 0, text: TEXT })).toBe(`${moved} ${stale}`);
    expect(movedText({ ...DRAFT, text: TEXT })).toBe(`${moved} ${values} ${stale}`);
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
