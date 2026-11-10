# WP-2206 — the bottom panel: Console and History

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — claimed by a ghostshift runner
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
- [ ] `BOTTOM_TABS` in `lib/tabs.ts` and the panel corpus; History leaves `TABS`;
  `tests/test_gui_manual.py` reads the third strip.
- [ ] `panels/Bottom.svelte`: the tab strip, the sash, the height; Console and History mounted
  in it and always mounted; the status bar's toggle, ⌘J and `h` open it. Console fills its pane
  and gains Copy. Vitest.
- [ ] History laid out for a short, wide panel; the layout browser test sweeps the bottom
  panel's controls; the dist rebuilt.
- [ ] The GUI chapters (the window's shape, Console, History, the keyboard), the screenshot
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

- **2026-11-10** — created and claimed by a ghostshift runner, with WP-2207 on one branch. No
  open WP owned the bottom panel: the milestone record listed it under "Designed, not yet filed".
