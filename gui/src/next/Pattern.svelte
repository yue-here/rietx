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
   *   labels (`° 2θ`, `√` or `log` on the intensity, `Δ/σ` on the difference),
   *   a hover explains the hint, and a click on the intensity or the
   *   difference axis opens a small menu of that axis's choices, the one
   *   place each is chosen. The choice is kept per project in
   *   `ProjectDoc.ui` (the maintainer's ruling of 2026-11-11, "Yes, build it");
   * - each legend label sits beside the pane its curve is drawn in and is its
   *   curve's switch (`gui/STYLE.md` § Plots). The excluded points have no
   *   label: the shading marks where they are (interaction rule 4), and the
   *   Observed switch shows and hides them with the rest of the data (the
   *   maintainer's ruling of 2026-11-13);
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
   * The chart is today's `lib/pattern.ts` figure, through its `/next` copy
   * (`next/pattern.ts`, drawn to the prototype by the polish). Its peak layer
   * shows while the peaks-and-indexing workflow is up (R6, WP-2240): the
   * picked lines' lenses and their fitted curve, the line chosen in the Pick
   * step's table, and a frame request that zooms to a line. The three-effect split
   * (fetch, knob, mode) is `panels/Plot.svelte`'s, for the same reasons.
   *
   * While the workflow has lines, the plot is their editing surface under
   * interaction rules 1 to 12: a click on empty space adds a line (after
   * 300 ms, so a double-click can still show everything, round 11c call 27),
   * a hover shows where it would land, a click on a lens selects it and opens
   * its bar, a drag moves it with the mark under the pointer, Option-click
   * removes it, right-click opens its menu, Esc puts a drag back or takes a
   * just-finished move back, and the main pane keeps 96 px clear above the
   * data for the lenses and the bar (call 28). The hover mark, the dragged
   * mark and the danger mark are DOM marks, so pointing repaints no pane
   * (gui/CLAUDE.md § Plot). The verbs are the workflow panel's (`onpeakedit`).
   */
  import { untrack } from "svelte";

  import { ApiError } from "../api";
  import { exportFigure, type ExportKind } from "../lib/exports";
  import { isShortcutTarget } from "../lib/palette";
  import {
    curveColors, curveToggles, dataOnlyHidden, isDataOnly, LENS_HEIGHT, LENS_WIDTH, mergeRegions,
    normalizeRegion,
    residual, shows, toggleCurve,
    type CandidateOverlay, type Protocol, type ResidualKind, type Scale, type Window,
  } from "../lib/plot";
  import type { PreviewAnswer } from "../lib/interactive";
  import {
    formatPosition, UNUSED_REACH_DEG, type GroupCurve, type PeakEdit, type PeakRow,
  } from "../lib/peaks";
  import type { Curves, Overlay, PatternChart } from "./pattern";
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
    preview = null,
    previewError = "",
    compared = null,
    oncurves = () => {},
    howText = "",
    peaks = null,
    groups = null,
    peaksActive = false,
    candidate = null,
    selectedPeak = $bindable(null),
    frameAt = null,
    onpeakedit = async () => false,
    onpeakundo = async () => false,
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
    /** the Interactive tab's preview, drawn over the last fit at its scale (WP-2128) */
    preview?: PreviewAnswer | null;
    /** the preview route's refusal, in its own words */
    previewError?: string;
    /** the curves each fetch drew, which the sliders' ranges are measured from */
    oncurves?: (curves: Curves | null) => void;
    /** the History tab's compared node: its step's name and its curve on its
     *  own channels (WP-2211), or null */
    compared?: { label: string; tt: Float64Array; y: Float64Array } | null;
    /** how the last fit ran, in words (`./howran.ts`, WP-2227), said beside its Rwp */
    howText?: string;
    /** the peak list's rows and its group fits (WP-2240), drawn while `peaksActive` */
    peaks?: readonly PeakRow[] | null;
    groups?: readonly GroupCurve[] | null;
    /** the peaks-and-indexing workflow is up: the peak layer is drawn */
    peaksActive?: boolean;
    /** the candidate cell chosen in the Index step: its lines (round 11, call 9) */
    candidate?: CandidateOverlay | null;
    /** the line chosen, in the Pick step's table or by a click on its lens */
    selectedPeak?: number | null;
    /** one edit to the peak list, through the workflow panel's verbs */
    onpeakedit?: (edit: PeakEdit) => Promise<boolean>;
    /** take the last peak edit back (Esc right after a drag, rule 2) */
    onpeakundo?: () => Promise<boolean>;
    /** a request to frame a line: 2θ, with a count so the same line asked
     *  twice frames twice */
    frameAt?: { two_theta: number; seq: number } | null;
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
  /** How far the chart's canvas reaches into the gutter, as the plot's right
   *  padding: the plot area ends at the gutter, and a 2θ label centred on that
   *  edge is drawn whole, as the prototype's canvas spans its gutter (WP-2245).
   *  Left to uPlot, the same 25 px sat outside the gutter, blank. */
  const OVERHANG = 25;
  const LEGEND_ROW = 20;

  let host: HTMLDivElement | undefined = $state();
  let chart: PatternChart | null = null;
  let chartModule: typeof import("./pattern") | null = null;
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
  /** Each pane's plot area in the host: its top, height and top padding, and
   *  where its top labelled tick and its zero sit from the plot area's top
   *  (`mark`, `zero`; null where there is none in view). */
  type PaneGeom = { top: number; height: number; pad: number; mark: number | null; zero: number | null };
  let geom = $state.raw<Record<"main" | "ticks" | "resid", PaneGeom> | null>(null);
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
  /** A scale mark's line height, and half a tick label plus the gap kept
   *  under the mark, in CSS px; the axis labels are 11 px type. */
  const MARK_LINE = 14;
  const LABEL_HALF = 12;
  /** The y tick labels end this far left of the plot area: uPlot's tick length
   *  (10 px) and its label gap (5 px), neither of which the chart changes. */
  const LABEL_INSET = 15;
  const X_STRIP = 18;
  let tipTimer: ReturnType<typeof setTimeout> | undefined;
  /** An SVG export redraws the panes from their spec, and a figure that
   *  leaves the window keeps its axis titles: the label functions return them
   *  only while one is being made. */
  let exporting = false;
  let colors = $state.raw<ReturnType<typeof curveColors> | null>(null);
  let viewAt = $state<MenuAt | null>(null);
  let viewButton: HTMLButtonElement | undefined = $state();
  let ctx = $state<{ at: MenuAt; region: Selection | null; peak?: number | null } | null>(null);
  /** The plot object selected: the fitted range, or one excluded region. */
  type Selection = { kind: "range" } | { kind: "region"; index: number };
  let selection = $state<Selection | null>(null);
  let note = $state("");

  // the excluded points are no curve of their own here: their shading marks
  // them, so the legend lists no "Excluded" (ruled 2026-11-13), and `drawn`
  // hides them with the observed points
  const toggles = $derived(held
    ? curveToggles(held, residual(kind, held).label).filter((t) => t.id !== "masked") : []);
  /** What the chart and the readout leave out: `hidden`, plus the excluded
   *  points while the observed ones are hidden. */
  const drawn = $derived(hidden.includes("obs") ? [...hidden, "masked"] : hidden);
  const stats = $derived(result?.statistics ?? null);
  const immature = $derived(Boolean(result?.maturity?.immature));

  /** What the graph shows, in words (`gui/STYLE.md` § Layout: the title says it). */
  const title = $derived.by(() =>
    loadError ? "The pattern could not be drawn"
    : !held ? "" : held.raw ? "Observed pattern" : "Last fit");

  /** Whether the title line describes the last fit, its Rwp and GoF. */
  const fitShown = $derived(!!held && !(held as Window).raw && !!stats);

  /** Whether a preview is in hand: values nobody has applied (WP-2128). */
  const hasPreview = $derived(!!preview && !!held && !loadError);
  /** Which of the two the graph draws while a preview is in hand: a view
   *  choice, session-local like the knobs, back to the preview whenever the
   *  preview goes (the maintainer's look, 2026-11-21, item 4: "a toggle
   *  between last refined and preview"). The last fit is drawn whole, as with
   *  no preview, so its difference, ticks and Rwp are the fit's. */
  let shown = $state<"preview" | "last">("preview");
  $effect(() => {
    if (!hasPreview) untrack(() => (shown = "preview"));
  });
  const SHOWN: { id: "preview" | "last"; label: string; title: string }[] = [
    { id: "preview", label: "Preview", title: "Draw the pattern at the values not yet applied" },
    { id: "last", label: "Last fit", title: "Draw the last fit, as it was before the edit" },
  ];
  /** Whether the graph draws the preview. */
  const previewing = $derived(hasPreview && shown === "preview");
  /** Data only also hides the preview, which has no toggle in `toggles`. */
  const dataOnly = $derived(isDataOnly(toggles, hidden)
    && (!previewing || hidden.includes("preview"))
    && (!compared || hidden.includes("compare")));
  const pct = (x: number | null | undefined) => (x == null ? "" : `${(x * 100).toFixed(2)} %`);
  /** The whole title line as its tooltip, since the title is what gives way
   *  (B1); a refused preview's reason is said there, in the route's words. */
  const titleTip = $derived(previewing ? "Preview, not refined"
    : previewError ? `${title}. Preview refused: ${previewError}`
    : (held as Window | null)?.stale ? `${title}, fitted over other channels`
    : fitShown && howText ? `${title}. ${howText}` : title);

  // -- the chart ---------------------------------------------------------

  function overlayNow(): Overlay {
    return { protocol, extent, peaks, groups, peaksActive, selected: selectedPeak,
             dragging: drag?.moved ? drag.index : landing?.index ?? null,
             candidate, hidden: drawn, held: untrack(() => held) };
  }

  // the peak layer is a repaint, never a refetch (gui/CLAUDE.md § Plot)
  $effect(() => {
    void peaks; void groups; void peaksActive; void selectedPeak; void candidate;
    void drag?.moved; void landing;
    untrack(() => {
      chart?.update(overlayNow());
      relayout();
    });
  });

  /** A row click frames its line at 2° of 2θ, or keeps a narrower zoom
   *  centred on it (round 11b), and leaves the line where it was asked for. */
  const FRAME_DEG = 2;
  $effect(() => {
    const f = frameAt;
    if (!f) return;
    untrack(() => {
      if (!chart) return;
      const { min, max } = chart.fig.panes.main.scales.x;
      const span = Math.min(FRAME_DEG, Math.abs(max - min) || FRAME_DEG);
      chart.fig.setX(f.two_theta - span / 2, f.two_theta + span / 2);
    });
  });

  /** Bumped after each draw, so the DOM marks re-read where the lenses went. */
  let painted = $state(0);

  let fetchSeq = 0;
  let applied: { kind: ResidualKind; scale: Scale; theme: Theme } | null = null;

  async function drawChart() {
    if (!host) return;
    const seq = ++fetchSeq;
    let mod: typeof import("./pattern");
    let c: Curves;
    try {
      mod = chartModule ??= await import("./pattern");
      c = await mod.fetchCurves();
    } catch (exc) {
      if (seq !== fetchSeq) return;
      dropChart();
      // no curves: the sliders' ranges and phase names must not stay the
      // previous pattern's
      oncurves(null);
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
        // no titles on screen (2026-11-11): each axis carries a hint instead,
        // and the y axes keep no strip for one (the look of 2026-11-21, item 1)
        titled: () => exporting,
        padRight: OVERHANG,
        labels: {
          y: () => (!exporting ? "" : scale === "linear" ? "intensity"
            : `intensity (${scale === "sqrt" ? "√" : "log"})`),
          resid: () => (exporting && held && !held.raw ? residual(kind, held).title : ""),
        },
      });
      // the x title is the chart module's own string, and uPlot reads the
      // live pane's axis at each draw: blank it there. Its strip stays, so
      // nothing under the plot moves, and the x hint sits in it
      const xAxis = chart.fig.panes.ticks?.axes?.[0];
      if (xAxis) {
        xAxis.label = () => (exporting ? "2θ (°)" : "");
        chart.fig.panes.ticks.redraw(false, false);
      }
      applied = untrack(() => ({ kind, scale, theme }));
      chart.fig.onCursor = (hit) => (hoverAt = hit ? hit.x : null);
      chart.fig.onSelect = (lo, hi) => { if (arm) armed(lo, hi); };
      chart.fig.setMode(arm ? "select" : "zoom");
      watchZoom(chart);
      // a chart built under a preview (the graph tab came back to Pattern)
      // has no view yet to keep: keeping one drew an empty plot (WP-2218)
      const p = untrack(() => (shown === "preview" ? preview : null));
      if (p) chart.setPreview(p.curves, false);
      const cmp = untrack(() => compared);
      if (cmp) chart.setCompared(cmp);
    } else {
      chart.setCurves(c, keep);
      chart.update(overlayNow());
    }
    oncurves(c);
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
      // the y range follows the x range, and the scale marks its top tick
      relayout();
    };
  }

  /** Where `v` sits from the plot area's top in CSS px, or null out of view. */
  function inView(u: any, v: number): number | null {
    const y = u.valToPos(v, "y");
    return Number.isFinite(y) && y >= -0.5 && y <= u.bbox.height / devicePixelRatio + 0.5 ? y : null;
  }

  /** The top labelled y tick's place, from the splits and labels uPlot drew. */
  function topTick(u: any): number | null {
    const axis = u.axes?.[1], splits: number[] = axis?._splits ?? [], values: unknown[] = axis?._values ?? [];
    let top: number | null = null;
    splits.forEach((v, i) => {
      if (values[i] == null || values[i] === "") return;
      const y = inView(u, v);
      if (y != null && (top == null || y < top)) top = y;
    });
    return top;
  }

  /** Each pane's plot area from the top of the host, which places the legend
   *  beside the pane its curve is drawn in. Read after a draw, since a scale
   *  switch builds a new pane. A preview redraws at every slider answer, so
   *  an unchanged layout is not published again. */
  function relayout() {
    requestAnimationFrame(() => {
      if (!chart) return;
      painted++;
      const dpr = devicePixelRatio, out: any = {};
      for (const key of ["main", "ticks", "resid"] as const) {
        const u = chart.fig.panes[key];
        if (!u) continue;
        out[key] = { top: (u.root as HTMLElement).offsetTop + u.bbox.top / dpr,
                     height: u.bbox.height / dpr, pad: u.bbox.top / dpr,
                     mark: topTick(u), zero: inView(u, 0) };
      }
      if (JSON.stringify(out) !== JSON.stringify(geom)) geom = out;
      const main = chart.fig.panes.main;
      if (main && host) {
        const x = { left: (main.over as HTMLElement).getBoundingClientRect().left
                      - host.getBoundingClientRect().left,
                    width: main.bbox.width / dpr };
        if (x.left !== plotX?.left || x.width !== plotX?.width) plotX = x;
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
    const k = kind, s = scale, h = drawn, t = theme;
    void protocolKey;
    void extentKey;
    const o = untrack(overlayNow);
    untrack(() => {
      if (!chart || !applied) return;
      if (applied.kind !== k) {
        chart.fig.setResidual(k);
        relayout();
      }
      if (applied.scale !== s) {
        chart.fig.setY(s === "linear" ? "lin" : s);
        relayout();
      }
      if (applied.theme !== t) void chart.retheme();
      applied = { kind: k, scale: s, theme: t };
      chart.fig.setHidden(h);
      chart.update(o);
      // a hidden curve can move the y range, and the scale mark its top tick
      relayout();
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

  // The preview is a repaint over the payload in hand, never a refetch
  // (WP-2128). Each one drawn leaves an `rx-preview-redraw` User Timing entry
  // from the moment its values were set to the frame after it painted: the
  // drag-to-redraw latency the browser test reads, as on today's page.
  $effect(() => {
    const p = shown === "preview" ? preview : null;
    untrack(() => {
      if (!chart) return;
      chart.setPreview(p?.curves ?? null);
      relayout();
      if (!p) performance.clearMeasures?.("rx-preview-redraw");
      else requestAnimationFrame(() => requestAnimationFrame(() =>
        performance.measure("rx-preview-redraw", { start: p.sentAt })));
    });
  });

  // A compared node is a repaint too (WP-2211). A new one arrives drawn, as a
  // curve a later build adds does: a hidden curve is not remembered.
  $effect(() => {
    const cmp = compared;
    untrack(() => {
      if (hidden.includes("compare")) hidden = hidden.filter((id) => id !== "compare");
      chart?.setCompared(cmp);
    });
  });

  // -- the readout, handed to the frame's status bar ----------------------

  $effect(() => {
    const reading = statusReadout(held, hoverAt, {
      kind, wavelengths, hidden: drawn,
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
      // the preview and a compared node have no toggle of their own but are
      // no data either
      hidden = [...dataOnlyHidden(toggles), "preview", "compare"];
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

  /** A scale mark's top in its axis button (which starts at the pane's top):
   *  its line's height plus half a tick label and a gap above the top labelled
   *  tick, right-aligned with the labels, so it sits in their column and never
   *  on one. `MARK_ROOM` (rxplot) is the padding that keeps a tick at the plot's
   *  top edge clear of it; no tick in view puts it at the plot's top. */
  function markTop(g: PaneGeom): number {
    return Math.max(0, g.pad + (g.mark ?? 0) - MARK_LINE - LABEL_HALF);
  }

  /** What each axis's hint says: a unit, or a scale's mark. Linear intensity
   *  has no mark, since counts are what an intensity axis is read in. */
  const hints = $derived({
    x: "° 2θ",
    y: scale === "sqrt" ? "√" : scale === "log" ? "log" : "",
    resid: kind === "cumulative" ? "Σχ²" : kind === "delta" ? "Δ" : "Δ/σ",
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
    } else if (id === "peak:delete" && ctx?.peak != null) {
      removePeak(ctx.peak);
    } else if (id === "peak:use" && ctx?.peak != null) {
      const row = peakRow(ctx.peak);
      if (row) void peakEdit({ kind: "use", index: row.index, on: !row.usable });
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

  // -- the peak lines as objects (WP-2240) ---------------------------------

  /** A press must travel this far, in CSS px, to be a drag, as for a region. */
  const DRAG_PX = 3;
  /** A click on empty space adds its line this long after, so a second
   *  click can make it a double-click, which shows everything (call 27). */
  const ADD_DELAY_MS = 300;
  const DOUBLE_MS = 350;

  /** Whether the plot edits peak lines: the workflow is up with a list, its
   *  layer is shown (a hidden layer would take lines nobody can see), and no
   *  range gesture is armed. */
  const peakMode = $derived(peaksActive && !!peaks?.length && !arm && !drawn.includes("peaks"));
  /** A lens being dragged: its line, where it started and where it is. */
  let drag = $state<{ index: number; from: number; at: number; x0: number; y0: number;
                      moved: boolean; pointer: number } | null>(null);
  /** A dropped lens waiting for the move's answer, drawn where it landed. */
  let landing = $state<{ index: number; at: number } | null>(null);
  /** The move a drag just made, while its line stays chosen: Esc takes it
   *  back (rule 2, call 35), and any other press ends that chance. */
  let moved: { after: number; before: number } | null = null;
  /** A click on empty space, waiting its 300 ms to add a line. */
  let pending = $state<{ at: number; x: number; y: number; t: number;
                         timer: ReturnType<typeof setTimeout> } | null>(null);
  /** The lens under the pointer, and whether Option is held over it. */
  let overMark = $state<number | null>(null);
  let altHeld = $state(false);

  const peakRow = (i: number | null | undefined) =>
    i == null ? null : peaks?.find((p) => p.index === i) ?? null;

  /** The unused line within reach of 2θ `x`, which a click there chooses
   *  rather than adding its twin (call 33). */
  function unusedNear(x: number): PeakRow | null {
    let best: PeakRow | null = null;
    for (const p of peaks ?? []) {
      if (p.usable || Math.abs(p.two_theta - x) > UNUSED_REACH_DEG) continue;
      if (!best || Math.abs(p.two_theta - x) < Math.abs(best.two_theta - x)) best = p;
    }
    return best;
  }

  /** Any edit ends Esc's chance to take a drag's move back, since Esc
   *  undoes the stack's last step, which is then this edit's. */
  async function peakEdit(e: PeakEdit): Promise<boolean> {
    moved = null;
    return onpeakedit(e);
  }

  function removePeak(index: number) {
    if (selectedPeak === index) selectedPeak = null;
    void peakEdit({ kind: "remove", index });
  }

  function down(ev: PointerEvent) {
    downAt = ev.button === 0 ? { x: ev.clientX, y: ev.clientY } : null;
    moved = null;
    if (!peakMode || !chart || ev.button !== 0 || busy) return;
    const m = chart.markAt(ev.clientX, ev.clientY);
    const row = peakRow(m);
    if (m == null || !row) return;
    // the press is the lens's: no box zoom starts under it (preventing the
    // pointerdown withholds the mouse events the chart listens to)
    ev.preventDefault();
    ev.stopPropagation();
    host?.setPointerCapture?.(ev.pointerId);
    drag = { index: m, from: row.two_theta, at: row.two_theta, x0: ev.clientX, y0: ev.clientY,
             moved: false, pointer: ev.pointerId };
  }

  function move(ev: PointerEvent) {
    altHeld = ev.altKey;
    if (drag && chart) {
      if (!drag.moved && Math.hypot(ev.clientX - drag.x0, ev.clientY - drag.y0) > DRAG_PX) {
        drag.moved = true;
      }
      if (drag.moved) drag.at = chart.thetaOf(ev.clientX) ?? drag.at;
      return;
    }
    overMark = peakMode && chart && !busy ? chart.markAt(ev.clientX, ev.clientY) : null;
  }

  function leave() {
    hoverAt = null;
    if (!drag) overMark = null;
  }

  /** End a drag: a press that did not travel is a click on the lens. */
  async function dropLens(ev: PointerEvent) {
    const d = drag!;
    drag = null;
    host?.releasePointerCapture?.(d.pointer);
    if (!d.moved) {
      if (ev.altKey) removePeak(d.index);
      else {
        selection = null;
        selectedPeak = d.index;
      }
      return;
    }
    if (Math.abs(d.at - d.from) < 1e-9) return;
    landing = { index: d.index, at: d.at };
    try {
      if (await peakEdit({ kind: "move", index: d.index, two_theta: d.at }) && selectedPeak != null) {
        moved = { after: selectedPeak, before: d.index };
      }
    } finally {
      landing = null;
    }
  }

  /** A click, not a drag: select the object under it, or clear the selection. */
  function up(ev: PointerEvent) {
    if (drag) {
      downAt = null;
      void dropLens(ev);
      return;
    }
    const d = downAt;
    downAt = null;
    if (arm || !d || !chart || Math.hypot(ev.clientX - d.x, ev.clientY - d.y) > 3) return;
    const x = chart.thetaOf(ev.clientX);
    const hit = x === null ? null : objectAt(x);
    if (hit && ev.altKey) {
      remove(hit);
      return;
    }
    if (!peakMode || hit || x === null) {
      selection = hit;
      // the chosen line is the workflow's: outside it a click leaves it be
      if (peaksActive) selectedPeak = null;
      return;
    }
    // a click elsewhere closes a region's bar and does nothing more (rule 3)
    if (selection) {
      selection = null;
      return;
    }
    // a second click on the spot is a double-click: no line, and the chart
    // shows everything
    if (pending && ev.timeStamp - pending.t < DOUBLE_MS
        && Math.hypot(ev.clientX - pending.x, ev.clientY - pending.y) < 6) {
      clearTimeout(pending.timer);
      pending = null;
      return;
    }
    // with a line chosen, a click on empty space only lets it go (round 11b)
    if (selectedPeak != null) {
      selectedPeak = null;
      return;
    }
    const near = unusedNear(x);
    if (near) {
      selectedPeak = near.index;
      return;
    }
    if (busy) return;
    if (pending) clearTimeout(pending.timer);
    const at = x;
    pending = { at, x: ev.clientX, y: ev.clientY, t: ev.timeStamp, timer: setTimeout(async () => {
      try {
        await peakEdit({ kind: "add", two_theta: at });
      } finally {
        if (pending?.at === at) pending = null;
      }
    }, ADD_DELAY_MS) };
  }

  function context(ev: MouseEvent) {
    if (!chart || arm) return;
    ev.preventDefault();
    const m = peakMode ? chart.markAt(ev.clientX, ev.clientY) : null;
    if (m != null) {
      selection = null;
      selectedPeak = m;
      ctx = { at: { x: ev.clientX, y: ev.clientY }, region: null, peak: m };
      return;
    }
    const x = chart.thetaOf(ev.clientX);
    const hit = x === null ? null : objectAt(x);
    if (hit) selection = hit;
    ctx = { at: { x: ev.clientX, y: ev.clientY }, region: hit, peak: null };
  }

  /** The chosen line's row, its lens, and where its bar sits over the plot. */
  const chosenPeak = $derived(peakMode ? peakRow(selectedPeak) : null);
  const peakSpot = $derived.by(() => {
    void painted;
    if (!chosenPeak || !chart || !geom || !plotX) return null;
    const mark = chart.markOf(chosenPeak.index);
    const x = mark?.x ?? chart.xOf(chosenPeak.two_theta);
    if (x == null) return null;
    // above its lens, or at the plot's top for a line with no lens
    const top = mark ? Math.max(2, mark.y - mark.h / 2 - 6) : 2;
    return { left: plotX.left + x, bottom: geom.main.top + top };
  });
  let barWidth = $state(0);
  let hostWidth = $state(0);
  /** The host's width short of the gutter, which its canvas reaches into by `OVERHANG`. */
  const columnWidth = $derived(hostWidth - OVERHANG);
  let peakBarWidth = $state(0);
  const peakBarLeft = $derived(peakSpot
    ? Math.max(peakBarWidth / 2, Math.min(columnWidth - peakBarWidth / 2, peakSpot.left)) : 0);

  /** The DOM marks: a dashed lens where a click would add a line (rule 9),
   *  the dragged or pending lens, and the danger lens under Option. */
  const lensOf = (tt: number) => {
    void painted;
    const at = chart?.lensAt(tt);
    return at && plotX && geom ? { left: plotX.left + at.x, top: geom.main.top + at.y } : null;
  };
  const hoverLens = $derived.by(() => {
    if (!peakMode || busy || drag || landing || pending || overMark != null || hoverAt == null
        || selectedPeak != null || objectAt(hoverAt) || unusedNear(hoverAt)) return null;
    return lensOf(hoverAt);
  });
  const movingLens = $derived.by(() => {
    const at = drag?.moved ? drag.at : landing?.at ?? pending?.at ?? null;
    return at == null ? null : lensOf(at);
  });
  const dangerLens = $derived.by(() => {
    void painted;
    if (!altHeld || overMark == null || drag || !chart || !plotX || !geom) return null;
    const m = chart.markOf(overMark);
    return m ? { left: plotX.left + m.x, top: geom.main.top + m.y, h: m.h } : null;
  });

  const ctxItems = $derived<MenuEntry[]>([
    ...(ctx?.peak != null && peakRow(ctx.peak)
      ? [{ id: "peak:use", label: peakRow(ctx.peak)!.usable ? "Leave out of the search" : "Use in the search" },
         { id: "peak:delete", label: "Delete the line" }, "-" as const]
      : []),
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
    if (ev.key === "Alt") altHeld = true;
    if (!isShortcutTarget(ev)) return;
    if (ev.key === "Escape" && drag) {
      // a drag backs out: the lens goes back where it started (rule 2)
      host?.releasePointerCapture?.(drag.pointer);
      drag = null;
      ev.preventDefault();
    } else if (ev.key === "Escape" && moved && selectedPeak === moved.after) {
      // right after a drag, the first Esc takes the move back (call 35)
      const m = moved;
      moved = null;
      ev.preventDefault();
      void onpeakundo().then((ok) => { if (ok) selectedPeak = m.before; });
    } else if (ev.key === "Escape" && arm) {
      arm = null;
      ev.preventDefault();
    } else if (ev.key === "Escape" && selection) {
      selection = null;
    } else if (ev.key === "Escape" && peakMode && selectedPeak != null) {
      selectedPeak = null;
    } else if ((ev.key === "Delete" || ev.key === "Backspace") && selection && !busy) {
      ev.preventDefault();
      remove(selection);
    } else if ((ev.key === "Delete" || ev.key === "Backspace") && chosenPeak && !busy) {
      ev.preventDefault();
      removePeak(chosenPeak.index);
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
    return Math.max(barWidth / 2, Math.min(columnWidth - barWidth / 2, mid));
  });

  // -- the legend ------------------------------------------------------------

  /** Each label's top, beside its pane: the main pane's curves from its top,
   *  the difference at its pane's middle, one tick row per phase. */
  const layout = $derived.by(() => {
    if (!geom) return { rows: [], end: 0 };
    const out: { id: string; label: string; top: number; absent?: string; reserved?: boolean }[] = [];
    let main = geom.main.top, tick = 0;
    const phases = toggles.filter((t) => t.id.startsWith("ticks:")).length;
    for (const t of toggles) {
      const label = CURVE_WORDS[t.id] ?? t.label;
      if (t.id === "diff") {
        // centred on the trace: its zero line, the ±3 esd band's middle,
        // else the strip's (the maintainer's look, 2026-11-21, item 2)
        const mid = kind !== "cumulative" && geom.resid.zero != null
          ? geom.resid.zero : geom.resid.height / 2;
        out.push({ id: t.id, label, top: geom.resid.top + mid - LEGEND_ROW / 2 });
      } else if (t.id.startsWith("ticks:")) {
        const row = geom.ticks.height / Math.max(phases, 1);
        out.push({ id: t.id, label, top: geom.ticks.top + row * (tick + 0.5) - LEGEND_ROW / 2 });
        tick++;
      } else {
        out.push({ id: t.id, label, top: main, absent: t.absent });
        main += LEGEND_ROW;
        // the preview's slot under the last fit, kept while no preview is
        // drawn, so one appearing moves no label (the prototype's legend)
        if (t.id === "calc") {
          out.push({ id: "preview", label: CURVE_WORDS.preview, top: main, reserved: !previewing });
          main += LEGEND_ROW;
        }
      }
    }
    // the compared node last, under every other label of the pane, so one
    // appearing moves none of them; the Show choice sits under it
    if (compared) {
      out.push({ id: "compare", label: compared.label, top: main });
      main += LEGEND_ROW;
    }
    return { rows: out, end: main };
  });
  const legend = $derived(layout.rows);
  /** Where the main pane's labels end, which the Show choice sits under. */
  const legendEnd = $derived(layout.end);

  function swatchColor(id: string): string {
    const c = colors;
    if (!c) return "currentColor";
    if (id.startsWith("ticks:")) {
      const phases = toggles.filter((t) => t.id.startsWith("ticks:"));
      const i = phases.findIndex((t) => t.id === id);
      return phases.length > 1 ? c.phase[i % c.phase.length] : c.obs;
    }
    return ({ obs: c.obs, calc: previewing ? c.last : c.calc, preview: c.calc, bkg: c.bkg,
              diff: c.diff, compare: c.compare } as any)[id]
      ?? "currentColor";
  }
</script>

<svelte:window onkeydown={keydown} onkeyup={(e) => { if (e.key === "Alt") altHeld = false; }}
  onblur={() => (altHeld = false)} />

<!-- a lens as a DOM mark, the canvas's `lens` (`lib/plot.ts`) at 18 by 4.5 px -->
{#snippet lensMark(cls: string, left: number, top: number, scale: number)}
  <svg class="lensmark {cls}" style:left="{left}px" style:top="{top}px"
    width={2 * LENS_WIDTH * scale + 4} height={LENS_HEIGHT * scale + 4} aria-hidden="true">
    <path d="M {LENS_WIDTH * scale + 2} 2 Q {2 * LENS_WIDTH * scale + 2} {LENS_HEIGHT * scale / 2 + 2} {LENS_WIDTH * scale + 2} {LENS_HEIGHT * scale + 2} Q 2 {LENS_HEIGHT * scale / 2 + 2} {LENS_WIDTH * scale + 2} 2 Z" />
  </svg>
{/snippet}

<div class="pattern">
  <div class="ghead">
    <!-- the whole line as its tooltip, since the title is what gives way (B1) -->
    <div class="gtitle" title={titleTip}>
      {#if previewing}
        <!-- a preview never reads as a changed fit (`gui/STYLE.md` § Layout):
             its Rwp is said beside the last fit's, as the prototype's is -->
        <b class="pv">Preview, not refined</b>
        <span class="stat">Rwp <span class="num">{pct(preview?.curves?.header?.rwp)}</span>{#if stats?.rwp != null},
          last fit <span class="num">{pct(stats.rwp)}</span>{/if}</span>
      {:else}
      {#if title}<b>{title}</b>{/if}
      {#if previewError}<span class="bad">Preview refused</span>{/if}
      {#if fitShown}
        <span class="stat">Rwp <span class="num">{stats.rwp == null ? "" : `${(stats.rwp * 100).toFixed(2)} %`}</span></span>
        <span class="stat">GoF <span class="num">{stats.gof?.toFixed(2)}</span></span>
        <!-- how the fit ran (WP-2227): one stage, or in stages and why -->
        {#if howText}<span class="how">{howText}</span>{/if}
      {/if}
      {#if held && !held.raw && immature}<span class="bad">Not a fit yet</span>{/if}
      {#if held?.stale}<span>fitted over other channels</span>{/if}
      {/if}
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
    <div class="plot" class:armed={!!arm} style:--gutter="{GUTTER}px" style:--overhang="{OVERHANG}px"
      style:--inset="{LABEL_INSET}px" style:--mark-line="{MARK_LINE}px">
      <!-- svelte-ignore a11y_no_static_element_interactions -->
      <div class="host" class:onmark={overMark != null && !altHeld} class:dragging={!!drag?.moved}
        bind:this={host} bind:clientWidth={hostWidth} onpointerdowncapture={down}
        onpointerupcapture={up} onpointermove={move} oncontextmenu={context}
        onpointerleave={leave}></div>
      {#if hoverLens}{@render lensMark("ghost", hoverLens.left, hoverLens.top, 1)}{/if}
      {#if movingLens}{@render lensMark("moving", movingLens.left, movingLens.top, drag || landing ? 1.4 : 1)}{/if}
      {#if dangerLens}{@render lensMark("danger", dangerLens.left, dangerLens.top, dangerLens.h / LENS_HEIGHT)}{/if}
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
          <span class="hint" class:blank={!hints.y} style:top="{markTop(geom.main)}px"
            >{hints.y || "\u00a0"}</span>
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
            <span class="hint" style:top="{markTop(geom.resid)}px">{hints.resid}</span>
          </button>
        {/if}
        <!-- svelte-ignore a11y_no_static_element_interactions -->
        <span class="hint xhint" style:top="{geom.ticks.top + geom.ticks.height + X_TICKS}px"
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
          <button class="gut" class:reserved={!!l.reserved} style:top="{l.top}px"
            aria-pressed={shows(hidden, l.id)} aria-hidden={l.reserved ? "true" : undefined}
            disabled={!!l.absent || !!l.reserved} title={l.absent ?? `${shows(hidden, l.id) ? "Hide" : "Show"} ${l.label}`}
            onclick={() => toggle(l.id)}>
            <svg class="sw" viewBox="0 0 16 12" aria-hidden="true" style:color={swatchColor(l.id)}>
              {#if l.id === "obs"}
                <path d="M5 3l6 6M11 3l-6 6" />
              {:else if l.id.startsWith("ticks:")}
                <path d="M8 1.5v9" />
              {:else if l.id === "bkg" || l.id === "compare"}
                <path d="M0 6h4M6 6h4M12 6h4" />
              {:else}
                <path d="M0 6h16" />
              {/if}
            </svg><span class="t">{l.label}</span>
          </button>
        {/each}
        {#if hasPreview && geom}
          <!-- the choice between the preview and the last fit, under the
               curves it chooses between, so the title line keeps its room for
               the fit's words (WP-2227; the maintainer's fallback of
               2026-11-22). Placed by the legend, it moves nothing as it comes -->
          <span class="vg" style:top="{legendEnd + LEGEND_ROW / 2}px">Show
            <span class="segmented" role="group" aria-label="Show">
              {#each SHOWN as s (s.id)}
                <button class:on={shown === s.id} aria-pressed={shown === s.id} title={s.title}
                  onclick={() => (shown = s.id)}>{s.label}</button>
              {/each}
            </span>
          </span>
        {/if}
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
      {#if chosenPeak && peakSpot}
        <div class="selbar peakbar" style:left="{peakBarLeft}px" style:top="{peakSpot.bottom}px"
          bind:clientWidth={peakBarWidth} role="toolbar" aria-label="Peak line">
          <span class="num">{formatPosition(chosenPeak.two_theta, null).value}</span><span class="unit">° 2θ</span>
          <span class="segmented" role="group" aria-label="In the search">
            <button class:on={chosenPeak.usable} aria-pressed={chosenPeak.usable} disabled={busy}
              onclick={() => !chosenPeak!.usable && peakEdit({ kind: "use", index: chosenPeak!.index, on: true })}>Used</button>
            <button class:on={!chosenPeak.usable} aria-pressed={!chosenPeak.usable} disabled={busy}
              onclick={() => chosenPeak!.usable && peakEdit({ kind: "use", index: chosenPeak!.index, on: false })}>Not used</button>
          </span>
          <button class="ib" aria-label="Delete the line" title="Delete the line" disabled={busy}
            onclick={() => removePeak(chosenPeak!.index)}>
            <svg viewBox="0 0 16 16" aria-hidden="true"><path d="M3 4.5h10M6.5 4.5V3h3v1.5M4.5 4.5l.7 8.5h5.6l.7-8.5" /></svg>
          </button>
          <button class="ib" aria-label="Close" title="Close" onclick={() => (selectedPeak = null)}>
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

  /* the plot is a card on the window's ground, as the prototype draws it */
  .plot {
    position: relative;
    flex: 1 1 auto;
    min-height: 300px;
    border-radius: 6px;
    background: var(--panel);
  }

  .host {
    position: absolute;
    inset: 0 calc(var(--gutter) - var(--overhang)) 0 0;
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

  /* the hint: muted and small, by the tick labels. A y axis's sits in its
     tick-label column over the top labelled tick, in room the chart keeps
     above the plot (`MARK_ROOM`), so it never lands on a label and costs no
     column of its own (the maintainer's look, 2026-11-21, item 1); the x
     axis's sits after its last label in the strip under them */
  .hint {
    display: inline-block;
    padding: 0 2px;
    color: var(--muted);
    font-size: var(--text-sm);
    line-height: 18px;
    white-space: nowrap;
  }

  /* a scale mark: in the tick-label column, right-aligned with the labels,
     its top set from the top labelled tick (`markTop`) */
  .axis .hint {
    position: absolute;
    right: var(--inset);
    margin: 0;
    line-height: var(--mark-line);
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

  /* the Show choice in the legend: its word over the two views, stacked to
     the gutter's width, the labels' left edge its own */
  .gutter .vg {
    position: absolute;
    left: 8px;
    right: 4px;
    flex-direction: column;
    align-items: stretch;
    gap: 4px;
    color: var(--muted);
    font-size: var(--text-sm);
  }

  .gutter .vg .segmented {
    flex-direction: column;
  }

  /* the Preview label's slot while no preview is drawn: laid out, unseen */
  .gut.reserved {
    visibility: hidden;
  }

  .sw {
    flex: none;
    width: 16px;
    height: 12px;
    fill: none;
    stroke: currentColor;
    stroke-width: 1.6;
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

  /* a line's bar stands on its lens: `top` is the bar's foot */
  .selbar.peakbar {
    transform: translate(-50%, -100%);
  }

  .lensmark {
    position: absolute;
    z-index: 2;
    transform: translate(-50%, -50%);
    pointer-events: none;
    overflow: visible;
  }

  .lensmark path {
    fill: var(--plot-peak);
  }

  /* where a click would add a line (rule 9) */
  .lensmark.ghost path {
    fill: none;
    stroke: var(--plot-peak);
    stroke-width: 1.2;
    stroke-dasharray: 2 2;
  }

  /* the lens Option-click would remove (rule 9) */
  .lensmark.danger path {
    fill: var(--bad);
  }

  .host.onmark :global(.u-over) {
    cursor: grab;
  }

  .host.dragging :global(.u-over) {
    cursor: grabbing;
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
