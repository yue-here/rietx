import { describe, expect, it } from "vitest";

import {
  CIVIDIS, DIFF_HIGH, DIFF_LOW, bandRows, barPart, cividis, columnRanges, countLabel, cutValue,
  diverging, hexRgb, labelStep, logFraction, lowerBound, nearest, roundWidth, rowColumns, shownRows,
} from "./seriesmap";

describe("the Map's colours (calls 8, 24)", () => {
  it("runs cividis from its first stop to its last", () => {
    expect(cividis(0)).toEqual(CIVIDIS[0]);
    expect(cividis(1)).toEqual(CIVIDIS[CIVIDIS.length - 1]);
    expect(cividis(0.5)).toEqual(CIVIDIS[4]);
    // out of range and not a number clamp, never throw
    expect(cividis(-1)).toEqual(CIVIDIS[0]);
    expect(cividis(NaN)).toEqual(CIVIDIS[0]);
  });

  it("puts zero difference on the ground, red where obs is above calc, saturating at 5 esd", () => {
    const mid = [250, 250, 250] as const;
    expect(diverging(0, mid)).toEqual(mid);
    expect(diverging(5, mid)).toEqual(DIFF_HIGH);
    expect(diverging(50, mid)).toEqual(DIFF_HIGH);
    expect(diverging(-5, mid)).toEqual(DIFF_LOW);
  });

  it("puts a count on a log scale that ends at the top count", () => {
    expect(logFraction(0, 1000)).toBe(0);
    expect(logFraction(1000, 1000)).toBe(1);
    expect(logFraction(-3, 1000)).toBe(0);
    expect(logFraction(5, 0)).toBe(0);
  });

  it("reads a token's hex", () => {
    expect(hexRgb("#ffffff")).toEqual([255, 255, 255]);
    expect(hexRgb(" #1c1917 ")).toEqual([28, 25, 23]);
    expect(hexRgb("#abc")).toEqual([170, 187, 204]);
    expect(hexRgb("oklch(0.5 0 0)")).toEqual([128, 128, 128]);
  });
});

describe("cells to pixels", () => {
  const tt = Float64Array.from({ length: 10 }, (_, i) => 10 + i);   // 10 … 19

  it("finds the first cell at or past a 2θ", () => {
    expect(lowerBound(tt, 9)).toBe(0);
    expect(lowerBound(tt, 12)).toBe(2);
    expect(lowerBound(tt, 12.5)).toBe(3);
    expect(lowerBound(tt, 99)).toBe(10);
  });

  it("gives every pixel at least one cell, and a wide pixel all of its cells", () => {
    const r = columnRanges(tt, 10, 20, 5);
    expect([...r]).toEqual([0, 2, 2, 4, 4, 6, 6, 8, 8, 10]);
    const fine = columnRanges(tt, 10, 11, 4);
    for (let c = 0; c < 4; c++) expect(fine[2 * c + 1] - fine[2 * c]).toBeGreaterThanOrEqual(1);
    // a narrow pixel takes the cell nearest its middle, not the next one
    expect([...fine]).toEqual([0, 1, 0, 1, 1, 2, 1, 2]);
    // a view ending on the last cell still draws it
    const end = columnRanges(tt, 10, 19, 3);
    expect(end[end.length - 1]).toBe(10);
  });

  it("finds the nearest cell", () => {
    expect(nearest(tt, 12.4)).toBe(2);
    expect(nearest(tt, 12.6)).toBe(3);
    expect(nearest(tt, 5)).toBe(0);
    expect(nearest(tt, 99)).toBe(9);
  });

  it("takes a pixel's highest count, and its mean difference, skipping NaN", () => {
    // two rows of ten cells, row 1 offset by ten
    const cells = Float64Array.from([1, 5, 2, 2, NaN, NaN, 3, 9, 0, 1, ...Array(10).fill(7)]);
    const r = columnRanges(tt, 10, 20, 5);
    expect([...rowColumns(cells, 0, r, false)].map(String)).toEqual(["5", "2", "NaN", "9", "1"]);
    expect([...rowColumns(cells, 0, r, true)].map(String)).toEqual(["3", "2", "NaN", "6", "0.5"]);
    expect([...rowColumns(cells, 10, r, false)]).toEqual([7, 7, 7, 7, 7]);
  });

  it("averages a row across the cut's width, and takes the nearest cell at no width", () => {
    const cells = Float64Array.from([0, 1, 2, 3, 4, 5, 6, 7, 8, 9]);
    expect(cutValue(cells, 0, tt, 14, 2)).toBe(3.5);     // [13, 15): 13 and 14
    expect(cutValue(cells, 0, tt, 14, 0)).toBe(4);
    expect(cutValue(cells, 0, tt, 14.2, 0)).toBe(4);
    expect(cutValue(cells, 0, tt, 14.7, 0)).toBe(5);
    expect(cutValue(Float64Array.from(Array(10).fill(NaN)), 0, tt, 14, 2)).toBeNaN();
  });
});

describe("rows and gestures", () => {
  it("shows every row, a window of them, or them flipped", () => {
    expect(shownRows(4, null, false)).toEqual([0, 1, 2, 3]);
    expect(shownRows(4, [2, 1], false)).toEqual([1, 2]);
    expect(shownRows(4, null, true)).toEqual([3, 2, 1, 0]);
    expect(shownRows(4, [1, 9], true)).toEqual([3, 2, 1]);
  });

  it("averages a shift-click's rows, else the selected one", () => {
    expect(bandRows(null, 2)).toEqual([2]);
    expect(bandRows([4, 1], 2)).toEqual([1, 2, 3, 4]);
  });

  it("names the part of the bar a press takes", () => {
    expect(barPart(100, 102, 150)).toBe("left");
    expect(barPart(148, 102, 150)).toBe("right");
    expect(barPart(120, 102, 150)).toBe("move");
    expect(barPart(300, 102, 150)).toBe("new");
  });

  it("rounds a width to three figures, never under one cell", () => {
    expect(roundWidth(0.123456, 0.01)).toBe(0.123);
    expect(roundWidth(0.001, 0.01)).toBe(0.01);
  });

  it("labels 2θ at most every 70 px, and a count in thousands past 10 000", () => {
    expect(labelStep(40, 700)).toBe(5);
    expect(labelStep(0.5, 700)).toBe(0.05);
    expect(countLabel(9876)).toBe("9876");
    expect(countLabel(123456)).toBe("120k");
    expect(countLabel(NaN)).toBe("");
  });
});
