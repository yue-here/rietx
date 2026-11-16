/**
 * What the pattern plot draws, as pure functions (WP-1029).
 *
 * Two knobs the plot never had: **which residual** and **which y-scaling**.
 * Both are drawing choices, so both live in the client — but the residuals
 * themselves do not: `/api/result/curves` sends all three, because what a
 * residual *is* depends on whether the file brought an esd column, and because
 * cumulative χ² has to be accumulated over every channel by the server, which
 * holds them all (WP-1461: a zoom re-bases it, `rxplot.chi2Base`). This module
 * only *chooses*.
 */

import {
  formatHkl,
  formatIntensity,
  formatPosition,
  intensityScale,
  nearestPeak,
  type GroupCurve,
  type PeakRow,
} from "./peaks";
import { formatValue } from "./table";

export type ResidualKind = "delta" | "weighted" | "cumulative";
export type Scale = "linear" | "sqrt" | "log";

/**
 * The five curve colours, read from the custom properties `app.css` themes.
 *
 * The plot samples these at *draw* time — a theme change restyles the page by
 * CSS alone, but a canvas keeps whatever colours it was painted with, which is
 * why the panel repaints on the resolved theme (WP-1029 q) and why no hex may
 * live in the component: a fixed `#1f5fa8` difference curve was near-invisible
 * on the dark surface, and correct repainting cannot fix a colour that never
 * changes.  The fallbacks are the light values, for a page with no stylesheet
 * (jsdom); `read` is injected so this stays a pure function.
 */
export function curveColors(read: (name: string) => string): {
  obs: string; calc: string; bkg: string; diff: string; zero: string;
  mask: string; edge: string; peak: string; peakfit: string; candidate: string;
  phase: string[];
} {
  const pick = (name: string, fallback: string) => read(name).trim() || fallback;
  return {
    obs: pick("--plot-obs", "#1c1917"),
    calc: pick("--plot-calc", "#c65d0a"),
    bkg: pick("--plot-bkg", "#b5793a"),
    diff: pick("--plot-diff", "#6b6259"),
    zero: pick("--plot-zero", "#cfcfcf"),
    // The peak layer's two (WP-1210).  It had none: the markers took `--accent`
    // and the fitted curve `--bad`, which on the light theme *are* `--plot-diff`
    // and `--plot-calc` to the last digit — so the picked-peak fit and the model
    // were one colour, which is what the report said.  One hue family and two
    // tones, because the layer is one thing; what tells the marks apart is the
    // mark.  Each value's separation from every other plot colour is asserted
    // in `tests/test_gui_palette.py`, against the same OKLab floor the phase
    // palette uses.
    peak: pick("--plot-peak", "#0072b2"),
    peakfit: pick("--plot-peakfit", "#6f83e6"),
    // The candidate overlay's one (WP-1211).  It could not share the peak
    // layer's: both are up on the same tab at the same time, and telling them
    // apart *is* the question — which of the picked lines does this cell
    // account for.
    candidate: pick("--plot-candidate", "#1a8f45"),
    // the two protocol colours (WP-1033).  `mask` is a wash rather than a
    // curve colour because what it marks is *absence from the residual*, and
    // `edge` is the boundary, which has to stay readable when the wash is
    // off-screen — a fit range shows only its edges once you zoom inside it.
    mask: pick("--plot-mask", "#1c191714"),
    edge: pick("--muted", "#6b6259"),
    // One colour per phase, keyed by the phase and not by the trace (WP-1438).
    // Before this the tick traces carried no colour at all, so plotly assigned
    // from its own cycle by position in the trace array — and every trace ahead
    // of them is conditional, so a phase's row changed colour when the stage
    // freed the background, when a reader toggled a curve off in the legend,
    // and on a pattern with an excluded region. `viz/theme.py` says which four
    // and why; these do not vary with the theme, so the fallbacks are the
    // values rather than a second light palette.
    phase: [pick("--phase-0", "#009e73"), pick("--phase-1", "#cc79a7"),
            pick("--phase-2", "#56b4e9"), pick("--phase-3", "#f0e442")],
  };
}

