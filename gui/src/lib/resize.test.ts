/**
 * The splitter's arithmetic (WP-1029).
 *
 * jsdom has no layout, so a splitter's *effect* is a screenshot question and
 * only this half can be asserted — which is exactly why it was pulled out of
 * `Console.svelte` into pure functions rather than generalised in place.
 */
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { GRIP, MODEL_MIN, SERIES_MIN, SHELL_MIN, axisOf, clampSize, dragged,
         fitColumns, modelStacks, modelThreshold, seriesCompact, shellStacks,
         shellThreshold } from "./resize";

// --- ported cases: the table below is copied verbatim into
// tests/watch_core.test.mjs, because `rietx watch`'s page cannot import this
// module and a copy that is not pinned is a copy that drifts. The two blocks
// are compared character for character by
// tests/test_watch_app.py::test_the_ported_drag_arithmetic_keeps_the_guis_cases,
// so a case edited here fails the page's copy until it follows. Keep the block
// free of types: it has to parse as plain JavaScript too.
const PORTED = [
  // axisOf(grow) — the coordinate a grip reads is the one its pane grows along
  ["axisOf", ["up"], "y"],
  ["axisOf", ["down"], "y"],
  ["axisOf", ["left"], "x"],
  ["axisOf", ["right"], "x"],
  // dragged(start, from, at, grow) — sign only, and the sign is per-edge.
  // Console.svelte's case: the log is below the grip, so dragging *up* makes
  // it taller.
  ["dragged", [150, 400, 340, "up"], 210],
  ["dragged", [150, 400, 460, "up"], 90],
  // the sidebar: its grip is on its left edge and the pane is to the right
  ["dragged", [420, 900, 820, "left"], 500],
  ["dragged", [420, 900, 980, "left"], 340],
  // the model pane's columns: each grip is on the right edge of the column it
  // sizes, so the two directions are both in use in one app
  ["dragged", [300, 300, 380, "right"], 380],
  // clampSize(value, min, keep, available) — the floor
  ["clampSize", [10, 26, 120, 800], 26],
  // and whatever must survive of the pane next door
  ["clampSize", [999, 26, 120, 800], 680],
  // jsdom, or a drag before the first layout: `available` of 0 must not clamp
  // every pane to a negative ceiling, which is what a naive `available - keep`
  // would do — and the same when the container is too small to hold both
  ["clampSize", [400, 26, 120, 0], 400],
  ["clampSize", [400, 26, 120, 100], 400],
  // rounds, so a style attribute is a whole number of pixels
  ["clampSize", [210.6, 26, 120, 0], 211],
];
// --- end ported cases ---

const PORTED_FNS: Record<string, (...a: never[]) => unknown> =
  { axisOf, clampSize, dragged } as unknown as
  Record<string, (...a: never[]) => unknown>;

describe("the arithmetic the rietx watch page also runs", () => {
  it("answers every ported case", () => {
    for (const row of PORTED as unknown as [string, never[], unknown][]) {
      const [name, args, want] = row;
      expect(PORTED_FNS[name](...args), `${name}(${args.join(", ")})`)
        .toBe(want);
    }
  });
});

describe("fitting stored columns into the window they are reopened in", () => {
  it("passes them through when they fit", () => {
    expect(fitColumns([400, 380], 1400, 200, 260)).toEqual([400, 380]);
  });

  it("shrinks them proportionally when they do not", () => {
    // measured in a browser: widths chosen at 1500 px reopened at 1000 px left
    // the third column **24 px** wide.  A drag clamps against the extent it was
    // performed in; a stored width has to be clamped against the one it is
    // rendered in, and no drag is present to do it.
    const fitted = fitColumns([920, 393], 1000, 200, 260)!;
    expect(fitted[0] + fitted[1]).toBeLessThanOrEqual(1000 - 260);
    // the *relative* choice survives, which is the part still worth keeping
    expect(fitted[0] / fitted[1]).toBeCloseTo(920 / 393, 1);
  });

  it("stops at the floor rather than shrinking to nothing", () => {
    expect(fitColumns([900, 900], 500, 200, 260)).toEqual([200, 200]);
  });

  it("leaves them alone when nothing is measurable", () => {
    expect(fitColumns([920, 393], 0)).toEqual([920, 393]);
    expect(fitColumns(null, 1200)).toBeNull();
  });
});

