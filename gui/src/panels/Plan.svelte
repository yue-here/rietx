<script lang="ts">
  /**
   * The plan editor: which preset, which stages, in which order, and — since
   * WP-1208 — which parameters each stage will actually free.
   *
   * A project stores the plan **expanded through its mode**, so this list is
   * exactly what a run will execute — picking `mccusker_default` in Le Bail mode
   * shows `profile_only`'s stages, because that is what `fit` would have
   * substituted at run time (WP-1008).  The preset name beside the menu is
   * *derived* by comparing the stages against the registry, so editing a stage
   * turns the label to "custom" by itself rather than by a flag someone has to
   * remember to clear.
   *
   * `Run this stage` sends the same `StageSpec` the list is holding, through the
   * same run machinery a whole fit uses — which is what makes "run one stage,
   * look, run the next" the interactive loop the CLI never had.
   *
   * Four rules for the ladder half.
   *
   * **The numbers come from the server, resolved, never matched here.**  The
   * client owns an fnmatch port (`lib/fnmatch.ts`) for the parameter table's
   * bulk-edit preview, and it is deliberately not used here: what a stage frees
   * is not the glob's matches, it is the glob's matches minus what is tied,
   * locked, mode-fixed or degenerate with a free cell, and those rules live in
   * `ParameterTable.set_vary`.  `GET /api/plan/resolve` runs them.
   *
   * **A dirty plan has no resolved facts**, because the ladder describes the
   * plan the server holds and an edited stage is not that plan.  They are
   * hidden rather than left standing, and the panel says why.
   *
   * **The advanced field list is derived from `lib/rxt.ts`**, whose three stage
   * arrays are pinned to `StageSpec` from python (`tests/test_textdoc.py`).  So
   * a field added to the schema arrives in this form, keyed to its own corpus
   * entry by its own name — the `controls.ts`/`wizard.ts` rule, one vocabulary
   * over.  A label it has no short name for renders as the field name.
   *
   * **An emptied box is `null` only where the schema admits one.**  Everywhere
   * else it is left alone, so the refusal a person meets is a typed value out
   * of range rather than a box they cleared by accident.
   */
  import Help from "../Help.svelte";
  import { ApiError, api } from "../api";
  import { STAGE_INT_WORDS, STAGE_NULLABLE_WORDS, STAGE_WORDS } from "../lib/rxt";

  let {
    mode = "rietveld",
    head = null,
    busy = false,
    noPhasesReason = null,
    simple = true,
    say = (_line: string) => {},
    onrun = (_stage: any) => {},
    onrunall = () => {},
  }: {
    mode?: string;
    head?: string | null;
    busy?: boolean;
    /** Why a run is refused right now, or `null` when it is not. Zero phases
     *  is a legal project state (WP-1207) and the run verb refuses it, so both
     *  run buttons here are disabled carrying the reason rather than offering
     *  a click whose only outcome is a 409 — `gui/CLAUDE.md`'s rule, which the
     *  header's own Run already follows. The **sentence** is the shell's, not
     *  this panel's: it names the route out (index a pattern, adopt a cell),
     *  and a second copy here said "add one in the Model tab", which is a
     *  different instruction for the same state. */
    noPhasesReason?: string | null;
    simple?: boolean;
    say?: (line: string) => void;
    onrun?: (stage: any) => void;
    onrunall?: () => void;
  } = $props();

  interface Stage {
    name: string;
    turn_on: string[];
    [key: string]: unknown;
  }

  /** Every `StageSpec` field but the two the list already draws. */
  const FIELDS = STAGE_WORDS.filter((word) => word !== "free");

  /** Short names for the boxes, at the width a sidebar has. A field with no
   *  entry here renders under its own name rather than going missing. */
  const FIELD_LABEL: Record<string, string> = {
    max_iter: "iter",
    lebail_cycles: "lebail",
    strain_seed: "strain",
    restraint_weight_scale: "restraint",
    window_slack_deg: "slack",
  };

  let stages = $state<Stage[]>([]);
  let guard = $state(0.98);
  let preset = $state<string | null>(null);
  let presets = $state<any[]>([]);
  let resolved = $state<any>(null);
  let error = $state("");
  let dirty = $state(false);
  let dragging = $state<number | null>(null);
  /** which stage the `.` shortcut and the palette entry would run */
  let selected = $state(0);

  /** Presets whose declared modes include the project's, first. */
  const offered = $derived(
    [...presets].sort((a, b) => {
      const fit = (p: any) => (p.modes?.includes(mode) ? 0 : 1);
      return fit(a) - fit(b);
    }),
  );
  const chosen = $derived(presets.find((p) => p.name === preset) ?? null);
  /** The resolved stages, or `null` while the plan on screen is not the
   *  server's — see the dirty-plan rule in the header comment. */
  const ladder = $derived(
    !dirty && resolved?.stages?.length === stages.length ? resolved.stages : null,
  );
  const setAside = $derived((dirty ? [] : resolved?.set_aside ?? []) as string[]);

  /** The plan fields this panel has no control for (`intermediate_ftol`,
   *  `lebail_passes`, whatever comes next), carried through a save: sending
   *  only what the panel edits made the server fill each with its default. */
  let extra = $state<Record<string, unknown>>({});
  function otherFields(plan: Record<string, unknown>) {
    const { stages: _s, correlation_guard: _g, ...rest } = plan;
    return rest;
  }

  async function load() {
    try {
      const [plan, registry, resolve] = await Promise.all([
        api.plan(), api.plans(), api.planResolve(),
      ]);
      stages = plan.plan.stages;
      guard = plan.plan.correlation_guard;
      extra = otherFields(plan.plan);
      preset = plan.preset;
      presets = registry.plans;
      resolved = resolve;
      dirty = false;
      error = "";
    } catch (exc) {
      if (!(exc instanceof ApiError && exc.empty)) error = (exc as Error).message;
    }
  }

  $effect(() => {
    void mode;
    void head;
    load();
  });

  async function put(body: Record<string, unknown>) {
    try {
      const payload = await api.putPlan(body);
      stages = payload.plan.stages;
      guard = payload.plan.correlation_guard;
      extra = otherFields(payload.plan);
      preset = payload.preset;
      dirty = false;
      error = "";
      resolved = await api.planResolve();
    } catch (exc) {
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the plan is read-only until it ends"
        : (exc as Error).message;
    }
  }

  async function pick(name: string) {
    say(`plan = resolve_plan(${JSON.stringify(name)}, ${JSON.stringify(mode)})`);
    await put({ preset: name });
  }

  async function save() {
    say(`project.doc.plan = PlanSpec(stages=[${stages.length}], correlation_guard=${guard})`);
    await put({ plan: { ...extra, stages, correlation_guard: guard } });
  }

  function touch() {
    dirty = true;
  }

  function move(from: number, to: number) {
    if (to < 0 || to >= stages.length || from === to) return;
    const next = [...stages];
    next.splice(to, 0, ...next.splice(from, 1));
    stages = next;
    touch();
  }

  function remove(index: number) {
    stages = stages.filter((_, i) => i !== index);
    touch();
  }

  function globs(index: number, text: string) {
    stages[index].turn_on = text.split(",").map((s) => s.trim()).filter(Boolean);
    touch();
  }

  function field(index: number, key: string, raw: string) {
    if (raw === "") {
      if (!STAGE_NULLABLE_WORDS.includes(key)) return;   // left alone, not nulled
      stages[index][key] = null;
    } else {
      stages[index][key] = STAGE_INT_WORDS.includes(key)
        ? parseInt(raw, 10) : Number(raw);
    }
    touch();
  }

  export function runStage(index = selected) {
    const stage = stages[index];
    if (stage) {
      selected = index;
      say(`ref.run_stage(Stage(${JSON.stringify(stage.name)}, ${JSON.stringify(stage.turn_on)}))`);
      onrun(stage);
    }
  }

  /** The stage `.` would run, for the palette's label — "" when there is none. */
  export function selectedName(): string {
    return stages[selected]?.name ?? "";
  }

  const pct = (value: number) => `${(value * 100).toFixed(2)}%`;
