/**
 * The Interactive tab's logic (WP-2128): which values get a slider, the range
 * each opens on, the track's scale, the number's one format, and the request
 * throttle the drags go through.
 *
 * Pure functions and one small class, so vitest asserts them without a DOM.
 * `panels/Interactive.svelte` draws them; the graphs draw what the route sends.
 *
 * The designs are the maintainer's, reviewed on screen between 2026-11-06 and
 * 2026-11-08 and restated with their rulings in WP-2128 § Context: sliders move
 * the model by hand and nothing refines until the person asks; some tracks are
 * non-linear; the unit lives in the range pop-up only; and a number never
 * changes format while it is dragged, so no text shifts.
 */

import type { Curves } from "rxplot";

import type { HelpCorpus } from "./help";
import { paramKey, resolve } from "./help";
import { fnmatch } from "./fnmatch";
import type { ParamRow } from "./table";

/** How a slider's default range is built (WP-2128 § Context, the prototype's rules). */
export type Kind = "scale" | "zero" | "disp" | "cell" | "axial" | "gauss" | "lor";

/** The families that get a slider, in the order they are drawn. A family is
 *  the glob a row's path matches; the first match wins. */
export const FAMILIES: readonly { glob: string; kind: Kind }[] = [
  { glob: "instrument.profile.u", kind: "gauss" },
  { glob: "instrument.profile.v", kind: "gauss" },
  { glob: "instrument.profile.w", kind: "gauss" },
  { glob: "instrument.profile.x", kind: "lor" },
  { glob: "instrument.profile.y", kind: "lor" },
  { glob: "instrument.zero_shift", kind: "zero" },
  { glob: "instrument.geometry.sample_displacement", kind: "disp" },
  { glob: "instrument.geometry.axial_sl", kind: "axial" },
  { glob: "instrument.geometry.axial_hl", kind: "axial" },
  { glob: "phases.*.scale", kind: "scale" },
  { glob: "phases.*.cell.a", kind: "cell" },
  { glob: "phases.*.cell.b", kind: "cell" },
  { glob: "phases.*.cell.c", kind: "cell" },
  { glob: "phases.*.lor_size", kind: "lor" },
  { glob: "phases.*.lor_strain", kind: "lor" },
  { glob: "phases.*.gauss_size", kind: "gauss" },
  { glob: "phases.*.gauss_strain", kind: "gauss" },
];

/** The displacement slider's half-range in mm, around the last fit. Settled by
 *  Claude, reversible (WP-2128 call 3): the shift a displacement causes needs
 *  the goniometer radius, which no payload this tab reads carries. */
export const DISPLACEMENT_SPAN_MM = 0.1;
/** The peak width the ranges are built from when the last fit has none to measure. */
export const FALLBACK_FWHM_DEG = 0.1;

export type Track = "lin" | "log";

export interface Slider {
  path: string;
  kind: Kind;
  /** the corpus title, or the path's leaf where no family is described */
  name: string;
  /** the corpus unit, shown in the range pop-up only (ruled 2026-11-07) */
  unit: string;
  /** "Instrument" or the phase's name: the group the slider is drawn under */
  group: string;
  /** the last fit's value, which the track's mark shows and ↺ returns to */
  ref: number;
  /** the row's own bounds; a typed value outside them is refused */
  bound: [number, number];
  lo: number;
  hi: number;
  track: Track;
  /** true once the person set the range or the scale in the pop-up */
  custom: boolean;
  /** the number's one format, fixed from the range (`fixFormat`) */
  exp: number | null;
  decimals: number;
}

/** What the default ranges are measured from: the widest window peak's FWHM
 *  and the highest Bragg angle, both read off the last fit's curves. */
export interface RangeContext {
  fwhm: number;
  thetaMaxDeg: number;
}

const RAD = Math.PI / 180;

/**
 * The range a slider opens on, from the last fit (WP-2128 § Context).
 *
 * A scale ×½ to ×2 on a logarithmic track; a zero shift ±2 FWHM; a cell length
 * the relative change that moves the highest-angle peak by 2 FWHM; a width term
 * from half to double the peak width, which is ×¼ to ×4 for a term in squared
 * degrees and ×½ to ×2 for one in degrees, on a logarithmic track; the axial
 * S/L and H/L from 0 to 3× their value, or 0.05. A width term at zero cannot be
 * scaled, so it opens on a linear track up to one peak width's worth.
 * Everything is clamped to the row's bounds, and a track that would reach zero
 * or below is linear.
 */
