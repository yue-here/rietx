/**
 * The hover readout as the rebuild's status bar prints it (WP-2216; the
 * maintainer's ruling of 2026-11-11, "try b"):
 *
 *     2θ 31.860°   d 2.806 Å   Observed 19693   Last fit 20307
 *     Background 175   Difference −4.4σ   fluorapatite (3 −1 1) +0.012°
 *
 * - each label is the legend's own word (`CURVE_WORDS`), and a phase's
 *   reflection is labelled with the phase's name, as its legend row is;
 * - 2θ, d and a reflection's offset take three decimals, counts are whole and
 *   ungrouped, and the weighted difference takes one decimal in σ;
 * - a negative number takes the minus sign − (U+2212), as the rest of the
 *   readout's prose does.
 *
 * Today's `lib/plot.ts:readout` is the authority for *what* is read at the
 * pointer: the nearest drawn channel over the fitted and the excluded arms, a
 * row only for a curve that is drawn, and the nearest tick per phase paired by
 * index with its reflection. This re-asks those questions with the same
 * helpers and formats the answers, because today's strip keeps today's digits
 * until the swap.
 *
 * The difference is the server's weighted residual, Δ/σ with σ from
 * `RefinementResult.sig()` (`viz.packed.curve_arrays`), never re-derived here.
 */
import { formatHkl } from "../lib/peaks";
import { nearestIndex, residual, shows, type ResidualKind, type Window } from "../lib/plot";
import { CURVE_WORDS } from "./words";

/** One labelled number in the status bar. */
export interface ReadItem {
  /** stable across hovers: `pos`, `d`, a curve id, or `ticks:<phase>` */
  id: string;
  label: string;
  value: string;
  /** the value's slot in `ch`, from the payload, so a sweep moves no label */
  slot: number;
  /** a reflection's value reads from its left, since its width varies */
  left?: boolean;
}

export interface StatusReadout {
  items: ReadItem[];
  /** the ids a narrow window drops, first to last: the reflections from the
   *  right, then Background (the ruling's order) */
  dropOrder: string[];
}

export interface StatusInputs {
  kind: ResidualKind;
  /** the source's emission lines, primary first: d is the primary's */
  wavelengths?: readonly number[] | null;
  /** the curves switched off: the readout names what is drawn */
  hidden?: readonly string[];
  /** what a cumulative χ² drawn from the view's left edge has subtracted */
  chi2Base?: number;
}

/** What a field with nothing to say prints, as today's strip prints it. */
export const EMPTY = "—";
const MINUS = "−";

/** `v` at `places` decimals with a typographic minus, and no `−0`. */
export function signed(v: number, places: number, plus = false): string {
  const text = Math.abs(v).toFixed(places);
  const zero = Number(text) === 0;
  return (v < 0 && !zero ? MINUS : plus ? "+" : "") + text;
}

