<script lang="ts">
  /**
   * The rebuild's Pattern graph (WP-2216, piece R2 of WP-2214's plan).
   *
   * One title line, the plot, and a legend gutter at its right, with every
   * rarer control one gesture away (WP-2214 rows 25-58):
   *
   * - the title line says what the graph shows, with Rwp and GoF, and holds
   *   the view's own controls: Show all (enabled while zoomed) and ⋯, the
   *   view menu;
   * - the view menu holds Show only the data and the two range gestures;
   * - the axes carry no titles. Each carries a muted unit hint by its tick
   *   labels (`° 2θ`, `√` or `log` on the intensity, `σ` on the difference),
   *   a hover explains the hint, and a click on the intensity or the
   *   difference axis opens a small menu of that axis's choices, the one
   *   place each is chosen. The choice is kept per project in
   *   `ProjectDoc.ui` (the maintainer's ruling of 2026-11-11, "Yes, build it");
   * - each legend label sits beside the pane its curve is drawn in and is its
   *   curve's switch (`gui/STYLE.md` § Plots);
   * - the fitted range and each excluded region is an object on the plot
   *   (interaction rules 1, 3, 4, 12): a click on its shading selects it, its
   *   selection bar holds the typed bounds and the channel count, Delete or
   *   Option-click removes it, and right-click opens its menu;
   * - the plot's context menu holds the exports and the range gestures;
   * - the hover readout is handed to the frame, which shows it in the status
   *   bar's right half (the maintainer's ruling of 2026-11-11, question 5), in
   *   the legend's words (`./readout.ts`, ruled "try b" the same day);
   * - the intensity opens on square root, as the prototype's does, until the
   *   project remembers another choice.
   *
   * The chart is today's `lib/pattern.ts` figure, drawn without the peak layer,
   * which the peaks-and-indexing workflow brings (R6). The three-effect split
   * (fetch, knob, mode) is `panels/Plot.svelte`'s, for the same reasons.
   */
  import { untrack } from "svelte";

  import { ApiError } from "../api";
  import { exportFigure, type ExportKind } from "../lib/exports";
  import { isShortcutTarget } from "../lib/palette";
  import {
    curveColors, curveToggles, dataOnlyHidden, isDataOnly, mergeRegions, normalizeRegion,
    residual, shows, toggleCurve,
    type Protocol, type ResidualKind, type Scale, type Window,
  } from "../lib/plot";
  import type { Curves, Overlay, PatternChart } from "../lib/pattern";
  import type { Theme } from "../lib/theme";
  import Menu, { type MenuAt, type MenuEntry } from "./Menu.svelte";
  import { statusReadout, type StatusReadout } from "./readout";
  import { CURVE_WORDS } from "./words";

  let {
    result,
    plotKey,
    theme = "light",
    protocol = { limits: null, regions: [] },
    extent = null,
    wavelengths = null,
    busy = false,
    protocolError = "",
    onprotocol = () => {},
    onreadout = () => {},
    projectPath = null,
    ui = null,
    onui = () => {},
  }: {
    result: any;
    /** bumped when the curves moved: a run landed or the history moved */
    plotKey: number;
    theme?: Theme;
    protocol?: Protocol;
    extent?: [number, number] | null;
    wavelengths?: number[] | null;
    busy?: boolean;
    /** the last refusal of a range or a region, in the verb's own words */
    protocolError?: string;
    /** may return the verb's promise, so a typed edit can follow the
     *  region it moved */
    onprotocol?: (patch: {
      two_theta_limits?: [number, number] | null;
      excluded_regions?: [number, number][];
    }) => void | Promise<void>;
    /** the hover readout, or null when the pointer leaves the plot */
    onreadout?: (reading: StatusReadout | null) => void;
    /** the open project's path: the axes' remembered choices are read when it changes */
    projectPath?: string | null;
    /** the project's `ui` keys, where the axes' choices are kept */
    ui?: Record<string, unknown> | null;
    /** persist an axis choice in the project's `ui` keys */
    onui?: (patch: Record<string, unknown>) => void;
  } = $props();

  /** The difference axis's choices: the three today's page draws
   *  (`lib/plot.ts`'s `RESIDUAL_KINDS`, in its order), in the view menu's
   *  words they had here before the axis took them. */
  const DIFFERENCES: { id: ResidualKind; label: string }[] = [
    { id: "weighted", label: "Difference in esd (Δ/σ)" }, { id: "delta", label: "Difference in counts (Δ)" },
    { id: "cumulative", label: "Cumulative χ²" },
  ];
  const SCALES: { id: Scale; label: string }[] = [
    { id: "linear", label: "Linear" }, { id: "sqrt", label: "Square root" }, { id: "log", label: "Log" },
  ];
  /** The `ProjectDoc.ui` keys the axes' choices are kept under. */
  const UI_SCALE = "intensity_scale";
  const UI_DIFFERENCE = "difference";
  const GUTTER = 112;
  const LEGEND_ROW = 20;

  let host: HTMLDivElement | undefined = $state();
  let chart: PatternChart | null = null;
  let chartModule: typeof import("../lib/pattern") | null = null;
  let curves: Curves | null = null;
  let held: Window | null = $state.raw(null);
  let loadError = $state("");
  let empty = $state(false);
  let kind = $state<ResidualKind>("weighted");
  /** square root first, as the prototype opens: the weak peaks a strong one
   *  hides are the ones a refinement is judged on */
  let scale = $state<Scale>("sqrt");
  let hidden = $state<string[]>([]);
  let beforeDataOnly = $state<string[] | null>(null);
  let hoverAt = $state<number | null>(null);
  let arm = $state<null | "limits" | "exclude">(null);
  let zoomed = $state(false);
  let geom = $state.raw<Record<"main" | "ticks" | "resid", { top: number; height: number; pad: number }> | null>(null);
  /** The plot area's left edge and width in the host, shared by every pane. */
  let plotX = $state.raw<{ left: number; width: number } | null>(null);
  /** The axis whose menu is open, and where. */
  let axisAt = $state<{ axis: "y" | "resid"; at: MenuAt } | null>(null);
  let axisButtons: Record<"y" | "resid", HTMLButtonElement | undefined> = $state({ y: undefined, resid: undefined });
  /** A hint's explanation, floating beside it while it is hovered or focused. */
  let tip = $state<{ axis: "x" | "y" | "resid"; left: number; top: number } | null>(null);
  /** The x axis's tick labels take this height under the plot, and the strip
   *  uPlot keeps for a title sits under them (`rxplot.mjs`, X_LABELS, TITLE). */
  const X_TICKS = 24;
  const X_STRIP = 18;
  let tipTimer: ReturnType<typeof setTimeout> | undefined;
  /** An SVG export redraws the panes from their spec, and a figure that
   *  leaves the window keeps its axis titles: the label functions return them
   *  only while one is being made. */
  let exporting = false;
  let colors = $state.raw<ReturnType<typeof curveColors> | null>(null);
  let viewAt = $state<MenuAt | null>(null);
  let viewButton: HTMLButtonElement | undefined = $state();
  let ctx = $state<{ at: MenuAt; region: Selection | null } | null>(null);
  /** The plot object selected: the fitted range, or one excluded region. */
  type Selection = { kind: "range" } | { kind: "region"; index: number };
  let selection = $state<Selection | null>(null);
  let note = $state("");

  const toggles = $derived(held ? curveToggles(held, residual(kind, held).label) : []);
  const dataOnly = $derived(isDataOnly(toggles, hidden));
  const stats = $derived(result?.statistics ?? null);
  const immature = $derived(Boolean(result?.maturity?.immature));

  /** What the graph shows, in words (`gui/STYLE.md` § Layout: the title says it). */
  const title = $derived.by(() =>
    loadError ? "The pattern could not be drawn"
    : !held ? "" : held.raw ? "Observed pattern" : "Last fit");

  // -- the chart ---------------------------------------------------------

  function overlayNow(): Overlay {
    return { protocol, extent, peaks: null, groups: null, peaksActive: false,
             candidate: null, hidden, held: untrack(() => held) };
  }

  let fetchSeq = 0;
  let applied: { kind: ResidualKind; scale: Scale; theme: Theme } | null = null;

  async function drawChart() {
    if (!host) return;
    const seq = ++fetchSeq;
    let mod: typeof import("../lib/pattern");
    let c: Curves;
    try {
      mod = chartModule ??= await import("../lib/pattern");
      c = await mod.fetchCurves();
    } catch (exc) {
      if (seq !== fetchSeq) return;
      dropChart();
      empty = exc instanceof ApiError && exc.empty;
      loadError = empty ? "" : (exc as Error).message;
      return;
    }
    if (seq !== fetchSeq || !host) return;
    loadError = "";
    empty = false;
    held = mod.windowOf(c);
    // the new payload is `curves` before the figure takes it: `watchZoom`
    // reads it inside the figure's own `setX`, which `setCurves` calls
    const keep = mod.sameGrid(curves, c);
    curves = c;
    if (!chart) {
      chart = new mod.PatternChart(host, c, overlayNow(), {
        scale: untrack(() => scale),
        kind: untrack(() => kind),
        // no titles on screen (2026-11-11): each axis carries a hint instead
        labels: {
          y: () => (!exporting ? "" : scale === "linear" ? "intensity"
            : `intensity (${scale === "sqrt" ? "√" : "log"})`),
          resid: () => (exporting && held && !held.raw ? residual(kind, held).title : ""),
        },
      });
      // the x title is the chart module's own string, and uPlot reads the
      // live pane's axis at each draw: blank it there. Its strip stays, so
      // nothing under the plot moves, and the x hint sits in it
      const xAxis = chart.fig.panes.resid?.axes?.[0];
      if (xAxis) {
        xAxis.label = () => (exporting ? "2θ (°)" : "");
        chart.fig.panes.resid.redraw(false, false);
      }
      applied = untrack(() => ({ kind, scale, theme }));
      chart.fig.onCursor = (hit) => (hoverAt = hit ? hit.x : null);
      chart.fig.onSelect = (lo, hi) => { if (arm) armed(lo, hi); };
      chart.fig.setMode(arm ? "select" : "zoom");
      watchZoom(chart);
    } else {
      chart.setCurves(c, keep);
      chart.update(overlayNow());
    }
    relayout();
  }

  function dropChart() {
    fetchSeq++;
    chart?.destroy();
    chart = null;
    curves = null;
    applied = null;
    held = null;
    geom = null;
    zoomed = false;
  }

  /** Whether the view is narrower than the pattern: every x move passes
   *  through the group's `setX`, a drag, a wheel, a reset and Show all alike. */
  function watchZoom(c: PatternChart) {
    const fig = c.fig, setX = fig.setX.bind(fig);
    fig.setX = (lo: number, hi: number) => {
      setX(lo, hi);
      const x = curves?.arrays?.two_theta ?? held?.two_theta;
      const n = x?.length ?? 0;
      zoomed = n > 1 && (lo > x![0] + 1e-9 || hi < x![n - 1] - 1e-9);
    };
  }

  /** Each pane's plot area from the top of the host, which places the legend
   *  beside the pane its curve is drawn in. Read after a draw, since a scale
   *  switch builds a new pane. */
  function relayout() {
    requestAnimationFrame(() => {
      if (!chart) return;
      const dpr = devicePixelRatio, out: any = {};
      for (const key of ["main", "ticks", "resid"] as const) {
        const u = chart.fig.panes[key];
        if (!u) continue;
        out[key] = { top: (u.root as HTMLElement).offsetTop + u.bbox.top / dpr,
                     height: u.bbox.height / dpr, pad: u.bbox.top / dpr };
      }
      geom = out;
      const main = chart.fig.panes.main;
      if (main && host) {
        plotX = { left: (main.over as HTMLElement).getBoundingClientRect().left
                    - host.getBoundingClientRect().left,
                  width: main.bbox.width / dpr };
      }
    });
  }

  $effect(() => {
    if (!host) return;
    const observer = new ResizeObserver(() => relayout());
    observer.observe(host);
    return () => observer.disconnect();
  });

  $effect(() => () => {
    fetchSeq++;
    chart?.destroy();
    chart = null;
  });

  const protocolKey = $derived(JSON.stringify([protocol.limits, protocol.regions]));
  const extentKey = $derived(JSON.stringify(extent));

  // fetch on what moves the curves: a run, a move in the history, the mask
  $effect(() => {
    void plotKey;
    void protocolKey;
    void result;
    untrack(() => drawChart());
  });

  // a knob applies what moved, and fetches nothing
  $effect(() => {
    const k = kind, s = scale, h = hidden, t = theme;
    void protocolKey;
    void extentKey;
    const o = untrack(overlayNow);
    untrack(() => {
      if (!chart || !applied) return;
      if (applied.kind !== k) chart.fig.setResidual(k);
      if (applied.scale !== s) {
        chart.fig.setY(s === "linear" ? "lin" : s);
        relayout();
      }
      if (applied.theme !== t) void chart.retheme();
      applied = { kind: k, scale: s, theme: t };
      chart.fig.setHidden(h);
      chart.update(o);
    });
  });

  // the legend's swatches read the plot's own colours, after the theme lands
  $effect(() => {
    void theme;
    queueMicrotask(() => {
      const css = getComputedStyle(document.documentElement);
      colors = curveColors((name) => css.getPropertyValue(name).trim());
    });
  });

  $effect(() => {
    const mode = arm ? "select" : "zoom";
    untrack(() => chart?.fig.setMode(mode));
  });

  // -- the readout, handed to the frame's status bar ----------------------

  $effect(() => {
    const reading = statusReadout(held, hoverAt, {
      kind, wavelengths, hidden,
      chi2Base: untrack(() => chart?.fig.chi2Base() ?? 0),
    });
    untrack(() => onreadout(reading));
  });

  // -- the view's controls ------------------------------------------------

  function showAll() {
    chart?.fig.reset();
  }

  function toggleDataOnly() {
    if (dataOnly && beforeDataOnly) {
      hidden = beforeDataOnly;
      beforeDataOnly = null;
    } else {
      beforeDataOnly = hidden;
      hidden = dataOnlyHidden(toggles);
    }
  }

  function toggle(id: string) {
    hidden = toggleCurve(hidden, id);
    beforeDataOnly = null;
  }

  function openView() {
    if (viewAt) return (viewAt = null);
    const r = viewButton!.getBoundingClientRect();
    viewAt = { x: r.right, y: r.bottom + 4, align: "right" };
  }

  const viewItems = $derived<MenuEntry[]>([
    { id: "data", label: "Show only the data", checked: dataOnly, disabled: !held },
    "-",
    ...rangeItems(),
  ]);

  function rangeItems(): MenuEntry[] {
    return [
      { id: "arm:limits", label: "Set the fitted range…", disabled: !held || busy },
      { id: "arm:exclude", label: "Exclude a region…", disabled: !held || busy },
      { id: "whole", label: "Fit the whole pattern", disabled: !protocol.limits || busy },
    ];
  }

  function chooseView(id: string) {
    if (id === "data") toggleDataOnly();
    else act(id);
  }

  // -- the axes: hints, their explanations and their menus -------------------

  // the project's remembered choices, read when another project opens; a
  // value this page does not know (an older page's, a hand edit) is ignored
  $effect(() => {
    void projectPath;
    untrack(() => {
      const s = ui?.[UI_SCALE], k = ui?.[UI_DIFFERENCE];
      scale = SCALES.some((o) => o.id === s) ? (s as Scale) : "sqrt";
      kind = DIFFERENCES.some((o) => o.id === k) ? (k as ResidualKind) : "weighted";
    });
  });

  /** What each axis's hint says: a unit, or a scale's mark. Linear intensity
   *  has no mark, since counts are what an intensity axis is read in. */
  const hints = $derived({
    x: "° 2θ",
    y: scale === "sqrt" ? "√" : scale === "log" ? "log" : "",
    resid: kind === "cumulative" ? "Σχ²" : kind === "delta" ? "counts" : "σ",
  });

  /** Where σ comes from, read off the route's `weighted` flag (WP-1029):
   *  the file's esd column, or Poisson's √max(y, 1). Never re-derived. */
  const sigmaFrom = $derived((held as Window | null)?.weighted === false
    ? "σ from Poisson counting statistics." : "σ from the file.");

  /** Each hint's explanation, in plain words, and what a click does. */
  const tips = $derived<Record<"x" | "y" | "resid", [string, string]>>({
    x: ["2θ in degrees.", ""],
    y: [scale === "sqrt" ? "Intensity on a square-root scale. The ticks are counts."
        : scale === "log" ? "Intensity on a log scale. Points at or below zero are not drawn."
        : "Intensity on a linear scale, in counts.", "Click to choose the scale"],
    resid: [kind === "cumulative" ? "Cumulative χ², summed from the left edge of the view."
            : kind === "delta" ? "Δ = observed − calculated, in counts."
            : `Δ/σ = (observed − calculated)/σ. ${sigmaFrom}`,
            "Click to choose what the difference shows"],
  });

  function showTip(axis: "x" | "y" | "resid", target: HTMLElement, now: boolean) {
    clearTimeout(tipTimer);
    if (axisAt) return;
    const r = target.getBoundingClientRect(), hr = host!.getBoundingClientRect();
    // under a y hint, and above the x hint, which sits at the foot
    const at = { axis, left: (axis === "x" ? r.right : r.left) - hr.left,
                 top: (axis === "x" ? r.top - 4 : r.bottom + 4) - hr.top };
    if (now) tip = at;
    else tipTimer = setTimeout(() => (tip = at), 450);
  }

  function hideTip() {
    clearTimeout(tipTimer);
    tip = null;
  }

  function openAxis(axis: "y" | "resid") {
    hideTip();
    if (axisAt?.axis === axis) return (axisAt = null);
    const r = axisButtons[axis]!.getBoundingClientRect();
    axisAt = { axis, at: { x: r.right + 4, y: r.top } };
  }

  const axisItems = $derived<MenuEntry[]>(axisAt?.axis === "y"
    ? SCALES.map((o) => ({ id: o.id, label: o.label, checked: scale === o.id, radio: true }))
    : DIFFERENCES.map((o) => ({ id: o.id, label: o.label, checked: kind === o.id, radio: true })));

  function chooseAxis(id: string) {
    if (axisAt?.axis === "y") {
      if (id === scale) return;
      scale = id as Scale;
      onui({ [UI_SCALE]: id });
    } else {
      if (id === kind) return;
      kind = id as ResidualKind;
      onui({ [UI_DIFFERENCE]: id });
    }
  }

  /** The verbs the view menu and the context menu share. */
  function act(id: string) {
    if (id === "arm:limits" || id === "arm:exclude") {
      selection = null;
      arm = id === "arm:limits" ? "limits" : "exclude";
    } else if (id === "whole") {
      onprotocol({ two_theta_limits: null });
      selection = null;
    } else if (id === "delete" && ctx?.region) {
      remove(ctx.region);
    } else if (id.startsWith("export:")) {
      void exportAs(id.slice(7) as ExportKind);
    }
  }

  async function exportAs(what: ExportKind) {
    exporting = what === "svg";
    try {
      note = await exportFigure(what, chart?.fig ?? null, "pattern");
    } finally {
      exporting = false;
    }
    setTimeout(() => (note = ""), 2500);
  }

  // -- the fitted range and the excluded regions as objects ----------------

  function armed(a: number, b: number) {
    const pair = normalizeRegion([a, b]);
    const which = arm;
    arm = null;
    if (!pair || !which) return;
    if (which === "limits") {
      onprotocol({ two_theta_limits: pair });
      selection = { kind: "range" };
    } else {
      onprotocol({ excluded_regions: mergeRegions(protocol.regions, pair) });
    }
  }

  /** The object under 2θ `x`: an excluded region first, then the shading
   *  outside the fitted range. */
  function objectAt(x: number): Selection | null {
    const i = protocol.regions.findIndex(([lo, hi]) => x >= lo && x <= hi);
    if (i >= 0) return { kind: "region", index: i };
    const l = protocol.limits;
    if (l && (x < l[0] || x > l[1])) return { kind: "range" };
    return null;
  }

  function remove(s: Selection) {
    if (s.kind === "region") {
      onprotocol({ excluded_regions: protocol.regions.filter((_, i) => i !== s.index) });
    } else {
      onprotocol({ two_theta_limits: null });
    }
    selection = null;
  }

  let downAt: { x: number; y: number } | null = null;

  function down(ev: PointerEvent) {
    downAt = ev.button === 0 ? { x: ev.clientX, y: ev.clientY } : null;
  }

  /** A click, not a drag: select the object under it, or clear the selection. */
  function up(ev: PointerEvent) {
    const d = downAt;
    downAt = null;
    if (arm || !d || !chart || Math.hypot(ev.clientX - d.x, ev.clientY - d.y) > 3) return;
    const x = chart.thetaOf(ev.clientX);
    const hit = x === null ? null : objectAt(x);
    if (hit && ev.altKey) {
      remove(hit);
      return;
    }
    selection = hit;
  }

  function context(ev: MouseEvent) {
    if (!chart || arm) return;
    ev.preventDefault();
    const x = chart.thetaOf(ev.clientX);
    const hit = x === null ? null : objectAt(x);
    if (hit) selection = hit;
    ctx = { at: { x: ev.clientX, y: ev.clientY }, region: hit };
  }

  const ctxItems = $derived<MenuEntry[]>([
    ...(ctx?.region
      ? [{ id: "delete", label: ctx.region.kind === "region" ? "Delete the region" : "Fit the whole pattern" }, "-" as const]
      : []),
    { id: "export:image", label: "Copy image" },
    { id: "export:data", label: "Copy data" },
    { id: "export:png", label: "Save as PNG…" },
    { id: "export:svg", label: "Save as SVG…" },
    "-",
    ...rangeItems().filter((e) => e === "-" || e.id !== "whole"),
  ]);

  function keydown(ev: KeyboardEvent) {
    if (!isShortcutTarget(ev)) return;
    if (ev.key === "Escape" && arm) {
      arm = null;
      ev.preventDefault();
    } else if (ev.key === "Escape" && selection) {
      selection = null;
    } else if ((ev.key === "Delete" || ev.key === "Backspace") && selection && !busy) {
      ev.preventDefault();
      remove(selection);
    }
  }

  /** The selected object's bounds and where its bar sits over the plot. */
  const chosen = $derived.by(() => {
    const s = selection;
    if (!s) return null;
    if (s.kind === "region") {
      const r = protocol.regions[s.index];
      return r ? { lo: r[0], hi: r[1] } : null;
    }
    return protocol.limits ? { lo: protocol.limits[0], hi: protocol.limits[1] } : null;
  });

  // a selection whose object went (a refit, a removal elsewhere) clears itself
  $effect(() => {
    if (selection && !chosen) selection = null;
  });

  /** The bounds as the boxes show them: one place more than the data
   *  resolves, as the old pills said them. Strings, so a new-but-equal
   *  protocol (every reload of the project) leaves a half-typed box alone. */
  const loShown = $derived(chosen ? chosen.lo.toFixed(3) : "");
  const hiShown = $derived(chosen ? chosen.hi.toFixed(3) : "");
  let loText = $state("");
  let hiText = $state("");
  $effect(() => {
    loText = loShown;
    hiText = hiShown;
  });

  /** The channels in [lo, hi], fitted and excluded together. */
  function count(lo: number, hi: number): number {
    let n = 0;
    for (const xs of [held?.two_theta, held?.excluded?.two_theta]) {
      if (!xs) continue;
      for (let i = 0; i < xs.length; i++) if (xs[i] >= lo && xs[i] <= hi) n++;
    }
    return n;
  }

  const counted = $derived.by(() => {
    if (!chosen || !selection) return "";
    const total = (held?.two_theta?.length ?? 0) + (held?.excluded?.two_theta?.length ?? 0);
    const n = count(chosen.lo, chosen.hi);
    return selection.kind === "range" ? `${n} of ${total} channels` : `${n} channels`;
  });

  /** Send the typed bounds. Enter and the box's change both land here, so
   *  an unedited pair sends nothing: the shown text is rounded, and sending it
   *  back would move the bound by the rounding. */
  let sending = false;
  async function typed() {
    const s = selection;
    const lo = Number(loText), hi = Number(hiText);
    if (!s || sending || !loText.trim() || !hiText.trim()) return;
    if (loText === loShown && hiText === hiShown) return;
    sending = true;
    try {
      if (s.kind === "range") {
        await onprotocol({ two_theta_limits: [lo, hi] });
        return;
      }
      const pair = normalizeRegion([lo, hi]);
      if (!pair) return;
      const before = protocol.regions;
      await onprotocol({ excluded_regions: mergeRegions(before.filter((_, i) => i !== s.index), pair) });
      // the merge sorts the list, so the region moved has a new index; a
      // refused edit leaves the list, and the selection, as they were
      if (protocol.regions === before) return;
      const i = protocol.regions.findIndex(([a, b]) => a <= pair[0] && b >= pair[1]);
      selection = i >= 0 ? { kind: "region", index: i } : null;
    } finally {
      sending = false;
    }
  }

  /** Where a selected object's bar sits: over the object's middle, at the top
   *  of the plot area, kept inside the plot. */
  let barWidth = $state(0);
  let hostWidth = $state(0);
  const span = $derived.by(() => {
    if (!chosen || !chart || !geom) return null;
    void zoomed;
    const u = chart.fig.panes.main, dpr = devicePixelRatio;
    // the plot area's left edge from the host's, read off the DOM: the pane's
    // own offsets do not include where the chart module placed it
    const left = (u.over as HTMLElement).getBoundingClientRect().left - host!.getBoundingClientRect().left;
    const width = u.bbox.width / dpr;
    const lo = Math.max(chosen.lo, u.scales.x.min), hi = Math.min(chosen.hi, u.scales.x.max);
    if (hi <= lo) return null;
    const a = left + Math.max(0, Math.min(width, u.valToPos(lo, "x")));
    const b = left + Math.max(0, Math.min(width, u.valToPos(hi, "x")));
    return { left: a, width: b - a, top: geom.main.top,
             height: (geom.resid?.top ?? geom.main.top) + (geom.resid?.height ?? geom.main.height) - geom.main.top };
  });
  /** The bar sits over the object's middle, kept inside the plot's column. */
  const barLeft = $derived.by(() => {
    if (!span) return 0;
    const mid = span.left + span.width / 2;
    return Math.max(barWidth / 2, Math.min(hostWidth - barWidth / 2, mid));
  });

  // -- the legend ------------------------------------------------------------

  /** Each label's top, beside its pane: the main pane's curves from its top,
   *  the difference at its pane's middle, one tick row per phase. */
  const legend = $derived.by(() => {
    if (!geom) return [];
    const out: { id: string; label: string; top: number; absent?: string }[] = [];
    let main = geom.main.top, tick = 0;
    const phases = toggles.filter((t) => t.id.startsWith("ticks:")).length;
    for (const t of toggles) {
      const label = CURVE_WORDS[t.id] ?? t.label;
      if (t.id === "diff") {
        out.push({ id: t.id, label, top: geom.resid.top + geom.resid.height / 2 - LEGEND_ROW / 2 });
      } else if (t.id.startsWith("ticks:")) {
        const row = geom.ticks.height / Math.max(phases, 1);
        out.push({ id: t.id, label, top: geom.ticks.top + row * (tick + 0.5) - LEGEND_ROW / 2 });
        tick++;
      } else {
        out.push({ id: t.id, label, top: main, absent: t.absent });
        main += LEGEND_ROW;
      }
    }
    return out;
  });

  function swatchColor(id: string): string {
    const c = colors;
    if (!c) return "currentColor";
    if (id.startsWith("ticks:")) {
      const phases = toggles.filter((t) => t.id.startsWith("ticks:"));
      const i = phases.findIndex((t) => t.id === id);
      return phases.length > 1 ? c.phase[i % c.phase.length] : c.obs;
    }
    return ({ obs: c.obs, masked: c.obs, calc: c.calc, bkg: c.bkg, diff: c.diff } as any)[id]
      ?? "currentColor";
  }
