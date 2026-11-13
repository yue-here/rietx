/**
 * The Plan tab's editing logic (WP-2127), as pure functions so it can be
 * asserted without a DOM.
 *
 * Nothing here resolves a glob.  What a stage frees is the server's answer
 * (`GET /api/plan/resolve`, WP-1208), because it is the glob's matches minus
 * what is tied, locked, mode-fixed or degenerate with a free cell, and those
 * rules live in `ParameterTable.set_vary`.  This module only edits the list.
 */

export interface Stage {
  name: string;
  turn_on: string[];
  /** what the stage fixes after it frees `turn_on` (WP-2208); a stored plan
   *  always carries it, a stage typed here may not yet */
  turn_off?: string[];
  [key: string]: unknown;
}

/** The list with one item moved from `from` to `to`; the same list when the
 *  move is a no-op or out of range. */
export function moveStage<T>(list: readonly T[], from: number, to: number): T[] {
  if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) {
    return [...list];
  }
  const next = [...list];
  next.splice(to, 0, ...next.splice(from, 1));
  return next;
}

/**
 * Where a lifted row lands, from the rows' centres when the drag began.
 *
 * `centres[k]` is row k's vertical centre at the drag's start, and `centre` is
 * the lifted row's centre now.  The row passes a neighbour once its centre
 * crosses the neighbour's, which is how a sortable list reads in practice
 * (the lifted row and its neighbours trade places at the halfway point).
 */
export function dropIndex(centres: readonly number[], from: number, centre: number): number {
  let to = from;
  centres.forEach((c, k) => {
    if (k < from && centre < c) to = Math.min(to, k);
    if (k > from && centre > c) to = Math.max(to, k);
  });
  return to;
}

/** How far each other row slides while the row at `from` is held over `to`:
 *  the rows between make room by the lifted row's height. */
export function slideOffset(k: number, from: number, to: number, height: number): number {
  if (k > from && k <= to) return -height;
  if (k < from && k >= to) return height;
  return 0;
}

/** Two stages are the same stage when every field agrees, key order aside.
 *  An empty `turn_off` is the field's default, so it equals an absent one. */
export function sameStage(a: Stage, b: Stage): boolean {
  const keys = new Set([...Object.keys(a), ...Object.keys(b)]);
  const value = (s: Stage, key: string) =>
    key === "turn_off" && !(s.turn_off ?? []).length ? null : (s[key] ?? null);
  for (const key of keys) {
    if (JSON.stringify(value(a, key)) !== JSON.stringify(value(b, key))) return false;
  }
  return true;
}

/**
 * How many leading stages of `shown` equal the plan the server holds.
 *
 * A plan is cumulative, so what stage k frees depends on stages 0…k alone:
 * those stages' resolved facts stay true while the plan is edited further
 * down, and every stage from the first difference on has none (the WP-1208
 * dirty-plan rule, narrowed to the stages it is about).
 */
export function resolvedPrefix(saved: readonly Stage[], shown: readonly Stage[]): number {
  let n = 0;
  while (n < saved.length && n < shown.length && sameStage(saved[n], shown[n])) n += 1;
  return n;
}

/** Whether the plan on screen differs from the server's. */
export function planDiffers(saved: readonly Stage[], shown: readonly Stage[]): boolean {
  return saved.length !== shown.length || resolvedPrefix(saved, shown) < shown.length;
}

/**
 * A stage's globs with typed text added.  Commas and whitespace separate
 * globs, since a dot-path holds neither; a glob already in the list is not
 * added twice.
 */
export function addGlobs(globs: readonly string[], text: string): string[] {
  const next = [...globs];
  for (const glob of text.split(/[\s,]+/).map((s) => s.trim()).filter(Boolean)) {
    if (!next.includes(glob)) next.push(glob);
  }
  return next;
}

/** The first `stage N` name no stage in the plan has. */
export function newStageName(stages: readonly Stage[]): string {
  const taken = new Set(stages.map((s) => s.name));
  let n = stages.length + 1;
  while (taken.has(`stage ${n}`)) n += 1;
  return `stage ${n}`;
}

/**
 * An undo stack of whole states.  `record` stores the state an edit is about
 * to leave and clears the redo side, as every editor's undo does.  States are
 * copied in and out, so a caller's later mutation cannot rewrite the past.
 */
export class Undo<T> {
  private past: string[] = [];
  private future: string[] = [];

  record(state: T): void {
    this.past.push(JSON.stringify(state));
    this.future = [];
  }

  get canUndo(): boolean {
    return this.past.length > 0;
  }

  get canRedo(): boolean {
    return this.future.length > 0;
  }

  /** The state before `current`, or `null` with nothing to undo. */
  undo(current: T): T | null {
    const last = this.past.pop();
    if (last === undefined) return null;
    this.future.push(JSON.stringify(current));
    return JSON.parse(last);
  }

  /** The state `undo` left, or `null` with nothing to redo. */
  redo(current: T): T | null {
    const next = this.future.pop();
    if (next === undefined) return null;
    this.past.push(JSON.stringify(current));
    return JSON.parse(next);
  }

  clear(): void {
    this.past = [];
    this.future = [];
  }
}
