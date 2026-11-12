/** The New project dialog's logic: previews first, one create (WP-1014, WP-2131).
 *
 * The flow is two-phase by construction: the pattern, each phase and an
 * instrument profile are *previewed* first and only tokens are committed. What
 * is left here is the bookkeeping between the rows and the one judgement the
 * client is allowed to make: whether the project can be created yet, and if not,
 * what is missing. `blocked()` returns that sentence; nothing here decides
 * anything the server would decide differently.
 *
 * The round-9 design (the maintainer, 2026-11-08) is one dialog of four rows:
 * Pattern, Phases, Instrument, Project. Mode and plan are not asked: a typed
 * cell has no atoms, so a project holding one is created in Le Bail mode, every
 * other project in Rietveld mode, and the plan is the default (`modeFor`).
 *
 * The instrument row sends a **decision**, not a model: a geometry and (for a
 * lab instrument) an anode name. The package owns the physics that follows: the
 * emission wavelengths come from its NIST-scale table (WP-0507), the doublet from
 * the anode, the polarization constant from the monochromator angle. With
 * nothing better known the decision is Bragg-Brentano with a Cu Kα1/Kα2 anode,
 * and the row says it was assumed (`InstrumentSource`).
 *
 * Which cell parameters a typed symbol leaves free is crystallography, so the
 * form asks `GET /api/spacegroup` and draws the boxes it names (WP-1206).
 *
 * `PRESET_FIELDS` is held to the constructors' own signatures across the language
 * boundary by `tests/data/gui/instrument_presets.json`, the same device the glob
 * corpus uses: written from `gui.imports.INSTRUMENT_PRESETS` by pytest, replayed
 * by `wizard.test.ts`. A field this form offers that the constructor does not
 * take is a control whose only outcome is a 400.
 *
 */

export type PresetFieldKind = "number" | "optnumber" | "anode";

export interface PresetField {
  name: string;
  label: string;
  kind: PresetFieldKind;
  unit?: string;
  /** prefilled when the step opens; "" means "leave it to the constructor" */
  initial?: string;
}

/**
 * The corpus key that describes one preset field (WP-1203).
 *
 * Derived from the field's own name, not stored beside it: the
 * `instrument_fields` arm is keyed by the union of `INSTRUMENT_PRESETS`, which
 * is the same list `PRESET_FIELDS` is already held to across the language
 * boundary, so a second list could only be a way for the two to disagree.
 *
 * `packing_fraction` was the field WP-1032 was reported against — offered in
 * three places with no `title` in any of them, on a form whose only help
 * mechanism *was* `title=`.  It has an entry now, and so does every other
 * field here, crossed both ways by `tests/test_help.py`.
 */
export function presetHelp(field: PresetField): string {
  return `instrument_fields:${field.name}`;
}

/** The three geometries, and the arguments each one takes. */
export const PRESET_FIELDS: Record<string, PresetField[]> = {
  debye_scherrer: [
    { name: "wavelength", label: "wavelength", kind: "number", unit: "Å" },
    { name: "polarization", label: "polarization", kind: "optnumber" },
    { name: "goniometer_radius_mm", label: "radius", kind: "optnumber", unit: "mm" },
    { name: "capillary_radius_mm", label: "capillary r", kind: "optnumber",
      unit: "mm" },
    { name: "mu_r", label: "µR", kind: "optnumber" },
    { name: "packing_fraction", label: "packing", kind: "optnumber" },
  ],
  bragg_brentano: [
    { name: "radiation", label: "anode", kind: "anode", initial: "CuKa" },
    { name: "goniometer_radius_mm", label: "radius", kind: "optnumber", unit: "mm" },
    { name: "monochromator_two_theta", label: "2θ monochromator", kind: "optnumber",
      unit: "°" },
    { name: "ka2_ratio", label: "Kα2/Kα1", kind: "optnumber" },
    { name: "mu_t", label: "µt", kind: "optnumber" },
    { name: "thickness_mm", label: "thickness", kind: "optnumber", unit: "mm" },
  ],
  flat_plate_transmission: [
    { name: "radiation", label: "anode", kind: "anode", initial: "CuKa1" },
    { name: "mu_t", label: "µt", kind: "optnumber" },
    { name: "thickness_mm", label: "thickness", kind: "optnumber", unit: "mm" },
    { name: "packing_fraction", label: "packing", kind: "optnumber" },
    { name: "ka2_ratio", label: "Kα2/Kα1", kind: "optnumber" },
  ],
};

