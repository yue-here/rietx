<script lang="ts">
  /**
   * The Text tab at /next (WP-2231, rows 139-146): the project as `.rxt` text.
   *
   * Moved from `panels/Text.svelte` (WP-1013) and changed in four ways. A
   * typed change is one pending edit in the window's action bar, applied by
   * its Apply or by ⌘⏎, so the tab has no Apply of its own. Re-read appears
   * only inside the stale notice, the one state it serves. A line the
   * rendering does not have is marked, as the prototype marks an edited
   * value. The footer's prose is gone (the 2026-11-10 ruling on chrome text).
   *
   * **The head is the reload signal**, as today: the head moves for every
   * writer, so this re-reads `GET /api/textdoc` on `head`, and `lib/sync.ts`
   * decides whether the answer may be adopted or only makes the buffer stale.
   * This component owns the debounce timer, the fetches and the DOM, and holds
   * no rule of its own.
   */
  import { untrack } from "svelte";
  import { ApiError, api } from "../api";
  import { commentLines } from "../lib/rxt";
  import { canApply, editedLines, initial, reduce, type Problem,
           type SyncEvent } from "../lib/sync";
  import type { TextDraft } from "../lib/recovery";
  import { PreviewQueue, type PreviewAnswer } from "../lib/interactive";
  import type { Curves } from "rxplot";
  // types only: the boot chunk still has no CodeMirror
  import type { EditorHandle, createEditor } from "../lib/editor";

  let {
    head = null,
    busy = false,
    active = false,
    dark = false,
    name = "project",
    say = (_line: string) => {},
    onmoved = () => {},
    onpending = (_edited: boolean, _why: string) => {},
    onapply = () => {},
    onpreview = (_answer: PreviewAnswer | null, _error: string) => {},
  }: {
    head?: string | null;
    busy?: boolean;
    active?: boolean;
    /** the resolved theme: CodeMirror's chrome needs the flag, not the colours */
    dark?: boolean;
    /** the project's name, which titles the file */
    name?: string;
    say?: (line: string) => void;
    onmoved?: () => void;
    /** whether the buffer differs from the rendering, and why it cannot be
     *  applied when it cannot ("" when it can) */
    onpending?: (edited: boolean, why: string) => void;
    /** ⌘⏎ in the editor: the bar's Apply */
    onapply?: () => void;
    /** the pattern at the typed values, or null to take it down */
    onpreview?: (answer: PreviewAnswer | null, error: string) => void;
  } = $props();

  /** Long enough that a burst of typing is one request, short enough that a
   *  pause feels answered (WP-1013). */
  const DEBOUNCE_MS = 300;

  let sync = $state(initial());
  let host = $state<HTMLDivElement | null>(null);
  let editor = $state<EditorHandle | null>(null);
  /** the editor chunk did not load */
  let bootError = $state("");
  /** the last read of the rendering failed; cleared by the next one that succeeds */
  let readError = $state("");
  let timer: ReturnType<typeof setTimeout> | null = null;
  /** the document has never been fetched, so the empty buffer is not "clean" */
  let loaded = $state(false);
  /** bumped by `forget`, so a read begun for the project left is dropped */
  let generation = 0;

  // -- the preview -----------------------------------------------------------
  // A typed number previews on the plot as a slider move does (the
  // maintainer's look, 2026-11-21, item 8, reversing WP-2231 § Settled 12).
  // The server's validation already diffs the buffer against the project, so
  // its `delta.values` are the typed values, and `POST /api/preview` draws
  // them, through one `PreviewQueue` as the Interactive tab's. A refine flag,
  // a setting or a peak move changes no curve, so a buffer of only those
  // previews nothing.

  /** Whether this tab has a preview (or a refusal) up, so taking it down is
   *  said once and never clears another panel's. */
  let previewUp = false;
  /** The values last sent, so a check that changes none of them (a comment,
   *  a refine flag) asks the server for no second identical pattern. */
  let previewKey = "";
  const queue = new PreviewQueue<Curves>(
    async (values) => {
      const [answer, chart] = await Promise.all([api.preview(values), import("rxplot")]);
      return chart.unpack(answer);
    },
    (curves, _values, sentAt) => {
      previewUp = true;
      onpreview({ curves, sentAt }, "");
    },
    (exc) => {
      previewUp = true;
      onpreview(null, (exc as Error).message);
    },
  );

  function dropPreview() {
    queue.clear();
    previewKey = "";
    if (!previewUp) return;
    previewUp = false;
    onpreview(null, "");
  }

  const problems = $derived(sync.problems);
  // primitives, so the line diff below reruns only when a text changes and
  // not on every dispatch (checking, checked) that leaves both alone
  const base = $derived(sync.base);
  const buffer = $derived(sync.buffer);
  /** The stale notice's words (the maintainer's look, 2026-11-21: today's
   *  `STALE_NOTICE` read unclearly). Re-read beside it discards the edit. */
  const STALE_CAUSE = "The project changed after this text was read.";
  const STALE_WORDS = `${STALE_CAUSE} Re-read it, then make your edit again.`;
  /** A comment does not survive a re-render (WP-1009), so say so before Apply
   *  replaces the buffer. */
  const addedComments = $derived(
    Math.max(0, commentLines(buffer) - commentLines(base)));
  const edited = $derived(loaded && buffer !== base);
  const editedMarks = $derived(edited ? editedLines(base, buffer) : []);
  const why = $derived(!edited ? ""
    : sync.stale ? `${STALE_CAUSE} Re-read it in the Text tab.`
    : sync.phase === "invalid"
      ? (problems.length
        ? `The text has ${problems.length} problem${problems.length === 1 ? "" : "s"}.`
        : sync.notice || "The text was not read.")
      : "");

  // nothing typed, a buffer the server cannot read, or one typed against an
  // older project: no preview stands for it
  $effect(() => {
    if (!edited || sync.stale || sync.phase === "invalid") untrack(dropPreview);
  });

  $effect(() => {
    onpending(edited, why);
  });

  function dispatch(event: SyncEvent) {
    sync = reduce(sync, event);
  }

  /** Read the rendering. A kept buffer waiting in `restoring` goes back over
   *  it instead, once a read has succeeded (WP-2213). */
  async function load(force = false) {
    const kept = restoring;
    const at = generation;
    try {
      const payload = await api.textdoc();
      if (at !== generation) return;
      if (kept && restoring !== kept) return;
      if (kept && !force) {
        dispatch({ kind: "restored", text: payload.text, revision: payload.revision,
                   buffer: kept.buffer, kept: kept.revision });
        restoring = null;
        if (sync.phase === "dirty" && !sync.stale && !busy) {
          if (timer) clearTimeout(timer);
          timer = setTimeout(check, DEBOUNCE_MS);
        }
      } else {
        dispatch({ kind: "rendered", text: payload.text, revision: payload.revision, force });
        if (force) restoring = null;
      }
      loaded = true;
      readError = "";
    } catch (error) {
      if (at !== generation) return;
      if (error instanceof ApiError && error.empty) return;
      readError = (error as Error).message;
    }
  }

  /** The buffer for the recovery copy, as typed, with the revision it descends
   *  from; `null` while it matches the rendering. */
  let restoring = $state.raw<TextDraft | null>(null);
  export function draft(): TextDraft | null {
    if (restoring) return restoring;
    if (!edited) return null;
    return { buffer: sync.buffer, revision: sync.revision };
  }

  /** Put a kept buffer back over a fresh rendering: dirty against the same
   *  rendering, stale when the project has moved since. */
  export async function restoreDraft(kept: TextDraft) {
    restoring = kept;
    await load();
  }

  /** Drop the buffer and read the rendering again: the bar's Revert, and
   *  Re-read in the stale notice. */
  export async function revert() {
    if (timer) clearTimeout(timer);
    restoring = null;
    if (!loaded) return;
    await load(true);
  }

  /** The open project changed: drop this buffer and read the next one afresh. */
  export function forget() {
    if (timer) clearTimeout(timer);
    dropPreview();
    generation += 1;
    restoring = null;
    sync = initial();
    loaded = false;
    bootError = "";
    readError = "";
  }

  function typed(text: string) {
    dispatch({ kind: "edited", text });
    if (timer) clearTimeout(timer);
    if (busy || sync.stale) return;
    timer = setTimeout(check, DEBOUNCE_MS);
  }

  async function check() {
    const seq = sync.seq;
    const text = sync.buffer;
    dispatch({ kind: "checking", seq });
    try {
      const payload = await api.putTextdoc(text, sync.revision, true);
      dispatch({ kind: "checked", seq, wouldChange: Boolean(payload.would_change) });
      // a newer keystroke has its own check coming, which previews its values
      if (seq !== sync.seq) return;
      const values = (payload.delta?.values ?? {}) as Record<string, number>;
      if (!Object.keys(values).length) dropPreview();
      else {
        const key = JSON.stringify(Object.entries(values).sort(([a], [b]) => (a < b ? -1 : 1)));
        if (key !== previewKey) {
          previewKey = key;
          queue.push(values);
        }
      }
    } catch (error) {
      absorb(error, seq);
    }
  }

  /** Apply the buffer as one delta, for the bar's Apply. True when nothing
   *  was waiting or the buffer applied; false when it was refused, and the
   *  tab then says why. */
  export async function apply(): Promise<boolean> {
    if (!edited) return true;
    // the server read the buffer and it changes nothing, such as a comment
    // added: applying it is reading the rendering again
    if (sync.phase === "valid" && !sync.wouldChange && !sync.stale && !busy) {
      await revert();
      return true;
    }
    if (!canApply(sync, busy)) return false;
    if (timer) clearTimeout(timer);
    const text = sync.buffer;
    dispatch({ kind: "applying" });
    try {
      const payload = await api.putTextdoc(text, sync.revision, false);
      const verbs: string[] = payload.applied ?? [];
      for (const call of verbs) say(call);
      dispatch({ kind: "applied", text: payload.text, revision: payload.revision, verbs });
      if (verbs.length) onmoved();
      return true;
    } catch (error) {
      absorb(error);
      return false;
    }
  }

  /** Turn an `ApiError` into the one event `lib/sync.ts` understands. */
  function absorb(error: unknown, seq?: number) {
    if (!(error instanceof ApiError)) {
      dispatch({ kind: "refused", seq, code: "HTTP_ERROR", message: (error as Error).message });
      return;
    }
    dispatch({ kind: "refused", seq, code: error.code, message: error.message,
               problems: error.details.filter((d) => d.line !== undefined) as Problem[] });
  }

  // The editor's document, squiggles and chrome are derived from `sync` and the
  // theme, never pushed (WP-1013).
  $effect(() => {
    editor?.setDoc(buffer);
  });
  $effect(() => {
    editor?.setProblems(sync.problems);
  });
  $effect(() => {
    editor?.setTheme(dark);
  });
  $effect(() => {
    editor?.setEdited(editedMarks);
  });

  // re-read when the working state moved, once the tab has been opened
  $effect(() => {
    void head;
    if (active) load();
  });

  // build the editor on first entry, and re-measure on every later one
  $effect(() => {
    if (!active || !host) return;
    if (editor) {
      editor.refresh();
      return;
    }
    void mountEditor(host);
  });

  let mounting = false;

  async function mountEditor(parent: HTMLElement) {
    if (mounting) return;
    mounting = true;
    try {
      const module: { createEditor: typeof createEditor } = await import("../lib/editor");
      editor = module.createEditor({ parent, doc: sync.buffer, onChange: typed,
                                     onApply: () => onapply(), dark });
    } catch (error) {
      mounting = false;
      bootError = `The editor did not load: ${(error as Error).message}`;
    }
  }

  $effect(() => () => {
    if (timer) clearTimeout(timer);
    editor?.destroy();
  });

  /** The sync word on the title line. */
  const status = $derived(
    !loaded ? "loading…"
    : sync.stale ? "stale"
    : sync.phase === "clean" ? "in sync"
    : sync.phase === "dirty" ? "edited"
    : sync.phase === "checking" ? "checking…"
    : sync.phase === "invalid"
      ? (problems.length ? `${problems.length} line${problems.length === 1 ? "" : "s"} not read`
        : "not read")
    : sync.phase === "applying" ? "applying…"
    : sync.wouldChange ? "edited" : "no change");
