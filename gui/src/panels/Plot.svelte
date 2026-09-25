<script lang="ts">
  /**
   * Observed, calculated, difference and reflection ticks.
   *
   * **The curves come once, at every channel** (WP-1461, D4).
   * `/api/result/curves` sends the pattern's every channel and the fit on the
   * channels it kept, as float64 arrays, and the figure zooms in the browser, so
   * a zoom fetches nothing. Which points a payload carries is the server's to
   * decide (`viz.compare.decimation_index`, past `CURVES_CEILING`); the chart
   * paints each pixel column's extremes of them, and the readout and every hit
   * test read every one.
   *
   * The figure is `rxplot.pattern` through `lib/pattern.ts`, which lays this
   * panel's own layers over it: the protocol's shading, the candidate's lines,
   * the picked peaks and their fitted profiles, and the hover ring. That module
   * is imported on the first draw, so a page with no project open fetches no
   * chart library.
   */
  import { untrack } from "svelte";

  import { ApiError } from "../api";
  import Exports from "./Exports.svelte";
  import { grabToleranceDeg, nearestPeak, type PeaksPayload } from "../lib/peaks";
  import {
    RESIDUAL_KINDS,
    SCALES,
    curveToggles,
    dataOnlyHidden,
    formatRegion,
    isDataOnly,
    mergeRegions,
    normalizeRegion,
    readout,
    residual,
    shows,
    toggleCurve,
    type CandidateOverlay,
    type Protocol,
    type Readout,
    type ResidualKind,
    type Scale,
    type Window,
  } from "../lib/plot";
  import type { Curves, Overlay, PatternChart } from "../lib/pattern";
  import type { Theme } from "../lib/theme";

  let {
    result,
    plotKey,
    zoom = null,
    error,
    theme = "light",
    peaks = null,
    peaksActive = false,
    hovered = null,
    candidate = null,
    candidatePicked = false,
    protocol = { limits: null, regions: [] },
    extent = null,
    channels = null,
    wavelengths = null,
    protocolError = "",
    busy = false,
    onhoverpeak = () => {},
    onaddpeak = () => {},
    onmovepeak = () => {},
    ontogglepeak = () => {},
    onremovepeak = () => {},
    onprotocol = () => {},
  }: {
    result: any;
    plotKey: number;
    /** a 2θ window another panel asked for (a report region, an unindexed peak);
     *  null means the whole pattern */
    zoom?: [number, number] | null;
    error: string;
    /** the resolved theme, and a *dependency of the knob effect*: the canvas
     *  keeps the colours it was painted with, so a theme change that only
     *  restyles the page leaves last theme's text on this plot (WP-1029 q) */
    theme?: Theme;
    /** the stored peak list with its raw pattern (WP-1027) — what lets this
     *  plot draw before any fit exists, which is indexing's whole situation */
    peaks?: PeaksPayload | null;
    /** the Peaks tab is showing: only then do clicks mean add/move/exclude —
     *  a stray click while reading the report must not edit a peak list */
    peaksActive?: boolean;
    /** the peak the pointer is over, wherever it is over it — one index in the
     *  shell, threaded to both panels, so the table and the plot point at the
     *  same line (WP-1032) */
    hovered?: number | null;
    /** the indexing candidate whose predicted lines are on the plot (WP-1211)
     *  — selected or merely hovered in the Peaks panel, which is why it arrives
     *  resolved rather than as an index: this component fetches nothing */
    candidate?: CandidateOverlay | null;
    /** whether a candidate is **selected**, as opposed to passed over by the
     *  pointer.  A separate question from which one is drawn, and it has to be:
     *  a selection clears the plot to the data, and if a preview did too then
     *  running the pointer down the candidate table would strobe the model on
     *  and off.  It stays true while a preview is showing over a selection,
     *  which is what makes that case swap the lines and nothing else. */
    candidatePicked?: boolean;
    /** what is being fitted, from `ProjectDoc` (WP-1033) — *not* a drawing
     *  choice: these persist on the verb and change Rwp, which is why they
     *  wear a different register from the knobs beside them */
    protocol?: Protocol;
    /** the measured 2θ range, which is what the shading has to reach past */
    extent?: [number, number] | null;
    /** `[fitted, measured]` channels — the check that a band is telling the
     *  truth, because a band over points still in the residual is worse than
     *  no band at all */
    channels?: [number, number] | null;
    /** the source's emission lines, primary first (WP-1213) — the readout says
     *  d = λ/(2 sin θ) with the first and names a candidate line with its own.
     *  The *instrument's*, off the settings document: the peak list carries a
     *  wavelength too and it is the one the picker ran at, which an instrument
     *  edit afterwards leaves behind. */
    wavelengths?: number[] | null;
    /** the last refusal from `POST /api/project`, in the verb's own words */
    protocolError?: string;
    busy?: boolean;
    onhoverpeak?: (index: number | null) => void;
    onaddpeak?: (twoTheta: number) => void;
    onmovepeak?: (index: number, twoTheta: number) => void;
    ontogglepeak?: (index: number) => void;
    onremovepeak?: (index: number) => void;
    onprotocol?: (patch: {
      two_theta_limits?: [number, number] | null;
      excluded_regions?: [number, number][];
    }) => void;
  } = $props();

  let node: HTMLDivElement | undefined = $state();
  /** The figure, its module and the payload it is drawing. Plain `let`s: they
   *  belong to the draw that reads them, and a reactive one would make every
   *  draw a reason to draw again. */
  let chart: PatternChart | null = null;
  let chartModule: typeof import("../lib/pattern") | null = null;
  let curves: Curves | null = null;
  let loadError = $state("");
  let shown = $state<{ n: number; total: number; lo: number; hi: number } | null>(null);
  /** Drawing choices, not facts about the fit — so neither is persisted, for
   *  WP-1015's reason one panel over: storing one would make a picture the
   *  project's opinion. */
  let kind = $state<ResidualKind>("weighted");
  let scale = $state<Scale>("linear");
  /** curves the user has switched off, by id — an *exception* list, so a curve
   *  this build does not know about yet still arrives drawn */
  let hidden = $state<string[]>([]);
  /** what was hidden before `data only` was pressed, so the second press puts
   *  the plot back rather than showing everything (WP-1210) */
  let beforeDataOnly = $state<string[] | null>(null);
  /** The payload in the readout's shape (`lib/pattern.ts:windowOf`).
   *
   *  `$state.raw`: a payload is replaced whole and never mutated, and a plain
   *  `$state` would proxy it, so the readout would read every array through a
   *  proxy on every pointer move. It is also what `held` and the payload a
   *  draw handed the figure have to be: one identity, never two (svelte says
   *  so in dev, `state_proxy_equality_mismatch`, WP-1213). */
  let held: Window | null = $state.raw(null);
  /** the toggles this payload offers — background only when there is one, one
   *  row per phase (WP-1032), the peak layer when a list exists (WP-1210) */
  const toggles = $derived(
    held
      ? curveToggles(held, residual(kind, held).label, {
          n: peaks?.peaks?.length ?? 0,
          groups: peaks?.groups?.length ?? 0,
          active: peaksActive,
        })
      : [],
  );
  const dataOnly = $derived(isDataOnly(toggles, hidden));
  /** The candidate overlay is drawn on the tab that can act on it, exactly as
   *  the peak layer is (WP-1210): the row that selects it is in the Peaks
   *  panel, so away from that tab there is nothing on screen the lines refer
   *  to.  Deriving it here rather than gating at each use is what makes the tab
   *  click *and* the hidden-curve handoff below both follow the tab. */
  const overlay = $derived(peaksActive ? candidate : null);
  /** …and the same gate on the selection, so leaving the tab puts the curves
   *  back as well as taking the lines off. */
  const picked = $derived(peaksActive && candidatePicked);

  /**
   * The 2θ under the pointer, or null while it is off the plot (WP-1213).
   *
   * The *only* hover state this panel keeps: the strip below is derived from
   * it, so a pointer move costs one recompute of a value object and no redraw
   * of the pattern at all — which is WP-1032's rule ("a hover link never
   * repaints the pattern") one step cheaper, because a strip is DOM.
   */
  let hoverAt = $state<number | null>(null);

  /** The radius every *non-destructive* pointer question here is asked with, in
   *  px: the readout's, the hover ring's, shift-toggle's and click-to-add's.
   *  WP-1027 made the **move** gesture's radius readable (`grabToleranceDeg`)
   *  because a drag edits a line; naming one does not, and at a survey view the
   *  fine radius is narrower than the channel spacing. */
  const PICK_RADIUS_PX = 10;

  /** What the strip prints. Derived, so the resting state and a reading are the
   *  same shape and the row of fields cannot reflow under the pointer. */
  const reading = $derived<Readout | null>(readout(held, hoverAt, {
    kind,
    wavelengths,
    peaks: peaks?.peaks ?? null,
    peaksActive,
    // the coarse 10-px radius `down`'s `click` aims with, so the strip names
    // the line a shift-click would take — one hit test, not a second opinion.
    // Not the move gesture's `grabToleranceDeg`: that one is deliberately fine
    // because a drag *edits*, and reading a line does not.
    peakTolerance: PICK_RADIUS_PX * degPerPx(),
    groups: peaks?.groups ?? null,
    candidate: overlay,
    candidateTolerance: PICK_RADIUS_PX * degPerPx(),
    hidden,
    // read as the pointer moves: a zoom re-bases the drawn Σχ² (`rxplot.chi2Base`),
    // and the pointer's own 2θ changes with it, so this is asked again
    chi2Base: chi2Base(),
  }));

  /** Hide everything but the data — or, pressed again, put back exactly what
   *  was on screen before, which is not the same as showing everything: a user
   *  who had already switched a phase's ticks off did not ask for them back. */
  function toggleDataOnly() {
    if (dataOnly) {
      hidden = beforeDataOnly ?? [];
      beforeDataOnly = null;
    } else {
      beforeDataOnly = hidden;
      hidden = dataOnlyHidden(toggles);
    }
  }

  /** The button. Pressing it by hand takes ownership of the state back from the
   *  overlay below, so a person who puts the curves up while a candidate is
   *  selected keeps them up when it is deselected. */
  function showDataOnly() {
    clearedForCandidate = false;
    toggleDataOnly();
  }

  /** Whether the *overlay's* arrival is what cleared the plot to the data.
   *
   *  There is one saved list and one path to it (`toggleDataOnly`), because two
   *  slots means four interleavings of two presses and no rule a reader could
   *  state. This flag is the rule: the press the overlay made, the overlay
   *  undoes; any other press is somebody else's. */
  let clearedForCandidate = $state(false);

  /**
   * "Through *just* the data" — selecting a candidate presses `data only`.
   *
   *  Through the button's own press rather than a mode of its own: an armed
   *  mode has to decide what a manual toggle underneath it means, which is the
   *  design WP-1210 declined for the same button. A plot already showing the
   *  data alone is left as it is and not taken over, so deselecting cannot
   *  un-clear a plot the overlay never cleared.
   *
   *  On `picked` and not on `overlay`: a hover preview draws lines without
   *  clearing anything, or running the pointer down the candidate table would
   *  strobe the model on and off once per row.
   */
  $effect(() => {
    const up = picked;
    untrack(() => {
      if (up && !clearedForCandidate && !dataOnly) {
        toggleDataOnly();
        clearedForCandidate = true;
      } else if (!up && clearedForCandidate) {
        if (dataOnly) toggleDataOnly();
        clearedForCandidate = false;
      }
    });
  });

  // -- the figure --------------------------------------------------------
  /** What the figure lays over the pattern, from this panel's props. `held` is
   *  read untracked: a new payload is drawn by the fetch that brought it, and
   *  tracked here it cost the knob effect a second paint of every fetch. */
  function overlayNow(): Overlay {
    return { protocol, extent, peaks: peaks?.peaks ?? null, groups: peaks?.groups ?? null,
             peaksActive, candidate: overlay, hidden, held: untrack(() => held) };
  }

  /** Which fetch is the latest. Two can be in flight (a run ending and a mask
   *  moving), and the older one landing last would draw the older curves, or
   *  build a second figure into the same host. */
  let fetchSeq = 0;

  /**
   * Fetch the curves once and draw them (D4). A zoom fetches nothing: the
   * payload is every channel, and the figure zooms in the browser. A payload
   * over the same channels keeps the reader's view, as a run landing should.
   */
  async function drawChart() {
    if (!node) return;
    const seq = ++fetchSeq;
    let mod: typeof import("../lib/pattern");
    let c: Curves;
    try {
      mod = chartModule ??= await import("../lib/pattern");
      c = await mod.fetchCurves();
    } catch (exc) {
      if (seq !== fetchSeq) return;
      shown = null;
      // an empty state (no project), not a failure (WP-1012's guard)
      if (!(exc instanceof ApiError && exc.empty)) loadError = (exc as Error).message;
      return;
    }
    if (seq !== fetchSeq || !node) return;
    loadError = "";
    const w = mod.windowOf(c);
    held = w;
    const tt = c.arrays.two_theta;
    // past `CURVES_CEILING` the server decimates, and `n_channels` is then the pattern's count
    shown = { n: tt.length, total: c.header.n_channels ?? tt.length,
              lo: tt[0] ?? 0, hi: tt[tt.length - 1] ?? 0 };
    if (!chart) {
      chart = new mod.PatternChart(node, c, overlayNow(), {
        scale: untrack(() => scale),
        kind: untrack(() => kind),
        labels: {
          y: () => (scale === "linear" ? "intensity" : `intensity (${scale})`),
          // an axis title names what is plotted: on the raw view that is each
          // peak group's own residual, since there is no model to take one from,
          // and nothing where that residual is not drawn (`PatternChart.groupResidual`)
          resid: () => (!held ? "" : !held.raw ? residual(kind, held).title
            : peaksActive && peaks?.groups?.length && shows(hidden, "peakfit")
              ? "(y − fit)/σ per group" : ""),
        },
      });
      applied = untrack(() => ({ kind, scale, theme }));
      chart.fig.onCursor = (hit) => hovering(hit ? hit.x : null);
      chart.fig.onSelect = (lo, hi) => { if (arm) selected(lo, hi); };
      chart.fig.setMode(arm ? "select" : "zoom");
    } else {
      chart.setCurves(c, mod.sameGrid(curves, c));
      chart.update(overlayNow());
    }
    curves = c;
    if (pendingZoom) {
      chart.fig.unpin();
      chart.fig.setX(...pendingZoom);
      pendingZoom = null;
    }
  }

  /** The knobs the figure was last drawn with, so a knob effect applies only what moved. */
  let applied: { kind: ResidualKind; scale: Scale; theme: Theme } | null = null;
  /** A window another panel asked for before the figure existed to show it. */
  let pendingZoom: [number, number] | null = null;

  /** The curves are gone (no project), and so is everything drawn from them:
   *  WP-1012's rule, applied to the copy in hand, so a knob or a theme change
   *  cannot redraw a state the project is no longer in. */
  function dropChart() {
    fetchSeq++;
    chart?.destroy();
    chart = null;
    curves = null;
    applied = null;
    held = null;
    shown = null;
  }

  /**
   * The pointer's 2θ, which is the whole of this panel's hover state, and the
   * peak link it drives. The link is `nearestPeak` at the coarse radius a
   * shift-click obeys (`PICK_RADIUS_PX`), and it is answered on every move while
   * the layer is up, `null` included, or the ring and the lit row would stay on
   * a line the pointer has left.
   */
  function hovering(x: number | null) {
    hoverAt = x;
    if (peaksActive) {
      onhoverpeak(x !== null && peaks?.peaks?.length
        ? nearestPeak(peaks.peaks, x, PICK_RADIUS_PX * degPerPx())
        : null);
    }
  }

  // -- pointer interactions (WP-1027) ---------------------------------
  /** pixel → 2θ through the figure's own x, or null off its plot area */
  function thetaOf(clientX: number): number | null {
    return chart?.thetaOf(clientX) ?? null;
  }

  function degPerPx(): number {
    return chart?.degPerPx() ?? 0.01;
  }

  /** What the drawn Σχ² curve has subtracted at the current zoom. */
  function chi2Base(): number {
    return chart?.fig.chi2Base() ?? 0;
  }

  /** The gesture in flight. `move` is the hit inside the *readable* grab
   *  radius (`grabToleranceDeg` — min(10 px, 1.5× median FWHM)); only that
   *  hit takes the pointer from the figure, so at the survey view — where a
   *  line is subpixel and 10 px spans two degrees — a drag stays a zoom
   *  instead of silently moving a line (measured: a zoom drag starting 0.9°
   *  from a marker moved it 11°).  `click` is the coarse 10-px hit that the
   *  non-destructive gestures (shift-toggle) still aim with. */
  let gesture: { move: number; click: number; startX: number; moved: boolean } | null = null;

  /**
   * The range gesture, and why it is a *mode* rather than a fourth drag
   * meaning (WP-1033).
   *
   * The canvas already carries five pointer meanings — peak-add, peak-move,
   * shift-toggle, right-click-remove and the zoom drag — and WP-1027 measured
   * what a sixth costs when two overlap: a 10 px grab radius is ±1.9° at the
   * survey view, so a zoom drag starting 0.9° from a marker silently moved a
   * line 11°.  The repair there was to make the radius *readable*
   * (`grabToleranceDeg`), so an ambiguous drag falls through to the harmless
   * verb.
   *
   * Here there is no radius to derive, because a region drag is ambiguous with
   * a zoom drag **everywhere** — same button, same shape, same distances.  So
   * the ambiguity is removed rather than arbitrated: arming is an explicit
   * click on a named control, it hands the drag to the figure's select mode
   * (x only, and zooming nothing), it *suspends* the peak verbs while it
   * holds, and it disarms itself after one selection. Nothing is momentary
   * except the mode the user asked for, and an un-armed drag still zooms,
   * which is the harmless thing.
   *
   * The non-pointer routes are the typed boxes in the strip below and the
   * `.rxt` document's `limits`/`excluded` lines — both of which existed
   * before this gesture did.
   */
  let arm = $state<null | "limits" | "exclude">(null);

  function selected(a: number, b: number) {
    const pair = normalizeRegion([a, b]);
    const which = arm;
    arm = null;   // one drag, one region: the mode does not linger
    if (!pair || !which) return;
    if (which === "limits") onprotocol({ two_theta_limits: pair });
    else onprotocol({ excluded_regions: mergeRegions(protocol.regions, pair) });
  }

  function down(ev: PointerEvent) {
    // armed: the drag is the figure's select box, and every peak verb stands down
    if (arm) return;
    if (!peaksActive || !peaks?.peaks || ev.button !== 0) return;
    const tt = thetaOf(ev.clientX);
    if (tt === null) return;
    const perPx = degPerPx();
    const move = nearestPeak(peaks.peaks, tt, grabToleranceDeg(peaks.peaks, perPx));
    const click = nearestPeak(peaks.peaks, tt, PICK_RADIUS_PX * perPx);
    gesture = { move: move ?? -1, click: click ?? -1, startX: ev.clientX, moved: false };
    if (move !== null) {
      // This gesture is a peak drag, not a zoom. A pointerdown's default is the
      // mouse events it would go on to fire, and uPlot's drag listens for
      // those, so cancelling it here, in the capture phase, keeps the drag ours.
      ev.stopPropagation();
      ev.preventDefault();
    }
  }

  function moved(ev: PointerEvent) {
    if (gesture && Math.abs(ev.clientX - gesture.startX) > 3) gesture.moved = true;
  }

  function up(ev: PointerEvent) {
    const g = gesture;
    gesture = null;
    if (arm || !g || !peaksActive || !peaks?.peaks) return;
    const tt = thetaOf(ev.clientX);
    if (tt === null) return;
    if (g.moved) {
      if (g.move >= 0) onmovepeak(g.move, tt);
      // a drag that started merely *near* a marker was never captured, so the
      // figure zoomed with it — nothing to do here
    } else if (ev.shiftKey) {
      if (g.click >= 0) ontogglepeak(g.click);
    } else if (g.click < 0) {
      // a plain click on empty space adds a line; near a marker it is
      // ambiguous, and an ambiguous click must not edit anything
      onaddpeak(tt);
    }
  }

  /**
   * Right-click **removes** the line under the pointer (WP-1032).
   *
   * It used to refit the line's whole group through a `window.prompt` for a
   * component count — a modal in the one gesture that has no undo, on a verb the
   * table's `↻` already carries.  Remove is the destructive edit a pointer
   * should be able to make directly; the panel's `×` is its non-pointer route,
   * and the coarse 10-px radius is the same one shift-toggle aims with, because
   * the precision of a *marker* hit does not come from the pixel radius.
   */
  function context(ev: MouseEvent) {
    if (arm || !peaksActive || !peaks?.peaks) return;
    const tt = thetaOf(ev.clientX);
    if (tt === null) return;
    const hit = nearestPeak(peaks.peaks, tt, PICK_RADIUS_PX * degPerPx());
    if (hit === null) return;
    ev.preventDefault();
    onremovepeak(hit);
  }

  $effect(() => () => {
    // a fetch still in flight then lands on a stale sequence, and builds no
    // figure into a host that is gone
    fetchSeq++;
    chart?.destroy();
    chart = null;
  });

  /** The protocol as a *primitive*, so this panel does not refetch on every
   *  ui-only PATCH — the effect-reads-the-project-object trap WP-1027's second
   *  pass recorded, one panel over. */
  const protocolKey = $derived(JSON.stringify([protocol.limits, protocol.regions]));
  /** …and the same trick for the measured extent, for the same reason: both are
   *  `$derived` off `project`, so both arrive new-but-equal on every settings
   *  PATCH, and an effect keyed on the object repaints for nothing. */
  const extentKey = $derived(JSON.stringify(extent));
  /** A pattern to draw before any fit, as a boolean so a peak edit is not a change. */
  const hasPattern = $derived(!!peaks?.pattern?.two_theta?.length);

  // -- the typed route (WP-1033) -------------------------------------
  // Empty means "no limit", which is why the placeholder is the measured
  // extent rather than a zero: a blank box says the whole pattern is fitted,
  // and that is also what `limits none` means in the .rxt document.
  let loText = $state("");
  let hiText = $state("");
  $effect(() => {
    void protocolKey;
    loText = protocol.limits ? String(protocol.limits[0]) : "";
    hiText = protocol.limits ? String(protocol.limits[1]) : "";
  });

  /** Send the typed range. A half-filled or unparseable pair is sent as it
   *  reads and refused by the document's own validator — this client has no
   *  opinion about validity, which is WP-1013's rule for the text pane and the
   *  same rule here: two validators would be two answers. */
  function applyLimits() {
    if (!loText.trim() && !hiText.trim()) {
      onprotocol({ two_theta_limits: null });
      return;
    }
    const num = (text: string) => (text.trim() === "" ? NaN : Number(text));
    onprotocol({ two_theta_limits: [num(loText), num(hiText)] });
  }

  /** The `zoom` prop this panel has already acted on, by **identity**.
   *
   *  A window from another panel is a *request*, and every other reason an
   *  effect here runs is not — so the two have to be told apart, and the
   *  array's identity is what does it: the shell writes a fresh pair per click,
   *  so clicking the same region twice asks twice. Deliberately not `$state`. */
  let asked: [number, number] | null | undefined;

  // Three effects, and which one a change wakes is the design.
  //
  // **Fetch** on what moves the curves: a run, a move in the history, the mask
  // (the masked channels are the payload's `kept`). Not on a peak edit, which
  // the layers redraw, and never on a zoom.
  $effect(() => {
    void plotKey;
    void protocolKey;
    void result;
    const show = !!result || hasPattern;
    untrack(() => (show ? drawChart() : dropChart()));
  });

  // **A window another panel asked for** is an axis move and nothing else,
  // with y fitted to what is there: the payload is every channel already, so
  // a report region arrives at full resolution with no fetch.
  $effect(() => {
    const request = zoom !== asked ? zoom : null;
    asked = zoom;
    if (!request) return;
    untrack(() => {
      if (!chart) {
        pendingZoom = request;
        return;
      }
      chart.fig.unpin();
      chart.fig.setX(...request);
    });
  });

  // **A knob** applies what moved: a residual is new numbers for one pane, a
  // scale rebuilds the main one (the module's finding 5), and the rest repaint.
  // uPlot paints once a tick however many of these ask, except the theme, which
  // waits a microtask for the shell to stamp it (`PatternChart.retheme`).
  //
  // The peak layer and the candidate's lines are inputs here because they are
  // drawn only on the Peaks tab (WP-1210, WP-1211): leaving it has to take them
  // off, and that is a repaint, never a refetch.
  $effect(() => {
    const k = kind, s = scale, h = hidden, t = theme;
    // The protocol and the extent go by value: each is a new object on every
    // settings PATCH, and keyed on the object this effect repainted for two
    // numbers that did not change (WP-1212).
    void protocolKey;
    void extentKey;
    void peaks;
    void peaksActive;
    void overlay;
    const o = untrack(overlayNow);
    untrack(() => {
      if (!chart || !applied) return;
      if (applied.kind !== k) chart.fig.setResidual(k);
      if (applied.scale !== s) chart.fig.setY(s === "linear" ? "lin" : s);
      if (applied.theme !== t) void chart.retheme();
      applied = { kind: k, scale: s, theme: t };
      chart.fig.setHidden(h);
      chart.update(o);
    });
  });

  // The hover link is *not* in the effect above, and that is the whole point:
  // a mouse move moves one DOM ring and never repaints the pattern (WP-1032).
  $effect(() => {
    const row = hovered === null ? undefined : peaks?.peaks?.find((p) => p.index === hovered);
    untrack(() => chart?.ring(row?.two_theta ?? null));
  });

  // …and arming is not in it either, for the same reason one rank up: the drag
  // mode is the figure's, so arming redraws nothing (WP-1212 counted it as two
  // of the four repaints an exclude drag cost, under plotly).
  $effect(() => {
    const mode = arm ? "select" : "zoom";
    untrack(() => chart?.fig.setMode(mode));
  });
