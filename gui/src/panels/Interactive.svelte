<script lang="ts">
  /**
   * The Interactive tab (WP-2128): the model moved by hand.
   *
   * The maintainer's rulings of 2026-11-07: sliders are visual fitting without
   * refinement, against data and model; the tab is a mode beside Parameters,
   * and the two never show at once; some tracks are non-linear, with a range
   * and scale pop-up opened from the parameter's name; the unit lives in that
   * pop-up only; a number never changes format while it is dragged, and a click
   * on it lets the person type a value. WP-2128 § Context restates each.
   *
   * The values are pending edits, held here until the action bar's Apply sends
   * them through `PATCH /api/params`. Every change asks `POST /api/preview` for
   * the pattern at the edited values through one `PreviewQueue`, which keeps one
   * request in flight and sends the newest values when it lands, so a drag
   * throttles itself to the route's latency. The answer goes to the shell,
   * which hands it to the graphs. Nothing here draws a curve.
   *
   * Like the Parameters panel, the edits survive a head move: the rows reload,
   * each range nobody set is rebuilt at the new values, and an edit equal to
   * the new value is no longer an edit.
   */
  import { untrack } from "svelte";
  import type { Curves } from "rxplot";

  import { ApiError, api } from "../api";
  import type { HelpCorpus } from "../lib/help";
  import {
    STEPS,
    PreviewQueue,
    buildSliders,
    defaults,
    editText,
    fixFormat,
    formatParts,
    maxDecimals,
    parseTyped,
    posFrac,
    valueAt,
    type PreviewAnswer,
    type RangeContext,
    type Slider,
    type Track,
  } from "../lib/interactive";
  import type { InteractiveDraft } from "../lib/recovery";
  import { normalize, type ParamRow } from "../lib/table";

  let {
    head = null,
    busy = false,
    corpus = null,
    context,
    phaseNames = [],
    say = () => {},
    onpending = () => {},
    onpreview = () => {},
  }: {
    head?: string | null;
    busy?: boolean;
    corpus?: HelpCorpus | null;
    /** the last fit's widest window peak and highest angle, the ranges' unit */
    context: RangeContext;
    phaseNames?: readonly string[];
    say?: (line: string) => void;
    /** how many slider values are pending */
    onpending?: (n: number) => void;
    /** the preview to draw, or null when nothing is pending; `error` is a refusal */
    onpreview?: (answer: PreviewAnswer | null, error: string) => void;
  } = $props();

  let rows = $state<ParamRow[]>([]);
  let sliders = $state<Slider[]>([]);
  let edits = $state(new Map<string, number>());
  let error = $state("");
  /** the slider whose range pop-up is open, and where it is anchored */
  let popFor = $state<string | null>(null);
  let popAt = $state<{ left: number; top: number } | null>(null);
  /** the slider whose number is being typed, and the text so far */
  let typing = $state<string | null>(null);
  let typed = $state("");

  const decimals = $derived(maxDecimals(sliders));
  const groups = $derived.by(() => {
    const out: { title: string; items: Slider[] }[] = [];
    for (const s of sliders) {
      const last = out[out.length - 1];
      if (last && last.title === s.group) last.items.push(s);
      else out.push({ title: s.group, items: [s] });
    }
    return out;
  });
  const popSlider = $derived(sliders.find((s) => s.path === popFor) ?? null);

  async function load() {
    try {
      rows = normalize((await api.params()).parameters);
      error = "";
    } catch (exc) {
      rows = [];
      error = exc instanceof ApiError && exc.empty ? "" : (exc as Error).message;
    }
  }

  // reload on a head move: the rows are the last fit's values, the track marks
  // and the ranges are built from them
  $effect(() => {
    void head;
    load();
  });

  // the sliders follow the rows and the curves the ranges are measured on; a
  // range the person set is kept (`prior`)
  $effect(() => {
    const r = rows, ctx = context, names = phaseNames, c = corpus;
    untrack(() => {
      const prior = new Map(sliders.map((s) => [s.path, s]));
      sliders = buildSliders(r, c, ctx, names, prior);
      const next = new Map(edits);
      for (const [path, v] of edits) {
        const row = r.find((x) => x.path === path);
        if (!row || !row.refinable || row.value === v) next.delete(path);
      }
      if (next.size !== edits.size) edits = next;
      if (edits.size) ask();
    });
  });

  $effect(() => {
    onpending(edits.size);
  });

  // the chart module is a chunk off the boot path (gui/CLAUDE.md), so its
  // reader is fetched with the first answer rather than imported here
  const queue = new PreviewQueue<Curves>(
    async (values) => {
      const [buffer, chart] = await Promise.all([api.preview(values), import("rxplot")]);
      return chart.unpack(buffer);
    },
    (curves, _values, sentAt) => {
      error = "";
      onpreview({ curves, sentAt }, "");
    },
    (exc) => {
      error = (exc as Error).message;
      onpreview(null, error);
    },
  );

  /** Ask for the pattern at the pending values, or take the preview down. */
  function ask() {
    if (!edits.size) {
      queue.clear();
      onpreview(null, "");
      return;
    }
    queue.push(Object.fromEntries(edits));
  }

  function current(s: Slider): number {
    return edits.get(s.path) ?? s.ref;
  }

  function set(s: Slider, v: number) {
    const next = new Map(edits);
    if (v === s.ref) next.delete(s.path);
    else next.set(s.path, v);
    edits = next;
    ask();
  }

  function dragged(s: Slider, event: Event) {
    const f = Number((event.currentTarget as HTMLInputElement).value) / STEPS;
    set(s, valueAt(s, f));
  }

  function startTyping(s: Slider) {
    typing = s.path;
    typed = editText(current(s));
  }

  const typedCheck = $derived.by(() => {
    const s = sliders.find((x) => x.path === typing);
    return s ? parseTyped(s, typed) : null;
  });

  function typeKey(s: Slider, event: KeyboardEvent) {
    if (event.key === "Escape") {
      typing = null;
      event.stopPropagation();
    } else if (event.key === "Enter" && typedCheck && "value" in typedCheck) {
      set(s, typedCheck.value);
      typing = null;
    }
  }

  function focusInput(node: HTMLInputElement) {
    node.focus();
    node.select();
  }

  // -- the range-and-scale pop-up -----------------------------------------
  let rangeLo = $state("");
  let rangeHi = $state("");

  function openPop(s: Slider, event: MouseEvent) {
    if (popFor === s.path) return closePop();
    const box = (event.currentTarget as HTMLElement).getBoundingClientRect();
    const below = window.innerHeight - box.bottom > 260;
    popAt = { left: Math.max(8, Math.min(box.left, window.innerWidth - 300)),
              top: below ? box.bottom + 6 : Math.max(8, box.top - 250) };
    popFor = s.path;
    rangeLo = editText(s.lo);
    rangeHi = editText(s.hi);
  }

  function closePop() {
    popFor = null;
    popAt = null;
  }

  function replace(s: Slider, patch: Partial<Slider>) {
    sliders = sliders.map((x) => {
      if (x.path !== s.path) return x;
      const y = { ...x, ...patch };
      return { ...y, ...fixFormat(y.lo, y.hi, y.ref) };
    });
  }

  const rangeWhy = $derived.by(() => {
    const lo = Number(rangeLo), hi = Number(rangeHi);
    if (!Number.isFinite(lo) || !Number.isFinite(hi)) return "not a number";
    if (!(hi > lo)) return "the end must be above the start";
    // a range past the row's bounds would let a drag reach a value the
    // preview and Apply both refuse, as a typed one is refused here
    const s = popSlider;
    if (s && lo < s.bound[0]) return `below the lower bound ${s.bound[0]}`;
    if (s && hi > s.bound[1]) return `above the upper bound ${s.bound[1]}`;
    return "";
  });

  function setRange(s: Slider) {
    if (rangeWhy) return;
    const lo = Number(rangeLo), hi = Number(rangeHi);
    if (lo === s.lo && hi === s.hi) return;
    replace(s, { lo, hi, custom: true, track: s.track === "log" && !(lo > 0) ? "lin" : s.track });
  }

  function setTrack(s: Slider, track: Track) {
    if (track === "log" && !(s.lo > 0)) return;
    replace(s, { track, custom: true });
  }

  function restoreDefault(s: Slider) {
    const d = defaults(s.kind, s.ref, s.bound, context);
    replace(s, { ...d, custom: false });
    rangeLo = editText(d.lo);
    rangeHi = editText(d.hi);
  }

  function clickAway(event: MouseEvent) {
    const t = event.target as HTMLElement;
    if (popFor && !t.closest(".rangepop") && !t.closest("[data-pop]")) closePop();
  }

  function keydown(event: KeyboardEvent) {
    if (event.key === "Escape" && popFor) closePop();
  }

  // -- the action bar's verbs ---------------------------------------------
  /** Apply the slider values; true when there were none or they all landed. */
  export async function apply(): Promise<boolean> {
    if (!edits.size) return true;
    const values = Object.fromEntries(edits);
    say(`ref.set_values(${JSON.stringify(values)})`);
    try {
      await api.patchParams({ values });
    } catch (exc) {
      error = exc instanceof ApiError && exc.busy
        ? "a run is in flight — the values wait until it ends"
        : (exc as Error).message;
      return false;
    }
    edits = new Map();
    error = "";
    ask();
    return true;
  }

  /** The slider values, for the recovery copy (WP-2209), or `null`. */
  export function draft(): InteractiveDraft | null {
    return edits.size ? { values: Object.fromEntries(edits) } : null;
  }

  /** Put recovered slider values back as pending values. */
  export function restoreDraft(d: InteractiveDraft) {
    edits = new Map(Object.entries(d.values ?? {}));
    error = "";
    ask();
  }

  /** Drop every slider value: the graphs go back to the last fit. */
  export function revert() {
    edits = new Map();
    error = "";
    ask();
  }

  const CARET = "▾";
