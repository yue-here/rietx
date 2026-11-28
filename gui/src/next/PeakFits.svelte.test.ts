// @vitest-environment jsdom
// The Fit step's windows (WP-2240 task 6): a line's own curve is hidden by its
// numbered toggle, and the choice follows the line by 2θ through a refit. What
// the canvases paint is a real browser's question
// (`tests/test_gui_layout_browser.py`).
import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import type { PeakRow, PeaksPayload } from "../lib/peaks";
import PeakFits from "./PeakFits.svelte";

const row = (index: number, two_theta: number): PeakRow => ({
  index, two_theta, two_theta_esd: 0.001, d: 1, intensity: 1, fwhm: 0.1, group: 0,
  n_in_group: 2, chi2_red: 1, flags: [], origin: "fitted", usable: true,
} as PeakRow);
const payload = (a: number, b: number) => ({
  peaks: [row(0, a), row(1, b)],
  groups: [{ group: 0, two_theta: [a - 0.2, b + 0.2], y_fit: [1, 1], y_env: [0, 0],
             delta: [0, 0], chi2_red: 1, n_components: 2 }],
} as unknown as PeaksPayload);

let app: Record<string, any> | null = null;
afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

const pressed = () => [...document.querySelectorAll(".ib.line")]
  .map((b) => b.getAttribute("aria-pressed"));

describe("a window's line toggles", () => {
  it("hide one line's curve, even beside a twin, and keep it hidden through a refit", () => {
    const props = $state({ peaks: payload(25.42, 25.4207), groups: [0], total: 1 });
    app = mount(PeakFits, { target: document.body, props });
    flushSync();
    expect(pressed()).toEqual(["true", "true"]);
    // two lines 0.0007° apart: hiding the first leaves the second drawn
    (document.querySelector(".ib.line") as HTMLElement).click();
    flushSync();
    expect(pressed()).toEqual(["false", "true"]);
    // a refit moves each line by its fit and may renumber the rows
    props.peaks = payload(25.4212, 25.4219);
    flushSync();
    expect(pressed()).toEqual(["false", "true"]);
    (document.querySelector(".ib.line") as HTMLElement).click();
    flushSync();
    expect(pressed()).toEqual(["true", "true"]);
  });
});
