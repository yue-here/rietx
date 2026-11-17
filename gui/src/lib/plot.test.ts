/** The pattern plot's two new choices (WP-1029). */
import { describe, expect, it } from "vitest";

import {
  curveColors,
  curveToggles,
  dataOnlyHidden,
  formatRegion,
  isDataOnly,
  maskShapes,
  masked,
  mergeRegions,
  nearestIndex,
  normalizeRegion,
  readout,
  residual,
  shows,
  toggleCurve,
  type Window,
} from "./plot";
import { hklLabel } from "rxplot";
import { formatHkl } from "./peaks";

const WEIGHTED: Window = {
  two_theta: [1, 2, 3],
  y_obs: [100, 400, 900],
  y_calc: [98, 405, 890],
  delta: [0.2, -0.25, 0.33],
  delta_raw: [2, -5, 10],
  cumulative_chi2: [0.04, 0.1025, 0.2114],
  weighted: true,
};

describe("choosing a residual", () => {
  it("gives each kind its own axis title", () => {
    expect(residual("weighted", WEIGHTED).title).toBe("(obs−calc)/σ");
    expect(residual("delta", WEIGHTED).title).toBe("obs−calc");
    expect(residual("cumulative", WEIGHTED).title).toBe("Σχ²");
    expect(residual("delta", WEIGHTED).values).toEqual([2, -5, 10]);
  });

  it("names the σ as assumed when it was not measured, and still draws Δ/σ", () => {
    // WP-1029 (s): the fit weighted by Poisson σ, so Δ/σ is exactly what it
    // minimised and is the honest curve to draw — the axis says which σ it is
    const poisson = { ...WEIGHTED, weighted: false };
    const res = residual("weighted", poisson);
    expect(res.title).toBe("(obs−calc)/σ (Poisson σ)");
    expect(res.values).toEqual(WEIGHTED.delta);
  });

  it("labels raw Δ the same either way — it is the same curve", () => {
    const poisson = { ...WEIGHTED, weighted: false };
    expect(residual("delta", poisson).title).toBe("obs−calc");
    expect(residual("delta", poisson).values).toEqual([2, -5, 10]);
  });

  it("drops the zero line under a curve that only rises", () => {
    expect(residual("cumulative", WEIGHTED).zeroline).toBe(false);
    expect(residual("weighted", WEIGHTED).zeroline).toBe(true);
  });
});

describe("the curve colours (WP-1029 q)", () => {
  it("reads each custom property and falls back per property, trimmed", () => {
    const set: Record<string, string> = {
      "--plot-obs": " #112233 ", // getPropertyValue keeps the leading space
      "--plot-diff": "#abc",
    };
    const colors = curveColors((name) => set[name] ?? "");
    expect(colors.obs).toBe("#112233");
    expect(colors.diff).toBe("#abc");
    // the un-set ones fall back to the light values — a page with no
    // stylesheet still draws the shipped plot
    expect(colors.calc).toBe("#c65d0a");
    expect(colors.bkg).toBe("#b5793a");
    expect(colors.zero).toBe("#cfcfcf");
  });

  it("reads the mask wash and its edge from properties too (WP-1033)", () => {
    // the edge is `--muted`, not a sixth plot colour: it is chrome for a
    // boundary, and it has to match the ink the strip below the plot uses
    const set: Record<string, string> = { "--plot-mask": "#00000022", "--muted": "#9a9a94" };
    const colors = curveColors((name) => set[name] ?? "");
    expect(colors.mask).toBe("#00000022");
    expect(colors.edge).toBe("#9a9a94");
    expect(curveColors(() => "").mask).toBe("#1c191714");
  });

  it("reads the peak layer's two, which are not `--accent` and `--bad` (WP-1210)", () => {
    // the plumbing only.  *How far apart* these values are is asserted in
    // `tests/test_gui_palette.py`, over `app.css` itself and through the one
    // OKLab distance this package has — a port here would be a second answer.
    const set: Record<string, string> = {
      "--plot-peak": "#0072b2", "--plot-peakfit": "#6f83e6",
      "--accent": "#c65d0a", "--bad": "#b4271f",
    };
    const colors = curveColors((name) => set[name] ?? "");
    expect(colors.peak).toBe("#0072b2");
    expect(colors.peakfit).toBe("#6f83e6");
    expect(colors.peak).not.toBe(set["--accent"]);
    expect(colors.peakfit).not.toBe(set["--bad"]);
    // a page with no stylesheet still draws the layer in its own colours
    expect(curveColors(() => "").peak).toBe("#0072b2");
    expect(curveColors(() => "").peakfit).toBe("#6f83e6");
  });

  it("reads the phase palette, whose fallbacks are the values (WP-1438)", () => {
    // these four do not follow the theme — a phase that changed colour with
    // the page would be a second fact about one row — so unlike every other
    // entry here the fallback is not "the light value", it is the value.
    const set: Record<string, string> = { "--phase-1": "#123456" };
    expect(curveColors((name) => set[name] ?? "").phase[1]).toBe("#123456");
    expect(curveColors(() => "").phase).toEqual(
      ["#009e73", "#cc79a7", "#56b4e9", "#f0e442"]);
  });
});