/**
 * The curves as the readout reads them (`lib/pattern.ts:windowOf`): the fitted
 * channels on the arrays, one value per channel, and the masked ones on their
 * own arm. Typed arrays, since they are the payload's own views (WP-1461, D4).
 */
export interface Window {
  /** the pattern before any fit: no model, and no residual but the peak groups' */
  raw?: boolean;
  two_theta: ArrayLike<number>;
  y_obs: ArrayLike<number>;
  y_calc?: ArrayLike<number>;
  y_background?: ArrayLike<number>;
  delta?: ArrayLike<number>;
  delta_raw?: ArrayLike<number>;
  cumulative_chi2?: ArrayLike<number>;
  /** σ was *measured* (the file's esd column), not the Poisson fallback */
  weighted?: boolean;
  /** the measured points the protocol masks — never in the residual, and not
   *  in the result at all, which is why the payload's `kept` sets them apart */
  excluded?: { two_theta: ArrayLike<number>; y_obs: ArrayLike<number> };
  n_excluded?: number;
  /** the curves on screen were fitted over a different channel set */
  stale?: boolean;
  /** every emission line's reflection positions, per phase */
  ticks?: Record<string, number[]>;
  /** which reflection each entry of `ticks` is, pinned to it by index */
  tick_hkl?: Record<string, number[][]>;
}

/**
 * What is being fitted — the protocol, not a drawing choice (WP-1033).
 *
 * Both fields are `ProjectDoc`'s, both persist on the verb that sets them, and
 * both change the answer: excluded channels never enter the residual, so they
 * never enter Rwp or χ² either. That is the whole reason they may not wear the
 * same clothes as the residual selector and the intensity scale beside them —
 * those are session-local and deliberately unpersisted (WP-1015), because
 * storing one would make a *picture* the project's opinion.
 */
export interface Protocol {
  limits: [number, number] | null;
  regions: [number, number][];
}

/** A band of 2θ the protocol does not fit, or the dotted edge of one. */
export type MaskShape =
  | { type: "rect"; x0: number; x1: number; color: string }
  | { type: "line"; x: number; color: string };

/**
 * What shades the channels the protocol does not fit, in 2θ.
 *
 * The chart's shading layer draws each band the full height of every pane:
 * an excluded channel is missing from the residual, not only from the pattern,
 * and a band in data coordinates would change shape with the intensity scale.
 *
 * **Every shape is clipped to the measured range**, because outside the
 * measured pattern there are no channels to exclude. It was a browser finding
 * first: under plotly a shape took part in the autorange, and bands drawn past
 * the data *became* the range, −40 to 100 on the 0.5–59.99° NAC pattern.
 *
 * The layer runs under the curves: a band that dimmed the points it covers
 * would be saying something about the data rather than about the protocol.
 */
export function maskShapes(protocol: Protocol, extent: [number, number],
                           colors: { mask: string; edge: string }): MaskShape[] {
  const [lo, hi] = extent;
  const band = (x0: number, x1: number): MaskShape | null => (x1 <= lo || x0 >= hi ? null
    : { type: "rect", x0: Math.max(x0, lo), x1: Math.min(x1, hi), color: colors.mask });
  const edge = (x: number): MaskShape | null => (x < lo || x > hi ? null
    : { type: "line", x, color: colors.edge });
  const shapes: (MaskShape | null)[] = [];
  if (protocol.limits) {
    const [a, b] = protocol.limits;
    shapes.push(band(lo, a), band(b, hi), edge(a), edge(b));
  }
  for (const [a, b] of protocol.regions) shapes.push(band(a, b), edge(a), edge(b));
  return shapes.filter((x): x is MaskShape => x !== null);
}

/** A drawn interval as an ordered pair, or null if it is a point. */
export function normalizeRegion(pair: [number, number]): [number, number] | null {
  const [a, b] = pair;
  if (!Number.isFinite(a) || !Number.isFinite(b) || a === b) return null;
  return a < b ? [a, b] : [b, a];
}

