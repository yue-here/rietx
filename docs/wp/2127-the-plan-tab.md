# WP-2127 — the Plan tab

Milestone: gui-overhaul · Status: ✅ 2026-11-09 — the Plan tab merged in #1483; the fixing stage is the milestone's row, the prototype's picker an owed item
Depends on: 2123 (the layout shell, PR #1476)

## Goal

The Plan tab in `rietx gui` reads as a recipe, top to bottom, one stage per row: first the
plan frees these parameters, then those. Each stage shows the parameters it takes out of the
user's hands. A three-line handle reorders stages by drag, a plan menu chooses a preset from
`PLAN_INFO`, and a person can build a plan: add and remove stages, add and remove a stage's
globs. Plan edits ride the action bar the shell built, so one Apply saves them and one Refine
runs them. The tab runs on the existing routes: `GET`/`PUT /api/plan`, `GET /api/plan/resolve`
and `POST /api/run` with kind `stage` or `fit`.

## Context

### Where the tab is today

`gui/src/panels/Plan.svelte` (WP-1011, WP-1208) draws a preset `<select>`, `Run all`, and while
the plan is edited `Save plan` and `Revert`. Under them sit three paragraphs of explanation, the
preset's description and the free count at the end. Each stage is a bordered card: a `⠿` grip
for HTML drag-and-drop, the name, a × that removes the stage, a comma-separated glob field
labelled `frees`, and a ladder line (`+2 → 2 free · Rwp 95.35%`) that opens to the paths the
stage frees, those already free and those it matches but holds. Every resolved fact hides the
moment the plan on screen differs from the server's. `Run this stage` sends the stage as it
stands on screen. Advanced mode adds a box per `StageSpec` field and the correlation guard.

The shell (WP-2123, PR #1476) put an action bar under every right-hand tab. It applies the
Parameters panel's pending edits and refines, one cycle on the ticked set or the staged plan.
The plan's edits do not ride it yet: the tab keeps its own Save, and the milestone's owed list
records that a run started from the Plan tab does not apply the Parameters edits waiting in the
bar.

### The designs, and the rulings they rest on

The maintainer designed the overhaul with Claude in twelve rounds of prototypes between
2026-11-06 and 2026-11-08 and reviewed each on screen. The prototypes are not published, so each
design this WP builds is restated here with its ruling.

1. **The plan shows which parameters it takes out of the user's hands, and users can build
   plans.** Ruled 2026-11-07 (fourth review). In rietx a plan replaces the vary flags: `fit`
   starts every plan from a table where nothing is free and frees only what the stages name
   (`_prepare_table(restore=False)`, WP-1208). So a stage's freed list is exactly what the plan
   decides on the user's behalf, and `set_aside` names the hand-freed rows the plan will hold.
2. **The plan has its own tab and reads as a recipe.** Ruled 2026-11-07 (fifth review): "Humans
   will read it as a list/recipe. First we free x, then y, then z." One stage is one row, read
   top to bottom.
3. **A drag handle of three stacked lines reorders stages, and a plan menu chooses plans.** Ruled
   2026-11-07 (sixth review). In the prototype the handle also answers the arrow keys when
   focused, the lifted stage follows the pointer and the others slide aside.
4. **A stage may fix as well as free.** Ruled 2026-11-07 (sixth review), and ruled required on
   2026-11-09. Not built here: a follow-up WP builds it. See *Ruled: a stage that fixes* below.
5. **No permanent explanatory text.** Ruled 2026-11-07 (sixth review), repeated 2026-11-08
   ("again, too much AI prose"): an explanation lives in a tooltip or a help box. Today's three
   paragraphs go.
6. **A choice must not look like an action.** Ruled 2026-11-07 (fifth review). The workshop's
   handover named the clash it leaves here: the prototype's stage items are removable chips, and
   `gui/CLAUDE.md` says a `.chip` never acts and a verb on a chip sits beside it. So a glob is a
   chip, a fact, and its × is a `button.ghost` beside it.
7. **The panel ends in Apply and "Apply and refine".** Ruled 2026-11-07 (fourth review), built
   by WP-2123. In the prototype an edited plan counts as one pending edit in that bar, Apply
   saves it and Revert drops it.
8. **No click moves the layout unless it asks to.** Ruled 2026-11-07 (third review), adopted as
   interaction rule 8 on 2026-11-08. Adding and deleting a stage, opening a stage's path list
   and the drag ask; editing a name or a glob, choosing a preset and pressing a stage's run
   button do not.
9. **Every edit can be undone.** Adopted as interaction rule 10 on 2026-11-08. Plan edits are
   settings in `project.json` and make no history node, so undo here is the panel's own stack.

A browser check clicks as a person does (`page.click`, `page.mouse`, `page.keyboard`), and the
drag is a real `page.mouse` drag. The server serves the committed dist, so every browser pass
follows `npm --prefix gui run build`.

### Rulebook seams

- **Registers** (`gui/CLAUDE.md` § House style): size, padding and radius belong to the register.
  The grip is not a button register; it is a focusable handle drawn by the panel.
- **The ladder** (`gui/CLAUDE.md`, WP-1208): the numbers come from `GET /api/plan/resolve`,
  never from the client's fnmatch port. A dirty plan has no resolved facts. This WP narrows that
  to the stages that changed: a stage's facts depend only on the stages up to it, so the leading
  stages that equal the saved plan's keep theirs.
- **Help keys** (`lib/help.test.ts`): `plans:{chosen.name}` and `stage_fields:{key}` stay.
- **One authority per plan**: `ProjectDoc.plan`, written by `PUT /api/plan`. The panel holds an
  unsaved copy and nothing else.

### Ruled: a stage that fixes

The maintainer ruled on 2026-11-07 that a stage may fix as well as free. In rietx that is a
stored-format change, so it waited for a go-ahead and its own WP.

**Ruled 2026-11-09 by Yue Wu**, verbatim: "specifically, I'm thinking of a common case where the
profile will be fixed with a pawley refinement, then locked; after that, the structural
parameters are released. Also the case for series refinements (as will be decided soon in the
series wps). The mechanism can be left to your best judgement but the functionality is
required."

So the functionality is required, and it is a follow-up WP, not PR #1483. The mechanism is
Claude's to settle. The brief recommended a `StageSpec.turn_off` list, shown as `fix` in `.rxt`,
with the closing stage re-solving the plan's end state rather than the union of every `turn_on`.
The follow-up WP takes two acceptance cases from the ruling:

1. A Pawley fit settles the profile, the profile is then fixed, and a Rietveld plan frees the
   structure. This crosses a mode change. `StageSpec` carries no mode field today (mode is the
   fit's), so the WP first checks whether one plan can carry the case or it spans two fits,
   where `hold` (WP-1435's verb that keeps a parameter fixed across plans) may be the mechanism.
2. Series refinements, which the series WPs will define.

The brief's fields, for the follow-up WP to confirm or replace:

- `StageSpec.turn_off: list[str] = []` in `src/rietx/schemas/plan.py`, dot-path globs this
  stage fixes after it frees `turn_on`, and the same field on the `Stage` dataclass
  (`strategy/staged.py`), validated through `PlanSpec`/`StageSpec` as today.
- In `.rxt`, a `fix <globs>` clause on a stage line after `free` (`gui/textdoc.py`; the stage
  keys derive from `StageSpec`, and `lib/rxt.ts`'s stage words follow by pin).
- In `GET /api/plan/resolve`, a per-stage `fixes` list beside `frees`, `already` and `held`.
- The record of what a stage ran: `StageResult` and the `stage` history node's `NodeAction`
  carry `turn_off` beside `turn_on`, or a replay or cherry-pick frees what the run fixed.

A file carrying `turn_off` would not open in an older rietx (`extra="forbid"`), which is what
makes it a stored-format change.

### The tier of each rule this WP adds

None is a heuristic in the sense of `docs/milestones/generality.md` § The rule: nothing here
reads the data or decides for a fit. The resolved facts stay the server's.

### Calls settled by Claude

No ruling covered these, so each took the smallest neutral option. Each is "settled by Claude,
reversible", with its alternative, and waits for the maintainer's review of the PR.

1. **Plan edits ride the action bar as one pending edit.** Apply stores the plan after the
   Parameters edits, Revert drops both, and Refine applies first. The tab's own `Save plan`,
   `Revert` and `Run all` are gone, so a view has one Apply. Alternative: keep a Save button in
   the tab beside the bar's.
2. **A preset pick is stored at once and is undone with ⌘Z.** Only the server expands a preset
   through the mode, so a pick held back until Apply would show stages nobody has seen.
   Alternative: hold the pick until Apply, which needs a route that returns the expansion
   without storing it.
3. **A glob is a mono `.chip` with a ghost × beside it**, added by typing into an "add a glob"
   field and pressing Enter (space or comma separates several). Alternative: the prototype's
   grouped picker, a non-goal above.
4. **The grip is a focusable three-line span, not a button register.** A pointer drag lifts the
   row and slides the others; ArrowUp and ArrowDown move it one place when focused.
   Alternative: HTML drag-and-drop, which draws a ghost image and has no keyboard route.
5. **An edit keeps the resolved facts of the unchanged leading stages.** A stage's ladder line
   depends only on the stages above it, so they stay true; every stage from the first change
   down reads "not applied". Alternative: WP-1208's rule, which blanked the whole ladder.
6. **The closing stage is a last, unnumbered row** that reads "Frees everything above", with
   its meaning in a tooltip. An edit blanks its Rwp and the set-aside list's paths and keeps
   both rows, because a row that vanished would move every row below it. Alternative: hide
   both on an edit.
7. **The blurbs became tooltips.** A "Preset" label beside the menu carries the plan's help
   entry; the menu reads "<title>, edited" once the stages differ from the preset. Alternative:
   one line of description under the menu.
8. **Undo is ⌘Z and ⇧⌘Z in the tab outside a text field, plus two palette commands.** A text
   field keeps its own undo, and one burst of typing in one field is one step. Alternative: an
   Undo button in the plan bar.
9. **`Run this stage` applies the Parameters edits first**, the way Refine does. This closes
   the Plan half of the milestone's owed item about a run discarding pending edits.
10. **`+ Stage` appends "stage N" and focuses its name**; the last stage has no ×.
11. **Stage names are shown as stored**, in mono, since a name is what the history node and
    the `.rxt` document carry.
12. **Rows are separated by a rule, not drawn as cards**, and the selected stage's number takes
    `--accent`.

## Non-goals

- A stage that fixes (above).
- Saving a plan under a name of the user's own. The prototype's menu had "Save as new plan…" and
  "Delete this plan"; rietx stores one plan per project and has no store for named plans.
- The prototype's picker, which offers named groups ("Cell (2)", "All Biso") and moves a
  parameter from any other stage. It needs family names the corpus has as labels and a route
  for the refinable set. Typing a glob is the route here.
- A "never freed" row. It needs the refinable set, which `GET /api/plan/resolve` does not serve.
- Stage badges in the Parameters panel (piece 2, WP-2126).

## Tasks

- [x] File the WP.
- [x] `lib/plan.ts`: moving a stage, the drop index from row midpoints, the resolved prefix, the
  undo stack, adding and removing a glob; with vitest.
- [x] The tab redrawn as a recipe: the plan bar (preset menu, + Stage), one row per stage (grip,
  number, name, run, ×), the glob chips with × beside them and an add field, the ladder line,
  the closing stage, the set-aside list; no permanent text.
- [x] The grip: pointer drag with the lifted row following the pointer, arrow keys when focused.
- [x] Plan edits in the action bar: one pending edit, Apply saves, Revert drops, Refine applies
  first; `Run this stage` applies the Parameters edits first; `Save plan`, `Revert` and
  `Run all` retired from the tab.
- [x] Undo and redo of plan edits: ⌘Z and ⇧⌘Z in the tab outside a text field, and the palette.
- [x] The layout browser test extended to the Plan tab: every control clicked, a real drag.
- [x] The dist rebuilt; the GUI chapters and the screenshots the tab changes.
- [x] Skill: none. The agent skill drives the python API, and no route changed.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_manual.py tests/test_gui_palette.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The layout-shift test reports no unasked-for movement on the Plan tab, a real drag reorders a
stage, and the milestone's row 8 (a five-stage plan read top to bottom) holds in a browser pass.

## References

- The maintainer's rulings of 2026-11-07 and 2026-11-08, restated above with their dates.
- WP-1208 (the ladder), WP-2123 (the shell).
- `docs/practice.md` § Staging and what a stage holds: MAUD's refinement wizard is the one
  surveyed program that offers cumulative stages in a GUI. § The window layout of a GUI.

## Handover log

- **2026-11-10** — closed. PR #1483 merged on 2026-11-09, so the Plan tab reads as a recipe on
  `main` and plan edits wait in the action bar beside the Parameters edits. The stage that fixes
  as well as frees is the one large thing left. The maintainer ruled it required, with the
  mechanism Claude's, and it is the row "Fixing plan stages" in
  `docs/milestones/gui-overhaul.md` § Designed, not yet filed. That row points back here for the
  ruling, the two acceptance cases and the brief's fields.

  *Leftovers, and where each went.* The fixing stage: the milestone's row above. The
  prototype's grouped picker and its "never freed" row both need the refinable set from a route,
  so they went to § Owed to the port as one item. Named plans ("Save as new plan…") need a store
  rietx does not have, and are noted in that item. The stage badges in the Parameters panel went
  to § Owed to the port with WP-2126's close. The twelve settled calls were reviewed with the
  PR at its merge. The narrative went to `docs/milestones/v1.12.md`.

  Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
  Next: none here. The fixing stage is filed when the milestone reaches its row.
- **2026-11-09** — the maintainer ruled the fixing stage required (§ Ruled: a stage that fixes):
  a follow-up WP, not this PR, with the mechanism Claude's to settle and two acceptance cases,
  Pawley-then-Rietveld and series. Recorded only; nothing built.
- **2026-11-09** — built by a ghostshift runner; PR #1483. The Plan tab now reads as a
  recipe: one row per stage, a handle that drags it, its globs as chips each with a × beside
  it, and the ladder line saying what the stage frees and holds. A person can build a plan in
  the tab (add and remove stages, rename them, add and remove globs, pick a preset) and undo
  each step. A plan edit no longer has a Save button of its own: it waits in the shell's action
  bar as one pending edit beside the Parameters edits, and `Run this stage` applies those edits
  first. A stage that fixes is not built and waits on the maintainer (§ Context).
  - *Done*: `lib/plan.ts` with vitest; `Plan.svelte` rewritten; `App.svelte` routes the plan
    through the action bar and the palette (`plan-undo`, `plan-redo`); the layout browser test
    clicks every plan control at both widths and drags a stage with a real mouse; the manual's
    Plan section, the two plan screenshots, `gui/CLAUDE.md`'s ladder rule and the milestone's
    owed item follow. Twelve visual and interaction calls are listed under § Calls settled by
    Claude for the maintainer's review.
  - *Review* (`/code-review high --fix`): eight fixes landed as one commit. A plan load
    overtaken by an Apply is dropped, the resolved facts are tied to the stages they describe,
    undo does nothing mid-run, a refused preset pick records no undo step, a reorder carries the
    selection and a half-typed glob, and the panel starts fresh for each opened project.
    Declined: dropping an unsaved plan edit when the mode changes. Keeping it is the panel's
    stated behaviour and loses nothing; a person can Revert.
  - *Measured*: fast suite on the final tree (origin/main merged, no change), worktree venv `[dev]` plus
    playwright, macOS arm64: 14479 passed, 410 skipped, 32 xfailed, exit 0, through the shift's
    serial queue. vitest 625 passed; svelte-check 0 errors; the layout browser file 17 passed;
    ruff clean; `tests.reader_output` exit 0. One local run's seconds for the added tests: the
    plan sweep 71.6 s over two widths, the typing test 4.9 s, the drag 1.5 s. The sweep joins the
    fast tier's tail and stays unmarked, because it is the Plan tab's layout gate and a PR's CI
    runs the fast tier alone.
  - *Gotchas*: on macOS the End key scrolls the nearest scroller rather than moving the caret
    in a text field, and the scroll is smooth, so it lands during the next keystroke. A browser
    test that types into a field inside a scroller does not press End.
  - Next: the maintainer reviews the settled calls and rules on the fixing stage. #1476 merges
    first; this PR then merges after it.
- **2026-11-09** — filed by a ghostshift runner as piece 3 of the gui-overhaul milestone. No
  open WP owned the Plan tab: WP-2123 lists it as a non-goal and WP-2126 is the Parameters panel.
  The milestone claims 22xx for its later pieces, and the shift numbered this one 2127, after
  2125 and 2126, which other runners filed the same day. Next: start the checklist.