export function defaults(kind: Kind, x: number, bound: [number, number],
                         ctx: RangeContext): { lo: number; hi: number; track: Track } {
  const G = ctx.fwhm > 0 ? ctx.fwhm : FALLBACK_FWHM_DEG;
  let lo: number, hi: number, track: Track = "lin";
  switch (kind) {
    case "scale":
      [lo, hi, track] = x > 0 ? [x / 2, 2 * x, "log"] : [0, 1, "lin"];
      break;
    case "zero":
      [lo, hi] = [x - 2 * G, x + 2 * G];
      break;
    case "disp":
      [lo, hi] = [x - DISPLACEMENT_SPAN_MM, x + DISPLACEMENT_SPAN_MM];
      break;
    case "cell": {
      // Δ2θ = 2·tanθ·(Δd/d) in radians, so a 2 FWHM move at θmax is this share
      const t = Math.tan(Math.min(Math.max(ctx.thetaMaxDeg, 1), 89) * RAD);
      const e = (2 * G * RAD) / (2 * t);
      [lo, hi] = [x * (1 - e), x * (1 + e)];
      break;
    }
    case "axial":
      [lo, hi] = [0, Math.max(3 * x, 0.05)];
      break;
    case "gauss":
    case "lor": {
      const [f, span] = kind === "gauss" ? [4, G * G] : [2, G];
      if (x > 0) [lo, hi, track] = [x / f, x * f, "log"];
      else [lo, hi] = [x - span, x + span];
      break;
    }
  }
  lo = Math.max(lo, bound[0]);
  hi = Math.min(hi, bound[1]);
  if (!(hi > lo)) hi = lo + (Math.abs(lo) || 1);
  if (track === "log" && !(lo > 0)) track = "lin";
  return { lo, hi, track };
}

/**
 * The number's one format, fixed when the range is set, so a drag never
 * switches between plain and scientific and no digit moves (ruled 2026-11-07).
 *
 * Scientific where the range or the last fit sits under 0.01 or from 10 000 up,
 * with the exponent of the last fit and four decimals; plain otherwise, with as
 * many decimals as leave five significant figures at the range's largest value.
 */
export function fixFormat(lo: number, hi: number, ref: number): { exp: number | null; decimals: number } {
  const m = Math.max(Math.abs(lo), Math.abs(hi), Math.abs(ref));
  if (m !== 0 && (m < 0.01 || m >= 1e4)) {
    const r = Math.abs(ref) || m;
    return { exp: Math.floor(Math.log10(r)), decimals: 4 };
  }
  return { exp: null, decimals: Math.max(0, Math.min(6, 4 - Math.floor(Math.log10(m || 1)))) };
}

/** A value split into the three slots it is drawn in: the integer part with its
 *  sign, the decimal part with its point, and the power of ten or "". */
export function formatParts(s: Pick<Slider, "exp" | "decimals">, v: number):
  { int: string; frac: string; exp: string } {
  const m = s.exp == null ? v : v / 10 ** s.exp;
  const text = m.toFixed(s.decimals);
  const [int, frac = ""] = text.split(".");
  // −0.0000 would read as a negative value nobody set
  const signed = /^-0$/.test(int) && /^0*$/.test(frac) ? "0" : int;
  return { int: signed.replace("-", "−"), frac: frac ? `.${frac}` : "",
           exp: s.exp == null ? "" : String(s.exp).replace("-", "−") };
}

/** The value as a person would type it back: no slot, no typographic minus. */
export function editText(v: number): string {
  return Number.isFinite(v) ? String(Number(v.toPrecision(12))) : "";
}

/** Read a typed value, or say why it is refused (not a number, out of the row's bounds). */
export function parseTyped(s: Pick<Slider, "bound">, text: string): { value: number } | { why: string } {
  const t = text.trim().replaceAll("−", "-");
  const v = t === "" ? NaN : Number(t);
  if (!Number.isFinite(v)) return { why: "not a number" };
  if (v < s.bound[0]) return { why: `below the lower bound ${s.bound[0]}` };
  if (v > s.bound[1]) return { why: `above the upper bound ${s.bound[1]}` };
  return { value: v };
}

const phi = (track: Track, x: number) => (track === "log" ? Math.log(x) : x);

/** Where `x` sits on the track, 0 at `lo` and 1 at `hi`, clamped. */
export function posFrac(s: Pick<Slider, "lo" | "hi" | "track">, x: number): number {
  if (s.track === "log" && !(x > 0)) return 0;
  const a = phi(s.track, s.lo), b = phi(s.track, s.hi);
  if (b === a) return 0.5;
  return Math.min(1, Math.max(0, (phi(s.track, x) - a) / (b - a)));
}

/** The value at track position `f` in [0, 1]. */
export function valueAt(s: Pick<Slider, "lo" | "hi" | "track">, f: number): number {
  if (f <= 0) return s.lo;
  if (f >= 1) return s.hi;
  if (s.track === "log") return Math.exp(Math.log(s.lo) + f * (Math.log(s.hi) - Math.log(s.lo)));
  return s.lo + f * (s.hi - s.lo);
}

/** The track's resolution: an `<input type=range>` from 0 to this, in steps of 1. */
export const STEPS = 1000;

/**
 * The sliders for a parameter table: every refinable row of a family in
 * `FAMILIES`, which leaves out a tied, locked or force-fixed one (b under a
 * hexagonal cell follows a and gets none). Each opens on its default range at
 * the row's value; `prior` keeps a range the person set, so a head move
 * rebases only the ranges nobody chose.
 */
