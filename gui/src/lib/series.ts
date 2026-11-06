/**
 * What the series panel draws and sends, as pure functions (WP-1016).
 *
 * A series is N separate refinements chained by a warm start, and the two things
 * a panel over it must not get wrong are both about honesty rather than layout.
 *
 * **The order is the series**, so every edit — reorder, remove, a typed
 * coordinate — produces the whole list and one `PUT /api/series` sends it. The
 * arithmetic of "move this one up" is here because it is the only part of that a
 * test can judge without a DOM.
 *
 * **A smooth curve is exactly what a poisoned chain produces** (WP-0505's
 * measured lesson), so when `direction="both"` ran the panel draws the backward
 * chain beside the forward one and states the gap between them as a number, in
 * esds, for every parameter and largest first (`SeriesResult.direction_gaps`).
 * No gap is called path-dependent: the 3σ line that once did was a number no
 * measurement set (WP-2003, C5), so a trajectory is ranked by its gap and
 * carries it, and the reader decides what size matters for their specimen.
 */

export interface SeriesPattern {
  upload: string;
  filename: string;
  label: string;
  x: number | null;
  reader: string;
  /** the *effective* reader keywords this member was read with */
  reader_options: Record<string, string>;
  n_points: number;
  two_theta_range: [number, number];
  /** the *file* carried esds — a mixed series is fitted under two weightings */
  has_sigma: boolean;
}

export interface SeriesSettings {
  carry: string[];
  refit: string;
  direction: string;
  x_label: string;
}

export interface SeriesSetup {
  patterns: SeriesPattern[];
  n_patterns: number;
  settings: SeriesSettings;
  choices: { refit: string[]; direction: string[] };
  carry_help: string;
  defaults: SeriesSettings;
  protocol: { mode: string; plan: string | null; n_stages: number };
  has_x: boolean;
  sigma_mixed: boolean;
  has_result: boolean;
  running: boolean;
}

export type Rung = "warm" | "warm_staged" | "cold";

/** Where a path's largest forward/backward gap sits, and what each chain kept
 *  there (the server's `gap_at`, read off `DirectionGap`). */
export interface GapAt {
  label: string;
  index: number;
  forward_rung: Rung;
  backward_rung: Rung;
}

/** One row of `SeriesResult.direction_gaps`: a path's gap at one pattern. */
export interface DirectionGap {
  path: string;
  label: string;
  index: number;
  forward: number;
  backward: number;
  gap: number;
  /** `gap` over the two chains' combined esd; `null` where either had none */
  gap_esd: number | null;
  forward_rung: Rung;
  backward_rung: Rung;
}

/** One row of `SeriesResult.steps`: a path's change between two neighbours. */
export interface SeriesStep {
  path: string;
  /** the two patterns' labels, earlier first */
  labels: [string, string];
  indices: [number, number];
  /** later minus earlier, signed, in the path's own unit */
  step: number;
  /** `step` over the later pattern's esd, signed; `null` where that esd is missing */
  size_esd: number | null;
  /** the same pair refitted cold over `step`; `null` where it was not re-measured */
  cold_ratio: number | null;
}

export interface Trajectory {
  path: string;
  x: number[];
  x_label: string;
  value: number[];
  stderr: Array<number | null>;
  labels: string[];
  /** the backward chain's values, aligned with `x`, when `direction="both"` ran */
  backward: number[] | null;
  /** the largest forward/backward gap in combined esds; `null` when the
   *  comparison did not run or no gap of this path has an esd on both sides */
  n_sigma: number | null;
  /** the pattern that gap sits at; `null` exactly where `n_sigma` is */
  gap_at: GapAt | null;
}