export const PRESET_TITLES: Record<string, string> = {
  debye_scherrer: "Capillary / synchrotron (Debye-Scherrer)",
  bragg_brentano: "Lab flat plate, reflection (Bragg-Brentano)",
  flat_plate_transmission: "Flat plate, transmission",
};

/** One phase of a new project: a staged CIF, or a typed symbol and cell. */
export type NewPhase =
  | { kind: "cif"; preview: any; aniso: boolean }
  | { kind: "cell"; symbol: string; facts: any; cell: Record<string, number> };

/** The Space group and cell form while it is open, before Add. */
export interface CellDraft {
  symbol: string;
  /** `GET /api/spacegroup`'s answer for the symbol, or null before it resolves */
  facts: any | null;
  /** what the symbol could not be resolved as, or "" */
  error: string;
  /** the free cell parameters as typed, keyed by name */
  cell: Record<string, string>;
}

/**
 * Where the instrument row's decision came from, which its tag says.
 *
 * `assumed` is the round-9 fallback: Bragg-Brentano with a Cu Kα1/Kα2 anode,
 * marked so, because a wrong anode shifts every refined cell and an unmarked
 * default reads as something the file said. `header` is what the pattern
 * file's own header named (`imports.suggest_instrument`), and `user` anything
 * a person changed in the form. A saved profile names its own file.
 */
export type InstrumentSource = "assumed" | "header" | "user";

export interface WizardState {
  /** `POST /api/upload/pattern`'s answer, or null before a file is chosen */
  pattern: any | null;
  /** the reader keywords this format offers, by name: `block`, `scan`, … */
  readerOptions: Record<string, string>;
  phases: NewPhase[];
  cellDraft: CellDraft | null;
  /** an uploaded instrument profile takes precedence over the preset form */
  instrument: any | null;
  preset: string;
  values: Record<string, string>;
  source: InstrumentSource;
  /** the project's name without `.rex`, and the folder it is made in */
  name: string;
  where: string;
  /** whether a person typed each, so a later pattern no longer moves it */
  nameSet: boolean;
  whereSet: boolean;
}

export function emptyWizard(): WizardState {
  return seedPreset({ pattern: null, readerOptions: {}, phases: [], cellDraft: null,
                      instrument: null, preset: "bragg_brentano", values: {},
                      source: "assumed", name: "", where: "", nameSet: false,
                      whereSet: false },
                    "bragg_brentano");
}

/**
 * Switch preset, filling in the initial values the form will *show*.
 *
 * Seeded rather than left blank so the anode the select displays is the anode the
 * body carries.  Leaving it unset would also work — the constructor's default is
 * `CuKa` — and that is exactly the problem: the form would be showing a value it
 * was not sending, and the two would agree only for as long as nobody changed the
 * default.
 */
export function seedPreset(state: WizardState, preset: string): WizardState {
  const values = { ...state.values };
  for (const field of PRESET_FIELDS[preset] ?? []) {
    if (field.initial && values[field.name] === undefined) {
      values[field.name] = field.initial;
    }
  }
  return { ...state, preset, values };
}

/**
 * Pre-fill the instrument form from what the pattern file already knows.
 *
 * The *matching* happened on the server (`imports.suggest_instrument`), because
 * deciding that 1.5418 Å is a Cu doublet is a physics judgement against the
 * package's radiation table and a copy of that table in TypeScript would be a
 * second authority on wavelengths. What arrives here is already a decision, so
 * this only has to seed the form with it — and a `null` hint (the header
 * contradicts itself) leaves the form exactly as it was, because a wrong
 * pre-fill is worse than an empty one: it looks like it was read.
 */
