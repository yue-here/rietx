/**
 * What the report panel shows, and the four ways a renderer could lie about a
 * report whose numbers are correct: hide an abstention, sort a vetoed suggestion
 * out of sight, colour a deliberately-capped confidence like a high one, or print
 * a whole-report estimate in a per-row column.
 */
import { describe, expect, it } from "vitest";

import {
  actionRows,
  confidenceTone,
  headline,
  predictionNote,
  underNote,
  worstRegions,
  zoomWindow,
  type ApplyArm,
  type FitDiagnostic,
  type Suggestion,
} from "./report";

function suggestion(kind: string, over: Partial<Suggestion> = {}): Suggestion {
  return {
    kind, confidence: 0.5, rationale: "because", parameter_paths: [`${kind}.path`],
    expected_delta_chi2: 16.19, alternatives: [], two_theta_range: null,
    vetoed_by: null, ...over,
  };
}

function arm(kind: string, over: Partial<ApplyArm> = {}): ApplyArm {
  return {
    kind, how: "stage", note: "", can_apply: true, refusal: "",
    paths: [`${kind}.path`], stage: { name: `apply:${kind}` },
    api_call: `ref.run_stage(data, rx.Stage('apply:${kind}', []))`, ...over,
  };
}

describe("the suggestion strip", () => {
  it("pairs an action with its arm by position, not by kind", () => {
    // two textured phases: same kind, different phases, different applicability
    const actions = [
      suggestion("refine_preferred_orientation", {
        parameter_paths: ["phases.0.preferred_orientation.r"], confidence: 0.8 }),
      suggestion("refine_preferred_orientation", {
        parameter_paths: ["phases.1.preferred_orientation.r"], confidence: 0.7 }),
    ];
    const arms = [
      arm("refine_preferred_orientation", { can_apply: false,
        refusal: "phases.0.preferred_orientation.r: not declared on the phase yet",
        stage: null, api_call: null }),
      arm("refine_preferred_orientation", { paths: ["phases.1.preferred_orientation.r"] }),
    ];
    const rows = actionRows(actions, arms);
    // the applicable one leads, and it is phase 1's — keying by kind would have
    // attached phase 1's button to phase 0's action
    expect(rows[0].action.parameter_paths).toEqual(["phases.1.preferred_orientation.r"]);
    expect(rows[0].arm?.can_apply).toBe(true);
    expect(rows[1].arm?.can_apply).toBe(false);
  });

  it("shows a vetoed action after the applicable ones and never drops it", () => {
    const rows = actionRows(
      [suggestion("refine_scale", { confidence: 0.9, vetoed_by: "already refined by the staged plan" }),
       suggestion("collect_better_data", { confidence: 0.6 }),
       suggestion("refine_cell", { confidence: 0.3 })],
      [arm("refine_scale", { can_apply: false, refusal: "vetoed: …", stage: null }),
       arm("collect_better_data", { how: "advice", note: "count longer", can_apply: false,
         refusal: "not a one-click action — count longer", stage: null }),
       arm("refine_cell")],
    );
    // applicable (0.3) first even at the lowest confidence, then the veto, then advice
    expect(rows.map((r) => r.action.kind)).toEqual([
      "refine_cell", "refine_scale", "collect_better_data"]);
    expect(rows).toHaveLength(3);
  });

  it("bands confidence at the values Layer 2 caps at", () => {
    // 0.3 is the cap on a non-separable attribution, 0.4 on an unresolved
    // texture axis: both are the report declining to call it, so neither is
    // allowed to look like a confident suggestion
    expect(confidenceTone(0.3)).toBe("low");
    expect(confidenceTone(0.4)).toBe("medium");
    expect(confidenceTone(0.6)).toBe("high");
    expect(confidenceTone(1.0)).toBe("high");
    expect(confidenceTone(0)).toBe("low");
  });
});

