<script lang="ts">
  /**
   * The series' Trends graph at `/next` (WP-2243 task 6), shown in its graph
   * tab while the series workflow is up.
   *
   * Round 12's design, restated in WP-2243 § The design: one small panel per
   * plotted value, sharing the coordinate axis, points with esd bars and
   * never joined (calls 3, 6); the second walk as rings over the first walk's
   * dots, and each panel's largest gap between the walks in its title band
   * (call 4); a y span over the values and their bars that reaches at most
   * one value-spread past the values (call 23); a sparse value only at its
   * own points (call 22). The Plot menu lists every value, one submenu per
   * group, and stays open while ticking; × removes a panel; Against switches
   * the axis between the coordinate and the pattern number (call 21). The
   * title names the selected pattern only, with the Pattern graph's ‹ ›
   * (call 26), and a point click selects its pattern. The rules are
   * `seriestrends.ts`'s; this file draws them.
   *
   * The panels are canvases drawn by hand, as the Peak fits windows are
   * (`PeakFits.svelte`), each under a title band in the page's own type; the
   * last one carries the shared axis. The hovered pattern is read in the
   * status bar, the readout's one place (gui/CLAUDE.md § Plot).
   */
  import type { HelpCorpus } from "../lib/help";
  import { curveColors } from "../lib/plot";
  import Menu, { type MenuAt, type MenuEntry } from "./Menu.svelte";
  import type { StatusReadout } from "./readout";
  import type { SeriesAnswer } from "./seriesresults";
  import { axisWord } from "./seriesrun";
  import {
    hasCoordinates, nearestPattern, panelGap, panelsOf, plotGroups, powerOf, spanOf, ticks,
    tickText, trendOf, unitOf, unitText, xValues, type Against, type Panel, type Trend,
    type TrendsView,
  } from "./seriestrends";
  import { esdText } from "../lib/series";

  let {
    trends = null,
    running = false,
    corpus = null,
    theme = "light",
    against = $bindable<Against>("x"),
    hidden = $bindable<string[]>([]),
    onplot = () => {},
    onselect = () => {},
    onstep = () => {},
    onreadout = () => {},
  }: {
    trends?: TrendsView | null;
    running?: boolean;
    corpus?: HelpCorpus | null;
    theme?: string;
    against?: Against;
    /** the walks not drawn: "first", "second" */
    hidden?: string[];
    /** plot the paths, or remove them */
    onplot?: (paths: string[], on: boolean) => void;
    onselect?: (index: number) => void;
    onstep?: (delta: number) => void;
    onreadout?: (r: StatusReadout | null) => void;
  } = $props();

  const answer = $derived(trends?.answer ?? null);
  const plottedTrends = $derived(answer
    ? (trends!.plotted.map((p) => trendOf(answer, p, corpus)).filter(Boolean) as Trend[]) : []);
  const panels = $derived(panelsOf(plottedTrends));
  const coords = $derived(answer ? hasCoordinates(answer) : false);
  const along = $derived<Against>(coords ? against : "n");
  const xs = $derived(answer ? xValues(answer, along) : new Map<number, number>());
  const twoWalks = $derived(!!answer?.trajectories.some((t) => t.backward));
  const showFirst = $derived(!hidden.includes("first"));
  const showSecond = $derived(twoWalks && !hidden.includes("second"));
  const xLabel = $derived(along === "x" ? trends?.axis ?? "" : "Pattern");

  /** the panels' shared margins: tick labels left, a little room right */
  const LEFT = 64, RIGHT = 10, AXIS = 26, GUTTER = 112;
  /** ink per value of a panel holding several; one value takes the
   *  observed points' ink */
  const INKS = ["--plot-obs", "--plot-peak", "--phase-0", "--phase-1"];
  const inkOf = (p: Panel, j: number) => (p.trends.length > 1 ? INKS[j % INKS.length] : "--plot-obs");

  let canvases: HTMLCanvasElement[] = $state([]);
  let width = $state(0);
  let height = $state(0);
  let hover = $state<number | null>(null);

  /** each pattern's place in px, across the plot area every panel shares */
  const xPx = $derived.by(() => {
    const vals = [...xs.values()];
    const out = new Map<number, number>();
    if (!vals.length || !width) return out;
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.04 || 1;
    const w = width - LEFT - RIGHT;
    for (const [i, v] of xs) out.set(i, LEFT + ((v - (lo - pad)) / (hi - lo + 2 * pad)) * w);
    return out;
  });
  const xTicks = $derived.by(() => {
    const vals = [...xs.values()];
    if (!vals.length || !width) return [] as Array<{ px: number; text: string }>;
    const lo = Math.min(...vals), hi = Math.max(...vals);
    const pad = (hi - lo) * 0.04 || 1;
    const w = width - LEFT - RIGHT;
    const px = (v: number) => LEFT + ((v - (lo - pad)) / (hi - lo + 2 * pad)) * w;
    if (along === "n") {
      const every = Math.max(1, Math.ceil(vals.length / Math.max(1, Math.floor(w / 36))));
      return vals.filter((v) => (v - 1) % every === 0).map((v) => ({ px: px(v), text: String(v) }));
    }
    const { values, step } = ticks(lo, hi, Math.max(2, Math.floor(w / 90)));
    return values.filter((v) => v >= lo - pad && v <= hi + pad)
      .map((v) => ({ px: px(v), text: tickText(v, step, 0) }));
  });

  $effect(() => {
    void theme; void width; void height; void panels; void xPx; void hover; void hidden;
    void trends?.selected;
    // one microtask: the frame stamps the theme in an effect of the same flush
    void Promise.resolve().then(() =>
      canvases.forEach((cv, k) => cv && panels[k] && draw(cv, panels[k], k === panels.length - 1)));
  });

  function draw(cv: HTMLCanvasElement, p: Panel, last: boolean) {
    const ctx = cv.getContext?.("2d");
    if (!ctx) return;
    const W = cv.clientWidth, H = cv.clientHeight, dpr = devicePixelRatio || 1;
    if (!W || !H) return;
    cv.width = Math.round(W * dpr);
    cv.height = Math.round(H * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, W, H);
    const style = getComputedStyle(cv);
    const read = (n: string) => style.getPropertyValue(n).trim();
    const c = curveColors(read);
    const muted = read("--muted") || "#888", line = read("--line") || "#ddd";
    const accent = read("--accent") || "#c65d0a", strong = read("--line-strong") || "#ccc";
    const mono = read("--mono-family") || "monospace";
    const top = 6, bot = H - (last ? AXIS : 6);
    const span = spanOf(p.trends);
    // the selected pattern, a band across every panel, and the hovered one
    const sel = trends?.selected;
    if (sel != null && xPx.has(sel)) {
      ctx.fillStyle = accent;
      ctx.globalAlpha = 0.14;
      ctx.fillRect(xPx.get(sel)! - 5, 0, 10, bot);
      ctx.globalAlpha = 1;
    }
    if (hover != null && hover !== sel && xPx.has(hover)) {
      const X = Math.round(xPx.get(hover)!) + 0.5;
      ctx.strokeStyle = strong;
      ctx.setLineDash([3, 3]);
      ctx.beginPath();
      ctx.moveTo(X, 0);
      ctx.lineTo(X, bot);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    ctx.font = `11px ${mono}`;
    if (last) {
      ctx.fillStyle = muted;
      ctx.textAlign = "center";
      for (const t of xTicks) ctx.fillText(t.text, t.px, H - 8);
    }
    if (!span) return;
    const [lo, hi] = span;
    const py = (v: number) => bot - ((v - lo) / (hi - lo || 1)) * (bot - top);
    // at least two labelled ticks (round 12b)
    let n = bot - top > 110 ? 4 : 3, yt = ticks(lo, hi, n);
    while (yt.values.filter((v) => v >= lo && v <= hi).length < 2 && n < 12) yt = ticks(lo, hi, (n += 2));
    const power = powerOf(lo, hi);
    ctx.strokeStyle = line;
    ctx.lineWidth = 1;
    ctx.fillStyle = muted;
    ctx.textAlign = "right";
    for (const v of yt.values) {
      if (v < lo || v > hi) continue;
      const q = Math.round(py(v)) + 0.5;
      ctx.beginPath();
      ctx.moveTo(LEFT, q);
      ctx.lineTo(W - RIGHT, q);
      ctx.stroke();
      ctx.fillText(tickText(v, yt.step, power), LEFT - 6, q + 4);
    }
    ctx.save();
    ctx.beginPath();
    ctx.rect(LEFT - 6, top - 4, W - LEFT - RIGHT + 12, bot - top + 8);
    ctx.clip();
    p.trends.forEach((t, j) => {
      const ink = read(inkOf(p, j)) || c.obs;
      ctx.strokeStyle = ink;
      ctx.fillStyle = ink;
      for (const pt of t.points) {
        const X = xPx.get(pt.index);
        if (X === undefined) continue;
        if (showFirst) {
          ctx.lineWidth = 1;
          if (pt.esd) {
            ctx.beginPath();
            ctx.moveTo(X, py(pt.value - pt.esd));
            ctx.lineTo(X, py(pt.value + pt.esd));
            ctx.stroke();
          }
          ctx.beginPath();
          ctx.arc(X, py(pt.value), pt.index === sel ? 3.6 : 2.8, 0, 2 * Math.PI);
          ctx.fill();
        }
        if (showSecond && pt.back !== null) {
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(X, py(pt.back), 4.6, 0, 2 * Math.PI);
          ctx.stroke();
        }
      }
    });
    ctx.restore();
  }

  /** A panel's power of ten, for its title's unit. */
  function powerFor(p: Panel): number {
    const s = spanOf(p.trends);
    return s ? powerOf(s[0], s[1]) : 0;
  }

  /** The group a panel's title names: a phase or an atom, never the fit or
   *  the instrument, whose values name themselves. */
  const groupWord = (t: Trend) => (t.group === "#fit" || t.group === "instrument" ? "" : t.groupTitle);

  // -- the pointer ------------------------------------------------------------

  function patternAt(ev: PointerEvent): number | null {
    const r = (ev.currentTarget as HTMLElement).getBoundingClientRect();
    return nearestPattern(xPx, ev.clientX - r.left);
  }

  function move(ev: PointerEvent) {
    const i = patternAt(ev);
    if (i === hover) return;
    hover = i;
    onreadout(i === null || !answer ? null : readoutOf(i));
  }

  function leave() {
    if (hover === null) return;
    hover = null;
    onreadout(null);
  }

  function click(ev: MouseEvent) {
    const i = patternAt(ev as PointerEvent);
    if (i !== null) onselect(i);
  }

  /** The hovered pattern in the status bar: its name, coordinate and Rwp. */
  function readoutOf(i: number): StatusReadout {
    const e = answer!.entries.find((x) => x.index === i);
    const items = [
      { id: "pattern", label: "Pattern", value: e?.label ?? `#${i + 1}`, slot: 16, left: true },
      { id: "x", label: trends?.axis ?? "x", value: e?.x == null ? "—" : String(e.x), slot: 8 },
      { id: "rwp", label: "Rwp", value: e?.statistics ? `${(e.statistics.rwp * 100).toFixed(2)} %` : "—", slot: 8 },
    ];
    return { items, dropOrder: ["rwp"] };
  }

  // -- the Plot menu ----------------------------------------------------------

  let plotAt = $state<MenuAt | null>(null);
  let plotButton: HTMLButtonElement | undefined = $state();

  function openPlot() {
    if (plotAt) return (plotAt = null);
    const r = plotButton!.getBoundingClientRect();
    plotAt = { x: r.right, y: r.bottom + 4, align: "right" };
  }

  const plotItems = $derived.by<MenuEntry[]>(() => {
    if (!answer) return [];
    const on = new Set(trends!.plotted);
    const groups: MenuEntry[] = plotGroups(answer).map((g) => {
      const n = g.paths.filter((p) => on.has(p)).length;
      return {
        id: `g:${g.key}`, label: g.title, note: n ? String(n) : undefined,
        sub: g.paths.map((path) => {
          const t = trendOf(answer, path, corpus);
          const unit = unitOf(path, corpus);
          return {
            id: `p:${path}`, label: `${t?.name ?? path}${unit ? ` (${unit})` : ""}`,
            checked: on.has(path),
            note: t && t.count < t.n ? `${t.count} of ${t.n}` : undefined,
          };
        }),
      };
    });
    return [...groups, "-", { id: "p:-", label: "Remove all", disabled: !on.size }];
  });

  function choosePlot(id: string) {
    if (id === "p:-") {
      onplot(trends?.plotted ?? [], false);
      plotAt = null;
      return;
    }
    const path = id.slice(2);
    onplot([path], !trends?.plotted.includes(path));
  }
</script>

<div class="trends">
  <div class="ghead">
    <div class="gtitle" title={trends ? `${trends.name}${trends.x == null ? "" : ` · ${trends.x}`}` : null}>
      {#if trends && trends.selected !== null}
        <!-- the selected pattern only (call 26), with the Pattern graph's ‹ › -->
        <span class="sstep">
          <button class="ib" aria-label="Previous pattern" title="Previous pattern (↑)"
            disabled={!trends.canPrev} onclick={() => onstep(-1)}>‹</button>
          <button class="ib" aria-label="Next pattern" title="Next pattern (↓)"
            disabled={!trends.canNext} onclick={() => onstep(1)}>›</button>
        </span>
        <b>{trends.name}</b>{#if trends.x != null}<span class="stat">{trends.x}</span>{/if}
      {:else}
        <b>Trends</b>
      {/if}
    </div>
    <div class="gctl">
      <span class="vg">Against
        <span class="segmented" role="group" aria-label="Against">
          <button class:on={along === "x"} aria-pressed={along === "x"} disabled={!coords}
            onclick={() => (against = "x")}>{axisWord(trends?.axis ?? "index")}</button>
          <button class:on={along === "n"} aria-pressed={along === "n"} disabled={!answer}
            onclick={() => (against = "n")}>Pattern</button>
        </span>
      </span>
      <button class="ghost plotbtn" bind:this={plotButton} aria-haspopup="menu"
        aria-expanded={!!plotAt} disabled={!answer} onclick={openPlot}>Plot
        <svg class="caret" viewBox="0 0 12 12" aria-hidden="true"><path d="M3 4.5l3 3 3-3" /></svg></button>
    </div>
  </div>

  <div class="view">
    {#if !answer}
      <p class="empty">{running ? "Plotted when the run ends." : "Run the series to plot its results."}</p>
    {:else if !panels.length}
      <p class="empty">Nothing plotted. Choose values with Plot.</p>
    {:else}
      <div class="plot" style:--gutter="{GUTTER}px" style:--left="{LEFT}px">
        <!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
        <div class="stack" class:over={hover !== null} bind:clientWidth={width} bind:clientHeight={height}
          onpointermove={move} onpointerleave={leave} onclick={click}>
          {#each panels as p, k (p.trends.map((t) => t.path).join(" "))}
            {@const gap = twoWalks ? panelGap(p) : null}
            {@const power = powerFor(p)}
            <figure class:last={k === panels.length - 1}>
              <figcaption>
                {#if groupWord(p.trends[0])}<b>{groupWord(p.trends[0])}</b>{/if}
                {#each p.trends as t, j (t.path)}
                  <span class="name" style:color={p.trends.length > 1 ? `var(${inkOf(p, j)})` : null}
                    >{t.name}{j < p.trends.length - 1 ? "," : ""}</span>
                  {#if t.count < t.n}<span class="muted num">{t.count} of {t.n}</span>{/if}
                {/each}
                {#if unitText(p.unit, power)}<span class="muted">({unitText(p.unit, power)})</span>{/if}
                {#if gap !== null}<span class="muted">walks differ by up to <span class="num">{esdText(gap)}</span> esd</span>{/if}
                <button class="ib x" aria-label="Remove this panel" title="Remove this panel"
                  onclick={(ev) => { ev.stopPropagation(); onplot(p.trends.map((t) => t.path), false); }}>
                  <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" /></svg>
                </button>
              </figcaption>
              <canvas bind:this={canvases[k]} aria-label={`${p.trends.map((t) => t.name).join(", ")} across the series`}></canvas>
            </figure>
          {/each}
        </div>
        <div class="gutter" aria-label="Walks">
          <button class="gut" style:top="4px" aria-pressed={showFirst}
            title="{showFirst ? 'Hide' : 'Show'} the first walk"
            onclick={() => (hidden = showFirst ? [...hidden, "first"] : hidden.filter((h) => h !== "first"))}>
            <svg class="sw" viewBox="0 0 16 12" aria-hidden="true"><circle class="dot" cx="8" cy="6" r="3" /></svg>
            <span class="t">First walk</span>
          </button>
          {#if twoWalks}
            <button class="gut" style:top="26px" aria-pressed={showSecond}
              title="{showSecond ? 'Hide' : 'Show'} the second walk"
              onclick={() => (hidden = showSecond ? [...hidden, "second"] : hidden.filter((h) => h !== "second"))}>
              <svg class="sw" viewBox="0 0 16 12" aria-hidden="true"><circle cx="8" cy="6" r="4.2" /></svg>
              <span class="t">Second walk</span>
            </button>
          {/if}
          <span class="xlabel" title={xLabel}>{xLabel}</span>
        </div>
      </div>
    {/if}
  </div>
</div>

{#if plotAt}
  <Menu at={plotAt} label="Plot" anchor={plotButton} items={plotItems}
    onchoose={choosePlot} onclose={() => (plotAt = null)} />
{/if}

<style>
  .trends {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  /* ‹ › before the selected pattern's name, as the Pattern graph's title */
  .gtitle > .sstep {
    display: inline-flex;
    gap: 2px;
    margin: 0 8px 0 0;
    color: var(--fg);
    vertical-align: middle;
  }

  .caret {
    width: 10px;
    height: 10px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
    stroke-linecap: round;
    stroke-linejoin: round;
  }

  .plotbtn {
    display: inline-flex;
    align-items: center;
    gap: 6px;
  }

  .view {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
    padding: 0 16px 12px;
  }

  .empty {
    margin: 0 0 8px;
    color: var(--muted);
  }

  /* the panels are one card on the window's ground, as the Pattern graph's */
  .plot {
    position: relative;
    flex: 1 1 auto;
    min-height: 300px;
    border-radius: 6px;
    background: var(--panel);
  }

  .stack {
    position: absolute;
    inset: 0 var(--gutter) 0 0;
    display: flex;
    flex-direction: column;
    overflow-y: auto;
  }

  .stack.over {
    cursor: pointer;
  }

  figure {
    flex: 1 1 0;
    min-height: 128px;
    display: flex;
    flex-direction: column;
    margin: 0;
  }

  figure.last {
    min-height: 154px;
  }

  /* a hairline between panels, as the prototype draws them */
  figure + figure {
    border-top: 1px solid var(--line-strong);
  }

  /* the panel's title band, above its plot, starting where the plot does */
  figcaption {
    flex: none;
    display: flex;
    align-items: center;
    gap: 6px;
    min-height: 26px;
    padding: 2px 4px 0 var(--left);
    white-space: nowrap;
    overflow: hidden;
  }

  figcaption .name {
    font-weight: 600;
  }

  figcaption .x {
    margin-left: auto;
  }

  .muted {
    color: var(--muted);
  }

  .num {
    font-family: var(--mono-family);
  }

  canvas {
    display: block;
    flex: 1 1 auto;
    min-height: 0;
    width: 100%;
  }

  .gutter {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: var(--gutter);
  }

  /* the walks' key, drawn as the Pattern graph's legend: the label is the
     switch (2026-11-07), symbol first */
  .gut {
    position: absolute;
    left: 4px;
    display: flex;
    align-items: center;
    gap: 6px;
    max-width: calc(var(--gutter) - 4px);
    height: 20px;
    padding: 0 4px;
    border: 0;
    border-radius: 4px;
    background: none;
    color: var(--fg);
    font: inherit;
    font-size: var(--text-sm);
    white-space: nowrap;
    cursor: pointer;
  }

  @media (hover: hover) {
    .gut:hover:not(:disabled) {
      background: var(--hover);
    }
  }

  .gut[aria-pressed="false"] {
    color: var(--muted);
  }

  .gut[aria-pressed="false"] .t {
    text-decoration: line-through;
  }

  .gut[aria-pressed="false"] .sw {
    opacity: 0.3;
  }

  .sw {
    flex: none;
    width: 16px;
    height: 12px;
    fill: none;
    stroke: var(--plot-obs);
    stroke-width: 1.2;
  }

  .sw .dot {
    fill: var(--plot-obs);
    stroke: none;
  }

  /* the shared axis's name, beside its tick labels at the foot */
  .xlabel {
    position: absolute;
    left: 8px;
    right: 4px;
    bottom: 6px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    color: var(--muted);
    font-size: var(--text-sm);
  }
</style>
