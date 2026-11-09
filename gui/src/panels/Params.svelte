<script lang="ts">
  /**
   * The parameter table: every row the θ vector has, grouped, filtered, editable.
   *
   * Three rules come from the API rather than from taste.  A row that cannot be
   * freed has **no vary checkbox at all** — the five reasons are distinct
   * (`locked`, `tied`, `mode_fixed`, `held`, `needs_held_cell`) and
   * `held_because` is
   * the tooltip, already written server-side, so nothing here re-derives why
   * (WP-1004).  A bulk
   * free/fix sends the **glob**, because `set_vary` takes one and records one
   * history node for it.  And value edits accumulate until Apply, because
   * `set_values` takes a dict and a node per keystroke would bury the log.
   *
   * The list is virtualized against `lib/table.ts`: a Pawley fit has thousands
   * of rows, and the DOM for all of them is the difference between a table and a
   * stall.
   */
  import { ApiError, api } from "../api";
  import Help from "../Help.svelte";
  import { paramKey } from "../lib/help";
  import {
    asGlob,
    editState,
    flatten,
    formatEsd,
    formatValue,
    groupOf,
    heldGlyph,
    heldKind,
    leafName,
    normalize,
    selection,
    validateEdit,
    varyEdit,
    varyOf,
    windowSlice,
    type ParamRow,
  } from "../lib/table";

  let {
    head = null,
    busy = false,
    simple = true,
    say = (_line: string) => {},
    onpending = (_touched: number, _invalid: string) => {},
  }: {
    head?: string | null;
    busy?: boolean;
    simple?: boolean;
    say?: (line: string) => void;
    /** the pending edits, reported to the shell's action bar (WP-2123): how
     *  many, and the first invalid one's reason or "" */
    onpending?: (touched: number, invalid: string) => void;
  } = $props();

  const ROW_HEIGHT = 22;

  let rows = $state<ParamRow[]>([]);
  let nFree = $state(0);
  let mode = $state("");
  let query = $state("");
  let error = $state("");
  let loading = $state(false);
  let collapsed = $state(new Set<string>());
  let edits = $state(new Map<string, string>());
  let varyEdits = $state(new Map<string, boolean>());
  let scrollTop = $state(0);
  let viewport = $state(400);

  const glob = $derived(asGlob(query));
  const view = $derived(flatten(rows, { glob, collapsed, simple }));
  const picked = $derived(selection(rows, glob));
  const slice = $derived(windowSlice(view.items.length, scrollTop, viewport, ROW_HEIGHT));
  const pending = $derived(editState(rows, edits, varyEdits.size));

  // The action bar at the panel column's foot shows the count and holds Apply
  // and Revert (WP-2123); this panel's own footer, which appeared on the first
  // edit and moved the table, is gone.
  $effect(() => {
    const first = pending.invalid[0];
    onpending(pending.touched,
              first ? `${first.path.split(".").pop()}: ${first.why}` : "");
  });

  async function load() {
    loading = true;
    try {
      const payload = await api.params();
      rows = normalize(payload.parameters);
      nFree = payload.n_free;
      mode = payload.mode;
      error = "";
    } catch (exc) {
      rows = [];
      // NO_PROJECT is the shell's empty state, not this panel's error
      error = exc instanceof ApiError && exc.empty ? "" : (exc as Error).message;
    } finally {
      loading = false;
    }
  }

  // reload when the working state moved: a run, a checkout, an edit elsewhere.
  // `head` is the history node the project stands at, which is the one signal
  // that covers all three (WP-1005: the head *is* the working state).
  $effect(() => {
    void head;
    load();
  });

  function absorb(payload: any) {
    rows = normalize(payload.parameters);
    nFree = payload.n_free;
    mode = payload.mode;
    edits = new Map();
    varyEdits = new Map();
    error = "";
  }

  async function patch(body: { values?: Record<string, number>; vary?: Record<string, boolean> }): Promise<boolean> {
    try {
      absorb(await api.patchParams(body));
      return true;
    } catch (exc) {
      // a refusal is the useful answer: a tied path names the source to set
      // instead, a bound violation prints the interval, a 409 says a run owns
      // the table.  Every one of them is the verb's own words.
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the table is read-only until it ends"
        : (exc as Error).message;
      return false;
    }
  }

  async function bulk(vary: boolean) {
    say(`ref.set_vary(${JSON.stringify(glob)}, ${vary ? "True" : "False"})`);
    await patch({ vary: { [glob]: vary } });
  }

  /** Apply the pending edits; true when there were none or they all landed,
   *  which is what "Apply and refine" waits on before it runs anything. */
  export async function apply(): Promise<boolean> {
    if (!pending.touched) return true;
    if (pending.invalid.length) return false;
    const { values } = pending;
    const vary = Object.fromEntries(varyEdits);
    if (Object.keys(values).length) say(`ref.set_values(${JSON.stringify(values)})`);
    for (const [path, flag] of varyEdits) {
      say(`ref.set_vary(${JSON.stringify(path)}, ${flag ? "True" : "False"})`);
    }
    return await patch({ values, vary });
  }

  export function revert() {
    edits = new Map();
    varyEdits = new Map();
    error = "";
  }

  function toggleGroup(key: string) {
    const next = new Set(collapsed);
    if (!next.delete(key)) next.add(key);
    collapsed = next;
  }

  function edit(path: string, text: string) {
    const next = new Map(edits);
    next.set(path, text);
    edits = next;
  }

  function toggleVary(row: ParamRow, checked: boolean) {
    varyEdits = varyEdit(varyEdits, row, checked);
  }

  function shownValue(row: ParamRow): string {
    const pending = edits.get(row.path);
    return pending !== undefined ? pending : formatValue(row.value, row.esd);
  }

  export function focusFilter() {
    document.querySelector<HTMLInputElement>("#param-filter")?.focus();
  }

  export const freeSelection = () => bulk(true);
  export const fixSelection = () => bulk(false);