export interface SeriesEntry {
  index: number;
  label: string;
  x: number | null;
  status: string;
  statistics: { rwp: number; gof: number } | null;
  n_iterations: number;
  reseeded: boolean;
  rwp_warm: number | null;
  /** which attempt of the escalation ladder produced these values (WP-1051);
   *  the first pattern of a chain is always `"cold"`, having nothing to warm
   *  from, so this is *not* the same question as `reseeded` */
  rung: string;
  /** every rung attempted on this pattern, in ladder order */
  rungs_tried: string[];
  node_id: string | null;
  tree_id: string | null;
  diagnostics: Array<{ level: string; code: string; message: string }>;
}

/** What the panel sends as one member of the list. */
export function asRequest(patterns: SeriesPattern[]): Array<Record<string, unknown>> {
  return patterns.map((p) => ({
    upload: p.upload, label: p.label,
    // `null` and `undefined` are the same answer here — no coordinate — and the
    // server reads a missing key as "index is the axis"
    ...(p.x === null ? {} : { x: p.x }),
    ...(p.reader_options && Object.keys(p.reader_options).length
      ? { reader_options: p.reader_options } : {}),
  }));
}

/**
 * Move one member by `delta`, clamped — the list unchanged if it cannot move.
 *
 * Returning the same array reference when nothing moves is what lets a caller
 * skip the round trip: reordering the first item upward is a no-op, and a PUT
 * for it would rewrite the server's list to what it already holds and re-read
 * every file to do it.
 */
export function moveBy(patterns: SeriesPattern[], index: number,
                       delta: number): SeriesPattern[] {
  const to = index + delta;
  if (index < 0 || index >= patterns.length || to < 0 || to >= patterns.length) {
    return patterns;
  }
  const next = [...patterns];
  const [moved] = next.splice(index, 1);
  next.splice(to, 0, moved);
  return next;
}

/** Sort the whole list by its coordinate — the ramp a user meant, not the order
 *  a file picker happened to hand over.  Members with no coordinate keep their
 *  places at the end, because inventing one is what `x` being `null` refuses. */
export function sortByX(patterns: SeriesPattern[]): SeriesPattern[] {
  const withX = patterns.filter((p) => p.x !== null);
  const without = patterns.filter((p) => p.x === null);
  return [...withX.sort((a, b) => (a.x as number) - (b.x as number)), ...without];
}

/**
 * The trajectories by their forward/backward gap, largest first, with no
 * threshold (WP-2003, C5). The panel's **second** order: it lists and opens on
 * the series' first-seen order, and this one is the reader's to choose
 * (ruled by the maintainer 2026-11-04, below).
 *
 * `n_sigma` is the record's own number (`DirectionGap.gap_esd`, read by the
 * server), so a parameter that disagrees most comes first and nothing is
 * called path-dependent. A trajectory with no gap in esds (`null`: the
 * comparison did not run, a chain gave no esd, or the path is a relative one)
 * goes after every number, in the series' first-seen order, which
 * `Array.prototype.sort` keeps for ties.
 *
 * The first version ranked only the flagged group, because on a clean ramp
 * the unflagged distances were noise (under 5e-4 σ) and ordering fifteen
 * parameters by it put `phases.0.cell.a` eighth. The record now sets a gap
 * under the trajectory's noise floor (`sequential.NOISE_FLOOR_REL`) to
 * exactly 0, and those ties keep the first-seen order. The floor does not
 * reach every noise gap: on the seven-pattern thermal ramp of
 * `test_sequential.py`, 84 of 91 gaps are 0 and the background terms keep
 * 1e-3 esd, so this order puts `instrument.background.c1` first and
 * `phases.0.cell.a` sixth (measured 2026-11-03). That is why the panel opens
 * on the first-seen parameter, usually the cell edge, and leaves the largest
 * gap one click away on the gap line (ruled by the maintainer 2026-11-04).
 */
export function rankTrajectories(trajectories: Trajectory[]): Trajectory[] {
  return [...trajectories].sort((a, b) => {
    if (a.n_sigma === null || b.n_sigma === null) {
      return Number(a.n_sigma === null) - Number(b.n_sigma === null);
    }
    return b.n_sigma - a.n_sigma;
  });
}

