// @vitest-environment jsdom
// The Console at /next draws by kind (WP-2212): a prompt in the gutter for
// each call, the events of a run folded under its call and closed by default,
// and Copy taking the calls alone.
import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";
import { eventLine, makeLine, type Line } from "./console";
import Console from "./Console.svelte";

let app: ReturnType<typeof mount> | null = null;

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

const LINES: Line[] = [
  { ...makeLine("call", 'ref.hold("instrument.zero_shift")', undefined, 100), entry: 1 },
  { ...makeLine("call", "ref.set_values({\"a\": 1})", undefined, 100), entry: 1 },
  { ...makeLine("call", "p.fit()", undefined, 101), entry: 2, run: true },
  eventLine({ seq: 1, kind: "stage_start", t: 102, data: { stage: "scale" } } as any),
  eventLine({ seq: 2, kind: "eval", t: 102, data: { stage: "scale", n_eval: 3 } } as any),
  { ...makeLine("comment", "# view kept", undefined, 103), entry: 3 },
];

describe("the Console", () => {
  it("draws each call behind its prompt, its strings in their own span", () => {
    app = mount(Console, { target: document.body, props: { lines: LINES, dropped: 0 } });
    const calls = [...document.querySelectorAll('.ln[data-kind="call"]')];
    expect(calls.map((l) => l.querySelector(".pr")?.textContent?.trim())).toEqual([">>>", "...", ">>>"]);
    expect(calls[0].querySelector(".str")?.textContent).toBe('"instrument.zero_shift"');
    expect(document.querySelectorAll(".entry .t")).toHaveLength(3);
  });

  it("folds a run's events under its call, and a click lists them", () => {
    app = mount(Console, { target: document.body, props: { lines: LINES, dropped: 0 } });
    const fold = document.querySelector<HTMLButtonElement>("button.fold")!;
    expect(fold.textContent).toContain("2 engine events, 1 stage, 3 evaluations");
    expect(fold.getAttribute("aria-expanded")).toBe("false");
    expect(document.querySelectorAll(".ln.event")).toHaveLength(0);
    // the fold sits in the run's entry, above the comment written after it
    expect(fold.closest(".entry")?.textContent).toContain("p.fit()");
    fold.click();
    flushSync();
    expect(document.querySelectorAll(".ln.event")).toHaveLength(2);
  });

  it("copies the calls alone, without prompts or output", async () => {
    const writeText = vi.fn(async () => {});
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    app = mount(Console, { target: document.body, props: { lines: LINES, dropped: 0 } });
    const copy = [...document.querySelectorAll("button")].find((b) => b.textContent?.includes("Copy"))!;
    copy.click();
    await Promise.resolve();
    expect(writeText).toHaveBeenCalledWith(
      'ref.hold("instrument.zero_shift")\nref.set_values({"a": 1})\np.fit()\n');
  });
});
