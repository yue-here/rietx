/** The text pane's state machine — framework-free, so it can be asserted.
 *
 * The server session is the single source of truth and the pane is a dirty
 * buffer over one of its renderings. Four rules, all of them WP-1009's rather
 * than this pane's:
 *
 * **A render never clobbers an edit.** `GET /api/textdoc` is re-read whenever the
 * head moves — a run, a checkout, a form edit, an applied suggestion — and if the
 * buffer is dirty the new rendering is *not* adopted: the pane goes
 * {@link SyncState.stale} and says so. Adopting would delete work the user can
 * see on screen.
 *
 * **There is no merge.** The document is regenerated from state, so a three-way
 * merge would be merging two renderings of one authority. A stale pane offers
 * exactly one resolution — re-read and re-apply — and that is also what the
 * server's `STALE_REVISION` 409 means, so the two paths land in the same place.
 *
 * **Only the server decides validity.** Every {@link SyncState.problems} entry
 * arrives from a `PUT` response; nothing here inspects the text. `lib/rxt.ts`
 * colours it and has no `error` token to emit.
 *
 * **A response from an older buffer is dropped.** Validation is debounced, so
 * two requests can be in flight across one pause in typing and they can land out
 * of order. Every edit bumps {@link SyncState.seq}; a response carrying an older
 * one is ignored rather than painting squiggles at line numbers that have moved.
 */

/** One server-reported problem, addressed the way an editor gutter needs it. */
export interface Problem {
  /** 1-based, as `textdoc.TextError` guarantees */
  line: number;
  message: string;
  where?: string;
  text?: string;
}

export type Phase = "clean" | "dirty" | "checking" | "valid" | "invalid" | "applying";

export interface SyncState {
  phase: Phase;
  /** the server rendering the buffer descends from */
  base: string;
  /** its CAS token — what a `PUT` sends as `base_revision` */
  revision: string;
  /** what the editor is showing; equal to `base` exactly when nothing was typed */
  buffer: string;
  /** from the last `PUT`; never derived here */
  problems: Problem[];
  /** the last validation said applying would emit at least one verb */
  wouldChange: boolean;
  /** the project moved underneath this buffer — the only fix is to re-read */
  stale: boolean;
  /** a sentence for the banner: a refusal, or what an apply just did */
  notice: string;
  /** the buffer's generation; a response from an older one is dropped */
  seq: number;
}

export type SyncEvent =
  /** `GET /api/textdoc` came back. `force` is the user asking for the server's
   *  copy, which is the one thing that may discard an edit. */
  | { kind: "rendered"; text: string; revision: string; force?: boolean }
  | { kind: "edited"; text: string }
  | { kind: "checking"; seq: number }
  | { kind: "checked"; seq: number; wouldChange: boolean }
  | { kind: "applying" }
  | { kind: "applied"; text: string; revision: string; verbs: string[] }
  | { kind: "refused"; seq?: number; code: string; message: string; problems?: Problem[] }
  /** A buffer kept in the recovery copy (WP-2213) comes back over a fresh
   *  rendering. `kept` is the revision it was typed against. */
  | { kind: "restored"; text: string; revision: string; buffer: string; kept: string };

export const STALE_NOTICE =
  "the project changed underneath this text — re-read it and re-apply your edit";

export function initial(): SyncState {
  return { phase: "clean", base: "", revision: "", buffer: "", problems: [],
           wouldChange: false, stale: false, notice: "", seq: 0 };
}

/** Adopt a server rendering wholesale: the buffer *is* the render again. */
function adopt(state: SyncState, text: string, revision: string,
               notice: string): SyncState {
  return { ...state, phase: "clean", base: text, revision, buffer: text,
           problems: [], wouldChange: false, stale: false, notice,
           seq: state.seq + 1 };
}

