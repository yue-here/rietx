<script lang="ts">
  /**
   * The peaks-and-indexing workflow's Index and Judge steps at `/next`
   * (WP-2240, tasks 7 and 8), mounted beside the Pick and Fit steps for the
   * workflow's life, so a step switch keeps the answer and the chosen row.
   *
   * Index (round 11, calls 4-9). The short form holds the crystal systems,
   * the largest volume ("from data" until typed) and the time limit; the rest
   * sits under More settings. The form is `ProjectDoc.indexing`, committed
   * whole on each edit (WP-1045), so the search a person set is the one the
   * next run reads. While the search runs: each system's state, the cells
   * found so far ungraded, and a foot with Stop and the clock (calls 5, 15).
   * When it ends, a line edged in the danger colour names the systems not
   * searched and those stopped early (call 6, WP-1042's "not reached is
   * loud"). Then the candidates, ranked by rietx, each a row with its
   * relation to another marked rather than merged (calls 7, 8). A row chooses
   * the candidate and draws its lines on the Pattern graph (call 9). Never a
   * confident singleton: the list is the answer, and the gate's pick is said
   * in Judge beside Adopt (`src/rietx/indexing/CLAUDE.md`).
   *
   * Judge (calls 10-12, 17). One candidate's evidence: its cell with esds,
   * its relation to another row, the grade and its caveats in words (a
   * refuting one in the danger colour), the Le Bail check, every figure of
   * merit with its blind spot a click away, and the engines that found it.
   * Screen extinctions ranks the extinction classes by ΔBIC; a refuted class
   * stays, muted, as evidence, and "rietx's pick" marks the class the gate
   * names. A class offers its space groups, its representative first. Adopt
   * takes any candidate (the maintainer's ruling B, 2026-11-08) with its
   * grade and caveats beside it, and is pending until Apply, which adopts the
   * cell as a Pawley start (the maintainer, 2026-11-23: Pawley is the
   * structure-free default) and returns the window to Refinement (call 11).
   *
   * The answer outlives this page: it is read from the server on mount and
   * after each run, and every index into it is dropped when a new answer
   * renumbers the candidates.
   */
  import { onMount } from "svelte";

  import { api } from "../api";
  import Help from "../Help.svelte";
  import {
    CONTROL_FIELDS, SEARCH_FIELDS, controlsFromDoc, foldSnapshots, parsePriorCell,
    priorCellText, searchHelp, setFormula, type IndexingControls,
  } from "../lib/controls";
  import type { HelpCorpus } from "../lib/help";
  import { clone } from "../lib/model";
  import { typesetSpaceGroup } from "../lib/spacegroup";
  import {
    absentOf, candidateRelation, cellColumns, cellLine, cellText, clock, collectTo, coverageLine,
    fomOf,
    formatHkl, limitWord,
    unindexedOf, type AdoptVerdict, type Candidate,
  } from "../lib/peaks";
  import type { CandidateOverlay } from "../lib/plot";
  import type { RunState } from "../lib/stream";
  import { serverScript, type Say } from "./console";

  let {
    step = 2,
    busy = false,
    run = null,
    doc = null,
    capabilities = null,
    corpus = null,
    nLines = 0,
    say = () => {},
    onstep = () => {},
    onproject = () => {},
    oncandidate = () => {},
    onadopted = () => {},
  }: {
    step?: number;
    busy?: boolean;
    run?: RunState | null;
    /** the project document; `doc.indexing` is the form's one authority */
    doc?: any;
    /** `/api/capabilities`: the vocabularies the form draws from */
    capabilities?: any;
    corpus?: HelpCorpus | null;
    /** how many picked lines the search would use */
    nLines?: number;
    say?: Say;
    onstep?: (step: number) => void;
    /** the document after a settings edit landed */
    onproject?: (doc: any) => void;
    /** the chosen candidate's lines for the Pattern graph, or none */
    oncandidate?: (overlay: CandidateOverlay | null) => void;
    /** a candidate was adopted: the model moved and the window goes back to
     *  Refinement */
    onadopted?: () => void;
  } = $props();

  // -- the answer ----------------------------------------------------------

  let answer = $state.raw<any>(null);
  /** the streamed per-system shortlists of the run in flight (WP-1045) */
  let snapshots = $state.raw<Array<Record<string, any>>>([]);
  let failure = $state("");
  /** the candidate chosen in the table, which Judge shows */
  let chosen = $state<number | null>(null);

  const candidates = $derived<Candidate[]>(answer?.result?.candidates ?? []);
  const verdicts = $derived<AdoptVerdict[]>(answer?.adopt ?? []);
  const indexing = $derived(busy && run?.run?.kind === "index");
  const shortlists = $derived(foldSnapshots(snapshots));

  onMount(async () => {
    await loadAnswer();
    await loadExtinction();
  });

  async function loadAnswer() {
    try {
      answer = await api.indexResult();
    } catch {
      // nothing has run in this session: the empty state, not a failure
      answer = null;
    }
    // new candidates, new numbering: the screen and the pending adopt are
    // about cells that no longer have these indices (the server 409s too)
    extinction = null;
    pending = null;
    void choose(null);
  }

  /** An engine event from the shell's stream: a search starting clears the
   *  shortlists, and each system's consensus is one more (WP-1045). */
  export function event(e: { kind: string; data?: Record<string, any> }) {
    if (e.kind === "index_start") snapshots = [];
    else if (e.kind === "stage_end" && e.data?.consensus) snapshots = [...snapshots, e.data];
  }

  /** A run of this workflow's ended: read what it left. */
  export function ran(kind: string | null) {
    if (kind === "index") void loadAnswer();
    else if (kind === "extinction") void loadExtinction();
  }

  // -- Judge -----------------------------------------------------------------

  /** the last extinction screen, about one candidate (`extinction.candidate`) */
  let extinction = $state.raw<any>(null);
  const screen = $derived(extinction?.candidate === chosen ? extinction?.result ?? null : null);
  const screening = $derived(busy && run?.run?.kind === "extinction");
  /** the class and the space group chosen; until then the gate's pick and
   *  its representative (calls 10, 12) */
  let chosenClass = $state<number | null>(null);
  let chosenGroup = $state<string | null>(null);
  /** Adopt pressed and not yet applied: the space group it will adopt in */
  let pending = $state<{ index: number; group: string | null } | null>(null);

  async function loadExtinction() {
    try {
      extinction = await api.extinctionResult();
    } catch {
      // none run, or cleared by a new indexing run
      extinction = null;
    }
    chosenClass = null;
    chosenGroup = null;
    // an Adopt pressed before this screen named a group from no screen, or
    // from the last one
    pending = null;
  }

  const classOrder = $derived.by(() => {
    const list = (screen?.candidates ?? []).map((c: any, k: number) => ({ c, k }));
    // live classes first, then by ΔBIC (the prototype's order)
    return list.sort((x: any, y: any) => Number(x.c.refuted) - Number(y.c.refuted)
      || (x.c.screened ? x.c.delta_bic : Infinity) - (y.c.screened ? y.c.delta_bic : Infinity));
  });
  const activeClass = $derived<number | null>(chosenClass
    ?? (screen ? extinction?.best ?? classOrder.find((x: any) => !x.c.refuted)?.k ?? null : null));
  const activeGroups = $derived.by<string[]>(() => {
    const cls = activeClass === null ? null : screen?.candidates?.[activeClass];
    if (!cls) return [];
    // the representative first: rietx's default within the class (call 12)
    return [...cls.space_groups].sort((a: string, b: string) =>
      Number(b === cls.representative) - Number(a === cls.representative));
  });
  const activeGroup = $derived(chosenGroup ?? activeGroups[0] ?? null);

  /** Show candidate `i` in Judge, as its row's click and ‹ › do. */
  export function judge(i: number) {
    pending = null;
    chosenClass = null;
    chosenGroup = null;
    void choose(i);
  }

  async function screenExtinctions(i: number) {
    failure = "";
    try {
      await api.screenExtinctions(i);
      say("call", `screen = rx.determine_extinction_symbol(data, result.candidates[${i}], instrument)`, null);
    } catch (exc) {
      failure = (exc as Error).message;
    }
  }

  async function apply() {
    if (!pending) return;
    failure = "";
    try {
      // Pawley is the structure-free default (the maintainer, 2026-11-23)
      const a = await api.adoptCandidate(pending.index, pending.group ?? undefined, "pawley");
      if (a?.api_call) say("call", a.api_call, serverScript(a.api_call));
      pending = null;
      onadopted();
    } catch (exc) {
      failure = (exc as Error).message;
    }
  }

  /** A grade's caveats in words, from the corpus where it has them. */
  const caveat = (k: string) => k.replaceAll("_", " ");
  /** the lines a refuted class forbids and the data shows, at most three */
  const refutation = (cls: any) => {
    const seen = (cls.forbidden_hkl ?? []).slice(0, 3).map((hkl: number[], j: number) =>
      `${formatHkl(hkl)} at ${cls.forbidden_two_theta?.[j]?.toFixed(2) ?? "?"}°`);
    return `This class forbids lines the data shows: ${seen.join(", ")}.`;
  };
  const refuting = $derived<string[]>(answer?.refuting_caveats ?? []);
  const FOM: Record<string, { word: string; sub?: string; pct?: boolean }> = {
    m20: { word: "M", sub: "20" }, f_n: { word: "F", sub: "N" },
    m_rev: { word: "M", sub: "rev" }, m_sym: { word: "M", sub: "sym" },
    indexed_fraction: { word: "Lines indexed", pct: true },
    indexed_intensity_fraction: { word: "Intensity indexed", pct: true },
    predicted_seen_fraction: { word: "Predicted lines seen", pct: true },
  };
  const fomValue = (f: { name: string; value: number | null }) =>
    f.value == null ? "–" : FOM[f.name]?.pct ? `${Math.round(100 * f.value)} %` : f.value.toFixed(2);

  // -- the candidate's lines on the Pattern graph (call 9) -----------------

  /** which numbering a lines fetch belongs to: a new answer bumps it */
  let era = 0;
  async function choose(i: number | null) {
    chosen = i;
    const mine = ++era;
    if (i === null || !candidates[i]) return oncandidate(null);
    try {
      const t = await api.candidateTicks(i);
      if (mine !== era) return;
      oncandidate({ label: `#${i + 1}`, two_theta: t.two_theta ?? [], hkl: t.hkl ?? [],
                    line: t.line, n_total: t.n_total ?? (t.two_theta?.length ?? 0) });
    } catch {
      // a cell too large to enumerate draws no lines; its volume says why
      if (mine === era) oncandidate(null);
    }
  }

  // -- the form (WP-1045) --------------------------------------------------

  let draft = $state<IndexingControls | null>(null);
  let formError = $state("");
  $effect(() => {
    // re-synced from the document whenever it moves, refusals included
    draft = doc ? clone(controlsFromDoc(doc)) : null;
  });

  const caps = $derived(capabilities ?? {});
  const systemsVocab = $derived<string[]>(caps.crystal_systems ?? []);
  const enginesVocab = $derived<Array<{ name: string; description: string }>>(
    caps.indexing_engines ?? []);
  const presetsVocab = $derived<Array<Record<string, any>>>(caps.search_presets ?? []);
  const centringsVocab = $derived<Record<string, string[]>>(caps.centrings ?? {});
  const templatesVocab = $derived<string[]>(caps.shift_templates ?? []);
  const defaultPreset = $derived<string>(presetsVocab.find((p) => p.default)?.name ?? "quick");
  /** the limits in rising order, the unbounded one last (the prototype's) */
  const limits = $derived([...presetsVocab].sort((x, y) =>
    (x.total_budget_seconds ?? Infinity) - (y.total_budget_seconds ?? Infinity)));
  const preset = $derived(draft?.search.preset ?? defaultPreset);
  const budget = $derived(draft?.search.total_budget_seconds
    ?? presetsVocab.find((p) => p.name === preset)?.total_budget_seconds ?? null);
  const asked = $derived<string[]>(draft?.search.systems ?? systemsVocab);
  const field = (name: string) => [...SEARCH_FIELDS, ...CONTROL_FIELDS].find((f) => f.name === name)!;
  /** a field's label in sentence case: the inventory's are lower case */
  const label = (name: string) => {
    const l = field(name).label;
    return l[0].toUpperCase() + l.slice(1);
  };

  async function commit() {
    if (!draft) return;
    formError = "";
    try {
      onproject(await api.patchProject({ indexing: draft }));
    } catch (exc) {
      formError = (exc as Error).message;
      // the document the server kept re-syncs the form
      try { onproject(await api.project()); } catch { /* the next head move does */ }
    }
  }

  function setSearch(name: string, value: unknown) {
    if (!draft) return;
    (draft.search as any)[name] = value;
    void commit();
  }

  /** empty text is the package default, sent as null */
  function numOrNull(text: string): number | null {
    const v = Number(text);
    return text.trim() === "" || !Number.isFinite(v) ? null : v;
  }

  /** Toggle one member of a list whose null means "all of them". */
  function toggled(list: string[] | null, all: string[], name: string): string[] | null | "empty" {
    const on = new Set(list ?? all);
    if (on.has(name)) on.delete(name);
    else on.add(name);
    if (!on.size) return "empty";
    return on.size === all.length ? null : all.filter((s) => on.has(s));
  }

  function toggleSystem(s: string) {
    const next = toggled(draft!.search.systems, systemsVocab, s);
    if (next === "empty") return (formError = "Keep at least one crystal system.");
    setSearch("systems", next);
  }

  function toggleEngine(name: string) {
    const next = toggled(draft!.engines, enginesVocab.map((e) => e.name), name);
    if (next === "empty") return (formError = "Keep at least one engine.");
    draft!.engines = next;
    void commit();
  }

  function toggleCentring(system: string, letter: string) {
    const allowed = centringsVocab[system] ?? [];
    const next = toggled(draft!.search.centrings?.[system] ?? null, allowed, letter);
    if (next === "empty") return (formError = `Keep one centring for ${system}, or leave the system out.`);
    const all = { ...(draft!.search.centrings ?? {}) };
    if (next === null) delete all[system];
    else all[system] = next;
    setSearch("centrings", Object.keys(all).length ? all : null);
  }

  function setLimit(name: string) {
    if (!draft) return;
    draft.search.preset = name === defaultPreset ? null : name;
    draft.search.total_budget_seconds = null;
    void commit();
  }

  let priorText = $state("");
  let sgText = $state("");
  function addPriorCell() {
    const parsed = parsePriorCell(priorText);
    if (typeof parsed === "string") return (formError = parsed);
    priorText = "";
    setSearch("prior_cells", [...(draft!.search.prior_cells ?? []), parsed]);
  }
  function addPriorSg() {
    if (!sgText.trim()) return;
    // validated by the server in gemmi's words (WP-1045)
    setSearch("prior_spacegroups", [...(draft!.search.prior_spacegroups ?? []), sgText.trim()]);
    sgText = "";
  }
  function dropPrior(name: "prior_cells" | "prior_spacegroups", i: number) {
    const kept = ((draft!.search as any)[name] ?? []).filter((_: unknown, k: number) => k !== i);
    setSearch(name, kept.length ? kept : null);
  }

  // -- the run -------------------------------------------------------------

  /** the systems the shown run asked for, kept from its start, so a form
   *  edited afterwards does not change what the coverage line says about it;
   *  a run started before a reload falls back to the form */
  let runAsked = $state<string[] | null>(null);
  async function startIndex() {
    failure = "";
    try {
      const sent = [...asked];
      await api.index();
      runAsked = sent;
      say("call", "result = rx.index_pattern(peaks, data=data, instrument=instrument)", null);
    } catch (exc) {
      failure = (exc as Error).message;
    }
  }

  async function stop() {
    try {
      await api.cancel();
      say("call", "token.cancel()", null);
    } catch (exc) {
      failure = (exc as Error).message;
    }
  }

  /** The run frame carries the elapsed time only when its state changes, so
   *  the clock counts on from the last frame by the browser's own time. */
  let frameElapsed = $state(0);
  let frameAt = $state(0);
  let now = $state(0);
  const stamped = $derived<number | null>(run?.run?.elapsed ?? null);
  /** a run's frames over the stream carry no elapsed time (only the polled
   *  state does), so a frame without one keeps the clock counting rather
   *  than restarting it at zero */
  let wasIndexing = false;
  $effect(() => {
    const on = indexing, s = stamped;
    if (s == null && on === wasIndexing) return;
    wasIndexing = on;
    frameElapsed = s ?? 0;
    frameAt = now = performance.now();
  });
  $effect(() => {
    if (!indexing) return;
    const id = setInterval(() => (now = performance.now()), 1000);
    return () => clearInterval(id);
  });
  const elapsed = $derived(frameElapsed + (indexing ? (now - frameAt) / 1000 : 0));

  function systemState(s: string): string {
    if (shortlists.some((snap) => snap.system === s)) return "searched";
    if (run?.run?.stage?.includes(s)) return "searching…";
    return "waiting";
  }
  /** the latest cells found, newest first, ungraded (call 5) */
  const found = $derived(shortlists.flatMap((snap) => (snap.candidates ?? [])
    .map((c: any) => ({ cell: c.cell as number[], system: snap.system }))).reverse().slice(0, 8));

  const coverage = $derived(coverageLine(answer?.result, runAsked ?? asked));
  const notes = $derived<any[]>(answer?.result?.diagnostics ?? []);
  /** a run with a formula adds Z, the formula units each cell holds (WP-2030) */
  const zColumn = $derived(answer?.result?.formula != null);