/** The characters the widest value of `xs` takes at `places` decimals. */
function widest(xs: ArrayLike<number> | undefined, places: number): number {
  let lo = 0, hi = 0;
  for (let i = 0; i < (xs?.length ?? 0); i++) {
    const v = xs![i];
    if (!Number.isFinite(v)) continue;
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  return Math.max(signed(lo, places).length, signed(hi, places).length);
}

/** Slots per payload: a hover reads ~20 000 channels' extremes once, not per move. */
const SLOTS = new WeakMap<object, Map<string, number>>();
function slotOf(w: Window, key: string, xs: ArrayLike<number> | undefined, places: number): number {
  let m = SLOTS.get(w);
  if (!m) SLOTS.set(w, (m = new Map()));
  let n = m.get(key);
  if (n === undefined) m.set(key, (n = widest(xs, places)));
  return n;
}

/**
 * Everything the plot knows at 2θ `x`, as the status bar prints it, or null
 * with nothing to read.
 */
export function statusReadout(w: Window | null, x: number | null,
                              inputs: StatusInputs): StatusReadout | null {
  if (!w || x == null || !Number.isFinite(x)) return null;
  const hidden = inputs.hidden ?? [];
  const fitted = w.two_theta;
  const excluded: ArrayLike<number> = shows(hidden, "masked") ? w.excluded?.two_theta ?? [] : [];
  if (!fitted.length && !excluded.length) return null;
  const kf = nearestIndex(fitted, x);
  const kx = nearestIndex(excluded, x);
  const masked = kf < 0 || (kx >= 0 && Math.abs(excluded[kx] - x) < Math.abs(fitted[kf] - x));
  const k = masked ? kx : kf;
  const at = masked ? excluded[k] : fitted[k];
  const items: ReadItem[] = [];

  const lam = inputs.wavelengths?.[0];
  const s = Math.sin((at * Math.PI) / 360);
  items.push({ id: "pos", label: "2θ", value: `${signed(at, 3)}°`, slot: 8 });
  if (lam) items.push({ id: "d", label: "d", value: s > 0 ? `${signed(lam / (2 * s), 3)} Å` : EMPTY, slot: 8 });

  const count = (v: number | undefined | null) =>
    v == null || !Number.isFinite(v) ? EMPTY : signed(Math.round(v), 0);
  // a masked channel is in no result, so there is no model at it to quote
  const fit = (v: number | undefined | null) => (masked ? EMPTY : count(v));
  // each curve's own widest value, so a background of hundreds is not set in
  // a slot sized for peaks of tens of thousands
  if (shows(hidden, "obs")) {
    items.push({ id: "obs", label: CURVE_WORDS.obs,
      slot: Math.max(slotOf(w, "obs", w.y_obs, 0), slotOf(w, "xobs", w.excluded?.y_obs, 0)),
      value: count(masked ? w.excluded?.y_obs?.[k] : w.y_obs?.[k]) });
  }
  if (!w.raw) {
    if (shows(hidden, "calc")) {
      items.push({ id: "calc", label: CURVE_WORDS.calc, value: fit(w.y_calc?.[k]),
        slot: slotOf(w, "calc", w.y_calc, 0) });
    }
    if (w.y_background?.length && shows(hidden, "bkg")) {
      items.push({ id: "bkg", label: CURVE_WORDS.bkg, value: fit(w.y_background[k]),
        slot: slotOf(w, "bkg", w.y_background, 0) });
    }
    if (shows(hidden, "diff")) {
      const res = residual(inputs.kind, w);
      const base = inputs.kind === "cumulative" ? inputs.chi2Base ?? 0 : 0;
      const v = res.values[k];
      const places = inputs.kind === "delta" ? 0 : 1;
      const unit = inputs.kind === "weighted" ? "σ" : "";
      const value = masked || v == null || !Number.isFinite(v) ? EMPTY
        : `${signed(inputs.kind === "delta" ? Math.round(v - base) : v - base, places)}${unit}`;
      items.push({ id: "diff", label: CURVE_WORDS.diff, value,
        slot: slotOf(w, `diff:${inputs.kind}`, res.values, places) + unit.length });
    }
  }

  const ticks: string[] = [];
  for (const [phase, positions] of Object.entries(w.ticks ?? {})) {
    if (!shows(hidden, `ticks:${phase}`)) continue;
    const j = nearestIndex(positions, at);
    const hkl = j < 0 ? undefined : (w.tick_hkl ?? {})[phase]?.[j];
    const near = j < 0 ? EMPTY : `${signed(positions[j] - at, 3, true)}°`;
    const id = `ticks:${phase}`;
    ticks.push(id);
    items.push({ id, label: phase, left: true, slot: 18,
      value: hkl?.length === 3 ? `${formatHkl(hkl)} ${near}` : near });
  }
  return { items, dropOrder: [...ticks.reverse(), "bkg"] };
}

/**
 * Which items a bar `room` wide drops: none while the ink fits, else the ids
 * of `order` in turn until it does. `widths` are each item's measured box and
 * `gap` the space between two; an item never measured is never dropped.
 * Past the order's end the bar cuts the reading's right end, keeping 2θ.
 */
export function dropsFor(ids: readonly string[], widths: ReadonlyMap<string, number>,
                         gap: number, room: number, order: readonly string[]): Set<string> {
  let ink = ids.reduce((sum, id) => sum + (widths.get(id) ?? 0), 0)
    + gap * Math.max(ids.length - 1, 0);
  const out = new Set<string>();
  for (const id of order) {
    if (ink <= room) break;
    const w = widths.get(id);
    if (w === undefined || !ids.includes(id)) continue;
    ink -= w + gap;
    out.add(id);
  }
  return out;
}
