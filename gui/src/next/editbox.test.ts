// @vitest-environment jsdom
// A clicked value at /next opens on its full stored value, and Enter on the
// text as it opened records no edit (WP-2223, the spreadsheet model Yue's
// "go with best practice" of 2026-11-19 chose). The Interactive slider's box
// and the Parameters panel's editor follow one rule. What a person sees after
// a real click is a real browser's question (`tests/test_gui_browser.py`).
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Caglioti W with 14 significant figures: a 12-digit editor reads it back different
const W = 0.0011090354888959;
const row = (path: string, value: number) => ({
  path, value, esd: null, lo: 0, hi: 1, vary: false, refinable: true, locked: false,
  tie: null, held: false, held_because: "", help_key: "", mode_fixed: false,
});
const ROWS = [row("instrument.profile.w", W)];
const preview = vi.fn(async (_values: unknown) => ({ header: {}, arrays: {} }));

vi.mock("../api", () => ({
  ApiError: class extends Error { code = ""; empty = false; busy = false; },
  api: {
    params: async () => ({ parameters: ROWS, n_free: 0 }),
    patchParams: async () => ({ parameters: ROWS, n_free: 0 }),
    preview: (values: unknown) => preview(values),
    structure: async () => ({ structure: { phases: [] }, sites: [], symmetry: [] }),
    symmetry: async () => ({ letters: [] }),
  },
}));

import Interactive from "./Interactive.svelte";
import Params from "./Params.svelte";

let app: ReturnType<typeof mount> | null = null;

async function settle() {
  for (let i = 0; i < 24; i++) await tick();
  await new Promise((r) => requestAnimationFrame(() => r(null)));
  for (let i = 0; i < 4; i++) await tick();
  flushSync();
}

async function key(input: HTMLInputElement, name: string, text?: string) {
  if (text !== undefined) {
    input.value = text;
    input.dispatchEvent(new Event("input", { bubbles: true }));
    flushSync();
  }
  input.dispatchEvent(new KeyboardEvent("keydown", { key: name, bubbles: true }));
  await settle();
}

beforeEach(() => preview.mockClear());

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

describe("the Interactive tab's value box (WP-2223)", () => {
  const pending: number[] = [];
  async function open() {
    pending.length = 0;
    app = mount(Interactive, { target: document.body, props: {
      head: "n1", context: { fwhm: 0.1, thetaMaxDeg: 60 },
      onpending: (n: number) => pending.push(n) } });
    await settle();
  }
  const box = () => document.querySelector<HTMLButtonElement>("button.num")!;
  const typed = () => document.querySelector<HTMLInputElement>("input.typed")!;

  it("opens on the stored value to its last digit, and Enter on it is no edit", async () => {
    await open();
    // drawn in the box's own digits
    expect(box().textContent).not.toContain("0.0011090354888959");
    box().click();
    await settle();
    expect(typed().value).toBe("0.0011090354888959");
    await key(typed(), "Enter");
    expect(typed()).toBeNull();
    expect(preview).not.toHaveBeenCalled();
    expect(pending.at(-1) ?? 0).toBe(0);
  });

  it("reads ×10ⁿ as the range fields do, and Escape keeps nothing", async () => {
    await open();
    box().click();
    await settle();
    await key(typed(), "Escape", "9");
    expect(preview).not.toHaveBeenCalled();
    box().click();
    await settle();
    await key(typed(), "Enter", "1.5×10⁻³");
    expect(pending.at(-1)).toBe(1);
    expect(preview).toHaveBeenCalled();
    expect(JSON.stringify(preview.mock.calls.at(-1))).toContain("0.0015");
  });

  it("takes a range end typed back to the text it opened on", async () => {
    await open();
    const thumb = () => document.querySelector<HTMLInputElement>('input[type="range"]')!.value;
    const from = () => document.querySelector<HTMLInputElement>('input[aria-label="Lowest value"]')!;
    const before = thumb();
    document.querySelector<HTMLButtonElement>("button.pname")!.click();
    await settle();
    const shown = from().value;
    await key(from(), "Enter", "0.0001");
    expect(thumb()).not.toBe(before);
    // the old text is now a change back, never "the end as shown"
    await key(from(), "Enter", shown);
    expect(thumb()).toBe(before);
  });
});

describe("the Parameters panel's editor (WP-2223)", () => {
  const pending: number[] = [];
  async function open() {
    pending.length = 0;
    app = mount(Params, { target: document.body, props: {
      head: "n1", onmoved: () => {}, onpending: (n: number) => pending.push(n) } });
    await settle();
  }
  const cell = () => document.querySelector<HTMLElement>('.ink[data-path="instrument.profile.w"]')!;
  const editor = () => document.querySelector<HTMLInputElement>("input.editor")!;

  it("opens on the stored value to its last digit, and Enter on it is no edit", async () => {
    await open();
    expect(cell().textContent).not.toContain("0.0011090354888959");
    cell().click();
    await settle();
    expect(editor().value).toBe("0.0011090354888959");
    await key(editor(), "Enter");
    expect(editor()).toBeNull();
    expect(pending.at(-1) ?? 0).toBe(0);
  });

  it("takes the drawn digits typed in as a new number, and the stored one back as none", async () => {
    await open();
    cell().click();
    await settle();
    await key(editor(), "Enter", "0.001109");
    expect(pending.at(-1)).toBe(1);
    cell().click();
    await settle();
    // a pending edit opens on its own text
    expect(editor().value).toBe("0.001109");
    await key(editor(), "Enter", "0.0011090354888959");
    expect(pending.at(-1)).toBe(0);
  });
});
