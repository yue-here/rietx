# WP-2206 — the bottom panel: Console and History

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — built; PR #1521 open with WP-2207, waiting on review
Depends on: 2207
Priority: P2 2026-11-10 — a feature the open milestone was opened for

## Goal

A panel across the foot of the window, above the status bar, holds two tabs: Console (the Python
the window has run, as the calls a script would make, and the engine's events) and History (the
refinement's tree, with compare and checkout). The status bar's toggle and ⌘J show and hide it,
and it starts hidden. Every history and console feature reachable before stays reachable.

## Context

### Where it is today

- **Console** (`panels/Console.svelte`, WP-1029) is a sized pane at the foot of the model
  column, under the action bar. Its lines are the shell's `lines`, fed by `say()` from every panel
  (each verb echoes the call a script would make: `ref.set_values({...})`,
  `ref.run_stage(Stage(...))`, `ref.checkout("...")`) and by the event stream through
  `lib/stream.ts:consoleLine`. It shows a `N frames dropped` warning and a `follow` button when
  scrolled up. Its height is `ProjectDoc.ui.console_height`, persisted on the drag.
- **History** (`panels/History.svelte`, WP-1012, WP-1217) is the ninth tab of the model column:
  the node graph with lanes, a selected node's details and verbs (Checkout, Tag, Branch, Label),
  and a two-node compare table (`⇄`). The `h` key and the palette's "Show the history" open it.
- The routes exist: `GET /api/history`, `/api/history/diff`, `/api/history/compare`, and
  `POST /api/history/checkout`, `/branch`, `/tag`, `/annotate` (WP-1008). The Console needs no
  route: every line it shows is written by the page.

### The design, and the rulings it rests on

- **A collapsible console showing what the Python is actually doing, and a History tab** (the
  maintainer's sixth review, 2026-11-07).
- **One shared bottom panel**, as VS Code's panel holds Output and Terminal, hidden at first,
  toggled from the status bar. Settled by Claude in round 4 of the prototype, which the
  maintainer was "happy with the general shape" of (2026-11-07). `gui/STYLE.md` § Layout and
  panels states it: "The bottom panel holds Console (the Python the window runs) and History
  (with Compare and Restore). The status bar toggles it, and it starts hidden."
- **The prototype's panel**: full window width, between the panes and the status bar, a tab
  strip (Console, History) with the History tab carrying its node count, a drag along its top
  edge to resize (keyboard arrows on the sash too, double-click resets), 200 px by default.
  Console is the session as a script: a timestamp line, then each call; a Copy button copies it.
  History is a table of nodes (Node, Step, Rwp, GoF, Free, When) with Compare (overlay a node's
  fit on the pattern) and Restore (load its values as pending edits).
- **Going back is History's Restore** (the file and project I/O ruling, 2026-11-07: work saves
  itself, so there is no revert-to-saved).
- **Port acceptance** (2026-11-09): a piece hews close to the prototype through the style guide,
  and the milestone's rule that a panel moves into the new shell as it is and is redesigned by
  its own piece.

### What this WP builds, against the prototype

The panel, its tabs, its toggle, its sash and its persisted height are the prototype's. The
Console moves in with the lines it already has, and gains the prototype's Copy. The History tab
moves the existing panel in whole: its graph, details, verbs and compare table. The prototype's
History table, its Compare as an overlay on the pattern, and its Restore as pending edits are a
redesign of that panel. They compose existing routes (`/api/history/diff` against the head gives
a node's differing values; `POST /api/preview` draws the pattern at them; the action bar holds
them as pending edits), but each is a new interaction on the main surface, so they are the
follow-up below rather than part of the move.

### Rulebook seams

- **The tab strips are data in `lib/tabs.ts`** (WP-1017, WP-2123): a third strip,
  `BOTTOM_TABS`, is written into `tests/data/gui/panels.json`, and `tests/test_gui_manual.py`
  holds the GUI chapters to name it. History leaves `TABS`.
- **`ProjectDoc.ui` keys are the frontend's** (WP-1044): `console_height` keeps its name and
  becomes the bottom panel's height, so an existing project keeps the height it stored. No format
  change.
- **Screenshots** (WP-1017): the history shot is taken of the bottom panel.

### Tier

Nothing here reads the data or decides for a fit, so no row joins `rietx._audit`.

## Non-goals

- The History redesign: the prototype's node table, Compare as an overlay on the pattern and
  Restore as pending edits. A follow-up WP, which owns the naming question (the panel's
  `Checkout` against the prototype's `Restore`).
- A Console that tells Python from engine events (the prototype's `>>>` prompt) or exports the
  session as a `.py` file. Both need the lines tagged by kind where `say()` and `consoleLine`
  write them; a follow-up.
- The status bar itself: WP-2207.

## Tasks

- [x] Claim: this file, the index, the milestone's piece table.
- [x] `BOTTOM_TABS` in `lib/tabs.ts` and the panel corpus; History leaves `TABS`;
  `tests/test_gui_manual.py` reads the third strip.
- [x] `panels/Bottom.svelte`: the tab strip, the sash, the height; Console and History mounted
  in it and always mounted; the status bar's toggle, ⌘J and `h` open it. Console fills its pane
  and gains Copy. Vitest.
- [x] History laid out for a short, wide panel; the layout browser test sweeps the bottom
  panel's controls; the dist rebuilt.
- [x] The GUI chapters (the window's shape, Console, History, the keyboard), the screenshot
  driver, the screenshots retaken.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_peaks_browser.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

## References

- The maintainer's rulings of 2026-11-07 (sixth review, round 4, file and project I/O) and
  2026-11-09 (port acceptance), restated above with their dates.
- WP-1012 and WP-1217 (the History panel), WP-1029 (the Console's sized pane), WP-2207 (the
  status bar).

## Handover log

- **2026-11-10** — Console and History now share a panel across the window's foot, shown from
  the status bar's `Console` button, ⌘J or Ctrl+J, and `h` opens it on History. It starts hidden.
  History moved whole: every verb and the compare table work as before, laid out as two
  columns (graph | details and compare) because the panel is short and wide. The Console gained
  Copy, and follows its newest line when shown. The model column has nine tabs now. The
  prototype's History redesign (a node table, Compare as an overlay, Restore as pending edits)
  is not built here. PR #1521 carries both WPs.
  *Done*: `BOTTOM_TABS` in `lib/tabs.ts`, written to `tests/data/gui/panels.json` and read by
  `tests/test_gui_manual.py`; `panels/Bottom.svelte` (tab strip, sash with double-click
  reset, both panes always mounted); `panels/Console.svelte` reduced to the log, a sticky bar
  with Follow and Copy, and a `shown` prop; `panels/History.svelte` in two wrapping columns;
  `ProjectDoc.ui.console_height` kept as the panel's height (default 200 px, floor 90 px, so a
  project that stored the old 26 px collapsed console opens at 90); the three GUI chapters; the
  screenshot driver opens the panel through the toggle; every manual screenshot retaken.
  *Review*: `/code-review high --fix` found 9; 5 fixed in one commit (drag from the drawn
  height, drag height cleared on landing, toggle state needs a project, palette wording, title
  on cut words) plus the first-run test's race. Declined: a hidden tab loses its scroll
  position (every side panel does the same today); the stacked side panel's dragged height is
  not re-clamped when the bottom panel opens (a layout choice beyond this WP); the 90/200 px
  constants are still written in CSS and App as well as `Bottom.svelte`.
  *Found by the browser test*: a hidden pane has no scroll height, so the Console opened after a
  run showed its first line; fixed with `shown`. A selected tab's bold label widens it by 2 px,
  in every strip in the window: not counted as a moved landmark, and not changed here.
  *Rule kept out of gui/CLAUDE.md for its cap*: a pane mounted while hidden is told when it
  shows, since it has no scroll height until then.
  *Measured* (worktree `[dev]` venv, darwin arm64, machine load 50-70 from parallel runners):
  vitest 727 passed in 33 files (one later run failed `keeps a typed buffer across a trip to
  another tab` once and passed alone: a load flake in a test this branch does not touch);
  svelte-check 420 files, 0 errors; layout browser file 34 tests, the new ones 6 passed after
  fixes; on the final tree the layout, gui and peaks browser files 40 passed and the compare,
  html, rxplot, structure3d and watch browser files 118 passed (CI runs none); `tests.reader_output`
  exit 0. Fast suite (`-m "not slow"`, under the machine's suite lock): 14625 passed, 410
  skipped, 32 xfailed, 11 min 34 s. The six added cases are three browser tests at two
  parameters each, all in `tests/test_gui_layout_browser.py`, which skips in CI (no
  playwright there): locally they cost 27 s, the bottom-panel sweep 20 s of it.
  *Open visual questions for the maintainer* (each taken nearest the prototype; screenshots
  at 1440x900 beside the prototype's are listed by path in PR #1521):
  1. History moved whole, in two columns, and its tab carries no node count. The prototype's
     tab reads `History 8` and its panel is a node table; that redesign is the follow-up below.
  2. The Console's Copy sits in a sticky bar at the top right, as the prototype's does, with a
     Follow button beside it that shows only when scrolled up.
  3. The panel opens hidden on every load (session-local), and its height is the project's.
     The prototype remembers whether it was shown.
  The status bar's three questions are in WP-2207's entry.
  *Follow-ups, unfiled* (the brief kept this runner to its two milestone rows; no open WP owns
  either): the History redesign, which owns the `Checkout` against `Restore` naming; Console
  lines tagged by kind where `say()` and `consoleLine` write them, for the `>>>` prompt and a
  `.py` export.
  Next: the maintainer's review of PR #1521 and the three questions above; then file the two
  follow-ups, the History redesign first, since its Restore is the prototype's way back.

- **2026-11-10** — created and claimed by a ghostshift runner, with WP-2207 on one branch. No
  open WP owned the bottom panel: the milestone record listed it under "Designed, not yet filed".
