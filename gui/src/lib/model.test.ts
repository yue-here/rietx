/**
 * The model editor's logic — and above all the split it rests on.
 *
 * `splitEdits` is where this panel decides whether an edit is the parameter
 * table's business or the model's, and getting it wrong is not cosmetic in
 * either direction: a cell edge sent as a whole-model PATCH would write past its
 * crystal-system tie, and a species sent to `set_values` would be a number that
 * is not one. Membership in `GET /api/params` is the whole test, which is why
 * these cases are built from rows rather than from a list of field names.
 */
import { describe, expect, it } from "vitest";

import {
  applyFields,
  atomRows,
  axialWarning,
  editableValue,
  fieldParam,
  fieldText,
  instrumentFields,
  newAtom,
  paramPath,
  phaseFields,
  positionEdits,
  readValue,
  renderField,
  splitEdits,
  structureFields,
  validateField,
  withAtom,
  withoutAtom,
  xyzText,
  type Field,
  type Site,
} from "./model";
import { normalize, type ParamRow } from "./table";

function row(path: string, extra: Partial<ParamRow> = {}): ParamRow {
  return normalize([{
    path, value: 1, vary: false, lo: "-Infinity", hi: "Infinity",
    tie: null, locked: false, esd: null,
    mode_fixed: false, refinable: true, held_because: "", ...extra,
  }])[0];
}

function instrument(): any {
  return {
    zero_shift: { value: 0.01, vary: false },
    source: {
      polarization: { value: 0.5, vary: false },
      lines: [{ wavelength: 1.5405929, weight: { value: 1, vary: false } },
              { wavelength: 1.5444274, weight: { value: 0.5, vary: false } }],
    },
    profile: { shape: "tchz_pv", u: { value: 0.002, vary: false },
               v: { value: 0, vary: false }, w: { value: 0.004, vary: false },
               x: { value: 0, vary: false }, y: { value: 0, vary: false } },
    geometry: { kind: "bragg_brentano", goniometer_radius_mm: 217.5,
                sample_displacement: { value: 0, vary: false },
                sample_transparency: { value: 0, vary: false },
                axial_sl: { value: 0.002, vary: false },
                axial_hl: { value: 0.002, vary: false },
                mu_t: null, thickness_mm: null },
    background: { kind: "chebyshev", coefficients: [{ value: 1 }, { value: 0 }] },
  };
}

function structure(): any {
  return {
    phases: [{
      name: "LaB6", space_group: "P m -3 m",
      cell: { a: { value: 4.1566 }, b: { value: 4.1566 }, c: { value: 4.1566 },
              alpha: { value: 90 }, beta: { value: 90 }, gamma: { value: 90 } },
      atoms: [
        { label: "La", species: "La", x: { value: 0 }, y: { value: 0 },
          z: { value: 0 }, occ: { value: 1 }, biso: { value: 0.5 }, aniso: null },
        { label: "B", species: "B", x: { value: 0.1993 }, y: { value: 0.5 },
          z: { value: 0.5 }, occ: { value: 1 }, biso: { value: 0.4 }, aniso: null },
      ],
    }],
  };
}

const SITES: Site[] = [
  { path: "phases.0.atoms.0", phase: 0, atom: 0, site_symmetry_order: 48,
    special: true, dof_paths: [], dof_directions: [], adp_paths: [],
    adp_patterns: [[1, 1, 1, 0, 0, 0]], aniso: false },
  { path: "phases.0.atoms.1", phase: 0, atom: 1, site_symmetry_order: 8,
    special: true, dof_paths: ["phases.0.atoms.1.dof.0"],
    dof_directions: [[1, 0, 0]], adp_paths: [], adp_patterns: [], aniso: false },
];

