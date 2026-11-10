// @vitest-environment jsdom
// The workflow menu (WP-2204): which workflow the window is in, read off the
// model panel's tab, and the menu and placeholder pane drawn from it.
import { flushSync, mount, unmount } from "svelte";
import { afterEach, describe, expect, it, vi } from "vitest";

import Workflow from "../panels/Workflow.svelte";
import WorkflowMenu from "../panels/WorkflowMenu.svelte";
import { TABS } from "./tabs";
import { WORKFLOWS, isPlaceholder, shownFor, workflowOf } from "./workflows";

let app: ReturnType<typeof mount> | null = null;

afterEach(() => {
  if (app) unmount(app);
  app = null;
  document.body.innerHTML = "";
});

describe("which workflow the window is in", () => {
  it("lists the five workflows of the design round, in its order", () => {
    expect(WORKFLOWS.map((w) => w.name)).toEqual(
      ["Refinement", "Peaks and indexing", "Series", "Structure solution", "Rigid bodies"]);
  });

  it("is built where a home tab exists, and a placeholder exactly where none does", () => {
    const tabs = new Set<string>(TABS.map((t) => t.id));
    for (const w of WORKFLOWS) {
      if (w.tab) expect(tabs.has(w.tab), w.id).toBe(true);
      expect(isPlaceholder(w.id), w.id).toBe(!!w.steps);
      expect(!!w.tab && !!w.steps, w.id).toBe(false);
    }
    expect(WORKFLOWS.filter((w) => isPlaceholder(w.id)).map((w) => w.id)).toEqual(["solve", "rigid"]);
  });

  it("is read off the tab, so any opener that sets one leaves a placeholder", () => {
    expect(workflowOf("peaks")).toBe("index");
    expect(workflowOf("series")).toBe("series");
    expect(workflowOf("solve")).toBe("solve");
    for (const t of ["params", "interactive", "plan", "model", "text", "report", "history", "build"] as const)
      expect(workflowOf(t), t).toBe("refine");
  });

  it("returns Refinement to the last tab that was its own", () => {
    expect(shownFor("refine", "plan")).toBe("plan");
    expect(shownFor("index", "plan")).toBe("peaks");
    expect(shownFor("series", "plan")).toBe("series");
    expect(shownFor("rigid", "plan")).toBe("rigid");
  });
});

describe("the menu", () => {
  function menu(current: any, onchoose = vi.fn()) {
    app = mount(WorkflowMenu, { target: document.body, props: { current, onchoose } });
    flushSync();
    return onchoose;
  }
  const trigger = () => document.querySelector<HTMLButtonElement>(".wf-name")!;
  const items = () => [...document.querySelectorAll<HTMLButtonElement>('[role="menuitemradio"]')];

  it("names the current workflow, and a placeholder says that it is one", () => {
    menu("refine");
    expect(trigger().textContent).toBe("Refinement▾");
    unmount(app!);
    menu("solve");
    expect(trigger().textContent).toBe("Structure solution · placeholder▾");
  });

  it("opens with no heading, a check on the current entry, and the two placeholders marked", () => {
    menu("index");
    trigger().click();
    flushSync();
    expect(document.querySelector('[role="menu"] h2, [role="menu"] h3')).toBeNull();
    expect(items().map((b) => b.textContent!.replace(/\s+/g, " ").trim())).toEqual([
      "Refinement", "✓ Peaks and indexing", "Series",
      "Structure solution · placeholder", "Rigid bodies · placeholder"]);
    expect(items().map((b) => b.getAttribute("aria-checked")))
      .toEqual(["false", "true", "false", "false", "false"]);
  });

  it("hands the choice on and closes; the current entry hands on nothing", () => {
    const onchoose = menu("refine");
    trigger().click();
    flushSync();
    items()[4].click();
    flushSync();
    expect(onchoose).toHaveBeenCalledWith("rigid");
    expect(document.querySelector('[role="menu"]')).toBeNull();
    trigger().click();
    flushSync();
    items()[0].click();
    flushSync();
    expect(onchoose).toHaveBeenCalledTimes(1);
  });

  it("closes on Escape before the shell sees it, so a running fit is not cancelled", () => {
    menu("refine");
    const shell = vi.fn();
    window.addEventListener("keydown", shell);
    trigger().click();
    flushSync();
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    flushSync();
    window.removeEventListener("keydown", shell);
    expect(document.querySelector('[role="menu"]')).toBeNull();
    expect(shell).not.toHaveBeenCalled();
  });

  it("is drawn and disabled without a project", () => {
    app = mount(WorkflowMenu, { target: document.body, props: { disabled: true } });
    flushSync();
    expect(trigger().disabled).toBe(true);
  });
});

describe("a placeholder in the model panel", () => {
  it("says it is not built, and shows each step the design round drew", () => {
    app = mount(Workflow, { target: document.body, props: { id: "solve" } });
    flushSync();
    const steps = [...document.querySelectorAll<HTMLButtonElement>(".steps button")];
    expect(steps.map((b) => b.textContent!.replace(/\s+/g, " ").trim())).toEqual(
      ["1 Cell and space group", "2 Composition", "3 Solve", "4 Complete"]);
    expect(document.querySelector(".box")!.textContent).toContain("Not built yet.");
    expect(document.querySelector("h3")!.textContent).toBe("Cell and space group");
    steps[2].click();
    flushSync();
    expect(steps[2].getAttribute("aria-current")).toBe("step");
    expect(document.querySelector("h3")!.textContent).toBe("Solve");
    expect(document.querySelector(".box")!.textContent).toContain("charge flipping");
  });
});