</script>

<svelte:window onkeydown={keydown} />

<div class="pattern">
  <div class="ghead">
    <!-- the whole line as its tooltip, since the title is what gives way (B1) -->
    <div class="gtitle" title={held?.stale ? `${title}, fitted over other channels` : title}>
      {#if title}<b>{title}</b>{/if}
      {#if held && !held.raw && stats}
        <span class="stat">Rwp <span class="num">{stats.rwp == null ? "" : `${(stats.rwp * 100).toFixed(2)} %`}</span></span>
        <span class="stat">GoF <span class="num">{stats.gof?.toFixed(2)}</span></span>
      {/if}
      {#if held && !held.raw && immature}<span class="bad">Not a fit yet</span>{/if}
      {#if held?.stale}<span>fitted over other channels</span>{/if}
    </div>
    <div class="gctl">
      <button class="ghost" disabled={!zoomed} onclick={showAll}
        title="Show the whole pattern">Show all</button>
      <button class="ib" bind:this={viewButton} aria-label="View" aria-haspopup="menu"
        aria-expanded={!!viewAt} disabled={!held} onclick={openView}>
        <svg viewBox="0 0 16 16" aria-hidden="true"><circle cx="3.5" cy="8" r="1" /><circle cx="8" cy="8" r="1" /><circle cx="12.5" cy="8" r="1" /></svg>
      </button>
    </div>
  </div>

  <div class="view">
    {#if empty}
      <p class="empty">No pattern to draw.</p>
    {:else if loadError}
      <p class="empty bad">{loadError}</p>
    {/if}
    <div class="plot" class:armed={!!arm} style:--gutter="{GUTTER}px">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="host" bind:this={host} bind:clientWidth={hostWidth} onpointerdowncapture={down}
        onpointerupcapture={up} oncontextmenu={context}
        onpointerleave={() => (hoverAt = null)}></div>
      {#if geom && plotX && held}
        <!-- each axis is its own control: its tick labels and its hint open its
             choices, the hint's explanation shows on hover and on focus -->
        <button class="axis" bind:this={axisButtons.y} style:--pad="{geom.main.pad}px"
          style:top="{geom.main.top - geom.main.pad}px" style:height="{geom.main.height + geom.main.pad}px"
          style:width="{plotX.left}px"
          aria-label="Intensity scale" aria-haspopup="menu" aria-expanded={axisAt?.axis === "y"}
          aria-describedby={tip?.axis === "y" ? "axis-tip" : undefined}
          onclick={() => openAxis("y")}
          onpointerenter={(e) => showTip("y", e.currentTarget.firstElementChild as HTMLElement, false)}
          onpointerleave={hideTip}
          onfocus={(e) => showTip("y", e.currentTarget.firstElementChild as HTMLElement, true)}
          onblur={hideTip}>
          <span class="hint" class:blank={!hints.y}>{hints.y || "\u00a0"}</span>
        </button>
        {#if !held.raw}
          <button class="axis" bind:this={axisButtons.resid}
            style:--pad="{geom.resid.pad}px"
            style:top="{geom.resid.top - geom.resid.pad}px" style:height="{geom.resid.height + geom.resid.pad}px"
            style:width="{plotX.left}px"
            aria-label="Difference axis" aria-haspopup="menu" aria-expanded={axisAt?.axis === "resid"}
            aria-describedby={tip?.axis === "resid" ? "axis-tip" : undefined}
            onclick={() => openAxis("resid")}
            onpointerenter={(e) => showTip("resid", e.currentTarget.firstElementChild as HTMLElement, false)}
            onpointerleave={hideTip}
            onfocus={(e) => showTip("resid", e.currentTarget.firstElementChild as HTMLElement, true)}
            onblur={hideTip}>
            <span class="hint">{hints.resid}</span>
          </button>
        {/if}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span class="hint xhint" style:top="{geom.resid.top + geom.resid.height + X_TICKS}px"
          style:height="{X_STRIP}px" style:right="calc(100% - {plotX.left + plotX.width}px)"
          onpointerenter={(e) => showTip("x", e.currentTarget, false)} onpointerleave={hideTip}
          >{hints.x}</span>
      {/if}
      {#if tip && !axisAt}
        <div id="axis-tip" class="tip" class:above={tip.axis === "x"} role="tooltip"
          style:left="{tip.left}px" style:top="{tip.top}px">
          <span>{tips[tip.axis][0]}</span>
          {#if tips[tip.axis][1]}<span class="muted">{tips[tip.axis][1]}</span>{/if}
        </div>
      {/if}
      <div class="gutter" aria-label="Curves">
        {#each legend as l (l.id)}
          <button class="gut" style:top="{l.top}px" aria-pressed={shows(hidden, l.id)}
            disabled={!!l.absent} title={l.absent ?? `${shows(hidden, l.id) ? "Hide" : "Show"} ${l.label}`}
            onclick={() => toggle(l.id)}>
            <svg class="sw" viewBox="0 0 16 12" aria-hidden="true" style:color={swatchColor(l.id)}>
              {#if l.id === "obs" || l.id === "masked"}
                <path d="M5 3l6 6M11 3l-6 6" class:faint={l.id === "masked"} />
              {:else if l.id.startsWith("ticks:")}
                <path d="M8 1.5v9" />
              {:else if l.id === "bkg"}
                <path d="M0 6h4M6 6h4M12 6h4" />
              {:else}
                <path d="M0 6h16" />
              {/if}
            </svg><span class="t">{l.label}</span>
          </button>
        {/each}
      </div>
      {#if arm}
        <div class="armnote" role="status">Drag across the plot to {arm === "limits" ? "set the fitted range" : "exclude a region"}. Esc cancels.</div>
      {/if}
      {#if span && selection}
        <!-- the selected object's outline: a DOM mark, so selecting repaints no pane -->
        <div class="chosen" style:left="{span.left}px" style:width="{span.width}px"
          style:top="{span.top}px" style:height="{span.height}px"></div>
      {/if}
      {#if chosen && selection}
        <div class="selbar" style:left="{barLeft}px" bind:clientWidth={barWidth} role="toolbar"
          aria-label={selection.kind === "range" ? "Fitted range" : "Excluded region"}>
          <input class="num" aria-label="From" bind:value={loText} disabled={busy}
            onchange={typed} onkeydown={(e) => e.key === "Enter" && typed()} />
          <span>–</span>
          <input class="num" aria-label="To" bind:value={hiText} disabled={busy}
            onchange={typed} onkeydown={(e) => e.key === "Enter" && typed()} />
          <span class="unit">° 2θ</span>
          <span class="muted num">{counted}</span>
          <button class="ib" aria-label={selection.kind === "range" ? "Fit the whole pattern" : "Delete the region"}
            title={selection.kind === "range" ? "Fit the whole pattern" : "Delete the region"}
            disabled={busy} onclick={() => remove(selection!)}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 8.5h5.6l.7-8.5" /></svg>
          </button>
          <button class="ib" aria-label="Close" title="Close" onclick={() => (selection = null)}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M4.5 4.5l7 7M11.5 4.5l-7 7" /></svg>
          </button>
        </div>
      {/if}
      {#if note || protocolError}
        <div class="toast" role="status" class:bad={!note && !!protocolError}>{note || protocolError}</div>
      {/if}
    </div>
  </div>
</div>

{#if viewAt}
  <Menu at={viewAt} label="View" anchor={viewButton} items={viewItems}
    onchoose={chooseView} onclose={() => (viewAt = null)} />
{/if}

{#if ctx}
  <Menu at={ctx.at} label="Plot" items={ctxItems} onchoose={act} onclose={() => (ctx = null)} />
{/if}

{#if axisAt}
  <Menu at={axisAt.at} label={axisAt.axis === "y" ? "Intensity scale" : "Difference axis"}
    anchor={axisButtons[axisAt.axis]} items={axisItems} onchoose={chooseAxis}
    onclose={() => (axisAt = null)} />
{/if}

<style>
  .pattern {
    flex: 1 1 auto;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  /* one row: what the graph shows on the left, the view's controls on the
     right; the title gives way first, with an ellipsis (B1, 2026-11-09) */
  .ghead {
    flex: none;
    display: flex;
    align-items: center;
    gap: 12px;
    min-height: 40px;
    padding: 2px 16px;
  }

  .gtitle {
    flex: 1 1 0;
    min-width: 9em;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .gtitle b {
    font-weight: 600;
  }

  .gtitle > span {
    margin-left: 10px;
    color: var(--muted);
    font-size: var(--text-sm);
  }

  .gtitle .num {
    font-family: var(--mono-family);
  }

  .gtitle .bad {
    color: var(--bad);
  }

  .gctl {
    flex: none;
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: var(--text-sm);
    color: var(--muted);
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

  .empty.bad {
    color: var(--bad);
  }

  .plot {
    position: relative;
    flex: 1 1 auto;
    min-height: 300px;
  }

  .host {
    position: absolute;
    inset: 0 var(--gutter) 0 0;
  }

  .plot.armed .host :global(.u-over) {
    cursor: col-resize;
  }

  /* an axis's tick labels and its hint, as one target over the margin the
     chart leaves at the plot's left: transparent, so the chart's own ticks
     show through it */
  .axis {
    position: absolute;
    left: 0;
    z-index: 1;
    display: block;
    padding: 0;
    border: 0;
    border-radius: 4px;
    background: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  @media (hover: hover) {
    .axis:hover {
      background: color-mix(in srgb, var(--hover) 60%, transparent);
    }
  }

  .axis[aria-expanded="true"] {
    background: color-mix(in srgb, var(--hover) 60%, transparent);
  }

  /* the hint: muted and small, by the tick labels, in the strips the chart
     keeps where a title used to be, so it moves nothing: a y axis's at the
     plot's top in the strip left of its labels (over the top label it
     collided with a tick at the plot's edge), the x axis's after its last
     label in the strip under them */
  .hint {
    display: inline-block;
    padding: 0 2px;
    color: var(--muted);
    font-size: var(--text-sm);
    line-height: 18px;
    white-space: nowrap;
  }

  .axis .hint {
    position: absolute;
    top: var(--pad);
    left: 0;
  }

  .hint.blank {
    visibility: hidden;
  }

  .xhint {
    position: absolute;
    z-index: 1;
    cursor: default;
  }

  .tip {
    position: absolute;
    z-index: 4;
    display: flex;
    flex-direction: column;
    gap: 2px;
    max-width: 280px;
    padding: 5px 8px;
    border: 1px solid var(--line);
    border-radius: 6px;
    background: var(--panel);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--fg) 14%, transparent);
    font-size: var(--text-sm);
    pointer-events: none;
  }

  .tip.above {
    transform: translate(-100%, -100%);
  }

  .gutter {
    position: absolute;
    top: 0;
    right: 0;
    bottom: 0;
    width: var(--gutter);
  }

  /* a legend reads symbol first: symbols in one column, labels aligned after
     them (2026-11-08); the label is the switch (2026-11-07) */
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

  .gut .t {
    overflow: hidden;
    text-overflow: ellipsis;
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

  .gut:disabled {
    color: var(--muted);
    cursor: default;
  }

  .sw {
    flex: none;
    width: 16px;
    height: 12px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
  }

  .sw .faint {
    opacity: 0.45;
  }

  /* floating layers: the panel ground, a hairline and one shadow */
  .armnote,
  .selbar,
  .toast {
    position: absolute;
    z-index: 3;
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 4px 8px;
    border: 1px solid var(--line);
    border-radius: 8px;
    background: var(--panel);
    box-shadow: 0 4px 14px color-mix(in srgb, var(--fg) 14%, transparent);
    font-size: var(--text-sm);
    white-space: nowrap;
  }

  .armnote {
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
  }

  .selbar {
    top: 4px;
    transform: translateX(-50%);
  }

  .chosen {
    position: absolute;
    z-index: 2;
    border: 1px solid var(--accent);
    border-radius: 2px;
    pointer-events: none;
  }

  .selbar input {
    width: 9ch;
    height: 24px;
    padding: 0 4px;
    border: 1px solid var(--line-strong);
    border-radius: var(--r-control);
    background: var(--bg);
    color: var(--fg);
    font-family: var(--mono-family);
    font-size: var(--text-sm);
  }

  .selbar .num {
    font-family: var(--mono-family);
  }

  .toast {
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
  }

  .toast.bad {
    color: var(--bad);
  }
</style>
