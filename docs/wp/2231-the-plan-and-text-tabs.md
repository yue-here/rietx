# WP-2231 — the Plan and Text tabs at `/next`: a plan read as a recipe with Free and Fix rows, and a text buffer whose edits ride the action bar

Milestone: gui-overhaul · Status: 🔄 2026-11-21 — the Plan tab in review (#1755); the Text tab is next
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
- [ ] The Text tab at `/next` (rows 139-146), from `panels/Text.svelte`. The file's name and
  its sync word on the title line; a typed change counted as one pending edit in the action
  bar, applied by its Apply and by ⌘Enter; Re-read inside the stale notice; one-line notices;
  problems in the gutter and in the list under the editor; the `?` box; the recovery copy's
  text arm offered and restored here. A vitest mount case and a browser pass that types a
  value and applies it from the bar. The second PR.
- [ ] Screenshots at 1440 × 900, light and dark, under `docs/wp/2231-screenshots/`, beside the
  prototype's at the same size in the runner's scratch, with an inventory of where each of
  today's Plan and Text features lives. The last PR waits on the maintainer's look.

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

## Handover log

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