/** A size in esds as the panel prints it: one decimal, `<0.1` below that, and
 *  `0` for the exact zero the record writes under the noise floor. */
export function esdText(v: number): string {
  const a = Math.abs(v);
  if (a === 0) return "0";
  return a < 0.1 ? "<0.1" : a.toFixed(1);
}

/** The words for two chains that kept different attempts at one pattern, or
 *  `""` when they kept the same. Where they differ the gap measures the
 *  escalation ladder as well as the order the series was walked in. */
export function rungNote(at: GapAt | null): string {
  if (!at || at.forward_rung === at.backward_rung) return "";
  return `At ${at.label} the forward chain kept the ${at.forward_rung} attempt and `
    + `the backward chain the ${at.backward_rung} one, so this gap measures the `
    + "escalation ladder as well as the order.";
}

/** The panel's one line over the whole comparison: the largest gap in the
 *  record, where it is, and what it orders. `""` where the comparison did not
 *  run (`direction_gaps` is `null`; the fences say why). */
export function gapLine(gaps: DirectionGap[] | null | undefined): string {
  if (!gaps) return "";
  const top = gaps.find((g) => g.gap_esd !== null);
  if (!top) {
    return "Forward and backward chains compared: no gap could be put in esds, "
      + "because one chain gave no esd.";
  }
  const at: GapAt = { label: top.label, index: top.index,
                      forward_rung: top.forward_rung, backward_rung: top.backward_rung };
  return `Forward and backward chains differ by ${esdText(top.gap_esd as number)} `
    + `esd at most, in ${top.path} at ${top.label}. ${rungNote(at)}`.trim();
}

/** The path with the largest gap, for the line's button. */
export function topGapPath(gaps: DirectionGap[] | null | undefined): string | null {
  return gaps?.find((g) => g.gap_esd !== null)?.path ?? null;
}

/**
 * One trajectory's y-axis title: the parameter's **leaf**, not its path.
 *
 * Measured in a browser, and the reason it is not a character-count threshold
 * like `viz/plots.py:plot_trajectory`'s: a *rotated* title competes with the tick
 * labels for the same fixed left margin, so `phases.0.cell.a` — fifteen
 * characters, well under matplotlib's cut — rendered as `aes.0.cell.a` beside
 * `4.161`-style ticks. The width that clips is the plot's margin, not the string,
 * and the leaf is what a y-axis wants anyway; the full path is the heading
 * directly above.
 *
 * A derived curve keeps its metric on the axis rather than stripping to the
 * leaf: `qpa.LaB6` is a weight percentage, and `r_bragg.`/`r_f.` are the two
 * McCusker residuals (fractions, not percentages). Their leaf alone is the bare
 * phase name — `LaB6` — which carries no unit, reads as a parameter named after
 * the phase, and is identical between the two residuals; naming the metric is
 * what keeps R_Bragg and R_F apart and off a plain leaf.
 */
export function axisTitle(traj: Trajectory | null): string {
  if (!traj) return "";
  if (traj.path.startsWith("qpa.")) return `${traj.path.slice(4)} (wt %)`;
  if (traj.path.startsWith("r_bragg.")) return `${traj.path.slice(8)} R_Bragg`;
  if (traj.path.startsWith("r_f.")) return `${traj.path.slice(4)} R_F`;
  return traj.path.split(".").at(-1) ?? traj.path;
}

/**
 * What the record says about a trajectory's two chains, as the panel's caption.
 *
 * The number and where it sits, then the rung clause where the two chains kept
 * different attempts, and no verdict: the size that matters is the reader's
 * (WP-2003, C5). Empty where `direction="both"` did not run.
 */
