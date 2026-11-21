import { fnmatch } from "../lib/fnmatch";

/** The rebuilt Background graph's controls (WP-2218), as pure functions.
 *
 * `lib/background.ts` holds the drawing and the band's words, which today's
 * tab shares. What is here is what only the rebuilt graph offers: the Type
 * choice, the Terms and Stiffness sliders, and the pending holds the band is
 * fetched with. Each is restated from the prototype in WP-2218 § Context.
 */

/** The Terms slider's span, the prototype's (2 to 16). */
export const TERMS_MIN = 2;
export const TERMS_MAX = 16;

/** A Chebyshev a type switch starts from: the comparison standards' count. */
export const DEFAULT_TERMS = 6;

/** The Stiffness slider's stops, the prototype's: λ in the P-spline's
 *  dimensionless units, 1 the package's default (`PSPLINE_LAMBDA_SMOOTH`). */
export const LAMBDA_STOPS = [1e-2, 1, 1e2, 1e4, 1e6] as const;

/** The knot spacing `BackgroundPSpline.for_range` uses, in degrees 2θ.
 *  `tests/data/gui/background_cases.json` holds it, the stiffness and the
 *  knots equal to Python's (`tests/test_gui_background.py` writes it). */
export const KNOT_STEP_DEG = 5;

/** `PSPLINE_LAMBDA_SMOOTH`, the stiffness a fresh P-spline starts at. */
export const DEFAULT_LAMBDA = 1;

/** The stop nearest λ on a log scale, so a value typed elsewhere still sits
 *  somewhere on the track. */
export function lambdaStop(lambda: number): number {
  if (!(lambda > 0)) return 0;
  let best = 0;
  for (let k = 1; k < LAMBDA_STOPS.length; k++) {
    if (Math.abs(Math.log10(LAMBDA_STOPS[k]) - Math.log10(lambda))
        < Math.abs(Math.log10(LAMBDA_STOPS[best]) - Math.log10(lambda))) best = k;
  }
  return best;
}

/** Every path or glob held and not yet applied, sorted: what the band is
 *  fetched with (`GET /api/background?hold=`). Not only the background's: a
 *  held scale moves the band through the covariance too, and a glob is
 *  resolved by the server as the hold verb resolves it. A pending release is
 *  left out, since a released term comes back fixed and its band is the held
 *  one. */
export function pendingHolds(holds: ReadonlyMap<string, boolean>): string[] {
  return [...holds].filter(([, held]) => held).map(([path]) => path).sort();
}

/** Is `path` held, counting a pending hold or release on it or on a glob
 *  matching it? The path's own entry wins, then the last glob set. */
export function heldWith(path: string, serverHeld: boolean,
                         holds: ReadonlyMap<string, boolean>): boolean {
  const own = holds.get(path);
  if (own !== undefined) return own;
  let held = serverHeld;
  for (const [glob, want] of holds) if (fnmatch(path, glob)) held = want;
  return held;
}

/** What a structural edit also asks of the hold and free registers, which
 *  `Refinement` keeps by path and reapplies to whatever the new model calls
 *  `c3` (`GuiSession.instrument_patch`): the holds to release first, the
 *  paths to free after, and which paths the edit removes or redefines, whose
 *  pending edits go too. */
export interface Arms {
  unhold: string[];
  free: string[];
  gone: (path: string) => boolean;
}

const BACKGROUND = "instrument.background.*";

/** A Type switch redefines every coefficient: release them all, free the new
 *  ones, so the fresh background starts at zero and free as its docstring
 *  says, and nothing pending on the old one survives. */
export function kindArms(): Arms {
  return { unhold: [BACKGROUND], free: [BACKGROUND], gone: (path) => fnmatch(path, BACKGROUND) };
}

/** A Terms change from `held` terms (each path and whether it is held now)
 *  to `n`: a cut releases the held terms it removes, or a later extension
 *  would bring them back held; an extension frees the terms it adds, which
 *  the free register does not name. */
