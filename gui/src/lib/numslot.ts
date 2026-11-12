/**
 * Number slots: a value drawn so its column never moves (WP-2126).
 *
 * The maintainer's rulings (2026-11-07): numbers default to scientific notation
 * with aligned decimal points; switching a number between scientific and plain
 * moves nothing; atom-table numbers stay plain. The thresholds are the
 * prototype's, which the maintainer saw and did not object to: scientific below
 * 0.01 and from 10 000 up, plain in between, so a cell length reads 10.2514 and
 * not 1.02514×10¹.
 *
 * A number is four parts (sign and integer, fraction, the esd's tail, an
 * exponent), and a column is three widths in `ch`: the integer slot is
 * right-aligned, the fraction slot left-aligned, so the points line up, and the
 * exponent slot is reserved for every number in a column that could need one.
 * The widths come from the **last fit's** values, never from a typed edit, so an
 * edit resizes nothing.
 */
import { formatEsd, formatValue } from "./table";

/** Below this magnitude a number is written with an exponent. */
export const SCI_LOW = 0.01;
/** From this magnitude up, likewise. */
export const SCI_HIGH = 10_000;

/** Typographic minus for drawn numbers; the edit text keeps the ASCII one. */
const MINUS = "−";

export interface NumParts {
  /** sign and integer digits, `−0`, `10` */
  int: string;
  /** the digits after the point, "" for none */
  frac: string;
  /** the esd in the last place, `(2)`, or ` ±110` where it swallowed the value */
  tail: string;
  /** the power of ten, or null when the number is written plain */
  exp: number | null;
}

export function wantsSci(value: number): boolean {
  const mag = Math.abs(value);
  return Number.isFinite(value) && value !== 0 && (mag < SCI_LOW || mag >= SCI_HIGH);
}

function split(text: string): { int: string; frac: string } {
  const at = text.indexOf(".");
  const int = at < 0 ? text : text.slice(0, at);
  return { int: int.replace("-", MINUS), frac: at < 0 ? "" : text.slice(at + 1) };
}

/** A value with its esd, as slot parts. `sci` false writes it plain. */
export function numParts(value: number, esd: number | null | undefined,
                         sci = true): NumParts {
  if (!Number.isFinite(value)) return { int: String(value), frac: "", tail: "", exp: null };
  if (!(sci && wantsSci(value))) {
    return { ...split(formatValue(value, esd)), tail: formatEsd(value, esd), exp: null };
  }
  let exp = Math.floor(Math.log10(Math.abs(value)));
  const known = esd != null && Number.isFinite(esd) && esd > 0;
  for (let pass = 0; pass < 2; pass++) {
    const scale = 10 ** exp;
    const mant = value / scale;
    // the esd in the exponent's frame, the swallowed `±` form included: it is
    // drawn before the `×10ⁿ`, so a raw-unit `±1.2` would read as ±1.2×10ⁿ
    const e = known ? esd! / scale : null;
    const text = formatValue(mant, e);
    if (Math.abs(Number(text)) >= 10 && pass === 0) {
      exp += 1;               // 9.9996e-3 rounds to 10.000: renormalise once
      continue;
    }
    return { ...split(text), tail: formatEsd(mant, e), exp };
  }
  return { int: String(value), frac: "", tail: "", exp: null };
}

/** The exponent as drawn, `−3`. */
export function expText(exp: number): string {
  return String(exp).replace("-", MINUS);
}

/** Width in `ch` of the `×10ⁿ` slot: three cells of "×10", then the exponent
 *  at 0.8 em, plus a 0.3 ch gap before it. */
export function expWidth(exp: number | null): number {
  return exp === null ? 0 : 3.3 + 0.8 * expText(exp).length;
}

export interface Slots {
  int: number;
  frac: number;
  exp: number;
}

/** The slot widths a column needs for these last-fit values.
 *
 * The switch-point guard: in a scientific column, a value at zero, under 0.1 or
 * from 1000 up is near a threshold, so the column reserves an exponent slot of
 * `−3`'s width even while every value in it is plain. A refinement crossing 0.01
 * then changes the format and moves nothing. */
export function slotsFor(values: ReadonlyArray<{ value: number; esd: number | null }>,
                         sci = true): Slots {
  const slots: Slots = { int: 1, frac: 0, exp: 0 };
  for (const { value, esd } of values) {
    const parts = numParts(value, esd, sci);
    slots.int = Math.max(slots.int, parts.int.length);
    slots.frac = Math.max(slots.frac, parts.frac.length + parts.tail.length);
    slots.exp = Math.max(slots.exp, expWidth(parts.exp));
    const mag = Math.abs(value);
    if (sci && Number.isFinite(value) && (mag === 0 || mag < 0.1 || mag >= 1000)) {
      slots.exp = Math.max(slots.exp, expWidth(-3));
    }
  }
  return slots;
}

/** The whole width of a slotted number, in `ch`: integer, point, fraction,
 *  exponent. One such width per panel makes every value box the same size, so
 *  the units after them form one column (round 6, 2026-11-07). */
export function slotWidth(slots: Slots): number {
  return slots.int + 1 + slots.frac + slots.exp;
}

/** The text an editor opens with, and what a typed number is compared with
 *  (WP-1009's rule: compare to the *rendered* value, so a click in and out
 *  moves nothing). Plain where the drawn number is plain, `1.52e-3` where it
 *  is scientific. */
export function editText(value: number, esd: number | null | undefined, sci = true): string {
  if (!(sci && wantsSci(value))) return formatValue(value, esd);
  const parts = numParts(value, esd, sci);
  const mant = parts.frac ? `${parts.int}.${parts.frac}` : parts.int;
  return `${mant.replace(MINUS, "-")}e${parts.exp}`;
}
