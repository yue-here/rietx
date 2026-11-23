<script lang="ts">
  /**
   * The peaks-and-indexing workflow's steps at `/next` (WP-2240, piece R6 of
   * WP-2214's plan), mounted across the model panel while the workflow is up.
   *
   * The design is round 11's (2026-11-08, closed "looks good"), restated in
   * WP-2240 § The design. Each step shows only what that step needs, and its
   * one action sits in a foot pinned under it: the workflow hides the action
   * bar, so that action is the view's one filled primary.
   *
   * Pick peaks. Before the first pick, the picker's three options and Pick
   * peaks. After it, a filter (All, Used, Not used) over a table of every
   * line: a tickbox sending the line to the search, 2θ, d, intensity and a
   * note in words. A row ticked or unticked stays in a filtered list until
   * the filter is chosen again, since a row leaving on a tick would move the
   * layout on a click that did not ask to (round 11b call 22). A row's click
   * frames its line on the Pattern graph. The picker's notes and the picking
   * settings sit under disclosures, and picking again first says how many of
   * the person's edits it replaces (round 11c call 29, interaction rule 11).
   *
   * The peak list is a project artifact (`peaks.json`, WP-1027), so the panel
   * reads it from `GET /api/peaks` and every verb answers with the new list,
   * which is handed up for the Pattern graph's marks. The panel owns the
   * verbs: the plot's gestures reach them through `edit`, and ⌘Z and ⇧⌘Z
   * step through the server's stack of stored lists (interaction rule 10),
   * since the list lives outside the history tree.
   */
  import { onMount } from "svelte";

  import { api } from "../api";
  import Help from "../Help.svelte";
  import { labelFor, type HelpCorpus } from "../lib/help";
  import {
    filterPeaks, formatIntensity, formatPosition, intensityScale, nearestRow,
    type PeakEdit, type PeakFilter, type PeakRow, type PeaksPayload,
  } from "../lib/peaks";
  import type { Step } from "../lib/workflows";
  import type { Say } from "./console";

  let {
    step = 0,
    steps,
    busy = false,
    corpus = null,
    say = () => {},
    onpeaks = () => {},
    onframe = () => {},
    selected = $bindable(null),
  }: {
    step?: number;
    steps: readonly Step[];
    busy?: boolean;
    corpus?: HelpCorpus | null;
    say?: Say;
    /** the list after every answer, for the Pattern graph's marks */
    onpeaks?: (payload: PeaksPayload | null) => void;
    /** frame this row's line on the Pattern graph */
    onframe?: (row: PeakRow) => void;
    /** the row chosen in the table, bound to the shell, which marks its line
     *  on the Pattern graph; a pick clears it, as the rows are renumbered */
    selected?: number | null;
  } = $props();

  let payload = $state.raw<PeaksPayload | null>(null);
  let loadError = $state("");
  let working = $state(false);
  let filter = $state<PeakFilter>("all");
  /** rows ticked or unticked since the filter was chosen (call 22) */
  let keep = $state<Set<number>>(new Set());
  /** the flags rietx had on a line a person ticked, for its note: the
   *  overrule drops them (`set_flags(..., use_for_indexing=True)`), and the
   *  stored list does not remember them (WP-2240 § Inherited) */
  let overruled = $state<Map<number, string[]>>(new Map());
  let asking = $state(false);
  let settingsOpen = $state(false);
  /** the picker's options as typed: the 2θ range's two ends are text, so a
   *  half-typed number is never sent */
  let lo = $state("");
  let hi = $state("");
  let shoulders = $state(true);
  let contamination = $state(true);
  /** the typed add row's 2θ (WP-1027: every pointer verb has a typed route) */
  let addText = $state("");
  let table: HTMLTableElement | undefined = $state();

  const rows = $derived(payload?.peaks ?? null);
  const unusable = $derived(new Set(payload?.unusable_flags ?? []));
  const imax = $derived(rows ? intensityScale(rows) : 0);
  const nUsed = $derived(rows ? rows.filter((p) => p.usable).length : 0);
  const shown = $derived(rows ? filterPeaks(rows, filter, keep) : []);
  /** what picking again would replace: lines added, moved or left out by a
   *  person, and the lines they ticked over rietx's flags */
  const edits = $derived(rows
    ? rows.filter((p) => p.origin !== "fitted" || p.flags.includes("excluded")).length
      + overruled.size : 0);
  const range = $derived.by((): [number, number] | null | "bad" => {
    if (!lo.trim() && !hi.trim()) return null;
    const a = Number(lo), b = Number(hi);
    return lo.trim() && hi.trim() && Number.isFinite(a) && Number.isFinite(b) ? [a, b] : "bad";
  });

  onMount(() => {
    void load();
  });

  async function load() {
    try {
      took(await api.peaks() as PeaksPayload, false);
      loadError = "";
    } catch (exc) {
      loadError = (exc as Error).message;
    }
  }

  /** Take a verb's answer: the list, its call in the Console, and the
   *  picker's options as the list was picked with them. */
  function took(next: PeaksPayload, echo = true) {
    payload = next;
    if (echo && next.api_call) say("call", next.api_call);
    const o = next.pick_options;
    if (o && !settingsOpen && !asking) {
      shoulders = o.shoulders ?? true;
      contamination = o.flag_contamination ?? true;
      const r = o.two_theta_range;
      lo = r ? String(r[0]) : "";
      hi = r ? String(r[1]) : "";
    }
    onpeaks(next);
  }

  /** How near, in degrees 2θ, a line must stand after an edit to be the
   *  line a row number pointed at before it. */
  const FOLLOW_DEG = 0.05;
  /** The verb in flight, which a plot edit made meanwhile waits on. */
  let inflight: Promise<unknown> = Promise.resolve();

  /** The row standing at 2θ `tt` now, within `FOLLOW_DEG`, or null. */
  function rowAt(tt: number | null | undefined): number | null {
    const hit = tt == null || !rows ? null : nearestRow(rows, tt);
    return hit && Math.abs(hit.two_theta - tt!) < FOLLOW_DEG ? hit.index : null;
  }

  /** Run one verb. An add or a removal renumbers the list, so everything
   *  this panel keys by row number (the chosen row, the rows kept in a
   *  filtered list, the overrule notes) follows its line by 2θ: `follow`
   *  names the 2θ to choose instead, `moved` where a moved line went, and
   *  `gone` a removed line. */
  function verb(run: () => Promise<unknown>, follow?: number | null,
                { moved, gone }: { moved?: { index: number; to: number }; gone?: number } = {},
  ): Promise<boolean> {
    working = true;
    const at = new Map(rows?.map((r) => [r.index, r.two_theta]) ?? []);
    if (moved) at.set(moved.index, moved.to);
    if (gone != null) at.delete(gone);
    const was = selected == null ? null : at.get(selected) ?? null;
    const done = (async () => {
      try {
        took(await run() as PeaksPayload);
        selected = rowAt(follow === undefined ? was : follow);
        const kept = new Set<number>();
        for (const i of keep) {
          const j = rowAt(at.get(i));
          if (j != null) kept.add(j);
        }
        keep = kept;
        const notes = new Map<number, string[]>();
        for (const [i, flags] of overruled) {
          const j = rowAt(at.get(i));
          if (j != null) notes.set(j, flags);
        }
        overruled = notes;
        return true;
      } catch (exc) {
        say("refusal", `refused: ${(exc as Error).message}`);
        return false;
      } finally {
        working = false;
      }
    })();
    inflight = done;
    return done;
  }

  async function pick() {
    if (range === "bad") return;
    const body: Parameters<typeof api.pickPeaks>[0] = {
      shoulders, flag_contamination: contamination,
      ...(range ? { two_theta_range: range } : {}),
    };
    if (await verb(() => api.pickPeaks(body))) {
      overruled = new Map();
      keep = new Set();
      selected = null;
      asking = false;
    }
  }

  function pickAgain() {
    if (edits > 0) asking = true;
    else void pick();
  }

  function choose(f: PeakFilter) {
    filter = f;
    keep = new Set();
  }

  async function use(row: PeakRow, box: HTMLInputElement) {
    // a refusal leaves the list as it was, and `checked` is one-way: the box
    // would otherwise keep the click and say the opposite of the stored line
    if (!(await setUse(row, box.checked))) box.checked = row.usable;
  }

  async function setUse(row: PeakRow, on: boolean): Promise<boolean> {
    const hard = row.flags.filter((f) => unusable.has(f) && f !== "excluded");
    keep = new Set([...keep, row.index]);
    if (!(await verb(() => api.flagPeak(row.index, { use_for_indexing: on })))) return false;
    const next = new Map(overruled);
    if (on && hard.length) next.set(row.index, hard);
    else if (!on) next.delete(row.index);
    overruled = next;
    return true;
  }

  /** One edit from the plot or the typed row. A move chooses the line where
   *  it landed; an add chooses nothing, since lines are placed many in a row
   *  (interaction rule 3). An edit made while the last one is still being
   *  fitted waits its turn, its line found again by 2θ, rather than being
   *  dropped. */
  export async function edit(e: PeakEdit): Promise<boolean> {
    const tt = e.kind === "add" ? null : rows?.find((r) => r.index === e.index)?.two_theta ?? null;
    while (working) await inflight;
    if (busy) return false;
    if (e.kind === "add") return verb(() => api.addPeak(e.two_theta), selected == null ? null : undefined);
    const index = rowAt(tt);
    if (index == null) return false;
    if (e.kind === "move") {
      return verb(() => api.movePeak(index, e.two_theta), e.two_theta,
                  { moved: { index, to: e.two_theta } });
    }
    if (e.kind === "remove") {
      return verb(() => api.removePeak(index), selected === index ? null : undefined, { gone: index });
    }
    const row = rows?.find((r) => r.index === index);
    return row ? setUse(row, e.on) : false;
  }

  /** Step back or forward through the stored lists. The session's notes on
   *  overruled lines are kept only for lines still used. */
  async function travel(back: boolean): Promise<boolean> {
    if (busy || working) return false;
    const ok = await verb(back ? api.undoPeaks : api.redoPeaks);
    if (ok) {
      overruled = new Map([...overruled].filter(([i]) => rows?.find((r) => r.index === i)?.usable));
      keep = new Set();
    }
    return ok;
  }

  export function undo(): Promise<boolean> {
    return travel(true);
  }

  export function redo(): Promise<boolean> {
    return travel(false);
  }

  export function canUndo(): boolean {
    return !busy && !working && (payload?.undo ?? 0) > 0;
  }

  export function canRedo(): boolean {
    return !busy && !working && (payload?.redo ?? 0) > 0;
  }

  /** ⌘Z and ⇧⌘Z while the workflow is up, outside a text field, which keeps
   *  its own undo (as the Plan tab's keys do). */
  function keydown(event: KeyboardEvent) {
    if (!(event.metaKey || event.ctrlKey) || event.altKey || event.key.toLowerCase() !== "z") return;
    const target = event.target as HTMLElement | null;
    if (target?.closest?.("input, textarea, select, .cm-editor, [role=dialog]")) return;
    event.preventDefault();
    // past either end of the stack the key does nothing, as in an editor,
    // rather than asking the server for a refusal
    if (event.shiftKey ? canRedo() : canUndo()) void travel(!event.shiftKey);
  }

  const addAt = $derived(addText.trim() === "" ? null : Number(addText));
  async function typedAdd() {
    if (addAt == null || !Number.isFinite(addAt)) return;
    if (await edit({ kind: "add", two_theta: addAt })) addText = "";
  }

  // a line chosen on the plot brings its row into view, at the nearest edge
  // and only when it is out of view (round 11b call 20)
  $effect(() => {
    const i = selected;
    if (i == null || !table) return;
    queueMicrotask(() => table?.querySelector(`tr[data-row="${i}"]`)
      ?.scrollIntoView?.({ block: "nearest" }));
  });

  function frame(row: PeakRow) {
    selected = row.index;
    onframe(row);
  }

  /** A row's note, in words: who placed or moved it, whether a person
   *  ticked it over rietx's flags, then the flags. */
  function note(row: PeakRow): Array<{ key: string | null; text: string }> {
    const out: Array<{ key: string | null; text: string }> = [];
    if (row.origin !== "fitted") {
      const key = `peak_origins:${row.origin}`;
      out.push({ key, text: labelFor(corpus, key) });
    }
    const over = overruled.get(row.index);
    if (over && row.usable) {
      out.push({ key: null, text: `used by you over “${over.map((f) => labelFor(corpus, `peak_flags:${f}`)).join(", ")}”` });
    }
    for (const f of row.flags) out.push({ key: `peak_flags:${f}`, text: labelFor(corpus, `peak_flags:${f}`) });
    return out;
  }

  const disabled = $derived(busy || working);
