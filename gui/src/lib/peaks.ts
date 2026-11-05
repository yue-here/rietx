/**
 * Peak-picker and candidate-table logic, as pure functions (WP-1027).
 *
 * The rules that must not be re-decided in a component live here, and two of
 * them are the server's: which flags make a peak unusable comes from the
 * `unusable_flags` arm of `/api/peaks`, and which caveats *refute* a candidate
 * comes from the `refuting_caveats` arm of `/api/index/result` — both quoted
 * from package constants, so the colouring cannot drift when a vocabulary
 * grows (the `held_because` rule, applied to chips).
 */

export interface PeakRow {
  index: number;
  two_theta: number;
  two_theta_esd: number;
  d: number;
  intensity: number;
  fwhm: number;
  group: number;
  n_in_group: number;
  chi2_red: number;
  flags: string[];
  origin: "fitted" | "manual" | "edited";
  usable: boolean;
}

export interface GroupCurve {
  group: number;
  two_theta: number[];
  y_fit: number[];
  y_env: number[];
  delta: number[];
  chi2_red: number;
  n_components: number;
}

export interface PeaksPayload {
  peaks: PeakRow[] | null;
  pattern: {
    two_theta: number[]; y_obs: number[]; n_total: number;
    /** the channels the protocol masks — this view is the only one a project
     *  has before its first fit, so it is where a fit range is first seen */
    excluded?: { two_theta: number[]; y_obs: number[] };
    n_excluded?: number;
  };
  groups?: GroupCurve[];
  diagnostics?: Array<{ level: string; code: string; message: string }>;
  flag_vocabulary: string[];
  unusable_flags: string[];
  n_total?: number;
  n_usable?: number;
  source?: "fitted" | "positions";
  wavelength?: number;
  api_call?: string;
}

/**
 * A chip's tone, in the app's one tone vocabulary (`app.css`).
 *
 * `note` is the neutral member and the chip's own default, so a tone function
 * that cannot decide returns it rather than nothing.
 */
export type Tone = "note" | "ok" | "warn" | "bad" | "accent";

/** A flag chip's tone: the unusable set reads as "this line is out". */
export function flagTone(flag: string, unusable: readonly string[]): Tone {
  return unusable.includes(flag) ? "bad" : "note";
}

/**
 * A candidate's confidence as a tone.
 *
 * The grade is the server's — `high` requires zero caveats — and this only
 * says how it is drawn: the middle grade is a warning because a `medium` cell
 * is one a caveat has already been raised against, not a slightly worse
 * answer.
 */
export function confidenceTone(confidence: "high" | "medium" | "low"): Tone {
  return confidence === "high" ? "ok" : confidence === "medium" ? "warn" : "note";
}

// ----------------------------------------------------------------------
// the table's numbers (WP-1209)
// ----------------------------------------------------------------------
/**
 * Flags under which a row's intensity is not a measurement: the component
 * refined onto its zero bound (`no_intensity` — on certified corundum two
 * components land at 2.1e-49 and 5.5e-19, which is the bound, not an area),
 * or its group never converged (`fit_failed` — the number is the seed). Named
 * here rather than read off `unusable_flags`, because that set is about
 * *evidence of a lattice* and holds `excluded`, a human's decision about a
 * perfectly well measured line. `peaks.test.ts` holds both names to the
 * corpus vocabulary.
 */
export const INTENSITY_UNMEASURED_FLAGS: readonly string[] = ["no_intensity", "fit_failed"];

export function intensityMeasured(flags: readonly string[]): boolean {
  return !flags.some((f) => INTENSITY_UNMEASURED_FLAGS.includes(f));
}

/**
 * The strongest measured intensity, the 100 of the relative scale — or 0 when
 * no row carries a measurement, which `formatIntensity` renders as `—` on
 * every row rather than dividing by it.
 */
export function intensityScale(
  rows: readonly { intensity: number; flags: readonly string[] }[],
): number {
  let imax = 0;
  for (const r of rows) {
    if (intensityMeasured(r.flags) && Number.isFinite(r.intensity) && r.intensity > imax) {
      imax = r.intensity;
    }
  }
  return imax;
}

/**
 * `I/Imax × 100` at one decimal — the relative scale a peak table is read in
 * — or `—` where the number is not a measurement. A fitted area is in the
 * pattern's counting units and means nothing on its own; `1.2e+3` beside
 * `2.1e-49` is what the raw column looked like.
 */
