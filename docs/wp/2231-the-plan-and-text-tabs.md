# WP-2231 — the Plan and Text tabs at `/next`: a plan read as a recipe with Free and Fix rows, and a text buffer whose edits ride the action bar

Milestone: gui-overhaul · Status: 🔄 2026-11-21 — the Text tab in review (#1763); the maintainer's look at both tabs waits
Depends on: 2218 (hand fitting and the other graphs)
Priority: P2 2026-11-21 — a feature the open milestone was opened for: R4, the next piece after R3

## Goal

The rebuilt GUI at `/next` gains its Plan and Text tabs. The Plan tab reads the plan as a
recipe, one stage per row: first the plan frees these parameters, then those, and here it fixes
these. A person builds a plan there from named groups rather than typed globs. The Text tab
shows the project as `.rxt` text, and a typed change is a pending edit in the action bar beside
the Parameters panel's, so the window has one Apply. The piece is judged whole beside the
prototype at 1440 × 900, light and dark.

## Context

WP-2214 is the plan. Its § The pieces names R4 and the inventory rows it owns: 104-117 (the Plan
tab) and 139-146 (the Text tab). Acceptance row 8 of the milestone is R4's: the plan reads top
to bottom as a recipe, on the existing plan routes, checked by a browser pass over a five-stage
plan.

The routes exist, with one addition. The plan is `GET`/`PUT /api/plan`, the presets
`GET /api/plans`, what each stage does `GET /api/plan/resolve`, and a single stage
`POST /api/run` with kind `stage`. WP-2208 (PR #1520) added `turn_off` to `StageSpec` and
`fixes` to the resolve route. The prototype's "Never freed" row needs the refinable rows no
stage frees. Only the server can say which, because a glob's matches minus the tied, locked and
mode-fixed rows is `ParameterTable.set_vary`'s answer (gui/CLAUDE.md, WP-1208). So the resolve
route gains one list, `never_freed`. The grouped picker reads the refinable set off
`GET /api/params`, which already carries `refinable` on every row. The Text tab runs on
`GET`/`POST /api/textdoc` and `lib/sync.ts` as today. Nothing R4 changes reaches what a fit
prints or returns.

R2 built what R4 reuses: the frame's right-hand tab strip, the action bar with its pending count
and one Apply, the menu and context-menu component (`next/Menu.svelte`), and the recovery offer.
Today's panels for the same jobs (`panels/Plan.svelte`, WP-2127; `panels/Text.svelte`, WP-1013)
move into `gui/src/next/` before R4 changes them, so today's page does not move (gui/CLAUDE.md,
the rule for a shared panel). The frame carries the recovery copy's Plan and Text arms without
drawing them today (`Frame.svelte`'s `carried`); R4 makes both arms this page's own.

### The rulings R4 rests on, restated

- **The prototype is the ruling for every visible difference** (the maintainer, 2026-11-11,
  "Merge, then polish"). Where it would break a written rule, the rule wins (`gui/STYLE.md`
  principle 9), and the difference is listed in § Questions.
- **Chrome text that serves no decision goes** (2026-11-10, the "infoslop" ruling). WP-2214
  § Questions 4 ruled on 2026-11-11 that its list is settled piece by piece. R4's rows on it
  are 146 (the Text tab's footer prose).
- **The plan has its own tab and reads as a recipe** (2026-11-07, fifth review): "Humans will
  read it as a list/recipe. First we free x, then y, then z, then fix a, refine b, etc." One
  stage is one row.
- **The plan shows which parameters it takes out of the user's hands, and users can build
  plans** (2026-11-07, fourth review).
- **A drag handle of three stacked lines reorders stages, and a plan menu chooses plans**
  (2026-11-07, sixth review).
- **A stage may fix as well as free** (2026-11-07, sixth review; required 2026-11-09, "the
  mechanism can be left to your best judgement but the functionality is required"). WP-2208
  built the mechanism; R4 draws the Fix row.
- **No permanent explanatory text** (2026-11-07, repeated 2026-11-08). An explanation lives in
  a tooltip, the help popover or the tab's `?` box.
- **Every edit can be undone** (interaction rule 10, adopted 2026-11-08). Plan edits are
  settings and make no history node, so the panel keeps its own stack (WP-2127).
- **Right-click opens a context menu holding the object's bar actions** (interaction rule 12,
  adopted 2026-11-08). A stage's Run this stage and Stage settings… sit on its ⋯ menu and its
  context menu (row 107, row 113).
- **A control exists only while it can act** (WP-2214's ways of hiding a control). Re-read
  appears only inside the stale notice (row 142).
- **A Text edit is a pending edit** (WP-2214 row 141). Today's Text tab keeps its own Apply
  beside the action bar's, which the milestone's owed list names as two Apply buttons in one
  view.
- **Staged or single must be visible** (the maintainer, 2026-11-19, on WP-2224: "it should be
  clear to users whether the run is staged or single", and "there should be visual feedback in
  the gui"). WP-2227 owns the feedback and puts three placement questions to the maintainer
  before any building. They wait at R4's review point (§ Questions 1).

### How each screen reads in the prototype, restated

- **Plan.** A bar at the top holds the plan menu, a button named for the plan with a dot when
  it is edited and a caret, and `+ Stage` at the right. The menu lists "This project's plan",
  then the rietx presets under a heading, then Save as new plan…, Revert to the plan's saved
  form and Delete this plan. Each stage is a block under a hairline. Its first line holds the
  three-line grip, the stage number in a small outlined accent badge, the name in an input that
  shows its border only on hover and focus, and a delete icon. Its second line reads "Free" in
  the muted ink, then one rounded chip per thing it frees, each with a ×, then `+ Add`. A third
  line, "Fix", is drawn only when the stage fixes something. A chip fixing what is not free at
  that point is marked. `+ Add` opens a picker 320 px wide: a Free or Fix choice, a search box,
  then "Groups" ("Cell (2)", "All Biso") and "Parameters", each option saying "in this stage" or
  "moves from stage 2". Fix offers only what is free by that stage. The last block has a dashed
  badge and "Never freed", listing what no stage frees, or "Nothing". The grip answers ↑ and ↓
  when focused, and a dragged stage follows the pointer while the others slide aside.
- **Text.** A bar names the file (`fap.rxt`), with a count of unreadable lines at the right. The
  editor fills the tab: line numbers in the faint ink, keywords in the accent's text role, the
  refine flag `@` in green, comments faint and italic. An edited value is highlighted and an
  unreadable line underlined. Its `?` box says a changed number or refine flag becomes a pending
  edit, as in Parameters.

### Inherited

- **#1652 item 1: the iteration field takes 0.** WP-1947 made `Stage` and `StageSpec` refuse
  `max_iter < 1`, so the server answers a plan holding 0 with a 4xx at
  `plan.stages.N.max_iter`. Today's field in `panels/Plan.svelte` has no `min`, so a person
  learns it only from the error. R4's Stage settings… popover gives the field `min="1"`, and
  today's panel takes the same attribute in the same rebuilt dist. Item 2 of #1652 (a manual
  paragraph on `predict`) is not GUI work and stays with the issue.
- **A restored draft can carry a stale hold (review of #1683, 2026-11-21, finding 1, low).**
  `restoreDraft` in `gui/src/next/Params.svelte` (about :438-446) restores pending edits without
  the reload-time `dropPending` (about :262-267), which runs only when the head moves. A draft
  marked "moved" that holds an edit on a path the head no longer has, such as a hold on
  `instrument.background.c7` after the terms were cut to six, survives Restore. The background
  band sends every pending hold, so it then reads "Band refused: no parameter to hold", and
  Apply is refused until Revert. Fix: run `dropPending` against the current rows at the end of
  `restoreDraft`. Put it in `Params.svelte`, never in `Frame.svelte`'s `restoreKept` block,
  which this WP edits.
  Fixed in the first PR (#1755).
- **A glob hold matching nothing refuses the band (same review, finding 2, low).**
  `src/rietx/gui/background.py` (about :214-219) answers `GET /api/background` with 400 "no
  parameter to hold" for a pending glob matching no row, while `Refinement.hold` takes the same
  glob as an empty sweep (`refine.py` about :4293), so the band refuses a hold that Apply
  accepts. Today's `/next` makes such a glob only through a restored draft. Fix: skip globs
  that match nothing and refuse only literal paths, as `Refinement.hold` does. Probe:
  `phases.0.atoms.*.adp.*` on `fap`.
  Fixed in the first PR (#1755).
- **2026-11-21, issue triage (#1656 item 2): the register guard does not read `/next`.**
  `styledFiles()` in `gui/src/lib/style.test.ts` lists `App.svelte` and `panels/*.svelte`
  only. So the milestone's acceptance row 3 ("R1, then every piece", measured by
  `lib/style.test.ts`) is not measured on the new page at all. Checked at `c1033a0e8` with a
  python copy of the guard's second assertion over the 17 files in `gui/src/next/`: 4 hits
  under today's `REGISTERS`, 6 with `.ib` and `.mbtn` added. Five are in this WP's
  `next/Plan.svelte`: `.ib.words` sets padding and font-size, and `button.op` sets padding,
  radius and font-size. The sixth is `.jump .link { padding }` in `next/Params.svelte`.
  `gui/STYLE.md` settles half of the issue's question. Its Components table lists the icon
  button as a kind, so `.ib` is a register under principle 3 ([Yue, WP-1201]). It has no
  menu-button row, so `.mbtn` is not yet settled. It also says the drawings live in
  `app.css`, while the rebuild draws `.ib` and `.mbtn` in `next/next.css`. Fix: extend
  `styledFiles()` to `next/*.svelte`, add `.ib` (and `.mbtn` once STYLE.md gains its row) to
  `REGISTERS`, name `next.css` as the rebuild's home for a register's geometry, and move the
  six overrides there as named variants. Moving them changes no pixel.

## Tasks

- [x] File the WP; the milestone's R4 row names it.
- [x] The Plan tab at `/next` (rows 104-117), from `panels/Plan.svelte`, and `never_freed` on
  `GET /api/plan/resolve`. The plan menu (presets, Revert, Plan settings… with the correlation
  guard); `+ Stage`; each stage's grip, badge, name, ⋯ menu and context menu (Run this stage,
  Stage settings…, Delete), delete icon; the Free and Fix rows of named chips; `+ Add` with the
  grouped picker; the stage's Rwp and free count at the row's right with the lists in a
  disclosure; "not applied"; the closing stage; Never freed; the hand-freed set-aside list;
  ⌘Z and ⇧⌘Z; `.` runs the selected stage; the plan counted in the action bar and kept in the
  recovery copy; `min="1"` on the iteration field (#1652 item 1). A vitest mount case and a
  browser pass over a five-stage plan with a real drag (acceptance row 8). The first PR.
- [x] The Text tab at `/next` (rows 139-146), from `panels/Text.svelte`. The file's name and
  its sync word on the title line; a typed change counted as one pending edit in the action
  bar, applied by its Apply and by ⌘Enter; Re-read inside the stale notice; one-line notices;
  problems in the gutter and in the list under the editor; the `?` box; the recovery copy's
  text arm offered and restored here. A vitest mount case and a browser pass that types a
  value and applies it from the bar. The second PR.
- [x] Screenshots at 1440 × 900, light and dark, under `docs/wp/2231-screenshots/`, beside the
  prototype's at the same size in the runner's scratch, with an inventory of where each of
  today's Plan and Text features lives. The last PR waits on the maintainer's look.
  Taken in the second PR; the inventory is the folder's README.
- [x] The maintainer's look at R4 (§ Rulings, eight items), built in the third PR in the order
  7, 5, 6, 1, 2, 3, 8, 4, with the graph strip's `?` box beside the model strip's. The
  toggle's place and words wait for the maintainer (§ Questions 2).

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py tests/test_gui_style_guide.py tests/test_gui_palette.py
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## Rulings

Filled in as the maintainer answers § Questions.

**The maintainer's look at R4, 2026-11-21** (relayed by the shift lead; eight items, built in
the third PR in the order 7, 5, 6, 1, 2, 3, 8, 4):

1. **The √ and Δ/σ scale markers sit in the tick-label column, not in a gutter of their own**
   (option A). Each marker sits above its axis's top tick: √ over the intensity axis's top
   tick, Δ/σ over the difference strip's top tick. It must not collide with a tick label, must
   align to the tick column, and must survive a log or linear switch and a narrow panel. The
   difference marker reads Δ/σ always; the weighted flag changes only the axis title's words
   (WP-1029).
2. **The Difference legend entry is centred vertically on the difference strip**, as Observed
   and Last fit sit beside the main plot.
3. **The horizontal gridlines come back as the prototype draws them.**
4. **The Pattern graph gains a toggle between the last refined curve and the preview.** The
   maintainer: "can we have a toggle between last refined and preview?" Its placement and
   words follow the prototype where it has them; where no design gives them, the options go
   to the maintainer in screenshots.
5. **"Never freed" on the Plan tab is drawn as read-only chips** in the stage rows' chip
   style, not as a sentence.
6. **The Text tab has the `?` help box the other panels have.** This reverses § Settled 11.
7. **The Text tab's stale notice is reworded and Re-read becomes a Button.** The words were
   unclear and Re-read sat too close to them. Under `gui/STYLE.md` a Link goes somewhere and
   Re-read is an action, so it is a Button (outlined, `line-strong`, hover ground).
8. **A Text edit previews on the plot, as a slider move does.** This reverses § Settled 12.

Items 6 and 8 are reversals of calls a runner settled; both are recorded in the maintainer's
memory as reversals in one area (leaving out an affordance a sibling panel has).

## Questions

Filled in by the session that builds each PR. Question 1 is carried from WP-2227, unanswered.

1. **How a Refine shows whether it ran in one stage or in stages** (WP-2227, filed 2026-11-19
   from the maintainer's ruling on WP-2224). Since WP-2224, a second `fit` of a model the last
   fit converged runs one stage, `warm_refit`. It runs the plan in stages instead when the plan
   frees a parameter the converged fit held, or when the one stage is rejected. Today's GUI
   passes `refit="stages"` on every Refine, so it never runs the one stage, because after one
   no history node matches a rung of the plan on screen and the Plan tab's Rwp column goes
   blank. WP-2227 asks three placement questions, which wait for the maintainer at R4's review
   point and are not settled here:
   - (a) Where the feedback shows: the Plan tab's ladder, the status bar beside Rwp, the
     Console line, or several.
   - (b) What a one-stage re-fit's ladder looks like: one row standing in for the plan's
     stages, or the plan's rows with one Rwp spanning them.
   - (c) Whether a Refine that runs staged because of a released parameter names that
     parameter on screen.
   Until they are answered, `/next` keeps `refit="stages"`, so every Refine on the staged plan
   runs in stages, as today's page does.
2. **Where the toggle between the preview and the last fit sits, and what it says** (§ Rulings
   item 4). No design gives either. The third PR builds the most conventional form: a
   segmented choice `Show [Preview | Last fit]` on the Pattern graph's title line, as the
   Peaks graph's `Show` is. It shows only while a preview is in hand, and the line keeps its
   slot unseen at rest, so a preview appearing moves no control. Last fit draws the fit whole,
   as with no preview, so the difference strip, the ticks and the title's Rwp are the fit's.
   The choice returns to Preview when the preview goes. The alternative already on the page
   is the legend's own switches: a click on Last fit hides the grey curve, while the
   difference strip keeps the preview's residual. The cost of the built form is width. At
   1440 px the title line elides the last fit's Rwp to "9.2…" (its tooltip keeps the whole
   line). Pictures: `toggle-preview`, `toggle-last` and `toggle-legend` under
   `2231-screenshots/`. "Last fit" is the page's existing word for the curve, where the
   maintainer wrote "last refined".

## Settled by Claude

Filled in as each PR settles a value under `gui/STYLE.md` and the prototype.

The Plan tab (the first PR), most consequential first:

1. **A chip carries no count.** The prototype's chips read "Background (6)". Counting needs a
   matcher, and the client's matcher is a preview only (`lib/fnmatch.ts`, WP-1011), while what
   a stage frees is the server's (WP-1208). The stage's free count at the row's right is the
   server's number. The alternative is the prototype's count, previewed by the client's
   matcher over the refinable rows, as the picker's group counts are.
2. **A chip's words are a group's name or the help corpus's title, and its tooltip is the
   glob.** Grounds: a chip's words are the corpus's (WP-1209). A small table in
   `gui/src/next/plan.ts` (`GROUPS`) names the globs that span several families, such as
   `phases.*.cell.*` ("Cell"). A glob with neither shows itself in mono. One phase of several
   is prefixed with the phase's name. The alternative is the prototype's own short words
   ("Scale", "All Biso"), which the corpus does not hold.
3. **The plan menu has no "Save as new plan" or "Delete plan".** No store of named plans
   exists, so either item would be a verb without a route. The menu holds the presets as
   radio rows, Revert to the saved plan, and Plan settings….
4. **The picker's Fix side offers only what is free by that stage**, previewed from the stages
   above it and its own. A free glob another stage already frees says "moves from stage N",
   and choosing it moves it, so a plan frees each glob once. The stage's own glob is listed
   disabled, "in this stage".
5. **The closing stage is a block of its own** with a dashed ✓ badge, "Free Everything above",
   and its Rwp while the facts are current. **Never freed** follows it with a dashed – badge,
   family names with counts, from the route's new `never_freed`.
6. **Stage settings open as a floating form** from the stage's ⋯ menu or context menu. Each
   label is the field's help title, and a field with a default says `default` (WP-1206). The
   value column is 96 px, wide enough for that word.
7. **The edited mark is a 6 px dot in `--accent-ink`.** `--accent` may not fill
   (`tests/test_gui_palette.py`, WP-2200).
8. **"Rwp" is set in sans and its number in mono**, as the Pattern graph's title line sets it.
9. **The picker is 320 px wide and scrolls past 380 px**; its search box is 30 px high.
10. **A typed dot-path glob is offered as itself** at the top of the picker, when no group
    or parameter carries that glob, and Enter takes it. Grounds: today's panel took a typed
    glob (WP-2208), and a picker of named options alone would lose it. The alternative is
    the prototype's picker, which offers named options only.

The Text tab (the second PR), most consequential first:

11. **Reversed by the maintainer on 2026-11-21** (§ Rulings item 6); the third PR built the
    box. As first settled: **The `?` box is not built here.** The task line names it, and no panel on `/next` has
    one yet. WP-2215 settled that the tab strips' `?` boxes (WP-2214 row 246) wait for a
    help piece, and no WP owns that piece yet. A box drawn for the Text tab alone would put
    a control on the strip that the other three tabs lack. The footer's words are removed from the tab and kept here for that
    piece: "Rectangular selection: ⌥-drag. Everything applies through the same verbs the
    forms call, so a bulk edit lands as history nodes and is undone by a checkout." The
    prototype's box adds: "Change a number or a refine flag and it becomes a pending edit,
    as in Parameters. Edited values are highlighted; a line rietx cannot read is
    underlined." The alternative is a `?` button on the model strip now, drawn only on the
    Text tab.
12. **Reversed by the maintainer on 2026-11-21** (§ Rulings item 8); the third PR previews a
    typed number. As first settled: **The whole buffer is one pending edit, and a text edit
    draws no preview.** The
    prototype turns each changed value into an entry of the Parameters panel's pending set,
    so the Pattern graph previews it. Grounds: this WP's task line counts "a typed change"
    as one pending edit, and the document applies as one delta through the verbs a form
    calls (WP-1009, WP-1013). The alternative is the prototype's per-value edits, which
    would need the text parsed into parameter values on the client.
13. **The text applies first** when Apply sends several panels' edits. The buffer carries
    the revision it was typed against, and any other apply moves the head under it, which
    would make it stale (WP-1013: no merge). A path that both the text and the Parameters
    panel change takes the Parameters value, applied after it. Run this stage applies the
    text too, as it applies the other edits waiting in the bar. The alternative is the
    text last, which would refuse every combined Apply as stale.
14. **⌘⏎ inside the editor is Apply, never Refine.** Grounds: today's tab binds ⌘⏎ to its
    Apply (WP-1013), and the task line names it. The frame's own ⌘⏎ (Refine) now skips a key
    pressed in the editor; without that, ⌘⏎ on an unedited buffer started a fit. The
    alternative is the frame's meaning, Apply and refine, everywhere.
15. **An edited line's text is marked in the accent at 16 %**, over the text and not the
    gutter. The prototype marks the line in its soft accent, about 10 %, with the text in
    the accent's ink. The editor's active line is already the accent at 8 %, so 16 % keeps
    a mark apart on the line the caret is on. Lines are matched by a longest common
    subsequence, so an inserted line marks itself and not every line after it.
16. **A buffer the server reads as changing nothing applies by reading the rendering
    again.** A comment added is such an edit. The tab already says, before Apply, that an
    added comment will not survive it. The alternative is refusing Apply, which would leave
    an edit in the bar that no Apply clears.
17. **A stale or unreadable buffer reads "invalid edit" in the action bar**, with its reason
    in the tooltip, as a refused Parameters edit reads. It refuses Apply, Refine and Run
    this stage for every panel's edits, as an invalid Parameters edit does, until the text
    is re-read or reverted. The alternative is applying the other panels' edits and leaving
    the text waiting, which would make the bar's one Apply apply only part of what it
    counts.
18. **The tab's title names the file after the project**, `<name>.rxt`, from the project's
    path (`lib/filemenu.ts:projectStem`), as the File menu names the project.

The maintainer's look (the third PR), most consequential first:

19. **While both the Interactive tab and the Text tab hold a preview, the graphs draw the
    panel that answered last**, and fall back to the other's when that one is taken down.
    Curves and refusal always come from one panel. Grounds: the plot follows what the person
    touched last, as the Structure graph already follows the sliders. The alternative, the
    Text tab's always, was this PR's first draft; the code review found it left a slider
    drag invisible on the Pattern graph while the Structure graph moved.
20. **A buffer whose changes are only refine flags, settings or peak moves previews
    nothing**, and takes down a preview it had. Grounds: none of them moves a curve, and
    `POST /api/preview` takes values only. The values come from the validation route's own
    diff (`delta.values`), so the client parses no `.rxt`.
21. **The graph strip has a `?` box too**, at its right, in the prototype's words cut to what
    the page does: the Background box drops the Points family the page does not draw, and
    the Pattern box names the new Show choice. Grounds: item 6 gave the model strip one,
    and the prototype draws one on each strip. The alternative was listing it as remaining.
22. **A scale mark sits 12 px over its top labelled tick's centre, in 28 px each pane keeps
    above its plot** (`LABEL_HALF`, `next/rxplot.mjs:MARK_ROOM`). The room keeps a tick at the
    plot's top edge clear of the mark on every scale and at the narrow floor
    (`pattern-*.png`).

## Handover log

- **2026-11-22** — the maintainer's look at R4, the third PR (branch `wp2231-gui-r4-look`, no
  PR yet), paused by the shift's budget. Six of the eight look items landed, one commit each,
  with the dist rebuilt and their pictures retaken under `docs/wp/2231-screenshots/`:
  item 7 (the stale notice's words, and Re-read as a Button set apart from them), item 5
  (Never freed as read-only chips), item 6 (a `?` box on the model strip for all four tabs,
  in `gui/src/next/HelpBox.svelte` and `helpbox.ts`), item 1 (the √, log and Δ/σ marks in
  the tick-label column, over the top labelled tick), item 2 (the Difference label on the
  strip's zero line) and item 3 (horizontal gridlines on the intensity pane; `gui/STYLE.md`
  § Plots updated for both).
  - *Not done*: item 8 (a Text edit previews on the plot) was half-written and set aside
    uncommitted: the validation route's `delta.values` feed a `PreviewQueue` in
    `next/Text.svelte`, and the frame keeps the slider and text previews apart. The runner's
    scratch holds the draft. Item 4 (the last refined or preview toggle) is not started; its
    placement and words are in no design, so its options go to the maintainer in pictures.
    The graph strip's `?` box is not built.
  - *Measured so far*: vitest on the touched files, svelte-check not yet run; no fast suite,
    browser files, lint steps or `tests.reader_output` yet. Nothing here changes what a fit
    prints or returns.
  - *Next*: item 8, then item 4, then § Settled 11 and 12 marked reversed, the pictures'
    README, the gates and `/wp-handover`.

- **2026-11-21** — the Text tab at `/next`, the second of R4's two PRs (#1763), and the
  screenshots and inventory for both tabs. The rebuilt page now shows the project as `.rxt`
  text. A typed change is one pending edit in the action bar beside the Parameters panel's,
  so the window has one Apply, and the editor marks each line that differs from the stored
  project. A buffer kept from a crash or a close is offered again and restored into the
  tab. Twenty-two pictures of the Plan and Text tabs wait in `docs/wp/2231-screenshots/` for
  the maintainer's look beside the prototype's, with a table placing every one of today's
  Plan and Text features. The tab's `?` box is not built, since no tab on `/next` has one
  yet (§ Settled 11).
  - *Done*: `gui/src/next/Text.svelte` carries today's panel's logic with no Apply of its
    own, Re-read only inside the stale notice, and no footer. `gui/src/next/Frame.svelte`
    mounts it, counts its edit, applies it first, applies it before Run this stage, reverts
    and forgets it, and offers and restores the recovery copy's Text arm, which it no longer
    only carries. `lib/sync.ts:editedLines` and `lib/editor.ts`'s `setEdited` mark edited
    lines; today's page does not call them. § Settled by Claude lists eight values, 11-18.
    The browser pass in `tests/test_gui_layout_browser.py` types a value with real keys,
    applies it from the bar, applies a second with ⌘⏎ and checks no run started. It was
    run red once without the frame's editor guard.
  - *Measured* (`[dev]` venv, darwin/arm64, at `6d9715351`, before a merge of main that
    moved docs and the suite-alarm tests only): the fast selection 15238 passed, 433
    skipped, 32 xfailed, playwright installed; the new browser test 19.7 s
    (`tests.added_test_times`); vitest 905 passed in 50 files; svelte-check 0 errors over
    467 files; every `tests/*_browser.py` together with the GUI python files and
    `test_docs_consistency.py`, 493 passed; ruff, the tutorials' prose build and Vale (0
    errors); `tests.reader_output` exit 0, unchanged against the merge base.
    The rebuilt page's second build pass now carries its own CodeMirror chunks
    (`next-editor.js`, `next-vendor-cm.js`, 328 kB), fetched on the first Text tab, as
    today's page fetches its own.
  - *Review*: `/code-review high --fix` over this branch's commits found nine defects and
    fixed seven in one commit, with two new vitest cases (the forget case run red without
    its fix): a second Apply while one ran was read as a refusal; a read begun for a
    project the tab was told to forget could land in the next project's buffer; a failed
    read stayed on screen after a good one; a refusal naming no line said "0 problems";
    the line diff reran on every sync event; the problem list's key could repeat;
    `editedLines` sized its cap off the wrong product. Declined: a stale buffer refusing the
    other panels' edits (§ Settled 17, by design); Run this stage repeating Apply's
    sequence by hand, since sharing it would commit a half-typed Parameters cell on every
    stage run. No heuristic, audit-table row or CLAUDE.md line was added, so no generality
    review.
  - *Not done*: the register guard's reach into `gui/src/next/` (folded into § Inherited by
    the issue triage, #1656 item 2) was measured and left listed. Extending
    `styledFiles()` to `next/*.svelte` with `.ib` added fires all three of the guard's
    assertions, not one: 6 geometry overrides, 2 literal font sizes in `next/Params.svelte`,
    and 45 filled buttons across 13 files, because `next.css` draws a bare button outlined
    where `app.css` draws it filled. The last needs the one-filled-primary check restated
    for the new page, which is more than this PR's fix.
  - *Gotchas*: Shift+End in the editor scrolls a long line's comment column into view and
    leaves the view scrolled after the line is retyped shorter; the pictures scroll back
    first. `Window.test.ts` mocks `lib/editor`, since CodeMirror in jsdom throws while
    measuring after a test has ended. A Window test that leaves a recovery write on the
    timer leaks it into the next test, so the Apply case waits for it.
  - *Next*: the maintainer's look at the pictures beside the prototype's (WP-2214 § How the
    maintainer reviews), which closes the WP. Questions 1 (a)-(c), carried from WP-2227,
    wait for that review. The `?` boxes wait for a help piece that no WP owns yet; the
    swap's inventory walk (WP-2214 § The swap, item 1) reaches their row, 246.
- **2026-11-21** — the Plan tab at `/next`, the first of R4's two PRs (#1755). The rebuilt page
  now shows the plan as the prototype draws it: one block per stage with its Free and Fix rows
  of named chips, a grouped picker behind `+ Add`, the closing stage, and the parameters no
  stage frees. Editing the plan counts as one pending edit in the action bar, survives a crash
  in the recovery copy, and is stored by Apply, as every other edit on the page is. The server
  gained one field for this, `never_freed`, so the page does not guess which parameters a plan
  leaves fixed. The two low findings inherited from the review of #1683 are fixed too: a
  restored draft no longer brings back an edit on a path the project has lost, and the
  background band no longer refuses a glob hold that Apply accepts. The Text tab is still "not
  built yet" on `/next`.
  - *Done*: `GET /api/plan/resolve` returns `never_freed`. `gui/src/next/Plan.svelte` carries
    today's panel's logic (load, preset pick, drag and arrow reorder, undo and redo, run one
    stage, the draft for recovery) under the new markup. `gui/src/next/plan.ts` names chips
    and builds the picker. The iteration field has `min="1"` on both pages (#1652 item 1).
    § Settled by Claude lists ten values. `restoreDraft` in `gui/src/next/Params.svelte` ends
    with the reload's drop of pending edits on unknown paths, skipped while no rows are
    loaded. `GET /api/background` refuses only a literal path the table lacks
    (`params.vector.is_literal_path`), as `Refinement.hold` does. Each fix's new case was
    run red without the fix first. main (with #1741) is merged in and the dist rebuilt.
  - *Measured* (`[dev]` venv, darwin/arm64, on the merged tree): fast suite 15233 passed, 433
    skipped, 32 xfailed (9:28, alone on the machine, through `serial.py`); the three added
    python tests cost 4.36 s locally, 4.28 s of it the two browser cases; vitest 889 passed
    (49 files); svelte-check 0 errors in 465 files; every `tests/*_browser.py` 176 passed; the
    GUI python files plus `test_gui_background.py` and `test_docs_consistency.py` 316 passed;
    ruff, the tutorials' format check, skill caps, skill surface and audit delta clean; Vale
    0 errors (281 warnings, none on a file this branch touches); `tests.reader_output`
    unchanged (exit 0).
  - *Review*: `/code-review high --fix` found nine defects in the Plan tab and its route,
    all fixed in one commit with three new vitest cases: Stage settings threw on a typed
    number and took an emptied guard as 0; opening another project kept the old plan on
    the undo stack; the action bar's stage count went stale after a store; Run this stage
    echoed before it could refuse and hid the refusal's panel; deleting a stage above the
    selection moved the selection; `never_freed` listed a stage's held paths; the typed
    glob already in the stage was not disabled; the picker rebuilt its options per
    keystroke. Declined, as outside this diff or as previews by design: the Rwp
    percentage formatter written in four files; two phases of one name hiding the second's
    groups; the Fix list ignoring earlier stages' fixes (labelled a preview); `.` running
    the stage while a Plan menu item has focus; the `pct` docstring's "thin space".
    No heuristic, audit-table row or CLAUDE.md line was added, so no generality review.
  - *Gotchas*: on this case-insensitive disk `plan.test.ts` and `Plan.test.ts` are one file,
    so the logic cases are `planwords.test.ts`. A Svelte element drops a trailing space, so
    the Rwp label is spelled `{"Rwp "}` to keep the words apart in `textContent`. The picker
    stays open after a choice, so a test clicking `+ Add` again shuts it.
  - *Next*: the Text tab at `/next`, the second PR (drafts in the runner's scratch), then the
    screenshots and the feature inventory, which wait on the maintainer's look. WP-2227's
    three questions stay open.
- **2026-11-21** — filed by a ghostshift runner, on the milestone's R4 row and WP-2214's
  inventory rows 104-117 and 139-146. No open WP owned R4: the milestone's row read "—", and
  WP-2227 names R4 as where its feedback lands without filing it. Issue #1652's first item is
  folded in under § Inherited.
  - *Next*: the Plan tab, the first PR.
