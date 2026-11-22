/** The parameter table's logic, as pure functions — grouping, filtering,
 * pending edits and the virtual window.
 *
 * Separated from the component for the reason the session is separated from the
 * server: a Pawley fit puts thousands of rows through this, and "which rows does
 * this glob select" and "which slice is on screen" are questions with answers
 * that can be asserted without a DOM.  `table.test.ts` is that assertion.
 *
 * Two rules here are the API's, not this table's.  A glob is the unit of a bulk
 * free/fix because `Refinement.set_vary` takes one and records **one** history
 * node for it; a value edit is batched into a dict because `set_values` takes
 * one and does the same (WP-1004).  So the filter box is the selection — there
 * is no second selection model, because a per-row multi-select would have to be
 * sent as N globs and would bury the history log under N nodes.
 */

export interface TieSpec {
  sources: string[];
  coefficients?: number[];
  offset?: number;
}

/** One row of `GET /api/params` — `ParameterRow` plus the two properties the
 * session adds back after `model_dump` drops them (they are the whole point). */
export interface ParamRow {
  path: string;
  value: number;
  vary: boolean;
  lo: number;
  hi: number;
  tie: TieSpec | null;
  locked: boolean;
  /** the caller declared this parameter does not move, with `Refinement.hold`
   *  (WP-1435).  The one held-reason a caller both created and can lift, and
   *  the only one a plan's `turn_on` glob loses to. */
  held: boolean;
  esd: number | null;
  mode_fixed: boolean;
  /** the fifth reason a row can be held: a free wavelength needs this
   *  histogram's cell held, since d = λ/(2 sin θ) fixes only the product */
  needs_held_cell: boolean;
  refinable: boolean;
  held_because: string;
  /** the corpus family glob this path belongs to (WP-1202), or null when no
   *  family claims it.  Matched server-side by `help_key_for`, so a client
   *  never re-derives it — the row holds the key rather than the entry because
   *  an entry describes a family and inlining one repeats a paragraph per
   *  atom. */
  help_key: string | null;
}

import { fnmatch } from "./fnmatch";

/**
 * Read a numeric field that may have crossed the wire as `"Infinity"`.
 *
 * Nearly every row has an infinite bound, and JSON has no way to spell one — so
 * this package spells it as a string (`ser_json_inf_nan="strings"`, the schemas'
 * rule since v0.2) and the GUI server follows suit, because the alternative,
 * Python's bare `Infinity` token, is not JSON at all and `JSON.parse` refuses
 * the whole response.  `Number("Infinity")` is the inverse, and `Number(null)`
 * is 0, so a genuine null is kept as `null` rather than silently becoming zero.
 */
export function num(value: unknown): number {
  if (typeof value === "number") return value;
  if (typeof value === "string") return Number(value);
  return NaN;
}

/** A `/api/params` payload's rows, with their numeric fields made numeric. */
export function normalize(rows: readonly any[]): ParamRow[] {
  return rows.map((row) => ({
    ...row,
    value: num(row.value),
    lo: num(row.lo),
    hi: num(row.hi),
    esd: row.esd == null ? null : num(row.esd),
  }));
}

/** Which reason holds this row, as a class name — or "" if free.
 *
 * Read off the row's own flags in `ParameterRow.held_because`'s order, and kept
 * as separate states rather than "greyed": `mode_fixed` comes back when the mode
 * changes, and a Le Bail phase's mandatory dummy atom is exactly the row a user
 * must not read as structurally fixed (WP-1004).
 *
 * **Five** of them, not the three WP-1011 wrote.  A free wavelength needs its
 * histogram's cell held, and that row arrived after the vocabulary did.  It went
 * unnoticed because the glyph was a ternary chain whose last arm caught
 * everything, so the wavelength of every project on screen wore the mode-fixed
 * mark (found in a browser on the 11-BM example, WP-1214).  The fifth is a
 * caller's own hold (WP-1435). */
