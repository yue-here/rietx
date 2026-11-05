/**
 * WP-1027 — the peak-picker logic that must hold without a DOM.
 *
 * The two colour splits (unusable flags, refuting caveats) are asserted to be
 * *data-driven*: the functions take the server's list and never carry one of
 * their own, which is what keeps the chips honest when a vocabulary grows.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  INTENSITY_UNMEASURED_FLAGS,
  POSITION_ESD_MAX_DEG,
  absentText,
  caveatTone,
  confidenceTone,
  cellText,
  collectTo,
  flagTone,
  fomColumns,
  fomOf,
  formatHkl,
  formatIntensity,
  formatPosition,
  grabToleranceDeg,
  intensityScale,
  joinCurves,
  nearestPeak,
  type Candidate,
  type GroupCurve,
} from "./peaks";

/** The corpus keys python wrote (`tests/test_gui_help.py`): the one place a
 *  TypeScript file may learn a flag's name from. */
const HELP_KEYS: string[] = JSON.parse(readFileSync(
  fileURLToPath(new URL("../../../tests/data/gui/help_keys.json", import.meta.url)),
  "utf-8")).keys;

describe("the table's numbers (WP-1209)", () => {
  // the certified corundum pattern, as the picker leaves it: two components
  // on their zero bound (2.1e-49 and 5.5e-19 — the bound, not an area), one
  // with the degenerate σ the equilibrated covariance now reports (111°),
  // one whose position esd underflows the fourth place (1e-13)
  const corundum = [
    { intensity: 1210.4, two_theta: 25.5784, two_theta_esd: 0.00021, flags: [] as string[] },
    { intensity: 2.1e-49, two_theta: 35.0912, two_theta_esd: 111, flags: ["no_intensity"] },
    { intensity: 5.5e-19, two_theta: 43.3551, two_theta_esd: 1e17, flags: ["no_intensity"] },
    { intensity: 605.2, two_theta: 37.7761, two_theta_esd: 1e-13, flags: [] as string[] },
    { intensity: 9.9e3, two_theta: 57.5, two_theta_esd: 0.02, flags: ["fit_failed"] },
  ];

  it("names its unmeasured flags from the corpus vocabulary, never a spelling of its own", () => {
    for (const flag of INTENSITY_UNMEASURED_FLAGS) {
      expect(HELP_KEYS).toContain(`peak_flags:${flag}`);
    }
  });

  it("scales intensities to the strongest *measured* line", () => {
    // 9.9e3 is a failed fit's seed and 2.1e-49 is a bound; neither is Imax
    expect(intensityScale(corundum)).toBe(1210.4);
    expect(intensityScale([])).toBe(0);
    expect(intensityScale([corundum[1], corundum[4]])).toBe(0);
  });

  it("shows I/Imax × 100 at one decimal, and — where the number is not a measurement", () => {
    const imax = intensityScale(corundum);
    expect(formatIntensity(1210.4, imax, [])).toBe("100.0");
    expect(formatIntensity(605.2, imax, [])).toBe("50.0");
    expect(formatIntensity(2.1e-49, imax, ["no_intensity"])).toBe("—");
    expect(formatIntensity(9.9e3, imax, ["fit_failed"])).toBe("—");
    // an unflagged but tiny area is a number, and it says 0.0 rather than 1e-17
    expect(formatIntensity(2.1e-19, imax, [])).toBe("0.0");
    // no scale at all: every row says so rather than dividing by zero
    expect(formatIntensity(1210.4, 0, [])).toBe("—");
    expect(formatIntensity(NaN, imax, [])).toBe("—");
  });

  it("prints 2θ at four places with the esd in the last place, or the value alone", () => {
    expect(formatPosition(25.5784, 0.00021)).toEqual({ value: "25.5784", esd: "(2)" });
    expect(formatPosition(25.57843, 0.012)).toEqual({ value: "25.5784", esd: "(120)" });
    // the degenerate σ: the value is the measurement, the flag says why no esd
    expect(formatPosition(35.0912, 111)).toEqual({ value: "35.0912", esd: "" });
    expect(formatPosition(43.3551, 1e17)).toEqual({ value: "43.3551", esd: "" });
    // an esd under half a unit of the fourth place: (0), not nothing
    expect(formatPosition(37.7761, 1e-13)).toEqual({ value: "37.7761", esd: "(0)" });
    // the one real corundum line over 0.1°: an esd, not a flat direction
    expect(formatPosition(116.5035, 0.1048)).toEqual({ value: "116.5035", esd: "(1048)" });
    // the threshold is the constant, inclusive on the way out
    expect(formatPosition(57.5, POSITION_ESD_MAX_DEG).esd).toBe("");
    expect(formatPosition(57.5, 0.9999).esd).toBe("(9999)");
    // an esd that rounds *up* to the gate is over it: four places never
    // carry five digits (code review)
    expect(formatPosition(57.5, 0.99996).esd).toBe("");
    expect(formatPosition(57.5, null).esd).toBe("");
    expect(formatPosition(57.5, 0).esd).toBe("(0)");
  });
});