/**
 * The region list with `add` folded in: sorted, and with overlaps merged.
 *
 * Merging is a **presentation** decision that provably changes nothing about
 * what is fitted — `PatternData.in_range_mask` removes the union of the
 * regions, so two overlapping entries and their merged one mask exactly the
 * same channels (asserted that way in `plot.test.ts`, over a grid, rather than
 * by re-deriving the union). What it buys is a chip list a user can read: three
 * drags over one peak are one exclusion, not three.
 *
 * Touching intervals merge too, because the mask is inclusive at both ends.
 */
export function mergeRegions(regions: readonly [number, number][],
                             add?: [number, number] | null): [number, number][] {
  const all = [...regions, ...(add ? [add] : [])]
    .map((r) => normalizeRegion(r as [number, number]))
    .filter((r): r is [number, number] => r !== null)
    .sort((p, q) => p[0] - q[0]);
  const out: [number, number][] = [];
  for (const [a, b] of all) {
    const last = out[out.length - 1];
    if (last && a <= last[1]) last[1] = Math.max(last[1], b);
    else out.push([a, b]);
  }
  return out;
}

/** Is 2θ inside any region?  The client's copy of the server's mask test, and
 *  the only thing `plot.test.ts` compares a merge against. */
export function masked(regions: readonly [number, number][], twoTheta: number): boolean {
  return regions.some(([a, b]) => twoTheta >= a && twoTheta <= b);
}

/** One decimal place more than the data resolves — a region is a protocol
 *  statement, so its chip shows what would be sent, not a rounded story. */
export function formatRegion([a, b]: [number, number]): string {
  return `${a.toFixed(3)}–${b.toFixed(3)}°`;
}

/**
 * An indexing candidate's predicted lines, as the plot needs them (WP-1211).
 *
 * `label` is built here rather than served: the panel already renders the cell,
 * and a server that formatted one would be a second opinion about how a cell
 * reads. `n_total` is the half of the server's cap that keeps it honest — over
 * `MAX_CANDIDATE_TICKS` the answer is thinned by rank in 2θ, so
 * `two_theta.length < n_total` means a sample was drawn and not a set.
 *
 * It is *not* a `CurveToggle`, and that is a decision rather than an omission:
 * a toggle would be a second control for a thing whose control is already the
 * candidate row, and pressing it would leave a row looking selected with
 * nothing on the plot. What the toggle row would have said, the status line
 * under the plot says instead.
 */
export interface CandidateOverlay {
  label: string;
  two_theta: number[];
  n_total: number;
  /** the reflection each drawn line is, parallel to `two_theta` (WP-1213) —
   *  served since WP-1211 and drawn nowhere until the readout strip */
  hkl?: number[][];
  /** which emission line each drawn position belongs to, as an index into the
   *  source's own list: a Kα2 line sits at a different 2θ for the same hkl */
  line?: number[];
}

/** A curve the plot can be asked to stop drawing. */
export interface CurveToggle {
  id: string;
  label: string;
  title: string;
  /** Why this curve is not on screen whatever the toggle says (WP-1210) — the
   *  peak layer away from the Peaks tab. A curve that *could* be drawn leaves
   *  this undefined; one that carries it is listed and disabled, because the
   *  honest answer to "where did my markers go" is a sentence, not a gap. */
  absent?: string;
}

/**
 * The picked-peak layer, as the toggle row needs to know it (WP-1210).
 *
 * It is not part of the window payload — a peak list belongs to the project and
 * outlives every fit — so it arrives beside one rather than inside it.
 */
export interface PeakLayer {
  /** picked lines in the list */
  n: number;
  /** fitted group curves riding with them */
  groups: number;
  /** the Peaks tab is up, which is the only tab the layer is drawn on */
  active: boolean;
}

/**
 * Which curves this window actually has, in drawing order (WP-1032).
 *
 * A *drawing* choice, so nothing here is persisted — WP-1015's rule one panel
 * over: storing one would make a picture the project's opinion. The list is
 * derived from the payload rather than fixed, because "background" is a curve
 * only when the model has one and a phase row exists only per phase.
 *
 * The reported item was "make it possible to toggle the background on", and the
 * measurement says which repair that is: the background trace is drawn
 * *unconditionally* whenever `y_background` is non-empty, so nothing was
 * missing — what was missing is the control to turn a forced curve **off**.
 */
