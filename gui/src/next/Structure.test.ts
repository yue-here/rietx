// @vitest-environment jsdom
// The Structure graph at /next (WP-2218, rows 69-82): its title says what is
// drawn (milestone acceptance row 6), a slider value that moves the structure
// is drawn as a preview and an instrument value is not, the title states the
// ellipsoids' probability while they show, and the hover line reaches the
// status bar. What the canvas paints is a real browser's question
// (`tests/test_gui_layout_browser.py`).
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

// vitest runs from gui/, and jsdom's import.meta.url is not a file URL
const RUTILE = JSON.parse(readFileSync(resolve(process.cwd(), "../tests/data/gui/scene_cases.json"),
                                       "utf-8")).payloads.rutile;

const calls: Array<{ values: Record<string, number> | null | undefined }> = [];
let refuse: Error | null = null;
let broken: Error | null = null;
vi.mock("../api", async (original) => ({
  ...(await original<typeof import("../api")>()),
  api: {
    structure3d: (_phase: number, _tol?: number, _dis?: string, _c?: unknown, _l?: unknown,
                  values?: Record<string, number> | null) => {
      calls.push({ values });
      if (broken) return Promise.reject(broken);
      if (values && refuse) return Promise.reject(refuse);
      return Promise.resolve(structuredClone(RUTILE));
    },
  },
}));

import { structureReadout, structureValues } from "./structure";
import Structure from "./Structure.svelte";

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
  calls.length = 0;
  refuse = null;
  broken = null;
  document.body.innerHTML = "";
});

function show(props: Record<string, unknown>) {
  const target = document.createElement("div");
  document.body.append(target);
  app = mount(Structure, { target, props: { head: "n1", projectPath: "/p.rex", ...props } });
}

describe("the Structure graph", () => {
  it("says it draws the current values, and a structural slider value as a preview", async () => {
    show({});
    await settle(() => titleText() === "Structure at the current values");
    expect(calls.at(-1)!.values).toBeNull();
    unmount(app!);
    show({ values: { "phases.0.cell.a": 4.6 } });
    await settle(() => titleText().startsWith("Preview, not refined"));
    expect(calls.at(-1)!.values).toEqual({ "phases.0.cell.a": 4.6 });
  });

  it("draws an instrument value as the current values, since it moves no atom", async () => {
    show({ values: { "instrument.zero_shift": 0.01 } });
    await settle(() => titleText() === "Structure at the current values");
    expect(calls.every((c) => c.values == null)).toBe(true);
  });

  it("keeps the drawing and says so when the preview is refused", async () => {
    refuse = new Error("phases.0.cell.a: below its minimum");
    show({ values: { "phases.0.cell.a": -1 } });
    await settle(() => titleText().includes("Preview refused"));
    expect(document.querySelector(".gtitle")!.getAttribute("title")).toContain("below its minimum");
  });

  it("asks once for the working state when it fails under a refused preview", async () => {
    broken = new Error("the server failed");
    show({ values: { "phases.0.cell.a": 4.6 } });
    await settle(() => document.querySelector(".empty")?.textContent === "the server failed");
    await new Promise((done) => setTimeout(done, 100));
    // the refused preview, then one working-state request, and no loop
    expect(calls.map((c) => c.values)).toEqual([{ "phases.0.cell.a": 4.6 }, null]);
  });

  it("states the ellipsoids' probability in the title while they show", async () => {
    show({});
    await settle(() => !!document.querySelector(".key"));
    expect(titleText()).not.toContain("Ellipsoids at");
    const button = [...document.querySelectorAll("button")].find((b) => b.textContent === "Ellipsoids")!;
    button.click();
    flushSync();
    expect(titleText()).toContain("Ellipsoids at 50 %");
  });

  it("draws one colour-key switch per species", async () => {
    show({});
    await settle(() => !!document.querySelector(".key"));
    const keys = [...document.querySelectorAll(".key .entry")].map((b) => b.textContent!.trim());
    expect(keys).toEqual(expect.arrayContaining(["Ti", "O"]));
    const ti = [...document.querySelectorAll(".key .entry")].find((b) => b.textContent!.trim() === "Ti")!;
    expect(ti.getAttribute("aria-pressed")).toBe("true");
    (ti as HTMLButtonElement).click();
    flushSync();
    expect(ti.getAttribute("aria-pressed")).toBe("false");
  });
});

describe("the helpers", () => {
  it("splits a hover line into the status bar's label and value", () => {
    expect(structureReadout("Ti1 (Ti)  ·  (0.0000, 0.0000, 0.0000)")!.items[0])
      .toMatchObject({ label: "Ti1 (Ti)", value: "(0.0000, 0.0000, 0.0000)" });
    expect(structureReadout("Ti1–O1  1.948 Å")!.items[0])
      .toMatchObject({ label: "Ti1–O1", value: "1.948 Å" });
    expect(structureReadout("")).toBeNull();
  });

  it("keeps only the values that move the structure", () => {
    expect(structureValues({ "instrument.zero_shift": 0.1 })).toBeNull();
    expect(structureValues({ "instrument.zero_shift": 0.1, "phases.0.cell.a": 4 }))
      .toEqual({ "phases.0.cell.a": 4 });
    expect(structureValues(null)).toBeNull();
  });
});