describe("reading a field", () => {
  it("unwraps a Parameter and leaves a plain value alone", () => {
    const ins = instrument();
    expect(readValue(ins, "profile.u")).toBe(0.002);
    expect(readValue(ins, "geometry.kind")).toBe("bragg_brentano");
    expect(readValue(ins, "source.lines.1.wavelength")).toBe(1.5444274);
  });

  it("renders an absent optional as empty rather than as zero", () => {
    // µt absent is the thick-specimen case; µt = 0 is a specimen of no
    // thickness, which raises — so these must not render alike
    const field: Field = { path: "geometry.mu_t", label: "µt", kind: "optnumber" };
    expect(renderField(instrument(), field)).toBe("");
    const declared = instrument();
    declared.geometry.mu_t = 0.5;
    expect(renderField(declared, field)).toBe("0.5");
  });
});

describe("validateField", () => {
  const number: Field = { path: "profile.u", label: "U", kind: "number" };
  const optional: Field = { path: "geometry.mu_t", label: "µt", kind: "optnumber" };
  const choice: Field = { path: "geometry.kind", label: "geometry", kind: "choice",
                          choices: ["debye_scherrer", "bragg_brentano"] };
  const text: Field = { path: "phases.0.atoms.0.species", label: "species",
                        kind: "text" };

  it("refuses what the server would refuse, and allows an empty optional", () => {
    expect(validateField(number, "")).toBe("not a number");
    expect(validateField(number, "wide")).toBe("not a number");
    expect(validateField(number, "-0.5")).toBe("");
    expect(validateField(optional, "  ")).toBe("");
    expect(validateField(choice, "kappa")).toMatch(/not one of/);
    expect(validateField(choice, "debye_scherrer")).toBe("");
    expect(validateField(text, " ")).toBe("cannot be empty");
  });
});

describe("splitEdits — the parameter table owns what it has", () => {
  const fields = instrumentFields(instrument());

  it("routes a Parameter through set_values, with the instrument prefix", () => {
    const rows = [row("instrument.profile.u"), row("instrument.zero_shift")];
    const delta = splitEdits(instrument(), fields,
                             new Map([["profile.u", "0.005"]]), rows, "instrument");
    expect(delta.values).toEqual({ "instrument.profile.u": 0.005 });
    expect(delta.fields).toEqual([]);
    expect(delta.touched).toBe(1);
  });

  it("routes a geometry declaration through the model patch", () => {
    const rows = [row("instrument.profile.u")];
    const delta = splitEdits(instrument(), fields,
                             new Map([["geometry.kind", "debye_scherrer"],
                                      ["geometry.goniometer_radius_mm", "240"]]),
                             rows, "instrument");
    expect(delta.values).toEqual({});
    expect(delta.fields.map((f) => f.path))
      .toEqual(["geometry.kind", "geometry.goniometer_radius_mm"]);
  });

  it("sends a cell edge to set_values even though it is tied", () => {
    // the refusal is the verb's own ("follows … as an affine tie"), and it must
    // reach the user rather than be pre-empted by writing past the tie here
    const rows = [row("phases.0.cell.a"),
                  row("phases.0.cell.b", { tie: { sources: ["phases.0.cell.a"] } })];
    const delta = splitEdits(structure(),
                             [{ path: "phases.0.cell.b", label: "b", kind: "number" }],
                             new Map([["phases.0.cell.b", "4.2"]]), rows, "structure");
    expect(delta.values).toEqual({ "phases.0.cell.b": 4.2 });
  });

  it("ignores a cell clicked into and out of again", () => {
    const rows = [row("instrument.profile.u", { value: 0.002 })];
    const delta = splitEdits(instrument(), fields,
                             new Map([["profile.u", "0.002"]]), rows, "instrument");
    expect(delta.values).toEqual({});
    expect(delta.touched).toBe(0);
  });

  it("compares against the *rendered* value, esd and all", () => {
    // the cell shows `4.15678` for a parameter known to ±0.00019; comparing the
    // typed text against the stored float would make clicking in and out again a
    // `set_values` that truncates the parameter (WP-1011's trap)
    const rows = [row("phases.0.cell.a", { value: 4.1567812, esd: 0.00019 })];
    const fields: Field[] = [{ path: "phases.0.cell.a", label: "a", kind: "number" }];
    const shown = fieldText(structure(), fields[0], new Map(rows.map((r) => [r.path, r])),
                            "structure");
    expect(shown).toBe("4.1568");
    expect(splitEdits(structure(), fields, new Map([["phases.0.cell.a", shown]]),
                      rows, "structure").values).toEqual({});
    expect(splitEdits(structure(), fields, new Map([["phases.0.cell.a", "4.2"]]),
                      rows, "structure").values).toEqual({ "phases.0.cell.a": 4.2 });
  });

  it("falls back to the model for a field the table does not have", () => {
    const field: Field = { path: "geometry.goniometer_radius_mm", label: "r",
                           kind: "number" };
    expect(fieldText(instrument(), field, new Map(), "instrument")).toBe("217.5");
  });

  it("collects an unsendable value instead of sending it", () => {
    const delta = splitEdits(instrument(), fields,
                             new Map([["profile.u", "big"]]), [], "instrument");
    expect(delta.invalid).toEqual([{ path: "profile.u", why: "not a number" }]);
    expect(delta.values).toEqual({});
  });

  it("prefixes only the instrument's paths", () => {
    expect(paramPath("instrument", "profile.u")).toBe("instrument.profile.u");
    expect(paramPath("structure", "phases.0.cell.a")).toBe("phases.0.cell.a");
  });
});

