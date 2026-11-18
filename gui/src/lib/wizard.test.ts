/**
 * The import wizard's logic, and the one cross-language pin it needs.
 *
 * The fixture is written by `tests/test_gui_server.py` from
 * `gui.imports.INSTRUMENT_PRESETS` — which is itself pinned to
 * `inspect.signature(Instrument.<preset>)` — so a field this form offers that
 * the constructor does not take fails here rather than as a 400 the first time
 * someone imports a project.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { GEOMETRIES, instrumentFields, phaseFields } from "./model";
import {
  PRESET_FIELDS,
  absorbPattern,
  addTypedCell,
  anodeLabel,
  applyInstrumentHint,
  basicField,
  blocked,
  cellBlocked,
  createBody,
  emptyWizard,
  freeCellFields,
  instrumentArgument,
  instrumentSummary,
  modeFor,
  patternSummary,
  presetHelp,
  presetSpec,
  projectPath,
  scanCount,
  sourceTag,
  sparkline,
  structureArgument,
  structureSummary,
  type CellDraft,
} from "./wizard";

const presets: Record<string, string[]> = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/instrument_presets.json",
                          import.meta.url)),
    "utf-8",
  ),
);

/** The corpus's key set, written from the live registry by
 *  `tests/test_gui_help.py` — the second cross-language pin this file needs
 *  now that the explanations live in `rietx.help` rather than beside the
 *  fields. */
const HELP_KEYS = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/help_keys.json",
                          import.meta.url)),
    "utf-8",
  ),
) as { keys: string[] };

const PATTERN = {
  upload: "p1", filename: "lab6.xy", n_points: 4200, two_theta_range: [10, 90],
  step: 0.02, has_sigma: true, suggested_project: "/data/lab6.rex",
  format: { name: "xy", title: "Two/three-column ASCII (.xy / .xye)" },
};

const CIF = {
  upload: "c1", filename: "lab6.cif",
  phases: [{ name: "LaB6", space_group: "P m -3 m", cell: [4.1566, 4.1566, 4.1566],
             n_atoms: 2, species: ["B", "La"] }],
};

/** `GET /api/spacegroup`'s answer for `R -3 c`, as the server sends it. */
const CORUNDUM = {
  space_group: "R -3 c", xhm: "R -3 c:H", crystal_system: "trigonal",
  setting: "R -3 c:H is trigonal on hexagonal axes",
  ties: { b: "a" }, fixed_angles: { alpha: 90, beta: 90, gamma: 120 },
  free_cell: ["a", "c"],
  constraints: "b = a \u00b7 \u03b1 = \u03b2 = 90\u00b0 \u00b7 \u03b3 = 120\u00b0",
};

/** A pattern and a CIF staged, the instrument still the assumed fallback. */
function staged(): ReturnType<typeof emptyWizard> {
  const state = absorbPattern(emptyWizard(), PATTERN);
  state.phases = [{ kind: "cif", preview: CIF, aniso: false }];
  return state;
}

function draft(cell: Record<string, string> = { a: "4.759091", c: "12.991779" }): CellDraft {
  return { symbol: "R -3 c", facts: CORUNDUM, error: "", cell };
}

describe("the preset forms are the constructors' arguments", () => {
  it("offers every argument each preset takes, and no others", () => {
    expect(Object.keys(PRESET_FIELDS).sort()).toEqual(Object.keys(presets).sort());
    for (const [name, args] of Object.entries(presets)) {
      const offered = PRESET_FIELDS[name].map((field) => field.name).sort();
      expect(offered, name).toEqual([...args].sort());
    }
  });
});

