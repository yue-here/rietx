<script lang="ts">
  /**
   * The peak list and the indexing answer — WP-1027's tab.
   *
   * Peak picking is the one step where a human eye beats the algorithm, so the
   * *plot* carries the interactions (click to add, drag to move, shift-click to
   * exclude) and this panel is the ledger beside it: every line with its σ and
   * flags, the fitter's own diagnostics as an inline strip (information, not an
   * interruption), and the candidate table when indexing has run.
   *
   * Two design rules come from the API's shape. The candidate list is the
   * **primary** view and the singleton a badge on it — `best_or_none()`
   * returning nothing is the *expected* first outcome on real lab data, so a
   * "here is your cell" happy path would look broken most of the time. And the
   * gate's pick is the **server's** `adopt` arm, never a local reading of
   * `confidence`. Every row can be adopted (Yue's ruling B, 2026-11-08,
   * WP-2124); a row the gate did not pick shows the arm's `why` under its
   * grade, the sentence its history node records. What the search covered is said
   * above the list whatever it found (WP-1042, WP-2130).
   */
  import { untrack } from "svelte";

  import { api } from "../api";
  import Help from "../Help.svelte";
  import {
    CONTROL_FIELDS,
    SEARCH_FIELDS,
    controlsDigest,
    controlsFromDoc,
    foldSnapshots,
    parsePriorCell,
    priorCellText,
    searchHelp,
    setFormula,
    textOrNull,
    type IndexingControls,
  } from "../lib/controls";
  import { labelFor, type HelpCorpus } from "../lib/help";
  import { clone } from "../lib/model";
  import {
    PEAK_STEPS,
    absentOf,
    candidateRelation,
    cellLine,
    cellText,
    clock,
    collectTo,
    filterPeaks,
    fomOf,
    formatHkl,
    formatIntensity,
    formatPosition,
    groupRows,
    intensityScale,
    searchCoverage,
    unindexedOf,
    type AdoptVerdict,
    type Candidate,
    type PeakFilter,
    type PeaksPayload,
  } from "../lib/peaks";
  import type { RunState } from "../lib/stream";

  let {
    peaks,
    indexAnswer,
    extinction = null,
    run,
    busy,
    capabilities = null,
    corpus = null,
    doc = null,
    snapshots = [],
    hovered = null,
    shownCandidate = null,
    say = () => {},
    onpeaks = () => {},
    onindexed = () => {},
    onzoom = () => {},
    onmoved = () => {},
    onhover = () => {},
    oncandidate = () => {},
    oncandidatehover = () => {},
    onproject = () => {},
    ongraph = () => {},
    onfitgroups = () => {},
  }: {
    peaks: PeaksPayload | null;
    indexAnswer: any;
    extinction?: any;
    run: RunState | null;
    busy: boolean;
    /** `/api/capabilities` — the live vocabularies the form renders from */
    capabilities?: any;
    /** `/api/help` — where a chip's words come from (WP-1209); absent, a chip
     *  says the name and the popover says "not described yet" */
    corpus?: HelpCorpus | null;
    /** the project document; `doc.indexing` is the form's one authority */
    doc?: any;
    /** streamed `consensus:<system>` snapshots of the run in flight */
    snapshots?: Array<Record<string, any>>;
    /** the line the pointer is over, in the plot or in this table (WP-1032) */
    hovered?: number | null;
    /** the candidate whose lines are on the plot right now (WP-1211) — the
     *  shell's, because a hover preview outranks the selection while it lasts
     *  and this panel must light the row that is actually drawn */
    shownCandidate?: number | null;
    say?: (line: string) => void;
    onpeaks?: (payload: PeaksPayload) => void;
    onindexed?: (answer: any) => void;
    onzoom?: (lo: number, hi: number) => void;
    onmoved?: () => void;
    onhover?: (index: number | null) => void;
    /** show this candidate's predicted lines, or none (WP-1211) */
    oncandidate?: (index: number | null) => void;
    /** preview one while the pointer is on its row */
    oncandidatehover?: (index: number | null) => void;
    /** the document changed server-side (a controls patch landed) */
    onproject?: () => void;
    /** show this graph tab: Fit peaks is drawn in the group windows, the
     *  other steps on the pattern (round 11, call 1) */
    ongraph?: (id: "pattern" | "single") => void;
    /** the overlap groups the fit windows draw, and the one chosen */
    onfitgroups?: (groups: number[], focused: number | null) => void;
  } = $props();

  // ------------------------------------------------------------------
  // the four steps (WP-2202): one shows at a time, under a step strip.
  // Choosing a step is a jump the person asked for, so it may change the
  // graph tab; nothing else here does (`gui/STYLE.md` principle 4).
  // ------------------------------------------------------------------
  let step = $state(0);
  function goStep(i: number) {
    step = i;
    ongraph(i === 1 ? "single" : "pattern");
  }

  /** Pick peaks: which rows the table lists, and the rows ticked since */
  let filter = $state<PeakFilter>("all");
  let keep = $state(new Set<number>());
  function setFilter(f: PeakFilter) {
    filter = f;
    keep = new Set();
  }

  /** the picker's three options, as typed; re-read from the stored list
   *  only when a new list arrives (keyed on its creation time) */
  let popt = $state({ lo: "", hi: "", shoulders: true, contamination: true });
  let confirming = $state(false);
  $effect(() => {
    void peaks?.created_utc;
    const o = untrack(() => peaks?.pick_options);
    const rng = o?.two_theta_range ?? null;
    popt = {
      lo: rng ? String(rng[0]) : "", hi: rng ? String(rng[1]) : "",
      shoulders: o?.shoulders ?? true, contamination: o?.flag_contamination ?? true,
    };
    confirming = false;
  });

  /** Fit peaks: the groups worth a look, or all of them */
  let groupFilter = $state<"look" | "all">("look");

  /** Judge: the extinction class chosen, and the space group within it */
  let chosenClass = $state<number | null>(null);
  let chosenGroup = $state<string | null>(null);

  let failure = $state("");
  let expanded = $state<number | null>(null);
  /** the typed-2θ add box — the non-pointer route to `add_peak` */
  let addAt = $state("");

  // ------------------------------------------------------------------
  // the search controls (WP-1045): ProjectDoc.indexing rendered as a form.
  // The document is the authority; `draft` is the buffer an input edits and
  // every commit is a whole-object POST /api/project {indexing} — settings
  // persist on the verb, and the server's 409 guards a run in flight.
  // ------------------------------------------------------------------
  /** the form's refusal, in the verb's words — deliberately not `failure`
   *  (a verb's refusal and a panel's load error must not share one field) */
  let controlsError = $state("");
  let draft = $state<IndexingControls | null>(null);
  let priorText = $state("");
  let sgText = $state("");
  $effect(() => {
    // re-sync from the document whenever it moves (the head is the signal)
    draft = doc ? clone(controlsFromDoc(doc)) : null;
  });

  const caps = $derived(capabilities ?? {});
  const systemsVocab = $derived<string[]>(caps.crystal_systems ?? []);
  const enginesVocab = $derived<Array<{ name: string; description: string }>>(
    caps.indexing_engines ?? []);
  const presetsVocab = $derived<Array<Record<string, any>>>(
    caps.search_presets ?? []);
  const centringsVocab = $derived<Record<string, string[]>>(
    caps.centrings ?? {});
  const templatesVocab = $derived<string[]>(caps.shift_templates ?? []);
  const defaultPreset = $derived<string>(
    presetsVocab.find((p) => p.default)?.name ?? "quick");
  const digest = $derived(controlsDigest(draft, defaultPreset));
  const shortlists = $derived(foldSnapshots(snapshots ?? []));
  const field = (name: string) =>
    [...SEARCH_FIELDS, ...CONTROL_FIELDS].find((f) => f.name === name)!;

  async function commit() {
    if (!draft) return;
    controlsError = "";
    try {
      await api.patchProject({ indexing: draft });
      say(`project.doc.indexing = …  # ${digest || "defaults"}`);
      onproject();
    } catch (error) {
      controlsError = (error as Error).message;
      onproject(); // re-sync the draft from the document the server kept
    }
  }

  function setSearch(name: string, value: unknown) {
    if (!draft) return;
    (draft.search as any)[name] = value;
    commit();
  }

  /** empty input → null (package default) for the optional numbers */
  function numOrNull(text: string): number | null {
    const v = Number(text);
    return text.trim() === "" || !Number.isFinite(v) ? null : v;
  }

  function toggleSystem(system: string) {
    if (!draft) return;
    const all = systemsVocab;
    const on = new Set(draft.search.systems ?? all);
    if (on.has(system)) on.delete(system);
    else on.add(system);
    if (on.size === 0) {
      controlsError = "at least one crystal system must stay searchable";
      return;
    }
    draft.search.systems =
      on.size === all.length ? null : all.filter((s) => on.has(s));
    commit();
  }

  function toggleCentring(system: string, letter: string) {
    if (!draft) return;
    const allowed = centringsVocab[system] ?? [];
    const on = new Set(draft.search.centrings?.[system] ?? allowed);
    if (on.has(letter)) on.delete(letter);
    else on.add(letter);
    if (on.size === 0) {
      controlsError = `${system} needs at least one centring — drop the `
        + "system instead";
      return;
    }
    const centrings = { ...(draft.search.centrings ?? {}) };
    if (on.size === allowed.length) delete centrings[system];
    else centrings[system] = allowed.filter((c) => on.has(c));
    draft.search.centrings =
      Object.keys(centrings).length ? centrings : null;
    commit();
  }

  function toggleEngine(name: string) {
    if (!draft) return;
    const all = enginesVocab.map((e) => e.name);
    const on = new Set(draft.engines ?? all);
    if (on.has(name)) on.delete(name);
    else on.add(name);
    if (on.size === 0) {
      controlsError = "at least one engine must run";
      return;
    }
    draft.engines = on.size === all.length ? null : all.filter((e) => on.has(e));
    commit();
  }

  function addPriorCell() {
    if (!draft) return;
    const parsed = parsePriorCell(priorText);
    if (typeof parsed === "string") {
      controlsError = parsed;
      return;
    }
    priorText = "";
    draft.search.prior_cells = [...(draft.search.prior_cells ?? []), parsed];
    commit();
  }

  function removePriorCell(index: number) {
    if (!draft) return;
    const kept = (draft.search.prior_cells ?? []).filter((_, i) => i !== index);
    draft.search.prior_cells = kept.length ? kept : null;
    commit();
  }

  function addPriorSg() {
    if (!draft || !sgText.trim()) return;
    // validated server-side (gemmi) — a refusal comes back in the verb's words
    draft.search.prior_spacegroups =
      [...(draft.search.prior_spacegroups ?? []), sgText.trim()];
    sgText = "";
    commit();
  }

  function removePriorSg(index: number) {
    if (!draft) return;
    const kept =
      (draft.search.prior_spacegroups ?? []).filter((_, i) => i !== index);
    draft.search.prior_spacegroups = kept.length ? kept : null;
    commit();
  }

  const rows = $derived(peaks?.peaks ?? []);
  const diagnostics = $derived(peaks?.diagnostics ?? []);
  /** the 100 of the relative intensity scale: the strongest *measured* line */
  const imax = $derived(intensityScale(rows));
  const indexing = $derived(busy && run?.run?.kind === "index");
  const screening = $derived(busy && run?.run?.kind === "extinction");
  const candidates = $derived<Candidate[]>(indexAnswer?.result?.candidates ?? []);
  const refuting = $derived<string[]>(indexAnswer?.refuting_caveats ?? []);
  const verdicts = $derived<AdoptVerdict[]>(indexAnswer?.adopt ?? []);
  const shown = $derived(filterPeaks(rows, filter, keep));
  const nUsed = $derived(rows.filter((p) => p.usable).length);
  /** the lines a person placed, moved or left out: what a re-pick replaces */
  const nEdits = $derived(rows.filter((p) => p.origin !== "fitted"
    || p.flags.includes("excluded")).length);
  const groupList = $derived(groupRows(peaks?.groups ?? [], rows));
  const groupsShown = $derived(groupFilter === "all" ? groupList
    : groupList.filter((g) => g.look));
  /** the group chosen in the list; the windows draw six from it onward */
  let focusedGroup = $state<number | null>(null);
  const FIT_WINDOWS = 6;
  $effect(() => {
    const k = Math.max(0, groupsShown.findIndex((g) => g.group === focusedGroup));
    onfitgroups(groupsShown.slice(k, k + FIT_WINDOWS).map((g) => g.group), focusedGroup);
  });
  const flagWord = (f: string) => labelFor(corpus, `peak_flags:${f}`);
  /** the time limit is a preset's ceiling, said as a time */
  const limitWord = (s: number | null | undefined) =>
    s == null ? "None" : s % 60 === 0 ? `${s / 60} minutes` : `${s} s`;
  const preset = $derived(draft?.search.preset ?? defaultPreset);
  const budget = $derived(draft?.search.total_budget_seconds
    ?? presetsVocab.find((p) => p.name === preset)?.total_budget_seconds ?? null);
  /** the systems the run asked for, and each one's state off the stream */
  const asked = $derived<string[]>(draft?.search.systems ?? systemsVocab);
  function systemState(s: string): string {
    if (shortlists.some((snap) => snap.system === s)) return "searched";
    if (run?.run?.stage?.includes(s)) return "searching…";
    return "waiting";
  }
  /** the candidate Judge shows: the one selected in Index */
  const judged = $derived(expanded);
  /** the two figures of merit the literature names by a symbol */
  const FOM_LABEL: Record<string, string> = { m20: "M₂₀", f_n: "F_N" };
  const caveatWords = (c: Candidate) =>
    c.confidence_caveats.map((k) => k.replaceAll("_", " "));
  /** the gate's pick, a badge on one row of the list and never the list's
   *  answer: every row can be adopted (Yue's ruling B, 2026-11-08) */
  const best = $derived(verdicts.findIndex((v) => v.picked));
  const quality = $derived(indexAnswer?.result?.quality ?? null);
  /** what the search tried and what it did not finish, said whatever it found
   *  (WP-1042: a system not reached is said loudly, WP-2130) */
  const coverage = $derived(searchCoverage(indexAnswer?.result));
  const screen = $derived(extinction?.result ?? null);

  /**
   * Selecting a candidate is one act with two effects (WP-1211): the detail row
   * opens and this cell's predicted lines go on the plot.
   *
   * `expanded` stays the one place that says which candidate is selected — a
   * second flag beside it would be a second selection state, and the two would
   * have to be kept in step at every write.
   */
  function selectCandidate(index: number | null) {
    expanded = index;
    chosenClass = null;
    chosenGroup = null;
    oncandidate(index);
  }

  /** A class of the screen chosen; until one is, the gate's pick is. */
  function chooseClass(k: number) {
    chosenClass = k;
    chosenGroup = null;
  }
  const activeClass = $derived<number | null>(chosenClass
    ?? (extinction?.candidate === judged ? extinction?.best ?? null : null));
  /** the space group Adopt sends: the one chosen, else the class's
   *  representative (round 11 calls 10 and 12) */
  const activeGroup = $derived.by<string | null>(() => {
    if (chosenGroup !== null) return chosenGroup;
    const cls = activeClass === null ? null : screen?.candidates?.[activeClass];
    if (!cls) return null;
    return cls.space_groups.includes(cls.representative)
      ? cls.representative : cls.space_groups[0] ?? null;
  });

  // A new answer renumbers the candidates, so the open row and the drawn lines
  // are both about a cell that no longer has that index — the same staleness
  // the server enforces on the extinction screen, one rank up.
  $effect(() => {
    void indexAnswer;
    if (untrack(() => expanded) !== null) selectCandidate(null);
  });

  async function verb(work: () => Promise<PeaksPayload>) {
    failure = "";
    try {
      const payload = await work();
      if (payload.api_call) say(payload.api_call);
      onpeaks(payload);
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  /** Pick with the three options; a range needs both ends or neither. */
  function pick() {
    const lo = popt.lo.trim(), hi = popt.hi.trim();
    if ((lo === "") !== (hi === "")) {
      failure = "give the 2θ range both ends, or neither for the whole pattern";
      return;
    }
    const body: Parameters<typeof api.pickPeaks>[0] = {
      shoulders: popt.shoulders, flag_contamination: popt.contamination };
    if (lo !== "") body.two_theta_range = [Number(lo), Number(hi)];
    confirming = false;
    verb(() => api.pickPeaks(body));
  }
  /** Pick peaks again: replaces the list, so it says how many edits first */
  function repick() {
    if (nEdits && !confirming) confirming = true;
    else pick();
  }
  async function stop() {
    try {
      await api.cancel();
      say("token.cancel()");
    } catch (error) {
      failure = (error as Error).message;
    }
  }
  function setLimit(name: string) {
    if (!draft) return;
    draft.search.preset = name === defaultPreset ? null : name;
    draft.search.total_budget_seconds = null;
    commit();
  }
  const remove = (index: number) => verb(() => api.removePeak(index));

  function addTyped() {
    const tt = Number(addAt);
    if (!Number.isFinite(tt)) {
      failure = `"${addAt}" is not a 2θ`;
      return;
    }
    addAt = "";
    verb(() => api.addPeak(tt));
  }
  function toggleUse(index: number, usable: boolean) {
    keep = new Set([...keep, index]);
    verb(() => api.flagPeak(index, { use_for_indexing: !usable }));
  }
  const refit = (group: number) => verb(() => api.refitGroup(group));

  async function startIndex() {
    failure = "";
    try {
      await api.index();
      say("index_pattern(peaks, data=…, instrument=…)");
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  async function adopt(index: number, spaceGroup?: string) {
    failure = "";
    try {
      const answer = await api.adoptCandidate(index, spaceGroup);
      say(answer.api_call);
      onmoved(); // the head moved: the model is the adopted cell now
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  async function screenExtinctions(index: number) {
    failure = "";
    try {
      await api.screenExtinctions(index);
      say(`determine_extinction_symbol(data, result.candidates[${index}], instrument)`);
    } catch (error) {
      failure = (error as Error).message;
    }
  }

  function zoomTo(tt: number, fwhm: number) {
    onzoom(tt - 8 * fwhm, tt + 8 * fwhm);
  }
</script>

<section class="peaks">
  <!-- The four steps, as the maintainer named them (2026-11-07). A step is
       one of N views over the same tab, so it is drawn as a tab (WP-2202). -->
  <nav class="steps" aria-label="Steps">
    {#each PEAK_STEPS as name, i (name)}
      <button class="tab" class:on={step === i}
        aria-current={step === i ? "step" : undefined}
        onclick={() => goStep(i)}><span class="n mono">{i + 1}</span> {name}</button>
    {/each}
  </nav>
  {#if failure}<p class="bad">{failure}</p>{/if}

  {#snippet pickOptions()}
    <div class="form">
      <span class="lab">2θ range</span>
      <span class="field">
        <input type="text" inputmode="decimal" aria-label="Lowest 2θ" disabled={busy}
          placeholder="start" bind:value={popt.lo} />
        <span class="muted">to</span>
        <input type="text" inputmode="decimal" aria-label="Highest 2θ" disabled={busy}
          placeholder="end" bind:value={popt.hi} />
        <span class="muted">°</span>
      </span>
      <span class="lab">Shoulders</span>
      <label class="opt"><input type="checkbox" disabled={busy}
        bind:checked={popt.shoulders} /> Look for shoulders</label>
      <span class="lab">Contamination</span>
      <label class="opt"><input type="checkbox" disabled={busy}
        bind:checked={popt.contamination} /> Flag Kβ and tungsten lines</label>
    </div>
  {/snippet}

  {#if step === 0}
    <!-- 1. Pick peaks -->
    {#if !peaks?.peaks}
      <h3>Picking settings</h3>
      {@render pickOptions()}
      <div class="foot">
        <button class="ghost" onclick={pick} disabled={busy}>Pick peaks</button>
      </div>
    {:else}
      <div class="bar">
        <div class="segmented" role="group" aria-label="Lines shown">
          {#each [["all", `All ${rows.length}`], ["used", `Used ${nUsed}`],
                  ["unused", `Not used ${rows.length - nUsed}`]] as [k, t] (k)}
            <button class:on={filter === k} aria-pressed={filter === k}
              onclick={() => setFilter(k as PeakFilter)}>{t}</button>
          {/each}
        </div>
        <input class="add mono" type="text" inputmode="decimal" placeholder="add at 2θ"
          aria-label="Add a line at 2θ" bind:value={addAt} disabled={busy}
          onkeydown={(ev) => ev.key === "Enter" && addTyped()} />
        {#if peaks.source === "positions"}
          <span class="warn"><Help for="diagnostics:PEAK_SIGMA_ASSUMED">σ assumed</Help></span>
        {/if}
      </div>
      <div class="scroll">
        <table class="tabular lines">
          <thead>
            <tr><th class="ck"></th><th class="r">2θ (°)</th><th class="r">d (Å)</th>
              <th class="r">I (rel)</th><th>Note</th><th></th></tr>
          </thead>
          <tbody>
            {#each shown as p (p.index)}
              {@const pos = formatPosition(p.two_theta, p.two_theta_esd)}
              <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
              <tr class:out={!p.usable} class:lit={hovered === p.index}
                onmouseenter={() => onhover(p.index)}
                onmouseleave={() => onhover(null)}>
                <td class="ck">
                  <input type="checkbox" checked={p.usable} disabled={busy}
                    aria-label="Use {p.two_theta.toFixed(3)}° in the search"
                    onchange={() => toggleUse(p.index, p.usable)} />
                </td>
                <td class="r">
                  <button class="pick pos" onclick={() => zoomTo(p.two_theta, p.fwhm)}
                    >{pos.value}<span class="muted">{pos.esd}</span></button>
                </td>
                <td class="r">{p.d.toFixed(4)}</td>
                <td class="r">{formatIntensity(p.intensity, imax, p.flags)}</td>
                <!-- who placed the line, then its flags, each in the corpus's
                     words with its explanation one click away (WP-1209) -->
                <td class="note muted">
                  {#if p.origin !== "fitted"}<span class="word"><Help for="peak_origins:{p.origin}"
                    >{labelFor(corpus, `peak_origins:${p.origin}`)}</Help></span>{/if}
                  {#each p.flags as f (f)}<span class="word"><Help for="peak_flags:{f}"
                    >{flagWord(f)}</Help></span>{/each}
                </td>
                <td class="acts">
                  <button class="ghost" disabled={busy} title="Remove this line"
                    onclick={() => remove(p.index)}>×</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      {#if diagnostics.length}
        <details class="fold">
          <summary>Notes from the picker ({diagnostics.length})</summary>
          <ul class="strip">
            {#each diagnostics as d (d.code + d.message)}
              <li class={d.level}><span class="mono">
                <Help for="diagnostics:{d.code}">{d.code}</Help></span> {d.message}</li>
            {/each}
          </ul>
        </details>
      {/if}
      <details class="fold">
        <summary>Picking settings</summary>
        {@render pickOptions()}
        <div class="foot">
          {#if confirming}
            <span class="muted why">Picking again replaces the list, with the {nEdits}
              {nEdits === 1 ? "line" : "lines"} you added, moved or left out.</span>
            <button class="ghost" onclick={() => (confirming = false)}>Cancel</button>
          {/if}
          <button class="ghost" onclick={repick} disabled={busy}>Pick peaks</button>
        </div>
      </details>
    {/if}

  {:else if step === 1}
    <!-- 2. Fit peaks: each overlap group's window fit, drawn in the graph -->
    {#if !peaks?.peaks}
      <div class="empty"><button class="ghost" onclick={() => goStep(0)}>Pick peaks first</button></div>
    {:else}
      <div class="bar">
        <div class="segmented" role="group" aria-label="Groups shown">
          <button class:on={groupFilter === "look"} aria-pressed={groupFilter === "look"}
            onclick={() => (groupFilter = "look")}
            >To look at {groupList.filter((g) => g.look).length}</button>
          <button class:on={groupFilter === "all"} aria-pressed={groupFilter === "all"}
            onclick={() => (groupFilter = "all")}>All groups {groupList.length}</button>
        </div>
      </div>
      <div class="scroll">
        <table class="tabular groups">
          <thead>
            <tr><th class="r">2θ (°)</th><th class="r">Lines</th>
              <th class="r">χ²ᵣ</th>
              <th>Note</th><th></th></tr>
          </thead>
          <tbody>
            {#each groupsShown as g (g.group)}
              <tr class:sel={focusedGroup === g.group}>
                <td class="r">
                  <button class="pick" onclick={() => (focusedGroup = g.group)}
                    >{g.lo.toFixed(2)}–{g.hi.toFixed(2)}</button>
                </td>
                <td class="r">{g.n}</td>
                <td class="r" class:hi={g.chi2_red > 10}>{g.chi2_red.toFixed(1)}</td>
                <td class="note muted">{g.flags.map(flagWord).join(", ")}</td>
                <td class="acts">
                  <button class="ghost" disabled={busy}
                    title="Refit this group under the picker's own judgement"
                    onclick={() => refit(g.group)}>↻</button>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

  {:else if step === 2}
    <!-- 3. Index: the settings show before a list exists; Index waits for one -->
      {#if draft}
        <div class="form" class:frozen={busy}>
          <span class="lab"><Help for={searchHelp(field("systems"))}>Crystal systems</Help></span>
          <span class="field wrap">
            {#each systemsVocab as s (s)}
              <label class="opt">
                <input type="checkbox" disabled={busy}
                  checked={draft.search.systems === null || draft.search.systems.includes(s)}
                  onchange={() => toggleSystem(s)} /> {s}
              </label>
            {/each}
          </span>
          <span class="lab"><Help for={searchHelp(field("max_volume"))}>Largest volume</Help></span>
          <span class="field">
            <input type="text" inputmode="decimal" disabled={busy} placeholder="from data"
              aria-label="Largest cell volume"
              value={draft.search.max_volume ?? ""}
              onchange={(ev) => setSearch("max_volume",
                numOrNull((ev.currentTarget as HTMLInputElement).value))} />
            <span class="muted">Å³</span>
          </span>
          <span class="lab"><Help for={searchHelp(field("preset"))}>Time limit</Help></span>
          <span class="field">
            <div class="segmented" role="group" aria-label="Time limit">
              {#each presetsVocab as p (p.name)}
                {@const on = draft.search.total_budget_seconds == null && preset === p.name}
                <button class:on={on} aria-pressed={on} disabled={busy}
                  onclick={() => setLimit(p.name)}>{limitWord(p.total_budget_seconds)}</button>
              {/each}
            </div>
          </span>
        </div>
        {@render moreSettings()}
        {#if controlsError}<p class="bad">{controlsError}</p>{/if}
      {/if}

      {#if indexing}
        <h3>Searching</h3>
        <table class="tabular sys">
          <tbody>
            {#each asked as s (s)}
              {@const state = systemState(s)}
              <tr><td>{s}</td><td class="muted" class:on={state === "searching…"}>{state}</td></tr>
            {/each}
          </tbody>
        </table>
        {#if shortlists.some((snap) => snap.candidates.length)}
          <h3>Found so far</h3>
          <ul class="strip found">
            {#each shortlists as snap (snap.system)}
              {#each snap.candidates.slice(0, 3) as c, i (i)}
                <li><span class="mono">{cellText(c.cell)}</span>
                  <span class="muted">{snap.system}</span></li>
              {/each}
            {/each}
          </ul>
        {/if}
      {/if}

      {#if indexAnswer && !indexing}
        <!-- What the search covered, above any answer: a run stopped at its
             ceiling reads like a finished one unless this is said (WP-1042).
             Shown whether or not there are candidates (WP-2130). -->
        <div class="coverage" class:short={coverage.incomplete.length
          || (indexAnswer.result?.diagnostics ?? []).some((d: any) => d.level !== "info")}>
          <p>Searched: {coverage.searched.join(", ") || "none"}</p>
          {#if coverage.incomplete.length}
            <p class="warn">Search incomplete in {coverage.incomplete.join(", ")}:
              a negative result there is not evidence.</p>
          {/if}
          <ul class="strip">
            {#each indexAnswer.result?.diagnostics ?? [] as d (d.code + d.message)}
              <li class={d.level}><span class="mono"><Help for="diagnostics:{d.code}">{d.code}</Help></span>
                {d.message}
                <!-- keyed by position: two `where` entries can be one string -->
                {#each d.where ?? [] as w, j (j)}<span class="where">{w}</span>{/each}</li>
            {/each}
          </ul>
        </div>
        {#if !candidates.length}
          <p class="muted">No candidate cells.
            {#if quality?.abstained_reason}{quality.abstained_reason}{/if}</p>
        {:else}
          <h3>Candidates <span class="muted">{candidates.length}, ranked by rietx</span></h3>
          {#if best < 0}
            <!-- best_or_none() returned None: the expected first outcome on
                 real lab data, so it is said as a fact, not an error -->
            <p class="muted">No candidate reaches the gate; the list below is ranked, not chosen.</p>
          {/if}
          <div class="scroll">
            <table class="tabular candidates">
              <thead>
                <tr>
                  <th class="r">#</th><th>Cell</th><th>Lattice</th><th class="r">V (Å³)</th>
                  <th class="r">M₂₀</th><th class="r">Unindexed</th>
                  <th class="r">Absent</th><th class="r">Rwp</th><th>Grade</th><th></th>
                </tr>
              </thead>
              <tbody>
                <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
                {#each candidates as c, i (i)}
                  {@const m20 = fomOf(c, "m20")}
                  {@const ab = absentOf(c)}
                  {@const rel = candidateRelation(candidates, i)}
                  <tr class:sel={judged === i} class:lit={shownCandidate === i}
                    onmouseenter={() => oncandidatehover(i)}
                    onmouseleave={() => oncandidatehover(null)}>
                    <td class="r">
                      <button class="pick" aria-label="Select candidate {i + 1}"
                        onclick={() => selectCandidate(judged === i ? null : i)}>{i + 1}</button>
                    </td>
                    <td class="cell">
                      <button class="pick mono" onclick={() => selectCandidate(judged === i ? null : i)}
                        >{cellLine(c)}</button>
                      {#if rel}<span class="muted rel">{rel}</span>{/if}
                      <!-- a row the gate did not pick says why, in the
                           sentence its adoption records (WP-2124, WP-2130) -->
                      {#if verdicts[i]?.why}<span class="muted why">{verdicts[i].why}</span>{/if}
                    </td>
                    <td>{c.system} {c.centring}</td>
                    <td class="r">{c.volume.toFixed(0)}</td>
                    <td class="r">{m20 === null ? "–" : m20.toFixed(1)}</td>
                    <td class="r">{unindexedOf(c)}</td>
                    <td class="r">{#if ab}{ab.absent} <span class="muted">of {ab.of}</span>{:else}–{/if}</td>
                    <td class="r">{c.lebail ? `${(c.lebail.rwp * 100).toFixed(1)} %` : "–"}</td>
                    <td>{c.confidence}{#if i === best}<span class="mark">rietx's pick</span>{/if}</td>
                    <!-- every row can be adopted (Yue's ruling B, 2026-11-08) -->
                    <td>
                      <button class="ghost" disabled={busy}
                        title="Adopt this cell as a Le Bail start (one history node)"
                        onclick={() => adopt(i)}>Adopt</button>
                    </td>
                  </tr>
                {/each}
              </tbody>
            </table>
          </div>
        {/if}
      {/if}

      <div class="foot">
        {#if indexing}
          <button class="ghost" onclick={stop}>Stop</button>
          <span class="muted mono why">{clock(run?.run?.elapsed ?? 0)} elapsed{#if budget != null}
            · about {clock(Math.max(0, budget - (run?.run?.elapsed ?? 0)))} left{/if}</span>
        {:else}
          {#if candidates.length}
            <button class="ghost" disabled={judged === null} onclick={() => goStep(3)}
              >Judge{judged === null ? "" : ` #${judged + 1}`} ›</button>
          {/if}
          {#if !rows.length}<span class="muted why">Pick peaks first.</span>{/if}
          <button class="ghost" onclick={startIndex} disabled={busy || !rows.length}
            >{indexAnswer ? "Index again" : "Index"}</button>
        {/if}
      </div>

  {:else}
    <!-- 4. Judge -->
    {#if judged === null || !candidates[judged]}
      <div class="empty"><button class="ghost" onclick={() => goStep(2)}
        >Choose a candidate in Index</button></div>
    {:else}
      {@const i = judged}
      {@const c = candidates[i]}
      {@const ab = absentOf(c)}
      <div class="nav">
        <button class="ghost" aria-label="Previous candidate" disabled={i === 0}
          onclick={() => selectCandidate(i - 1)}>‹</button>
        <span><strong>#{i + 1}</strong> <span class="muted">of {candidates.length}</span></span>
        <button class="ghost" aria-label="Next candidate" disabled={i >= candidates.length - 1}
          onclick={() => selectCandidate(i + 1)}>›</button>
        <span class="grow"></span>
        <span class="muted">{c.system} {c.centring}</span>
      </div>
      <p class="mono cellline">{cellLine(c, true)}, V = {c.volume.toFixed(1)} Å³</p>
      <!-- the relation line keeps its height when empty, so stepping between
           candidates moves nothing below it (round 11) -->
      <p class="muted rel">{candidateRelation(candidates, i) || " "}</p>

      <h3>Grade <span class="muted">{c.confidence}</span></h3>
      <p class="caveats">
        {#each c.confidence_caveats as k (k)}
          <span class:bad={refuting.includes(k)}>{k.replaceAll("_", " ")}</span>
        {:else}<span class="muted">no caveats</span>{/each}
      </p>

      <h3>Le Bail check</h3>
      {#if c.lebail}
        <dl class="kv">
          <dt>Rwp</dt><dd class="mono">{(c.lebail.rwp * 100).toFixed(1)} %</dd>
          <dt>Predicted lines with no peak</dt>
          <dd><span class="mono">{ab?.absent}</span> of <span class="mono">{ab?.of}</span></dd>
          <dt>Peaks no line explains</dt><dd class="mono">{c.lebail.unmatched_observed ?? "–"}</dd>
        </dl>
      {:else}
        <p class="muted">Not checked by a Le Bail fit.</p>
      {/if}

      <h3>Figures of merit</h3>
      <dl class="kv">
        {#each c.fom as f (f.name)}
          <!-- each figure's blind spot is one click away (round 11) -->
          <dt>{#if f.blind_spot}<Help text={f.blind_spot}>{FOM_LABEL[f.name] ?? f.name}</Help>
            {:else}{FOM_LABEL[f.name] ?? f.name}{/if}</dt>
          <dd class="mono">{f.value == null ? "–" : f.value.toFixed(2)}</dd>
        {/each}
        <dt>Found by</dt><dd>{c.found_by.join(", ")}</dd>
      </dl>
      {#if collectTo(c) !== null}
        <p class="warn">Collect to 2θ ≈ {collectTo(c)?.toFixed(1)}° to tell this cell
          from its partner; the lines that separate them lie beyond the measured range.</p>
      {/if}

      <h3>Space group</h3>
      {#if extinction?.candidate !== i || !screen}
        <button class="ghost" disabled={busy} onclick={() => screenExtinctions(i)}
          >{screening ? "Screening extinctions…" : "Screen extinctions"}</button>
      {:else}
        <p class="muted">Against {screen.lattice_group}, absence-free:
          {screen.n_screened} of {screen.n_classes} classes fitted,
          2θ {screen.two_theta_range[0].toFixed(1)}–{screen.two_theta_range[1].toFixed(1)}°</p>
        {#if extinction.best === null}
          <!-- refuted classes, an indecisive ΔBIC margin or unfitted classes
               leave an unasked question, which must not read as an answer -->
          <p class="muted">No class is singled out; the list below is ranked, not chosen.</p>
        {/if}
        <div class="scroll">
          <table class="tabular classes">
            <thead>
              <tr><th>Class</th>
                <th class="r">ΔBIC</th>
                <th class="r">Tested</th><th>Groups</th></tr>
            </thead>
            <tbody>
              {#each screen.candidates as cls, k (cls.symbol + k)}
                <!-- a refuted class stays in the table, muted, as evidence
                     (round 11 call 17); it cannot be chosen -->
                <tr class:out={cls.refuted} class:sel={activeClass === k}>
                  <td class="cell">
                    {#if cls.refuted}<span class="mono">{cls.symbol}</span>
                    {:else}<button class="pick mono" onclick={() => chooseClass(k)}
                      >{cls.symbol}</button>{/if}
                    {#if extinction.best === k}<span class="mark">rietx's pick</span>{/if}
                    {#if cls.refuted && cls.n_present}
                      <span class="why">refuted by {(cls.forbidden_hkl ?? []).slice(0, 3)
                        .map((hkl: number[], j: number) =>
                          `${formatHkl(hkl)} ${cls.forbidden_two_theta?.[j]?.toFixed(2) ?? "?"}°`)
                        .join(", ")}</span>
                    {/if}
                  </td>
                  <td class="r">{cls.screened ? cls.delta_bic.toFixed(1) : "–"}</td>
                  <td class="r">{#if cls.n_absent}{cls.screened ? cls.n_testable : "–"} <span
                    class="muted">of {cls.n_absent}</span>{:else}–{/if}</td>
                  <td class="muted">{cls.refuted ? "refuted" : !cls.screened ? "not screened"
                    : cls.space_groups.join(", ")}</td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <ul class="strip">
          {#each screen.diagnostics ?? [] as d (d.code + d.message)}
            <li class={d.level}><span class="mono"><Help for="diagnostics:{d.code}"
              >{d.code}</Help></span> {d.message}</li>
          {/each}
        </ul>
        {#if activeClass !== null && screen.candidates[activeClass]}
          {@const cls = screen.candidates[activeClass]}
          <div class="form">
            <span class="lab">Adopt in</span>
            <span class="field">
              <div class="segmented sgs" role="group" aria-label="Space group">
                {#each cls.space_groups as sg (sg)}
                  <button class:on={activeGroup === sg} aria-pressed={activeGroup === sg}
                    onclick={() => (chosenGroup = sg)}>{sg}</button>
                {/each}
              </div>
            </span>
          </div>
        {/if}
      {/if}

      <div class="foot">
        <button class="ghost" disabled={busy}
          onclick={() => adopt(i, activeGroup ?? undefined)}>Adopt as a Le Bail start</button>
        <span class="muted why">Grade {c.confidence}{caveatWords(c).length
          ? `: ${caveatWords(c).join(", ")}` : ""}{activeGroup ? `, in ${activeGroup}` : ""}</span>
      </div>
    {/if}
  {/if}

  {#snippet moreSettings()}
    <details class="fold search">
      <summary>More settings{#if digest}<span class="muted"> · {digest}</span>{/if}</summary>
      <div class="grid" class:frozen={busy}>
        <div class="block">
          <span class="lab"><Help for={searchHelp(field("engines"))}
            >{field("engines").label}</Help></span>
          {#each enginesVocab as e (e.name)}
            <label class="opt" title={e.description}>
              <input type="checkbox" disabled={busy}
                checked={draft!.engines === null || draft!.engines.includes(e.name)}
                onchange={() => toggleEngine(e.name)} />
              {e.name}
            </label>
          {/each}
        </div>
        {#each systemsVocab as s (s)}
          {#if (draft!.search.systems === null || draft!.search.systems.includes(s))
            && (centringsVocab[s]?.length ?? 0) > 1}
            <div class="block">
              <span class="lab">Centrings, {s}</span>
              {#each centringsVocab[s] as letter (letter)}
                {@const cOn = !draft!.search.centrings?.[s]
                  || draft!.search.centrings[s].includes(letter)}
                <label class="opt"><input type="checkbox" disabled={busy} checked={cOn}
                  onchange={() => toggleCentring(s, letter)} /> {letter}</label>
              {/each}
            </div>
          {/if}
        {/each}
        <div class="row">
          <label class="num">
            <Help for={searchHelp(field("total_budget_seconds"))}
              >{field("total_budget_seconds").label}</Help>
            <input type="text" inputmode="decimal" disabled={busy}
              value={draft!.search.total_budget_seconds ?? ""}
              onchange={(ev) => setSearch("total_budget_seconds",
                numOrNull((ev.currentTarget as HTMLInputElement).value))} />
          </label>
          <label class="num">
            <Help for={searchHelp(field("budget_seconds"))}
              >{field("budget_seconds").label}</Help>
            <input type="text" inputmode="decimal" disabled={busy}
              value={draft!.search.budget_seconds}
              onchange={(ev) => setSearch("budget_seconds",
                numOrNull((ev.currentTarget as HTMLInputElement).value)
                  ?? draft!.search.budget_seconds)} />
          </label>
          <label class="num">
            <Help for={searchHelp(field("validate_candidates"))}
              >{field("validate_candidates").label}</Help>
            <input type="checkbox" disabled={busy}
              checked={draft!.validate_candidates}
              onchange={(ev) => {
                draft!.validate_candidates =
                  (ev.currentTarget as HTMLInputElement).checked;
                commit();
              }} />
          </label>
          <label class="num">
            <Help for={searchHelp(field("check_top"))}>{field("check_top").label}</Help>
            <input type="text" inputmode="numeric" disabled={busy}
              value={draft!.check_top ?? ""}
              onchange={(ev) => {
                draft!.check_top =
                  numOrNull((ev.currentTarget as HTMLInputElement).value);
                commit();
              }} />
          </label>
        </div>
        <div class="row">
          {#each [["min_d_axis", draft!.search.min_d_axis],
                  ["max_d_axis", draft!.search.max_d_axis],
                  ["min_volume", draft!.search.min_volume]] as [name, value] (name)}
            <label class="num">
              <Help for={searchHelp(field(name as string))}
                >{field(name as string).label}</Help>
              <input type="text" inputmode="decimal" disabled={busy}
                value={value}
                onchange={(ev) => setSearch(name as string,
                  numOrNull((ev.currentTarget as HTMLInputElement).value)
                    ?? value)} />
            </label>
          {/each}
          <!-- the specimen's formula sits beside the volume limits it would
               set (WP-2030); a temperature without one is refused, so its
               box waits for a formula -->
          <label class="num">
            <Help for={searchHelp(field("formula"))}>{field("formula").label}</Help>
            <input type="text" spellcheck="false" disabled={busy}
              placeholder="e.g. CuSO4·5H2O"
              value={draft!.formula ?? ""}
              onchange={(ev) => {
                setFormula(draft!,
                  (ev.currentTarget as HTMLInputElement).value);
                commit();
              }} />
          </label>
          <label class="num">
            <Help for={searchHelp(field("temperature"))}
              >{field("temperature").label}</Help>
            <input type="text" inputmode="decimal"
              disabled={busy || draft!.formula === null}
              value={draft!.temperature ?? ""}
              onchange={(ev) => {
                draft!.temperature =
                  numOrNull((ev.currentTarget as HTMLInputElement).value);
                commit();
              }} />
          </label>
        </div>
        <div class="row">
          {#each [["n_unindexed", draft!.search.n_unindexed],
                  ["n_search_lines", draft!.search.n_search_lines],
                  ["k_sigma", draft!.search.k_sigma],
                  ["shift_allowance_deg", draft!.search.shift_allowance_deg],
                  ["max_candidates", draft!.search.max_candidates],
                  ["seed", draft!.search.seed]] as [name, value] (name)}
            <label class="num">
              <Help for={searchHelp(field(name as string))}
                >{field(name as string).label}</Help>
              <input type="text" inputmode="decimal" disabled={busy}
                value={value}
                onchange={(ev) => setSearch(name as string,
                  numOrNull((ev.currentTarget as HTMLInputElement).value)
                    ?? value)} />
            </label>
          {/each}
          <label class="num">
            <Help for={searchHelp(field("shift_template"))}
              >{field("shift_template").label}</Help>
            <select disabled={busy}
              value={draft!.search.shift_template ?? ""}
              onchange={(ev) => setSearch("shift_template",
                (ev.currentTarget as HTMLSelectElement).value || null)}>
              <option value="">none</option>
              {#each templatesVocab as t (t)}<option value={t}>{t}</option>{/each}
            </select>
          </label>
        </div>
        <div class="block">
          <span class="lab"><Help for={searchHelp(field("prior_cells"))}
            >{field("prior_cells").label}</Help></span>
          {#each draft!.search.prior_cells ?? [] as cell, i (i)}
            <span class="tagged">
              <span class="mono">{priorCellText(cell)}</span>
              <button class="ghost" disabled={busy} title="Drop this prior"
                onclick={() => removePriorCell(i)}>×</button>
            </span>
          {/each}
          <input class="add" type="text" disabled={busy}
            placeholder="a b c α β γ" bind:value={priorText}
            onkeydown={(ev) => ev.key === "Enter" && addPriorCell()} />
          <button class="ghost" disabled={busy || !priorText.trim()}
            onclick={addPriorCell}>Add</button>
        </div>
        <div class="block">
          <span class="lab"><Help for={searchHelp(field("prior_spacegroups"))}
            >{field("prior_spacegroups").label}</Help></span>
          {#each draft!.search.prior_spacegroups ?? [] as sg, i (sg + i)}
            <span class="tagged">
              <span class="mono">{sg}</span>
              <button class="ghost" disabled={busy} title="Drop this prior"
                onclick={() => removePriorSg(i)}>×</button>
            </span>
          {/each}
          <input class="add" type="text" disabled={busy}
            placeholder="e.g. R -3 c" bind:value={sgText}
            onkeydown={(ev) => ev.key === "Enter" && addPriorSg()} />
          <button class="ghost" disabled={busy || !sgText.trim()}
            onclick={addPriorSg}>Add</button>
        </div>
      </div>
    </details>
  {/snippet}
</section>

<style>
  section {
    padding: 0 var(--s3) var(--s3);
    overflow: auto;
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }

  /* the step strip: a tab strip whose words carry their number */
  .steps {
    flex: 0 0 auto;
    position: sticky;
    top: 0;
    z-index: 2;
    background: var(--panel);
    display: flex;
    flex-wrap: wrap;
    border-bottom: 1px solid var(--line);
  }
  .steps .n {
    color: var(--muted);
    margin-right: var(--s1);
  }

  h3 {
    margin: var(--s3) 0 0;
  }

  .bar, .foot, .nav {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s2);
    align-items: center;
    flex: 0 0 auto;
  }
  .foot {
    position: sticky;
    bottom: calc(-1 * var(--s3));
    background: var(--panel);
    padding: var(--s2) 0;
    border-top: 1px solid var(--line);
    margin-top: var(--s2);
  }
  .grow { flex: 1 1 auto; }
  .why {
    flex: 1 1 12em;
    min-width: 0;
  }
  .empty {
    display: flex;
    justify-content: center;
    padding: var(--s3) 0;
  }

  /* a form: labels in one column that fits the longest, fields after */
  .form {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--s2) var(--s3);
    align-items: center;
    font-size: var(--text-sm);
  }
  .form.frozen, .grid.frozen { opacity: 0.6; }
  .lab { color: var(--muted); }
  .field {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
    min-width: 0;
  }
  .field.wrap { flex-wrap: wrap; gap: var(--s1) var(--s3); }
  .field input[type="text"] {
    width: 8ch;
    font-family: var(--mono-family, monospace);
  }
  .add {
    width: 10ch;
  }
  .opt {
    display: inline-flex;
    gap: var(--s1);
    align-items: center;
    white-space: nowrap;
  }

  details.fold {
    flex: 0 0 auto;
    font-size: var(--text-sm);
  }
  details.fold summary {
    cursor: pointer;
    color: var(--muted);
    user-select: none;
    padding: var(--s1) 0;
  }

  .grid {
    display: flex;
    flex-direction: column;
    gap: var(--s2);
    padding: var(--s1) 0;
  }
  .block, .row {
    display: flex;
    gap: var(--s2);
    flex-wrap: wrap;
    align-items: center;
  }
  .row { align-items: flex-end; }
  .num {
    display: inline-flex;
    flex-direction: column;
    gap: 1px;
    color: var(--muted);
  }
  .num input[type="text"] { width: 9ch; }
  .num input[type="checkbox"] { align-self: flex-start; }
  .tagged {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
  }

  /* each table scrolls in a window of its own (WP-1032's measurement) */
  .scroll {
    overflow: auto;
    flex: 0 0 auto;
    max-height: 45vh;
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
    white-space: nowrap;
    vertical-align: top;
  }
  th.r, td.r { text-align: right; }
  td.ck, th.ck { width: 1.5em; padding-right: var(--s2); }
  td.note { white-space: normal; }
  /* a greyed row stays clickable: it is dimmed by colour, never by
     pointer-events (round 11's fault) */
  tr.out td { color: var(--muted); }
  tr.lit td { background: color-mix(in srgb, var(--accent) 12%, transparent); }
  tr.sel td { background: color-mix(in srgb, var(--accent) 18%, transparent); }
  .candidates tr.lit td {
    background: color-mix(in srgb, var(--plot-candidate) 16%, transparent);
  }
  td.hi { color: var(--warn); }
  td.on { color: var(--fg); }
  .pos { font: inherit; }
  td.cell { white-space: normal; min-width: 12em; }
  td.cell .rel, td.cell .why {
    display: block;
    overflow-wrap: anywhere;
  }
  .mark {
    margin-left: var(--s2);
    color: var(--accent);
  }
  .acts {
    display: flex;
    gap: 2px;
    align-items: center;
  }

  .coverage { flex: 0 0 auto; }
  .coverage.short {
    border-left: 2px solid var(--warn);
    padding-left: var(--s2);
  }
  .coverage p { margin: 0; }
  .strip {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: var(--text-sm);
  }
  .strip li { padding: 1px 0; color: var(--muted); }
  .strip li.warning { color: var(--warn); }
  .strip li.error { color: var(--bad); }
  .strip .where::before { content: " · "; }

  .cellline { margin: var(--s1) 0 0; }
  p.rel { margin: 0; min-height: 1.4em; }
  .caveats {
    display: flex;
    flex-wrap: wrap;
    gap: var(--s1) var(--s3);
    margin: var(--s1) 0;
    font-size: var(--text-sm);
  }
  .caveats .bad { color: var(--bad); }
  dl.kv {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: 2px var(--s3);
    margin: var(--s1) 0;
    font-size: var(--text-sm);
  }
  dl.kv dt { color: var(--muted); }
  dl.kv dd { margin: 0; }
  .sgs { flex-wrap: wrap; }
  p { margin: var(--s1) 0; }
</style>
