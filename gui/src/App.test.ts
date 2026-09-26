// @vitest-environment jsdom
/**
 * Mount the real shell against a stubbed server and read the DOM.
 *
 * Not a substitute for looking at the page — it is a substitute for *shipping a
 * blank one*.  The failure mode a component test catches that no Python test
 * can is a runtime error during mount: the bundle loads, the server answers, and
 * the user sees nothing.  So this boots `App.svelte` with `fetch` stubbed,
 * waits for the boot chain, and asserts the header, the run controls and the
 * empty states are actually in the document.
 *
 * The three shell states asserted first are the three a user will spend time in:
 * no project, a project with no fit, and a run in flight (where Run must be
 * disabled off the *state frame* rather than off what the last click hoped).
 * The editors that follow are asserted through their **requests**: what the
 * parameter table sends is the whole contract with `set_vary`/`set_values`, and
 * a table that renders beautifully while PATCHing the wrong body is the bug this
 * file exists to catch.
 */
import { diagnosticCount } from "@codemirror/lint";
import { EditorView } from "@codemirror/view";
import { mount, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App.svelte";
import { STAGE_WORDS } from "./lib/rxt";
import { pack } from "./test-curves";
import { StubPlot } from "./test-uplot";
import { exports, frames, lifecycle, type Frame } from "./test-gl3d";
import { project } from "./lib/structure3d";
// Loaded here so the panels' own `import("../lib/pattern")` and
// `import("../lib/seriesChart")` find them loaded: a first import outlasts
// `flush()`, and a plot case run alone (`-t`) then drew nothing where the same
// case in the whole file passed.
import "./lib/pattern";
import "./lib/seriesChart";

const CAPABILITIES = {
  package_version: "1.0.0.dev0",
  features: { anisotropic_adp: true, indexing: false, cancellation: true },
  plans: [],
};

/** `GET /api/help` in the shape the route serves (WP-1202/1203).
 *
 * Three entries and the base, which is all the popover's behaviour needs: one
 * parameter family (a glob key, a manual anchor and the detail rows), one
 * stage field with neither, and `docs_url` so the link can be asserted as a
 * whole URL rather than as a suffix. */
const HELP = {
  parameters: [
    { paths: ["phases.*.cell.a", "phases.*.cell.b", "phases.*.cell.c"],
      title: "Cell edge", description: "A unit-cell edge length.",
      unit: "Å", default: null, typical: "3-40 Å for an inorganic phase",
      anchor: "peak-positions.html#lattice-metric-and-bragg-s-law" },
  ],
  // a flag and an origin with the label a chip carries (WP-1209): the chip says
  // the label and the popover restores the name behind it
  peak_flags: {
    not_separable: { title: "Improves the group as a shape, not as a line",
                     description: "A nested fit without it is not refuted.",
                     unit: null, default: null, typical: null, anchor: null,
                     label: "not separable" },
  },
  peak_diagnostics: {},
  peak_origins: {
    manual: { title: "Placed by a person", description: "Someone added this line.",
              unit: null, default: null, typical: null, anchor: null, label: "manual" },
  },
  stage_fields: {
    max_iter: { title: "Iteration cap", description: "Least-squares iterations.",
                unit: null, default: "100", typical: null, anchor: null },
  },
  reader_options: {},
  instrument_fields: {},
  search_fields: {},
  plans: {},
  docs_url: "https://rietx.org",
};

const PROJECT = {
  path: "/tmp/lab6.rex",
  doc: { mode: "rietveld", plan: null, ui: {}, two_theta_limits: null,
         excluded_regions: [] },
  // `two_theta_range` is what the shading has to reach past and `n_fitted` is
  // the channel count that says whether it is telling the truth (WP-1033)
  // …and `wavelengths` is the source's emission lines, primary first, which is
  // what the readout strip computes d with and names a candidate line by
  // (WP-1213)
  data: { filename: "synth.xye", n_points: 4200, n_fitted: 4200, has_sigma: true,
          reader: "xy", two_theta_range: [3, 23.995],
          wavelengths: [1.5405929, 1.5444274] },
  head: "n0000",
  n_nodes: 1,
};

/** The same project with a fit range and one excluded region already set. */
const MASKED_PROJECT = {
  ...PROJECT,
  doc: { ...PROJECT.doc, two_theta_limits: [8, 19], excluded_regions: [[13, 16]] },
  data: { ...PROJECT.data, n_fitted: 1600 },
};

const IDLE_RUN = {
  state: "idle",
  run: { kind: null, status: null, stage: null, stage_index: null, n_stages: null,
         rwp: null, gof: null, node_id: null, completed_stages: [], error: null },
  project: PROJECT.path,
  head: "n0000",
};

const RESULT = {
  statistics: { rwp: 0.0415, gof: 0.79 },
  curves: { n_points: 4200, two_theta_range: [3, 23.995] },
  ticks: { LaB6: [5.7, 8.1] },
};

/** Rows chosen to carry all three held reasons plus a plain refinable one.
 *
 * The bounds are the **strings** the server sends: `JSON.parse` rejects Python's
 * bare `Infinity` token, so `gui/server.py` spells a non-finite float the way the
 * schemas do (`ser_json_inf_nan="strings"`). Writing numbers here instead would
 * make this suite pass against a payload the browser cannot even parse. */
function param(path: string, over: Record<string, unknown> = {}) {
  const row = {
    path, value: 1, vary: false, lo: "-Infinity" as any, hi: "Infinity" as any,
    transform: "identity",
    tie: null as any, locked: false, esd: null as number | null, mode_fixed: false,
    // the family glob the server matched (WP-1202); the table renders it as a
    // help key and never re-derives the match
    help_key: null as string | null,
    ...over,
  };
  return {
    ...row,
    refinable: !row.locked && row.tie === null && !row.mode_fixed,
    held_because: row.locked
      ? "structurally fixed by symmetry or by the model"
      : row.tie
        ? "tied: = 1·phases.0.cell.a"
        : row.mode_fixed
          ? "force-fixed by the intensity mode (lebail/pawley)"
          : "",
  };
}

const PARAMS = {
  parameters: [
    param("phases.0.cell.a", { value: 4.15678, vary: true, esd: 0.00019, lo: 0.1,
                              help_key: "phases.*.cell.a" }),
    param("phases.0.cell.b", { value: 4.15678, help_key: "phases.*.cell.b",
                               tie: { sources: ["phases.0.cell.a"] } }),
    param("phases.0.cell.alpha", { value: 90, locked: true }),
    param("phases.0.scale", { value: 1.02, vary: true, help_key: "phases.*.scale" }),
    param("phases.0.atoms.0.biso", { value: 0.5, mode_fixed: true }),
    param("instrument.profile.w", { value: 0.004, lo: 0, hi: 1 }),
  ],
  n_free: 2,
  mode: "rietveld",
  head: "n0000",
  live: false,
};

const PLAN = {
  plan: {
    stages: [
      { name: "scale+bkg", turn_on: ["phases.*.scale", "instrument.background.*"],
        max_iter: 100, lebail_cycles: 3, seed: 0, strain_seed: 0 },
      { name: "cell", turn_on: ["phases.*.cell.*"], max_iter: 100, lebail_cycles: 3,
        seed: 0, strain_seed: 0 },
    ],
    correlation_guard: 0.98,
  },
  selected: true,
  preset: "mccusker_default",
  mode: "rietveld",
};

/** `GET /api/plan/resolve` (WP-1208): what each of `PLAN`'s two stages will
 *  free on the live table, in the shape the ladder draws. */
const PLAN_RESOLVE = {
  mode: "rietveld",
  n_parameters: 12,
  n_free_final: 5,
  set_aside: [],
  head: "n0002",
  live: false,
  stages: [
    { name: "scale+bkg", turn_on: ["phases.*.scale", "instrument.background.*"],
      frees: ["phases.0.scale", "instrument.background.c0"], already: [], held: [],
      n_matched: 2, n_free: 2, rwp: 0.9535 },
    { name: "cell", turn_on: ["phases.*.cell.*"],
      frees: ["phases.0.cell.a"], already: [],
      held: [{ path: "phases.0.cell.b",
               held_because: "tied: = 1\u00b7phases.0.cell.a" }],
      n_matched: 2, n_free: 3, rwp: 0.4457 },
  ],
};

const PLANS = {
  plans: [
    { name: "mccusker_default", title: "Standard (profile only)",
      description: "Scale and background, zero shift, cell, then the widths.",
      modes: ["rietveld"], when_to_use: "The default first fit of a known structure." },
    { name: "profile_only", title: "Profile only",
      description: "Background, zero shift, cell and widths only.",
      modes: ["rietveld", "lebail"], when_to_use: "Le Bail, or a profile without a structure." },
  ],
};

/** LaB6: La on a fully fixed 1a site, B on 6f with one DOF along x. */
const STRUCTURE = {
  phases: [{
    name: "LaB6", space_group: "P m -3 m",
    cell: { a: { value: 4.15678, vary: true }, b: { value: 4.15678, vary: false },
            c: { value: 4.15678, vary: false }, alpha: { value: 90, vary: false },
            beta: { value: 90, vary: false }, gamma: { value: 90, vary: false } },
    scale: { value: 1.02, vary: true },
    atoms: [
      { label: "La", species: "La", x: { value: 0 }, y: { value: 0 }, z: { value: 0 },
        occ: { value: 1 }, biso: { value: 0.5 }, aniso: null },
      { label: "B", species: "B", x: { value: 0.1993 }, y: { value: 0.5 },
        z: { value: 0.5 }, occ: { value: 1 }, biso: { value: 0.4 }, aniso: null },
    ],
  }],
};

const SITES = [
  { path: "phases.0.atoms.0", phase: 0, atom: 0, site_symmetry_order: 48,
    special: true, dof_paths: [], dof_directions: [], adp_paths: [],
    adp_patterns: [[1, 1, 1, 0, 0, 0]], aniso: false },
  { path: "phases.0.atoms.1", phase: 0, atom: 1, site_symmetry_order: 8,
    special: true, dof_paths: ["phases.0.atoms.1.dof.0"], dof_directions: [[1, 0, 0]],
    adp_paths: [], adp_patterns: [], aniso: false },
];

/** `GET /api/structure`'s two free symmetry arms (WP-1035) — one gemmi lookup
 *  per phase, and the sentence naming what holds each held row. */
const SYMMETRY = [{
  phase: 0, space_group: "P m -3 m", xhm: "P m -3 m", number: 221,
  hall: "-P 4 2 3", short_name: "Pm-3m", ext: "", qualifier: "",
  crystal_system: "cubic", laue_class: "m-3m", point_group: "m-3m",
  centring: "P", unique_axis: "", centrosymmetric: true, sohncke: false,
  enantiomorphic: false, symmorphic: true, reference_setting: true,
  setting: "P m -3 m is cubic",
  ties: { b: "a", c: "a" },
  fixed_angles: { alpha: 90, beta: 90, gamma: 90 },
  tie_error: "", constraints: "b = a, c = a · α = β = γ = 90°",
}];

const CAUSES = {
  "phases.0.cell.b": "P m -3 m is cubic, so b follows a",
  "phases.0.cell.alpha": "P m -3 m is cubic, so α is fixed at 90°",
  "phases.0.atoms.0.x": "a site symmetry of order 48 allows no displacement at "
    + "all — a fully fixed special position, so x cannot move",
};

/** …and the tier that costs a spglib search per atom, on its own route. */
const LETTERS = {
  phase: 0,
  symmetry: SYMMETRY[0],
  letters: [
    { path: "phases.0.atoms.0", atom: 0, label: "La", wyckoff: "1a",
      site_symmetry: "m-3m", multiplicity: 1 },
    { path: "phases.0.atoms.1", atom: 1, label: "B", wyckoff: "6f",
      site_symmetry: "4m.m", multiplicity: 6 },
  ],
  causes: { ...CAUSES,
    "phases.0.atoms.0.x": "Wyckoff 1a, site symmetry m-3m allows no displacement "
      + "at all — a fully fixed special position, so x cannot move" },
};

/** A preview that changes the table (cubic → tetragonal) and one that cannot be
 *  applied at all (an orbit collision), in the shapes the server sends. */
const PREVIEW_OK = {
  phase: 0, from: SYMMETRY[0],
  to: { ...SYMMETRY[0], xhm: "P 4/m m m", number: 123,
        crystal_system: "tetragonal", ties: { b: "a" },
        constraints: "b = a · α = β = γ = 90°" },
  changed: true, blocked: false, refusals: [], notes: [],
  entries: { added: [], removed: [], tied: [], untied: ["phases.0.cell.c"],
             locked: [], unlocked: [] },
  sites: [{ path: "phases.0.atoms.1", atom: 1, label: "B",
            from: { order: 8, multiplicity: 6, dofs: 1, adps: 0,
                    dof_directions: [[1, 0, 0]] },
            to: { order: 4, multiplicity: 6, dofs: 1, adps: 0,
                  dof_directions: [[1, 0, 0]] } }],
};

const PREVIEW_BLOCKED = {
  ...PREVIEW_OK,
  to: { ...SYMMETRY[0] },
  blocked: true,
  refusals: [{ where: "phases.0.atoms.0",
               message: "phases.0.atoms.0: the anisotropic tensor […] is not "
                 + "compatible with the site symmetry; the nearest allowed "
                 + "tensor is [0.0063, 0.0063, 0.0063, 0, 0, 0]" }],
  notes: [{ kind: "orbit_collision",
            where: ["phases.0.atoms.0", "phases.0.atoms.1"],
            message: "La and B become symmetry-equivalent under P m -3 m" }],
  entries: { added: [], removed: [], tied: [], untied: [], locked: [], unlocked: [] },
  sites: [],
};

/** `GET /api/structure3d` for the same LaB6: the orbit of the corner atom with
 *  one of its boundary copies, one boron, one bond, and the twelve cell edges.
 *  Trimmed by hand — the geometry itself is `tests/test_structure3d.py`'s
 *  ground, and what a mount can check is that the panel *draws* it. */
const GEOMETRY = {
  phase: 0, phases: ["LaB6"], name: "LaB6", space_group: "P m -3 m",
  cell: [4.15678, 4.15678, 4.15678, 90, 90, 90], volume: 71.82,
  lattice: [[4.15678, 0, 0], [0, 4.15678, 0], [0, 0, 4.15678]],
  corners: [[0, 0, 0], [4.15678, 0, 0], [0, 4.15678, 0], [4.15678, 4.15678, 0],
            [0, 0, 4.15678], [4.15678, 0, 4.15678], [0, 4.15678, 4.15678],
            [4.15678, 4.15678, 4.15678]],
  edges: [[0, 1], [2, 3], [4, 5], [6, 7], [0, 2], [1, 3],
          [4, 6], [5, 7], [0, 4], [1, 5], [2, 6], [3, 7]],
  sites: [
    { index: 0, path: "phases.0.atoms.0", label: "La", species: "La",
      element: "La", color: "#995cbc", radius: 2.07, metal: true, occ: 1,
      biso: 0.5, u_iso: 0.00633, aniso: false, multiplicity: 1, special: true,
      npd: false },
    { index: 1, path: "phases.0.atoms.1", label: "B", species: "B",
      element: "B", color: "#e0a080", radius: 0.84, metal: false, occ: 1,
      biso: 0.4, u_iso: 0.00507, aniso: false, multiplicity: 6, special: true,
      npd: false },
  ],
  atoms: [
    { site: 0, frac: [0, 0, 0], pos: [0, 0, 0], boundary: false,
      ellipsoid: [[0.08, 0, 0], [0, 0.08, 0], [0, 0, 0.08]],
      rms: [0.08, 0.08, 0.08], npd: false },
    { site: 0, frac: [1, 0, 0], pos: [4.15678, 0, 0], boundary: true,
      ellipsoid: [[0.08, 0, 0], [0, 0.08, 0], [0, 0, 0.08]],
      rms: [0.08, 0.08, 0.08], npd: false },
    { site: 1, frac: [0.1993, 0.5, 0.5], pos: [0.8284, 2.0784, 2.0784],
      boundary: false, ellipsoid: [[0.07, 0, 0], [0, 0.07, 0], [0, 0, 0.07]],
      rms: [0.07, 0.07, 0.07], npd: false },
  ],
  bonds: [{ i: 0, j: 2, a: [0, 0, 0], b: [0.8284, 2.0784, 2.0784], d: 3.058 }],
  polyhedra: [],
  probability: 0.5, probability_levels: { "0.5": 1.5382, "0.9": 2.5003 },
  scale: 1.5382, ball_fraction: 0.40, bond_tolerance: 1.15,
  bond_metals: false, note: "",
};

const INSTRUMENT = {
  zero_shift: { value: 0.01, vary: false },
  source: { polarization: { value: 0.99, vary: false },
            lines: [{ wavelength: 0.413909, weight: { value: 1, vary: false } }],
            dispersion: { table: "cromer_liberman", overrides: {} } },
  profile: { shape: "tchz_pv", u: { value: 0.002, vary: false },
             v: { value: 0, vary: false }, w: { value: 0.004, vary: true },
             x: { value: 0, vary: false }, y: { value: 0, vary: false } },
  geometry: { kind: "debye_scherrer", goniometer_radius_mm: null,
              sample_displacement: { value: 0, vary: false },
              sample_transparency: { value: 0, vary: false },
              axial_sl: { value: 0.002, vary: false },
              axial_hl: { value: 0.002, vary: false },
              mu_r: null, capillary_radius_mm: null, packing_fraction: 0.6 },
  background: { kind: "chebyshev", coefficients: [{ value: 1 }, { value: 0 }, { value: 0 }] },
};

/** A history with a fork: n0003 ran from n0001, which already had n0002. */
const HISTORY = {
  tree_id: "t1",
  head: "n0003",
  root: "n0000",
  n_nodes: 4,
  nodes: [
    { id: "n0000", parents: [], children: ["n0001"], label: "", created_utc: "2026-07-30T10:00:00Z",
      kind: "root", name: "", action: { kind: "root" }, api_call: "rx.Refinement(structure, instrument)",
      status: null, n_iterations: null, rwp: null, gof: null, n_free: null,
      n_diagnostics: 0, diagnostics: [], tags: [], scores: {}, notes: {} },
    { id: "n0001", parents: ["n0000"], children: ["n0002", "n0003"], label: "",
      created_utc: "2026-07-30T10:00:01Z", kind: "stage", name: "scale+bkg",
      action: { kind: "stage", name: "scale+bkg", turn_on: ["phases.*.scale"] },
      api_call: "ref.run_stage(data, rx.Stage('scale+bkg', ['phases.*.scale'], max_iter=100))",
      status: "converged", n_iterations: 7, rwp: 0.21, gof: 1.9, n_free: 4,
      n_diagnostics: 0, diagnostics: [], tags: [], scores: {}, notes: {} },
    { id: "n0002", parents: ["n0001"], children: [], label: "",
      created_utc: "2026-07-30T10:00:02Z", kind: "stage", name: "cell",
      action: { kind: "stage", name: "cell", turn_on: ["phases.*.cell.*"] },
      api_call: "ref.run_stage(data, rx.Stage('cell', ['phases.*.cell.*'], max_iter=100))",
      status: "converged", n_iterations: 5, rwp: 0.04, gof: 0.8, n_free: 5,
      n_diagnostics: 1,
      diagnostics: [{ level: "warning", code: "HIGH_CORRELATION",
                      message: "a ~ b (ρ=+0.994)", where: ["phases.0.cell.a", "instrument.zero_shift"] }],
      tags: ["best-so-far"], scores: {}, notes: {} },
    { id: "n0003", parents: ["n0001"], children: [], label: "",
      created_utc: "2026-07-30T10:00:03Z", kind: "set_vary",
      name: "", action: { kind: "set_vary", turn_on: ["a", "b", "c"], turn_off: [] },
      api_call: "ref.set_vary(['a', 'b', 'c'], True)",
      status: null, n_iterations: null, rwp: null, gof: null, n_free: null,
      n_diagnostics: 0, diagnostics: [], tags: [], scores: {}, notes: {} },
  ],
};

/** A report with all three layers, an unindexed peak, and one of each
 *  applicability: a button, a veto, and advice. */
const REPORT = {
  report: {
    thresholds_version: "0.4",
    rwp: 0.216, gof: 1.41,
    summary: "Rwp 21.6 %, 15 misfitting regions; Layer 1 on 15/15 regions",
    regions: [
      { two_theta_lo: 9.0, two_theta_hi: 9.4, local_rwp: 0.31, chi2_share: 0.42,
        max_abs_delta_over_sigma: 41, n_reflections: 1 },
      { two_theta_lo: 5.6, two_theta_hi: 5.9, local_rwp: 0.88, chi2_share: 0.02,
        max_abs_delta_over_sigma: 6, n_reflections: 0 },
    ],
    unmatched: [{ two_theta: 12.34, height_over_sigma: 19, kind: "unmatched_obs" }],
    attribution: [
      { two_theta_lo: 9.0, two_theta_hi: 9.4, n_reflections: 1, chi2_share: 0.42,
        mean_two_theta: 9.2, mean_fwhm: 0.016, r2: 0.91, gram_condition: 220,
        chi2_reduced: 30, gates_passed: true, gate_failures: [],
        coefficients: [{ kind: "position", value: -0.0024, stderr: 0.0002,
                         significant: true, share: 0.9 }] },
      { two_theta_lo: 5.6, two_theta_hi: 5.9, n_reflections: 0, chi2_share: 0.02,
        mean_two_theta: 5.7, mean_fwhm: 0.016, r2: 0.2, gram_condition: 1.2e5,
        chi2_reduced: 4, gates_passed: false,
        gate_failures: [
          { code: "local_r2", message: "local_r2=0.20<0.5" },
          { code: "gram_condition", message: "gram_condition=1.2e+05>1e+04" }],
        coefficients: [] },
    ],
    trends: [
      { observable: "position", n_regions_used: 15, max_template_collinearity: 0.999,
        separability_ratio: 1.1, separable: false, misfit_share: 0.85,
        templates: [{ name: "tan_theta", coefficient: -0.0024, stderr: 0.0002, r2: 0.88 },
                    { name: "constant", coefficient: -0.0011, stderr: 0.0003, r2: 0.71 }] },
    ],
    texture: [], strain: [], restraints: null,
    layer1_available: true, abstained_reason: null,
    suggested_actions: [
      { kind: "refine_scale", confidence: 0.9, rationale: "intensities are uniformly off",
        parameter_paths: ["phases.*.scale"], expected_delta_chi2: 16.19,
        alternatives: ["refine_biso"], two_theta_range: null,
        vetoed_by: "already refined by the staged plan (phases.*.scale)" },
      { kind: "refine_cell", confidence: 0.5,
        rationale: "position error follows the tan_theta template; templates are collinear",
        parameter_paths: ["phases.*.cell.*"], expected_delta_chi2: 16.19,
        alternatives: ["refine_zero_shift"], two_theta_range: null, vetoed_by: null },
      { kind: "add_impurity_phase", confidence: 0.4,
        rationale: "1 observed peak has no calculated reflection nearby",
        parameter_paths: [], expected_delta_chi2: null,
        alternatives: ["reindex_or_recheck_cell"], two_theta_range: [12.34, 12.34],
        vetoed_by: null },
    ],
  },
  apply: [
    { kind: "refine_scale", how: "stage", note: "", can_apply: false,
      refusal: "vetoed: already refined by the staged plan (phases.*.scale)",
      paths: ["phases.*.scale"], stage: null, api_call: null },
    { kind: "refine_cell", how: "stage", note: "", can_apply: true, refusal: "",
      paths: ["phases.*.cell.*"],
      stage: { name: "apply:refine_cell", turn_on: ["phases.*.cell.*"], max_iter: 100,
               lebail_cycles: 3, seed: 0, strain_seed: 0 },
      api_call: "ref.run_stage(data, rx.Stage('apply:refine_cell', ['phases.*.cell.*'], max_iter=100))" },
    { kind: "add_impurity_phase", how: "advice",
      note: "no phase is named yet, so there is nothing to free.",
      can_apply: false,
      refusal: "not a one-click action — no phase is named yet, so there is nothing to free.",
      paths: [], stage: null, api_call: null },
  ],
};

interface Call {
  method: string;
  path: string;
  /** the path *with* its query — the report panel's zoom is a query, not a body */
  url: string;
  body: any;
  blob?: Blob | null;
}

/** The series setup as the server answers it before any file is staged: an empty
 *  list plus the defaults, which *is* the empty state (WP-1016). */
const SERIES_SETUP = {
  patterns: [],
  n_patterns: 0,
  settings: { carry: ["*"], refit: "single", direction: "forward", x_label: "index" },
  choices: { refit: ["single", "stages"], direction: ["forward", "backward", "both"] },
  carry_help: "dot-path globs naming which parameters cross the pattern boundary",
  defaults: { carry: ["*"], refit: "single", direction: "forward", x_label: "index" },
  protocol: { mode: "rietveld", plan: "mccusker_default", n_stages: 5 },
  has_x: false,
  sigma_mixed: false,
  has_result: false,
  running: false,
};

/** Two staged patterns, one of them without a file esd column — which is the
 *  weighting inconsistency the panel has to surface before the chain runs. */
const SERIES_STAGED = {
  ...SERIES_SETUP,
  patterns: [
    { upload: "tok0", filename: "T300.xye", label: "T300", x: 300, reader: "xy",
      reader_options: {}, n_points: 4200, two_theta_range: [3, 24], has_sigma: true },
    { upload: "tok1", filename: "T400.xye", label: "T400", x: 400, reader: "xy",
      reader_options: {}, n_points: 4200, two_theta_range: [3, 24], has_sigma: false },
  ],
  n_patterns: 2,
  settings: { carry: ["*"], refit: "single", direction: "both", x_label: "T" },
  has_x: true,
  sigma_mixed: true,
};

/** A finished two-pattern series whose cell edge is path-dependent — the case
 *  the panel exists to make un-missable. */
const SERIES_ANSWER = {
  result: {
    mode: "rietveld", x_label: "T", direction: "both",
    entries: [
      { index: 0, label: "T300", x: 300, status: "converged",
        statistics: { rwp: 0.091, gof: 1.2 }, parameters: [], qpa: null,
        diagnostics: [], n_iterations: 31, reseeded: false, rwp_warm: null,
        node_id: "n0001", tree_id: "t1" },
      { index: 1, label: "T400", x: 400, status: "converged",
        statistics: { rwp: 0.094, gof: 1.3 }, parameters: [], qpa: null,
        diagnostics: [], n_iterations: 12, reseeded: true, rwp_warm: 0.31,
        node_id: "n0002", tree_id: "t2" },
    ],
    diagnostics: [
      { level: "warning", code: "SEQUENTIAL_PATH_DEPENDENT",
        where: ["phases.0.cell.a"],
        message: "phases.0.cell.a differs between the forward and backward chains",
        suggestion: "hold it, restrain it, or quote the spread" },
      { level: "warning", code: "SEQUENTIAL_RESEED", where: ["T400"],
        message: "pattern 1 (T400) was refitted from the initial model",
        suggestion: "check whether the specimen changed here" },
    ],
  },
  trajectories: [
    { path: "instrument.zero_shift", x: [300, 400], x_label: "T",
      value: [0.008, 0.0081], stderr: [1e-5, 1e-5], labels: ["T300", "T400"],
      path_dependent: false, discontinuous: false, backward: [0.008, 0.0081],
      n_sigma: 0.4 },
    { path: "phases.0.cell.a", x: [300, 400], x_label: "T",
      value: [4.1566, 4.1587], stderr: [1e-4, null], labels: ["T300", "T400"],
      path_dependent: true, discontinuous: false, backward: [4.1571, 4.1592],
      n_sigma: 5.2 },
  ],
  path_dependent: ["phases.0.cell.a"],
  path_dependence_sigma: 3.0,
  has_backward: true,
  n_iterations: 43,
  curves: [true, true],
  running: false,
};

/** What `GET /api/examples` answers (WP-1204): the shipped example projects,
 *  `built` saying whether opening one costs a build first. */
const EXAMPLES = [
  { name: "fap", title: "GSAS-II LabData — fluorapatite (lab CuK\u03b1 doublet)",
    description: "seven atomic sites with real positional freedom",
    bytes: 47104, built: false, path: "/home/me/.rietx/examples/fap.rex" },
  { name: "nac", title: "APS 11-BM — NAC + CaF\u2082 (synchrotron capillary)",
    description: "two phases, and one of them you did not ask for",
    bytes: 2562048, built: true, path: "/home/me/.rietx/examples/nac.rex" },
];


/** A stub server that also records what was asked of it. */
/** A handler may return a `gate` to hold its answer open — which is the only
 *  way to put two requests in flight at once and choose the order they land in. */
function server(routes: Record<string, (call: Call) =>
                { status?: number; body: unknown; gate?: Promise<void> }>) {
  const calls: Call[] = [];
  const fetcher = vi.fn(async (input: any, init: any = {}) => {
    const url = String(input);
    const path = url.split("?")[0];
    const call: Call = {
      method: init.method ?? "GET",
      path,
      url,
      // an upload's body is bytes, not JSON — the only route family in the
      // surface whose body is not a JSON object (WP-1014)
      body: typeof init.body === "string" ? JSON.parse(init.body) : null,
      blob: init.body instanceof Blob ? init.body : null,
    };
    calls.push(call);
    const handler = routes[path];
    const { status = 200, body, gate } = handler
      ? handler(call)
      : { status: 404, body: { error: { code: "NOT_FOUND", message: path } },
          gate: undefined };
    if (gate) await gate;
    // the curves route answers float64 arrays rather than JSON (WP-1461, D4)
    if (body instanceof ArrayBuffer) {
      return { ok: status < 400, status, arrayBuffer: async () => body, text: async () => "" } as any;
    }
    return { ok: status < 400, status, text: async () => JSON.stringify(body) } as any;
  });
  return { fetcher, calls };
}

/** The routes a mounted shell asks for before anyone has clicked anything.
 *
 * `appUi` is the *person's* settings store (WP-1044), which is a different
 * scope from `project.doc.ui` and answers a different question — the theme is
 * about the screen, a column width is about the project. */
function boot(project: any = PROJECT, run: any = IDLE_RUN,
              appUi: Record<string, unknown> = {}) {
  const ui = { ...appUi };
  return {
    "/api/settings": (call: Call) => {
      if (call.method === "POST") Object.assign(ui, call.body.ui);
      return { body: { ui } };
    },
    "/api/version": () => ({ body: { package_version: "1.0.0.dev0", project: project?.path ?? null } }),
    "/api/capabilities": () => ({ body: CAPABILITIES }),
    "/api/help": () => ({ body: HELP }),
    "/api/project": (call: Call) =>
      project
        ? { body: call.method === "POST"
              ? { ...project, doc: { ...project.doc, ui: { ...project.doc.ui, ...(call.body.ui ?? {}) } } }
              : project }
        : { status: 409, body: { error: { code: "NO_PROJECT", message: "no project" } } },
    "/api/run/state": () => ({ body: run }),
    // WP-1204: answered rather than 404'd, so a test that is not about the
    // examples sees the same empty section a build without them shows
    "/api/examples": () => ({ body: { examples: [] } }),
    "/api/result": () => ({ status: 409, body: { error: { code: "NO_RESULT", message: "none" } } }),
    "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...run } }),
    "/api/params": () => ({ body: PARAMS }),
    "/api/plan": () => ({ body: PLAN }),
    "/api/plan/resolve": () => ({ body: PLAN_RESOLVE }),
    "/api/plans": () => ({ body: PLANS }),
    "/api/history": () => ({ body: HISTORY }),
    "/api/report": () => ({ status: 409, body: { error: { code: "NO_RESULT", message: "none" } } }),
    "/api/structure": () => ({ body: { structure: STRUCTURE, sites: SITES,
                                       symmetry: SYMMETRY, causes: CAUSES } }),
    "/api/structure3d": () => ({ body: GEOMETRY }),
    "/api/instrument": () => ({ body: { instrument: INSTRUMENT } }),
    // the series tab fetches only when it is looked at, but the tab *tour* looks
    // at it — and an unstubbed route is a 404, which the panel would show as a
    // failure banner rather than as its empty state
    "/api/series": () => ({ body: SERIES_SETUP }),
    "/api/series/result": () => ({ status: 409, body: { error: {
      code: "NO_SERIES_RESULT", message: "no series has completed" } } }),
  } as Record<string, (call: Call) => { status?: number; body: unknown }>;
}

const i32 = (v: number[]) => Int32Array.from(v);

/**
 * A fit's curves as `/api/result/curves` sends them (WP-1461, D4): every
 * channel of the pattern, `kept` for the ones the protocol fits now, and the
 * model on the channels `fitted` names. Two channels at 9 and 9.4° unless a
 * test says otherwise, every one of them fitted.
 */
function fitCurves(over: {
  two_theta?: number[]; y_obs?: number[]; kept?: number[]; fitted?: number[];
  y_calc?: number[]; y_background?: number[]; delta?: number[];
  header?: Record<string, unknown>;
} = {}) {
  const two_theta = over.two_theta ?? [9, 9.4];
  const y_obs = over.y_obs ?? two_theta.map((_, i) => i + 1);
  const fitted = over.fitted ?? two_theta.map((_, i) => i);
  const zeros = fitted.map(() => 0);
  const arrays: Record<string, ArrayLike<number>> = {
    two_theta, y_obs, kept: i32(over.kept ?? fitted), fitted: i32(fitted),
    y_calc: over.y_calc ?? fitted.map((i) => y_obs[i]),
    delta: over.delta ?? zeros, delta_raw: zeros, cumulative_chi2: zeros,
  };
  if (over.y_background) arrays.y_background = over.y_background;
  return () => ({ body: pack({ fit: true, weighted: true, stale: false,
                               n_channels: two_theta.length, n_fitted: fitted.length,
                               ticks: {}, tick_hkl: {}, ...over.header }, arrays) });
}

/** The pattern alone, as the curves route answers before any fit. */
function rawCurves(two_theta: number[], y_obs: number[]) {
  return () => ({ body: pack({ fit: false, weighted: true, n_channels: two_theta.length },
                             { two_theta, y_obs, kept: i32(two_theta.map((_, i) => i)) }) });
}

/** The result routes, for the tests that need a fit to exist. */
const FITTED = {
  "/api/result": () => ({ body: { result: { ...RESULT, statistics: { rwp: 0.216, gof: 1.41, chi2: 16.96 } } } }),
  "/api/result/curves": fitCurves(),
  "/api/report": () => ({ body: REPORT }),
};

/** A fit with a background and two phases' ticks — what the curve toggles and
 *  the tick band are about, and what the bare FITTED one has neither of. */
const TWO_PHASE = {
  "/api/result/curves": fitCurves({ y_background: [0.4, 0.4],
                                    header: { ticks: { NAC: [9.1], CaF2: [9.3] } } }),
};

/** A fit over the whole 3-24° the project measured, so a region, a peak and a
 *  zoom anywhere in it are in view. */
const WIDE = {
  "/api/result/curves": fitCurves({
    two_theta: [3, 6, 9, 9.4, 10, 12, 14, 18, 23.995],
    y_obs: [1, 2, 1, 2, 5, 3, 4, 1, 1] }),
};

/** MASKED_PROJECT's curves: 8-19° fitted less 13-16°, so two channels of seven. */
const MASKED_CURVES = {
  "/api/result/curves": fitCurves({
    two_theta: [3, 5, 9, 9.4, 14, 20, 23.995], y_obs: [5, 5, 1, 2, 6, 6, 6],
    kept: [2, 3], fitted: [2, 3] }),
};

/** The theme's plot inks as `curveColors` falls back to them: jsdom loads no
 *  stylesheet, so these are what the panel paints with here. */
const INK = {
  obs: "#8a8a8a", calc: "#c23b22", diff: "#1f5fa8", mask: "#1b1b1b14", edge: "#6b6b66",
  peak: "#8c257e", peakfit: "#c158b0", candidate: "#1a8f45",
  phase: ["#009e73", "#cc79a7"],
};

/** The chart's pane `key` in this test's host (`rxplot.panes`, over `test-uplot.ts`). */
function pane(key: "main" | "ticks" | "resid"): StubPlot {
  const u = StubPlot.instances.find((p) => p.key === key && host.contains(p.root));
  if (!u) throw new Error(`no ${key} pane is drawn`);
  return u;
}

const charted = () => StubPlot.instances.some((p) => host.contains(p.root));

/** The x range every pane shares. */
const xRange = (key: "main" | "ticks" | "resid" = "main") =>
  [pane(key).scales.x.min, pane(key).scales.x.max];

/** The ink series `index` was painted in, in its pane's last paint. */
const ink = (key: "main" | "ticks" | "resid", index: number) =>
  pane(key).marks.find((m) => m.op === "series" && m.index === index)?.style;

/** The main pane's curves the last paint showed and that hold something to
 *  draw, by `hidden`'s ids, then `diff` when the residual is shown. */
function drawn(): string[] {
  const ids = ["obs", "masked", "calc", "bkg"];
  const main = pane("main");
  const out = main.marks
    .filter((m) => m.op === "series" && main.data[m.index!].some((v: unknown) => v != null))
    .map((m) => ids[m.index! - 1]);
  if (pane("resid").marks.some((m) => m.op === "series")) out.push("diff");
  return out;
}

/** The ink of each tick row the band painted, top row first. */
const tickInks = () => pane("ticks").marks.filter((m) => m.op === "stroke").map((m) => m.style);

/** The 2θ of the channels series `index` of the main pane holds. */
const heldAt = (index: number) => {
  const u = pane("main");
  return Array.from(u.data[0] as ArrayLike<number>).filter((_, i) => u.data[index][i] != null);
};

/** The pointer over the pattern at 2θ `tt`, or off it: the events uPlot turns a mouse into. */
async function pointAt(tt: number | null) {
  const u = pane("main");
  if (tt === null) {
    u.over.dispatchEvent(new MouseEvent("mouseleave"));
  } else {
    u.over.dispatchEvent(new MouseEvent("mouseenter"));
    u.setCursor({ left: u.valToPos(tt, "x"), top: 10 });
  }
  await flush();
}

/** A drag across the whole height of the main pane from 2θ `lo` to `hi`, as
 *  uPlot hands it to the chart module: a zoom, or a selection when armed. */
async function dragOver(lo: number, hi: number) {
  const u = pane("main");
  const a = u.valToPos(lo, "x"), b = u.valToPos(hi, "x");
  u.setSelect({ left: a, width: b - a, top: 0, height: 300 });
  await flush();
}

const curvesFetched = (stub: { calls: Call[] }) =>
  stub.calls.filter((c) => c.path === "/api/result/curves").length;

const flush = async () => {
  for (let i = 0; i < 16; i++) await Promise.resolve();
  await new Promise((resolve) => setTimeout(resolve, 0));
  for (let i = 0; i < 16; i++) await Promise.resolve();
};

let host: HTMLDivElement;
let app: any;

function button(text: string): HTMLButtonElement | undefined {
  return [...host.querySelectorAll("button")].find((b) => b.textContent?.trim() === text);
}

function rowsInDom(): HTMLElement[] {
  return [...host.querySelectorAll<HTMLElement>(".row")];
}

/** The editable cell of the row whose leaf is `leaf` — by name, because the
 *  positions shift: a tied row renders a span rather than an input. */
function cell(leaf: string): HTMLInputElement {
  const row = rowsInDom().find((r) => r.querySelector(".path")?.textContent?.trim() === leaf);
  return row!.querySelector<HTMLInputElement>("input.value")!;
}

async function type(selector: string, value: string) {
  const input = host.querySelector<HTMLInputElement>(selector)!;
  input.value = value;
  input.dispatchEvent(new Event("input", { bubbles: true }));
  await flush();
}

beforeEach(() => {
  StubPlot.instances = [];
  host = document.createElement("div");
  document.body.appendChild(host);
  // the shell subscribes to the stream on mount; a session with no EventSource
  // falls back to polling, and the stub below is what it polls
  (globalThis as any).EventSource = undefined;
});

afterEach(() => {
  if (app) unmount(app);
  host.remove();
  vi.restoreAllMocks();
});

describe("the shell", () => {
  it("renders the no-project state as the import wizard, with its recent list", async () => {
    vi.stubGlobal("fetch", server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [{ path: "/tmp/a.rex", name: "a.rex" }] } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    // the empty state *is* the wizard (WP-1014) rather than a note about it
    expect(host.textContent).toContain("New project");
    expect(host.textContent).toContain("Choose a data file");
    expect(host.textContent).toContain("a.rex");
    expect(button("Create project")?.disabled).toBe(true);
    // Run is disabled without a project — the control follows the state, not hope
    expect(button("Run")?.disabled).toBe(true);
  });

  it("renders a project with no fit, and offers Run", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("synth.xye");
    expect(host.textContent).toContain("4200 pts");
    expect(host.textContent).toContain("σ from file");     // which weights the fit used
    expect(host.textContent).toContain("No fitted curves yet");
    // the panels still owed — empty since WP-1016 built the series panel, which
    // was the last one the v1.0 GUI plan named.  The assertion is kept (rather
    // than deleted with the list it was about) because the *mechanism* is what
    // makes the next owed panel visible: no WP number may appear in the Build
    // panel while nothing is owed.
    expect(host.textContent).toContain("every panel the v1.0 GUI plan named");
    expect(host.textContent).not.toMatch(/WP-\d{4}/);
    expect(button("Run")?.disabled).toBe(false);
  });

  it("shows the statistics and the stage while a run is in flight", async () => {
    const running = {
      ...IDLE_RUN,
      state: "running",
      run: { ...IDLE_RUN.run, kind: "fit", stage: "cell", stage_index: 3, n_stages: 5 },
    };
    vi.stubGlobal("fetch", server({
      ...boot(PROJECT, running),
      "/api/result": () => ({ body: { result: RESULT } }),
      "/api/result/curves": fitCurves(),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("cell");
    expect(host.textContent).toContain("(3/5)");           // 1-based, from stage_start
    expect(host.textContent).toContain("4.150%");          // Rwp as a percentage
    expect(button("Run")?.disabled).toBe(true);            // 409 made unclickable
    expect(button("Cancel")?.disabled).toBe(false);
  });

  it("drops the last run's Rwp once the result it described is gone", async () => {
    // An edit discards the curves server-side — `set_values`: "the fitted curve
    // and statistics described the *old* values" — but the run *frame* survives
    // it, so the header printed `Rwp 9.582%` beside a plot saying "No fitted
    // curves yet".  Found in WP-1034's browser pass, which is the first time
    // the two were on screen together.  The frame is still the live source
    // while a run is in flight, which is the case above.
    const ended = { ...IDLE_RUN,
                    run: { ...IDLE_RUN.run, kind: "fit", status: "converged",
                           rwp: 0.09582, gof: 3.633, node_id: "n0007" } };
    vi.stubGlobal("fetch", server(boot(PROJECT, ended)).fetcher);   // /api/result 409s
    app = mount(App, { target: host });
    await flush();

    expect(host.querySelector(".stats")?.textContent?.trim()).toBe("");
    expect(host.textContent).toContain("No fitted curves yet");
  });

  it("does not present a hopeless fit in the register of a good one", async () => {
    // WP-1029 item (c). The judgement is the *report's* — `maturity` quotes
    // MATURITY_MAX_RWP, the Rwp past which Layer 1 refuses to speak about
    // individual parameters — and `status` still says `converged`, because
    // that vocabulary is WP-1028's and two owners would disagree.
    const hopeless = {
      ...RESULT,
      status: "converged",
      statistics: { rwp: 0.963, gof: 18.4 },
      maturity: { immature: true, max_rwp: 0.35,
                  message: "Rwp 96.3% is past the point where the report will "
                    + "speak about individual parameters … the structure and the "
                    + "pattern are of the same specimen" },
    };
    vi.stubGlobal("fetch", server({
      ...boot(),
      "/api/result": () => ({ body: { result: hopeless } }),
      "/api/result/curves": fitCurves(),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.querySelector(".stats")?.classList.contains("immature")).toBe(true);
    // A chip, not a button (WP-1201): a chip is a fact and never acts, so the
    // judgement travels as a `bad` tone and the maturity message, and the panel
    // that explains it is reached from the tab strip like every other panel.
    // WP-1029 had made this badge a route to the Report tab; the register
    // vocabulary trades that shortcut for "a thing that acts looks like one".
    const flag = [...host.querySelectorAll<HTMLElement>(".stats .chip")]
      .find((c) => c.textContent?.trim() === "⚠ not a fit yet")!;
    expect(flag).toBeTruthy();
    expect(flag.tagName).toBe("SPAN");
    expect(flag.classList.contains("bad")).toBe(true);
    // …and the message is reachable (WP-1203).  It was this chip's `title=`,
    // which is exactly what a chip cannot carry: WP-1201 moved the badge off a
    // `<button>` and took the sentence out of reach of the keyboard with it.
    // The term inside the chip is focusable and answers Enter.
    const term = flag.querySelector<HTMLElement>(".help")!;
    expect(term.getAttribute("tabindex")).toBe("0");
    expect(flag.title).toBe("");
    term.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await flush();
    expect(host.ownerDocument.querySelector(".popover")?.textContent)
      .toContain("same specimen");
    // the calm pill is still there and still says `converged` — untouched
    expect(host.querySelector(".pill")?.textContent?.trim()).toBe("idle");
  });

  it("surfaces an open refusal verbatim rather than 'could not open'", async () => {
    const message =
      "file has changed since the project was created (sha256 1a2b3c4d, recorded 9f8e7d6c)";
    vi.stubGlobal("fetch", server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [{ path: "/tmp/a.rex", name: "a.rex" }] } }),
      "/api/project/open": () => ({ status: 400, body: { error: { code: "PROJECT_ERROR", message } } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    const open = [...host.querySelectorAll("button")].find((b) => b.textContent?.includes("a.rex"));
    open!.click();
    await flush();
    expect(host.textContent).toContain("sha256");
  });
});

// ----------------------------------------------------------------------
// the parameter table (WP-1011)
// ----------------------------------------------------------------------
const ADVANCED = { ...PROJECT, doc: { ...PROJECT.doc, ui: { simple: false } } };

describe("the parameter table", () => {
  it("groups rows and gives a held row no checkbox at all", async () => {
    vi.stubGlobal("fetch", server(boot(ADVANCED)).fetcher);
    app = mount(App, { target: host });
    await flush();

    // one heading per dot-path prefix, in the server's order
    const groups = [...host.querySelectorAll(".group")].map((g) => g.textContent?.trim());
    expect(groups?.[0]).toContain("phases.0.cell");
    expect(groups.some((g) => g?.includes("instrument.profile"))).toBe(true);

    expect(rowsInDom().length).toBe(PARAMS.parameters.length);
    // three of the six rows cannot be freed, and a checkbox that errors on click
    // is worse than no checkbox — so there are exactly three
    const boxes = host.querySelectorAll('.row input[type="checkbox"]');
    expect(boxes.length).toBe(3);
    // …and each held row says which of the three reasons holds it
    const held = rowsInDom().filter((row) => row.classList.contains("held"));
    expect(held.map((row) => row.dataset.held).sort()).toEqual(["locked", "mode", "tied"]);
    // …and the reason is reachable rather than hovered: WP-1203 moved it off
    // `title=` onto the glyph itself, which a keyboard can get to
    const glyph = host.querySelector<HTMLElement>('[data-held="tied"] .vary .help')!;
    expect(glyph.getAttribute("tabindex")).toBe("0");
    glyph.click();
    await flush();
    expect(host.querySelector(".popover")?.textContent).toContain("tied: =");
  });

  it("hides held rows in Simple mode and says how many", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);   // ui.simple defaults true
    app = mount(App, { target: host });
    await flush();

    expect(rowsInDom().length).toBe(3);
    expect(host.textContent).toContain("3 held hidden");   // a count, not a silent cut
  });

  it("shows a value to the precision its esd justifies", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    const value = host.querySelector<HTMLInputElement>(".row input.value");
    expect(value?.value).toBe("4.1568");                   // 4.1568(2), not 4.15678
    expect(host.textContent).toContain("(2)");
  });

  it("sends the glob for a bulk free — one round trip, one history node", async () => {
    const stub = server({ ...boot(ADVANCED), "/api/params": () => ({ body: PARAMS }) });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    await type("#param-filter", "phases.*.cell.*");
    // the preview counts what set_vary could actually free: a and b and alpha
    // match, but b is tied and alpha is locked, so only `a` is freeable — and it
    // is already free, leaving one to fix and none to free
    expect(button("Fix 1")).toBeTruthy();
    button("Fix 1")!.click();
    await flush();

    const patch = stub.calls.find((call) => call.method === "PATCH");
    expect(patch?.path).toBe("/api/params");
    expect(patch?.body).toEqual({ vary: { "phases.*.cell.*": false } });
    // the console echoes the call, which is the API this GUI is a front for
    expect(host.textContent).toContain('ref.set_vary("phases.*.cell.*", False)');
  });

  it("wraps a bare word as a substring glob, so preview and apply agree", async () => {
    const stub = server(boot(ADVANCED));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    await type("#param-filter", "cell");
    expect(rowsInDom().length).toBe(3);                    // a, b, alpha
    button("Free 0")?.click();                             // disabled: none freeable
    await flush();
    expect(stub.calls.some((call) => call.method === "PATCH")).toBe(false);
  });

  it("batches value edits into one set_values call", async () => {
    const stub = server(boot(ADVANCED));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    for (const [leaf, text] of [["a", "4.157"], ["scale", "1.05"]] as const) {
      const input = cell(leaf);
      input.value = text;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    }
    await flush();
    expect(host.textContent).toContain("2 pending edits");

    button("Apply")!.click();
    await flush();
    const patch = stub.calls.find((call) => call.method === "PATCH");
    expect(patch?.body).toEqual({
      values: { "phases.0.cell.a": 4.157, "phases.0.scale": 1.05 },
      vary: {},
    });
  });

  it("refuses an out-of-bounds value before the round trip", async () => {
    const stub = server(boot(ADVANCED));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const w = [...host.querySelectorAll<HTMLInputElement>(".row input.value")].at(-1)!;
    w.value = "2";                                          // instrument.profile.w is [0, 1]
    w.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();

    expect(w.classList.contains("bad")).toBe(true);
    expect(w.title).toContain("upper bound");
    // Apply is blocked, not silently partial — and Revert is still offered,
    // which is the affordance the bad cell most needs
    expect(button("Apply")?.disabled).toBe(true);
    expect(host.textContent).toContain("above the upper bound 1");
    button("Revert")!.click();
    await flush();
    expect(host.textContent).not.toContain("pending edit");
    expect(stub.calls.some((call) => call.method === "PATCH")).toBe(false);
  });

  it("shows the server's refusal in the server's own words", async () => {
    const message =
      "'phases.0.cell.b' follows 'phases.0.cell.a' as an affine tie; set that instead";
    const stub = server({
      ...boot(ADVANCED),
      "/api/params": (call) =>
        call.method === "PATCH"
          ? { status: 400, body: { error: { code: "INVALID_REQUEST", message,
                                            where: ["phases.0.cell.b"] } } }
          : { body: PARAMS },
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const input = host.querySelector<HTMLInputElement>(".row input.value")!;
    input.value = "4.2";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    expect(host.textContent).toContain("as an affine tie; set that instead");
  });
});

// ----------------------------------------------------------------------
// the plan editor and the disclosure toggle (WP-1011)
// ----------------------------------------------------------------------
describe("the plan editor", () => {
  async function openPlan(project: any = PROJECT, extra: Record<string, any> = {}) {
    const stub = server({ ...boot(project), ...extra });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Plan")!.click();
    await flush();
    return stub;
  }

  it("lists the stages the run will actually execute, and names the preset", async () => {
    await openPlan();
    const names = [...host.querySelectorAll<HTMLInputElement>(".name")].map((i) => i.value);
    expect(names).toEqual(["scale+bkg", "cell"]);
    expect(host.querySelector<HTMLSelectElement>("select")?.value).toBe("mccusker_default");
    // the preset's own words, from PLAN_INFO through /api/plans.  `description`
    // is the visible one since WP-1208 and `when_to_use` is in the popover, so
    // this is the line a person reads without clicking anything
    expect(host.textContent).toContain("Scale and background, zero shift, cell,");
    // …and the explainer above it, which is the panel's whole subject
    expect(host.textContent).toContain("A plan is an ordered list of stages.");
  });

  it("resolves each stage against the live table, and says what it holds", async () => {
    // WP-1208: the ladder is `GET /api/plan/resolve`, never a client-side glob
    // match — what a stage frees is its matches minus what is tied, locked,
    // mode-fixed or degenerate with a free cell
    await openPlan();
    const rungs = [...host.querySelectorAll("ol.stages > li .rung summary")]
      .map((n) => n.textContent!.replace(/\s+/g, " ").trim());
    expect(rungs).toEqual([
      "1 · +2 → 2 free · Rwp 95.35%",
      "2 · +1 → 3 free · 1 held · Rwp 44.57%",
    ]);
    expect(host.textContent).toContain("Ends with 5 of 12 parameters free.");
    // the held row carries the server's own sentence, never one written here
    expect(host.textContent).toContain("phases.0.cell.b");
    const held = [...host.querySelectorAll(".rung .body .help")];
    expect(held.map((n) => n.getAttribute("aria-haspopup"))).toEqual(["dialog"]);
  });

  it("refuses both of its run buttons at zero phases, in the shell's words",
     async () => {
    // WP-1207: zero phases is a legal state and every run verb refuses it, so
    // a client must disable rather than offer a click whose only outcome is a
    // 409. The panel's two buttons did not (found by `/code-review`), and the
    // repair must not spell the reason a second time — the shell's sentence
    // names the route out, and a local copy said something else.
    await openPlan({ ...PROJECT, n_phases: 0 });
    const runAll = button("Run all")!;
    const runStage = [...host.querySelectorAll<HTMLButtonElement>(
      "ol.stages > li .rung button")].filter(
        (b) => b.textContent?.trim() === "Run this stage");
    expect(runAll.disabled).toBe(true);
    expect(runStage.length).toBeGreaterThan(0);
    expect(runStage.every((b) => b.disabled)).toBe(true);

    const header = button("Run")!;
    expect(header.disabled).toBe(true);
    // one sentence, three buttons
    expect(runAll.title).toBe(header.title);
    expect(runStage[0].title).toBe(header.title);
    expect(header.title).toContain("no phase yet");

    // …and with a phase, all three act again
    unmount(app);
    app = null;
    host.innerHTML = "";
    await openPlan();
    expect(button("Run all")!.disabled).toBe(false);
    expect(button("Run")!.disabled).toBe(false);
  });

  it("hides the resolved facts while the plan on screen is not the server's", async () => {
    await openPlan(PROJECT, {
      "/api/plan": (call: Call) => ({ body: call.method === "PUT" ? { ...PLAN, preset: null } : PLAN }),
    });
    expect(host.querySelector(".rung summary")).not.toBeNull();
    const first = host.querySelector<HTMLInputElement>("ol.stages > li input.globs")!;
    first.value = "instrument.*";
    first.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();

    expect(host.querySelector(".rung summary")).toBeNull();
    expect(host.textContent).toContain("Save the plan to see what its stages free");
    // …and Run all is refused meanwhile, because it would run the saved plan
    expect(button("Run all")!.disabled).toBe(true);
  });

  it("runs one stage through the same machinery a whole fit uses", async () => {
    const stub = await openPlan();
    const runs = [...host.querySelectorAll<HTMLButtonElement>("ol.stages > li .rung button")]
      .filter((b) => b.textContent?.trim() === "Run this stage");
    expect(runs).toHaveLength(2);
    runs[1].click();
    await flush();

    const post = stub.calls.find((call) => call.path === "/api/run");
    expect(post?.body.kind).toBe("stage");
    expect(post?.body.stage).toMatchObject({ name: "cell", turn_on: ["phases.*.cell.*"] });
    expect(host.textContent).toContain('ref.run_stage(Stage("cell"');
  });

  it("stores a picked preset expanded through the mode", async () => {
    const stub = await openPlan(PROJECT, {
      "/api/plan": (call: Call) =>
        call.method === "PUT"
          ? { body: { ...PLAN, preset: "profile_only" } }
          : { body: PLAN },
    });
    const select = host.querySelector<HTMLSelectElement>("select")!;
    select.value = "profile_only";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    const put = stub.calls.find((call) => call.method === "PUT");
    expect(put?.path).toBe("/api/plan");
    expect(put?.body).toEqual({ preset: "profile_only" });
  });

  it("keeps a stage's advanced fields behind the disclosure", async () => {
    await openPlan();
    expect(host.querySelector(".advanced")).toBeNull();
    unmount(app);
    app = null;
    host.innerHTML = "";
    await openPlan(ADVANCED);
    expect(host.querySelector(".advanced")).not.toBeNull();
    expect(host.textContent).toContain("strain");           // Stage.strain_seed
    expect(host.textContent).toContain("correlation guard");

    // …and it offers *every* stage field, because the list is derived from
    // `lib/rxt.ts`'s stage words rather than typed out here (WP-1208).  Those
    // are pinned to `StageSpec` from python, so a schema field cannot reach
    // the `.rxt` document and miss this form.
    const boxes = host.querySelectorAll("ol.stages > li .advanced label");
    expect(boxes.length).toBe((STAGE_WORDS.length - 1) * PLAN.plan.stages.length);
    const helped = [...host.querySelectorAll("ol.stages > li:first-child .advanced .help")]
      .map((n) => n.textContent!.trim());
    expect(helped).toHaveLength(STAGE_WORDS.length - 1);
    // the two fields that were only reachable through the text document
    expect(helped).toContain("ftol");
    expect(helped).toContain("slack");
  });

  it("reorders stages by drag, and offers to save the edited plan", async () => {
    const stub = await openPlan(PROJECT, {
      "/api/plan": (call: Call) => ({ body: call.method === "PUT" ? { ...PLAN, preset: null } : PLAN }),
    });
    // jsdom has no DragEvent; the handlers read only the indices they were
    // bound with, so a plain Event of the same type drives them identically
    const items = [...host.querySelectorAll("ol.stages > li")];
    items[1].dispatchEvent(new Event("dragstart", { bubbles: true }));
    items[0].dispatchEvent(new Event("drop", { bubbles: true }));
    await flush();

    const names = [...host.querySelectorAll<HTMLInputElement>(".name")].map((i) => i.value);
    expect(names).toEqual(["cell", "scale+bkg"]);
    button("Save plan")!.click();
    await flush();

    const put = stub.calls.find((call) => call.method === "PUT");
    expect(put?.body.plan.stages.map((s: any) => s.name)).toEqual(["cell", "scale+bkg"]);
    expect(put?.body.plan.correlation_guard).toBe(0.98);
  });
});

// ----------------------------------------------------------------------
// the history worktree and the report panel (WP-1012)
// ----------------------------------------------------------------------
async function openTab(name: string, project: any = PROJECT,
                       extra: Record<string, any> = {}) {
  const stub = server({ ...boot(project), ...extra });
  vi.stubGlobal("fetch", stub.fetcher);
  app = mount(App, { target: host });
  await flush();
  button(name)!.click();
  await flush();
  return stub;
}

describe("the history worktree", () => {
  it("draws the DAG with a second lane for the fork, and marks HEAD", async () => {
    await openTab("History");
    // four nodes, and the fork (n0003 from n0001, which already had n0002) needs
    // a second rail — this DAG has no refs, so a lane is where it divided
    expect(host.querySelectorAll(".node").length).toBe(4);
    expect(host.querySelectorAll("svg.rail circle").length).toBe(4);
    expect(host.textContent).toContain("2 lanes");
    expect(host.querySelector("svg.rail circle.head")).not.toBeNull();

    // the action, not the id — and Rwp with its move against the first parent
    expect(host.textContent).toContain("scale+bkg");
    expect(host.textContent).toContain("free 3 paths");
    expect(host.textContent).toContain("4.00%");
    expect(host.textContent).toContain("▾17.00");           // 0.04 against 0.21
    expect(host.textContent).toContain("best-so-far");      // a tag chip
    expect(host.textContent).toContain("⚠ 1");              // a node's diagnostics
  });

  it("shows the selected node's api_call and its guard finding's paths", async () => {
    await openTab("History");
    const rows = [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")];
    rows[2].click();                                        // n0002
    await flush();
    expect(host.querySelector(".call")?.textContent).toContain("rx.Stage('cell'");
    // WP-1007: `where` carries the pair, so no message needs parsing
    expect(host.textContent).toContain("HIGH_CORRELATION");
    expect(host.textContent).toContain("phases.0.cell.a instrument.zero_shift");
  });

  it("checks a node out and tells the shell the curves are gone", async () => {
    const stub = await openTab("History", PROJECT, {
      ...FITTED,
      "/api/history/checkout": () => ({ body: { head: "n0002", parameters: [], n_free: 0 } }),
    });
    [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
    await flush();
    expect(host.textContent).toContain("Checking out discards the fitted curves");

    const before = stub.calls.filter((c) => c.path === "/api/result").length;
    button("Checkout")!.click();
    await flush();
    const post = stub.calls.find((c) => c.path === "/api/history/checkout");
    expect(post?.body).toEqual({ node_id: "n0002" });
    // …and the shell refetched: a checkout discards the result server-side, so a
    // plot of the old curves would be a plot of a state the project is not in
    expect(stub.calls.filter((c) => c.path === "/api/result").length).toBe(before + 1);
    expect(host.textContent).toContain('ref.checkout("n0002")');
  });

  it("branches by naming a fork point — checkout plus tag, not a new ref", async () => {
    const stub = await openTab("History", PROJECT, {
      ...FITTED,
      "/api/history/branch": () => ({ body: { branched_from: "n0002", name: "keeper",
                                              head: "n0002", parameters: [] } }),
    });
    [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
    await flush();
    await type("footer input", "keeper");
    button("Branch")!.click();
    await flush();
    const post = stub.calls.find((c) => c.path === "/api/history/branch");
    expect(post?.body).toEqual({ node_id: "n0002", name: "keeper" });
  });

  it("compares two nodes through diff, ranked, with the metrics beside it", async () => {
    const stub = await openTab("History", PROJECT, {
      "/api/history/diff": () => ({ body: { a: "n0001", b: "n0002", diff: {
        "phases.0.cell.a": [4.1566, 4.1568], "instrument.profile.w": [0.00025, 0.0005] } } }),
      "/api/history/compare": () => ({ body: { rows: [
        { id: "n0001", rwp: 0.21, n_free: 4, action: "stage:scale+bkg" },
        { id: "n0002", rwp: 0.04, n_free: 5, action: "stage:cell" }] } }),
    });
    const nodes = [...host.querySelectorAll<HTMLElement>(".node")];
    nodes[1].querySelector<HTMLButtonElement>("button.pick")!.click();
    await flush();
    nodes[2].querySelector<HTMLButtonElement>("button.ghost")!.click();   // ⇄
    await flush();

    expect(stub.calls.some((c) => c.url.includes("/api/history/diff?a=n0001&b=n0002"))).toBe(true);
    expect(host.textContent).toContain("2 paths differ");
    // biggest relative move first: w doubled, a moved 5e-5
    const rows = [...host.querySelectorAll(".drow:not(.heads)")];
    expect(rows.map((n) => n.querySelector(".path")?.textContent?.trim()))
      .toEqual(["instrument.profile.w", "phases.0.cell.a"]);
    expect(host.textContent).toContain("21.00% → 4.00%");
    // each side at its family's own places, the difference twice (WP-1217): the
    // percentage is what says a 5e-5 Å move on a 4.15 Å axis is 48 ppm
    expect([...rows[1].querySelectorAll("span")].map((n) => n.textContent?.trim()))
      .toEqual(["phases.0.cell.a", "4.15660", "4.15680", "+0.00020", "+0.00481%"]);
    expect([...rows[0].querySelectorAll("span")].map((n) => n.textContent?.trim()))
      .toEqual(["instrument.profile.w", "0.000250", "0.000500", "+0.000250", "+100%"]);
  });
});

describe("the report panel", () => {
  it("renders the layers, and an unapplicable suggestion keeps its reason", async () => {
    await openTab("Report", PROJECT, FITTED);
    expect(host.textContent).toContain("21.600%");
    expect(host.textContent).toContain("Layer 1 on 15/15 regions");
    expect(host.textContent).toContain("1 unindexed");
    // the gates that refused, by name, counted — the values are on the row
    expect(host.textContent).toContain("local_r2 ×1");

    const actions = [...host.querySelectorAll<HTMLElement>(".action")];
    // applicable first, then the veto, then advice — and nothing is dropped
    expect(actions.map((a) => a.querySelector(".kind")?.textContent?.trim()))
      .toEqual(["refine_cell", "refine_scale", "add_impurity_phase"]);
    expect(actions[1].textContent).toContain("already refined by the staged plan");
    expect(actions[2].textContent).toContain("no phase is named yet");
    // one Apply button: the other two are refusals with reasons, not controls
    expect(host.querySelectorAll(".action button:not(.ghost)").length).toBe(1);
    // 0.5 is capped by the collinear templates, so it must not read as confident
    expect(actions[0].dataset.tone).toBe("medium");
  });

  it("says the predicted Δχ² is the report's, once, not per suggestion", async () => {
    await openTab("Report", PROJECT, FITTED);
    expect(host.textContent).toContain("one estimate for the whole report");
    // the figure appears once, in the note — not in a column beside three rows
    expect(host.textContent!.split("16.19").length - 1).toBe(1);
  });

  it("zooms the plot to a region, padded, and fetches nothing to do it", async () => {
    const stub = await openTab("Report", PROJECT, FITTED);
    const rows = [...host.querySelectorAll<HTMLButtonElement>(".trow")];
    // ranked by χ² share: the 9.0–9.4° region leads, not the worse local Rwp one
    expect(rows[0].textContent).toContain("9.00–9.40");
    const fetched = curvesFetched(stub);
    rows[0].click();
    await flush();
    // padded by 35 % of its own width, so a one-peak region arrives with a
    // baseline; and it is an axis move and nothing else, since the payload is
    // every channel already (WP-1461) — where a window used to be refetched
    const [lo, hi] = xRange();
    expect(lo).toBeCloseTo(8.86, 10);
    expect(hi).toBeCloseTo(9.54, 10);
    expect(xRange("resid")).toEqual([lo, hi]);
    expect(curvesFetched(stub)).toBe(fetched);
  });

  it("applies a suggestion and measures it, with undo as a checkout", async () => {
    const stub = await openTab("Report", PROJECT, {
      ...FITTED,
      "/api/report/apply": () => ({ body: {
        applied: { kind: "refine_cell", confidence: 0.5, rationale: "…",
                   expected_delta_chi2: 16.19,
                   stage: { name: "apply:refine_cell", turn_on: ["phases.*.cell.*"] } },
        api_call: "ref.run_stage(data, rx.Stage('apply:refine_cell', ['phases.*.cell.*'], max_iter=100))",
        undo: "n0003", chi2_before: 16.96,
        state: "running", run: { ...IDLE_RUN.run, kind: "stage" }, head: "n0003" } }),
    });
    button("Apply")!.click();
    await flush();

    const post = stub.calls.find((c) => c.path === "/api/report/apply");
    expect(post?.body).toEqual({ kind: "refine_cell", paths: ["phases.*.cell.*"] });
    // the console echoes the stage the server said it would run
    expect(host.textContent).toContain("rx.Stage('apply:refine_cell'");
    // mid-run the observed value is *absent*, not zero: `chi2` is still the one
    // the action was applied at, and subtracting it would print a confident
    // "observed 0.000" for a measurement nobody has made
    expect(host.textContent).toContain("observed running…");
    expect(host.textContent).toContain("applied refine_cell");
    // …and Undo waits for the stage: a checkout mid-run is what the server 409s
    expect(button("Undo")?.disabled).toBe(true);
  });

  it("puts the observed Δχ² beside the predicted one, and undoes by checkout", async () => {
    // The applied stage runs and finishes, and the shell learns *only* from the
    // state frame that carries the outcome — which is the case a transition test
    // ("have I seen a running frame?") misses on a stage this fast, leaving the
    // previous fit's curves and χ² on screen.
    let done = false;
    let reads = 0;
    const finished = { state: "idle", project: PROJECT.path, head: "n0004",
                       run: { ...IDLE_RUN.run, kind: "stage", status: "converged",
                              node_id: "n0004" } };
    const stub = await openTab("Report", PROJECT, {
      ...FITTED,
      "/api/result": () => ({ body: { result: { ...RESULT, statistics: {
        rwp: 0.216, gof: 1.41, chi2: reads++ ? 0.63 : 16.96 } } } }),
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1,
                                      ...(done ? finished : IDLE_RUN) } }),
      "/api/report/apply": () => {
        done = true;
        return { body: {
          applied: { kind: "refine_cell", expected_delta_chi2: 16.19,
                     stage: { name: "apply:refine_cell" } },
          api_call: "ref.run_stage(data, rx.Stage('apply:refine_cell', ['phases.*.cell.*'], max_iter=100))",
          undo: "n0003", chi2_before: 16.96,
          state: "running", run: { ...IDLE_RUN.run, kind: "stage" }, head: "n0003" } };
      },
      "/api/history/checkout": () => ({ body: { head: "n0003", parameters: [], n_free: 0 } }),
    });
    button("Apply")!.click();
    await flush();
    await new Promise((resolve) => setTimeout(resolve, 800)); // one poll interval
    await flush();

    expect(host.textContent).toContain("predicted Δχ² 16.19");
    expect(host.textContent).toContain("observed 16.33");

    // undo needs no inverse verb: the head before the apply is a history node
    button("Undo")!.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/history/checkout")?.body)
      .toEqual({ node_id: "n0003" });
    expect(host.textContent).not.toContain("applied refine_cell");
  });

  it("keeps the per-region coefficients behind the disclosure", async () => {
    await openTab("Report", PROJECT, FITTED);
    expect(host.textContent).not.toContain("Attribution");
    unmount(app);
    app = null;
    host.innerHTML = "";
    await openTab("Report", ADVANCED, FITTED);
    expect(host.textContent).toContain("Attribution");
    // a trend the report itself calls non-separable must say so where it is read:
    // its confidence was already capped, and the alternatives travel with it
    expect(host.textContent).toContain("not separable");
    expect(host.textContent).toContain("tan_theta");
  });

  it("renders an abstention as an abstention", async () => {
    const abstained = {
      ...REPORT,
      report: { ...REPORT.report, layer1_available: false, attribution: [], trends: [],
                abstained_reason: "fit is immature (Rwp=0.407 > 0.35); Layer 1 abstains",
                suggested_actions: [REPORT.report.suggested_actions[2]] },
      apply: [REPORT.apply[2]],
    };
    await openTab("Report", PROJECT, { ...FITTED, "/api/report": () => ({ body: abstained }) });
    expect(host.textContent).toContain("Layer 1 abstained");
    expect(host.textContent).toContain("fit is immature");
    // the model-free action survives the abstention, which is the whole point
    expect(host.textContent).toContain("add_impurity_phase");
  });

  it("says there is nothing to report on before a fit, without erroring", async () => {
    await openTab("Report");                            // /api/report 409s NO_RESULT
    expect(host.textContent).toContain("No fit to report on yet");
    expect(host.querySelector(".bad")).toBeNull();
  });
});

describe("disclosure and the command palette", () => {
  it("persists Simple/Advanced to the project's ui keys on the verb", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    button("Advanced")!.click();
    await flush();
    const post = stub.calls.find((call) => call.method === "POST" && call.path === "/api/project");
    // settings persist on the verb, not on a later save (WP-1005/1008)
    expect(post?.body).toEqual({ ui: { simple: false } });
    expect(rowsInDom().length).toBe(PARAMS.parameters.length);  // held rows are back
  });

  it("opens on Cmd-K and shows the API call behind every command", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
    await flush();
    expect(host.textContent).toContain("Run the fit");
    expect(host.textContent).toContain("ref.fit(data, plan=…)");
    expect(host.textContent).toContain("ref.set_vary(glob, True)");
    // Cancel is shown greyed rather than hidden: that is how the shortcut is learnt
    const cancel = [...host.querySelectorAll("button")]
      .find((b) => b.textContent?.includes("Cancel the run"));
    expect(cancel?.disabled).toBe(true);
  });

  it("gives the console a fixed height it can be dragged out of", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    // sized, not flexible: sharing the sidebar with `flex: 1 1 auto` gave the
    // log half the column, which is the wrong split for a panel read in glances
    const panel = host.querySelector<HTMLElement>("section.console")!;
    expect(panel.style.flex).toBe("0 0 150px");

    // `.grip` is also the plan editor's drag handle, and `.caret` is a group
    // header's — scope to the console or the query finds a hidden panel's
    const grip = host.querySelector<HTMLElement>("section.console .grip")!;
    grip.dispatchEvent(new MouseEvent("pointerdown", { clientY: 400, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointermove", { clientY: 340, bubbles: true }));
    await flush();
    expect(panel.style.flex).toBe("0 0 210px");            // dragging up grows it

    window.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await flush();
    // one write per drag, not one per pixel — and it lands in the project's ui
    const writes = stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project");
    expect(writes).toHaveLength(1);
    expect(writes[0].body).toEqual({ ui: { console_height: 210 } });
  });

  it("selects the layout from one segmented control, and keeps the plot mounted", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    // WP-1034: the top-level choice is no longer *which pane* — Model and Text
    // are tabs — it is how much window the panel column gets.  Two options, the
    // current one lit, and neither click means two things (WP-1029's rule).
    const group = host.querySelector<HTMLElement>('[aria-label="layout"]')!;
    const labels = [...group.querySelectorAll("button")].map((b) => b.textContent?.trim());
    expect(labels).toEqual(["Split", "Full"]);
    expect(group.querySelector("button.on")?.textContent?.trim()).toBe("Split");
    expect(host.querySelector(".plotcol")?.classList.contains("hidden")).toBe(false);

    button("Full")!.click();
    await flush();
    expect(host.querySelector(".side")?.classList.contains("wide")).toBe(true);
    // hidden, not unmounted — a layout click must not purge the drawn window
    expect(host.querySelector(".plotcol")?.classList.contains("hidden")).toBe(true);
    expect(host.querySelector(".plot")).not.toBeNull();
    // the tab strip travels with the column, which is what makes this a hatch
    // for every panel rather than for the two that used to have their own mode
    // — nine since WP-1016, which needed no mode of its own for exactly this
    expect(host.querySelectorAll("nav.tabs button").length).toBe(9);
    // …and no splitter, because there is nothing on the other side of it
    expect(host.querySelector('.side > .grip[data-grow="left"]')).toBeNull();

    button("Split")!.click();
    await flush();
    expect(group.querySelector("button.on")?.textContent?.trim()).toBe("Split");
    // a layout is a view choice, not a setting: nothing reached the document
    expect(host.querySelector(".side")?.classList.contains("wide")).toBe(false);
  });

  it("carries nine tabs with no label shortened and every panel reachable", async () => {
    const stub = server({ ...boot(), ...FITTED });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const tabs = [...host.querySelectorAll<HTMLButtonElement>("nav.tabs button")];
    expect(tabs.map((b) => b.textContent?.trim())).toEqual([
      "Parameters", "Plan", "Peaks", "Model", "Text", "Series", "Report",
      "History", "Build"]);
    // the overflow rule is `flex-wrap` plus `min-width: max-content`: a strip
    // that hides a tab or elides its name is worse than the mode buttons it
    // replaced, so the *count* and the *labels* are the assertion jsdom can make
    expect(tabs.every((b) => (b.textContent ?? "").trim().length > 0)).toBe(true);

    for (const [label, marker] of [["Plan", "scale+bkg"], ["Peaks", "peak"],
                                   ["Series", "No patterns staged"],
                                   ["Report", "21.600%"], ["History", "2 lanes"],
                                   // the owed list is empty since this panel
                                   // landed — the last one the plan named
                                   ["Build", "every panel the v1.0"]] as const) {
      button(label)!.click();
      await flush();
      expect(host.textContent?.toLowerCase()).toContain(marker.toLowerCase());
    }
    // every panel is still in the document after the tour — switching must not
    // throw away a filter, a pending edit or a two-node comparison
    expect(host.querySelectorAll(".side .panel").length).toBe(9);
  });

  it("stamps an explicit theme on the root and persists the choice", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    // no choice stored → "system", and jsdom's matchMedia stub reports light
    expect(document.documentElement.dataset.theme).toBe("light");

    const dark = [...host.querySelectorAll("button")].find((b) => b.getAttribute("aria-label") === "dark");
    dark!.click();
    await flush();
    expect(document.documentElement.dataset.theme).toBe("dark");
    // …and `color-scheme` with it, which is what the unstyled native controls read
    expect(document.documentElement.style.colorScheme).toBe("dark");

    // …to the *app's* settings, not the project's (WP-1044)
    const post = stub.calls.find((call) => call.method === "POST" && call.path === "/api/settings");
    expect(post?.body).toEqual({ ui: { theme: "dark" } });
    expect(stub.calls.some((call) => call.method === "POST" && call.path === "/api/project"))
      .toBe(false);
  });

  it("restores the person's theme, and the project has no say in it (WP-1044)", async () => {
    // The defect: `readUi` re-read the choice off whichever document was open,
    // so a project that had never been told reset it — measured in Chrome,
    // choosing dark and opening a second project came back `system`. The
    // project below carries a stale `ui.theme` from before this moved, and the
    // page must ignore it: one authority, and it is not this one.
    const stale = { ...PROJECT, doc: { ...PROJECT.doc, ui: { theme: "light" } } };
    const stub = server(boot(stale, IDLE_RUN, { theme: "dark" }));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(document.documentElement.dataset.theme).toBe("dark");
    const on = [...host.querySelectorAll<HTMLElement>('[aria-label="theme"] button')]
      .find((b) => b.classList.contains("on"));
    expect(on?.getAttribute("aria-label")).toBe("dark");
  });

  it("offers the theme with no project open — the empty state is a screen too",
     async () => {
    const stub = server(boot(null));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const dark = [...host.querySelectorAll("button")]
      .find((b) => b.getAttribute("aria-label") === "dark");
    expect(dark).toBeTruthy();
    dark!.click();
    await flush();
    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(stub.calls.find((c) => c.method === "POST" && c.path === "/api/settings")?.body)
      .toEqual({ ui: { theme: "dark" } });
  });

  it("repaints the plot on a theme change — new ink, no refetch", async () => {
    // The canvas keeps whatever colours it was painted with, so a draw that
    // does not depend on the theme leaves the old theme's text on the new
    // theme's page — light grey on white, found by use within hours of the
    // toggle landing (WP-1029 q).  The colours come from the `--plot-*` custom
    // properties, sampled at *paint* time; jsdom loads no stylesheet, so the
    // un-set ones are the fallbacks and a set one is ours.
    document.body.style.setProperty("--plot-obs", "#112233");
    try {
      const stub = server({ ...boot(), ...FITTED });
      vi.stubGlobal("fetch", stub.fetcher);
      app = mount(App, { target: host });
      await flush();

      expect(ink("main", 1)).toBe("#112233");
      expect(ink("resid", 1)).toBe(INK.diff);
      // …and the zero line under the residual, in a token of its own
      expect(pane("resid").marks.some((m) => m.op === "stroke" && m.style === "#88888888"))
        .toBe(true);

      const fetched = curvesFetched(stub);
      const painted = pane("main").paints;
      // what the dark stylesheet does in a browser, done by hand here
      document.body.style.setProperty("--plot-obs", "#445566");
      [...host.querySelectorAll("button")]
        .find((b) => b.getAttribute("aria-label") === "dark")!.click();
      await flush();

      // a repaint with the new colours — and *not* a refetch: the numbers did
      // not move, only the ink did
      expect(pane("main").paints).toBeGreaterThan(painted);
      expect(ink("main", 1)).toBe("#445566");
      expect(curvesFetched(stub)).toBe(fetched);
    } finally {
      document.body.style.removeProperty("--plot-obs");
    }
  });

  it("does not repaint curves a checkout discarded when the theme changes", async () => {
    // A checkout clears the result server-side, and the figure goes with it —
    // WP-1012's rule applied to the copy in hand: when the result goes, what
    // was drawn from it goes too, so the theme buttons (always in the header)
    // cannot redraw a state the project is no longer in.
    let fitted = true;
    const stub = server({
      ...boot(),
      ...FITTED,
      "/api/result": () =>
        fitted
          ? { body: { result: { ...RESULT, statistics: { rwp: 0.216, gof: 1.41, chi2: 16.96 } } } }
          : { status: 409, body: { error: { code: "NO_RESULT", message: "none" } } },
      "/api/history/checkout": () => {
        fitted = false;
        return { body: { head: "n0002", parameters: [], n_free: 0 } };
      },
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    expect(charted()).toBe(true);              // the fitted curves were drawn

    button("History")!.click();
    await flush();
    [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
    await flush();
    button("Checkout")!.click();
    await flush();
    expect(charted()).toBe(false);             // the figure went with them

    const built = StubPlot.instances.length;
    [...host.querySelectorAll("button")]
      .find((b) => b.getAttribute("aria-label") === "dark")!.click();
    await flush();
    expect(charted()).toBe(false);             // nothing to repaint, so nothing built
    expect(StubPlot.instances.length).toBe(built);
  });

  it("gives the reflection ticks a band of their own, not the residual's pane", async () => {
    // On the residual's axis their visibility was a property of which residual
    // was selected: under cumulative χ², whose values ran to 6.6e5 on the
    // measured NAC fit, the rows at y = −0.5 were a line on the floor (WP-1032).
    const stub = server({ ...boot(), ...FITTED, ...TWO_PHASE });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    // one row each, in each phase's own ink (WP-1438), in a pane whose y means
    // nothing and cannot be zoomed
    const ticks = pane("ticks");
    const rows = ticks.marks.filter((m) => m.op === "stroke");
    expect(rows.map((m) => m.style)).toEqual(INK.phase);
    const mid = ticks.bbox.top + ticks.bbox.height / 2;
    expect(rows[0].points!.every(([, y]) => y <= mid)).toBe(true);
    expect(rows[1].points!.every(([, y]) => y >= mid)).toBe(true);
    expect(ticks.opts.scales.y.range()).toEqual([0, 1]);
    // …and the residual keeps a pane of its own
    expect(ink("resid", 1)).toBe(INK.diff);
  });

  it("draws no box over the data: no legend, and no mark at the cursor", async () => {
    // WP-1213 deleted this plot's hover box on a report that it covered the
    // data, and WP-1438 found plotly drawing a second one of its own. uPlot can
    // draw either kind (a legend that follows the cursor, a point on each
    // series), and this panel takes neither: what the pointer is over is said
    // in the strip under the plot.
    const stub = server({ ...boot(), ...FITTED, ...TWO_PHASE });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    for (const key of ["main", "ticks", "resid"] as const) {
      expect(pane(key).opts.legend.show, key).toBe(false);
      expect(pane(key).opts.cursor.points.show, key).toBe(false);
    }
  });

  it("drops a curve the user switched off, without asking the server again", async () => {
    // The background trace was already unconditional, so the reported
    // "toggle the background on" is a missing *control*, not a missing trace.
    // And a drawing choice is not persisted (WP-1015's rule, one panel over).
    const stub = server({ ...boot(), ...FITTED, ...TWO_PHASE });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const curves = host.querySelector<HTMLElement>('.segmented[aria-label="curves"]')!;
    expect([...curves.querySelectorAll("button")].map((b) => b.textContent!.trim()))
      .toEqual(["obs", "calc", "bkg", "Δ/σ", "NAC", "CaF2"]);
    expect(drawn()).toContain("bkg");

    const fetched = curvesFetched(stub);
    [...curves.querySelectorAll("button")].find((b) => b.textContent!.trim() === "bkg")!.click();
    await flush();
    expect(drawn()).not.toContain("bkg");
    expect(drawn()).toContain("calc");
    expect(curvesFetched(stub)).toBe(fetched);

    // one phase's ticks off, the other's still drawn, in the ink it had
    [...curves.querySelectorAll("button")].find((b) => b.textContent!.trim() === "CaF2")!.click();
    await flush();
    expect(tickInks()).toEqual([INK.phase[0]]);

    // nothing about a picture reached the project document
    expect(stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project")).toEqual([]);
  });

  it("drags the panel column wider and persists the width once", async () => {
    // the sidebar starts on the CSS clamp — `null`, so a fresh project is
    // responsive rather than frozen at the first window it was opened in
    const sized = { ...PROJECT, doc: { ...PROJECT.doc, ui: { side_width: 420 } } };
    const stub = server(boot(sized));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const side = host.querySelector<HTMLElement>(".side")!;
    expect(side.style.flex).toBe("0 0 420px");

    const grip = side.querySelector<HTMLElement>(':scope > .grip[data-grow="left"]')!;
    grip.dispatchEvent(new MouseEvent("pointerdown", { clientX: 900, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 820, bubbles: true }));
    await flush();
    expect(side.style.flex).toBe("0 0 500px");              // dragging left grows it

    window.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await flush();
    const writes = stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project");
    expect(writes).toHaveLength(1);
    expect(writes[0].body).toEqual({ ui: { side_width: 500 } });
  });

  it("lays the cell out as one row of six, in crystallography's letters", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();

    const labels = [...host.querySelectorAll(".cellrow .cell > span:first-child")]
      .map((s) => s.textContent?.trim());
    expect(labels).toEqual(["a", "b", "c", "α", "β", "γ"]);
    // the *path* keeps the spelled-out name: a glyph in one would be a second
    // vocabulary for the same field
    expect(host.querySelector('[data-field="phases.0.cell.alpha"]')
      ?? host.querySelector(".cellrow .fixed")).toBeTruthy();
  });

  it("drags a model column and persists both widths together", async () => {
    const stub = server(boot({ ...PROJECT,
      doc: { ...PROJECT.doc, ui: { model_columns: [400, 380] } } }));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();

    const columns = [...host.querySelectorAll<HTMLElement>(".column")];
    expect(columns[0].style.flex).toBe("0 0 400px");
    expect(columns[1].style.flex).toBe("0 0 380px");

    // the grips are flex items *between* the columns, not absolute children of
    // them: a column scrolls, and an absolute edge inside `overflow: auto`
    // scrolls away from the edge it is supposed to be
    const grip = host.querySelector<HTMLElement>('.editors > .grip[data-flow="inline"]')!;
    grip.dispatchEvent(new MouseEvent("pointerdown", { clientX: 400, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointermove", { clientX: 460, bubbles: true }));
    window.dispatchEvent(new MouseEvent("pointerup", { bubbles: true }));
    await flush();

    expect(columns[0].style.flex).toBe("0 0 460px");
    expect(columns[1].style.flex).toBe("0 0 380px");        // untouched, not reset
    const writes = stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project");
    expect(writes.at(-1)!.body).toEqual({ ui: { model_columns: [460, 380] } });
  });

  it("collapses to its header and remembers the height to come back to", async () => {
    const tall = { ...PROJECT, doc: { ...PROJECT.doc, ui: { console_height: 260 } } };
    const stub = server(boot(tall));
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const panel = host.querySelector<HTMLElement>("section.console")!;
    expect(panel.style.flex).toBe("0 0 260px");            // restored from the project

    const caret = host.querySelector<HTMLButtonElement>("section.console .caret")!;
    caret.click();
    await flush();
    expect(panel.style.flex).toBe("0 0 26px");             // header only
    expect(panel.classList.contains("shut")).toBe(true);

    caret.click();
    await flush();
    expect(panel.style.flex).toBe("0 0 260px");            // …and back to where it was
  });

  it("runs the fit on `r`, but not while a filter box has focus", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const filter = host.querySelector<HTMLInputElement>("#param-filter")!;
    filter.dispatchEvent(new KeyboardEvent("keydown", { key: "r", bubbles: true }));
    await flush();
    expect(stub.calls.some((call) => call.path === "/api/run")).toBe(false);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "r", bubbles: true }));
    await flush();
    expect(stub.calls.some((call) => call.path === "/api/run")).toBe(true);
  });
});

/**
 * The text pane (WP-1013), driven through the real CodeMirror view.
 *
 * `EditorView.findFromDOM` is what makes these end-to-end rather than a test of
 * `lib/sync.ts` twice: a dispatch on the live view is exactly what a keystroke
 * produces, so the debounce, the transport and the state machine are all in the
 * path. The two assertions worth having are the two the WP names as risks — a
 * concurrent model change may not eat an edit, and a conflict has one exit.
 */
const TEXTDOC = 'rxt 1\nproject "lab6"\nmode rietveld\nlimits none\n';
const TEXTDOC_MOVED = 'rxt 1\nproject "lab6"\nmode rietveld\nlimits 3 60\n';

/** Mount, then enter the text mode (a mode, not a tab — the strip stays five wide). */
async function openText(extra: Record<string, any> = {}, project: any = PROJECT) {
  const stub = server({
    "/api/textdoc": () => ({ body: { text: TEXTDOC, revision: "r1", format_version: "1" } }),
    ...boot(project),
    ...extra,
  });
  vi.stubGlobal("fetch", stub.fetcher);
  app = mount(App, { target: host });
  await flush();
  button("Text")!.click();
  await waitForEditor();
  return stub;
}

/** The editor arrives on a dynamic `import()` — a real await, not a microtask.
 *
 * That is the design working rather than a test smell: `vendor-cm.js` is a
 * separate chunk fetched the first time the pane is opened, so the boot path
 * keeps the size WP-1010 measured. A `flush()` of microtasks cannot see the end
 * of a module load, so this polls for the mounted editor. */
async function waitForEditor(timeout = 4000) {
  const deadline = Date.now() + timeout;
  while (!host.querySelector(".cm-content") && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
  await flush();
}

/** The live editor, and a dispatch on it is a keystroke. */
function editorView(): EditorView {
  return EditorView.findFromDOM(host.querySelector(".cm-content") as HTMLElement)!;
}

async function typeInto(text: string) {
  const view = editorView();
  view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
  await flush();
}

/** Past the 300 ms validate debounce — real timers, because `flush` uses one. */
const settle = async () => {
  await new Promise((resolve) => setTimeout(resolve, 360));
  await flush();
};

describe("the text pane", () => {
  it("costs nothing until it is opened, then renders the document", async () => {
    const stub = server({
      "/api/textdoc": () => ({ body: { text: TEXTDOC, revision: "r1", format_version: "1" } }),
      ...boot(),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    // the boot path is what WP-1010 measured; a document nobody asked for would
    // both re-render every parameter row and pull in the editor chunk
    expect(stub.calls.some((call) => call.path === "/api/textdoc")).toBe(false);
    expect(host.querySelector(".cm-content")).toBeNull();

    button("Text")!.click();
    await waitForEditor();
    expect(stub.calls.some((call) => call.path === "/api/textdoc")).toBe(true);
    expect(host.querySelector(".cm-content")?.textContent).toContain("mode rietveld");
    expect(host.textContent).toContain("in sync");
  });

  it("validates a debounced edit without applying it", async () => {
    const stub = await openText({
      "/api/textdoc": (call: Call) => ({
        body: call.method === "GET"
          ? { text: TEXTDOC, revision: "r1", format_version: "1" }
          : { valid: true, applied: [], delta: {}, revision: "r1", would_change: true },
      }),
    });
    await typeInto(TEXTDOC_MOVED);
    expect(host.textContent).toContain("edited");
    expect(stub.calls.some((call) => call.method === "PUT")).toBe(false);  // still debouncing

    await settle();
    const put = stub.calls.find((call) => call.method === "PUT")!;
    expect(put.body).toEqual({ text: TEXTDOC_MOVED, base_revision: "r1", validate_only: true });
    expect(host.textContent).toContain("ready to apply");
  });

  it("applies explicitly, echoes the verbs, and adopts the re-render", async () => {
    const stub = await openText({
      "/api/textdoc": (call: Call) => ({
        body: call.method === "GET"
          ? { text: TEXTDOC, revision: "r1", format_version: "1" }
          : call.body.validate_only
            ? { valid: true, applied: [], delta: {}, revision: "r1", would_change: true }
            : { valid: true, applied: ['project.set_two_theta_limits(3.0, 60.0)'],
                delta: {}, text: TEXTDOC_MOVED, revision: "r2" },
      }),
    });
    await typeInto(TEXTDOC_MOVED);
    await settle();
    button("Apply ⌘⏎")!.click();
    await flush();

    const applied = stub.calls.filter((c) => c.method === "PUT" && !c.body.validate_only);
    expect(applied).toHaveLength(1);
    expect(applied[0].body.base_revision).toBe("r1");
    // the same verbs a form calls, so the console reads the same either way
    expect(host.textContent).toContain("project.set_two_theta_limits(3.0, 60.0)");
    expect(host.textContent).toContain("applied 1 change(s)");
    // the response carried the re-render: canonical output normalises glob lines
    // away, so the buffer is replaced rather than patched — and needs no 2nd GET
    expect(editorView().state.doc.toString()).toBe(TEXTDOC_MOVED);
    expect((button("Apply ⌘⏎") as HTMLButtonElement).disabled).toBe(true);
  });

  it("never lets a model change underneath overwrite an edit", async () => {
    let moved = false;
    const stub = await openText({
      "/api/textdoc": (call: Call) => ({
        body: call.method === "GET"
          ? { text: moved ? TEXTDOC_MOVED : TEXTDOC, revision: moved ? "r2" : "r1",
              format_version: "1" }
          : { valid: true, applied: [], delta: {}, revision: "r1", would_change: true },
      }),
      // a checkout from the history panel, an applied suggestion, a form edit:
      // every one of them moves the head, which is this pane's reload signal
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...IDLE_RUN,
                                      head: moved ? "n0009" : "n0000" } }),
    });
    const mine = TEXTDOC + "excluded 7.5 8\n";
    await typeInto(mine);
    moved = true;
    await new Promise((resolve) => setTimeout(resolve, 800));  // one poll interval
    await flush();

    expect(editorView().state.doc.toString()).toBe(mine);       // the edit survives
    expect(host.textContent).toContain("stale");
    expect(host.textContent).toContain("There is no merge");
    expect((button("Apply ⌘⏎") as HTMLButtonElement).disabled).toBe(true);

    // one exit, and it is the same one the server's 409 recommends
    button("Re-read")!.click();
    await flush();
    expect(editorView().state.doc.toString()).toBe(TEXTDOC_MOVED);
    expect(host.textContent).toContain("in sync");
    expect(stub.calls.filter((c) => c.path === "/api/textdoc" && c.method === "GET").length)
      .toBeGreaterThan(1);
  });

  it("shows a refusal at its line, and clears it when the line is retyped", async () => {
    await openText({
      "/api/textdoc": (call: Call) => ({
        status: call.method === "GET" ? 200 : 400,
        body: call.method === "GET"
          ? { text: TEXTDOC, revision: "r1", format_version: "1" }
          : { error: { code: "TEXTDOC_INVALID",
                       message: "1 problem(s) in the document; nothing was applied",
                       where: ["mode"],
                       details: [{ line: 3, message: "unknown mode 'nonsense'",
                                   where: "mode", text: "mode nonsense" }] } },
      }),
    });
    await typeInto(TEXTDOC.replace("rietveld", "nonsense"));
    await settle();

    expect(host.textContent).toContain("1 problem(s)");
    expect(host.textContent).toContain("unknown mode 'nonsense'");
    expect(host.textContent).toContain("line 3");
    // the squiggle and the list are two views of one answer — asserted through
    // CM's own lint state, because reading `textContent` sees only the list and
    // that is exactly how the defect below hid
    expect(diagnosticCount(editorView().state)).toBe(1);
    // the highlighter said nothing about any of this: only the server can
    expect(host.querySelector(".cm-content [class*='tok-']")).not.toBeNull();

    await typeInto(TEXTDOC);
    expect(host.textContent).not.toContain("unknown mode");
    expect(diagnosticCount(editorView().state)).toBe(0);
  });

  it("keeps the squiggle when the head moves underneath an invalid buffer", async () => {
    // Found in a browser, invisible to a `textContent` assertion: `load` cleared
    // the editor's diagnostics unconditionally, so a checkout — or a form edit,
    // or an applied suggestion — wiped the squiggle and the gutter marker while
    // the problem list below still named the line. Both now derive from `sync`.
    let moved = false;
    await openText({
      "/api/textdoc": (call: Call) => ({
        status: call.method === "GET" ? 200 : 400,
        body: call.method === "GET"
          ? { text: moved ? TEXTDOC_MOVED : TEXTDOC, revision: moved ? "r2" : "r1",
              format_version: "1" }
          : { error: { code: "TEXTDOC_INVALID", message: "1 problem(s)", where: ["mode"],
                       details: [{ line: 3, message: "unknown mode 'nonsense'",
                                   where: "mode", text: "mode nonsense" }] } },
      }),
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...IDLE_RUN,
                                      head: moved ? "n0009" : "n0000" } }),
    });
    await typeInto(TEXTDOC.replace("rietveld", "nonsense"));
    await settle();
    expect(diagnosticCount(editorView().state)).toBe(1);

    moved = true;
    await new Promise((resolve) => setTimeout(resolve, 800));  // one poll interval
    await flush();

    expect(host.textContent).toContain("stale");
    expect(host.textContent).toContain("unknown mode 'nonsense'");  // the list
    expect(diagnosticCount(editorView().state)).toBe(1);            // …and the squiggle
  });

  it("is read-only in the way that matters while a run is in flight", async () => {
    const running = { ...IDLE_RUN, state: "running",
                      run: { ...IDLE_RUN.run, kind: "fit", stage: "cell" } };
    const stub = await openText({
      "/api/run/state": () => ({ body: running }),
      "/api/events": () => ({ body: { events: [], next: 0, oldest: 1, ...running } }),
    });
    await typeInto(TEXTDOC_MOVED);
    await settle();

    // no validate is even attempted: the server would answer RUN_IN_FLIGHT, and
    // the state refusal outranking a parse complaint is only useful if the pane
    // does not ask a question it knows the answer to
    expect(stub.calls.some((call) => call.method === "PUT")).toBe(false);
    expect((button("Apply ⌘⏎") as HTMLButtonElement).disabled).toBe(true);
  });

  it("warns that comments will not survive before Apply replaces the buffer", async () => {
    await openText();
    await typeInto(TEXTDOC + "# checked against the certificate 2026-07-30\n");
    expect(host.textContent).toContain("will not survive the next render");
  });

  it("keeps a typed buffer across a trip to another tab", async () => {
    // The pane is a tab now (WP-1034) rather than a mode over the window, and
    // the property WP-1013 shipped it with has to survive that move: every panel
    // stays mounted, so a buffer typed but not applied is still there — and the
    // editor is not rebuilt, which would take the undo history with it.
    await openText();
    const mine = TEXTDOC + "excluded 7.5 8\n";
    await typeInto(mine);
    const view = editorView();

    button("Parameters")!.click();
    await flush();
    expect(host.querySelector(".panel .cm-content")).not.toBeNull();  // mounted, hidden

    button("Text")!.click();
    await flush();
    expect(editorView()).toBe(view);                    // the same editor, not a new one
    expect(editorView().state.doc.toString()).toBe(mine);
    expect(host.textContent).toContain("edited");
  });
});

// ----------------------------------------------------------------------
// the import wizard and the model editors (WP-1014)
// ----------------------------------------------------------------------
/** A `File` on a file input, which jsdom will not let you assign directly. */
function chooseFile(input: HTMLInputElement, name: string, text = "data") {
  const file = new File([text], name, { type: "application/octet-stream" });
  Object.defineProperty(input, "files", { value: [file], configurable: true });
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

const PATTERN_PREVIEW = {
  upload: "p1", kind: "pattern", filename: "nac.fxye", bytes: 12, sha256: "aa",
  format: { name: "gsas", title: "GSAS raw powder data (FXYE / ESD / STD)",
            sniff: "a BANK record in the first 4 kB — by content, not by suffix",
            sigma: "the third column (FXYE)", options: [] },
  reader_options: {}, n_points: 4200, two_theta_range: [3, 24], step: 0.005,
  has_sigma: true, metadata: {},
  curve: { two_theta: [3, 10, 24], intensity: [1, 9, 2], n_returned: 3 },
  suggested_project: "/work/nac.rex",
};

const CIF_PREVIEW = {
  upload: "c1", kind: "cif", filename: "lab6.cif", bytes: 40, sha256: "bb",
  structure: STRUCTURE, aniso: false, aniso_available: false, aniso_error: "",
  phases: [{ name: "LaB6", space_group: "P m -3 m",
             cell: [4.1566, 4.1566, 4.1566, 90, 90, 90], n_atoms: 2,
             species: ["B", "La"], n_aniso: 0 }],
  unknown_species: [],
};

describe("the import wizard", () => {
  it("stages each file, then commits tokens — nothing exists until Create", async () => {
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/upload/pattern": () => ({ body: PATTERN_PREVIEW }),
      "/api/upload/cif": () => ({ body: CIF_PREVIEW }),
      "/api/project/new": () => ({ body: PROJECT }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const files = [...host.querySelectorAll<HTMLInputElement>('input[type="file"]')];
    chooseFile(files[0], "nac.fxye");
    await flush();
    // the reader that claimed it, in its own words — not the extension
    expect(host.textContent).toContain("GSAS raw powder data");
    expect(host.textContent).toContain("σ from the file");
    // …and how it was recognised is behind the popover, not always-on prose
    // (WP-1205): the trigger is the format's short name, "gsas".
    const sniff = [...host.querySelectorAll<HTMLElement>(".help")]
      .find((el) => el.textContent?.trim() === "gsas")!;
    expect(sniff).toBeTruthy();
    sniff.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await flush();
    expect(host.ownerDocument.querySelector(".popover")?.textContent)
      .toContain("BANK record");
    // …and the filename went in the query, while the bytes went in the body
    const staged = stub.calls.find((c) => c.path === "/api/upload/pattern")!;
    expect(staged.url).toContain("filename=nac.fxye");
    expect(staged.body).toBeNull();
    expect(staged.blob).toBeInstanceOf(Blob);

    chooseFile(files[1], "lab6.cif");
    await flush();
    expect(host.textContent).toContain("P m -3 m");
    // the aniso checkbox is offered *disabled* when the file has no loop
    const aniso = host.querySelector<HTMLInputElement>('input[type="checkbox"]')!;
    expect(aniso.disabled).toBe(true);
    expect(host.textContent).toContain("no aniso loop in this file");

    // the project path was suggested by the pattern step, and the anode by the preset
    expect(button("Create project")?.disabled).toBe(false);
    button("Create project")!.click();
    await flush();

    const created = stub.calls.find((c) => c.path === "/api/project/new")!;
    expect(created.body.pattern).toEqual({ upload: "p1" });
    expect(created.body.structure).toEqual({ upload: "c1", aniso: false });
    expect(created.body.instrument).toEqual({ preset: "bragg_brentano", radiation: "CuKa" });
    expect(created.body.path).toBe("/work/nac.rex");
    // and the shell adopted it without a second GET /api/project
    expect(host.textContent).toContain("synth.xye");
  });

  it("shows the reader's refusal and stages nothing", async () => {
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/upload/cif": () => ({ status: 400, body: { error: { code: "UPLOAD_INVALID",
        message: "could not read a structure from notes.cif: ValueError: "
                 + "notes.cif:1:0(0): expected block header (data_)" } } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const files = [...host.querySelectorAll<HTMLInputElement>('input[type="file"]')];
    chooseFile(files[1], "notes.cif");
    await flush();

    expect(host.textContent).toContain("expected block header");
    expect(button("Create project")?.disabled).toBe(true);
  });

  it("carries the recent list inside itself, reachable with a project open", async () => {
    // WP-1034: the only recent list used to be the *empty state's*, so with a
    // project open there was no route back to another one short of restarting
    // the program.  The wizard is one component either way (WP-1014), so the
    // list lives in it and the header's `Open…` is the route.
    const other = { ...PROJECT, path: "/tmp/nac.rex",
                    data: { ...PROJECT.data, filename: "nac.fxye" } };
    const stub = server({
      ...boot(),
      "/api/recent": () => ({ body: { recent: [{ path: "/tmp/nac.rex", name: "nac.rex" }] } }),
      "/api/project/open": () => ({ body: other }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    expect(host.textContent).not.toContain("Open a recent project");   // not until asked

    button("Open…")!.click();
    await flush();
    expect(host.textContent).toContain("Open a recent project");
    expect(host.textContent).toContain("nothing is unsaved");

    button("nac.rex")!.click();
    await flush();
    const opened = stub.calls.find((c) => c.path === "/api/project/open")!;
    expect(opened.body).toEqual({ path: "/tmp/nac.rex" });
    // the session's project is replaced, and the shell lands on the parameters
    expect(host.textContent).toContain("nac.fxye");
    expect(host.querySelector("nav.tabs button.on")?.textContent?.trim()).toBe("Parameters");
    expect(host.textContent).toContain("project.open(/tmp/nac.rex)");
  });

  it("lists the shipped examples and opens one, building it on the way", async () => {
    // WP-1204: the other half of the empty state.  A new user has no recent
    // list, so without this the first screen offers only "choose a data file"
    // to someone who has no data file.
    const built = { ...PROJECT, path: "/home/me/.rietx/examples/fap.rex",
                    data: { ...PROJECT.data, filename: "FAP.XRA" } };
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/examples": () => ({ body: { examples: EXAMPLES } }),
      "/api/examples/open": () => ({ body: built }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.textContent).toContain("Open an example");
    expect(host.textContent).toContain("APS 11-BM");
    // the description is what says which one to pick, so it is on the row
    expect(host.textContent).toContain("one of them you did not ask for");
    // Reset appears only where there is a copy to throw away
    expect(button("Reset")).toBeTruthy();
    expect(host.querySelectorAll("section.examples button.ghost")).toHaveLength(1);

    [...host.querySelectorAll<HTMLButtonElement>("section.examples button.pick")]
      .find((b) => b.textContent?.includes("fluorapatite"))!.click();
    await flush();

    const opened = stub.calls.find((c) => c.path === "/api/examples/open")!;
    expect(opened.body).toEqual({ name: "fap" });
    // an example is a project like any other from the moment it exists
    expect(host.textContent).toContain("FAP.XRA");
    expect(host.querySelector("nav.tabs button.on")?.textContent?.trim()).toBe("Parameters");
  });

  it("resets an example through its own verb, not by opening it again", async () => {
    const fresh = { ...PROJECT, path: "/home/me/.rietx/examples/nac.rex" };
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/examples": () => ({ body: { examples: EXAMPLES } }),
      "/api/examples/reset": () => ({ body: fresh }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    button("Reset")!.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/examples/reset")!.body)
      .toEqual({ name: "nac" });
    expect(stub.calls.some((c) => c.path === "/api/examples/open")).toBe(false);
  });

  it("shows a refused example beside the list that asked for it", async () => {
    const message = "could not build the nac example: [Errno 28] No space left";
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/examples": () => ({ body: { examples: EXAMPLES } }),
      "/api/examples/open": () => ({ status: 500, body: {
        error: { code: "EXAMPLE_BUILD_FAILED", message } } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    host.querySelector<HTMLButtonElement>("section.examples button.pick")!.click();
    await flush();
    expect(host.textContent).toContain(message);
  });

  it("shows a refused open beside the list that asked for it", async () => {
    const message = "file has changed since the project was created (sha256 1a2b3c4d)";
    const stub = server({
      ...boot(),
      "/api/recent": () => ({ body: { recent: [{ path: "/tmp/nac.rex", name: "nac.rex" }] } }),
      "/api/project/open": () => ({ status: 400,
        body: { error: { code: "PROJECT_ERROR", message } } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Open…")!.click();
    await flush();
    button("nac.rex")!.click();
    await flush();

    // verbatim, in the wizard, and the project that was open is still open —
    // every Project.open refusal names a different remedy (WP-1008)
    expect(host.querySelector(".wizard .bad")?.textContent).toContain("sha256 1a2b3c4d");
    expect(host.textContent).toContain("synth.xye");
  });

  // ------------------------------------------------------------------
  // the filesystem browser (WP-1205)
  // ------------------------------------------------------------------
  const FS_HOME = {
    path: "/home/me", parent: null, roots: ["/home/me", "/home/me/work"],
    entries: [
      { name: "rietx-projects", path: "/home/me/rietx-projects", is_project: false },
      { name: "nac.rex", path: "/home/me/nac.rex", is_project: true },
    ],
  };

  it("browses the filesystem and opens a project directly", async () => {
    const other = { ...PROJECT, path: "/home/me/nac.rex",
                    data: { ...PROJECT.data, filename: "nac.fxye" } };
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/fs": () => ({ body: FS_HOME }),
      "/api/project/open": () => ({ body: other }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    expect(host.querySelector(".backdrop")).toBeNull();   // not until asked

    button("Open…")!.click();
    await flush();
    expect(stub.calls.some((c) => c.path === "/api/fs")).toBe(true);
    // a plain directory and a project are different rows: only the project
    // gets a `.pick` "open" affordance
    expect(host.querySelector(".backdrop ul")?.textContent).toContain("rietx-projects");
    const openRow = [...host.querySelectorAll<HTMLButtonElement>(".backdrop button.pick")]
      .find((b) => b.textContent?.includes("nac.rex"))!;
    expect(openRow).toBeTruthy();

    openRow.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/project/open")!.body)
      .toEqual({ path: "/home/me/nac.rex" });
    expect(host.querySelector(".backdrop")).toBeNull();    // closed on success
    expect(host.textContent).toContain("nac.fxye");
  });

  it("navigates a plain directory instead of opening it", async () => {
    const inner = { path: "/home/me/rietx-projects", parent: "/home/me",
                    roots: FS_HOME.roots, entries: [] };
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/fs": (call) => ({ body: call.url.includes("rietx-projects") ? inner : FS_HOME }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Open…")!.click();
    await flush();

    button("rietx-projects/")!.click();
    await flush();
    const calls = stub.calls.filter((c) => c.path === "/api/fs");
    expect(calls[calls.length - 1].url).toContain("rietx-projects");
    expect(host.querySelector(".backdrop")).toBeTruthy();   // still open — a navigation, not a project
    expect(host.querySelector(".backdrop .none")?.textContent).toBe("nothing here");
  });

  it("settles the wizard after opening a different project from over one already open", async () => {
    // The bug this closes (WP-1205): `Model` used to be mounted twice — the
    // empty-state wizard and the Model tab were separate component
    // instances, each its own `wizardOpen`.  Opening a *different* project
    // from the tab instance's own wizard left it painted over the freshly
    // opened one, because `project` stayed truthy the whole time and nothing
    // ever tore the instance down to reset it.
    const other = { ...PROJECT, path: "/home/me/nac.rex",
                    data: { ...PROJECT.data, filename: "nac.fxye" } };
    const stub = server({
      ...boot(),   // a project is already open
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/fs": () => ({ body: FS_HOME }),
      "/api/project/open": () => ({ body: other }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    expect(host.textContent).toContain("Structure & instrument");   // not the wizard

    button("Model")!.click();
    await flush();
    button("Open…")!.click();      // the App-level header button (startImport)
    await flush();
    expect(host.textContent).toContain("New project");

    button("Browse for a project…")!.click();
    await flush();
    const openRow = [...host.querySelectorAll<HTMLButtonElement>(".backdrop button.pick")]
      .find((b) => b.textContent?.includes("nac.rex"))!;
    openRow.click();
    await flush();

    // the wizard is gone — the panel shows the freshly-opened project's model,
    // never the wizard painted over it (checked on the heading and the wizard
    // markup itself, not a text search: "New project…" is also the button
    // that reopens it, and stays in the DOM whenever the wizard is closed)
    expect(host.querySelector(".model header h1")?.textContent).toBe("Structure & instrument");
    expect(host.querySelector(".model .wizard")).toBeNull();
  });

  it("browses to a different directory for a new project, keeping the suggested name", async () => {
    // A browser cannot suggest a new folder's name, only where it should
    // live — so picking a directory swaps the *parent* of the path the
    // staged pattern already suggested, rather than replacing it outright.
    const stub = server({
      ...boot(null),
      "/api/recent": () => ({ body: { recent: [] } }),
      "/api/upload/pattern": () => ({ body: PATTERN_PREVIEW }),
      "/api/fs": () => ({ body: FS_HOME }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const fileInput = host.querySelector<HTMLInputElement>('input[type="file"]')!;
    chooseFile(fileInput, "nac.fxye");
    await flush();
    const pathInput = () => host.querySelector<HTMLInputElement>(".steps input.wide")!;
    expect(pathInput().value).toBe("/work/nac.rex");   // PATTERN_PREVIEW's suggestion

    button("Browse…")!.click();
    await flush();
    expect(host.querySelector(".backdrop")).toBeTruthy();

    button("Use this directory")!.click();
    await flush();
    expect(host.querySelector(".backdrop")).toBeNull();
    expect(pathInput().value).toBe("/home/me/nac.rex");   // the parent moved, the name did not
  });
});

/** The parameter rows the model editor needs on top of the table's own fixture:
 *  the coordinate DOF that moves B, and the two atom rows it types through. */
const MODEL_PARAMS = {
  ...PARAMS,
  parameters: [
    ...PARAMS.parameters,
    param("phases.0.atoms.1.dof.0", { value: 0 }),
    // the coordinates themselves are rows too, and held ones: La's are locked
    // (a fully fixed site) and B's `x` is a tie onto its DOF.  They are here
    // because that is what the server sends — `_collect_atom_coords` adds x, y
    // and z whatever the site does — and because the `vary` cell of a fully
    // fixed atom is drawn from `…x` (WP-1215).
    param("phases.0.atoms.0.x", { value: 0, locked: true }),
    param("phases.0.atoms.0.y", { value: 0, locked: true }),
    param("phases.0.atoms.0.z", { value: 0, locked: true }),
    param("phases.0.atoms.1.x", { value: 0.1993,
      tie: { terms: [["phases.0.atoms.1.dof.0", 1]], const: 0.1993, user: false } }),
    param("phases.0.atoms.1.y", { value: 0.5, locked: true }),
    param("phases.0.atoms.1.z", { value: 0.5, locked: true }),
    param("phases.0.atoms.0.occ", { value: 1 }),
    param("phases.0.atoms.1.occ", { value: 1 }),
    param("phases.0.atoms.1.biso", { value: 0.4 }),
    param("instrument.zero_shift", { value: 0.01 }),
  ],
};

describe("the model editor", () => {
  async function openModel(extra: Record<string, any> = {}) {
    const stub = server({ ...boot(), "/api/params": () => ({ body: MODEL_PARAMS }),
                          ...extra });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();
    return stub;
  }

  function field(path: string): HTMLInputElement {
    return host.querySelector<HTMLInputElement>(`[data-field="${path}"]`)!;
  }

  /** A coordinate cell. Its own address because a coordinate is neither a model
   *  field nor a parameter row: it goes to `/api/structure/position` (WP-1215). */
  function coord(path: string): HTMLInputElement {
    return host.querySelector<HTMLInputElement>(`[data-coord="${path}"]`)!;
  }

  it("gives a fully fixed special position no coordinate control, with the reason", async () => {
    // WP-1215 moved the reason from a sub-row under the atom to the title of the
    // cells that would have been the control. The claim is the same one: an atom
    // whose site allows nothing to move has nothing to grey out, so it has no
    // input at all rather than a disabled one.
    await openModel();
    expect(field("phases.0.name").value).toBe("LaB6");
    const fixed = [...host.querySelectorAll<HTMLElement>(
      "table.atoms tbody tr:first-child td.coord .fixed")];
    expect(fixed).toHaveLength(3);
    expect(fixed[0].title).toContain("fully fixed special position");
    expect(fixed[0].title).toContain("48");
    expect(coord("phases.0.atoms.0.x")).toBeFalsy();

    // …while the 6f site gets three typed cells, and its title says which way
    // the one DOF its symmetry allows lets it go
    expect(coord("phases.0.atoms.1.x")).toBeTruthy();
    expect(coord("phases.0.atoms.1.y")).toBeTruthy();
    expect(coord("phases.0.atoms.1.x").title).toContain("moves along [1 0 0]");
    // the DOF boxes the sub-row used to carry are gone with it
    expect(field("phases.0.atoms.1.dof.0")).toBeFalsy();
  });

  it("sends a typed coordinate to the position route, not to the model", async () => {
    // WP-1215.  The three claims: it goes to its own route (x is a tie, so it is
    // in no whole-model PATCH and has no column of its own to set), the whole
    // position goes even though one axis was typed, and it goes *before* any
    // model patch — a whole-model PATCH carries the x, y, z it was built from.
    const stub = await openModel({
      "/api/structure/position": () => ({ body: { node_id: "n0009", changed: true,
        nearest: [0.21, 0.5, 0.5], structure: STRUCTURE, sites: SITES,
        symmetry: SYMMETRY, causes: CAUSES } }),
    });
    expect(coord("phases.0.atoms.1.x").value).toBe("0.19930");

    coord("phases.0.atoms.1.x").value = "0.21";
    coord("phases.0.atoms.1.x").dispatchEvent(new Event("input", { bubbles: true }));
    field("phases.0.atoms.1.label").value = "B1";
    field("phases.0.atoms.1.label").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    const posted = stub.calls.filter((c) => c.path === "/api/structure/position");
    expect(posted).toHaveLength(1);
    expect(posted[0].body).toEqual({ atom: "phases.0.atoms.1",
                                     xyz: [0.21, 0.5, 0.5] });
    // the label went as a whole model, and after the position
    const patched = stub.calls.findIndex(
      (c) => c.method === "PATCH" && c.path === "/api/structure");
    expect(patched).toBeGreaterThan(stub.calls.indexOf(posted[0]));
    // …and a coordinate is not a `set_values` value: it has no column in theta
    const params = stub.calls.find(
      (c) => c.method === "PATCH" && c.path === "/api/params");
    expect(params).toBeUndefined();
  });

  it("gives the position one refine flag, over the glob its DOFs share", async () => {
    // there is one flag rather than three because the site's DOFs are freed
    // together — `ParameterTable`: "per-axis intent does not map onto rows such
    // as [1,1,0]" — so the box is about `…dof.*` and records one node
    const stub = await openModel();
    const box = host.querySelector<HTMLInputElement>(
      '[data-vary="phases.0.atoms.1.dof.*"]')!;
    expect(box).toBeTruthy();
    expect(box.checked).toBe(false);
    // and the fully fixed atom gets the mark rather than a box
    expect(host.querySelector('[data-vary="phases.0.atoms.0.dof.*"]')).toBeNull();
    expect(host.querySelector<HTMLElement>(
      '[data-vary="phases.0.atoms.0.x"]')!.textContent).toBe("🔒");

    box.checked = true;
    box.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    const patch = stub.calls.find(
      (c) => c.method === "PATCH" && c.path === "/api/params")!;
    expect(patch.body).toEqual({ values: {},
                                 vary: { "phases.0.atoms.1.dof.*": true } });
  });

  it("keeps the U^ij patterns behind a per-atom disclosure", async () => {
    // the sub-rows are what made an atom one to three `<tr>`s, and the separator
    // under the last of them sat on the next atom's inputs
    const aniso = { ...STRUCTURE, phases: [{ ...STRUCTURE.phases[0],
      atoms: [STRUCTURE.phases[0].atoms[0],
              { ...STRUCTURE.phases[0].atoms[1],
                aniso: { u11: 0.005, u22: 0.005, u33: 0.005,
                         u12: 0, u13: 0, u23: 0 } }] }] };
    const sites = [SITES[0], { ...SITES[1], aniso: true,
      adp_paths: ["phases.0.atoms.1.adp.0", "phases.0.atoms.1.adp.1"],
      adp_patterns: [[1, 0, 0, 0, 0, 0], [0, 1, 1, 0, 0, 0]] }];
    await openModel({
      "/api/structure": () => ({ body: { structure: aniso, sites,
                                         symmetry: SYMMETRY, causes: CAUSES } }),
      "/api/params": () => ({ body: { ...MODEL_PARAMS, parameters: [
        ...MODEL_PARAMS.parameters,
        param("phases.0.atoms.1.adp.0", { value: 0.005 }),
        param("phases.0.atoms.1.adp.1", { value: 0.005 }) ] } }),
    });

    // one row per atom until the disclosure is opened
    const bodyRows = () => host.querySelectorAll("table.atoms tbody tr").length;
    expect(bodyRows()).toBe(2);
    expect(field("phases.0.atoms.1.adp.0")).toBeFalsy();

    host.querySelector<HTMLButtonElement>('[data-adp="phases.0.atoms.1"]')!.click();
    await flush();
    expect(bodyRows()).toBe(3);
    expect(field("phases.0.atoms.1.adp.0")).toBeTruthy();
    expect(host.textContent).toContain("[0 1 1 0 0 0]");
  });

  it("puts the atom table in a scroller of its own", async () => {
    // WP-1034: the table's `min-content` is 448 px and the pane is now routinely
    // 340-560 wide, so *something* has to scroll.  Before this it was the whole
    // column, which took the cell row and the headings sideways with the table.
    await openModel();
    const table = host.querySelector("table.atoms")!;
    expect(table.parentElement?.classList.contains("tablewrap")).toBe(true);
  });

  it("sends a value the parameter table owns through set_values", async () => {
    const stub = await openModel();
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    const patch = stub.calls.find((c) => c.method === "PATCH" && c.path === "/api/params")!;
    expect(patch.body).toEqual({ values: { "phases.0.cell.a": 4.2 }, vary: {} });
    // …and nothing was sent as a whole model: a cell edge is not a shape change
    expect(stub.calls.some((c) => c.path === "/api/structure" && c.method === "PATCH"))
      .toBe(false);
  });

  it("draws the instrument in three groups, U V W over X Y, esds and all", async () => {
    // WP-1216. jsdom computes no layout, so what is asserted here is the half
    // that decides it: which grid each field is in, and the order inside the
    // profile's fixed three columns — read three at a time, that order *is* the
    // two parallel rows. The widths themselves are the browser pass.
    await openModel({ "/api/params": () => ({ body: { ...MODEL_PARAMS, parameters: [
      ...MODEL_PARAMS.parameters.filter((p) => p.path !== "instrument.profile.w"),
      param("instrument.profile.w", { value: 0.004, vary: true, esd: 0.0002 }),
    ] } }) });
    const profile = host.querySelector(".grid.profile")!;
    const column = profile.closest(".column")!;
    expect([...column.querySelectorAll("h3")].map((h) => h.textContent?.trim()))
      .toEqual(["Source", "Geometry", "Profile", "Background"]);

    const fields = (root: Element) => [...root.querySelectorAll("[data-field]")]
      .map((e) => e.getAttribute("data-field"));
    expect(fields(profile)).toEqual([
      "profile.u", "profile.v", "profile.w", "profile.x", "profile.y",
      "geometry.axial_sl", "geometry.axial_hl"]);
    expect([...profile.querySelectorAll(".cell.rowstart")]
      .map((c) => c.querySelector("[data-field]")?.getAttribute("data-field")))
      .toEqual(["profile.u", "profile.x", "geometry.axial_sl"]);

    // the two fields whose group disagrees with their own path, drawn where the
    // group says and not where the prefix does
    const grids = [...column.querySelectorAll(".grid")];
    const geometry = grids[1];
    expect(fields(geometry)).toContain("zero_shift");
    expect(fields(geometry)).toContain("geometry.sample_displacement");
    expect(fields(geometry)).not.toContain("geometry.axial_sl");
    expect(fields(grids[0])).toEqual(
      ["source.lines.0.wavelength", "source.polarization"]);

    // the geometry select is the row's own cell, which is what keeps its
    // longest option out of the tracks the numbers are measured in
    expect(host.querySelector('.cell.fullrow [data-field="geometry.kind"]')).toBeTruthy();

    // and a refined width now says what it is known to, in the slot the cell
    // row and the phase grid have always drawn it in
    const w = host.querySelector('[data-field="profile.w"]')!.closest(".cell")!;
    expect(w.querySelector(".varyline .muted")?.textContent).toBe("(2)");
  });

  it("frees a parameter from the model editor, in the same PATCH as the values", async () => {
    // WP-1214: the flags a crystallographer wants to set are next to the
    // numbers they are about, and they travel the parameter table's own verb —
    // one `set_vary` node per path, values first.
    const stub = await openModel();
    const box = host.querySelector<HTMLInputElement>('[data-vary="instrument.profile.w"]')!;
    expect(box.tagName).toBe("INPUT");
    box.checked = true;
    box.dispatchEvent(new Event("change", { bubbles: true }));
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    const patch = stub.calls.find((c) => c.method === "PATCH" && c.path === "/api/params")!;
    expect(patch.body).toEqual({ values: { "phases.0.cell.a": 4.2 },
                                 vary: { "instrument.profile.w": true } });
    // one PATCH, not one per kind of edit
    expect(stub.calls.filter((c) => c.method === "PATCH" && c.path === "/api/params"))
      .toHaveLength(1);
  });

  it("holds a box back onto its own flag rather than sending a node that says nothing",
     async () => {
    const stub = await openModel();
    const box = host.querySelector<HTMLInputElement>('[data-vary="phases.0.cell.a"]')!;
    expect(box.checked).toBe(true);       // the row arrives free
    for (const checked of [false, true]) {
      box.checked = checked;
      box.dispatchEvent(new Event("change", { bubbles: true }));
      await flush();
    }
    // back where it started: nothing pending, so there is nothing to apply
    expect(button("Apply")).toBeFalsy();
    expect(stub.calls.some((c) => c.method === "PATCH" && c.path === "/api/params"))
      .toBe(false);
  });

  it("gives a held value no box at all, and says which reason holds it", async () => {
    // the parameter table's rule (WP-1011), reached here from `lib/table.ts` so
    // the two panels cannot come to draw the three reasons differently
    await openModel();
    const mark = (path: string) => host.querySelector(`[data-vary="${path}"]`);
    expect(mark("phases.0.cell.b")!.tagName).toBe("SPAN");
    expect(mark("phases.0.cell.b")!.textContent).toBe("=");
    expect(mark("phases.0.cell.alpha")!.textContent).toBe("🔒");
    // …and a mode-fixed row keeps its editable value: `set_values` still takes
    // one, it is only `set_vary` that the mode overrules
    expect(mark("phases.0.atoms.0.biso")!.textContent).toBe("·");
    expect(field("phases.0.atoms.0.biso")).toBeTruthy();
    // a field that is not in θ at all gets neither: the geometry declares which
    // corrections exist, and no stage can free it
    expect(mark("instrument.geometry.kind")).toBeNull();
  });

  it("puts the phase's scale and sample broadening where the phase is", async () => {
    // WP-1214: `phases.*.lor_size` is the family most often freed by hand, and
    // `instrument.profile.u` was already two columns away on the same screen
    await openModel();
    expect(field("phases.0.scale")).toBeTruthy();
    expect(host.querySelector('[data-vary="phases.0.scale"]')!.tagName).toBe("INPUT");
    expect(field("phases.0.lor_size")).toBeTruthy();
    expect(field("phases.0.gauss_strain")).toBeTruthy();
  });

  it("writes an instrument profile from the model, and says where it went", async () => {
    // the counterpart of `Load profile…`, which this panel has had since
    // WP-1014 with no way back out (WP-1214).  Model-gated: nothing has been
    // fitted in this fixture and the button is live all the same.
    const stub = await openModel({
      "/api/export/instrument_profile": () => ({ body: {
        kind: "instrument_profile", name: "instrument_profile.json", bytes: 812,
        path: "/tmp/sample.rex/exports/instrument_profile.json" } }),
    });
    button("Save profile…")!.click();
    await flush();

    expect(stub.calls.some((c) => c.method === "POST"
      && c.path === "/api/export/instrument_profile")).toBe(true);
    expect(host.textContent).toContain("exports/instrument_profile.json");
  });

  it("sends a species as a whole model, built on a freshly read one", async () => {
    const stub = await openModel();
    field("phases.0.atoms.1.species").value = "B";
    field("phases.0.atoms.1.species").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    field("phases.0.atoms.0.species").value = "La3+";
    field("phases.0.atoms.0.species").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    const reads = stub.calls.filter((c) => c.path === "/api/structure" && c.method === "GET");
    const patch = stub.calls.find((c) => c.path === "/api/structure" && c.method === "PATCH")!;
    // the model patched is the one read *after* the edit was made, not the one
    // rendered — a stale whole-model PATCH reverts every field it did not touch
    expect(reads.length).toBeGreaterThan(1);
    expect(patch.body.structure.phases[0].atoms[0].species).toBe("La3+");
    // the unchanged one is untouched, and typing a value back to what it was is
    // not an edit at all
    expect(patch.body.structure.phases[0].atoms[1].species).toBe("B");
    expect(stub.calls.some((c) => c.method === "PATCH" && c.path === "/api/params"))
      .toBe(false);
  });

  it("offers µR to a capillary and never both absorption fields", async () => {
    await openModel();
    expect(field("geometry.mu_r")).toBeTruthy();
    expect(field("geometry.mu_t")).toBeFalsy();
    // an absent optional renders empty, because µt = 0 is a specimen of zero
    // thickness and µR = 0 is simply off — the two "off"s disagree
    expect(field("geometry.mu_r").value).toBe("");
  });

  it("surfaces the FCJ corner rather than defaulting it away", async () => {
    await openModel();
    expect(host.textContent).toContain("S/L = H/L");
    expect(host.textContent).toContain("ρ = +1.000");
  });

  it("adds an atom to the model the shell is holding, not to a copy of it", async () => {
    // Regression, found in Chrome and not in jsdom until this existed: the model
    // lives in a `$state` rune, which is a **Proxy**, and `structuredClone`
    // throws `#<Object> could not be cloned` on one. The click did nothing and
    // the page logged an uncaught error.
    const stub = await openModel();
    const add = [...host.querySelectorAll<HTMLInputElement>(".add input")];
    const fill = (input: HTMLInputElement, value: string) => {
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    };
    fill(add[0], "O1");
    fill(add[1], "O");
    fill(add[2], "0.25");
    await flush();
    button("Add atom")!.click();
    await flush();

    const patch = stub.calls.find((c) => c.path === "/api/structure" && c.method === "PATCH")!;
    const atoms = patch.body.structure.phases[0].atoms;
    expect(atoms).toHaveLength(3);
    expect(atoms[2].label).toBe("O1");
    expect(atoms[2].x.value).toBe(0.25);
  });

  it("keeps a refusal on screen through the reload that follows it", async () => {
    // Also a browser finding: `apply` reloads after a failure, because a partial
    // apply leaves the server half-ahead — and `load` was clearing the same
    // variable the refusal had just been written to, so an unknown species was
    // refused and the message vanished. Two facts, two fields (WP-1013's rule).
    await openModel({
      "/api/structure": (call: Call) => call.method === "PATCH"
        ? { status: 400, body: { error: { code: "UNKNOWN_SPECIES",
            message: "1 atom(s) carry a scattering species this build has no form "
                     + "factor for: La (Xx).",
            where: ["phases.0.atoms.0.species"] } } }
        : { body: { structure: STRUCTURE, sites: SITES } },
    });
    field("phases.0.atoms.0.species").value = "Xx";
    field("phases.0.atoms.0.species").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();

    expect(host.textContent).toContain("no form factor for: La (Xx)");
  });

  it("toggles one atom's ADPs through the verb that knows the metric", async () => {
    const stub = await openModel({
      "/api/structure/aniso": () => ({ body: { node_id: "n0004", changed: true,
                                               structure: STRUCTURE, sites: SITES } }),
    });
    // addressed by `data-aniso`: the parameter tab's vary boxes are mounted too
    // (every panel is), and since WP-1214 this row carries three of its own
    const checkbox = host.querySelector<HTMLInputElement>(
      '[data-aniso="phases.0.atoms.0"]')!;
    checkbox.checked = true;
    checkbox.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    const call = stub.calls.find((c) => c.path === "/api/structure/aniso")!;
    expect(call.body).toEqual({ path: "phases.0.atoms.0", on: true });
  });

  // -- symmetry (WP-1035) --------------------------------------------
  it("says what the symbol is, and what it holds, without being asked", async () => {
    await openModel();
    // the free tier, off the route this pane already fetches
    expect(host.textContent).toContain("No. 221");
    expect(host.textContent).toContain("Laue m-3m");
    expect(host.textContent).toContain("P lattice");
    expect(host.textContent).toContain("b = a, c = a");
    // …and a held cell row now names its cause *beside* `held_because`, which
    // stays the parameter surface's own wording rather than being rewritten
    const edges = [...field("phases.0.cell.a").closest(".cellrow")!
      .querySelectorAll<HTMLElement>("label.cell")];
    const tied = edges.find((l) => l.textContent?.trim().startsWith("b"))!;
    expect(tied.title).toContain("tied: = 1·phases.0.cell.a");
    expect(tied.title).toContain("so b follows a");
    const locked = edges.find((l) => l.textContent?.trim().startsWith("α"))!;
    expect(locked.title).toContain("structurally fixed");
    expect(locked.title).toContain("α is fixed at 90°");
  });

  it("fetches the Wyckoff letters itself, in parallel and off the load path",
     async () => {
    // WP-1215: the button is gone. The search is memoised server-side on
    // (space group, positions), so the `site` column can be a column - what is
    // asserted here is that nobody has to ask for it.
    const stub = await openModel({ "/api/structure/symmetry": () => ({ body: LETTERS }) });
    const route = () => stub.calls.filter((c) => c.path === "/api/structure/symmetry");
    expect(route().length).toBeGreaterThan(0);
    expect(button("Wyckoff letters…")).toBeUndefined();
    expect(host.textContent).toContain("1a · m-3m");
    expect(host.textContent).toContain("6f · 4m.m");
    // the sentences it brought back are read before the free tier's counting
    // ones - held in their own field, since the two fetches are concurrent
    const site = host.querySelector<HTMLElement>("table.atoms td.site")!;
    expect(site.title).toContain("Wyckoff 1a, site symmetry m-3m");
  });

  it("loses the site column, and nothing else, when the letters do not arrive",
     async () => {
    // its own error field: a column that failed to arrive is not a refused
    // edit, and sharing `symError` made a fetch failure read as a bad symbol
    await openModel({
      "/api/structure/symmetry": () => ({ status: 500,
        body: { error: { code: "INTERNAL", message: "spglib said no" } } }),
    });
    expect(host.textContent).toContain("site symmetry:");
    expect(host.textContent).toContain("spglib said no");
    expect(host.textContent).not.toContain("6f · 4m.m");
    // ...and the rest of the panel is there
    expect(field("phases.0.name").value).toBe("LaB6");
    expect(host.querySelectorAll("table.atoms tbody tr").length).toBeGreaterThan(0);
  });

  it("previews a symbol before applying it, and applies nothing until Apply",
     async () => {
    const stub = await openModel({
      "/api/structure/symmetry/preview": () => ({ body: PREVIEW_OK }),
      "/api/structure/symmetry": () => ({ body: { node_id: "n0004", changed: true,
        structure: STRUCTURE, sites: SITES, symmetry: SYMMETRY, causes: CAUSES } }),
    });
    const symbol = field("phases.0.space_group");
    expect(symbol.value).toBe("P m -3 m");
    expect(button("Preview…")!.disabled).toBe(true);   // nothing typed yet

    symbol.value = "P 4/m m m";
    symbol.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    expect(button("Preview…")!.disabled).toBe(false);
    button("Preview…")!.click();
    await flush();

    // …and it is a preview: the apply route has not been touched
    expect(stub.calls.filter((c) => c.path === "/api/structure/symmetry"
                                    && c.method === "POST")).toHaveLength(0);
    expect(host.textContent).toContain("1 stop being tied and refine on their own: cell.c");
    expect(host.textContent).toContain("B: site symmetry order 8 → 4");

    button("Apply")!.click();
    await flush();
    const applied = stub.calls.find((c) => c.path === "/api/structure/symmetry"
                                           && c.method === "POST")!;
    expect(applied.body).toEqual({ phase: 0, space_group: "P 4/m m m" });
  });

  it("shows a blocked preview in the server's words and disables Apply", async () => {
    await openModel({
      "/api/structure/symmetry/preview": () => ({ body: PREVIEW_BLOCKED }),
    });
    const symbol = field("phases.0.space_group");
    // whitespace alone is not a change: gemmi owns the symbol grammar, and the
    // client's only job is "is this different text" (`symbolChanged`)
    symbol.value = " P m -3 m ";
    symbol.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    expect(button("Preview…")!.disabled).toBe(true);

    symbol.value = "I a -3 d";
    symbol.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Preview…")!.click();
    await flush();

    // the refusal verbatim, with the nearest allowed tensor the raise computed
    expect(host.textContent).toContain("nearest allowed tensor is");
    expect(host.textContent).toContain("become symmetry-equivalent");
    expect(button("Apply")!.disabled).toBe(true);
    // …and Discard puts the field back to the model's own symbol
    button("Discard")!.click();
    await flush();
    expect(field("phases.0.space_group").value).toBe("P m -3 m");
  });
});

// ----------------------------------------------------------------------
// the structure viewer (WP-1015, WP-1462)
// ----------------------------------------------------------------------
describe("the structure viewer", () => {
  /** `test-gl3d.ts` keeps every frame the viewer asked for; the viewer's
   *  assertions are about the *scene and view it hands over*. */
  function last(): Frame {
    return frames[frames.length - 1];
  }

  async function openViewer(extra: Record<string, any> = {}) {
    const stub = server({ ...boot(), "/api/params": () => ({ body: MODEL_PARAMS }),
                          ...extra });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Model")!.click();
    await flush();
    return stub;
  }

  /** The drawing knobs are behind a disclosure since WP-1029 — every one of
   *  them used to be on screen at once under a 300 px plot. */
  async function openKnobs() {
    [...host.querySelectorAll("button")]
      .find((b) => b.textContent?.includes("drawing"))!.click();
    await flush();
  }

  function canvas(): HTMLCanvasElement {
    return host.querySelector<HTMLCanvasElement>(".viewer canvas")!;
  }

  /** A drag across the canvas: jsdom has no `PointerEvent`, and the handlers
   *  read only what a mouse event carries. */
  async function drag(dx: number, dy: number) {
    const at = (type: string, x: number, y: number) =>
      canvas().dispatchEvent(new MouseEvent(type, { clientX: x, clientY: y, bubbles: true }));
    at("pointerdown", 100, 100);
    at("pointermove", 100 + dx, 100 + dy);
    at("pointerup", 100 + dx, 100 + dy);
    await flush();
  }

  it("draws each atom, each bond half and the cell, all in Å", async () => {
    await openViewer();
    const { scene } = last();
    expect(scene.atoms.map((a) => a.index)).toEqual([0, 1, 2]);
    // the image outside the cell is drawn dimmer than the La it is a copy of
    expect(scene.atoms[1].color[0]).toBeLessThan(scene.atoms[0].color[0]);
    expect(scene.halves.length).toBe(2);
    expect(scene.lines.length).toBe(12);
    expect(scene.labels.map((l) => l.text)).toEqual(["a", "b", "c"]);
    // a ball is the covalent radius times the ball fraction, in Å
    expect(scene.atoms[0].shape[0]).toBeCloseTo(0.4 * 2.07, 12);
    // …and the letters are on the page, over the canvas
    expect([...host.querySelectorAll(".viewer .letters span")].map((s) => s.textContent))
      .toEqual(["a", "b", "c"]);
  });

  it("draws polyhedra in ball mode and not in ellipsoid mode until switched (WP-1466)", async () => {
    // La with four B around it, the stick to the first given way to the faces
    const B = GEOMETRY.atoms[2];
    const withPolyhedra = {
      ...GEOMETRY,
      atoms: [...GEOMETRY.atoms, { ...B, pos: [2.08, 0.83, 2.08] },
              { ...B, pos: [2.08, 2.08, 0.83] }, { ...B, pos: [-0.83, -0.83, -0.83] }],
      polyhedra: [{
        center: 0, site: 0, vertices: [2, 3, 4, 5],
        faces: [[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]],
        edges: [[0, 1], [0, 2], [0, 3], [1, 2], [1, 3], [2, 3]],
        bonds: [0], coordination: 4, mean_distance: 2.9, gap: 1.5, drawn_by_default: true,
      }],
    };
    await openViewer({ "/api/structure3d": () => ({ body: withPolyhedra }) });
    expect(last().scene.faces).toHaveLength(1);
    expect(last().scene.halves).toHaveLength(0);
    expect(host.textContent).toContain("polyhedra LaB₄ ×1");

    button("ellipsoids")!.click();
    await flush();
    expect(last().scene.faces).toHaveLength(0);
    expect(last().scene.halves).toHaveLength(2);
    expect(host.textContent).toContain("polyhedra off (LaB₄)");
    // the one switch turns them on in the mode it is pressed in…
    button("polyhedra")!.click();
    await flush();
    expect(last().scene.faces).toHaveLength(1);
    // …and ball mode keeps its own setting
    button("balls")!.click();
    await flush();
    expect(last().scene.faces).toHaveLength(1);
    // the legend switches one formula
    button("LaB₄")!.click();
    await flush();
    expect(last().scene.faces).toHaveLength(0);
    expect(host.textContent).toContain("polyhedra off (LaB₄)");
  });

  it("says what it drew and at which thresholds", async () => {
    await openViewer();
    expect(host.textContent).toContain("2 atoms in the cell + 1 image outside it");
    expect(host.textContent).toContain("1 bond segment at 1.15×");
    expect(host.textContent).toContain("metal–metal and metal–cation contacts not bonded");
    expect(host.textContent).toContain("balls at 0.40× the covalent radius");
  });

  it("rescales the ellipsoids without asking the server again", async () => {
    // the payload carries k(p) for every level it offers, so a probability
    // change is a client multiply — a refetch would be a round trip for a
    // number already on the page
    const stub = await openViewer();
    button("ellipsoids")!.click();
    await openKnobs();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    // La's tensor is 0.08 Å on the diagonal, so its drawn semi-axis is 0.08 · k(p)
    expect(last().scene.atoms[0].shape[8]).toBeCloseTo(0.08 * 1.5382, 6);

    const select = [...host.querySelectorAll("select")]
      .find((s) => [...s.options].some((o) => o.textContent?.trim() === "90 %"))!;
    select.value = "0.9";
    select.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);
    expect(last().scene.atoms[0].shape[8]).toBeCloseTo(0.08 * 2.5003, 6);
    expect(host.textContent).toContain("ellipsoids at 90 %");

    // …and the level survives a reload.  Found in Chrome: the payload carries
    // the server's default probability, so every refetch quietly put the
    // ellipsoids back to 50 % — a choice undone by the next cell edit.
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();
    expect(host.textContent).toContain("ellipsoids at 90 %");
    expect(last().scene.atoms[0].shape[8]).toBeCloseTo(0.08 * 2.5003, 6);
  });

  it("calls an exaggeration an exaggeration, never a probability", async () => {
    // WP-1029's one design question. A probability cannot exceed 1 — k(p) =
    // √χ²₃(p) diverges as p → 1 and `probability_scale(1.0)` raises — so
    // "bigger so I can see it" is a drawing scale, and a viewer that drew
    // 1.5·k(0.5) under a "50 %" label would be claiming a surface it is not
    // drawing.
    await openViewer();
    button("ellipsoids")!.click();
    await openKnobs();
    const at50 = last().scene.atoms[0].shape[8];

    const size = [...host.querySelectorAll<HTMLInputElement>('input[type="range"]')]
      .find((i) => i.max === "4")!;
    size.value = "2";
    size.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();

    expect(last().scene.atoms[0].shape[8]).toBeCloseTo(at50 * 2, 6);
    // the probability is still the probability…
    expect(host.textContent).toContain("ellipsoids at 50 % (k = 1.538)");
    // …and the factor is stated beside it, as what it is
    expect(host.textContent).toContain("× 2.00 exaggeration");
    expect(host.textContent).toContain("not a probability");
    expect(host.textContent).not.toContain("ellipsoids at 100 %");
  });

  it("thins the stick for the mode it is drawn in", async () => {
    // an open stick is buried in its atom only while it is thinner than the
    // atom, and in ellipsoid mode an atom's size is √U·k(p), not a radius
    await openViewer();
    const ball = last().scene.halves[0].radius;
    button("ellipsoids")!.click();
    await flush();
    expect(last().scene.halves[0].radius).toBeLessThan(ball);
    expect(host.textContent).toContain("sticks 0.0");
  });

  it("keeps the view the user rotated to across a redraw", async () => {
    // plotly rebuilt its scene from the layout on every redraw and the view had
    // to be read back from a private object; the view is this component's now
    await openViewer();
    const opening = last().view.rotation;
    await drag(40, 10);
    button("ellipsoids")!.click();
    await flush();
    const rotated = last().view.rotation;
    expect(rotated).not.toEqual(opening);
    button("balls")!.click();
    await flush();
    expect(last().view.rotation).toEqual(rotated);
  });

  it("looks down a lattice vector without asking the server anything", async () => {
    const stub = await openViewer();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    const opening = last().view;
    await drag(40, 10);

    button("c")!.click();
    await flush();
    // LaB6 is cubic, so down c puts a right and b up exactly
    const down = last().view.rotation;
    [1, 0, 0, 0, 1, 0, 0, 0, 1].forEach((v, k) => expect(down[k]).toBeCloseTo(v, 12));

    button("reset")!.click();
    await flush();
    expect(last().view).toEqual(opening);
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length)
      .toBe(before);
  });

  it("says what is under the pointer in the strip below, not in a box over it", async () => {
    // WP-1213's rule, carried to the 3D pane: a box over the picture covers
    // the thing it describes
    await openViewer();
    Object.defineProperty(canvas(), "clientWidth", { value: 400, configurable: true });
    Object.defineProperty(canvas(), "clientHeight", { value: 400, configurable: true });
    const { scene, view } = last();
    const hover = async (p: number[]) => {
      const [x, y] = project(scene, view, 400, 400, p);
      canvas().dispatchEvent(new MouseEvent("pointermove", { clientX: x, clientY: y, bubbles: true }));
      await flush();
      return host.querySelector(".viewer .reading")!.textContent!.trim();
    };
    expect(await hover([0.8284, 2.0784, 2.0784])).toContain("B (B)");
    expect(await hover([0, 0, 0])).toContain("La (La)");
    expect(await hover([0.414, 1.039, 1.039])).toContain("La–B  3.058 Å");
  });

  it("refetches when the bond threshold moves, because the server owns the rule", async () => {
    const stub = await openViewer();
    await openKnobs();
    const slider = host.querySelector<HTMLInputElement>('input[type="range"]')!;
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;

    // the *label* follows the drag — one fetch per pixel would be a flood, but
    // showing a number is not a fetch, and tying the cheap one to the expensive
    // one is the whole of item (n)
    slider.value = "1.05";
    slider.dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    expect(host.textContent).toContain("1.05×");
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);

    // …and the *fetch* waits for the release, because the server owns the rule
    slider.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
    const latest = stub.calls.filter((c) => c.path === "/api/structure3d").pop()!;
    expect(latest.url).toContain("bond_tolerance=1.05");
  });

  /** A promise plus the button that resolves it. */
  function gate(): { promise: Promise<void>; open: () => void } {
    let open = () => {};
    const promise = new Promise<void>((resolve) => { open = () => resolve(); });
    return { promise, open };
  }

  it("drops an answer a later request has already overtaken", async () => {
    // WP-1013's rule, one panel over: two quick releases of the bond slider put
    // two requests in flight, and the picture must agree with the control that
    // asked for it rather than with whichever answer landed last
    const held: Array<() => void> = [];
    await openViewer({
      "/api/structure3d": (call: Call) => {
        const asked = new URL(call.url, "http://x").searchParams
          .get("bond_tolerance");
        const body = { ...GEOMETRY, bond_tolerance: Number(asked) };
        if (asked === "1.15") return { body };      // the opening load
        const g = gate();
        held.push(g.open);
        return { body, gate: g.promise };
      },
    });
    await openKnobs();
    const slider = host.querySelector<HTMLInputElement>('input[type="range"]')!;
    for (const value of ["1.05", "1.25"]) {
      slider.value = value;
      slider.dispatchEvent(new Event("change", { bubbles: true }));
      await flush();
    }
    expect(held.length).toBe(2);
    held[1]();                 // the newer answer lands first…
    await flush();
    held[0]();                 // …and the older one is dropped rather than drawn
    await flush();
    // the caption quotes the payload's own echo, so this is what the server said
    expect(host.textContent).toContain("at 1.25×");
    expect(host.textContent).not.toContain("at 1.05×");
  });

  it("says it is loading until the first answer settles", async () => {
    // "no structure yet" was a false statement while the first answer was on
    // its way — one `geo === null` cannot say both "not fetched" and
    // "fetched, and there is nothing here"
    const g = gate();
    await openViewer({
      "/api/structure3d": () => ({ body: GEOMETRY, gate: g.promise }),
    });
    expect(host.textContent).toContain("loading the structure");
    expect(host.textContent).not.toContain("no structure yet");
    g.open();
    await flush();
    expect(host.textContent).not.toContain("loading the structure");
  });

  it("switches a species off from the legend without a round trip", async () => {
    const stub = await openViewer();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    // the legend acts, so since WP-1201 it is `button.ghost` and not a chip
    const swatch = [...host.querySelectorAll<HTMLButtonElement>(".legend button")]
      .find((b) => b.textContent?.trim() === "La")!;
    swatch.click();
    await flush();
    // La's half-sticks go with it: a half belongs to its atom
    const { scene } = last();
    expect(scene.atoms.map((a) => a.index)).toEqual([2]);
    expect(scene.halves.length).toBe(1);
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);
  });

  it("offers the draw mode as one segmented control with one side on", async () => {
    // two plain buttons wore the primary (filled) register, so both read as
    // pressed — a control that answers no question (found by use, 2026-07-31)
    await openViewer();
    const group = host.querySelector('.viewer .segmented[aria-label="draw mode"]')!;
    const on = () => [...group.querySelectorAll("button.on")].map((b) => b.textContent!.trim());
    expect([...group.querySelectorAll("button")].map((b) => b.textContent!.trim()))
      .toEqual(["balls", "ellipsoids"]);
    expect(on()).toEqual(["balls"]);
    button("ellipsoids")!.click();
    await flush();
    expect(on()).toEqual(["ellipsoids"]);
  });

  it("redraws on a theme change, without asking the server", async () => {
    // the cell frame samples `--accent` and the canvas the panel's background
    // at draw time, so the redraw is what lets a theme change reach the canvas
    // at all (WP-1029 q) — and the geometry did not move, so refetching it
    // would be a round trip for numbers already in hand
    const stub = await openViewer();
    const fetched = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    const painted = frames.length;
    [...host.querySelectorAll("button")]
      .find((b) => b.getAttribute("aria-label") === "dark")!.click();
    await flush();
    expect(frames.length).toBeGreaterThan(painted);
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(fetched);
  });

  it("redraws as soon as the pane around it re-reads, not one frame later", async () => {
    // A cell edit goes through `PATCH /api/params`, and the model pane re-reads
    // the moment that returns — while the head reaches the *shell* only on the
    // next SSE frame.  Following the pane is what keeps the picture and the atom
    // table showing the same structure.
    const stub = await openViewer();
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    const painted = frames.length;
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length)
      .toBeGreaterThan(before);
    expect(frames.length).toBeGreaterThan(painted);
  });

  it("can be closed, gives its WebGL context back, and asks for nothing while closed", async () => {
    // browsers keep about sixteen live contexts a page and drop the oldest
    // without a word, so a viewer toggled a few times must not hold on to its
    const stub = await openViewer();
    const given = lifecycle.disposed;
    button("3D")!.click();
    await flush();
    expect(lifecycle.disposed).toBe(given + 1);
    const before = stub.calls.filter((c) => c.path === "/api/structure3d").length;
    expect(host.querySelector('input[type="range"]')).toBeNull();
    field("phases.0.cell.a").value = "4.3";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();
    expect(stub.calls.filter((c) => c.path === "/api/structure3d").length).toBe(before);
  });

  it("keeps one renderer through every redraw", async () => {
    // a canvas keeps the first context it gave, so a renderer disposed and
    // made again on it draws with a dead one — which a mode switch once did,
    // because the mount effect had come to depend on the geometry
    await openViewer();
    const { created, disposed, onDeadCanvas } = { ...lifecycle };
    button("ellipsoids")!.click();
    await flush();
    [...host.querySelectorAll<HTMLButtonElement>(".legend button")]
      .find((b) => b.textContent?.trim() === "B")!.click();
    await flush();
    [...host.querySelectorAll("button")]
      .find((b) => b.getAttribute("aria-label") === "dark")!.click();
    await flush();
    field("phases.0.cell.a").value = "4.2";
    field("phases.0.cell.a").dispatchEvent(new Event("input", { bubbles: true }));
    await flush();
    button("Apply")!.click();
    await flush();
    expect(lifecycle.created).toBe(created);
    expect(lifecycle.disposed).toBe(disposed);
    expect(lifecycle.onDeadCanvas).toBe(onDeadCanvas);
  });

  it("exports a PNG rendered again, with its letters, on either background", async () => {
    // D5: the export is a render of its own at EXPORT_LONG_SIDE, not the
    // screen's pixels, and the letters are DOM on screen, so it is handed them
    vi.stubGlobal("URL", Object.assign(URL, {
      createObjectURL: () => "blob:structure",
      revokeObjectURL: () => {},
    }));
    const before = exports.length;
    await openViewer();
    button("PNG")!.click();
    await flush();
    expect(exports.length).toBe(before + 1);
    const first = exports[exports.length - 1].options;
    expect(first.background).not.toBeNull();
    expect(first.labels.map((l) => l.text)).toEqual(["a", "b", "c"]);

    await openKnobs();
    const box = [...host.querySelectorAll<HTMLLabelElement>(".drawer label")]
      .find((l) => l.textContent?.includes("transparent PNG"))!
      .querySelector("input")!;
    box.click();
    await flush();
    button("PNG")!.click();
    await flush();
    expect(exports[exports.length - 1].options.background).toBeNull();
  });

  function field(path: string): HTMLInputElement {
    return host.querySelector<HTMLInputElement>(`[data-field="${path}"]`)!;
  }
});

// ----------------------------------------------------------------------
// WP-1027 — the peaks tab and the candidate table's gate
// ----------------------------------------------------------------------
import Peaks from "./panels/Peaks.svelte";

const PEAK = (index: number, tt: number, extra: Record<string, unknown> = {}) => ({
  index, two_theta: tt, two_theta_esd: 0.0011, d: 4.4, intensity: 1234,
  intensity_esd: 20, q: 0.05, q_esd: 1e-4, fwhm: 0.08, eta: 0.5, group: index,
  n_in_group: 1, chi2_red: 1.1, flags: [], origin: "fitted", usable: true,
  ...extra,
});

const PEAKS_PAYLOAD = {
  peaks: [
    PEAK(0, 10.0),
    PEAK(1, 12.0, { flags: ["not_separable"], usable: false }),
    PEAK(2, 14.0, { origin: "manual" }),
  ],
  pattern: { two_theta: [9, 10, 11, 12, 13, 14], y_obs: [1, 5, 2, 3, 1, 4], n_total: 6 },
  groups: [],
  diagnostics: [{ level: "warning", code: "PEAK_LIST_TOO_SHORT", message: "3 usable lines" }],
  flag_vocabulary: ["ghost_kbeta", "excluded", "not_separable", "sigma_assumed"],
  unusable_flags: ["ghost_kbeta", "excluded", "not_separable"],
  n_total: 3, n_usable: 2, source: "fitted", wavelength: 1.5406,
};

/** PEAKS_PAYLOAD's pattern as the curves route answers it before any fit. */
const RAW = {
  "/api/result/curves": rawCurves(PEAKS_PAYLOAD.pattern.two_theta, PEAKS_PAYLOAD.pattern.y_obs),
};

const MEDIUM_CANDIDATE = {
  cell: [4.7594, 4.7594, 12.992, 90, 90, 120], cell_esd: [0, 0, 0, 0, 0, 0],
  system: "hexagonal", centring: "R", lattice_group: "R -3 m", volume: 254.9,
  n_indexed: 20, n_lines: 20,
  fom: [{ name: "M20", value: 43.1, n_lines: 20, blind_spot: "" }],
  found_by: ["dichotomy", "trial_error"], confidence: "medium",
  confidence_caveats: ["shift_allowance_assumed"], ambiguity: [], lebail: null,
  diagnostics: [],
};

describe("what is fitted, shaded and selectable (WP-1033)", () => {
  /** The settings bodies this session sent, in order — `calls.at(-1)` would be
   *  whatever the event poll asked for a tick later. */
  function patches(stub: { calls: Call[] }) {
    return stub.calls
      .filter((c) => c.method === "POST" && c.path === "/api/project")
      .map((c) => c.body);
  }

  it("shades the range's outside and every region, from the document", async () => {
    // Not inferred from a hole in the data: a gap in the arrays is what an
    // exclusion *leaves*, and a renderer that guessed would be a second
    // authority on the protocol.
    const stub = server({ ...boot(MASKED_PROJECT), ...FITTED, ...MASKED_CURVES });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    // what the shading layer filled, back in 2θ: the fit range's outside,
    // clipped to the measured data, then the region
    const main = pane("main");
    const theta = (px: number) => Number(main.posToVal(px, "x").toFixed(3));
    const bands = main.marks.filter((m) => m.op === "fillRect" && m.style === INK.mask);
    expect(bands.map((m) => m.points!.map(([x]) => theta(x))))
      .toEqual([[3, 8], [19, 23.995], [13, 16]]);
    // …each edge dotted, in the edge's own ink
    const edges = main.marks.filter((m) => m.op === "stroke" && m.style === INK.edge);
    expect(edges.every((m) => m.dash)).toBe(true);
    expect(edges.map((m) => Math.round(theta(m.points![0][0])))).toEqual([8, 19, 13, 16]);
    // …under the curves: a wash that dimmed the points would be saying
    // something about the data rather than about the protocol
    expect(main.marks.indexOf(bands[0])).toBeLessThan(
      main.marks.findIndex((m) => m.op === "series"));
    // …and the full height of every pane, which is what survives a √ or log
    // scale, and the truth: an excluded channel is missing from the residual too
    for (const key of ["main", "ticks", "resid"] as const) {
      const u = pane(key);
      const rects = u.marks.filter((m) => m.op === "fillRect" && m.style === INK.mask);
      expect(rects, key).toHaveLength(3);
      for (const m of rects) {
        expect(m.points![0][1]).toBe(u.bbox.top);
        expect(m.points![1][1]).toBe(u.bbox.top + u.bbox.height);
      }
    }
  });

  it("draws the masked channels the result does not carry", async () => {
    // measured before it was written: with limits set, the result spans only
    // the fitted range (a 3–24° pattern came back 8.005–18.990°), so without
    // them the axis fits inside the range and the shading has nothing to shade
    const stub = server({ ...boot(MASKED_PROJECT), ...FITTED, ...MASKED_CURVES });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    // the observed points split by the payload's `kept` over one x: the fitted
    // ones, and the masked ones in a recessive series of their own
    expect(heldAt(1)).toEqual([9, 9.4]);
    expect(heldAt(2)).toEqual([3, 5, 14, 20, 23.995]);
    expect(xRange()).toEqual([3, 23.995]);
    // …and it is a curve, so it gets a toggle beside the others
    const curves = host.querySelector<HTMLElement>('.segmented[aria-label="curves"]')!;
    expect([...curves.querySelectorAll("button")].map((b) => b.textContent!.trim()))
      .toContain("masked");
  });

  it("arms a mode rather than adding a fourth drag meaning, and disarms itself",
     async () => {
    // A region drag is ambiguous with a zoom drag *everywhere* — same button,
    // same shape — so the ambiguity is removed rather than arbitrated: an
    // explicit arm, the figure's own select box, and one drag per arming.
    const stub = server({ ...boot(), ...FITTED, ...WIDE });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const panes = () => [pane("main"), pane("ticks"), pane("resid")];
    // unarmed, a box drag zooms both axes
    expect(panes().every((u) => u.cursor.drag.y)).toBe(true);
    const before = xRange();
    const painted = pane("main").paints;
    const arm = host.querySelector<HTMLElement>('.segmented[aria-label="select on the plot"]')!;
    [...arm.querySelectorAll("button")].find((b) => b.textContent!.includes("exclude"))!.click();
    await flush();
    // the mode is the figure's, so arming repaints nothing: x only, zooming nothing
    expect(panes().every((u) => !u.cursor.drag.y)).toBe(true);
    expect(pane("main").paints).toBe(painted);
    expect(host.textContent).toContain("the peak gestures are suspended");

    await dragOver(13, 16);

    // ordered and sent, the box dropped, nothing zoomed — the shading is the record now
    const sent = stub.calls.find((c) => c.method === "POST" && c.path === "/api/project")!.body;
    expect(sent.excluded_regions).toHaveLength(1);
    expect(sent.excluded_regions[0][0]).toBeCloseTo(13, 9);
    expect(sent.excluded_regions[0][1]).toBeCloseTo(16, 9);
    expect(pane("main").select.width).toBe(0);
    expect(xRange()).toEqual(before);
    expect(panes().every((u) => u.cursor.drag.y)).toBe(true);
    expect(host.textContent).not.toContain("the peak gestures are suspended");
  });

  it("suspends the peak gestures while it is armed", async () => {
    // WP-1027's rule, kept: an ambiguous pointer verb must do the harmless
    // thing.  Here nothing is ambiguous *because* the peak verbs stand down.
    const stub = server({
      ...boot(),
      ...RAW,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/remove": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    // the raw pattern spans 9-14° over the 1000-px plot area, so 600 px is 12.0°
    const node = host.querySelector<HTMLElement>(".plot")!;
    const arm = host.querySelector<HTMLElement>('.segmented[aria-label="select on the plot"]')!;
    [...arm.querySelectorAll("button")].find((b) => b.textContent!.includes("range"))!.click();
    await flush();

    node.dispatchEvent(new MouseEvent("contextmenu", { clientX: 600, bubbles: true }));
    await flush();
    expect(stub.calls.some((c) => c.path === "/api/peaks/remove")).toBe(false);

    // Esc gives the canvas back, and the peak verb works again
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await flush();
    node.dispatchEvent(new MouseEvent("contextmenu", { clientX: 600, bubbles: true }));
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/peaks/remove")?.body).toEqual({ index: 1 });
  });

  it("sends a typed range, and shows the verb's refusal where it was typed", async () => {
    // The non-pointer route, and the client has no opinion about validity:
    // two validators would be two answers (WP-1013's rule for the text pane).
    const stub = server({
      ...boot(), ...FITTED,
      "/api/project": (call: Call) =>
        call.method === "POST" && call.body.two_theta_limits?.[0] === 60
          ? { status: 400, body: { error: { code: "BAD_REQUEST", where: ["two_theta_limits"],
              message: "two_theta_limits must run low to high: (60.0, 20.0) is inverted" } } }
          : { body: call.method === "POST" && call.body.two_theta_limits
                ? { ...PROJECT, doc: { ...PROJECT.doc, two_theta_limits: call.body.two_theta_limits },
                    data: { ...PROJECT.data, n_fitted: 1600 } }
                : PROJECT },
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const boxes = [...host.querySelectorAll<HTMLInputElement>(".protocol input")];
    // empty means the whole pattern, and the placeholder says which range that is
    expect(boxes.map((b) => b.value)).toEqual(["", ""]);
    expect(boxes.map((b) => b.placeholder)).toEqual(["3.000", "23.995"]);

    const set = async (lo: string, hi: string) => {
      for (const [box, value] of [[boxes[0], lo], [boxes[1], hi]] as const) {
        box.value = value;
        box.dispatchEvent(new Event("input", { bubbles: true }));
      }
      button("Set")!.click();
      await flush();
    };

    const strip = () => host.querySelector<HTMLElement>(".protocol")!.textContent!;
    await set("60", "20");
    // beside the box that caused it, not only in the console — the user needs
    // the sentence while they retype
    expect(strip()).toContain("must run low to high: (60.0, 20.0) is inverted");

    await set("8", "19");
    expect(patches(stub).at(-1)).toEqual({ two_theta_limits: [8, 19] });
    expect(strip()).not.toContain("must run low to high");
    // the channel count is the check that the band is telling the truth
    expect(host.textContent).toContain("1,600 of 4,200 channels fitted");
  });

  it("removes one region by its chip and fits the whole pattern again by All",
     async () => {
    const stub = server({ ...boot(MASKED_PROJECT), ...FITTED });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.querySelector(".regions")!.textContent).toContain("13.000–16.000°");
    host.querySelector<HTMLButtonElement>(".regions button")!.click();
    await flush();
    expect(patches(stub).at(-1)).toEqual({ excluded_regions: [] });

    button("All")!.click();
    await flush();
    expect(patches(stub).at(-1)).toEqual({ two_theta_limits: null });
  });

  it("says when the curves on screen were fitted over other channels", async () => {
    // settings persist on the verb, curves move only on a run — so between an
    // exclusion and the next fit the picture contradicts the setting, and a
    // band over channels still in the residual is worse than no band at all
    const stub = server({
      ...boot(MASKED_PROJECT), ...FITTED,
      "/api/result/curves": fitCurves({ header: { stale: true } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    expect(host.textContent).toContain("fitted over a different set of channels");
  });

  it("draws an exclusion from one fetch, and keeps the view", async () => {
    // Under plotly an exclude drag cost four repaints (WP-1212). The mask is
    // the payload's `kept`, so a new region is one fetch of the curves and
    // nothing else, and the reader's zoom survives it.
    const stub = server({
      ...boot(), ...FITTED, ...WIDE,
      "/api/project": (call) => (call.method === "POST"
        ? { body: { ...PROJECT, doc: { ...PROJECT.doc, excluded_regions: [[13, 16]] } } }
        : { body: PROJECT }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    await dragOver(9, 18);
    const arm = host.querySelector<HTMLElement>('.segmented[aria-label="select on the plot"]')!;
    [...arm.querySelectorAll("button")].find((b) => b.textContent!.includes("exclude"))!.click();
    await flush();
    const fetched = curvesFetched(stub);
    await dragOver(13, 16);

    expect(curvesFetched(stub)).toBe(fetched + 1);
    const [lo, hi] = xRange();
    expect(lo).toBeCloseTo(9, 9);
    expect(hi).toBeCloseTo(18, 9);
  });
});

describe("the view survives a redraw (WP-1044)", () => {
  // Under plotly every redraw re-fitted the axes over everything drawn, the
  // peak markers and the mask shapes included, so a zoom lasted only as long
  // as nothing else moved (measured: a drag to 9.97–14.66° came back
  // 4.57–24.85 with a peak list on the plot), and WP-1212 then found the
  // pinning that repaired it re-fitting on every hover. The chart zooms in the
  // browser over a payload that is every channel, so a redraw moves no axis by
  // construction; these hold the panel to it where the panel could still undo it.

  it("keeps the zoom through a knob", async () => {
    const stub = server({ ...boot(), ...FITTED, ...WIDE });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    await dragOver(9, 14);
    const zoomed = xRange();
    const fetched = curvesFetched(stub);
    // a scale rebuilds the main pane (uPlot takes its scales at construction),
    // and a residual is new numbers for the lower one
    const scales = host.querySelector<HTMLElement>('.segmented[aria-label="intensity scale"]')!;
    [...scales.querySelectorAll("button")].find((b) => b.textContent!.trim() === "√")!.click();
    await flush();
    const kinds = host.querySelector<HTMLElement>('.segmented[aria-label="residual"]')!;
    [...kinds.querySelectorAll("button")].find((b) => b.textContent!.trim() === "Δ")!.click();
    await flush();

    for (const key of ["main", "ticks", "resid"] as const) expect(xRange(key)).toEqual(zoomed);
    expect(curvesFetched(stub)).toBe(fetched);
  });

  it("keeps the zoom through a peak edit, and fetches nothing for it", async () => {
    // A peak edit redraws the layer and nothing else: the curves did not move.
    // Under plotly it refetched the window, and until WP-1044 the fetch went
    // wide and threw the zoom away.
    const stub = server({
      ...boot(), ...FITTED, ...WIDE,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/flag": () => ({ body: { ...PEAKS_PAYLOAD, api_call: "session.set_peak_flags(1)" } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    await dragOver(10, 14);
    const zoomed = xRange();
    const fetched = curvesFetched(stub);
    const boxes = [...host.querySelectorAll<HTMLInputElement>('td.use input[type="checkbox"]')];
    boxes[1].dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    expect(stub.calls.some((c) => c.path === "/api/peaks/flag")).toBe(true);
    expect(curvesFetched(stub)).toBe(fetched);
    expect(xRange()).toEqual(zoomed);
  });

  it("keeps the zoom when a fit lands on the same channels, and not on others", async () => {
    // A run landing is the reader's same pattern with new numbers, so the view
    // they chose survives it (WP-1044). A payload over other channels is
    // another pattern, and a range from the old one would be a claim about it.
    let grid = [3, 6, 9, 9.4, 10, 12, 14, 18, 23.995];
    const stub = server({
      ...boot(), ...FITTED,
      "/api/result/curves": () => fitCurves({ two_theta: grid, y_obs: grid.map(() => 1) })(),
      "/api/history/checkout": () => ({ body: { head: "n0002", parameters: [], n_free: 0 } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const checkout = async () => {
      button("History")!.click();
      await flush();
      [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
      await flush();
      button("Checkout")!.click();
      await flush();
    };
    await dragOver(9, 14);
    const zoomed = xRange();
    const fetched = curvesFetched(stub);
    await checkout();
    expect(curvesFetched(stub)).toBe(fetched + 1);
    expect(xRange()).toEqual(zoomed);

    grid = [20, 30, 40];
    await checkout();
    expect(xRange()).toEqual([20, 40]);
  });

  it("still moves for a panel's request — the same one twice, if it is asked twice",
     async () => {
    // A window from another panel is a *request*, and the array's identity is
    // what tells it apart from every other reason the effect runs: the shell
    // writes a fresh pair per click, so asking twice moves twice.
    const stub = server({
      ...boot(), ...FITTED, ...WIDE,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    // the table's own zoom verb: 8 FWHM either side of the line (WP-1027)
    const zoomTo = [...host.querySelectorAll<HTMLButtonElement>("button")]
      .filter((b) => b.title === "zoom the plot to this line");
    zoomTo[0].click();
    await flush();
    const eight = 8 * PEAKS_PAYLOAD.peaks[0].fwhm;
    expect(xRange()).toEqual([10 - eight, 10 + eight]);

    // …the user drags somewhere else, and asks for the same line again
    await dragOver(13, 15);
    zoomTo[0].click();
    await flush();
    expect(xRange()).toEqual([10 - eight, 10 + eight]);
  });

  it("shows all of it again on a double-click", async () => {
    const stub = server({ ...boot(), ...FITTED, ...WIDE });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    await dragOver(9, 14);
    pane("main").over.dispatchEvent(new MouseEvent("dblclick"));
    await flush();
    for (const key of ["main", "ticks", "resid"] as const) {
      expect(xRange(key)).toEqual([3, 23.995]);
    }
  });

  it("marks the plot while a range gesture is armed, for the cursor to hang on",
     async () => {
    // A select drag and a zoom drag are the same pointer, so arming has to say
    // so under it (WP-1044): the class is the hook, and the rule that uses it
    // sets `col-resize` on the chart's plot area.
    vi.stubGlobal("fetch", server({ ...boot(), ...FITTED }).fetcher);
    app = mount(App, { target: host });
    await flush();

    const plot = host.querySelector(".plot")!;
    expect(plot.classList.contains("armed")).toBe(false);
    const arm = host.querySelector<HTMLElement>('.segmented[aria-label="select on the plot"]')!;
    [...arm.querySelectorAll("button")].find((b) => b.textContent!.includes("exclude"))!.click();
    await flush();
    expect(plot.classList.contains("armed")).toBe(true);

    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    await flush();
    expect(plot.classList.contains("armed")).toBe(false);
  });
});

describe("the peaks tab (WP-1027)", () => {
  it("lists every line, the fitter's exclusions distinguished, diagnostics inline", async () => {
    vi.stubGlobal("fetch", server({
      ...boot(),
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    expect(host.textContent).toContain("2 of 3 lines usable");
    // the fitter's own explanation of a strong peak's shape stays visible, as
    // the corpus's label rather than the flag's name (WP-1209)…
    const chips = [...host.querySelectorAll<HTMLElement>("td.flags .chip")]
      .map((c) => c.textContent!.trim());
    expect(chips).toEqual(["not separable", "manual"]);
    expect(host.textContent).not.toContain("not_separable");
    // …and the name is one click away, restored by the popover the label hid it from
    host.querySelector<HTMLElement>("td.flags .help")!.click();
    await flush();
    const popover = host.ownerDocument.querySelector(".popover")!.textContent!;
    expect(popover).toContain("Improves the group as a shape");
    expect(popover).toContain("Name");
    expect(popover).toContain("not_separable");
    // …but a label that *is* the name hid nothing, so no Name row (code review)
    host.querySelectorAll<HTMLElement>("td.flags .help")[1]!.click();
    await flush();
    const origin = host.ownerDocument.querySelector(".popover")!.textContent!;
    expect(origin).toContain("Placed by a person");
    expect(origin).not.toContain("Name");

    // the seven columns, use on its own; the picker's notes folded to a count
    const heads = [...host.querySelectorAll<HTMLElement>(".panel:not(.hidden) thead th")]
      .map((th) => th.textContent!.trim());
    expect(heads).toEqual(["#", "2θ (°)", "d (Å)", "I (rel)", "flags", "use", ""]);
    expect(host.querySelectorAll('td.use input[type="checkbox"]').length).toBe(3);
    expect(host.querySelector("details.notes summary")!.textContent!.replace(/\s+/g, " ").trim())
      .toBe("1 note from the picker");
    expect(host.textContent).toContain("PEAK_LIST_TOO_SHORT");

    // the numbers: every fixture line has the same area, so each is 100.0 of
    // the relative scale; 2θ at four places with the esd in the last place
    const cells = (col: number) => [...host.querySelectorAll<HTMLElement>(
      ".panel:not(.hidden) tbody tr")].map((tr) => tr.children[col].textContent!.trim());
    expect(cells(3)).toEqual(["100.0", "100.0", "100.0"]);
    expect(cells(1)).toEqual(["10.0000(11)", "12.0000(11)", "14.0000(11)"]);
  });

  it("sends the overrule verb from the use-for-indexing checkbox", async () => {
    const stub = server({
      ...boot(),
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/flag": (call: Call) => ({ body: { ...PEAKS_PAYLOAD, api_call:
        `session.set_peak_flags(${call.body.index}, use_for_indexing=${call.body.use_for_indexing})` } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const boxes = [...host.querySelectorAll<HTMLInputElement>('td.use input[type="checkbox"]')];
    expect(boxes.length).toBe(3);
    boxes[1].dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
    const sent = stub.calls.find((c) => c.path === "/api/peaks/flag");
    // the unusable line's checkbox asks to *use* it — the overrule, not a toggle blind
    expect(sent?.body).toEqual({ index: 1, use_for_indexing: true });
  });

  it("draws the groups' own residual under the raw pattern, in the peak layer's ink",
     async () => {
    // Before a fit there is no model to take a residual from, so the lower pane
    // is each fitted group's (y − fit)/σ, on the channels its window covers. It
    // is part of the peak layer, so it is drawn on the Peaks tab and in the
    // layer's ink, which is also how its row in the strip names it.
    const withGroups = {
      ...PEAKS_PAYLOAD,
      groups: [{ two_theta: [10, 11, 12], y_fit: [4, 2, 3], delta: [0.5, -1, 2] }],
    };
    vi.stubGlobal("fetch", server({
      ...boot(), ...RAW,
      "/api/peaks": () => ({ body: withGroups }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();

    const strip = () => {
      const u = pane("resid");
      return Array.from(u.data[0] as ArrayLike<number>)
        .flatMap((x, i) => (u.data[1][i] == null ? [] : [[x, u.data[1][i]]]));
    };
    button("Peaks")!.click();
    await flush();
    expect(strip()).toEqual([[10, 0.5], [11, -1], [12, 2]]);
    expect(ink("resid", 1)).toBe(INK.peakfit);
    expect(pane("resid").opts.axes[1].label()).toBe("(y − fit)/σ per group");

    // …and leaving the tab takes it off with the rest of the layer
    button("Report")!.click();
    await flush();
    expect(strip()).toEqual([]);
  });

  it("removes the line under a right-click, with no prompt in the way", async () => {
    // WP-1032, a scope decision the user took: right-click **removes**, and
    // refit stays on the table's `↻`.  The `window.prompt` for a component
    // count went with it — a modal in the one gesture that has no undo.
    const stub = server({
      ...boot(),
      ...RAW,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/remove": (call: Call) => ({ body: { ...PEAKS_PAYLOAD,
        api_call: `session.remove_peak(${call.body.index})` } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    const prompt = vi.fn();
    vi.stubGlobal("prompt", prompt);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    // the raw pattern spans 9-14° over the 1000-px plot area, so 600 px is
    // 12.0° and the 10-px radius is 0.05°
    const node = host.querySelector<HTMLElement>(".plot")!;
    node.dispatchEvent(new MouseEvent("contextmenu", { clientX: 600, bubbles: true }));
    await flush();

    expect(stub.calls.find((c) => c.path === "/api/peaks/remove")?.body).toEqual({ index: 1 });
    expect(stub.calls.some((c) => c.path === "/api/peaks/refit")).toBe(false);
    expect(prompt).not.toHaveBeenCalled();
  });

  it("adds a line on a click, moves one on a drag and toggles one on a shift-click",
     async () => {
    // The three pointer verbs through the chart, where WP-1461 moved them: each
    // arrives as the 2θ under the pointer, read through the chart's own x.
    const stub = server({
      ...boot(),
      ...RAW,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/add": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/move": () => ({ body: PEAKS_PAYLOAD }),
      "/api/peaks/flag": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    // 9-14° over the 1000-px plot area: 200 px a degree, and both radii are
    // 10 px, since 1.5× the 0.08° FWHM is wider than 0.05°
    const node = host.querySelector<HTMLElement>(".plot")!;
    const at = (type: string, x: number, shiftKey = false) =>
      node.dispatchEvent(new MouseEvent(type, { clientX: x, shiftKey, bubbles: true }));
    const gesture = async (from: number, to: number, shiftKey = false) => {
      at("pointerdown", from, shiftKey);
      if (to !== from) at("pointermove", to, shiftKey);
      at("pointerup", to, shiftKey);
      await flush();
    };
    const sent = (path: string) => stub.calls.filter((c) => c.path === path).map((c) => c.body);

    await gesture(300, 300);               // 10.5°, clear of every line
    expect(sent("/api/peaks/add")).toEqual([{ two_theta: 10.5 }]);

    await gesture(604, 604);               // 4 px from the 12° line: ambiguous
    expect(sent("/api/peaks/add")).toHaveLength(1);

    await gesture(602, 700);               // grabs the 12° line and drops it at 12.5°
    expect(sent("/api/peaks/move")).toEqual([{ index: 1, two_theta: 12.5 }]);

    await gesture(201, 201, true);         // the 10° line, which is in use
    expect(sent("/api/peaks/flag")).toEqual([{ index: 0, use_for_indexing: false }]);
    expect(sent("/api/peaks/add")).toHaveLength(1);
  });

  it("caps a line's σ whisker at 3×FWHM", async () => {
    // WP-1027: a degenerate component reports σ in tens of degrees (111°
    // measured), and an uncapped whisker would span the whole pattern
    const payload = { ...PEAKS_PAYLOAD,
      peaks: [PEAK(0, 10.0, { two_theta_esd: 111 }), PEAK(1, 12.0, { two_theta_esd: 0.02 })] };
    const stub = server({ ...boot(), ...RAW, "/api/peaks": () => ({ body: payload }) });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    // a whisker is one stroke of six points, its bar and its two caps; at 200 px
    // a degree the capped one reaches 3 × 0.08° each side, the other its own σ
    const half = pane("main").marks
      .filter((m) => m.op === "stroke" && m.style === INK.peak && m.points?.length === 6)
      .map((m) => Math.round((m.points![1][0] - m.points![0][0]) / 2));
    expect(half).toEqual([48, 4]);
  });

  it("links the table and the plot by hover, through a DOM ring rather than a repaint",
     async () => {
    // Task 1 of WP-1032 measured what a repaint of this pattern cost under
    // plotly (~111 ms); a mouse move must not pay it. The ring is a DOM mark
    // over the canvas, so moving it repaints nothing.
    const stub = server({
      ...boot(), ...FITTED, ...WIDE,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const ring = host.querySelector<HTMLElement>(".rx-ring")!;
    expect(ring.style.display).toBe("none");

    const painted = pane("main").paints;
    const rows = [...host.querySelectorAll<HTMLElement>(".panel:not(.hidden) tbody tr")];
    rows[2].dispatchEvent(new MouseEvent("mouseenter", { bubbles: false }));
    await flush();

    // the row lights up, the ring moves to that line's 2θ, and nothing was repainted
    expect(rows[2].classList.contains("lit")).toBe(true);
    expect(ring.style.display).toBe("block");
    expect(ring.style.left).toBe(`${pane("main").valToPos(14.0, "x")}px`);
    expect(pane("main").paints).toBe(painted);

    rows[2].dispatchEvent(new MouseEvent("mouseleave", { bubbles: false }));
    await flush();
    expect(rows[2].classList.contains("lit")).toBe(false);
    expect(ring.style.display).toBe("none");   // off the plot, not at 0
  });

  it("states the gestures whenever the tab that owns them is showing", async () => {
    // it used to render only in the raw state, so the moment a fit existed the
    // pointer verbs were undocumented — and each one names its non-pointer route
    const stub = server({
      ...boot(), ...FITTED, ...TWO_PHASE,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    expect(host.querySelector(".gestures")).toBeNull();   // not while reading the report

    button("Peaks")!.click();
    await flush();
    const line = host.querySelector(".gestures")!.textContent!;
    for (const gesture of ["Click", "drag", "shift-click", "right-click"]) {
      expect(line).toContain(gesture);
    }
    for (const route of ["2θ box", "2θ column", "checkbox", "×"]) {
      expect(line).toContain(route);
    }
  });

  it("draws the peak layer on the tab that can edit it, and nowhere else", async () => {
    // The layer was pushed unconditionally, so a marker sat on the plot in
    // every tab — a picture of something the click under it cannot touch
    // (the plot is an editing surface only while Peaks is up, WP-1027).
    const stub = server({
      ...boot(), ...FITTED, ...WIDE,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const layer = () => pane("main").marks.filter((m) => m.style === INK.peak);
    expect(layer()).toEqual([]);
    // and the toggle row says where it went rather than dropping the button
    const curves = () => host.querySelector<HTMLElement>('.segmented[aria-label="curves"]')!;
    const peaksButton = () =>
      [...curves().querySelectorAll("button")].find((b) => b.textContent!.trim() === "peaks")!;
    expect(peaksButton().disabled).toBe(true);
    expect(peaksButton().title).toContain("Peaks tab");

    button("Peaks")!.click();
    await flush();
    expect(layer().length).toBeGreaterThan(0);
    expect(peaksButton().disabled).toBe(false);

    // …and leaving takes it off again, which needs a repaint and not a refetch
    const fetched = curvesFetched(stub);
    button("Report")!.click();
    await flush();
    expect(layer()).toEqual([]);
    expect(curvesFetched(stub)).toBe(fetched);
  });

  it("tells the picked-peak fit from the model by colour and by dash", async () => {
    // the report: "both the same colour".  Measured — `--accent` *is*
    // `--plot-diff` and `--bad` *is* `--plot-calc` on the light theme, so the
    // layer had been borrowing two curves' colours (WP-1210).
    const withGroups = {
      ...PEAKS_PAYLOAD,
      groups: [{ two_theta: [9.5, 10, 10.5], y_fit: [1, 5, 1], delta: [0, 0, 0] }],
    };
    const stub = server({
      ...boot(), ...FITTED, ...WIDE,
      "/api/peaks": () => ({ body: withGroups }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const main = pane("main");
    const fit = main.marks.find((m) => m.op === "stroke" && m.style === INK.peakfit)!;
    expect(fit.dash).toBe(true);
    expect(ink("main", 3)).toBe(INK.calc);
    expect(INK.peakfit).not.toBe(INK.calc);
    expect(main.opts.series[3].dash).toBeUndefined();
    // both are named on the panel itself — the toggle row and, since WP-1213,
    // the readout strip under the plot — so neither curve has to be identified
    // by elimination
    expect(host.textContent).toContain("peak fit");
    // the markers are the layer's other colour, and the whole layer is *one*
    // colour: an unusable line is the same ink, hollow.  Spending a second on
    // the state is what had it on `--bad` (which is `--plot-calc` exactly),
    // and the recessive grey tried next measured 0.032 from `--plot-obs` on
    // the dark theme — the ink of the points these markers sit on.
    // A marker is an arc (a circle) or four points (a diamond); a whisker is
    // the six points of its bar and its two caps.
    const markers = main.marks.filter((m) => m.style === INK.peak
      && (m.op === "fill" || m.op === "stroke") && (m.points!.length === 1 || m.points!.length === 4));
    expect(markers.map((m) => [m.op, m.points!.length === 1 ? "circle" : "diamond"])).toEqual([
      ["fill", "circle"],      // fitted, usable
      ["stroke", "circle"],    // fitted, unusable: hollow
      ["fill", "diamond"],     // placed by a person
    ]);
    expect(INK.peak).not.toBe(INK.calc);
    expect(INK.peak).not.toBe(INK.diff);
    // …and the hover ring wears it too
    host.querySelector<HTMLElement>(".panel:not(.hidden) tbody tr")!
      .dispatchEvent(new MouseEvent("mouseenter", { bubbles: false }));
    await flush();
    const probe = document.createElement("i");
    probe.style.color = INK.peak;
    expect(host.querySelector<HTMLElement>(".rx-ring")!.style.borderColor).toBe(probe.style.color);
  });

  it("clears the plot to the data and puts back what was there before", async () => {
    // "an easy way to hide everything except the data" — and the way back is
    // the state the plot was in, not everything on: a user who had already
    // switched a phase's ticks off did not ask for them back.
    const stub = server({ ...boot(), ...FITTED, ...TWO_PHASE });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const curves = host.querySelector<HTMLElement>('.segmented[aria-label="curves"]')!;
    const curve = (label: string) =>
      [...curves.querySelectorAll("button")].find((b) => b.textContent!.trim() === label)!;
    const dataOnly = [...host.querySelectorAll<HTMLButtonElement>(".knobs button")]
      .find((b) => b.textContent!.trim() === "data only")!;

    curve("CaF2").click();
    await flush();
    expect(tickInks()).toEqual([INK.phase[0]]);

    dataOnly.click();
    await flush();
    expect(drawn()).toEqual(["obs"]);
    expect(tickInks()).toEqual([]);
    expect(dataOnly.classList.contains("on")).toBe(true);

    dataOnly.click();
    await flush();
    // back to the picture as it was — CaF2 still off, everything else on
    expect(drawn()).toEqual(["obs", "calc", "bkg", "diff"]);
    expect(tickInks()).toEqual([INK.phase[0]]);
    expect(dataOnly.classList.contains("on")).toBe(false);

    // and nothing about a picture reached the project document
    expect(stub.calls.filter((c) => c.method === "POST" && c.path === "/api/project")).toEqual([]);
  });

  it("disables Adopt for a medium candidate and quotes the server's why", async () => {
    vi.stubGlobal("fetch", server({}).fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [MEDIUM_CANDIDATE], diagnostics: [], quality: null },
        adopt: [{ allowed: false, why: "confidence is 'medium' (shift_allowance_assumed); only the one candidate best_or_none() returns can be adopted" }],
        refuting_caveats: ["predicted_but_absent"], running: false,
      },
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    const adopt = button("Adopt")!;
    // the gate does not leak into the UI: the button follows the server's arm
    expect(adopt.disabled).toBe(true);
    expect(adopt.title).toContain("medium");
    expect(host.textContent).toContain("the list below is ranked, not chosen");
  });

  it("enables Adopt only when the server's arm allows, and sends the candidate", async () => {
    const stub = server({
      "/api/index/adopt": (call: Call) => ({ body: { node_id: "n0007", mode: "lebail",
        api_call: `session.adopt_candidate(${call.body.candidate})` } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [{ ...MEDIUM_CANDIDATE, confidence: "high",
                                 confidence_caveats: [] }],
                  diagnostics: [], quality: null },
        adopt: [{ allowed: true, why: "" }],
        refuting_caveats: [], running: false,
      },
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    const adopt = button("Adopt")!;
    expect(adopt.disabled).toBe(false);
    expect(host.textContent).toContain("best_or_none()");
    adopt.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/index/adopt")?.body)
      .toEqual({ candidate: 0 });
  });
});

// ----------------------------------------------------------------------
// WP-1027 — the extinction screen (WP-1025 served)
// ----------------------------------------------------------------------
const SCREEN_CLASS = (extra: Record<string, unknown> = {}) => ({
  symbol: "P 63/m - -", representative: "P 63/m", space_groups: ["P 63", "P 63/m"],
  conditions: ["00l: l = 2n"], conditions_complete: true, n_lines: 40,
  n_absent: 6, n_testable: 4, n_present: 0, forbidden_hkl: [], forbidden_two_theta: [],
  rwp: 0.09, gof: 1.2, chi2: 100, delta_bic: -14.2, absences_rejected: false,
  screened: true, refuted: false, refuted_reason: null, diagnostics: [],
  ...extra,
});

const EXTINCTION = (best: number | null) => ({
  result: {
    candidates: [
      SCREEN_CLASS(),
      SCREEN_CLASS({ symbol: "P - - -", representative: "P 6/m", n_absent: 0,
                     n_testable: 0, space_groups: ["P 6/m", "P 6/m m m"], delta_bic: 0 }),
      SCREEN_CLASS({ symbol: "P 63/m c m", representative: "P 63/m c m",
                     space_groups: ["P 63 c m"], refuted: true, screened: false,
                     refuted_reason: "intensity at 2 forbidden positions",
                     n_present: 2, forbidden_hkl: [[0, 0, 1], [0, 0, 3]],
                     forbidden_two_theta: [10.51, 31.72] }),
      // unrefuted but never fitted (a max_classes cap): the unasked question.
      // `n_testable` is null there because it needs the class's own fit
      // (WP-1077) — the server cannot know it, so the cell must not print one
      SCREEN_CLASS({ symbol: "P 63/m m c", representative: "P 63/m m c",
                     space_groups: ["P 63 m c"], screened: false, delta_bic: 0,
                     n_testable: null }),
    ],
    lattice_group: "P 6/m m m", cell: [3, 3, 5, 90, 90, 120], system: "hexagonal",
    centring: "P", wavelength: 1.5406, two_theta_range: [5.0, 90.0],
    n_classes: 4, n_screened: 2, status: "converged",
    diagnostics: [{ level: "info", code: "EXTINCTION_GROUPS_NOT_SEPARABLE",
                    message: "the class members produce identical patterns" }],
  },
  candidate: 0,
  best,
  running: false,
});

/**
 * A candidate's predicted lines on the plot (WP-1211).
 *
 * What is asserted here is the wiring across three components — the row that
 * selects, the shell that fetches and caches, the plot that draws — because
 * that is where this feature is, and `lib/plot.test.ts` already owns the pure
 * halves. What was drawn is read off the uPlot stand-in's recording context
 * (`test-uplot.ts`), which is how every drawing claim in this file is made:
 * jsdom has no canvas.
 */
describe("an indexing candidate on the plot (WP-1211)", () => {
  const INDEX_ANSWER = {
    "/api/index/result": () => ({ body: {
      result: { candidates: [MEDIUM_CANDIDATE], diagnostics: [], quality: null },
      adopt: [{ allowed: false, why: "confidence is 'medium'" }],
      refuting_caveats: [], running: false,
    } }),
    "/api/index/ticks": () => ({ body: {
      candidate: 0, space_group: "R -3 m :H",
      two_theta: [9.1, 9.3], hkl: [[0, 1, 2], [1, 0, 4]], line: [0, 0],
      n_total: 2, n_returned: 2, shift_template: null, shift_coefficient: 0,
    } }),
  };

  /** The candidate's lines as the last paint stroked them, in 2θ, or null. */
  function lines(): number[] | null {
    const u = pane("main");
    const m = u.marks.find((k) => k.op === "stroke" && k.style === INK.candidate);
    if (!m) return null;
    const xs = [...new Set(m.points!.map(([x]) => x))];
    return xs.map((x) => Number(u.posToVal(x, "x").toFixed(2)));
  }

  it("draws them full height through the data, and clears the curves to do it",
     async () => {
    const stub = server({
      ...boot(), ...FITTED, ...TWO_PHASE, ...INDEX_ANSWER,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();
    // before anything is selected the model is on screen and nothing is fetched
    expect(drawn()).toContain("calc");
    expect(stub.calls.some((c) => c.path === "/api/index/ticks")).toBe(false);

    // the disclosure *is* the selection: one control, because "show me this
    // cell" means the caveats and where it says the lines are
    host.querySelector<HTMLElement>(".candidates tbody button.ghost")!.click();
    await flush();

    expect(stub.calls.find((c) => c.path === "/api/index/ticks")?.url)
      .toContain("candidate=0");
    // one stroke of full-height segments, one per line…
    expect(lines()).toEqual([9.1, 9.3]);
    const main = pane("main");
    const stroke = main.marks.find((m) => m.op === "stroke" && m.style === INK.candidate)!;
    expect(new Set(stroke.points!.map(([, y]) => y)))
      .toEqual(new Set([main.bbox.top, main.bbox.top + main.bbox.height]));
    // …under the data, since 426 lines over 115° buried the pattern on top
    expect(main.marks.indexOf(stroke))
      .toBeLessThan(main.marks.findIndex((m) => m.op === "series"));
    expect(host.textContent).toContain("4.7594");
    // "through *just* the data": selecting presses `data only` for you
    expect(drawn()).toContain("obs");
    expect(drawn()).not.toContain("calc");
    expect(host.textContent).toContain("2 predicted lines");

    // deselecting puts back exactly what was there, and takes the lines off
    host.querySelector<HTMLElement>(".candidates tbody button.ghost")!.click();
    await flush();
    expect(drawn()).toContain("calc");
    expect(lines()).toBeNull();
  });

  it("follows the tab that owns it, and is fetched once per candidate", async () => {
    // WP-1210's rule: a layer is drawn where it can be acted on, and the row
    // that acts on this one is in the Peaks panel.  The cache is the other
    // half — the hover preview below fires on every row the pointer crosses.
    const stub = server({
      ...boot(), ...FITTED, ...TWO_PHASE, ...INDEX_ANSWER,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const row = () => host.querySelector<HTMLElement>(".candidates tbody tr")!;
    row().dispatchEvent(new MouseEvent("mouseenter", { bubbles: false }));
    await flush();
    expect(lines()).not.toBeNull();
    // a hover is a preview, not a selection: the curves stay up
    expect(drawn()).toContain("calc");

    row().dispatchEvent(new MouseEvent("mouseleave", { bubbles: false }));
    await flush();
    expect(lines()).toBeNull();

    // select, then leave the tab: the layer goes with it
    host.querySelector<HTMLElement>(".candidates tbody button.ghost")!.click();
    await flush();
    button("Parameters")!.click();
    await flush();
    expect(lines()).toBeNull();
    expect(drawn()).toContain("calc");

    // …and comes back with it, off the cache: one fetch for three showings
    button("Peaks")!.click();
    await flush();
    expect(lines()).not.toBeNull();
    expect(stub.calls.filter((c) => c.path === "/api/index/ticks").length).toBe(1);
  });

  /** A promise plus the button that resolves it. */
  function held(): { promise: Promise<void>; open: () => void } {
    let open = () => {};
    const promise = new Promise<void>((resolve) => { open = () => resolve(); });
    return { promise, open };
  }

  it("clears the curves only once it has lines to put there", async () => {
    // The selection is instant and the answer is a round trip, so keying the
    // clear on "a row is selected" hid the model first and drew the lines on a
    // second repaint — a flash on any candidate whose enumeration takes real
    // time, and on a *refused* one a plot left showing nothing at all, with no
    // lines and no sentence saying why (found by review, not by this suite).
    const gate = held();
    vi.stubGlobal("fetch", server({
      ...boot(), ...FITTED, ...TWO_PHASE, ...INDEX_ANSWER,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/index/ticks": () => ({ ...INDEX_ANSWER["/api/index/ticks"](),
                                   gate: gate.promise }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    host.querySelector<HTMLElement>(".candidates tbody button.ghost")!.click();
    await flush();
    // in flight: the model is still on screen and there is nothing over it
    expect(drawn()).toContain("calc");
    expect(lines()).toBeNull();

    gate.open();
    await flush();
    expect(lines()).not.toBeNull();
    expect(drawn()).not.toContain("calc");
  });

  it("leaves the plot alone when the route refuses the cell", async () => {
    // `INDEX_CELL_TOO_LARGE`, or a lattice group gemmi will not build. The
    // honest outcome is that nothing on the plot moves — not a plot cleared to
    // the data with no lines on it, which reads as a drawing defect.
    vi.stubGlobal("fetch", server({
      ...boot(), ...FITTED, ...TWO_PHASE, ...INDEX_ANSWER,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/index/ticks": () => ({ status: 409, body: { error: {
        code: "INDEX_CELL_TOO_LARGE", message: "too many reflections" } } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    host.querySelector<HTMLElement>(".candidates tbody button.ghost")!.click();
    await flush();
    expect(drawn()).toContain("calc");
    expect(lines()).toBeNull();
    // …and the detail row still opened, so the click was not a no-op
    expect(host.querySelector(".candidates tr.detail")).toBeTruthy();
  });

  it("asks once for a row the pointer crosses twice before the answer lands",
     async () => {
    // The cache dedupes only once an answer is *back*, and each request is a
    // whole `generate_reflections` enumeration per emission line against a
    // server with no cancellation — so the in-flight set is the other half.
    const gate = held();
    const stub = server({
      ...boot(), ...FITTED, ...TWO_PHASE, ...INDEX_ANSWER,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/index/ticks": () => ({ ...INDEX_ANSWER["/api/index/ticks"](),
                                   gate: gate.promise }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const row = () => host.querySelector<HTMLElement>(".candidates tbody tr")!;
    for (let i = 0; i < 3; i++) {
      row().dispatchEvent(new MouseEvent("mouseenter", { bubbles: false }));
      await flush();
      row().dispatchEvent(new MouseEvent("mouseleave", { bubbles: false }));
      await flush();
    }
    expect(stub.calls.filter((c) => c.path === "/api/index/ticks").length).toBe(1);

    // and once it lands, the slot is released rather than leaked — a later ask
    // for the same row is served from the cache, still without a second fetch
    gate.open();
    await flush();
    row().dispatchEvent(new MouseEvent("mouseenter", { bubbles: false }));
    await flush();
    expect(stub.calls.filter((c) => c.path === "/api/index/ticks").length).toBe(1);
  });

  it("says so when the server could only send a sample", async () => {
    // the cap is not silent: a thinned set drawn without saying so reads as
    // "these are the lines this cell predicts", which is the one claim this
    // picture must not make falsely (CLAUDE.md's no-silent-caps rule)
    vi.stubGlobal("fetch", server({
      ...boot(), ...FITTED, ...TWO_PHASE, ...INDEX_ANSWER,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/index/ticks": () => ({ body: {
        candidate: 0, space_group: "P -1", two_theta: [9.1, 9.3],
        hkl: [[0, 1, 2], [1, 0, 4]], line: [0, 0],
        n_total: 92103, n_returned: 2, shift_template: null, shift_coefficient: 0,
      } }),
    }).fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();
    host.querySelector<HTMLElement>(".candidates tbody button.ghost")!.click();
    await flush();

    expect(host.textContent).toContain("2 of 92103 predicted lines");
    expect(host.textContent).toContain("sampled evenly");
  });
});

describe("the hover readout (WP-1213)", () => {
  /** The strip as `label → value` pairs, in the order it draws them. */
  function strip(): [string, string][] {
    const el = host.querySelector<HTMLElement>('[aria-label="under the pointer"]');
    return [...(el?.querySelectorAll<HTMLElement>(".field") ?? [])].map((f) => [
      f.querySelector(".key")!.textContent!.trim(),
      f.querySelector(".val")!.textContent!.trim(),
    ]);
  }

  it("says what the box said in a strip under the plot, and costs no repaint",
     async () => {
    vi.stubGlobal("fetch", server({ ...boot(), ...FITTED, ...TWO_PHASE }).fetcher);
    app = mount(App, { target: host });
    await flush();

    // the resting strip is the same fields, emptied — a strip that grew them
    // on hover would resize the canvas above it once per entry
    expect(strip()).toEqual([
      ["2θ", "—"], ["d", "—"], ["obs", "—"], ["calc", "—"], ["bkg", "—"],
      ["Δ/σ", "—"], ["NAC", "—"], ["CaF2", "—"],
    ]);

    const painted = pane("main").paints;
    await pointAt(9.4);

    expect(strip()).toEqual([
      ["2θ", "9.4000°"],
      // d = λ/(2 sin θ) with the *primary* line, off the settings document
      ["d", "9.4009 Å"],
      ["obs", "2"], ["calc", "2"], ["bkg", "0.4"], ["Δ/σ", "0"],
      // each phase's nearest reflection as a signed offset — 9.1 and 9.3
      ["NAC", "-0.3000°"], ["CaF2", "-0.1000°"],
    ]);
    // and reading it cost no repaint at all: the strip is DOM, and this is
    // WP-1032's "a hover never repaints the pattern" one step cheaper
    expect(pane("main").paints).toBe(painted);

    await pointAt(null);
    expect(strip().every(([, v]) => v === "—")).toBe(true);
  });

  it("names the picked line under the pointer, and lights its row", async () => {
    const stub = server({
      ...boot(), ...FITTED, ...TWO_PHASE,
      "/api/peaks": () => ({ body: { ...PEAKS_PAYLOAD, peaks: [PEAK(0, 9.4)] } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    await pointAt(9.4);

    // the peak table's own spellings (WP-1209): four places with the esd in
    // the last of them, and I relative to the strongest *measured* line
    expect(Object.fromEntries(strip()).peak).toBe("#0 9.4000(11)° · I 100.0");
    // …and the hit is `nearestPeak` at the radius a click obeys, which is also
    // what lights the table row — one hit test, not a second opinion
    expect(host.querySelector("tbody tr.lit")).toBeTruthy();

    await pointAt(9.0);
    expect(Object.fromEntries(strip()).peak).toBe("—");
    expect(host.querySelector("tbody tr.lit")).toBeNull();
  });

  it("names a candidate's line by hkl and by the λ it belongs to", async () => {
    const stub = server({
      ...boot(), ...FITTED, ...TWO_PHASE,
      "/api/peaks": () => ({ body: PEAKS_PAYLOAD }),
      "/api/index/result": () => ({ body: {
        result: { candidates: [MEDIUM_CANDIDATE], diagnostics: [], quality: null },
        adopt: [{ allowed: false, why: "confidence is 'medium'" }],
        refuting_caveats: [], running: false } }),
      "/api/index/ticks": () => ({ body: {
        candidate: 0, space_group: "R -3 m :H", two_theta: [9.398, 12.0],
        hkl: [[1, 0, -4], [1, 1, 0]], line: [1, 0],
        n_total: 2, n_returned: 2, shift_template: null, shift_coefficient: 0 } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();
    host.querySelector<HTMLElement>(".candidates tbody button.ghost")!.click();
    await flush();

    await pointAt(9.4);

    const fields = Object.fromEntries(strip());
    // the hkl WP-1211 serves and plotly's unified box would have put in a row
    // at every pointer position
    expect(fields.candidate).toBe("(1 0 −4) · λ 1.5444 Å");
    // selecting a candidate presses `data only`, and the strip follows what is
    // drawn — so the model's rows are gone rather than quoting hidden curves
    expect(strip().map(([k]) => k)).toEqual(["2θ", "d", "obs", "candidate"]);
  });
});

describe("the extinction screen table (WP-1027)", () => {
  it("ranks classes, lists every space group, and keeps chips inert without the adopt verdict", async () => {
    vi.stubGlobal("fetch", server({}).fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [MEDIUM_CANDIDATE], diagnostics: [], quality: null },
        adopt: [{ allowed: false, why: "confidence is 'medium'" }],
        refuting_caveats: [], running: false,
      },
      extinction: EXTINCTION(null),
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    // the gate's abstention is the headline, not an error
    expect(host.textContent).toContain("No class is singled out");
    // every class row: the symbol, the refutation with its hkl, the unfitted cap
    expect(host.textContent).toContain("P 63/m - -");
    expect(host.textContent).toContain("refuted");
    // spaced since WP-1213: `[1, 0, -4].join("")` is `10-4`, so both places
    // that write a reflection now write it through `formatHkl`
    expect(host.textContent).toContain("(0 0 1) 10.51°");
    expect(host.textContent).toContain("not screened");
    // a screened class shows its measured testable count; an unscreened one
    // shows a dash, because nobody asked (WP-1077)
    expect(host.textContent).toContain("4/6");
    expect(host.textContent).toContain("—/6");
    // both members of the class render — the singleton is unmeasurable…
    expect(host.textContent).toContain("P 63/m");
    expect(host.textContent).toContain("P 63");
    // …and with the candidate not adoptable, no space-group chip is a button
    expect(button("P 63")).toBeFalsy();
    // the not-separable info must be shown (it is information, not a footnote)
    expect(host.textContent).toContain("EXTINCTION_GROUPS_NOT_SEPARABLE");
  });

  it("adopts in a chosen space group when the server's arm allows", async () => {
    const stub = server({
      "/api/index/adopt": (call: Call) => ({ body: { node_id: "n0009", mode: "lebail",
        api_call: `session.adopt_candidate(${call.body.candidate}, space_group=${call.body.space_group})` } }),
    });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(Peaks, { target: host, props: {
      peaks: PEAKS_PAYLOAD as any,
      indexAnswer: {
        result: { candidates: [{ ...MEDIUM_CANDIDATE, confidence: "high",
                                 confidence_caveats: [] }],
                  diagnostics: [], quality: null },
        adopt: [{ allowed: true, why: "" }],
        refuting_caveats: [], running: false,
      },
      extinction: EXTINCTION(0),
      run: IDLE_RUN as any, busy: false,
    } });
    await flush();

    expect(host.textContent).toContain("best_or_none()");
    const chip = button("P 63/m")!;
    expect(chip).toBeTruthy();
    chip.click();
    await flush();
    expect(stub.calls.find((c) => c.path === "/api/index/adopt")?.body)
      .toEqual({ candidate: 0, space_group: "P 63/m" });
    // a refuted class's members never act, whatever the verdict
    expect(button("P 63 c m")).toBeFalsy();
  });
});

/**
 * The series panel (WP-1016) — the ninth tab, and the one panel whose subject is
 * a *method* rather than a model.
 *
 * A sequential fit is path-dependent by construction, so what these mounts assert
 * is the honesty of the presentation: the list the panel sends is the order it is
 * showing, the σ inconsistency is surfaced before the chain runs rather than
 * after, and `SEQUENTIAL_PATH_DEPENDENT` reaches the top of the panel with the
 * parameter named. jsdom cannot see the plot, so the trajectory drawing is
 * asserted in `lib/series.test.ts` and the *requests* are asserted here.
 */
describe("the series panel", () => {
  beforeEach(() => {
    host = document.createElement("div");
    document.body.appendChild(host);
  });

  afterEach(() => {
    if (app) unmount(app);
    app = null;
    host.remove();
    vi.unstubAllGlobals();
  });

  /** Mount, then open the Series tab (the panel fetches only when looked at). */
  async function openSeries(routes: Record<string, any>) {
    const stub = server({ ...boot(), ...routes });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Series")!.click();
    await flush();
    return stub;
  }

  /** The Series panel's figure's pane `key`, never the pattern panel's. */
  function seriesPane(key: string): StubPlot {
    const box = host.querySelector(".plotbox");
    const u = StubPlot.instances.find((p) => p.key === key && !p.destroyed && box?.contains(p.root));
    if (!u) throw new Error(`no ${key} pane is drawn in the series panel`);
    return u;
  }

  /** `--warn` as the panel falls back to it: jsdom loads no stylesheet. */
  const WARN = "#b7791f";

  /** The panel's icon buttons, which have no label to search by. */
  function icons(glyph: string): HTMLButtonElement[] {
    return [...host.querySelectorAll<HTMLButtonElement>(".side button")]
      .filter((b) => b.textContent?.trim() === glyph);
  }

  it("fetches only when the tab is opened, and offers the empty state", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    // mounted from boot like every tab, but a nine-panel shell that fetched
    // everything on boot would pay for nine panels to show one
    expect(stub.calls.some((c) => c.path === "/api/series")).toBe(false);

    button("Series")!.click();
    await flush();
    expect(stub.calls.some((c) => c.path === "/api/series")).toBe(true);
    expect(host.textContent).toContain("No patterns staged");
    // the protocol is the project's and is stated, not offered
    expect(host.textContent).toContain("mccusker_default");
    // and it cannot be run: one pattern is a fit, and every fence a series has
    // compares a pattern with its neighbours
    expect(button("Run series")?.disabled).toBe(true);
  });

  it("sends the list it is showing, and surfaces a mixed-σ series", async () => {
    const stub = await openSeries({
      "/api/series": () => ({ body: SERIES_STAGED }) });

    // the weighting inconsistency is a correctness property that is invisible
    // once the files are read, so it is said before the chain runs
    expect(host.textContent).toContain("disagree about carrying esds");
    expect(button("Run series")?.disabled).toBe(false);

    // reorder: the order *is* the series, so one PUT carries the whole list
    icons("↓")[0].click();
    await flush();
    const put = stub.calls.find((c) => c.method === "PUT" && c.path === "/api/series");
    expect(put?.body).toEqual({ patterns: [
      { upload: "tok1", label: "T400", x: 400 },
      { upload: "tok0", label: "T300", x: 300 },
    ] });
  });

  it("never PUTs a reorder that cannot happen", async () => {
    const stub = await openSeries({
      "/api/series": () => ({ body: SERIES_STAGED }) });
    // the first member's "earlier" is disabled *and* inert: a PUT here would
    // re-read every staged file to rewrite the list as it already is
    expect(icons("↑")[0].disabled).toBe(true);
    icons("↑")[0].click();
    await flush();
    expect(stub.calls.some((c) => c.method === "PUT")).toBe(false);
  });

  it("puts the path-dependence where it cannot be missed", async () => {
    const stub = await openSeries({
      "/api/series": () => ({ body: { ...SERIES_STAGED, has_result: true } }),
      "/api/series/result": () => ({ body: SERIES_ANSWER }),
      "/api/series/curves": fitCurves({ header: { index: 1, label: "T400", x: 400 } }),
      "/api/series/history": () => ({ body: { index: 1, label: "T400",
        checkout: false, tree_id: "t2", head: "n0002", root: "n0000",
        n_nodes: 2, nodes: [
          { id: "n0000", parents: [], label: "root", kind: "root", name: "",
            action: {}, api_call: "", status: null, n_iterations: 0, rwp: null,
            gof: null, n_free: null, n_diagnostics: 0, diagnostics: [],
            tags: [], children: ["n0002"], scores: {},
            notes: { series_warm_start_node: "n0001" } },
          { id: "n0002", parents: ["n0000"], label: "warm_refit", kind: "stage",
            name: "warm_refit", action: {}, api_call: "", status: "converged",
            n_iterations: 12, rwp: 0.094, gof: 1.3, n_free: 4,
            n_diagnostics: 0, diagnostics: [], tags: [], children: [],
            scores: {}, notes: {} },
        ] } }),
    });

    // the banner, not a strip entry — and it names the parameter
    const banner = host.querySelector(".banner.bad")!;
    expect(banner.textContent).toContain("1 parameter");
    expect(banner.textContent).toContain("path-dependent");
    expect(banner.textContent).toContain("phases.0.cell.a");

    // the reseed fence rides the row it is about, and the ranking put the
    // flagged trajectory on the plot first
    expect(host.textContent).toContain("reseeded");
    expect(host.textContent).toContain("Trajectory — phases.0.cell.a");
    expect(host.textContent).toContain("5.2σ");

    // …and drew it as the evidence it is: the forward chain in the warning ink
    // and dashed, the reseeded T400 ringed in the same ink, and the backward
    // chain beside it, muted and dotted
    const marks = seriesPane("traj").marks;
    const strokes = (style: string) => marks.filter((m) => m.op === "stroke" && m.style === style);
    expect(strokes(WARN).some((m) => m.dash && m.points!.length === 2)).toBe(true);
    expect(strokes(WARN).some((m) => m.points!.some((p) => p.length === 3))).toBe(true);
    expect(strokes(INK.edge).some((m) => m.dash)).toBe(true);
    const legend = () => [...host.querySelectorAll<HTMLButtonElement>(".legend button")];
    expect(legend().map((b) => b.textContent?.trim()))
      .toEqual(["forward (path-dependent)", "esd", "backward", "reseeded"]);
    // a legend click hides that mark, and says so on the button
    legend()[2].click();
    await flush();
    expect(legend()[2].getAttribute("aria-pressed")).toBe("false");
    expect(seriesPane("traj").marks.some((m) => m.op === "stroke" && m.style === INK.edge))
      .toBe(false);

    // walking into a pattern loads *its* tree, and says the nodes are read-only
    icons("▸").at(-1)!.click();
    await flush();
    const asked = stub.calls.find((c) => c.path === "/api/series/history");
    expect(asked?.url).toContain("index=1");
    expect(host.textContent).toContain("read-only here");
    // the warm-start link is what makes the chain navigable
    expect(host.textContent).toContain("n0001");
    // …and the plot followed: that member's curves, drawn as a pattern, and
    // the trajectory's figure gone
    const curves = stub.calls.find((c) => c.path === "/api/series/curves");
    expect(curves?.url).toContain("index=1");
    expect([...seriesPane("main").data[0]]).toEqual([9, 9.4]);
    expect(() => seriesPane("traj")).toThrow();
  });

  it("runs the chain through the one run machine", async () => {
    const stub = await openSeries({
      "/api/series": () => ({ body: SERIES_STAGED }),
      "/api/series/run": () => ({ body: { ...IDLE_RUN, state: "running",
        run: { ...IDLE_RUN.run, kind: "series", n_stages: 2 } } }),
    });
    button("Run series")!.click();
    await flush();
    const started = stub.calls.find((c) => c.path === "/api/series/run");
    expect(started?.method).toBe("POST");
    // the echo is the API line, like every other verb's
    expect(host.textContent).toContain("refine_sequential(");
  });

  it("keeps the two measured settings behind Advanced", async () => {
    const stub = await openSeries({
      "/api/series": () => ({ body: SERIES_STAGED }) });
    // `refit` and `carry` are WP-0505 *results*, not preferences, so Simple does
    // not offer them and nothing re-litigates the default
    expect(host.querySelector("input.carry")).toBeNull();
    button("Advanced")!.click();
    await flush();
    expect(host.querySelector("input.carry")).not.toBeNull();

    const carry = host.querySelector<HTMLInputElement>("input.carry")!;
    carry.value = "phases.* instrument.zero_shift";
    carry.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();
    const put = stub.calls.filter((c) => c.method === "PUT").at(-1);
    expect(put?.body.carry).toEqual(["phases.*", "instrument.zero_shift"]);
  });
});

describe("the search controls (WP-1045)", () => {
  // the document serves the block complete (pydantic defaults filled), so the
  // form carries no default of its own
  const CONTROLS = {
    search: { systems: null, centrings: null, min_d_axis: 2, max_d_axis: 25,
      min_volume: 15, max_volume: null, n_unindexed: 2, n_search_lines: 20,
      k_sigma: 3, shift_allowance_deg: 0, shift_template: null,
      budget_seconds: 30, total_budget_seconds: null, preset: null,
      max_candidates: 12, seed: 0, prior_cells: null, prior_spacegroups: null },
    engines: null, validate_candidates: true, check_top: null,
  };
  const VOCAB_CAPS = {
    ...CAPABILITIES,
    indexing_engines: [
      { name: "dichotomy", description: "exhaustive branch-and-bound" },
      { name: "svd", description: "iterative assignment" },
      { name: "trial_error", description: "exact solve over assumed indices" },
    ],
    crystal_systems: ["cubic", "hexagonal", "trigonal", "tetragonal",
                      "orthorhombic", "monoclinic", "triclinic"],
    centrings: { cubic: ["P", "I", "F"], hexagonal: ["P"],
                 trigonal: ["P", "R"], tetragonal: ["P", "I"],
                 orthorhombic: ["P", "C", "I", "F"], monoclinic: ["P", "C"],
                 triclinic: ["P"] },
    search_presets: [
      { name: "quick", title: "Quick (default)", description: "",
        when_to_use: "", default: true, total_budget_seconds: 120,
        typical_seconds: [1, 126] },
      { name: "full", title: "Full (no ceiling)", description: "",
        when_to_use: "", default: false, total_budget_seconds: null,
        typical_seconds: [4, 440] },
    ],
    shift_templates: ["constant", "cos_theta", "sin_2theta"],
  };
  const INDEXING_PROJECT = {
    ...PROJECT, doc: { ...PROJECT.doc, indexing: CONTROLS },
  };

  function controlsBoot() {
    let indexing: any = CONTROLS;
    return {
      ...boot(INDEXING_PROJECT),
      "/api/capabilities": () => ({ body: VOCAB_CAPS }),
      "/api/project": (call: Call) => {
        if (call.method === "POST" && call.body.indexing)
          indexing = call.body.indexing;
        return { body: { ...INDEXING_PROJECT,
                         doc: { ...INDEXING_PROJECT.doc, indexing } } };
      },
    };
  }

  function numInput(labelStart: string): HTMLInputElement {
    const label = [...host.querySelectorAll<HTMLElement>("label.num")]
      .find((l) => l.textContent!.trim().startsWith(labelStart))!;
    return label.querySelector("input, select") as HTMLInputElement;
  }

  it("states every control from the document and the live vocabularies", async () => {
    const stub = server(controlsBoot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const details = host.querySelector("details.search")!;
    expect(details).toBeTruthy();
    // one checkbox per registered engine, one per crystal system — quoted
    // from capabilities, so a fourth engine appears with no GUI change
    const engineBoxes = [...details.querySelectorAll(".block")[0]
      .querySelectorAll('input[type="checkbox"]')];
    expect(engineBoxes.length).toBe(3);
    const systemBoxes = [...details.querySelectorAll(".block")[1]
      .querySelectorAll('input[type="checkbox"]')];
    expect(systemBoxes.length).toBe(7);
    // the preset select offers the registry plus "default — quick"
    const preset = numInput("preset") as unknown as HTMLSelectElement;
    expect([...preset.options].map((o) => o.value)).toEqual(["", "quick", "full"]);
    // every numeric control is present, and its label is a help term rather
    // than a `title=` (WP-1203's no-mute-fields rule, retargeted): the key
    // itself is crossed against the corpus in `controls.test.ts`
    for (const start of ["min axis", "max axis", "min volume", "max volume",
                         "unindexed allowed", "search lines", "k·σ window",
                         "shift allowance", "max candidates", "seed",
                         "budget / slice", "total budget", "check top"]) {
      const input = numInput(start);
      expect(input, start).toBeTruthy();
      const label = input.closest("label")!;
      expect(label.title, start).toBe("");
      expect(label.querySelector(".help"), start).toBeTruthy();
    }
  });

  it("commits an edit as one whole-object patch on the verb", async () => {
    const stub = server(controlsBoot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const box = numInput("unindexed allowed");
    box.value = "4";
    box.dispatchEvent(new Event("change", { bubbles: true }));
    await flush();

    const post = stub.calls.find(
      (c) => c.method === "POST" && c.path === "/api/project" && c.body.indexing);
    expect(post).toBeTruthy();
    expect(post!.body.indexing.search.n_unindexed).toBe(4);
    // the rest of the block travels with it — a partial merge could let two
    // half-specs disagree
    expect(post!.body.indexing.search.n_search_lines).toBe(20);
    expect(post!.body.indexing.validate_candidates).toBe(true);
  });

  it("adds a typed prior cell, and refuses a malformed one locally", async () => {
    const stub = server(controlsBoot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Peaks")!.click();
    await flush();

    const input = [...host.querySelectorAll<HTMLInputElement>("input")]
      .find((i) => i.placeholder.startsWith("a b c"))!;
    input.value = "4.76 4.76 12.99 90 90 120";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await flush();

    const post = stub.calls.find(
      (c) => c.method === "POST" && c.path === "/api/project" && c.body.indexing);
    expect(post!.body.indexing.search.prior_cells).toEqual(
      [[4.76, 4.76, 12.99, 90, 90, 120]]);

    const before = stub.calls.length;
    input.value = "4.76 4.76";
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.dispatchEvent(new KeyboardEvent("keydown", { key: "Enter", bubbles: true }));
    await flush();
    // refused in the form's own error line, with no round trip
    expect(host.textContent).toContain("six numbers");
    expect(stub.calls.filter(
      (c) => c.method === "POST" && c.path === "/api/project").length)
      .toBe(stub.calls.slice(0, before).filter(
        (c) => c.method === "POST" && c.path === "/api/project").length);
  });
});

describe("the help popover", () => {
  /** The `.help` term inside the row whose leaf is `leaf`. */
  function term(leaf: string): HTMLElement {
    const row = rowsInDom().find(
      (r) => r.querySelector(".path")?.textContent?.trim() === leaf);
    return row!.querySelector<HTMLElement>(".path .help")!;
  }

  const popover = () => host.querySelector<HTMLElement>(".popover");

  /** Boot, and show every row: Simple hides the held ones, and two of the
   *  three things asserted here are about a held row. */
  async function openTable(routes: Record<string, any> = {}) {
    const stub = server({ ...boot(), ...routes });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    button("Advanced")!.click();
    await flush();
    return stub;
  }

  it("renders the corpus entry a parameter row's family key names", async () => {
    await openTable();
    expect(popover()).toBeNull();

    term("a").click();
    await flush();

    const shown = popover()!;
    // the entry, not the path: a row carries the family glob and the family is
    // what has a description (WP-1202's measured reason for the indirection)
    expect(shown.textContent).toContain("Cell edge");
    expect(shown.textContent).toContain("A unit-cell edge length.");
    expect(shown.textContent).toContain("Å");
    expect(shown.textContent).toContain("3-40 Å for an inorganic phase");
    const link = shown.querySelector<HTMLAnchorElement>("a")!;
    // the anchor is a page and a heading, joined to the base the same payload
    // carries — nothing in the frontend knows where the manual lives
    expect(link.href).toBe(
      "https://rietx.org/peak-positions.html#lattice-metric-and-bragg-s-law");
  });

  it("says so rather than inventing one when the key names nothing", async () => {
    await openTable();
    // `phases.*.scale` is a live family the fixture corpus does not carry —
    // exactly the shape of a key the corpus has not caught up with
    term("scale").click();
    await flush();
    expect(popover()!.textContent).toContain("Not described yet");
  });

  it("is one popover: opening another term moves it rather than adding one", async () => {
    await openTable();
    term("a").click();
    await flush();
    term("scale").click();
    await flush();
    expect(host.querySelectorAll(".popover").length).toBe(1);
    expect(popover()!.textContent).toContain("Not described yet");
  });

  it("closes on a second click, on Esc and on a click away", async () => {
    await openTable();
    const trigger = term("a");

    trigger.click();
    await flush();
    expect(popover()).toBeTruthy();
    trigger.click();
    await flush();
    expect(popover()).toBeNull();

    trigger.click();
    await flush();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await flush();
    expect(popover()).toBeNull();
    // Esc hands focus back to the term it came from, or a keyboard user is
    // dropped at the top of the document
    expect(document.activeElement).toBe(trigger);

    trigger.click();
    await flush();
    host.querySelector<HTMLElement>("header")!.click();
    await flush();
    expect(popover()).toBeNull();
  });

  it("does not let a run be cancelled by the Esc that closes it", async () => {
    // Esc means "close the thing that just opened"; cancelling a fit because a
    // popover was open is not undone by pressing it again
    const running = { ...IDLE_RUN, state: "running",
                      run: { ...IDLE_RUN.run, kind: "fit", stage: "cell" } };
    const stub = server({ ...boot(PROJECT, running),
                          "/api/cancel": () => ({ body: running }) });
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();
    const trigger = host.querySelector<HTMLElement>(".path .help")!;
    trigger.click();
    await flush();
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await flush();
    expect(popover()).toBeNull();
    expect(stub.calls.some((c) => c.path === "/api/cancel")).toBe(false);

    // …and a second Esc, with nothing open, still cancels
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    await flush();
    expect(stub.calls.some((c) => c.path === "/api/cancel")).toBe(true);
  });

  it("answers Enter and Space on a term, which a span does not do for free", async () => {
    await openTable();
    const trigger = term("a");
    trigger.dispatchEvent(new KeyboardEvent("keydown", { key: " ", bubbles: true }));
    await flush();
    expect(popover()).toBeTruthy();
    expect(trigger.getAttribute("aria-expanded")).toBe("true");
  });

  it("names a term by its own words, so it cannot rename what encloses it",
     async () => {
    // Measured in Chromium before this was fixed: `aria-label="explain"` on a
    // term renamed every control that computes its own name from its contents
    // — accname descends into the term and takes the label instead of the text
    // — so the instrument editor's inputs were named `explain (mm)` and the
    // atom table's headers `explain`.  jsdom has no accname, so what is
    // asserted is the cause: inside a naming context a term declares no name.
    await openTable();
    button("Model")!.click();
    await flush();
    const enclosed = [...host.querySelectorAll<HTMLElement>(".help")]
      .filter((el) => el.closest("label, th") !== null);
    expect(enclosed.length).toBeGreaterThan(0);
    expect(enclosed.filter((el) => el.hasAttribute("aria-label"))).toEqual([]);
    // and every one still says an explanation opens, in the channel that does
    // not take part in a name
    expect(enclosed.every((el) => el.getAttribute("aria-haspopup") === "dialog"))
      .toBe(true);
    // the term the popover reads from keeps its text as its name
    expect(term("a").textContent?.trim()).toBe("a");
    expect(term("a").hasAttribute("aria-label")).toBe(false);
  });

  it("moves focus into the popover, and hands it back on the way out", async () => {
    // a `role="dialog"` nobody is in announces nothing: before this, Tab from
    // an activated term went to the next input in the row and the popover's
    // `in the manual →` link was reachable only by tabbing the whole app
    await openTable();
    const trigger = term("a");

    trigger.click();
    await flush();
    expect(document.activeElement).toBe(popover());

    // a click away must not steal focus back from whatever was clicked
    trigger.click();
    await flush();
    expect(document.activeElement).toBe(trigger);
  });

  it("carries a held row's reason, which is the verb's own words", async () => {
    await openTable();
    const row = rowsInDom().find(
      (r) => r.querySelector(".path")?.textContent?.trim() === "alpha")!;
    row.querySelector<HTMLElement>(".vary .help")!.click();
    await flush();
    // no corpus can hold this: it is about one row, not about one name
    expect(popover()!.textContent).toContain("structurally fixed by symmetry");
  });
});

describe("the first-run checklist (WP-1017)", () => {
  it("shows four derived steps on a project that has never dismissed it", async () => {
    vi.stubGlobal("fetch", server(boot()).fetcher);
    app = mount(App, { target: host });
    await flush();

    const strip = host.querySelector(".checklist")!;
    expect(strip).toBeTruthy();
    // derived, not stored: the project has a phase and no result, so two are
    // done and two are not
    expect(strip.textContent).toContain("Open a project");
    expect(strip.textContent).toContain("Have a phase to refine");
    expect(strip.textContent).toContain("Run the fit");
    expect(strip.textContent).toContain("Read the report");
    expect(strip.textContent).toContain("2 left");
  });

  it("ticks Run once a result exists, without anything being stored", async () => {
    vi.stubGlobal("fetch", server({ ...boot(), ...FITTED }).fetcher);
    app = mount(App, { target: host });
    await flush();

    // one step left — the report has not been looked at yet
    expect(host.querySelector(".checklist")!.textContent).toContain("1 left");
  });

  it("points a project with no phase at the peak picker", async () => {
    const noPhase = { ...PROJECT, n_phases: 0 };
    vi.stubGlobal("fetch", server(boot(noPhase)).fetcher);
    app = mount(App, { target: host });
    await flush();

    const strip = host.querySelector(".checklist")!;
    expect(strip.textContent).toContain("no phase yet");
    expect(strip.textContent).toContain("3 left");
  });

  it("dismisses onto ProjectDoc.ui, on the verb", async () => {
    const stub = server(boot());
    vi.stubGlobal("fetch", stub.fetcher);
    app = mount(App, { target: host });
    await flush();

    const dismiss = [...host.querySelectorAll<HTMLButtonElement>(".checklist button")]
      .find((b) => b.textContent?.trim() === "Dismiss")!;
    dismiss.click();
    await flush();

    // persisted the way every other `ui` key is: on the verb, not on a save
    const patch = stub.calls.find(
      (c) => c.path === "/api/project" && c.method === "POST"
        && (c.body as any)?.ui?.first_run === false);
    expect(patch).toBeTruthy();
    expect(host.querySelector(".checklist")).toBeNull();
  });

  it("keeps Read the report ticked across a head move", async () => {
    // The reset belongs where the *project* changes, not in `readUi()` — which
    // `moved()` also calls on every head move, so put there, reading the report
    // and then checking a node out un-ticks the step the person just finished.
    const stub = await openTab("History", PROJECT, {
      ...FITTED,
      "/api/history/checkout": () => ({ body: { head: "n0002", parameters: [], n_free: 0 } }),
    });
    const tabs = () => [...host.querySelectorAll<HTMLButtonElement>(".tab")];
    tabs().find((t) => t.textContent?.trim() === "Report")!.click();
    await flush();
    // every step done, so the strip says so rather than counting
    expect(host.querySelector(".checklist")!.textContent).toContain("that is the loop");

    tabs().find((t) => t.textContent?.trim() === "History")!.click();
    await flush();
    [...host.querySelectorAll<HTMLButtonElement>(".node button.pick")][2].click();
    await flush();
    button("Checkout")!.click();
    await flush();

    expect(stub.calls.some((c) => c.path === "/api/history/checkout")).toBe(true);
    // Still every step done: the head moved, the project did not. Before the
    // fix this read "1 left" — the reset had been put in `readUi()`, which
    // `moved()` calls on every head move, so reading the report and then
    // checking a node out un-ticked the step the person had just finished.
    expect(host.querySelector(".checklist")!.textContent).toContain("that is the loop");
  });

  it("stays hidden on a project that dismissed it before", async () => {
    const dismissed = { ...PROJECT, doc: { ...PROJECT.doc, ui: { first_run: false } } };
    vi.stubGlobal("fetch", server(boot(dismissed)).fetcher);
    app = mount(App, { target: host });
    await flush();

    expect(host.querySelector(".checklist")).toBeNull();
  });
});
