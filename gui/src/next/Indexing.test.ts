// @vitest-environment jsdom
// The peaks-and-indexing workflow's Pick step at /next (WP-2240): the picker's
// three options before a list exists, the list after it with its filter and
// tickboxes, a ticked row staying in a filtered list until the filter is chosen
// again (round 11b call 22), a row's click framing its line, and picking again
// saying first how many edits it replaces (round 11c call 29); the typed add
// row, the plot's edits through `edit`, and ⌘Z over them. Real clicks on
// the plot and the table are `tests/test_gui_layout_browser.py`'s.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { PeakRow, PeaksPayload } from "../lib/peaks";
import { workflow } from "../lib/workflows";

const row = (index: number, two_theta: number, over: Partial<PeakRow> = {}): PeakRow => ({
  index, two_theta, two_theta_esd: 0.001, d: 1.5406 / (2 * Math.sin((two_theta * Math.PI) / 360)),
  intensity: 100 * (index + 1), fwhm: 0.1, group: index, n_in_group: 1, chi2_red: 1.2,
  flags: [], origin: "fitted", usable: true, ...over,
});

const base = { pattern: { two_theta: [], y_obs: [], n_total: 0 }, flag_vocabulary: [],
  unusable_flags: ["duplicate", "excluded"] };
let stored: PeaksPayload;
const listed = (): PeaksPayload => ({ ...base, peaks: [
  row(0, 20.1), row(1, 31.8, { flags: ["duplicate"], usable: false }),
  row(2, 25.4, { origin: "manual" })],
  diagnostics: [{ level: "info", code: "PEAK_NOTE", message: "Eleven lines are weak." }],
  pick_options: { shoulders: true, flag_contamination: true, two_theta_range: null },
  api_call: "session.pick_peaks()" } as PeaksPayload);

const peaks = vi.fn(async () => stored);
const pickPeaks = vi.fn(async (_body: unknown) => (stored = listed()));
const flagPeak = vi.fn(async (index: number, body: { use_for_indexing?: boolean }) => {
  stored = { ...stored, peaks: stored.peaks!.map((p) => p.index !== index ? p
    : { ...p, usable: !!body.use_for_indexing, flags: body.use_for_indexing ? [] : ["excluded"] }),
    api_call: `session.set_peak_flags(${index}, use_for_indexing=${body.use_for_indexing ? "True" : "False"})` };
  return stored;
});

let before: PeaksPayload[] = [];
const keepBefore = () => before.push(stored);
const addPeak = vi.fn(async (tt: number) => {
  keepBefore();
  const n = stored.peaks!.length;
  return (stored = { ...stored, peaks: [...stored.peaks!, row(n, tt, { origin: "manual" })],
                     undo: before.length, redo: 0, api_call: `session.add_peak(${tt})` });
});
const movePeak = vi.fn(async (index: number, tt: number) => {
  keepBefore();
  return (stored = { ...stored, peaks: stored.peaks!.map((p) => p.index !== index ? p
    : { ...p, two_theta: tt + 0.004, origin: "edited" }), undo: before.length, redo: 0 });
});
const undoPeaks = vi.fn(async () => (stored = { ...before.pop()!, undo: before.length, redo: 1 }));
const refitGroup = vi.fn(async (group: number) => {
  keepBefore();
  return (stored = { ...stored, undo: before.length, redo: 0,
                     api_call: `session.refit_group(${group})` });
});

vi.mock("../api", () => ({
  ApiError: class extends Error {},
  api: {
    peaks: () => peaks(),
    pickPeaks: (b: unknown) => pickPeaks(b),
    flagPeak: (i: number, b: { use_for_indexing?: boolean }) => flagPeak(i, b),
    addPeak: (tt: number) => addPeak(tt),
    movePeak: (i: number, tt: number) => movePeak(i, tt),
    undoPeaks: () => undoPeaks(),
    refitGroup: (g: number) => refitGroup(g),
  },
}));

import Indexing from "./Indexing.svelte";

let app: any = null;
const said: string[] = [];
const framed: number[] = [];
let handed: PeaksPayload | null = null;
const fits: Array<{ groups: number[]; focused: number | null; total: number }> = [];
const steps: number[] = [];

async function settle() {
  for (let i = 0; i < 12; i++) await tick();
  flushSync();
}