</script>

<section>
  <header>
    <select
      value={preset ?? ""}
      disabled={busy}
      onchange={(event) => pick((event.currentTarget as HTMLSelectElement).value)}>
      {#if preset === null}
        <option value="" disabled>custom ({stages.length} stages)</option>
      {/if}
      {#each offered as item (item.name)}
        <option value={item.name} title={item.when_to_use}>
          {item.title}{item.modes?.includes(mode) ? "" : ` · not for ${mode}`}
        </option>
      {/each}
    </select>
    <!-- ghost, not the primary: the header's own Run is this same verb and is
         on screen whichever tab is up, so two filled buttons would be one
         action drawn twice.  Saving is the action that belongs to this panel,
         and it takes the fill while there is something to save. -->
    <button class="ghost" disabled={busy || dirty || !!noPhasesReason} onclick={onrunall}
      title={noPhasesReason
             ?? (dirty ? "save the plan first — this runs the plan the project holds"
                       : "run every stage in order")}>Run all</button>
    {#if dirty}
      <button disabled={busy} onclick={save}>Save plan</button>
      <button class="ghost" disabled={busy} onclick={load}>Revert</button>
    {/if}
  </header>

  <p class="blurb">
    A plan is an ordered list of stages. Each stage frees the parameters it
    names and refines them together with everything an earlier stage freed, so
    the free set only grows. Run all works down the whole list from a table
    where nothing is free. Run this stage runs one, from where the model
    stands now.
  </p>

  {#if chosen}
    <!-- the preset's own words are the corpus's `plans` arm, projected from
         `PLAN_INFO` — the line shown is `description`, and `when_to_use` is
         one click away rather than one hover (WP-1203/1208) -->
    <p class="muted blurb">
      <Help for="plans:{chosen.name}">{chosen.description}</Help>
    </p>
  {:else}
    <p class="muted blurb">
      Edited — no preset matches these stages. Saving stores them as they stand.
    </p>
  {/if}

  {#if dirty}
    <p class="muted blurb">Unsaved edits. Save the plan to see what its stages free.</p>
  {:else if resolved}
    <p class="muted blurb">
      Ends with {resolved.n_free_final} of {resolved.n_parameters} parameters free.
    </p>
  {/if}

  {#if error}<p class="bad">{error}</p>{/if}

  <ol class="stages">
    {#each stages as stage, index (index)}
      {@const step = ladder?.[index] ?? null}
      <li
        class:dragging={dragging === index}
        class:selected={selected === index}
        draggable={!busy}
        ondragstart={() => (dragging = index)}
        ondragend={() => (dragging = null)}
        ondragover={(event) => event.preventDefault()}
        ondrop={() => dragging !== null && move(dragging, index)}>
        <div class="head">
          <span class="grip muted" title="drag to reorder">⠿</span>
          <span class="lab"><Help for="stage_fields:name">name</Help></span>
          <input class="name mono" bind:value={stage.name} oninput={touch} disabled={busy}
            onfocus={() => (selected = index)} />
          <button class="ghost" disabled={busy} onclick={() => remove(index)} title="remove"
            >×</button>
        </div>
        <!-- the grip's width is the gutter these two rows are indented past,
             so `name` and `frees` sit in one column -->
        <label class="globs-row indent">
          <span class="lab"><Help for="stage_fields:turn_on">frees</Help></span>
          <input
            class="globs mono"
            value={stage.turn_on.join(", ")}
            placeholder="dot-path globs freed here — phases.*.cell.*"
            disabled={busy}
            oninput={(event) => globs(index, (event.currentTarget as HTMLInputElement).value)} />
        </label>

        <div class="rung indent">
          {#if step}
            <details>
              <summary>
                <span class="step">{index + 1}</span> ·
                <span class="count">+{step.frees.length}</span>
                → {step.n_free} free
                {#if step.held.length}· {step.held.length} held{/if}
                {#if step.rwp !== null}· Rwp {pct(step.rwp)}{/if}
              </summary>
              <div class="body">
                {#if step.frees.length}
                  <p class="lab">frees here</p>
                  <ul class="paths mono">
                    {#each step.frees as path (path)}<li>{path}</li>{/each}
                  </ul>
                {/if}
                {#if step.already.length}
                  <p class="lab">already free when this stage starts</p>
                  <ul class="paths mono">
                    {#each step.already as path (path)}<li>{path}</li>{/each}
                  </ul>
                {/if}
                {#if step.held.length}
                  <p class="lab">matched, and held</p>
                  <ul class="paths mono">
                    {#each step.held as row (row.path)}
                      <li>
                        <Help text={row.held_because}>{row.path}</Help>
                      </li>
                    {/each}
                  </ul>
                {/if}
                {#if !step.n_matched}
                  <p class="muted">No parameter matches these globs.</p>
                {/if}
              </div>
            </details>
          {:else}
            <span class="muted"><span class="step">{index + 1}</span> · not resolved</span>
          {/if}
          <!-- enabled while the plan is dirty, unlike Run all: this sends the
               stage as it stands on screen, so there is nothing to save first -->
          <button class="ghost" disabled={busy || !!noPhasesReason}
            title={noPhasesReason
                   ?? "run this stage as it stands here, through the same machinery a fit uses"}
            onclick={() => runStage(index)}>Run this stage</button>
        </div>

        {#if !simple}
          <div class="advanced mono muted">
            {#each FIELDS as key (key)}
              <label>
                <Help for="stage_fields:{key}">{FIELD_LABEL[key] ?? key}</Help>
                <input type="number" step="any" disabled={busy}
                  value={(stage[key] ?? "") as string | number}
                  oninput={(event) =>
                    field(index, key, (event.currentTarget as HTMLInputElement).value)} />
              </label>
            {/each}
          </div>
        {/if}
      </li>
    {/each}
  </ol>

  <!-- the stage every plan ends with (WP-2002): not editable here, and its Rwp
       is the answer's, which the last declared rung's is not -->
  {#if ladder && resolved?.closing}
    <p class="muted blurb">
      Then <span class="mono">{resolved.closing.name}</span>: every stage's globs once
      more, with windows that drop {pct(resolved.closing.window_area_tol)} of each peak{#if
        resolved.closing.rwp !== null} · Rwp {pct(resolved.closing.rwp)}{/if}
    </p>
  {/if}

  {#if setAside.length}
    <details class="aside">
      <summary>
        {setAside.length} parameter{setAside.length === 1 ? "" : "s"} you freed by
        hand, named by no stage
      </summary>
      <p class="muted">
        Run all holds these: it starts every plan from a table where nothing is
        free. Run this stage keeps them free, because a single stage continues
        from where the model stands.
      </p>
      <ul class="paths mono">
        {#each setAside as path (path)}<li>{path}</li>{/each}
      </ul>
    </details>
  {/if}

  {#if !simple}
    <p class="muted blurb">
      <label title="report a parameter pair correlated above this after each stage">
        correlation guard
        <input class="mono guard" type="number" step="0.01" min="0" max="1" bind:value={guard}
          oninput={touch} disabled={busy} />
      </label>
    </p>
  {/if}
</section>

<style>
  section {
    display: flex;
    flex-direction: column;
    min-height: 0;
    overflow: auto;
    flex: 1 1 auto;
    padding: 6px 8px 10px;
  }

  header {
    display: flex;
    gap: 6px;
    align-items: center;
    flex-wrap: wrap;
  }

  select {
    flex: 1 1 auto;
    min-width: 0;
    padding: 3px 4px;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--bg);
    color: var(--fg);
  }

  .blurb {
    margin: 4px 0;
  }

  ol.stages {
    list-style: none;
    margin: 4px 0 0;
    padding: 0;
  }

  ol.stages > li {
    border: 1px solid var(--line);
    border-radius: 5px;
    padding: 4px 5px;
    margin-bottom: 4px;
    background: var(--panel);
  }

  ol.stages > li.dragging {
    opacity: 0.5;
  }

  ol.stages > li.selected {
    border-color: var(--accent);
  }

  .head {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .grip {
    cursor: grab;
    flex: 0 0 14px;
  }

  /* past the grip, so every row's label starts in the same column */
  .indent {
    padding-left: 18px;
  }

  .step {
    font-variant-numeric: tabular-nums;
  }

  /* a field's label sits on the control's row (WP-1201's --text-sm register) */
  .lab {
    font-size: var(--text-sm);
    flex: 0 0 34px;
  }

  input {
    border: 1px solid transparent;
    background: transparent;
    color: inherit;
    border-radius: 3px;
    padding: 1px 3px;
    min-width: 0;
  }

  input:focus {
    border-color: var(--accent);
    background: var(--bg);
    outline: none;
  }

  .name {
    flex: 1 1 auto;
    font-weight: 600;
  }

  .globs-row {
    display: flex;
    align-items: center;
    gap: 4px;
    margin-top: 3px;
  }

  .globs {
    flex: 1 1 auto;
    border-color: var(--line);
  }

  /* the ladder line: what this stage adds, and the one verb that runs it */
  .rung {
    display: flex;
    align-items: baseline;
    justify-content: space-between;
    gap: 6px;
    flex-wrap: wrap;
    margin-top: 3px;
    font-size: var(--text-sm);
  }

  .rung details {
    flex: 1 1 auto;
    min-width: 0;
  }

  .rung summary {
    cursor: pointer;
    user-select: none;
  }

  .rung .count {
    font-variant-numeric: tabular-nums;
    font-weight: 600;
  }

  .rung .body {
    padding: 2px 0 2px 12px;
  }

  .rung .body p {
    margin: 3px 0 1px;
  }

  ul.paths {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  ul.paths li {
    overflow-wrap: anywhere;
  }

  /* one kind of field per box, so a column each — inline labels of different
     widths put the boxes at as many different offsets on every stage */
  .advanced {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 2px 8px;
    margin-top: 3px;
    font-size: var(--text-sm);
  }

  .advanced label {
    display: flex;
    flex-direction: column;
    gap: 1px;
    min-width: 0;
  }

  .advanced input {
    width: 100%;
    border-color: var(--line);
  }

  details.aside {
    margin-top: 6px;
    border: 1px solid var(--line);
    border-radius: 4px;
    padding: 2px 8px 4px;
    font-size: var(--text-sm);
  }

  details.aside summary {
    cursor: pointer;
    user-select: none;
  }

  .guard {
    width: 60px;
    border-color: var(--line);
  }

  .bad {
    color: var(--bad);
    margin: 2px 0;
  }
</style>
