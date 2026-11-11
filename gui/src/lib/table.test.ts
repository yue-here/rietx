/**
 * The parameter table's logic, asserted without a DOM.
 *
 * Rows are built from the *same* committed vocabulary the glob fixture uses, so
 * the grouping rule is exercised against the path shapes the package actually
 * produces — an ADP component, a Stephens DOF, a second emission line's weight —
 * rather than against three paths someone invented while writing the rule.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  asGlob,
  editState,
  flatten,
  formatEsd,
  formatValue,
  groupOf,
  heldGlyph,
  leafName,
  heldKind,
  normalize,
  num,
  selection,
  validateEdit,
  varyEdit,
  varyEditFor,
  varyOf,
  varyOfAll,
  varyStillPending,
  varyTargets,
  windowSlice,
  type ParamRow,
} from "./table";

const PATHS: string[] = JSON.parse(
  readFileSync(
    fileURLToPath(new URL("../../../tests/data/gui/fnmatch_cases.json", import.meta.url)),
    "utf-8",
  ),
).paths;

function row(path: string, over: Partial<ParamRow> = {}): ParamRow {
  const base: ParamRow = {
    path,
    value: 1,
    vary: false,
    lo: -Infinity,
    hi: Infinity,
    tie: null,
    locked: false,
    held: false,
    esd: null,
    mode_fixed: false,
    needs_held_cell: false,
    refinable: true,
    held_because: "",
    help_key: null,
    ...over,
  };
  // the server's own definition (`ParameterRow.refinable`), so a fixture cannot
  // claim a row is free while carrying a reason it is not
  base.refinable = over.refinable ?? (!base.locked && base.tie === null
    && !base.mode_fixed && !base.held && !base.needs_held_cell);
  return base;
}

const ROWS = PATHS.map((path) => row(path));

describe("grouping", () => {
  it("drops the leaf, and one more when the leaf is a bare index", () => {
    expect(groupOf("phases.0.cell.a")).toBe("phases.0.cell");
    expect(groupOf("instrument.profile.w")).toBe("instrument.profile");
    expect(groupOf("phases.0.scale")).toBe("phases.0");
    // one atom, one heading — its DOFs, its ADP components and its biso together
    expect(groupOf("phases.0.atoms.3.dof.1")).toBe("phases.0.atoms.3");
    expect(groupOf("phases.0.atoms.3.adp.0")).toBe("phases.0.atoms.3");
    expect(groupOf("phases.0.atoms.3.biso")).toBe("phases.0.atoms.3");
    expect(groupOf("phases.0.microstrain.dof.2")).toBe("phases.0.microstrain");
    expect(groupOf("instrument.source.lines.1.weight")).toBe("instrument.source.lines.1");
  });

  it("keeps the server's order, which is the θ-vector order", () => {
    const { items, groups } = flatten(ROWS);
    // groups appear where their first row does, and rows never move: three
    // views of one table (this, the text document, a stage plan) would
    // otherwise disagree about the order things are freed in
    const firstAppearance: string[] = [];
    for (const path of PATHS) {
      const key = groupOf(path);
      if (!firstAppearance.includes(key)) firstAppearance.push(key);
    }
    expect(groups).toEqual(firstAppearance);
    expect(groups[0]).toBe("phases.0.cell");
    // grouping is the *only* reordering: rows are gathered under the heading
    // that appeared first and are otherwise in the order the server sent them
    const expected = [...PATHS].sort((a, b) =>
      firstAppearance.indexOf(groupOf(a)) - firstAppearance.indexOf(groupOf(b)));
    const paths = items.filter((i) => i.kind === "row").map((i) => i.key);
    expect(paths).toEqual(expected);
  });

  it("collapses a group to its header without losing the count", () => {
    const full = flatten(ROWS);
    const collapsed = flatten(ROWS, { collapsed: new Set(["phases.0.cell"]) });
    const header = collapsed.items.find((i) => i.kind === "group" && i.key === "phases.0.cell");
    expect(header).toMatchObject({ n: 6, free: 0 });
    expect(collapsed.items.length).toBe(full.items.length - 6);
  });

  it("counts free rows per group, so a header says what is refining", () => {
    const rows = ROWS.map((r) => (r.path.startsWith("phases.0.cell") ? { ...r, vary: true } : r));
    const header = flatten(rows).items.find((i) => i.kind === "group" && i.key === "phases.0.cell");
    expect(header).toMatchObject({ n: 6, free: 6 });
  });
});

describe("what a row is called", () => {
  it("keeps the index's own name, so a row is never called `0`", () => {
    // measured in a browser on NAC: five rows under one heading called `0`,
    // `1`, `2`, `3` and `occ`, because the last dot segment of
    // `phases.0.atoms.0.adp.0` is a bare index and says nothing (WP-1029)
    expect(leafName("phases.0.atoms.0.adp.0", "phases.0.atoms.0")).toBe("adp.0");
    expect(leafName("phases.0.atoms.0.dof.1", "phases.0.atoms.0")).toBe("dof.1");
    expect(leafName("phases.0.microstrain.dof.2", "phases.0.microstrain")).toBe("dof.2");
    // …and a leaf that is a name is left alone, heading or no heading
    expect(leafName("phases.0.atoms.0.biso", "phases.0.atoms.0")).toBe("biso");
    expect(leafName("phases.0.cell.a", "phases.0.cell")).toBe("a");
    expect(leafName("instrument.source.lines.1.weight", "instrument.source.lines.1"))
      .toBe("weight");
  });
});

describe("the filter is the selection", () => {
  it("wraps a bare word and passes a glob through untouched", () => {
    expect(asGlob("cell")).toBe("*cell*");
    expect(asGlob("  ")).toBe("*");
    expect(asGlob("phases.*.cell.*")).toBe("phases.*.cell.*");
    expect(asGlob("instrument.background.c?")).toBe("instrument.background.c?");
  });

  it("previews with the very string the PATCH will send", () => {
    // the point of asGlob: preview and apply cannot select different sets
    const glob = asGlob("cell");
    const { shown } = flatten(ROWS, { glob });
    expect(shown).toBe(selection(ROWS, glob).matched);
    // a phase's six cell rows, and the six of a phase whose cell is stated
    // through its parent's (`parent_cell.cell.*`, WP-1419)
    expect(shown).toBe(12);
  });

  it("excludes locked and tied rows from a free/fix count", () => {
    const rows = [
      row("phases.0.cell.a", { vary: true }),
      row("phases.0.cell.b", { tie: { sources: ["phases.0.cell.a"] } }),
      row("phases.0.cell.alpha", { locked: true }),
      row("phases.0.cell.c", { tie: { sources: ["phases.0.cell.a"] } }),
    ];
    // set_vary never matches a locked or tied entry however broad the glob, so
    // a preview that counted them would promise four and deliver one
    expect(selection(rows, "phases.*.cell.*")).toMatchObject({
      matched: 4,
      freeable: 1,
      toFree: 0,
      toFix: 1,
    });
  });

  it("counts a mode-fixed row as freeable, because set_vary does free it", () => {
    const rows = [row("phases.0.atoms.0.biso", { mode_fixed: true })];
    expect(selection(rows, "*biso*")).toMatchObject({ freeable: 1, toFree: 1 });
  });
});

describe("the three held states", () => {
  it("names each one separately — mode_fixed is not locked", () => {
    expect(heldKind(row("a", { locked: true }))).toBe("locked");
    expect(heldKind(row("a", { tie: { sources: ["b"] } }))).toBe("tied");
    expect(heldKind(row("a", { mode_fixed: true }))).toBe("mode");
    expect(heldKind(row("a"))).toBe("");
  });

  it("hides them in Simple mode and reports how many", () => {
    const rows = [
      row("phases.0.cell.a"),
      row("phases.0.cell.b", { tie: { sources: ["phases.0.cell.a"] } }),
      row("phases.0.cell.alpha", { locked: true }),
    ];
    const simple = flatten(rows, { simple: true });
    expect(simple.shown).toBe(1);
    expect(simple.hidden).toBe(2);   // a count, not a silent truncation
    expect(flatten(rows).hidden).toBe(0);
  });
});

describe("the refine flag", () => {
  it("marks each held reason and leaves a free row unmarked", () => {
    // two panels draw this now (WP-1214), which is why the glyphs are here and
    // not in either of them
    expect(heldGlyph(row("a", { locked: true }))).toBe("🔒");
    expect(heldGlyph(row("a", { tie: { sources: ["b"] } }))).toBe("=");
    expect(heldGlyph(row("a", { mode_fixed: true }))).toBe("·");
    // the fourth, which the three-arm ternary this replaced drew as the third:
    // a free wavelength needs its cell held, and that is a degeneracy rather
    // than a tie — nothing derives the row, another free parameter merely makes
    // it unmeasurable (found in a browser, WP-1214)
    expect(heldGlyph(row("a", { needs_held_cell: true, refinable: false })))
      .toBe("≈");
    expect(heldKind(row("a", { needs_held_cell: true }))).toBe("degenerate");
    // the fifth: the caller declared this one with `Refinement.hold`, so a
    // plan's turn_on glob loses to it (WP-1435).  A pin rather than a lock,
    // because unhold() takes it back and a space group does not
    expect(heldGlyph(row("a", { held: true, refinable: false }))).toBe("📌");
    expect(heldKind(row("a", { held: true }))).toBe("hold");
    // and it loses in turn to the reasons above it, which unhold cannot lift
    expect(heldKind(row("a", { held: true, locked: true }))).toBe("locked");
    expect(heldKind(row("a", { held: true, mode_fixed: true }))).toBe("mode");
    expect(heldGlyph(row("a"))).toBe("");
    // …and a reason this client does not know still gets a mark: an empty box
    // reads as a control that failed to render
    expect(heldGlyph(row("a", { refinable: false }))).toBe("·");
  });

  it("shows what was toggled, else what the row has", () => {
    const free = row("a", { vary: true });
    expect(varyOf(free, new Map())).toBe(true);
    expect(varyOf(free, new Map([["a", false]]))).toBe(false);
  });

  it("drops a toggle that lands back on the row's own flag", () => {
    const held = row("a", { vary: false });
    const once = varyEdit(new Map(), held, true);
    expect([...once]).toEqual([["a", true]]);
    // …and back again is not an edit: `set_vary` would record a node saying
    // nothing, and the Apply button is enabled by this count
    expect([...varyEdit(once, held, false)]).toEqual([]);
  });

  it("does not mutate the map it was given", () => {
    const before = new Map<string, boolean>();
    varyEdit(before, row("a"), true);
    expect(before.size).toBe(0);
  });
});

describe("a vary key that names a group", () => {
  // WP-1215: an atom's coordinate DOFs are freed together — "per-axis intent
  // does not map onto rows such as [1,1,0]" — so one box is about N rows and
  // `set_vary` is told the glob, in one node.
  const DOFS = [row("phases.0.atoms.1.dof.0"), row("phases.0.atoms.1.dof.1"),
                row("phases.0.atoms.2.biso", { vary: true })];
  const GLOB = "phases.0.atoms.1.dof.*";

  it("names one row for a path and every match for a glob", () => {
    expect(varyTargets(DOFS, "phases.0.atoms.1.dof.0").map((r) => r.path))
      .toEqual(["phases.0.atoms.1.dof.0"]);
    expect(varyTargets(DOFS, GLOB).map((r) => r.path))
      .toEqual(["phases.0.atoms.1.dof.0", "phases.0.atoms.1.dof.1"]);
    expect(varyTargets(DOFS, "phases.0.atoms.7.dof.*")).toEqual([]);
  });

  it("answers null for a group that disagrees with itself", () => {
    // the third answer is the one worth having: `false` over a half-freed site
    // says something untrue about the other half, and the DOM has an
    // `indeterminate` for exactly this
    expect(varyOfAll(DOFS, new Map(), GLOB)).toBe(false);
    const half = [row("phases.0.atoms.1.dof.0", { vary: true }),
                  row("phases.0.atoms.1.dof.1")];
    expect(varyOfAll(half, new Map(), GLOB)).toBe(null);
    // …and a pending toggle is the whole answer, since it is about the group
    expect(varyOfAll(half, new Map([[GLOB, true]]), GLOB)).toBe(true);
  });

  it("drops a toggle only when every row it names already agrees", () => {
    const once = varyEditFor(new Map(), DOFS, GLOB, true);
    expect([...once]).toEqual([[GLOB, true]]);
    expect([...varyEditFor(once, DOFS, GLOB, false)]).toEqual([]);
    // a half-freed group never drops: setting it *does* say something about the
    // half that disagrees
    const half = [row("phases.0.atoms.1.dof.0", { vary: true }),
                  row("phases.0.atoms.1.dof.1")];
    expect([...varyEditFor(new Map(), half, GLOB, true)]).toEqual([[GLOB, true]]);
  });

  it("stops being pending when someone else has already done it", () => {
    // the same check `varyPending` makes per keystroke: a box ticked before the
    // parameter panel freed the same rows would otherwise send a `set_vary`
    // whose hits are empty
    expect(varyStillPending(DOFS, GLOB, true)).toBe(true);
    const freed = DOFS.map((r) => ({ ...r, vary: true }));
    expect(varyStillPending(freed, GLOB, true)).toBe(false);
    expect(varyStillPending(DOFS, "phases.0.atoms.7.dof.*", true)).toBe(false);
  });
});

describe("the virtual window", () => {
  it("covers the viewport and pads to the full scroll height", () => {
    const rowHeight = 22;
    const slice = windowSlice(5000, 4400, 600, rowHeight);
    expect(slice.start).toBeLessThanOrEqual(200);            // 4400/22
    expect(slice.end).toBeGreaterThanOrEqual(200 + 600 / rowHeight);
    expect(slice.padTop + (slice.end - slice.start) * rowHeight + slice.padBottom)
      .toBe(5000 * rowHeight);
  });

  it("clamps at both ends without going negative", () => {
    expect(windowSlice(5000, 0, 600, 22)).toMatchObject({ start: 0, padTop: 0 });
    const bottom = windowSlice(5000, 5000 * 22, 600, 22);
    expect(bottom.end).toBe(5000);
    expect(bottom.padBottom).toBe(0);
    // a list shorter than the viewport is one slice, not a negative pad
    expect(windowSlice(3, 0, 600, 22)).toMatchObject({ start: 0, end: 3, padBottom: 0 });
  });
});

describe("pending edits", () => {
  const bounded = row("instrument.profile.w", { value: 0.004, lo: 0, hi: 1 });

  it("refuses out-of-bounds and non-numbers before the round trip", () => {
    expect(validateEdit(bounded, "0.006")).toBe("");
    expect(validateEdit(bounded, "-1")).toContain("lower bound");
    expect(validateEdit(bounded, "2")).toContain("upper bound");
    expect(validateEdit(bounded, "abc")).toBe("not a number");
    expect(validateEdit(bounded, "")).toBe("not a number");
  });

  it("batches into one set_values body, dropping unchanged text", () => {
    const rows = [bounded, row("phases.0.cell.a", { value: 4.1568 })];
    const edits = new Map([
      ["instrument.profile.w", "0.004"],        // unchanged
      ["phases.0.cell.a", "4.157"],             // changed
      ["nope", "1"],                            // not a row
    ]);
    const state = editState(rows, edits);
    expect(state.values).toEqual({ "phases.0.cell.a": 4.157 });
    expect(state.touched).toBe(1);
    expect(state.invalid).toEqual([]);
  });

  it("compares typed text against the *rendered* value, not the stored float", () => {
    // the cell shows 4.1568 for a value of 4.156783(19); clicking in and out
    // again must not send 4.1568 and truncate the parameter (WP-1009's rule)
    const rows = [row("phases.0.cell.a", { value: 4.156783, esd: 0.00019 })];
    const untouched = editState(rows, new Map([["phases.0.cell.a", "4.1568"]]));
    expect(untouched.values).toEqual({});
    expect(untouched.touched).toBe(0);
  });

  it("counts an invalid cell as touched, so Revert exists for it", () => {
    const state = editState([bounded], new Map([["instrument.profile.w", "2"]]), 1);
    expect(state.values).toEqual({});
    expect(state.invalid).toEqual([{ path: "instrument.profile.w", why: "above the upper bound 1" }]);
    expect(state.touched).toBe(2);              // the bad cell, plus one vary toggle
  });
});

describe("the wire's spelling of an infinite bound", () => {
  it("reads Infinity back from the string JSON can carry", () => {
    // the server sends "Infinity" because Python's bare `Infinity` token is not
    // JSON and `JSON.parse` rejects the whole response — nearly every row here
    // has an unbounded side, so this is not an edge case
    expect(num("Infinity")).toBe(Infinity);
    expect(num("-Infinity")).toBe(-Infinity);
    expect(num(0.1)).toBe(0.1);
  });

  it("normalizes a payload's rows so bounds compare as numbers", () => {
    const [row] = normalize([
      { path: "phases.0.cell.a", value: 4.1, lo: 0.1, hi: "Infinity", esd: null },
    ]);
    expect(row.hi).toBe(Infinity);
    expect(row.esd).toBeNull();                 // a genuine null is not 0
    expect(validateEdit(row, "1e9")).toBe("");
    expect(validateEdit(row, "0.05")).toContain("lower bound");
  });
});

describe("value formatting", () => {
  it("shows a value to the place its esd justifies", () => {
    // 4.1568(2) — one significant figure of the esd sets the last place, the
    // crystallographic convention; `4.156783000` for something known to ±0.0002
    // is a number pretending to a precision the fit never had
    expect(formatValue(4.156783, 0.00019)).toBe("4.1568");
    expect(formatEsd(4.156783, 0.00019)).toBe("(2)");
    expect(formatValue(4.15678312, 0.000002)).toBe("4.156783");
    expect(formatEsd(4.15678312, 0.000002)).toBe("(2)");
  });

  it("falls back to six significant figures without an esd", () => {
    expect(formatValue(4.15678312, null)).toBe("4.15678");
    expect(formatEsd(4.15678312, null)).toBe("");
    expect(formatEsd(4.15678312, 0)).toBe("");
  });

  it("abandons the last-digit notation only where the esd has swallowed the value (WP-1209)", () => {
    // the measured case: a 2θ of 35.09° with a degenerate σ of 111° printed
    // `35(111)` — a flat direction wearing an integer's precision
    expect(formatValue(35.09, 111)).toBe("35.09");
    expect(formatEsd(35.09, 111)).toBe(" ±110");
    // an esd of 1 or more that is a precision keeps the convention
    expect(formatValue(12345.6, 56)).toBe("12346");
    expect(formatEsd(12345.6, 56)).toBe("(56)");
    expect(formatValue(3.7, 2.0)).toBe("4");
    expect(formatEsd(3.7, 2.0)).toBe("(2)");
    // a Biso consistent with zero: the value survives, the esd rides beside it
    expect(formatValue(0.4, 1.3)).toBe("0.4");
    expect(formatEsd(0.4, 1.3)).toBe(" ±1.3");
    // below 1 the convention still has a place to count in
    expect(formatValue(0.002, 0.005)).toBe("0.002");
    expect(formatEsd(0.002, 0.005)).toBe("(5)");
    // the corundum position esds the pseudo-inverse used to truncate to 0.06°
    expect(formatEsd(43.3551, 1e17)).toBe(" ±1.0e+17");
    expect(formatEsd(43.3551, 1e49)).toBe(" ±1.0e+49");
    // the notation is chosen after rounding to two figures, or 999 999 prints
    // the seven digits the exponential form exists to avoid (code review)
    expect(formatEsd(43.3551, 999_999)).toBe(" ±1.0e+6");
    expect(formatEsd(43.3551, 949_999)).toBe(" ±950000");
    // the boundary: equal is not larger
    expect(formatValue(111, 111)).toBe("111");
    expect(formatEsd(111, 111)).toBe("(111)");
  });
});
