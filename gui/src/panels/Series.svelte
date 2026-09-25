<script lang="ts">
  /**
   * An in-situ ramp or a parametric sweep, driven from the GUI — WP-1016's tab.
   *
   * A series is N *separate* refinements chained by a warm start, and this panel
   * is built around the one thing that makes that dangerous: a sequential fit is
   * path-dependent by construction, so **a smooth curve is exactly what a
   * poisoned chain produces** (WP-0505). Hence the shape of the panel. The
   * `direction="both"` verification pass has its own control and its answer —
   * `SEQUENTIAL_PATH_DEPENDENT` — is a banner at the top, not a diagnostic in a
   * strip; a flagged trajectory is *drawn* differently and has the other chain
   * drawn beside it, because the disagreement is the evidence.
   *
   * Two structural facts about where a series lives. Its patterns are staged
   * uploads and its answer is session-scoped (`ProjectDoc.patterns` stays length
   * 1), so there is nothing to save and nothing to reopen; and it inherits the
   * *project's* protocol — mode, plan, 2θ limits, excluded regions — which the
   * strip states rather than offering, because one protocol over N specimens is
   * what makes their trajectories comparable.
   *
   * The plot area holds one figure of the chart module (WP-1461) with two
   * views: a parameter's trajectory across the series (`rxplot.trajectory`), or
   * one pattern's own obs, calc and Δ (`rxplot.pattern`, over the member's
   * curves route). Selecting a pattern switches it, which is what "the plot
   * follows" means here. The figure's own `ResizeObserver` refits it when the
   * column does: 539 → 1480 px when the column takes the window.
   */
  import { onDestroy } from "svelte";

  import { api } from "../api";
  import Exports from "./Exports.svelte";
  import { seriesCompact } from "../lib/resize";
  import { curveColors, toggleCurve } from "../lib/plot";
  import {
    asRequest,
    axisTitle,
    memberLegend,
    moveBy,
    pointText,
    rankTrajectories,
    reseededFlags,
    sortByX,
    trajectoryLegend,
    trajectoryNote,
    unrecoveredFlags,
    type LegendEntry,
    type SeriesEntry,
    type SeriesPattern,
    type SeriesSetup,
    type Trajectory,
  } from "../lib/series";
  import type { RunState } from "../lib/stream";

  let {
    project,
    run,
    busy,
    simple = true,
    active = false,
    theme = "light",
    say = () => {},
  }: {
    project: any;
    run: RunState | null;
    busy: boolean;
    simple?: boolean;
    /** this tab is showing — the panel stays mounted, so a staged list and a
     *  half-typed coordinate survive a look at the plot */
    active?: boolean;
    theme?: string;
    say?: (line: string) => void;
  } = $props();

  let setup = $state<SeriesSetup | null>(null);
  let answer = $state<any>(null);
  let failure = $state("");
  let staging = $state("");
  /** the list as this panel is editing it; `null` until the server has spoken */
  let patterns = $state<SeriesPattern[]>([]);
  let carryText = $state("*");
  let selectedPath = $state<string>("");
  /** which pattern the plot and the history list are showing, or `null` for the
   *  trajectory view */
  let selectedPattern = $state<number | null>(null);
  let memberHistory = $state<any>(null);
  let plotNode = $state<HTMLDivElement | undefined>();
  /** the panel's own width, for the table reflow below its measured floor */
  let panelWidth = $state(0);
  let loaded = false;
  const compact = $derived(seriesCompact(panelWidth));

  const entries = $derived<SeriesEntry[]>(answer?.result?.entries ?? []);
  const trajectories = $derived<Trajectory[]>(answer?.trajectories ?? []);
  const ranked = $derived(rankTrajectories(trajectories));
  const flagged = $derived<string[]>(answer?.path_dependent ?? []);
  const sigmaBar = $derived<number>(answer?.path_dependence_sigma ?? 3);
  const diagnostics = $derived<any[]>(answer?.result?.diagnostics ?? []);
  /** every fence except the headline one, which has its own banner */
  const otherDiagnostics = $derived(
    diagnostics.filter((d) => d.code !== "SEQUENTIAL_PATH_DEPENDENT"));
  const current = $derived<Trajectory | null>(
    trajectories.find((t) => t.path === selectedPath)
      ?? ranked[0] ?? null);
  const running = $derived(busy && run?.run?.kind === "series");
  const settings = $derived(setup?.settings ?? null);
  const canRun = $derived(!busy && patterns.length >= 2);

  // The panel is mounted from boot (every tab is), so it must not fetch until it
  // is looked at — and then only once, because the setup is session state nothing
  // else moves.  `hasProject` rather than `project`: an effect reading the object
  // refires on every ui-only PATCH (WP-1027's third browser finding).
  const hasProject = $derived(Boolean(project));
  $effect(() => {
    if (active && hasProject && !loaded) {
      loaded = true;
      load();
    }
  });

  /** A run just ended (the shell calls this): the answer is the whole outcome,
   *  and `load` fetches it off `has_result` — so this is one call, not two. */
  export async function reload() {
    await load();
  }

  async function load() {
    try {
      absorb(await api.series());
      failure = "";
      // The session outlives this page, and a series answer lives in the
      // session: a reload — or a first look at this tab after a run started from
      // the palette — must not lose it.  The shell does the same for the indexing
      // answer on boot, and `has_result` is what makes it one fetch rather than a
      // 409 every time.
      if (setup?.has_result) await loadAnswer();
    } catch (error) {
      setup = null;
      failure = (error as Error).message;
      loaded = false;   // a failed first fetch must not make the tab inert
    }
  }

  /** The server's list becomes this panel's, always — never merged.
   *
   * The `.rxt` pane's rule at a smaller scale: the answer to a PUT is the whole
   * setup, so a local list that disagreed with it would be a second authority on
   * what the series *is*, and the labels are exactly where that bites (the server
   * disambiguates repeats by position, so the name it will run under is not
   * always the one that was typed). */
  function absorb(next: SeriesSetup) {
    setup = next;
    patterns = [...next.patterns];
    carryText = next.settings.carry.join(" ");
  }

  async function loadAnswer() {
    try {
      answer = await api.seriesResult();
      if (!selectedPath && answer.trajectories?.length) {
        selectedPath = rankTrajectories(answer.trajectories)[0].path;
      }
      draw();
    } catch {
      // NO_SERIES_RESULT — nothing has run in this session; an empty state
      answer = null;
    }
  }

  /** Send the list and the settings as one PUT — the order *is* the series. */
  async function put(extra: Record<string, unknown> = {}) {
    failure = "";
    try {
      absorb(await api.putSeries({ patterns: asRequest(patterns), ...extra }));
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  /** Stage N files, then send the list once.  Sequential on purpose: each upload
   *  is read server-side, and the line it prints is per file, so a bad file names
   *  itself instead of failing a batch. */
  async function addFiles(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const files = Array.from(input.files ?? []);
    input.value = "";   // the same file twice is a legitimate series member
    if (!files.length) return;
    failure = "";
    const added: SeriesPattern[] = [];
    for (const file of files) {
      staging = `reading ${file.name}…`;
      try {
        const preview = await api.uploadFile("pattern", file);
        added.push({
          upload: preview.upload, filename: preview.filename,
          label: preview.filename.replace(/\.[^.]+$/, ""), x: null,
          reader: preview.format.name,
          reader_options: preview.reader_options ?? {},
          n_points: preview.n_points,
          two_theta_range: preview.two_theta_range,
          has_sigma: preview.has_sigma,
        });
      } catch (error) {
        failure = (error as Error).message;
        break;
      }
    }
    staging = "";
    if (added.length) {
      patterns = [...patterns, ...added];
      await put();
      say(`# staged ${added.length} pattern(s) for the series`);
    }
  }

  const move = (index: number, delta: number) => {
    const next = moveBy(patterns, index, delta);
    if (next === patterns) return;   // nothing moved: no round trip
    patterns = next;
    put();
  };

  function remove(index: number) {
    patterns = patterns.filter((_, i) => i !== index);
    put();
  }

  function setX(index: number, text: string) {
    const value = text.trim() === "" ? null : Number(text);
    if (value !== null && !Number.isFinite(value)) {
      failure = `"${text}" is not a number`;
      return;
    }
    patterns = patterns.map((p, i) => (i === index ? { ...p, x: value } : p));
    put();
  }

  /** An emptied label is sent **empty**, not filled in here: the server's own
   *  rule is "blank means the file's stem", and a client that guessed would send
   *  `T300.xye` where the run uses `T300`. */
  function setLabel(index: number, text: string) {
    patterns = patterns.map((p, i) =>
      (i === index ? { ...p, label: text.trim() } : p));
    put();
  }

  const sort = () => { patterns = sortByX(patterns); put(); };

  const setSetting = (key: string, value: unknown) => put({ [key]: value });

  /** Read off the event target rather than a bound variable: every other field
   *  here does, and `bind:value` would make this depend on an `input` event
   *  having fired before the `change` — true when a human types and not when
   *  anything else sets the value. */
  function setCarry(text: string) {
    carryText = text;
    const globs = text.split(/\s+/).filter(Boolean);
    if (!globs.length) {
      failure = "carry needs at least one glob; ['*'] carries everything";
      return;
    }
    put({ carry: globs });
  }

  async function start() {
    failure = "";
    try {
      // no local run state: the state frame from the event stream is the one
      // truth about "is a run in flight" (App.svelte's founding rule)
      await api.runSeries();
      const x = setup?.has_x ? `x=[…], x_label=${JSON.stringify(settings?.x_label)}, ` : "";
      say(`refine_sequential(patterns, structure, instrument, ${x}`
          + `carry=${JSON.stringify(settings?.carry)}, `
          + `refit=${JSON.stringify(settings?.refit)}, `
          + `direction=${JSON.stringify(settings?.direction)})`);
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  /** Walk into one pattern: its own history tree, and the plot follows. */
  async function openPattern(index: number) {
    if (selectedPattern === index) {
      selectedPattern = null;
      memberHistory = null;
      draw();
      return;
    }
    selectedPattern = index;
    failure = "";
    try {
      memberHistory = await api.seriesHistory(index);
      say(`series.trees_[${index}]  # read-only: pinned to this pattern's `
          + `fingerprint, so its nodes cannot be checked out here`);
    } catch (error) {
      memberHistory = null;
      failure = (error as Error).message;
    }
    draw();
  }

  function showTrajectory(path: string) {
    selectedPath = path;
    selectedPattern = null;
    memberHistory = null;
    draw();
  }

  // -- the plot ------------------------------------------------------
  /** The figure on screen, the trajectory or one member's pattern. */
  let fig: any = null;

  /** An export's file name: the parameter the trajectory is of, or the pattern shown. */
  function exportName(): string {
    // numbered as the heading and the table number it, from 0
    if (selectedPattern !== null) return `series-pattern-${selectedPattern}`;
    return `trajectory-${(current?.path ?? "series").replace(/[^\w.-]+/g, "_")}`;
  }
  /** What its legend offers, and which of those the reader hid, for this view. */
  let legend = $state<LegendEntry[]>([]);
  let hidden = $state<string[]>([]);
  /** The point under the pointer on a trajectory, in the plot box's own px. */
  let tip = $state<{ text: string; left: number; top: number } | null>(null);
  /** Each draw takes a ticket, and one that has been overtaken builds nothing. */
  let drawing = 0;

  onDestroy(() => fig?.destroy());

  /** The inks, read when a figure is built and when the theme moves, never per paint. */
  function readColors() {
    const style = getComputedStyle(document.documentElement);
    const read = (name: string) => style.getPropertyValue(name);
    return { ...curveColors(read), warn: read("--warn").trim() || "#b7791f" };
  }
  let colors = readColors();

  /** The answer the figure on screen was drawn from. Showing the tab again
   *  keeps that figure, with the reader's zoom and hidden marks. */
  let drawnFrom: any = null;

  // a new answer is a new figure
  $effect(() => {
    void plotNode;
    if (active && answer !== drawnFrom) draw();
  });

  /** A canvas keeps the colours it was painted with, so a theme click
   *  repaints (WP-1029 q). One microtask first: the shell stamps the theme in
   *  an effect of the same flush (gui/CLAUDE.md). */
  $effect(() => {
    void theme;
    Promise.resolve().then(() => {
      colors = readColors();
      fig?.redraw();
    });
  });

  function toggle(id: string) {
    hidden = toggleCurve(hidden, id);
    fig?.setHidden(hidden);
  }

  async function draw() {
    if (!plotNode || !answer) return;
    const ticket = ++drawing;
    const chart = await import("../lib/seriesChart");
    let curves: any = null;
    const index = selectedPattern;
    if (index !== null) {
      try {
        curves = chart.unpack(await api.seriesCurves(index));
      } catch (error) {
        failure = (error as Error).message;
        return;
      }
    }
    if (ticket !== drawing || !plotNode) return;
    drawnFrom = answer;
    fig?.destroy();
    fig = null;
    tip = null;
    hidden = [];
    colors = readColors();
    if (index !== null) {
      const { arrays, header } = curves;
      legend = memberLegend(arrays.kept.length < arrays.two_theta.length,
                            "y_background" in arrays);
      fig = chart.mountMember(plotNode, curves, {
        colors: () => ({ ...colors, masked: colors.edge }),
        residual: "weighted",
        labels: { y: () => "counts",
                  resid: () => (header.weighted ? "Δ/σ" : "Δ/σ (Poisson)") },
      });
      return;
    }
    if (!current) return;
    const traj = current;
    const reseeded = reseededFlags(traj, entries);
    const unrecovered = unrecoveredFlags(traj, entries);
    legend = trajectoryLegend(traj, reseeded, unrecovered);
    fig = chart.mountTrajectory(plotNode, traj, {
      colors: () => ({ tone: traj.path_dependent ? colors.warn : colors.diff,
                       warn: colors.warn, muted: colors.edge }),
      dashed: traj.path_dependent,
      rings: reseeded,
      crosses: unrecovered,
      xLabel: traj.x_label,
      yLabel: axisTitle(traj),
    });
    fig.onPoint = (hit: any) => {
      if (!hit || !plotNode) { tip = null; return; }
      const over = fig.panes.traj.over.getBoundingClientRect();
      const box = plotNode.getBoundingClientRect();
      tip = { text: pointText(traj, hit.i, hit.chain),
              left: over.left - box.left + hit.left, top: over.top - box.top + hit.top };
    };
  }
</script>

<section bind:clientWidth={panelWidth}>
  <!-- the headline, not a footnote: the one check that separates a measured
       trajectory from an ordering artefact (WP-0505) -->
  {#if flagged.length}
    <p class="banner bad">
      <strong>{flagged.length} parameter{flagged.length === 1 ? "" : "s"}
        path-dependent</strong> — the forward and backward chains disagree by more
      than {sigmaBar}σ, so {flagged.length === 1 ? "its" : "their"} trajector{flagged.length === 1 ? "y is" : "ies are"}
      an artefact of the order the series was refined in, not a measurement.
      {#each flagged.slice(0, 6) as path (path)}
        <button class="ghost" onclick={() => showTrajectory(path)}
          title="show this trajectory with the backward chain beside it">{path}</button>
      {/each}
      {#if flagged.length > 6}<span class="muted">+{flagged.length - 6}</span>{/if}
    </p>
  {:else if answer?.has_backward}
    <p class="banner ok">
      Both chain directions agree within their esds — the trajectories below are
      measurements rather than ordering artefacts.
    </p>
  {/if}

  {#if failure}<p class="bad">{failure}</p>{/if}

  <h2>Patterns</h2>
  {#if setup}
    <p class="muted">
      A series is N separate refinements chained by a warm start — one history
      tree each, not one joint residual. It runs under <em>this project's</em>
      protocol ({setup.protocol.mode}{#if setup.protocol.plan}, {setup.protocol.plan}{/if},
      {setup.protocol.n_stages} stage{setup.protocol.n_stages === 1 ? "" : "s"})
      and warm-starts from its current model.
    </p>
  {/if}

  <div class="controls">
    <label class="file">
      <input type="file" multiple disabled={busy}
        onchange={addFiles} />
      <span>Add patterns…</span>
    </label>
    {#if patterns.some((p) => p.x !== null)}
      <button class="ghost" onclick={sort} disabled={busy}
        title="order the series by its coordinate — patterns with none keep their places at the end"
        >Sort by {settings?.x_label ?? "x"}</button>
    {/if}
    {#if staging}<span class="muted">{staging}</span>{/if}
  </div>

  {#if setup?.sigma_mixed}
    <p class="warn" title="the fit weights by the file's esd column when it
has one and by the Poisson √max(y,1) fallback otherwise, so a mixed series is
fitted under two weighting policies — a correctness property that is invisible
once the files are read">
      ⚠ these files disagree about carrying esds: part of this series will be
      weighted by measured σ and part by the Poisson fallback.
    </p>
  {/if}

  {#if !patterns.length}
    <p class="muted hint">
      No patterns staged. <strong>Add patterns…</strong> takes the ramp's files in
      one go; give each a coordinate (temperature, time, pressure) or leave them
      blank and the pattern index is the axis.
    </p>
  {:else}
    <!-- Below its measured floor the table drops the four descriptive columns
         (`lib/resize.ts:seriesCompact`) rather than side-scrolling: the reorder
         buttons are the last column and the panel's main verb, so scrolling put
         them off the right edge of a box a user then had to scroll to reorder a
         series. Nothing is lost — the four move into the label's tooltip. -->
    <div class="scroll">
      <table class="tabular">
        <thead>
          <tr>
            <th>#</th><th>label</th>
            <th title="the series coordinate — blank means the index is the axis"
              >{settings?.x_label ?? "x"}</th>
            {#if !compact}
              <th>file</th><th>pts</th><th>2θ</th><th>σ</th>
            {/if}
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each patterns as p, i (p.upload + i)}
            {@const detail = `${p.filename} · read as ${p.reader} · ${p.n_points} points`
              + ` · 2θ ${p.two_theta_range[0].toFixed(1)}–${p.two_theta_range[1].toFixed(1)}°`
              + ` · σ ${p.has_sigma ? "from file" : "Poisson fallback"}`}
            <tr>
              <td class="muted">{i}</td>
              <td title={detail}>
                <input class="label" type="text" value={p.label} disabled={busy}
                  onchange={(ev) => setLabel(i, (ev.currentTarget as HTMLInputElement).value)} />
              </td>
              <td>
                <input class="x" type="text" inputmode="decimal"
                  value={p.x === null ? "" : p.x} disabled={busy}
                  onchange={(ev) => setX(i, (ev.currentTarget as HTMLInputElement).value)} />
              </td>
              {#if !compact}
                <td class="muted" title={detail}>{p.filename}</td>
                <td>{p.n_points}</td>
                <td class="muted">{p.two_theta_range[0].toFixed(1)}–{p.two_theta_range[1].toFixed(1)}°</td>
                <td>{p.has_sigma ? "file" : "Poisson"}</td>
              {/if}
              <td class="acts">
                <button class="ghost" disabled={busy || i === 0}
                  title="earlier in the series" onclick={() => move(i, -1)}>↑</button>
                <button class="ghost" disabled={busy || i === patterns.length - 1}
                  title="later in the series" onclick={() => move(i, 1)}>↓</button>
                <button class="ghost" disabled={busy}
                  title="remove from the series" onclick={() => remove(i)}>×</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  <h2>The chain</h2>
  <div class="controls">
    <label class="field" title="the chain direction. `both` runs the series each
way and reports every parameter the two directions disagree on — the only check
that separates a measured trajectory from an ordering artefact, and it costs a
second pass">
      direction
      <select value={settings?.direction ?? "forward"} disabled={busy}
        onchange={(ev) => setSetting("direction", (ev.currentTarget as HTMLSelectElement).value)}>
        {#each setup?.choices.direction ?? [] as choice (choice)}
          <option value={choice}>{choice}</option>
        {/each}
      </select>
    </label>
    <button onclick={start} disabled={!canRun}
      title={patterns.length < 2
        ? "a series needs at least two patterns; one pattern is a fit"
        : "run the chain: each pattern warm-started from its predecessor"}>
      {answer ? "Re-run series" : "Run series"}
    </button>
    {#if running}
      <span class="muted">
        {run?.run.stage ?? "starting"}
        {#if run?.run.stage_index}({run.run.stage_index}/{run.run.n_stages}){/if}
      </span>
    {/if}
  </div>

  {#if !simple}
    <!-- Advanced, because both are measured results rather than preferences
         (WP-0505) and re-litigating them in the UI would invite a worse default. -->
    <div class="controls advanced">
      <label class="field" title="`single` (the default) collapses the plan into
one stage per pattern once a converged neighbour is the starting point: measured
at 904 iterations against 1623 for re-walking the staged plan, with the QPA error
identical to three decimals. `stages` re-walks it.">
        refit
        <select value={settings?.refit ?? "single"} disabled={busy}
          onchange={(ev) => setSetting("refit", (ev.currentTarget as HTMLSelectElement).value)}>
          {#each setup?.choices.refit ?? [] as choice (choice)}
            <option value={choice}>{choice}</option>
          {/each}
        </select>
      </label>
      <label class="field" title={setup?.carry_help ?? ""}>
        carry
        <input class="carry" type="text" value={carryText} disabled={busy}
          onchange={(ev) => setCarry((ev.currentTarget as HTMLInputElement).value)}
          placeholder="*" />
      </label>
      <label class="field" title="what the series coordinate is called — the
plot's x-axis title, and the column above">
        x label
        <input class="xlabel" type="text" value={settings?.x_label ?? "index"}
          disabled={busy}
          onchange={(ev) => setSetting("x_label", (ev.currentTarget as HTMLInputElement).value)} />
      </label>
    </div>
    <p class="muted">{setup?.carry_help ?? ""}</p>
  {/if}

  {#if answer}
    <h2>
      {selectedPattern === null
        ? `Trajectory — ${current?.path ?? ""}`
        : `Pattern ${selectedPattern} — ${entries[selectedPattern]?.label ?? ""}`}
    </h2>
    <!-- every control above the plot, WP-1015's shape for every panel here -->
    <div class="controls">
      <select value={current?.path ?? ""} disabled={busy}
        onchange={(ev) => showTrajectory((ev.currentTarget as HTMLSelectElement).value)}>
        {#each ranked as t (t.path)}
          <option value={t.path}>
            {t.path_dependent ? "⚠ " : t.discontinuous ? "↕ " : ""}{t.path}
            {#if t.n_sigma !== null && t.path_dependent}({t.n_sigma.toFixed(1)}σ){/if}
          </option>
        {/each}
      </select>
      {#if selectedPattern !== null}
        <button class="ghost" onclick={() => showTrajectory(current?.path ?? "")}
          title="back to the trajectory across the series">Show trajectory</button>
      {/if}
    </div>
    {#if selectedPattern === null && current}
      <p class:warn={current.path_dependent}>
        {trajectoryNote(current, sigmaBar)}
      </p>
    {/if}
    <!-- the legend is the pattern panel's curve toggles with a swatch in each,
         in the flow above the figure: this panel scrolls, so a row it gains
         moves nothing a reader is holding still -->
    <div class="segmented legend" role="group" aria-label="what the plot draws">
      {#each legend as entry (entry.id)}
        <button class:on={!entry.absent && !hidden.includes(entry.id)}
          aria-pressed={!entry.absent && !hidden.includes(entry.id)} disabled={!!entry.absent}
          title={entry.absent
            ?? `${entry.label} — click to ${hidden.includes(entry.id) ? "show" : "hide"}`}
          onclick={() => toggle(entry.id)}><i class={entry.mark}
          style:--ink={`var(${entry.ink})`}></i>{entry.label}</button>
      {/each}
    </div>
    <Exports figure={() => fig} name={exportName} />
    <div class="plotbox">
      <div class="plot" bind:this={plotNode}></div>
      {#if tip}
        <div class="tip" style:left={`${tip.left}px`} style:top={`${tip.top}px`}>{tip.text}</div>
      {/if}
    </div>

    <h2>Per pattern</h2>
    <div class="scroll">
      <table class="tabular">
        <thead>
          <tr>
            <th>#</th><th>label</th><th>{answer.result.x_label}</th>
            <th>status</th><th>Rwp</th>
            <!-- the same floor as the staged table one section up, and GoF is
                 what goes: Rwp is the headline and this column was the 6 px that
                 put the drill-down button off the right edge (measured) -->
            {#if !compact}<th>GoF</th>{/if}
            <th title="least-squares iterations over every attempt on this pattern,
every rung of the escalation ladder included — what the warm start actually buys">iter</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {#each entries as e, i (e.index)}
            <tr class:lit={selectedPattern === i} class:out={e.status === "diverged"}>
              <td class="muted">{e.index}</td>
              <td>{e.label}</td>
              <td>{e.x === null ? e.index : e.x}</td>
              <td>
                {e.status}
                {#if e.status === "diverged"}
                  <span class="chip warn" title="no rung of the escalation ladder
recovered this pattern (tried: {e.rungs_tried.join(" → ")}). It is reported because it
was measured, but the chain stepped over it: it seeded no successor and its Rwp was
left out of the series median. Read it as a failed fit, not as a datum.">unrecovered</span>
                {:else if e.reseeded}
                  <span class="chip warn" title="the warm start was rejected (it
reached Rwp {((e.rwp_warm ?? 0) * 100).toFixed(2)}%) and this pattern was refitted from the
initial model. A good fit — but its starting values did not come from its
neighbour, so it is not evidence that the trajectory is continuous here.">reseeded</span>
                {:else if e.rung === "warm_staged"}
                  <span class="chip" title="the quick warm refit was rejected (it
reached Rwp {((e.rwp_warm ?? 0) * 100).toFixed(2)}%) and the full staged plan recovered
it — still starting from the neighbour's answer, so the chain is unbroken
here">restaged</span>
                {:else if e.rwp_warm !== null}
                  <span class="chip warn" title="the reseed guard fired and no restart
rescued it (tried: {e.rungs_tried.join(" → ")}): this pattern was hard for a reason a
different starting point could not fix">hard</span>
                {/if}
              </td>
              <td title={e.statistics ? `GoF ${e.statistics.gof.toFixed(3)}` : ""}>
                {e.statistics ? (e.statistics.rwp * 100).toFixed(2) + "%" : "—"}</td>
              {#if !compact}
                <td>{e.statistics ? e.statistics.gof.toFixed(3) : "—"}</td>
              {/if}
              <td>{e.n_iterations}</td>
              <td>
                <button class="ghost" disabled={busy || !answer.curves[i]}
                  title="this pattern's own fit and its own history tree"
                  onclick={() => openPattern(i)}>
                  {selectedPattern === i ? "▾" : "▸"}
                </button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
    <p class="muted tabular">
      {answer.n_iterations} iterations over the whole series
      {#if answer.has_backward}· plus a backward verification pass{/if}
    </p>

    {#if memberHistory}
      <h2>History — {memberHistory.label}</h2>
      <p class="muted">
        One tree per pattern, pinned to that pattern by its data fingerprint — so
        these nodes are <strong>read-only here</strong>: checking one out would
        restore a state fitted against different data. The chain itself is
        recorded on the root node's notes.
      </p>
      <ul class="nodes">
        {#each memberHistory.nodes as node (node.id)}
          <li>
            <span class="mono">{node.id}</span>
            <span class="kind">{node.kind}{node.name ? ` ${node.name}` : ""}</span>
            {#if node.rwp !== null}
              <span class="tabular">Rwp {(node.rwp * 100).toFixed(2)}%</span>
            {/if}
            {#if node.n_iterations}<span class="muted">{node.n_iterations} iter</span>{/if}
            {#if node.notes?.series_warm_start_node}
              <span class="muted mono" title="the node this pattern's starting values came from">
                ← {node.notes.series_warm_start_node}
              </span>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}

    {#if otherDiagnostics.length}
      <h2>Fences</h2>
      <ul class="strip">
        {#each otherDiagnostics as d (d.code + d.message)}
          <li class={d.level}>
            <span class="mono">{d.code}</span> {d.message}
            {#if d.suggestion}<span class="muted"> — {d.suggestion}</span>{/if}
          </li>
        {/each}
      </ul>
    {/if}
  {:else if patterns.length >= 2}
    <p class="muted hint">
      Nothing has run yet. <strong>Run series</strong> chains the patterns above,
      each warm-started from its predecessor; with <code>direction=both</code> it
      runs the chain each way and reports every parameter the two disagree on.
    </p>
  {/if}
</section>

<style>
  section {
    padding: 8px 10px;
    overflow: auto;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  h2 {
    margin: var(--s3) 0 var(--s1);
  }

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    flex-wrap: wrap;
    flex: 0 0 auto;
  }

  /* a row of controls, so it is control-sized */
  .field {
    display: flex;
    gap: 4px;
    align-items: center;
    font-size: var(--text-sm);
    color: var(--muted);
  }

  .banner {
    margin: 2px 0;
    padding: 5px 8px;
    border: 1px solid var(--line);
    border-left-width: 3px;
    border-radius: 3px;
    font-size: var(--text-sm);
    flex: 0 0 auto;
  }

  .banner.bad {
    border-left-color: var(--warn);
    color: var(--fg);
  }

  .banner.ok {
    border-left-color: var(--ok);
    color: var(--muted);
  }

  /* Bounded like the peak panel's tables and for the same measured reason: as
     unbounded flex children two stacked tables shrink each other, and the plot
     between them collapses to nothing. */
  .scroll {
    overflow: auto;
    flex: 0 0 auto;
    max-height: 34vh;
  }

  table {
    border-collapse: collapse;
    font-size: var(--text-sm);
    width: 100%;
  }

  th {
    text-align: left;
    font-weight: 600;
    color: var(--muted);
    padding: 2px 6px;
    position: sticky;
    top: 0;
    z-index: 1;
    background: var(--panel);
  }

  td {
    padding: 1px 6px;
    border-top: 1px solid var(--line);
    white-space: nowrap;
    vertical-align: middle;
  }

  tr.out td {
    opacity: 0.55;
  }

  tr.lit td {
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }

  .acts {
    display: flex;
    gap: 2px;
    align-items: center;
  }

  input.x, input.xlabel {
    width: 62px;
    font: var(--mono);
  }

  input.label {
    width: 92px;
  }

  input.carry {
    width: 150px;
    font: var(--mono);
  }

  /* a fixed height, not a share: the panel scrolls, so a flex-sized plot would
     be whatever was left over after two tables — which on a short window is
     nothing */
  .plotbox {
    position: relative;
    flex: 0 0 auto;
  }

  /* The figure's host. Its panes are sized from this box, so the height is
     the box's and never the panes', or each resize would feed the next. */
  .plot {
    height: 260px;
    overflow: hidden;
  }

  .legend {
    flex: 0 0 auto;
    align-self: flex-start;
    flex-wrap: wrap;
  }

  /* the swatch: which ink and which mark, as the figure draws it */
  .legend i {
    display: inline-block;
    vertical-align: middle;
    margin-right: 5px;
    width: 14px;
    height: 0;
    border-top: 1.5px solid var(--ink);
  }

  .legend i.dash {
    border-top-style: dashed;
  }

  .legend i.dot {
    border-top-style: dotted;
    border-top-width: 3px;
    width: 9px;
  }

  .legend i.ring {
    width: 8px;
    height: 8px;
    border: 1.5px solid var(--ink);
    border-radius: 50%;
  }

  .legend i.cross {
    width: 10px;
    height: 10px;
    border: 0;
    background:
      linear-gradient(45deg, transparent 43%, var(--ink) 43% 57%, transparent 57%),
      linear-gradient(-45deg, transparent 43%, var(--ink) 43% 57%, transparent 57%);
  }

  /* the point under the pointer, a DOM label over the canvas: pointing paints no curve */
  .tip {
    position: absolute;
    transform: translate(-50%, calc(-100% - 8px));
    pointer-events: none;
    white-space: nowrap;
    font-size: var(--text-sm);
    padding: 2px 6px;
    background: var(--panel);
    border: 1px solid var(--line);
  }

  .nodes, .strip {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: var(--text-sm);
    flex: 0 0 auto;
  }

  .nodes li {
    display: flex;
    gap: 8px;
    padding: 1px 0;
    border-top: 1px solid var(--line);
  }

  .nodes .kind {
    color: var(--accent);
  }

  .strip li {
    padding: 1px 0;
    color: var(--muted);
  }

  .strip li.warning { color: var(--warn); }
  .strip li.error { color: var(--bad); }

  p { margin: var(--s1) 0; }
</style>
