<script lang="ts">
  /**
   * The New project dialog (WP-2131): one dialog of four rows, then Create.
   *
   * The maintainer's round-9 design of 2026-11-08, with Claude's ten settled
   * calls recorded in the WP. One dialog rather than a wizard, because each
   * row's answer is independent of the others and Profex's single dialog
   * already does this for powder data. The rows are Pattern, Phases,
   * Instrument and Project. Mode and plan are not asked: the mode follows
   * from the phases (`lib/wizard.ts:modeFor`), and the plan is the project's
   * default until someone opens the Plan tab.
   *
   * The instrument is **assumed and tagged** rather than asked. A pattern
   * file's header seeds it when it names an anode, and otherwise the dialog
   * assumes Bragg-Brentano with a Cu Kα1/Kα2 anode, the first of GSAS-II's
   * default instrument files (docs/practice.md § The start screen).
   * Either way the row says where the answer came from, because a wrong anode
   * shifts every refined cell and an unmarked default reads as something the
   * file said.
   *
   * Everything here goes through the two-phase upload routes (WP-1014): a file
   * is staged and read before anything is created, and only its token travels
   * in the create body.
   */
  import Help from "../Help.svelte";
  import SpaceGroup from "../SpaceGroup.svelte";
  import { api } from "../api";
  import Browse from "./Browse.svelte";
  import {
    PRESET_FIELDS,
    PRESET_TITLES,
    absorbPattern,
    addTypedCell,
    basicField,
    blocked,
    cellBlocked,
    createBody,
    emptyWizard,
    freeCellFields,
    instrumentSummary,
    modeFor,
    patternSummary,
    presetHelp,
    projectPath,
    scanCount,
    seedPreset,
    sourceTag,
    sparkline,
    type NewPhase,
  } from "../lib/wizard";

  let {
    capabilities = null,
    busy = false,
    say = (_line: string) => {},
    onclose = () => {},
    onopened = async (_doc: any) => {},
  }: {
    capabilities?: any;
    busy?: boolean;
    say?: (line: string) => void;
    onclose?: () => void;
    onopened?: (doc: any) => Promise<void> | void;
  } = $props();

  let wiz = $state(emptyWizard());
  /** which upload is being read: "pattern", "cif", "instrument", or "" */
  let staging = $state("");
  let error = $state("");
  let creating = $state(false);
  /** the pattern's scans, labelled, fetched as soon as a multi-scan file stages */
  let scanChoices = $state<any[]>([]);
  let addOpen = $state(false);
  let instrumentOpen = $state(false);
  let picking = $state(false);
  let cifInput = $state<HTMLInputElement | null>(null);
  let dialog = $state<HTMLElement | null>(null);

  const anodes = $derived<any[]>(capabilities?.anodes ?? []);
  const readerOptions = $derived<any[]>(capabilities?.reader_options ?? []);
  const reason = $derived(blocked(wiz));
  const cellReason = $derived(cellBlocked(wiz.cellDraft));
  const CELL_GLYPH: Record<string, string> = { alpha: "α", beta: "β", gamma: "γ" };

  $effect(() => {
    // the dialog takes focus, so Escape and a screen reader both land in it
    dialog?.querySelector<HTMLElement>("input, button")?.focus();
  });

  async function upload(kind: "pattern" | "cif" | "instrument", event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    staging = kind;
    error = "";
    try {
      const preview = await api.uploadFile(kind, file);
      if (kind === "pattern") takePattern(preview, true);
      else if (kind === "cif") {
        wiz.phases = [...wiz.phases, { kind: "cif", preview, aniso: false }];
        say(`structure_from_cif("${preview.filename}")`);
      } else {
        wiz.instrument = preview;
        instrumentOpen = false;
        say(`load_instrument_profile("${preview.filename}")`);
      }
    } catch (err) {
      error = (err as Error).message;   // the reader's own complaint
    } finally {
      staging = "";
      input.value = "";   // choosing the same file again re-reads it
    }
  }

  function takePattern(preview: any, fresh: boolean) {
    wiz = absorbPattern(wiz, preview, fresh);
    if (fresh) {
      scanChoices = [];
      if (scanCount(preview) > 1) loadScans();
      say(`read_pattern("${preview.filename}")  # ${preview.format.name}, `
        + `${preview.n_points} points`);
    }
  }

  async function loadScans() {
    if (scanChoices.length || !wiz.pattern) return;
    try {
      scanChoices = (await api.patternScans(wiz.pattern.upload)).scans ?? [];
    } catch {
      scanChoices = [];   // the numbered fallback is still a picker
    }
  }

  /** Re-read the staged pattern with other reader options: no second upload. */
  async function rereadPattern(name: string, value: string) {
    wiz.readerOptions = { ...wiz.readerOptions, [name]: value };
    const options = Object.fromEntries(
      Object.entries(wiz.readerOptions).filter(([, v]) => v !== ""));
    try {
      takePattern(await api.restage("pattern", wiz.pattern.upload, options), false);
      error = "";
    } catch (err) {
      error = (err as Error).message;
    }
  }

  /** Re-read one staged CIF with or without its U^ij loop. */
  async function setAniso(index: number, aniso: boolean) {
    const phase = wiz.phases[index];
    if (phase.kind !== "cif") return;
    try {
      const preview = await api.restage("cif", phase.preview.upload, aniso ? { aniso: "1" } : {});
      wiz.phases = wiz.phases.map((p, i) => (i === index ? { kind: "cif", preview, aniso } : p));
      error = "";
    } catch (err) {
      error = (err as Error).message;
    }
  }

  function removePhase(index: number) {
    wiz.phases = wiz.phases.filter((_, i) => i !== index);
  }

  function chooseCif() {
    addOpen = false;
    cifInput?.click();
  }

  function startCell() {
    addOpen = false;
    wiz.cellDraft = { symbol: "", facts: null, error: "", cell: {} };
  }

  /** Resolve the typed symbol on change, never per keystroke. */
  async function lookupSymbol() {
    const draft = wiz.cellDraft;
    if (!draft) return;
    const symbol = draft.symbol.trim();
    if (!symbol) { draft.facts = null; draft.error = ""; return; }
    try {
      const facts = await api.spacegroup(symbol);
      // an answer for a symbol since retyped is dropped, never drawn
      if (draft.symbol.trim() !== symbol) return;
      draft.facts = facts;
      draft.error = "";
      say(`get_spacegroup("${symbol}")  # ${facts.constraints}`);
    } catch (err) {
      if (draft.symbol.trim() !== symbol) return;
      draft.facts = null;
      draft.error = (err as Error).message;
    }
  }

  function setPreset(preset: string) {
    wiz = { ...seedPreset(wiz, preset), source: "user" };
  }

  function setValue(name: string, value: string) {
    wiz.values = { ...wiz.values, [name]: value };
    wiz.source = "user";
  }

  function pickWhere(dir: string) {
    wiz.where = dir;
    wiz.whereSet = true;
    picking = false;
  }

  async function create() {
    error = "";
    creating = true;
    try {
      const doc = await api.newProject(createBody(wiz));
      say(`Project.create("${projectPath(wiz)}", mode="${modeFor(wiz)}", …)`);
      await onopened(doc);
    } catch (err) {
      error = (err as Error).message;
    } finally {
      creating = false;
    }
  }

  function phaseCell(phase: NewPhase): string {
    if (phase.kind === "cell") {
      return freeCellFields({ symbol: phase.symbol, facts: phase.facts, error: "", cell: {} })
        .map((n) => `${CELL_GLYPH[n] ?? n} ${phase.cell[n]}`).join("  ");
    }
    const cell = phase.preview.phases?.[0]?.cell ?? [];
    return cell.slice(0, 3).map((v: number) => v.toFixed(4)).join("  ") + " Å";
  }

  function keydown(event: KeyboardEvent) {
    if (event.key !== "Escape" || picking) return;
    if (addOpen) addOpen = false;
    else onclose();
  }

  function away(event: MouseEvent) {
    if (!addOpen) return;
    if (!(event.target as HTMLElement | null)?.closest?.(".addphase")) addOpen = false;
  }