describe("the parameter path a field is about", () => {
  const fields = instrumentFields(instrument());
  const find = (path: string) => fields.find((f) => f.path === path)!;

  it("prefixes the instrument's, and takes the field's own where it has one", () => {
    // the polarization factor is `source.polarization` in the instrument and
    // `instrument.polarization` in θ.  Before WP-1214 the prefixed guess named
    // no row, so the cell rendered off the model, applied as a whole-model
    // PATCH past `set_values`' bounds, and had no row for a refine flag to act
    // on — silently, because a field the table does not have is an ordinary
    // model field.
    expect(fieldParam("instrument", find("profile.u"))).toBe("instrument.profile.u");
    expect(fieldParam("instrument", find("source.polarization")))
      .toBe("instrument.polarization");
    expect(fieldParam("structure", { path: "phases.0.scale", label: "scale",
                                     kind: "number" })).toBe("phases.0.scale");
  });

  it("sends polarization through set_values under the name the table has", () => {
    const rows = [row("instrument.polarization", { value: 0.5 })];
    const delta = splitEdits(instrument(), fields,
                             new Map([["source.polarization", "0.9"]]), rows,
                             "instrument");
    expect(delta.values).toEqual({ "instrument.polarization": 0.9 });
    expect(delta.fields).toEqual([]);
  });
});

describe("the phase's own numbers", () => {
  it("offers the scale and both broadening pairs, at their own units", () => {
    // the phase half of the instrument ⊕ sample split: Gaussian variances add,
    // Lorentzian FWHMs do, which is why the units differ
    const fields = phaseFields(0);
    expect(fields.map((f) => f.path)).toEqual([
      "phases.0.scale", "phases.0.lor_size", "phases.0.lor_strain",
      "phases.0.gauss_size", "phases.0.gauss_strain",
    ]);
    expect(fields.map((f) => f.unit))
      .toEqual([undefined, "°2θ", "°2θ", "deg²", "deg²"]);
    expect(fields.every((f) => f.help?.startsWith("parameters:phases.*."))).toBe(true);
  });

  it("is what the structure form carries for each phase", () => {
    // one list, so a field cannot render in the form and be missing from the
    // delta — the shape `Field` exists to make impossible
    const paths = structureFields(structure()).map((f) => f.path);
    for (const field of phaseFields(0)) expect(paths).toContain(field.path);
  });
});

