# WP-2204 — the workflow menu

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — built; PR #1524 waits on the maintainer's look and six visual questions
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

### 2026-11-10 — the workflow menu built; PR #1524

The top bar now has a workflow menu beside the graphs toggle. Its button names the workflow the
window is in. Refinement, Peaks and indexing and Series open the panels that already work.
Structure solution and Rigid bodies are placeholders and say so: `· placeholder` after the name
in the menu and on the button, and "Not built yet." at the top of the panel's box. A placeholder
shows its steps across the model panel, as the design round drew them, and hides the action bar.
Nothing on the server changed. The PR waits on the maintainer's look (milestone row 10) and the
six visual questions below.

**Done.** `lib/workflows.ts` holds the five entries as data. The workflow is never stored: it is
read off the model panel's tab, where a placeholder is a tab value of its own. So every opener
that sets a tab (the strip, the palette, a run ending, opening or closing a project) leaves a
placeholder without being told, and Refinement returns to the last tab that was its own.
`panels/WorkflowMenu.svelte` is the button and its overlay menu: a check on the current entry, no
heading, and Escape caught before the shell's run-cancelling Escape. `panels/Workflow.svelte` is
the placeholder pane: the step strip in the tab register with numbers (WP-2202's drawing for the
Peaks steps), then a heading over a dashed box. `App.svelte` changes in five places: the imports,
the `tab` type and its derivations, the menu at the start of the header's `.bar`, the side strip
and action bar in a placeholder, and Close resetting the tab. ⌘⏎ does nothing while a placeholder
hides the action bar, as in the prototype. The GUI guide has a header row and a Workflow menu
section. Screenshots in `docs/wp/2204-screenshots/`.

**Review** (`/code-review high --fix`, 8 findings). Fixed: Close left a placeholder's name on the
start screen's button; the guide called the label "the first word". Fixed after it: ⌘⏎ in a
placeholder (the prototype blocked it outside Refinement). Declined: with the model panel hidden,
the action bar under the graphs stays in a placeholder, because the placeholder pane is hidden
too and the bar is the only Refine on screen. The `r` key still refines from a placeholder, being
a palette command that works on every screen. Moved to the milestone's "Owed to the port": the
menu's drawing is copied from the File menu, and both lack arrow-key movement, focus on open, and
a hold on single-key shortcuts while open. `isPlaceholder` lists its two ids beside the data,
since a type guard needs the literal union; a vitest holds them equal.

**Settled by Claude.**
1. Peaks and indexing and Series are working entries, not placeholders, though the milestone row
   says "placeholders for peaks and indexing, series". The row restates the sixth review
   (2026-11-07), when both were placeholders; rounds 11 and 12 (2026-11-08) built them, the Peaks
   and Series tabs work today, and WP-2202 names the menu as the way into its tab. A placeholder
   over a working panel would read as a broken feature. Alternative: all four as placeholders.
2. Peaks and Series stay in the tab strip, and the button follows the tab. Moving them out is
   their redesign pieces' job (milestone acceptance row 2 keeps every panel reachable).
3. The menu's drawing is copied from the File menu rather than lifted into `app.css`, because
   #1517 and #1522 both rewrite `app.css` and `FileMenu.svelte`.

**Visual questions for the maintainer** (each settled nearest the prototype for now).
1. Placement: the button sits first in the bar, before the `rietx 1.12` wordmark. The prototype
   has no wordmark; `gui/STYLE.md` orders graphs toggle, workflow menu, project name. The
   alternative is after the wordmark.
2. Wording: `· placeholder`, the prototype's word, in the menu and on the button, plus "Not built
   yet." heading the box, which the prototype did not have. The alternative is "not built yet" in
   the menu too.
3. The step strip uses the tab register with plain numbers, as WP-2202's Peaks steps do. The
   prototype drew circled numbers and a raised ground on the current step.
4. The open button takes the File menu's hover tint. The prototype drew a border and a raised
   ground.
5. The prototype's one-line purpose of each placeholder lived in the panel's ? box, which the GUI
   does not have yet, so it is not shown.
6. The graph tabs are not narrowed in a placeholder. The prototype showed Pattern and Structure;
   `main` has no Structure tab until WP-2203 merges.

**Measured** ([dev] venv plus playwright 1.65.0, darwin/arm64, chromium 1243). Vitest 727 passed
(main 717, +10 in `lib/workflows.test.ts`); svelte-check 420 files, 0 errors.
`tests/test_gui_layout_browser.py`, `tests/test_gui_browser.py` and `tests/test_gui_manual.py`:
44 passed before the review fixes (the new test 2 of them). On the final tree, merged with
main at 5e90f9b41: the fast selection 14621 passed, 410 skipped, 32 xfailed (one suite on the
machine, through the shift's serial queue); every `tests/*_browser.py` plus
`tests/test_gui_manual.py`, 164 passed in two runs (46 and 118). The added test costs 3.74 s
for its two cases on this machine. `python -m tests.reader_output` exits 0: nothing a fit
prints or returns changed.

**Forward.** WP-2202 (in flight, its file on its branch only): the menu exists, its Peaks and
indexing entry opens the Peaks tab, and the button reads "Peaks and indexing" whenever that tab
shows. Nothing there needs to change.

**Next.** The maintainer looks at the PR's screenshots and answers the six visual questions;
then the PR merges. After #1517 and #1522 merge, the shared menu register from "Owed to the
port".

- **2026-11-10** — created. No open WP owns the workflow menu: the milestone lists it under
  "Designed, not yet filed", and WP-2202 names it as its own row.
