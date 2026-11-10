/** The workflow menu's entries, as data (WP-2204).
 *
 * The maintainer ruled on 2026-11-07 that peak picking and indexing, series,
 * structure solution and rigid bodies are alternative workflows, chosen from a
 * menu in the top bar, never tabs. A workflow keeps the window and shows its
 * steps across the model panel (`gui/STYLE.md` § Layout and panels).
 *
 * Three entries open panels that work today: Refinement is the model panel's
 * own strip, and Peaks and indexing and Series are its Peaks and Series tabs,
 * which WP-2202 and the series piece redraw in steps. The other two are
 * placeholders, and say so: rietx's `solve` package is not public yet, and
 * rigid bodies have no form in the GUI. Their steps and wording are the design
 * round's (round 4, 2026-11-07), restated in WP-2204.
 *
 * Which workflow the window is in is never stored. It is read off the model
 * panel's tab, where a placeholder is a tab value of its own, so any opener
 * that sets a tab (the strip, the palette, a run ending, a project opening)
 * leaves a placeholder without being told about it.
 */
import type { Tab } from "./tabs";

export type PlaceholderId = "solve" | "rigid";
export type WorkflowId = "refine" | "index" | "series" | PlaceholderId;
/** What the model panel shows: a tab of the strip, or a placeholder workflow. */
export type Shown = Tab | PlaceholderId;

export interface Step {
  /** the word in the step strip */
  name: string;
  /** the heading over the step's box */
  heading: string;
  /** what the step will hold, in the box */
  body: string;
}

export interface Workflow {
  id: WorkflowId;
  name: string;
  /** the tab that is this workflow's home today, for the three that work */
  tab?: Tab;
  /** the steps a placeholder shows, for the two that are not built */
  steps?: readonly Step[];
}

export const WORKFLOWS: readonly Workflow[] = [
  { id: "refine", name: "Refinement" },
  { id: "index", name: "Peaks and indexing", tab: "peaks" },
  { id: "series", name: "Series", tab: "series" },
  {
    id: "solve",
    name: "Structure solution",
    steps: [
      { name: "Cell and space group", heading: "Cell and space group",
        body: "From indexing, or typed in." },
      { name: "Composition", heading: "Composition", body: "Formula and Z." },
      { name: "Solve", heading: "Solve",
        body: "Route: direct space or charge flipping. Ranked candidates with their evidence." },
      { name: "Complete", heading: "Complete",
        body: "Difference Fourier: find the missing atoms, then refine." },
    ],
  },
  {
    id: "rigid",
    name: "Rigid bodies",
    steps: [
      { name: "Define", heading: "Bodies",
        body: "A fragment from a CIF, a SMILES string or picked atoms." },
      { name: "Place", heading: "Place", body: "Origin and orientation in the cell." },
      { name: "Refine", heading: "Refine",
        body: "Origin, rotation and torsions free; the atoms come back with esds." },
    ],
  },
];

/** The word a placeholder carries after its name, in the menu and on the button. */
export const PLACEHOLDER_MARK = "placeholder";

export function workflow(id: WorkflowId): Workflow {
  return WORKFLOWS.find((w) => w.id === id)!;
}

export function isPlaceholder(shown: Shown | WorkflowId): shown is PlaceholderId {
  return shown === "solve" || shown === "rigid";
}

/** The workflow the window is in, read off what the model panel shows. */
export function workflowOf(shown: Shown): WorkflowId {
  if (isPlaceholder(shown)) return shown;
  return WORKFLOWS.find((w) => w.tab === shown)?.id ?? "refine";
}

/** What the model panel shows once `id` is chosen from the menu.
 *
 * Refinement returns to the last tab that belongs to it, so a look at a
 * placeholder, Peaks or Series and back lands where the person was. */
export function shownFor(id: WorkflowId, lastRefineTab: Tab): Shown {
  if (isPlaceholder(id)) return id;
  return workflow(id).tab ?? lastRefineTab;
}
