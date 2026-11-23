// @vitest-environment jsdom
// Another project opened in the same window at /next (WP-2242). Node ids
// repeat across projects (`n0000`, `n0001`, …), so the next project's head can
// be this one's: both fixtures stand at `n0001`, and a panel that reloads on
// `head` alone keeps the last project's rows. Asserted through the requests,
// as `App.test.ts` asserts today's page; what each panel draws is the browser
// check's (`tests/test_gui_browser.py`).
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/stream", async (original) => ({
  ...(await original<typeof import("../lib/stream")>()),
  follow: () => () => {},
}));

import Frame from "./Frame.svelte";

const A = { path: "/tmp/fap.rex", name: "fap", head: "n0001", n_nodes: 2, n_phases: 1,
            doc: { mode: "rietveld", ui: {}, plan: null, two_theta_limits: null,
                   excluded_regions: [] },
            data: { filename: "FAP.XRA", n_points: 10, has_sigma: true } };
const B = { ...A, path: "/tmp/nac.rex", name: "nac",
            data: { ...A.data, filename: "nac.fxye" } };
const RECENT = [
  { path: A.path, name: "fap.rex", opened_utc: "2026-11-22T10:00:00+00:00", missing: false },
  { path: B.path, name: "nac.rex", opened_utc: "2026-11-21T10:00:00+00:00", missing: false },
];
const IDLE = { state: "idle", run: {}, project: A.path, head: "n0001" };

/** Routes an open need not read again: the session's or the person's, and the
 *  document the open's own answer carries. */
const SESSION = new Set(["/api/settings", "/api/version", "/api/capabilities", "/api/help",
                         "/api/recent", "/api/examples", "/api/events", "/api/run/state",
                         "/api/project"]);

interface Call { method: string; path: string }
let calls: Call[] = [];

/** A stub server: the routes the frame needs answered, and a 409 "nothing to
 *  show" for every other read, which each panel draws as its empty state. */
function serve() {
  const routes: Record<string, () => unknown> = {
    "/api/settings": () => ({ ui: {} }),
    "/api/version": () => ({ package_version: "9.9.9" }),
    "/api/capabilities": () => ({}),
    "/api/help": () => ({ docs_url: "https://example.invalid/docs/" }),
    "/api/project": () => A,
    "/api/project/open": () => B,
    "/api/run/state": () => IDLE,
    "/api/recent": () => ({ recent: RECENT }),
    "/api/examples": () => ({ examples: [] }),
    "/api/events": () => ({ events: [], next: 0, oldest: 1, ...IDLE }),
  };
  vi.stubGlobal("fetch", vi.fn(async (input: any, init: any = {}) => {
    const path = String(input).split("?")[0];
    calls.push({ method: init.method ?? "GET", path });
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

const byLabel = (label: string) =>
  document.querySelector<HTMLButtonElement>(`button[aria-label="${label}"]`);
const tab = (name: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[role="tab"]')]
    .find((b) => b.textContent!.replace(/\s+/g, " ").trim().replace(/\d+$/, "") === name);
const item = (name: string) =>
  [...document.querySelectorAll<HTMLButtonElement>('[role="menuitem"]')]
    .find((b) => b.textContent!.trim().startsWith(name));

/** Open B from the File menu's Open recent, as a person does. */
async function openB() {
  document.querySelector<HTMLButtonElement>("header .proj button")!.click();
  await settle();
  item("Open recent")!.click();
  await settle();
  item("nac")!.click();
  await settle();
}

const TOUR = ["Peaks", "Background", "Structure", "Pattern",
              "Interactive", "Plan", "Text", "Parameters", "Console", "History"];

async function tour() {
  for (const name of TOUR) {
    tab(name)!.click();
    await settle();
  }
}

/** How often each project route was read, from `calls[from]` on. */
function reads(from = 0): Map<string, number> {
  const out = new Map<string, number>();
  for (const c of calls.slice(from)) {
    if (c.method !== "GET" || SESSION.has(c.path)) continue;
    out.set(c.path, (out.get(c.path) ?? 0) + 1);
  }
  return out;
}

beforeEach(() => {
  calls = [];
  serve();
  vi.stubGlobal("matchMedia", () => ({ matches: false, addEventListener() {}, removeEventListener() {} }));
});

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  vi.unstubAllGlobals();
});

describe("another project opened in the same window (WP-2242)", () => {
  it("reads every project route again, as often as it did for the first", async () => {
    app = mount(Frame, { target: document.body });
    await settle();
    byLabel("Show the console")!.click();
    await settle();
    await tour();
    const first = reads();
    const mark = calls.length;

    await openB();
    expect(calls.some((c) => c.path === "/api/project/open")).toBe(true);
    await tour();
    const second = reads(mark);
    const short = [...first].filter(([path, n]) => (second.get(path) ?? 0) < n)
      .map(([path, n]) => `${path} ${second.get(path) ?? 0} of ${n}`);
    expect(short).toEqual([]);
  });

  it("reads the shown panels again with no tab touched", async () => {
    // the tour above remounts each graph as it is chosen, which would read
    // again whatever the open did; here only the open happens
    app = mount(Frame, { target: document.body });
    await settle();
    byLabel("Show the console")!.click();
    await settle();
    tab("History")!.click();
    await settle();
    const before = reads();
    const mark = calls.length;

    await openB();
    const after = reads(mark);
    const missed = [...before.keys()].filter((path) => !after.has(path));
    expect(missed).toEqual([]);
  });
});
