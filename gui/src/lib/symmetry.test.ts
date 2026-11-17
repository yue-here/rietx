import { describe, expect, it } from "vitest";

import {
  entryLines,
  noteTone,
  shortPath,
  siteLines,
  symbolChanged,
  symbolTokens,
  symmetryLine,
  wyckoffLabel,
  type PhaseSymmetry,
} from "./symmetry";

const CUBIC: PhaseSymmetry = {
  phase: 0, space_group: "P m -3 m", xhm: "P m -3 m", number: 221,
  crystal_system: "cubic", laue_class: "m-3m", point_group: "m-3m",
  centring: "P", ext: "", unique_axis: "", centrosymmetric: true,
  reference_setting: true, setting: "P m -3 m is cubic",
  ties: { b: "a", c: "a" }, fixed_angles: { alpha: 90, beta: 90, gamma: 90 },
  constraints: "b = a, c = a · α = β = γ = 90°",
};

describe("symmetryLine", () => {
  it("reads out what the symbol is, in the order a narrow column needs", () => {
    expect(symmetryLine(CUBIC)).toBe(
      "No. 221 · cubic · Laue m-3m · P lattice · centrosymmetric");
  });

  it("names the setting wherever the crystal system is not enough", () => {
    // WP-1036's whole finding: three settings disagree with the system alone,
    // and a summary that shows only "monoclinic" or "trigonal" does not say
    // which cell edges are tied — while every free-parameter *count* is right.
    expect(symmetryLine({ ...CUBIC, xhm: "P 1 1 21/b", number: 14,
                          crystal_system: "monoclinic", laue_class: "2/m",
                          unique_axis: "c" }))
      .toContain("unique axis c");
    expect(symmetryLine({ ...CUBIC, xhm: "R -3 c:R", number: 167,
                          crystal_system: "trigonal", laue_class: "-3m",
                          centring: "R", ext: "R" }))
      .toContain("rhombohedral axes");
    expect(symmetryLine({ ...CUBIC, xhm: "R -3 c:H", ext: "H",
                          crystal_system: "trigonal" }))
      .toContain("hexagonal axes");
  });

  it("says non-centrosymmetric out loud rather than by omission", () => {
    expect(symmetryLine({ ...CUBIC, centrosymmetric: false }))
      .toContain("non-centrosymmetric");
  });

  it("renders an unresolvable symbol as the server's complaint", () => {
    expect(symmetryLine({ phase: 0, space_group: "P q -7 z",
                          error: "unknown space group symbol: 'P q -7 z'" }))
      .toBe("unknown space group symbol: 'P q -7 z'");
    expect(symmetryLine(null)).toBe("");
  });
});

describe("noteTone", () => {
  it("separates the one kind that blocks from the ones that only warn", () => {
    expect(noteTone("orbit_collision")).toBe("bad");
    for (const kind of ["setting_change", "centring_change",
                        "multiplicity_change", "free_paths_dropped",
                        "free_paths_renumbered"]) {
      expect(noteTone(kind)).toBe("warn");
    }
    // a shared site is legal modelling and a pre-existing collision is not this
    // edit's — both are facts about the change, not complaints about it
    expect(noteTone("orbit_collision_shared")).toBe("info");
    expect(noteTone("orbit_collision_existing")).toBe("info");
    expect(noteTone("something_a_later_wp_adds")).toBe("info");
  });
});

describe("entryLines", () => {
  it("leads with the count, because that is the part a reader acts on", () => {
    expect(entryLines({ added: [], removed: [], tied: [],
                        untied: ["phases.0.cell.c"], locked: [], unlocked: [] }))
      .toEqual(["1 stop being tied and refine on their own: cell.c"]);
  });

  it("truncates the paths and never the count", () => {
    const added = ["a", "b", "c", "d", "e", "f"].map((n) => `phases.0.atoms.0.${n}`);
    const [line] = entryLines({ added });
    expect(line.startsWith("6 parameter(s) appear: ")).toBe(true);
    expect(line.endsWith(" … +2")).toBe(true);
  });

  it("says nothing at all when nothing moves", () => {
    expect(entryLines(undefined)).toEqual([]);
    expect(entryLines({ added: [], removed: [] })).toEqual([]);
  });
});