describe("applyFields", () => {
  it("writes into a copy, through a Parameter to its value", () => {
    const before = instrument();
    const next = applyFields(before, [
      { path: "geometry.kind", label: "", kind: "choice", choices: ["debye_scherrer"] },
      { path: "profile.u", label: "", kind: "number" },
      { path: "geometry.mu_t", label: "", kind: "optnumber" },
    ], new Map([["geometry.kind", "debye_scherrer"], ["profile.u", "0.01"],
                ["geometry.mu_t", ""]]));
    expect(next.geometry.kind).toBe("debye_scherrer");
    expect(next.profile.u.value).toBe(0.01);
    expect(next.geometry.mu_t).toBeNull();
    expect(before.geometry.kind).toBe("bragg_brentano");   // untouched
  });
});

describe("the instrument form follows the geometry it is editing", () => {
  it("offers µR to a capillary and µt to a flat plate, never both", () => {
    const capillary = instrument();
    capillary.geometry.kind = "debye_scherrer";
    const paths = (model: any) => instrumentFields(model).map((f) => f.path);
    expect(paths(capillary)).toContain("geometry.mu_r");
    expect(paths(capillary)).not.toContain("geometry.mu_t");
    expect(paths(instrument())).toContain("geometry.mu_t");
    expect(paths(instrument())).not.toContain("geometry.mu_r");
  });

  it("offers neither to an unstated geometry, which has no specimen to correct", () => {
    const unstated = instrument();
    delete unstated.geometry.kind;      // a hand-built one reads unstated (WP-2015)
    const paths = instrumentFields(unstated).map((f) => f.path);
    for (const path of ["geometry.mu_r", "geometry.mu_t", "geometry.thickness_mm",
                        "geometry.capillary_radius_mm"]) {
      expect(paths).not.toContain(path);
    }
    expect(paths).toContain("geometry.kind");
  });

  it("offers one row per emission line, and no weight for the locked first", () => {
    const paths = instrumentFields(instrument()).map((f) => f.path);
    expect(paths).toContain("source.lines.0.wavelength");
    expect(paths).toContain("source.lines.1.weight");
    expect(paths).not.toContain("source.lines.0.weight");
  });
});

describe("the groups the instrument form is drawn in (WP-1216)", () => {
  /** Every geometry, so no group is asserted on one geometry's fields alone. */
  const GEOMETRIES = ["unstated", "debye_scherrer", "bragg_brentano",
                      "flat_plate_transmission"];
  const all = () => GEOMETRIES.flatMap((kind) => {
    const ins = instrument();
    ins.geometry.kind = kind;
    return instrumentFields(ins);
  });

  it("gives every field a group, and writes all three", () => {
    // Both ways, as `capabilities()`'s arms are: a field with no group would
    // be drawn in no grid at all, and a group nothing is in is a heading over
    // an empty section — the same claim-without-a-writer either way.
    expect(all().filter((f) => !f.group).map((f) => f.path)).toEqual([]);
    expect([...new Set(all().map((f) => f.group))].sort())
      .toEqual(["geometry", "profile", "source"]);
  });

  it("groups by what the field is, not by the prefix of its path", () => {
    const group = new Map(all().map((f) => [f.path, f.group]));
    // the two that disagree with their own prefix, which is the whole reason
    // this is data: the apertures shape the peak, the zero shift moves it
    expect(group.get("geometry.axial_sl")).toBe("profile");
    expect(group.get("geometry.axial_hl")).toBe("profile");
    expect(group.get("zero_shift")).toBe("geometry");
    expect(group.get("geometry.sample_displacement")).toBe("geometry");
    expect(group.get("source.polarization")).toBe("source");
  });

  it("draws U V W over X Y, and starts each profile row at its first cell", () => {
    const profile = instrumentFields(instrument())
      .filter((f) => f.group === "profile" && f.kind === "number");
    // the order *is* the layout: the grid has three fixed columns, so this list
    // read three at a time is what the user sees, and a reordering here moves X
    // out from under U with nothing else to notice
    expect(profile.map((f) => f.label))
      .toEqual(["U", "V", "W", "X", "Y", "S/L", "H/L"]);
    expect(profile.filter((f) => f.startsRow).map((f) => f.label))
      .toEqual(["U", "X", "S/L"]);
    // …and the second row is two wide because this profile has no Z
    expect(profile.map((f) => f.label).indexOf("S/L")).toBe(5);
  });
});

