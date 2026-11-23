<script lang="ts">
  /**
   * The series workflow's steps at `/next` (WP-2243, piece R7 of WP-2214's
   * plan), mounted across the model panel while the workflow is up.
   *
   * The design is round 12's (2026-11-08, closed "looks great"), restated in
   * WP-2243 § The design. Each step shows only what that step needs, and its
   * one action sits in a foot pinned under it: the workflow hides the action
   * bar, so that action is the view's one filled primary.
   *
   * Patterns. The files in series order: Add files… for many at once, Sort by
   * the axis, a typed coordinate per file and × to remove it (no drag to
   * reorder, call 15). Then the walk: the axis name and Order, and the
   * carried-over globs under More settings. The order is the series, so every
   * edit sends the whole list in one `PUT /api/series` and the answer replaces
   * this panel's list (WP-1016).
   *
   * Run. The run's table fills as fits land, folded from the events the page
   * already follows (`seriesrun.ts`), and the record replaces the fold once
   * the run ends. Stop keeps what finished (call 10).
   */
  import { onMount, untrack } from "svelte";

  import { api } from "../api";
  import { asRequest, sortByX, type SeriesEntry, type SeriesPattern,
           type SeriesSetup } from "../lib/series";
  import type { EngineEvent, RunState } from "../lib/stream";
  import type { Step } from "../lib/workflows";
  import type { Say } from "./console";
  import {
    ORDER, axisWord, emptyProgress, fitsDone, fold, inOrder, merged, rwpText, secondWalkDone,
    spanOf, startedFrom, walksOf, type RunProgress,
  } from "./seriesrun";

  let {
    step = 0,
    steps,
    busy = false,
    run = null,
    say = () => {},
    onstep = () => {},
    onrun = async () => {},
    onstop = () => {},
  }: {
    step?: number;
    steps: readonly Step[];
    busy?: boolean;
    /** the run frame, which says whether the run in flight is a series */
    run?: RunState | null;
    say?: Say;
    /** move the strip to another step */
    onstep?: (step: number) => void;
    /** start a run behind its call (the shell's, so the Console holds it) */
    onrun?: (body: Record<string, unknown>, text: string) => Promise<void>;
    onstop?: () => void;
  } = $props();

  let setup = $state.raw<SeriesSetup | null>(null);
  let patterns = $state.raw<SeriesPattern[]>([]);
  let failure = $state("");
  let reading = $state("");
  let carryText = $state("");
  let moreOpen = $state(false);
  /** the record of the last series run in this session */
  let entries = $state.raw<SeriesEntry[] | null>(null);
  let cancelled = $state(false);
  /** the patterns the second walk fitted, from the record (`secondWalkDone`) */
  let backDone = $state.raw<Set<number>>(new Set());
  let progress = $state.raw<RunProgress>(emptyProgress());
  /** a series run this page started or saw in flight */
  let ran = $state(false);
  /** the list or the walk changed after the last run (call 13) */
  let changed = $state(false);
  let selected = $state<number | null>(null);
  let fileInput: HTMLInputElement | undefined = $state();
  /** the list and the walk the last run ran over, taken when its record is
   *  read: the Run step's rows are keyed by series index, so an edit after the
   *  run must not re-label them. Null while a run is in flight, when the
   *  server's list is the run's, since every edit is refused until it ends. */
  let ranOver = $state.raw<{ patterns: SeriesPattern[]; direction: string } | null>(null);
  /** this panel started the run now rising, so its progress is already reset */
  let startedHere = false;

  const settings = $derived(setup?.settings ?? null);
  const axis = $derived(settings?.x_label ?? "index");
  const span = $derived(spanOf(patterns));
  const sorted = $derived(inOrder(patterns));
  const running = $derived(busy && run?.run?.kind === "series");
  const editable = $derived(!busy && !reading);
  const walks = $derived(walksOf(settings?.direction ?? "forward"));
  const rows = $derived(ranOver?.patterns ?? patterns);
  const runDirection = $derived(ranOver?.direction ?? settings?.direction ?? "forward");
  const runWalks = $derived(walksOf(runDirection));
  /** a series needs two patterns to run */
  const few = $derived(patterns.length < 2);
  const heading = $derived(patterns.length
    ? `${patterns.length} file${patterns.length === 1 ? "" : "s"}`
      + (span ? ` · ${span[0].toFixed(1)}–${span[1].toFixed(1)}° 2θ` : "") : "");

  onMount(() => {
    void load();
  });

  /** Fold one event the page follows; the shell hands every one in. */
  export function event(e: EngineEvent) {
    const next = fold(progress, e);
    if (next !== progress) {
      progress = next;
      ran = true;
    }
  }

  /** Forget the last run's table, for a run about to fill a new one. */
  function clearRun() {
    ranOver = null;
    progress = emptyProgress();
    entries = null;
    cancelled = false;
    backDone = new Set();
  }

  // a series run ending reads its record: the entries replace the fold's guess
  let wasRunning = false;
  $effect(() => {
    const now = running;
    untrack(() => {
      if (now) ran = true;
      // a run another page started folds onto an empty table, never onto the
      // last run's fits and rungs
      if (now && !wasRunning && !startedHere) clearRun();
      if (now) startedHere = false;
      // a run that failed left the server's record at the run before it
      if (wasRunning && !now) void load(run?.run?.status !== "failed");
      wasRunning = now;
    });
  });

  async function load(answer = true) {
    try {
      absorb(await api.series() as SeriesSetup);
      failure = "";
      if (setup?.running) await replay();
      // while a run is in flight the record is still the run before it
      else if (answer && setup?.has_result) await loadAnswer();
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  /** A panel mounted mid-run folds the run's buffered events, which the
   *  server clears when a run starts; the shell hands in the rest. */
  async function replay() {
    const { events } = await api.events(0) as { events: EngineEvent[] };
    let p = progress;
    for (const e of events) p = fold(p, e);
    if (p !== progress) {
      progress = p;
      ran = true;
    }
  }

  async function loadAnswer() {
    try {
      const answer = await api.seriesResult();
      entries = answer.result.entries as SeriesEntry[];
      cancelled = (answer.result.diagnostics ?? [])
        .some((d: { code: string }) => d.code === "SEQUENTIAL_CANCELLED");
      // the list as the run left it (no edit lands while one is in flight),
      // and the walk the record says ran
      const direction = settings?.direction ?? "forward";
      ranOver ??= { patterns, direction: answer.has_backward ? "both"
        : direction === "both" ? "forward" : direction };
      progress = merged(progress, entries, ranOver.direction);
      backDone = answer.has_backward
        ? secondWalkDone(entries, answer.trajectories?.[0]) : new Set();
      ran = true;
    } catch {
      // nothing has run in this session: the Run step's empty state
    }
  }

  /** The server's list becomes this panel's, never merged (WP-1016). */
  function absorb(next: SeriesSetup) {
    setup = next;
    patterns = [...next.patterns];
    carryText = next.settings.carry.join(" ");
  }

  /** Send the list and the settings as one PUT: the order is the series. */
  async function put(extra: Record<string, unknown> = {}): Promise<boolean> {
    failure = "";
    try {
      absorb(await api.putSeries({ patterns: asRequest(patterns), ...extra }) as SeriesSetup);
      if (ran) changed = true;
      return true;
    } catch (error) {
      failure = (error as Error).message;
      // the list the server holds is still the series
      if (setup) patterns = [...setup.patterns];
      return false;
    }
  }

  /** Read N files, then send the list once. One at a time, so a file that
   *  does not read names itself and the files before it stay. */
  async function addFiles(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = "";   // the same file twice is a legitimate series member
    if (!files.length) return;
    failure = "";
    const added: SeriesPattern[] = [];
    for (const file of files) {
      reading = file.name;
      try {
        const preview = await api.uploadFile("pattern", file);
        added.push({
          upload: preview.upload, filename: preview.filename,
          label: preview.filename.replace(/\.[^.]+$/, ""), x: null,
          reader: preview.format.name, reader_options: preview.reader_options ?? {},
          n_points: preview.n_points, two_theta_range: preview.two_theta_range,
          has_sigma: preview.has_sigma,
        });
      } catch (error) {
        failure = `${file.name}: ${(error as Error).message}`;
        break;
      }
    }
    reading = "";
    if (added.length) {
      patterns = [...patterns, ...added];
      if (await put()) say("comment", `# added ${added.length} pattern${added.length === 1 ? "" : "s"} to the series`);
    }
  }

  function remove(index: number) {
    patterns = patterns.filter((_, i) => i !== index);
    if (selected === index) selected = null;
    else if (selected !== null && selected > index) selected -= 1;
    void put();
  }

  function setX(index: number, box: HTMLInputElement) {
    const text = box.value.trim();
    const value = text === "" ? null : Number(text);
    if (value !== null && !Number.isFinite(value)) {
      failure = `"${box.value}" is not a number.`;
      box.value = patterns[index].x == null ? "" : String(patterns[index].x);
      return;
    }
    if (value === patterns[index].x) return;
    patterns = patterns.map((p, i) => (i === index ? { ...p, x: value } : p));
    void put();
  }

  function sort() {
    patterns = sortByX(patterns);
    selected = null;
    void put();
  }

  function setAxis(box: HTMLInputElement) {
    const text = box.value.trim();
    if (!text || text === settings?.x_label) {
      box.value = settings?.x_label ?? "";
      return;
    }
    void put({ x_label: text });
  }

  function setCarry(box: HTMLInputElement) {
    const globs = box.value.split(/[\s,]+/).filter(Boolean);
    if (!globs.length) {
      failure = "Name at least one parameter or glob; * carries everything.";
      box.value = carryText;
      return;
    }
    if (globs.join(" ") === carryText) return;
    void put({ carry: globs });
  }

  /** The call the Console shows for a run, in the package's words. */
  function callText(): string {
    const x = setup?.has_x ? `x=[…], x_label=${JSON.stringify(axis)}, ` : "";
    return `rx.refine_sequential(patterns, structure, instrument, ${x}`
      + `carry=${JSON.stringify(settings?.carry ?? ["*"])}, `
      + `direction=${JSON.stringify(settings?.direction ?? "forward")})`;
  }

  async function start() {
    failure = "";
    const was = { progress, entries, cancelled, backDone, ranOver };
    clearRun();
    changed = false;
    startedHere = true;
    onstep(2);
    try {
      await onrun({ kind: "series" }, callText());
      ran = true;
    } catch (error) {
      ({ progress, entries, cancelled, backDone, ranOver } = was);
      startedHere = false;
      failure = (error as Error).message;
    }
  }

  /** A coordinate as the tables print it. */
  const xText = (x: number | null | undefined) => (x == null ? "" : String(x));

  const nFits = $derived((progress.n ?? rows.length) * runWalks);
  const nDone = $derived(fitsDone(progress));
  const firstPass = $derived(progress.passes[0] ?? (runDirection === "backward" ? "backward" : "forward"));
  const secondPass = $derived(runWalks > 1 ? (firstPass === "forward" ? "backward" : "forward") : null);
  const nConverged = $derived(entries ? entries.filter((e) => e.status === "converged").length : 0);
  const status = $derived.by(() => {
    if (running) {
      const c = progress.current;
      if (!c) return `Fitting · ${nDone} of ${nFits}`;
      const x = rows[c.index]?.x;
      const walk = runWalks > 1 ? ` · ${c.pass === firstPass ? "first walk" : "second walk"}` : "";
      return `Fitting ${c.label}${x == null ? "" : ` · ${x}`}${walk} · ${Math.min(nDone + 1, nFits)} of ${nFits}`;
    }
    if (cancelled) return `Stopped · ${nDone} of ${nFits} fits`;
    if (entries) return `Finished · ${nConverged} of ${rows.length} converged`;
    return "";
  });
  /** a finished run is whole, even read by a page that did not follow it */
  const fraction = $derived(!running && entries && !cancelled ? 1
    : nFits ? Math.min(1, nDone / nFits) : 0);
</script>

<div class="steppane">
  {#if !steps[step]?.built}
    <div class="body"><p class="box">{steps[step]?.body}</p></div>
  {:else if step === 0}
    <div class="body">
      <h3>Patterns{#if heading}<span class="nt">{heading}</span>{/if}</h3>
      <div class="field">
        <input type="file" multiple hidden bind:this={fileInput} onchange={addFiles} />
        <button class="ghost" disabled={!editable} onclick={() => fileInput?.click()}>Add files…</button>
        {#if patterns.length}
          <button class="ghost" disabled={!editable || sorted} onclick={sort}
            title={sorted ? `Already in order of ${axis}` : `Put the patterns in order of ${axis}`}
            >Sort by {axisWord(axis)}</button>
        {/if}
      </div>
      {#if patterns.length}
        <table class="rows">
          <thead>
            <tr><th class="r">#</th><th>File</th><th class="r">{axis}</th>
              <th class="r">Points</th><th class="x"></th></tr>
          </thead>
          <tbody>
            {#each patterns as p, i (p.upload + ":" + i)}
              <tr class:sel={selected === i} onclick={(ev) => {
                if (!(ev.target as HTMLElement).closest("input, button")) selected = i; }}>
                <td class="r num muted">{i + 1}</td>
                <td class="fname" title={p.filename}>{p.filename}</td>
                <td class="r"><input class="num coord" inputmode="decimal" value={xText(p.x)}
                  aria-label="{axis} of {p.label}" disabled={!editable}
                  onchange={(ev) => setX(i, ev.currentTarget)} /></td>
                <td class="r num">{p.n_points.toLocaleString("en")}</td>
                <td class="x"><button class="ib" aria-label="Remove {p.label}" title="Remove from the series"
                  disabled={!editable} onclick={() => remove(i)}>
                  <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" /></svg>
                </button></td>
              </tr>
            {/each}
          </tbody>
        </table>
        {#if setup?.sigma_mixed}
          <p class="warn">Some files carry esds and some do not, so the series is fitted under two weightings.</p>
        {/if}
      {:else}
        <p class="muted empty">No patterns yet.</p>
      {/if}
      <h3>Walk</h3>
      <div class="field">
        <span class="label">Axis</span>
        <input class="axis" value={axis} disabled={!editable} aria-label="What the series coordinate is called"
          onchange={(ev) => setAxis(ev.currentTarget)} />
      </div>
      <div class="field">
        <span class="label">Order</span>
        <span class="segmented" role="group" aria-label="Order">
          {#each ORDER.filter((o) => !setup || setup.choices.direction.includes(o.id)) as o (o.id)}
            <button class:on={settings?.direction === o.id} aria-pressed={settings?.direction === o.id}
              title={o.title} disabled={!editable}
              onclick={() => settings?.direction !== o.id && put({ direction: o.id })}>{o.words}</button>
          {/each}
        </span>
      </div>
      <details class="more" bind:open={moreOpen}>
        <summary>More settings</summary>
        <div class="field">
          <span class="label">Carried over</span>
          <input class="carry" value={carryText} disabled={!editable}
            aria-label="Parameters carried from one pattern to the next"
            onchange={(ev) => setCarry(ev.currentTarget)} />
        </div>
      </details>
      {#if failure}<p class="bad">{failure}</p>{/if}
    </div>
    <div class="foot">
      <button disabled={few} onclick={() => onstep(1)}>First fit</button>
      <button class="ghost" disabled={!editable || few} onclick={start}
        title="Run without a first fit: the first pattern starts from the model">Run series</button>
      <span class="muted">{#if reading}Reading {reading}…{:else if few}Needs two patterns{:else if changed}Changed since the last run{:else}{patterns.length} patterns · {walks === 2 ? "two walks" : "one walk"}{/if}</span>
    </div>
  {:else if step === 2}
    {#if !ran && !entries}
      <div class="body"><p class="muted empty">Not run yet.</p>
        {#if failure}<p class="bad">{failure}</p>{/if}</div>
      <div class="foot">
        <button disabled={!editable || few} onclick={start}>Run series</button>
      </div>
    {:else}
      <div class="body">
        <p class="status">{status}</p>
        <div class="gauge" role="progressbar" aria-label="Series progress" aria-valuemin="0"
          aria-valuemax="100" aria-valuenow={Math.round(fraction * 100)}>
          <i style:width="{(fraction * 100).toFixed(1)}%"></i></div>
        <table class="rows">
          <thead>
            <tr><th class="r">#</th><th>Pattern</th><th class="r">{axis}</th>
              <th class="r">Rwp (%)</th><th>Started from</th>
              {#if secondPass}<th class="r">Second walk</th>{/if}</tr>
          </thead>
          <tbody>
            {#each rows as p, i (p.upload + ":" + i)}
              {@const fit = progress.fits[firstPass]?.[i]}
              {@const cur = running && progress.current?.index === i ? progress.current.pass : null}
              <tr class:sel={selected === i} onclick={() => (selected = i)}>
                <td class="r num muted">{i + 1}</td>
                <td class="fname">{p.label}</td>
                <td class="r num">{xText(p.x)}</td>
                <td class="r num">{fit ? rwpText(fit.rwp) : cur === firstPass ? "…" : ""}</td>
                <td>{fit ? startedFrom(fit.rung) : ""}</td>
                {#if secondPass}
                  <td class="r">{progress.fits[secondPass]?.[i] || backDone.has(i) ? "✓"
                    : cur === secondPass ? "…" : ""}</td>
                {/if}
              </tr>
            {/each}
          </tbody>
        </table>
        {#if failure}<p class="bad">{failure}</p>{/if}
      </div>
      <div class="foot">
        {#if running}
          <button class="ghost" disabled={run?.state === "cancelling"} onclick={onstop}
            title="Patterns already fitted keep their results">Stop</button>
        {:else}
          <button onclick={() => onstep(3)}>See results</button>
          <button class="ghost" disabled={!editable || few} onclick={start}
            title="Replaces these results">Run again</button>
        {/if}
      </div>
    {/if}
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
    margin: 14px 0 6px;
  }

  h3 .nt {
    margin-left: 8px;
    font-weight: 400;
    color: var(--muted);
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

  input.axis {
    width: 12ch;
  }

  input.carry {
    width: 20ch;
  }

  table.rows {
    width: 100%;
    margin-top: 4px;
    border-collapse: collapse;
  }

  .rows th {
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

  .rows td {
    height: 30px;
    padding: 1px 6px;
    white-space: nowrap;
    vertical-align: middle;
  }

  .rows .r {
    text-align: right;
  }

  .rows td.fname {
    max-width: 24ch;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .rows .x {
    width: 34px;
    padding: 0;
    text-align: center;
  }

  .rows input.coord {
    width: 9ch;
    height: 26px;
    text-align: right;
  }

  .rows tbody tr {
    cursor: pointer;
  }

  @media (hover: hover) {
    .rows tbody tr:hover td {
      background: var(--hover);
    }
  }

  .rows tr.sel td {
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }

  .num {
    font-family: var(--mono-family);
  }

  .muted {
    color: var(--muted);
  }

  .empty {
    margin: 14px 0;
  }

  .warn {
    margin: 8px 0;
    color: var(--warn);
  }

  .bad {
    margin: 8px 0;
    color: var(--bad);
  }

  .more summary {
    margin: 12px 0 4px;
    cursor: pointer;
  }

  .status {
    margin: 10px 0 6px;
  }

  /* the run's progress: a hairline track, filled in the accent */
  .gauge {
    height: 6px;
    margin-bottom: 10px;
    border-radius: 3px;
    background: var(--line);
    overflow: hidden;
  }

  /* the filled part is an accent wash, the pages' one way of laying the
     accent over an area (test_gui_palette: never a solid accent fill) */
  .gauge i {
    display: block;
    height: 100%;
    background: color-mix(in srgb, var(--accent) 70%, var(--line));
  }
</style>
