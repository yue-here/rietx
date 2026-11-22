// @vitest-environment jsdom
// The Text tab at /next (WP-2231): the file's name and its sync word on the
// title line, a typed change reported as one pending edit with no Apply of its
// own, the bar's Apply sending it as one delta, and Re-read only inside the
// stale notice. Typing and applying from the bar in a real browser is
// `tests/test_gui_layout_browser.py`'s.
import { flushSync, mount, tick, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

const DOC = "rxt 1\nproject \"fap\"\n";
let revision = "r1";
const putTextdoc = vi.fn(async (text: string, _rev: string, validateOnly: boolean) =>
  validateOnly ? { would_change: true }
    : { text, revision: "r2", applied: ["ref.set_values({...})"] });
const textdoc = vi.fn(async () => ({ text: DOC, revision }));

vi.mock("../api", () => ({
  ApiError: class extends Error { code = ""; empty = false; details: unknown[] = []; },
  api: {
    textdoc: () => textdoc(),
    putTextdoc: (t: string, r: string, v: boolean) => putTextdoc(t, r, v),
  },
}));

let typed: ((text: string) => void) | null = null;
let applied: (() => void) | null = null;
let marked: number[] = [];
vi.mock("../lib/editor", () => ({
  createEditor: (options: any) => {
    typed = options.onChange;
    applied = options.onApply;
    return { setDoc() {}, setProblems() {}, setTheme() {}, refresh() {}, destroy() {},
             goToLine() {}, setEdited(lines: number[]) { marked = lines; } };
  },
}));

import { ApiError } from "../api";
import Text from "./Text.svelte";

let app: any = null;

async function settle() {
  for (let i = 0; i < 24; i++) await tick();
  flushSync();
}

const text = (el: Element | null) => (el?.textContent ?? "").replace(/\s+/g, " ").trim();

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  putTextdoc.mockClear();
  textdoc.mockClear();
  revision = "r1";
  typed = null;
  applied = null;
  marked = [];
});

