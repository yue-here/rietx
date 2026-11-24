// @vitest-environment jsdom
// The series workflow's Patterns and Run steps at /next (WP-2243): the list
// with its count and span, a typed coordinate and Sort by sending the whole
// list, Order, the foot's words, and the Run step's table filling from the
// run's own events. Real clicks are `tests/test_gui_layout_browser.py`'s.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { SeriesPattern, SeriesSetup } from "../lib/series";
import type { EngineEvent, RunState } from "../lib/stream";
import { workflow } from "../lib/workflows";

const pattern = (label: string, x: number | null, lo = 5, hi = 50): SeriesPattern => ({
  upload: `tok-${label}`, filename: `${label}.xye`, label, x, reader: "xye",
  reader_options: {}, n_points: 22003, two_theta_range: [lo, hi], has_sigma: true,
});

let stored: SeriesSetup;
const setupOf = (patterns: SeriesPattern[], over: Partial<SeriesSetup["settings"]> = {}): SeriesSetup => ({
  patterns, n_patterns: patterns.length,
  settings: { carry: ["*"], refit: "single", direction: "forward", x_label: "T (K)", ...over },
  choices: { refit: ["single", "stages"], direction: ["forward", "backward", "both"] },
  carry_help: "", defaults: { carry: ["*"], refit: "single", direction: "forward", x_label: "index" },
  protocol: { mode: "rietveld", plan: "mccusker_default", n_stages: 5 },
  has_x: patterns.some((p) => p.x !== null), sigma_mixed: false, has_result: false, running: false,
});

const series = vi.fn(async () => stored);
const putSeries = vi.fn(async (body: any) => {
  const byToken = new Map(stored.patterns.map((p) => [p.upload, p]));
  const patterns = body.patterns
    ? body.patterns.map((m: any) => ({ ...byToken.get(m.upload)!, x: m.x ?? null }))
    : stored.patterns;
  const { patterns: _p, ...settings } = body;
  return (stored = setupOf(patterns, { ...stored.settings, ...settings }));
});
const seriesResult = vi.fn(async (): Promise<any> => { throw new Error("no series has completed"); });

vi.mock("../api", () => ({
  ApiError: class extends Error {},
  api: {
    series: () => series(),
    putSeries: (b: unknown) => putSeries(b),
    seriesResult: () => seriesResult(),
    uploadFile: vi.fn(),
  },
}));

import Series from "./Series.svelte";

let app: any = null;
const steps: number[] = [];
const runs: Array<[Record<string, unknown>, string]> = [];

async function settle() {
  for (let i = 0; i < 12; i++) await tick();
  flushSync();
}

const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const button = (words: string) => [...document.querySelectorAll<HTMLButtonElement>("button")]
  .find((b) => text(b) === words)!;
const cells = (row: number) => [...document.querySelectorAll("table.rows tbody tr")[row]
  .querySelectorAll("td")].map(text);

async function boot(step = 0, run: RunState | null = null) {
  app = mount(Series, { target: document.body, props: {
    step, steps: workflow("series").steps!, busy: run?.state === "running", run,
    onstep: (i: number) => steps.push(i),
    onrun: async (body: Record<string, unknown>, t: string) => { runs.push([body, t]); },
  } });
  await settle();
}

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  steps.length = 0;
  runs.length = 0;
  vi.clearAllMocks();
});

