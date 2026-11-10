import { describe, expect, it } from "vitest";
import { buildTree, cellFoldText, triState, type AtomTable, type Group } from "./paramtree";
import type { ParamRow } from "./table";

function r(path: string, extra: Partial<ParamRow> = {}): ParamRow {
  return {
    path, value: 1, vary: false, lo: -Infinity, hi: Infinity, tie: null, locked: false,
    held: false, esd: null, mode_fixed: false, needs_held_cell: false, refinable: true,
    held_because: "", help_key: null, ...extra,
  };
}

const tied = (source: string) => ({ refinable: false, tie: { sources: [source] },
                                     held_because: `tied: = 1·${source}` });
const locked = { refinable: false, locked: true, held_because: "structurally fixed" };

// fluorapatite's shape: hexagonal P 63/m, one atom on a 3-fold axis (one DOF, z)
const ROWS: ParamRow[] = [
  r("phases.0.cell.a"), r("phases.0.cell.b", tied("phases.0.cell.a")), r("phases.0.cell.c"),
  r("phases.0.cell.alpha", { ...locked, value: 90 }), r("phases.0.cell.beta", { ...locked, value: 90 }),
  r("phases.0.cell.gamma", { ...locked, value: 120 }),
  r("phases.0.scale"), r("phases.0.lor_size"), r("phases.0.gauss_strain"),
  r("phases.0.atoms.0.x", locked), r("phases.0.atoms.0.y", locked),
  r("phases.0.atoms.0.z", tied("phases.0.atoms.0.dof.0")), r("phases.0.atoms.0.dof.0"),
  r("phases.0.atoms.0.occ"), r("phases.0.atoms.0.biso"),
  r("phases.0.preferred_orientation.r", { help_key: "phases.*.preferred_orientation.r" }),
  r("instrument.zero_shift"), r("instrument.profile.u"), r("instrument.profile.w"),
  r("instrument.background.c0"), r("instrument.background.c1"), r("instrument.polarization"),
];

const INFO = {
  phases: [{ name: "fluorapatite", space_group: "P 63/m", crystal_system: "hexagonal",
             ties: { b: "a" }, fixed_angles: { alpha: 90, beta: 90, gamma: 120 },
             atoms: [{ label: "CA1", species: "Ca" }] }],
  sites: [{ path: "phases.0.atoms.0", dof_paths: ["phases.0.atoms.0.dof.0"],
            dof_directions: [[0, 0, 1]] }],
  letters: [{ path: "phases.0.atoms.0", wyckoff: "4f", multiplicity: 4, site_symmetry: "3.." }],
  titleOf: (key: string | null) => (key ? "March-Dollase r" : null),
};

describe("the Parameters panel tree (WP-2126)", () => {
  it("folds what the setting holds into the crystallographer's line", () => {
    expect(cellFoldText({ b: "a", c: "a" }, { alpha: 90, beta: 90, gamma: 90 }))
      .toBe("a = b = c, α = β = γ = 90°");
    expect(cellFoldText({ b: "a" }, { alpha: 90, beta: 90, gamma: 120 }))
      .toBe("a = b, α = β = 90°, γ = 120°");
    // rhombohedral axes: the lengths and the angles are each one free value
    expect(cellFoldText({ b: "a", c: "a", beta: "alpha", gamma: "alpha" }, {}))
      .toBe("a = b = c, α = β = γ");
    expect(cellFoldText({}, {})).toBe("");
  });

  it("puts single parameters first, then groups in refinement order, then the atoms", () => {
    const [phase, instrument] = buildTree(ROWS, INFO);
    expect(phase.title).toBe("fluorapatite");
    expect(phase.items.map((it) => it.kind === "row" ? it.label
      : it.kind === "group" ? it.title : "atoms"))
      .toEqual(["Scale", "March-Dollase r", "Cell", "Size and strain", "atoms"]);
    expect(instrument.items.map((it) => it.kind === "row" ? it.label
      : it.kind === "group" ? it.title : "atoms"))
      .toEqual(["Zero shift", "Background", "Peak shape", "Source and geometry"]);
  });

  it("shows the cell's free rows and folds the held ones", () => {
    const cell = buildTree(ROWS, INFO)[0].items.find(
      (it): it is Group => it.kind === "group" && it.title === "Cell")!;
    expect(cell.lines.map((l) => l.label)).toEqual(["a", "c"]);
    expect(cell.fold?.text).toBe("a = b, α = β = 90°, γ = 120°");
    expect(cell.fold?.lines.map((l) => l.label)).toEqual(["b", "α", "β", "γ"]);
    expect(cell.members.map((m) => m.path)).toEqual(["phases.0.cell.a", "phases.0.cell.c"]);
  });

  it("draws the background as one group with no coefficient rows", () => {
    const bg = buildTree(ROWS, INFO)[1].items.find(
      (it): it is Group => it.kind === "group" && it.title === "Background")!;
    expect(bg.lines).toEqual([]);
    expect(bg.summary).toBe("2 terms");
    expect(bg.members.length).toBe(2);
  });

  it("makes one atom one row, its box beside the coordinate the DOF moves", () => {
    const table = buildTree(ROWS, INFO)[0].items.at(-1) as AtomTable;
    expect(table.atoms.length).toBe(1);
    const atom = table.atoms[0];
    expect([atom.label, atom.species, atom.wyckoff, atom.multiplicity])
      .toEqual(["CA1", "Ca", "4f", 4]);
    expect(atom.x.dof).toBeNull();
    expect(atom.y.dof).toBeNull();
    expect(atom.z.dof?.path).toBe("phases.0.atoms.0.dof.0");
    expect(atom.dofs.map((d) => d.path)).toEqual(["phases.0.atoms.0.dof.0"]);
  });

  it("tells two members of one family apart by the index their path names", () => {
    const rows = [r("instrument.source.lines.0.weight", { help_key: "w" }),
                  r("instrument.source.lines.1.weight", { help_key: "w" }),
                  r("instrument.polarization", { help_key: "p" })];
    const titles: Record<string, string> = { w: "Emission line weight", p: "Polarisation factor" };
    const source = buildTree(rows, { ...INFO, titleOf: (k) => (k ? titles[k] : null) })[0]
      .items.find((it): it is Group => it.kind === "group")!;
    expect(source.lines.map((l) => l.label))
      .toEqual(["Emission line weight 0", "Emission line weight 1", "Polarisation factor"]);
  });

  it("keeps every row reachable: a row the filter keeps is somewhere in the tree", () => {
    const tree = buildTree(ROWS, { ...INFO, keep: (p) => p.includes("profile") });
    expect(tree.length).toBe(1);
    expect(tree[0].items.length).toBe(1);
  });

  it("reads a set of boxes as on, off or mixed", () => {
    expect(triState([true, true])).toBe(true);
    expect(triState([false, false])).toBe(false);
    expect(triState([true, false])).toBeNull();
  });
});
