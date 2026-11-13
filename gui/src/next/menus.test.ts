// @vitest-environment jsdom
// The rebuilt page's axes and its structural menus (WP-2216, the third PR).
//
// The axes carry no titles: a muted hint by each axis's ticks, an explanation
// on hover, and a menu of that axis's choices on a click, kept in the
// project's `ui` keys (the maintainer's ruling of 2026-11-11, "Yes, build
// it"). The Parameters panel's structural edits live in a phase band's ⋯ and
// an atom row's context menu (WP-2214 rows 121-131), and Free and Fix in the
// filter row's ⋯. Where the hints sit and how they look is a real browser's
// question (`tests/test_gui_layout_browser.py`); this pins the wiring.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { pack } from "../test-curves";

const i32 = (a: number[]) => Int32Array.from(a);
let weighted = true;
const patchStructure = vi.fn(async (_s: unknown, _label?: string) => ({}));
const aniso = vi.fn(async (_p: string, _on: boolean) => ({}));
const patchParams = vi.fn(async (_b: unknown) => ({ parameters: ROWS, n_free: 1 }));

const STRUCTURE = {
  phases: [{ name: "fluorapatite", space_group: "P 63/m",
             atoms: [{ label: "Ca1", species: "Ca", x: { value: 0.333 }, y: { value: 0.667 }, z: { value: 0 } },
                     { label: "F1", species: "F", x: { value: 0 }, y: { value: 0 }, z: { value: 0.25 } }] }],
};
const row = (path: string, vary = false) => ({
  path, value: 1, esd: null, lo: -Infinity, hi: Infinity, vary, refinable: true, locked: false,
  tie: null, held: false, held_because: "", help_key: "", mode_fixed: false,
});
const ROWS = [row("phases.0.scale", true), row("phases.0.atoms.0.biso"), row("phases.0.atoms.1.biso"),
              row("instrument.zero_shift")];

vi.mock("../api", () => ({
  ApiError: class extends Error { code = ""; empty = false; busy = false; },
  api: {
    curves: async () => pack({ fit: true, weighted, stale: false, n_channels: 3, n_fitted: 3,
                               ticks: {}, tick_hkl: {} },
                             { two_theta: [10, 20, 30], y_obs: [5, 9, 4], kept: i32([0, 1, 2]),
                               fitted: i32([0, 1, 2]), y_calc: [5, 8, 4], delta: [0, 1, 0],
                               delta_raw: [0, 1, 0], cumulative_chi2: [0, 1, 1] }),
    params: async () => ({ parameters: ROWS, n_free: 1 }),
    patchParams: (b: unknown) => patchParams(b),
    structure: async () => ({ structure: STRUCTURE, sites: [
      { path: "phases.0.atoms.0", aniso: false }, { path: "phases.0.atoms.1", aniso: true }],
      symmetry: [] }),
    symmetry: async () => ({ letters: [] }),
    patchStructure: (s: unknown, label?: string) => patchStructure(s, label),
    aniso: (p: string, on: boolean) => aniso(p, on),
  },
}));

import Params from "./Params.svelte";
import Pattern from "./Pattern.svelte";

let app: ReturnType<typeof mount> | null = null;

async function settle() {
  for (let i = 0; i < 24; i++) await tick();
  await new Promise((r) => requestAnimationFrame(() => r(null)));
  for (let i = 0; i < 4; i++) await tick();
  flushSync();
}

const named = (name: string) => [...document.querySelectorAll<HTMLElement>("button, [role=menuitem], [role=menuitemradio], [role=menuitemcheckbox]")]
  .find((b) => (b.getAttribute("aria-label") ?? b.textContent ?? "").trim() === name);
const menuLabels = () => [...document.querySelectorAll(".rx-menu [role^=menuitem]")]
  .map((b) => b.textContent!.trim());

beforeEach(() => {
  weighted = true;
  patchStructure.mockClear();
  aniso.mockClear();
  patchParams.mockClear();
});

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