export function formatIntensity(
  intensity: number, imax: number, flags: readonly string[],
): string {
  if (!intensityMeasured(flags) || !(imax > 0) || !Number.isFinite(intensity)) return "—";
  return (100 * intensity / imax).toFixed(1);
}

/**
 * From this σ(2θ) up a position's esd is not printed: the value is the
 * measurement and the row's flag says why it has no precision. A degree is
 * wider than any peak (the widest FWHM on the corundum pattern is 0.35°), so
 * an esd that large is a flat direction rather than a precision — the
 * degenerate ones measured there are 1e17° and 1e49° (WP-1110 item 14) —
 * (`esdSwallowsValue` in `table.ts` shares the literal 1 and nothing else:
 * it also asks whether the esd exceeds the value). The triage's 0.1° cut a real
 * line off: 51 of that pattern's 62 esds are under 0.01°, 8 sit in
 * [0.01, 0.1), and one asymmetric line is at 0.105°, which at 0.1° printed
 * bare beside a neighbour's `(875)`.
 */
export const POSITION_ESD_MAX_DEG = 1.0;

/**
 * A 2θ at four places, with its esd in units of the last place — `35.0912`
 * and `(3)` — or an empty esd when it is at or above `POSITION_ESD_MAX_DEG`.
 *
 * Four places always, rather than the place the esd justifies: a column is
 * scanned down, so its decimals must line up, and a peak's position is known
 * to its fourth place whenever it is known at all. An esd below half a unit
 * of that place prints `(0)`, which says "under the last digit" and is not
 * the same statement as none.
 */
export function formatPosition(
  twoTheta: number, esd: number | null | undefined,
): { value: string; esd: string } {
  const value = Number.isFinite(twoTheta) ? twoTheta.toFixed(4) : String(twoTheta);
  if (esd == null || !Number.isFinite(esd) || esd < 0 || esd >= POSITION_ESD_MAX_DEG) {
    return { value, esd: "" };
  }
  const digits = Math.round(esd * 1e4);
  // 0.99996° rounds to 10000 units of the fourth place: over the gate, not under it
  return { value, esd: digits >= 1e4 ? "" : `(${digits})` };
}

/**
 * The peak nearest `tt`, or null when none is within `tol` (° 2θ).
 *
 * Hit-testing for the plot's pointer interactions. The tolerance is handed in
 * as degrees because the caller owns the pixel↔2θ mapping — this function must
 * stay testable without a layout engine.
 */
export function nearestPeak(
  peaks: readonly { index: number; two_theta: number }[],
  tt: number,
  tol: number,
): number | null {
  let best: number | null = null;
  let dist = tol;
  for (const p of peaks) {
    const d = Math.abs(p.two_theta - tt);
    if (d <= dist) {
      best = p.index;
      dist = d;
    }
  }
  return best;
}

/**
 * The grab radius for the *move* gesture, in ° 2θ: the smaller of the pixel
 * radius and 1.5× the median fitted FWHM.
 *
 * A pixel radius alone is a screen constant applied to a physics axis, and at
 * the survey view it is destructive: on the corundum pattern (0.19°/px, 64
 * lines over 145°) 10 px is ±1.9°, the 9-px markers themselves tile ~75 % of
 * the axis, and a measured zoom drag starting 0.9° from a line silently moved
 * that line 11° instead of zooming. The FWHM cap says when a drag may *mean*
 * "move this line": once 10 px covers more than ~a line width, the line is
 * subpixel and precision-editing it is not what any drag can express — so the
 * drag falls through to the chart's zoom, which is the survey view's gesture.
 * The coarse pixel radius stays right for the non-destructive gestures
 * (shift-toggle, right-click refit target a *labelled* thing) and for
 * click-to-add, whose final position comes from the group refit, not the
 * pixel.
 */
export function grabToleranceDeg(
  peaks: readonly { fwhm: number }[],
  degPerPx: number,
  pxRadius = 10,
): number {
  const px = pxRadius * degPerPx;
  const widths = peaks.map((p) => p.fwhm).filter((w) => w > 0).sort((a, b) => a - b);
  if (!widths.length) return px;
  return Math.min(px, 1.5 * widths[widths.length >> 1]);
}

/**
 * Group-curve arrays joined into one plotable trace, windows separated by null.
 *
 * One trace instead of one per group: sixty groups as sixty scattergl traces is
 * a measurable legend and draw cost, and the gaps between fit windows are real
 * — a null point breaks the line exactly where the model ends.
 */
