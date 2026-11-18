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

/** The knot spacing `BackgroundPSpline.for_range` uses, in degrees 2θ. */
export const KNOT_STEP_DEG = 5;

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

/** The background paths held and not yet applied, sorted: what the band is
 *  fetched with (`GET /api/background?hold=`). A pending release is left out,
 *  since a released term comes back fixed and its band is the held one. */
export function pendingBackgroundHolds(holds: ReadonlyMap<string, boolean>): string[] {
  return [...holds].filter(([path, held]) => held && /^instrument\.background\.[^*?[]+$/.test(path))
    .map(([path]) => path).sort();
}

/** A copy of `instrument` with its Chebyshev cut or extended to `n` terms. An
 *  added term starts at zero and free, as `BackgroundChebyshev.with_terms`. */
export function withTerms(instrument: any, n: number): any {
  const next = JSON.parse(JSON.stringify(instrument));
  const current = next.background.coefficients as any[];
  next.background.coefficients = n <= current.length
    ? current.slice(0, n)
    : [...current, ...Array.from({ length: n - current.length }, () => ({ value: 0, vary: true }))];
  return next;
}

/** Uniform knots over [lo, hi], as `BackgroundPSpline.for_range` places them. */
export function knots(lo: number, hi: number, step = KNOT_STEP_DEG): number[] {
  const n = Math.max(Math.round((hi - lo) / step) + 1, 2);
  return Array.from({ length: n }, (_, i) => lo + ((hi - lo) * i) / (n - 1));
}

/** A copy of `instrument` with a background of the other type, built as the
 *  package builds a fresh one: a P-spline over the measured range at the
 *  default stiffness, or a Chebyshev of `DEFAULT_TERMS`. Its coefficients start
 *  at zero and free, so the next refine fits them. */
export function switchKind(instrument: any, kind: "chebyshev" | "pspline", lo: number, hi: number): any {
  const next = JSON.parse(JSON.stringify(instrument));
  if (kind === "pspline") {
    const breakpoints = knots(lo, hi);
    next.background = {
      kind: "pspline", breakpoints, lambda_smooth: 1, lambda_units: "dimensionless",
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
