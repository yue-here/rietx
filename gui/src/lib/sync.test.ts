/**
 * The text pane's state machine, as transitions rather than as a rendered pane.
 *
 * The v1.0 GUI plan lists two-way text sync as its top correctness risk, and the
 * mitigations were decided before any code existed — one server-side parser, CAS
 * revisions, explicit apply, all-or-nothing deltas.  So what is worth testing is
 * not whether those are good ideas but whether the machine actually implements
 * them: that a render arriving mid-edit cannot delete the edit, that a stale
 * buffer has exactly one exit, and that a response belonging to an older buffer
 * is dropped rather than painted at line numbers that have moved.
 */
import { describe, expect, it } from "vitest";

import {
  STALE_NOTICE,
  canApply,
  initial,
  minimalChange,
  reduce,
  type SyncEvent,
  type SyncState,
} from "./sync";

const DOC = 'rxt 1\nproject "lab6"\nmode rietveld\n';
const MOVED = 'rxt 1\nproject "lab6"\nmode lebail\n';

/** Fold a script of events, so a test reads as the sequence it is about. */
function run(events: SyncEvent[], from: SyncState = initial()): SyncState {
  return events.reduce(reduce, from);
}

const loaded = () => run([{ kind: "rendered", text: DOC, revision: "r1" }]);

describe("loading and editing", () => {
  it("adopts the first render and calls it clean", () => {
    const state = loaded();
    expect(state.phase).toBe("clean");
    expect(state.buffer).toBe(DOC);
    expect(state.base).toBe(DOC);
    expect(state.revision).toBe("r1");
    expect(canApply(state)).toBe(false);
  });

  it("goes dirty on an edit and clean again when it is typed back", () => {
    const dirty = run([{ kind: "edited", text: DOC + "limits 3 60\n" }], loaded());
    expect(dirty.phase).toBe("dirty");
    expect(canApply(dirty)).toBe(true);

    // typing the edit back out is not a change — the base is the comparison,
    // which is `textdoc.changes`' rule one level up
    const back = run([{ kind: "edited", text: DOC }], dirty);
    expect(back.phase).toBe("clean");
    expect(canApply(back)).toBe(false);
  });

  it("validates, and stops offering Apply when the delta is empty", () => {
    const dirty = run([{ kind: "edited", text: DOC + "\n" }], loaded());
    const checked = run(
      [{ kind: "checking", seq: dirty.seq },
       { kind: "checked", seq: dirty.seq, wouldChange: false }], dirty);
    expect(checked.phase).toBe("valid");
    // an untouched document emitting no verbs is WP-1009's own property, so the
    // button says so rather than posting a no-op
    expect(canApply(checked)).toBe(false);

    const real = run([{ kind: "checked", seq: dirty.seq, wouldChange: true }], dirty);
    expect(canApply(real)).toBe(true);
  });
});

describe("a model change arriving underneath", () => {
  it("adopts it while the buffer is clean", () => {
    const state = run([{ kind: "rendered", text: MOVED, revision: "r2" }], loaded());
    expect(state.phase).toBe("clean");
    expect(state.buffer).toBe(MOVED);
    expect(state.revision).toBe("r2");
    expect(state.stale).toBe(false);
  });

  it("never overwrites a dirty buffer — it goes stale instead", () => {
    const mine = DOC + "limits 3 60\n";
    const state = run([{ kind: "edited", text: mine },
                       { kind: "rendered", text: MOVED, revision: "r2" }], loaded());
    expect(state.buffer).toBe(mine);        // the edit survives, which is the point
    expect(state.revision).toBe("r1");      // …and still descends from r1
    expect(state.stale).toBe(true);
    expect(state.notice).toBe(STALE_NOTICE);
    expect(canApply(state)).toBe(false);    // applying would 409 anyway
  });

  it("stays stale across further typing, and only a re-read clears it", () => {
    const stale = run([{ kind: "edited", text: DOC + "x\n" },
                       { kind: "rendered", text: MOVED, revision: "r2" }], loaded());
    const typing = run([{ kind: "edited", text: DOC + "xy\n" }], stale);
    expect(typing.stale).toBe(true);

    const reread = run([{ kind: "rendered", text: MOVED, revision: "r2", force: true }],
                       typing);
    expect(reread.stale).toBe(false);
    expect(reread.phase).toBe("clean");
    expect(reread.buffer).toBe(MOVED);
  });

  it("does not cry stale when the head moved but the document did not", () => {
    // a `set_vary` that freed nothing, a tag, an annotation: the head is the
    // reload signal precisely because it covers writers that change no text
    const dirty = run([{ kind: "edited", text: DOC + "x\n" }], loaded());
    const same = run([{ kind: "rendered", text: DOC, revision: "r1" }], dirty);
    expect(same).toBe(dirty);               // literally untouched
    expect(same.stale).toBe(false);
  });

  it("adopts a render the user had typed their way to", () => {
    const dirty = run([{ kind: "edited", text: MOVED }], loaded());
    const state = run([{ kind: "rendered", text: MOVED, revision: "r2" }], dirty);
    expect(state.phase).toBe("clean");
    expect(state.stale).toBe(false);
  });
});