</script>

<section class="text" aria-label="text">
  <div class="bar">
    <span class="file">{name}.rxt</span>
    <span class="sync" data-phase={sync.stale ? "stale" : sync.phase} role="status">{status}</span>
  </div>

  {#if sync.stale}
    <div class="notice bad stale">
      <p>{STALE_WORDS}</p>
      <button class="ghost" onclick={() => revert()}
        title="Read the project's text again, discarding your edit">Re-read</button>
    </div>
  {:else if sync.notice}
    <p class="notice">{sync.notice}</p>
  {/if}
  {#if bootError || readError}
    <p class="notice bad">{bootError || readError}</p>
  {/if}
  {#if addedComments > 0}
    <p class="notice">{addedComments} comment line{addedComments === 1 ? "" : "s"} you added will not survive Apply.</p>
  {/if}

  <div class="editor" bind:this={host}></div>

  {#if problems.length}
    <ul class="problems" aria-label="Problems">
      {#each problems as problem}
        <li>
          <button class="link mono" onclick={() => editor?.goToLine(problem.line)}
            >line {problem.line}</button>
          {#if problem.where}<span class="mono muted">{problem.where}</span>{/if}
          {problem.message}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .text {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }

  .bar {
    display: flex;
    align-items: center;
    gap: 8px;
    flex: none;
    height: 40px;
    box-sizing: border-box;
    padding: 0 12px;
    border-bottom: 1px solid var(--line);
    font-size: var(--text-sm);
    color: var(--muted);
  }

  .sync {
    margin-left: auto;
  }

  .sync[data-phase="stale"] {
    color: var(--warn);
  }

  .sync[data-phase="invalid"] {
    color: var(--bad);
  }

  .notice {
    flex: none;
    margin: 0;
    padding: 6px 12px;
    border-bottom: 1px solid var(--line);
    font-size: var(--text-sm);
  }

  .notice.bad {
    color: var(--bad);
  }

  /* Words and the Re-read button on one row, the button kept clear of the
     words and never wrapped under them while the row has room. */
  .notice.stale {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .notice.stale p {
    flex: 1 1 auto;
    min-width: 0;
    margin: 0;
  }

  .notice.stale button {
    flex: none;
  }

  .editor {
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
  }

  .problems {
    flex: none;
    max-height: 22%;
    overflow: auto;
    margin: 0;
    padding: 4px 12px 6px;
    list-style: none;
    border-top: 1px solid var(--line);
    font-size: var(--text-sm);
  }

  .problems li {
    margin: 2px 0;
  }
</style>
