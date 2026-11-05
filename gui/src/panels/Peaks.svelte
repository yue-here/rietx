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
   * Adopt button's enabled-ness is the **server's** `adopt` arm, never a local
   * reading of `confidence`: the button and the route must be one answer.
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
    type IndexingControls,
  } from "../lib/controls";
  import { labelFor, type HelpCorpus } from "../lib/help";
  import { clone } from "../lib/model";
  import {
    absentText,
    caveatTone,
    cellText,
    collectTo,
    confidenceTone,
    flagTone,
    fomColumns,
    fomOf,
    formatHkl,
    formatIntensity,
    formatPosition,
    intensityScale,
    type Candidate,
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
  } = $props();

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
  const unusable = $derived(peaks?.unusable_flags ?? []);
  const diagnostics = $derived(peaks?.diagnostics ?? []);
  /** the 100 of the relative intensity scale: the strongest *measured* line */
  const imax = $derived(intensityScale(rows));
  /** the loudest level among the picker's notes, which tones the fold's count */
  const noteTone = $derived(
    diagnostics.some((d) => d.level === "error") ? "bad"
      : diagnostics.some((d) => d.level === "warning") ? "warn" : "note");
  const indexing = $derived(busy && run?.run?.kind === "index");
  const screening = $derived(busy && run?.run?.kind === "extinction");
  const candidates = $derived<Candidate[]>(indexAnswer?.result?.candidates ?? []);
  const refuting = $derived<string[]>(indexAnswer?.refuting_caveats ?? []);
  const verdicts = $derived<Array<{ allowed: boolean; why: string }>>(
    indexAnswer?.adopt ?? []);
  const columns = $derived(fomColumns(candidates));
  const best = $derived(verdicts.findIndex((v) => v.allowed));
  const quality = $derived(indexAnswer?.result?.quality ?? null);
  const screen = $derived(extinction?.result ?? null);
  /** may the screened candidate be adopted?  The server's verdict, reused —
   *  it decides whether a space-group chip is a button or a fact */
  const screenAdoptable = $derived(
    extinction !== null && Boolean(verdicts[extinction.candidate]?.allowed));

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
    oncandidate(index);
  }

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

  const pick = () => verb(() => api.pickPeaks());
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
  const toggleUse = (index: number, usable: boolean) =>
    verb(() => api.flagPeak(index, { use_for_indexing: !usable }));
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

