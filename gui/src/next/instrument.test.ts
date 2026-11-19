import { describe, expect, it } from "vitest";

import { anodeChoices, anodeOf, clearForGeometry, dialogFields, dialogRows, draftOf,
         geometryRefusal, SHAPE_LABELS, withAnode } from "./instrument";

const p = (value: number, vary = false) => ({ value, vary });

/** A lab instrument as `GET /api/instrument` sends one: a Cu doublet on a flat plate. */
const lab = () => ({
  source: { kind: "xray_cw", polarization: p(0.8),
            lines: [{ wavelength: p(1.5405), weight: p(1) },
                    { wavelength: p(1.5443), weight: p(0.5) }] },
  geometry: { kind: "bragg_brentano", goniometer_radius_mm: 217.5, mu_t: null, thickness_mm: null,
              packing_fraction: 0.6, mu_r: null, capillary_radius_mm: null,
              sample_displacement: p(0), sample_transparency: p(0),
              axial_sl: p(0.02), axial_hl: p(0.02) },
  zero_shift: p(0),
  profile: { shape: "tchz_pv", u: p(0), v: p(0), w: p(0.01), x: p(0), y: p(0) },
});

const ANODES = [
  { name: "CoKa", wavelengths: [1.788996, 1.792835] },
  { name: "CuKa", wavelengths: [1.5405929, 1.54441] },
  { name: "CuKa1", wavelengths: [1.5405929] },
  { name: "MoKa1", wavelengths: [0.70931715] },
];

