// The workflow menu's data (WP-2204, carried into the rebuild by WP-2215).
import { describe, expect, it } from "vitest";

import { WORKFLOWS, isNotBuilt, menuLabel, workflow } from "./workflows";

describe("the workflows", () => {
  it("are the five of the design round, in its order", () => {
    expect(WORKFLOWS.map((w) => w.name)).toEqual(
      ["Refinement", "Peaks and indexing", "Series", "Structure solution", "Rigid bodies"]);
  });

  it("mark every one not built in the rebuilt page, and only those", () => {
    expect(WORKFLOWS.filter((w) => isNotBuilt(w.id)).map((w) => w.id))
      .toEqual(["index", "series", "solve", "rigid"]);
    expect(menuLabel(workflow("refine"))).toBe("Refinement");
    expect(menuLabel(workflow("solve"))).toBe("Structure solution · not built yet");
  });

  it("give each unbuilt one steps with words", () => {
    for (const w of WORKFLOWS.filter((w) => w.steps)) {
      expect(w.steps!.length, w.id).toBeGreaterThan(2);
      for (const s of w.steps!) expect(s.name && s.body, `${w.id}: ${s.name}`).toBeTruthy();
    }
  });
});
