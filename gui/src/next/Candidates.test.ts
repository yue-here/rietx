// @vitest-environment jsdom
// The peaks-and-indexing workflow's Index step at /next (WP-2240 task 7): the
// short form committed whole to the project document (WP-1045), the run's
// progress with Stop, the coverage line said whatever the search found
// (WP-1042, round 11 call 6), and the candidate table whose row draws the
// cell's lines on the Pattern graph (call 9). Real clicks are
// `tests/test_gui_layout_browser.py`'s.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { Candidate } from "../lib/peaks";

const indexing = () => ({
  search: { systems: null, centrings: null, min_d_axis: 2, max_d_axis: 25, min_volume: 20,
    max_volume: null, n_unindexed: 2, n_search_lines: 20, k_sigma: 3, shift_allowance_deg: 0.1,
    shift_template: null, budget_seconds: 30, total_budget_seconds: null, preset: null,
    max_candidates: 12, seed: 0, prior_cells: null, prior_spacegroups: null },
  engines: null, validate_candidates: true, check_top: null, formula: null, temperature: null,
});
const capabilities = {
  crystal_systems: ["cubic", "hexagonal", "tetragonal"],
  indexing_engines: [{ name: "dichotomy", description: "" }, { name: "svd", description: "" }],
  search_presets: [{ name: "full", default: false, total_budget_seconds: null },
                   { name: "quick", default: true, total_budget_seconds: 120 }],
  centrings: { cubic: ["P", "I", "F"], hexagonal: ["P"], tetragonal: ["P", "I"] },
  shift_templates: [],
};
const cand = (a: number, c: number, over: Partial<Candidate> = {}): Candidate => ({
  cell: [a, a, c, 90, 90, 120], cell_esd: [], system: "hexagonal", centring: "P",
  lattice_group: "P6/mmm", volume: 0.866 * a * a * c, n_indexed: 18, n_lines: 20,
  fom: [{ name: "m20", value: 41.25, n_lines: 20, blind_spot: "" }], found_by: ["svd"],
  confidence: "low", confidence_caveats: [], ambiguity: [],
  lebail: { rwp: 0.183, predicted_but_absent: 34, n_reflections: 200, status: "ok",
            absent_source: "line_screen", n_lines_screened: 189 },
  diagnostics: [], ...over,
});
const answered = {
  result: {
    candidates: [cand(9.375, 6.89), cand(9.375, 6.89, { system: "trigonal" })],
    systems_searched: ["cubic", "hexagonal"], search_complete: { cubic: true, hexagonal: false },
    diagnostics: [{ level: "warning", code: "INDEX_BUDGET_EXHAUSTED",
      message: "The run hit its declared ceiling of 120 s, so the answer covers what was reached.",
      where: ["truncated: hexagonal", "not reached: tetragonal"] }],
  },
  adopt: [{ picked: false, why: "grade low" }, { picked: false, why: "grade low" }],
};

let doc: any;
let screen: any = null;
const screenExtinctions = vi.fn(async (_i: number) => ({}));
const adoptCandidate = vi.fn(async (i: number, sg?: string) => ({
  api_call: `s = rx.structure_from_candidate(result.candidates[${i}], space_group="${sg}")` }));
const adopted: number[] = [];
let answer: any = null;
const patchProject = vi.fn(async (body: any) => (doc = { ...doc, indexing: body.indexing }));
const index = vi.fn(async () => ({}));
const candidateTicks = vi.fn(async (i: number) => ({ two_theta: [10 + i, 20], hkl: [[1, 0, 0], [1, 1, 0]],
                                                    n_total: 2 }));
vi.mock("../api", () => ({
  ApiError: class extends Error {},
  api: {
    indexResult: async () => {
      if (!answer) throw new Error("no index result");
      return answer;
    },
    patchProject: (b: any) => patchProject(b),
    project: async () => doc,
    index: () => index(),
    cancel: async () => ({}),
    candidateTicks: (i: number) => candidateTicks(i),
    extinctionResult: async () => {
      if (!screen) throw new Error("no screen");
      return screen;
    },
    screenExtinctions: (i: number) => screenExtinctions(i),
    adoptCandidate: (i: number, sg?: string) => adoptCandidate(i, sg),
  },
}));

import Candidates from "./Candidates.svelte";

let app: any = null;
const said: string[] = [];
const drawn: any[] = [];
const steps: number[] = [];

