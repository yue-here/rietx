/**
 * The Structure graph's two pure helpers (WP-2218, inventory rows 69-82).
 */
import type { StatusReadout } from "./readout";

/**
 * The hover line for the status bar's right half (row 74): what is under the
 * pointer as the viewer names it (`lib/structure3d.ts`'s `atomLabel`,
 * `bondLabel`, `polyhedronLabel`, `fillLabel`), split at its first double space
 * into a label and the rest, as the Pattern graph's readout pairs a word and a
 * number. `null` when nothing is under the pointer, so the bar shows its
 * findings count again.
 */
export function structureReadout(text: string): StatusReadout | null {
  const line = text.trim();
  if (!line) return null;
  const cut = line.indexOf("  ");
  const label = cut < 0 ? line : line.slice(0, cut);
  const value = cut < 0 ? "" : line.slice(cut).replace(/^\s*·?\s*/, "");
  return { items: [{ id: "structure", label, value, slot: value.length, left: true }],
           dropOrder: [] };
}

/**
 * The unapplied slider values that can move the drawing, or `null` when none
 * can. An instrument value moves the pattern and never the structure, so a
 * zero-shift drag leaves the graph at the current values rather than calling
 * an unchanged drawing a preview.
 */
export function structureValues(
  values: Record<string, number> | null | undefined,
): Record<string, number> | null {
  if (!values) return null;
  const kept = Object.entries(values).filter(([path]) => !path.startsWith("instrument."));
  return kept.length ? Object.fromEntries(kept) : null;
}