export function trajectoryNote(traj: Trajectory | null): string {
  if (!traj || traj.backward === null) return "";
  if (traj.n_sigma === null || traj.gap_at === null) {
    return "The backward chain is drawn beside the forward one. The record "
      + "holds no gap in esds for this parameter: a chain gave no esd, or the "
      + "parameter is relative to where each fit began.";
  }
  const where = `Forward and backward differ by ${esdText(traj.n_sigma)} esd at `
    + `${traj.gap_at.label}, their largest gap. An esd here is the two chains' `
    + "esds combined.";
  const rung = rungNote(traj.gap_at);
  return rung ? `${where} ${rung}` : where;
}

/** One legend entry: the mark it toggles, what it says, and the custom property
 *  its swatch is drawn in, so a theme switch restyles it by CSS alone. */
export interface LegendEntry {
  id: string;
  label: string;
  ink: string;
  mark: "line" | "dash" | "dot" | "ring" | "cross";
  /** Why the mark cannot be drawn, when it cannot: its entry is listed and
   *  disabled, never dropped (`CurveToggle.absent`). */
  absent?: string;
}

/**
 * What the trajectory's legend offers — the marks `rxplot.trajectory` draws.
 *
 * The forward chain is one ink for every parameter, since no parameter is
 * called path-dependent (WP-2003, C5); the disagreement is the backward chain
 * drawn beside it. That chain is offered only when `direction="both"` ran.
 *
 * Reseeded points are ringed and never dropped: the fit is good, but its
 * starting values did not come from its neighbour, so it is not evidence that
 * the trajectory is continuous there (`SEQUENTIAL_RESEED`). A point no rung of
 * the ladder recovered is **crossed** instead (`SEQUENTIAL_UNRECOVERED`,
 * WP-1051). The two marks say opposite things: a ring is a good fit reached
 * from a different starting model, a cross a diverged fit whose value is not a
 * measurement. The crossed point is still plotted, because a gap reads as data
 * nobody collected. Both are named by the trace's vocabulary labels
 * (`trajectoryMarks`), so the trajectory and the trace cannot call one pattern
 * two things.
 *
 * A point with no esd carries no whisker at all, which the figure owns. A
 * well-determined trajectory then shows no visible whisker, and that is the
 * data rather than a defect: on the synthetic ramp under `mccusker_default`,
 * σ(a) is 6.5e-6 Å against a 4.8e-3 Å axis over 189 px, so a 2σ whisker is
 * 0.5 px. Scaling it up to be seen would be WP-1029's "an exaggeration is not
 * a probability" one panel over.
 */
export function trajectoryLegend(traj: Trajectory, marks: Partial<TrajectoryMarks> = {},
                                 trace: Trace | null = null): LegendEntry[] {
  const { rings: reseeded = [], crosses: unrecovered = [] } = marks;
  const name = (code: string, fallback: string) =>
    trace?.vocabulary.find((r) => r.key === code)?.label ?? fallback;
  const tone = "--plot-diff";
  const out: LegendEntry[] = [
    { id: "forward", label: "forward", ink: tone, mark: "line" },
  ];
  if (traj.stderr.some((e) => typeof e === "number" && Number.isFinite(e))) {
    out.push({ id: "esd", label: "esd", ink: tone, mark: "line" });
  }
  if (traj.backward) {
    out.push({ id: "backward", label: "backward", ink: "--muted", mark: "dot" });
  }
  if (reseeded.some(Boolean)) {
    out.push({ id: "rings", label: name("SEQUENTIAL_RESEED", "reseeded"),
               ink: "--warn", mark: "ring" });
  }
  if (unrecovered.some(Boolean)) {
    out.push({ id: "crosses", label: name("SEQUENTIAL_UNRECOVERED", "unrecovered"),
               ink: "--warn", mark: "cross" });
  }
  return out;
}

/** `v` to `n` significant figures, with no trailing zeros. */
const sig = (v: number, n: number) => String(Number(v.toPrecision(n)));