async function settle() {
  for (let i = 0; i < 12; i++) await tick();
  flushSync();
}
const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const button = (words: string) => [...document.querySelectorAll<HTMLButtonElement>("button")]
  .find((b) => text(b) === words)!;

async function boot(props: Record<string, unknown> = {}) {
  app = mount(Candidates, { target: document.body, props: {
    step: 2, doc, capabilities, nLines: 20,
    say: (_k: string, t: string) => said.push(t),
    onstep: (i: number) => steps.push(i),
    onproject: (d: any) => app && app.$set?.({ doc: d }),
    oncandidate: (c: any) => drawn.push(c),
    onadopted: () => adopted.push(1),
    ...props,
  } });
  await settle();
}

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  said.length = 0;
  drawn.length = 0;
  steps.length = 0;
  answer = null;
  screen = null;
  adopted.length = 0;
  vi.clearAllMocks();
});

describe("the Index step", () => {
  it("draws the short form, commits an edit to the document, and indexes", async () => {
    doc = { indexing: indexing() };
    await boot();
    expect([...document.querySelectorAll(".field > .label")].slice(0, 3).map(text))
      .toEqual(["Crystal systems", "Largest volume", "Time limit"]);
    expect([...document.querySelectorAll(".tgs")][0].querySelectorAll("button").length).toBe(3);
    expect(document.querySelector<HTMLInputElement>("input[aria-label='Largest cell volume']")!
      .placeholder).toBe("from data");
    // the time limits in rising order, the unbounded one last; quick by default
    expect([...document.querySelectorAll(".segmented button")].map(text)).toEqual(["2 minutes", "None"]);
    expect(button("2 minutes").getAttribute("aria-pressed")).toBe("true");
    button("tetragonal").click();
    await settle();
    expect(patchProject).toHaveBeenCalledTimes(1);
    expect(patchProject.mock.calls[0][0].indexing.search.systems).toEqual(["cubic", "hexagonal"]);
    // the one filled action, in the foot
    const go = button("Index");
    expect(go.closest(".foot")).not.toBeNull();
    expect(go.classList.contains("ghost")).toBe(false);
    go.click();
    await settle();
    expect(index).toHaveBeenCalled();
  });

  it("shows each system's state and the cells found so far while the search runs, with Stop", async () => {
    doc = { indexing: indexing() };
    await boot({ busy: true, run: { state: "running", run: { kind: "index", stage: "hexagonal",
                                                              elapsed: 12 } } });
    expect(text(document.querySelector("h3"))).toBe("Searching");
    const sys = () => [...document.querySelectorAll("table.sys tr")]
      .map((tr) => [...tr.querySelectorAll("td")].map(text).join(" "));
    expect(sys()).toEqual(["cubic waiting", "hexagonal searching…", "tetragonal waiting"]);
    app.event({ kind: "stage_end", data: { consensus: true, system: "cubic", n_candidates: 1,
                                           candidates: [{ cell: [4.1, 4.1, 4.1, 90, 90, 90] }] } });
    flushSync();
    expect(sys()[0]).toBe("cubic searched");
    expect(text(document.querySelector("table.found td"))).toBe("a = 4.1000 Å");
    expect(text(document.querySelector(".foot .why"))).toMatch(/^0:1\d elapsed · about 1:4\d left$/);
    expect(button("Stop").classList.contains("ghost")).toBe(true);
  });

  it("says what the search did not cover, lists the candidates, and draws a chosen row's lines", async () => {
    doc = { indexing: indexing() };
    answer = answered;
    await boot();
    expect(text(document.querySelector(".coverage")))
      .toBe("Not searched: tetragonal. Stopped early: hexagonal. The 2-minute limit ran out.");
    expect([...document.querySelectorAll("table.cands th")].map(text))
      .toEqual(["#", "Cell", "Lattice", "V", "M₂₀", "Unindexed", "Absent", "Rwp", "Grade"]);
    const rows = [...document.querySelectorAll("table.cands tbody tr")];
    expect([...rows[0].querySelectorAll("td")].map(text))
      .toEqual(["1", "a = 9.3750, c = 6.8900 Å", "hexagonal P", "524", "41.3", "2", "34 of 189",
                "18.3 %", "low"]);
    // a related row is marked, never merged (call 8)
    expect(text(rows[1].querySelector(".rel"))).toBe("same cell as #1");
    expect(button("Judge ›").disabled).toBe(true);
    (rows[1] as HTMLElement).click();
    await settle();
    expect(candidateTicks).toHaveBeenCalledWith(1);
    expect(drawn.at(-1)).toMatchObject({ label: "#2", two_theta: [11, 20], n_total: 2 });
    expect(rows[1].classList.contains("sel")).toBe(true);
    button("Judge #2 ›").click();
    expect(steps).toEqual([3]);
    expect(button("Index again").classList.contains("ghost")).toBe(true);
  });
});

