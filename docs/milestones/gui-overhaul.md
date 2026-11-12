# gui-overhaul — the GUI redesigned around the pattern and the model

**Opened 2026-11-08** by the maintainer, who chose the first piece that evening. **Turned into a
rebuild on 2026-11-11** (§ The rebuild). [`../ROADMAP.md`](../ROADMAP.md) § gui-overhaul carries
the short prose, and the WP index lists the rows. The block 22xx is claimed for the pieces after
the first. The first piece is WP-2123, numbered before this record was written.

Narrative about the WPs below goes to the record of the release in flight,
[v1.12](v1.12.md) today, as for every other WP (protocol rule 5).

## Scope

The maintainer dislikes the GUI's current look: too much information at once, dense rows,
boxes and chips with no clear purpose, and controls whose purpose is unclear (ruled
2026-11-06). The website and the manual are the reference for the new visual language. The
redesign was worked out between 2026-11-06 and 2026-11-08 in twelve rounds of prototypes the
maintainer reviewed on screen. Each WP restates the designs it builds and the ruling each
rests on, dated, because the prototypes are not published.

The order the maintainer accepted on 2026-11-06: redesign inside today's `rietx gui` first,
then agent access, then a downloadable desktop app (Tauri, for people who do not use Python,
unsigned for now), then a browser build. This milestone is the first of those four.

Every piece is judged against `gui/STYLE.md`, the style guide WP-2142 writes. The maintainer
ruled on 2026-11-09 for "a consistent style that hews very close to the workshop version",
achieved through a concise guide that states each rule's motive, so a piece completes what the
prototype left unfinished by the guide rather than by copying the prototype.

## The rebuild

On 2026-11-11 the maintainer ruled, on a brief, to rebuild the GUI's front end from the
prototype, beside the old GUI, instead of porting it piece by piece. In his words: "What I want
is the new gui to look and feel like the prototype. I'd like you to find elegant ways to include
the extra features of the current gui into the new one in a visually uncluttered way. For
example, the many buttons above and below the main panels should be hidden and accessible
according to UI design best practice. At the moment, I feel that we're litigating every small
change to the old gui." The evening before he had said "a large part of the redesign is
concealing a lot of these cluttered buttons", and asked to "drop the wordmark and other random
infoslop (this comment could be generalised to more of the gui)".

The rebuild keeps the Python server and its routes, the logic layer in `gui/src/lib`, the chart
module and the colour tokens in `src/rietx/viz/theme.py`. It replaces the shell and the panels.
The new front end is a second page of the same build, served beside today's at `/next`
(`rietx gui --new` opens it), and may be incomplete until it reaches parity. Then it replaces
today's page. The rule that every merge leaves every panel reachable moves from each merge to
that swap.

[WP-2214](../wp/2214-the-gui-rebuild-plan-and-inventory.md) holds the plan and an inventory of
every feature of today's GUI, each given its home in the new design, with five placements waiting
on the maintainer. The pieces, in order, each a screen or a workflow judged whole beside the
prototype at 1440 × 900:

| Piece | WP | What it builds |
|---|---|---|
| R1 | [WP-2215](../wp/2215-the-frame.md), in flight | the frame: the `/next` page, top bar, status bar, side and bottom panels, the workflow and File menus, Settings, the command palette and keys, one menu and context-menu component; the start screen, New project and the Console mounted in it |
| R2 | [WP-2216](../wp/2216-the-refinement-window.md), in flight | the refinement window: the Pattern graph (legend gutter, view menu, the fitted range and excluded regions as plot objects, the plot's context menu), the Parameters tab with the phase and atom menus, the action bar with one Apply, and the recovery offer for the edits it brings (moved from R1 by WP-2215) |
| R3 | — | hand fitting and the other graphs: the Interactive tab, the Peaks, Background and Structure graphs, the Instrument dialog |
| R4 | — | the Plan tab with Free and Fix rows, and the Text tab whose edits ride the action bar |
| R5 | [2211](../wp/2211-the-history-table.md), [2212](../wp/2212-console-lines-by-kind.md) | History as a table, Console lines by kind, and the report |
| R6 | — | the peaks-and-indexing workflow in four steps |
| R7 | — | the series workflow in four steps, with Trends and Map |
| Swap | — | `/` serves the new page; today's shell and the panels nothing imports are deleted; the manual's GUI chapters rewritten and their screenshots retaken. Its PR waits on the maintainer, since it deletes |

The maintainer reviews whole screens beside the prototype at each piece's end, and never single
values. A small visual value is settled under `gui/STYLE.md` and listed in the PR. A piece's
earlier PRs merge on green, and its last waits on his look.

## The port, until 2026-11-11

The redesign was first ported in five pieces, in this order. All five merged before the rebuild
ruling, and the rebuild mounts their panels in its new frame.

| Piece | WP | What it built |
|---|---|---|
| 1 | [2123](../wp/2123-the-layout-shell.md) | the layout shell: graphs on the left in tabs with a title line, the model panel on the right in tabs with a sash, both panels collapsible, a one-row action bar with Apply and refine, the segmented register redrawn, new colour tokens, a one-column layout for a narrow window, and a browser test that no click moves the layout unless it asks to |
| 2 | [2126](../wp/2126-the-parameters-panel.md) | the Parameters panel: one row per atom, number slots that never move, the padlock as `hold`, the floating editor |
| 3 | [2127](../wp/2127-the-plan-tab.md) | the Plan tab on the existing plan routes, read top to bottom as a recipe |
| 4 | [2125](../wp/2125-the-pattern-at-values-nobody-has-applied.md), [2128](../wp/2128-the-model-moved-by-hand.md) | previews: a route evaluating the pattern at unsaved values, the interactive sliders, and the Pattern and Peaks previews drawn at the last fit's scale |
| 5 | [2129](../wp/2129-the-background-tab.md) | the Background tab: a route serving the band from rietx's covariance, a held Chebyshev term, the P-spline's λ |

Until the rebuild, every merge left a working GUI with no panel or route unreachable, and a
panel moved into the new shell as it was before its own piece redesigned it.

### Designed after the five pieces

The design rounds drew these and the five pieces did not build them. Each was filed as a WP in
the 22xx block, or now lives in a rebuild piece. Where to find each since 2026-11-11:

| Piece | What it builds | Ruled | Now |
|---|---|---|---|
| The palette | the site's palette as the default theme, light and dark: warm neutrals, orange accent and calculated curve, grey difference, the plot palette re-measured against its floor, the peak-mark colour | 2026-11-06, 2026-11-09 | [WP-2200](../wp/2200-the-palette.md), PR #1517, merged 2026-11-11 |
| Named themes | established themes (Solarized light and dark, Monokai and others) listed in Settings after Match system, Light and Dark, on the seam WP-2200 leaves | 2026-11-06, 2026-11-09 | after the swap |
| Sentence-case headings | one `app.css` rule at the start screen's register, app-wide | 2026-11-09 | R1; PR #1522 (WP-2201) closes as a source |
| Peaks and indexing | the redesign in four steps (pick peaks, fit peaks, index, judge), the eight-column candidate table, lens peak marks, per-line curves in the fit windows | 2026-11-08, 2026-11-09 | R6; PR #1526 (WP-2202) stays open as a source until R6 starts |
| Structure tab | the 3D structure as one of the graph tabs | 2026-11-07 | R3; PR #1519 (WP-2203) closes as a source |
| Workflow menu | the top bar's workflow menu, with structure solution and rigid bodies marked "not built yet" | 2026-11-07 | R1; PR #1524 (WP-2204) closes as a source |
| Settings dialog | theme, density and number format | 2026-11-07 | R1 for the theme; density and number format with the first piece that draws what they change |
| Bottom panel and status bar | Console (the Python the window runs) and History, toggled from the status bar along the window's foot | 2026-11-07 | R1 and R5; PR #1521 (WP-2206, WP-2207) closes as a source |
| Fixing plan stages | a plan stage that fixes as well as frees: `StageSpec.turn_off`, a `fix` clause in `.rxt` | 2026-11-09 | [WP-2208](../wp/2208-a-plan-stage-that-fixes.md), PR #1520, merged 2026-11-11; R4 draws it |
| Edit recovery | unapplied edits kept across a close or crash in a recovery copy in rietx's state directory, apart from the project, as editors such as VS Code keep theirs | 2026-11-09 | [WP-2209](../wp/2209-unapplied-edits-survive-a-close.md), PR #1523, merged 2026-11-11; its follow-up [WP-2213](../wp/2213-text-and-model-edits-join-the-recovery-copy.md) (the Text buffer and Model forms join the copy) shrinks, since R4 makes a Text edit a pending edit |
| Fit statistics in the action bar | Rwp, GoF and the not-a-fit judgement beside Refine while the graphs are hidden ("try B") | 2026-11-09 | R2; PR #1518 (WP-2210) closes as a source |
| The graph window | curves switched from a legend, a view menu, the fitted range and excluded regions as plot objects | 2026-11-10 | R2; the branch `wp2213-the-graph-window` is a source, and its WP number is retired because PR #1523 files WP-2213 |

Three decisions went to the maintainer before the piece that needs them. The first is now ruled, and two still wait:

- A plan stage that fixes as well as frees. The maintainer wants it (2026-11-07); in rietx it is
  a `turn_off` list on `StageSpec` and a `fix` clause in `.rxt`, both stored-format changes, so
  piece 3 asked for the go-ahead in its WP. Ruled required on 2026-11-09, the mechanism left to
  Claude; WP-2208 built it, merged 2026-11-11 in PR #1520.
- A background drawn through points the user places. rietx has no such background type; a new
  one is a stored-format change.
- A text file kept beside the project, which the maintainer deferred to the port on 2026-11-07.

### Owed to the port

The design rounds found these rietx defects and left them for the port, by the maintainer's
ruling of 2026-11-08 that the design work changes nothing on `main`. Each becomes work in the
rebuild piece that touches it, or a WP of its own.

- The extinction screen is refused on a project with no phase: `GuiSession.run` groups the kind
  `extinction` with the refinement kinds, though WP-1027 ruled the screen ungated, and the
  refusal reads "a extinction run". WP-2124 took `extinction` out of the refusal, so a
  pattern-only project screens a candidate.
- Adopt is gated to `best_or_none()` (`ADOPT_GATED`). The maintainer ruled on 2026-11-08 that a
  person may adopt any candidate, with its grade and caveats shown beside Adopt and recorded in
  the history node. WP-2124 lifted the gate on the route and WP-2130 offers Adopt on every row.
- The Peaks panel hides `systems_searched`, `search_complete` and the run-level `INDEX_*`
  diagnostics whenever there are candidates, against WP-1042's rule that what was not reached
  is said loudly. WP-2130 says it above the list in every case.
- `.rxt` renders no block for user variables, and its tie refusal names only symmetry ties.
  WP-2121 made the refusal name a user tie's own verbs, `ref.untie()` and `ref.tie()`. The
  block for user variables is still owed.
- The Le Bail check's absent lines arrive in its own refined frame, about 0.011° from the
  candidate's ticks on fluorapatite; they should be served as tick indices.
- `supercell_checks` names a relation for 8 of fluorapatite's 12 candidates (measured by WP-2124
  on 63d7c120a; naming the other four is WP-2124's follow-up); lattice relations between
  candidates ("c doubled", "a × √3", "same cell") belong in rietx.
- `PeakEditor.curves` serves only each group's sum; per-line curves need a route. PR #1526
  (WP-2202) serves them as `lines` on each group, and R6 takes that half.
- `set_flags(..., use_for_indexing=True)` forgets which flags a person overruled.
- `--plot-peak` (purple) loses to the data crosses as a mark colour. WP-2130 measured the ruled
  blue against the palette and took the choice to the maintainer, who ruled on 2026-11-09 that it
  moves with the palette piece, since the blue was chosen as the complement of orange fits.
  WP-2200 carried it, merged 2026-11-11 in PR #1517.
- The pick route takes only `shoulders`; the 2θ range and `flag_contamination` need to reach it.
  WP-2124 added both to the route, and `pick_options` records all three.
- Right-click on a plot object opens no context menu, and peak edits have no undo, though the
  maintainer adopted both rules on 2026-11-08. R1 builds the context-menu service; R6 owes the
  peak edits' undo.
- A GUI series lives in session memory only; several series gaps wait on the series fitting
  now changing on `main`.
- The Model and Text panels keep their own Apply beside the action bar's. R2 and R4 give the
  window one Apply.
- A run started from the Report or Series panel, or by the `.` key, does not apply the
  Parameters edits waiting in the action bar. The bar's Refine, the `r` key (WP-2123) and the
  Plan panel's `Run this stage` (WP-2127) do.
- The Parameters panel has no formula editor: no route serves `add_variable` or an expression
  tie, so the popover's "=" button (design 13) waits for both routes (WP-2126's follow-up).
