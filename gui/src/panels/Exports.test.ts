// @vitest-environment jsdom
// The export row (WP-1461, D6). The work is the chart module's, driven in a
// real browser by tests/test_rxplot_browser.py; what is left here is what the
// row does with it: which verb a button calls, what it names the file, and
// that a refusal is said rather than thrown.
import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import Exports from "./Exports.svelte";

let app: ReturnType<typeof mount> | null = null;

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
  vi.restoreAllMocks();
});

function row(figure: () => any, name = "pattern") {
  app = mount(Exports, { target: document.body, props: { figure, name: () => name } });
  flushSync();
}

function press(label: string) {
  const button = [...document.querySelectorAll("button")].find((b) => b.textContent === label);
  if (!button) throw new Error(`no ${label} button`);
  button.click();
}

const said = () => document.querySelector(".said")?.textContent ?? "";

/** Wait for the row to say `text`: a verb awaits the module, the clipboard or both. */
const saying = (text: string) => vi.waitFor(() => { flushSync(); expect(said()).toBe(text); });

describe("the export row", () => {
  it("copies the figure's table, and says how many rows", async () => {
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    row(() => ({ tsv: () => "two_theta\ty_obs\n1\t2\n3\t4" }));
    press("copy data");
    await saying("copied 2 rows");
    expect(writeText).toHaveBeenCalledWith("two_theta\ty_obs\n1\t2\n3\t4");
  });

  it("names the file and saves the figure's PNG", async () => {
    const blob = new Blob(["png"], { type: "image/png" });
    const clicked: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
      clicked.push(this.download);
    });
    URL.createObjectURL = vi.fn(() => "blob:x");
    URL.revokeObjectURL = vi.fn();
    row(() => ({ png: async () => blob }), "trajectory-phases.0.cell.a");
    press("PNG");
    await saying("saved a PNG");
    expect(clicked).toEqual(["trajectory-phases.0.cell.a.png"]);
  });

  it("says so when nothing is drawn, and when the clipboard refuses", async () => {
    row(() => null);
    press("copy image");
    flushSync();
    expect(said()).toBe("nothing is drawn yet");
    unmount(app!);
    row(() => ({ copyImage: async () => { throw new Error("Document is not focused."); } }));
    press("copy image");
    await saying("copy image failed: Document is not focused.");
  });
});