describe("the Judge step", () => {
  const cls = (symbol: string, over: Record<string, unknown> = {}) => ({
    symbol, representative: "P 63/m", space_groups: ["P 63", "P 63/m"], screened: true,
    refuted: false, delta_bic: 0, n_absent: 4, n_testable: 3, n_present: 0, ...over });

  it("sends a person with no candidate chosen back to Index", async () => {
    doc = { indexing: indexing() };
    answer = answered;
    await boot({ step: 3 });
    button("Choose a candidate in Index").click();
    expect(steps).toEqual([2]);
  });

  it("shows one candidate's evidence, screens its extinctions, and adopts it pending Apply", async () => {
    doc = { indexing: indexing() };
    answer = { ...answered, refuting_caveats: ["validation_failed"],
      result: { ...answered.result, candidates: [cand(9.375, 6.89, {
        cell_esd: [0.0006, 0, 0.0008], confidence_caveats: ["validation_failed", "zero_shift_assumed"] }),
        cand(9.375, 6.89)] } };
    await boot({ step: 3 });
    app.judge(0);
    await settle();
    expect(text(document.querySelector(".cellline"))).toBe("a = 9.3750(6), c = 6.8900(8) Å, V = 524.4 Å³");
    // the relation line holds its height when there is none
    expect(document.querySelector(".relline")!.textContent).toBe(" ");
    // a refuting caveat in the danger colour, a capping one plain
    const cav = [...document.querySelectorAll(".caveats > span")];
    expect(cav.map(text)).toEqual(["validation failed", "zero shift assumed"]);
    expect(cav.map((e) => e.classList.contains("bad"))).toEqual([true, false]);
    expect(button("‹").disabled).toBe(true);
    // the extinction screen, then its classes with the gate's pick
    button("Screen extinctions").click();
    await settle();
    expect(screenExtinctions).toHaveBeenCalledWith(0);
    screen = { candidate: 0, best: 1, result: { candidates: [
      cls("P - - -", { refuted: true, n_present: 2, delta_bic: 3, forbidden_hkl: [[0, 0, 1]],
                       forbidden_two_theta: [12.84], representative: "P 6/m", space_groups: ["P 6/m"] }),
      cls("P 63 - -")], diagnostics: [] } };
    app.ran("extinction");
    await settle();
    const rows = [...document.querySelectorAll("table.classes tbody tr")];
    // live classes first; a refuted one stays, muted (call 17)
    expect(rows.map((r) => r.querySelector(".sg")!.getAttribute("aria-label"))).toEqual(["P 63 - -", "P - - -"]);
    expect(text(rows[0].querySelector(".mark"))).toBe("rietx's pick");
    expect(rows[1].classList.contains("off")).toBe(true);
    // the class's space groups, its representative first and chosen (call 12)
    const sgs = [...document.querySelectorAll(".sgs button")];
    expect(sgs.map((b) => b.querySelector(".sg")!.getAttribute("aria-label"))).toEqual(["P 63/m", "P 63"]);
    expect(sgs[0].getAttribute("aria-pressed")).toBe("true");
    (sgs[1] as HTMLElement).click();
    flushSync();
    // Adopt is pending until Apply (call 11)
    button("Adopt as a Le Bail start").click();
    flushSync();
    expect(adoptCandidate).not.toHaveBeenCalled();
    expect(text(document.querySelector(".foot .why"))).toBe("Adopt #1 in P63 as a Le Bail start");
    button("Revert").click();
    flushSync();
    button("Adopt as a Le Bail start").click();
    flushSync();
    button("Apply").click();
    await settle();
    expect(adoptCandidate).toHaveBeenCalledWith(0, "P 63");
    expect(said.at(-1)).toContain("structure_from_candidate(result.candidates[0]");
    expect(adopted).toEqual([1]);
  });
});