export function applyInstrumentHint(state: WizardState, hint: any): WizardState {
  if (!hint || typeof hint !== "object" || !PRESET_FIELDS[hint.preset]) return state;
  const seeded = seedPreset({ ...state, values: { ...state.values } }, hint.preset);
  const values = { ...seeded.values };
  for (const field of PRESET_FIELDS[hint.preset]) {
    if (hint[field.name] !== undefined && hint[field.name] !== null) {
      values[field.name] = String(hint[field.name]);
    }
  }
  return { ...seeded, values };
}

/** How many measurements the staged pattern holds — 1 when it does not say.
 *
 * From the preview's own metadata, which the single read already carried, so
 * asking costs nothing. What each scan *is* costs a second walk and is fetched
 * separately, only when someone opens the picker.
 */
export function scanCount(pattern: any): number {
  const n = Number(pattern?.metadata?.scan_count);
  return Number.isFinite(n) && n > 0 ? n : 1;
}

/** The preset arguments, empty fields dropped and numbers made numbers.
 *
 * Dropping an empty field rather than sending `null` is the point: every one of
 * these has a constructor default that is a *decision* (217.5 mm, 0.5, no
 * monochromator, no thickness), and sending null would overwrite it with
 * something nobody chose — which for `mu_t` is not even a legal instrument.
 */
export function presetSpec(state: WizardState): Record<string, unknown> {
  const spec: Record<string, unknown> = { preset: state.preset };
  for (const field of PRESET_FIELDS[state.preset] ?? []) {
    const text = (state.values[field.name] ?? "").trim();
    if (!text) continue;
    spec[field.name] = field.kind === "anode" ? text : Number(text);
  }
  return spec;
}

/** The instrument argument: an uploaded profile if there is one, else the form. */
export function instrumentArgument(state: WizardState): Record<string, unknown> {
  return state.instrument
    ? { upload: state.instrument.upload }
    : presetSpec(state);
}

/**
 * Take a staged pattern, and the defaults it brings.
 *
 * The name and the folder follow the file until a person types either, from
 * the preview's `suggested_project`: a browser upload carries a file's name
 * and never its folder, so the place is the server's suggestion rather than
 * the pattern's own folder the round-9 design names. The instrument hint
 * seeds the form only while it is still the assumed fallback, so a person's
 * choice is never overwritten by a second file.
 */
export function absorbPattern(state: WizardState, preview: any,
                              fresh = true): WizardState {
  let next: WizardState = { ...state, pattern: preview,
    readerOptions: { ...(preview?.reader_options ?? {}) } };
  const suggested = String(preview?.suggested_project ?? "");
  const cut = lastSeparator(suggested);
  if (!next.nameSet) {
    next.name = (cut >= 0 ? suggested.slice(cut + 1) : suggested).replace(/\.rex$/, "");
  }
  if (!next.whereSet && cut > 0) next.where = suggested.slice(0, cut);
  if (fresh && next.source !== "user" && !next.instrument) {
    // A header-seeded form belongs to the file that seeded it: a replacement
    // pattern re-seeds it from its own header, or falls back to the assumed
    // default, so the tag never names a header this file does not have.
    const base = seedPreset({ ...next, values: {} }, "bragg_brentano");
    const hinted = preview?.instrument_hint
      ? applyInstrumentHint(base, preview.instrument_hint) : base;
    if (hinted !== base) next = { ...hinted, source: "header" };
    else if (next.source === "header") next = { ...base, source: "assumed" };
  }
  return next;
}

/** The last path separator in a server path, `/` or a Windows `\`; -1 if none. */
export function lastSeparator(path: string): number {
  return Math.max(path.lastIndexOf("/"), path.lastIndexOf("\\"));
}

/** The cell parameters the open cell form draws, in the server's own order. */
export function freeCellFields(draft: CellDraft | null): string[] {
  const free = draft?.facts?.free_cell;
  return Array.isArray(free) ? free.map(String) : [];
}

