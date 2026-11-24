/**
 * The series' Trends graph (WP-2243 task 6; round 12, calls 3 to 6, 12 and
 * 20 to 23), as pure functions.
 *
 * Each plotted value is one small panel across the series, sharing the
 * coordinate axis: points with esd bars, never joined (call 6). Two values
 * share a panel when they sit in one group, share a unit and their ranges
 * overlap, as b and c do (call 3). The second walk draws as rings over the
 * first walk's dots, and a panel names the largest gap between the walks on
 * it, which is the record's number (`Trajectory.n_sigma`, read off
 * `SeriesResult.direction_gaps`), never recomputed here (call 4). A value
 * refined on only some patterns draws only its own points (call 22).
 *
 * A value's unit is the help corpus's (`rietx.help`, the one authority for
 * what a name is), found by the family glob its path matches; the fit
 * statistics and the QPA fractions, which are not parameters, carry theirs
 * here. A value with no unit never shares a panel.
 */
import { fnmatch } from "../lib/fnmatch";
import type { HelpCorpus } from "../lib/help";
import { groupOfPath, groupTitle, leafOf, type SeriesAnswer } from "./seriesresults";

/** What Series hands the graph (`Series.svelte`'s `trends`). */
export interface TrendsView {
  answer: SeriesAnswer;
  /** the plotted paths, in the order they were ticked */
  plotted: string[];
  /** the selected pattern's series index, or null */
  selected: number | null;
  /** the title: the selected pattern's name and coordinate */
  name: string;
  x: number | null;
  canPrev: boolean;
  canNext: boolean;
  /** the series coordinate's name */
  axis: string;
}

/** One point of a value: its pattern's series index, the value, its esd,
 *  and the second walk's value there. */
export interface TrendPoint {
  index: number;
  value: number;
  esd: number | null;
  back: number | null;
}

/** One value across the series, as a panel draws it. */
export interface Trend {
  path: string;
  /** what the value adds to its group's title (`a`, `scale`, `Rwp`) */
  name: string;
  /** the group's key and title, as the Results list heads them */
  group: string;
  groupTitle: string;
  unit: string | null;
  points: TrendPoint[];
  /** the patterns it has a point on, and the patterns in the series */
  count: number;
  n: number;
  /** the largest gap between the walks, in combined esds: the record's */
  gap: number | null;
}

/** The fit statistics, which the record carries per entry rather than as a
 *  trajectory. */
const STATS: Record<string, { name: string; unit: string | null; read: (s: { rwp: number; gof: number }) => number }> = {
  rwp: { name: "Rwp", unit: "%", read: (s) => s.rwp * 100 },
  gof: { name: "GoF", unit: null, read: (s) => s.gof },
};

/** A path's unit: the help corpus's for a parameter, `%` for a QPA weight
 *  fraction (`SeriesResult.qpa_trajectory` serves percent), else none. */
export function unitOf(path: string, corpus: HelpCorpus | null): string | null {
  if (path in STATS) return STATS[path].unit;
  if (path.startsWith("qpa.")) return "%";
  const entry = corpus?.parameters?.find((e) => e.paths.some((g) => fnmatch(path, g)));
  return entry?.unit ?? null;
}

const finite = (v: unknown): number | null =>
  (typeof v === "number" && Number.isFinite(v) ? v : null);

/** One value across the series, or null where the record has none. */
export function trendOf(a: SeriesAnswer, path: string, corpus: HelpCorpus | null): Trend | null {
  const n = a.entries.length;
  const stat = STATS[path];
  if (stat) {
    const points = a.entries.flatMap((e) => (e.statistics
      ? [{ index: e.index, value: stat.read(e.statistics), esd: null, back: null }] : []));
    return { path, name: stat.name, group: "#fit", groupTitle: "Fit", unit: stat.unit,
             points, count: points.length, n, gap: null };
  }
  const t = a.trajectories.find((x) => x.path === path);
  if (!t) return null;
  // the trajectory keeps only the patterns that refined the value, in series
  // order, so its labels are matched to the entries in order: a sparse
  // value lands on its own patterns, and a label two files share on each
  const points: TrendPoint[] = [];
  let e = 0;
  t.labels.forEach((label, k) => {
    while (e < a.entries.length && a.entries[e].label !== label) e++;
    if (e >= a.entries.length) return;
    const value = finite(t.value[k]);
    if (value !== null) {
      points.push({ index: a.entries[e].index, value, esd: finite(t.stderr[k]),
                    back: finite(t.backward?.[k]) });
    }
    e++;
  });
  const group = groupOfPath(path);
  return { path, name: leafOf(path), group, groupTitle: groupTitle(group, a),
           unit: unitOf(path, corpus), points, count: t.labels.length, n,
           gap: t.n_sigma };
}

