// @vitest-environment jsdom
// A tab strip's `?` box at /next (WP-2231, the maintainer's look of
// 2026-11-21, item 6): one button opens the box for the tab that is up, with
// a link into the manual, and Esc or Close shuts it.
import { readFileSync } from "node:fs";
import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";
import HelpBox from "./HelpBox.svelte";
import { GRAPH_HELP, HISTORY_HELP, MODEL_HELP } from "./helpbox";
import { GRAPH_TABS, MODEL_TABS } from "./tabs";

let app: Record<string, any> | null = null;

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

describe("the ? box", () => {
  it("has words for every model tab", () => {
    expect(Object.keys(MODEL_HELP).sort()).toEqual(MODEL_TABS.map((t) => t.id).sort());
    for (const t of MODEL_TABS) expect(MODEL_HELP[t.id].title).toBe(t.label);
  });

  it("has words for every graph tab", () => {
    expect(Object.keys(GRAPH_HELP).sort()).toEqual(GRAPH_TABS.map((t) => t.id).sort());
    for (const t of GRAPH_TABS) expect(GRAPH_HELP[t.id].title).toBe(t.label);
  });

  it("links only to sections the manual's GUI chapter has", () => {
    // `help.py`'s anchors are checked against the built manual; these live in
    // TypeScript, so a renamed heading would otherwise leave a dead link
    // a jsdom test's module URL is vite's `/@fs/…`, so drop that prefix
    const guide = readFileSync(decodeURIComponent(
      new URL("../../../docs/docs/reference/gui-guide.md", import.meta.url).pathname)
      .replace(/^\/@fs/, ""), "utf-8");
    const ids = new Set([...guide.matchAll(/^#{1,6} (.+)$/gm)].map(([, h]) =>
      h.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "")));
    for (const entry of [...Object.values(MODEL_HELP), ...Object.values(GRAPH_HELP), HISTORY_HELP]) {
      expect(ids, entry.anchor).toContain(entry.anchor);
    }
  });

  it("opens the tab's box, links the manual's section, and closes on Esc and on Close", () => {
    app = mount(HelpBox, { target: document.body, props: {
      entry: MODEL_HELP.text, label: "About the Text tab", docsUrl: "https://rietx.org/docs/" } });
    const button = document.querySelector<HTMLButtonElement>("button.help")!;
    expect(button.getAttribute("aria-label")).toBe("About the Text tab");
    expect(document.querySelector("[role=dialog]")).toBeNull();
    button.click();
    flushSync();
    const box = document.querySelector("[role=dialog]")!;
    expect(box.getAttribute("aria-label")).toBe("Text");
    expect(document.activeElement).toBe(box);
    expect(box.textContent).toContain("becomes a pending edit");
    expect(box.querySelector("a")!.getAttribute("href"))
      .toBe("https://rietx.org/docs/reference/gui-guide.html#text");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
    flushSync();
    expect(document.querySelector("[role=dialog]")).toBeNull();
    button.click();
    flushSync();
    [...document.querySelectorAll<HTMLButtonElement>("[role=dialog] button")]
      .find((b) => b.textContent === "Close")!.click();
    flushSync();
    expect(document.querySelector("[role=dialog]")).toBeNull();
  });
});
