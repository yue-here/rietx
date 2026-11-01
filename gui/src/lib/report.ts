/** The FitReport panel's logic — what to show, in what order, and how honestly.
 *
 * The report's own rule is that it must never return a confident wrong singleton
 * (CLAUDE.md), and a renderer can break that without touching the numbers: by
 * hiding an abstention, by sorting suggestions so a vetoed one looks absent, or by
 * printing a per-report estimate in a per-row column.  So the decisions that could
 * do that live here as functions, with `report.test.ts` asserting them.
 *
 * Every numeric field goes through `num()` from `table.ts`: a gate's Gram
 * condition and a separability ratio are legitimately ±∞, and this package spells
 * a non-finite float as a **string** on the wire because `JSON.parse` rejects
 * Python's bare `Infinity` (WP-1011).  `Number("1e4") > 1e3` is true;
 * `"1e4" > 1e3` is a string comparison that happens to work and then does not.
 */

import { num } from "./table";

export interface Region {
  two_theta_lo: number;
  two_theta_hi: number;
  local_rwp: number;
  chi2_share: number;
  max_abs_delta_over_sigma: number;
  n_reflections: number;
}

export interface Attribution {
  two_theta_lo: number;
  two_theta_hi: number;
  n_reflections: number;
  chi2_share: number;
  mean_two_theta: number;
  mean_fwhm: number;
  coefficients: Array<{ kind: string; value: number; stderr: number;
                        significant: boolean; share: number }>;
  r2: number;
  gram_condition: number;
  chi2_reduced: number;
  gates_passed: boolean;
  gate_failures: GateFailure[];
}

/** One refused gate: `code` to group on, `message` for the numbers (WP-1003).
 *
 * Until the freeze the entries were formatted strings alone and this client
 * recovered the gate's name by parsing the prefix back out (`gateName`) — the
 * gap WP-1007 closed for `Diagnostic.where`, one layer up.  The code field
 * retired that parse.
 */
export interface GateFailure {
  code: string;
  message: string;
}

export interface Suggestion {
  kind: string;
  confidence: number;
  rationale: string;
  parameter_paths: string[];
  expected_delta_chi2: number | null;
  alternatives: string[];
  two_theta_range: [number, number] | null;
  vetoed_by: string | null;
}

/** One entry of `GET /api/report`'s `apply` arm — the server's own judgement. */
export interface ApplyArm {
  kind: string;
  how: "stage" | "index" | "advice";
  note: string;
  can_apply: boolean;
  refusal: string;
  paths: string[];
  stage: Record<string, unknown> | null;
  api_call: string | null;
}

export interface Row {
  action: Suggestion;
  arm: ApplyArm | null;
  /** confidence band, for the colour — three bands, not a gradient */
  tone: "high" | "medium" | "low";
}

/**
 * Suggestions in the order a panel should list them, paired with their arm.
 *
 * The pairing is **positional**, because that is how the server sends it: a kind
 * is not a unique key (two textured phases emit two
 * `refine_preferred_orientation` actions), so keying by kind here would attach one
 * phase's applicability to the other phase's button.
 *
 * Order: what you can act on, then what the engine vetoed, then what is only
 * advice — and within each group by confidence.  A vetoed action is never dropped:
 * the veto *is* the reasoning, and hiding it would leave the panel implying the
 * report saw nothing (Layer 2's rule, one level up).
 */
export function actionRows(actions: readonly Suggestion[],
                           arms: readonly ApplyArm[]): Row[] {
  const rank = (row: Row) =>
    row.arm?.can_apply ? 0 : row.action.vetoed_by ? 1 : 2;
  return actions
    .map((action, i) => ({
      action,
      arm: arms[i] ?? null,
      tone: confidenceTone(num(action.confidence)),
    }))
    .sort((a, b) => rank(a) - rank(b) || num(b.action.confidence) - num(a.action.confidence));
}

/** Three bands rather than a continuous colour ramp.
 *
 * The thresholds are the report's own vocabulary, not taste: Layer 2 caps a
 * non-separable attribution's confidence at 0.3 and a texture action with an
 * unresolved axis at 0.4, so everything below 0.4 is something the report is
 * explicitly declining to call, and drawing it in the same green as a 0.9 would
 * erase that. */
export function confidenceTone(confidence: number): "high" | "medium" | "low" {
  if (!(confidence > 0)) return "low";
  if (confidence >= 0.6) return "high";
  return confidence >= 0.4 ? "medium" : "low";
}

/**
 * The worst regions, biggest χ² share first, for the click-zoom list.
 *
 * Ranked by share of χ² rather than by local Rwp: a region can have a dreadful
 * local Rwp over four counts of noise, and the panel's job is to send the user
 * where the misfit actually is.  Both are shown; only one decides the order.
 */
export function worstRegions(regions: readonly Region[], limit = 8): Region[] {
  return [...(regions ?? [])]
    .sort((a, b) => num(b.chi2_share) - num(a.chi2_share))
    .slice(0, limit);
}

/** A 2θ window padded by a fraction of its own width, for the zoom.
 *
 * A region is often one peak wide; zooming to exactly its edges shows a peak with
 * no context and no baseline, so it is widened. */
export function zoomWindow(lo: number, hi: number, pad = 0.35): [number, number] {
  const a = num(lo);
  const b = num(hi);
  const width = Math.max(b - a, 1e-6);
  return [a - pad * width, b + pad * width];
}

