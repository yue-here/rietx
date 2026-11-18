/**
 * Drag-to-resize arithmetic, as pure functions.
 *
 * `Console.svelte` (WP-1010) shipped the whole rule inline — a grip on one edge,
 * a floor the drag cannot cross, a neighbour that must survive it, and **one
 * write per drag rather than one per pixel**.  WP-1029 needs the same rule on
 * the plot/sidebar split and on the model pane's columns, so the numbers move
 * here and the grip moves to `panels/Splitter.svelte`.
 *
 * Splitting it this way is not tidiness: jsdom has no layout, so a splitter's
 * *effect* is a screenshot question and only its arithmetic can be asserted.
 * Everything a test can judge is in this file.
 */

/** Which way the pointer travels to make the pane on the grip's side *bigger*. */
export type Grow = "up" | "down" | "left" | "right";

const AXIS = { up: "y", down: "y", left: "x", right: "x" } as const;
const SIGN = { up: -1, down: 1, left: -1, right: 1 } as const;

/** The pointer coordinate a grip reads; the other one is noise during a drag. */
export function axisOf(grow: Grow): "x" | "y" {
  return AXIS[grow];
}

/** The size a pointer now at `at` asks for, having grabbed at `from` on a pane
 *  that was `start` px.  Sign only: the clamping is the next function's. */
export function dragged(start: number, from: number, at: number, grow: Grow): number {
  return start + SIGN[grow] * (at - from);
}

/**
 * Clamp to the floor, and to whatever must survive of the pane next door.
 *
 * `available` is the extent the two panes share.  Zero (or anything too small to
 * hold `min + keep`) means nothing is measurable — jsdom, or a drag before the
 * first layout — and then only the floor applies, which is the fallback
 * `Console.svelte` shipped with.
 */
export function clampSize(value: number, min: number, keep: number, available: number): number {
  const ceiling = available > keep + min ? available - keep : Number.POSITIVE_INFINITY;
  return Math.round(Math.min(Math.max(value, min), ceiling));
}

/**
 * Fit stored column widths into the space there actually is.
 *
 * A drag clamps against the extent it was performed in; **a stored width has to
 * be clamped against the extent it is being rendered in**, and no drag is
 * present to do it. Found in a browser: widths saved at 1500 px reopened at
 * 1000 px left the third column **24 px wide** — a 3D scene in a sliver. The
 * sidebar covers the same case with a CSS `max-width`, which a row of N sized
 * columns cannot express, so this is that guard as arithmetic.
 *
 * Shrinks proportionally rather than truncating the last column, because the
 * user's *relative* choice is the part worth keeping when their absolute one no
 * longer fits. `available <= 0` means nothing is measurable (jsdom, or before
 * layout) and the widths pass through, which is the same fallback `clampSize`
 * makes.
 */
/**
 * What each of the model pane's three columns needs, in px.
 *
 * `structure` is **measured**, not chosen (WP-1034 task 1, re-measured WP-1215
 * when the atom row went from seven columns to eleven): the atom table's
 * `min-content` is **642 px** on the fluorapatite example, and the column adds
 * 24 px of padding. Below 666 the table cannot show its eleven columns at all.
 *
 * Measured in the widest state the table reaches, which is not the state it
 * opens in: 610 px plain, 642 with one atom anisotropic — the disclosure button
 * appears (+10) and `biso` gives its checkbox up for the locked mark (+23).
 * Opening the disclosure costs nothing further, and that is a fix rather than a
 * fact: a `colspan` cell's grid **is** part of the table's min-content, so four
 * 210 px U^ij patterns made the whole table 840 px until the track floor became
 * `min(210px, 100%)` (`Model.svelte`).
 *
 * The example that sets the number moved too. WP-1034 measured NAC because NAC
 * was then the widest thing this table had to draw; FAP is wider now for a
 * reason the column count does not predict — three coordinate cells at 65 px
 * against 50, because a minus sign is width. So both are measured (NAC: 567 /
 * 599) rather than one being scaled from the other.
 *
 * `form` is **320** since WP-1216, and it is arithmetic too: the instrument form
 * is three columns wide at every width — that is what puts U V W over X Y — so
 * it needs 3 x 92 px of track, 2 x 10 px of gap and the column's own 24 px of
 * padding. It was 200 while the form was a wrapping row that could reflow to one
 * column; a declared column count is a declared minimum, and at 203 px the
 * profile's tracks came out at 53 px with `-0.0002` clipped inside one. The
 * three constants live in `Model.svelte` (`--w-num`, `--grid-gap`, the column's
 * padding) and `resize.test.ts` crosses this number against them, because a
 * width restated is a width that goes stale (WP-1215).
 *
 * `view` is `Model.svelte`'s own `VIEW_KEEP`; `form` is where its `COL_MIN` now
 * comes *from*, so the threshold below is arithmetic rather than a number
 * somebody liked, and the CSS basis reads it through `--col-min`.
 */