describe("flag and caveat tones come from the served lists", () => {
  it("marks a flag as out only when the server says it is unusable", () => {
    const unusable = ["ghost_kbeta", "excluded", "not_separable"];
    expect(flagTone("excluded", unusable)).toBe("bad");
    expect(flagTone("not_separable", unusable)).toBe("bad");
    expect(flagTone("sigma_assumed", unusable)).toBe("note");
    // a grown vocabulary changes nothing here — the split is the argument
    expect(flagTone("some_future_flag", [...unusable, "some_future_flag"])).toBe("bad");
  });

  it("colours a caveat red only when the served refuting set holds it", () => {
    const refuting = ["predicted_but_absent", "validation_failed"];
    expect(caveatTone("predicted_but_absent", refuting)).toBe("bad");
    expect(caveatTone("shift_allowance_assumed", refuting)).toBe("warn");
  });

  // every tone a component asks for has to be a member of the one set the
  // stylesheet declares (WP-1201) — a chip with an unknown tone is not a
  // failure a browser reports, it is a chip drawn in the neutral tone
  it("returns members of the app's tone vocabulary", () => {
    const tones = ["note", "ok", "warn", "bad", "accent"];
    expect(tones).toContain(flagTone("excluded", ["excluded"]));
    expect(tones).toContain(flagTone("sigma_assumed", ["excluded"]));
    expect(tones).toContain(caveatTone("x", ["x"]));
    expect(tones).toContain(caveatTone("y", ["x"]));
    for (const grade of ["high", "medium", "low"] as const) {
      expect(tones).toContain(confidenceTone(grade));
    }
    expect(confidenceTone("high")).toBe("ok");
    expect(confidenceTone("medium")).toBe("warn");
    expect(confidenceTone("low")).toBe("note");
  });
});

describe("nearestPeak", () => {
  const peaks = [
    { index: 0, two_theta: 10.0 },
    { index: 3, two_theta: 10.05 },
    { index: 7, two_theta: 25.0 },
  ];

  it("returns the closest peak inside the tolerance, by its index field", () => {
    expect(nearestPeak(peaks, 10.04, 0.1)).toBe(3);
    expect(nearestPeak(peaks, 9.99, 0.1)).toBe(0);
    expect(nearestPeak(peaks, 25.4, 0.5)).toBe(7);
  });

  it("returns null when nothing is inside the tolerance", () => {
    expect(nearestPeak(peaks, 17.0, 0.2)).toBeNull();
    expect(nearestPeak([], 10.0, 1.0)).toBeNull();
  });

  it("can hit index 0 — the ?? -1 trap at the call site is real", () => {
    expect(nearestPeak(peaks, 10.0, 0.01)).toBe(0);
  });
});

describe("grabToleranceDeg — the move gesture's radius is readable, not a screen constant", () => {
  const lab = Array.from({ length: 5 }, (_, i) => ({ fwhm: 0.2 + 0.01 * i })); // median 0.22

  it("caps the pixel radius at 1.5× the median FWHM at the survey view", () => {
    // corundum's measured survey view: 0.19 °/px → 10 px would be 1.9°, and a
    // zoom drag starting 0.9° from a line moved it 11°; the cap refuses that
    expect(grabToleranceDeg(lab, 0.19)).toBeCloseTo(1.5 * 0.22, 12);
  });

  it("keeps the 10 px rule once zoomed in enough for the line to be visible", () => {
    expect(grabToleranceDeg(lab, 0.01)).toBeCloseTo(0.1, 12);
  });

  it("scales with the pattern: a synchrotron list caps far tighter", () => {
    const sharp = [{ fwhm: 0.01 }, { fwhm: 0.012 }, { fwhm: 0.014 }];
    expect(grabToleranceDeg(sharp, 0.01)).toBeCloseTo(1.5 * 0.012, 12);
  });

  it("falls back to the pixel rule when no width is known", () => {
    expect(grabToleranceDeg([], 0.05)).toBeCloseTo(0.5, 12);
    expect(grabToleranceDeg([{ fwhm: 0 }], 0.05)).toBeCloseTo(0.5, 12);
  });
});

