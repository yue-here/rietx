import { describe, expect, it } from "vitest";

import {
  Undo, addGlobs, dropIndex, moveStage, newStageName, planDiffers, resolvedPrefix,
  sameStage, slideOffset,
} from "./plan";

const A = { name: "scale_bkg", turn_on: ["phases.*.scale"], max_iter: 100 };
const B = { name: "cell", turn_on: ["phases.*.cell.*"], max_iter: 100 };
const C = { name: "biso", turn_on: ["phases.*.atoms.*.biso"], max_iter: 100 };

describe("moving a stage", () => {
  it("moves one item and leaves the rest in order", () => {
    expect(moveStage(["a", "b", "c", "d"], 3, 1)).toEqual(["a", "d", "b", "c"]);
    expect(moveStage(["a", "b", "c", "d"], 0, 2)).toEqual(["b", "c", "a", "d"]);
  });

  it("returns a copy for a no-op or an out-of-range move", () => {
    const list = ["a", "b"];
    expect(moveStage(list, 1, 1)).toEqual(list);
    expect(moveStage(list, 0, 5)).toEqual(list);
    expect(moveStage(list, 0, 5)).not.toBe(list);
  });
});

describe("where a lifted row lands", () => {
  const centres = [10, 40, 70, 100];

  it("stays put until its centre crosses a neighbour's", () => {
    expect(dropIndex(centres, 1, 45)).toBe(1);
    expect(dropIndex(centres, 1, 69)).toBe(1);
    expect(dropIndex(centres, 1, 71)).toBe(2);
  });

  it("passes every row whose centre it crosses, either way", () => {
    expect(dropIndex(centres, 0, 101)).toBe(3);
    expect(dropIndex(centres, 3, 5)).toBe(0);
    expect(dropIndex(centres, 3, 39)).toBe(1);
  });

  it("slides the rows between by the lifted row's height", () => {
    // row 0 held over row 2: rows 1 and 2 move up, row 3 stays
    expect([1, 2, 3].map((k) => slideOffset(k, 0, 2, 30))).toEqual([-30, -30, 0]);
    // row 3 held over row 1: rows 1 and 2 move down, row 0 stays
    expect([0, 1, 2].map((k) => slideOffset(k, 3, 1, 30))).toEqual([0, 30, 30]);
  });
});

describe("which resolved facts stay true while the plan is edited", () => {
  it("compares every field, in any key order", () => {
    expect(sameStage(A, { max_iter: 100, turn_on: ["phases.*.scale"], name: "scale_bkg" }))
      .toBe(true);
    expect(sameStage(A, { ...A, max_iter: 50 })).toBe(false);
    expect(sameStage(A, { ...A, turn_on: ["phases.*.scale", "x"] })).toBe(false);
  });

  it("reads an empty fix list as the absent one, and a fix as a change", () => {
    // a stored plan carries `turn_off: []`; a stage typed here has none
    expect(sameStage(A, { ...A, turn_off: [] })).toBe(true);
    expect(sameStage({ ...A, turn_off: [] }, A)).toBe(true);
    expect(sameStage(A, { ...A, turn_off: ["instrument.profile.*"] })).toBe(false);
  });

  it("keeps the stages before the first difference", () => {
    expect(resolvedPrefix([A, B, C], [A, B, C])).toBe(3);
    expect(resolvedPrefix([A, B, C], [A, { ...B, name: "cell2" }, C])).toBe(1);
    // a swap changes everything from the first moved stage on
    expect(resolvedPrefix([A, B, C], [B, A, C])).toBe(0);
    // a stage added at the end leaves every earlier one resolved
    expect(resolvedPrefix([A, B], [A, B, C])).toBe(2);
  });

  it("calls the plan edited on any difference, a removed last stage included", () => {
    expect(planDiffers([A, B], [A, B])).toBe(false);
    expect(planDiffers([A, B], [A])).toBe(true);
    expect(planDiffers([A], [A, B])).toBe(true);
  });
});

describe("a stage's globs", () => {
  it("adds what is typed, split on commas and spaces, once each", () => {
    expect(addGlobs(["a.*"], "b.*, c.* a.*")).toEqual(["a.*", "b.*", "c.*"]);
    expect(addGlobs(["a.*"], "   ")).toEqual(["a.*"]);
  });

  it("names a new stage after the first free number", () => {
    expect(newStageName([A, B])).toBe("stage 3");
    expect(newStageName([A, { ...B, name: "stage 3" }])).toBe("stage 4");
  });
});

describe("undo", () => {
  it("steps back and forward through whole states", () => {
    const undo = new Undo<string[]>();
    expect(undo.undo(["x"])).toBeNull();
    undo.record(["a"]);
    undo.record(["a", "b"]);
    expect(undo.undo(["a", "b", "c"])).toEqual(["a", "b"]);
    expect(undo.undo(["a", "b"])).toEqual(["a"]);
    expect(undo.canUndo).toBe(false);
    expect(undo.redo(["a"])).toEqual(["a", "b"]);
    expect(undo.redo(["a", "b"])).toEqual(["a", "b", "c"]);
    expect(undo.canRedo).toBe(false);
  });

  it("forgets the redo side on a new edit, and copies what it keeps", () => {
    const undo = new Undo<{ v: number[] }>();
    const state = { v: [1] };
    undo.record(state);
    state.v.push(2);                       // a later mutation of the caller's object
    expect(undo.undo({ v: [9] })).toEqual({ v: [1] });
    undo.record({ v: [5] });
    expect(undo.canRedo).toBe(false);
  });
});
