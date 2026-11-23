/** The workflow menu's entries, as data (WP-2204, carried into the rebuild by WP-2215).
 *
 * The maintainer ruled on 2026-11-07 that peak picking and indexing, series,
 * structure solution and rigid bodies are alternative workflows, chosen from a
 * menu in the top bar, never tabs. A workflow keeps the window and shows its
 * steps across the model panel (`gui/STYLE.md` § Layout and panels).
 *
 * In the rebuilt page Refinement and Peaks and indexing are built (R6,
 * WP-2240, builds the second a step at a time, and a step not built yet shows
 * its sentence). Series is R7 (WP-2214 § The pieces); until it lands it is not
 * built yet, like structure solution and rigid bodies, and says so, so a
 * workflow that is not built never reads as one that is. The mark is "not
 * built yet", never "placeholder" (the maintainer's ruling, 2026-11-10).
 * The steps and their words are the design round's (round 4, 2026-11-07),
 * restated in WP-2204.
 */
export type WorkflowId = "refine" | "index" | "series" | "solve" | "rigid";

export interface Step {
  /** the word in the step strip */
  name: string;
  /** what the step will hold */
  body: string;
  /** the step is built: its own panel shows, not `body` */
  built?: boolean;
}

export interface Workflow {
  id: WorkflowId;
  name: string;
  /** the workflow's steps, across the model panel; absent for Refinement,
   *  which shows the model's tabs instead */
  steps?: readonly Step[];
  /** the workflow is built; a workflow with steps and no `built` is not */
  built?: boolean;
  /** where the last step leads back to, said on the strip's "iterate" mark */
  loop?: string;
  /** the graph tabs the workflow shows, when not all of them (the
   *  prototype's: peaks and indexing draws the pattern and the peak fits) */
  graphs?: readonly ("pattern" | "peaks" | "background" | "structure")[];
}

export const WORKFLOWS: readonly Workflow[] = [
  { id: "refine", name: "Refinement" },
  {
    id: "index",
    name: "Peaks and indexing",
    built: true,
    loop: "Back to Pick peaks",
    graphs: ["pattern", "peaks"],
    steps: [
      { name: "Pick peaks", body: "Click the pattern to add a line; drag to move it.", built: true },
      { name: "Fit peaks", body: "Each line fitted in its window, with its own esd.", built: true },
      { name: "Index", body: "Engines, crystal systems, centrings, cell bounds, formula.", built: true },
      { name: "Judge",
        body: "Screen extinctions, check each candidate by a whole-pattern Pawley fit, then adopt one as a Pawley start.",
        built: true },
    ],
  },
  {
    id: "series",
    name: "Series",
    steps: [
      { name: "Patterns", body: "The files in series order, and what each pattern after the first refines." },
      { name: "First fit", body: "Refine the walk's first pattern alone; the series starts from that result." },
      { name: "Run", body: "Each fit as it lands." },
      { name: "Results", body: "One row per pattern, with trends and a map." },
    ],
  },
  {
    id: "solve",
    name: "Structure solution",
    steps: [
      { name: "Cell and space group", body: "From indexing, or typed in." },
      { name: "Composition", body: "Formula and Z." },
      { name: "Solve", body: "Route: direct space or charge flipping. Ranked candidates with their evidence." },
      { name: "Complete", body: "Difference Fourier: find the missing atoms, then refine." },
    ],
  },
  {
    id: "rigid",
    name: "Rigid bodies",
    steps: [
      { name: "Define", body: "A fragment from a CIF, a SMILES string or picked atoms." },
      { name: "Place", body: "Origin and orientation in the cell." },
      { name: "Refine", body: "Origin, rotation and torsions free; the atoms come back with esds." },
    ],
  },
];

/** The words an unbuilt workflow carries after its name, in the menu. */
export const NOT_BUILT_MARK = "not built yet";

export function workflow(id: WorkflowId): Workflow {
  return WORKFLOWS.find((w) => w.id === id)!;
}

export function isNotBuilt(id: WorkflowId): boolean {
  const w = workflow(id);
  return !!w.steps && !w.built;
}

/** The graph tab a step opens on: the peak fits for Fit peaks, the pattern
 *  for every other step (the prototype's, round 11). */
export function stepGraph(id: WorkflowId, step: number): "pattern" | "peaks" | null {
  if (id !== "index") return null;
  return step === 1 ? "peaks" : "pattern";
}

/** The menu's label for an entry: its name, and the mark when it is not built. */
export function menuLabel(w: Workflow): string {
  return isNotBuilt(w.id) ? `${w.name} · ${NOT_BUILT_MARK}` : w.name;
}