describe("joinCurves", () => {
  const groups: GroupCurve[] = [
    { group: 0, two_theta: [1, 2], y_fit: [10, 20], y_env: [1, 1],
      delta: [0, 1], chi2_red: 1, n_components: 1 },
    { group: 2, two_theta: [5, 6], y_fit: [30, 40], y_env: [2, 2],
      delta: [2, 3], chi2_red: 1, n_components: 1 },
  ];

  it("separates fit windows with a null so the line breaks between them", () => {
    const { x, y } = joinCurves(groups, (g) => g.y_fit);
    expect(x).toEqual([1, 2, null, 5, 6]);
    expect(y).toEqual([10, 20, null, 30, 40]);
  });

  it("joins any picked field the same way", () => {
    expect(joinCurves(groups, (g) => g.delta).y).toEqual([0, 1, null, 2, 3]);
  });
});

const CANDIDATE: Candidate = {
  cell: [4.7594, 4.7594, 12.992, 90, 90, 120],
  cell_esd: [3e-4, 3e-4, 1e-3, 0, 0, 0],
  system: "hexagonal",
  centring: "R",
  lattice_group: "R -3 m",
  volume: 254.9,
  n_indexed: 20,
  n_lines: 20,
  fom: [
    { name: "M20", value: 43.1, n_lines: 20, blind_spot: "oversized cells" },
    { name: "F20", value: 80.2, n_lines: 20, blind_spot: "" },
  ],
  found_by: ["dichotomy", "trial_error"],
  confidence: "medium",
  confidence_caveats: ["shift_allowance_assumed"],
  ambiguity: [],
  lebail: { rwp: 0.21, predicted_but_absent: 0, n_reflections: 28, status: "converged" },
  diagnostics: [],
};

describe("the candidate table's shape", () => {
  it("collects FoM columns as the union over candidates, first seen first", () => {
    const other = { ...CANDIDATE, fom: [
      { name: "M20", value: 12, n_lines: 20, blind_spot: "" },
      { name: "coverage", value: 0.9, n_lines: 20, blind_spot: "" },
    ] };
    expect(fomColumns([CANDIDATE, other])).toEqual(["M20", "F20", "coverage"]);
    expect(fomColumns([])).toEqual([]);
  });

  it("looks a member up by name, never by position", () => {
    expect(fomOf(CANDIDATE, "F20")).toBe(80.2);
    expect(fomOf(CANDIDATE, "coverage")).toBeNull();
  });

  it("reads the absent column off the lines screened, with the windowed count", () => {
    const fitted = CANDIDATE.lebail!;
    expect(absentText(fitted)).toBe("0/28");
    const screened = { ...fitted, predicted_but_absent: 6, n_reflections: 87,
      absent_source: "line_screen" as const, n_lines_screened: 23,
      predicted_but_absent_uncancellable_in_window: 0 };
    expect(absentText(screened)).toBe("6/23 lines · 0 in window");
  });

  it("summarises a cell as lengths and angles", () => {
    expect(cellText(CANDIDATE.cell)).toBe("4.7594 4.7594 12.9920 Å · 90.00 90.00 120.00°");
  });

  it("finds the furthest discriminating 2θ — the collect-to-here annotation", () => {
    expect(collectTo(CANDIDATE)).toBeNull();
    const ambiguous = { ...CANDIDATE, ambiguity: [
      { cell: [1, 1, 1, 90, 90, 90], index: 2, system: "cubic",
        discriminating_two_theta: [158.2, 161.7] },
      { cell: [2, 2, 2, 90, 90, 90], index: 4, system: "cubic",
        discriminating_two_theta: [155.0] },
    ] };
    expect(collectTo(ambiguous)).toBe(161.7);
  });
});

describe("writing a reflection (WP-1213)", () => {
  it("spaces the indices and gives a negative one a real minus", () => {
    // `[1, 0, -4].join("")` is `10-4`, which reads as one number and is worse
    // the moment an index reaches two digits
    expect(formatHkl([1, 0, -4])).toBe("(1 0 −4)");
    expect(formatHkl([12, 0, 10])).toBe("(12 0 10)");
    expect(formatHkl([0, 0, 0])).toBe("(0 0 0)");
  });
});