/** Plotted by default: Rwp and the first phase's a, b and c (call 12), as
 *  far as the record has them. */
export function defaultPlotted(a: SeriesAnswer): string[] {
  const has = new Set(a.trajectories.map((t) => t.path));
  return ["rwp", ...["a", "b", "c"].map((k) => `phases.0.cell.${k}`).filter((p) => has.has(p))];
}

/** Every value the Plot menu offers, grouped as the Results list groups
 *  them: the fit statistics first, then the trajectories in the record's
 *  order. */
export function plotGroups(a: SeriesAnswer): Array<{ key: string; title: string; paths: string[] }> {
  const out = [{ key: "#fit", title: "Fit", paths: ["rwp", "gof"] }];
  const byKey = new Map<string, { key: string; title: string; paths: string[] }>();
  for (const t of a.trajectories) {
    const key = groupOfPath(t.path);
    let g = byKey.get(key);
    if (!g) {
      g = { key, title: groupTitle(key, a), paths: [] };
      byKey.set(key, g);
      out.push(g);
    }
    g.paths.push(t.path);
  }
  return out;
}

/** The lowest and highest a value reaches, bars and the second walk
 *  included: what decides which values share a panel. */
function reach(t: Trend): [number, number] {
  let lo = Infinity, hi = -Infinity;
  for (const p of t.points) {
    const e = p.esd ?? 0;
    lo = Math.min(lo, p.value - e);
    hi = Math.max(hi, p.value + e);
    if (p.back !== null) {
      lo = Math.min(lo, p.back);
      hi = Math.max(hi, p.back);
    }
  }
  return Number.isFinite(lo) ? [lo, hi] : [0, 0];
}

/** The most values one panel holds, the prototype's. */
export const PANEL_MAX = 4;

/** One panel: the values it draws, in the order they were plotted. */
export interface Panel {
  trends: Trend[];
  unit: string | null;
}

/** The panels, in the order the values were plotted. A value joins the
 *  first panel of its group with the same unit whose range overlaps its own
 *  (call 3), up to `PANEL_MAX` values. */
export function panelsOf(trends: readonly Trend[]): Panel[] {
  const out: Array<Panel & { group: string; lo: number; hi: number }> = [];
  for (const t of trends) {
    const [lo, hi] = reach(t);
    const q = t.unit === null ? undefined : out.find((p) => p.unit === t.unit
      && p.group === t.group && lo <= p.hi && hi >= p.lo && p.trends.length < PANEL_MAX);
    if (q) {
      q.trends.push(t);
      q.lo = Math.min(q.lo, lo);
      q.hi = Math.max(q.hi, hi);
    } else out.push({ trends: [t], unit: t.unit, group: t.group, lo, hi });
  }
  return out.map(({ trends: ts, unit }) => ({ trends: ts, unit }));
}

/**
 * A panel's y span (call 23): the values of both walks and their esd bars,
 * reaching at most one value-spread past the values, so a value the data
 * barely fixes keeps its bar without flattening the others, and a longer bar
 * is cut at the edge. A small margin is added each side.
 */
