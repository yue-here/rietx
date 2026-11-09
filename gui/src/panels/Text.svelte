<script lang="ts">
  /**
   * The project as text — the power-user surface, full width.
   *
   * **Not a sixth tab.** The sidebar strip is five tabs wide inside
   * `clamp(340px, 38%, 560px)`, and this is the one panel whose content is
   * line-oriented: the `.rxt` format aligns its columns *so that a rectangular
   * selection can hit one field*, and a 340 px column wraps or side-scrolls the
   * alignment away. So the pane is a mode over the whole window. It stays
   * mounted while hidden — a buffer with unsaved edits has to survive a look at
   * the parameter table — and the editor is built the first time the mode is
   * entered, which is what keeps CodeMirror out of the boot path.
   *
   * **The head is the reload signal.** There is no new SSE frame type for
   * "the document changed": WP-1008 declined to add an `EventKind` for a guess
   * and the head already covers every writer — a run, a checkout, a form edit,
   * an applied suggestion. So this re-reads `GET /api/textdoc` on `head` exactly
   * as the parameter table re-reads `/api/params`, and `lib/sync.ts` decides
   * whether the answer may be adopted or only makes the buffer stale.
   *
   * Everything else is `lib/sync.ts`: this component owns the debounce timer,
   * the fetches and the DOM, and holds no rule of its own.
   */
  import { ApiError, api } from "../api";
  import { commentLines } from "../lib/rxt";
  import { canApply, initial, reduce, type Problem, type SyncEvent } from "../lib/sync";
  // types only — erased at build time, so the boot chunk still has no CodeMirror
  import type { EditorHandle, createEditor } from "../lib/editor";

  let {
    head = null,
    busy = false,
    active = false,
    dark = false,
    say = (_line: string) => {},
    onmoved = () => {},
  }: {
    head?: string | null;
    busy?: boolean;
    active?: boolean;
    /** the *resolved* theme, not the choice — `lib/theme.ts` owns the resolving,
     *  and CodeMirror's chrome needs the flag rather than the colours */
    dark?: boolean;
    say?: (line: string) => void;
    onmoved?: () => void;
  } = $props();

  /** Long enough that a burst of typing is one request, short enough that a
   *  pause feels answered.  WP-1013's number, not a tuned one. */
  const DEBOUNCE_MS = 300;

  let sync = $state(initial());
  let host = $state<HTMLDivElement | null>(null);
  /** `$state` rather than a plain `let`, so the two effects below can *derive*
   *  the editor's document and diagnostics from `sync` once it exists. */
  let editor = $state<EditorHandle | null>(null);
  let bootError = $state("");
  let timer: ReturnType<typeof setTimeout> | null = null;
  /** the document has never been fetched, so the empty buffer is not "clean" */
  let loaded = $state(false);

  const problems = $derived(sync.problems);
  const applyable = $derived(canApply(sync, busy));
  /** the user's own comments do not survive a re-render (WP-1009 refused to
   *  store one: it would be a second authority) — so say so *before* Apply
   *  replaces the buffer, not after the notes are gone */
  const addedComments = $derived(
    Math.max(0, commentLines(sync.buffer) - commentLines(sync.base)));

  function dispatch(event: SyncEvent) {
    sync = reduce(sync, event);
  }

  async function load(force = false) {
    try {
      const payload = await api.textdoc();
      dispatch({ kind: "rendered", text: payload.text, revision: payload.revision, force });
      loaded = true;
    } catch (error) {
      if (error instanceof ApiError && error.empty) return; // no project yet
      bootError = (error as Error).message;
    }
  }

  function edited(text: string) {
    dispatch({ kind: "edited", text });
    if (timer) clearTimeout(timer);
    // no point asking a server that will refuse on state, or one whose answer we
    // already know is stale
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
    } catch (error) {
      absorb(error, seq);
    }
  }

  async function apply() {
    if (!canApply(sync, busy)) return;
    if (timer) clearTimeout(timer);
    const text = sync.buffer;
    dispatch({ kind: "applying" });
    try {
      const payload = await api.putTextdoc(text, sync.revision, false);
      for (const call of payload.applied ?? []) say(call);
      dispatch({ kind: "applied", text: payload.text, revision: payload.revision,
                 verbs: payload.applied ?? [] });
      // the verbs committed history nodes, so the head moved and every other
      // panel is now looking at the previous state
      if ((payload.applied ?? []).length) onmoved();
    } catch (error) {
      absorb(error);
    }
  }

  /** Turn an `ApiError` into the one event `lib/sync.ts` understands. */
  function absorb(error: unknown, seq?: number) {
    if (!(error instanceof ApiError)) {
      dispatch({ kind: "refused", seq, code: "HTTP_ERROR",
                 message: (error as Error).message });
      return;
    }
    dispatch({ kind: "refused", seq, code: error.code, message: error.message,
               problems: error.details.filter((d) => d.line !== undefined) as Problem[] });
  }

  // The editor's document and its squiggles are **derived** from `sync`, not
  // pushed at it from the four places that change it.  Pushing is what a browser
  // caught: `load` cleared the diagnostics unconditionally, so a head moving
  // underneath an invalid buffer — a checkout, a form edit, an applied
  // suggestion — wiped the squiggle and the gutter marker while the problem list
  // below still named the line.  Two views of one answer that could disagree.
  // `setDoc` is a no-op when the text already matches (`minimalChange` returns
  // null), so this also runs harmlessly on every keystroke.
  $effect(() => {
    editor?.setDoc(sync.buffer);
  });
  $effect(() => {
    editor?.setProblems(sync.problems);
  });
  // …and so is the chrome, for the same reason: a theme toggle is a fifth thing
  // that changes underneath a mounted editor, and a rebuild would take the
  // buffer and its undo history with it
  $effect(() => {
    editor?.setTheme(dark);
  });

  // re-read when the working state moved (WP-1005: the head *is* the working
  // state).  Only once the pane has been opened: a text document nobody is
  // looking at costs a render of every parameter row per head change.
  $effect(() => {
    void head;
    if (active) load();
  });

  // build the editor the first time the mode is entered, and re-measure on every
  // later entry — CM lays out to a container that was `display: none`
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
    if (mounting) return; // the mode can be re-entered before the chunk lands
    mounting = true;
    try {
      // dynamic, so `vendor-cm.js` is fetched on first use rather than at boot
      const module: { createEditor: typeof createEditor } = await import("../lib/editor");
      // no `setProblems` here: the effect above adopts them the moment `editor`
      // is assigned, which is the point of deriving them
      editor = module.createEditor({
        parent,
        doc: sync.buffer,
        onChange: edited,
        onApply: apply,
        dark,
      });
    } catch (error) {
      // released only on failure: on success `editor` is set and the effect
      // above short-circuits, but a chunk that failed to load should be
      // retryable by leaving the mode and coming back
      mounting = false;
      bootError = `the editor did not load: ${(error as Error).message}`;
    }
  }

  $effect(() => () => {
    if (timer) clearTimeout(timer);
    editor?.destroy();
  });

  const status = $derived(
    !loaded ? "loading…"
    : sync.stale ? "stale"
    : sync.phase === "clean" ? "in sync"
    : sync.phase === "dirty" ? "edited"
    : sync.phase === "checking" ? "checking…"
    : sync.phase === "invalid" ? `${problems.length} problem(s)`
    : sync.phase === "applying" ? "applying…"
    : sync.wouldChange ? "ready to apply" : "no changes");