describe("siteLines", () => {
  it("reports the order change and holds the DOF count steady when it is", () => {
    expect(siteLines([{ label: "B",
                        from: { order: 8, dofs: 1, multiplicity: 6 },
                        to: { order: 4, dofs: 1, multiplicity: 6 } }]))
      .toEqual(["B: site symmetry order 8 → 4, 1 coordinate DOF(s)"]);
    expect(siteLines([{ label: "La",
                        from: { order: 48, dofs: 0, multiplicity: 1 },
                        to: { order: 1, dofs: 3, multiplicity: 48 } }]))
      .toEqual(["La: site symmetry order 48 → 1, multiplicity 1 → 48, "
                + "0 → 3 coordinate DOF(s)"]);
    expect(siteLines(undefined)).toEqual([]);
  });

  it("says the multiplicity moved even when nothing else did", () => {
    // NAC's I 21 3 → I 41 3 2, found in a browser: same order, same DOFs, same
    // ties, same centring — and twice as many atoms in the cell.
    expect(siteLines([{ label: "Ca1",
                        from: { order: 2, dofs: 1, multiplicity: 12 },
                        to: { order: 2, dofs: 1, multiplicity: 24 } }]))
      .toEqual(["Ca1: site symmetry order 2 → 2, multiplicity 12 → 24, "
                + "1 coordinate DOF(s)"]);
  });
});

describe("wyckoffLabel", () => {
  const letters = [
    { path: "phases.0.atoms.0", atom: 0, label: "La", wyckoff: "1a",
      site_symmetry: "m-3m", multiplicity: 1 },
    { path: "phases.0.atoms.1", atom: 1, label: "B", error: "spglib disagreed" },
  ];

  it("is empty until the letters are fetched, and stays empty on a failure", () => {
    expect(wyckoffLabel(letters, "phases.0.atoms.0")).toBe("1a · m-3m");
    expect(wyckoffLabel(letters, "phases.0.atoms.1")).toBe("");
    expect(wyckoffLabel(letters, "phases.0.atoms.9")).toBe("");
    expect(wyckoffLabel(undefined, "phases.0.atoms.0")).toBe("");
  });
});

describe("symbolChanged", () => {
  it("asks whether the text differs and nothing else", () => {
    // deliberately not a symbol grammar: gemmi's table is the authority and it
    // is on the other side of the wire, so a client-side regex would refuse
    // perfectly legal settings — the second-copy trap in miniature
    expect(symbolChanged("P 4/m m m", "P m -3 m")).toBe(true);
    expect(symbolChanged("  P m -3 m  ", "P m -3 m")).toBe(false);
    expect(symbolChanged("", "P m -3 m")).toBe(false);
    expect(symbolChanged("R -3 c:R", "R -3 c:H")).toBe(true);
    expect(symbolChanged("230", "I a -3 d")).toBe(true);
  });
});

describe("shortPath", () => {
  it("drops the prefix the panel is already inside", () => {
    expect(shortPath("phases.0.atoms.1.dof.0")).toBe("atoms.1.dof.0");
    expect(shortPath("instrument.profile.w")).toBe("profile.w");
    expect(shortPath("phases.12.cell.c")).toBe("cell.c");
  });
});

describe("symbolTokens", () => {
  it("typesets a screw axis, a glide and a bar", () => {
    expect(symbolTokens("P 21/c").tokens).toEqual([
      { kind: "letter", text: "P" }, { kind: "screw", text: "2", sub: "1" },
      { kind: "slash", text: "/" }, { kind: "letter", text: "c" }]);
    const r = symbolTokens("R -3 c:H");
    expect(r.tokens.map((t) => t.kind)).toEqual(["letter", "bar", "letter"]);
    expect(r.ext).toBe("H");
    expect(symbolTokens("P 63/m m c").tokens.map((t) => t.text).join(""))
      .toBe("P6/mmc");
  });

  it("returns nothing for an empty symbol", () => {
    expect(symbolTokens("")).toEqual({ tokens: [], ext: "" });
  });
});