export function curveToggles(w: Window,
                             residualLabel = "Δ",
                             layer?: PeakLayer | null): CurveToggle[] {
  const out: CurveToggle[] = [
    { id: "obs", label: "obs", title: "the measured points" },
  ];
  if (w.excluded?.two_theta?.length) {
    // a *curve* toggle for the excluded points, not for the shading: hiding
    // them is a drawing choice, while the region itself is protocol and is
    // switched off only by removing it (WP-1033)
    out.push({ id: "masked", label: "masked",
      title: "the measured points outside the fit range or inside an excluded "
        + "region — drawn recessively, and in no residual" });
  }
  if (!w.raw) {
    out.push({ id: "calc", label: "calc", title: "the model" });
    if (w.y_background?.length) {
      out.push({ id: "bkg", label: "bkg", title: "the background, drawn additively — "
        + "it is held or co-refined, never subtracted from the data" });
    }
    out.push({ id: "diff", label: residualLabel,
      title: "the residual in the lower panel" });
    for (const phase of Object.keys(w.ticks ?? {})) {
      out.push({ id: `ticks:${phase}`, label: phase,
        title: `reflection positions for ${phase} — every emission line, `
          + "so a Kα2 tick is a tick and not an impurity" });
    }
  }
  // Last, because the layer draws over everything else — and outside the
  // `raw` branch, since a peak list is what a project has *before* a fit.
  if (layer?.n) {
    const absent = layer.active
      ? undefined
      : "drawn on the Peaks tab, where a marker can be moved, excluded or "
        + "removed — a click on this plot means something else here";
    out.push({ id: "peaks", label: "peaks", absent,
      title: "the picked lines, at the measured intensity under each position — "
        + "hollow where the line is not used" });
    if (layer.groups) {
      out.push({ id: "peakfit", label: "peak fit", absent,
        title: "the profile fitted to each group of picked lines, dashed — it is "
          + "what the positions were measured from, not the refined model" });
    }
  }
  return out;
}

/**
 * "Data only": every curve hidden but the measured points (WP-1210).
 *
 * Over *every* id **the payload offers when it is pressed**, absent ones
 * included — so a layer that is listed but undrawable (the peak layer away from
 * its tab) is hidden too, and switching to that tab does not undo the button.
 *
 * What it deliberately does not cover, because `hidden` is an exception list
 * and this returns a value rather than arming a mode: a curve that comes into
 * *existence* later is not in the list and therefore draws. Press this with
 * hand-placed peaks and no fitted groups, then refit, and the dashed peak-fit
 * curve appears on a cleared plot. Fixing it means an armed mode that keeps
 * re-hiding, which then has to decide what a manual toggle underneath it means
 * — a bigger design than this button (WP-1210's log; found in review, not use).
 */
export function dataOnlyHidden(toggles: readonly CurveToggle[]): string[] {
  return toggles.filter((curve) => curve.id !== "obs").map((curve) => curve.id);
}

/** Is the plot showing the data and nothing else?  The button's own state. */
export function isDataOnly(toggles: readonly CurveToggle[],
                           hidden: readonly string[]): boolean {
  return toggles.length > 1
    && shows(hidden, "obs")
    && dataOnlyHidden(toggles).every((id) => hidden.includes(id));
}

/** Is `id` drawn?  Hidden is the exception list, so a new curve arrives shown. */
export function shows(hidden: readonly string[], id: string): boolean {
  return !hidden.includes(id);
}

/** Toggle one id in an exception list, returning a new one. */
export function toggleCurve(hidden: readonly string[], id: string): string[] {
  return hidden.includes(id) ? hidden.filter((h) => h !== id) : [...hidden, id];
}

export interface Residual {
  values: ArrayLike<number>;
  /** the y2 axis title — it names what is plotted, never what was hoped for */
  title: string;
  label: string;
  /** cumulative χ² only rises, so a zero line through it says nothing */
  zeroline: boolean;
}

