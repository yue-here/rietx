// @vitest-environment jsdom
// The refinement window in the rebuilt page (WP-2216): the action bar's wiring,
// the status bar's findings count, Rwp and GoF on the bar while the graphs are
// hidden, and the recovery offer. Layout and the plot are a real browser's
// question (`tests/test_gui_layout_browser.py`); this pins the wiring.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const PROJECT = { path: "/tmp/fap.rex", name: "fap", head: "n1",
                  doc: { mode: "rietveld", ui: {}, excluded_regions: [] },
                  data: { filename: "FAP.XRA", n_points: 10, has_sigma: true }, n_phases: 1 };
const RESULT = {
  statistics: { rwp: 0.0928, gof: 1.66 },
  maturity: { immature: false },
  diagnostics: [{ level: "warning", code: "A" }, { level: "info", code: "B" },
                { level: "error", code: "C" }],
};
let result: any = RESULT;
let kept: any = { draft: null };
// an idle answer, so a second Refine is not refused as a run in flight
const runFit = vi.fn(async (_body: unknown) => ({ state: "idle", run: {} }));
const putRecovery = vi.fn(async () => ({}));

vi.mock("../api", () => ({
  ApiError: class extends Error { code = ""; empty = false; },
  api: {
    settings: async () => ({ ui: {} }),
    patchSettings: async () => ({}),
    version: async () => ({ package_version: "9.9.9" }),
    project: async () => PROJECT,
    runState: async () => ({ state: "idle", run: {} }),
    capabilities: async () => ({}),
    help: async () => ({ docs_url: null }),
    recent: async () => ({ recent: [] }),
    examples: async () => ({ examples: [] }),
    events: async () => ({ events: [] }),
    result: async () => ({ result }),
    curves: async () => { throw Object.assign(new Error("none"), { empty: true }); },
    recovery: async () => kept,
    putRecovery: () => putRecovery(),
    params: async () => ({ head: "n1", rows: [] }),
    structure: async () => ({ phases: [] }),
    run: (body: unknown) => runFit(body),
  },
}));
vi.mock("../lib/stream", async (original) => ({
  ...(await original<typeof import("../lib/stream")>()),
  follow: () => () => {},
}));

import Frame from "./Frame.svelte";

let app: ReturnType<typeof mount> | null = null;

async function boot() {
  app = mount(Frame, { target: document.body });
  for (let i = 0; i < 24; i++) await tick();
  flushSync();
}

const button = (name: string) => [...document.querySelectorAll<HTMLButtonElement>("button")]
  .find((b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").trim() === name);

beforeEach(() => {
  result = RESULT;
  kept = { draft: null };
  runFit.mockClear();
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
});

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

describe("the status bar's right half", () => {
  it("counts the result's errors and warnings at rest", async () => {
    await boot();
    expect(document.querySelector("footer .right")!.textContent!.trim()).toBe("2 findings");
  });

  it("is empty with no fit", async () => {
    result = null;
    await boot();
    expect(document.querySelector("footer .right")!.textContent!.trim()).toBe("");
  });
});

describe("the Parameters panel at /next", () => {
  it("is the rebuild's own, with the prototype's filter text", async () => {
    await boot();
    const filter = document.querySelector<HTMLInputElement>("#param-filter")!;
    expect(filter.placeholder).toBe("Filter, for example biso or Ca1");
    expect(filter.classList.contains("mono")).toBe(false);
  });
});

describe("the action bar", () => {
  it("ends the model panel with Revert, Apply and Refine, the first two idle without edits", async () => {
    await boot();
    const bar = document.querySelector("section.model .actions")!;
    expect(bar).not.toBeNull();
    expect(button("Revert")!.disabled).toBe(true);
    expect(button("Apply")!.disabled).toBe(true);
    expect(button("Refine")!.disabled).toBe(false);
  });

  it("runs the staged plan on Refine and on ⌘Enter", async () => {
    await boot();
    button("Refine")!.click();
    for (let i = 0; i < 4; i++) await tick();
    expect(runFit).toHaveBeenLastCalledWith({ kind: "fit" });
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", metaKey: true, bubbles: true }));
    for (let i = 0; i < 4; i++) await tick();
    expect(runFit).toHaveBeenCalledTimes(2);
  });

  it("runs one cycle on what is ticked when One cycle is chosen", async () => {
    await boot();
    button("One cycle")!.click();
    flushSync();
    button("Refine")!.click();
    for (let i = 0; i < 4; i++) await tick();
    expect(runFit).toHaveBeenLastCalledWith({ kind: "stage", stage: { name: "cycle", turn_on: [] } });
  });

  it("carries Rwp and GoF only while the graphs are hidden", async () => {
    await boot();
    const bar = () => document.querySelector("section.model .actions")!.textContent!;
    expect(bar()).not.toContain("Rwp");
    button("Hide the graphs")!.click();
    flushSync();
    expect(bar()).toContain("9.28 %");
    expect(bar()).toContain("1.66");
  });
});

describe("the recovery offer", () => {
  it("offers kept Parameters edits when the project opens", async () => {
    kept = { draft: { count: 1, params: { values: { "phases.0.scale": "2" } } }, saved_utc: null };
    await boot();
    expect(document.body.textContent).toMatch(/Unapplied edits/);
  });

  it("offers nothing when no edits were kept", async () => {
    await boot();
    expect(document.body.textContent).not.toMatch(/Unapplied edits/);
  });
});
