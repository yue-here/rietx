// @vitest-environment jsdom
// The help popover at /next (WP-2244). It was mounted by today's page alone, so
// every `<Help>` term here opened nothing. What it shows is `App.test.ts`'s
// "the help popover"; this pins that the rebuilt page mounts it, and that its
// Esc is the popover's before any layer's. A real click is
// `tests/test_gui_layout_browser.py`'s.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/stream", async (original) => ({
  ...(await original<typeof import("../lib/stream")>()),
  follow: () => () => {},
}));

import Frame from "./Frame.svelte";

const PROJECT = { path: "/tmp/fap.rex", name: "fap", head: "n0001", n_nodes: 2, n_phases: 1,
                  doc: { mode: "rietveld", ui: {}, plan: null, two_theta_limits: null,
                         excluded_regions: [] },
                  data: { filename: "FAP.XRA", n_points: 10, has_sigma: true } };
const IDLE = { state: "idle", run: {}, project: PROJECT.path, head: "n0001" };
const HELP = {
  docs_url: "https://example.invalid/docs/",
  parameters: [
    { paths: ["phases.*.cell.a"], title: "Cell edge", description: "A unit-cell edge length.",
      unit: "Å", default: null, typical: null,
      anchor: "theory/peak-positions.html#lattice-metric-and-bragg-s-law" },
  ],
};
const ROW = { path: "phases.0.cell.a", value: 9.37, vary: true, lo: 0.1, hi: "Infinity",
              tie: null, locked: false, esd: null, mode_fixed: false, held: false,
              help_key: "phases.*.cell.a", refinable: true, held_because: "" };

function serve() {
  const routes: Record<string, () => unknown> = {
    "/api/settings": () => ({ ui: {} }),
    "/api/version": () => ({ package_version: "9.9.9" }),
    "/api/capabilities": () => ({}),
    "/api/help": () => HELP,
    "/api/project": () => PROJECT,
    "/api/run/state": () => IDLE,
    "/api/recent": () => ({ recent: [] }),
    "/api/examples": () => ({ examples: [] }),
    "/api/events": () => ({ events: [], next: 0, oldest: 1, ...IDLE }),
    "/api/params": () => ({ parameters: [ROW], n_free: 1 }),
    "/api/structure": () => ({ structure: { phases: [] }, sites: [], symmetry: [] }),
  };
  vi.stubGlobal("fetch", vi.fn(async (input: any) => {
    const path = String(input).split("?")[0];
    const handler = routes[path] as (() => unknown) | undefined;
    const status = handler ? 200 : 409;
    const body = handler ? handler()
      : { error: { code: "NO_RESULT", message: `nothing at ${path}` } };
    return { ok: status < 400, status, text: async () => JSON.stringify(body) } as any;
  }));
}

let app: ReturnType<typeof mount> | null = null;

async function settle() {
  for (let i = 0; i < 24; i++) await tick();
  await new Promise((resolve) => setTimeout(resolve, 0));
  for (let i = 0; i < 24; i++) await tick();
  flushSync();
}

const popover = () => document.querySelector<HTMLElement>(".popover");
const term = () => document.querySelector<HTMLElement>(`[data-row="${ROW.path}"] .label .help`);

beforeEach(() => {
  serve();
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
});

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

describe("the help popover at /next", () => {
  it("opens on a parameter's name with the corpus entry and its manual link", async () => {
    app = mount(Frame, { target: document.body });
    await settle();
    expect(term()).toBeTruthy();
    expect(popover()).toBeNull();

    term()!.click();
    await settle();
    const shown = popover()!;
    expect(shown).toBeTruthy();
    expect(shown.textContent).toContain("Cell edge");
    expect(shown.textContent).toContain("A unit-cell edge length.");
    expect(shown.querySelector("a")!.getAttribute("href")).toBe(
      "https://example.invalid/docs/theory/peak-positions.html#lattice-metric-and-bragg-s-law");
    expect(term()!.getAttribute("aria-expanded")).toBe("true");
    expect(document.activeElement).toBe(shown);
  });

  it("closes on Esc before any other listener sees it, and gives focus back", async () => {
    app = mount(Frame, { target: document.body });
    await settle();
    const later = vi.fn();
    // a layer opened after the page, as every dialog at /next is, taking Esc on
    // the window in the capture phase
    window.addEventListener("keydown", later, true);
    try {
      term()!.click();
      await settle();
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      await settle();
      expect(popover()).toBeNull();
      expect(document.activeElement).toBe(term());
      expect(later).not.toHaveBeenCalled();

      // with nothing open, Esc is the layer's again
      document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
      expect(later).toHaveBeenCalledTimes(1);
    } finally {
      window.removeEventListener("keydown", later, true);
    }
  });
});