</script>

<svelte:window onkeydown={keydown} onclick={away} />

<div class="backdrop">
  <div class="dialog" role="dialog" aria-modal="true" aria-labelledby="np-title"
    bind:this={dialog}>
    <h2 id="np-title">New project</h2>

    <section class="nrow" aria-label="Pattern">
      <div class="nlabel">Pattern</div>
      <div class="nbody">
        {#if !wiz.pattern}
          <div class="slot">
            <label class="file">
              <input type="file" onchange={(e) => upload("pattern", e)} />
              <span>{staging === "pattern" ? "Reading…" : "Choose a pattern file…"}</span>
            </label>
          </div>
        {:else}
          <div class="line">
            <span class="mono fname">{wiz.pattern.filename}</span>
            <label class="file">
              <input type="file" onchange={(e) => upload("pattern", e)} />
              <span>{staging === "pattern" ? "Reading…" : "Replace…"}</span>
            </label>
          </div>
          <p class="muted summary">{patternSummary(wiz.pattern)}</p>
          <svg class="spark" viewBox="0 0 260 34" preserveAspectRatio="none"
            role="img" aria-label="the pattern, intensity on a square-root axis">
            <path d={sparkline(wiz.pattern.curve)} />
          </svg>
          {#if scanCount(wiz.pattern) > 1}
            <label class="inline">
              <span class="muted">Scan</span>
              <select class="mono" value={wiz.readerOptions.scan ?? "0"}
                onchange={(e) => rereadPattern("scan", (e.currentTarget as HTMLSelectElement).value)}>
                {#each Array.from({ length: scanCount(wiz.pattern) }, (_, i) => i) as i (i)}
                  <option value={String(i)}>{scanChoices[i]?.label ?? `scan ${i}`}</option>
                {/each}
              </select>
              <span class="muted">of {scanCount(wiz.pattern)} in this file</span>
            </label>
          {/if}
          <details>
            <summary class="muted">How the file was read</summary>
            <p class="muted">
              Read by
              <Help text="{wiz.pattern.format.sniff} σ: {wiz.pattern.format.sigma}"
                title="How this file was read">{wiz.pattern.format.name}</Help>
            </p>
            {#each readerOptions.filter((o: any) => o.name !== "scan"
                && wiz.pattern.format.options.includes(o.name)) as opt (opt.name)}
              <label class="inline">
                <Help for="reader_options:{opt.name}">{opt.name}</Help>
                <input class="mono" value={wiz.readerOptions[opt.name] ?? ""}
                  inputmode={opt.kind === "int" ? "numeric" : undefined}
                  onchange={(e) => rereadPattern(opt.name,
                    (e.currentTarget as HTMLInputElement).value.trim())} />
              </label>
            {/each}
            {#each wiz.pattern.diagnostics ?? [] as note (note.code + note.message)}
              <p class={note.level === "error" ? "bad" : note.level === "warning" ? "warn" : "muted"}>
                <span class="mono">{note.code}</span> {note.message}
              </p>
            {/each}
          </details>
        {/if}
      </div>
    </section>

    <section class="nrow" aria-label="Phases">
      <div class="nlabel">Phases</div>
      <div class="nbody">
        {#each wiz.phases as phase, i (i)}
          {@const first = phase.kind === "cif" ? phase.preview.phases?.[0] : null}
          <div class="phl">
            <span class="pname">{phase.kind === "cif" ? first?.name ?? "phase" : "typed cell"}</span>
            <SpaceGroup symbol={phase.kind === "cif" ? first?.space_group ?? ""
              : phase.facts?.xhm || phase.symbol} />
            <span class="mono muted">{phaseCell(phase)}</span>
            <span class="muted">{phase.kind === "cif" ? `${first?.n_atoms ?? 0} sites` : "cell only"}</span>
            <span class="muted src">{phase.kind === "cif" ? phase.preview.filename : ""}</span>
            <button class="ghost" aria-label="Remove this phase"
              onclick={() => removePhase(i)}>×</button>
          </div>
          {#if phase.kind === "cif" && (phase.preview.phases?.length ?? 0) > 1}
            <p class="muted">and {phase.preview.phases.length - 1} more phase(s) in this file</p>
          {/if}
          {#if phase.kind === "cif" && phase.preview.aniso_available}
            <label class="inline">
              <input type="checkbox" checked={phase.aniso}
                onchange={(e) => setAniso(i, (e.currentTarget as HTMLInputElement).checked)} />
              <span class="muted">Keep the file's anisotropic ADPs</span>
            </label>
          {/if}
          {#if phase.kind === "cif" && phase.preview.unknown_species?.length}
            <p class="bad">
              No form factor for {phase.preview.unknown_species
                .map((u: any) => `${u.label} (${u.species})`).join(", ")}.
            </p>
          {/if}
        {/each}

        {#if wiz.cellDraft}
          <div class="tc">
            <label class="inline">
              <span class="muted">Space group</span>
              <input class="mono" bind:value={wiz.cellDraft.symbol} onchange={lookupSymbol} />
            </label>
            {#if wiz.cellDraft.facts}
              <p class="muted">{wiz.cellDraft.facts.setting}; {wiz.cellDraft.facts.constraints}</p>
              <div class="cellgrid">
                {#each freeCellFields(wiz.cellDraft) as name (name)}
                  <label class="fld">
                    <span class="muted"><Help for="parameters:phases.*.cell.{name}"
                      >{CELL_GLYPH[name] ?? name}</Help>{name in CELL_GLYPH ? " (°)" : " (Å)"}</span>
                    <input class="mono" bind:value={wiz.cellDraft.cell[name]} />
                  </label>
                {/each}
              </div>
            {/if}
            {#if wiz.cellDraft.error}<p class="bad">{wiz.cellDraft.error}</p>{/if}
            <div class="line">
              <span class="muted">{cellReason}</span>
              <span class="grow"></span>
              <button class="ghost" onclick={() => (wiz.cellDraft = null)}>Cancel</button>
              <button class="ghost" disabled={!!cellReason}
                onclick={() => (wiz = addTypedCell(wiz))}>Add</button>
            </div>
          </div>
        {/if}

        {#if !wiz.phases.length && !wiz.cellDraft}
          <p class="muted">
            None yet. A project can start from the pattern alone; the Peaks tab
            indexes it and adopts a cell.
          </p>
        {/if}

        <input type="file" accept=".cif" class="hiddenfile" bind:this={cifInput}
          onchange={(e) => upload("cif", e)} />
        <div class="addphase">
          <button class="ghost" aria-haspopup="menu" aria-expanded={addOpen}
            disabled={staging === "cif"}
            onclick={() => (addOpen = !addOpen)}
            >{staging === "cif" ? "Reading…" : "Add phase"}</button>
          {#if addOpen}
            <div class="menu" role="menu">
              <button class="pick" role="menuitem" onclick={chooseCif}>From a CIF…</button>
              <button class="pick" role="menuitem" disabled={!!wiz.cellDraft}
                onclick={startCell}>Space group and cell…</button>
            </div>
          {/if}
        </div>
      </div>
    </section>

    <section class="nrow" aria-label="Instrument">
      <div class="nlabel">Instrument</div>
      <div class="nbody">
        <div class="line">
          <span>{instrumentSummary(wiz)}</span>
          {#if sourceTag(wiz)}
            <span class="chip">{sourceTag(wiz)}</span>
          {/if}
          <span class="grow"></span>
          {#if wiz.instrument}
            <button class="ghost" onclick={() => (wiz.instrument = null)}>Use the form</button>
          {:else}
            <button class="ghost" aria-expanded={instrumentOpen}
              onclick={() => (instrumentOpen = !instrumentOpen)}
              >{instrumentOpen ? "Done" : "Change…"}</button>
          {/if}
        </div>
        {#if wiz.source === "header" && !wiz.instrument && wiz.pattern?.instrument_hint?.why}
          <p class="muted">{wiz.pattern.instrument_hint.why}</p>
        {/if}
        {#if instrumentOpen && !wiz.instrument}
          <div class="iform">
            <label class="fld">
              <span class="muted">Geometry</span>
              <select value={wiz.preset}
                onchange={(e) => setPreset((e.currentTarget as HTMLSelectElement).value)}>
                {#each Object.keys(PRESET_FIELDS) as name (name)}
                  <option value={name}>{PRESET_TITLES[name]}</option>
                {/each}
              </select>
            </label>
            {#snippet field(f: any)}
              <label class="fld">
                <span class="muted" class:cap={/^[a-z]{2}/.test(f.label)}><Help for={presetHelp(f)}>{f.label}</Help>{f.unit ? ` (${f.unit})` : ""}</span>
                {#if f.kind === "anode"}
                  <select class="mono" value={wiz.values[f.name] ?? f.initial ?? ""}
                    onchange={(e) => setValue(f.name, (e.currentTarget as HTMLSelectElement).value)}>
                    {#each anodes as anode (anode.name)}
                      <option value={anode.name}>
                        {anode.name} · {anode.wavelengths.map((w: number) => w.toFixed(5)).join(", ")} Å
                      </option>
                    {/each}
                  </select>
                {:else}
                  <input class="mono" value={wiz.values[f.name] ?? ""}
                    placeholder={f.kind === "optnumber" ? "default" : ""}
                    oninput={(e) => setValue(f.name, (e.currentTarget as HTMLInputElement).value)} />
                {/if}
              </label>
            {/snippet}
            {#each PRESET_FIELDS[wiz.preset].filter(basicField) as f (f.name)}
              {@render field(f)}
            {/each}
            <details class="more">
              <summary class="muted">Advanced</summary>
              <div class="iform">
                {#each PRESET_FIELDS[wiz.preset].filter((f) => !basicField(f)) as f (f.name)}
                  {@render field(f)}
                {/each}
              </div>
            </details>
            <label class="file">
              <input type="file" onchange={(e) => upload("instrument", e)} />
              <span>{staging === "instrument" ? "Reading…" : "Load an instrument profile…"}</span>
            </label>
          </div>
        {/if}
      </div>
    </section>

    <section class="nrow" aria-label="Project">
      <div class="nlabel">Project</div>
      <div class="nbody">
        <label class="fld">
          <span class="muted">Name</span>
          <span class="pjn">
            <input class="mono" value={wiz.name}
              oninput={(e) => { wiz.name = (e.currentTarget as HTMLInputElement).value; wiz.nameSet = true; }} />
            <span class="muted mono">.rex</span>
          </span>
        </label>
        <label class="fld">
          <span class="muted">Where</span>
          <span class="pjn">
            <input class="mono" value={wiz.where}
              oninput={(e) => { wiz.where = (e.currentTarget as HTMLInputElement).value; wiz.whereSet = true; }} />
            <button class="ghost" onclick={() => (picking = true)}>Browse…</button>
          </span>
        </label>
      </div>
    </section>

    {#if error}<p class="bad">{error}</p>{/if}
    <footer class="npf">
      <span class="muted reason">{reason}</span>
      <button class="ghost" onclick={onclose}>Cancel</button>
      <button disabled={!!reason || busy || creating} onclick={create}>Create project</button>
    </footer>
  </div>
</div>

{#if picking}
  <Browse mode="pick" onclose={() => (picking = false)} onpick={pickWhere} />
{/if}

<style>
  .backdrop {
    position: fixed;
    inset: 0;
    z-index: 9;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 6vh 16px 16px;
    background: rgba(0, 0, 0, 0.35);
    overflow: auto;
  }

  .dialog {
    width: min(660px, 100%);
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
    padding: 16px 20px 12px;
  }

  /* sentence case, the maintainer's heading ruling of 2026-11-06, over the
     app's uppercase section heading (app.css) */
  h2 {
    margin: 0 0 4px;
    font-size: var(--text);
    font-weight: 600;
    color: var(--fg);
    text-transform: none;
    letter-spacing: normal;
  }

  /* each row: a 6.5em label column, then the row's body (round 9) */
  .nrow {
    display: grid;
    grid-template-columns: 6.5em minmax(0, 1fr);
    gap: 12px;
    padding: 12px 0;
    border-top: 1px solid var(--line);
  }

  .nlabel {
    font-weight: 500;
  }

  .nbody {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }

  .nbody p {
    margin: 0;
  }

  .slot {
    display: flex;
    align-items: center;
    justify-content: center;
    min-height: 52px;
    border: 1px dashed var(--line);
    border-radius: 8px;
  }

  .line {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  .grow {
    flex: 1 1 auto;
  }

  .fname {
    overflow-wrap: anywhere;
  }

  .spark {
    width: 100%;
    height: 34px;
  }

  .spark path {
    fill: none;
    stroke: var(--plot-obs, var(--fg));
    stroke-width: 1;
    vector-effect: non-scaling-stroke;
  }

  .inline {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  details > summary {
    cursor: pointer;
  }

  details > :not(summary) {
    margin-top: 6px;
  }

  .phl {
    display: flex;
    align-items: baseline;
    gap: 10px;
    flex-wrap: wrap;
  }

  .pname {
    font-weight: 500;
  }

  .src {
    flex: 1 1 auto;
    text-align: right;
    overflow-wrap: anywhere;
  }

  .tc {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 8px 10px;
    border: 1px solid var(--line);
    border-radius: 8px;
  }

  .cellgrid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
    gap: 6px 12px;
  }

  .cellgrid .fld {
    grid-template-columns: 3em minmax(0, 1fr);
  }

  .hiddenfile {
    display: none;
  }

  .addphase {
    position: relative;
    align-self: flex-start;
  }

  .menu {
    position: absolute;
    left: 0;
    top: calc(100% + 2px);
    z-index: 2;
    display: flex;
    flex-direction: column;
    min-width: 200px;
    padding: 4px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  .menu .pick {
    padding: 6px 10px;
    border-radius: var(--r-control);
  }

  .menu .pick:hover:not(:disabled) {
    background: color-mix(in srgb, var(--fg) 6%, var(--panel));
  }

  .menu .pick:disabled {
    color: var(--muted);
  }

  /* the instrument form and the project fields: label and control in two
     columns, the label's 6.5em leaving room for "Wavelength (Å)" (the
     round-9 label fix) */
  .iform {
    display: flex;
    flex-direction: column;
    gap: 6px;
  }

  .fld {
    display: grid;
    grid-template-columns: 6.5em minmax(0, 1fr);
    align-items: center;
    gap: 12px;
  }

  /* the preset fields' labels are lower case where the table names them,
     so the form starts each with a capital beside Geometry, Name and Where.
     Only a label that starts with a word: a symbol (µR, a, α) keeps its case,
     since an upper-case µ or α reads as a Latin M or A. */
  .fld > .cap::first-letter {
    text-transform: uppercase;
  }

  .fld select,
  .fld input {
    min-width: 0;
    width: 100%;
  }

  .pjn {
    display: flex;
    align-items: center;
    gap: 8px;
    min-width: 0;
  }

  .pjn input {
    flex: 1 1 auto;
  }

  .npf {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
  }

  .reason {
    flex: 1 1 auto;
  }

  @media (max-width: 520px) {
    .nrow {
      grid-template-columns: minmax(0, 1fr);
      gap: 6px;
    }
  }
</style>