</script>

<svelte:window onpointermove={moved} onpointerup={up}
  onkeydown={(ev) => { if (ev.key === "Escape" && arm) arm = null; }} />

<section>
  {#if error}
    <p class="hint bad">{error}</p>
  {:else if !result && !peaks?.peaks?.length}
    <p class="hint muted">
      No fitted curves yet. Press <strong>Run</strong> — or, if you just moved the
      history, run again: a checkout restores parameter values, not a fit.
    </p>
  {:else if !result && peaksActive}
    <p class="hint muted">Raw pattern — no fit yet, which is when peaks are picked.</p>
  {:else if loadError}
    <p class="hint bad">{loadError}</p>
  {/if}
  <!-- The gestures, stated whenever the tab that owns them is showing — fit or
       no fit (WP-1032).  This line used to render only in the *raw* state, so
       the moment a fit existed the pointer verbs were undocumented on screen.
       Each one names its non-pointer route beside it, which is WP-1027's rule
       made visible rather than only true. -->
  {#if arm}
    <!-- While a range gesture is armed it owns the canvas, and this line is
         where that is said: the peak verbs are suspended, not competing. -->
    <p class="hint arming">
      <strong>Drag on the plot</strong> to {arm === "limits"
        ? "set the fitted 2θ range" : "exclude a 2θ region"}
      <span class="muted">— the peak gestures are suspended; Esc cancels</span>
    </p>
  {:else if peaksActive && peaks?.peaks?.length}
    <p class="hint muted gestures">
      <strong>Click</strong> to add a line <span class="muted">(or the panel's 2θ box)</span> ·
      <strong>drag</strong> a marker to move it <span class="muted">(or the Text pane's 2θ column)</span> ·
      <strong>shift-click</strong> to exclude <span class="muted">(or the row's checkbox)</span> ·
      <strong>right-click</strong> to remove <span class="muted">(or the row's ×)</span>
    </p>
  {/if}
  <!-- role: the div is a pointer-driven editing surface when the Peaks tab is
       active.  Every verb has a non-pointer route too — the line above names
       each — so the pointer path is an accelerator, not the only way in. -->
  <div class="plot" class:armed={arm !== null} role="application"
    aria-label="diffraction pattern"
    bind:this={node} onpointerdowncapture={down} oncontextmenu={context}></div>
  <!-- The readout (WP-1213), under the plot rather than over it.  The report
       was "the tooltip frequently covers a large part of the data", and plotly
       offered no positioning for its unified box beyond `hoverlabel.align` — so
       the box was deleted rather than moved, and everything it said is here,
       beside the plot's other control rows.  The chart draws no box either:
       a tooltip is a capability it has, and not one this panel takes.

       Every field keeps its slot while the pointer is off the plot and prints
       an em dash: a strip that grew fields on hover would resize the canvas
       above it once per entry, and the value widths are fixed in `ch` below so
       the wrap points cannot move under the pointer either.  Which fields
       there are is a property of the payload and the tab — never of where the
       pointer is (`lib/plot.ts:readout`). -->
  {#if reading}
    <div class="readout" role="group" aria-label="under the pointer">
      <span class="field">
        <span class="key">2θ</span>
        <span class="val mono tabular">{reading.position}</span>
      </span>
      <span class="field">
        <span class="key">d</span>
        <span class="val mono tabular">{reading.d}</span>
      </span>
      {#each reading.rows as row (row.id)}
        <span class="field"
          class:wide={row.id === "peaks" || row.id === "candidate"
                      || row.id.startsWith("ticks:")}>
          <!-- the mark's own ink, so the strip says which curve is which twice
               over: `ReadoutInk` is `curveColors`' key set, and a key is the
               `--plot-*` token's suffix by construction (WP-1210's rule — a
               plot mark has a token of its own) -->
          <span class="key" title={row.label}
            style:color={row.ink ? `var(--plot-${row.ink})` : null}>{row.label}</span>
          <span class="val mono tabular">{row.value}</span>
        </span>
      {/each}
    </div>
  {/if}
  {#if shown}
    <div class="knobs">
      <div class="segmented" role="group" aria-label="residual">
        {#each RESIDUAL_KINDS as entry (entry.id)}
          <button class:on={kind === entry.id} onclick={() => (kind = entry.id)}
            title={entry.title}>{entry.label}</button>
        {/each}
      </div>
      <div class="segmented" role="group" aria-label="intensity scale">
        {#each SCALES as entry (entry.id)}
          <button class:on={scale === entry.id} onclick={() => (scale = entry.id)}
            title={entry.title}>{entry.label}</button>
        {/each}
      </div>
      <!-- Which curves are drawn.  Unpersisted, like the two knobs beside it:
           a drawing choice is not the project's opinion (WP-1015/1029). -->
      {#if toggles.length > 1}
        <div class="segmented curves" role="group" aria-label="curves">
          {#each toggles as curve (curve.id)}
            <!-- an absent curve is listed and disabled, its title the reason:
                 "where did my markers go" has an answer, and a missing button
                 is not it (WP-1210) -->
            <button class:on={shows(hidden, curve.id) && !curve.absent}
              disabled={!!curve.absent}
              onclick={() => (hidden = toggleCurve(hidden, curve.id))}
              title={curve.absent
                     ? `${curve.title} — ${curve.absent}`
                     : `${curve.title} — click to ${shows(hidden, curve.id) ? "hide" : "show"}`}
              >{curve.label}</button>
          {/each}
        </div>
        <!-- one press to the data and back again.  A `.segmented` of one would
             be a choice of one; this is an action, so it is a ghost button. -->
        <button class="ghost" class:on={dataOnly} onclick={showDataOnly}
          title={dataOnly
                 ? "put the other curves back"
                 : "hide every curve but the measured points"}>data only</button>
      {/if}
      <Exports figure={() => chart?.fig ?? null} name={() => "pattern"} />
      <!-- Past `CURVES_CEILING` the server decimates, and the line says so: a
           sample drawn without saying so would read as every channel. -->
      <p class="hint muted tabular">
        {#if shown.n < shown.total}
          {shown.n} of {shown.total} channels, {shown.lo.toFixed(3)}–{shown.hi.toFixed(3)}°
          · min/max decimated server-side
        {:else}
          {shown.total} channels, {shown.lo.toFixed(3)}–{shown.hi.toFixed(3)}°
        {/if}
      </p>
      <!-- The overlay has no toggle (its control is the candidate row), so this
           is where it says it is on screen — and where a thinned set admits it.
           A sample drawn without saying so would read as "these are the lines
           this cell predicts", which is the one claim the picture must not
           make falsely. -->
      {#if overlay}
        <p class="hint muted tabular candidate">
          {overlay.two_theta.length === overlay.n_total
            ? `${overlay.n_total} predicted lines`
            : `${overlay.two_theta.length} of ${overlay.n_total} predicted lines,
               sampled evenly — this cell predicts more than can be drawn`}
          · {overlay.label}
        </p>
      {/if}
    </div>
  {/if}
  <!-- The protocol strip (WP-1033), and its separation from the knobs above is
       the point rather than a layout preference: those are drawing choices,
       session-local and unpersisted, while everything here changes what is
       fitted, persists in `project.json` on the verb, and moves Rwp.  Two kinds
       of knob on one plot; if they wore the same clothes a user could not tell
       which one changes the answer. -->
  {#if extent}
    <div class="protocol" role="group" aria-label="what is fitted">
      <label class="field" title="the lowest 2θ the fit includes; empty means the
        whole measured pattern. Channels outside are dropped from the residual,
        so they are in no Rwp or χ² either.">
        <span>Fitted range</span>
        <input class="tabular" type="text" inputmode="decimal" bind:value={loText}
          placeholder={extent[0].toFixed(3)} disabled={busy}
          onkeydown={(ev) => { if (ev.key === "Enter") applyLimits(); }} />
      </label>
      <label class="field" title="the highest 2θ the fit includes; empty means the
        whole measured pattern">
        <span>–</span>
        <input class="tabular" type="text" inputmode="decimal" bind:value={hiText}
          placeholder={extent[1].toFixed(3)} disabled={busy}
          onkeydown={(ev) => { if (ev.key === "Enter") applyLimits(); }} />
      </label>
      <button class="ghost" onclick={applyLimits} disabled={busy}
        title="send the typed range — project.doc.two_theta_limits">Set</button>
      <button class="ghost" onclick={() => onprotocol({ two_theta_limits: null })}
        disabled={busy || !protocol.limits}
        title="fit the whole measured pattern again">All</button>

      <div class="segmented arm" role="group" aria-label="select on the plot">
        <button class:on={arm === "limits"} disabled={busy}
          onclick={() => (arm = arm === "limits" ? null : "limits")}
          title="then drag on the plot to set the fitted range — the peak
            gestures stand down while this is armed, and Esc cancels"
          >⇥ range</button>
        <button class:on={arm === "exclude"} disabled={busy}
          onclick={() => (arm = arm === "exclude" ? null : "exclude")}
          title="then drag on the plot to exclude that 2θ region from the
            residual — the peak gestures stand down while this is armed"
          >✂ exclude</button>
      </div>

      {#if protocol.regions.length}
        <ul class="regions" aria-label="excluded regions">
          {#each protocol.regions as region, i (formatRegion(region))}
            <li>
              <span class="pill tabular"
                title="excluded from the residual">{formatRegion(region)}</span>
              <button class="ghost" disabled={busy}
                aria-label="stop excluding {formatRegion(region)}"
                title="fit these channels again"
                onclick={() => onprotocol({
                  excluded_regions: protocol.regions.filter((_, k) => k !== i) })}
                >×</button>
            </li>
          {/each}
        </ul>
      {/if}

      <!-- The check that the shading is telling the truth, on screen rather
           than only in the acceptance run: a band over channels still in the
           residual is worse than no band at all. -->
      {#if channels}
        <p class="hint muted tabular count">
          {channels[0].toLocaleString()} of {channels[1].toLocaleString()} channels fitted
        </p>
      {/if}
      {#if held?.stale}
        <p class="hint warn">
          the curves shown were fitted over a different set of channels — re-run
        </p>
      {/if}
      {#if protocolError}
        <p class="hint bad">{protocolError}</p>
      {/if}
    </div>
  {/if}
</section>

<style>
  section {
    flex: 1 1 auto;
    display: flex;
    flex-direction: column;
    min-width: 0;
    padding: 8px 10px;
  }

  /* The figure's host (WP-1461). Its panes are sized from this box's height,
     so the height has to come from the column and never from the panes, or
     each resize would feed the next. */
  .plot {
    flex: 1 1 0;
    min-height: 240px;
    overflow: hidden;
  }

  /* The live gesture dressed as the thing it is about to become (WP-1212): an
     armed drag means "exclude this range", so its box is drawn as the shading
     and dotted edges the exclusion will leave behind. */
  .plot :global(.u-select) {
    background: var(--plot-mask);
    border-left: 1px dotted var(--muted);
    border-right: 1px dotted var(--muted);
  }

  /* An armed range gesture has to say so **where the gesture is**, since a
     select drag and a zoom drag are otherwise pointer-identical (WP-1044). */
  .plot.armed :global(.u-over) {
    cursor: col-resize;
  }

  /* The hover link's ring: a DOM mark over the canvas, so moving it paints no pattern. */
  .plot :global(.rx-ring) {
    position: absolute;
    width: 16px;
    height: 16px;
    margin: -8px 0 0 -8px;
    box-sizing: border-box;
    border: 2px solid;
    border-radius: 50%;
    pointer-events: none;
  }

  /* The readout strip (WP-1213).  Not a register: it is one panel's row of
     labelled numbers, and what keeps it from being a fourth kind of chip is
     that it has no box — the plot above it is the thing being annotated.

     The widths are the load-bearing part.  Mono digits make `ch` exact, so a
     `min-width` per field freezes the wrap points: the strip's height is then
     a function of the payload, the tab and the column width, and never of what
     the pointer happens to be over.  Without them a peak coming into reach
     rewrapped the row, which resizes the canvas — the jitter WP-1212 removed,
     arriving through its own repair. */
  .readout {
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 2px 12px;
    padding: 4px 0 2px;
    font-size: var(--text-sm);
    color: var(--muted);
  }

  .readout .field {
    display: inline-flex;
    align-items: baseline;
    gap: 4px;
  }

  /* a phase name is arbitrarily long, and it is the label of its own tick row
     — clip the label, not the strip (the curves toggle's rule, one row down) */
  .readout .key {
    max-width: 100px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .readout .val {
    color: var(--fg);
    min-width: 8ch;
  }

  /* the fields that carry a sentence rather than a number: a picked line with
     its esd and relative intensity, a candidate's hkl with its λ, and a
     phase's nearest reflection with the offset to it (WP-1438).

     22ch has to be a *bound* to be a floor at all: content wider than its
     floor grows the field, the strip rewraps mid-sweep, and that is the
     jitter this min-width exists to stop.  The widest an index gets is set by
     d*max = 2 sinθ/λ, so a 10 Å cell at 150° 2θ on Cu Kα reaches 12 —
     `(−12 −4 −10)` is 12 characters, a signed offset up to 99° is 9, and the
     space between them makes 22.  Measured on the NAC example over 2–24° the
     index runs 7–8 characters, so the floor is what is drawn.  Past the bound
     the field still grows, which is only where it already did: a phase whose
     nearest line is a hundred degrees away. */
  .readout .field.wide .val {
    min-width: 22ch;
  }

  .knobs {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
  }

  /* a phase name is arbitrarily long — clip the button, not the row */
  .segmented.curves button {
    max-width: 120px;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .gestures strong {
    font-weight: 600;
    color: var(--fg);
  }

  /* The overlay's own line, in the overlay's own ink: it is the only thing in
     the knob row that names a layer nothing there can switch off, so it has to
     be attributable to the lines on the plot at a glance.  A whole row of its
     own because the point count above it is about the *data*. */
  .candidate {
    flex-basis: 100%;
    color: var(--plot-candidate);
  }

  .arming {
    color: var(--accent);
  }

  .arming strong {
    color: var(--accent);
  }

  /* A register of its own, and deliberately not `.knobs`: a rule above the
     strip and typed fields inside it read as "settings", where a segmented
     button reads as "view".  The only segmented control here arms a *gesture*,
     which is a view of the same setting, not a fourth drawing choice. */
  .protocol {
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
    margin-top: 6px;
    padding-top: 6px;
    border-top: 1px solid var(--line);
    /* a strip of controls, so everything on it is control-sized — including
       the channel count, which is a readout on the strip rather than prose
       about it (it read a step larger than the fields it belongs to) */
    font-size: var(--text-sm);
  }

  .field {
    display: flex;
    align-items: center;
    gap: 5px;
    color: var(--muted);
  }

  .field input {
    width: 76px;
    font: var(--mono);
    padding: 2px 5px;
    border: 1px solid var(--line);
    border-radius: 4px;
    background: var(--panel);
    color: var(--fg);
  }

  .regions {
    display: flex;
    align-items: center;
    gap: 6px;
    flex-wrap: wrap;
    list-style: none;
    margin: 0;
    padding: 0;
  }

  /* the readout and the verb that acts on it, side by side: a pill is
     non-interactive, so the × is a control of its own rather than one inside it */
  .regions li {
    display: flex;
    align-items: center;
    gap: var(--s1);
  }

  .count {
    margin-left: auto;
  }

  .warn {
    color: var(--warn);
  }

  .bad {
    color: var(--bad);
  }
</style>
