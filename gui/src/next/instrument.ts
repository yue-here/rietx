/**
 * The Instrument dialog's rules (WP-2218, inventory rows 133-136), kept pure so
 * they are asserted without a DOM.
 *
 * The dialog edits the open project's instrument, so its fields are today's
 * instrument form's (`lib/model.ts:instrumentFields`), never the New project
 * presets: a preset builds a whole new instrument, and sending one here would
 * reset every refined profile value. The dialog shows the source and geometry
 * groups and the axial pair, since the pair's warning sits beside it (row 136).
 * The other profile values are the Parameters tab's (row 135).
 */
import { at, clone, instrumentFields, validateField, writeField,
         type InstrumentField } from "../lib/model";

/** One anode of `GET /api/capabilities`. */
export interface Anode {
  name: string;
  wavelengths: number[];
}

/** The values a fit refines to place the peaks. They are the Parameters
 *  tab's (row 135), never the dialog's. */
const REFINED = new Set(["zero_shift", "geometry.sample_displacement",
                         "geometry.sample_transparency"]);

/** A constant-wavelength neutron source's one wavelength. The instrument
 *  form walks emission lines, and a neutron source has none. */
const NEUTRON_WAVELENGTH: InstrumentField = {
  path: "source.wavelength", label: "λ", kind: "number", unit: "Å", group: "source",
};

/** The fields the dialog draws for this instrument: every source and
 *  geometry field the model holds, less the refined ones, and the axial pair.
 *  A neutron source has no emission lines and no polarization, so those
 *  fields are absent. A constant-wavelength one draws its wavelength instead. */
export function dialogFields(model: any): InstrumentField[] {
  const fields = instrumentFields(model);
  if (model?.source?.kind === "neutron_cw") fields.unshift(NEUTRON_WAVELENGTH);
  return fields.filter((f) =>
    (f.group !== "profile" || f.path.startsWith("geometry.axial_"))
    && !REFINED.has(f.path) && at(model, f.path) !== undefined);
}

/** The fields one geometry refuses, by the schema's own validators: the
 *  capillary's on a flat plate, and the flat plate's on a capillary. */
const ONLY_ON: Record<string, string[]> = {
  debye_scherrer: ["mu_r", "capillary_radius_mm"],
  flat_plate: ["mu_t", "thickness_mm"],
};

/** Clear, in place, the drawn geometry fields the model's own geometry
 *  refuses, so a geometry switch does not fail on a field the dialog has just
 *  taken away. A valid model is left as it is. `geometryRefusal` names what
 *  else a switch can trip. */
export function clearForGeometry(model: any): any {
  const geometry = model?.geometry;
  if (!geometry) return model;
  const refused = geometry.kind === "debye_scherrer" ? ONLY_ON.flat_plate
    : ONLY_ON.debye_scherrer;
  for (const name of refused) if (geometry[name] != null) geometry[name] = null;
  return model;
}

/** Whether a capillary offset is in use. The schema refuses one on any
 *  other geometry, and one without a goniometer radius. */
function offsetInUse(offset: any): boolean {
  return !!offset && (Number(offset.value) !== 0 || !!offset.vary);
}

/**
 * Why the schema would refuse this geometry, in the dialog's words, or "".
 * These are the schema's other geometry validators, the ones a switch trips
 * on a value the dialog must not invent or does not draw: Bragg-Brentano's
 * radius, a surface-roughness block, and the capillary offsets. Clearing them
 * would discard what the project set, so the dialog says what stands in the way.
 */
export function geometryRefusal(model: any): string {
  const g = model?.geometry;
  if (!g) return "";
  if (g.kind === "bragg_brentano" && !g.goniometer_radius_mm) {
    return "Radius: Bragg-Brentano needs the goniometer radius";
  }
  if (g.surface_roughness != null && g.kind !== "bragg_brentano") {
    return "This project's surface roughness applies only to Bragg-Brentano";
  }
  const offsets = ["capillary_offset_along_beam", "capillary_offset_across_beam"]
    .filter((name) => offsetInUse(g[name]));
  if (offsets.length && g.kind !== "debye_scherrer") {
    return "The capillary offsets apply only to a capillary. "
      + "Set them to zero and fixed in the Parameters tab first";
  }
  if (offsets.length && !g.goniometer_radius_mm) {
    return "The capillary offsets need the goniometer radius";
  }
  return "";
}

/**
 * The model as the dialog's typed text would leave it: the geometry first,
 * since it decides which fields exist, then every field whose text is valid.
 * What the fields and the axial warning are read from.
 */
export function draftOf(model: any, edits: ReadonlyMap<string, string>): any {
  if (!model) return model;
  const kind = edits.get("geometry.kind");
  const next = clone(model);
  if (kind) next.geometry.kind = kind;
  clearForGeometry(next);
  for (const field of dialogFields(next)) {
    const text = edits.get(field.path);
    if (text === undefined || field.path === "geometry.kind") continue;
    if (!validateField(field, text)) writeField(next, field, text);
  }
  return next;
}

/** Two wavelengths agree when they differ by less than a part in 10⁴, so a
 *  wavelength quoted to four decimals (1.5405 Å) still names its anode. The
 *  Kα doublet's split is 25 times wider, so no two anodes agree. */
function same(a: number, b: number): boolean {
  return Math.abs(a - b) <= 1e-4 * Math.max(Math.abs(a), Math.abs(b));
}

const WAVELENGTH = /^instrument\.source\.lines\.\d+\.wavelength$/;

/**
 * The parameter rows the dialog treats as the table's. A wavelength is not
 * one of them: it travels in the whole model (gui/CLAUDE.md, WP-1014), since
 * an anode moves every line at once, and every line past the first is
 * force-fixed, so `set_values` would refuse it.
 */
export function dialogRows<R extends { path: string }>(rows: readonly R[]): R[] {
  return rows.filter((r) => !WAVELENGTH.test(r.path));
}

/** The anodes a source with `n` lines can switch to without adding or
 *  removing a line, which would change what the parameter table holds. */
export function anodeChoices(anodes: readonly Anode[], n: number): Anode[] {
  return anodes.filter((a) => a.wavelengths.length === n);
}

/** The anode whose lines these wavelengths are, or "" when they are typed. */
export function anodeOf(anodes: readonly Anode[], wavelengths: readonly number[]): string {
  const hit = anodes.find((a) => a.wavelengths.length === wavelengths.length
    && a.wavelengths.every((w, i) => same(w, wavelengths[i])));
  return hit?.name ?? "";
}

/**
 * The edits an anode choice makes: each line's wavelength, written only where
 * it differs from what the field shows, so choosing the anode already there
 * leaves nothing pending.
 */
export function withAnode(edits: ReadonlyMap<string, string>, anode: Anode,
                          shown: (path: string) => string): Map<string, string> {
  const next = new Map(edits);
  anode.wavelengths.forEach((w, i) => {
    const path = `source.lines.${i}.wavelength`;
    const current = Number(shown(path));
    if (Number.isFinite(current) && same(current, w)) next.delete(path);
    else next.set(path, String(w));
  });
  return next;
}
