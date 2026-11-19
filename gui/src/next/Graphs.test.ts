// @vitest-environment jsdom
// The Peaks and Background graphs at /next (WP-2218, rows 59-68): each title
// line says what the graph shows (milestone acceptance row 6), the Peaks graph
// frames up to three windows or says it has none, and the Background graph's
// term chips are pending holds that the band is fetched with. What a canvas
// paints is a real browser's question (`tests/test_gui_layout_browser.py`).
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

/** A fitted payload: Gaussians at `centres` on 10 counts of background. */
function curves(centres: number[], fit = true): any {
  const n = 4001, tt = new Float64Array(n), calc = new Float64Array(n), bkg = new Float64Array(n);
  for (let i = 0; i < n; i++) {
    tt[i] = 10 + i * 0.01;
    bkg[i] = 10;
    calc[i] = 10 + centres.reduce((s, c) => s + 100 * Math.exp(-4 * Math.LN2 * ((tt[i] - c) / 0.1) ** 2), 0);
  }
  const fitted = Int32Array.from({ length: n }, (_, i) => i);
  return { header: { fit, ticks: { apatite: centres }, tick_hkl: { apatite: centres.map((_, k) => [k, 0, 1]) } },
           arrays: { two_theta: tt, y_obs: calc, fitted, y_calc: calc, y_background: bkg,
                     delta: new Float64Array(n) } };
}

let payload: any = curves([12, 20, 30, 40, 48]);
vi.mock("./pattern", () => ({ fetchCurves: async () => payload }));

const background = vi.fn();
const answer = {
  header: { head: "n1", kind: "chebyshev", n_free: 3, n_background_free: 3, n_other_free: 0,
            chi2_red: 1, esd_inflation: 1, band_absent: null, pending_holds: [],
            terms: [0, 1, 2].map((k) => ({ path: `instrument.background.c${k}`, value: 1, esd: 0.1,
                                           vary: true, held: false, refinable: true, held_because: null })) },
  arrays: { two_theta: Float64Array.from([10, 20]), y_obs: Float64Array.from([5, 6]),
            y_background: Float64Array.from([4, 4]), band_esd: Float64Array.from([0.1, 0.1]) },
};
vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  api: { background: (hold: string[]) => { background(hold); return Promise.resolve(new ArrayBuffer(0)); } },
}));
vi.mock("./rxplot.mjs", async (original) => ({
  ...(await original<typeof import("./rxplot.mjs")>()),
  unpack: () => answer,
}));

import Background from "./Background.svelte";
import Peaks from "./Peaks.svelte";

let app: ReturnType<typeof mount> | null = null;
const titleText = () => document.querySelector(".gtitle")!.textContent!.replace(/\s+/g, " ").trim();

async function settle(ready: () => boolean) {
  await vi.waitFor(() => { flushSync(); if (!ready()) throw new Error("not yet"); },
                   { timeout: 15000, interval: 20 });
  await tick();
  flushSync();
}

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  background.mockClear();
  payload = curves([12, 20, 30, 40, 48]);
});

