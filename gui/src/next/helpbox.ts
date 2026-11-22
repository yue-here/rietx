/**
 * What each model tab's `?` box says (WP-2231; the maintainer's look of
 * 2026-11-21, item 6, reversing § Settled 11).
 *
 * The prototype puts one `?` button at the right of each tab strip, in a fixed
 * place, and its box explains the tab that is up. These are its words, cut to
 * what the rebuilt page does. `anchor` is the section of the manual's GUI
 * chapter (`reference/gui-guide.md`) the box links to.
 */
import type { ModelTab } from "./tabs";

export type HelpBoxEntry = {
  title: string;
  /** one paragraph, then the list */
  lead?: string;
  items: string[];
  anchor: string;
};

export const MODEL_HELP: Record<ModelTab, HelpBoxEntry> = {
  params: {
    title: "Parameters",
    items: [
      "Tick a box to refine that parameter in the next cycle.",
      "Click a number to type a new value. It stays pending until Apply.",
    ],
    anchor: "parameters",
  },
  interactive: {
    title: "Interactive",
    lead: "Move the model by hand and watch the graphs. Nothing is refined until you choose to.",
    items: [
      "The mark on each track is the last fit.",
      "Click a name to set its range and scale. Click a number to type a value.",
    ],
    anchor: "interactive",
  },
  plan: {
    title: "Plan",
    lead: "Read it top to bottom. Each stage refines what earlier stages freed, plus what it frees, less what it fixes.",
    items: [
      "Drag the handle to reorder, or focus it and use the arrow keys.",
      "Fix offers only what is free by that stage.",
      "Refine runs this plan when Staged plan is chosen.",
    ],
    anchor: "plan",
  },
  text: {
    title: "Text",
    lead: "The model as rietx text, the same file you can edit in any editor.",
    items: [
      "Change a number or a refine flag and it becomes a pending edit, as in Parameters. Apply in the action bar, or ⌘⏎, sends it.",
      "Edited lines are highlighted. A line rietx cannot read is underlined.",
      "Rectangular selection: ⌥-drag.",
      "An edit applies through the same verbs the forms call, so it lands as history nodes and a checkout undoes it.",
    ],
    anchor: "text",
  },
};