/** The most step rows the table draws. The record holds one per refined path
 *  per neighbouring pair, so thousands on a long series; the panel says how
 *  many it left off. */
export const STEP_ROWS_CAP = 60;

/**
 * The step rows to draw, in the record's order.
 *
 * `SeriesResult.steps` is already largest |size_esd| first with the rows that
 * have no size last (WP-2003), so this filters and caps and sorts nothing:
 * the order is the record's, and a second sort here could disagree with it.
 * `path` limits the rows to one parameter, `null` takes every parameter.
 * `total` is the rows there are before the cap.
 */
export function stepRows(steps: SeriesStep[] | null | undefined, path: string | null,
                         cap: number = STEP_ROWS_CAP): { rows: SeriesStep[]; total: number } {
  const all = (steps ?? []).filter((s) => path === null || s.path === path);
  return { rows: all.slice(0, cap), total: all.length };
}

/** A step's cells as the table prints them. */
export function stepCells(s: SeriesStep): { between: string; step: string;
                                            esd: string; cold: string } {
  const sign = (v: number) => (v < 0 ? "−" : v > 0 ? "+" : "");
  return {
    between: `${s.labels[0]} → ${s.labels[1]}`,
    step: `${sign(s.step)}${sig(Math.abs(s.step), 3)}`,
    // no esd, no size: a step against none has no size in esds, and 0 would read as one
    esd: s.size_esd === null ? "—" : `${sign(s.size_esd)}${esdText(s.size_esd)}`,
    cold: s.cold_ratio === null ? "—" : s.cold_ratio.toFixed(2),
  };
}

/**
 * What the pointer on one point says: the pattern, its coordinate, and the
 * value, with its esd when the fit gave one. The value takes six significant
 * figures, as the hover did under plotly (`%{y:.6g}`), and the esd two, as an
 * esd is quoted. A backward point is named as the backward chain's, since
 * both chains share every coordinate.
 */
export function pointText(traj: Trajectory, i: number,
                          chain: "forward" | "backward"): string {
  const where = `${traj.labels[i] ?? i} · ${sig(traj.x[i], 6)}`;
  if (chain === "backward") return `${where}: ${sig(traj.backward![i], 6)} (backward)`;
  const e = traj.stderr[i];
  const esd = typeof e === "number" && Number.isFinite(e) ? ` ± ${sig(e, 2)}` : "";
  return `${where}: ${sig(traj.value[i], 6)}${esd}`;
}

/**
 * What a member's pattern chart offers: the fitted points, the masked ones
 * when the protocol masked any, the model, the background and the residual.
 * `rxplot.pattern`'s ids, over its own inks. A fit with no background keeps
 * the entry, disabled and saying why.
 */
export function memberLegend(masked: boolean, background = true): LegendEntry[] {
  return [
    { id: "obs", label: "obs", ink: "--plot-obs", mark: "dot" },
    ...(masked ? [{ id: "masked", label: "excluded", ink: "--muted", mark: "dot" } as LegendEntry] : []),
    { id: "calc", label: "calc", ink: "--plot-calc", mark: "line" },
    { id: "bkg", label: "background", ink: "--plot-bkg", mark: "dash",
      ...(background ? {} : { absent: "this pattern's fit has no background" }) },
    { id: "diff", label: "Δ/σ", ink: "--plot-diff", mark: "line" },
  ];
}

// ---------------------------------------------------------------- the trace

/** One row of `rietx.gui.series.TRACE_VOCABULARY`: a mark, what it is
 *  called, the field of the series answer it reads, and what it says. */
export interface TraceRow {
  key: string;
  mark: string;
  label: string;
  source: string;
  means: string;
}

