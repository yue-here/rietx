// The History tab's pure half (WP-2211): the table's words, the Graph view's
// lanes with rounded turns, and what Restore loads. The panel's mount cases
// are `historyPanel.test.ts` (a separate name: macOS folds case, so
// `History.test.ts` and `history.test.ts` are one file there).
import { describe, expect, it } from "vitest";
import type { ParamRow } from "../lib/table";
import {
  edgePath, freeText, gofText, lanes, restoreCount, restorePlan, roundedPolyline, rwpText,
  stepName, whenText, type HistoryNode,
} from "./history";
import { layout } from "../lib/history";

function node(id: string, parents: string[]): HistoryNode {
  return {
    id, parents, children: [], label: "", created_utc: "2026-11-22T10:04:05+00:00",
    kind: parents.length ? "stage" : "root", name: parents.length ? `s_${id}` : "",
    action: {}, api_call: `ref.run_stage(${id})`, status: null, n_iterations: null,
    rwp: parents.length ? 0.1234 : null, gof: parents.length ? 1.5 : null,
    n_free: parents.length ? 7 : null, n_diagnostics: 0, diagnostics: [], tags: [],
    scores: {}, notes: {},
  };
}

/** The plan run, then run again from n0002: a fork. */
const BRANCHED: HistoryNode[] = [
  node("n0000", []), node("n0001", ["n0000"]), node("n0002", ["n0001"]),
  node("n0003", ["n0002"]), node("n0004", ["n0003"]), node("n0005", ["n0002"]),
  node("n0006", ["n0005"]),
];

describe("the table's words", () => {
  it("names the root Start and a stage by its name", () => {
    expect(stepName(BRANCHED[0])).toBe("Start");
    expect(stepName(BRANCHED[1])).toBe("s_n0001");
  });

  it("puts a dash where a node ran no fit", () => {
    expect(rwpText(null)).toBe("—");
    expect(gofText(undefined)).toBe("—");
    expect(freeText(null)).toBe("—");
    expect(rwpText(0.09293)).toBe("9.29 %");
    expect(gofText(1.456)).toBe("1.46");
    expect(freeText(0)).toBe("0");
  });

  it("gives the time of day in eight characters", () => {
    expect(whenText("2026-11-22T10:04:05+00:00")).toMatch(/^\d\d:\d\d:05$/);
    expect(whenText("not a time")).toBe("—");
  });
});

describe("the Graph view's lanes", () => {
  it("puts the fork in a second lane and the trunk in the first", () => {
    const drawn = lanes(BRANCHED);
    expect(drawn.dots.get("n0004")?.lane).toBe(0);
    expect(drawn.dots.get("n0005")?.lane).toBe(1);
    expect(drawn.dots.get("n0006")?.lane).toBe(1);
    expect(drawn.width).toBe(28);
    const ys = BRANCHED.map((n) => drawn.dots.get(n.id)!.y);
    expect(ys).toEqual([...ys].sort((a, b) => a - b));
  });

  it("turns into a new lane with a rounded corner, never a diagonal", () => {
    const { edges } = layout(BRANCHED);
    const fork = edges.find((e) => e.from === "n0002" && e.to === "n0005")!;
    const d = edgePath(fork);
    expect(d).toContain("Q");
    // every straight piece is horizontal or vertical: the only turns are the Qs
    let at = [NaN, NaN];
    for (const cmd of d.match(/[MLQ][^MLQ]*/g)!) {
      const n = cmd.slice(1).trim().split(/\s+/).map(Number);
      const end = n.slice(-2);
      if (cmd[0] === "L") expect(end[0] === at[0] || end[1] === at[1]).toBe(true);
      at = end;
    }
  });

  it("draws a straight edge as one straight line", () => {
    const { edges } = layout(BRANCHED);
    const trunk = edges.find((e) => e.from === "n0000" && e.to === "n0001")!;
    expect(edgePath(trunk)).not.toContain("Q");
  });

  it("rounds a corner no wider than half its shorter side", () => {
    expect(roundedPolyline([[0, 0], [4, 0], [4, 30]], 6)).toBe("M0 0 L2 0 Q4 0 4 2 L4 30");
  });
});

function row(path: string, extra: Partial<ParamRow> = {}): ParamRow {
  return {
    path, value: 0, vary: false, lo: -Infinity, hi: Infinity, tie: null, locked: false,
    held: false, esd: null, mode_fixed: false, needs_held_cell: false, refinable: true,
    held_because: "", help_key: null, ...extra,
  };
}

describe("Restore", () => {
  const rows = [
    row("phases.0.cell.a"),
    row("phases.0.cell.b", { tie: { terms: [["phases.0.cell.a", 1]], const: 0 } as any }),
    row("phases.0.scale"), row("phases.0.atoms.1.x"), row("phases.0.atoms.1.y"),
    row("phases.0.atoms.1.dof.0"), row("phases.0.cell.alpha", { locked: true }),
  ];

  it("loads values, positions by atom, and leaves out what follows", () => {
    const plan = restorePlan({
      "phases.0.cell.a": [9.37, 9.38], "phases.0.cell.b": [9.37, 9.38],
      "phases.0.scale": [1.5, 1.4], "phases.0.atoms.1.x": [0.25, 0.26],
      "phases.0.cell.alpha": [90, 90.1],
    }, rows);
    expect(plan.values).toEqual({ "phases.0.cell.a": "9.37", "phases.0.scale": "1.5" });
    expect(plan.positions).toEqual({ "phases.0.atoms.1": { x: "0.25" } });
    expect(plan.missing).toEqual([]);
    expect(restoreCount(plan)).toBe(3);
  });

  it("restores an absolute DOF and leaves out a site's relative one", () => {
    const plan = restorePlan({
      "phases.0.microstrain.dof.0": [12, 10], "phases.0.atoms.1.dof.0": [0.01, 0],
    }, [...rows, row("phases.0.microstrain.dof.0")]);
    expect(plan.values).toEqual({ "phases.0.microstrain.dof.0": "12" });
  });

  it("names the paths either side lacks: the model itself differs", () => {
    const plan = restorePlan({
      "phases.0.atoms.4.biso": [0.5, null], "phases.0.scale": [1.5, 1.4],
      "instrument.background.c9": [null, 2],
    }, rows);
    expect(plan.missing).toEqual(["instrument.background.c9", "phases.0.atoms.4.biso"]);
  });
});
