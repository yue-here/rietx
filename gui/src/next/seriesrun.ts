/**
 * The series workflow's Patterns and Run steps, as pure functions (WP-2243,
 * piece R7 of WP-2214's plan).
 *
 * The Run step's table is folded out of the run's own events. A series stamps
 * `series_index`, `series_label`, `series_n` and `series_pass` onto every event
 * of each pattern's fit (`sequential._SeriesStream`), and a pattern's
 * `fit_end` carries its Rwp and GoF, so the step needs no route of its own
 * while the chain runs. A restart on the ladder stamps `series_rung` too.
 * When the run ends, the record's entries replace what the fold guessed
 * (`merged`), since the record is the authority on which rung each pattern
 * kept.
 */
import type { EngineEvent } from "../lib/stream";
import { sortByX, type Rung, type SeriesEntry, type SeriesPattern } from "../lib/series";

/** The 2θ span every member covers between them, low end first. */
export function spanOf(patterns: readonly SeriesPattern[]): [number, number] | null {
  if (!patterns.length) return null;
  return [Math.min(...patterns.map((p) => p.two_theta_range[0])),
          Math.max(...patterns.map((p) => p.two_theta_range[1]))];
}

/** Whether Sort by would change nothing: no member has a coordinate, or the
 *  members with one already rise and come first (`sortByX`'s order). */
export function inOrder(patterns: readonly SeriesPattern[]): boolean {
  const order = sortByX([...patterns]);
  return order.every((p, i) => p === patterns[i]);
}

/** The axis's first word, for "Sort by T": the name without its unit. */
export function axisWord(label: string): string {
  return label.trim().split(/\s+/)[0] || "index";
}

/** Order's three choices, in the server's vocabulary, with the words and
 *  tooltips of round 12 (call 16: rietx's default, forward, comes first). */
export const ORDER: readonly { id: string; words: string; title: string }[] = [
  { id: "forward", words: "First to last",
    title: "Each pattern starts from the result of the one before it" },
  { id: "backward", words: "Last to first",
    title: "Walk from the last pattern to the first" },
  { id: "both", words: "Both, and compare",
    title: "Walk both ways. Where the two walks disagree, the answer depends on the order of the walk." },
];

/** How many walks a direction runs. */
export const walksOf = (direction: string) => (direction === "both" ? 2 : 1);

/** Where a pattern's fit started, in the Run and Results tables' words
 *  (round 12): the first pattern of a walk from the model, a later one from
 *  its neighbour, and from its neighbour with the whole plan on the ladder's
 *  second rung. */
export function startedFrom(rung: Rung | string | null): string {
  if (rung === "cold") return "model";
  if (rung === "warm_staged") return "previous, whole plan";
  if (rung === "warm") return "previous";
  return "";
}

/** One pattern's fit in one walk, as the Run step shows it. */
export interface RunFit {
  rwp: number | null;
  gof: number | null;
  status: string | null;
  rung: Rung | null;
}

/** What the Run step knows of a series run in flight. */
export interface RunProgress {
  /** patterns in the series, from the first stamped event */
  n: number | null;
  /** the walks in the order they ran, "forward" or "backward" first */
  passes: string[];
  /** the fit running now; null between fits and after the last */
  current: { index: number; label: string; pass: string } | null;
  /** the fit that started last, kept between fits, so the status line still
   *  names a pattern while the next one starts */
  last: { index: number; label: string; pass: string } | null;
  /** each walk's finished fits by series index */
  fits: Record<string, Record<number, RunFit>>;
  /** the rung each pattern's fit is on now, per walk */
  rungs: Record<string, Record<number, Rung>>;
}

export const emptyProgress = (): RunProgress =>
  ({ n: null, passes: [], current: null, last: null, fits: {}, rungs: {} });

/**
 * Fold one event into the progress. An event with no `series_index` is not a
 * series pattern's and changes nothing, so the fold can take every event the
 * page follows. A `verify` pass (a post-walk refit, WP-1305) is not a walk
 * and is left out.
 */