/** One pattern on the trace, a failed one included. */
export interface TracePoint {
  index: number;
  label: string;
  /** the series coordinate, `null` where the pattern has none */
  x: number | null;
  /** the fit's status, or `"failed"` for a pattern with no fit */
  status: string;
  rwp: number | null;
  /** the codes of the series verdicts naming this pattern */
  marks: string[];
  /** this pattern's own fit's codes, each at its worst level */
  findings: Array<{ code: string; level: string }>;
}

export interface TraceStep {
  indices: [number, number];
  size_esd: number;
  cold_ratio: number | null;
}

/** `/api/series/result`'s `trace` (WP-1317, `rietx.gui.series.trace`). */
export interface Trace {
  x_label: string;
  points: TracePoint[];
  /** each path's largest step in its esds, read off `SeriesResult.steps` */
  largest_steps: Record<string, TraceStep>;
  vocabulary: TraceRow[];
  /** the mark of a verdict whose code the vocabulary has no row for */
  other_mark: string;
}

/** The glyph a verdict's code is drawn with: its vocabulary row's, or the
 *  served fallback for a code the table does not list, which is drawn rather
 *  than dropped because the codes are an open vocabulary. */
export function markOf(trace: Trace, code: string): string {
  return trace.vocabulary.find((r) => r.key === code)?.mark ?? trace.other_mark;
}

/**
 * What the trace figure draws, from the served trace and nothing else: each
 * pattern's index, its coordinate, the glyphs of its verdicts and the count of
 * its own findings. A series with no coordinate on any pattern is drawn on its
 * index alone (`y: null`), since a line of index against index says nothing.
 */
export function traceData(trace: Trace) {
  const y = trace.points.some((p) => p.x !== null)
    ? trace.points.map((p) => p.x) : null;
  return {
    index: trace.points.map((p) => p.index),
    y,
    marks: trace.points.map((p) => [...new Set(p.marks.map((c) => markOf(trace, c)))]),
    findings: trace.points.map((p) => p.findings.length),
  };
}

/** The key under the trace: one entry per vocabulary row this series uses,
 *  then one per code the vocabulary does not list, named by its code. The
 *  largest step is listed only when the parameter on show has one. */
export function traceKey(trace: Trace, path: string | null): TraceRow[] {
  const used = new Set(trace.points.flatMap((p) => p.marks));
  const rows = trace.vocabulary.filter((r) => {
    if (r.key === "findings") return trace.points.some((p) => p.findings.length);
    if (r.key === "largest_step") return !!(path && trace.largest_steps[path]);
    return used.has(r.key);
  });
  const known = new Set(trace.vocabulary.map((r) => r.key));
  for (const code of [...used].filter((c) => !known.has(c)).sort()) {
    rows.push({ key: code, mark: trace.other_mark, label: code,
                source: "SeriesResult.diagnostics", means: code });
  }
  return rows;
}

/** The parameter on show's largest step as the pair the trace shades, or null. */
export function largestStep(trace: Trace, path: string | null): [number, number] | null {
  const step = path ? trace.largest_steps[path] : undefined;
  return step ? [step.indices[0], step.indices[1]] : null;
}

/** What the pointer on one pattern of the trace says: its label and
 *  coordinate, its Rwp, the verdicts by their vocabulary labels, and its
 *  own findings by code. */
export function traceText(trace: Trace, i: number): string {
  const p = trace.points[i];
  if (!p) return "";
  const at = p.x === null ? `#${p.index}` : `${trace.x_label} ${sig(p.x, 6)}`;
  const label = (c: string) => trace.vocabulary.find((r) => r.key === c)?.label ?? c;
  const parts = [`${p.label} · ${at}`];
  if (p.status === "failed") parts.push("no fit");
  else if (p.rwp !== null) parts.push(`Rwp ${(p.rwp * 100).toFixed(2)}%`);
  if (p.marks.length) parts.push(p.marks.map(label).join(", "));
  if (p.findings.length) {
    parts.push(`${p.findings.length} finding${p.findings.length === 1 ? "" : "s"}: `
               + p.findings.map((f) => f.code).join(", "));
  }
  return parts.join(" · ");
}

