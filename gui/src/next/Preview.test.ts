// @vitest-environment jsdom
// Hand fitting at /next (WP-2218): the Pattern graph's title line says what it
// shows in each state, so a preview never reads as a changed fit (milestone
// acceptance row 6), and the Interactive tab is the rebuild's own. What the
// chart paints, the legend's reserved slot and a real drag are a real
// browser's question (`tests/test_gui_layout_browser.py`).
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

const f64 = (...v: number[]) => Float64Array.from(v);
const CURVES = {
  header: { fit: true, weighted: true, ticks: {}, tick_hkl: {} },
  arrays: {
    two_theta: f64(10, 20, 30), y_obs: f64(1, 2, 3), kept: Int32Array.from([0, 1, 2]),
    fitted: Int32Array.from([0, 1, 2]), y_calc: f64(1, 2, 3), y_background: f64(0, 0, 0),
    delta: f64(0, 0, 0), delta_raw: f64(0, 0, 0), cumulative_chi2: f64(0, 0, 0),
  },
};
const setPreview = vi.fn();
// a pane as `relayout` reads it: where it sits, and its plot area
const pane = () => ({ root: { offsetTop: 0 }, bbox: { top: 0, height: 100, width: 100 },
                      over: document.createElement("div"), scales: { x: { min: 10, max: 30 } },
                      valToPos: () => 0, axes: [] });

vi.mock("./pattern", async (original) => ({
  ...(await original<typeof import("./pattern")>()),
  fetchCurves: async () => CURVES,
  PatternChart: class {
    fig = { panes: { main: pane(), ticks: pane(), resid: pane() }, setMode() {}, setX() {}, setHidden() {}, setResidual() {}, setY() {},
            redraw() {}, chi2Base: () => 0, onCursor: null, onSelect: null };
    setCurves() {}
    update() {}
    setPreview(p: unknown) { setPreview(p); }
    destroy() {}
    retheme() {}
  },
}));

import Pattern from "./Pattern.svelte";

const RESULT = { statistics: { rwp: 0.0928, gof: 1.66 }, maturity: { immature: false } };
let app: ReturnType<typeof mount> | null = null;

async function draw(props: Record<string, unknown>) {
  app = mount(Pattern, { target: document.body, props: { result: RESULT, plotKey: 0, ...props } });
  // the chart module is a dynamic import, so the first draw lands after a few macrotasks
  await vi.waitFor(() => { flushSync(); if (!document.querySelector(".gtitle b")) throw new Error("no title yet"); },
                    { timeout: 15000, interval: 20 });
  await tick();
  flushSync();
}

const titleText = () => document.querySelector(".gtitle")!.textContent!.replace(/\s+/g, " ").trim();

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  setPreview.mockClear();
});

describe("the Pattern graph's title line", () => {
  it("says Last fit with its Rwp and GoF at rest", async () => {
    await draw({});
    expect(titleText()).toBe("Last fit Rwp 9.28 % GoF 1.66");
  });

  it("says a preview is not refined, with its Rwp beside the last fit's", async () => {
    await draw({ preview: { curves: { header: { rwp: 0.3001 }, arrays: {} }, sentAt: 0 } });
    expect(document.querySelector(".gtitle b.pv")?.textContent).toBe("Preview, not refined");
    expect(titleText()).toBe("Preview, not refined Rwp 30.01 %, last fit 9.28 %");
    expect(setPreview).toHaveBeenCalled();
  });

  it("toggles between the preview and the last fit, drawn whole", async () => {
    // the maintainer's look, 2026-11-21, item 4
    await draw({});
    expect(document.querySelector(".gctl .segmented")).toBeNull();
    app && unmount(app);
    document.body.innerHTML = "";
    const curves = { header: { rwp: 0.3001 }, arrays: {} };
    await draw({ preview: { curves, sentAt: 0 } });
    const buttons = [...document.querySelectorAll<HTMLButtonElement>(".gctl .segmented button")];
    expect(buttons.map((b) => b.textContent)).toEqual(["Preview", "Last fit"]);
    expect(buttons[0].getAttribute("aria-pressed")).toBe("true");
    setPreview.mockClear();
    buttons[1].click();
    flushSync();
    expect(setPreview).toHaveBeenLastCalledWith(null);
    expect(titleText()).toBe("Last fit Rwp 9.28 % GoF 1.66");
    buttons[0].click();
    flushSync();
    expect(setPreview).toHaveBeenLastCalledWith(curves);
    expect(titleText()).toBe("Preview, not refined Rwp 30.01 %, last fit 9.28 %");
  });

  it("says a refused preview, the route's words in its tooltip", async () => {
    await draw({ previewError: "below the lower bound 0" });
    expect(titleText()).toBe("Last fit Preview refused Rwp 9.28 % GoF 1.66");
    expect(document.querySelector(".gtitle")!.getAttribute("title"))
      .toBe("Last fit. Preview refused: below the lower bound 0");
  });

  it("hands the curves it drew to the frame, which measures the sliders' ranges on them", async () => {
    const oncurves = vi.fn();
    await draw({ oncurves });
    expect(oncurves).toHaveBeenCalledWith(CURVES);
  });
});
