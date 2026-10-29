/** WP-1045 — the indexing control surface: one spec, rendered.
 *
 * The field inventory here is held against the committed corpus
 * (`tests/data/gui/index_controls.json`, written by
 * `tests/test_search_controls.py` from the live `SearchSpecSpec`) by
 * `controls.test.ts` — the fnmatch-corpus mechanism: python owns the model
 * and the vocabularies, this file proves the form can state every field.  A
 * field added to the model shows up as a vitest failure here until the form
 * states it, which is the GUI's leg of the three-chair bijection.
 *
 * Values come from `ProjectDoc.indexing` **verbatim** — the server serves the
 * block complete (pydantic defaults filled), so this file carries no second
 * copy of any default.  Vocabularies (engines, systems, centrings, presets,
 * shift templates) come from `/api/capabilities`, never from literals.
 */

export interface SearchValues {
  systems: string[] | null;
  centrings: Record<string, string[]> | null;
  min_d_axis: number;
  max_d_axis: number;
  min_volume: number;
  max_volume: number | null;
  n_unindexed: number;
  n_search_lines: number;
  k_sigma: number;
  shift_allowance_deg: number;
  shift_template: string | null;
  budget_seconds: number;
  total_budget_seconds: number | null;
  preset: string | null;
  max_candidates: number;
  seed: number;
  prior_cells: number[][] | null;
  prior_spacegroups: string[] | null;
}

export interface IndexingControls {
  search: SearchValues;
  engines: string[] | null;
  validate_candidates: boolean;
  check_top: number | null;
}

/** How one control is stated in the form. */
export interface ControlField {
  name: string;
  /** which widget states it — every kind is rendered by the panel */
  kind:
    | "systems"        // checkbox per crystal system, with centring chips
    | "centrings"      // stated inside the systems widget, per system
    | "number"         // a float input
    | "int"            // an integer input
    | "select"         // a vocabulary select (preset, shift template)
    | "prior_cells"    // the analogue-cell list editor
    | "list"           // comma-separated names (prior space groups)
    | "engines"        // checkbox per registered engine
    | "toggle";        // a checkbox
  label: string;
  /** null/absent means "package default" and is sent as null */
  optional?: boolean;
}

/** The corpus key that describes one control (WP-1203).
 *
 * Derived from the field's own name rather than stored beside it: the arm is
 * keyed by `IndexingControls` flattened one level, which is the same
 * vocabulary this inventory states, so a second list would only be a way for
 * the two to disagree.  The prose these fields used to carry as `title=` is
 * now `rietx.help.SEARCH_FIELD_HELP` — moved rather than rewritten, because
 * the form was the only place several of those measurements were written
 * down.
 */
export function searchHelp(field: ControlField): string {
  return `search_fields:${field.name}`;
}

/** Every `SearchSpecSpec` field, in display order. */
export const SEARCH_FIELDS: ControlField[] = [
  { name: "systems", kind: "systems", label: "crystal systems" },
  { name: "centrings", kind: "centrings", label: "centrings" },
  { name: "preset", kind: "select", label: "preset", optional: true },
  { name: "total_budget_seconds", kind: "number", label: "total budget (s)",
    optional: true },
  { name: "budget_seconds", kind: "number", label: "budget / slice (s)" },
  { name: "min_d_axis", kind: "number", label: "min axis (Å)" },
  { name: "max_d_axis", kind: "number", label: "max axis (Å)" },
  { name: "min_volume", kind: "number", label: "min volume (Å³)" },
  { name: "max_volume", kind: "number", label: "max volume (Å³)", optional: true },
  { name: "n_unindexed", kind: "int", label: "unindexed allowed" },
  { name: "n_search_lines", kind: "int", label: "search lines" },
  { name: "k_sigma", kind: "number", label: "k·σ window" },
  { name: "shift_allowance_deg", kind: "number", label: "shift allowance (°)" },
  { name: "shift_template", kind: "select", label: "shift template", optional: true },
  { name: "max_candidates", kind: "int", label: "max candidates" },
  { name: "seed", kind: "int", label: "seed" },
  { name: "prior_cells", kind: "prior_cells", label: "analogue cells" },
  { name: "prior_spacegroups", kind: "list", label: "analogue space groups" },
];