describe("the Text tab", () => {
  it("names the file and its sync word, and has no Apply of its own", async () => {
    app = mount(Text, { target: document.body, props: { active: true, name: "fap" } });
    await settle();
    expect(text(document.querySelector(".bar .file"))).toBe("fap.rxt");
    expect(text(document.querySelector(".bar .sync"))).toBe("in sync");
    expect([...document.querySelectorAll("button")].map((b) => text(b))).toEqual([]);
  });

  it("reports a typed change as pending, and the bar's Apply sends it as one delta", async () => {
    const pending = vi.fn();
    const onapply = vi.fn();
    app = mount(Text, { target: document.body,
                        props: { active: true, name: "fap", onpending: pending, onapply } });
    await settle();
    expect(pending).toHaveBeenLastCalledWith(false, "");
    typed!(DOC + "limits none\n");
    await settle();
    expect(pending).toHaveBeenLastCalledWith(true, "");
    expect(text(document.querySelector(".bar .sync"))).toBe("edited");
    expect(marked).toEqual([3]);
    expect(app.draft()).toEqual({ buffer: DOC + "limits none\n", revision: "r1" });
    applied!();
    expect(onapply).toHaveBeenCalledTimes(1);
    expect(await app.apply()).toBe(true);
    await settle();
    const sent = putTextdoc.mock.calls.filter((c) => c[2] === false);
    expect(sent).toEqual([[DOC + "limits none\n", "r1", false]]);
    expect(pending).toHaveBeenLastCalledWith(false, "");
    expect(text(document.querySelector(".bar .sync"))).toBe("in sync");
  });

  it("offers Re-read only inside the stale notice", async () => {
    app = mount(Text, { target: document.body, props: { active: true, name: "fap" } });
    await settle();
    typed!(DOC + "# mine\n");
    await settle();
    expect(text(document.body)).toContain("1 comment line you added will not survive Apply.");
    // the project moves underneath the buffer
    revision = "r9";
    textdoc.mockResolvedValueOnce({ text: DOC + "mode lebail\n", revision: "r9" });
    await app.restoreDraft({ buffer: DOC + "# mine\n", revision: "r1" });
    await settle();
    expect(text(document.querySelector(".bar .sync"))).toBe("stale");
    const reread = [...document.querySelectorAll(".notice button")];
    expect(reread.map((b) => text(b))).toEqual(["Re-read"]);
    // an action, so a Button and never a Link (the maintainer's look, 2026-11-21)
    expect(reread[0].classList.contains("ghost")).toBe(true);
    expect(reread[0].classList.contains("link")).toBe(false);
    expect(text(document.querySelector(".notice.stale p")))
      .toContain("make your edit again");
    (reread[0] as HTMLButtonElement).click();
    await settle();
    expect(document.querySelector(".notice button")).toBeNull();
    expect(text(document.querySelector(".bar .sync"))).toBe("in sync");
  });

  it("applies a buffer that changes nothing by reading the rendering again", async () => {
    const pending = vi.fn();
    app = mount(Text, { target: document.body, props: { active: true, name: "fap", onpending: pending } });
    await settle();
    putTextdoc.mockResolvedValueOnce({ would_change: false } as any);
    typed!(DOC + "# a note\n");
    await new Promise((r) => setTimeout(r, 350));
    await settle();
    expect(text(document.querySelector(".bar .sync"))).toBe("no change");
    const reads = textdoc.mock.calls.length;
    expect(await app.apply()).toBe(true);
    await settle();
    expect(putTextdoc.mock.calls.filter((c) => c[2] === false)).toEqual([]);
    expect(textdoc.mock.calls.length).toBe(reads + 1);
    expect(pending).toHaveBeenLastCalledWith(false, "");
  });

  it("names an unreadable buffer's problems, and the bar's Apply is refused", async () => {
    const pending = vi.fn();
    app = mount(Text, { target: document.body, props: { active: true, name: "fap", onpending: pending } });
    await settle();
    const refusal = Object.assign(new (ApiError as any)("1 line not read"), {
      code: "TEXTDOC_INVALID",
      details: [{ line: 3, message: "unknown key", where: "limits" }],
    });
    putTextdoc.mockRejectedValueOnce(refusal);
    typed!(DOC + "limits sideways\n");
    await new Promise((r) => setTimeout(r, 350));
    await settle();
    expect(text(document.querySelector(".bar .sync"))).toBe("1 line not read");
    expect(text(document.querySelector("[aria-label=Problems]"))).toBe("line 3 limits unknown key");
    expect(pending).toHaveBeenLastCalledWith(true, "The text has 1 problem.");
    expect(await app.apply()).toBe(false);
  });

  it("says the server's words when a refusal names no line, never \"0 problems\"", async () => {
    const pending = vi.fn();
    app = mount(Text, { target: document.body, props: { active: true, name: "fap", onpending: pending } });
    await settle();
    putTextdoc.mockRejectedValueOnce(Object.assign(new (ApiError as any)("the document is not rxt 1"),
                                                   { code: "TEXTDOC_INVALID", details: [] }));
    typed!("rxt 2\n");
    await new Promise((r) => setTimeout(r, 350));
    await settle();
    expect(text(document.querySelector(".bar .sync"))).toBe("not read");
    const why = pending.mock.calls.at(-1)![1];
    expect(why).not.toMatch(/0 problems/);
    expect(why.length).toBeGreaterThan(0);
  });

  it("drops a read begun for the project it was told to forget", async () => {
    app = mount(Text, { target: document.body, props: { active: true, name: "fap" } });
    await settle();
    let late: (v: unknown) => void = () => {};
    textdoc.mockImplementationOnce(() => new Promise((r) => { late = r; }) as any);
    const reading = app.revert();
    app.forget();
    late({ text: "rxt 1\nproject \"other\"\n", revision: "rX" });
    await reading;
    await settle();
    expect(app.draft()).toBeNull();
    expect(text(document.querySelector(".bar .sync"))).toBe("loading…");
  });
});