describe("shading what is not fitted (WP-1033)", () => {
  const COLORS = { mask: "#1b1b1b14", edge: "#6b6b66" };
  const EXTENT: [number, number] = [3, 24];

  it("draws nothing when the whole pattern is being fitted", () => {
    expect(maskShapes({ limits: null, regions: [] }, EXTENT, COLORS)).toEqual([]);
  });

  it("shades the *outside* of the fit range, clipped to the measured data", () => {
    // measured in a browser: a shape bound to a data axis takes part in the
    // autorange, so bands drawn past the data to cover a zoom-out *became* the
    // range — the 0.5–59.99° NAC pattern came back reading −40 to 100
    const shapes = maskShapes({ limits: [8, 19], regions: [] }, EXTENT, COLORS);
    const bands = shapes.flatMap((s) => (s.type === "rect" ? [[s.x0, s.x1]] : []));
    expect(bands).toEqual([[3, 8], [19, 24]]);
  });

  it("draws no band where a limit is already outside the data", () => {
    // …and no edge either: outside the measured pattern there are no channels
    // to exclude, so there is nothing there to mark
    const shapes = maskShapes({ limits: [1, 40], regions: [[30, 33]] }, EXTENT, COLORS);
    expect(shapes).toEqual([]);
  });

  it("washes a band and dots its edges, in the protocol's two inks", () => {
    // the wash marks absence from the residual and the edge is the boundary,
    // which has to stay readable when the wash is off-screen — a fit range
    // shows only its edges once you zoom inside it
    const shapes = maskShapes({ limits: [8, 19], regions: [[13, 16]] }, EXTENT, COLORS);
    expect(shapes.filter((s) => s.type === "rect").every((s) => s.color === COLORS.mask))
      .toBe(true);
    expect(shapes.filter((s) => s.type === "line").every((s) => s.color === COLORS.edge))
      .toBe(true);
  });

  it("gives every region a band and both its edges", () => {
    const shapes = maskShapes({ limits: null, regions: [[13, 16], [20, 21]] },
                              EXTENT, COLORS);
    expect(shapes.flatMap((s) => (s.type === "rect" ? [[s.x0, s.x1]] : [])))
      .toEqual([[13, 16], [20, 21]]);
    expect(shapes.filter((s) => s.type === "line").map((s) => (s.type === "line" ? s.x : NaN)))
      .toEqual([13, 16, 20, 21]);
  });
});

describe("the region list (WP-1033)", () => {
  it("orders a backwards drag and refuses a zero-width one", () => {
    expect(normalizeRegion([19, 8])).toEqual([8, 19]);
    expect(normalizeRegion([8, 19])).toEqual([8, 19]);
    expect(normalizeRegion([8, 8])).toBeNull();
    expect(normalizeRegion([NaN, 19])).toBeNull();
  });

  it("merges overlapping and touching entries, and sorts", () => {
    expect(mergeRegions([[20, 21], [3, 5]])).toEqual([[3, 5], [20, 21]]);
    expect(mergeRegions([[3, 5]], [4, 9])).toEqual([[3, 9]]);
    // touching merges because the mask is inclusive at both ends
    expect(mergeRegions([[3, 5]], [5, 9])).toEqual([[3, 9]]);
    expect(mergeRegions([[3, 9]], [4, 5])).toEqual([[3, 9]]);
  });

  it("merging changes the chip list and provably not the mask", () => {
    // the reason merging is allowed at all: `in_range_mask` removes the *union*
    // of the regions, so this is a presentation change — asserted against the
    // mask over a grid rather than by re-deriving the union in the assertion
    const drawn: [number, number][] = [[13, 16], [15.5, 17], [4, 4.5], [17, 18]];
    const merged = mergeRegions(drawn);
    expect(merged).toEqual([[4, 4.5], [13, 18]]);
    for (let x = 3; x <= 24; x += 0.05) {
      expect(masked(merged, x)).toBe(masked(drawn, x));
    }
  });

  it("labels a chip with what would be sent, not a rounded story", () => {
    expect(formatRegion([13.0004, 16])).toBe("13.000–16.000°");
  });
});