describe("the Pattern graph's axes", () => {
  const onui = vi.fn();
  async function draw(ui: Record<string, unknown> | null = null) {
    onui.mockClear();
    app = mount(Pattern, { target: document.body,
      props: { result: { statistics: { rwp: 0.1, gof: 1.2 } }, plotKey: 1, projectPath: "/p.rex", ui, onui } });
    // the chart module is a chunk fetched on first draw, slower under the
    // whole suite's load than alone: wait for the axes it places
    for (let i = 0; i < 50 && !document.querySelector("button.axis"); i++) await settle();
  }

  it("draws no Intensity control on the title line", async () => {
    await draw();
    expect(document.querySelector(".ghead")!.textContent).not.toMatch(/Intensity|Square root/);
  });

  it("hints each axis's unit, the intensity's on square root at first", async () => {
    await draw();
    const hints = [...document.querySelectorAll(".hint")].map((h) => h.textContent!.trim());
    expect(hints).toEqual(["√", "σ", "° 2θ"]);
  });

  it("opens the intensity's three scales on a click and keeps the choice with the project", async () => {
    await draw();
    named("Intensity scale")!.click();
    flushSync();
    expect(menuLabels()).toEqual(["Linear", "Square root", "Log"]);
    named("Log")!.click();
    flushSync();
    expect(onui).toHaveBeenCalledWith({ intensity_scale: "log" });
    expect(document.querySelector(".rx-menu")).toBeNull();
    expect(document.querySelector("button.axis .hint")!.textContent).toBe("log");
  });

  it("offers the three differences today's page draws, and hints counts for Δ", async () => {
    await draw();
    named("Difference axis")!.click();
    flushSync();
    expect(menuLabels()).toEqual(["Difference in esd (Δ/σ)", "Difference in counts (Δ)", "Cumulative χ²"]);
    named("Difference in counts (Δ)")!.click();
    flushSync();
    expect(onui).toHaveBeenCalledWith({ difference: "delta" });
    expect(document.querySelectorAll(".hint")[1].textContent!.trim()).toBe("counts");
  });

  it("opens on the project's remembered choices", async () => {
    await draw({ intensity_scale: "linear", difference: "cumulative" });
    const hints = [...document.querySelectorAll(".hint")].map((h) => h.textContent!.trim());
    expect(hints).toEqual(["", "Σχ²", "° 2θ"]);
  });

  it("says where σ comes from on focus, off the route's flag", async () => {
    await draw();
    named("Difference axis")!.dispatchEvent(new FocusEvent("focus"));
    flushSync();
    expect(document.querySelector("#axis-tip")!.textContent).toContain("σ from the file.");
    unmount(app!);
    weighted = false;
    await draw();
    named("Difference axis")!.dispatchEvent(new FocusEvent("focus"));
    flushSync();
    expect(document.querySelector("#axis-tip")!.textContent).toContain("σ from Poisson counting statistics.");
  });
});

describe("the Parameters panel's menus", () => {
  const onmoved = vi.fn();
  async function open() {
    onmoved.mockClear();
    app = mount(Params, { target: document.body, props: { head: "n1", onmoved } });
    await settle();
  }

  it("holds Free and Fix in the filter row's ⋯", async () => {
    await open();
    expect(named("Free 2")).toBeUndefined();
    named("Free or fix")!.click();
    flushSync();
    expect(menuLabels()).toEqual(["Free all 3", "Fix all 1"]);
    named("Fix all 1")!.click();
    for (let i = 0; i < 4; i++) await tick();
    expect(patchParams).toHaveBeenCalledWith({ vary: { "*": false } });
  });

  it("puts the structural edits in the phase band's ⋯", async () => {
    await open();
    named("fluorapatite actions")!.click();
    flushSync();
    expect(menuLabels()).toEqual(["Rename…", "Change space group…", "Add atom…", "Replace from CIF…"]);
    // only a phase band carries one
    expect(document.querySelectorAll(".band button.ib").length).toBe(1);
  });

  it("renames a phase through one whole-model edit", async () => {
    await open();
    named("fluorapatite actions")!.click();
    flushSync();
    named("Rename…")!.click();
    flushSync();
    const input = document.querySelector<HTMLInputElement>("form.ask input")!;
    input.value = "apatite";
    input.dispatchEvent(new Event("input"));
    document.querySelector<HTMLFormElement>("form.ask")!.requestSubmit();
    for (let i = 0; i < 8; i++) await tick();
    expect(patchStructure).toHaveBeenCalledTimes(1);
    expect((patchStructure.mock.calls[0][0] as any).phases[0].name).toBe("apatite");
    expect(onmoved).toHaveBeenCalled();
  });

  it("opens an atom's menu on right-click, with its ADP state ticked", async () => {
    await open();
    const rows = document.querySelectorAll<HTMLTableRowElement>("tr[data-atom]");
    rows[1].dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 50, clientY: 60 }));
    flushSync();
    expect(menuLabels()).toEqual(["Rename…", "Change species…", "Anisotropic ADPs", "Delete"]);
    expect(named("Anisotropic ADPs")!.getAttribute("aria-checked")).toBe("true");
    named("Anisotropic ADPs")!.click();
    for (let i = 0; i < 4; i++) await tick();
    expect(aniso).toHaveBeenCalledWith("phases.0.atoms.1", false);
  });

  it("deletes an atom at once", async () => {
    await open();
    document.querySelector("tr[data-atom]")!.dispatchEvent(
      new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 5, clientY: 5 }));
    flushSync();
    named("Delete")!.click();
    for (let i = 0; i < 8; i++) await tick();
    const sent = patchStructure.mock.calls[0][0] as any;
    expect(sent.phases[0].atoms.map((a: any) => a.label)).toEqual(["F1"]);
  });

  it("waits while edits are pending, and says why", async () => {
    await open();
    document.querySelector<HTMLButtonElement>("button.ink")!.click();
    flushSync();
    const editor = document.querySelector<HTMLInputElement>("input.editor")!;
    editor.value = "3";
    editor.dispatchEvent(new Event("input"));
    editor.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    flushSync();
    named("fluorapatite actions")!.click();
    flushSync();
    const rename = named("Rename…") as HTMLButtonElement;
    expect(rename.disabled).toBe(true);
    expect(rename.title).toBe("Apply or revert the pending edits first");
  });
});
