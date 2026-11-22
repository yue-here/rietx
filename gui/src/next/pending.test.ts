// @vitest-environment jsdom
// No pending edit outlives its path (WP-2229). An instrument edit answers the
// paths whose old parameter it ended, the Parameters panel drops every kind of
// pending edit on them, and the Instrument dialog and the Background graph
// pass the answer on and echo what the server did to the hold and free
// registers. What a person sees after a real click is a real browser's
// question (`tests/test_gui_layout_browser.py`).
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

const row = (path: string, value = 0.5) => ({
  path, value, esd: null, lo: -Infinity, hi: Infinity, vary: false, refinable: true, locked: false,
  tie: null, held: false, held_because: "", help_key: "", mode_fixed: false, needs_held_cell: false,
});
const ROWS = ["instrument.background.c4", "instrument.background.c5", "phases.0.atoms.0.x",
              "phases.0.atoms.1.x", "phases.0.atoms.1.y", "phases.0.atoms.1.z",
              "phases.0.atoms.1.biso"].map((path) => row(path));

const p = (value: number, vary = false) => ({ value, vary });
/** A Cu doublet on a flat plate, as `GET /api/instrument` sends one. */
const LAB = {
  source: { kind: "xray_cw", polarization: p(0.8),
            lines: [{ wavelength: p(1.5405), weight: p(1) }, { wavelength: p(1.5443), weight: p(0.5) }] },
  geometry: { kind: "bragg_brentano", goniometer_radius_mm: 217.5, mu_t: null, thickness_mm: null,
              packing_fraction: 0.6, mu_r: null, capillary_radius_mm: null,
              sample_displacement: p(0), sample_transparency: p(0), axial_sl: p(0.02), axial_hl: p(0.02) },
  zero_shift: p(0),
  profile: { shape: "tchz_pv", u: p(0), v: p(0), w: p(0.01), x: p(0), y: p(0) },
  background: { kind: "chebyshev", coefficients: [p(1, true), p(2, true), p(3, true)] },
};
/** What the server answers a profile of another background kind with. */
const EDIT = {
  node_id: "n2", instrument: LAB, released: ["instrument.background.c1"],
  freed: ["instrument.background.c0", "instrument.background.c1"],
  ended: ["instrument.background.c0", "instrument.background.c1", "instrument.background.c2"],
};
const patchInstrument = vi.fn(async (_instrument: unknown, _label?: string): Promise<any> => EDIT);
const patchParams = vi.fn(async (_delta: unknown) => ({}));

vi.mock("../api", async (original) => {
  const real = await original<typeof import("../api")>();
  return {
    ...real,
    api: {
      params: async () => ({ parameters: ROWS, n_free: 0 }),
      structure: async () => ({ structure: { phases: [] }, sites: [], symmetry: [] }),
      symmetry: async () => ({ letters: [] }),
      instrument: async () => ({ instrument: LAB }),
      uploadFile: async () => ({ upload: "u1" }),
      patchInstrument: (instrument: unknown, label?: string) => patchInstrument(instrument, label),
      patchParams: (delta: unknown) => patchParams(delta),
    },
  };
});

import Instrument from "./Instrument.svelte";
import Params from "./Params.svelte";

let app: ReturnType<typeof mount> | null = null;

async function settle() {
  for (let i = 0; i < 24; i++) await tick();
  await new Promise((r) => requestAnimationFrame(() => r(null)));
  for (let i = 0; i < 4; i++) await tick();
  flushSync();
}

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  patchInstrument.mockClear();
  patchParams.mockClear();
});

describe("the Parameters panel's pending edits (WP-2229 case 3)", () => {
  it("drops every kind of pending edit on a gone path, positions and restraints included", async () => {
    const lines: string[] = [];
    app = mount(Params, { target: document.body, props: {
      head: "n1", onmoved: () => {}, say: (line: string) => lines.push(line) } });
    await settle();
    const panel = app as any;
    panel.restoreDraft({
      edits: { "instrument.background.c5": "1.5", "instrument.background.c4": "2" },
      vary: { "instrument.background.c5": true },
      hold: { "instrument.background.c5": true },
      limits: { "instrument.background.c5": [0, 10] },
      restraints: { "instrument.background.c5": { target: 1, sigma: 0.1 },
                    "phases.0.atoms.1.biso": { target: 1, sigma: 0.1 } },
      positions: { "phases.0.atoms.1": { x: "0.25" }, "phases.0.atoms.0": { x: "0.1" } },
    });
    flushSync();
    // the cut of c5 and the removal of atom 1, as an edit elsewhere ends them
    const gone = (key: string) => key === "instrument.background.c5" || key.startsWith("phases.0.atoms.1.");
    const dropped = panel.dropPending(gone);
    expect([...new Set(dropped)].sort()).toEqual(
      ["instrument.background.c5", "phases.0.atoms.1", "phases.0.atoms.1.biso"]);
    const left = panel.draft();
    expect(left.edits).toEqual({ "instrument.background.c4": "2" });
    expect([left.vary, left.hold, left.limits]).toEqual([{}, {}, {}]);
    expect(left.restraints).toEqual({});
    expect(left.positions).toEqual({ "phases.0.atoms.0": { x: "0.1" } });
    expect(lines.at(-1)).toContain("pending edits dropped");
  });

  it("keeps a pending position whose atom the reload still has", async () => {
    app = mount(Params, { target: document.body, props: { head: "n1", onmoved: () => {} } });
    await settle();
    const panel = app as any;
    panel.restoreDraft({ edits: {}, vary: {}, hold: {}, limits: {}, restraints: {},
                         positions: { "phases.0.atoms.1": { y: "0.3" } } });
    flushSync();
    // the reload's own question: is the key's path among the rows?
    const known = ROWS.map((r) => r.path);
    expect(panel.dropPending((key: string) => !known.includes(key))).toEqual([]);
    expect(panel.draft().positions).toEqual({ "phases.0.atoms.1": { y: "0.3" } });
  });
});