export function buildSliders(rows: readonly ParamRow[], corpus: HelpCorpus | null,
                             ctx: RangeContext, phaseNames: readonly string[] = [],
                             prior: ReadonlyMap<string, Slider> = new Map()): Slider[] {
  const out: Slider[] = [];
  for (const family of FAMILIES) {
    for (const row of rows) {
      if (!row.refinable || !fnmatch(row.path, family.glob)) continue;
      const entry = resolve(corpus, paramKey(row.help_key) ?? "");
      const phase = /^phases\.(\d+)\./.exec(row.path);
      const group = phase ? phaseNames[+phase[1]] ?? `Phase ${+phase[1] + 1}` : "Instrument";
      const bound: [number, number] = [row.lo, row.hi];
      const old = prior.get(row.path);
      const range = old?.custom ? { lo: old.lo, hi: old.hi, track: old.track }
        : defaults(family.kind, row.value, bound, ctx);
      out.push({
        path: row.path, kind: family.kind, group, bound, ref: row.value,
        // the corpus has one entry for a, b and c, so two cell sliders in one
        // phase would carry one name; a cell length is named by its own edge
        name: family.kind === "cell" ? `Lattice parameter ${row.path.split(".").at(-1)}`
          : entry?.title ?? row.path.split(".").slice(-2).join(" "),
        unit: entry?.unit ?? "", custom: !!old?.custom, ...range,
        ...fixFormat(range.lo, range.hi, row.value),
      });
    }
  }
  // instrument first, then each phase in its own order, keeping family order inside
  const rank = (s: Slider) => (s.group === "Instrument" ? -1 : +(/^phases\.(\d+)/.exec(s.path)?.[1] ?? 0));
  return out.map((s, i) => [s, i] as const)
    .sort((a, b) => rank(a[0]) - rank(b[0]) || a[1] - b[1]).map(([s]) => s);
}

/** The widest decimal part any slider shows, so every decimal point aligns. */
export function maxDecimals(sliders: readonly Slider[]): number {
  return Math.max(0, ...sliders.map((s) => s.decimals));
}

/**
 * One preview request in flight, the newest values sent when it lands, and an
 * answer dropped once the edits it answered are gone (WP-2128).
 *
 * A drag throttles itself to the route's own latency this way: a fast drag
 * never queues, because every value but the newest is overwritten while a
 * request is out (WP-2125's handover asked for exactly this). `clear()` is a
 * revert or an apply: an answer still in flight then answers values that no
 * longer exist, so it is dropped rather than drawn.
 */
export class PreviewQueue<T> {
  private inFlight = false;
  private next: { values: Record<string, number>; at: number } | null = null;
  private generation = 0;

  constructor(
    private readonly send: (values: Record<string, number>) => Promise<T>,
    private readonly land: (answer: T, values: Record<string, number>, sentAt: number) => void,
    private readonly fail: (error: unknown) => void,
    private readonly now: () => number = () => performance.now(),
  ) {}

  /** Ask for these values; while a request is out they replace any waiting. */
  push(values: Record<string, number>): void {
    this.next = { values, at: this.now() };
    if (!this.inFlight) void this.pump();
  }

  /** Forget everything waiting, and drop the answer in flight. */
  clear(): void {
    this.generation++;
    this.next = null;
  }

  get busy(): boolean {
    return this.inFlight;
  }

  private async pump(): Promise<void> {
    while (this.next) {
      const { values, at } = this.next;
      this.next = null;
      const generation = this.generation;
      this.inFlight = true;
      try {
        const answer = await this.send(values);
        if (generation === this.generation) this.land(answer, values, at);
      } catch (error) {
        if (generation === this.generation) this.fail(error);
      } finally {
        this.inFlight = false;
      }
    }
  }
}

/**
 * Where each of `sub`'s values lands in `grid`, both ascending: the index in
 * `grid` holding the same 2θ, or −1 where `grid` has no such channel.
 *
 * The preview answers every channel the next fit would fit, and the curves
 * payload carries the last fit's, decimated past `CURVES_CEILING`. Both are the
 * pattern's own doubles, so a channel is found by equality and the preview is
 * drawn on exactly the channels the payload kept (WP-2128).
 */
export function channelIndex(grid: ArrayLike<number>, sub: ArrayLike<number>): Int32Array {
  const out = new Int32Array(sub.length).fill(-1);
  let j = 0;
  for (let i = 0; i < sub.length; i++) {
    const x = sub[i];
    while (j < grid.length && grid[j] < x) j++;
    if (j < grid.length && grid[j] === x) out[i] = j;
  }
  return out;
}

/** What the graphs draw: the route's answer, and when its values were set. */
export interface PreviewAnswer {
  curves: Curves;
  /** `performance.now()` when the newest of these values was set */
  sentAt: number;
}