/** The trace position `delta` patterns on from `at` (a position in
 *  `trace.points`), clamped to the series; an end when nothing is on show. */
export function stepTo(trace: Trace, at: number | null, delta: number): number {
  const last = trace.points.length - 1;
  if (last < 0) return -1;
  if (at === null) return delta < 0 ? last : 0;
  return Math.max(0, Math.min(last, at + delta));
}

/** Which series entries carry a flag, by trajectory position, matched on
 *  **label**: a trajectory skips patterns where its path is absent
 *  (`SeriesResult.trajectory` does not fill gaps), so index and position are the
 *  same list only when every pattern carried the path. */
function flagsFor(traj: Trajectory, entries: SeriesEntry[],
                  flagged: (e: SeriesEntry) => boolean): boolean[] {
  const marked = new Set(entries.filter(flagged).map((e) => e.label));
  return traj.labels.map((label) => marked.has(label));
}

/** Which trajectory points a verdict names, by trajectory position.
 *
 * A trajectory skips patterns where its path is absent (`SeriesResult.trajectory`
 * does not fill gaps), so a point is matched on **label** rather than on index —
 * the two are the same list only when every pattern carried the path. The
 * verdict is read off the trace, so the trajectory's rings and crosses
 * and the trace's glyphs are one vocabulary and cannot disagree. */
export function markedFlags(traj: Trajectory, trace: Trace | null,
                            code: string): boolean[] {
  const marked = new Set((trace?.points ?? []).filter((p) => p.marks.includes(code))
    .map((p) => p.label));
  return traj.labels.map((label) => marked.has(label));
}

/** The trajectory's per-point marks, each from the verdict it draws. */
export interface TrajectoryMarks {
  rings: boolean[];
  crosses: boolean[];
}

/** A reseed is ringed and an unrecovered fit crossed. A ring is read off the
 *  trace's verdicts; a cross off `rejected`, the server's own answer from the
 *  chain's test, so the trajectory marks exactly what the library quarantined. */
export function trajectoryMarks(traj: Trajectory, trace: Trace | null,
                                entries: SeriesEntry[],
                                rejected: boolean[]): TrajectoryMarks {
  return {
    rings: markedFlags(traj, trace, "SEQUENTIAL_RESEED"),
    crosses: unrecoveredFlags(traj, entries, rejected),
  };
}

/** Which entries the library quarantined (`SEQUENTIAL_UNRECOVERED`, WP-1051).
 *
 * `rejected` is the server's, one boolean per entry **by position** in
 * `entries`, computed by the test the chain itself applies
 * (`schemas.sequential._rejected`): the solver diverged, or the fit carries an
 * `error`-level code. It is more than `status === "diverged"`, a fit can
 * converge and still be rejected, and a display reads the field and never
 * re-derives the test (WP-2003, C2 q5). A pattern that raised has no entry, so
 * an entry's `index` is not its position. */
export function unrecoveredFlags(traj: Trajectory, entries: SeriesEntry[],
                                 rejected: boolean[]): boolean[] {
  const at = new Map(entries.map((e, i) => [e, i]));
  return flagsFor(traj, entries, (e) => rejected[at.get(e) ?? -1] === true);
}

/** Why the library rejected an entry, in the entry's own fields: the solver
 *  status and the `error`-level codes it carries. The test is the server's; this
 *  only names what made it true, for the chip's caption. */
export function rejectedBecause(e: SeriesEntry): string {
  const codes = [...new Set(e.diagnostics.filter((d) => d.level === "error")
    .map((d) => d.code))];
  const parts: string[] = [];
  if (e.status === "diverged") parts.push("the solver diverged");
  if (codes.length) {
    parts.push(`it carries the error-level code${codes.length > 1 ? "s" : ""} `
      + codes.join(", "));
  }
  return parts.join(" and ");
}