describe("presetSpec", () => {
  it("sends a decision, not a wavelength", () => {
    expect(presetSpec(staged())).toEqual({ preset: "bragg_brentano", radiation: "CuKa" });
  });

  it("drops empty fields rather than nulling a constructor default", () => {
    const state = staged();
    state.values = { radiation: "CuKa", goniometer_radius_mm: "", mu_t: "  " };
    expect(presetSpec(state)).toEqual({ preset: "bragg_brentano", radiation: "CuKa" });
  });

  it("makes numbers numbers and leaves an anode a name", () => {
    const state = staged();
    state.values = { radiation: "MoKa", goniometer_radius_mm: "240", ka2_ratio: "0.48" };
    expect(presetSpec(state)).toEqual({
      preset: "bragg_brentano", radiation: "MoKa",
      goniometer_radius_mm: 240, ka2_ratio: 0.48,
    });
  });

  it("prefers an uploaded profile over the form", () => {
    const state = staged();
    state.instrument = { upload: "i1" };
    expect(instrumentArgument(state)).toEqual({ upload: "i1" });
  });
});

describe("the instrument is assumed and says so (round 9)", () => {
  it("starts on Bragg-Brentano with a Cu doublet, tagged assumed", () => {
    const state = emptyWizard();
    expect(state.preset).toBe("bragg_brentano");
    expect(state.values.radiation).toBe("CuKa");
    expect(instrumentSummary(state)).toBe("Bragg-Brentano · Cu Kα1/Kα2");
    expect(sourceTag(state)).toBe("assumed");
  });

  it("takes the file's header and says it did", () => {
    const hint = { preset: "debye_scherrer", wavelength: 0.4139, why: "the header" };
    const state = absorbPattern(emptyWizard(), { ...PATTERN, instrument_hint: hint });
    expect(state.preset).toBe("debye_scherrer");
    expect(sourceTag(state)).toBe("from the file's header");
    expect(instrumentSummary(state)).toBe("Debye-Scherrer · λ 0.4139 Å");
  });

  it("re-seeds a header-seeded form from the replacement file's own header", () => {
    const mo = { preset: "bragg_brentano", radiation: "MoKa", why: "Mo" };
    const first = absorbPattern(emptyWizard(), { ...PATTERN, instrument_hint: mo });
    expect(first.values.radiation).toBe("MoKa");
    const second = absorbPattern(first, { ...PATTERN, instrument_hint: null });
    expect(sourceTag(second)).toBe("assumed");
    expect(second.values.radiation).toBe("CuKa");
  });

  it("splits a Windows suggestion on its backslashes", () => {
    const state = absorbPattern(emptyWizard(),
      { ...PATTERN, suggested_project: "C:\\Users\\me\\rietx\\lab6.rex" });
    expect(state.name).toBe("lab6");
    expect(state.where).toBe("C:\\Users\\me\\rietx");
    expect(blocked(state)).toBe("");
  });

  it("never lets a second file overwrite a person's choice", () => {
    const hint = { preset: "debye_scherrer", wavelength: 0.4139 };
    const state = { ...emptyWizard(), source: "user" as const };
    expect(absorbPattern(state, { ...PATTERN, instrument_hint: hint }).preset)
      .toBe("bragg_brentano");
  });

  it("names a saved profile by its file", () => {
    const state = staged();
    state.instrument = { upload: "i1", filename: "d8.json",
                         summary: { geometry: "bragg_brentano", wavelengths: [1.5406] } };
    expect(sourceTag(state)).toBe("from d8.json");
    expect(instrumentSummary(state)).toBe("bragg_brentano · λ 1.54060 Å");
  });

  it("spells an anode as its lines", () => {
    expect(anodeLabel("CuKa")).toBe("Cu Kα1/Kα2");
    expect(anodeLabel("MoKa1")).toBe("Mo Kα1");
    expect(anodeLabel("custom")).toBe("custom");
  });

  it("shows the source and the radius before Advanced, and the rest after", () => {
    const basic = PRESET_FIELDS.bragg_brentano.filter(basicField).map((f) => f.name);
    expect(basic).toEqual(["radiation", "goniometer_radius_mm"]);
    expect(PRESET_FIELDS.debye_scherrer.filter(basicField).map((f) => f.name))
      .toEqual(["wavelength", "goniometer_radius_mm"]);
  });
});