export function reduce(state: SyncState, event: SyncEvent): SyncState {
  switch (event.kind) {
    case "rendered": {
      // adoptable when the user has nothing to lose: an untouched buffer, a
      // buffer that already reads exactly like the new render, or an explicit
      // "give me the server's copy"
      if (event.force || state.phase === "clean" || event.text === state.buffer) {
        return adopt(state, event.text, event.revision, "");
      }
      // the same document we already descend from: a head moved for a reason
      // that changed no text, so there is nothing to be stale about
      if (event.revision === state.revision) return state;
      return { ...state, stale: true, notice: STALE_NOTICE };
    }

    case "edited": {
      const phase: Phase = event.text === state.base ? "clean" : "dirty";
      // problems are cleared rather than kept: their line numbers describe text
      // that no longer exists, and a squiggle in the wrong place is worse than none
      return { ...state, buffer: event.text, phase, problems: [],
               wouldChange: false, seq: state.seq + 1 };
    }

    case "checking":
      if (event.seq !== state.seq) return state;
      return { ...state, phase: "checking" };

    case "checked":
      if (event.seq !== state.seq) return state;
      return { ...state, phase: "valid", problems: [],
               wouldChange: event.wouldChange };

    case "applying":
      return { ...state, phase: "applying", notice: "" };

    case "applied":
      return adopt(state, event.text, event.revision,
                   event.verbs.length
                     ? `applied ${event.verbs.length} change(s)`
                     : "nothing to apply");

    case "restored": {
      const fresh = adopt(state, event.text, event.revision, "");
      if (event.buffer === event.text) return fresh;
      // typed against this very rendering: a dirty buffer, as it was left
      if (event.kept === event.revision) return { ...fresh, phase: "dirty", buffer: event.buffer };
      // typed against another one, and there is no merge: the buffer comes back
      // stale, on screen to copy from, with re-read the one way out.  It keeps
      // the revision it was typed against, so kept again it is stale again.
      return { ...fresh, phase: "dirty", buffer: event.buffer, revision: event.kept,
               stale: true, notice: STALE_NOTICE };
    }

    case "refused": {
      if (event.seq !== undefined && event.seq !== state.seq) return state;
      // a settled phase to fall back to when the refusal was not about the text
      const settled: Phase = state.buffer === state.base ? "clean" : "dirty";
      if (event.code === "STALE_REVISION") {
        return { ...state, phase: settled, stale: true, notice: STALE_NOTICE };
      }
      if (event.code === "TEXTDOC_INVALID") {
        return { ...state, phase: "invalid", problems: event.problems ?? [],
                 notice: event.problems?.length ? "" : event.message };
      }
      // RUN_IN_FLIGHT and everything else: the buffer is untouched and the
      // server's own words are the useful answer (the state refusal outranks a
      // parse complaint, so there is nothing to squiggle)
      return { ...state, phase: settled, notice: event.message };
    }
  }
}

/** Whether Apply would do anything, and so whether its button is live.
 *
 * Enabled while still `dirty` — before the debounce has fired — because the
 * server validates the document it is handed anyway, and a Cmd-Enter that does
 * nothing for 300 ms reads as a dropped keystroke. Disabled once validation has
 * come back saying the document emits no verbs: an untouched document applying
 * nothing is WP-1009's own property, not a failure.
 */
export function canApply(state: SyncState, busy = false): boolean {
  if (busy || state.stale) return false;
  if (state.phase === "valid") return state.wouldChange;
  return state.phase === "dirty" || state.phase === "checking";
}

export interface DocChange {
  from: number;
  to: number;
  insert: string;
}

/**
 * The smallest single splice turning `before` into `after`, or null if equal.
 *
 * Replacing the whole document would work and would also throw away the cursor,
 * the selection and the scroll position on every re-render — and the pane
 * re-renders whenever anything else in the app moves the head. Trimming the
 * common prefix and suffix leaves a change CodeMirror can map a selection
 * through, which is the difference between a pane you can leave open and one
 * that jumps.
 */
export function minimalChange(before: string, after: string): DocChange | null {
  if (before === after) return null;
  const shortest = Math.min(before.length, after.length);
  let start = 0;
  while (start < shortest && before[start] === after[start]) start += 1;
  let endBefore = before.length;
  let endAfter = after.length;
  while (endBefore > start && endAfter > start
         && before[endBefore - 1] === after[endAfter - 1]) {
    endBefore -= 1;
    endAfter -= 1;
  }
  return { from: start, to: endBefore, insert: after.slice(start, endAfter) };
}
