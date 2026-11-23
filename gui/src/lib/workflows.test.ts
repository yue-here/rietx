// The workflow menu's data (WP-2204, carried into the rebuild by WP-2215).
import { describe, expect, it } from "vitest";

import { WORKFLOWS, isNotBuilt, menuLabel, stepGraph, workflow } from "./workflows";

describe("the workflows", () => {
  it("are the five of the design round, in its order", () => {
    expect(WORKFLOWS.map((w) => w.name)).toEqual(
      ["Refinement", "Peaks and indexing", "Series", "Structure solution", "Rigid bodies"]);
  });

  it("mark every one not built in the rebuilt page, and only those", () => {
    expect(WORKFLOWS.filter((w) => isNotBuilt(w.id)).map((w) => w.id))
      .toEqual(["solve", "rigid"]);
    expect(menuLabel(workflow("series"))).toBe("Series");
    expect(menuLabel(workflow("index"))).toBe("Peaks and indexing");
    expect(menuLabel(workflow("refine"))).toBe("Refinement");
    expect(menuLabel(workflow("solve"))).toBe("Structure solution · not built yet");
  });

  it("open each peaks-and-indexing step on its graph", () => {
    expect([0, 1, 2, 3].map((i) => stepGraph("index", i)))
      .toEqual(["pattern", "peaks", "pattern", "pattern"]);
    expect(stepGraph("series", 1)).toBeNull();
    for (const i of [0, 1, 2, 3]) expect(workflow("index").graphs).toContain(stepGraph("index", i));
  });

  it("give each workflow with steps words for every step", () => {
    for (const w of WORKFLOWS.filter((w) => w.steps)) {
      expect(w.steps!.length, w.id).toBeGreaterThan(2);
      for (const s of w.steps!) expect(s.name && s.body, `${w.id}: ${s.name}`).toBeTruthy();
    }
  });
});