describe("the name and the folder follow the file until a person types", () => {
  it("takes both from the server's suggestion", () => {
    const state = staged();
    expect(state.name).toBe("lab6");
    expect(state.where).toBe("/data");
    expect(projectPath(state)).toBe("/data/lab6.rex");
  });

  it("keeps what was typed when another pattern arrives", () => {
    const state = { ...staged(), name: "mine", nameSet: true };
    const next = absorbPattern(state, { ...PATTERN, suggested_project: "/other/x.rex" });
    expect(next.name).toBe("mine");
    expect(next.where).toBe("/other");
  });
});

describe("createBody", () => {
  it("commits tokens, never paths, and asks for no plan", () => {
    const body = createBody(staged()) as any;
    expect(body.pattern).toEqual({ upload: "p1" });
    expect(body.structure).toEqual({ upload: "c1", aniso: false });
    expect(body.path).toBe("/data/lab6.rex");
    expect(body.mode).toBe("rietveld");
    expect("plan" in body).toBe(false);
  });

  it("carries the reader options only when one was picked", () => {
    const state = staged();
    expect(createBody(state).reader_options).toBeUndefined();
    state.readerOptions = { block: "meas" };
    expect(createBody(state).reader_options).toEqual({ block: "meas" });
    state.readerOptions = { block: "" };
    expect(createBody(state).reader_options).toBeUndefined();
  });

  it("sends null with no phase, which the server reads as an answer", () => {
    const state = { ...staged(), phases: [] };
    expect(structureArgument(state)).toBeNull();
    expect(createBody(state).structure).toBeNull();
  });

  it("sends several phases as a list of the single forms", () => {
    const state = addTypedCell({ ...staged(), cellDraft: draft() });
    expect(structureArgument(state)).toEqual([
      { upload: "c1", aniso: false },
      { space_group: "R -3 c", cell: { a: 4.759091, c: 12.991779 } },
    ]);
  });
});

describe("the mode follows from the phases", () => {
  it("is Le Bail when any phase is a typed cell, else Rietveld", () => {
    expect(modeFor(staged())).toBe("rietveld");
    expect(modeFor({ ...staged(), phases: [] })).toBe("rietveld");
    expect(modeFor(addTypedCell({ ...staged(), cellDraft: draft() }))).toBe("lebail");
  });
});

describe("a typed cell", () => {
  it("draws the boxes the server named, and no others", () => {
    expect(freeCellFields(draft())).toEqual(["a", "c"]);
    expect(freeCellFields(null)).toEqual([]);
  });

  it("blocks on the symbol, then on each free number", () => {
    expect(cellBlocked({ ...draft(), symbol: "" })).toMatch(/symbol/);
    expect(cellBlocked(draft({ a: "4.76" }))).toMatch(/needs a, c/);
    expect(cellBlocked(draft({ a: "4.76", c: "wide" }))).toMatch(/c is not a number/);
    expect(cellBlocked(draft({ a: "4.76", c: "-1" }))).toMatch(/greater than zero/);
    expect(cellBlocked({ ...draft(), error: "unknown symbol" })).toBe("unknown symbol");
    expect(cellBlocked(draft())).toBe("");
    // a symbol edited since its lookup still has the old symbol's boxes
    expect(cellBlocked({ ...draft(), symbol: "P m -3 m" })).toBe("Looking up P m -3 m…");
  });

  it("is added as numbers and closes its form", () => {
    const state = addTypedCell({ ...staged(), cellDraft: draft() });
    expect(state.cellDraft).toBeNull();
    expect(state.phases[1]).toMatchObject({ kind: "cell", cell: { a: 4.759091, c: 12.991779 } });
  });

  it("is not added while it is incomplete", () => {
    const state = { ...staged(), cellDraft: draft({ a: "4.76" }) };
    expect(addTypedCell(state)).toBe(state);
  });
});

