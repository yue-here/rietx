// @vitest-environment jsdom
// The popover's summary form (WP-2240): a key with a title shows the title
// alone and keeps the entry's manual link. The candidate table's relation
// marks open it (the maintainer, 2026-11-23: "just a summary of what it
// means", with "a manual link").
import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it } from "vitest";

import HelpPopover, { HelpHost } from "./HelpPopover.svelte";
import type { HelpCorpus } from "./lib/help";

const corpus = {
  docs_url: "https://rietx.org/docs/dev",
  cell_relations: {
    sublattice: { title: "Supercell of another candidate", description: "Written N× #k.",
                  unit: null, default: null, typical: null, label: null,
                  anchor: "reference/indexing-evidence.html#relations-between-candidates" },
  },
} as unknown as HelpCorpus;

let app: ReturnType<typeof mount> | null = null;
afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

function open(request: { key: string | null; text: string | null; title: string | null }) {
  const host = new HelpHost();
  app = mount(HelpPopover, { target: document.body, props: { host, corpus } });
  const term = document.createElement("span");
  document.body.append(term);
  host.toggle(term, request);
  flushSync();
  return document.querySelector<HTMLElement>(".popover")!;
}

describe("the help popover's summary form", () => {
  it("shows the row's summary alone, then the entry's manual link", () => {
    const shown = open({ key: "cell_relations:sublattice", text: null,
                         title: "Supercell of #1, twice its primitive cell" });
    expect(shown.querySelector("h2")!.textContent).toBe("Supercell of #1, twice its primitive cell");
    expect(shown.querySelector("p")).toBeNull();
    expect(shown.querySelector<HTMLAnchorElement>("a.link")!.href).toBe(
      "https://rietx.org/docs/dev/reference/indexing-evidence.html#relations-between-candidates");
  });

  it("shows the entry's own words for a key alone", () => {
    const shown = open({ key: "cell_relations:sublattice", text: null, title: null });
    expect(shown.querySelector("h2")!.textContent).toBe("Supercell of another candidate");
    expect(shown.querySelector("p")!.textContent).toBe("Written N× #k.");
  });
});
