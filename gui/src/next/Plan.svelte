<script lang="ts">
  /**
   * The plan as a recipe at `/next` (WP-2231, R4; moved from
   * `panels/Plan.svelte`, WP-2127, whose rules it keeps). One stage per block,
   * read top to bottom: first the plan frees these, then those, and here it
   * fixes these. A last block names what no stage frees.
   *
   * What it keeps from today's panel, each a rule of gui/CLAUDE.md:
   *
   * - **The numbers are the server's.** What a stage frees is
   *   `GET /api/plan/resolve`'s answer (WP-1208), and an edited stage, with
   *   every stage below it, has none (`lib/plan.ts:resolvedPrefix`).
   * - **The plan's edits are the action bar's.** An edited plan is one pending
   *   edit there; Apply stores it (`save`), Revert drops it (`revert`).
   * - **Every edit can be undone**: ⌘Z and ⇧⌘Z inside the tab, outside a text
   *   field, on the panel's own stack, since a plan edit is a setting and makes
   *   no history node.
   *
   * What the rebuild changes, from the prototype and WP-2214 rows 104-117: the
   * preset select becomes the plan menu on the plan's name; a glob is a named
   * chip on a Free or Fix row, added from a grouped picker rather than typed;
   * Run this stage and the stage's settings sit on its ⋯ menu and its context
   * menu; the closing stage and "Never freed" end the list.
   */
  import { tick } from "svelte";

  import Help from "../Help.svelte";
  import { ApiError, api } from "../api";
  import type { HelpCorpus } from "../lib/help";
  import { resolve as helpEntry } from "../lib/help";
  import {
    type Stage, Undo, dropIndex, moveStage, newStageName, planDiffers, resolvedPrefix, slideOffset,
  } from "../lib/plan";
  import type { PlanDraft } from "../lib/recovery";
  import { STAGE_INT_WORDS, STAGE_NULLABLE_WORDS, STAGE_WORDS } from "../lib/rxt";
  import Menu, { type MenuAt, type MenuEntry } from "./Menu.svelte";
  import {
    type PickOption, type PlanRow, freeBy, globName, matchesQuery, namedIn, pct, pickOptions, withGlob,
  } from "./plan";

  let {
    mode = "rietveld",
    head = null,
    busy = false,
    noPhasesReason = null,
    corpus = null,
    phaseNames = [],
    say = (_line: string) => {},
    onrun = (_stage: any, _echo: string) => {},
    onpending = (_edited: boolean) => {},
    onsaved = () => {},
  }: {
    mode?: string;
    head?: string | null;
    busy?: boolean;
    /** why a run is refused right now (the shell's sentence, WP-1207), or null */
    noPhasesReason?: string | null;
    corpus?: HelpCorpus | null;
    phaseNames?: readonly string[];
    say?: (line: string) => void;
    /** run `stage`; `echo` is its Python, for the shell to print once the run starts */
    onrun?: (stage: any, echo: string) => void;
    /** whether the plan on screen differs from the one the project holds */
    onpending?: (edited: boolean) => void;
    /** the project now holds another plan (Apply, or a preset picked) */
    onsaved?: () => void;
  } = $props();

  /** Every `StageSpec` field a stage's settings hold: all but its globs. */
  const FIELDS = STAGE_WORDS.filter((word) => word !== "free");

  /** The plan the project holds, as `GET /api/plan` last answered. */
  let saved = $state<Stage[]>([]);
  let savedGuard = $state(0.98);
  /** The plan on screen. */
  let stages = $state<Stage[]>([]);
  let guard = $state(0.98);
  let preset = $state<string | null>(null);
  let presets = $state<any[]>([]);
  let resolved = $state.raw<any>(null);
  let resolvedFor = $state<Stage[]>([]);
  /** The parameter rows, for the picker and the names of what no stage frees. */
  let rows = $state.raw<PlanRow[]>([]);
  let error = $state("");
  /** which stage the `.` key and the palette run */
  let selected = $state(0);
  /** the stages whose lists are open, by index; a disclosure stays open until
   *  its own control closes it (`gui/STYLE.md` § Components) */
  let open = $state<Set<number>>(new Set());
  let asideOpen = $state(false);
  let list = $state<HTMLDivElement | null>(null);

  /** The plan fields this panel has no control for, carried through a save. */
  let extra = $state<Record<string, unknown>>({});
  function otherFields(plan: Record<string, unknown>) {
    const { stages: _s, correlation_guard: _g, ...rest } = plan;
    return rest;
  }

  const edited = $derived(planDiffers(saved, stages) || guard !== savedGuard);
  $effect(() => onpending(edited));

  const prefix = $derived(
    resolved?.stages?.length === resolvedFor.length ? resolvedPrefix(resolvedFor, stages) : 0,
  );
  /** Whether the whole-plan facts (the closing Rwp, Never freed, the set-aside
   *  list) describe the plan on screen. */
  const current = $derived(!edited && !planDiffers(resolvedFor, saved));
  const closing = $derived(resolved?.closing ?? null);
  const setAside = $derived((resolved?.set_aside ?? []) as string[]);
  const neverFreed = $derived((resolved?.never_freed ?? []) as string[]);
  const chosen = $derived(presets.find((p) => p.name === preset) ?? null);
  const planName = $derived(chosen ? chosen.title : "This project's plan");

  /** What no stage frees, one read-only chip per family: its name, its count
   *  and the paths it stands for, which the chip's tooltip lists. */
  const neverChips = $derived.by(() => {
    const byPath = new Map(rows.map((r) => [r.path, r]));
    const named = new Map<string, string[]>();
    for (const path of neverFreed) {
      const key = byPath.get(path)?.help_key ?? null;
      const name = (key && globName(key, corpus)) || path;
      named.set(name, [...(named.get(name) ?? []), path]);
    }
    return [...named].map(([name, paths]) => ({
      words: paths.length > 1 ? `${name} (${paths.length})` : name,
      mono: name === paths[0],
      paths,
    }));
  });

  /* ---- undo ------------------------------------------------------------ */

  const history = new Undo<{ stages: Stage[]; guard: number }>();
  let undoTick = $state(0);
  /** the field being typed into, so one burst of typing is one undo step */
  let typing = "";

  function snapshot() {
    return { stages: $state.snapshot(stages) as Stage[], guard };
  }

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

  function clampSelected() {
    selected = Math.min(selected, Math.max(0, stages.length - 1));
  }

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

  /** Bumped by every load and every save, so an overtaken answer is dropped
   *  (the bar's Apply moves the head, a load, and then saves the plan). */
  let generation = 0;

  async function load() {
    const mine = ++generation;
    try {
      const [plan, registry, answer, params] = await Promise.all([
        api.plan(), api.plans(), api.planResolve(), api.params(),
      ]);
      presets = registry.plans;
      if (mine !== generation) return;
      adopt(plan);
      resolved = answer;
      resolvedFor = structuredClone(plan.plan.stages);
      rows = params.parameters ?? [];
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

  async function put(body: Record<string, unknown>): Promise<boolean> {
    ++generation;
    let payload: any;
    try {
      payload = await api.putPlan(body);
    } catch (exc) {
      error = exc instanceof ApiError && exc.busy
        ? "A run is in flight, so the plan cannot change until it ends."
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
    onsaved();
    try {
      resolved = await api.planResolve();
      resolvedFor = structuredClone(payload.plan.stages);
    } catch (exc) {
      error = (exc as Error).message;
    }
    return true;
  }

  async function pick(name: string) {
    const before = snapshot();
    say(`plan = resolve_plan(${JSON.stringify(name)}, ${JSON.stringify(mode)})`);
    if (await put({ preset: name })) {
      history.record(before);
      typing = "";
      undoTick += 1;
    }
  }

  /** The action bar's Apply: store the plan on screen. True when there was
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

  /** Another project is opening: drop the edit and the undo stack, which
   *  hold this project's plan and would put it on the next one's screen. */
  export function leave() {
    stages = $state.snapshot(saved) as Stage[];
    guard = savedGuard;
    error = "";
    history.clear();
    typing = "";
    undoTick += 1;
    open = new Set();
    selected = 0;
    picker = null;
    settings = null;
    menu = null;
  }

  /** The action bar's Revert: the plan the project holds, back on screen. */
  export function revert() {
    if (!edited) return;
    remember();
    stages = $state.snapshot(saved) as Stage[];
    guard = savedGuard;
    error = "";
    clampSelected();
  }

  /* ---- edits ----------------------------------------------------------- */

  function move(from: number, to: number) {
    if (from === to || to < 0 || to >= stages.length) return;
    remember();
    const order = moveStage(stages.map((_, i) => i), from, to);
    stages = moveStage(stages, from, to);
    selected = Math.max(0, order.indexOf(selected));
    open = new Set([...open].map((i) => order.indexOf(i)));
  }

  function removeStage(index: number) {
    if (stages.length <= 1) return;
    remember();
    stages = stages.filter((_, i) => i !== index);
    open = new Set([...open].filter((i) => i !== index).map((i) => (i > index ? i - 1 : i)));
    // the selected stage keeps its selection when one above it goes
    selected = Math.min(selected > index ? selected - 1 : selected, stages.length - 1);
  }

  async function addStage() {
    remember();
    const name = newStageName(stages);
    stages = [...stages, { name, turn_on: [], turn_off: [] }];
    selected = stages.length - 1;
    await tick();
    const input = list?.querySelector<HTMLInputElement>(`[data-stage="${stages.length - 1}"] input.sn`);
    input?.focus({ preventScroll: true });
    input?.select();
    input?.scrollIntoView?.({ block: "nearest" });
  }

  function rename(index: number, value: string) {
    remember(`name:${index}`);
    stages[index].name = value;
  }

  function removeGlob(index: number, side: "free" | "fix", glob: string) {
    remember();
    if (side === "free") stages[index].turn_on = stages[index].turn_on.filter((g) => g !== glob);
    else stages[index].turn_off = (stages[index].turn_off ?? []).filter((g) => g !== glob);
  }

  function toggleOpen(index: number) {
    const next = new Set(open);
    if (next.has(index)) next.delete(index);
    else next.add(index);
    open = next;
  }

  /* ---- reorder: the three-line handle ---------------------------------- */

  let drag = $state<{ from: number; to: number; dy: number; height: number;
                      centres: number[]; y0: number } | null>(null);

  function grab(event: PointerEvent, index: number) {
    if (busy || event.button !== 0 || !list) return;
    const blocks = [...list.querySelectorAll<HTMLElement>(":scope > .stg")];
    const rects = blocks.map((b) => b.getBoundingClientRect());
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

  /** Esc during a drag puts the stage back (interaction rule 2). */
  function dragKey(event: KeyboardEvent) {
    if (drag && event.key === "Escape") {
      event.stopPropagation();
      event.preventDefault();
      drag = null;
    }
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
    if (!stage || busy || noPhasesReason) return;
    selected = index;
    const off = stage.turn_off?.length ? `, turn_off=${JSON.stringify(stage.turn_off)}` : "";
    // the shell prints it once the run starts: it can still refuse
    onrun($state.snapshot(stage),
          `ref.run_stage(Stage(${JSON.stringify(stage.name)}, ${JSON.stringify(stage.turn_on)}${off}))`);
  }

  /** The stage `.` would run, for the palette's label: "" when there is none. */
  export function selectedName(): string {
    return stages[selected]?.name ?? "";
  }

  /* ---- menus and popovers ---------------------------------------------- */

  type Open =
    | { kind: "plan"; at: MenuAt; anchor: HTMLElement }
    | { kind: "stage"; index: number; at: MenuAt; anchor: HTMLElement | null };
  let menu = $state<Open | null>(null);

  function below(el: HTMLElement, alignRight = false): MenuAt {
    const r = el.getBoundingClientRect();
    return alignRight ? { x: r.right, y: r.bottom + 4, align: "right" } : { x: r.left, y: r.bottom + 4 };
  }

  function toggleMenu(next: Open) {
    menu = menu && menu.anchor && menu.anchor === next.anchor ? null : next;
  }

  function stageMenu(event: MouseEvent, index: number) {
    if ((event.target as HTMLElement).closest("input")) return;
    event.preventDefault();
    selected = index;
    const at = event.clientX || event.clientY ? { x: event.clientX, y: event.clientY }
      : below(event.currentTarget as HTMLElement);
    menu = { kind: "stage", index, at, anchor: null };
  }

  const runWhy = $derived(busy ? "A run is in flight" : noPhasesReason ?? "");

  const menuItems = $derived.by<MenuEntry[]>(() => {
    const m = menu;
    if (!m) return [];
    if (m.kind === "plan") {
      const fits = (p: any) => !p.modes || p.modes.includes(mode);
      return [
        ...presets.map((p) => ({
          id: `preset:${p.name}`, label: p.title, radio: true,
          checked: !edited && preset === p.name, disabled: busy,
          title: fits(p) ? p.description : `Not for ${mode}: ${p.description}`,
        })),
        "-",
        { id: "revert", label: "Revert to the saved plan", disabled: !edited || busy },
        { id: "settings", label: "Plan settings…", disabled: busy },
      ];
    }
    return [
      { id: "run", label: "Run this stage", disabled: !!runWhy,
        title: runWhy || "Run this stage as it stands here, from where the model stands" },
      { id: "settings", label: "Stage settings…", disabled: busy },
      "-",
      { id: "delete", label: "Delete stage", disabled: busy || stages.length <= 1,
        title: stages.length <= 1 ? "A plan needs at least one stage" : undefined },
    ];
  });

  function chooseMenu(id: string) {
    const m = menu;
    if (!m) return;
    menu = null;
    if (m.kind === "plan") {
      if (id.startsWith("preset:")) void pick(id.slice("preset:".length));
      else if (id === "revert") revert();
      else if (id === "settings") openSettings(null, m.at);
      return;
    }
    if (id === "run") runStage(m.index);
    else if (id === "settings") openSettings(m.index, m.at);
    else if (id === "delete") removeStage(m.index);
  }

  /** The stage's settings, or the plan's (`index` null), in a small form. */
  let settings = $state<{ index: number | null; at: MenuAt;
                          values: Record<string, string | number | null>;
                          error: string } | null>(null);
  let settingsEl: HTMLFormElement | undefined = $state();

  function openSettings(index: number | null, at: MenuAt) {
    const values: Record<string, string> = {};
    if (index === null) values.correlation_guard = String(guard);
    else for (const key of FIELDS) values[key] = stages[index][key] == null ? "" : String(stages[index][key]);
    settings = { index, at: { x: at.x, y: at.y }, values, error: "" };
    void tick().then(() => settingsEl?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true }));
  }

  /** A box's text: `bind:value` on a number input holds a number once typed
   *  into, and `null` once emptied, where the form opened on strings. */
  function boxText(value: string | number | null | undefined): string {
    return value == null ? "" : String(value).trim();
  }

  function submitSettings(event: SubmitEvent) {
    event.preventDefault();
    const s = settings;
    if (!s) return;
    if (s.index === null) {
      const raw = boxText(s.values.correlation_guard);
      const value = Number(raw);
      if (raw === "" || !Number.isFinite(value) || value < 0 || value > 1) {
        s.error = "The correlation guard is a number from 0 to 1.";
        return;
      }
      if (value !== guard) {
        remember();
        guard = value;
      }
      settings = null;
      return;
    }
    const next: Record<string, unknown> = {};
    for (const key of FIELDS) {
      const raw = boxText(s.values[key]);
      if (raw === "") {
        if (!STAGE_NULLABLE_WORDS.includes(key)) {
          s.error = `${titleOf(key)} needs a value.`;
          return;
        }
        next[key] = null;
        continue;
      }
      const value = Number(raw);
      if (!Number.isFinite(value) || (STAGE_INT_WORDS.includes(key) && !Number.isInteger(value))) {
        s.error = `${titleOf(key)} is not a number.`;
        return;
      }
      if (key === "max_iter" && value < 1) {
        s.error = `${titleOf(key)} is at least 1.`;
        return;
      }
      next[key] = value;
    }
    const stage = stages[s.index];
    if (FIELDS.some((key) => (stage[key] ?? null) !== next[key])) {
      remember();
      stages[s.index] = { ...stage, ...next };
    }
    settings = null;
  }

  function titleOf(key: string): string {
    return helpEntry(corpus, `stage_fields:${key}`)?.title ?? key;
  }

  /** The `+ Add` picker: one stage, one side, a search. */
  let picker = $state<{ index: number; side: "free" | "fix"; query: string;
                        left: number; top: number } | null>(null);
  let pickerEl: HTMLDivElement | undefined = $state();

  async function openPicker(event: MouseEvent, index: number) {
    if (picker?.index === index) {
      picker = null;
      return;
    }
    const r = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const roomBelow = window.innerHeight - r.bottom > 400;
    picker = { index, side: "free", query: "",
               left: Math.max(8, Math.min(r.left, window.innerWidth - 330)),
               top: roomBelow ? r.bottom + 6 : Math.max(8, r.top - 396) };
    selected = index;
    await tick();
    pickerEl?.querySelector<HTMLInputElement>("input")?.focus({ preventScroll: true });
  }

  /** Every option for the picker's stage and side, before the search: kept
   *  apart so a keystroke filters them rather than matching every glob again. */
  const unfiltered = $derived.by(() => {
    const index = picker?.index;
    const side = picker?.side;
    if (index === undefined || !side) return null;
    const pool = side === "fix" ? freeBy(stages, index) : null;
    return pickOptions(rows, corpus, phaseNames, pool);
  });

  const options = $derived.by(() => {
    const p = picker;
    const all = unfiltered;
    if (!p || !all) return { typed: [] as PickOption[], groups: [] as PickOption[], parameters: [] as PickOption[] };
    const groups = all.groups.filter((o) => matchesQuery(o, p.query));
    const parameters = all.parameters.filter((o) => matchesQuery(o, p.query));
    // a typed dot-path glob is offered as itself, so a glob no group names can
    // still be added, as the old panel's typed field allowed (WP-2208)
    const q = p.query.trim();
    const typed = /^[\w*?.]+$/.test(q) && /[.*]/.test(q)
      && ![...groups, ...parameters].some((o) => o.glob === q)
      ? [{ glob: q, name: q, detail: "", count: 0 }] : [];
    return { typed, groups, parameters };
  });

  /** Enter in the search box takes the first option that can be chosen. */
  function pickFirst(event: KeyboardEvent) {
    if (event.key !== "Enter") return;
    event.preventDefault();
    const first = [...options.typed, ...options.groups, ...options.parameters]
      .find((o) => !noteFor(o).here);
    if (first) choose(first);
  }

  function noteFor(option: PickOption): { here: boolean; note: string } {
    const p = picker!;
    const globs = p.side === "free" ? stages[p.index].turn_on : (stages[p.index].turn_off ?? []);
    if (globs.includes(option.glob)) return { here: true, note: "in this stage" };
    if (p.side === "fix") return { here: false, note: "" };
    const elsewhere = namedIn(stages, option.glob, "free", p.index);
    return { here: false, note: elsewhere.length ? `moves from stage ${elsewhere.join(", ")}` : "" };
  }

  function choose(option: PickOption) {
    const p = picker;
    if (!p) return;
    remember();
    stages = withGlob($state.snapshot(stages) as Stage[], p.index, option.glob, p.side);
  }

  function floatKey(event: KeyboardEvent) {
    if (event.key !== "Escape" || !(picker || settings)) return;
    event.stopPropagation();
    event.preventDefault();
    picker = null;
    settings = null;
  }

  function away(event: PointerEvent) {
    const target = event.target as Node | null;
    if (picker && target && !pickerEl?.contains(target)
        && !(target as HTMLElement).closest?.(`[data-add="${picker.index}"]`)) picker = null;
    if (settings && target && !settingsEl?.contains(target)) settings = null;
  }

  function chipWords(glob: string): string | null {
    return globName(glob, corpus, phaseNames);
  }
</script>

<svelte:window onkeydowncapture={(e) => { dragKey(e); floatKey(e); }}
  onpointerdowncapture={away} onresize={() => { picker = null; settings = null; }} />

{#snippet grip()}
  <svg viewBox="0 0 12 12" aria-hidden="true"><path d="M2 3.5h8M2 6h8M2 8.5h8" /></svg>
{/snippet}
{#snippet dots()}
  <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="3.5" cy="8" r="1" /><circle cx="8" cy="8" r="1" /><circle cx="12.5" cy="8" r="1" /></svg>
{/snippet}
{#snippet trash()}
  <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.6 8.5h5.8l.6-8.5" /></svg>
{/snippet}
{#snippet cross()}
  <svg viewBox="0 0 10 10" aria-hidden="true"><path d="M2.5 2.5l5 5M7.5 2.5l-5 5" /></svg>
{/snippet}
{#snippet rwp(value: number | null)}
  <span class="rwp">{#if value !== null}<span class="muted">{"Rwp "}</span>{/if}<span class="num">{value === null ? "" : pct(value)}</span></span>
{/snippet}
{#snippet chev(on: boolean)}
  <svg class="chev" class:on viewBox="0 0 12 12" aria-hidden="true"><path d="M4.5 3l3 3-3 3" /></svg>
{/snippet}

{#snippet chips(index: number, side: "free" | "fix", globs: readonly string[], fixes: readonly string[] | null)}
  {#each globs as glob (glob)}
    {@const words = chipWords(glob)}
    {@const idle = side === "fix" && fixes !== null && !fixes.length}
    <span class="pt" class:mono={!words} class:idle title={idle
      ? `${glob}: nothing it reaches is free at this point in the plan` : glob}>
      {words ?? glob}<button class="x" disabled={busy}
        aria-label="Remove {words ?? glob} from stage {index + 1}"
        title="Remove from this stage" onclick={() => removeGlob(index, side, glob)}>{@render cross()}</button>
    </span>
  {/each}
{/snippet}

<!-- svelte-ignore a11y_no_noninteractive_element_interactions -->
<section class="plan" onkeydown={keydown} aria-label="plan">
  <header>
    <button class="mbtn name" aria-haspopup="menu" aria-expanded={menu?.kind === "plan"}
      title={chosen && !edited ? chosen.description : "Choose a plan"}
      onclick={(e) => toggleMenu({ kind: "plan", at: below(e.currentTarget), anchor: e.currentTarget })}>
      {planName}<span class="edot" title="Edited since it was applied"
        style:visibility={edited ? "visible" : "hidden"}></span>
      <svg class="caret" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5l3 3 3-3" /></svg>
    </button>
    <span class="sp"></span>
    <button class="ib words" disabled={busy} title="Add a stage at the end" onclick={addStage}>+ Stage</button>
  </header>

  {#if error}<p class="bad">{error}</p>{/if}

  <div class="scroller">
    <div class="stages" bind:this={list}>
      {#each stages as stage, index (index)}
        {@const step = index < prefix ? resolved.stages[index] : null}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <div class="stg" data-stage={index} class:lift={drag?.from === index}
          class:slide={!!drag && drag.from !== index} class:selected={selected === index}
          style:transform={shift(index)} oncontextmenu={(e) => stageMenu(e, index)}>
          <div class="stg1">
            <span class="grip" role="button" tabindex={busy ? -1 : 0} data-handle={index}
              aria-label="Move stage {index + 1}" aria-disabled={busy}
              title="Drag to reorder, or press ↑ and ↓"
              onpointerdown={(event) => grab(event, index)} onpointermove={drift}
              onpointerup={drop} onpointercancel={() => (drag = null)}
              onkeydown={(event) => nudge(event, index)}>{@render grip()}</span>
            <span class="badge">{index + 1}</span>
            <input class="sn" value={stage.name} disabled={busy} aria-label="Name of stage {index + 1}"
              oninput={(event) => rename(index, (event.currentTarget as HTMLInputElement).value)}
              onfocus={() => (selected = index)} onblur={() => (typing = "")} />
            {#if step}
              <button class="facts" aria-expanded={open.has(index)}
                title={open.has(index) ? "Hide what this stage frees" : "Show what this stage frees"}
                onclick={() => toggleOpen(index)}>
                <span class="muted">{step.n_free} free</span>
                {@render rwp(step.rwp)}
                {@render chev(open.has(index))}
              </button>
            {:else}
              <span class="facts muted" title="Apply the plan to see what this stage frees">not applied</span>
            {/if}
            <button class="ib" aria-label="Stage {index + 1} actions" aria-haspopup="menu"
              aria-expanded={menu?.kind === "stage" && menu.index === index}
              title="Run this stage, its settings"
              onclick={(e) => { selected = index; toggleMenu({ kind: "stage", index,
                at: below(e.currentTarget, true), anchor: e.currentTarget }); }}>{@render dots()}</button>
            <button class="ib" disabled={busy || stages.length <= 1}
              aria-label="Delete stage {index + 1}"
              title={stages.length <= 1 ? "A plan needs at least one stage" : "Delete this stage"}
              onclick={() => removeStage(index)}>{@render trash()}</button>
          </div>
          <div class="stg2">
            <span class="verb"><Help for="stage_fields:turn_on">Free</Help></span>
            {@render chips(index, "free", stage.turn_on, null)}
            <button class="ib words" data-add={index} disabled={busy} aria-haspopup="dialog"
              aria-expanded={picker?.index === index} title="Free or fix more at this stage"
              onclick={(e) => openPicker(e, index)}>+ Add</button>
          </div>
          {#if stage.turn_off?.length}
            <div class="stg2">
              <span class="verb"><Help for="stage_fields:turn_off">Fix</Help></span>
              {@render chips(index, "fix", stage.turn_off, step ? step.fixes ?? [] : null)}
            </div>
          {/if}
          {#if step && open.has(index)}
            <div class="lists">
              {#if step.frees.length}
                <p class="muted">Freed here</p>
                <ul class="mono">{#each step.frees as path (path)}<li>{path}</li>{/each}</ul>
              {/if}
              {#if step.fixes?.length}
                <p class="muted">Fixed here</p>
                <ul class="mono">{#each step.fixes as path (path)}<li>{path}</li>{/each}</ul>
              {/if}
              {#if step.already.length}
                <p class="muted">Already free</p>
                <ul class="mono">{#each step.already as path (path)}<li>{path}</li>{/each}</ul>
              {/if}
              {#if step.held.length}
                <p class="muted">Matched and held</p>
                <ul class="mono">
                  {#each step.held as row (row.path)}<li><Help text={row.held_because}>{row.path}</Help></li>{/each}
                </ul>
              {/if}
              {#if !step.n_matched}<p class="muted">No parameter matches.</p>{/if}
            </div>
          {/if}
        </div>
      {/each}
    </div>

    {#if closing}
      <!-- the stage every plan ends with (WP-2002): not editable, and its Rwp
           is the answer's, which the last declared stage's is not -->
      <div class="stg out">
        <div class="stg1">
          <span class="gripslot"></span>
          <span class="badge none">✓</span>
          <b class="title">{closing.name}</b>
          <span class="facts" title="Every stage's frees once more, at windows that drop {pct(closing.window_area_tol)} of each peak">
            {@render rwp(current ? closing.rwp : null)}
          </span>
        </div>
        <div class="stg2">
          <span class="verb">Free</span><span class="muted">Everything above{#if closing.fixes?.length}, keeping {closing.fixes.length} fixed{/if}</span>
        </div>
      </div>
    {/if}

    <div class="stg out">
      <div class="stg1">
        <span class="gripslot"></span>
        <span class="badge none">–</span>
        <b class="title">Never freed</b>
      </div>
      <div class="stg2">
        <span class="verb"></span>
        {#if !current}
          <span class="muted">not applied</span>
        {:else if !neverChips.length}
          <span class="muted">Nothing</span>
        {:else}
          <span class="bag">
            {#each neverChips as chip (chip.words)}
              <span class="pt still" class:mono={chip.mono} title={chip.paths.join("\n")}>{chip.words}</span>
            {/each}
          </span>
        {/if}
      </div>
    </div>

    {#if setAside.length}
      <div class="aside">
        <button class="facts" aria-expanded={asideOpen} onclick={() => (asideOpen = !asideOpen)}
          title="The staged plan starts from a table where nothing is free, so it holds these. Run this stage keeps them free.">
          {@render chev(asideOpen)}
          <span class="muted">{current ? `${setAside.length} you freed by hand, held by the plan` : "Freed by hand: not applied"}</span>
        </button>
        {#if asideOpen && current}
          <ul class="mono">{#each setAside as path (path)}<li>{path}</li>{/each}</ul>
        {/if}
      </div>
    {/if}
  </div>
</section>

{#if menu}
  <Menu at={menu.at} label={menu.kind === "plan" ? "Plan" : "Stage"} anchor={menu.anchor}
    items={menuItems} onchoose={chooseMenu} onclose={() => (menu = null)} />
{/if}

{#if picker}
  {@const p = picker}
  <div class="float pick" role="dialog" aria-label="Add to stage {p.index + 1}" bind:this={pickerEl}
    style="left: {p.left}px; top: {p.top}px">
    <div class="segmented" role="radiogroup" aria-label="Free or fix">
      <button role="radio" aria-checked={p.side === "free"} class:on={p.side === "free"}
        onclick={() => (picker && (picker.side = "free"))}>Free</button>
      <button role="radio" aria-checked={p.side === "fix"} class:on={p.side === "fix"}
        onclick={() => (picker && (picker.side = "fix"))}>Fix</button>
    </div>
    <input class="q" placeholder="Search, for example biso or cell" aria-label="Search parameters"
      bind:value={picker.query} onkeydown={pickFirst} />
    <div class="opts">
      {#each options.typed as option (option.glob)}
        {@const n = noteFor(option)}
        <p class="og">Glob</p>
        <button class="op" disabled={n.here} title={option.glob} onclick={() => choose(option)}>
          <span class="mono">{option.glob}</span><span class="w">{n.note}</span>
        </button>
      {/each}
      {#if options.groups.length}
        <p class="og">Groups</p>
        {#each options.groups as option (option.glob)}
          {@const n = noteFor(option)}
          <button class="op" disabled={n.here} title={option.glob} onclick={() => choose(option)}>
            <span>{option.name} ({option.count})</span><span class="w">{n.note}</span>
          </button>
        {/each}
      {/if}
      {#if options.parameters.length}
        <p class="og">Parameters</p>
        {#each options.parameters as option (option.glob)}
          {@const n = noteFor(option)}
          <button class="op" disabled={n.here} title={option.glob} onclick={() => choose(option)}>
            <span>{option.name} <span class="mono muted">{option.detail}</span></span><span class="w">{n.note}</span>
          </button>
        {/each}
      {/if}
      {#if !options.typed.length && !options.groups.length && !options.parameters.length}
        <p class="og">{p.side === "fix" && !p.query.trim() ? "Nothing is free yet at this stage." : "Nothing matches."}</p>
      {/if}
    </div>
  </div>
{/if}

{#if settings}
  {@const s = settings}
  <form class="float settings" aria-label={s.index === null ? "Plan settings" : `Stage ${s.index + 1} settings`}
    bind:this={settingsEl} style="left: {Math.min(s.at.x, window.innerWidth - 320)}px; top: {s.at.y}px"
    onsubmit={submitSettings}>
    <div class="grid">
      {#if s.index === null}
        <label for="plan-guard">Correlation guard</label>
        <input id="plan-guard" class="mono" type="number" step="0.01" min="0" max="1"
          bind:value={settings.values.correlation_guard} />
      {:else}
        {#each FIELDS as key (key)}
          <label for="stage-{key}"><Help for="stage_fields:{key}">{titleOf(key)}</Help></label>
          <input id="stage-{key}" class="mono" type="number" step={STAGE_INT_WORDS.includes(key) ? 1 : "any"}
            min={key === "max_iter" ? 1 : undefined} placeholder={STAGE_NULLABLE_WORDS.includes(key) ? "default" : undefined}
            bind:value={settings.values[key]} />
        {/each}
      {/if}
    </div>
    {#if s.error}<p class="bad">{s.error}</p>{/if}
    <div class="foot">
      <button type="button" class="ghost" onclick={() => (settings = null)}>Cancel</button>
      <button type="submit">Done</button>
    </div>
  </form>
{/if}

<style>
  .plan {
    display: flex;
    flex-direction: column;
    min-height: 0;
    flex: 1 1 auto;
  }

  header {
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px 6px;
  }

  .sp {
    flex: 1 1 auto;
  }

  .mbtn.name {
    font-weight: 600;
  }

  .edot {
    width: 6px;
    height: 6px;
    border-radius: 3px;
    background: var(--accent-ink);
  }

  .caret,
  .chev {
    width: 10px;
    height: 10px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
    color: var(--muted);
    flex: none;
  }

  .chev.on {
    transform: rotate(90deg);
  }

  .ib.words {
    padding: 0 8px;
    font-size: var(--text);
  }

  .bad {
    color: var(--bad);
    margin: 2px 12px;
  }

  .scroller {
    flex: 1 1 auto;
    overflow: auto;
    min-height: 0;
    padding-bottom: 12px;
  }

  .stg {
    padding: 10px 12px;
    border-top: 1px solid var(--line);
    background: var(--panel);
  }

  .stg.slide {
    transition: transform 120ms ease;
  }

  .stg.lift {
    position: relative;
    z-index: 2;
    box-shadow: 0 6px 18px color-mix(in srgb, var(--fg) 16%, transparent);
  }

  .stg1 {
    display: flex;
    align-items: center;
    gap: 8px;
    min-height: 28px;
  }

  .grip,
  .gripslot {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 24px;
    flex: none;
    color: var(--muted);
    cursor: grab;
    touch-action: none;
  }

  .gripslot {
    cursor: default;
  }

  .grip svg {
    width: 12px;
    height: 12px;
    stroke: currentColor;
    stroke-width: 1.4;
    stroke-linecap: round;
  }

  .grip[aria-disabled="true"] {
    cursor: default;
    opacity: 0.45;
  }

  .badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    flex: none;
    box-sizing: border-box;
    border: 1px solid var(--accent-ink);
    border-radius: 4px;
    font-family: var(--mono-family);
    font-size: var(--text-xs);
    color: var(--accent-ink);
  }

  .badge.none {
    border-color: var(--line-strong);
    border-style: dashed;
    color: var(--muted);
  }

  .sn {
    flex: 1 1 auto;
    min-width: 0;
    height: 28px;
    box-sizing: border-box;
    margin-left: -7px;
    padding: 0 6px;
    border: 1px solid transparent;
    border-radius: 6px;
    background: none;
    color: var(--fg);
    font: inherit;
    font-weight: 600;
  }

  @media (hover: hover) {
    .sn:hover:not(:disabled) {
      border-color: var(--line-strong);
    }
  }

  .sn:focus {
    border-color: var(--accent);
    background: var(--bg);
    outline: none;
  }

  .title {
    flex: 1 1 auto;
    font-weight: 600;
  }

  .facts {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 0 4px;
    height: 24px;
    border: 0;
    background: none;
    color: var(--fg);
    font-size: var(--text-sm);
    white-space: nowrap;
  }

  button.facts {
    cursor: pointer;
  }

  .facts .rwp {
    display: inline-flex;
    gap: 4px;
  }

  .facts .num {
    font-family: var(--mono-family);
    min-width: 7ch;
    text-align: right;
  }

  .stg2 {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: 6px;
    margin: 6px 0 0 26px;
    font-size: var(--text-sm);
  }

  .verb {
    width: 3.2em;
    color: var(--muted);
  }

  .pt {
    display: inline-flex;
    align-items: center;
    gap: 2px;
    height: 24px;
    padding: 0 2px 0 8px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--fg) 7%, var(--panel));
    color: var(--fg);
  }

  /* Never freed's chips wrap under each other, never under the verb column */
  .bag {
    display: flex;
    flex: 1 1 0;
    flex-wrap: wrap;
    gap: 6px;
    min-width: 0;
  }

  /* a read-only chip (Never freed): no × to make room for */
  .pt.still {
    padding: 0 8px;
  }

  .pt.mono {
    font-family: var(--mono-family);
  }

  .pt.idle {
    color: var(--muted);
    text-decoration: line-through;
    text-decoration-color: var(--muted);
  }

  .pt .x {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 20px;
    height: 20px;
    padding: 0;
    border: 0;
    border-radius: 10px;
    background: none;
    color: var(--muted);
    cursor: pointer;
  }

  .pt .x svg {
    width: 10px;
    height: 10px;
    stroke: currentColor;
    stroke-width: 1.4;
    stroke-linecap: round;
  }

  @media (hover: hover) {
    .pt .x:hover:not(:disabled) {
      background: var(--line-strong);
      color: var(--fg);
    }
  }

  .lists {
    margin: 8px 0 0 26px;
    font-size: var(--text-sm);
  }

  .lists p {
    margin: 6px 0 2px;
  }

  ul {
    margin: 0;
    padding: 0 0 0 12px;
    list-style: none;
    font-size: var(--text-sm);
  }

  .mono {
    font-family: var(--mono-family);
  }

  .stg.out .stg2 {
    color: var(--muted);
  }

  .aside {
    padding: 8px 12px;
    border-top: 1px solid var(--line);
  }

  .float {
    position: fixed;
    z-index: 20;
    box-sizing: border-box;
    padding: 10px 12px;
    background: var(--panel);
    border: 1px solid var(--line);
    border-radius: 8px;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.18);
  }

  .pick {
    width: 320px;
    max-height: 380px;
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .pick .segmented {
    flex: none;
    align-self: flex-start;
  }

  .q {
    flex: none;
    height: 30px;
    box-sizing: border-box;
    padding: 0 8px;
    border: 1px solid var(--line-strong);
    border-radius: 6px;
    background: var(--bg);
    color: var(--fg);
    font: inherit;
  }

  .opts {
    overflow-y: auto;
    min-height: 0;
  }

  .og {
    margin: 0;
    padding: 6px 2px 2px;
    font-size: var(--text-sm);
    color: var(--muted);
  }

  button.op {
    display: flex;
    align-items: center;
    gap: 8px;
    width: 100%;
    height: auto;
    min-height: 28px;
    padding: 0 6px;
    border: 0;
    border-radius: 6px;
    background: none;
    color: var(--fg);
    font-size: var(--text-sm);
    font-weight: 400;
    text-align: left;
    cursor: pointer;
  }

  button.op:disabled {
    color: var(--muted);
    cursor: default;
  }

  @media (hover: hover) {
    button.op:hover:not(:disabled) {
      background: var(--hover);
    }
  }

  .op .w {
    margin-left: auto;
    font-size: var(--text-sm);
    color: var(--muted);
    white-space: nowrap;
  }

  .settings {
    width: 320px;
    display: flex;
    flex-direction: column;
    gap: 10px;
  }

  .grid {
    display: grid;
    grid-template-columns: 1fr 96px;
    gap: 6px 10px;
    align-items: center;
    font-size: var(--text-sm);
  }

  .grid input {
    width: 100%;
    height: 26px;
    box-sizing: border-box;
    padding: 0 6px;
    border: 1px solid var(--line-strong);
    border-radius: 6px;
    background: var(--bg);
    color: var(--fg);
  }

  .foot {
    display: flex;
    justify-content: flex-end;
    gap: 8px;
  }
</style>
