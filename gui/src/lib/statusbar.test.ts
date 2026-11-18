import { describe, expect, it } from "vitest";

import { modifier, runWords, toggleTitle } from "./statusbar";
import type { RunState } from "./stream";

function frame(state: RunState["state"], run: Partial<RunState["run"]>): RunState {
  return {
    state,
    run: {
      kind: "plan", status: null, stage: null, stage_index: null, n_stages: null,
      rwp: null, gof: null, node_id: null, completed_stages: [], error: null, ...run,
    },
    project: null,
    head: null,
  };
}

describe("the run state's words (WP-2207)", () => {
  it("says nothing before the first frame", () => {
    expect(runWords(null)).toBe("");
  });

  it("says idle before any run, and the last status after one", () => {
    expect(runWords(frame("idle", {}))).toBe("idle");
    expect(runWords(frame("idle", { status: "converged" }))).toBe("converged");
    expect(runWords(frame("idle", { status: "cancelled", stage: "cell" }))).toBe("cancelled");
  });

  it("names the stage and counts the stages while a run is in flight", () => {
    expect(runWords(frame("running", {}))).toBe("starting");
    expect(runWords(frame("running", { stage: "cell", stage_index: 2, n_stages: 5 })))
      .toBe("cell (2/5)");
    expect(runWords(frame("cancelling", { stage: "cell" }))).toBe("cell");
  });

  it("counts a Le Bail alternation's passes", () => {
    const run = frame("running", { stage: "profile", lebail: { pass: 2, of: 4 } });
    expect(runWords(run)).toBe("profile · pass 2 of 4");
    expect(runWords(frame("running", { stage: "profile", lebail: { pass: 3, of: null } })))
      .toBe("profile · pass 3");
  });
});

describe("the console toggle's tooltip", () => {
  it("is a verb phrase with the shortcut on its second line", () => {
    expect(toggleTitle(true, false, "⌘")).toBe("Show the console and history\n⌘J");
    expect(toggleTitle(true, true, "Ctrl+")).toBe("Hide the console and history\nCtrl+J");
  });

  it("says why it is disabled without a project", () => {
    expect(toggleTitle(false, false, "⌘")).toBe("No project is open");
  });

  it("writes ⌘ on a Mac and Ctrl elsewhere", () => {
    expect(modifier("MacIntel")).toBe("⌘");
    expect(modifier("Win32")).toBe("Ctrl+");
    expect(modifier("Linux x86_64")).toBe("Ctrl+");
  });
});
