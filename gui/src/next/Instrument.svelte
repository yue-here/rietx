<script lang="ts">
  /**
   * The Instrument dialog at `/next` (WP-2218, inventory rows 133-136): the
   * open project's source and geometry, and the axial pair with its warning.
   * Opened from the Instrument band's ⋯ menu in the Parameters tab (the
   * maintainer's ruling of 2026-11-11, WP-2214 question 1).
   *
   * It is drawn as the New project form draws its instrument: a geometry
   * choice, an anode, the numbers in bordered boxes with their units after
   * them, an Advanced disclosure, and "Load an instrument profile…". What it
   * edits is the project's own instrument, so its fields are today's
   * instrument form's (`next/instrument.ts` says why a preset is not sent).
   *
   * A modal form with its own Apply, as New project and Settings are. Apply
   * sends the model fields as one whole-model edit and then the values the
   * parameter table owns as one `set_values` (gui/CLAUDE.md, WP-1014), so it
   * makes one history node for each that has anything to send. A refusal stays
   * in the dialog in the verb's own words, with the typed text kept. Loading a
   * profile replaces the instrument at once, one node, and the dialog then
   * shows what it loaded. Saving a profile is File › Export (row 133).
   */
  import { ApiError, api } from "../api";
  import Help from "../Help.svelte";
  import { GEOMETRIES, applyFields, axialWarning, editableValue, fieldParam, fieldText,
           splitEdits, type InstrumentField } from "../lib/model";
  import type { ParamRow } from "../lib/table";
  import { PRESET_TITLES, anodeLabel } from "../lib/wizard";
  import { anodeChoices, anodeOf, clearForGeometry, dialogFields, dialogRows, draftOf,
           geometryRefusal, withAnode, type Anode } from "./instrument";

  let {
    rows,
    anodes = [],
    busy = false,
    say = (_line: string) => {},
    onlanded = () => {},
    onclose,
  }: {
    /** `GET /api/params`, the panel's: which fields the table owns, and the
     *  values they show */
    rows: readonly ParamRow[];
    /** `GET /api/capabilities`'s anodes */
    anodes?: readonly Anode[];
    busy?: boolean;
    say?: (line: string) => void;
    /** an edit landed: the head moved */
    onlanded?: () => void;
    onclose: () => void;
  } = $props();

  let model = $state<any>(null);
  let loadError = $state("");
  /** the typed text, by model path */
  let edits = $state(new Map<string, string>());
  /** a verb's refusal, in its own words: its own field, apart from the load's
   *  (gui/CLAUDE.md, WP-1014) */
  let refusal = $state("");
  let loaded = $state("");
  let sending = $state(false);
  let dlg: HTMLElement | undefined = $state();
  let focused = false;

  const owned = $derived(dialogRows(rows));
  const byPath = $derived(new Map(owned.map((r) => [r.path, r])));
  const draft = $derived(draftOf(model, edits));
  const fields = $derived(draft ? dialogFields(draft) : []);
  const fieldAt = $derived(new Map(fields.map((f) => [f.path, f])));
  const delta = $derived(model ? splitEdits(model, fields, edits, owned, "instrument") : null);
  const warning = $derived(draft ? axialWarning(draft) : "");
  const lines = $derived<any[]>(draft?.source?.lines ?? []);
  const xray = $derived(draft?.source?.kind === "xray_cw" && lines.length > 0);
  const choices = $derived(anodeChoices(anodes, lines.length));
  const anode = $derived(anodeOf(anodes, lines.map((l: any) => Number(l?.wavelength?.value))));

  const source = $derived(fields.filter((f) => f.group === "source"));
  const geometry = $derived(fields.filter((f) => f.group === "geometry" && !f.advanced
    && f.path !== "geometry.kind"));
  const advanced = $derived(fields.filter((f) => f.group === "geometry" && f.advanced));
  const axial = $derived(fields.filter((f) => f.group === "profile"));

  /** why Apply cannot go, or "" */
  const why = $derived(busy ? "A run is in flight"
    : delta?.invalid.length ? `${label(delta.invalid[0].path)}: ${delta.invalid[0].why}`
    : delta?.touched ? geometryRefusal(draft) : "");

  async function load() {
    try {
      model = (await api.instrument()).instrument;
      loadError = "";
    } catch (exc) {
      model = null;
      loadError = (exc as Error).message;
    }
  }

  void load();

  // focus the first control once, when the fields first draw: a reload after
  // Apply or a loaded profile leaves focus where the person put it
  $effect(() => {
    if (!model || !dlg || focused) return;
    focused = true;
    dlg.querySelector<HTMLElement>("select, input:not([disabled]), button")
      ?.focus({ preventScroll: true });
  });

  /** A field's label in sentence case. The form's labels are lower case
   *  where the table names them; a symbol (µR, λ1) keeps its case, since an
   *  upper-case µ reads as a Latin M. */
  function named(label: string): string {
    return /^[a-z]{2}/.test(label) ? label.charAt(0).toUpperCase() + label.slice(1) : label;
  }

  function label(path: string): string {
    const f = fieldAt.get(path);
    return f ? named(f.label) : path;
  }

  function shown(path: string): string {
    const f = fieldAt.get(path);
    return f && model ? fieldText(model, f, byPath, "instrument") : "";
  }

  function text(field: InstrumentField): string {
    return edits.get(field.path) ?? shown(field.path);
  }

  function edited(field: InstrumentField): boolean {
    const t = edits.get(field.path);
    return t !== undefined && t.trim() !== shown(field.path);
  }

  function type(path: string, value: string) {
    const next = new Map(edits);
    if (value.trim() === shown(path)) next.delete(path);
    else next.set(path, value);
    edits = next;
    refusal = "";
    loaded = "";
  }

  function chooseAnode(name: string) {
    const hit = choices.find((a) => a.name === name);
    if (!hit) return;
    edits = withAnode(edits, hit, shown);
    refusal = "";
    loaded = "";
  }

  function held(field: InstrumentField): ParamRow | undefined {
    const row = byPath.get(fieldParam("instrument", field));
    return row && !editableValue(row) ? row : undefined;
  }

  function busyWords(exc: unknown): string {
    return exc instanceof ApiError && exc.busy ? "A run is in flight." : (exc as Error).message;
  }

  async function apply() {
    const d = delta;
    if (!d || !d.touched || d.invalid.length || busy || sending) return;
    sending = true;
    let moved = false;
    try {
      // the model first, read fresh: it carries every value the table holds,
      // so values set before it would be written back by it
      if (d.fields.length) {
        const fresh = (await api.instrument()).instrument;
        await api.patchInstrument(clearForGeometry(applyFields(fresh, d.fields, edits)),
                                  "instrument edited");
        say("ref.edit(instrument=…)");
        moved = true;
        // what landed is no longer an edit: kept, it would compare unequal to
        // the reloaded rendering and send the same model again
        const rest = new Map(edits);
        for (const f of d.fields) rest.delete(f.path);
        rest.delete("geometry.kind");
        edits = rest;
      }
      const values = Object.entries(d.values);
      if (values.length) {
        await api.patchParams({ values: d.values });
        say(`ref.set_values({${values.map(([k, v]) => `"${k}": ${v}`).join(", ")}})`);
        moved = true;
      }
      onlanded();
      onclose();
    } catch (exc) {
      refusal = busyWords(exc);
      if (moved) {
        onlanded();
        await load();
      }
    } finally {
      sending = false;
    }
  }

  async function loadProfile(event: Event) {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) return;
    sending = true;
    try {
      const preview = await api.uploadFile("instrument", file);
      await api.patchInstrument({ upload: preview.upload }, `instrument from ${file.name}`);
      say(`ref.edit(instrument=load_instrument_profile("${file.name}"))`);
      edits = new Map();
      refusal = "";
      loaded = `Loaded ${file.name}`;
      onlanded();
      await load();
    } catch (exc) {
      refusal = busyWords(exc);
    } finally {
      sending = false;
      input.value = "";
    }
  }

  function keydown(event: KeyboardEvent) {
    if (event.key !== "Escape") return;
    event.stopPropagation();
    event.preventDefault();
    // a verb in flight keeps the dialog open, so its refusal has somewhere to land
    if (!sending) onclose();
  }

  function submit(event: SubmitEvent) {
    event.preventDefault();
    void apply();
  }