</script>

{#snippet toggles(names: string[], on: (n: string) => boolean, flip: (n: string) => void, aria: string)}
  <span class="tgs" role="group" aria-label={aria}>
    {#each names as n (n)}
      <button class="ib tg" aria-pressed={on(n)} disabled={busy} onclick={() => flip(n)}>{n}</button>
    {/each}
  </span>
{/snippet}

{#snippet sg(symbol: string)}
  <span class="sg" aria-label={symbol}>{#each symbol.trim().split(/\s+/) as word, wi (wi)}{#if word === "-"}–{:else}{#each typesetSpaceGroup(word) as t, ti (ti)}{#if t.kind === "italic"}<i>{t.text}</i>{:else if t.kind === "bar"}<span class="bar">{t.text}</span>{:else if t.kind === "screw"}{t.text}<sub>{t.sub}</sub>{:else if t.kind === "slash"}/{:else if t.kind === "ext"}<small>{t.text}</small>{:else}{t.text}{/if}{/each}{/if}{/each}</span>
{/snippet}

{#snippet fomName(name: string)}
  {#if FOM[name]}{FOM[name].word}{#if FOM[name].sub}<sub>{FOM[name].sub}</sub>{/if}{:else}{name}{/if}
{/snippet}

{#snippet noteList(list: any[])}
  {#each list as d, i (i)}
    <p class="dg"><b>{d.level === "warning" || d.level === "error" ? "Warning." : "Note."}</b>
      {d.message}{#if d.where?.length}{" "}<span class="muted">({d.where.join("; ")})</span>{/if}</p>
  {/each}
{/snippet}

<div class="steppane" class:gone={step !== 2}>
  <div class="body">
    {#if failure}<p class="bad">{failure}</p>{/if}
    {#if draft}
      <div class="form">
        <div class="field">
          <span class="label"><Help for={searchHelp(field("systems"))}>Crystal systems</Help></span>
          {@render toggles(systemsVocab, (s) => draft!.search.systems === null
            || draft!.search.systems.includes(s), toggleSystem, "Crystal systems")}
        </div>
        <div class="field">
          <span class="label"><Help for={searchHelp(field("max_volume"))}>Largest volume</Help></span>
          <input class="num" inputmode="decimal" placeholder="from data" disabled={busy}
            aria-label="Largest cell volume" value={draft.search.max_volume ?? ""}
            onchange={(ev) => setSearch("max_volume", numOrNull((ev.currentTarget as HTMLInputElement).value))} />
          <span class="u">Å³</span>
        </div>
        <div class="field">
          <span class="label"><Help for={searchHelp(field("preset"))}>Time limit</Help></span>
          <span class="segmented" role="group" aria-label="Time limit">
            {#each limits as p (p.name)}
              {@const on = draft.search.total_budget_seconds == null && preset === p.name}
              <button class:on aria-pressed={on} disabled={busy}
                onclick={() => setLimit(p.name)}>{limitWord(p.total_budget_seconds)}</button>
            {/each}
          </span>
        </div>
        <details class="notes more">
          <summary>More settings</summary>
          <div class="field">
            <span class="label"><Help for={searchHelp(field("engines"))}>{label("engines")}</Help></span>
            {@render toggles(enginesVocab.map((e) => e.name), (n) => draft!.engines === null
              || draft!.engines.includes(n), toggleEngine, "Engines")}
          </div>
          {#each asked.filter((s) => (centringsVocab[s]?.length ?? 0) > 1) as s (s)}
            <div class="field">
              <span class="label"><Help for={searchHelp(field("centrings"))}>Centrings, {s}</Help></span>
              {@render toggles(centringsVocab[s], (c) => !draft!.search.centrings?.[s]
                || draft!.search.centrings[s].includes(c), (c) => toggleCentring(s, c), `Centrings, ${s}`)}
            </div>
          {/each}
          {#each ["min_d_axis", "max_d_axis", "min_volume", "n_search_lines", "n_unindexed",
                  "k_sigma", "shift_allowance_deg", "budget_seconds", "total_budget_seconds",
                  "max_candidates", "seed"] as name (name)}
            {@const v = (draft.search as any)[name]}
            <div class="field">
              <span class="label"><Help for={searchHelp(field(name))}>{label(name)}</Help></span>
              <input class="num" inputmode="decimal" disabled={busy} value={v ?? ""}
                placeholder={field(name).optional ? "default" : undefined} aria-label={label(name)}
                onchange={(ev) => setSearch(name, numOrNull((ev.currentTarget as HTMLInputElement).value)
                  ?? (field(name).optional ? null : v))} />
            </div>
          {/each}
          <div class="field">
            <span class="label"><Help for={searchHelp(field("shift_template"))}>{label("shift_template")}</Help></span>
            <select disabled={busy} value={draft.search.shift_template ?? ""} aria-label={label("shift_template")}
              onchange={(ev) => setSearch("shift_template", (ev.currentTarget as HTMLSelectElement).value || null)}>
              <option value="">none</option>
              {#each templatesVocab as t (t)}<option value={t}>{t}</option>{/each}
            </select>
          </div>
          <div class="field">
            <span class="label"><Help for={searchHelp(field("validate_candidates"))}>Validation</Help></span>
            <label class="check"><input type="checkbox" disabled={busy} checked={draft.validate_candidates}
              onchange={(ev) => { draft!.validate_candidates = (ev.currentTarget as HTMLInputElement).checked;
                                  void commit(); }} /> Check the best cells by a Le Bail fit</label>
          </div>
          <div class="field">
            <span class="label"><Help for={searchHelp(field("check_top"))}>{label("check_top")}</Help></span>
            <input class="num" inputmode="numeric" disabled={busy} placeholder="default"
              aria-label={label("check_top")} value={draft.check_top ?? ""}
              onchange={(ev) => { draft!.check_top = numOrNull((ev.currentTarget as HTMLInputElement).value);
                                  void commit(); }} />
          </div>
          <div class="field">
            <span class="label"><Help for={searchHelp(field("formula"))}>{label("formula")}</Help></span>
            <input class="text" spellcheck="false" disabled={busy} placeholder="none"
              aria-label="Formula" value={draft.formula ?? ""}
              onchange={(ev) => { setFormula(draft!, (ev.currentTarget as HTMLInputElement).value);
                                  void commit(); }} />
          </div>
          <div class="field">
            <span class="label"><Help for={searchHelp(field("temperature"))}>{label("temperature")}</Help></span>
            <input class="num" inputmode="decimal" disabled={busy || draft.formula === null}
              placeholder="default" aria-label={label("temperature")} value={draft.temperature ?? ""}
              onchange={(ev) => { draft!.temperature = numOrNull((ev.currentTarget as HTMLInputElement).value);
                                  void commit(); }} />
          </div>
          {#each [["prior_cells", priorCellText], ["prior_spacegroups", (s: string) => s]] as const as [name, show] (name)}
            <div class="field">
              <span class="label"><Help for={searchHelp(field(name))}>{label(name)}</Help></span>
              {#each (draft.search as any)[name] ?? [] as item, i (i)}
                <span class="prior num">{(show as (x: any) => string)(item)}<button class="ib" disabled={busy}
                  title="Drop this prior" onclick={() => dropPrior(name, i)}>×</button></span>
              {/each}
              {#if name === "prior_cells"}
                <input class="text" disabled={busy} placeholder="a b c α β γ" bind:value={priorText}
                  aria-label="Add an analogue cell" onkeydown={(ev) => ev.key === "Enter" && addPriorCell()} />
              {:else}
                <input class="text" disabled={busy} placeholder="symbol" bind:value={sgText}
                  aria-label="Add an analogue space group" onkeydown={(ev) => ev.key === "Enter" && addPriorSg()} />
              {/if}
            </div>
          {/each}
        </details>
        {#if formError}<p class="bad">{formError}</p>{/if}
      </div>
    {/if}

    {#if indexing}
      <h3>Searching</h3>
      <table class="lines sys">
        <tbody>
          {#each asked as s (s)}
            {@const state = systemState(s)}
            <tr><td>{s}</td><td class="note" class:live={state === "searching…"}>{state}</td></tr>
          {/each}
        </tbody>
      </table>
      {#if found.length}
        <h3>Found so far <span class="muted">not graded until the search ends</span></h3>
        <table class="lines found">
          <tbody>
            {#each found as f, i (i)}
              <tr><td class="num">{cellLine({ cell: f.cell, cell_esd: [], system: f.system })}</td>
                <td class="note">{f.system}</td></tr>
            {/each}
          </tbody>
        </table>
      {/if}
    {:else if answer}
      {#if coverage.notSearched.length || coverage.stopped.length}
        <!-- what the search did not cover, said whatever it found (WP-1042) -->
        <p class="coverage">
          {#if coverage.notSearched.length}Not searched: {coverage.notSearched.join(", ")}.{/if}
          {#if coverage.stopped.length}Stopped early: {coverage.stopped.join(", ")}.{/if}
          {#if coverage.ceiling != null}The {coverage.ceiling % 60 ? `${coverage.ceiling}-second`
            : `${coverage.ceiling / 60}-minute`} limit ran out.{/if}
        </p>
      {/if}
      {#if !candidates.length}
        <p class="muted">No candidate cells.{#if answer.result?.quality?.abstained_reason}
          {" "}{answer.result.quality.abstained_reason}{/if}</p>
      {:else}
        <h3>Candidates <span class="muted">{candidates.length}, ranked by rietx</span></h3>
        <table class="lines cands">
          <thead>
            <!-- the cell as six columns, and a row's relation to another on its own
                 line, compact, its sentence a click away (the maintainer, 2026-11-23) -->
            <tr><th class="r">#</th><th aria-label="Relation"></th>
              {#each ["a", "b", "c", "α", "β", "γ"] as n (n)}<th class="r">{n}</th>{/each}
              <th>Lattice</th><th class="r">V</th>
              {#if zColumn}<th class="r"><Help for={searchHelp(field("formula"))}>Z</Help></th>{/if}
              <th class="r">M₂₀</th><th class="r">Unindexed</th><th class="r">Absent</th>
              <th class="r">Rwp</th><th>Grade</th></tr>
          </thead>
          <tbody>
            {#each candidates as c, i (i)}
              {@const m20 = fomOf(c, "m20")}
              {@const ab = absentOf(c)}
              {@const rel = candidateRelation(candidates, i)}
              <tr class:sel={chosen === i} data-cand={i} onclick={() => { if (i !== chosen) judge(i); }}>
                <td class="r num">{i + 1}</td>
                <td class="rel num">{#if rel}<Help text={rel.text}>{rel.mark}</Help>{/if}</td>
                {#each cellColumns(c) as col, k (k)}
                  <td class="r num" class:fixed={col.fixed}>{col.value}{#if col.pad}<span
                    class="pad" style:width="{col.pad.length}ch"></span>{/if}</td>
                {/each}
                <td>{c.system} {c.centring}</td>
                <td class="r num">{c.volume.toFixed(0)}</td>
                {#if zColumn}<td class="r num">{c.formula_units == null ? "–" : c.formula_units.toFixed(2)}</td>{/if}
                <td class="r num">{m20 === null ? "–" : m20.toFixed(1)}</td>
                <td class="r num">{unindexedOf(c)}</td>
                <td class="r num">{#if ab}{ab.absent}<span class="u">{" "}of {ab.of}</span>{:else}–{/if}</td>
                <td class="r num">{c.lebail ? `${(c.lebail.rwp * 100).toFixed(1)} %` : "–"}</td>
                <td>{c.confidence}</td>
              </tr>
            {/each}
          </tbody>
        </table>
      {/if}
      {#if notes.length}
        <details class="notes">
          <summary>Notes from the search ({notes.length})</summary>
          {@render noteList(notes)}
        </details>
      {/if}
    {/if}
  </div>
  <div class="foot">
    {#if indexing}
      <button class="ghost" onclick={stop}>Stop</button>
      <span class="why num">{clock(elapsed)} elapsed{#if budget != null}{" "}· about
        {clock(Math.max(0, budget - elapsed))} left{/if}</span>
    {:else if answer && candidates.length}
      <button disabled={chosen === null} onclick={() => onstep(3)}
        >Judge{chosen === null ? "" : ` #${chosen + 1}`} ›</button>
      <button class="ghost" disabled={busy || !nLines} onclick={startIndex}>Index again</button>
    {:else}
      <button disabled={busy || !nLines} onclick={startIndex}>{answer ? "Index again" : "Index"}</button>
      {#if !nLines}<span class="why">Pick peaks first.</span>{/if}
    {/if}
  </div>
</div>

<div class="steppane" class:gone={step !== 3}>
  {#if chosen === null || !candidates[chosen]}
    <div class="body">
      <p class="empty"><button class="ghost" onclick={() => onstep(2)}>Choose a candidate in Index</button></p>
    </div>
  {:else}
    {@const i = chosen}
    {@const c = candidates[i]}
    {@const ab = absentOf(c)}
    <div class="body">
      {#if failure}<p class="bad">{failure}</p>{/if}
      <div class="nav">
        <button class="ib" aria-label="Previous candidate" disabled={i === 0}
          onclick={() => judge(i - 1)}>‹</button>
        <span><b>#{i + 1}</b> <span class="muted">of {candidates.length}</span></span>
        <button class="ib" aria-label="Next candidate" disabled={i >= candidates.length - 1}
          onclick={() => judge(i + 1)}>›</button>
        <span class="grow"></span>
        <span class="muted">{c.system} {c.centring}</span>
      </div>
      <p class="num cellline">{cellLine(c, true)}, V = {c.volume.toFixed(1)} Å³</p>
      <!-- the relation line keeps its height when empty, so stepping between
           candidates moves nothing under it -->
      <p class="relline">{candidateRelation(candidates, i)?.text ?? " "}</p>

      <h3>Grade <span class="muted">{c.confidence}</span></h3>
      <p class="caveats">
        {#each c.confidence_caveats as k, ki (k)}{#if ki}{", "}{/if}<span
          class:bad={refuting.includes(k)}>{caveat(k)}</span>{:else}<span class="muted">no caveats</span>{/each}
      </p>

      <h3>Le Bail check</h3>
      {#if c.lebail}
        <dl class="kv">
          <dt>Rwp</dt><dd class="num">{(c.lebail.rwp * 100).toFixed(1)} %</dd>
          <dt>Predicted lines with no peak</dt>
          <dd><span class="num">{ab?.absent}</span> of <span class="num">{ab?.of}</span></dd>
          <dt>Peaks no line explains</dt><dd class="num">{c.lebail.unmatched_observed ?? "–"}</dd>
        </dl>
      {:else}
        <p class="muted">Not checked by a Le Bail fit.</p>
      {/if}

      <h3>Figures of merit</h3>
      <dl class="kv">
        {#each c.fom as f (f.name)}
          <!-- each figure's blind spot is one click away -->
          <dt>{#if f.blind_spot}<Help text={f.blind_spot}>{@render fomName(f.name)}</Help>
            {:else}{@render fomName(f.name)}{/if}</dt>
          <dd class="num">{fomValue(f)}</dd>
        {/each}
        <dt>Found by</dt><dd>{c.found_by.join(", ")}</dd>
      </dl>
      {#each c.ambiguity ?? [] as partner, k (k)}
        <p class="partner">Geometrically indistinguishable from <span class="num"
          >{cellText(partner.cell)}</span> ({partner.system}, index {partner.index}).</p>
      {/each}
      {#if collectTo(c) !== null}
        <p class="warn">Collect to 2θ ≈ {collectTo(c)?.toFixed(1)}° to tell this cell from its partner.</p>
      {/if}
      {#if c.diagnostics?.length}
        <details class="notes">
          <summary>Notes on this cell ({c.diagnostics.length})</summary>
          {@render noteList(c.diagnostics)}
        </details>
      {/if}

      <h3>Space group</h3>
      {#if !screen}
        <button class="ghost" disabled={busy} onclick={() => screenExtinctions(i)}
          >{screening ? "Screening extinctions…" : "Screen extinctions"}</button>
      {:else}
        <table class="lines classes">
          <thead>
            <tr><th>Class</th><th class="r">ΔBIC</th><th class="r">Tested</th><th>Groups</th></tr>
          </thead>
          <tbody>
            {#each classOrder as { c: cls, k } (k)}
              <!-- a refuted class stays, muted, as evidence (call 17) -->
              <tr class:off={cls.refuted} class:sel={activeClass === k} data-class={k}
                onclick={() => { chosenClass = k; chosenGroup = null; pending = null; }}>
                <td>{@render sg(cls.symbol)}{#if extinction?.best === k}<span class="mark">rietx's pick</span>{/if}</td>
                <td class="r num">{cls.screened ? cls.delta_bic.toFixed(1) : "–"}</td>
                <td class="r num">{#if cls.n_absent}{cls.screened ? cls.n_testable ?? "–" : "–"}<span
                  class="u">{" "}of {cls.n_absent}</span>{:else}–{/if}</td>
                <!-- the lines that refute a class are one click away, so each row
                     keeps one line as the prototype draws it -->
                <td class="note">{#if cls.refuted && cls.n_present}<Help text={refutation(cls)}>refuted</Help>{:else}{cls.refuted
                  ? "refuted" : !cls.screened ? "not screened"
                  : cls.space_groups.length === 1 ? "" : `${cls.space_groups.length} groups`}{/if}{#if
                  !cls.refuted && cls.screened && cls.space_groups.length === 1}{@render sg(cls.space_groups[0])}{/if}</td>
              </tr>
            {/each}
          </tbody>
        </table>
        {#if activeGroups.length}
          <div class="field">
            <span class="label">Adopt in</span>
            <span class="segmented sgs" role="group" aria-label="Space group">
              {#each activeGroups as g (g)}
                <button class:on={activeGroup === g} aria-pressed={activeGroup === g}
                  onclick={() => { chosenGroup = g; pending = null; }}>{@render sg(g)}</button>
              {/each}
            </span>
          </div>
        {/if}
        {#if screen.diagnostics?.length}
          <details class="notes">
            <summary>Notes from the screen ({screen.diagnostics.length})</summary>
            {@render noteList(screen.diagnostics)}
          </details>
        {/if}
      {/if}
    </div>
    <div class="foot">
      {#if pending}
        <span class="why">Adopt #{pending.index + 1}{#if pending.group}{" "}in {@render sg(pending.group)}{/if}
          {" "}as a Pawley start</span>
        <button class="ghost" onclick={() => (pending = null)}>Revert</button>
        <button disabled={busy} onclick={apply}>Apply</button>
      {:else}
        <button disabled={busy} onclick={() => (pending = { index: i, group: activeGroup })}
          >Adopt as a Pawley start</button>
        <!-- the grade and its caveats beside Adopt, and the gate's own
             sentence a click away (ruling B, WP-2124) -->
        <span class="why">{#if verdicts[i]?.picked}rietx's pick, grade {c.confidence}{:else}<Help
          text={verdicts[i]?.why || "The grade and its caveats are recorded with the adoption."}
          >Grade {c.confidence}{c.confidence_caveats.length ? `: ${c.confidence_caveats.map(caveat).join(", ")}` : ""}</Help>{/if}</span>
      {/if}
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

  .steppane.gone {
    display: none;
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

  h3 {
    margin: 14px 0 6px;
  }

  h3 .muted {
    font-weight: 400;
    margin-left: 4px;
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
    width: 10ch;
  }

  .field input.text {
    width: 16ch;
  }

  .tgs {
    display: inline-flex;
    flex-wrap: wrap;
    gap: 4px;
  }

  /* a toggle among several that may all be on: the accent's text role while
     on, a faint dashed box while off, as the fit windows' line toggles */
  .tg {
    border: 1px solid var(--accent-ink);
    color: var(--accent-ink);
  }

  .tg[aria-pressed="false"] {
    border: 1px dashed var(--line-strong);
    color: var(--muted);
  }

  .check {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    cursor: pointer;
  }

  .prior {
    display: inline-flex;
    align-items: center;
    gap: 2px;
  }

  details.notes {
    margin: 12px 0;
    color: var(--muted);
  }

  details.notes summary {
    cursor: pointer;
    color: var(--fg);
  }

  details.more[open] {
    padding-bottom: 6px;
  }

  .dg {
    margin: 6px 0 0 14px;
  }

  .dg b {
    font-weight: 500;
    color: var(--fg);
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

  .cands tbody tr {
    cursor: pointer;
  }

  @media (hover: hover) {
    .cands tbody tr:hover td {
      background: var(--hover);
    }
  }

  .lines tr.sel td {
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }

  /* a value the crystal system sets: muted, and a fixed angle written whole,
     so the column still aligns on the point */
  .cands td.fixed {
    color: var(--muted);
  }

  /* room for a fixed angle's places, empty so a copy reads `90` */
  .cands .pad {
    display: inline-block;
  }

  .cands td.rel {
    color: var(--muted);
  }

  .note {
    color: var(--muted);
  }

  .live {
    color: var(--accent-ink);
  }

  /* what the search did not cover: edged in the danger colour (call 6) */
  .coverage {
    margin: 10px 0;
    padding: 6px 10px;
    border-left: 2px solid var(--bad);
    background: var(--hover);
  }

  .num {
    font-family: var(--mono-family);
  }

  .u,
  .muted {
    color: var(--muted);
  }

  .why {
    flex: 1 1 12em;
    min-width: 0;
    color: var(--muted);
  }

  .bad {
    color: var(--bad);
  }

  .warn {
    color: var(--warn);
  }

  .empty {
    margin: 10px 0;
  }

  .nav {
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 34px;
  }

  .grow {
    flex: 1 1 auto;
  }

  .cellline {
    margin: 6px 0 0;
  }

  /* one line high even when empty */
  .relline {
    margin: 2px 0 0;
    min-height: 1.4em;
    color: var(--muted);
    font-size: var(--text-sm);
  }

  .caveats {
    margin: 0;
  }

  .kv {
    display: grid;
    grid-template-columns: max-content auto;
    gap: 4px 16px;
    margin: 0;
  }

  .kv dt {
    color: var(--muted);
  }

  .kv dd {
    margin: 0;
  }

  .partner {
    margin: 8px 0 0;
  }

  .classes tbody tr {
    cursor: pointer;
  }

  .classes tr.off td {
    color: var(--muted);
  }

  /* "rietx's pick": the gate's class, in the accent's text role */
  .mark {
    margin-left: 8px;
    color: var(--accent-ink);
    font-size: var(--text-sm);
  }

  .sg {
    font-family: "STIX Two Text", "Cambria Math", "Times New Roman", Times, serif;
  }

  .sg i {
    margin-right: 0.08em;
  }

  .sg .bar {
    text-decoration: overline;
  }

  .sgs {
    margin: 0;
  }
</style>
