/**
 * What each tab's `?` box says, on the model strip and the graph strip
 * (WP-2231; the maintainer's look of 2026-11-21, item 6, reversing § Settled 11).
 *
 * The prototype puts one `?` button at the right of each tab strip, in a fixed
 * place, and its box explains the tab that is up. These are its words, cut to
 * what the rebuilt page does. `anchor` is the section of the manual's GUI
 * chapter (`reference/gui-guide.md`) the box links to.
 */
import type { WorkflowId } from "../lib/workflows";
import type { GraphTab, ModelTab } from "./tabs";

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
      "A changed number previews on the plot, as a slider move does.",
      "Edited lines are highlighted. A line rietx cannot read is underlined.",
      "Rectangular selection: ⌥-drag.",
      "An edit applies through the same verbs the forms call, so it lands as history nodes and a checkout undoes it.",
    ],
    anchor: "text",
  },
};

export const GRAPH_HELP: Record<GraphTab, HelpBoxEntry> = {
  pattern: {
    title: "Pattern",
    items: [
      "Drag across the plot to zoom in. Double-click it, or press Show all, to zoom out.",
      "Click a label on the right to hide or show its curve.",
      "The difference is (observed − calculated) / esd. The shaded band is ±3 esd.",
      "While you edit, the preview draws in orange and the last fit turns grey. Show switches between the preview and the last fit.",
    ],
    anchor: "the-pattern",
  },
  peaks: {
    title: "Peaks",
    lead: "Each window shows the strongest reflection in its part of the pattern.",
    items: [
      "‹ and › step to the next one.",
      "The scale stays at the last fit, so a preview that grows a peak runs off the top.",
    ],
    anchor: "single-peaks",
  },
  background: {
    title: "Background",
    lead: "The shaded band shows where the curve may move in the next fit, given what else is free. “Band drawn” only exaggerates it.",
    items: [
      "Chebyshev: a held term keeps its value from the last fit.",
      "P-spline: stiffness sets how smooth the curve must be.",
    ],
    anchor: "the-background",
  },
  structure: {
    title: "Structure",
    items: [
      "Drag to rotate. Scroll to zoom.",
      "a, b and c look down that axis.",
      "It draws the last fit, or the preview while you move a position or the cell in Interactive.",
    ],
    anchor: "the-3d-view",
  },
};

/** The bottom panel's History tab (WP-2211), in the design's words, with the
 *  node's menu named where the screen cannot say it. */
export const HISTORY_HELP: HelpBoxEntry = {
  title: "History",
  lead: "Each refinement adds a row, the newest at the bottom.",
  items: [
    "Compare overlays that fit on the pattern. Press it again to take it off.",
    "Restore loads its values as pending edits. Nothing changes until Apply.",
    "Right-click a row to make it current, branch from it, name it or write a note on it.",
  ],
  anchor: "history",
};

/** What a workflow's `?` box says, at the right of its step strip (WP-2240):
 *  the prototype's words for each workflow (rounds 11 and 12), cut to the
 *  steps built. */
export const WORKFLOW_HELP: Partial<Record<WorkflowId, HelpBoxEntry>> = {
  index: {
    title: "Peaks and indexing",
    lead: "Find the cell of an unknown phase. Go back to Pick peaks whenever the ticks say a line is missing or extra.",
    items: [
      "Pick peaks: tick a line to use it in the search, untick it to leave it out. Click a row to frame its line on the pattern.",
      "Picking again replaces the list, and says first how many of your edits it replaces.",
    ],
    anchor: "peaks",
  },
  series: {
    title: "Series",
    lead: "Refine many patterns in turn, each starting from its neighbour's result: a temperature ramp, an in-situ run.",
    items: [
      "Patterns: the files in series order and how to walk them. Type each pattern's value of the series axis; Sort by puts them in that order.",
      "Run: each fit as it lands. Stop keeps the patterns already fitted.",
    ],
    anchor: "series",
  },
};