describe("the Patterns step", () => {
  it("says it has no patterns, and that a run needs two", async () => {
    stored = setupOf([]);
    await boot();
    expect(text(document.querySelector("h3"))).toBe("Patterns");
    expect(text(document.querySelector(".empty"))).toBe("No patterns yet.");
    expect(button("Add files…").disabled).toBe(false);
    expect(text(document.querySelector(".foot .muted"))).toBe("Needs two patterns");
    expect(button("Run series").disabled).toBe(true);
  });

  it("lists the files with their count and span, and sorts by the typed coordinate", async () => {
    stored = setupOf([pattern("T300", 300, 5, 49.9), pattern("T100", null, 4.5, 50)]);
    await boot();
    expect(text(document.querySelector("h3"))).toBe("Patterns2 files · 4.5–50.0° 2θ");
    expect(cells(0)).toEqual(["1", "T300.xye", "", "22,003", ""]);
    // one member has no coordinate yet, and it is last: nothing to sort
    expect(button("Sort by T").disabled).toBe(true);
    const box = document.querySelectorAll<HTMLInputElement>("input.coord")[1];
    expect(box.getAttribute("aria-label")).toBe("T (K) of T100");
    box.value = "100";
    box.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(putSeries).toHaveBeenLastCalledWith({ patterns: [
      { upload: "tok-T300", label: "T300", x: 300 }, { upload: "tok-T100", label: "T100", x: 100 }] });
    button("Sort by T").click();
    await settle();
    expect(putSeries.mock.calls.at(-1)![0].patterns.map((p: any) => p.upload))
      .toEqual(["tok-T100", "tok-T300"]);
    expect(button("Sort by T").disabled).toBe(true);
  });

  it("sends a removal, an order and the carried globs, each as one PUT", async () => {
    stored = setupOf([pattern("a", 1), pattern("b", 2), pattern("c", 3)]);
    await boot();
    expect(text(document.querySelector(".foot .muted"))).toBe("3 patterns · one walk");
    document.querySelector<HTMLButtonElement>('button[aria-label="Remove b"]')!.click();
    await settle();
    expect(putSeries.mock.calls.at(-1)![0].patterns.map((p: any) => p.label)).toEqual(["a", "c"]);
    expect([...document.querySelectorAll(".segmented button")].map(text))
      .toEqual(["First to last", "Last to first", "Both, and compare"]);
    button("Both, and compare").click();
    await settle();
    expect(putSeries.mock.calls.at(-1)![0].direction).toBe("both");
    expect(text(document.querySelector(".foot .muted"))).toBe("2 patterns · two walks");
    const carry = document.querySelector<HTMLInputElement>("input.carry")!;
    carry.value = "phases.*, instrument.background.*";
    carry.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(putSeries.mock.calls.at(-1)![0].carry).toEqual(["phases.*", "instrument.background.*"]);
  });

  it("keeps a coordinate typed while an earlier PUT is on the wire", async () => {
    stored = setupOf([pattern("a", null), pattern("b", null), pattern("c", null)]);
    await boot();
    // the first PUT's answer waits until the second edit is typed
    let release!: () => void;
    const held = new Promise<void>((r) => (release = r));
    putSeries.mockImplementationOnce(async (body: any) => {
      await held;
      const byToken = new Map(stored.patterns.map((p) => [p.upload, p]));
      return (stored = setupOf(body.patterns.map((m: any) => ({ ...byToken.get(m.upload)!, x: m.x ?? null })),
                               stored.settings));
    });
    const box = (i: number) => document.querySelectorAll<HTMLInputElement>("input.coord")[i];
    box(0).value = "300";
    box(0).dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    box(1).value = "400";
    box(1).dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    release();
    await settle();
    box(2).value = "500";
    box(2).dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(putSeries.mock.calls.at(-1)![0].patterns.map((p: any) => p.x)).toEqual([300, 400, 500]);
    expect([...document.querySelectorAll<HTMLInputElement>("input.coord")].map((b) => b.value))
      .toEqual(["300", "400", "500"]);
  });

  it("fills Run series while First fit is not built, and First fit once it is", async () => {
    stored = setupOf([pattern("a", 1), pattern("b", 2)]);
    await boot();
    const first = button("First fit");
    expect(first.closest(".foot")).not.toBeNull();
    expect(first.classList.contains("ghost")).toBe(true);
    expect(button("Run series").classList.contains("ghost")).toBe(false);
    unmount(app);
    document.body.innerHTML = "";
    const built = workflow("series").steps!.map((s, i) => (i === 1 ? { ...s, built: true } : s));
    app = mount(Series, { target: document.body, props: {
      step: 0, steps: built, onstep: (i: number) => steps.push(i),
      onrun: async (body: Record<string, unknown>, t: string) => { runs.push([body, t]); } } });
    await settle();
    expect(button("First fit").classList.contains("ghost")).toBe(false);
    expect(button("Run series").classList.contains("ghost")).toBe(true);
    button("Run series").click();
    await settle();
    expect(steps).toEqual([2]);
    expect(runs[0][0]).toEqual({ kind: "series" });
    expect(runs[0][1]).toContain('rx.refine_sequential(patterns, structure, instrument, x=[…], x_label="T (K)"');
  });
});