describe("blocked", () => {
  it("names the missing row, in order", () => {
    const state = emptyWizard();
    expect(blocked(state)).toMatch(/pattern/);
    const next = absorbPattern(state, PATTERN);
    expect(blocked(next)).toBe("");
    expect(blocked({ ...next, cellDraft: draft() })).toMatch(/typed cell/);
    expect(blocked({ ...next, name: "  " })).toMatch(/Name the project/);
    expect(blocked({ ...next, name: "a/b" })).toMatch(/slash/);
    expect(blocked({ ...next, where: "" })).toMatch(/where/);
  });

  it("asks for the one field a preset cannot default", () => {
    const state = { ...staged(), preset: "debye_scherrer", values: {} };
    expect(blocked(state)).toMatch(/Debye-Scherrer needs a wavelength/);
    expect(blocked({ ...state, values: { wavelength: "0.4139" } })).toBe("");
  });

  it("catches a typed non-number before the round trip", () => {
    const state = { ...staged(), values: { radiation: "CuKa", goniometer_radius_mm: "wide" } };
    expect(blocked(state)).toMatch(/not a number/);
  });

  it("stops asking for preset fields once a profile is uploaded", () => {
    const state = { ...staged(), preset: "debye_scherrer", values: {},
                    instrument: { upload: "i1" } };
    expect(blocked(state)).toBe("");
  });
});

describe("the summaries quote the reader rather than the extension", () => {
  it("says where the esds come from", () => {
    expect(patternSummary(PATTERN)).toBe(
      "Two/three-column ASCII (.xy / .xye) · 4200 points · 2θ 10.00–90.00°, "
      + "step 0.02° · esd from the file");
    expect(patternSummary({ ...PATTERN, has_sigma: false })).toContain("esd from counts");
    expect(patternSummary(null)).toBe("");
  });

  it("summarises a phase without inventing anything", () => {
    expect(structureSummary(CIF)).toBe(
      "LaB6 · P m -3 m · 4.1566 4.1566 4.1566 Å · 2 atoms (B, La)");
  });

  it("draws the preview on a square-root axis", () => {
    const path = sparkline({ two_theta: [0, 1, 2], intensity: [0, 25, 100] }, 2, 10);
    // √25 is half of √100, so the middle point sits at half height
    expect(path).toBe("M0.0,10.0 L1.0,5.0 L2.0,0.0");
    expect(sparkline({ two_theta: [1], intensity: [1] })).toBe("");
  });
});