/** Why the open cell form cannot be added yet, or "". */
export function cellBlocked(draft: CellDraft | null): string {
  if (!draft) return "";
  const symbol = draft.symbol.trim();
  if (!symbol) return "Type a space-group symbol.";
  if (draft.error) return draft.error;
  // the boxes drawn are the last resolved symbol's: an edited symbol not yet
  // looked up would send its free parameters under the new one
  if (draft.facts && String(draft.facts.space_group ?? "").trim() !== symbol) {
    return `Looking up ${symbol}…`;
  }
  const free = freeCellFields(draft);
  if (!free.length) return "Type a space-group symbol.";
  for (const name of free) {
    const text = (draft.cell[name] ?? "").trim();
    if (!text) return `${symbol} needs ${free.join(", ")}.`;
    if (!Number.isFinite(Number(text))) return `${name} is not a number.`;
    if (Number(text) <= 0) return `${name} must be greater than zero.`;
  }
  return "";
}

/** Add the open cell form as a phase, if it is complete. */
export function addTypedCell(state: WizardState): WizardState {
  const draft = state.cellDraft;
  if (!draft || cellBlocked(draft)) return state;
  const cell: Record<string, number> = {};
  for (const name of freeCellFields(draft)) cell[name] = Number(draft.cell[name].trim());
  return { ...state, cellDraft: null, phases: [...state.phases,
    { kind: "cell", symbol: draft.symbol.trim(), facts: draft.facts, cell }] };
}

/**
 * Le Bail when a phase is a typed cell, else Rietveld.
 *
 * A typed cell carries no atoms, so `rietveld` is not a mode it can be created
 * in: the server refuses it (WP-1206), and the dialog makes the refusal
 * unreachable. With a CIF beside it the project is still Le Bail, the only
 * mode in which both are legal. With no phase the mode governs nothing, and
 * adopting an indexed cell sets it.
 */
export function modeFor(state: WizardState): string {
  return state.phases.some((p) => p.kind === "cell") ? "lebail" : "rietveld";
}

function phaseArgument(phase: NewPhase): Record<string, unknown> {
  return phase.kind === "cell"
    ? { space_group: phase.symbol, cell: phase.cell }
    : { upload: phase.preview?.upload, aniso: phase.aniso };
}

/**
 * The `structure` argument: `null` with no phase, one form, or a list.
 *
 * `null` is the pattern-only project, which the server reads as an answer
 * rather than as a missing key (WP-1207). Several phases go as a list of the
 * single forms (WP-2131).
 */
export function structureArgument(state: WizardState): unknown {
  if (!state.phases.length) return null;
  const forms = state.phases.map(phaseArgument);
  return forms.length === 1 ? forms[0] : forms;
}

/** Where the project is made: the folder, the name, `.rex`. */
export function projectPath(state: WizardState): string {
  const where = state.where.trim().replace(/[/\\]+$/, "");
  const name = state.name.trim().replace(/\.rex$/, "");
  return `${where}/${name}.rex`;
}

/** The `POST /api/project/new` body: tokens, never staged paths, and no plan. */
export function createBody(state: WizardState): Record<string, unknown> {
  const body: Record<string, unknown> = {
    path: projectPath(state),
    pattern: { upload: state.pattern?.upload },
    structure: structureArgument(state),
    instrument: instrumentArgument(state),
    mode: modeFor(state),
  };
  const options = Object.fromEntries(
    Object.entries(state.readerOptions).filter(([, v]) => v !== ""));
  if (Object.keys(options).length) body.reader_options = options;
  return body;
}

/** Why this cannot be created yet, or "": one sentence, naming the row. */
export function blocked(state: WizardState): string {
  if (!state.pattern) return "Choose a pattern file.";
  if (state.cellDraft) return "Add the typed cell, or cancel it.";
  if (!state.instrument) {
    for (const field of PRESET_FIELDS[state.preset] ?? []) {
      const text = (state.values[field.name] ?? "").trim();
      if (field.kind === "number" && !text) {
        return `${SHORT_TITLES[state.preset]} needs a ${field.label}.`;
      }
      if (text && field.kind !== "anode" && !Number.isFinite(Number(text))) {
        return `${field.label} is not a number.`;
      }
    }
  }
  if (!state.name.trim()) return "Name the project.";
  if (/[/\\]/.test(state.name.trim())) return "A project name has no slash in it.";
  if (!state.where.trim()) return "Choose where the project goes.";
  return "";
}