describe("the Run step", () => {
  const ev = (seq: number, kind: string, index: number, pass: string, data: Record<string, unknown> = {}): EngineEvent =>
    ({ seq, kind, t: seq, data: { series_index: index, series_label: `T${index}`, series_n: 2,
                                   series_pass: pass, ...data } });

  it("says it has not run, with Run series in its foot", async () => {
    stored = setupOf([pattern("a", 1), pattern("b", 2)]);
    await boot(2);
    expect(text(document.querySelector(".empty"))).toBe("Not run yet.");
    expect(button("Run series").closest(".foot")).not.toBeNull();
  });

  it("fills the table as fits land, the pattern being fitted marked, with Stop", async () => {
    stored = setupOf([pattern("T0", 10), pattern("T1", 20)], { direction: "both" });
    await boot(2, { state: "running", run: { kind: "series" } } as RunState);
    app.event(ev(1, "fit_start", 0, "forward"));
    app.event(ev(2, "fit_end", 0, "forward", { rwp: 0.2241, gof: 1.9, status: "converged" }));
    app.event(ev(3, "fit_start", 1, "forward"));
    flushSync();
    // counted per walk, as the Console counts: the pattern's place in the series
    expect(text(document.querySelector(".status"))).toBe("Fitting T1 · 20 · first walk · 2 of 2");
    expect([...document.querySelectorAll(".rows th")].map(text))
      .toEqual(["#", "Pattern", "T (K)", "Rwp (%)", "Started from", "Second walk Rwp (%)"]);
    expect(cells(0)).toEqual(["1", "T0", "10", "22.41", "model", ""]);
    expect(cells(1)).toEqual(["2", "T1", "20", "…", "", ""]);
    expect(document.querySelector(".gauge")!.getAttribute("aria-valuenow")).toBe("25");
    expect(button("Stop").title).toBe("Patterns already fitted keep their results");
    // between two fits the line still names the pattern that started last
    app.event(ev(4, "fit_end", 1, "forward", { rwp: 0.2302, gof: 2.0, status: "converged" }));
    flushSync();
    expect(text(document.querySelector(".status"))).toBe("Fitting T1 · 20 · first walk · 2 of 2");
    // the second walk, backward from the last pattern, prints its Rwp
    app.event(ev(5, "fit_start", 1, "backward"));
    app.event(ev(6, "fit_end", 1, "backward", { rwp: 0.2299, gof: 2.0, status: "converged" }));
    app.event(ev(7, "fit_start", 0, "backward"));
    flushSync();
    expect(text(document.querySelector(".status"))).toBe("Fitting T0 · 10 · second walk · 1 of 2");
    expect(cells(1)).toEqual(["2", "T1", "20", "23.02", "previous", "22.99"]);
    expect(cells(0)[5]).toBe("…");
  });
});

describe("the Results step", () => {
  const entry = (index: number, rwp: number, diagnostics: any[] = []) => ({
    index, label: `T${index}`, x: 10 * (index + 1), status: "converged",
    statistics: { rwp, gof: 1.9 }, n_iterations: 8, reseeded: false, rwp_warm: null,
    rung: index ? "warm" : "cold", rungs_tried: [], node_id: null, tree_id: null, diagnostics,
  });

  it("says it has not run, with Run series in its foot", async () => {
    stored = setupOf([pattern("T0", 10), pattern("T1", 20)]);
    await boot(3);
    expect(text(document.querySelector(".empty"))).toBe("Not run yet.");
    expect(button("Run series").closest(".foot")).not.toBeNull();
  });

  it("reads the record: the summary, a row per pattern, the values and warnings at the selected one", async () => {
    stored = { ...setupOf([pattern("T0", 10), pattern("T1", 20)]), has_result: true };
    seriesResult.mockImplementationOnce(async () => ({
      result: {
        entries: [entry(0, 0.0419), entry(1, 0.0434, [{ level: "warning", code: "BOUND_HIT", message: "a hit its bound" }])],
        diagnostics: [],
        steps: [{ path: "phases.0.cell.a", labels: ["T0", "T1"], indices: [0, 1], step: 0.002,
                  size_esd: 4.26, cold_ratio: null }],
        direction_gaps: null,
        code_counts: [{ code: "BOUND_HIT", path: "phases.0.cell.a", count: 1, n_patterns: 2, level: "warning" }],
        phase_names: ["LaB6"], atom_labels: [[]],
      },
      trajectories: [{ path: "phases.0.cell.a", x: [10, 20], x_label: "T (K)", value: [4.15692, 4.15901],
                       stderr: [0.00002, 0.00003], labels: ["T0", "T1"], backward: null,
                       n_sigma: null, gap_at: null }],
      has_backward: false,
    }) as any);
    await boot(3);
    expect([...document.querySelectorAll(".summary dt")].map(text)).toEqual(["Converged", "Largest step"]);
    expect([...document.querySelectorAll(".summary dd")].map(text))
      .toEqual(["2 of 2", "LaB6 cell.a · 10 → 20 · 4.3 esd"]);
    expect(cells(0)).toEqual(["1", "10", "4.19", "1.90", "model", ""]);
    expect(cells(1)).toEqual(["2", "20", "4.34", "1.90", "previous", "1"]);
    const values = () => [...document.querySelectorAll(".values tbody tr")]
      .map((r) => [...r.querySelectorAll("td")].map(text).join(" "));
    expect(values()).toEqual(["Fit", "Rwp (%) 4.19", "GoF 1.90", "LaB6", "cell.a 4.15692"]);
    expect(text(document.querySelector(".body p.muted:not(.empty)"))).toBe("No warnings.");
    // a row click selects its pattern: its values and its warnings follow
    (document.querySelectorAll("table.rows tbody tr")[1] as HTMLElement).click();
    flushSync();
    expect(values()).toContain("cell.a 4.15901");
    expect(text(document.querySelector(".body .dg"))).toBe("BOUND_HIT a hit its bound");
    expect(text(document.querySelector("details.notes summary"))).toBe("Warnings across the series");
  });
});
