// @vitest-environment jsdom
// The rebuilt page's frame (WP-2215): the bars' order, the panel toggles and
// their keys, the workflow menu and Settings. Layout itself is a real browser's
// question (`tests/test_gui_layout_browser.py`); this pins the wiring.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const PROJECT = { path: "/tmp/fap.rex", name: "fap", doc: { mode: "rietveld", ui: {} },
                  data: { filename: "FAP.XRA", n_points: 10, has_sigma: true }, n_phases: 1 };
let project: any = PROJECT;
let run: any = { state: "idle", run: {} };
const patchSettings = vi.fn(async (_ui: unknown) => ({}));
const cancel = vi.fn(async () => ({ state: "cancelling", run: {} }));

vi.mock("../api", () => ({
  ApiError: class extends Error { code = ""; },
  api: {
    settings: async () => ({ ui: {} }),
    patchSettings: (ui: any) => patchSettings(ui),
    version: async () => ({ package_version: "9.9.9" }),
    project: async () => {
      if (!project) throw Object.assign(new Error("none"), { code: "NO_PROJECT" });
      return project;
    },
    runState: async () => run,
    cancel: () => cancel(),
    events: async () => ({ events: [] }),
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
  for (let i = 0; i < 6; i++) await tick();
  flushSync();
}

function key(k: string) {
  window.dispatchEvent(new KeyboardEvent("keydown", { key: k, metaKey: true, bubbles: true }));
  flushSync();
}

const byLabel = (label: string) =>
  document.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);

beforeEach(() => {
  project = PROJECT;
  run = { state: "idle", run: {} };
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
});

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

describe("the top bar", () => {
  it("holds the graphs toggle, the workflow menu, the project name, Settings and the model toggle, in order", async () => {
    await boot();
    const bar = document.querySelector("header.topbar")!;
    const names = [...bar.querySelectorAll("button")].map(
      (b) => b.getAttribute("aria-label") ?? b.textContent!.replace(/\s+/g, " ").trim());
    expect(names).toEqual(["Hide the graphs", "Refinement", "fap▾", "Settings", "Hide the model"]);
    expect(bar.textContent).not.toContain("rietx");
  });

  it("is drawn without a project, its project controls disabled", async () => {
    project = null;
    await boot();
    expect(byLabel("Hide the graphs")!.disabled).toBe(true);
    expect(byLabel("Hide the model")!.disabled).toBe(true);
    expect(document.querySelector<HTMLButtonElement>("button.mbtn.wf")!.disabled).toBe(true);
    expect(byLabel("Show the console")!.disabled).toBe(true);
  });
});

describe("the panels", () => {
  it("hide from their toggles and their keys, and never both sides at once", async () => {
    await boot();
    expect(document.querySelector('section[aria-label="Graphs"]')).not.toBeNull();
    key("1");
    expect(document.querySelector('section[aria-label="Graphs"]')).toBeNull();
    expect(byLabel("Hide the model")!.disabled).toBe(true);
    key("2");
    expect(document.querySelector('section[aria-label="Model"]')).not.toBeNull();
    byLabel("Show the graphs")!.click();
    flushSync();
    key("2");
    expect(document.querySelector('section[aria-label="Model"]')).toBeNull();
  });

  it("show the bottom panel from the status bar and ⌘J, hidden at first", async () => {
    await boot();
    const bottom = () => document.querySelector('section[aria-label="Console and history"]');
    expect(bottom()).toBeNull();
    byLabel("Show the console")!.click();
    flushSync();
    expect(bottom()).not.toBeNull();
    key("j");
    expect(bottom()).toBeNull();
  });
});

describe("the workflow menu", () => {
  it("lists the five, checks the current, and shows a placeholder's steps across the model panel", async () => {
    await boot();
    document.querySelector<HTMLButtonElement>("button.mbtn.wf")!.click();
    flushSync();
    const items = [...document.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')];
    expect(items.map((b) => b.textContent!.trim())).toEqual([
      "Refinement", "Peaks and indexing · placeholder", "Series · placeholder",
      "Structure solution · placeholder", "Rigid bodies · placeholder"]);
    expect(items[0].getAttribute("aria-checked")).toBe("true");
    items[3].click();
    flushSync();
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(document.querySelector("button.mbtn.wf")!.textContent).toContain("Structure solution");
    const steps = [...document.querySelectorAll<HTMLButtonElement>('nav.steps button')];
    expect(steps.map((b) => b.textContent)).toEqual(
      ["Cell and space group", "Composition", "Solve", "Complete"]);
    steps[2].click();
    flushSync();
    expect(document.querySelector(".box")!.textContent).toContain("charge flipping");
  });
});

describe("the status bar", () => {
  it("says the run's state and offers Stop only while a run is in flight; ⌘. stops it", async () => {
    await boot();
    const stop = () => [...document.querySelectorAll<HTMLButtonElement>("footer button")]
      .find((b) => b.textContent === "Stop")!;
    expect(stop().disabled).toBe(true);
    expect(document.querySelector('footer [role="status"]')!.textContent).toBe("");
    unmount(app!);
    run = { state: "running", run: { stage: "cell", stage_index: 2, n_stages: 5 } };
    await boot();
    expect(document.querySelector('footer [role="status"]')!.textContent).toBe("cell (2/5)");
    expect(stop().disabled).toBe(false);
    key(".");
    await tick();
    expect(cancel).toHaveBeenCalledTimes(1);
  });
});

describe("Settings", () => {
  it("opens on ⌘, with the theme as three choices and the version as its About line", async () => {
    await boot();
    key(",");
    const dlg = document.querySelector('[role="dialog"]')!;
    expect([...dlg.querySelectorAll('[role="radio"]')].map((b) => b.textContent))
      .toEqual(["Match system", "Light", "Dark"]);
    expect(dlg.textContent).toContain("rietx 9.9.9");
    dlg.querySelectorAll<HTMLButtonElement>('[role="radio"]')[2].click();
    flushSync();
    expect(patchSettings).toHaveBeenCalledWith({ theme: "dark" });
    expect(document.documentElement.dataset.theme).toBe("dark");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    flushSync();
    expect(document.querySelector('[role="dialog"]')).toBeNull();
  });
});