describe("the Peaks graph (rows 59-62)", () => {
  it("frames three windows of the last fit and says so", async () => {
    app = mount(Peaks, { target: document.body, props: { rwp: 0.0928 } });
    await settle(() => document.querySelectorAll("figure").length > 0);
    expect(titleText()).toBe("Last fit Rwp 9.28 %");
    expect(document.querySelectorAll("figure")).toHaveLength(3);
    const caption = document.querySelector("figcaption")!.textContent!.replace(/\s+/g, " ");
    expect(caption).toMatch(/\d+\.\d\d°/);
    expect(caption).toContain("apatite");
    // the two views, on the title line
    const show = [...document.querySelectorAll('[aria-label="Show"] button')].map((b) => b.textContent);
    expect(show).toEqual(["Data and model", "Peak shape alone"]);
  });

  it("shades each shown window's range on the overview, and a step moves its band", async () => {
    app = mount(Peaks, { target: document.body, props: { rwp: 0.0928 } });
    await settle(() => document.querySelectorAll("figure").length > 0);
    const bands = () => [...document.querySelectorAll<HTMLElement>(".overview .band")].map((b) => b.style.left);
    const before = bands();
    expect(before).toHaveLength(document.querySelectorAll("figure").length);
    (document.querySelector('[aria-label="Previous peak"]:not(:disabled)') as HTMLButtonElement).click();
    await settle(() => bands().join() !== before.join());
    expect(bands()).toHaveLength(before.length);
  });

  it("says a preview is not refined, with both Rwp values", async () => {
    const preview = { curves: { header: { rwp: 0.3001 }, arrays: payload.arrays }, sentAt: 0 };
    app = mount(Peaks, { target: document.body, props: { rwp: 0.0928, preview } });
    await settle(() => document.querySelectorAll("figure").length > 0);
    expect(titleText()).toBe("Preview, not refined Rwp 30.01 %, last fit 9.28 %");
    expect(document.querySelector(".gtitle b.pv")).not.toBeNull();
  });

  it("has a one-line empty state before a fit", async () => {
    payload = curves([12], false);
    app = mount(Peaks, { target: document.body, props: {} });
    await settle(() => !!document.querySelector(".empty"));
    expect(document.querySelector(".empty")!.textContent).toBe("No fitted peaks to frame yet.");
    expect(document.querySelectorAll("figure")).toHaveLength(0);
  });
});

describe("the Background graph (rows 63-68)", () => {
  it("draws the band for the pending holds and says it is a preview", async () => {
    const onhold = vi.fn();
    const holds = new Map([["instrument.background.c1", true], ["phases.0.cell.a", true]]);
    app = mount(Background, { target: document.body, props: { head: "n1", holds, onhold } });
    await settle(() => document.querySelectorAll(".chips .term").length === 3);
    expect(background).toHaveBeenLastCalledWith(["instrument.background.c1"]);
    expect(titleText()).toBe("Background preview");
    const chips = [...document.querySelectorAll<HTMLButtonElement>(".chips .term")];
    expect(chips.map((c) => c.getAttribute("aria-pressed"))).toEqual(["false", "true", "false"]);
    // a chip is a pending edit: it asks the shell, and writes nothing itself
    chips[0].click();
    expect(onhold).toHaveBeenCalledWith("instrument.background.c0", true, false);
    expect([...document.querySelectorAll('[aria-label="Type"] button')].map((b) => b.getAttribute("aria-pressed")))
      .toEqual(["true", "false"]);
    expect(document.querySelector<HTMLInputElement>('input[aria-label="Terms"]')!.value).toBe("3");
  });

  it("offers no dimensionless stiffness stop on a λ in intensity units", async () => {
    const saved = answer.header;
    answer.header = { ...saved, kind: "pspline", lambda_smooth: 1e-6, lambda_units: "intensity" } as any;
    try {
      app = mount(Background, { target: document.body, props: { head: "n1" } });
      await settle(() => !!document.querySelector('input[aria-label="Stiffness"]'));
      const slider = document.querySelector<HTMLInputElement>('input[aria-label="Stiffness"]')!;
      expect(slider.disabled).toBe(true);
      expect(slider.closest(".bgctl")!.textContent).toContain("intensity⁻²");
    } finally {
      answer.header = saved;
    }
  });

  it("names the current values at rest, and waits for a run", async () => {
    app = mount(Background, { target: document.body, props: { head: "n1" } });
    await settle(() => document.querySelectorAll(".chips .term").length === 3);
    expect(background).toHaveBeenLastCalledWith([]);
    expect(titleText()).toBe("Background at the current values");
    unmount(app);
    app = mount(Background, { target: document.body, props: { head: "n1", busy: true } });
    flushSync();
    expect(titleText()).toBe("Background at the current values waiting for the run");
  });
});