export const RESIDUAL_KINDS: { id: ResidualKind; label: string; title: string }[] = [
  { id: "weighted", label: "Δ/σ", title: "the weighted residual the fit actually minimises" },
  { id: "delta", label: "Δ", title: "observed − calculated, in counts" },
  { id: "cumulative", label: "Σχ²", title: "χ² accumulated from the view's left edge — "
    + "a flat stretch contributed nothing, a step is where the misfit is" },
];

export const SCALES: { id: Scale; label: string; title: string }[] = [
  { id: "linear", label: "lin", title: "intensity as measured" },
  { id: "sqrt", label: "√", title: "square root — the weak peaks a strong one hides, "
    + "with the axis still labelled in intensity" },
  { id: "log", label: "log", title: "logarithmic; non-positive points are not drawable "
    + "and are dropped" },
];

/**
 * The chosen residual, and an axis title that says which σ it is over.
 *
 * `delta` is *always* Δ/σ: the fit always weighted by something, so there is
 * always a weighted residual to draw (WP-1029 (s)). `weighted` does not say
 * whether σ exists — it says whether σ was **measured**, i.e. whether the file
 * brought an esd column or the server fell back to Poisson √max(y,1). That
 * changes only the axis title, never which curve is plotted.
 *
 * This used to switch the *curve*, dropping to raw Δ when `weighted` was false.
 * It never fired: the server derived the flag from the result rather than from
 * the data reference, so it was pinned true and a Poisson fit was labelled
 * `(obs−calc)/σ` as if its σ had been measured.
 */
export function residual(kind: ResidualKind, w: Window): Residual {
  const measured = w.weighted !== false;
  if (kind === "cumulative") {
    return {
      values: w.cumulative_chi2 ?? [],
      title: "Σχ²",
      label: "Σχ²",
      zeroline: false,
    };
  }
  if (kind === "weighted") {
    return {
      values: w.delta ?? [],
      // an assumed σ is still a σ, but the axis has to admit which one it is
      title: measured ? "(obs−calc)/σ" : "(obs−calc)/σ (Poisson σ)",
      label: "Δ/σ",
      zeroline: true,
    };
  }
  return {
    values: w.delta_raw ?? w.delta ?? [],
    title: "obs−calc",
    label: "Δ",
    zeroline: true,
  };
}

// ----------------------------------------------------------------------
// the readout strip (WP-1213)
// ----------------------------------------------------------------------
/**
 * The index of the value nearest `x` in an ascending array — binary search.
 *
 * The plot's one nearest-channel question, asked by the readout and by the peak
 * layer's marker heights. `-1` when there is nothing to look in.
 */
export function nearestIndex(xs: ArrayLike<number>, x: number): number {
  if (!xs.length) return -1;
  let lo = 0;
  let hi = xs.length - 1;
  while (hi - lo > 1) {
    const mid = (lo + hi) >> 1;
    if (xs[mid] < x) lo = mid;
    else hi = mid;
  }
  return Math.abs(xs[lo] - x) <= Math.abs(xs[hi] - x) ? lo : hi;
}

/** Which plot ink a readout row is about, so the strip can say it in the mark's
 *  own colour as well as by name. `curveColors`' keys, and no others. */
export type ReadoutInk = "obs" | "calc" | "bkg" | "diff" | "peak" | "peakfit"
  | "candidate";

/** One labelled field of the strip. `value` is already formatted: the strip
 *  prints it and decides nothing. */
export interface ReadoutRow {
  /** stable across hovers, so the strip's slots keep their order */
  id: string;
  label: string;
  value: string;
  ink?: ReadoutInk;
}

export interface Readout {
  /** the drawn channel under the pointer, at four places with its degree sign */
  position: string;
  /** `d = λ/(2 sin θ)` there, empty where the source's λ is not in hand */
  d: string;
  rows: ReadoutRow[];
}

