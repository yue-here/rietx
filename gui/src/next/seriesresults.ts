/**
 * The series workflow's Results step, as pure functions (WP-2243, task 4).
 *
 * Every number here is the record's, read and never recomputed (gui/CLAUDE.md
 * § Series): the largest walk gap is the first row of
 * `SeriesResult.direction_gaps` with a size, since the record sorts them
 * largest first, and the largest step is the first row of `SeriesResult.steps`
 * with a size, for the same reason. No verdict rides on either (round 12,
 * call 11): the step prints the size and stops.
 */
import { formatValue } from "../lib/table";
import type { DirectionGap, SeriesEntry, SeriesStep, Trajectory } from "../lib/series";

/** What the Results step reads off `GET /api/series/result`. */
export interface SeriesAnswer {
  entries: SeriesEntry[];
  trajectories: Trajectory[];
  steps: SeriesStep[] | null;
  gaps: DirectionGap[] | null;
  codes: SeriesCode[] | null;
  phaseNames: string[] | null;
  atomLabels: string[][] | null;
}

/** One row of `SeriesResult.code_counts`. */
export interface SeriesCode {
  code: string;
  path: string | null;
  count: number;
  n_patterns: number;
  level: string;
}

/** The answer route's payload, narrowed to what the step reads. */
export function answerOf(payload: any): SeriesAnswer {
  const r = payload?.result ?? {};
  return {
    entries: r.entries ?? [],
    trajectories: payload?.trajectories ?? [],
    steps: r.steps ?? null,
    gaps: r.direction_gaps ?? null,
    codes: r.code_counts ?? null,
    phaseNames: r.phase_names ?? null,
    atomLabels: r.atom_labels ?? null,
  };
}

/** A group's heading: a phase by its name, an atom by its phase and label,
 *  anything else by its dot-path (the parameter table's headings). */
export function groupTitle(group: string, a: Pick<SeriesAnswer, "phaseNames" | "atomLabels">): string {
  const m = /^phases\.(\d+)(?:\.atoms\.(\d+))?$/.exec(group);
  if (!m) return group;
  const phase = a.phaseNames?.[Number(m[1])] ?? `phases.${m[1]}`;
  if (m[2] === undefined) return phase;
  return `${phase} ${a.atomLabels?.[Number(m[1])]?.[Number(m[2])] ?? `atoms.${m[2]}`}`;
}

/** The group a trajectory's path sits under: an atom, a phase, or the
 *  path's first word (`instrument`, and the `qpa`/`r_bragg` metrics). */
export function groupOfPath(path: string): string {
  const m = /^phases\.\d+(?:\.atoms\.\d+)?/.exec(path);
  return m ? m[0] : path.split(".")[0];
}

/** What a path adds to its group's heading. */
export function leafOf(path: string): string {
  const group = groupOfPath(path);
  return path === group ? path : path.slice(group.length + 1);
}

/** A path as one line names it: its group's title and what it adds. */
export function pathName(path: string, a: Pick<SeriesAnswer, "phaseNames" | "atomLabels">): string {
  const group = groupOfPath(path);
  return path === group ? path : `${groupTitle(group, a)} ${leafOf(path)}`;
}

/** One value the step lists, with its value at one pattern. */
export interface ValueRow {
  /** the trajectory's path, or `rwp`/`gof` for the fit statistics */
  path: string;
  name: string;
  /** the patterns it has a point on, and the patterns in the series */
  count: number;
  n: number;
  /** its value at the selected pattern, as the table prints it; `""` where
   *  it has no point there */
  value: string;
}

export interface ValueGroup {
  /** the group's path prefix, unique where two titles may read alike */
  key: string;
  title: string;
  rows: ValueRow[];
}

/** The values the step lists: the fit statistics first, then every
 *  trajectory under its group, in the record's order. `at` is the selected
 *  pattern's series index. */
export function valueGroups(a: SeriesAnswer, at: number | null): ValueGroup[] {
  const n = a.entries.length;
  const entry = a.entries.find((e) => e.index === at) ?? null;
  const fitted = a.entries.filter((e) => e.statistics).length;
  const groups: ValueGroup[] = [{ key: "#fit", title: "Fit", rows: [
    { path: "rwp", name: "Rwp (%)", count: fitted, n,
      value: entry?.statistics ? (entry.statistics.rwp * 100).toFixed(2) : "" },
    { path: "gof", name: "GoF", count: fitted, n,
      value: entry?.statistics ? entry.statistics.gof.toFixed(2) : "" },
  ] }];
  const byGroup = new Map<string, ValueGroup>();
  for (const t of a.trajectories) {
    const key = groupOfPath(t.path);
    let g = byGroup.get(key);
    if (!g) {
      g = { key, title: groupTitle(key, a), rows: [] };
      byGroup.set(key, g);
      groups.push(g);
    }
    const k = entry ? t.labels.indexOf(entry.label) : -1;
    const v = k >= 0 ? t.value[k] : null;
    g.rows.push({
      path: t.path, name: leafOf(t.path), count: t.labels.length, n,
      value: v == null || !Number.isFinite(v) ? "" : formatValue(v, t.stderr[k]),
    });
  }
  return groups;
}

/** The record's largest walk gap with a size, or null where none has one. */
export function largestGap(gaps: DirectionGap[] | null): DirectionGap | null {
  return gaps?.find((g) => g.gap_esd !== null) ?? null;
}

/** The record's steps that have a size, largest first as the record keeps them. */
export function sizedSteps(steps: SeriesStep[] | null): SeriesStep[] {
  return (steps ?? []).filter((s) => s.size_esd !== null);
}

/** A pattern's warnings: the diagnostics a fit raised at warning or error. */
export function warningsOf(entry: SeriesEntry | null | undefined) {
  return (entry?.diagnostics ?? []).filter((d) => d.level === "warning" || d.level === "error");
}

/** The series' warnings, in the record's order: every code that is not info,
 *  counted over the patterns. */
export function seriesWarnings(codes: SeriesCode[] | null): SeriesCode[] {
  return (codes ?? []).filter((c) => c.level !== "info");
}

/** How many patterns a code fired on, as a line says it. */
export const countText = (c: SeriesCode) =>
  (c.count === c.n_patterns ? "every pattern" : `${c.count} of ${c.n_patterns}`);
