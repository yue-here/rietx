# WP-2207 — the status bar

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — claimed by a ghostshift runner
Depends on: 2123
Priority: P2 2026-11-10 — a feature the open milestone was opened for; the bottom panel (2206) is toggled from it

## Goal

A bar along the foot of the window carries the console toggle at its left end and the run's
state beside it, with Cancel at its right end. The bar never changes shape, so no toggle in it
moves. The run state leaves the header, so a project's first run no longer moves the header's
controls.

## Context

### Where it is today

The window has a header and nothing at its foot. The header (WP-2123) carries the two collapse
buttons at its ends, the project's name and line, `Simple | Advanced`, the theme, a run pill,
`Cancel` and `⌘K`. The run pill is a `.pill` whose text is the stage while a run is in flight
and the last status otherwise (`idle`, `converged`, `failed`, `cancelled`). The Console is a
sized pane at the foot of the model column, under the action bar, with its own collapse caret
and a drag from its top edge (WP-1029).

**The defect this WP fixes** (found by another runner on WP-2123's header, 2026-11-10). On a
project's first run the pill's text changes from `idle` to the run's status. The pill is
content-sized and sits left of `Cancel` and `⌘K` in a right-aligned group, so `Simple |
Advanced`, the theme control and `Cancel` move 35 px left. The layout-shift test
(`tests/test_gui_layout_browser.py::test_a_refine_moves_nothing_while_it_runs_or_after`)
missed it: its fixture had already fitted one stage, so the pill read `converged` before the
click and after it.

### The design, and the rulings it rests on

- **The bars.** The maintainer's sixth review (2026-11-07) asked for a collapsible console
  showing what the Python is doing. Round 4 of the prototype, which the maintainer was "happy
  with the general shape" of (2026-11-07), drew the frame: a top bar with the graphs toggle at
  the far left and the model toggle at the far right, and a status bar along the foot with the
  console toggle at the far left. The bars never change, so no toggle moves.
  `gui/STYLE.md` § Layout and panels states it: "The status bar holds the console toggle at its
  left."
- **The toggle.** The prototype draws the panel icon (a window with its bottom band filled while
  the panel shows) followed by the word `Console`, with ⌘J as its shortcut, and the title
  "Show the console (⌘J)" or "Hide the console (⌘J)". With no project open the toggle is drawn
  and disabled. The header's two collapse buttons are drawn the same way since WP-2123.
- **The run state.** The prototype writes its simulated run's progress ("Running stage 1 of
  5…") in the status bar, right of the toggle. The header's run pill moves there for this
  reason and for the defect above: a slot that changes its words must sit where nothing to its
  right depends on its width.
- **No click moves the layout unless it asks to** (the maintainer's ruling of 2026-11-07,
  `gui/STYLE.md` principle 4, milestone acceptance row 1). A run's start and end ask for no
  layout change.
- **A fact is words, without a box** (`gui/STYLE.md` § Components, Fact: "a bordered box is a
  control, so `.chip` and `.pill` go as their panels are redrawn"). The run state is redrawn
  here, so it is words, in a state colour only where the tone is a judgement.

### Rulebook seams

- **Routes and panel names** (WP-1017): the header table in `reference/gui-guide.md` names the
  pill, and the quickstart's run section says where the stage is counted. Both move.
- **Screenshots** (WP-1017) come from `docs/docs/make_screenshots.py`, whose run waits on the
  pill's `data-state`; it waits on the status bar's instead.
- **The layout-shift test** (milestone acceptance row 1) covers a project's first run.

### Tier

Nothing here reads the data or decides for a fit, so no row joins `rietx._audit`.

## Non-goals

- The bottom panel the toggle opens: WP-2206, on this branch.
- The top bar's target shape (workflow menu, Settings): those pieces move `Simple | Advanced`,
  the theme and `⌘K`. This WP takes only the run state and `Cancel` out of the header.
- Rwp and GoF in the bar: they stay on the graph title line, and beside Refine while the graphs
  are hidden (the "Fit statistics in the action bar" row, WP-2210).

## Tasks

- [x] Claim: this file, the index, the milestone's piece table.
- [ ] `panels/StatusBar.svelte` and `lib/statusbar.ts`: the console toggle at the left, the run
  state beside it, `Cancel` at the right end; the header's pill and `Cancel` go. Vitest for the
  run-state words and the toggle.
- [ ] The layout browser test covers a project's first run, the status bar's landmarks and its
  toggle; the dist rebuilt.
- [ ] The GUI chapters: the header table, a status bar section, the quickstart's run section;
  the screenshot driver waits on the status bar; the screenshots retaken.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- The maintainer's rulings of 2026-11-07 (sixth review, round 4) and 2026-11-09 (port
  acceptance, the style guide), restated above with their dates.
- WP-2123 (the layout shell and its layout-shift test), WP-2206 (the bottom panel).

## Handover log

- **2026-11-10** — created and claimed by a ghostshift runner, with WP-2206 on one branch. No
  open WP owned the status bar: the milestone record listed it under "Designed, not yet filed".