export function termsArms(terms: readonly { path: string; held: boolean }[], n: number): Arms {
  const index = (path: string) => {
    const m = /^instrument\.background\.c(\d+)$/.exec(path);
    return m ? Number(m[1]) : -1;
  };
  return {
    unhold: terms.filter((t) => t.held && index(t.path) >= n).map((t) => t.path),
    free: Array.from({ length: Math.max(0, n - terms.length) },
                     (_, k) => `instrument.background.c${terms.length + k}`),
    gone: (path) => index(path) >= n,
  };
}

/** A copy of `instrument` with its Chebyshev cut or extended to `n` terms,
 *  keeping the fitted values and flags of the terms it keeps. An added term
 *  is built at zero and free, as `BackgroundChebyshev.with_terms` builds one;
 *  `termsArms`' `free` makes it free in the table too. */
export function withTerms(instrument: any, n: number): any {
  const next = JSON.parse(JSON.stringify(instrument));
  const current = next.background.coefficients as any[];
  next.background.coefficients = n <= current.length
    ? current.slice(0, n)
    : [...current, ...Array.from({ length: n - current.length }, () => ({ value: 0, vary: true }))];
  return next;
}

/** Python's `round`: a half goes to the even neighbour, where `Math.round`
 *  takes it up, so a span of 12.5° would get one knot more than Python's. */
function roundHalfEven(x: number): number {
  const r = Math.round(x);
  return r - x === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

/** Uniform knots over [lo, hi], as `BackgroundPSpline.for_range` places them. */
export function knots(lo: number, hi: number, step = KNOT_STEP_DEG): number[] {
  const n = Math.max(roundHalfEven((hi - lo) / step) + 1, 2);
  return Array.from({ length: n }, (_, i) => lo + ((hi - lo) * i) / (n - 1));
}

/** A copy of `instrument` with a background of the other type: a P-spline
 *  as `BackgroundPSpline.for_range` builds one over the fitted channels' ends,
 *  or a Chebyshev of `DEFAULT_TERMS`. Its coefficients start at zero, and
 *  `kindArms`' `free` frees them, so the next refine fits them. */
export function switchKind(instrument: any, kind: "chebyshev" | "pspline", lo: number, hi: number): any {
  const next = JSON.parse(JSON.stringify(instrument));
  if (kind === "pspline") {
    const breakpoints = knots(lo, hi);
    next.background = {
      kind: "pspline", breakpoints, lambda_smooth: DEFAULT_LAMBDA, lambda_units: "dimensionless",
      coefficients: Array.from({ length: breakpoints.length + 2 }, () => ({ value: 0, vary: true })),
    };
  } else {
    next.background = {
      kind: "chebyshev",
      coefficients: Array.from({ length: DEFAULT_TERMS }, () => ({ value: 0, vary: true })),
    };
  }
  return next;
}

/** The Python a Terms change runs, for the console: the coefficients kept
 *  with their values, or extended by zero terms. */
export function termsEcho(from: number, n: number): string {
  return n < from
    ? `instrument.background.coefficients = instrument.background.coefficients[:${n}]`
    : `instrument.background.coefficients += [Parameter(value=0.0, vary=True) for _ in range(${n - from})]`;
}

/** The Python a Type switch runs, for the console, at the bounds sent. */
export function kindEcho(kind: "chebyshev" | "pspline", lo: number, hi: number): string {
  return kind === "pspline"
    ? `instrument.background = BackgroundPSpline.for_range(${pyFloat(lo)}, ${pyFloat(hi)})`
    : `instrument.background = BackgroundChebyshev.with_terms(${DEFAULT_TERMS})`;
}

/** A float as Python's `repr` spells it: the shortest round-trip digits,
 *  which `String` gives too, with ".0" on an integer value. */
function pyFloat(x: number): string {
  const t = String(x);
  return /[.eE]/.test(t) ? t : `${t}.0`;
}
