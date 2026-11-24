/**
 * The series workflow's selected pattern (WP-2243 task 5, round 12 calls 2
 * and 9), as pure functions.
 *
 * One selected pattern links the step's tables and the Pattern graph. A row
 * click, ‹ › in the graph's title and ↑ ↓ all move it, and during a run it
 * follows the pattern being fitted until a row click.
 *
 * A selection names the list it was made on, because after an edit the
 * staged list is not the list the last run fitted: Patterns shows the staged
 * list, Run and Results the run's (`Series.svelte`'s `rows`). While the two
 * lists hold the same files in the same places, a selection on one is a
 * selection on both, and the graph draws the run's member, which carries
 * the fit.
 */
import type { SeriesPattern } from "../lib/series";

/** Which list a place is in: the run's (in flight or last) or the staged one. */
export type ListName = "run" | "staged";

export interface Selection {
  of: ListName;
  index: number;
}

/** What the Pattern graph draws for the series: where its curves come from,
 *  and its title line (`Pattern.svelte`'s `source` and `nav`). */
export interface SeriesView {
  source: { key: string; load: () => Promise<ArrayBuffer> };
  name: string;
  sub: string;
  canPrev: boolean;
  canNext: boolean;
}

/** Whether two lists hold the same files in the same places: a coordinate
 *  typed after a run changes the axis, never which file is where. */
export function sameMembers(a: readonly SeriesPattern[], b: readonly SeriesPattern[]): boolean {
  return a.length === b.length && a.every((p, i) => p.upload === b[i].upload
    && JSON.stringify(p.reader_options) === JSON.stringify(b[i].reader_options));
}

/** The row a table over `list` marks for the place the graph draws: its
 *  own, or the other list's while the two are the same. */
export function markedIn(drawn: Selection | null, list: ListName, same: boolean): number | null {
  return drawn && (drawn.of === list || same) ? drawn.index : null;
}

/** The list and place the graph draws. With nothing chosen it is the first
 *  pattern, as the prototype opens. A staged place draws the run's member
 *  while the lists are the same, so its fit shows. */
export function drawnPlace(sel: Selection | null, hasRun: boolean, same: boolean,
                           nRun: number, nStaged: number): Selection | null {
  const want = sel ?? { of: hasRun ? "run" : "staged", index: 0 };
  const of: ListName = want.of === "run" ? (hasRun ? "run" : "staged")
    : hasRun && same ? "run" : "staged";
  const n = of === "run" ? nRun : nStaged;
  if (!n) return null;
  return { of, index: Math.min(Math.max(want.index, 0), n - 1) };
}

/** One step through a list of `n`, held at its ends. */
export const stepped = (index: number, delta: number, n: number) =>
  Math.min(Math.max(index + delta, 0), Math.max(n - 1, 0));

/** The graph title's second half, the prototype's words: the coordinate,
 *  the place, then the fit's Rwp, "fitting…" or "not fitted". */
export function subText(x: number | null | undefined, index: number, n: number,
                        rwp: number | null | undefined, fitting: boolean): string {
  const at = `${x == null ? "" : `${x} · `}${index + 1} of ${n}`;
  if (rwp != null) return `${at} · Rwp ${(rwp * 100).toFixed(2)} %`;
  return `${at} · ${fitting ? "fitting…" : "not fitted"}`;
}

/** Whether a packed curves payload carries a fit: its header's `fitted`. */
export function packedFitted(buffer: ArrayBuffer): boolean {
  const n = new DataView(buffer).getUint32(0, true);
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer, 4, n)));
  return header.fitted === true;
}

/**
 * Fetch a member's curves, asking again while a fit the run's events say has
 * landed has not reached the route yet. A pattern's `fit_end` is emitted
 * before the chain hands the result over (`sequential`'s `on_result`), and
 * an escalated rung fits again, so the event can come first by a moment.
 */
export async function loadMember(get: () => Promise<ArrayBuffer>, expectFit: boolean,
                                 tries = 4, wait = 250): Promise<ArrayBuffer> {
  let buffer = await get();
  for (let k = 1; expectFit && k < tries && !packedFitted(buffer); k++) {
    await new Promise((r) => setTimeout(r, wait));
    buffer = await get();
  }
  return buffer;
}

/** The selection's step for a key press: ↓ the next pattern, ↑ the one
 *  before, never with a modifier, which the frame's shortcuts own. Where the
 *  key lands (a field, a menu) is the frame's `isShortcutTarget`. */
export function arrowStep(e: KeyboardEvent): number {
  if (e.altKey || e.ctrlKey || e.metaKey || e.shiftKey) return 0;
  return e.key === "ArrowDown" ? 1 : e.key === "ArrowUp" ? -1 : 0;
}
