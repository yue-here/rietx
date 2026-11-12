/**
 * The rebuild's words where today's page spells a thing otherwise (WP-2216).
 *
 * Today's page keeps its own until the swap, so these live beside the page
 * that uses them rather than in the shared `lib/`.
 */

/** The legend's words, one per curve. The status bar's hover readout labels
 *  its numbers with these same words, so the two never disagree. A phase's
 *  ticks are labelled with the phase's name, which is not in this table. */
export const CURVE_WORDS: Record<string, string> = {
  obs: "Observed", masked: "Excluded", calc: "Last fit", bkg: "Background",
  diff: "Difference",
};

/**
 * A unit as the prototype writes it: `° 2θ` and `°² 2θ`, never `deg 2θ`.
 *
 * The corpus's units are the schema's own (`rietx.help`, through
 * `UNIT_DISPLAY`), and the manual and today's page print them as they are.
 * The word `deg` becomes the sign wherever it stands as a word, so a cell
 * angle reads `°` and a peak area `counts·° 2θ`.
 */
export function unitText(unit: string): string {
  return unit.replace(/\bdeg\b/g, "°");
}

/**
 * A row's name as the prototype writes it: the broadening rows lose
 * "broadening", which the group's title ("Size and strain") already says, so
 * each fits on one line (`Lorentzian size`, `Gaussian strain`).
 */
export function shortTitle(title: string): string {
  return title.replace(/ broadening$/, "");
}
