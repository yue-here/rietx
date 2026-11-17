/** The panel strip, written out for the manual to be held to (WP-1017).
 *
 * The `fnmatch`/`controls` mechanism with the authorities swapped. There,
 * python owns the vocabulary and TypeScript replays a committed corpus to
 * prove the form states it. Here the tab strip is the *app's* — no python
 * object knows the panels exist — so this side writes the corpus and
 * `tests/test_gui_manual.py` reads it, failing when a GUI chapter does not
 * name a tab.
 *
 * Writing rather than asserting is deliberate: a renamed panel should update
 * the corpus and fail the *manual*, which is the file that is now wrong. A
 * committed corpus also keeps the python suite node-free, the same property
 * `test_gui_dist.py` protects for the built dist.
 */
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { GRAPH_TABS, TABS } from "./tabs";

const CORPUS = resolve(__dirname, "../../../tests/data/gui/panels.json");

describe("the panel corpus", () => {
  it("writes the live tab strip for the python suite", () => {
    const payload = {
      _comment:
        "Written by gui/src/lib/tabs.test.ts from lib/tabs.ts. Do not edit: " +
        "edit the strip. Read by tests/test_gui_manual.py, which fails when a " +
        "GUI chapter of the manual does not name a tab.",
      tabs: TABS.map((tab) => ({ id: tab.id, label: tab.label })),
      graph_tabs: GRAPH_TABS.map((tab) => ({ id: tab.id, label: tab.label })),
    };
    mkdirSync(dirname(CORPUS), { recursive: true });
    writeFileSync(CORPUS, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

    const back = JSON.parse(readFileSync(CORPUS, "utf8"));
    expect(back.tabs).toHaveLength(TABS.length);
    expect(back.tabs.map((t: { label: string }) => t.label)).toEqual(
      TABS.map((t) => t.label),
    );
  });

  it("has an id and a label on every tab, and no duplicates", () => {
    // The corpus is keyed by label in the manual, so two tabs sharing one would
    // make a chapter that names it cover both by accident.
    const labels = TABS.map((t) => t.label);
    const ids = TABS.map((t) => t.id);
    expect(new Set(labels).size).toBe(labels.length);
    expect(new Set(ids).size).toBe(ids.length);
    for (const tab of TABS) {
      expect(tab.label.length).toBeGreaterThan(0);
      expect(tab.id.length).toBeGreaterThan(0);
    }
  });
});
