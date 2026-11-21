// @vitest-environment jsdom
// The Plan tab at /next (WP-2231): the plan reads as a recipe, one block per
// stage with its Free and Fix rows of named chips, then the closing stage and
// what no stage frees. An edit is one pending edit in the bar, and Apply stores
// it. A real drag and the no-layout-shift rule are a real browser's question
// (`tests/test_gui_layout_browser.py`).
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

const STAGES = [
  { name: "scale_bkg", turn_on: ["phases.*.scale", "instrument.background.*"], turn_off: [], max_iter: 100 },
  { name: "cell", turn_on: ["phases.*.cell.*"], turn_off: ["instrument.zero_shift"], max_iter: 100 },
];
const step = (frees: string[], n: number, rwp: number | null, fixes: string[] = []) =>
  ({ frees, fixes, already: [], held: [], n_matched: frees.length, n_free: n, rwp });
const RESOLVE = {
  stages: [step(["phases.0.scale", "instrument.background.c0"], 2, 0.2104),
           step(["phases.0.cell.a"], 3, 0.0928, [])],
  closing: { name: "closing", window_area_tol: 0.001, fixes: [], rwp: 0.0911 },
  set_aside: [], never_freed: ["instrument.profile.u", "instrument.profile.v", "instrument.zero_shift"],
};
const ROWS = [
  { path: "phases.0.scale", help_key: "phases.*.scale", refinable: true },
  { path: "phases.0.cell.a", help_key: "phases.*.cell.a", refinable: true },
  { path: "phases.0.cell.c", help_key: "phases.*.cell.c", refinable: true },
  { path: "instrument.profile.u", help_key: "instrument.profile.u", refinable: true },
  { path: "instrument.profile.v", help_key: "instrument.profile.v", refinable: true },
  { path: "instrument.zero_shift", help_key: "instrument.zero_shift", refinable: true },
];
const putPlan = vi.fn(async (body: any) => ({ plan: { ...body.plan }, preset: null }));

vi.mock("../api", () => ({
  ApiError: class extends Error { code = ""; empty = false; busy = false; },
  api: {
    plan: async () => ({ plan: { stages: STAGES, correlation_guard: 0.98 }, preset: "mccusker_default" }),
    plans: async () => ({ plans: [{ name: "mccusker_default", title: "McCusker default",
                                    description: "", modes: ["rietveld"] }] }),
    planResolve: async () => RESOLVE,
    params: async () => ({ parameters: ROWS, n_free: 0 }),
    putPlan: (body: any) => putPlan(body),
  },
}));

import Plan from "./Plan.svelte";

let app: any = null;

async function settle() {
  for (let i = 0; i < 24; i++) await tick();
  flushSync();
}

const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  putPlan.mockClear();
});

describe("the Plan tab", () => {
  it("reads top to bottom: each stage's frees and fixes, the closing stage, then what no stage frees", async () => {
    const pending = vi.fn();
    app = mount(Plan, { target: document.body, props: { onpending: pending } });
    await settle();
    const blocks = [...document.querySelectorAll(".stg")];
    expect(blocks).toHaveLength(4);
    expect(text(document.querySelector(".mbtn.name"))).toBe("McCusker default");
    // stage 1: its number, its name, its Rwp, and a chip per glob
    expect(blocks[0].querySelector(".badge")!.textContent).toBe("1");
    expect((blocks[0].querySelector("input.sn") as HTMLInputElement).value).toBe("scale_bkg");
    expect(text(blocks[0].querySelector(".facts"))).toBe("2 free Rwp 21.04 %");
    expect([...blocks[0].querySelectorAll(".pt")].map((c) => c.getAttribute("title")))
      .toEqual(["phases.*.scale", "instrument.background.*"]);
    expect(text(blocks[0].querySelectorAll(".pt")[1])).toBe("Background");
    // stage 2 fixes the zero shift, after it frees the cell; the fix reaches
    // nothing free there, so the chip says so
    const fixRow = blocks[1].querySelectorAll(".stg2")[1];
    expect(text(fixRow.querySelector(".verb"))).toBe("Fix");
    expect(fixRow.querySelector(".pt")!.classList.contains("idle")).toBe(true);
    expect(text(blocks[2])).toContain("Everything above");
    expect(text(blocks[3])).toContain("Never freed");
    expect(text(blocks[3])).toContain("instrument.zero_shift");
    expect(pending).toHaveBeenLastCalledWith(false);
  });

  it("makes an edit one pending edit, which the bar's Apply stores", async () => {
    const pending = vi.fn();
    app = mount(Plan, { target: document.body, props: { onpending: pending } });
    await settle();
    (document.querySelectorAll(".pt .x")[0] as HTMLButtonElement).click();
    await settle();
    expect(pending).toHaveBeenLastCalledWith(true);
    // an edited stage, and every stage below it, has no facts
    const blocks = [...document.querySelectorAll(".stg")];
    expect(text(blocks[0].querySelector(".facts"))).toBe("not applied");
    expect(text(blocks[3])).toContain("not applied");
    expect(await app.save()).toBe(true);
    expect(putPlan).toHaveBeenCalledTimes(1);
    expect(putPlan.mock.calls[0][0].plan.stages[0].turn_on).toEqual(["instrument.background.*"]);
  });

  it("adds from the grouped picker and undoes it", async () => {
    app = mount(Plan, { target: document.body, props: {} });
    await settle();
    (document.querySelector('[data-add="1"]') as HTMLButtonElement).click();
    await settle();
    const dialog = document.querySelector('[role="dialog"]')!;
    expect(text(dialog)).toContain("Groups");
    const cell = [...dialog.querySelectorAll("button.op")].find((b) => text(b).startsWith("Cell"))!;
    expect((cell as HTMLButtonElement).disabled).toBe(true);
    expect(text(cell)).toContain("in this stage");
    const shift = [...dialog.querySelectorAll("button.op")].find((b) => b.getAttribute("title") === "instrument.zero_shift")!;
    (shift as HTMLButtonElement).click();
    await settle();
    const chips = [...document.querySelectorAll('.stg[data-stage="1"] .stg2')[0].querySelectorAll(".pt")];
    expect(chips.map((c) => c.getAttribute("title"))).toEqual(["phases.*.cell.*", "instrument.zero_shift"]);
    app.undo();
    await settle();
    expect(document.querySelectorAll('.stg[data-stage="1"] .stg2')[0].querySelectorAll(".pt")).toHaveLength(1);
  });
});
