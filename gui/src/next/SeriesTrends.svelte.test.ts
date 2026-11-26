// @vitest-environment jsdom
// The series' Trends graph (WP-2243 task 6): a panel per value with its title
// band and ×, the walks' gap in the band, Against, and the Plot menu's
// submenus staying open while ticking. What the canvases paint, and a point
// click, are `tests/test_gui_series_browser.py`'s.
import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import type { SeriesAnswer } from "./seriesresults";
import SeriesTrends from "./SeriesTrends.svelte";
import type { TrendsView } from "./seriestrends";

const entry = (index: number) => ({
  index, label: `T${index}`, x: 100 * (index + 1), status: "converged",
  statistics: { rwp: 0.05, gof: 1.5 }, n_iterations: 5, reseeded: false, rwp_warm: null,
  rung: "warm", rungs_tried: [], node_id: null, tree_id: null, diagnostics: [],
});
const traj = (path: string, value: number[], over: Record<string, unknown> = {}) => ({
  path, x: [100, 200, 300], x_label: "T (K)", value, stderr: [0.001, 0.001, 0.001],
  labels: ["T0", "T1", "T2"], backward: null, n_sigma: null, gap_at: null, ...over,
});
const answer: SeriesAnswer = {
  entries: [entry(0), entry(1), entry(2)] as any,
  trajectories: [
    traj("phases.0.cell.a", [5.8, 5.81, 5.82], { backward: [5.8, 5.812, 5.82], n_sigma: 5.83 }),
    traj("phases.0.cell.c", [5.805, 5.815, 5.83]),
    traj("phases.0.scale", [1, 2, 3]),
  ] as any,
  steps: null, gaps: null, codes: null, phaseNames: ["CuCr2O4"], atomLabels: [[]],
};
const corpus = { parameters: [
  { title: "Lattice parameter a, b, c", unit: "Å", paths: ["phases.*.cell.a", "phases.*.cell.c"] },
] } as any;

let app: Record<string, any> | null = null;
afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();
const byText = (sel: string, words: string) => [...document.querySelectorAll<HTMLElement>(sel)]
  .find((b) => text(b) === words)!;

function boot(plotted: string[]) {
  const calls: Array<[string[], boolean]> = [];
  const view: TrendsView = { answer, plotted, selected: 1, name: "T1", x: 200,
                             canPrev: true, canNext: true, axis: "Temperature (K)" };
  const props = $state({ trends: view, corpus, against: "x" as "x" | "n",
                         onplot: (p: string[], on: boolean) => calls.push([p, on]) });
  app = mount(SeriesTrends, { target: document.body, props });
  flushSync();
  return { calls, props };
}

describe("the Trends graph", () => {
  it("draws a panel per value, b and c sharing one, with the walks' gap and ×", () => {
    const { calls } = boot(["rwp", "phases.0.cell.a", "phases.0.cell.c", "phases.0.scale"]);
    expect(text(document.querySelector(".gtitle b"))).toBe("T1");
    expect(text(document.querySelector(".gtitle .stat"))).toBe("200");
    const bands = [...document.querySelectorAll("figcaption")].map(text);
    expect(bands).toEqual([
      "Rwp (%)",
      "CuCr2O4 cell.a, cell.c (Å) walks differ by up to 5.8 esd",
      "CuCr2O4 scale",
    ]);
    // × removes the panel's values together
    (document.querySelectorAll("figcaption .x")[1] as HTMLElement).click();
    expect(calls).toEqual([[["phases.0.cell.a", "phases.0.cell.c"], false]]);
    // the second walk's key shows, since the record has one
    expect([...document.querySelectorAll(".gut")].map(text)).toEqual(["First walk", "Second walk"]);
  });

  it("switches the axis between the coordinate and the pattern number", () => {
    const { props } = boot(["rwp"]);
    expect(byText(".segmented button", "Temperature").getAttribute("aria-pressed")).toBe("true");
    byText(".segmented button", "Pattern").click();
    flushSync();
    expect(props.against).toBe("n");
    expect(text(document.querySelector(".xlabel"))).toBe("Pattern");
  });

  it("lists every value in the Plot menu, a submenu per group, open while ticking", () => {
    const { calls } = boot(["rwp"]);
    byText("button", "Plot").click();
    flushSync();
    const rows = [...document.querySelectorAll(".rx-menu:not(.sub) .item")].map(text);
    expect(rows).toEqual(["Fit 1", "CuCr2O4", "Remove all"]);
    byText(".rx-menu .item", "CuCr2O4").click();
    flushSync();
    const sub = () => [...document.querySelectorAll(".rx-menu.sub .item")];
    expect(sub().map(text)).toEqual(["cell.a (Å)", "cell.c (Å)", "scale"]);
    (sub()[2] as HTMLElement).click();
    flushSync();
    expect(calls).toEqual([[["phases.0.scale"], true]]);
    // a checkbox keeps the menu and its submenu open
    expect(sub().length).toBe(3);
    expect(document.querySelector(".rx-menu:not(.sub)")).not.toBeNull();
  });

  it("asks for a run, or for a value, rather than drawing an empty card", () => {
    boot([]);
    expect(text(document.querySelector(".empty"))).toBe("Nothing plotted. Choose values with Plot.");
  });
});
