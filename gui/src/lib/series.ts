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
 * measured lesson), so `SEQUENTIAL_PATH_DEPENDENT` is the headline and a flagged
 * trajectory is drawn differently rather than annotated in a footnote: the
 * panel gives a flagged parameter the warning colour, dashes its line
 * (`trajectoryLegend`), and — when `direction="both"` ran — draws the backward
 * chain beside it,
 * because the disagreement *is* the evidence and describing it in words would be
 * asking the reader to take it on trust.
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

export interface Trajectory {
  path: string;
  x: number[];
  x_label: string;
  value: number[];
  stderr: Array<number | null>;
  labels: string[];
  path_dependent: boolean;
  discontinuous: boolean;
  /** the backward chain's values, aligned with `x`, when `direction="both"` ran */
  backward: number[] | null;
  /** the largest forward/backward difference in combined σ; `null` when neither
   *  chain estimated an esd, which is where the fence itself abstains */
  n_sigma: number | null;
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
 * The trajectories worth showing first: the path-dependent ones, then the rest.
 *
 * Ranked on `n_sigma` **inside the flagged group only**, which is why the server
 * computes it — a `Diagnostic` carries `where` and no magnitude, so "which
 * parameter disagrees *most*" is not answerable from the fences alone (WP-1012 hit
 * the same wall; the answer was to compute it from the two chains rather than to
 * grow the schema).
 *
 * Sorting the *unflagged* ones by σ too was the first version and a browser
 * showed why not: on a clean ramp nothing is flagged, every distance is under
 * 5e-4 σ, and ordering 15 parameters by that noise put `phases.0.cell.a` — the
 * one anybody opens a ramp to look at — eighth, in an order that reads as random.
 * Below the fence there is nothing to rank, so the series' own first-seen order
 * stands (`Array.prototype.sort` is stable).
 */
export function rankTrajectories(trajectories: Trajectory[]): Trajectory[] {
  const score = (t: Trajectory) => (t.path_dependent ? 2 : t.discontinuous ? 1 : 0);
  return [...trajectories].sort((a, b) => {
    const diff = score(b) - score(a);
    if (diff !== 0) return diff;
    if (!a.path_dependent) return 0;
    return (b.n_sigma ?? 0) - (a.n_sigma ?? 0);
  });
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

/** A one-line reading of a trajectory's standing — the panel's caption. */
export function trajectoryNote(traj: Trajectory | null, sigmaBar: number): string {
  if (!traj) return "";
  if (traj.path_dependent) {
    const n = traj.n_sigma === null ? "" : ` by up to ${traj.n_sigma.toFixed(1)}σ`;
    return `the forward and backward chains disagree${n} (over ${sigmaBar}σ): this `
      + "trajectory depends on the order the series was refined in, so it is not "
      + "determined by the data alone — hold the parameter, restrain it, or quote "
      + "the between-chain spread as its uncertainty";
  }
  if (traj.discontinuous) {
    return "a step far larger than this parameter's own scatter: either the "
      + "specimen changed here or the chain failed and carried the error onward "
      + "— open that pattern's own fit before reading the jump as physics";
  }
  if (traj.backward !== null) {
    return "the forward and backward chains agree within their esds";
  }
  return "";
}

/** One legend entry: the mark it toggles, what it says, and the custom property
 *  its swatch is drawn in, so a theme switch restyles it by CSS alone. */
export interface LegendEntry {
  id: string;
  label: string;
  ink: string;
  mark: "line" | "dash" | "dot" | "ring" | "cross" | "square";
  /** Why the mark cannot be drawn, when it cannot: its entry is listed and
   *  disabled, never dropped (`CurveToggle.absent`). */
  absent?: string;
}

/**
 * What the trajectory's legend offers — the marks `rxplot.trajectory` draws.
 *
 * A flagged parameter's forward chain wears `--warn` and is dashed, and its
 * name says why: the disagreement between the chains is the evidence, so it is
 * drawn rather than described. The backward chain is offered only when
 * `direction="both"` ran.
 *
 * Reseeded points are ringed and never dropped: the fit is good, but its
 * starting values did not come from its neighbour, so it is not evidence that
 * the trajectory is continuous there (`SEQUENTIAL_RESEED`). A point no rung of
 * the ladder recovered is **crossed** instead (`SEQUENTIAL_UNRECOVERED`,
 * WP-1051). The two marks say opposite things: a ring is a good fit reached
 * from a different starting model, a cross a diverged fit whose value is not a
 * measurement. The crossed point is still plotted, because a gap reads as data
 * nobody collected. A hollow square marks a point every rung left above the
 * Rwp fence (`SEQUENTIAL_RWP_OUTLIER`, WP-1469), as `plot_trajectory` boxes
 * it, so the two renderers read one series the same way. All three are read
 * off the trace (`trajectoryMarks`) and named by its vocabulary's labels, so
 * the trajectory and the trace cannot call one pattern two things.
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
  const { rings: reseeded = [], crosses: unrecovered = [], squares: above = [] } = marks;
  const name = (code: string, fallback: string) =>
    trace?.vocabulary.find((r) => r.key === code)?.label ?? fallback;
  const flagged = traj.path_dependent;
  const tone = flagged ? "--warn" : "--plot-diff";
  const out: LegendEntry[] = [
    { id: "forward", label: flagged ? "forward (path-dependent)" : "forward",
      ink: tone, mark: flagged ? "dash" : "line" },
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
  if (above.some(Boolean)) {
    out.push({ id: "squares", label: name("SEQUENTIAL_RWP_OUTLIER", "above the fence"),
               ink: "--warn", mark: "square" });
  }
  return out;
}

/** `v` to `n` significant figures, with no trailing zeros. */
const sig = (v: number, n: number) => String(Number(v.toPrecision(n)));

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

/** Which trajectory points a verdict names, by trajectory position.
 *
 * A trajectory skips patterns where its path is absent (`SeriesResult.trajectory`
 * does not fill gaps), so a point is matched on **label** rather than on index —
 * the two are the same list only when every pattern carried the path. The
 * verdict is read off the trace, so the trajectory's rings, crosses and squares
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
  squares: boolean[];
}

/** A reseed is ringed, an unrecovered fit crossed, and a fit every rung left
 *  above the Rwp fence boxed. */
export function trajectoryMarks(traj: Trajectory, trace: Trace | null): TrajectoryMarks {
  return {
    rings: markedFlags(traj, trace, "SEQUENTIAL_RESEED"),
    crosses: markedFlags(traj, trace, "SEQUENTIAL_UNRECOVERED"),
    squares: markedFlags(traj, trace, "SEQUENTIAL_RWP_OUTLIER"),
  };
}