describe("the server's refusals", () => {
  it("treats a 409 STALE_REVISION as the same conflict a render would have caused", () => {
    const dirty = run([{ kind: "edited", text: DOC + "x\n" }], loaded());
    const state = run([{ kind: "refused", code: "STALE_REVISION",
                         message: "the project changed since this text was rendered" }],
                      dirty);
    expect(state.stale).toBe(true);
    expect(state.buffer).toBe(dirty.buffer);   // nothing was applied, nothing lost
    expect(canApply(state)).toBe(false);
  });

  it("carries the parse problems and applies none of the document", () => {
    const dirty = run([{ kind: "edited", text: DOC + "mode nonsense\n" }], loaded());
    const state = run([{ kind: "refused", code: "TEXTDOC_INVALID",
                         message: "1 problem(s) in the document; nothing was applied",
                         problems: [{ line: 4, message: "unknown mode", where: "mode" }] }],
                      dirty);
    expect(state.phase).toBe("invalid");
    expect(state.problems).toEqual([{ line: 4, message: "unknown mode", where: "mode" }]);
    expect(state.buffer).toBe(dirty.buffer);
  });

  it("says a run is in flight without calling the text invalid", () => {
    // the state refusal outranks a parse complaint (WP-1008), so a 409 here must
    // not paint squiggles: the document was never even looked at
    const dirty = run([{ kind: "edited", text: DOC + "x\n" }], loaded());
    const state = run([{ kind: "refused", code: "RUN_IN_FLIGHT",
                         message: "a run is in flight" }], dirty);
    expect(state.phase).toBe("dirty");
    expect(state.problems).toEqual([]);
    expect(state.notice).toBe("a run is in flight");
    expect(state.stale).toBe(false);
  });

  it("clears stale problems the moment the text moves", () => {
    const invalid = run([{ kind: "edited", text: DOC + "bad\n" },
                         { kind: "refused", code: "TEXTDOC_INVALID", message: "…",
                           problems: [{ line: 4, message: "unknown keyword" }] }], loaded());
    expect(invalid.problems).toHaveLength(1);
    const typing = run([{ kind: "edited", text: DOC + "ba\n" }], invalid);
    // the line numbers describe text that no longer exists
    expect(typing.problems).toEqual([]);
  });
});

describe("out-of-order responses", () => {
  it("drops a validation belonging to an older buffer", () => {
    // 300 ms debounce, two requests across one pause, and no ordering guarantee:
    // the slow first answer must not overwrite the fast second one
    const first = run([{ kind: "edited", text: DOC + "a\n" }], loaded());
    const second = run([{ kind: "edited", text: DOC + "ab\n" }], first);
    const late = run([{ kind: "checked", seq: first.seq, wouldChange: true }], second);
    expect(late).toBe(second);
    expect(late.phase).toBe("dirty");
  });

  it("drops a refusal belonging to an older buffer", () => {
    const first = run([{ kind: "edited", text: DOC + "a\n" }], loaded());
    const second = run([{ kind: "edited", text: DOC + "ab\n" }], first);
    const late = run([{ kind: "refused", seq: first.seq, code: "TEXTDOC_INVALID",
                        message: "…", problems: [{ line: 4, message: "boom" }] }], second);
    expect(late.problems).toEqual([]);
  });

  it("accepts a refusal with no sequence — an apply is never speculative", () => {
    const dirty = run([{ kind: "edited", text: DOC + "a\n" }], loaded());
    const state = run([{ kind: "applying" },
                       { kind: "refused", code: "TEXTDOC_INVALID", message: "…",
                         problems: [{ line: 2, message: "boom" }] }], dirty);
    expect(state.phase).toBe("invalid");
  });
});

