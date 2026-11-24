// @vitest-environment jsdom
// The History tab at /next (WP-2211): a branched tree's rows, oldest first, in
// the Graph view by default and the Table view on request; Compare hands the
// node's replayed curve up; Restore hands its values up as pending edits, and a
// node with another model is refused with Make current offered; the node's
// menu speaks the ruled words. That no click moves the layout is a real
// browser's question (`tests/test_gui_layout_browser.py`).
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("./rxplot.mjs", () => ({
  unpack: () => ({ header: { node: "n0002" },
                   arrays: { two_theta: new Float64Array([10, 11]), y_calc: new Float64Array([5, 6]) } }),
}));

const NODES = [
  ["n0000", []], ["n0001", ["n0000"]], ["n0002", ["n0001"]], ["n0003", ["n0002"]],
  ["n0004", ["n0002"]],
].map(([id, parents]) => ({
  id, parents, children: [], label: "", created_utc: "2026-11-22T10:04:05+00:00",
  kind: parents.length ? "stage" : "root", name: parents.length ? `stage_${id}` : "", action: {},
  api_call: `ref.run_stage("${id}")`, status: null, n_iterations: null,
  rwp: parents.length ? 0.1 : null, gof: parents.length ? 1.25 : null, n_free: parents.length ? 4 : null,
  n_diagnostics: 0, diagnostics: [], tags: id === "n0003" ? ["first try"] : [], scores: {}, notes: {},
}));
const diff = vi.fn(async (a: string, _b: string) => (a === "n0001"
  ? { diff: { "phases.0.atoms.3.biso": [0.5, null], "phases.0.scale": [2, 1] } }
  : { diff: { "phases.0.scale": [2, 1], "phases.0.cell.a": [9.37, 9.38] } }));
const checkout = vi.fn(async (_id: string) => ({}));

vi.mock("../api", () => ({
  ApiError: class extends Error {},
  api: {
    history: async () => ({ head: "n0004", n_nodes: NODES.length, nodes: NODES }),
    historyDiff: (a: string, b: string) => diff(a, b),
    historyCurves: async () => new ArrayBuffer(0),
    params: async () => ({ parameters: [
      { path: "phases.0.scale", value: 1, vary: true, lo: 0, hi: "Infinity", tie: null, locked: false },
      { path: "phases.0.cell.a", value: 9.38, vary: true, lo: 0, hi: "Infinity", tie: null, locked: false },
    ], n_free: 2 }),
    checkout: (id: string) => checkout(id),
  },
}));

import History from "./History.svelte";

let app: any = null;

async function settle() {
  for (let i = 0; i < 24; i++) await tick();
  flushSync();
}

const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

function open(props: Record<string, unknown> = {}) {
  const calls = { count: 0, compared: undefined as any, restored: null as any, moved: 0, said: [] as string[] };
  app = mount(History, { target: document.body, props: {
    head: "n0004", say: (_kind: string, l: string) => calls.said.push(l),
    oncount: (n: number) => (calls.count = n),
    oncompare: (c: any) => (calls.compared = c),
    onrestore: (p: any) => (calls.restored = p),
    onmoved: () => (calls.moved += 1),
    ...props,
  } });
  return calls;
}

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  diff.mockClear();
  checkout.mockClear();
});

