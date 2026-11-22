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
   * which is handed up for the Pattern graph's marks.
   */
  import { onMount } from "svelte";

  import { api } from "../api";
  import Help from "../Help.svelte";
  import { labelFor, type HelpCorpus } from "../lib/help";
  import {
    filterPeaks, formatIntensity, formatPosition, intensityScale,
    type PeakFilter, type PeakRow, type PeaksPayload,
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
  } = $props();

  let payload = $state.raw<PeaksPayload | null>(null);
  let loadError = $state("");
  let working = $state(false);
  let filter = $state<PeakFilter>("all");
  /** rows ticked or unticked since the filter was chosen (call 22) */
  let keep = $state<Set<number>>(new Set());
  let selected = $state<number | null>(null);
  /** the flags rietx had on a line a person ticked, for its note: the
   *  overrule drops them (`set_flags(..., use_for_indexing=True)`), and the
   *  stored list does not remember them (WP-2240 § Inherited) */
  let overruled = $state<Map<number, string[]>>(new Map());
  let removed = $state(0);
  let asking = $state(false);
  let settingsOpen = $state(false);
  /** the picker's options as typed: the 2θ range's two ends are text, so a
   *  half-typed number is never sent */
  let lo = $state("");
  let hi = $state("");
  let shoulders = $state(true);
  let contamination = $state(true);

  const rows = $derived(payload?.peaks ?? null);
  const unusable = $derived(new Set(payload?.unusable_flags ?? []));
  const imax = $derived(rows ? intensityScale(rows) : 0);
  const nUsed = $derived(rows ? rows.filter((p) => p.usable).length : 0);
  const shown = $derived(rows ? filterPeaks(rows, filter, keep) : []);
  /** what picking again would replace: lines added, moved or left out by a
   *  person, the lines they ticked over rietx's flags, and those removed */
  const edits = $derived(rows
    ? rows.filter((p) => p.origin !== "fitted" || p.flags.includes("excluded")).length
      + overruled.size + removed : 0);
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

  async function verb(run: () => Promise<unknown>): Promise<boolean> {
    working = true;
    try {
      took(await run() as PeaksPayload);
      return true;
    } catch (exc) {
      say("refusal", `refused: ${(exc as Error).message}`);
      return false;
    } finally {
      working = false;
    }
  }

  async function pick() {
    if (range === "bad") return;
    const body: Parameters<typeof api.pickPeaks>[0] = {
      shoulders, flag_contamination: contamination,
      ...(range ? { two_theta_range: range } : {}),
    };
    if (await verb(() => api.pickPeaks(body))) {
      overruled = new Map();
      removed = 0;
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

  async function use(row: PeakRow, on: boolean) {
    const hard = row.flags.filter((f) => unusable.has(f) && f !== "excluded");
    keep = new Set([...keep, row.index]);
    if (await verb(() => api.flagPeak(row.index, { use_for_indexing: on }))) {
      const next = new Map(overruled);
      if (on && hard.length) next.set(row.index, hard);
      else if (!on) next.delete(row.index);
      overruled = next;
    }
  }

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
      <table class="lines">
        <thead>
          <tr><th class="ck"></th><th class="r">2θ</th><th class="r">d</th>
            <th class="r">Intensity</th><th>Note</th></tr>
        </thead>
        <tbody>
          {#each shown as row (row.index)}
            <tr class:off={!row.usable} class:sel={selected === row.index}
              onclick={(ev) => { if (!(ev.target as HTMLElement).closest("label")) frame(row); }}>
              <td class="ck"><label><input type="checkbox" checked={row.usable} {disabled}
                aria-label="Use {formatPosition(row.two_theta, null).value}° in the search"
                onchange={(ev) => use(row, (ev.target as HTMLInputElement).checked)} /></label></td>
              <td class="r num">{formatPosition(row.two_theta, null).value}<span class="u">°</span></td>
              <td class="r num">{row.d.toFixed(4)}{" "}<span class="u">Å</span></td>
              <td class="r num">{formatIntensity(row.intensity, imax, row.flags)}</td>
              <td class="note">{#each note(row) as w, i (i)}{#if i}, {/if}{#if w.key}<Help for={w.key}>{w.text}</Help>{:else}{w.text}{/if}{/each}</td>
            </tr>
          {/each}
        </tbody>
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
              line{edits === 1 ? "" : "s"} you added, moved, removed or ruled on.</span>
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
