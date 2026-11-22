// The rebuilt Plan tab's words (`next/plan.ts`, WP-2231): what a chip says for
// a glob and what the picker offers. Named apart from `Plan.test.ts`, the
// mount case, because a case-insensitive disk holds one of `plan.test.ts` and
// `Plan.test.ts`.
import { describe, expect, it } from "vitest";

import type { HelpCorpus, ParameterEntry } from "../lib/help";
import type { Stage } from "../lib/plan";
import { freeBy, globName, matchesQuery, namedIn, pickOptions, withGlob } from "./plan";

const entry = (title: string, paths: string[]): ParameterEntry => ({
  title, paths, description: "", unit: null, default: null, typical: null, anchor: null,
});

const corpus = {
  parameters: [
    entry("Biso", ["phases.*.atoms.*.biso"]),
    entry("Zero-point shift", ["instrument.zero_shift"]),
    entry("Lattice parameter a", ["phases.*.cell.a"]),
    entry("Background coefficient", ["instrument.background.c*"]),
  ],
} as unknown as HelpCorpus;

const rows = [
  { path: "phases.0.cell.a", help_key: "phases.*.cell.a", refinable: true },
  { path: "phases.0.cell.c", help_key: "phases.*.cell.c", refinable: true },
  { path: "phases.0.cell.b", help_key: "phases.*.cell.b", refinable: false },
  { path: "phases.0.atoms.0.biso", help_key: "phases.*.atoms.*.biso", refinable: true },
  { path: "phases.0.atoms.1.biso", help_key: "phases.*.atoms.*.biso", refinable: true },
  { path: "instrument.zero_shift", help_key: "instrument.zero_shift", refinable: true },
  { path: "instrument.background.c0", help_key: "instrument.background.c*", refinable: true },
  { path: "instrument.background.c1", help_key: "instrument.background.c*", refinable: true },
];

const stage = (name: string, on: string[], off: string[] = []): Stage =>
  ({ name, turn_on: on, turn_off: off });

describe("a chip's words", () => {
  it("names a group, a described family, and nothing else", () => {
    expect(globName("phases.*.cell.*", corpus)).toBe("Cell");
    expect(globName("phases.*.atoms.*.biso", corpus)).toBe("Biso");
    expect(globName("instrument.zero_shift", corpus)).toBe("Zero-point shift");
    expect(globName("phases.*.atoms.*", corpus)).toBeNull();
  });

  it("prefixes one phase of several with the phase's name", () => {
    expect(globName("phases.1.cell.*", corpus, ["Quartz", "Calcite"])).toBe("Calcite: Cell");
    expect(globName("phases.0.cell.*", corpus, ["Quartz"])).toBe("Cell");
    expect(globName("phases.4.cell.*", corpus, ["Quartz", "Calcite"])).toBeNull();
  });
});

describe("the picker", () => {
  it("offers a group only where it reaches two refinable rows, once per name", () => {
    const { groups, parameters } = pickOptions(rows, corpus);
    expect(groups.map((g) => [g.name, g.glob, g.count])).toEqual([
      ["Cell", "phases.*.cell.*", 2],
      ["Background", "instrument.background.*", 2],
      ["Biso", "phases.*.atoms.*.biso", 2],
    ]);
    expect(parameters.map((p) => p.glob)).not.toContain("phases.0.cell.b");
    expect(parameters.find((p) => p.glob === "instrument.zero_shift")?.name).toBe("Zero-point shift");
  });

  it("adds each phase's own groups when there are several", () => {
    const two = [...rows, { path: "phases.1.cell.a", help_key: "phases.*.cell.a", refinable: true },
                 { path: "phases.1.cell.c", help_key: "phases.*.cell.c", refinable: true }];
    const names = pickOptions(two, corpus, ["Quartz", "Calcite"]).groups.map((g) => g.name);
    expect(names).toContain("Quartz: Cell");
    expect(names).toContain("Calcite: Cell");
    expect(names).not.toContain("Calcite: Biso");
  });

  it("narrows to a pool, and a search reads words and glob alike", () => {
    const pool = freeBy([stage("one", ["phases.*.cell.*"])], 0);
    const { groups, parameters } = pickOptions(rows, corpus, [], pool);
    expect(groups.map((g) => g.name)).toEqual(["Cell"]);
    expect(parameters.map((p) => p.glob)).toEqual(["phases.0.cell.a", "phases.0.cell.c"]);
    expect(matchesQuery(groups[0], "CELL")).toBe(true);
    expect(matchesQuery(parameters[0], "cell.a")).toBe(true);
    expect(matchesQuery(parameters[0], "biso")).toBe(false);
  });
});

describe("adding a glob", () => {
  const plan = [stage("one", ["phases.*.scale", "phases.*.cell.*"]), stage("two", [])];

  it("moves a freed glob from the stage that named it", () => {
    expect(namedIn(plan, "phases.*.cell.*", "free", 1)).toEqual([1]);
    const next = withGlob(plan, 1, "phases.*.cell.*", "free");
    expect(next[0].turn_on).toEqual(["phases.*.scale"]);
    expect(next[1].turn_on).toEqual(["phases.*.cell.*"]);
  });

  it("adds a fix to its stage alone, and never twice", () => {
    const next = withGlob(plan, 1, "phases.*.scale", "fix");
    expect(next[0]).toBe(plan[0]);
    expect(next[1].turn_off).toEqual(["phases.*.scale"]);
    expect(withGlob(next, 1, "phases.*.scale", "fix")[1].turn_off).toEqual(["phases.*.scale"]);
  });
});
