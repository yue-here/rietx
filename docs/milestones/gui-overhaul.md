# gui-overhaul — the GUI redesigned around the pattern and the model

**Opened 2026-11-08** by the maintainer, who chose the first piece that evening.
[`../ROADMAP.md`](../ROADMAP.md) § gui-overhaul carries the short prose, and the WP
index lists the rows. The block 22xx is claimed for the pieces after the first. The first
piece is WP-2123, numbered before this record was written.

Narrative about the WPs below goes to the record of the release in flight,
[v1.12](v1.12.md) today, as for every other WP (protocol rule 5).

## Scope

The maintainer dislikes the GUI's current look: too much information at once, dense rows,
boxes and chips with no clear purpose, and controls whose purpose is unclear (ruled
2026-11-06). The website and the manual are the reference for the new visual language. The
redesign was worked out between 2026-11-06 and 2026-11-08 in twelve rounds of prototypes the
maintainer reviewed on screen. Each port WP restates the designs it builds and the ruling each
rests on, dated, because the prototypes are not published.

The order the maintainer accepted on 2026-11-06: redesign inside today's `rietx gui` first,
then agent access, then a downloadable desktop app (Tauri, for people who do not use Python,
unsigned for now), then a browser build. This milestone is the first of those four. The
redesign is ported in five pieces, in this order:

| Piece | WP | What it builds |
|---|---|---|
| 1 | [2123](../wp/2123-the-layout-shell.md) | the layout shell: graphs on the left in tabs with a title line, the model panel on the right in tabs with a sash, both panels collapsible, a one-row action bar with Apply and refine, the segmented register redrawn, new colour tokens, a one-column layout for a narrow window, and a browser test that no click moves the layout unless it asks to |
| 2 | not yet filed | the Parameters panel: one row per atom, number slots that never move, the padlock as `hold`, the floating editor |
| 3 | [2127](../wp/2127-the-plan-tab.md) | the Plan tab on the existing plan routes, read top to bottom as a recipe |
| 4 | not yet filed | previews: a route evaluating the pattern at unsaved values, the interactive sliders, and the Pattern and Peaks previews drawn at the last fit's scale |
| 5 | not yet filed | the Background tab: a route serving the preview's matrices, a held Chebyshev term, the P-spline |

Every merge leaves a working GUI. No existing panel or route becomes unreachable at any piece;
a panel moves into the new shell as it is, and is redesigned by its own piece.

Three decisions wait on the maintainer before the piece that needs them:

- A plan stage that fixes as well as frees. The maintainer wants it (2026-11-07); in rietx it is
  a `turn_off` list on `StageSpec` and a `fix` clause in `.rxt`, both stored-format changes, so
  piece 3 asks for the go-ahead in its WP.
- A background drawn through points the user places. rietx has no such background type; a new
  one is a stored-format change.
- A text file kept beside the project, which the maintainer deferred to the port on 2026-11-07.

### Owed to the port

The design rounds found these rietx defects and left them for the port, by the maintainer's
ruling of 2026-11-08 that the design work changes nothing on `main`. Each becomes port work, in
the piece that touches it or a WP of its own.

- The extinction screen is refused on a project with no phase: `GuiSession.run` groups the kind
  `extinction` with the refinement kinds, though WP-1027 ruled the screen ungated, and the
  refusal reads "a extinction run".
- Adopt is gated to `best_or_none()` (`ADOPT_GATED`). The maintainer ruled on 2026-11-08 that a
  person may adopt any candidate, with its grade and caveats shown beside Adopt and recorded in
  the history node.
- The Peaks panel hides `systems_searched`, `search_complete` and the run-level `INDEX_*`
  diagnostics whenever there are candidates, against WP-1042's rule that what was not reached
  is said loudly.
- `.rxt` renders no block for user variables, and its tie refusal names only symmetry ties.
- The Le Bail check's absent lines arrive in its own refined frame, about 0.011° from the
  candidate's ticks on fluorapatite; they should be served as tick indices.
- `supercell_checks` names a relation for 8 of fluorapatite's 12 candidates (measured by WP-2124
  on 63d7c120a; naming the other four is WP-2124's follow-up); lattice relations between
  candidates ("c doubled", "a × √3", "same cell") belong in rietx.
- `PeakEditor.curves` serves only each group's sum; per-line curves need a route.
- `set_flags(..., use_for_indexing=True)` forgets which flags a person overruled.
- `--plot-peak` (purple) loses to the data crosses as a mark colour.
- The pick route takes only `shoulders`; the 2θ range and `flag_contamination` need to reach it.
- Right-click on a plot object opens no context menu, and peak edits have no undo, though the
  maintainer adopted both rules on 2026-11-08.
- A GUI series lives in session memory only; several series gaps wait on the series fitting
  now changing on `main`.
- The Model and Text panels keep their own Apply beside the action bar's, outlined so the bar's
  Refine stays the one filled button, because WP-2123 routes only the Parameters edits through
  the action bar. Their edits still wait on two Apply buttons in one view.
- A run started from the Plan, Report or Series panel, or by the `.` key, does not apply the
  Parameters edits waiting in the action bar; the bar's Refine and the `r` key do (WP-2123).

## Acceptance

Written at the open. Each row is checked when its piece closes, and the milestone completes
when all are met on one tree.

| # | Row | Piece | How it is measured |
|---|---|---|---|
| 1 | No click moves the layout unless it asks to. Expanding, collapsing, switching a tab and jumping ask; editing a value, ticking a box and choosing a mode do not | 1, then every piece | the layout-shift browser test clicks every control on a fresh page in each starting state and compares element boxes before and after |
| 2 | Every panel and route of the GUI before the milestone stays reachable after each piece | every piece | `tests/test_gui_manual.py`'s partitions, plus a browser pass that opens every tab |
| 3 | A choice never looks like an action: every segmented choice is a sunken track with one raised option, and actions are outlined or filled buttons | 1 | `lib/style.test.ts` and a look at the screenshots |
| 4 | Colour values live in `src/rietx/viz/theme.py`, and `gui/src/tokens.css` is generated from it | 1, then every piece | `tests/test_gui_palette.py` |
| 5 | Below a measured width the window is one column, graphs above the model, with no sideways scroll of the page | 1 | the browser test at 420 px and at the threshold |
| 6 | The graphs say what they show, so a preview never reads as a changed fit | 1, 4 | the title line's text in each state, asserted in vitest |
| 7 | One atom is one row, and switching a number between scientific and plain moves nothing | 2 | the layout-shift test over the Parameters panel |
| 8 | The plan reads top to bottom as a recipe, on the existing plan routes | 3 | a browser pass over a five-stage plan |
| 9 | A preview is drawn at the last fit's scale and never moves the comparison | 4 | the preview route's timing and a browser pass |
| 10 | The maintainer has looked at each piece on screen before its merge | every piece | the PR's review |