describe("when the model pane becomes one stacked column", () => {
  it("is decided by the three floors, not by a round number", () => {
    // WP-1034 task 1, re-measured WP-1215 when the atom row went from seven
    // columns to eleven: the table's min-content is 642 px on the fluorapatite
    // example, in the widest state it reaches (one atom anisotropic), and the
    // column adds 24 px of padding — so `structure` is a measurement and this
    // number moves when the row does.
    expect(modelThreshold()).toBe(1256);
    expect(modelStacks(modelThreshold() - 1)).toBe(true);
    expect(modelStacks(modelThreshold())).toBe(false);
  });

  it("takes the form column's floor from the form's own three columns", () => {
    // WP-1216, and it is WP-1215's rule turned into a test rather than a
    // comment: this number is stated in `lib/resize.ts` and *drawn* from three
    // constants in `Model.svelte`, and a width restated in two places goes
    // stale in one of them.  Read the CSS, do the arithmetic, compare.  The
    // form is three columns wide at every width — that is what puts U V W over
    // X Y — so its minimum is three tracks, two gaps and the column's padding.
    const css = readFileSync(
      fileURLToPath(new URL("../panels/Model.svelte", import.meta.url)), "utf-8");
    const read = (re: RegExp) => {
      const m = re.exec(css);
      expect(m, `no match for ${re}`).toBeTruthy();
      return Number(m![1]);
    };
    const track = read(/--w-num:\s*([\d.]+)px/);
    const gap = read(/--grid-gap:\s*([\d.]+)px/);
    const padding = read(/\.column \{[^}]*?padding:\s*[\d.]+px\s+([\d.]+)px/s);
    expect(MODEL_MIN.form).toBe(3 * track + 2 * gap + 2 * padding);
    // …and the grid caps itself at exactly the three tracks it declares, so a
    // wide column gives the form no more than it asked for
    expect(css).toContain("calc(3 * var(--w-num) + 2 * var(--grid-gap))");
  });

  it("counts the grips, because they are inside the row it is measuring", () => {
    // found in a browser (WP-1215): the three floors alone came to 1126 and the
    // structure column measured 636 of the 642 its table needs, side-scrolling
    // at exactly the width the threshold exists to protect. The gap was there
    // at 932 too; nobody had put a ruler on it.
    expect(modelThreshold() - 2 * GRIP)
      .toBe(MODEL_MIN.structure + MODEL_MIN.form + MODEL_MIN.view);
    expect(modelStacks(MODEL_MIN.structure + MODEL_MIN.form + MODEL_MIN.view))
      .toBe(true);
  });

  it("stacks at every sidebar width the shell can produce", () => {
    // the clamp floor, a 1000/1200 px window's 38 %, and the clamp ceiling —
    // measured 340 / 380 / 456 / 560, all narrower than three columns need
    for (const width of [340, 380, 456, 560, 720]) {
      expect(modelStacks(width)).toBe(true);
    }
    // …and does not, once the pane has the whole of a wide window
    expect(modelStacks(1500)).toBe(false);
  });

  it("leaves the flex defaults alone when nothing is measurable", () => {
    // jsdom, or the render before the first layout: the same fallback
    // `clampSize` and `fitColumns` make, rather than a stacked pane by accident
    expect(modelStacks(0)).toBe(false);
  });
});

describe("when the staged-series table drops its descriptive columns", () => {
  it("is decided by the measured halves, not by a round number", () => {
    // WP-1016's browser pass: the row is 539 px, of which the four load-bearing
    // columns (#, label, coordinate, the reorder/remove buttons) are 308 and the
    // four descriptive ones are 231.
    expect(SERIES_MIN.core + SERIES_MIN.detail).toBe(539);
    expect(seriesCompact(538)).toBe(true);
    expect(seriesCompact(539)).toBe(false);
  });

  it("reflows at every sidebar width narrower than the clamp ceiling", () => {
    // the panel is the sidebar minus its 20 px of padding, so 559 px of column
    // is where the full table fits exactly — which is the `clamp(340px, 38%,
    // 560px)` ceiling, i.e. the shipped default just holds it
    for (const width of [320, 340, 436, 460, 538]) {
      expect(seriesCompact(width)).toBe(true);
    }
    expect(seriesCompact(540)).toBe(false);
    expect(seriesCompact(1480)).toBe(false);   // the full-window hatch
  });

  it("keeps the full table when nothing is measurable", () => {
    // jsdom, or before the first layout: the same fallback every other
    // measurement here makes, rather than a reflowed table by accident
    expect(seriesCompact(0)).toBe(false);
  });
});

describe("the window's one-column threshold (WP-2123)", () => {
  it("is the sum of the two panels' floors", () => {
    expect(shellThreshold()).toBe(SHELL_MIN.graphs + SHELL_MIN.side);
    expect(shellThreshold()).toBe(760);
    expect(shellStacks(shellThreshold() - 1)).toBe(true);
    expect(shellStacks(shellThreshold())).toBe(false);
  });

  it("stays side by side while nothing is measurable", () => {
    expect(shellStacks(0)).toBe(false);
  });
});