export function heldKind(row: ParamRow): "" | "locked" | "tied" | "mode" | "hold" | "degenerate" {
  if (row.locked) return "locked";
  if (row.tie) return "tied";
  if (row.mode_fixed) return "mode";
  if (row.held) return "hold";
  if (row.needs_held_cell) return "degenerate";
  return "";
}

/** What `heldGlyph` answers for a row the padlock marks: drawn, not typed. */
export const PADLOCK = "padlock";

/** The mark a held row wears where its vary checkbox would be, or "" if free.
 *
 * Here rather than in either panel because two of them draw it now (WP-1214):
 * the parameter table and the model editor show the same reasons, and a second
 * copy of the glyphs is how they would come to disagree.  The marks distinguish;
 * `held_because` explains, and every caller shows it.  `≈` is a *degeneracy*
 * rather than a tie, which is why it is not `=`: nothing derives this row's
 * value, another free parameter merely makes it unmeasurable.
 *
 * A row the server holds for a reason with no mark here still gets one.
 * `refinable` is the server's answer and it knows reasons this client may not,
 * and a held row drawn with nothing in the box's place reads as a control that
 * failed to render — which is what the fourth reason did until WP-1214.
 * `tests/test_gui_server.py` fails when a fifth arrives.
 *
 * A lock and a hold both answer `PADLOCK`, which `HeldMark.svelte` draws as
 * the one stroked padlock (`Padlock.svelte`), never an emoji (the maintainer's
 * look of 2026-11-22, WP-2212). The mark tells them apart by its ink. */
export function heldGlyph(row: ParamRow): string {
  const kind = heldKind(row);
  if (kind === "locked" || kind === "hold") return PADLOCK;
  if (kind === "tied") return "=";
  if (kind === "degenerate") return "≈";
  return kind === "" && row.refinable ? "" : "·";
}

/** The vary flag a row would be sent with: what was toggled, else what it has. */
export function varyOf(row: ParamRow, edits: ReadonlyMap<string, boolean>): boolean {
  return edits.get(row.path) ?? row.vary;
}

/** One row toggled, as a new map.
 *
 * A toggle back onto the row's own flag **drops** the entry rather than
 * recording it: the pending count is what the Apply button is enabled by, and a
 * box clicked twice has nothing to apply — `set_vary` would record a node
 * saying nothing. */
export function varyEdit(edits: ReadonlyMap<string, boolean>, row: ParamRow,
                         checked: boolean): Map<string, boolean> {
  const next = new Map(edits);
  if (checked === row.vary) next.delete(row.path);
  else next.set(row.path, checked);
  return next;
}

/**
 * The rows a pending vary *key* names — one path, or every match of a glob.
 *
 * A vary edit has been one path per box since WP-1214, and an atom's position
 * broke that (WP-1215): the site's DOFs are freed **together** — "per-axis
 * intent does not map onto rows such as [1,1,0]", `ParameterTable` says — so one
 * box is about N rows and `phases.0.atoms.1.dof.*` is what `set_vary` should be
 * told, in one node, with the glob the structural plans already use.
 */
