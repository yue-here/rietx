# WP-2204 — the workflow menu

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — claimed by ghostshift runner
Depends on: 2123
Priority: P3 2026-11-10 — a designed piece of the open milestone; the panels it opens are reachable from their tabs today

## Goal

The top bar carries a workflow menu beside the graphs toggle. Its button names the workflow the
window is in. The menu lists Refinement, Peaks and indexing, Series, Structure solution and Rigid
bodies. The first three open the panels that already work. Structure solution and Rigid bodies
are placeholders: the menu and the window say plainly that they are not built yet, and the model
panel shows each one's steps.

## Context

### Where it is today

The top bar holds, left to right: the graphs toggle, the word `rietx` and the version, the
project's name (which opens the File menu, WP-2133), the project line, then Simple/Advanced, the
theme, the run pill, Cancel and ⌘K, and the model toggle at the right end (WP-2123). There is no
workflow menu. Peak picking and indexing live in the model panel's Peaks tab, and the series in its
Series tab (`gui/src/lib/tabs.ts:TABS`). WP-2202 (in flight) redraws the Peaks tab as four steps
and says: "The workflow menu that will open it is its own milestone row; until it exists the
Peaks tab is the workflow's home, so no route or tab becomes unreachable."

### The design, and the rulings it rests on

The prototypes are not published, so the design is restated here.

**The maintainer's sixth review, 2026-11-07** (after round 3 of the window prototype): add
placeholders for peak picking and indexing (then in flight on `main`), series, structure solution
and rigid bodies. "These are alternative workflows, not tabs." Indexing is a workflow: pick peaks,
fit, index, judge, iterate. `gui/STYLE.md` § Layout and panels carries it: "Workflows (peaks and
indexing, series, structure solution, rigid bodies) are entries in the workflow menu, never tabs.
A workflow keeps the window and shows its steps across the model panel."

**On round 4, 2026-11-07** ("happy with the general shape"): the workflow menu needs no
"Workflow" heading, which round 4 had and which was removed. A menu does not restate the button
that opened it (`gui/STYLE.md` § Components).

**The frame, 2026-11-07** (`gui/STYLE.md` § Layout and panels): the top bar holds, left to right,
the graphs toggle, the workflow menu, the project name (which opens the File menu), Settings and
the model toggle. The bars never change, so no toggle moves.

What round 4 and its successors drew:

- The menu button is a borderless word with a caret: the current workflow's name in the heading
  weight, a border and a raised ground on hover and while open. On the start screen, with no
  project, it is drawn and disabled.
- The menu lists the five workflows in one column, a check beside the current one. A placeholder
  carries `· placeholder` after its name, in the muted ink, in the menu and on the button.
- Choosing a workflow keeps the window. A workflow other than Refinement replaces the model
  panel's tab strip with one tab carrying its name, hides the action bar (Apply and refine has
  nothing to apply there), and shows its steps across the top of the panel as numbered words
  joined by `›`. Each step shows a heading and a dashed box saying what the step will hold.
  Indexing ends its strip with `↺ iterate` (back to Pick peaks).
- The placeholder text, as drawn:
  - Structure solution: steps Cell and space group › Composition › Solve › Complete. "From
    indexing, or typed in." "Formula and Z." "Route: direct space or charge flipping. Ranked
    candidates with their evidence." "Difference Fourier: find the missing atoms, then refine."
  - Rigid bodies: steps Define › Place › Refine, headed Bodies, Place, Refine. "A fragment from
    a CIF, a SMILES string or picked atoms." "Origin and orientation in the cell." "Origin,
    rotation and torsions free; the atoms come back with esds."
  - Each had a one-line purpose in the panel's ? box: "Find atom positions from a known cell,
    space group and composition, then complete the model by difference Fourier." and "Refine a
    molecule or fragment as one body: its origin, orientation and torsions, rather than every
    atom."
- A placeholder also narrowed the graph tabs (Pattern and Structure).
- Workflow names follow rietx's milestone names (settled by Claude in round 4, no objection).

Rounds 11 (2026-11-08) and 12 (2026-11-08) then built Peaks and indexing and Series as working
workflows, so by the last round only Structure solution and Rigid bodies were placeholders.

### Rulebook seams

- **No click moves the layout unless it asks to** (`gui/STYLE.md` principle 4;
  `tests/test_gui_layout_browser.py`). Opening the menu is an overlay and moves nothing.
  Choosing a workflow is a jump, which asks.
- **The menu is an overlay in viewport coordinates**, as the File menu is (WP-2133), so the
  header's wrapping does not clip it.
- **Every panel stays reachable** (milestone acceptance row 2). The tab strip keeps all ten tabs
  in Refinement, Peaks and indexing, and Series.
- **No permanent explanatory text** (`gui/STYLE.md` principle 5).
- **The header is shared with open PRs**: #1521 (WP-2206/2207) moves the run pill and Cancel
  into a status bar, and #1518 (WP-2210) adds statistics to the action bar. This WP touches only
  the start of the header's `.bar`, so either merges against it in one hunk.

### Tier

Nothing here reads the data or decides for a fit, so no row joins `rietx._audit`.

### Inherited

(none)

## Non-goals

- Moving the Peaks and Series panels out of the tab strip, and their step strips. WP-2202 draws
  the Peaks tab's four steps; the series redesign is its own piece.
- Structure solution and rigid bodies themselves. rietx's `solve` package is not public yet
  (structure-solution milestone), and rigid bodies are a schema feature with no GUI form
  (rigid-bodies milestone).
- Settings in the top bar: the Settings dialog piece.
- Narrowing the graph tabs for a placeholder. On `main` the graph strip has no Structure tab yet
  (WP-2203 is in flight), so a placeholder would show Pattern alone.

## Tasks

- [x] File this WP, its ROADMAP prose and its milestone row.
- [x] `panels/WorkflowMenu.svelte` and `lib/workflows.ts`: the button, the menu, the five
  entries, the current one derived from the model tab or the chosen placeholder.
- [x] The placeholder pane in the model panel: one tab with the workflow's name, the step strip,
  each step's heading and dashed box; the action bar hidden.
- [x] Tests: vitest for the derivation and the menu; the layout browser test opens the menu,
  chooses every entry and comes back; the dist rebuilt.
- [x] The GUI chapter: the header table and a Workflow menu section.
- [x] Screenshot beside the prototype's at the same window size, for the PR.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_manual.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

Milestone rows 1 (no click moves the layout), 2 (every panel and route reachable), 10 (the
maintainer looks before merge) and 11 (the screenshot beside the prototype's).

## References

`gui/STYLE.md`; `docs/milestones/gui-overhaul.md`.

## Handover log

- **2026-11-10** — created. No open WP owns the workflow menu: the milestone lists it under
  "Designed, not yet filed", and WP-2202 names it as its own row.