/** The geometries as the instrument row's summary names them. */
export const SHORT_TITLES: Record<string, string> = {
  debye_scherrer: "Debye-Scherrer",
  bragg_brentano: "Bragg-Brentano",
  flat_plate_transmission: "Transmission",
};

/** An anode name as a line list: `CuKa` is Cu Kα1/Kα2, `CuKa1` is Cu Kα1. */
export function anodeLabel(name: string): string {
  const m = /^([A-Z][a-z]?)Ka(1?)$/.exec(name);
  return m ? `${m[1]} Kα1${m[2] ? "" : "/Kα2"}` : name;
}

/** The instrument row's one line: the geometry and the source's lines. */
export function instrumentSummary(state: WizardState): string {
  if (state.instrument) {
    const s = state.instrument.summary ?? {};
    const lam = (s.wavelengths ?? []).map((w: number) => w.toFixed(5)).join(", ");
    return `${s.geometry ?? "saved profile"}${lam ? ` · λ ${lam} Å` : ""}`;
  }
  const geometry = SHORT_TITLES[state.preset] ?? state.preset;
  if (state.preset === "debye_scherrer") {
    const lam = (state.values.wavelength ?? "").trim();
    return `${geometry} · ${lam ? `λ ${lam} Å` : "no wavelength yet"}`;
  }
  return `${geometry} · ${anodeLabel(state.values.radiation ?? "")}`;
}

/** The tag beside that line, saying where the decision came from. */
export function sourceTag(state: WizardState): string {
  if (state.instrument) return `from ${state.instrument.filename}`;
  return state.source === "assumed" ? "assumed"
    : state.source === "header" ? "from the file's header" : "";
}

/** A staged pattern in rietx's words: reader, points, range and step, esds. */
export function patternSummary(preview: any): string {
  if (!preview) return "";
  const [lo, hi] = (preview.two_theta_range ?? [0, 0]).map(Number);
  const step = preview.step ? `, step ${Number(Number(preview.step).toPrecision(4))}°` : "";
  return `${preview.format.title} · ${preview.n_points} points · `
    + `2θ ${lo.toFixed(2)}–${hi.toFixed(2)}°${step} · `
    + `esd ${preview.has_sigma ? "from the file" : "from counts"}`;
}

/** A staged CIF's first phase on one line: name, symbol, cell edges, atoms. */
export function structureSummary(preview: any): string {
  if (!preview) return "";
  const phase = preview.phases?.[0];
  if (!phase) return "";
  const cell = phase.cell.slice(0, 3).map((v: number) => v.toFixed(4)).join(" ");
  return `${phase.name} · ${phase.space_group} · ${cell} Å · `
    + `${phase.n_atoms} atoms (${phase.species.join(", ")})`;
}

/**
 * Whether the instrument form shows a field before Advanced is opened.
 *
 * The round-9 form asks for the geometry, the source and the goniometer
 * radius. Every other preset argument has a constructor default that suits
 * most specimens, so it waits under Advanced (settled by Claude, reversible:
 * the alternative is the whole preset form at once).
 */
export function basicField(field: PresetField): boolean {
  return field.kind !== "optnumber" || field.name === "goniometer_radius_mm";
}

/**
 * A preview curve as one SVG path, with intensity drawn on a square-root axis.
 *
 * The square root is the round-9 design's: on a linear axis a pattern's weak
 * lines vanish beside its strongest one at a 34 px height.
 */
export function sparkline(curve: any, width = 260, height = 34): string {
  const xs: number[] = curve?.two_theta ?? [];
  const ys: number[] = (curve?.intensity ?? []).map((y: number) => Math.sqrt(Math.max(y, 0)));
  if (xs.length < 2) return "";
  const x0 = xs[0], x1 = xs[xs.length - 1];
  const lo = Math.min(...ys), hi = Math.max(...ys);
  const span = hi - lo || 1;
  return xs.map((x, i) => {
    const px = ((x - x0) / (x1 - x0 || 1)) * width;
    const py = height - ((ys[i] - lo) / span) * height;
    return `${i ? "L" : "M"}${px.toFixed(1)},${py.toFixed(1)}`;
  }).join(" ");
}