describe("the History tab", () => {
  it("draws the graph by default, oldest first, the fork in a second lane", async () => {
    const calls = open();
    await settle();
    expect(calls.count).toBe(5);
    const rows = [...document.querySelectorAll(".grow")];
    expect(rows.map((r) => r.getAttribute("data-node"))).toEqual(
      ["n0000", "n0001", "n0002", "n0003", "n0004"]);
    expect(text(rows[0])).toContain("Start");
    expect(text(rows[3])).toContain("first try");
    expect(rows[4].classList.contains("cur")).toBe(true);
    expect(text(rows[4])).toContain("current");
    // the root offers neither verb; the head cannot be restored onto itself
    expect(rows[0].querySelectorAll("button").length).toBe(0);
    const restoreHead = [...rows[4].querySelectorAll("button")].find((b) => b.textContent === "Restore")!;
    expect(restoreHead.disabled).toBe(true);
    // a fork: two edges leave n0002, one of them with a rounded turn
    expect([...document.querySelectorAll(".rails path")].some((p) => p.getAttribute("d")!.includes("Q"))).toBe(true);
  });

  it("lists the numbers in the table view, the api call as each row's tooltip", async () => {
    open({ view: "table" });
    await settle();
    const head = [...document.querySelectorAll("th")].map((th) => text(th));
    expect(head.slice(0, 6)).toEqual(["Node", "Step", "Rwp", "GoF", "Free", "When"]);
    const rows = [...document.querySelectorAll("tbody tr")];
    expect(rows.length).toBe(5);
    expect(text(rows[0].querySelectorAll("td")[2])).toBe("—");
    expect(text(rows[1].querySelectorAll("td")[2])).toBe("10.00 %");
    expect(text(rows[1].querySelectorAll("td")[3])).toBe("1.25");
    expect(text(rows[1].querySelectorAll("td")[4])).toBe("4");
    expect(rows[1].getAttribute("title")).toBe('ref.run_stage("n0001")');
  });

  it("hands a node's curve up on Compare, drawn by the page", async () => {
    const calls = open();
    await settle();
    const row = document.querySelector('[data-node="n0002"]')!;
    const compare = [...row.querySelectorAll("button")].find((b) => b.textContent === "Compare")!;
    compare.click();
    await settle();
    expect(calls.compared.id).toBe("n0002");
    expect(calls.compared.label).toBe("stage_n0002");
    expect([...calls.compared.y]).toEqual([5, 6]);
    expect(calls.said).toEqual([]);
  });

  it("clears the compared node on a second press", async () => {
    const calls = open({ compared: "n0002" });
    await settle();
    const row = document.querySelector('[data-node="n0002"]')!;
    const compare = [...row.querySelectorAll("button")].find((b) => b.textContent === "Compare")!;
    expect(compare.getAttribute("aria-pressed")).toBe("true");
    expect(row.classList.contains("cmp")).toBe(true);
    compare.click();
    await settle();
    expect(calls.compared).toBeNull();
  });

  it("loads a node's values as pending edits on Restore", async () => {
    const calls = open();
    await settle();
    const row = document.querySelector('[data-node="n0002"]')!;
    [...row.querySelectorAll("button")].find((b) => b.textContent === "Restore")!.click();
    await settle();
    expect(diff).toHaveBeenCalledWith("n0002", "n0004");
    expect(calls.restored.values).toEqual({ "phases.0.scale": "2", "phases.0.cell.a": "9.37" });
    expect(calls.said[0]).toMatch(/^# n0002's values loaded as 2 pending edits/);
  });

  it("refuses a node with another model and offers Make current", async () => {
    const calls = open();
    await settle();
    const row = document.querySelector('[data-node="n0001"]')!;
    [...row.querySelectorAll("button")].find((b) => b.textContent === "Restore")!.click();
    await settle();
    expect(calls.restored).toBeNull();
    const note = document.querySelector(".hnote")!;
    expect(text(note)).toContain("phases.0.atoms.3.biso");
    [...note.querySelectorAll("button")].find((b) => b.textContent === "Make current")!.click();
    await settle();
    expect(checkout).toHaveBeenCalledWith("n0001");
    expect(calls.said).toContain('ref.checkout("n0001")');
    expect(calls.moved).toBe(1);
  });

  it("opens the node's menu on right-click, in plain words", async () => {
    open();
    await settle();
    const row = document.querySelector('[data-node="n0002"]')!;
    row.dispatchEvent(new MouseEvent("contextmenu", { bubbles: true, cancelable: true, clientX: 40, clientY: 40 }));
    await settle();
    const items = [...document.querySelectorAll('[role="menu"] [role^="menuitem"]')].map((el) => text(el));
    expect(items).toEqual(["Make current", "Branch from here…", "Name…", "Note…"]);
    const first = document.querySelector('[role="menu"] [role^="menuitem"]')!;
    expect(first.getAttribute("title")).toContain('ref.checkout("n0002")');
  });
});