describe("the headline", () => {
  const REPORT = {
    rwp: 0.216, gof: 1.4,
    unmatched: [{ two_theta: 9.1, height_over_sigma: 12, kind: "unmatched_obs" }],
    attribution: [
      { gates_passed: true, gate_failures: [], chi2_share: 0.4 },
      { gates_passed: false, chi2_share: 0.2, gate_failures: [
        { code: "local_r2", message: "local_r2=0.31<0.5" }] },
      { gates_passed: false, chi2_share: 0.1, gate_failures: [
        { code: "local_r2", message: "local_r2=0.44<0.5" },
        { code: "gram_condition", message: "gram_condition=2.4e+04>1e+04" }] },
    ],
    suggested_actions: [suggestion("refine_cell")],
  };

  it("counts the gates that refused, by code, with their values dropped", () => {
    const head = headline(REPORT);
    expect(head.gated).toBe("1/3");
    expect(head.refusedBy).toEqual(["local_r2 ×2", "gram_condition ×1"]);
    expect(head.abstained).toBeNull();
  });

  it("counts the two unmatched kinds apart", () => {
    // measured on a real report: a fit whose cell was 0.0005 Å off had 15
    // `unmatched_calc` and 0 `unmatched_obs`, so one combined badge said
    // "15 unindexed" beside a summary saying "0 unmatched observed peak(s)".
    // A mispositioned model produces the second kind at *every* peak; only the
    // first means "something is here that the model has no reflection for".
    const head = headline({ ...REPORT, unmatched: [
      { two_theta: 9.1, height_over_sigma: 12, kind: "unmatched_obs" },
      { two_theta: 12.0, height_over_sigma: 30, kind: "unmatched_calc" },
      { two_theta: 14.0, height_over_sigma: 22, kind: "unmatched_calc" },
    ] });
    expect(head.unindexed).toBe(1);
    expect(head.unobserved).toBe(2);
  });

  it("keeps an abstention as an abstention", () => {
    const head = headline({ ...REPORT, layer1_available: false, attribution: [],
      abstained_reason: "fit is immature (Rwp=0.407 > 0.35)" });
    expect(head.abstained).toContain("immature");
    expect(head.gated).toBe("0/0");
  });

  it("names the predicted Δχ² as the whole report's, not the row's", () => {
    const note = predictionNote(headline(REPORT));
    expect(note).toContain("16.19");
    expect(note).toContain("not per suggestion");
    expect(note).toContain("not a");
    // …and no prediction at all is silence rather than a zero
    expect(predictionNote(headline({ ...REPORT, suggested_actions: [] }))).toBe("");
  });

});

describe("the worst-region list", () => {
  const regions = [
    { two_theta_lo: 5, two_theta_hi: 6, local_rwp: 0.9, chi2_share: 0.01,
      max_abs_delta_over_sigma: 3, n_reflections: 0 },
    { two_theta_lo: 9, two_theta_hi: 10, local_rwp: 0.2, chi2_share: 0.4,
      max_abs_delta_over_sigma: 40, n_reflections: 2 },
  ];

  it("ranks by χ² share, not by local Rwp", () => {
    // the 5-6° region has the worse local Rwp over noise and no reflections at
    // all; sending the user there would be sending them nowhere
    expect(worstRegions(regions).map((r) => r.two_theta_lo)).toEqual([9, 5]);
    expect(worstRegions(regions, 1)).toHaveLength(1);
    expect(worstRegions([])).toEqual([]);
  });

  it("pads a zoom so a one-peak region comes with a baseline", () => {
    expect(zoomWindow(9, 10)).toEqual([8.65, 10.35]);
    const [lo, hi] = zoomWindow(9.5, 9.5);
    expect(hi).toBeGreaterThan(lo);
  });
});

describe("a folded diagnostic's note", () => {
  const diag = (level: string, warning_under?: string[]): FitDiagnostic =>
    ({ level, code: "FLOOR_HIT", message: "m", warning_under });

  it("joins the server's purposes in the order they came", () => {
    expect(underNote(diag("warning", ["qpa", "structure"])))
      .toBe("warning under qpa, structure");
  });

  it("names series alone where the server's list is empty", () => {
    // `warning_under` leaves `series` out, and a warning naming a path is
    // always one under it, so an empty list is a warning only a series reads
    expect(underNote(diag("warning", []))).toBe("warning under series only");
  });

  it("says nothing on an error or an info, whose chip says it all", () => {
    expect(underNote(diag("error", []))).toBeNull();
    expect(underNote(diag("info"))).toBeNull();
  });
});