</script>

<section>
  <header>
    <input
      id="param-filter"
      class="mono"
      placeholder="filter — a word, or a glob like phases.*.cell.*"
      bind:value={query}
      disabled={!rows.length} />
    <span class="muted mono" title="the glob that will be sent">{glob}</span>
  </header>

  <div class="bar">
    <span class="muted">
      {view.shown} of {rows.length} rows · <strong>{nFree}</strong> free
      {#if mode}· <span class="mono">{mode}</span>{/if}
      {#if view.hidden}
        · <span class="muted" title="locked, tied or mode-fixed rows; Advanced shows them">
          {view.hidden} held hidden</span>
      {/if}
    </span>
    <span class="spacer"></span>
    <button class="ghost" disabled={busy || !picked.toFree} onclick={() => bulk(true)}
      title="one set_vary call on the glob above — one history node">
      Free {picked.toFree}
    </button>
    <button class="ghost" disabled={busy || !picked.toFix} onclick={() => bulk(false)}>
      Fix {picked.toFix}
    </button>
  </div>

  {#if error}
    <p class="bad">{error}</p>
  {/if}

  <div
    class="scroller"
    bind:clientHeight={viewport}
    onscroll={(event) => (scrollTop = (event.currentTarget as HTMLElement).scrollTop)}>
    {#if loading && !rows.length}
      <p class="muted pad">loading the table…</p>
    {:else if !rows.length}
      <p class="muted pad">No parameters — open a project.</p>
    {:else if !view.items.length}
      <p class="muted pad">Nothing matches <span class="mono">{glob}</span>.</p>
    {:else}
      <div style:height="{slice.padTop}px"></div>
      {#each view.items.slice(slice.start, slice.end) as item (item.key)}
        {#if item.kind === "group"}
          <button class="group mono pick" onclick={() => toggleGroup(item.key)}>
            <span class="caret">{collapsed.has(item.key) ? "▸" : "▾"}</span>
            {item.label}
            <span class="muted">{item.free}/{item.n}</span>
          </button>
        {:else}
          {@const row = item.row}
          {@const held = heldKind(row)}
          {@const bad = edits.has(row.path) ? validateEdit(row, edits.get(row.path)!) : ""}
          <div class="row" class:held={held !== ""} data-held={held}>
            <!-- `title` here is the *value* this column truncates, not an
                 explanation (WP-1203): the leaf is shown and the whole path is
                 what a narrow sidebar cut off.  What the parameter *is* is the
                 corpus's, reached from the leaf itself. -->
            <span class="path mono" title={row.path}>
              <Help for={paramKey(row.help_key)}
                >{leafName(row.path, groupOf(row.path))}</Help>
            </span>
            {#if row.tie}
              <span class="value mono muted" title={row.held_because}>
                {formatValue(row.value, row.esd)}
              </span>
            {:else}
              <input
                class="value mono tabular"
                class:bad={bad !== ""}
                class:edited={edits.has(row.path)}
                value={shownValue(row)}
                title={bad || row.held_because}
                disabled={busy}
                oninput={(event) => edit(row.path, (event.currentTarget as HTMLInputElement).value)} />
            {/if}
            <span class="esd mono muted tabular">{formatEsd(row.value, row.esd)}</span>
            {#if !simple}
              <span class="bounds mono muted" title="bounds">
                {row.lo > -Infinity || row.hi < Infinity
                  ? `[${row.lo}, ${row.hi}]`
                  : ""}
              </span>
            {/if}
            {#if row.refinable}
              <input
                type="checkbox"
                class="vary"
                checked={varyOf(row, varyEdits)}
                disabled={busy}
                title="free this parameter"
                onchange={(event) =>
                  toggleVary(row, (event.currentTarget as HTMLInputElement).checked)} />
            {:else}
              <!-- no checkbox at all: a control that errors on click is worse
                   than an absent one, and `held_because` says which of the
                   four reasons holds it (`heldGlyph` in `lib/table.ts` is the
                   one vocabulary, WP-1214).

                   The one `<Help label=…>` in the app, because it is the one
                   term whose children are a glyph: `·` names nothing, and no
                   `<label>` or `<th>` encloses this span for the name to leak
                   into (`Help.svelte` has the measurement). -->
              <span class="vary muted">
                <Help text={row.held_because} title="This row is held"
                  label="why this row is held"
                  >{heldGlyph(row)}</Help>
              </span>
            {/if}
          </div>
        {/if}
      {/each}
      <div style:height="{slice.padBottom}px"></div>
    {/if}
  </div>

  <!-- Apply and Revert live in the shell's action bar (WP-2123).  An invalid
       cell still blocks Apply rather than being dropped silently: the whole
       point of carrying bounds on the row is to say so before the round trip,
       and a partial apply is a worse answer than none. -->
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
  }

  /* a row of controls, so it is control-sized: the glob echo beside the filter
     field read a step larger than the field it describes */
  header {
    display: flex;
    gap: 6px;
    align-items: center;
    padding: 6px 8px 4px;
    font-size: var(--text-sm);
  }

  header input {
    flex: 1 1 auto;
    min-width: 0;
    font: var(--mono);
    padding: 3px 6px;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--bg);
    color: var(--fg);
  }

  /* rows of controls, so they are control-sized — the counts beside the
     buttons read with them rather than as prose */
  .bar {
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 0 8px 4px;
    font-size: var(--text-sm);
  }

  .spacer {
    flex: 1 1 auto;
  }

  .scroller {
    flex: 1 1 auto;
    overflow-y: auto;
    border-top: 1px solid var(--line);
    min-height: 120px;
  }

  .pad {
    padding: 10px;
  }

  /* one row of the parameter table, so everything on it is control-sized —
     the path, the esd and the editable value were 13/13/11.5 in a 22 px row */
  .group,
  .row {
    display: flex;
    align-items: center;
    gap: 5px;
    height: 22px;
    padding: 0 8px;
    box-sizing: border-box;
    font-size: var(--text-sm);
  }

  /* the `.pick` register (app.css) with the group header's own surface */
  .group {
    width: 100%;
    background: color-mix(in srgb, var(--panel) 60%, var(--bg));
    border-bottom: 1px solid var(--line);
    font-weight: 600;
    padding-left: 6px;
  }

  .caret {
    color: var(--muted);
    width: 10px;
  }

  .row.held {
    color: var(--muted);
  }

  /* The three widths below are one budget, and WP-1203's browser pass is what
     measured it: at the sidebar's 340 px floor in Advanced the row's fixed
     columns wanted 372 px, so `.path` was handed **zero** and the leaf name
     disappeared.  That had been invisible while the leaf was only text; a help
     term has to be clickable, and an unclickable one is a control that does
     nothing.

     Two of the three are the repair.  `min-width: 0` on the input is the
     actual defect: a flex item's automatic minimum is its *content* size, and
     an `<input>`'s is its default twenty characters — so `flex: 0 0 92px` was
     being floored at 152 px, 65 % over its own declaration, and the extra 60
     came out of the leaf.  `.bounds` gives way next, because a truncated bound
     string is the most expendable thing on the row.  The 44 px floor on
     `.path` is last: 24 px is WCAG 2.2's minimum target size and 44 px is that
     rounded up to a whole number of mono cells at `--text-sm`, which is a
     truncated name plus its ellipsis rather than an ellipsis alone. */
  .path {
    flex: 1 1 auto;
    min-width: 44px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .value {
    flex: 0 0 92px;
    min-width: 0;
    text-align: right;
  }

  input.value {
    border: 1px solid transparent;
    background: transparent;
    color: inherit;
    padding: 1px 3px;
    border-radius: 3px;
  }

  input.value:focus {
    border-color: var(--accent);
    background: var(--bg);
    outline: none;
  }

  input.value.edited {
    border-color: var(--warn);
  }

  input.value.bad {
    border-color: var(--bad);
    color: var(--bad);
  }

  .esd {
    flex: 0 0 46px;
  }

  .bounds {
    flex: 0 1 120px;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
  }

  .vary {
    flex: 0 0 18px;
    text-align: center;
    margin: 0;
  }

  .bad {
    color: var(--bad);
    padding: 0 8px;
    margin: 2px 0;
  }
</style>