</script>

{#snippet options()}
  <div class="field">
    <span class="label">2θ range</span>
    <input class="num" inputmode="decimal" placeholder="default" bind:value={lo}
      aria-label="Lowest 2θ" {disabled} />
    <span class="muted">to</span>
    <input class="num" inputmode="decimal" placeholder="default" bind:value={hi}
      aria-label="Highest 2θ" {disabled} />
    <span class="muted">°</span>
  </div>
  <div class="field">
    <span class="label">Shoulders</span>
    <label class="check"><input type="checkbox" bind:checked={shoulders} {disabled} /> Look for shoulders</label>
  </div>
  <div class="field">
    <span class="label">Contamination</span>
    <label class="check"><input type="checkbox" bind:checked={contamination} {disabled} /> Flag Kβ and tungsten lines</label>
  </div>
  {#if range === "bad"}<p class="bad">Type both ends of the 2θ range, or neither.</p>{/if}
{/snippet}

<svelte:window onkeydown={keydown} />

<div class="steppane">
  {#if !steps[step]?.built}
    <div class="body"><p class="box">{steps[step]?.body}</p></div>
  {:else if loadError}
    <div class="body"><p class="bad">The peak list could not be read: {loadError}</p></div>
  {:else if payload && !rows}
    <div class="body">
      <h3>Picking settings</h3>
      {@render options()}
    </div>
    <div class="foot">
      <button onclick={pick} disabled={disabled || range === "bad"}>
        {working ? "Picking peaks…" : "Pick peaks"}</button>
    </div>
  {:else if rows}
    <div class="body">
      <div class="bar">
        <span class="segmented" role="group" aria-label="Show">
          {#each [["all", "All", rows.length], ["used", "Used", nUsed],
                  ["unused", "Not used", rows.length - nUsed]] as [id, word, n] (id)}
            <!-- each count holds the room of the longest, so a tick that
                 shortens a count moves nothing (principle 4) -->
            <button class:on={filter === id} aria-pressed={filter === id}
              onclick={() => choose(id as PeakFilter)}>{word}
              <span class="count" style:min-width="{String(rows.length).length}ch">{n}</span></button>
          {/each}
        </span>
      </div>
      <table class="lines" bind:this={table}>
        <thead>
          <tr><th class="ck"></th><th class="r">2θ</th><th class="r">d</th>
            <th class="r">Intensity</th><th>Note</th></tr>
        </thead>
        <tbody>
          {#each shown as row (row.index)}
            <tr class:off={!row.usable} class:sel={selected === row.index} data-row={row.index}
              onclick={(ev) => { if (!(ev.target as HTMLElement).closest("label")) frame(row); }}>
              <td class="ck"><label><input type="checkbox" checked={row.usable} {disabled}
                aria-label="Use {formatPosition(row.two_theta, null).value}° in the search"
                onchange={(ev) => use(row, ev.target as HTMLInputElement)} /></label></td>
              <td class="r num">{formatPosition(row.two_theta, null).value}<span class="u">°</span></td>
              <td class="r num">{row.d.toFixed(4)}{" "}<span class="u">Å</span></td>
              <td class="r num">{formatIntensity(row.intensity, imax, row.flags)}</td>
              <td class="note">{#each note(row) as w, i (i)}{#if i}, {/if}{#if w.key}<Help for={w.key}>{w.text}</Help>{:else}{w.text}{/if}{/each}</td>
            </tr>
          {/each}
        </tbody>
        <tfoot>
          <!-- every pointer verb has a typed route (WP-1027, row 194) -->
          <tr class="add">
            <td class="ck"></td>
            <td class="r"><input class="num" inputmode="decimal" placeholder="2θ" bind:value={addText}
              aria-label="Add a line at 2θ" {disabled}
              onkeydown={(e) => e.key === "Enter" && typedAdd()} /><span class="u">°</span></td>
            <td colspan="3"><button class="ghost" {disabled} onclick={typedAdd}
              title="Add a line at this 2θ and fit its group">Add</button>
              {#if addAt != null && !Number.isFinite(addAt)}<span class="bad">Type a number.</span>{/if}</td>
          </tr>
        </tfoot>
      </table>
      {#if payload?.diagnostics?.length}
        <details class="notes">
          <summary>Notes from the picker ({payload.diagnostics.length})</summary>
          {#each payload.diagnostics as d, i (i)}
            <p class="dg"><b>{d.level === "warning" || d.level === "error" ? "Warning." : "Note."}</b> {d.message}</p>
          {/each}
        </details>
      {/if}
      <details class="notes" bind:open={settingsOpen}>
        <summary>Picking settings</summary>
        {@render options()}
        <div class="field">
          {#if asking}
            <span class="why">Picking again replaces the list, with the {edits}
              line{edits === 1 ? "" : "s"} you added, moved or ruled on.</span>
            <button class="ghost" onclick={() => (asking = false)}>Cancel</button>
            <button onclick={pick} disabled={disabled || range === "bad"}>Pick peaks</button>
          {:else}
            <button class="ghost" onclick={pickAgain} disabled={disabled || range === "bad"}
              title="Run the picker again over the whole pattern with these settings">Pick peaks</button>
          {/if}
        </div>
      </details>
    </div>
  {/if}
</div>

<style>
  .steppane {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .body {
    flex: 1 1 auto;
    min-height: 0;
    overflow: auto;
    padding: 6px 12px 12px;
  }

  /* the step's one action, pinned under its body (the prototype's foot) */
  .foot {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 6px 12px;
    border-top: 1px solid var(--line);
  }

  .box {
    margin: 10px 4px;
    padding: 12px 14px;
    border: 1px dashed var(--line-strong);
    border-radius: 6px;
    color: var(--muted);
  }

  h3 {
    margin: 10px 0 6px;
  }

  .field {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px 10px;
    min-height: 36px;
  }

  .field .label {
    flex: none;
    width: 8.5em;
    color: var(--muted);
  }

  .field input.num {
    width: 8ch;
  }

  .check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    white-space: nowrap;
    cursor: pointer;
  }

  .bar {
    display: flex;
    align-items: center;
    min-height: 34px;
    margin-bottom: 4px;
  }

  table.lines {
    width: 100%;
    border-collapse: collapse;
  }

  .lines th {
    position: sticky;
    top: 0;
    z-index: 1;
    height: 28px;
    padding: 0 6px;
    background: var(--bg);
    border-bottom: 1px solid var(--line);
    text-align: left;
    font-weight: 500;
    color: var(--muted);
    white-space: nowrap;
  }

  .lines td {
    height: 28px;
    padding: 2px 6px;
    white-space: nowrap;
  }

  .lines .r {
    text-align: right;
  }

  .lines .ck {
    width: 30px;
    padding: 0 0 0 2px;
  }

  .lines .ck input {
    margin: 0;
    accent-color: var(--accent-ink);
  }

  .lines tbody tr {
    cursor: pointer;
    scroll-margin-top: 34px;
  }

  @media (hover: hover) {
    .lines tbody tr:hover td {
      background: var(--hover);
    }
  }

  .lines tr.add td {
    padding-top: 6px;
  }

  .lines tr.add input {
    width: 8ch;
    text-align: right;
  }

  .lines tr.sel td {
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }

  /* a line left out of the search: greyed, and still a target, since its
     tickbox brings it back (interaction rule 4) */
  .lines tr.off td {
    color: var(--muted);
  }

  .num {
    font-family: var(--mono-family);
  }

  .u {
    color: var(--muted);
  }

  .count {
    display: inline-block;
    text-align: left;
    font-variant-numeric: tabular-nums;
  }

  .note {
    color: var(--muted);
  }

  details.notes {
    margin: 12px 0;
    color: var(--muted);
  }

  details.notes summary {
    cursor: pointer;
    color: var(--fg);
  }

  .dg {
    margin: 6px 0 0 14px;
    white-space: normal;
  }

  .dg b {
    font-weight: 500;
    color: var(--fg);
  }

  .why {
    flex: 1 1 12em;
    min-width: 0;
    color: var(--muted);
  }

  .bad {
    color: var(--bad);
  }
</style>