export interface ReadoutInputs {
  /** which residual the lower panel is drawing — the strip names the one on
   *  screen, never all three */
  kind: ResidualKind;
  /** the source's emission lines, primary first: `d` is the primary's, and a
   *  candidate line names its own */
  wavelengths?: readonly number[] | null;
  /** the picked lines, and whether their layer is on the plot at all — it is
   *  drawn only on the Peaks tab (WP-1210), so elsewhere there is no row */
  peaks?: readonly PeakRow[] | null;
  peaksActive?: boolean;
  /** how near a picked line has to be to be the one under the pointer, in ° 2θ:
   *  the caller's, because the pixel↔2θ map is the caller's.  The **coarse**
   *  radius the non-destructive verbs aim with (10 px, `down`'s `click`), not
   *  the move gesture's `grabToleranceDeg` — reading a line is not editing one,
   *  and at a survey view the fine radius is a fraction of a channel */
  peakTolerance?: number;
  /** the fitted group profiles, so the dashed curve can say what it is worth */
  groups?: readonly GroupCurve[] | null;
  /** the candidate overlay on screen, if any, and the same question for it */
  candidate?: CandidateOverlay | null;
  candidateTolerance?: number;
  /** the curves switched off (`curveToggles`' ids): the strip names what is
   *  **drawn**, so `data only` empties it down to the points — the same
   *  exception list, read the same way */
  hidden?: readonly string[];
  /** what a cumulative χ² drawn from the view's left edge has subtracted
   *  (`rxplot.chi2Base`), so the strip quotes the curve it sits under */
  chi2Base?: number;
}

/** What a field with nothing in it prints — one spelling, so an empty strip
 *  and an empty field are the same mark. */
const EMPTY = "—";

/**
 * `+0.0035°` / `-0.0035°` — an offset, signed and always signed.
 *
 * An ASCII minus, deliberately: the strip prints `formatValue`'s numbers beside
 * these, and those come out of `toPrecision`, so a typographic `−` here put two
 * spellings of minus in one row (seen in Chrome). The rule the app already
 * follows unwritten is that **prose takes `−` and numbers take `-`** — the
 * residual's axis title is `obs−calc` and its values are not. `formatHkl` is
 * the exception that proves it: an index is a label standing in for an overbar,
 * not a measurement.
 */
function offset(delta: number): string {
  return `${delta < 0 ? "-" : "+"}${Math.abs(delta).toFixed(4)}°`;
}

/**
 * Everything the plot knows at one 2θ, as the strip under it prints it.
 *
 * **Why a strip and not a hover box** (the report: "the tooltip frequently
 * covers a large part of the data"): plotly offers no positioning for the
 * unified box beyond `hoverlabel.align`, so "put it somewhere else" is not a
 * setting — the box has to go, and what replaces it is a row of the plot's own
 * controls. That also settles something the box could not do: under
 * `hovermode: "x unified"` plotly snaps *every* trace to its nearest point in
 * x, so the candidate overlay would have put a row in the box at every pointer
 * position, which is why WP-1211 gave it `hoverinfo: "skip"` and left its
 * served `hkl` undrawn. Here it is one more row.
 *
 * Pure, and every value is formatted here rather than in the component, because
 * what makes a readout right is that it reads as the table beside it reads:
 * `formatPosition`/`formatIntensity` are `lib/peaks.ts`' (WP-1209), and the
 * intensities are `formatValue`'s six significant figures — which is what the
 * deleted `hovertemplate`s printed, `%{customdata:.6g}` over the **unscaled**
 * value, so a √ view still reads in intensity.
 *
 * A row a payload cannot fill is **absent, not empty**: there is a row per
 * curve that is *drawn*, which makes the strip's shape a property of the
 * payload, the tab and the curve toggles — never of where the pointer happens
 * to be. Everything that varies with the pointer keeps its slot and empties it
 * instead: the three "nearest something" rows, and `x === null` for the pointer
 * being off the plot altogether, which is most of the time. A strip that grew a
 * field on hover would resize the canvas above it once per entry, and that is
 * the jitter WP-1212 spent itself removing, arriving through the repair for it.
 *
 * Two questions, two positions, and they are not the same one. What a *curve*
 * says is the nearest drawn channel's, and the position printed is that
 * channel's, so every number belongs to one measured point and the tick offsets
 * are consistent with it. What is *near the pointer* — a picked line, a
 * predicted one — is hit-tested against the pointer's own `x`, because a drawn
 * pattern is decimated and the channel it snapped to can be further away than
 * the tolerance being applied.
 *
 * The one place this reads two arms is the **masked** channels: they are in no
 * result, so they arrive beside it (WP-1033), and a pointer inside an excluded
 * region is over one of them. The nearest channel is therefore taken over both
 * arms, and a masked one has no model to quote — which is also how the strip
 * says where the pointer is, without a field that changes width to say it.
 */