export const MODEL_MIN = { structure: 666, form: 320, view: 260 } as const;

/**
 * The width an inline splitter grip takes out of the row, in px.
 *
 * `Splitter.svelte`'s `flex: 0 0 5px`. It is here because the stacking threshold
 * is the *sum of what the row must hold*, and two grips sit inside that row
 * between the three columns — left out, the arithmetic said 1126 and the
 * structure column measured 636 of the 642 its table needs, side-scrolling by
 * six pixels at exactly the width the threshold exists to protect (WP-1215; the
 * gap was there at 932 too and no one had measured it).
 */
export const GRIP = 5;

/**
 * Does the model pane have to become one stacked column?
 *
 * Three columns side by side need the structure column's floor plus a form
 * column plus what the 3D view keeps **plus the two grips between them** — 1256
 * px since WP-1216 (1136 while `form` was 200, 932 before WP-1215 counted the
 * grips). Below that something is being squeezed under
 * its minimum, and the thing that loses is the atom table, which side-scrolls
 * *the whole column* and takes the cell row and the headings with it (measured
 * at 860 px: `10.25710.25790` where a, b, c should be).
 *
 * Zero means nothing is measurable (jsdom, or before the first layout), and
 * then the flex defaults hold — the same fallback `clampSize` and `fitColumns`
 * make.
 */
export function modelStacks(available: number): boolean {
  return available > 0 && available < modelThreshold();
}

/** The width three columns need, grips included — the sum, in one place. */
export function modelThreshold(): number {
  return MODEL_MIN.structure + MODEL_MIN.form + MODEL_MIN.view + 2 * GRIP;
}

/**
 * The window's two panels and the floor each keeps beside the other (WP-2123).
 *
 * `side` is the panel column's floor, the lower end of its CSS clamp
 * `clamp(340px, 38%, 560px)` and the floor its sash drags to. `graphs` is the
 * floor the design rounds settled for the graph column (2026-11-07): under it
 * the pattern's knob rows wrap twice and the plot is shorter than it is wide.
 * The side column's sash is an overlay on its edge, so no grip sits in the row
 * and the sum is the whole arithmetic.
 */
export const SHELL_MIN = { graphs: 420, side: 340 } as const;

/** The window width below which graphs and model cannot sit side by side. */
export function shellThreshold(): number {
  return SHELL_MIN.graphs + SHELL_MIN.side;
}

/**
 * Does the window drop to one column, graphs above the model?
 *
 * The maintainer's ruling of 2026-11-07: below a width the window becomes one
 * column, as the Claude app drops to one panel. The width is where side by side
 * stops being possible, computed from the floors above rather than chosen.
 * Zero means nothing is measurable (jsdom before layout), and then the window
 * stays side by side, the same fallback `modelStacks` makes.
 */
export function shellStacks(width: number): boolean {
  return width > 0 && width < shellThreshold();
}

/**
 * The staged-series table's two halves, in px — **measured**, not chosen.
 *
 * On the browser pass (WP-1016, three ramp patterns, 1500 px window): the row is
 * 539 px wide, of which `#` (22) + label (117) + the coordinate (83) + the
 * reorder/remove buttons (86) are **308**, and file (73) + points (47) + 2θ range
 * (78) + σ (33) are **231**. The split is not cosmetic — the buttons are the
 * panel's main verb and they are the *last* column, so below the floor they go off
 * the right edge of a box that scrolls horizontally, and a user has to scroll a
 * table sideways to reorder a series.
 */
export const SERIES_MIN = { core: 308, detail: 231 } as const;

/**
 * Does the staged-series table have to drop its descriptive columns?
 *
 * `available` is the panel's own width. The sum plus the section's 20 px of
 * padding is 559, which is what a `clamp(340px, 38%, 560px)` sidebar measures at
 * the ceiling — so the full table fits exactly at the shipped default and
 * anything narrower reflows. Nothing is lost when it does: the reader, the point
 * count, the range and the σ source move into the label cell's tooltip.
 *
 * Zero means nothing is measurable (jsdom, or before the first layout) and the
 * full table stands — the same fallback `clampSize`, `fitColumns` and
 * `modelStacks` make.
 */
export function seriesCompact(available: number): boolean {
  return available > 0 && available < SERIES_MIN.core + SERIES_MIN.detail;
}

export function fitColumns(widths: number[] | null | undefined, available: number,
                           min = 200, keep = 260): number[] | null {
  if (!widths || !widths.length || available <= 0) return widths ?? null;
  const room = available - keep;
  const total = widths.reduce((a, b) => a + b, 0);
  if (total <= room) return widths;
  const floor = min * widths.length;
  if (room <= floor) return widths.map(() => min);
  const factor = room / total;
  return widths.map((w) => Math.max(min, Math.round(w * factor)));
}