const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const button = (words: string) => [...document.querySelectorAll<HTMLButtonElement>("button")]
  .find((b) => text(b) === words)!;
const rowsShown = () => [...document.querySelectorAll("table.lines tbody tr")]
  .map((tr) => text(tr.querySelectorAll("td")[1]));

async function boot(step = 0) {
  app = mount(Indexing, { target: document.body, props: {
    step, steps: workflow("index").steps!, say: (_k: string, t: string) => said.push(t),
    onpeaks: (p: PeaksPayload | null) => (handed = p),
    onframe: (r: PeakRow) => framed.push(r.index),
    onstep: (i: number) => steps.push(i),
    onfitgroups: (groups: number[], focused: number | null, total: number) =>
      fits.push({ groups, focused, total }),
  } });
  await settle();
}

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  said.length = 0;
  framed.length = 0;
  fits.length = 0;
  steps.length = 0;
  handed = null;
  before = [];
  vi.clearAllMocks();
});

describe("the Pick step", () => {
  it("offers the picker's three options and one Pick peaks before a list exists", async () => {
    stored = { ...base, peaks: null } as PeaksPayload;
    await boot();
    expect(text(document.querySelector("h3"))).toBe("Picking settings");
    expect([...document.querySelectorAll(".field .label")].map(text))
      .toEqual(["2θ range", "Shoulders", "Contamination"]);
    // a placeholder is a word, never a plausible number (gui/STYLE.md)
    expect([...document.querySelectorAll<HTMLInputElement>("input.num")].map((i) => i.placeholder))
      .toEqual(["default", "default"]);
    const pick = button("Pick peaks");
    expect(pick.closest(".foot")).not.toBeNull();
    expect(pick.classList.contains("ghost")).toBe(false);
    pick.click();
    await settle();
    expect(pickPeaks).toHaveBeenCalledWith({ shoulders: true, flag_contamination: true });
    expect(said).toContain("session.pick_peaks()");
    expect(handed!.peaks!.length).toBe(3);
  });

  it("lists every line in 2θ order, keeps a ticked row until the filter is chosen again, and frames a row", async () => {
    stored = listed();
    await boot();
    expect(rowsShown()).toEqual(["20.1000°", "25.4000°", "31.8000°"]);
    expect([...document.querySelectorAll(".segmented button")].map(text))
      .toEqual(["All 3", "Used 2", "Not used 1"]);
    // the notes are words from the corpus, and the person's line says so
    const notes = [...document.querySelectorAll("td.note")].map(text);
    expect(notes[2]).toContain("duplicate");
    button("Used 2").click();
    flushSync();
    expect(rowsShown()).toEqual(["20.1000°", "25.4000°"]);
    // unticking a used row in the Used filter keeps it in the list
    const box = document.querySelector<HTMLInputElement>("table.lines tbody tr input")!;
    box.checked = false;
    box.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(flagPeak).toHaveBeenCalledWith(0, { use_for_indexing: false });
    expect(rowsShown()).toEqual(["20.1000°", "25.4000°"]);
    expect(document.querySelector("table.lines tbody tr")!.classList.contains("off")).toBe(true);
    button("Used 1").click();
    flushSync();
    expect(rowsShown()).toEqual(["25.4000°"]);
    // a row's click frames its line and marks the row
    (document.querySelector("table.lines tbody tr td.num") as HTMLElement).click();
    flushSync();
    expect(framed).toEqual([2]);
    expect(document.querySelector("table.lines tbody tr")!.classList.contains("sel")).toBe(true);
  });

  it("says a ticked line was used over rietx's flags, and asks before picking again over edits", async () => {
    stored = listed();
    await boot();
    const off = [...document.querySelectorAll("table.lines tbody tr")][2];
    const box = off.querySelector<HTMLInputElement>("input")!;
    box.checked = true;
    box.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(flagPeak).toHaveBeenCalledWith(1, { use_for_indexing: true });
    expect(text([...document.querySelectorAll("td.note")][2])).toContain("used by you over");
    // the notes from the picker fold under their own disclosure
    expect(text(document.querySelector("details.notes summary"))).toBe("Notes from the picker (1)");
    // one line added by a person and one overruled: picking again asks first
    button("Pick peaks").click();
    flushSync();
    expect(pickPeaks).not.toHaveBeenCalled();
    expect(text(document.querySelector(".why"))).toContain("the 2 lines you added");
    button("Cancel").click();
    flushSync();
    expect(document.querySelector(".why")).toBeNull();
  });

  it("adds a typed line, follows a moved line, and takes both back with ⌘Z", async () => {
    stored = listed();
    await boot();
    // the typed add row at the table's foot (row 194): a word for a placeholder
    const add = document.querySelector<HTMLInputElement>("tr.add input")!;
    expect(add.placeholder).toBe("2θ");
    add.value = "28.5";
    add.dispatchEvent(new Event("input", { bubbles: true }));
    flushSync();
    button("Add").click();
    await settle();
    expect(addPeak).toHaveBeenCalledWith(28.5);
    expect(rowsShown()).toEqual(["20.1000°", "25.4000°", "28.5000°", "31.8000°"]);
    expect(add.value).toBe("");
    // a move from the plot chooses the line where it landed
    await app.edit({ kind: "move", index: 0, two_theta: 20.3 });
    await settle();
    expect(movePeak).toHaveBeenCalledWith(0, 20.3);
    expect(document.querySelector("tr.sel td.num")?.textContent).toContain("20.3040");
    expect(app.canUndo()).toBe(true);
    // ⌘Z over the plot steps back through the stored lists
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true }));
    await settle();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true }));
    await settle();
    expect(undoPeaks).toHaveBeenCalledTimes(2);
    expect(rowsShown()).toEqual(["20.1000°", "25.4000°", "31.8000°"]);
    // a text field keeps its own undo
    add.dispatchEvent(new KeyboardEvent("keydown", { key: "z", metaKey: true, bubbles: true }));
    await settle();
    expect(undoPeaks).toHaveBeenCalledTimes(2);
  });

});

