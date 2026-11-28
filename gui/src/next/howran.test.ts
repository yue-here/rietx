// How the last Refine ran, in words (`next/howran.ts`, WP-2227): one case per
// state the maintainer ruled on 2026-11-22, the words the title line and the
// status bar say, and the Console's comment after a fit.
import { describe, expect, it } from "vitest";

import type { HelpCorpus, ParameterEntry } from "../lib/help";
import type { HowRan, RunState } from "../lib/stream";
import { howComment, howWords } from "./howran";

const entry = (title: string, paths: string[]): ParameterEntry => ({
  title, paths, description: "", unit: null, default: null, typical: null, anchor: null,
});

const corpus = {
  parameters: [
    entry("Atom position shift", ["phases.*.atoms.*.dof.*"]),
    entry("Isotropic displacement parameter", ["phases.*.atoms.*.biso"]),
    entry("Site occupancy", ["phases.*.atoms.*.occ"]),
  ],
} as unknown as HelpCorpus;

const ONE: HowRan = { ran: "one_stage", reason: "converged",
                      plan_line: "plan: one stage (warm_refit), because the model had already converged on this pattern." };
const released = (families: string[]): HowRan => ({
  ran: "stages", reason: "released", families,
  released: families.map((f) => f.replace("*", "0").replace("*", "1")),
  plan_line: "plan: scale_bkg, cell, positions, in stages, because this fit frees phases.0.atoms.1.dof.0, which the last fit held.",
});
const frame = (kind: string, how: HowRan | null): RunState => ({
  state: "idle", project: "/p.rex", head: "n9",
  run: { kind, status: "converged", stage: null, stage_index: null, n_stages: null, rwp: 0.0925,
         gof: 1.65, node_id: "n9", completed_stages: [], error: null, how },
});

describe("how a Refine ran, in words", () => {
  it("one stage: the model the last fit converged", () => {
    expect(howWords(ONE, corpus)).toBe("One stage: the model had converged");
  });

  it("in stages for a released parameter: the family named by its help title", () => {
    expect(howWords(released(["phases.*.atoms.*.dof.*"]), corpus))
      .toBe("In stages: Atom position shift was held");
    expect(howWords(released(["phases.*.atoms.*.dof.*", "phases.*.atoms.*.biso"]), corpus))
      .toBe("In stages: Atom position shift and Isotropic displacement parameter were held");
    expect(howWords(released(["phases.*.atoms.*.dof.*", "phases.*.atoms.*.biso",
                              "phases.*.atoms.*.occ", "instrument.zero_shift"]), corpus))
      .toBe("In stages: Atom position shift, Isotropic displacement parameter and 2 more were held");
    // a family with no help entry is named by its key
    expect(howWords(released(["vars.x"]), corpus)).toBe("In stages: vars.x was held");
  });

  it("in stages after the one stage was rejected, and why it was", () => {
    expect(howWords({ ran: "stages", reason: "fallback", diverged: true }, corpus))
      .toBe("In stages: the one-stage re-fit diverged");
    expect(howWords({ ran: "stages", reason: "fallback", diverged: false }, corpus))
      .toBe("In stages: the one-stage re-fit was discarded");
  });

  it("in stages, a first fit's plan, and nothing before any fit", () => {
    expect(howWords({ ran: "stages", reason: null }, corpus)).toBe("In stages");
    expect(howWords(null, corpus)).toBe("");
    expect(howWords(undefined, null)).toBe("");
  });

  it("the Console's comment is the plan line summary() prints, after a fit only", () => {
    expect(howComment(frame("fit", ONE))).toBe(`# ${ONE.plan_line}`);
    expect(howComment(frame("stage", ONE))).toBeNull();
    expect(howComment(frame("fit", null))).toBeNull();
    expect(howComment(null)).toBeNull();
  });
});