</script>

<section class="text">
  <header>
    <strong>Project text</strong>
    <span class="muted mono">.rxt</span>
    <span class="pill mono" data-phase={sync.stale ? "stale" : sync.phase}>{status}</span>
    <span class="spacer"></span>
    <button class="ghost" onclick={apply} disabled={!applyable} title="apply the whole document as one delta">
      Apply <kbd>⌘⏎</kbd>
    </button>
    <!-- one button, not a Revert *and* a Re-read: both discard the buffer and
         re-render from state, which is also the only exit a stale pane has -->
    <button class="ghost" onclick={() => load(true)}
      title="discard this buffer and re-read the project">Re-read</button>
  </header>

  {#if sync.stale}
    <p class="banner bad">
      {sync.notice}
      <span class="muted">There is no merge: the document is regenerated from state,
        so re-read it and re-apply.</span>
    </p>
  {:else if sync.notice}
    <p class="banner">{sync.notice}</p>
  {/if}

  {#if bootError}
    <p class="banner bad">{bootError}</p>
  {/if}

  {#if addedComments > 0}
    <p class="banner muted">
      {addedComments} comment line(s) you added will not survive the next render —
      comments parse but are not stored (WP-1009). Apply, then re-read.
    </p>
  {/if}

  <div class="editor" bind:this={host}></div>

  {#if problems.length}
    <ul class="problems">
      {#each problems as problem (problem.line + problem.message)}
        <li>
          <button class="link mono" onclick={() => editor?.goToLine(problem.line)}
            >line {problem.line}</button>
          {#if problem.where}<span class="mono muted">{problem.where}</span>{/if}
          {problem.message}
        </li>
      {/each}
    </ul>
  {/if}

  <footer class="muted">
    Rectangular selection: <kbd>⌥</kbd>-drag. Everything applies through the same
    verbs the forms call, so a bulk edit lands as history nodes and is undone by
    a checkout.
  </footer>
</section>

<style>
  .text {
    display: flex;
    flex-direction: column;
    height: 100%;
    min-height: 0;
  }

  header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 6px 10px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
    flex: 0 0 auto;
  }

  .spacer {
    margin-left: auto;
  }

  .pill[data-phase="stale"] {
    color: var(--warn);
    border-color: var(--warn);
  }

  .pill[data-phase="invalid"] {
    color: var(--bad);
    border-color: var(--bad);
  }

  .pill[data-phase="valid"] {
    color: var(--ok);
    border-color: var(--ok);
  }

  .banner {
    margin: 0;
    padding: 5px 10px;
    border-bottom: 1px solid var(--line);
    background: var(--panel);
    flex: 0 0 auto;
  }

  .editor {
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
  }

  .problems {
    flex: 0 0 auto;
    max-height: 22%;
    overflow: auto;
    margin: 0;
    padding: 4px 10px 6px 10px;
    list-style: none;
    border-top: 1px solid var(--line);
    background: var(--panel);
  }

  .problems li {
    margin: 2px 0;
  }

  footer {
    flex: 0 0 auto;
    padding: 4px 10px 6px;
    border-top: 1px solid var(--line);
  }
</style>