describe("which curves are drawn (WP-1032)", () => {
  const FITTED = { ...WEIGHTED, y_background: [3, 3, 3], ticks: { NAC: [1], CaF2: [2] } };

  it("offers the background only when the payload has one", () => {
    // the reported item was "make it possible to toggle the background on"; the
    // trace was already unconditional, so what was missing is the control to
    // turn a *forced* curve off
    expect(curveToggles(FITTED).map((t) => t.id))
      .toEqual(["obs", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2"]);
    expect(curveToggles({ ...FITTED, y_background: [] }).map((t) => t.id))
      .toEqual(["obs", "calc", "diff", "ticks:NAC", "ticks:CaF2"]);
  });

  it("offers only the observed points on the raw view", () => {
    // no fit, so there is no calculated curve, no background and no reflection
    // to tick — the state a project is in while peaks are picked
    expect(curveToggles({ ...FITTED, raw: true } as any).map((t) => t.id)).toEqual(["obs"]);
  });

  it("names the difference button whatever the residual knob chose", () => {
    expect(curveToggles(FITTED, "Σχ²").find((t) => t.id === "diff")!.label).toBe("Σχ²");
  });

  it("offers the masked points only when the protocol masks some (WP-1033)", () => {
    // the *points* are a drawing choice and get a toggle; the shading is not,
    // and is switched off only by removing the region that causes it
    const withMask = { ...FITTED, excluded: { two_theta: [3, 4], y_obs: [1, 2] } };
    expect(curveToggles(withMask).map((t) => t.id))
      .toEqual(["obs", "masked", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2"]);
    expect(curveToggles({ ...withMask, excluded: { two_theta: [], y_obs: [] } })
      .map((t) => t.id)).not.toContain("masked");
    // and on the raw view, which is the only place a fit range can be seen
    // before there is a fit at all
    expect(curveToggles({ ...withMask, raw: true } as any).map((t) => t.id))
      .toEqual(["obs", "masked"]);
  });

  it("hides by exception, so a curve this build does not know about is drawn", () => {
    expect(shows([], "bkg")).toBe(true);
    expect(shows(["bkg"], "bkg")).toBe(false);
    expect(toggleCurve([], "bkg")).toEqual(["bkg"]);
    expect(toggleCurve(["bkg", "obs"], "bkg")).toEqual(["obs"]);
  });

  describe("the peak layer's own two (WP-1210)", () => {
    const LAYER = { n: 3, groups: 2, active: true };

    it("offers them last, and the fit only when a group was fitted", () => {
      // last because the layer draws over everything else, and offered on the
      // raw view too: a peak list is what a project has *before* a fit
      expect(curveToggles(FITTED, "Δ", LAYER).map((t) => t.id))
        .toEqual(["obs", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2",
                  "peaks", "peakfit"]);
      expect(curveToggles({ ...FITTED, raw: true } as any, "Δ", LAYER).map((t) => t.id))
        .toEqual(["obs", "peaks", "peakfit"]);
      expect(curveToggles(FITTED, "Δ", { ...LAYER, groups: 0 }).map((t) => t.id))
        .not.toContain("peakfit");
      expect(curveToggles(FITTED, "Δ", { ...LAYER, n: 0 }).map((t) => t.id))
        .not.toContain("peaks");
      expect(curveToggles(FITTED, "Δ").map((t) => t.id)).not.toContain("peaks");
    });

    it("states the absence rather than dropping the button", () => {
      // "where did my markers go" has an answer — the tab they can be edited
      // on — and a button that is simply not there is not it
      const away = curveToggles(FITTED, "Δ", { ...LAYER, active: false });
      const peaks = away.find((t) => t.id === "peaks")!;
      expect(peaks.absent).toContain("Peaks tab");
      expect(away.find((t) => t.id === "peakfit")!.absent).toBe(peaks.absent);
      // and every other curve is drawable, so none of them carries a reason
      expect(away.filter((t) => t.absent).map((t) => t.id)).toEqual(["peaks", "peakfit"]);
      expect(curveToggles(FITTED, "Δ", LAYER).filter((t) => t.absent)).toEqual([]);
    });
  });

  describe("data only (WP-1210)", () => {
    const LAYER = { n: 3, groups: 2, active: false };

    it("hides every id but the measured points, absent ones included", () => {
      // an absent layer left out here would arrive drawn the moment its tab
      // came up, which is the button's meaning quietly lapsing
      const toggles = curveToggles(FITTED, "Δ", LAYER);
      expect(dataOnlyHidden(toggles))
        .toEqual(["calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2", "peaks", "peakfit"]);
      expect(isDataOnly(toggles, dataOnlyHidden(toggles))).toBe(true);
    });

    it("is not on while anything else is drawn, or while obs is not", () => {
      const toggles = curveToggles(FITTED, "Δ", LAYER);
      expect(isDataOnly(toggles, [])).toBe(false);
      expect(isDataOnly(toggles, ["calc"])).toBe(false);
      // obs hidden as well is *nothing* drawn, which is not the same claim
      expect(isDataOnly(toggles, [...dataOnlyHidden(toggles), "obs"])).toBe(false);
      // a lone `obs` cannot be "data only": there is nothing else to be without
      expect(isDataOnly([{ id: "obs", label: "obs", title: "" }], [])).toBe(false);
    });
  });
});

describe("an indexing candidate's lines (WP-1211)", () => {
  it("has a colour of its own, not the peak layer's", () => {
    // both layers are up on the same tab at the same time, and telling them
    // apart *is* the question the overlay answers — which of the picked lines
    // does this cell account for (WP-1210's rule, at its sharpest)
    const colors = curveColors(() => "");
    expect(colors.candidate).toBe("#1a8f45");
    expect(colors.candidate).not.toBe(colors.peak);
    expect(colors.candidate).not.toBe(colors.peakfit);
    expect(curveColors((n) => (n === "--plot-candidate" ? "#0f0" : "")).candidate)
      .toBe("#0f0");
  });

  it("is not a curve toggle, so `data only` cannot hide it", () => {
    // its control is the candidate row.  A toggle would be a second one, and
    // pressing it would leave a row looking selected with nothing on the plot.
    const toggles = curveToggles(
      { ...WEIGHTED, ticks: { NAC: [1] } }, "Δ", { n: 1, groups: 0, active: true });
    expect(toggles.map((t) => t.id)).not.toContain("candidate");
    expect(dataOnlyHidden(toggles)).not.toContain("candidate");
  });
});

describe("the readout strip (WP-1213)", () => {
  const FITTED = {
    ...WEIGHTED,
    y_background: [3, 4, 5],
    ticks: { NAC: [1.002, 2.5], CaF2: [2.9] },
  };
  // the same payload with the `tick_hkl` companion the route serves beside
  // `ticks`, pinned to it index for index
  const INDEXED = {
    ...FITTED,
    tick_hkl: { NAC: [[1, 1, 0], [2, 0, 0]], CaF2: [[2, -2, 0]] },
  };
  const PEAKS = [
    { index: 0, two_theta: 2.0004, two_theta_esd: 0.0003, d: 4.4, intensity: 50,
      fwhm: 0.1, group: 0, n_in_group: 1, chi2_red: 1, flags: [],
      origin: "fitted" as const, usable: true },
    { index: 1, two_theta: 2.9, two_theta_esd: 0.0002, d: 3.1, intensity: 100,
      fwhm: 0.1, group: 1, n_in_group: 1, chi2_red: 1, flags: [],
      origin: "manual" as const, usable: true },
  ];
  const GROUPS = [
    { group: 0, two_theta: [1.9, 2.0, 2.1], y_fit: [10, 400, 11],
      y_env: [0, 0, 0], delta: [0.1, -0.2, 0.3], chi2_red: 1, n_components: 1 },
  ];
  const value = (r: ReturnType<typeof readout>, id: string) =>
    r!.rows.find((row) => row.id === id)?.value;

  it("reads the channel nearest the pointer, not the pointer", () => {
    // the curves are drawn at channels, so a readout quoting a 2θ between two
    // of them would print one position and another channel's intensities
    const out = readout(FITTED, 1.9, { kind: "weighted" })!;
    expect(out.position).toBe("2.0000°");
    expect(value(out, "obs")).toBe("400");
    expect(value(out, "calc")).toBe("405");
    expect(value(out, "bkg")).toBe("4");
  });

  it("finds the nearest channel by halving, over a long ascending axis", () => {
    const xs = Array.from({ length: 1001 }, (_, i) => 5 + i * 0.01);
    expect(nearestIndex(xs, 5)).toBe(0);
    expect(nearestIndex(xs, 15)).toBe(1000);
    expect(nearestIndex(xs, 9.997)).toBe(500);   // 10.00 is nearer than 9.99
    expect(nearestIndex(xs, -3)).toBe(0);        // off the end, both ways
    expect(nearestIndex(xs, 99)).toBe(1000);
    expect(nearestIndex([], 1)).toBe(-1);
  });

  it("names the residual on screen, and only that one", () => {
    expect(value(readout(FITTED, 3, { kind: "weighted" }), "diff")).toBe("0.33");
    const cumulative = readout(FITTED, 3, { kind: "cumulative" })!;
    expect(cumulative.rows.find((r) => r.id === "diff")!.label).toBe("Σχ²");
    expect(cumulative.rows.filter((r) => r.id === "diff")).toHaveLength(1);
  });

  it("quotes a zoomed Σχ² from the view's left edge, as the curve is drawn (WP-1461)", () => {
    // the payload sums over every fitted channel, and a zoom re-bases the curve
    // (`rxplot.chi2Base`); a strip quoting the whole sum would sit under a
    // curve reading something else
    const at = (kind: "cumulative" | "weighted") =>
      value(readout(FITTED, 3, { kind, chi2Base: 0.04 }), "diff");
    expect(at("cumulative")).toBe(String(0.2114 - 0.04));
    // …and only there: a Δ/σ has nothing summed to subtract
    expect(at("weighted")).toBe("0.33");
  });

  it("quotes the unscaled intensity at six figures, as the deleted templates did", () => {
    // `%{customdata:.6g}` over `w.y_obs`, never the √ of it: a strip that read
    // in √counts beside an axis labelled in intensity is two answers
    const big = { ...FITTED, y_obs: [1234567.89, 400, 900] };
    expect(value(readout(big, 1, { kind: "weighted" }), "obs")).toBe("1234570");
  });

  it("computes d from the source's primary line, and omits it without one", () => {
    // λ/(2 sin θ) at 2θ = 2°, λ = 1.5406 Å
    expect(readout(FITTED, 2, { kind: "weighted", wavelengths: [1.5406] })!.d)
      .toBe("44.1372 Å");
    expect(readout(FITTED, 2, { kind: "weighted" })!.d).toBe("—");
  });

  it("gives every drawn curve a row and every undrawn one none", () => {
    // the strip's shape follows the payload and the tab, never the pointer:
    // a row that appeared and vanished under one sweep would reflow it
    expect(readout(FITTED, 2, { kind: "weighted" })!.rows.map((r) => r.id))
      .toEqual(["obs", "calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2"]);
    expect(readout({ ...FITTED, y_background: [] }, 2, { kind: "weighted" })!
      .rows.map((r) => r.id)).not.toContain("bkg");
    // the raw view: no model, no background, no ticks
    expect(readout({ ...FITTED, raw: true, ticks: {} } as any, 2, { kind: "weighted" })!
      .rows.map((r) => r.id)).toEqual(["obs"]);
  });

  it("gives each row the ink of the mark it names", () => {
    const inks = Object.fromEntries(
      readout(FITTED, 2, { kind: "weighted" })!.rows.map((r) => [r.id, r.ink]));
    expect(inks).toMatchObject({ obs: "obs", calc: "calc", bkg: "bkg", diff: "diff" });
    // a phase's tick row still carries no ink, and the reason changed with
    // WP-1438: the row *has* a colour now, `--phase-N`, but `ink` names a
    // `--plot-*` role and a phase colour is not one of them
    expect(inks["ticks:NAC"]).toBeUndefined();
  });

  it("says how far the nearest reflection of each phase is, signed", () => {
    const out = readout(FITTED, 1, { kind: "weighted" })!;
    expect(value(out, "ticks:NAC")).toBe("+0.0020°");
    expect(value(out, "ticks:CaF2")).toBe("+1.9000°");
    expect(value(readout(FITTED, 3, { kind: "weighted" }), "ticks:CaF2")).toBe("-0.1000°");
  });

  it("names the reflection it is the offset to (WP-1438)", () => {
    // pinned to the position by index, and spelled as the candidate row two
    // rows down spells one — this is the answer the hover box was briefly
    // asked for, and it is here because WP-1213's box is gone
    const out = readout(INDEXED, 1, { kind: "weighted" })!;
    expect(value(out, "ticks:NAC")).toBe("(1 1 0) +0.0020°");
    expect(value(out, "ticks:CaF2")).toBe("(2 −2 0) +1.9000°");
  });

  it("keeps the offset alone where a result carries no indices", () => {
    // a project written before the indices were carried reopens with the
    // positions and not them, and a row that gained `undefined` would be
    // worse than one that gained nothing
    expect(value(readout(FITTED, 1, { kind: "weighted" }), "ticks:NAC"))
      .toBe("+0.0020°");
    // and so does a phase the companion happens not to cover
    const half = { ...FITTED, tick_hkl: { NAC: [[1, 1, 0], [2, 0, 0]] } };
    const out = readout(half as typeof FITTED, 1, { kind: "weighted" })!;
    expect(value(out, "ticks:NAC")).toBe("(1 1 0) +0.0020°");
    expect(value(out, "ticks:CaF2")).toBe("+1.9000°");
  });

  it("prints a picked line as the peak table prints it (WP-1209)", () => {
    const out = readout(FITTED, 2, {
      kind: "weighted", peaks: PEAKS, peaksActive: true, peakTolerance: 0.05 });
    // four places, esd in the last of them, and I relative to the strongest
    // *measured* line — the raw area means nothing on its own
    expect(value(out, "peaks")).toBe("#0 2.0004(3)° · I 50.0");
  });

  it("keeps the picked-line slot with an em dash when none is in reach", () => {
    const out = readout(FITTED, 1, {
      kind: "weighted", peaks: PEAKS, peaksActive: true, peakTolerance: 0.05 });
    expect(value(out, "peaks")).toBe("—");
  });

  it("hit-tests the pointer, not the channel the readout snapped to", () => {
    // Measured in Chrome on the NAC example: the drawn pattern is decimated,
    // so at a survey view the nearest drawn channel is up to ~0.03° from the
    // pointer — wider than the tolerance being applied — and the pointer sat
    // exactly on three picked lines in a row while the row read `—`.
    const coarse = { ...FITTED, two_theta: [1, 3], y_obs: [100, 900],
                     y_calc: [98, 890], delta: [0.2, 0.33], ticks: {} };
    const line = [{ ...PEAKS[0], two_theta: 2.4 }];
    const out = readout(coarse, 2.4, {
      kind: "weighted", peaks: line, peaksActive: true, peakTolerance: 0.05 });
    // the position is still the channel's — every printed number belongs to
    // one measured point — while the line under the pointer is found anyway
    expect(out!.position).toBe("3.0000°");
    expect(value(out, "peaks")).toContain("#0 2.4000(3)°");
  });

  it("has no peak row at all away from the tab that draws the layer (WP-1210)", () => {
    const out = readout(FITTED, 2, { kind: "weighted", peaks: PEAKS, groups: GROUPS });
    expect(out!.rows.map((r) => r.id)).not.toContain("peaks");
    expect(out!.rows.map((r) => r.id)).not.toContain("peakfit");
  });

  it("names the fitted group profile, which is why it stopped being skipped", () => {
    // WP-1210 gave the dashed curve a hover so a reader could tell it from the
    // model; deleting the templates means the strip carries that naming
    const out = readout(FITTED, 2, {
      kind: "weighted", groups: GROUPS, peaksActive: true });
    expect(out!.rows.find((r) => r.id === "peakfit")!.label).toBe("peak fit");
    expect(value(out, "peakfit")).toBe("400");
    // outside every fitted window there is no curve to quote
    expect(value(readout(FITTED, 3, {
      kind: "weighted", groups: GROUPS, peaksActive: true }), "peakfit")).toBe("—");
  });

  it("adds the groups' own residual only on the raw view, where it is drawn", () => {
    const raw = { ...FITTED, raw: true, ticks: {} } as any;
    expect(readout(raw, 2, { kind: "weighted", groups: GROUPS, peaksActive: true })!
      .rows.map((r) => r.id)).toEqual(["obs", "peakfit", "peakdelta"]);
    expect(readout(FITTED, 2, { kind: "weighted", groups: GROUPS, peaksActive: true })!
      .rows.map((r) => r.id)).not.toContain("peakdelta");
  });

  it("names the candidate line by hkl and by the λ it belongs to (WP-1211)", () => {
    const candidate = {
      label: "4.7 4.7 12.9 Å", n_total: 3, two_theta: [1.0, 2.001, 2.9],
      hkl: [[1, 0, 0], [1, 0, -4], [1, 1, 0]], line: [0, 1, 0],
    };
    const out = readout(FITTED, 2, {
      kind: "weighted", candidate, candidateTolerance: 0.05,
      wavelengths: [1.5406, 1.5444] });
    expect(value(out, "candidate")).toBe("(1 0 −4) · λ 1.5444 Å");
  });

  it("quotes no ordinal and no count, because the drawn set can be a sample", () => {
    // past `MAX_CANDIDATE_TICKS` the server thins by rank, so "the 743rd line"
    // would be a statement about the sample; the status line owns the count
    const candidate = {
      label: "c", n_total: 92103, two_theta: [2.0], hkl: [[1, 0, 0]], line: [0] };
    const text = value(readout(FITTED, 2, {
      kind: "weighted", candidate, wavelengths: [1.5406] }), "candidate")!;
    expect(text).not.toMatch(/92103|#|\bof\b/);
  });

  it("keeps the candidate slot when nothing is near, and drops it with no overlay", () => {
    const candidate = { label: "c", n_total: 1, two_theta: [1.0],
                        hkl: [[1, 0, 0]], line: [0] };
    expect(value(readout(FITTED, 3, {
      kind: "weighted", candidate, candidateTolerance: 0.05 }), "candidate")).toBe("—");
    expect(readout(FITTED, 3, { kind: "weighted" })!.rows.map((r) => r.id))
      .not.toContain("candidate");
  });

  it("names what is drawn, so `data only` empties the strip to the points", () => {
    // the rows follow `curveToggles`' own exception list, read the same way: a
    // readout quoting a curve nobody can see is naming something that is not
    // on the plot
    const out = readout(FITTED, 2, {
      kind: "weighted", hidden: ["calc", "bkg", "diff", "ticks:NAC", "ticks:CaF2"] });
    expect(out!.rows.map((r) => r.id)).toEqual(["obs"]);
  });

  describe("inside an excluded region", () => {
    // the masked channels are in no result and arrive on their own arm
    // (WP-1033), so a pointer in a region is over a point the fitted array does
    // not have at all
    const MASKED = { ...FITTED, two_theta: [1, 3], y_obs: [100, 900],
                     y_calc: [98, 890], y_background: [3, 5],
                     delta: [0.2, 0.33], ticks: { NAC: [1.002] },
                     excluded: { two_theta: [2], y_obs: [444] } };

    it("reads the masked point rather than the nearest surviving channel", () => {
      const out = readout(MASKED, 2.01, { kind: "weighted" })!;
      expect(out.position).toBe("2.0000°");
      expect(value(out, "obs")).toBe("444");
    });

    it("quotes no model there, because there is none — which is how it says so", () => {
      const out = readout(MASKED, 2.01, { kind: "weighted" })!;
      expect(value(out, "calc")).toBe("—");
      expect(value(out, "bkg")).toBe("—");
      expect(value(out, "diff")).toBe("—");
      // …and the reflection offset is still the truth about that 2θ
      expect(value(out, "ticks:NAC")).toBe("-0.9980°");
    });

    it("ignores the masked arm when its points are not drawn", () => {
      const out = readout(MASKED, 2.01, { kind: "weighted", hidden: ["masked"] })!;
      expect(out.position).toBe("3.0000°");
      expect(value(out, "obs")).toBe("900");
    });
  });

  it("answers nothing where there is nothing to read", () => {
    // no payload and no channels are the two states with no strip at all; a
    // pointer that is merely elsewhere is a different answer (below)
    expect(readout(null, 2, { kind: "weighted" })).toBeNull();
    expect(readout({ ...FITTED, two_theta: [] }, 2, { kind: "weighted" })).toBeNull();
  });

  it("keeps every field and empties it while the pointer is off the plot", () => {
    // the resting state, which is most of the time. It is the same shape as a
    // reading, because a strip that grew a field on hover would resize the
    // canvas above it once per entry — WP-1212's jitter, arriving through the
    // repair for it
    const resting = readout(FITTED, null, {
      kind: "weighted", peaks: PEAKS, peaksActive: true, groups: GROUPS,
      wavelengths: [1.5406],
      candidate: { label: "c", n_total: 1, two_theta: [2], hkl: [[1, 0, 0]], line: [0] },
    })!;
    const reading = readout(FITTED, 2, {
      kind: "weighted", peaks: PEAKS, peaksActive: true, groups: GROUPS,
      wavelengths: [1.5406],
      candidate: { label: "c", n_total: 1, two_theta: [2], hkl: [[1, 0, 0]], line: [0] },
    })!;
    expect(resting.rows.map((r) => r.id)).toEqual(reading.rows.map((r) => r.id));
    expect(resting.rows.map((r) => r.label)).toEqual(reading.rows.map((r) => r.label));
    expect(resting.rows.map((r) => r.value)).toEqual(resting.rows.map(() => "—"));
    expect(resting.position).toBe("—");
    expect(resting.d).toBe("—");
    // a non-finite x is the same answer, not a crash and not a null strip
    expect(readout(FITTED, NaN, { kind: "weighted" })!.position).toBe("—");
  });
});


// ----------------------------------------------------------------------
// which reflection a tick is (WP-1438)
// ----------------------------------------------------------------------
describe("the watcher's hkl label", () => {
  const CASES: [number[], string][] = [
    [[1, 1, 0], "(1 1 0)"],
    [[0, 0, 2], "(0 0 2)"],
    [[1, 0, -1], "(1 0 \u22121)"],
    [[-12, 4, -10], "(\u221212 4 \u221210)"],
  ];

  it("is `formatHkl`, case for case", async () => {
    // Two pages showing one reflection two ways is the shape `viz/theme.py`
    // exists to stop, one rank over: this app writes an index through
    // `formatHkl` — the peaks table, the strip's candidate row, the strip's
    // tick rows — and `rietx watch` writes the same index into a hover box.
    // The watcher's copy is a `.mjs` in the wheel and this one is TypeScript
    // in a build input, so neither can import the other, and the guard is
    // this table run against both.
    // The specifier is a variable, so TypeScript does not try to resolve a
    // declaration file for a plain `.mjs` in the wheel's tree — there is
    // none to find, and a suppression comment would be this repo's first.
    // resolved against this file rather than the vite root, which is `gui/`
    // and has no view of the wheel's tree
    const where = new URL(
      "../../../src/rietx/watch/static/watch-core.mjs",
      import.meta.url).href;
    const core = (await import(/* @vite-ignore */ where)) as {
      hklLabel: (hkl: unknown) => string;
    };
    for (const [hkl, want] of CASES) {
      expect(core.hklLabel(hkl)).toBe(want);
      expect(core.hklLabel(hkl)).toBe(formatHkl(hkl));
      // the chart module's, which `rietx compare` writes its tick box with;
      // the watcher's copy cannot import it under `node --test` (WP-1461)
      expect(hklLabel(hkl)).toBe(want);
    }
    expect(hklLabel([1, 1])).toBe("");
    // and its own guard, which `formatHkl` does not need: the watcher reads
    // a snapshot somebody else wrote, while every caller here holds a row
    // the route built (`watch_core.test.mjs` owns the rest of that case)
    expect(core.hklLabel([1, 1])).toBe("");
  });
});