describe("a restored draft (review of #1683, finding 1)", () => {
  it("drops a pending edit on a path the head no longer has", async () => {
    const lines: string[] = [];
    app = mount(Params, { target: document.body, props: {
      head: "n1", onmoved: () => {}, say: (line: string) => lines.push(line) } });
    await settle();
    const panel = app as any;
    // kept while the background had eight terms; the head now has c4 and c5
    panel.restoreDraft({ edits: {}, vary: {}, limits: {}, restraints: {}, positions: {},
                         hold: { "instrument.background.c7": true,
                                 "instrument.background.c4": true } });
    flushSync();
    expect(panel.draft().hold).toEqual({ "instrument.background.c4": true });
    expect(lines.at(-1)).toContain("instrument.background.c7");
  });
});

describe("the Instrument dialog's Load profile (WP-2229 case 1)", () => {
  it("echoes the registers' part and drops the pending edits on the paths it ended", async () => {
    const lines: string[] = [];
    const ondropped = vi.fn();
    app = mount(Instrument, { target: document.body, props: {
      rows: ROWS, anodes: [], say: (line: string) => lines.push(line), ondropped,
      onlanded: () => {}, onclose: () => {} } });
    await settle();
    const input = document.querySelector<HTMLInputElement>('input[type="file"]')!;
    const file = new File(["{}"], "spline.json", { type: "application/json" });
    Object.defineProperty(input, "files", { value: [file], configurable: true });
    input.dispatchEvent(new Event("change", { bubbles: true }));
    await settle();
    expect(patchInstrument).toHaveBeenCalledWith({ upload: "u1" }, "instrument from spline.json");
    expect(lines).toEqual([
      'ref.unhold(["instrument.background.c1"])',
      'ref.edit(instrument=load_instrument_profile("spline.json"))',
      'ref.set_vary(["instrument.background.c0","instrument.background.c1"], True)',
    ]);
    expect(ondropped).toHaveBeenCalledTimes(1);
    const ended = ondropped.mock.calls[0][0] as (path: string) => boolean;
    expect(["instrument.background.c2", "instrument.background.c3", "instrument.background.*"]
      .map(ended)).toEqual([true, false, false]);
  });
});

describe("the Instrument dialog's Apply (WP-2229 review)", () => {
  it("sends no typed value on a path its own model edit ended", async () => {
    const lines: string[] = [];
    const rows = [row("instrument.geometry.axial_sl", 0.02), row("instrument.geometry.axial_hl", 0.02)];
    patchInstrument.mockImplementationOnce(async () => ({
      ...EDIT, released: [], freed: [], ended: ["instrument.geometry.axial_sl"] }));
    app = mount(Instrument, { target: document.body, props: {
      rows, anodes: [], say: (line: string) => lines.push(line), ondropped: () => {},
      onlanded: () => {}, onclose: () => {} } });
    await settle();
    const typeInto = (field: string, value: string) => {
      const input = document.querySelector<HTMLInputElement>(`input[data-field="${field}"]`)!;
      input.value = value;
      input.dispatchEvent(new Event("input", { bubbles: true }));
    };
    // one model field and two typed parameter values; the edit ends one of them
    typeInto("geometry.goniometer_radius_mm", "200");
    typeInto("geometry.axial_sl", "0.03");
    typeInto("geometry.axial_hl", "0.04");
    await settle();
    const apply = [...document.querySelectorAll("button")].find((b) => b.textContent === "Apply")!;
    apply.click();
    await settle();
    expect(patchInstrument).toHaveBeenCalledTimes(1);
    expect(patchParams).toHaveBeenCalledWith({ values: { "instrument.geometry.axial_hl": 0.04 } });
    expect(lines).toContain("# typed values dropped: instrument.geometry.axial_sl");
  });
});