describe("axialWarning", () => {
  it("fires on the FCJ corner, and says when one of the pair is free", () => {
    const ins = instrument();
    expect(axialWarning(ins)).toMatch(/corner/);
    expect(axialWarning(ins)).not.toMatch(/at least one is free/);
    ins.geometry.axial_sl.vary = true;
    expect(axialWarning(ins)).toMatch(/at least one is free/);
    ins.geometry.axial_hl.value = 0.003;
    expect(axialWarning(ins)).toBe("");
  });

  it("says nothing about the equal pair that is not a hazard", () => {
    // both zero and both held is axial divergence *off*, which is every freshly
    // created lab instrument — warning there would be warning nobody reads
    const ins = instrument();
    ins.geometry.axial_sl.value = ins.geometry.axial_hl.value = 0;
    expect(axialWarning(ins)).toBe("");
    ins.geometry.axial_hl.vary = true;      // …but freeing one makes it live
    expect(axialWarning(ins)).toMatch(/corner/);
  });
});

describe("editableValue", () => {
  it("is the two refusals set_values makes, and not the third", () => {
    expect(editableValue(row("phases.0.cell.a"))).toBe(true);
    expect(editableValue(row("x", { locked: true }))).toBe(false);
    expect(editableValue(row("x", { tie: { sources: ["a"] } }))).toBe(false);
    // a mode-fixed row can still be *set*; it simply will not be varied
    expect(editableValue(row("x", { mode_fixed: true }))).toBe(true);
    expect(editableValue(undefined)).toBe(true);
  });
});

describe("atomRows", () => {
  const rows = [row("phases.0.atoms.1.dof.0"), row("phases.0.atoms.0.biso"),
                row("phases.0.atoms.1.biso")];

  it("gives a fixed special position no coordinate control and a reason", () => {
    const [la, b] = atomRows(structure(), SITES, rows);
    expect(la.dofs).toEqual([]);
    expect(la.frozen).toMatch(/fully fixed special position/);
    expect(la.frozen).toContain("48");
    expect(b.frozen).toBe("");
    expect(b.dofs.map((r) => r.path)).toEqual(["phases.0.atoms.1.dof.0"]);
    expect(b.xyz).toEqual([0.1993, 0.5, 0.5]);
  });

  it("survives a site arm that has not caught up with an added atom", () => {
    const grown = withAtom(structure(), 0, newAtom("O1", "O", [0.25, 0.25, 0.25]));
    const [, , added] = atomRows(grown, SITES, rows);
    expect(added.site).toBeNull();
    expect(added.dofs).toEqual([]);
    expect(added.frozen).toBe("");
  });
});