describe("no form field without help (WP-1032)", () => {
  /** Every geometry the instrument editor can be showing, so its whole field
   *  vocabulary is reachable from one assertion. */
  const INSTRUMENTS = GEOMETRIES.map((kind) => ({
    zero_shift: { value: 0 },
    source: { polarization: { value: 0.5 },
              lines: [{ wavelength: 1.54, weight: { value: 1 } },
                      { wavelength: 1.544, weight: { value: 0.5 } }] },
    profile: { shape: "tchz_pv", u: {}, v: {}, w: {}, x: {}, y: {} },
    geometry: { kind },
  }));

  it("gives every preset field a help key that resolves (no mute fields)", () => {
    // WP-1029's rule, retargeted by WP-1203: the explanation is an entry in
    // `rietx.help` rather than a `title=` beside the field, so what has to hold
    // is that every key names one.  `packing` — the field WP-1032 was reported
    // against, offered in three places with a title in none — is covered by
    // construction now: the key is the field's own name.
    const known = new Set(HELP_KEYS.keys);
    const mute = Object.entries(PRESET_FIELDS).flatMap(([preset, fields]) =>
      fields.filter((f) => !known.has(presetHelp(f))).map((f) => `${preset}.${f.name}`));
    expect(mute).toEqual([]);
  });

  it("gives every instrument-editor field a help key or a stated exception", () => {
    // Two fields have no corpus entry and say so in `lib/model.ts`:
    // `geometry.kind` and `profile.shape` are model *choices*, not named
    // quantities, and neither has a vocabulary the corpus is keyed by.  Naming
    // them here rather than allowing any `title` keeps the exception countable
    // — a third one fails until it is either described or added to this list.
    const known = new Set(HELP_KEYS.keys);
    const NO_ENTRY = ["geometry.kind", "profile.shape"];
    const bare: string[] = [];
    const exceptions = new Set<string>();
    for (const instrument of INSTRUMENTS) {
      for (const f of instrumentFields(instrument)) {
        if (f.help && known.has(f.help)) continue;
        if (NO_ENTRY.includes(f.path) && f.title?.trim()) {
          exceptions.add(f.path);
          continue;
        }
        bare.push(`${instrument.geometry.kind}:${f.path}`);
      }
    }
    expect(bare).toEqual([]);
    // …and the exception list may not outlive its members
    expect([...exceptions].sort()).toEqual([...NO_ENTRY].sort());
  });

  it("gives every phase field a help key that resolves", () => {
    // The structure column's fields carry a key as data too since WP-1214, and
    // `<Help for={field.help}>` is an *expression*, so `help.test.ts`'s scan of
    // the markup cannot see it: a rename of `phases.*.lor_size` would leave the
    // form drawing "not yet described" under a perfectly good control.
    const known = new Set(HELP_KEYS.keys);
    const bare = phaseFields(0).filter((f) => !f.help || !known.has(f.help));
    expect(bare.map((f) => f.path)).toEqual([]);
  });

  it("explains packing the same way wherever it is offered", () => {
    // One wording, and now by construction rather than by comparison: both
    // forms name the same corpus entry, so the two cannot drift.  The
    // assertion is that they name the *same* one — a wizard field pointing at
    // `instrument_fields:packing_fraction` and an editor field pointing
    // anywhere else would be the same defect in a new shape.
    const keys = new Set<string>();
    for (const fields of Object.values(PRESET_FIELDS)) {
      for (const f of fields) if (f.name === "packing_fraction") keys.add(presetHelp(f));
    }
    for (const instrument of INSTRUMENTS) {
      for (const f of instrumentFields(instrument)) {
        if (f.path === "geometry.packing_fraction") keys.add(f.help!);
      }
    }
    expect([...keys]).toEqual(["instrument_fields:packing_fraction"]);
  });
});

describe("applyInstrumentHint", () => {
  it("seeds the preset and its fields from what the file knew", () => {
    const state = applyInstrumentHint(emptyWizard(), {
      preset: "bragg_brentano", radiation: "CuKa1",
      goniometer_radius_mm: 280, why: "…",
    });
    expect(state.preset).toBe("bragg_brentano");
    expect(state.values.radiation).toBe("CuKa1");
    expect(state.values.goniometer_radius_mm).toBe("280");
    // the spec the form will actually post carries them, not just the display
    expect(presetSpec(state)).toMatchObject(
      { preset: "bragg_brentano", radiation: "CuKa1", goniometer_radius_mm: 280 });
  });

  it("switches geometry when the file's wavelength is no Kα line", () => {
    const state = applyInstrumentHint(emptyWizard(), {
      preset: "debye_scherrer", wavelength: 0.413909, why: "…",
    });
    expect(state.preset).toBe("debye_scherrer");
    expect(presetSpec(state)).toMatchObject(
      { preset: "debye_scherrer", wavelength: 0.413909 });
  });

  it("leaves the form untouched when there is no hint", () => {
    // a header whose name and wavelength disagree sends null rather than a
    // guess, and an empty form beats one that looks like it was read
    const before = emptyWizard();
    for (const hint of [null, undefined, {}, { preset: "not_a_preset" }]) {
      expect(applyInstrumentHint(before, hint)).toEqual(before);
    }
  });
});

describe("scanCount", () => {
  it("reads the preview's own metadata and defaults to one", () => {
    expect(scanCount({ metadata: { scan_count: "3" } })).toBe(3);
    expect(scanCount({ metadata: {} })).toBe(1);
    expect(scanCount(null)).toBe(1);
  });
});