describe("the Fit step", () => {
  const group = (g: number, lo: number, chi2_red: number) => ({
    group: g, two_theta: [lo, lo + 0.2], y_fit: [1, 1], y_env: [0, 0], delta: [0, 0],
    chi2_red, n_components: 1 });
  const fitted = (): PeaksPayload => {
    const p = listed();
    p.peaks![2].flags = ["unresolved_shoulder"];
    return { ...p, groups: [group(0, 20, 1.2), group(1, 31.7, 14.2), group(2, 25.3, 2)] };
  };

  it("lists the groups worth a look, hands the windows up, and chooses one by its row", async () => {
    stored = fitted();
    await boot(1);
    expect([...document.querySelectorAll(".segmented button")].map(text))
      .toEqual(["To look at 2", "All groups 3"]);
    // a χ²ᵣ over 10 or a flag that doubts the window fit (call 13), in 2θ order
    expect([...document.querySelectorAll("table.groups tbody tr")]
      .map((tr) => text(tr.querySelector("td")))).toEqual(["25.30–25.50°", "31.70–31.90°"]);
    expect(fits.at(-1)).toEqual({ groups: [2, 1], focused: null, total: 2 });
    (document.querySelectorAll("table.groups tbody tr")[1] as HTMLElement).click();
    flushSync();
    expect(fits.at(-1)).toEqual({ groups: [1], focused: 1, total: 2 });
    expect(document.querySelectorAll("table.groups tbody tr")[1].classList.contains("sel")).toBe(true);
    // choosing the filter again lets the chosen group go
    button("All groups 3").click();
    flushSync();
    expect(fits.at(-1)).toEqual({ groups: [0, 2, 1], focused: null, total: 3 });
    // Refit, from the graph's window, is one verb and one undo step
    expect(await app.refit(1)).toBe(true);
    await settle();
    expect(refitGroup).toHaveBeenCalledWith(1);
    expect(said).toContain("session.refit_group(1)");
    expect(app.canUndo()).toBe(true);
  });

  it("sends a person with no list back to Pick peaks", async () => {
    stored = { ...base, peaks: null } as PeaksPayload;
    await boot(1);
    button("Pick peaks first").click();
    expect(steps).toEqual([0]);
  });
});

describe("the Index and Judge steps", () => {
  it("leave this pane mounted and hidden, keeping the list's filter", async () => {
    stored = listed();
    await boot(2);
    expect(document.querySelector(".steppane")!.classList.contains("gone")).toBe(true);
    expect(workflow("index").steps!.every((s) => s.built)).toBe(true);
  });
});