describe("the Instrument dialog's rules (WP-2218, rows 133-136)", () => {
  it("draws the source, the geometry and the peak shape, and leaves the refined values to Parameters", () => {
    const paths = dialogFields(lab()).map((f) => f.path);
    expect(paths).toEqual(expect.arrayContaining([
      "source.lines.0.wavelength", "source.lines.1.wavelength", "source.lines.1.weight",
      "source.polarization", "geometry.kind", "geometry.goniometer_radius_mm", "geometry.mu_t",
      "geometry.thickness_mm", "geometry.axial_sl", "geometry.axial_hl", "profile.shape"]));
    // the shape is a model choice, under Advanced, and every choice has a label
    const shape = dialogFields(lab()).find((f) => f.path === "profile.shape")!;
    expect(shape.advanced).toBe(true);
    expect(shape.choices!.map((c) => SHAPE_LABELS[c])).toEqual(["TCHZ pseudo-Voigt", "Voigt"]);
    for (const refined of ["zero_shift", "geometry.sample_displacement",
                           "geometry.sample_transparency", "profile.u"]) {
      expect(paths).not.toContain(refined);
    }
  });

  it("draws no field the model lacks: a neutron source has no lines and no polarization", () => {
    const neutron = { ...lab(), source: { kind: "neutron_cw", wavelength: p(1.6) } };
    const paths = dialogFields(neutron).map((f) => f.path);
    // its one wavelength instead, which the instrument form does not walk
    expect(paths.filter((x) => x.startsWith("source."))).toEqual(["source.wavelength"]);
    expect(paths).toContain("geometry.axial_sl");
    const tof = { ...lab(), source: { kind: "neutron_tof", difc: p(1000) } };
    expect(dialogFields(tof).map((f) => f.path).filter((x) => x.startsWith("source."))).toEqual([]);
  });

  it("names what else a geometry switch trips, rather than discarding it", () => {
    expect(geometryRefusal(lab())).toBe("");
    const capillary = lab();
    capillary.geometry.kind = "debye_scherrer";
    capillary.geometry.goniometer_radius_mm = null as any;
    expect(geometryRefusal(capillary)).toBe("");
    expect(geometryRefusal({ ...capillary, geometry: { ...capillary.geometry,
      kind: "bragg_brentano" } })).toMatch(/goniometer radius/);
    const rough = { ...lab().geometry, surface_roughness: { kind: "suortti" } };
    expect(geometryRefusal({ geometry: rough })).toBe("");
    expect(geometryRefusal({ geometry: { ...rough, kind: "flat_plate_transmission" } }))
      .toMatch(/surface roughness/);
    // an offset at zero and fixed is off, so it does not stand in the way
    const offset = { ...capillary.geometry, goniometer_radius_mm: 250,
                     capillary_offset_along_beam: p(0), capillary_offset_across_beam: p(0, true) };
    expect(geometryRefusal({ geometry: offset })).toBe("");
    expect(geometryRefusal({ geometry: { ...offset, kind: "bragg_brentano" } }))
      .toMatch(/capillary offsets apply only to a capillary/);
    expect(geometryRefusal({ geometry: { ...offset, goniometer_radius_mm: null } }))
      .toMatch(/need the goniometer radius/);
    expect(geometryRefusal({ geometry: { ...offset, capillary_offset_across_beam: p(0) } })).toBe("");
  });

  it("follows a geometry switch and clears the fields the new geometry refuses", () => {
    const capillary = lab();
    capillary.geometry.kind = "debye_scherrer";
    capillary.geometry.mu_r = 1.2 as any;
    const draft = draftOf(capillary, new Map([["geometry.kind", "bragg_brentano"],
                                              ["geometry.mu_t", "40"]]));
    expect(draft.geometry.kind).toBe("bragg_brentano");
    expect(draft.geometry.mu_r).toBeNull();
    expect(draft.geometry.mu_t).toBe(40);
    // the model handed in is not edited
    expect(capillary.geometry.kind).toBe("debye_scherrer");
    const plate = lab();
    plate.geometry.mu_t = 40 as any;
    expect(clearForGeometry({ ...plate, geometry: { ...plate.geometry, kind: "debye_scherrer" } })
      .geometry.mu_t).toBeNull();
    // a valid model is left as it is
    expect(clearForGeometry(plate).geometry.mu_t).toBe(40);
  });

  it("writes typed text into the draft the axial warning reads, and skips text that is not a number", () => {
    const draft = draftOf(lab(), new Map([["geometry.axial_sl", "0.03"], ["geometry.axial_hl", "x"]]));
    expect(draft.geometry.axial_sl.value).toBe(0.03);
    expect(draft.geometry.axial_hl.value).toBe(0.02);
  });

  it("names the anode of wavelengths quoted to four places, and offers only anodes with as many lines", () => {
    expect(anodeOf(ANODES, [1.5405, 1.5443])).toBe("CuKa");
    expect(anodeOf(ANODES, [1.5405])).toBe("CuKa1");
    expect(anodeOf(ANODES, [0.4139])).toBe("");
    // Kα1 and Kα2 are 25 times further apart than the tolerance
    expect(anodeOf(ANODES, [1.5443])).toBe("");
    expect(anodeChoices(ANODES, 2).map((a) => a.name)).toEqual(["CoKa", "CuKa"]);
    expect(anodeChoices(ANODES, 1).map((a) => a.name)).toEqual(["CuKa1", "MoKa1"]);
  });

  it("writes an anode's wavelengths where they differ, and nothing for the anode already there", () => {
    const shown = (path: string) => ({ "source.lines.0.wavelength": "1.5405",
                                       "source.lines.1.wavelength": "1.5443" } as any)[path];
    const co = withAnode(new Map(), ANODES[0], shown);
    expect([...co]).toEqual([["source.lines.0.wavelength", "1.788996"],
                             ["source.lines.1.wavelength", "1.792835"]]);
    expect([...withAnode(co, ANODES[1], shown)]).toEqual([]);
  });

  it("sends a wavelength in the model, never through set_values", () => {
    const rows = [{ path: "instrument.source.lines.0.wavelength" },
                  { path: "instrument.source.lines.1.wavelength" },
                  { path: "instrument.source.lines.1.weight" },
                  { path: "instrument.geometry.axial_sl" }];
    expect(dialogRows(rows).map((r) => r.path)).toEqual(
      ["instrument.source.lines.1.weight", "instrument.geometry.axial_sl"]);
  });
});