- The popover offers no limits for a coordinate DOF, whose entry stores no `min`/`max`, and
  refuses them by name for a texture or background coefficient. Both need the path-to-model map
  that lives only inside `ParameterTable`'s write-back (WP-2126's follow-up).
- The panel's Apply sends `PATCH /api/params` and then one `POST /api/structure/position` per
  moved atom, so a refused position leaves the PATCH applied. A `positions` arm on the PATCH
  makes it one rehearsed request; the Model panel's value-then-model sequence has the same shape
  (WP-2126's follow-up).
- No group toggle in the Parameters panel shows which plan stage frees it. WP-2126 left the
  badges to the Plan tab and WP-2127 left them to the panel. R2 draws them.
- `gui/src/lib/spacegroup.ts:typesetSpaceGroup` (WP-2126) and
  `gui/src/lib/symmetry.ts:symbolTokens` (WP-2131) typeset a space-group symbol by the same
  rules into two token types. One should go.
- The Plan tab adds a glob by typing it. The prototype's grouped picker ("Cell (2)", "All Biso")
  and its "never freed" row both need the refinable set, which `GET /api/plan/resolve` does not
  serve. Its "Save as new plan…" needs a store for named plans, and rietx keeps one plan per
  project (WP-2127's non-goals).
- New project cannot add a phase from a TOPAS, FullProf or GSAS-II project file, which the
  round-9 design offers. A browser upload carries one file, and such a project names a data
  file beside it (WP-2131's settled call 2).
- `gui/CLAUDE.md` still holds 36 visual rules that belong in `gui/STYLE.md`. WP-2134's § What
  `gui/STYLE.md` covers of these sorts them: drop the covered ones from the rulebook, merge the
  partly covered ones into the guide, and bring the departures and the uncovered ones to the
  maintainer, since visual questions go to him (WP-2134's and WP-2142's next step).
- `rietx watch`'s state pills set their text in a state colour over an 18 % wash of the same
  colour. On the light theme `.running` is 3.90:1 and `.cancelled` 4.45:1, under AA. The fix
  is a pill design call, so WP-2200 left it for whichever piece redraws the chips.

## Acceptance

Written at the open, and adjusted on 2026-11-11 for the rebuild. Each row is checked when its
piece closes, and the milestone completes when all are met on one tree. "Every piece" means every
rebuild piece, on the new page. Rows 2 and 13 moved to the swap with the rebuild ruling; rows 10
and 11 now review whole screens at a piece's end.

| # | Row | Piece | How it is measured |
|---|---|---|---|
| 1 | No click moves the layout unless it asks to. Expanding, collapsing, switching a tab and jumping ask; editing a value, ticking a box and choosing a mode do not | R1, then every piece | the layout-shift browser test clicks every control on a fresh page in each starting state and compares element boxes before and after |
| 2 | Every panel and route of the GUI before the milestone stays reachable | the swap | `tests/test_gui_manual.py`'s partitions, plus a browser pass that opens every tab |
| 3 | A choice never looks like an action: every segmented choice is a sunken track with one raised option, and actions are outlined or filled buttons | R1, then every piece | `lib/style.test.ts` and a look at the screenshots |
| 4 | Colour values live in `src/rietx/viz/theme.py`, and `gui/src/tokens.css` is generated from it | R1, then every piece | `tests/test_gui_palette.py` |
| 5 | Below a measured width the window is one column, graphs above the model, with no sideways scroll of the page | R1 | the browser test at 420 px and at the threshold |
| 6 | The graphs say what they show, so a preview never reads as a changed fit | R2, R3 | the title line's text in each state, asserted in vitest |
| 7 | One atom is one row, and switching a number between scientific and plain moves nothing | R2 | the layout-shift test over the Parameters panel |
| 8 | The plan reads top to bottom as a recipe, on the existing plan routes | R4 | a browser pass over a five-stage plan |
| 9 | A preview is drawn at the last fit's scale and never moves the comparison | R3 | the preview route's timing and a browser pass |
| 10 | The maintainer has looked at each screen beside the prototype at its piece's end | every piece | the piece's last PR |
| 11 | A piece's last PR puts whole-window screenshots at 1440 × 900, light and dark, beside the prototype's at the same size, a region in question boxed with a zoomed crop | every piece | a review aid in the PR, not a pixel test |
| 12 | Every rule in `gui/STYLE.md` names its motive and who stated it, and names only tokens and tests that exist | 2142, then every piece | `tests/test_gui_style_guide.py` |
| 13 | Every row of WP-2214's inventory whose home is not "removed" can be reached on the new page | the swap | a browser pass that walks the inventory, recorded in the swap's PR |