export function spanOf(trends: readonly Trend[]): [number, number] | null {
  const vals: number[] = [], ends: number[] = [];
  for (const t of trends) {
    for (const p of t.points) {
      vals.push(p.value);
      const e = p.esd ?? 0;
      ends.push(p.value - e, p.value + e);
      if (p.back !== null) {
        vals.push(p.back);
        ends.push(p.back);
      }
    }
  }
  if (!vals.length) return null;
  let lo = Math.min(...vals), hi = Math.max(...vals);
  const spread = (hi - lo) || Math.abs(hi) * 1e-3 || 1;
  lo = Math.max(lo - spread, Math.min(...ends));
  hi = Math.min(hi + spread, Math.max(...ends));
  if (hi - lo < spread) {
    lo -= spread / 2;
    hi += spread / 2;
  }
  const pad = (hi - lo) * 0.06;
  return [lo - pad, hi + pad];
}

/** The largest gap between the walks over a panel's values, or null where
 *  none of them has one. */
export function panelGap(p: Panel): number | null {
  const gaps = p.trends.map((t) => t.gap).filter((g): g is number => g !== null);
  return gaps.length ? Math.max(...gaps) : null;
}

/** What the horizontal axis reads (call 21): the series coordinate, or the
 *  pattern's place in the list. */
export type Against = "x" | "n";

/** Each pattern's place on the horizontal axis: its coordinate, or its
 *  number from 1. The coordinate needs one on every pattern, or the axis is
 *  the pattern number. */
export function xValues(a: SeriesAnswer, against: Against): Map<number, number> {
  const useX = against === "x" && hasCoordinates(a);
  return new Map(a.entries.map((e) => [e.index, useX ? e.x! : e.index + 1]));
}

/** Whether every pattern carries a coordinate. */
export const hasCoordinates = (a: SeriesAnswer) =>
  a.entries.length > 0 && a.entries.every((e) => finite(e.x) !== null);

/** Round ticks over `[lo, hi]`, about `n` of them: 1, 2, 2.5 or 5 times a
 *  power of ten. */
export function ticks(lo: number, hi: number, n: number): { values: number[]; step: number } {
  const range = hi - lo || Math.abs(hi) || 1;
  const raw = range / Math.max(1, n);
  const p = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].map((k) => k * p).find((k) => k >= raw) ?? 10 * p;
  const values: number[] = [];
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) {
    values.push(Number(v.toPrecision(12)));
  }
  return { values, step };
}

/** The power of ten a panel's tick labels carry in its unit, for values
 *  very small or very large; 0 otherwise. */
export function powerOf(lo: number, hi: number): number {
  const m = Math.floor(Math.log10(Math.max(Math.abs(lo), Math.abs(hi)) || 1));
  return m <= -3 || m >= 5 ? m : 0;
}

/** A tick label at the step's decimals, scaled by the panel's power, with
 *  the minus sign − the readout's prose takes. */
export function tickText(v: number, step: number, power: number): string {
  const s = 10 ** power, unit = step / s;
  // the decimals that print the step exactly: two for a 0.25 step
  let digits = 0;
  while (digits < 12 && Math.abs(unit * 10 ** digits - Math.round(unit * 10 ** digits)) > 1e-6) digits++;
  return (v / s).toFixed(digits).replace("-", "−");
}

const SUP: Record<string, string> = {
  "-": "⁻", 0: "⁰", 1: "¹", 2: "²", 3: "³", 4: "⁴", 5: "⁵", 6: "⁶", 7: "⁷", 8: "⁸", 9: "⁹",
};

/** A panel's unit as its title prints it: the power of ten first. */
export function unitText(unit: string | null, power: number): string {
  const p = power ? `×10${String(power).split("").map((c) => SUP[c] ?? c).join("")}` : "";
  return [p, unit ?? ""].filter(Boolean).join(" ");
}

/** The pattern nearest a pointer, within `reach` px: `xs` are the patterns'
 *  pixel positions, keyed by series index. */
export function nearestPattern(xs: ReadonlyMap<number, number>, px: number, within = 24): number | null {
  let best: number | null = null, d = Infinity;
  for (const [i, x] of xs) {
    const dd = Math.abs(x - px);
    if (dd < d) {
      d = dd;
      best = i;
    }
  }
  return d <= within ? best : null;
}
