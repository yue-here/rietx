<script lang="ts">
  /**
   * The plan as a recipe (WP-2127; the ladder since WP-1208, the editor since
   * WP-1011): one stage per row, read top to bottom, each saying which
   * parameters it takes out of the user's hands.
   *
   * A project stores the plan **expanded through its mode**, so this list is
   * exactly what a run will execute — picking `mccusker_default` in Le Bail
   * mode shows `profile_only`'s stages, because that is what `fit` would have
   * substituted at run time (WP-1008).  The preset named in the menu is
   * *derived* by comparing the stages against the registry, so an edited plan
   * reads "edited" by itself rather than by a flag someone has to clear.
   *
   * Five rules.
   *
   * **The numbers come from the server, resolved, never matched here.**  What
   * a stage frees is not its globs' matches: it is the matches minus what is
   * tied, locked, mode-fixed or degenerate with a free cell, and those rules
   * live in `ParameterTable.set_vary`.  `GET /api/plan/resolve` runs them, and
   * `lib/fnmatch.ts` stays the parameter table's bulk-edit preview.
   *
   * **An edited stage has no resolved facts, and the stages before it keep
   * theirs.**  A plan is cumulative, so stage k's facts depend on stages 0…k
   * alone (`lib/plan.ts:resolvedPrefix`).  The closing stage's Rwp and the
   * set-aside list depend on the whole plan, so an edit blanks them and keeps
   * their rows, since a row that vanished would move what is below it.
   *
   * **The plan's edits are the action bar's** (the maintainer's ruling of
   * 2026-11-07: the panel ends in Apply and "Apply and refine").  An edited
   * plan is one pending edit there; Apply stores it through `PUT /api/plan`
   * (`save`), Revert drops it (`revert`), and Refine on the staged plan
   * applies it first.  So this panel has no Save button of its own.  A head
   * move refetches the server's plan and keeps an unsaved one on screen,
   * because the bar's Apply moves the head before it saves the plan.
   *
   * **Every edit can be undone** (interaction rule 10, adopted 2026-11-08).
   * Plan edits are settings, not history nodes, so the stack is the panel's
   * own (`lib/plan.ts:Undo`): ⌘Z and ⇧⌘Z inside the tab, outside a text
   * field, and the palette.  A preset pick is stored at once, because only
   * the server can expand it through the mode, and undoing it puts the stages
   * before it back on screen as an edit for Apply to store.
   *
   * **The advanced field list is derived from `lib/rxt.ts`**, whose stage
   * arrays are pinned to `StageSpec` from python (`tests/test_textdoc.py`), so
   * a field added to the schema arrives in this form under its own name.  An
   * emptied box is `null` only where the schema admits one.
   *
   * A glob is a `.chip`, a fact, and the verb that removes it is a ghost
   * button beside it: a chip never acts (`gui/CLAUDE.md` § House style).
   * A stage's fixes (WP-2208) are a second row of the same shape, drawn when
   * the stage fixes something or `+ Fix` opened it, as the workshop prototype
   * draws its Fix row, so a plan that fixes nothing reads as it did.
   */
  import { tick } from "svelte";

  import Help from "../Help.svelte";
  import { ApiError, api } from "../api";
  import {
    type Stage, Undo, addGlobs, dropIndex, moveStage, newStageName, planDiffers,
    resolvedPrefix, slideOffset,
  } from "../lib/plan";
  import type { PlanDraft } from "../lib/recovery";
  import { STAGE_INT_WORDS, STAGE_NULLABLE_WORDS, STAGE_WORDS } from "../lib/rxt";

  let {
    mode = "rietveld",
    head = null,
    busy = false,
    noPhasesReason = null,
    simple = true,
    say = (_line: string) => {},
    onrun = (_stage: any) => {},
    onpending = (_edited: boolean) => {},
  }: {
    mode?: string;
    head?: string | null;
    busy?: boolean;
    /** Why a run is refused right now, or `null`.  The sentence is the
     *  shell's (WP-1207): it names the route out, and a second copy here said
     *  something else for the same state. */
    noPhasesReason?: string | null;
    simple?: boolean;
    say?: (line: string) => void;
    onrun?: (stage: any) => void;
    /** whether the plan on screen differs from the one the project holds */
    onpending?: (edited: boolean) => void;
  } = $props();

  /** Every `StageSpec` field but the two each row already draws. */
  const FIELDS = STAGE_WORDS.filter((word) => word !== "free");

  /** Short names for the boxes, at the width a sidebar has. */
  const FIELD_LABEL: Record<string, string> = {
    max_iter: "iter",
    lebail_cycles: "lebail",
    lebail_tol: "lebail tol",
    strain_seed: "strain",
    restraint_weight_scale: "restraint",
    window_slack_deg: "slack",
    lorentz_window_tol: "lorentz tol",
  };

  /** The plan the project holds, as `GET /api/plan` last answered. */
  let saved = $state<Stage[]>([]);
  let savedGuard = $state(0.98);
  /** The plan on screen. */
  let stages = $state<Stage[]>([]);
  let guard = $state(0.98);
  let preset = $state<string | null>(null);
  let presets = $state<any[]>([]);
  let resolved = $state<any>(null);
  let error = $state("");
  /** which stage the `.` shortcut and the palette entry would run */
  let selected = $state(0);
  /** the text typed into each stage's add field, by index */
  let adding = $state<Record<number, string>>({});
  /** the text typed into each stage's fix field, by index (WP-2208); a key
   *  present, even as "", is a fix row `+ Fix` opened */
  let fixing = $state<Record<number, string>>({});
  let list = $state<HTMLOListElement | null>(null);

  /** The plan fields this panel has no control for (`intermediate_ftol`,
   *  `lebail_passes`, whatever comes next), carried through a save. */
  let extra = $state<Record<string, unknown>>({});
  function otherFields(plan: Record<string, unknown>) {
    const { stages: _s, correlation_guard: _g, ...rest } = plan;
    return rest;
  }

  const edited = $derived(planDiffers(saved, stages) || guard !== savedGuard);
  $effect(() => onpending(edited));

  /** The stored stages `resolved` was computed for.  A save moves `saved`
   *  before its resolve answers, and the old facts must not read as the new
   *  plan's in between (or for good, if that resolve fails). */
  let resolvedFor = $state<Stage[]>([]);

  /** How many leading stages still carry the server's resolved facts. */
  const prefix = $derived(
    resolved?.stages?.length === resolvedFor.length ? resolvedPrefix(resolvedFor, stages) : 0,
  );
  /** Whether the whole-plan facts (closing Rwp, set-aside) describe the plan
   *  on screen. */
  const current = $derived(!edited && !planDiffers(resolvedFor, saved));
  // Both depend on the whole plan, so an edit takes their numbers away and
  // leaves their rows: an edit that removed a row would move what is below
  // it, and no edit may move the layout (ruled 2026-11-07).  The closing
  // stage follows the plan's own field, which no stage edit changes.
  const closing = $derived(resolved?.closing ?? null);
  const setAside = $derived((resolved?.set_aside ?? []) as string[]);

  /** Presets whose declared modes include the project's, first. */
  const offered = $derived(
    [...presets].sort((a, b) => {
      const fit = (p: any) => (p.modes?.includes(mode) ? 0 : 1);
      return fit(a) - fit(b);
    }),
  );
  const chosen = $derived(presets.find((p) => p.name === preset) ?? null);

  /* ---- undo ------------------------------------------------------------ */

  const history = new Undo<{ stages: Stage[]; guard: number }>();
  /** bumped on every change of the stack, so `canUndo` is reactive */
  let undoTick = $state(0);
  /** the field being typed into, so one burst of typing is one undo step */
  let typing = "";

  function snapshot() {
    return { stages: $state.snapshot(stages) as Stage[], guard };
  }

  /** Record the state an edit is about to leave. */
  function remember(key = "") {
    if (key && key === typing) return;
    typing = key;
    history.record(snapshot());
    undoTick += 1;
  }

  function restore(state: { stages: Stage[]; guard: number } | null) {
    if (!state) return;
    stages = state.stages;
    guard = state.guard;
    typing = "";
    undoTick += 1;
    clampSelected();
  }

  /** Keep the selected stage on the list after its length changed. */
  function clampSelected() {
    selected = Math.min(selected, Math.max(0, stages.length - 1));
  }

  // the controls are disabled during a run, and ⌘Z must not edit around them
  export function undo() {
    if (!busy) restore(history.undo(snapshot()));
  }

  export function redo() {
    if (!busy) restore(history.redo(snapshot()));
  }

  export function canUndo(): boolean {
    void undoTick;
    return !busy && history.canUndo;
  }

  export function canRedo(): boolean {
    void undoTick;
    return !busy && history.canRedo;
  }

  function keydown(event: KeyboardEvent) {
    if (!(event.metaKey || event.ctrlKey) || event.key.toLowerCase() !== "z") return;
    // a text field keeps its own undo, which is the one a person typing expects
    const target = event.target as HTMLElement | null;
    if (target?.closest?.("input, textarea, select")) return;
    event.preventDefault();
    if (event.shiftKey) redo();
    else undo();
  }

  /* ---- the server's plan ----------------------------------------------- */

  function adopt(plan: any) {
    const keep = edited;
    saved = plan.plan.stages;
    savedGuard = plan.plan.correlation_guard;
    extra = otherFields(plan.plan);
    preset = plan.preset;
    if (!keep) {
      stages = structuredClone(plan.plan.stages);
      guard = plan.plan.correlation_guard;
      clampSelected();
    }
  }

  /** Bumped by every load and every save, so an answer that a later request
   *  has overtaken is dropped.  The bar's Apply moves the head (a load) and
   *  then saves the plan: a GET sent before that PUT and answered after it
   *  would otherwise put the old plan back on screen as the stored one. */
  let generation = 0;

  async function load() {
    const mine = ++generation;
    try {
      const [plan, registry, resolve] = await Promise.all([
        api.plan(), api.plans(), api.planResolve(),
      ]);
      presets = registry.plans;
      if (mine !== generation) return;
      adopt(plan);
      resolved = resolve;
      resolvedFor = structuredClone(plan.plan.stages);
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

  /** Store a plan; true when the server took it. */
  async function put(body: Record<string, unknown>): Promise<boolean> {
    ++generation;
    let payload: any;
    try {
      payload = await api.putPlan(body);
    } catch (exc) {
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the plan is read-only until it ends"
        : (exc as Error).message;
      return false;
    }
    saved = payload.plan.stages;
    savedGuard = payload.plan.correlation_guard;
    stages = structuredClone(payload.plan.stages);
    guard = payload.plan.correlation_guard;
    extra = otherFields(payload.plan);
    preset = payload.preset;
    error = "";
    clampSelected();
    // the plan is stored whatever the resolve answers, so a failure here is
    // reported and does not refuse the bar's Apply
    try {
      resolved = await api.planResolve();
      resolvedFor = structuredClone(payload.plan.stages);
    } catch (exc) {
      error = (exc as Error).message;
    }
    return true;
  }

  async function pick(name: string) {
    // recorded only once the server took the pick, so a refused one leaves
    // no empty undo step and keeps the redo side
    const before = snapshot();
    say(`plan = resolve_plan(${JSON.stringify(name)}, ${JSON.stringify(mode)})`);
    if (await put({ preset: name })) {
      history.record(before);
      typing = "";
      undoTick += 1;
    }
  }

  /** The action bar's Apply: store the plan on screen.  True when there was
   *  nothing to store or the server took it. */
  export async function save(): Promise<boolean> {
    if (!edited) return true;
    say(`project.doc.plan = PlanSpec(stages=[${stages.length}], correlation_guard=${guard})`);
    return put({ plan: { ...extra, stages: $state.snapshot(stages), correlation_guard: guard } });
  }

  /** The edited plan, for the recovery copy (WP-2209), or `null`. */
  export function draft(): PlanDraft | null {
    return edited ? { stages: $state.snapshot(stages) as Stage[], guard } : null;
  }

  /** Put a recovered plan back on screen as the pending edit; one undo step. */
  export function restoreDraft(d: PlanDraft) {
    if (!Array.isArray(d.stages)) return;
    remember();
    stages = structuredClone(d.stages) as Stage[];
    guard = typeof d.guard === "number" ? d.guard : guard;
    clampSelected();
  }

  /** The action bar's Revert: the plan the project holds, back on screen. */
  export function revert() {
    if (!edited) return;
    remember();
    stages = $state.snapshot(saved) as Stage[];
    guard = savedGuard;
    adding = {};
    fixing = {};
    error = "";
    clampSelected();
  }

  /* ---- edits ----------------------------------------------------------- */

  function move(from: number, to: number) {
    if (from === to || to < 0 || to >= stages.length) return;
    remember();
    // the selection and each half-typed glob follow their stage, which every
    // stage between `from` and `to` changes the index of
    const order = moveStage(stages.map((_, i) => i), from, to);
    stages = moveStage(stages, from, to);
    selected = Math.max(0, order.indexOf(selected));
    const follow = (typed: Record<number, string>) => Object.fromEntries(
      order.map((old, k) => [k, typed[old]] as const).filter(([, text]) => text !== undefined),
    );
    adding = Object.fromEntries(Object.entries(follow(adding)).filter(([, text]) => text));
    fixing = follow(fixing);
  }

  function removeStage(index: number) {
    if (stages.length <= 1) return;
    remember();
    stages = stages.filter((_, i) => i !== index);
    adding = {};
    fixing = {};
    selected = Math.min(selected, stages.length - 1);
  }

  async function addStage() {
    remember();
    const name = newStageName(stages);
    stages = [...stages, { name, turn_on: [], turn_off: [] }];
    selected = stages.length - 1;
    await tick();
    const input = list?.querySelector<HTMLInputElement>(
      `:scope > li.stage:nth-child(${stages.length}) input.name`);
    input?.focus({ preventScroll: true });
    input?.select();
    input?.scrollIntoView?.({ block: "nearest" });
  }

  function rename(index: number, value: string) {
    remember(`name:${index}`);
    stages[index].name = value;
  }

  function addGlob(index: number) {
    const text = adding[index] ?? "";
    const next = addGlobs(stages[index].turn_on, text);
    adding[index] = "";
    if (next.length === stages[index].turn_on.length) return;
    remember();
    stages[index].turn_on = next;
  }

  function removeGlob(index: number, at: number) {
    remember();
    stages[index].turn_on = stages[index].turn_on.filter((_, i) => i !== at);
  }

  /* a stage's fixes (WP-2208): applied after its frees, as `_run_stage` does */
  function addFix(index: number) {
    const text = fixing[index] ?? "";
    const before = stages[index].turn_off ?? [];
    const next = addGlobs(before, text);
    fixing[index] = "";
    if (next.length === before.length) return;
    remember();
    stages[index].turn_off = next;
  }

  /** `+ Fix`: open the stage's fix row and put the cursor in its field. */
  async function openFix(index: number) {
    fixing[index] = fixing[index] ?? "";
    await tick();
    list?.querySelector<HTMLInputElement>(
      `:scope > li.stage:nth-child(${index + 1}) input.add.fix`)?.focus({ preventScroll: true });
  }

  function removeFix(index: number, at: number) {
    remember();
    stages[index].turn_off = (stages[index].turn_off ?? []).filter((_, i) => i !== at);
  }

  function field(index: number, key: string, raw: string) {
    let value: unknown;
    if (raw === "") {
      if (!STAGE_NULLABLE_WORDS.includes(key)) return;   // left alone, not nulled
      value = null;
    } else {
      value = STAGE_INT_WORDS.includes(key) ? parseInt(raw, 10) : Number(raw);
    }
    remember(`field:${index}:${key}`);
    stages[index][key] = value;
  }

  function setGuard(raw: string) {
    if (raw === "") return;
    remember("guard");
    guard = Number(raw);
  }

  /* ---- reorder: the three-line handle ---------------------------------- */

  /** The drag in progress: where it started, where the row would land, and
   *  the rows' geometry when it began. */
  let drag = $state<{ from: number; to: number; dy: number; height: number;
                      centres: number[]; y0: number } | null>(null);

  function grab(event: PointerEvent, index: number) {
    if (busy || event.button !== 0 || !list) return;
    const rows = [...list.querySelectorAll<HTMLElement>(":scope > li.stage")];
    const rects = rows.map((row) => row.getBoundingClientRect());
    drag = { from: index, to: index, dy: 0, height: rects[index].height,
             centres: rects.map((r) => r.top + r.height / 2), y0: event.clientY };
    (event.currentTarget as HTMLElement).setPointerCapture?.(event.pointerId);
    event.preventDefault();
  }

  function drift(event: PointerEvent) {
    if (!drag) return;
    const dy = event.clientY - drag.y0;
    drag.dy = dy;
    drag.to = dropIndex(drag.centres, drag.from, drag.centres[drag.from] + dy);
  }

  async function drop() {
    if (!drag) return;
    const { from, to } = drag;
    drag = null;
    move(from, to);
    await tick();
    handleAt(to)?.focus({ preventScroll: true });
  }

  function handleAt(index: number) {
    return list?.querySelector<HTMLElement>(`[data-handle="${index}"]`) ?? null;
  }

  async function nudge(event: KeyboardEvent, index: number) {
    const step = ({ ArrowUp: -1, ArrowDown: 1 } as Record<string, number>)[event.key];
    if (!step || busy) return;
    event.preventDefault();
    const to = index + step;
    if (to < 0 || to >= stages.length) return;
    move(index, to);
    await tick();
    handleAt(to)?.focus({ preventScroll: true });
  }

  function shift(index: number): string {
    if (!drag) return "";
    if (index === drag.from) return `translateY(${drag.dy}px)`;
    const by = slideOffset(index, drag.from, drag.to, drag.height);
    return by ? `translateY(${by}px)` : "";
  }

  /* ---- runs ------------------------------------------------------------ */

  export function runStage(index = selected) {
    const stage = stages[index];
    if (stage) {
      selected = index;
      const off = stage.turn_off?.length ? `, turn_off=${JSON.stringify(stage.turn_off)}` : "";
      say(`ref.run_stage(Stage(${JSON.stringify(stage.name)}, ${JSON.stringify(stage.turn_on)}${off}))`);
      onrun($state.snapshot(stage));
    }
  }

  /** The stage `.` would run, for the palette's label — "" when there is none. */
  export function selectedName(): string {
    return stages[selected]?.name ?? "";
  }

  const pct = (value: number) => `${(value * 100).toFixed(2)}%`;
</script>

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<section onkeydown={keydown} aria-label="plan">
  <header>
    <span class="lab">
      {#if chosen && !edited}<Help for="plans:{chosen.name}">Preset</Help>{:else}Preset{/if}
    </span>
    <select
      value={edited || preset === null ? "" : preset}
      disabled={busy}
      title={chosen && !edited ? chosen.description : null}
      onchange={(event) => pick((event.currentTarget as HTMLSelectElement).value)}>
      {#if edited || preset === null}
        <option value="" disabled>
          {chosen ? `${chosen.title}, edited` : `custom, ${stages.length} stages`}
        </option>
      {/if}
      {#each offered as item (item.name)}
        <option value={item.name} title={item.when_to_use}>
          {item.title}{item.modes?.includes(mode) ? "" : ` · not for ${mode}`}
        </option>
      {/each}
    </select>
    <button class="ghost" disabled={busy} onclick={addStage}>+ Stage</button>
  </header>

  {#if error}<p class="bad">{error}</p>{/if}

  <ol class="stages" bind:this={list}>
    {#each stages as stage, index (index)}
      {@const step = index < prefix ? resolved.stages[index] : null}
      <li class="stage" class:lift={drag?.from === index} class:slide={!!drag && drag.from !== index}
        class:selected={selected === index} style:transform={shift(index)}>
        <div class="head">
          <!-- a handle, not a button register: it is dragged, and a box would
               be a second thing to aim at in a row that is already the target -->
          <span class="handle" role="button" tabindex={busy ? -1 : 0} data-handle={index}
            aria-label="Move stage {index + 1}" aria-disabled={busy}
            title="Drag to reorder, or press ↑ and ↓"
            onpointerdown={(event) => grab(event, index)} onpointermove={drift}
            onpointerup={drop} onpointercancel={() => (drag = null)}
            onkeydown={(event) => nudge(event, index)}>
            <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 3.5h8M2 6h8M2 8.5h8" /></svg>
          </span>
          <span class="step">{index + 1}</span>
          <input class="name mono" value={stage.name} disabled={busy}
            aria-label="Name of stage {index + 1}"
            oninput={(event) => rename(index, (event.currentTarget as HTMLInputElement).value)}
            onfocus={() => (selected = index)} onblur={() => (typing = "")} />
          <button class="ghost" disabled={busy || !!noPhasesReason}
            title={noPhasesReason ?? "run this stage as it stands here, from where the model stands"}
            onclick={() => runStage(index)}>Run this stage</button>
          <button class="ghost" disabled={busy || stages.length <= 1}
            aria-label="Remove stage {index + 1}"
            title={stages.length <= 1 ? "a plan needs at least one stage" : "remove this stage"}
            onclick={() => removeStage(index)}>×</button>
        </div>

        <div class="frees indent">
          <span class="lab"><Help for="stage_fields:turn_on">Frees</Help></span>
          {#each stage.turn_on as glob, at (at)}
            <span class="glob">
              <span class="chip mono">{glob}</span>
              <button class="ghost" disabled={busy}
                aria-label="Remove {glob} from stage {index + 1}"
                title="remove from this stage"
                onclick={() => removeGlob(index, at)}>×</button>
            </span>
          {/each}
          <input class="add mono" disabled={busy} placeholder="add a glob"
            aria-label="Add a glob to stage {index + 1}"
            title="Type a dot-path glob and press Enter"
            value={adding[index] ?? ""}
            oninput={(event) => (adding[index] = (event.currentTarget as HTMLInputElement).value)}
            onkeydown={(event) => { if (event.key === "Enter") addGlob(index); }} />
          {#if !stage.turn_off?.length && fixing[index] === undefined}
            <button class="ghost" disabled={busy}
              title="fix parameters in this stage, after it frees its own"
              onclick={() => openFix(index)}>+ Fix</button>
          {/if}
        </div>

        <!-- what the stage fixes after it frees (WP-2208), drawn once it fixes
             something or `+ Fix` opened it -->
        {#if stage.turn_off?.length || fixing[index] !== undefined}
        <div class="frees fixing indent">
          <span class="lab"><Help for="stage_fields:turn_off">Fixes</Help></span>
          {#each stage.turn_off ?? [] as glob, at (at)}
            <span class="glob">
              <span class="chip mono">{glob}</span>
              <button class="ghost" disabled={busy}
                aria-label="Remove {glob} from what stage {index + 1} fixes"
                title="remove from this stage"
                onclick={() => removeFix(index, at)}>×</button>
            </span>
          {/each}
          <input class="add fix mono" disabled={busy} placeholder="add a glob to fix"
            aria-label="Add a glob stage {index + 1} fixes"
            title="Type a dot-path glob and press Enter: the stage fixes it after its frees"
            value={fixing[index] ?? ""}
            oninput={(event) => (fixing[index] = (event.currentTarget as HTMLInputElement).value)}
            onkeydown={(event) => { if (event.key === "Enter") addFix(index); }} />
        </div>
        {/if}

        <div class="rung indent">
          {#if step}
            <details>
              <summary>
                <span class="count">+{step.frees.length}</span>
                {#if step.fixes?.length}<span class="count">−{step.fixes.length}</span>{/if}
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
                {#if step.fixes?.length}
                  <p class="lab">fixed here</p>
                  <ul class="paths mono">
                    {#each step.fixes as path (path)}<li>{path}</li>{/each}
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
                      <li><Help text={row.held_because}>{row.path}</Help></li>
                    {/each}
                  </ul>
                {/if}
                {#if !step.n_matched}
                  <p class="muted">No parameter matches these globs.</p>
                {/if}
              </div>
            </details>
          {:else}
            <span class="muted" title="Apply the plan to see what this stage frees">not applied</span>
          {/if}
        </div>

        {#if !simple}
          <div class="advanced mono muted indent">
            {#each FIELDS as key (key)}
              <label>
                <Help for="stage_fields:{key}">{FIELD_LABEL[key] ?? key}</Help>
                <input type="number" step="any" disabled={busy}
                  value={(stage[key] ?? "") as string | number}
                  onblur={() => (typing = "")}
                  oninput={(event) =>
                    field(index, key, (event.currentTarget as HTMLInputElement).value)} />
              </label>
            {/each}
          </div>
        {/if}
      </li>
    {/each}

    <!-- the stage every plan ends with (WP-2002): not editable here, and its
         Rwp is the answer's, which the last declared rung's is not -->
    {#if closing}
      <li class="closing">
        <div class="head">
          <span class="handle-space"></span>
          <span class="step"></span>
          <span class="mono muted">{closing.name}</span>
        </div>
        <div class="frees indent muted"
          title="every stage's globs once more, with windows that drop {pct(closing.window_area_tol)} of each peak">
          <span class="lab">Frees</span> everything above
          {#if closing.fixes?.length}· keeps {closing.fixes.length} fixed{/if}
          {#if current && closing.rwp !== null}· Rwp {pct(closing.rwp)}{/if}
        </div>
      </li>
    {/if}
  </ol>

  {#if setAside.length}
    <details class="aside">
      <summary title="The staged plan starts from a table where nothing is free, so it holds these. Run this stage keeps them free, because a single stage continues from where the model stands.">
        {#if !current}parameters you freed by hand: not applied{:else}{setAside.length}
          parameter{setAside.length === 1 ? "" : "s"} you freed by hand, held by the plan{/if}
      </summary>
      {#if current}
        <ul class="paths mono">
          {#each setAside as path (path)}<li>{path}</li>{/each}
        </ul>
      {/if}
    </details>
  {/if}

  {#if !simple}
    <p class="guardline muted">
      <label title="report a parameter pair correlated above this after each stage">
        correlation guard
        <input class="mono guard" type="number" step="0.01" min="0" max="1" value={guard}
          disabled={busy} onblur={() => (typing = "")}
          oninput={(event) => setGuard((event.currentTarget as HTMLInputElement).value)} />
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
    padding: 0 8px 10px;
  }

  /* the plan bar stays in view while a long plan scrolls under it */
  header {
    position: sticky;
    top: 0;
    z-index: 2;
    display: flex;
    gap: 6px;
    align-items: center;
    padding: 6px 0;
    background: var(--panel);
    border-bottom: 1px solid var(--line);
  }

  select {
    flex: 1 1 0;
    min-width: 0;
    padding: 3px 4px;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--bg);
    color: var(--fg);
  }

  ol.stages {
    list-style: none;
    margin: 0;
    padding: 0;
  }

  ol.stages > li {
    padding: 6px 0;
    background: var(--panel);
  }

  ol.stages > li + li {
    border-top: 1px solid var(--line);
  }

  /* the lifted stage follows the pointer above its neighbours, which slide
     aside to show where it will land */
  ol.stages > li.lift {
    position: relative;
    z-index: 1;
    box-shadow: 0 6px 20px rgb(0 0 0 / 0.16);
  }

  ol.stages > li.slide {
    transition: transform 0.14s ease;
  }

  .head {
    display: flex;
    align-items: center;
    gap: 4px;
  }

  .handle,
  .handle-space {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    flex: 0 0 18px;
    height: 22px;
    color: var(--muted);
  }

  .handle {
    cursor: grab;
    border-radius: 4px;
    touch-action: none;
  }

  .handle:hover {
    color: var(--fg);
    background: color-mix(in srgb, var(--fg) 8%, transparent);
  }

  .handle:focus-visible {
    outline: 2px solid var(--accent);
    outline-offset: -2px;
  }

  li.lift .handle {
    cursor: grabbing;
  }

  .handle svg {
    width: 12px;
    height: 12px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.5;
    stroke-linecap: round;
  }

  .step {
    flex: 0 0 2ch;
    text-align: right;
    font-variant-numeric: tabular-nums;
    color: var(--muted);
  }

  li.selected .step {
    color: var(--accent-ink);
    font-weight: 600;
  }

  /* past the handle and the number, so a stage's lines start under its name */
  .indent {
    padding-left: calc(18px + 2ch + 8px);
  }

  .lab {
    font-size: var(--text-sm);
    color: var(--muted);
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

  /* the recipe's verb line: what this stage frees, one chip per glob */
  .frees {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 4px 6px;
    margin-top: 3px;
    font-size: var(--text-sm);
  }

  /* a glob and its × wrap as one, so the verb never lands on another line
     from the fact it acts on */
  .glob {
    display: inline-flex;
    align-items: center;
    gap: 1px;
  }

  .add {
    flex: 1 1 12ch;
    border-color: var(--line);
  }

  .rung {
    margin-top: 3px;
    font-size: var(--text-sm);
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
    border-top: 1px solid var(--line);
    padding: 4px 0;
    font-size: var(--text-sm);
  }

  details.aside summary {
    cursor: pointer;
    user-select: none;
  }

  .guardline {
    margin: 6px 0 0;
  }

  .guard {
    width: 60px;
    border-color: var(--line);
  }

  .bad {
    color: var(--bad);
    margin: 4px 0;
  }
</style>