</script>

<svelte:window onkeydowncapture={keydown} />

{#snippet field(f: InstrumentField)}
  {@const row = held(f)}
  <label class="fld">
    <span>
      {#if row}<Help text={row.held_because ?? ""}>{named(f.label)}</Help>
      {:else if f.help}<Help for={f.help}>{named(f.label)}</Help>
      {:else}{named(f.label)}{/if}
    </span>
    <input class="num" class:edited={edited(f)} data-field={f.path} value={text(f)}
      disabled={!!row} autocomplete="off" spellcheck="false" inputmode="decimal"
      placeholder={f.kind === "optnumber" ? "unset" : ""}
      oninput={(e) => type(f.path, (e.currentTarget as HTMLInputElement).value)} />
    <span class="u">{f.unit ?? ""}</span>
  </label>
{/snippet}

<div class="scrim" role="presentation"
  onpointerdown={(e) => e.target === e.currentTarget && !delta?.touched && !sending && onclose()}>
  <div class="dlg" role="dialog" aria-modal="true" aria-labelledby="instrument-title"
    bind:this={dlg}>
  <form onsubmit={submit}>
    <h2 id="instrument-title">Instrument</h2>
    {#if loadError}
      <p class="bad">{loadError}</p>
    {:else if !model}
      <p class="muted">Loading…</p>
    {:else}
      {#if (xray && choices.length) || source.length}
      <div class="nrow">
        <span class="nl">Source</span>
        <div class="nbody">
          {#if xray && choices.length}
            <label class="fld">
              <span>Anode</span>
              <select value={anode}
                onchange={(e) => chooseAnode((e.currentTarget as HTMLSelectElement).value)}>
                {#if !anode}<option value="" disabled>Other</option>{/if}
                {#each choices as a (a.name)}
                  <option value={a.name}>
                    {anodeLabel(a.name)} · {a.wavelengths.map((w) => w.toFixed(5)).join(", ")} Å
                  </option>
                {/each}
              </select>
            </label>
          {/if}
          {#each source as f (f.path)}{@render field(f)}{/each}
        </div>
      </div>
      {/if}
      <div class="nrow">
        <span class="nl">Geometry</span>
        <div class="nbody">
          <!-- the row names it, so the choice takes the label's column too -->
          <label class="fld wide">
            <select aria-label="Geometry" class:edited={edits.has("geometry.kind")} value={draft.geometry.kind}
              onchange={(e) => type("geometry.kind", (e.currentTarget as HTMLSelectElement).value)}>
              {#each GEOMETRIES as kind (kind)}
                <option value={kind}>{PRESET_TITLES[kind] ?? kind}</option>
              {/each}
            </select>
          </label>
          {#each geometry as f (f.path)}{@render field(f)}{/each}
          {#if advanced.length}
            <details class="more">
              <summary class="muted">Advanced</summary>
              <div class="nbody">
                {#each advanced as f (f.path)}{@render field(f)}{/each}
              </div>
            </details>
          {/if}
        </div>
      </div>
      {#if axial.length}
        <div class="nrow">
          <span class="nl">Axial divergence</span>
          <div class="nbody">
            {#each axial as f (f.path)}{@render field(f)}{/each}
            {#if warning}<p class="warn" role="note">{warning}</p>{/if}
          </div>
        </div>
      {/if}
      <!-- under the fields, as New project's form puts it: it replaces them all -->
      <div class="nrow last">
        <span class="nl"></span>
        <div class="nbody">
          <label class="file" class:off={busy || sending || !!delta?.touched}>
            <input type="file" accept=".json" disabled={busy || sending || !!delta?.touched}
              onchange={loadProfile} />
            <span>Load an instrument profile…</span>
          </label>
        </div>
      </div>
    {/if}
    <div class="foot">
      <span class="reason" class:bad={!!refusal} role="status">{refusal || why || loaded}</span>
      <button type="button" class="ghost" disabled={sending} onclick={onclose}>Cancel</button>
      <button type="submit" disabled={!delta?.touched || !!why || sending}>Apply</button>
    </div>
  </form>
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 30;
    display: flex;
    align-items: flex-start;
    justify-content: center;
    padding: 6vh 16px 16px;
    background: color-mix(in srgb, var(--fg) 22%, transparent);
    overflow: auto;
  }

  .dlg {
    width: min(660px, 100%);
    padding: 16px 20px 12px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 10px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  /* sentence case, as every heading at /next (`gui/STYLE.md` § Type) */
  h2 {
    margin: 0 0 4px;
    font-size: var(--text);
    font-weight: 600;
    color: var(--fg);
    text-transform: none;
    letter-spacing: normal;
  }

  /* a row: its name, then its fields, as New project's rows */
  .nrow {
    display: grid;
    grid-template-columns: 7.5em minmax(0, 1fr);
    gap: 12px;
    padding: 12px 0;
    border-top: 1px solid var(--line);
  }

  /* the button under the fields belongs to them, so no rule above it */
  .nrow.last {
    padding-top: 0;
    border-top: 0;
  }

  .nl,
  .fld > span {
    color: var(--muted);
  }

  .nbody {
    display: flex;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }

  /* a dialog field: label, box, unit. The label column fits the longest
     label; every number box has one width, wide enough for any value it
     holds, and a choice runs to the row's end */
  .fld {
    display: grid;
    grid-template-columns: 7em 14ch minmax(0, 1fr);
    align-items: center;
    gap: 8px;
  }

  .fld select {
    grid-column: 2 / 4;
  }

  .fld.wide select {
    grid-column: 1 / 4;
  }

  .nrow.last .file {
    align-self: flex-start;
  }

  .fld input,
  .fld select {
    min-width: 0;
    width: 100%;
    padding: var(--s1) var(--s2);
    color: var(--fg);
    background: var(--panel);
    border: 1px solid var(--line-strong);
    border-radius: var(--r-control);
  }

  .fld input.num {
    font-family: var(--mono-family);
  }

  .fld input:disabled {
    color: var(--muted);
    background: transparent;
  }

  /* a typed value, as the Parameters tab tints one */
  .fld .edited {
    background: color-mix(in srgb, var(--accent) 12%, var(--panel));
    color: var(--accent-ink, var(--accent));
  }

  .u {
    color: var(--muted);
  }

  .more > summary {
    cursor: pointer;
  }

  .more > .nbody {
    margin-top: 6px;
  }

  .warn {
    margin: 0;
    color: var(--warn);
  }

  .bad {
    color: var(--bad);
  }

  .foot {
    display: flex;
    align-items: center;
    gap: 8px;
    padding-top: 12px;
    border-top: 1px solid var(--line);
  }

  .reason {
    flex: 1 1 auto;
    min-width: 0;
    color: var(--muted);
  }

  .reason.bad {
    color: var(--bad);
  }

  /* a profile cannot load over typed values, nor during a run */
  .file.off > span {
    color: var(--muted);
    cursor: default;
  }

  .file.off > span:hover {
    background: none;
  }
</style>