export function readout(
  w: Window | null,
  x: number | null,
  inputs: ReadoutInputs,
): Readout | null {
  if (!w) return null;
  const hidden = inputs.hidden ?? [];
  const fitted = w.two_theta;
  // The masked channels are a *separate arm* (WP-1033: they are in no result,
  // so the server sends them beside it), and they are measured points like any
  // other — a pointer inside an excluded region is over one of them. Without
  // this the readout snapped to the nearest surviving channel and printed its
  // numbers under a pointer that could be a whole region away.
  const maskedOn = shows(hidden, "masked");
  const excluded: ArrayLike<number> = maskedOn ? w.excluded?.two_theta ?? [] : [];
  if (!fitted.length && !excluded.length) return null;
  // `null` is the pointer being off the plot, which is most of the time: the
  // strip keeps its fields and empties them, because a strip that grew fields
  // on hover would resize the canvas above it once per entry (WP-1032 measured
  // a resize at ~111 ms; WP-1212 spent itself on smaller movements than that).
  const live = x != null && Number.isFinite(x);
  const kf = live ? nearestIndex(fitted, x!) : -1;
  const kx = live ? nearestIndex(excluded, x!) : -1;
  const masked = kf < 0
    || (kx >= 0 && Math.abs(excluded[kx] - x!) < Math.abs(fitted[kf] - x!));
  const k = masked ? kx : kf;
  const at = k < 0 ? null : (masked ? excluded[k] : fitted[k]);
  const lam = inputs.wavelengths?.[0];
  const rows: ReadoutRow[] = [];
  const value = (v: number | undefined | null) =>
    at == null || v == null || !Number.isFinite(v) ? EMPTY : formatValue(v, null);
  // a masked channel is in no result, so there is no model at it to quote —
  // which is also how the strip says the pointer is inside a region
  const fit = (v: number | undefined | null) => (masked ? EMPTY : value(v));

  if (shows(hidden, "obs")) {
    rows.push({ id: "obs", label: "obs", ink: "obs",
      value: masked ? value(w.excluded?.y_obs?.[k]) : value(w.y_obs?.[k]) });
  }
  if (!w.raw) {
    if (shows(hidden, "calc")) {
      rows.push({ id: "calc", label: "calc", value: fit(w.y_calc?.[k]), ink: "calc" });
    }
    if (w.y_background?.length && shows(hidden, "bkg")) {
      rows.push({ id: "bkg", label: "bkg", value: fit(w.y_background[k]), ink: "bkg" });
    }
    if (shows(hidden, "diff")) {
      const res = residual(inputs.kind, w);
      // a cumulative curve is drawn from the view's left edge, and so is its value
      const base = inputs.kind === "cumulative" ? inputs.chi2Base ?? 0 : 0;
      const v = res.values[k];
      rows.push({ id: "diff", label: res.label, value: fit(v == null ? v : v - base), ink: "diff" });
    }
  }

  // the fitted group profile, named because a reader had no other way to tell
  // the dashed curve from the model (WP-1210's own repair, carried here)
  if (inputs.peaksActive && inputs.groups?.length && shows(hidden, "peakfit")) {
    const group = at == null ? undefined : inputs.groups.find(
      (g) => g.two_theta.length && g.two_theta[0] <= at
        && g.two_theta[g.two_theta.length - 1] >= at);
    const j = group ? nearestIndex(group.two_theta, at!) : -1;
    rows.push({ id: "peakfit", label: "peak fit", ink: "peakfit",
      value: group && j >= 0 ? formatValue(group.y_fit[j], null) : EMPTY });
    if (w.raw) {
      // on the raw view the lower subplot is the groups' own residual, and it
      // is a drawn curve like any other
      rows.push({ id: "peakdelta", label: "(y−fit)/σ", ink: "peakfit",
        value: group && j >= 0 ? formatValue(group.delta[j], null) : EMPTY });
    }
  }

  // The nearest tick per phase, as a reflection and an offset: the position is
  // this readout's own 2θ plus the offset, and an offset is the number that
  // says "there is a reflection right here" without arithmetic.
  //
  // The index is `tick_hkl`'s (WP-1438), which the route cuts to the window in
  // the same pass as the positions and hands back pinned to them by index —
  // two reflections land at the same 2θ to every decimal, so there is no
  // other way to pair them. It goes here rather than in a hover box for the
  // reason the box went (WP-1213), and it is spelled as the candidate row two
  // rows down spells one. A result reopened from a project written before the
  // indices were carried has the positions and not them, and then the row says
  // what it always said.
  for (const [phase, ticks] of Object.entries(w.ticks ?? {})) {
    if (!shows(hidden, `ticks:${phase}`)) continue;
    const j = at == null ? -1 : nearestIndex(ticks, at);
    const hkl = j < 0 ? undefined : (w.tick_hkl ?? {})[phase]?.[j];
    const near = j < 0 ? EMPTY : offset(ticks[j] - at!);
    rows.push({ id: `ticks:${phase}`, label: phase,
      value: hkl?.length === 3 ? `${formatHkl(hkl)} ${near}` : near });
  }

  // The picked line under the pointer, printed as the panel's table prints it —
  // and hit-tested against `x` rather than the channel this readout snapped to.
  // Measured in Chrome on the NAC example: the drawn pattern is decimated, so
  // at a survey view the nearest drawn channel is up to ~0.03° from the
  // pointer, which is *wider than the tolerance*; the pointer sat exactly on
  // three picked lines in a row and the row read `—`.
  if (inputs.peaksActive && inputs.peaks?.length && shows(hidden, "peaks")) {
    const hit = !live ? null
      : nearestPeak(inputs.peaks, x!, inputs.peakTolerance ?? Infinity);
    const row = hit === null ? null : inputs.peaks.find((p) => p.index === hit);
    const pos = row ? formatPosition(row.two_theta, row.two_theta_esd) : null;
    rows.push({ id: "peaks", label: "peak", ink: "peak",
      value: row && pos
        ? `#${row.index} ${pos.value}${pos.esd}° · I ${
            formatIntensity(row.intensity, intensityScale(inputs.peaks), row.flags)}`
        : EMPTY });
  }

  // …and the candidate's, which is the hkl WP-1211 serves and does not draw.
  // No ordinal and no count: past `MAX_CANDIDATE_TICKS` the drawn set is a
  // sample thinned by rank, so "the 743rd line" would be a statement about the
  // sample. The status line under the plot is where the count is honest. No
  // `hidden` gate either: the overlay has no curve toggle, because its control
  // is the candidate row (WP-1211).
  const lines = inputs.candidate?.two_theta ?? [];
  if (lines.length) {
    const j = !live ? -1 : nearestIndex(lines, x!);
    const near = j >= 0
      && Math.abs(lines[j] - x!) <= (inputs.candidateTolerance ?? Infinity);
    const hkl = inputs.candidate?.hkl?.[j];
    const li = inputs.candidate?.line?.[j];
    const lineLam = li == null ? undefined : inputs.wavelengths?.[li];
    rows.push({ id: "candidate", label: "candidate", ink: "candidate",
      value: near && hkl
        ? [formatHkl(hkl), lineLam == null ? null : `λ ${lineLam.toFixed(4)} Å`]
            .filter(Boolean).join(" · ")
        : EMPTY });
  }

  const theta = at == null ? 0 : Math.sin((at * Math.PI) / 360);
  return {
    position: at == null ? EMPTY : `${at.toFixed(4)}°`,
    d: at != null && lam && theta > 0 ? `${(lam / (2 * theta)).toFixed(4)} Å` : EMPTY,
    rows,
  };
}
