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
   *
   * Results. The record read whole (`seriesresults.ts`): three label-value
   * rows with no verdict (call 11), the last two with Plot, one row per
   * pattern, every value at the selected pattern with a tick that plots it
   * on Trends (call 20), that pattern's warnings, and the series' warnings and
   * largest steps under disclosures. A summary row's Plot, and a row of the
   * largest steps, plots its value, selects the pattern it names and shows
   * Trends (`ongraph`); what Trends plots is this panel's (`ontrends`).
   *
   * One selected pattern links the tables and the Pattern graph (round 12,
   * calls 2 and 9; `seriespattern.ts`). A row click, ‹ › in the graph's title
   * and ↑ ↓ move it; during a run it follows the pattern being fitted until a
   * row click, and "Follow the run" resumes. The panel hands the frame what
   * the graph draws (`onview`), mid-run too, and the Map the row it marks
   * (`onmark`); a Map click comes back through `select`.
   */
  import { onMount, untrack } from "svelte";

  import { api } from "../api";
  import { asRequest, sortByX, type SeriesEntry, type SeriesPattern,
           type SeriesSetup } from "../lib/series";
  import type { EngineEvent, RunState } from "../lib/stream";
  import type { Step } from "../lib/workflows";
  import type { Say } from "./console";
  import {
    answerOf, countText, largestGap, pathName, seriesWarnings, sizedSteps, valueGroups,
    warningsOf, type SeriesAnswer,
  } from "./seriesresults";
  import { esdText } from "../lib/series";
  import {
    ORDER, axisWord, emptyProgress, fitsDone, fittingText, fold, inOrder, merged, rwpText,
    secondWalkDone, spanOf, startedFrom, walksOf, type RunProgress,
  } from "./seriesrun";
  import {
    drawnPlace, loadMember, markedIn, sameMembers, stepped, subText,
    type ListName, type Selection, type SeriesView,
  } from "./seriespattern";
  import { defaultPlotted, type TrendsView } from "./seriestrends";

  let {
    step = 0,
    steps,
    busy = false,
    run = null,
    say = () => {},
    onstep = () => {},
    onrun = async () => {},
    onstop = () => {},
    onview = () => {},
    ontrends = () => {},
    ongraph = () => {},
    onstaged = () => {},
    onmark = () => {},
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
    /** what the Pattern graph draws for the series, or null with no pattern */
    onview?: (view: SeriesView | null) => void;
    /** what the Trends graph draws, or null with no record (task 6) */
    ontrends?: (view: TrendsView | null) => void;
    /** show a graph tab: a summary row's Plot shows Trends */
    ongraph?: (tab: "trends") => void;
    /** the server took a new list or walk, so the Map asks again */
    onstaged?: () => void;
    /** the row the Map marks: the drawn pattern's place in the staged list,
     *  or null while the drawn one is the run's on a list since edited */
    onmark?: (staged: number | null) => void;
  } = $props();

  let setup = $state.raw<SeriesSetup | null>(null);
  let patterns = $state.raw<SeriesPattern[]>([]);
  let failure = $state("");
  let reading = $state("");
  let carryText = $state("");
  let moreOpen = $state(false);
  /** the record of the last series run in this session */
  let entries = $state.raw<SeriesEntry[] | null>(null);
  /** the record's answer whole, which the Results step reads */
  let answer = $state.raw<SeriesAnswer | null>(null);
  let cancelled = $state(false);
  /** the patterns the second walk fitted, from the record (`secondWalkDone`) */
  let backDone = $state.raw<Set<number>>(new Set());
  let progress = $state.raw<RunProgress>(emptyProgress());
  /** a series run this page started or saw in flight */
  let ran = $state(false);
  /** the list or the walk changed after the last run (call 13) */
  let changed = $state(false);
  /** the pattern chosen, on the list it was chosen on; null draws the first */
  let sel = $state.raw<Selection | null>(null);
  /** the selection moves with the pattern being fitted (call 9) */
  let follow = $state(false);
  /** a run has ended and its record is being read: the run's list still holds */
  let awaiting = $state(false);
  let fileInput: HTMLInputElement | undefined = $state();
  /** the list and the walk the last run ran over, taken when its record is
   *  read: the Run step's rows are keyed by series index, so an edit after the
   *  run must not re-label them. Null while a run is in flight, when the
   *  server's list is the run's, since every edit is refused until it ends. */
  let ranOver = $state.raw<{ patterns: SeriesPattern[]; direction: string } | null>(null);
  /** this panel started the run now rising, so its progress is already reset */
  let startedHere = false;
  /** the values Trends plots, in the order they were ticked; Rwp and the
   *  first phase's cell until a tick changes them (call 12) */
  let plotted = $state.raw<string[]>([]);
  let plotTouched = false;

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
  const firstFitBuilt = $derived(!!steps[1]?.built);
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
    answer = null;
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
      if (now && !wasRunning) follow = true;
      if (now) startedHere = false;
      // a run that failed left the server's record at the run before it
      if (wasRunning && !now) {
        // only a run whose record will be read keeps its list meanwhile: a
        // failed one left the server at the run before it, which is not the
        // list this panel shows
        const read = run?.run?.status !== "failed";
        awaiting = read;
        void load(read).finally(() => (awaiting = false));
      }
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
      const payload = await api.seriesResult();
      answer = answerOf(payload);
      entries = answer.entries;
      // a run keeps what was ticked, less the values its record lacks
      const has = new Set(["rwp", "gof", ...answer.trajectories.map((t) => t.path)]);
      plotted = plotTouched ? plotted.filter((p) => has.has(p)) : defaultPlotted(answer);
      cancelled = (payload.result.diagnostics ?? [])
        .some((d: { code: string }) => d.code === "SEQUENTIAL_CANCELLED");
      // the list as the run left it (no edit lands while one is in flight),
      // and the walk the record says ran
      const direction = settings?.direction ?? "forward";
      ranOver ??= { patterns: runList(payload), direction: payload.has_backward ? "both"
        : direction === "both" ? "forward" : direction };
      progress = merged(progress, entries, ranOver.direction);
      backDone = payload.has_backward
        ? secondWalkDone(entries, payload.trajectories?.[0]) : new Set();
      ran = true;
    } catch {
      // nothing has run in this session: the Run step's empty state
    }
  }

  /** The list the record's run fitted, for a page that did not follow it:
   *  the staged list while the record's labels agree with it place by place,
   *  else the record's own labels and coordinates. After an edit and a
   *  reload the staged list is not the run's, and the graph's run-list fetch
   *  must not draw one file under another's name. */
  function runList(payload: any): SeriesPattern[] {
    const named = new Map<number, { label: string; x: number | null }>();
    for (const e of [...(payload.result.entries ?? []), ...(payload.result.failures ?? [])]) {
      named.set(e.index, { label: e.label, x: e.x ?? null });
    }
    const agree = [...named].every(([k, m]) => patterns[k]?.label === m.label);
    if (agree) return patterns;
    const n = Math.max(...named.keys()) + 1;
    return Array.from({ length: n }, (_, k) => ({
      upload: `run:${k}`, filename: named.get(k)?.label ?? `#${k + 1}`,
      label: named.get(k)?.label ?? `#${k + 1}`, x: named.get(k)?.x ?? null,
      reader: "", reader_options: {}, n_points: 0, two_theta_range: [0, 0], has_sigma: false,
    }));
  }

  /** The server's list becomes this panel's, never merged (WP-1016). */
  function absorb(next: SeriesSetup) {
    setup = next;
    patterns = [...next.patterns];
    carryText = next.settings.carry.join(" ");
  }

  /** the PUTs this panel has sent, and the one now on the wire */
  let sent = 0;
  let wire: Promise<unknown> = Promise.resolve();

  /** Send the list and the settings as one PUT: the order is the series.
   *  The body is the list as it stands now. The PUTs go one after another,
   *  and only the last one's answer becomes the panel's list: an earlier
   *  answer lacks an edit typed while it was on the wire, and absorbing it
   *  would drop that edit from every later PUT (gui/CLAUDE.md § Svelte and
   *  browser traps, a stale response is dropped). */
  async function put(extra: Record<string, unknown> = {}): Promise<boolean> {
    failure = "";
    const mine = ++sent;
    const body = { patterns: asRequest(patterns), ...extra };
    const answer = wire.then(() => api.putSeries(body));
    wire = answer.catch(() => {});
    try {
      const next = await answer as SeriesSetup;
      // an earlier answer is still what the server holds until the next one
      // lands, so a later PUT that fails reverts to it, never to the list
      // before it
      if (mine === sent) absorb(next);
      else setup = next;
      onstaged();
      if (ran) changed = true;
      return true;
    } catch (error) {
      failure = (error as Error).message;
      // a later PUT carries this one's list, so only the last reverts it
      if (mine !== sent) return false;
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
    // a place on the run's list stays: that list did not change
    if (sel?.of === "staged" && sel.index === index) sel = null;
    else if (sel?.of === "staged" && sel.index > index) sel = { of: "staged", index: sel.index - 1 };
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
    if (sel?.of === "staged") sel = null;
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
    const was = { progress, entries, answer, cancelled, backDone, ranOver };
    clearRun();
    changed = false;
    startedHere = true;
    onstep(2);
    try {
      await onrun({ kind: "series" }, callText());
      ran = true;
    } catch (error) {
      ({ progress, entries, answer, cancelled, backDone, ranOver } = was);
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
    if (running) return fittingText(progress, runWalks, firstPass, (i) => rows[i]?.x);
    if (cancelled) return `Stopped · ${nDone} of ${nFits} fits`;
    if (entries) return `Finished · ${nConverged} of ${rows.length} converged`;
    return "";
  });
  // -- the selected pattern (seriespattern.ts) ---------------------------

  /** the run's list is the one in flight, or the last run's */
  const hasRun = $derived(running || awaiting || ranOver !== null);
  /** the staged list holds the files the run fitted, in its places */
  const same = $derived(!ranOver || sameMembers(ranOver.patterns, patterns));
  const drawn = $derived(drawnPlace(sel, hasRun, same, rows.length, patterns.length));
  const markStaged = $derived(markedIn(drawn, "staged", same));
  const markRun = $derived(markedIn(drawn, "run", same));

  function choose(of: ListName, index: number) {
    sel = { of, index };
    follow = false;
  }

  /** ‹ › and ↑ ↓: the next pattern or the one before, in the list drawn. */
  export function move(delta: number) {
    if (!drawn) return;
    const n = drawn.of === "run" ? rows.length : patterns.length;
    choose(drawn.of, stepped(drawn.index, delta, n));
  }

  // during a run the selection is the pattern being fitted (call 9)
  $effect(() => {
    const c = progress.current ?? progress.last;
    if (!running || !follow || !c) return;
    untrack(() => {
      if (sel?.of !== "run" || sel.index !== c.index) sel = { of: "run", index: c.index };
    });
  });

  /** the pattern the Results step reads, the first until a row is clicked */
  const at = $derived(drawn?.of === "run" ? drawn.index : entries?.[0]?.index ?? null);
  const atEntry = $derived(entries?.find((e) => e.index === at) ?? null);
  const gap = $derived(answer ? largestGap(answer.gaps) : null);
  const bigSteps = $derived(answer ? sizedSteps(answer.steps) : []);
  /** a pattern's coordinate: the record's, else the list's as it ran */
  const xOf = (index: number) => entries?.find((e) => e.index === index)?.x ?? rows[index]?.x ?? null;
  /** a coordinate where a line needs one, the pattern's number without */
  const xAt = (index: number) => xOf(index) ?? `#${index + 1}`;
  const atX = $derived(at === null ? null : xOf(at));
  const atName = $derived(atEntry ? `${atEntry.label}${atX == null ? "" : `, ${atX}`}` : "");
  const view = $derived.by((): SeriesView | null => {
    if (!drawn) return null;
    const { of, index } = drawn;
    const list = of === "run" ? rows : patterns;
    const p = list[index];
    if (!p) return null;
    const fit = of === "run" ? progress.fits[firstPass]?.[index] ?? null : null;
    const fitting = of === "run" && running && progress.current?.index === index;
    return {
      // the key moves when the fit lands or the record replaces it, so the
      // graph asks again then and never on a redraw
      source: { key: `${of}:${index}:${p.upload}:${fit ? `${fit.rwp}:${fit.rung}` : "-"}`,
                load: () => loadMember(() => api.seriesPattern(index, of), !!fit) },
      name: p.label,
      sub: subText(of === "run" ? xOf(index) : p.x, index, list.length, fit?.rwp, fitting),
      canPrev: index > 0,
      canNext: index < list.length - 1,
    };
  });
  $effect(() => {
    const v = view;
    untrack(() => onview(v));
  });
  $effect(() => () => onview(null));
  $effect(() => {
    const m = markStaged;
    untrack(() => onmark(m));
  });

  // -- Trends (task 6): the plotted values and the selection it marks -------

  /** Plot the paths on Trends, or take them off. */
  export function plot(paths: string[], on: boolean) {
    plotTouched = true;
    plotted = on ? [...plotted, ...paths.filter((p) => !plotted.includes(p))]
      : plotted.filter((p) => !paths.includes(p));
  }

  /** Select a pattern: a point click on Trends picks from the run's list,
   *  a row click on the Map from the staged one. */
  export function select(index: number, of: ListName = "run") {
    choose(of, index);
  }

  /** A summary row's Plot: the value on Trends, the pattern it names
   *  selected, and the graph switched to Trends (the prototype's). */
  function show(path: string, index: number) {
    plot([path], true);
    choose("run", index);
    ongraph("trends");
  }

  /** A tick in the Plot list plots on Trends and shows it (the prototype's). */
  function tick(path: string, on: boolean) {
    plot([path], on);
    ongraph("trends");
  }

  const trends = $derived.by((): TrendsView | null => {
    if (!answer) return null;
    const selected = drawn?.of === "run" ? drawn.index : null;
    const e = answer.entries.find((x) => x.index === selected);
    return {
      answer, plotted, selected,
      name: selected === null ? "" : e?.label ?? rows[selected]?.label ?? "",
      x: selected === null ? null : xOf(selected),
      canPrev: selected !== null && selected > 0,
      canNext: selected !== null && selected < rows.length - 1,
      axis,
    };
  });
  $effect(() => {
    const t = trends;
    untrack(() => ontrends(t));
  });
  $effect(() => () => ontrends(null));

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
              <tr class:sel={markStaged === i} onclick={(ev) => {
                if (!(ev.target as HTMLElement).closest("input, button")) choose("staged", i); }}>
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
      <!-- First fit is the view's one primary once its step is built; until
           then Run series is, as in the Run step's foot -->
      <button class:ghost={!firstFitBuilt} disabled={few} onclick={() => onstep(1)}>First fit</button>
      <button class:ghost={firstFitBuilt} disabled={!editable || few} onclick={start}
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
        <p class="status">{status}{#if running && !follow}{" · "}<button class="link"
            title="Move the selection with the pattern being fitted"
            onclick={() => (follow = true)}>Follow the run</button>{/if}</p>
        <div class="gauge" role="progressbar" aria-label="Series progress" aria-valuemin="0"
          aria-valuemax="100" aria-valuenow={Math.round(fraction * 100)}>
          <i style:width="{(fraction * 100).toFixed(1)}%"></i></div>
        <table class="rows">
          <thead>
            <tr><th class="r">#</th><th>Pattern</th><th class="r">{axis}</th>
              <th class="r">Rwp (%)</th><th>Started from</th>
              {#if secondPass}<th class="r">Second walk Rwp (%)</th>{/if}</tr>
          </thead>
          <tbody>
            {#each rows as p, i (p.upload + ":" + i)}
              {@const fit = progress.fits[firstPass]?.[i]}
              {@const cur = running && progress.current?.index === i ? progress.current.pass : null}
              <tr class:sel={markRun === i} onclick={() => choose("run", i)}>
                <td class="r num muted">{i + 1}</td>
                <td class="fname">{p.label}</td>
                <td class="r num">{xText(p.x)}</td>
                <td class="r num">{fit ? rwpText(fit.rwp) : cur === firstPass ? "…" : ""}</td>
                <td>{fit ? startedFrom(fit.rung) : ""}</td>
                {#if secondPass}
                  {@const back = progress.fits[secondPass]?.[i]}
                  <!-- the second walk's Rwp as its fit lands; a page that did
                       not follow the run reads only that the walk fitted it,
                       since the record keeps no second-walk fits -->
                  <td class="r num">{back ? rwpText(back.rwp) || "✓" : backDone.has(i) ? "✓"
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
  {:else if step === 3}
    {#if !answer}
      <div class="body"><p class="muted empty">{running ? "Running. The results appear when the run ends." : "Not run yet."}</p>
        {#if failure}<p class="bad">{failure}</p>{/if}</div>
      <div class="foot">
        <button disabled={!editable || few} onclick={start}>Run series</button>
      </div>
    {:else}
      {@const a = answer}
      <div class="body">
        <dl class="kv summary">
          <dt>Converged</dt>
          <dd><span class="num">{nConverged}</span> of <span class="num">{a.entries.length}</span>{#if a.entries.length < rows.length}{" "}fitted{/if}</dd>
          {#if gap}
            <dt>Largest walk gap</dt>
            <dd>{pathName(gap.path, a)} · {xAt(gap.index)} · <span class="num">{esdText(gap.gap_esd!)}</span> esd
              <button class="link" title="Plot this value on Trends"
                onclick={() => show(gap.path, gap.index)}>Plot</button></dd>
          {/if}
          {#if bigSteps[0]}
            {@const s = bigSteps[0]}
            <dt>Largest step</dt>
            <dd>{pathName(s.path, a)} · {xAt(s.indices[0])} → {xAt(s.indices[1])} · <span class="num">{esdText(s.size_esd!)}</span> esd
              <button class="link" title="Plot this value on Trends"
                onclick={() => show(s.path, s.indices[1])}>Plot</button></dd>
          {/if}
        </dl>
        {#if changed}<p class="warn">Changed since this run</p>{/if}
        <h3>Patterns</h3>
        <table class="rows">
          <thead>
            <tr><th class="r">#</th><th class="r">{axis}</th><th class="r">Rwp (%)</th>
              <th class="r">GoF</th><th>Started from</th><th class="r">Warnings</th></tr>
          </thead>
          <tbody>
            {#each rows as p, i (p.upload + ":" + i)}
              {@const e = a.entries.find((x) => x.index === i)}
              {@const nw = warningsOf(e).length}
              <tr class:sel={at === i} onclick={() => choose("run", i)}>
                <td class="r num muted">{i + 1}</td>
                <td class="r num">{xText(e?.x ?? p.x)}</td>
                <td class="r num">{e?.statistics ? rwpText(e.statistics.rwp) : "—"}</td>
                <td class="r num">{e?.statistics ? e.statistics.gof.toFixed(2) : ""}</td>
                <td>{e ? startedFrom(e.rung) : "not fitted"}</td>
                <td class="r num">{nw || ""}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        <h3>Plot{#if atName}<span class="nt">values at {atName}</span>{/if}</h3>
        <table class="rows values">
          <tbody>
            {#each valueGroups(a, at) as g (g.key)}
              <tr class="gh"><td colspan="3">{g.title}</td></tr>
              {#each g.rows as v (v.path)}
                {@const on = plotted.includes(v.path)}
                <!-- a tick plots the value on Trends; the row is the target too -->
                <tr onclick={(ev) => { if (!(ev.target as HTMLElement).closest("input")) tick(v.path, !on); }}>
                  <td class="ck"><input type="checkbox" checked={on} aria-label="Plot {g.key === '#fit' ? v.name : pathName(v.path, a)}"
                    onchange={(ev) => tick(v.path, ev.currentTarget.checked)} /></td>
                  <td>{v.name}{#if v.count < v.n}<span class="nt num">{v.count}/{v.n}</span>{/if}</td>
                  <td class="r num">{v.value}</td>
                </tr>
              {/each}
            {/each}
          </tbody>
        </table>
        {#if atEntry}
          <h3>{atEntry.label}{#if atX != null}<span class="nt">{atX}</span>{/if}</h3>
          {#each warningsOf(atEntry) as d, k (k)}
            <p class="dg"><b>{d.code}</b> {d.message}</p>
          {:else}
            <p class="muted">No warnings.</p>
          {/each}
        {/if}
        {#if seriesWarnings(a.codes).length}
          <details class="notes">
            <summary>Warnings across the series</summary>
            {#each seriesWarnings(a.codes).slice(0, 8) as c, k (k)}
              <p class="dg"><b>{c.code}</b>{#if c.path}{" "}<span class="muted">{c.path}</span>{/if}: {countText(c)}</p>
            {/each}
          </details>
        {/if}
        {#if bigSteps.length}
          <details class="notes">
            <summary>Largest steps between neighbours</summary>
            <table class="rows">
              <tbody>
                {#each bigSteps.slice(0, 10) as s, k (k)}
                  <tr onclick={() => show(s.path, s.indices[1])}>
                    <td>{pathName(s.path, a)}</td>
                    <td class="muted">{xAt(s.indices[0])} → {xAt(s.indices[1])}</td>
                    <td class="r num">{esdText(s.size_esd!)} esd</td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </details>
        {/if}
        {#if failure}<p class="bad">{failure}</p>{/if}
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

  /* as wide as the carried-over globs' box, so "Temperature (K)" shows whole */
  input.axis {
    width: 20ch;
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

  /* the label-value rows, as the Candidates step's checks draw them */
  .kv {
    display: grid;
    grid-template-columns: max-content auto;
    gap: 4px 16px;
    margin: 10px 0 0;
  }

  .kv dt {
    color: var(--muted);
  }

  .kv dd {
    margin: 0;
  }

  .rows tr.gh td {
    padding-top: 10px;
    font-weight: 500;
    color: var(--muted);
  }

  .rows .ck {
    width: 26px;
    padding: 0 0 0 2px;
  }
  .rows .ck input {
    margin: 0;
    vertical-align: middle;
  }
  .kv dd .link {
    margin-left: 8px;
  }

  .rows .nt {
    margin-left: 8px;
    color: var(--muted);
  }

  .dg {
    margin: 6px 0 0;
  }

  details.notes {
    margin: 12px 0;
    color: var(--muted);
  }

  details.notes summary {
    cursor: pointer;
    color: var(--fg);
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