<section>
  <div class="controls">
    <button onclick={pick} disabled={busy}
      title="fit every detectable line; replaces the stored list, edits included">
      {rows.length ? "Re-pick peaks" : "Pick peaks"}
    </button>
    <button onclick={startIndex} disabled={busy || !rows.length}
      title="run every indexing engine on the usable lines; agreement is the confidence">
      Index
    </button>
    {#if peaks?.peaks}
      <input class="add" type="text" inputmode="decimal" placeholder="add at 2θ…"
        bind:value={addAt} disabled={busy}
        onkeydown={(ev) => ev.key === "Enter" && addTyped()}
        title="seed a component at this 2θ and refit the group it lands in
(the plot's click does the same)" />
    {/if}
    {#if indexing}
      <span class="muted">
        {run?.run?.stage ?? "starting"}
        {#if run?.run?.stage_index}({run.run.stage_index}/{run.run.n_stages}){/if}
      </span>
    {/if}
  </div>
  {#if failure}<p class="bad">{failure}</p>{/if}

  {#if draft}
    <details class="search">
      <summary>
        Search controls
        {#if digest}<span class="muted">· {digest}</span>{/if}
      </summary>

      <div class="grid" class:frozen={busy}>
        <div class="block">
          <span class="lab"><Help for={searchHelp(field("engines"))}
            >{field("engines").label}</Help></span>
          {#each enginesVocab as e (e.name)}
            <label class="opt" title={e.description}>
              <input type="checkbox" disabled={busy}
                checked={draft.engines === null || draft.engines.includes(e.name)}
                onchange={() => toggleEngine(e.name)} />
              {e.name}
            </label>
          {/each}
        </div>

        <div class="block">
          <span class="lab"><Help for={searchHelp(field("systems"))}
            >{field("systems").label}</Help></span>
          {#each systemsVocab as s (s)}
            {@const on = draft.search.systems === null
              || draft.search.systems.includes(s)}
            <span class="sys">
              <label class="opt">
                <input type="checkbox" disabled={busy} checked={on}
                  onchange={() => toggleSystem(s)} />
                {s}
              </label>
              {#if on && (centringsVocab[s]?.length ?? 0) > 1}
                {#each centringsVocab[s] as letter (letter)}
                  {@const cOn = !draft.search.centrings?.[s]
                    || draft.search.centrings[s].includes(letter)}
                  <button class="ghost" class:on={cOn} disabled={busy}
                    title="try this centring in this system"
                    onclick={() => toggleCentring(s, letter)}>{letter}</button>
                {/each}
              {/if}
            </span>
          {/each}
        </div>

        <div class="row">
          <label class="num">
            <Help for={searchHelp(field("preset"))}>{field("preset").label}</Help>
            <select disabled={busy}
              value={draft.search.preset ?? ""}
              onchange={(ev) => setSearch("preset",
                (ev.currentTarget as HTMLSelectElement).value || null)}>
              <option value="">default — {defaultPreset}</option>
              {#each presetsVocab as p (p.name)}
                <option value={p.name} title={p.when_to_use}>{p.title}</option>
              {/each}
            </select>
          </label>
          <label class="num">
            <Help for={searchHelp(field("total_budget_seconds"))}
              >{field("total_budget_seconds").label}</Help>
            <input type="text" inputmode="decimal" disabled={busy}
              value={draft.search.total_budget_seconds ?? ""}
              onchange={(ev) => setSearch("total_budget_seconds",
                numOrNull((ev.currentTarget as HTMLInputElement).value))} />
          </label>
          <label class="num">
            <Help for={searchHelp(field("budget_seconds"))}
              >{field("budget_seconds").label}</Help>
            <input type="text" inputmode="decimal" disabled={busy}
              value={draft.search.budget_seconds}
              onchange={(ev) => setSearch("budget_seconds",
                numOrNull((ev.currentTarget as HTMLInputElement).value)
                  ?? draft!.search.budget_seconds)} />
          </label>
          <label class="num">
            <Help for={searchHelp(field("validate_candidates"))}
              >{field("validate_candidates").label}</Help>
            <input type="checkbox" disabled={busy}
              checked={draft.validate_candidates}
              onchange={(ev) => {
                draft!.validate_candidates =
                  (ev.currentTarget as HTMLInputElement).checked;
                commit();
              }} />
          </label>
          <label class="num">
            <Help for={searchHelp(field("check_top"))}>{field("check_top").label}</Help>
            <input type="text" inputmode="numeric" disabled={busy}
              value={draft.check_top ?? ""}
              onchange={(ev) => {
                draft!.check_top =
                  numOrNull((ev.currentTarget as HTMLInputElement).value);
                commit();
              }} />
          </label>
        </div>

        <div class="row">
          {#each [["min_d_axis", draft.search.min_d_axis],
                  ["max_d_axis", draft.search.max_d_axis],
                  ["min_volume", draft.search.min_volume]] as [name, value] (name)}
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
            <Help for={searchHelp(field("max_volume"))}
              >{field("max_volume").label}</Help>
            <input type="text" inputmode="decimal" disabled={busy}
              value={draft.search.max_volume ?? ""}
              onchange={(ev) => setSearch("max_volume",
                numOrNull((ev.currentTarget as HTMLInputElement).value))} />
          </label>
        </div>

        <div class="row">
          {#each [["n_unindexed", draft.search.n_unindexed],
                  ["n_search_lines", draft.search.n_search_lines],
                  ["k_sigma", draft.search.k_sigma],
                  ["shift_allowance_deg", draft.search.shift_allowance_deg],
                  ["max_candidates", draft.search.max_candidates],
                  ["seed", draft.search.seed]] as [name, value] (name)}
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
              value={draft.search.shift_template ?? ""}
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
          {#each draft.search.prior_cells ?? [] as cell, i (i)}
            <span class="tagged">
              <span class="chip note">{priorCellText(cell)}</span>
              <button class="ghost" disabled={busy}
                title="drop this prior"
                onclick={() => removePriorCell(i)}>×</button>
            </span>
          {/each}
          <input class="add" type="text" disabled={busy}
            placeholder="a b c α β γ…" bind:value={priorText}
            onkeydown={(ev) => ev.key === "Enter" && addPriorCell()} />
          <button disabled={busy || !priorText.trim()}
            onclick={addPriorCell}>add</button>
        </div>

        <div class="block">
          <span class="lab"><Help for={searchHelp(field("prior_spacegroups"))}
  >{field("prior_spacegroups").label}</Help></span>
          {#each draft.search.prior_spacegroups ?? [] as sg, i (sg + i)}
            <span class="tagged">
              <span class="chip note">{sg}</span>
              <button class="ghost" disabled={busy}
                title="drop this prior"
                onclick={() => removePriorSg(i)}>×</button>
            </span>
          {/each}
          <input class="add" type="text" disabled={busy}
            placeholder="e.g. R -3 c" bind:value={sgText}
            onkeydown={(ev) => ev.key === "Enter" && addPriorSg()} />
          <button disabled={busy || !sgText.trim()}
            onclick={addPriorSg}>add</button>
        </div>
      </div>
      {#if controlsError}<p class="bad">{controlsError}</p>{/if}
    </details>
  {/if}

  {#if shortlists.length}
    <div class="stream">
      <h2>{indexing ? "Streaming — completed systems" : "Streamed shortlists"}</h2>
      {#each shortlists as snap (snap.system)}
        <p class="tabular">
          <strong>{snap.system}</strong>
          {#if !snap.candidates.length}
            <span class="muted">— nothing of this symmetry fits</span>
          {:else}
            {#each snap.candidates.slice(0, 3) as c, i (i)}
              <span class="chip note" title="streamed grade — conservative: it
can rise when validation and ambiguity run, never fall">
                {cellText(c.cell)} <em>{c.confidence}</em></span>
            {/each}
          {/if}
        </p>
      {/each}
    </div>
  {/if}

  {#if !peaks?.peaks}
    <p class="muted hint">
      No peak list yet. <strong>Pick peaks</strong> fits every detectable line;
      afterwards, click the plot to add one the fitter missed, drag a marker to
      correct one, shift-click to exclude.
    </p>
  {:else}
    <p class="muted tabular">
      {peaks.n_usable} of {peaks.n_total} lines usable for indexing
      {#if peaks.source === "positions"}
        · <span class="chip warn"
          ><Help for="diagnostics:PEAK_SIGMA_ASSUMED">σ assumed</Help></span>
      {/if}
    </p>

    <!-- The picker's notes about the *list*, folded (WP-1209): a strip of
         three codes and their sentences read as an interruption above the
         table, and the count says whether there is anything to open. The
         count is a chip because it is a fact with a level; the summary is
         what acts. -->
    {#if diagnostics.length}
      <details class="notes">
        <summary>
          <span class="chip {noteTone}">{diagnostics.length}</span>
          {diagnostics.length === 1 ? "note" : "notes"} from the picker
        </summary>
        <ul class="strip">
          {#each diagnostics as d (d.code + d.message)}
            <li class={d.level}>
              <span class="mono">
                <Help for="diagnostics:{d.code}">{d.code}</Help>
              </span> {d.message}
            </li>
          {/each}
        </ul>
      </details>
    {/if}

    <!-- Seven columns (WP-1209): the numbers a peak table is read in, the
         flags, then `use` on its own — the one cell that is a decision — and
         the verbs last. 2θ is four places with the esd in the last place, or
         none from `POSITION_ESD_MAX_DEG` (1°) up, where the flag says why;
         I is the relative scale. -->
    <div class="scroll">
      <table class="tabular">
        <thead>
          <tr>
            <th>#</th><th>2θ (°)</th><th>d (Å)</th><th class="rel">I (rel)</th>
            <th>flags</th><th>use</th><th></th>
          </tr>
        </thead>
        <tbody>
          {#each rows as p (p.index)}
            {@const pos = formatPosition(p.two_theta, p.two_theta_esd)}
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
            <tr class:out={!p.usable} class:lit={hovered === p.index}
              onmouseenter={() => onhover(p.index)}
              onmouseleave={() => onhover(null)}>
              <td class="muted">{p.index}</td>
              <td>
                <button class="ghost pos" title="zoom the plot to this line"
                  onclick={() => zoomTo(p.two_theta, p.fwhm)}>
                  {pos.value}<span class="muted">{pos.esd}</span>
                </button>
              </td>
              <td>{p.d.toFixed(4)}</td>
              <td class="rel">{formatIntensity(p.intensity, imax, p.flags)}</td>
              <td class="flags">
                {#if p.origin !== "fitted"}
                  <span class="chip accent">
                    <Help for="peak_origins:{p.origin}"
                      >{labelFor(corpus, `peak_origins:${p.origin}`)}</Help>
                  </span>
                {/if}
                {#each p.flags as f (f)}
                  <span class="chip {flagTone(f, unusable)}">
                    <Help for="peak_flags:{f}">{labelFor(corpus, `peak_flags:${f}`)}</Help>
                  </span>
                {/each}
              </td>
              <td class="use">
                <input type="checkbox" checked={p.usable} disabled={busy}
                  title={p.usable ? "exclude from indexing" :
                         "use for indexing (overrules the fitter's flags)"}
                  onchange={() => toggleUse(p.index, p.usable)} />
              </td>
              <td class="acts">
                {#if p.n_in_group > 1}
                  <button class="ghost" disabled={busy}
                    title="refit group {p.group} ({p.n_in_group} components) under the picker's own judgement"
                    onclick={() => refit(p.group)}>↻</button>
                {/if}
                <button class="ghost" disabled={busy} title="remove this line"
                  onclick={() => remove(p.index)}>×</button>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
    </div>
  {/if}

  {#if indexAnswer}
    <h2>Indexing</h2>
    {#if !candidates.length}
      <p class="hint muted">
        No candidate cells.
        {#if quality?.abstained_reason}{quality.abstained_reason}{/if}
      </p>
      <ul class="strip">
        {#each indexAnswer.result?.diagnostics ?? [] as d (d.code + d.message)}
          <li class={d.level}><span class="mono">{d.code}</span> {d.message}</li>
        {/each}
      </ul>
    {:else}
      {#if best < 0}
        <p class="hint muted" title="best_or_none() returned None — the expected
          outcome until the evidence singles one cell out">
          No candidate reaches the gate; the list below is ranked, not chosen.
        </p>
      {/if}
      <div class="scroll">
        <table class="tabular candidates">
          <thead>
            <tr>
              <th></th><th>cell</th><th>lattice</th>
              {#each columns as name (name)}<th>{name}</th>{/each}
              <th>Rwp</th><th title="lines predicted where the pattern has no
                intensity, of the lines screened; 'in window' is the count the
                predicted_but_absent caveat caps on — the oversized-cell detector">absent</th>
              <th>engines</th><th></th>
            </tr>
          </thead>
          <tbody>
            <!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
            {#each candidates as c, i (i)}
              <tr class:best={i === best} class:lit={shownCandidate === i}
                onmouseenter={() => oncandidatehover(i)}
                onmouseleave={() => oncandidatehover(null)}>
                <td>
                  <!-- one control, two effects, because they are one thought:
                       "show me this cell" means the caveats *and* where it says
                       the lines are.  A second button would be a second
                       selection state to keep in step with this one. -->
                  <button class="ghost" title="details, caveats and ambiguity —
and this cell's predicted lines through the data"
                    onclick={() => selectCandidate(expanded === i ? null : i)}>
                    {expanded === i ? "▾" : "▸"}
                  </button>
                </td>
                <td class="cell">{cellText(c.cell)}
                  <span class="chip {confidenceTone(c.confidence)}">{c.confidence}</span>
                  {#if i === best}<span class="chip ok">best_or_none()</span>{/if}
                </td>
                <td>{c.centring} {c.system}<br /><span class="muted">{c.volume.toFixed(1)} Å³</span></td>
                {#each columns as name (name)}
                  {@const v = fomOf(c, name)}
                  <td>{v === null ? "—" : v.toFixed(1)}</td>
                {/each}
                <td>{c.lebail ? (c.lebail.rwp * 100).toFixed(1) + "%" : "—"}</td>
                <td>{c.lebail ? absentText(c.lebail) : "—"}</td>
                <td class="flags">
                  {#each c.found_by as e (e)}<span class="chip note">{e}</span>{/each}
                </td>
                <td>
                  <button disabled={busy || !(verdicts[i]?.allowed)}
                    title={verdicts[i]?.allowed
                      ? "adopt this cell as the model (a Le Bail scaffold; one history node)"
                      : verdicts[i]?.why ?? ""}
                    onclick={() => adopt(i)}>Adopt</button>
                </td>
              </tr>
              {#if expanded === i}
                <tr class="detail">
                  <td></td>
                  <td colspan={7 + columns.length}>
                    {#if c.confidence_caveats.length}
                      <p class="flags">
                        {#each c.confidence_caveats as caveat (caveat)}
                          <span class="chip {caveatTone(caveat, refuting)}">{caveat}</span>
                        {/each}
                      </p>
                    {/if}
                    {#each c.ambiguity as partner, k (k)}
                      <p>
                        geometrically indistinguishable: {cellText(partner.cell)}
                        ({partner.system}, index {partner.index})
                        {#if partner.discriminating_two_theta?.length}
                          — separable at 2θ ≈
                          {partner.discriminating_two_theta.slice(0, 4).map((t: number) => t.toFixed(2)).join(", ")}°
                        {/if}
                      </p>
                    {/each}
                    {#if collectTo(c) !== null}
                      <p class="warn">collect to 2θ ≈ {collectTo(c)?.toFixed(1)}°
                        to break the ambiguity — the discriminating lines are beyond
                        the measured range</p>
                    {/if}
                    <p>
                      <button disabled={busy}
                        title="rank the extinction classes this lattice allows: one shared
profile fit, then one Le Bail per class — the answer is a ranked list of
classes, and every class lists all its space groups (WP-1025)"
                        onclick={() => screenExtinctions(i)}>Screen extinctions</button>
                      {#if extinction?.candidate === i && screen}
                        <span class="muted">screened — table below</span>
                      {/if}
                    </p>
                    <ul class="strip">
                      {#each c.diagnostics as d (d.code + d.message)}
                        <li class={d.level}><span class="mono">{d.code}</span> {d.message}</li>
                      {/each}
                    </ul>
                  </td>
                </tr>
              {/if}
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    {#if screening && !screen}
      <p class="muted">screening extinction classes…</p>
    {/if}
    {#if screen}
      <h2>Extinction — candidate {extinction.candidate}</h2>
      <p class="muted tabular">
        reference {screen.lattice_group} (absence-free) ·
        {screen.n_screened} of {screen.n_classes} classes fitted ·
        2θ {screen.two_theta_range[0].toFixed(1)}–{screen.two_theta_range[1].toFixed(1)}°
      </p>
      {#if extinction.best === null}
        <p class="hint muted" title="best_or_none() returned None — refuted
          classes, an indecisive ΔBIC margin, or unfitted classes leave an
          unasked question, which must not read as a clean answer">
          No class is singled out; the list below is ranked, not chosen.
        </p>
      {/if}
      <div class="scroll">
        <table class="tabular">
          <thead>
            <tr>
              <th>class</th>
              <th title="BIC(class) − BIC(absence-free reference); negative favours the class">ΔBIC</th>
              <th title="absences the data could test / absences the class asserts —
an absence outside the range, under a neighbour, or in a window this class's own
fit already fills with a tail is not an observation.  Needs the fit, so an
unscreened class shows —">testable</th>
              <th title="testable forbidden positions carrying intensity; each one refutes the class">refuting</th>
              <th title="every space group in the class — a powder cannot
distinguish them, so a singleton here would be unmeasurable">space groups</th>
            </tr>
          </thead>
          <tbody>
            {#each screen.candidates as cls, k (cls.symbol + k)}
              <tr class:out={cls.refuted} class:best={extinction.best === k}>
                <td class="mono">{cls.symbol}
                  {#if extinction.best === k}<span class="chip ok">best_or_none()</span>{/if}
                  {#if cls.refuted}
                    <span class="chip bad" title={cls.refuted_reason ?? ""}>refuted</span>
                  {:else if !cls.screened}
                    <span class="chip warn" title="left unfitted (cap or cancel) —
an unasked question, so the gate abstains">not screened</span>
                  {/if}
                </td>
                <td>{cls.screened ? cls.delta_bic.toFixed(1) : "—"}</td>
                <td>{cls.screened ? cls.n_testable : "—"}/{cls.n_absent}</td>
                <td>
                  {#if cls.n_present}
                    {cls.n_present}:
                    {(cls.forbidden_hkl ?? []).slice(0, 3)
                      .map((hkl: number[], j: number) =>
                        `${formatHkl(hkl)} ${cls.forbidden_two_theta?.[j]?.toFixed(2) ?? "?"}°`)
                      .join(" ")}
                  {:else}—{/if}
                </td>
                <td class="flags">
                  {#each cls.space_groups as sg (sg)}
                    {#if screenAdoptable && !cls.refuted}
                      <button class="ghost" disabled={busy}
                        title="adopt candidate {extinction.candidate} as a Le Bail scaffold
in {sg} — the class cannot distinguish its members, so this choice is a
convention, not a measurement"
                        onclick={() => adopt(extinction.candidate, sg)}>{sg}</button>
                    {:else}
                      <span class="chip">{sg}</span>
                    {/if}
                  {/each}
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
      <ul class="strip">
        {#each screen.diagnostics ?? [] as d (d.code + d.message)}
          <li class={d.level}><span class="mono">{d.code}</span> {d.message}</li>
        {/each}
      </ul>
    {/if}
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

  .controls {
    display: flex;
    gap: 8px;
    align-items: center;
    flex: 0 0 auto;
  }

  .add {
    width: 90px;
    font: var(--mono);
  }

  /* -- the search-controls disclosure (WP-1045) ---------------------- */
  details.search {
    flex: 0 0 auto;
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 2px 8px 4px;
  }

  details.search summary {
    cursor: pointer;
    font-size: var(--text-sm);
    user-select: none;
  }

  .grid {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 6px 0 2px;
  }

  /* the 409 is the server's; this is only its shadow on the pointer */
  .grid.frozen {
    opacity: 0.6;
  }

  /* rows of controls, so they are control-sized: a field's label rides with
     the field rather than reading as prose about it */
  .block {
    display: flex;
    gap: 6px;
    flex-wrap: wrap;
    align-items: center;
    font-size: var(--text-sm);
  }

  .lab {
    color: var(--muted);
    min-width: 108px;
  }

  .opt {
    display: inline-flex;
    gap: 3px;
    align-items: center;
    white-space: nowrap;
  }

  .sys {
    display: inline-flex;
    gap: 2px;
    align-items: center;
  }

  .row {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
    align-items: flex-end;
    font-size: var(--text-sm);
  }

  .num {
    display: inline-flex;
    flex-direction: column;
    gap: 1px;
    color: var(--muted);
  }

  .num input[type="text"] {
    width: 76px;
    font: var(--mono);
  }

  .num input[type="checkbox"] {
    align-self: flex-start;
  }

  .stream {
    flex: 0 0 auto;
  }

  h2 {
    margin: var(--s3) 0 var(--s1);
  }

  /* Each table gets a bounded window of its own rather than a share of the
     section: as flex children with min-height 0, three stacked tables shrank
     each other proportionally, and the 71-row extinction table came up as a
     70 px sliver (measured). No shrink + a 45vh cap keeps a short table at
     its content height, a long one at ~20 rows under its sticky header, and
     the section's own scrollbar handles the rest. */
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

  /* `z-index` is the whole of WP-1032's reported "headings clash with the list
     on scroll", and it is *not* the transparency the report guessed at: this
     backdrop is opaque in both themes (measured #1e1e1e / #ffffff).  What puts a
     row on top of it is `tr.out td { opacity: 0.55 }` two rules down — an
     element with opacity < 1 paints as though it were positioned at z-index 0,
     and `tbody` follows `thead` in tree order, so a *dimmed* row wins the tie
     against a sticky header left at `z-index: auto`.  Which is why only the
     excluded rows ever clashed, and why the fix belongs here rather than on the
     rows: dimming a row is a statement about the row, not about paint order.
     (Measured: `elementFromPoint` inside the header band returned the chip.) */
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
    vertical-align: top;
  }

  tr.out td {
    opacity: 0.55;
  }

  tr.best td {
    background: color-mix(in srgb, var(--ok) 8%, transparent);
  }

  /* the hover link, both ways: this row and the plot's ring name one line */
  tr.lit td {
    background: color-mix(in srgb, var(--accent) 14%, transparent);
  }

  /* The candidate table's own lit row is the overlay's ink, not the chrome
     accent (WP-1210's rule): the row and the lines drawn from it are one
     statement, and a reader has to be able to see that they are. */
  .candidates tr.lit td {
    background: color-mix(in srgb, var(--plot-candidate) 16%, transparent);
  }

  .pos {
    padding: 0;
    font: inherit;
  }

  /* a fact and the verb that acts on it, side by side: a chip is
     non-interactive, so a control inside one would be two registers in one box */
  .tagged {
    display: inline-flex;
    align-items: center;
    gap: var(--s1);
  }

  .flags {
    display: flex;
    gap: 3px;
    flex-wrap: wrap;
    align-items: center;
  }

  .strip {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: var(--text-sm);
    flex: 0 0 auto;
  }

  /* the folded notes: a summary at control size, its count a chip */
  details.notes {
    flex: 0 0 auto;
    font-size: var(--text-sm);
  }

  details.notes summary {
    cursor: pointer;
    color: var(--muted);
    user-select: none;
  }

  /* numbers read down a column: the relative intensity right-aligns so its
     decimals line up, as 2θ's fixed four places already do.  Not `.num`: that
     is the search form's label (`display: inline-flex`), and a `td` wearing it
     stops being a table cell — the browser wraps it and the flex `td.flags`
     beside it into *one* anonymous cell, so the chips sat under the number in
     a column headed by nothing (measured in Chrome, invisible to jsdom). */
  .rel {
    text-align: right;
  }

  .strip li {
    padding: 1px 0;
    color: var(--muted);
  }

  .strip li.warning { color: var(--warn); }
  .strip li.error { color: var(--bad); }

  .acts {
    display: flex;
    gap: 2px;
    align-items: center;
  }

  p { margin: var(--s1) 0; }
  td.cell { white-space: normal; min-width: 150px; }
</style>