export function fold(p: RunProgress, event: EngineEvent): RunProgress {
  const d = event.data ?? {};
  const index = d.series_index;
  const pass = d.series_pass;
  if (typeof index !== "number" || typeof pass !== "string" || pass === "verify") return p;
  const n = typeof d.series_n === "number" ? d.series_n : p.n;
  const passes = p.passes.includes(pass) ? p.passes : [...p.passes, pass];
  const label = String(d.series_label ?? index);
  if (event.kind === "fit_start") {
    // the first fit of a walk has nothing to warm from; a restart names its rung
    const known = p.rungs[pass] ?? {};
    const rung: Rung = d.series_rung ?? known[index]
      ?? (Object.keys(known).length === 0 ? "cold" : "warm");
    const current = { index, label, pass };
    return { ...p, n, passes, current, last: current,
             rungs: { ...p.rungs, [pass]: { ...p.rungs[pass], [index]: rung } } };
  }
  if (event.kind === "fit_end") {
    const fit: RunFit = {
      rwp: typeof d.rwp === "number" ? d.rwp : null,
      gof: typeof d.gof === "number" ? d.gof : null,
      status: d.status ?? null,
      rung: (p.rungs[pass] ?? {})[index] ?? null,
    };
    return { ...p, n, passes, current: null,
             fits: { ...p.fits, [pass]: { ...p.fits[pass], [index]: fit } } };
  }
  return n === p.n && passes === p.passes ? p : { ...p, n, passes };
}

/** The status line while a series runs, counted as the Console counts: the
 *  pattern's place in the series over the series' length, per walk, never the
 *  fits finished across both walks (`lib/stream.ts:seriesPrefix`). Between two
 *  fits it names the pattern that started last. `xOf` is the coordinate a
 *  pattern's row prints, `firstPass` the walk that ran first. */
export function fittingText(p: RunProgress, walks: number, firstPass: string,
                            xOf: (index: number) => number | null | undefined): string {
  const c = p.current ?? p.last;
  if (!c) return "Fitting";
  const x = xOf(c.index);
  const walk = walks > 1 ? ` · ${c.pass === firstPass ? "first walk" : "second walk"}` : "";
  const n = p.n ? ` · ${c.index + 1} of ${p.n}` : "";
  return `Fitting ${c.label}${x == null ? "" : ` · ${x}`}${walk}${n}`;
}

/** How many fits have finished, across the walks. */
export const fitsDone = (p: RunProgress) =>
  Object.values(p.fits).reduce((sum, f) => sum + Object.keys(f).length, 0);

/** The record's entries over the fold's first walk: once the run has ended,
 *  each pattern's Rwp, GoF, status and rung are the record's. */
export function merged(p: RunProgress, entries: readonly SeriesEntry[] | null,
                       direction: string): RunProgress {
  if (!entries) return p;
  const first = direction === "backward" ? "backward" : "forward";
  const fits: Record<number, RunFit> = {};
  for (const e of entries) {
    fits[e.index] = { rwp: e.statistics?.rwp ?? null, gof: e.statistics?.gof ?? null,
                      status: e.status, rung: e.rung as Rung };
  }
  const passes = p.passes.includes(first) ? p.passes : [first, ...p.passes];
  return { ...p, passes, current: null, fits: { ...p.fits, [first]: fits } };
}

/** The patterns the second walk fitted, by series index, read off the
 *  record's first trajectory for a page that did not follow the run: the
 *  record keeps the second walk's values, never its per-pattern fits. */
export function secondWalkDone(
  entries: readonly SeriesEntry[],
  trajectory: { labels: string[]; backward: number[] | null } | null | undefined,
): Set<number> {
  const index = new Map(entries.map((e) => [e.label, e.index]));
  const done = new Set<number>();
  trajectory?.labels.forEach((label, k) => {
    const i = index.get(label);
    if (i !== undefined && Number.isFinite(trajectory.backward?.[k])) done.add(i);
  });
  return done;
}

/** An Rwp as the tables print it: a percentage at two places. */
export const rwpText = (rwp: number | null | undefined) =>
  rwp == null || !Number.isFinite(rwp) ? "" : (rwp * 100).toFixed(2);