describe("positionEdits", () => {
  const edits = (obj: Record<string, string>) => new Map(Object.entries(obj));

  it("fills the axes the user did not touch from the model", () => {
    // the route takes a whole position because the projection is a whole
    // position: a `[1 1 0]` site cannot answer "what should x be" without y
    const delta = positionEdits(structure(), 0,
                                edits({ "phases.0.atoms.1.x": "0.21" }));
    expect(delta.moves).toEqual([
      { atom: "phases.0.atoms.1", xyz: [0.21, 0.5, 0.5] }]);
    expect(delta.touched).toBe(1);
    expect(delta.invalid).toEqual([]);
  });

  it("is not a move when the coordinate is retyped as it is shown", () => {
    // against what the cell *shows*, like `splitEdits` — otherwise every
    // rounded display would send a tiny move on Apply
    const delta = positionEdits(structure(), 0,
                                edits({ "phases.0.atoms.1.x": xyzText(0.1993) }));
    expect(delta.moves).toEqual([]);
    expect(delta.touched).toBe(1);      // …but it *was* touched
    expect(xyzText(0.1993)).toBe("0.19930");
  });

  it("keeps the stored precision of an axis retyped as it was shown", () => {
    // the cell shows five places and the model holds more, so an axis the user
    // clicked into and typed back contributes the *stored* value: pushing the
    // rounded one would move a coordinate nobody changed by up to 5e-6, which
    // is five times `POSITION_TOL` and can turn a reachable position into a
    // refusal on a constrained site
    const s = structure();
    s.phases[0].atoms[1].x.value = 0.199317;
    expect(xyzText(0.199317)).toBe("0.19932");
    const delta = positionEdits(s, 0, edits({
      "phases.0.atoms.1.x": "0.19932", "phases.0.atoms.1.z": "0.55",
    }));
    expect(delta.moves).toEqual([
      { atom: "phases.0.atoms.1", xyz: [0.199317, 0.5, 0.55] }]);
  });

  it("groups three typed axes into one move, in atom order", () => {
    const delta = positionEdits(structure(), 0, edits({
      "phases.0.atoms.1.z": "0.55",
      "phases.0.atoms.0.x": "0.01",
      "phases.0.atoms.1.x": "0.21",
      "phases.0.atoms.1.y": "0.52",
    }));
    expect(delta.moves).toEqual([
      { atom: "phases.0.atoms.0", xyz: [0.01, 0, 0] },
      { atom: "phases.0.atoms.1", xyz: [0.21, 0.52, 0.55] },
    ]);
    expect(delta.touched).toBe(4);
  });

  it("refuses text that is not a number, and sends nothing for that atom", () => {
    const delta = positionEdits(structure(), 0, edits({
      "phases.0.atoms.1.x": "0.21", "phases.0.atoms.1.y": "half",
    }));
    expect(delta.moves).toEqual([]);            // the whole position, or none
    expect(delta.invalid).toEqual([
      { path: "phases.0.atoms.1.y", why: "a coordinate is a number" }]);
    expect(delta.touched).toBe(2);
    // an emptied cell is the same refusal — a blank is not zero
    expect(positionEdits(structure(), 0,
                         edits({ "phases.0.atoms.1.x": "  " })).invalid)
      .toHaveLength(1);
  });

  it("ignores edits belonging to another phase, and to an atom that is gone", () => {
    const delta = positionEdits(structure(), 0, edits({
      "phases.1.atoms.0.x": "0.3",       // another phase
      "phases.0.atoms.9.x": "0.3",       // removed since it was typed
      "phases.0.atoms.1.biso": "0.4",    // not a coordinate at all
    }));
    expect(delta.moves).toEqual([]);
    expect(delta.touched).toBe(0);
  });

  it("does not decide whether the site can reach the position", () => {
    // the projection is the server's, and a second copy of the DOF basis here
    // is the trap `symbolChanged` names: `y` is locked on this site, and this
    // still sends it, because the refusal that comes back names the nearest
    // reachable position and this could not
    const delta = positionEdits(structure(), 0,
                                edits({ "phases.0.atoms.1.y": "0.6" }));
    expect(delta.moves).toEqual([
      { atom: "phases.0.atoms.1", xyz: [0.1993, 0.6, 0.5] }]);
  });
});

describe("adding and removing an atom", () => {
  it("returns a new structure and leaves the old one alone", () => {
    const before = structure();
    const grown = withAtom(before, 0, newAtom("O1", "O"));
    expect(grown.phases[0].atoms).toHaveLength(3);
    expect(before.phases[0].atoms).toHaveLength(2);
    expect(grown.phases[0].atoms[2].species).toBe("O");
    const shrunk = withoutAtom(grown, 0, 0);
    expect(shrunk.phases[0].atoms.map((a: any) => a.label)).toEqual(["B", "O1"]);
  });

  it("places a new atom where it was asked for, since that decides its DOFs", () => {
    const atom = newAtom("O1", "O", [0.25, 0.5, 0]);
    expect([atom.x.value, atom.y.value, atom.z.value]).toEqual([0.25, 0.5, 0]);
    expect(atom.occ.value).toBe(1);
  });
});