export interface Headline {
  rwp: number;
  gof: number;
  /** how many attribution regions passed all four gates, of how many */
  gated: string;
  /** the gates that refused, worst first, as `name ×n` */
  refusedBy: string[];
  /** observed peaks with no calculated tick — an impurity, or a wrong cell */
  unindexed: number;
  /** calculated peaks with no observed intensity — the opposite diagnosis, and
   *  the one a mispositioned model produces at *every* peak */
  unobserved: number;
  /** null when Layer 1 spoke; the reason when it abstained */
  abstained: string | null;
  /** the *report-level* predicted Δχ², or null — see `predictionNote` */
  predicted: number | null;
}

/**
 * The one-line state of the report, including what it refused to say.
 *
 * `refusedBy` is aggregated from `gate_failures` rather than from a count, because
 * "eleven regions failed the validity radius" and "eleven regions failed
 * significance" mean opposite things: the first says the model is far enough off
 * that linearising is wrong, the second says there is nothing there to attribute.
 *
 * The two `unmatched` kinds are counted **separately** for the same reason, and
 * this one was found by looking at a real report rather than a fixture: a single
 * "15 unindexed" badge sat beside a summary reading "0 unmatched observed peak(s)"
 * on a fit whose cell was 0.0005 Å off.  All fifteen were `unmatched_calc` —
 * calculated peaks with no observed intensity, which is what a *mispositioned*
 * model produces at every peak — and calling them unindexed would point a user at
 * an impurity that is not there.
 */
export function headline(report: any): Headline {
  const attribution: Attribution[] = report?.attribution ?? [];
  const counts = new Map<string, number>();
  for (const region of attribution) {
    for (const failure of region.gate_failures ?? []) {
      counts.set(failure.code, (counts.get(failure.code) ?? 0) + 1);
    }
  }
  const predicted = (report?.suggested_actions ?? [])
    .map((a: Suggestion) => a.expected_delta_chi2)
    .find((v: number | null) => v !== null && v !== undefined);
  const unmatched: Array<{ kind: string }> = report?.unmatched ?? [];
  return {
    rwp: num(report?.rwp),
    gof: num(report?.gof),
    gated: `${attribution.filter((a) => a.gates_passed).length}/${attribution.length}`,
    refusedBy: [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([name, n]) => `${name} ×${n}`),
    unindexed: unmatched.filter((u) => u.kind === "unmatched_obs").length,
    unobserved: unmatched.filter((u) => u.kind === "unmatched_calc").length,
    abstained: report?.abstained_reason ?? null,
    predicted: predicted === undefined ? null : num(predicted),
  };
}

/**
 * How to label the predicted Δχ² — which is *not* per suggestion.
 *
 * `build_report` computes one estimate and stamps it on every Layer-1-derived
 * action, and it bounds only the misfit attributed inside the gated regions
 * (measured in `tests/test_report_apply.py`: 16.19 predicted against 16.33
 * observed).  So it is shown once, at the top, saying what it is — printing it in
 * a per-row column would invent a per-action prediction the report does not make.
 */
export function predictionNote(headlineValue: Headline): string {
  if (headlineValue.predicted === null) return "";
  return (`the gated regions hold Δχ² ≈ ${headlineValue.predicted.toPrecision(4)} ` +
          `— one estimate for the whole report, not per suggestion, and not a ` +
          `bound on what any one of them achieves`);
}

/** One entry of `RefinementResult.diagnostics`, as `/api/result` sends it. */
export interface FitDiagnostic {
  level: string;
  code: string;
  message: string;
  where?: string[];
  suggestion?: string | null;
  /** printed in full rather than as one line: the server's view (WP-2037) */
  full?: boolean;
  /** the purposes it is a warning under, `series` never among them */
  warning_under?: string[];
}

/**
 * The purposes a warning is a warning under, as a collapsed row says them;
 * `null` for any other level, whose chip already says all there is.  The list
 * is the server's (`diagnostic_view`) and this only joins it.  An empty one is
 * a warning only a series reads: the list leaves `series` out, and a warning
 * naming a path is always one under it.
 */
export function underNote(d: FitDiagnostic): string | null {
  if (d.level !== "warning") return null;
  const under = d.warning_under ?? [];
  return under.length ? `warning under ${under.join(", ")}` : "warning under series only";
}

const LEVEL_RANK: Record<string, number> = { error: 0, warning: 1, info: 2 };

/**
 * The result's own diagnostics, error first, none dropped.
 *
 * The package emits these (`BOUND_HIT`, `RESOLUTION_UNCONSTRAINED`,
 * `LEBAIL_ALTERNATION_STOPPED`, …) and a history node carries only the ones
 * committed with it, so this list is the one place a client sees what the
 * *answer* says.  The sort is stable: within a level the package's own order
 * stands, and a level this build does not know sorts last rather than away.
 */
export function orderDiagnostics(list: readonly FitDiagnostic[] | null | undefined): FitDiagnostic[] {
  const rank = (d: FitDiagnostic) => LEVEL_RANK[d.level] ?? 3;
  return [...(list ?? [])]
    .map((d, i) => ({ d, i }))
    .sort((a, b) => rank(a.d) - rank(b.d) || a.i - b.i)
    .map(({ d }) => d);
}

/** A diagnostic's chip tone: the app's vocabulary, `note` for an unknown level. */
export function diagnosticTone(level: string): "bad" | "warn" | "note" {
  return level === "error" ? "bad" : level === "warning" ? "warn" : "note";
}