/** The `IndexingControls` fields beside `search`, in display order. */
export const CONTROL_FIELDS: ControlField[] = [
  { name: "engines", kind: "engines", label: "engines" },
  { name: "validate_candidates", kind: "toggle", label: "whole-profile validation" },
  { name: "check_top", kind: "int", label: "check top", optional: true },
];

/** The names this form states, for the corpus test. */
export function statedFieldNames(): { search: string[]; controls: string[] } {
  return {
    search: SEARCH_FIELDS.map((f) => f.name),
    controls: CONTROL_FIELDS.map((f) => f.name),
  };
}

/** `doc.indexing` verbatim — the server serves the block complete. */
export function controlsFromDoc(doc: any): IndexingControls | null {
  return doc?.indexing ?? null;
}

/** Parse an "a b c α β γ" line into a prior cell, or return the complaint. */
export function parsePriorCell(text: string): number[] | string {
  const parts = text.trim().split(/[\s,]+/).filter(Boolean).map(Number);
  if (parts.length !== 6 || parts.some((v) => !Number.isFinite(v))) {
    return "a prior cell is six numbers: a b c α β γ";
  }
  const [a, b, c, al, be, ga] = parts;
  if (Math.min(a, b, c) <= 0) return "axes must be positive";
  if ([al, be, ga].some((x) => x <= 0 || x >= 180)) {
    return "angles must lie in (0, 180)°";
  }
  return parts;
}

/** `4.7594 4.7594 12.9917 · 90 90 120` — the chip text for one prior cell. */
export function priorCellText(cell: readonly number[]): string {
  const lengths = cell.slice(0, 3).map((v) => Number(v.toPrecision(6)));
  const angles = cell.slice(3, 6).map((v) => Number(v.toPrecision(5)));
  return `${lengths.join(" ")} · ${angles.join(" ")}`;
}

/** A short digest for the collapsed summary line. */
export function controlsDigest(controls: IndexingControls | null,
                               defaultPreset: string): string {
  if (!controls) return "";
  const s = controls.search;
  const bits: string[] = [];
  bits.push(s.total_budget_seconds != null ? "custom budget"
    : (s.preset ?? defaultPreset));
  if (controls.engines?.length) bits.push(`${controls.engines.length} engine${controls.engines.length === 1 ? "" : "s"}`);
  if (s.systems?.length) bits.push(`${s.systems.length} system${s.systems.length === 1 ? "" : "s"}`);
  const priors = (s.prior_cells?.length ?? 0) + (s.prior_spacegroups?.length ?? 0);
  if (priors) bits.push(`${priors} prior${priors === 1 ? "" : "s"}`);
  if (!controls.validate_candidates) bits.push("no validation");
  return bits.join(" · ");
}

/** One streamed per-system shortlist (WP-1042's `consensus:<system>` unit),
 * newest per system, in the order systems completed. */
export interface SystemSnapshot {
  system: string;
  n_candidates: number;
  candidates: Array<Record<string, any>>;
}

export function foldSnapshots(datas: ReadonlyArray<Record<string, any>>
                              ): SystemSnapshot[] {
  const bySystem = new Map<string, SystemSnapshot>();
  for (const d of datas) {
    if (!d?.consensus || typeof d.system !== "string") continue;
    bySystem.delete(d.system);
    bySystem.set(d.system, {
      system: d.system,
      n_candidates: Number(d.n_candidates ?? d.candidates?.length ?? 0),
      candidates: d.candidates ?? [],
    });
  }
  return [...bySystem.values()];
}