export function varyTargets(rows: readonly ParamRow[],
                            key: string): ParamRow[] {
  if (!/[*?[]/.test(key)) {
    const row = rows.find((r) => r.path === key);
    return row ? [row] : [];
  }
  return matches(rows, key);
}

/** Is a whole group of rows freed?  `null` when they disagree.
 *
 * The third answer is the one worth having: a box that reads `false` over a
 * half-freed site says something untrue about the other half, and the DOM has an
 * `indeterminate` for exactly this. */
export function varyOfAll(rows: readonly ParamRow[],
                          edits: ReadonlyMap<string, boolean>,
                          key: string): boolean | null {
  const pending = edits.get(key);
  if (pending !== undefined) return pending;
  const targets = varyTargets(rows, key);
  if (!targets.length) return false;
  const first = varyOf(targets[0], edits);
  return targets.every((row) => varyOf(row, edits) === first) ? first : null;
}

/** One vary key toggled — a path or a glob — as a new map.
 *
 * Drops the entry when the rows it names **already all** carry that flag, for
 * `varyEdit`'s reason one rank up: `set_vary` would record a node saying
 * nothing.  A half-freed group never drops, because setting it does say
 * something about the half that disagrees. */
export function varyEditFor(edits: ReadonlyMap<string, boolean>,
                            rows: readonly ParamRow[],
                            key: string, checked: boolean): Map<string, boolean> {
  const next = new Map(edits);
  const targets = varyTargets(rows, key);
  if (targets.length && targets.every((row) => row.vary === checked)) {
    next.delete(key);
  } else {
    next.set(key, checked);
  }
  return next;
}

/** Does a pending vary key still say something about the rows as they stand? */
export function varyStillPending(rows: readonly ParamRow[], key: string,
                                 flag: boolean): boolean {
  const targets = varyTargets(rows, key);
  return targets.length > 0 && targets.some((row) => row.vary !== flag);
}

/**
 * The group a path belongs to: the path minus its leaf, and minus one more when
 * the leaf is a bare index.
 *
 * That second clause is what puts an atom's coordinate DOFs, its `biso` and its
 * ADP components under one heading — `phases.0.atoms.3.dof.1` and
 * `phases.0.atoms.3.biso` both group as `phases.0.atoms.3` — rather than
 * scattering one atom across three headings named `dof`, `adp` and the atom.
 */
export function groupOf(path: string): string {
  const parts = path.split(".");
  if (parts.length < 2) return path;
  const leaf = parts[parts.length - 1];
  const drop = /^\d+$/.test(leaf) && parts.length > 2 ? 2 : 1;
  return parts.slice(0, parts.length - drop).join(".");
}

/**
 * The glob a filter box's text means.
 *
 * A query carrying a glob metacharacter is used verbatim; anything else is
 * wrapped as a substring search.  One function rather than two code paths
 * because the *same* string is both the preview predicate and what `PATCH
 * /api/params` sends — a filter that previewed with `includes()` and applied
 * with fnmatch would select two different sets.
 */
export function asGlob(query: string): string {
  const text = query.trim();
  if (!text) return "*";
  return /[*?[]/.test(text) ? text : `*${text}*`;
}

export function matches(rows: readonly ParamRow[], glob: string): ParamRow[] {
  return glob === "*" ? [...rows] : rows.filter((row) => fnmatch(row.path, glob));
}

/** What a bulk free/fix would do, for the count beside the button.
 *
 * `freeable` excludes locked and tied rows because `set_vary` never matches
 * them however broad the glob — showing "free 214" and having 41 move is how a
 * preview loses its meaning. `mode_fixed` rows *are* counted: they can be freed
 * and are dropped again when a stage runs, which is a different fact. */
export function selection(rows: readonly ParamRow[], glob: string) {
  const hit = matches(rows, glob);
  const freeable = hit.filter((row) => !row.locked && !row.tie);
  return {
    glob,
    matched: hit.length,
    freeable: freeable.length,
    toFree: freeable.filter((row) => !row.vary).length,
    toFix: freeable.filter((row) => row.vary).length,
  };
}

export type Item =
  | { kind: "group"; key: string; label: string; n: number; free: number }
  | { kind: "row"; key: string; row: ParamRow };

export interface FlattenOptions {
  /** the filter glob (`asGlob` of the box's text) */
  glob?: string;
  /** group keys the user collapsed */
  collapsed?: ReadonlySet<string>;
  /** Simple mode: hide rows nothing can free, and say how many were hidden */
  simple?: boolean;
}

/** Rows → the flat list a virtual scroller indexes, headers included.
 *
 * Group order and row order are the server's, which is the θ-vector order — the
 * order a stage plan frees things in, and the order the text document prints.
 * Sorting alphabetically here would make three views of one table disagree. */
export function flatten(rows: readonly ParamRow[], options: FlattenOptions = {}) {
  const { glob = "*", collapsed = new Set<string>(), simple = false } = options;
  const visible = matches(rows, glob);
  const held = simple ? visible.filter((row) => !row.refinable).length : 0;
  const kept = simple ? visible.filter((row) => row.refinable) : visible;

  const order: string[] = [];
  const byGroup = new Map<string, ParamRow[]>();
  for (const row of kept) {
    const key = groupOf(row.path);
    let bucket = byGroup.get(key);
    if (bucket === undefined) {
      bucket = [];
      byGroup.set(key, bucket);
      order.push(key);
    }
    bucket.push(row);
  }

  const items: Item[] = [];
  for (const key of order) {
    const bucket = byGroup.get(key)!;
    items.push({
      kind: "group",
      key,
      label: key,
      n: bucket.length,
      free: bucket.filter((row) => row.vary).length,
    });
    if (collapsed.has(key)) continue;
    for (const row of bucket) items.push({ kind: "row", key: row.path, row });
  }
  return { items, groups: order, shown: kept.length, hidden: held };
}

/** The slice of a fixed-height list that a viewport shows, plus its padding.
 *
 * Fixed row height on purpose: measuring rows would mean rendering them, which
 * is the cost virtualization exists to avoid. `overscan` rows above and below
 * keep a fast scroll from showing blank bands. */
export function windowSlice(
  count: number,
  scrollTop: number,
  viewport: number,
  rowHeight: number,
  overscan = 6,
) {
  const first = Math.max(0, Math.floor(scrollTop / rowHeight) - overscan);
  const visible = Math.ceil(viewport / rowHeight) + 2 * overscan;
  const end = Math.min(count, first + visible);
  const start = Math.min(first, Math.max(0, end - visible));
  return {
    start,
    end,
    padTop: start * rowHeight,
    padBottom: Math.max(0, (count - end) * rowHeight),
  };
}

/**
 * Why this typed value cannot be sent, or `""` if it can.
 *
 * Checked here because the row carries its own bounds and `set_values` refuses
 * an out-of-bounds value (WP-1004) — a round trip to be told what the row
 * already said is a slow way to render a red border.  The *refusals that only
 * the server can make* (a tied path, a locked one) are not duplicated: those
 * rows have no editable cell at all.
 */
export function validateEdit(row: ParamRow, text: string): string {
  const value = Number(text);
  if (text.trim() === "" || !Number.isFinite(value)) return "not a number";
  if (value < row.lo) return `below the lower bound ${row.lo}`;
  if (value > row.hi) return `above the upper bound ${row.hi}`;
  return "";
}

export interface EditState {
  /** the `{path: value}` body of one `set_values` call */
  values: Record<string, number>;
  /** paths whose typed text cannot be sent, with the reason */
  invalid: Array<{ path: string; why: string }>;
  /** how many cells the user has touched — invalid ones included, so the
   *  Revert affordance exists for the edit that most needs it */
  touched: number;
}

/**
 * What the grid's pending edits amount to.
 *
 * `against` says what a cell's text is compared with, and it follows what the
 * cell's editor opened on. `"drawn"`, the default, compares with the
 * **rendered** value: a field that opens on the value at the precision its esd
 * justifies (the Model form) would otherwise turn "clicked in and out again"
 * into a `set_values` that quietly truncates the parameter (WP-1009's rule for
 * the text document). `"stored"` compares the number with the stored float:
 * the Parameters panel's editor opens on the full value (WP-2223), so the
 * drawn digits typed in are a different number and are sent.
 */
export function editState(
  rows: readonly ParamRow[],
  edits: ReadonlyMap<string, string>,
  varyCount = 0,
  against: "drawn" | "stored" = "drawn",
): EditState {
  const byPath = new Map(rows.map((row) => [row.path, row]));
  const values: Record<string, number> = {};
  const invalid: Array<{ path: string; why: string }> = [];
  let touched = varyCount;
  for (const [path, text] of edits) {
    const row = byPath.get(path);
    if (!row) continue;
    const why = validateEdit(row, text);
    if (why) {
      invalid.push({ path, why });
      touched += 1;
    } else if (against === "stored" ? Number(text) !== row.value
                                     : text.trim() !== formatValue(row.value, row.esd)) {
      values[path] = Number(text);
      touched += 1;
    }
  }
  return { values, invalid, touched };
}

/**
 * Whether an esd has swallowed the value it qualifies (WP-1209).
 *
 * The last-digit convention counts the esd in the value's last decimal place,
 * and an esd of 1 or more leaves no decimal place to count in: `places` clamps
 * to zero and the value rounds to an integer. That is still right for
 * `12346(56)`, where the esd is a precision. It is wrong for a 2θ of 35.09°
 * with the measured degenerate σ of 111° (WP-1110 item 14 — a flat direction
 * whose esd is not a precision at all), which printed `35(111)` and reads as a
 * typo. So the guard is both conditions at once: an esd at or above 1 *and*
 * larger than the value, and such a pair is written as the value at its own
 * precision with `±esd` beside it. Below 1 the convention still holds —
 * `0.002(5)` is a coordinate consistent with zero, not a defect.
 */
export function esdSwallowsValue(value: number, esd: number): boolean {
  return esd >= 1 && esd > Math.abs(value);
}

/** A value with its esd, at the precision the esd justifies.
 *
 * One significant figure on the esd sets the value's last place — the
 * crystallographic convention, and the reason a table showing `4.156780000` for
 * a parameter known to ±0.0002 is worse than useless. Without an esd the value
 * is shown at 6 significant figures, which is a display choice and says nothing;
 * an esd that has swallowed the value (`esdSwallowsValue`) is treated as none. */
export function formatValue(value: number, esd: number | null | undefined): string {
  if (!Number.isFinite(value)) return String(value);
  if (esd == null || !Number.isFinite(esd) || esd <= 0 || esdSwallowsValue(value, esd)) {
    return String(Number(value.toPrecision(6)));
  }
  const places = Math.max(0, Math.min(12, -Math.floor(Math.log10(esd))));
  return value.toFixed(places);
}

/**
 * The part of a dot-path a group heading has not already shown.
 *
 * The last segment alone is enough for `…cell.a` and useless for
 * `phases.0.atoms.0.adp.0`, which renders as **`0`** — measured in a browser on
 * NAC, where the parameter table listed five rows called `0`, `1`, `2`, `3` and
 * `occ` under one heading (WP-1029). A purely numeric leaf is an index into
 * something, so it keeps the thing it indexes.
 */
export function leafName(path: string, group = ""): string {
  const rest = group && path.startsWith(`${group}.`) ? path.slice(group.length + 1) : path;
  const parts = rest.split(".");
  const last = parts[parts.length - 1];
  if (parts.length > 1 && /^\d+$/.test(last)) return parts.slice(-2).join(".");
  return last;
}

/** `4.15678(19)` — the esd in units of the value's last decimal place; ` ±110`
 * where the esd has swallowed the value and there is no last place to count in
 * (`esdSwallowsValue`). Two significant figures there, exponential from 1e6 —
 * the corundum lines' degenerate position esds are ~1e17 and ~1e49 degrees. */
export function formatEsd(value: number, esd: number | null | undefined): string {
  if (esd == null || !Number.isFinite(esd) || esd <= 0) return "";
  if (esdSwallowsValue(value, esd)) {
    const two = Number(esd.toPrecision(2));  // 999 999 rounds to 1e6: decide after
    return ` ±${two >= 1e6 ? two.toExponential(1) : two}`;
  }
  const places = Math.max(0, Math.min(12, -Math.floor(Math.log10(esd))));
  const digits = Math.round(esd * 10 ** places);
  return `(${digits})`;
}