export function joinCurves(
  groups: readonly GroupCurve[],
  pick: (g: GroupCurve) => number[],
): { x: (number | null)[]; y: (number | null)[] } {
  const x: (number | null)[] = [];
  const y: (number | null)[] = [];
  for (const g of groups) {
    if (x.length) {
      x.push(null);
      y.push(null);
    }
    x.push(...g.two_theta);
    y.push(...pick(g));
  }
  return { x, y };
}

// ----------------------------------------------------------------------
// candidates
// ----------------------------------------------------------------------
export interface Candidate {
  cell: number[];
  cell_esd: number[];
  system: string;
  centring: string;
  lattice_group: string;
  volume: number;
  n_indexed: number;
  n_lines: number;
  fom: Array<{ name: string; value: number; n_lines: number; blind_spot: string }>;
  found_by: string[];
  confidence: "high" | "medium" | "low";
  confidence_caveats: string[];
  ambiguity: Array<{
    cell: number[];
    index: number;
    system: string;
    discriminating_two_theta: number[];
  }>;
  lebail: {
    rwp: number;
    predicted_but_absent: number;
    n_reflections: number;
    status: string;
    absent_source?: "line_screen" | "fitted_background";
    n_lines_screened?: number | null;
    predicted_but_absent_uncancellable_in_window?: number | null;
  } | null;
  diagnostics: Array<{ level: string; code: string; message: string }>;
}

export interface AdoptVerdict {
  allowed: boolean;
  why: string;
}

/**
 * The FoM columns to show: the union of panel members over all candidates, in
 * first-seen order. A member can be absent on a candidate (what could be
 * computed varies), so the cell is looked up by name, never by position.
 */
export function fomColumns(candidates: readonly Candidate[]): string[] {
  const seen: string[] = [];
  for (const c of candidates) {
    for (const f of c.fom ?? []) {
      if (!seen.includes(f.name)) seen.push(f.name);
    }
  }
  return seen;
}

export function fomOf(candidate: Candidate, name: string): number | null {
  for (const f of candidate.fom ?? []) {
    if (f.name === name) return f.value;
  }
  return null;
}

/** Red for a caveat that refutes, amber for one that merely caps. */
export function caveatTone(caveat: string, refuting: readonly string[]): Tone {
  return refuting.includes(caveat) ? "bad" : "warn";
}

/**
 * The absent column: a share of the lines the count was taken over.  Since
 * indexing thresholds 1.12 the count is the line screen's, over merged lines
 * (`n_lines_screened`), not the Le Bail fit's reflections; the windowed
 * uncancellable count, the one the caveat caps on, rides beside it.  A
 * validation without a peak list keeps the fitted background's share.
 */
export function absentText(lebail: NonNullable<Candidate["lebail"]>): string {
  if (lebail.absent_source === "line_screen" && lebail.n_lines_screened != null) {
    const w = lebail.predicted_but_absent_uncancellable_in_window;
    return `${lebail.predicted_but_absent}/${lebail.n_lines_screened} lines`
      + (w == null ? "" : ` · ${w} in window`);
  }
  return `${lebail.predicted_but_absent}/${lebail.n_reflections}`;
}

/** `4.7594(3) 4.7594(3) 12.992(1)` style cell summary — lengths only. */
export function cellText(cell: readonly number[]): string {
  const lengths = cell.slice(0, 3).map((v) => v.toFixed(4)).join(" ");
  const angles = cell.slice(3, 6).map((v) => v.toFixed(2)).join(" ");
  return `${lengths} Å · ${angles}°`;
}

/**
 * The furthest discriminating 2θ of a candidate's partners, or null.
 *
 * WP-1024: what survives ambiguity screening is separated only *beyond* the
 * measured range, so the actionable rendering is "collect to here".
 */
export function collectTo(candidate: Candidate): number | null {
  let hi: number | null = null;
  for (const partner of candidate.ambiguity ?? []) {
    for (const tt of partner.discriminating_two_theta ?? []) {
      if (hi === null || tt > hi) hi = tt;
    }
  }
  return hi;
}

/**
 * `(1 0 −4)` — a reflection's indices, spaced, with a real minus sign.
 *
 * Spaced because `(10-4)` is what `join("")` makes of `[1, 0, -4]`, and a
 * two-digit index makes it worse: the separator is not decoration. The minus is
 * U+2212, which is what the rest of the app's typography uses (`obs−calc`),
 * rather than the hyphen `toFixed` would give.
 */
export function formatHkl(hkl: readonly number[]): string {
  return `(${hkl.map((v) => (v < 0 ? `−${Math.abs(v)}` : String(v))).join(" ")})`;
}