</script>

<svelte:window onclick={clickAway} onkeydown={keydown} />

<div class="interactive" style:--dec={`${decimals + 1}ch`}>
  {#if error}<p class="bad err">{error}</p>{/if}
  {#if !sliders.length && !error}
    <p class="muted empty">No value here can be moved by hand.</p>
  {/if}
  {#each groups as group (group.title)}
    <h3>{group.title}</h3>
    {#each group.items as s (s.path)}
      {@const v = current(s)}
      {@const parts = formatParts(s, v)}
      <div class="slider" class:changed={edits.has(s.path)}>
        <div class="line">
          <button class="pick pname" data-pop={s.path} aria-haspopup="dialog"
            aria-expanded={popFor === s.path} title="Range and scale"
            onclick={(e) => openPop(s, e)}>{s.name} <span class="caret">{CARET}</span></button>
          <span class="value">
            {#if typing === s.path}
              <input class="typed mono" class:bad={typedCheck && "why" in typedCheck}
                title={typedCheck && "why" in typedCheck ? typedCheck.why : null}
                aria-label={s.name} bind:value={typed} use:focusInput
                onkeydown={(e) => typeKey(s, e)} onblur={() => (typing = null)} />
            {/if}
            <button class="pick num mono tabular" class:ghosted={typing === s.path}
              aria-label={`Type a value for ${s.name}`} title="Click to type a value"
              onclick={() => startTyping(s)}
              ><span class="int">{parts.int}</span><span class="frac">{parts.frac}</span
              ><span class="exp">{#if parts.exp}×10<sup>{parts.exp}</sup>{/if}</span></button>
          </span>
          <button class="pick reset" class:shown={edits.has(s.path)}
            aria-label={`Back to the last fit's ${s.name}`} title="Back to the last fit"
            disabled={!edits.has(s.path)} onclick={() => set(s, s.ref)}>↺</button>
        </div>
        <div class="track">
          <input type="range" min="0" max={STEPS} step="1" aria-label={s.name}
            value={Math.round(posFrac(s, v) * STEPS)} disabled={busy}
            oninput={(e) => dragged(s, e)} />
          <!-- the last fit's value on the track; the ↺ beside the number says it in words -->
          <span class="mark" aria-hidden="true"
            style:left={`calc(8px + (100% - 16px) * ${posFrac(s, s.ref)})`}></span>
        </div>
      </div>
    {/each}
  {/each}
</div>

{#if popSlider && popAt}
  {@const s = popSlider}
  <div class="rangepop" role="dialog" aria-label={`Range and scale for ${s.name}`}
    style:left={`${popAt.left}px`} style:top={`${popAt.top}px`}>
    <strong>{s.name}{#if s.unit}<span class="muted"> ({s.unit})</span>{/if}</strong>
    <p class="muted">Last fit <span class="mono">{editText(s.ref)}</span></p>
    <label><span>From</span>
      <input class="mono" bind:value={rangeLo} aria-label="Lowest value"
        onchange={() => setRange(s)} onkeydown={(e) => e.key === "Enter" && setRange(s)} />
      <span class="muted">{s.unit}</span></label>
    <label><span>To</span>
      <input class="mono" bind:value={rangeHi} aria-label="Highest value"
        onchange={() => setRange(s)} onkeydown={(e) => e.key === "Enter" && setRange(s)} />
      <span class="muted">{s.unit}</span></label>
    <p class="bad why">{rangeWhy}</p>
    <div class="segmented" role="group" aria-label="scale">
      <button class:on={s.track === "lin"} aria-pressed={s.track === "lin"}
        onclick={() => setTrack(s, "lin")}>Linear</button>
      <button class:on={s.track === "log"} aria-pressed={s.track === "log"}
        disabled={!(s.lo > 0)} title={s.lo > 0 ? null : "needs a range above zero"}
        onclick={() => setTrack(s, "log")}>Logarithmic</button>
    </div>
    <div class="popactions">
      <button class="ghost" disabled={!s.custom} onclick={() => restoreDefault(s)}>Default</button>
      <button class="ghost" onclick={closePop}>Done</button>
    </div>
  </div>
{/if}

<style>
  .interactive {
    flex: 1 1 auto;
    min-height: 0;
    overflow-y: auto;
    padding: var(--s2) var(--s3) var(--s3);
    font-size: var(--text-sm);
    /* the three slots every number is drawn in, shared by every slider so the
       decimal points form one column and no digit moves while dragging */
    --int: 5ch;
    --exp: 5ch;
  }
  h3 {
    margin: var(--s3) 0 var(--s1);
    font-size: var(--text-xs);
    font-weight: 600;
    color: var(--muted);
  }
  h3:first-of-type {
    margin-top: 0;
  }
  .slider {
    padding: var(--s1) 0 var(--s2);
    border-top: 1px solid var(--line);
  }
  .line {
    display: flex;
    align-items: center;
    gap: var(--s2);
    min-height: 1.8em;
  }
  .pname {
    flex: 1 1 auto;
    min-width: 0;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    cursor: pointer;
  }
  .pname:hover,
  .pname[aria-expanded="true"] {
    color: var(--accent-ink);
  }
  .caret {
    color: var(--muted);
  }
  .value {
    position: relative;
    flex: 0 0 auto;
  }
  .num {
    display: inline-flex;
    cursor: text;
    white-space: nowrap;
  }
  .num:hover {
    color: var(--accent-ink);
  }
  .changed .num {
    color: var(--accent-ink);
  }
  .num.ghosted {
    visibility: hidden;
  }
  .int {
    width: var(--int);
    text-align: right;
  }
  .frac {
    width: var(--dec);
    text-align: left;
  }
  .exp {
    width: var(--exp);
    text-align: left;
    color: var(--muted);
  }
  .exp sup {
    line-height: 0;
  }
  /* over the number it replaces, as wide as the whole number or wider, so a
     typed value is never clipped and nothing beside it moves */
  .typed {
    position: absolute;
    right: 0;
    top: 50%;
    transform: translateY(-50%);
    width: max(100%, 16ch);
    z-index: 2;
  }
  .typed.bad {
    border-color: var(--bad);
  }
  .reset {
    flex: 0 0 auto;
    width: 1.5em;
    visibility: hidden;
    color: var(--muted);
    cursor: pointer;
  }
  .reset.shown {
    visibility: visible;
  }
  .reset:hover {
    color: var(--fg);
  }
  .track {
    position: relative;
    display: flex;
    align-items: center;
    height: 1.6em;
  }
  .track input {
    width: 100%;
    margin: 0;
    accent-color: var(--accent);
  }
  .mark {
    position: absolute;
    top: 50%;
    width: 2px;
    height: 12px;
    margin: -6px 0 0 -1px;
    background: var(--muted);
    pointer-events: none;
  }
  .err,
  .empty {
    margin: 0 0 var(--s2);
  }
  .rangepop {
    position: fixed;
    z-index: 30;
    width: 280px;
    padding: var(--s3);
    border: 1px solid var(--line);
    background: var(--panel);
    box-shadow: 0 8px 28px rgb(0 0 0 / 0.16);
    font-size: var(--text-sm);
    display: flex;
    flex-direction: column;
    gap: var(--s2);
  }
  .rangepop p {
    margin: 0;
  }
  .rangepop label {
    display: grid;
    grid-template-columns: 3.5em minmax(0, 1fr) 4em;
    align-items: center;
    gap: var(--s2);
  }
  .rangepop input {
    width: 100%;
  }
  .rangepop .why {
    min-height: 1lh;
  }
  .popactions {
    display: flex;
    justify-content: space-between;
  }
</style>