describe("apply", () => {
  it("adopts the re-render the PUT hands back, without a second round trip", () => {
    // canonical output normalises a glob line away, so the buffer *must* be
    // replaced rather than patched — and the response already carries the text
    const dirty = run([{ kind: "edited", text: DOC + "profile.* @\n" }], loaded());
    const state = run([{ kind: "applying" },
                       { kind: "applied", text: MOVED, revision: "r2",
                         verbs: ['ref.set_vary("instrument.profile.*", True)'] }], dirty);
    expect(state.phase).toBe("clean");
    expect(state.buffer).toBe(MOVED);
    expect(state.revision).toBe("r2");
    expect(state.notice).toBe("applied 1 change(s)");
    expect(canApply(state)).toBe(false);
  });

  it("re-applies cleanly after a conflict was resolved by re-reading", () => {
    const stale = run([{ kind: "edited", text: DOC + "x\n" },
                       { kind: "rendered", text: MOVED, revision: "r2" }], loaded());
    const reread = run([{ kind: "rendered", text: MOVED, revision: "r2", force: true }], stale);
    const again = run([{ kind: "edited", text: MOVED + "limits 3 60\n" }], reread);
    expect(again.revision).toBe("r2");     // the PUT now sends the current token
    expect(canApply(again)).toBe(true);
  });

  it("is never offered while a run is in flight", () => {
    const dirty = run([{ kind: "edited", text: DOC + "x\n" }], loaded());
    expect(canApply(dirty, true)).toBe(false);
  });
});

describe("minimalChange", () => {
  it("is null when nothing moved", () => {
    expect(minimalChange(DOC, DOC)).toBeNull();
  });

  it("splices only the run that differs", () => {
    const change = minimalChange("abc def ghi", "abc XYZ ghi")!;
    expect(change).toEqual({ from: 4, to: 7, insert: "XYZ" });
  });

  it("handles pure insertion and pure deletion without overlapping", () => {
    expect(minimalChange("ab", "aXb")).toEqual({ from: 1, to: 1, insert: "X" });
    expect(minimalChange("aXb", "ab")).toEqual({ from: 1, to: 2, insert: "" });
    // repeated characters are where a naive prefix/suffix trim overlaps
    expect(minimalChange("aaa", "aa")).toEqual({ from: 2, to: 3, insert: "" });
    expect(minimalChange("aa", "aaa")).toEqual({ from: 2, to: 2, insert: "a" });
  });

  it("round-trips: applying the splice reproduces the target", () => {
    const pairs: Array<[string, string]> = [
      [DOC, MOVED],
      [DOC, ""],
      ["", DOC],
      [DOC, DOC.replace("rietveld", "pawley")],
      ["  cell.a        @ 4.1606", "  cell.a          4.1606"],
    ];
    for (const [before, after] of pairs) {
      const change = minimalChange(before, after);
      const applied = change === null
        ? before
        : before.slice(0, change.from) + change.insert + before.slice(change.to);
      expect(applied).toBe(after);
    }
  });
});

describe("a buffer restored from the recovery copy (WP-2213)", () => {
  const typed = DOC + "# my note\nlimits 3 60\n";

  it("comes back dirty over the rendering it was typed against", () => {
    const state = run([{ kind: "restored", text: DOC, revision: "r1", buffer: typed, kept: "r1" }]);
    expect(state.phase).toBe("dirty");
    expect(state.stale).toBe(false);
    expect(state.buffer).toBe(typed);
    expect(state.base).toBe(DOC);
    expect(canApply(state)).toBe(true);
    // the pane re-reading on its next head move adopts nothing over it
    expect(run([{ kind: "rendered", text: DOC, revision: "r1" }], state)).toEqual(state);
  });

  it("comes back stale when the project has moved since, with re-read the one exit", () => {
    const state = run([{ kind: "restored", text: MOVED, revision: "r2", buffer: typed, kept: "r1" }]);
    expect(state.stale).toBe(true);
    expect(state.notice).toBe(STALE_NOTICE);
    expect(state.buffer).toBe(typed);
    expect(canApply(state)).toBe(false);
    // kept again, it still names the revision it was typed against
    expect(state.revision).toBe("r1");
    expect(run([{ kind: "rendered", text: MOVED, revision: "r2" }], state).stale).toBe(true);
    const reread = run([{ kind: "rendered", text: MOVED, revision: "r2", force: true }], state);
    expect(reread.phase).toBe("clean");
    expect(reread.buffer).toBe(MOVED);
  });

  it("is a clean pane when the kept buffer reads like the rendering", () => {
    const state = run([{ kind: "restored", text: DOC, revision: "r2", buffer: DOC, kept: "r1" }]);
    expect(state.phase).toBe("clean");
    expect(state.stale).toBe(false);
  });
});
