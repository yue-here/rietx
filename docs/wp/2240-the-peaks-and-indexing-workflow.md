# WP-2240 — the peaks-and-indexing workflow at `/next`: pick peaks, fit peaks, index, judge

Milestone: gui-overhaul · Status: 🔄 2026-11-23 — tasks 1-9 built and the R6 look's rulings applied; #1792 waits on the maintainer's second look
Depends on: 2218 (hand fitting and the other graphs)
Priority: P2 2026-11-22 — a feature the open milestone was opened for: R6, the rebuild's next piece

## Goal

The rebuilt GUI at `/next` gains its first workflow after Refinement. Chosen from the top bar's
workflow menu, Peaks and indexing walks a person through four steps across the model panel:
Pick peaks, Fit peaks, Index and Judge. Each step shows only what that step needs, and its one
action sits in a foot under it. The Pattern graph marks the picked lines and is the surface for
adding, moving and removing them. The Peaks graph shows each overlap group's window fit with
each line's own curve. Index ends in a candidate table of eight columns, and Judge holds one
candidate's evidence, its extinction screen and Adopt. The piece is judged whole beside the
prototype at 1440 × 900, light and dark.

## Context

WP-2214 is the plan. Its § The pieces names R6 and the inventory rows it owns: 193-211 (the
workflow), 51, 52, 55 and 56 (the peak gestures, the hover ring and a candidate's lines on the
Pattern graph) and 38 (a candidate's legend entry). Today the workflow menu lists Peaks and
indexing as "not built yet", and the model panel shows the four step names with a sentence
each (`gui/src/lib/workflows.ts`, R1).

The server half exists. `POST /api/peaks` picks with all three of `pick_peaks`'s options
(WP-2124), the peak verbs edit `peaks.json`, `GET /api/peaks` serves the list with each
group's fit as `groups`,
`POST /api/index` and `POST /api/index/extinction` run on the one run machine, and
`POST /api/index/adopt` takes any candidate (WP-2124, the maintainer's ruling B of 2026-11-08).
One addition comes from PR #1526 (WP-2202), which built this design inside today's Peaks tab
and stays open as a source until R6 takes its halves (WP-2214 § What happens to the open GUI
pull requests):
`PeakEditor.curves` serves each line's own curve and the group's observed counts. Its
`lib/peaks.ts` step helpers and its fit windows come with it. Nothing R6 changes reaches what
a fit prints or returns.

`/next`'s chart module copy (`gui/src/next/pattern.ts`) already carries the peak layer: the
markers, the picked lines' fitted curve and a candidate's lines, drawn while `peaksActive` is
set. R2 built the plot-object grammar R6 reuses for peaks: a click on the fitted range or an
excluded region selects it, its bar holds its fields, Delete or Option-click removes it and
right-click opens its menu (`gui/src/next/Pattern.svelte`).

### The rulings R6 rests on, restated

- **Indexing is a workflow, not a tab** (the maintainer, sixth review, 2026-11-07): "pick
  peaks, fit, index, judge, iterate". A workflow keeps the window and shows its steps across
  the model panel (`gui/STYLE.md` § Layout and panels).
- **Round 11 closed with "looks good"** (2026-11-08), after three looks. All 35 of its
  settled calls stand. The design below restates them.
- **Any candidate may be adopted** (ruling B, 2026-11-08). One the gate (`best_or_none()`) did
  not pick shows its grade and caveats beside Adopt, and the history node records them.
- **The interaction rules 1 to 12** (adopted 2026-11-08, `gui/STYLE.md` § Interaction) govern
  the peak marks: click adds, a mark click selects and opens its bar, drag moves, Esc backs
  out of a drag and takes a just-finished move back, Option-click removes, right-click opens
  the menu, a row click frames its line, and every edit can be undone.
- **Peak marks are lenses** that echo the reflection ticks, larger and higher above the peak
  (round 11b look, 2026-11-08). A used line's mark is filled, an unused line has no mark on
  the pattern, and a selected one is larger with a ring in the text ink (`gui/STYLE.md`
  § Plots, ruled 2026-11-09). Their blue moved with the palette (WP-2200).
- **The prototype is the ruling for every visible difference** (the maintainer, 2026-11-11,
  "Merge, then polish"). Where it would break a written rule, the rule wins (`gui/STYLE.md`
  principle 9), and the difference is listed in § Questions. So WP-2202's six questions about
  where today's panel departs from the prototype are not asked again: R6 draws the prototype's
  numbered step strip, fills each step's one action in its foot (the workflow hides the action
  bar, so the step's action is the view's one primary), shows the fit windows in the Peaks
  graph tab, keeps the coverage line and folds the informational notes, and leaves the gate's
  `why` out of the candidate table, where Judge says it beside Adopt.
- **No permanent explanatory text** (2026-11-07, repeated 2026-11-08), and chrome text that
  serves no decision goes (2026-11-10). The line naming the gestures under today's plot is
  removed (row 52); the step's `?` box says it.

### The design, restated (round 11 and its looks, 2026-11-08)

The step strip sits at the top of the model panel: each step a button holding its number in a
small outlined circle and its name, the current one on a raised ground, a `›` between steps and
"↺ iterate" at the right. Each step's body scrolls, and its action sits in a foot pinned under
it.

1. **Pick peaks.** Before the first pick: "Picking settings" with the picker's three options
   (2θ range, "Look for shoulders", "Flag Kβ and tungsten lines") and a filled Pick peaks in the
   foot. After it: a segmented filter (All N, Used N, Not used N) over a table of every line
   with a tickbox (use in the search), 2θ, d, intensity and a note in words: the flags, "added
   by you", "moved by you", or "used by you over …" where a person ticked a line rietx had left
   out. A line ticked or unticked stays in the filtered list until the filter is chosen again.
   Unused lines are greyed rows whose tickbox brings them back, and a greyed row's click frames
   its line with a dotted line. The picker's notes sit under a disclosure, and so do the
   picking settings with Pick peaks again, which first says how many of the person's edits it
   replaces. A row click frames its line on the plot at 2° or keeps a narrower zoom; a mark
   click scrolls the table to its row.
2. **Fit peaks.** The overlap groups, filtered "To look at N" or "All groups N", with the 2θ
   span, the line count, χ²ᵣ and the notes. "To look at" is χ²ᵣ above 10 or a flag saying the
   window fit is in doubt (call 13). The Peaks graph shows the group windows: the data, the
   fit, the background envelope, the line marks and the residual in esd with its ±3 band. Each
   line's own curve is a tinted fill under the sum, its Kα2 partner included, with numbered
   toggles per window; every curve starts shown (calls 23, 30).
3. **Index.** Crystal systems, largest volume ("from data" until typed) and a time limit of 2
   minutes or none; the rest under More settings (call 4). While the search runs: per-system
   status, the cells found so far ungraded, and a foot with Stop and the elapsed and remaining
   time (calls 5, 15). When it ends, a line edged in the danger colour names the systems not
   searched and those stopped early, with Search these (call 6). Then "Candidates N, ranked by
   rietx": #, cell, lattice, V, M₂₀, unindexed, absent of screened, Rwp, grade (call 7), and a
   related row marked rather than merged ("same cell as #2", "#2 with c doubled", call 8). A
   row selects the candidate and draws its lines on the Pattern graph (call 9). The foot holds
   Judge #n › (filled) and Index again.
4. **Judge.** Previous and next, the cell with esds and V, the relation line, the grade and its
   caveats in words (refuting ones in the danger colour), the Le Bail check, every figure of
   merit with its blind spot on hover, the engines, then Screen extinctions: classes by ΔBIC
   with the absences tested, "rietx's pick" on the class the gate names, refuted classes kept
   and muted (call 17). Choosing a class offers its space groups as a segmented choice, the
   class's representative first (calls 10, 12). The foot holds Adopt as a Le Bail start
   (filled) with the grade and caveats beside it. Adopt is pending until Apply: the foot then
   reads "Adopt #n in <group> as a Le Bail start" with Revert and Apply, and Apply switches the
   window to the Refinement workflow (call 11).

### The tier of each rule this WP adds

"To look at" (χ²ᵣ above 10, or one of the flags in `gui/src/lib/peaks.ts:LOOK_FLAGS`) is a
view filter over the picker's own numbers. It changes which rows a person sees first, never
which lines reach the search, so it is a display choice in the GUI and not a heuristic of the
package. `src/rietx/_audit.py` is untouched.

### Inherited

- From the milestone's § Owed to the port: per-line curves need a route (#1526 serves them,
  R6 takes that half), and peak edits have no undo though the maintainer adopted the rule on
  2026-11-08 (R6 owes it). Peak edits live in `peaks.json`, outside the history tree, so the
  undo is the workflow's own stack, as the Plan tab keeps one for plan edits (WP-2127).
- Four owed items stay out of R6 and keep their lines there: the Le Bail check's absent lines
  served as tick indices, lattice relations between candidates computed in rietx, an overrule
  that remembers which flags a person overruled (a `peaks.json` format change), and keeping the
  indexing result across a restart (a stored-format change).

## Rulings

- **Reversed by Yue at the R6 look, 2026-11-23: the dotted `--plot-peak` mark.** Claude had
  settled the mark for a chosen line left out of indexing as a dotted line in `--plot-peak`,
  under `gui/CLAUDE.md`'s one-colour-per-layer rule (WP-1210). Yue reversed it in ruling 1
  below. Plot colours and mark styles in a GUI step are now a trigger: they go to Yue drawn.
- **Yue's ruling 1, 2026-11-23 (the R6 look): the peak fit takes the fit line's token.** "I
  don't like the blue-on-blue line with markers, or the dotted line. I think we should use the
  same token as the regular fit line. Since this is indexing there's no risk of confusion."
  Built: the picked lines' fitted curve on the Pattern graph and each window's fit in the
  Peaks graph are drawn in `--plot-calc`, solid, at the calculated curve's width. The groups'
  own residual takes the difference curve's ink. The mark for a chosen line left out of
  indexing is a thin solid line in `--plot-calc`. The lens marks stay blue, as `gui/STYLE.md`
  § Plots and the prototype have them (Yue 2026-11-09). The look entry's questions 1 and 2
  (§ Handover log, fourth session) ask about both.
- **Yue's ruling 2, 2026-11-23: the green candidate lines.** "The green index markers feel off
  somehow but I can't articulate it." Not chosen: four ways to draw a chosen cell's lines are
  drawn for Yue (the look entry's question 3). Nothing is built for it.
- **Yue's ruling 3, 2026-11-23: a relation is a column on the row's own line.** "I like the
  'same cell as #1' notification but I don't like that it's underneath the cell — looks messy.
  Can we introduce a same-line equivalence column of some kind which indicates the
  relationship? I'd like it compact, same-line and clear." Built: a column after # holds
  `≡ #1` (the same cell under another lattice label), `2× #1` (a supercell with twice the
  volume) or `⊇ #1` (indexes every line #1 does). Its tooltip gives the sentence, since
  `/next` has no help popover yet.
- **Yue's ruling 4, 2026-11-23: the cell in six columns.** "Cell results should be in 6
  columns (a, b, c, angles)." Built: a, b, c at four places and α, β, γ at two, each column
  aligned on the decimal point. A value the crystal system sets is muted, and a fixed angle is
  written whole (`90`, `120`) in the column's alignment. The table is now wider than the Index
  step at 1440 × 900 and scrolls in its own box; the look entry's question 5 asks how to fit it.
- **Yue's ruling 5, 2026-11-23: Pawley is the structure-free default.** "The default
  structure-free fit should be Pawley." Built for the workflow: Adopt in Judge reads "Adopt as
  a Pawley start", and Apply sets the project's mode to `pawley`
  (`POST /api/index/adopt` takes `mode`). The candidate check, a Pawley fit since WP-2011,
  is now named for the mode it ran ("Pawley check"). The structure-free defaults outside the
  workflow are listed in the look entry's question 4 and left as they are.

## Non-goals

- Search these running a narrowed search; it waits on a route that starts a search over named
  systems with the rest of the form unchanged.
- Peak lists pasted from another program, indexing a multi-phase pattern, and peaks in `.rxt`.
- The manual's GUI chapters, rewritten at the swap.

## Tasks

- [x] 1. File this WP; the milestone's R6 row names it.
- [x] 2. Per-line curves: `PeakEditor.curves` serves `lines` and `y_obs` on each group (from
  #1526); a pytest holds the lines' sum to the group's model.
- [x] 3. `lib/peaks.ts` helpers for the steps, filters, groups to look at, the candidate
  columns and relations, with `lib/peaksteps.test.ts` (from #1526).
- [x] 4. The workflow built at `/next`: the step strip drawn as the prototype's, each step's
  foot, and the Pick step (settings, Pick peaks, the filtered table with its tickboxes and
  notes, Picking settings with Pick peaks again asking first); the Pattern graph's peak layer
  while the workflow is up, with a row click framing its line. A vitest mount case. The first
  PR.
- [x] 5. The peak gestures on the Pattern graph under interaction rules 1 to 12: click adds
  with a dashed hover mark, a mark click selects with its bar (2θ, Used or Not used, Delete,
  ×), drag moves, Esc during and right after a drag, Option-click removes, right-click opens
  the menu; a typed add row at the table's foot (row 194); ⌘Z and ⇧⌘Z over peak edits.
- [x] 6. The Fit step and the group windows with per-line curves in the Peaks graph tab while
  the workflow is up, with refit.
- [x] 7. The Index step: the short form and More settings, the progress with Stop and the cells
  found so far, the coverage line, the eight-column candidate table with its relations, and the
  selected candidate's lines on the Pattern graph.
- [x] 8. The Judge step: the candidate's evidence, the extinction screen with its space-group
  choice, and Adopt pending until Apply.
- [x] 9. Browser passes over the four steps by real clicks; screenshots at 1440 × 900, light and
  dark, under `docs/wp/2240-screenshots/`, beside the prototype's in the runner's scratch, with
  an inventory of where each of today's Peaks features lives. The last PR waits on the
  maintainer's look.
- [ ] Skill: none. The skill drives the Python API, and this piece changes only the GUI.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_peaks.py tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py tests/test_gui_style_guide.py tests/test_gui_palette.py
.venv/bin/python -m pytest tests/*_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## Handover log

- **2026-11-23 (fourth session)** — Yue's R6 look rulings, on the same PR, #1792. Yue looked at
  the screenshots and ruled five things (§ Rulings, 1 to 5). The peak fit is now drawn like the
  calculated curve, orange and solid, on the Pattern graph and in each Peaks window. A chosen
  line left out of indexing is marked by a thin solid line, not a dotted one. The candidate
  table shows the cell as six columns, a, b, c, α, β, γ, and a related row says so in a compact
  column on its own line (`≡ #1`) instead of a line under the cell. Adopt in Judge now lands a
  Pawley start. The green candidate lines are unchanged: Yue asked for alternatives, which are
  drawn below. The WP stays 🔄 for Yue's look at them.

  *Done.* The branch took `main` first (WP-2242's `{#key opens}` around the workflow's panes;
  the Frame now also forgets the chosen cell's lines and the Fit step's windows on an open).
  Ruling 1: `next/pattern.ts` draws the groups' fit in `--plot-calc`, solid, at the calculated
  curve's width, and their residual in `--plot-diff`; `next/PeakFits.svelte` draws each
  window's fit in `--plot-calc`; `gui/STYLE.md` § Plots and interaction rule 5 say so. Rulings 3
  and 4: `cellColumns` and a `Relation` (mark and sentence) in `lib/peaks.ts`, and the table in
  `next/Candidates.svelte`. Ruling 5: `POST /api/index/adopt` takes `mode` (`lebail`, the
  default, or `pawley`; anything else is refused), `/next` sends `pawley`, and the button reads
  "Adopt as a Pawley start". The candidate check has been a Pawley fit since WP-2011
  (`indexing.workflow.VALIDATION_MODE`), so Judge's heading now names the mode the check ran
  ("Pawley check") and More settings says "Check the best cells by a Pawley fit". Every
  screenshot in `docs/wp/2240-screenshots/` that shows the Pattern graph is retaken zoomed to
  20-40° 2θ (Yue's addition), with a full-range Pick picture beside it.

  *Checked by real clicks* (fap example, 1440 × 900, light and dark, `r6l_probe.py` in the runner's scratch). The
  candidate table's header reads #, a blank relation column, a, b, c, α, β, γ, Lattice, V, M₂₀,
  Unindexed, Absent, Rwp, Grade. Row 1 reads 9.3744 9.3744 6.8875 90 90 120 trigonal P, with
  the tied b and the three set angles muted. Nine rows carry a relation (`≡` four times, `2×`
  twice, `3×` three times), each with its sentence in the tooltip. Every row is 28 px, one
  line. Judge's button reads "Adopt as a Pawley start". Apply moved the project's mode from
  `rietveld` to `pawley`, and a fit then ran in 0.7 s and returned a `pawley` result. Every
  zoom read 19.9-39.8° off the status bar after the drag. No page errors.

  *Measured.* The same Pawley start fitted through the API converged in 6 stages at Rwp
  8.10 %. The six-column table is 868 px wide against the Index step's 760 px at 1440 × 900,
  so it now scrolls in its own box (question 5). Gates, on an arm64 Mac in the worktree venv:
  the fast suite 15362 passed, 438 skipped, 32 xfailed; vitest 62 files, 999 passed;
  svelte-check 0 errors over 491 files; the browser files this touches (layout, console,
  switch) 55 passed; CI's lint steps all exit 0 (Vale 0 errors, 281 warnings).

  *Settled by Claude.* Each is small and visible in the screenshots.
  - The lens marks stay blue. Yue's words name the line ("the same token as the regular fit
    line"), `gui/STYLE.md` § Plots rules the marks blue (Yue 2026-11-09), and the prototype
    draws an orange fit under blue lenses. Question 1 shows the other reading.
  - The groups' own residual, drawn before a fit, takes `--plot-diff`, the regular residual's
    token, as its fit now takes the regular fit's. Alternative: keep `--plot-peakfit` there.
  - The relation marks: `≡ #1` for the same cell under another lattice label, `2× #1` for a
    supercell with twice the volume, `⊇ #1` for a cell indexing every line #1 does. The
    column sits after #, so a row reads "2 ≡ #1". The sentence is the mark's tooltip
    (`title=`). `gui/CLAUDE.md` keeps `title=` off authored prose and sends it to `<Help>`, but
    `/next` mounts no help popover, so a `<Help>` term there opens nothing (found below).
  - A value the crystal system sets is muted. A set angle is written whole (`90`, `120`) and
    keeps the column's decimal alignment by empty room, so a copied row reads `90`. A tied
    length keeps its four places. Angles take two places, which saves a column's width.
    Alternative: `= a` in the tied column.
  - The adopt route keeps `lebail` as its default, so today's Peaks tab is unchanged.

  *For Yue to look at.* The look page is `~/.cache/ghostshift/rietx/gui-r6/look-index/index.html`,
  every picture zoomed to 20-40° 2θ first.
  1. The lens marks' colour. Built: blue lenses over the orange fit. Drawn beside it: orange
     lenses too, a reading of ruling 1 that covers the marks.
  2. The mark for a chosen line left out of indexing (ruling 1 drops the dotted line). Built:
     a thin solid orange line through the pattern. Drawn beside it: a hollow orange lens at the
     line's crest with the chosen ring, and a hollow blue lens, which is how the Peaks windows
     already draw an unused line (round 11 call 34).
  3. A chosen cell's lines (ruling 2, not chosen). Four are drawn: (a) today's green
     full-height lines; (b) a row of tick lenses under the pattern in the observed points'
     neutral ink, as the prototype draws "#n"; (c) full-height lines in the strong rule's grey
     (`--line-strong`); (d) the tick row of (b) in the candidate green. (b) and (d) are a
     probe-only mock: the row's "#n" label and the prototype's "Ticks of #n" title are left out.
  4. Structure-free defaults outside the workflow, left as they are (ruling 5 names the
     workflow):
     - New project's typed cell gives Le Bail (`lib/wizard.ts` `modeFor`, today's page).
     - `POST /api/index/adopt` defaults to `lebail` when no mode is sent (today's Peaks tab).
     - The extinction screen's cell-only prefit is a Le Bail `profile_only` fit
       (`indexing/extinction.py`).
     - The report's `lebail_gap` comparison forces Le Bail (`report/layer0.py`).
     - The agent skill calls Le Bail with `profile_only` the fit "for a cell without a trusted
       structure" (`docs/skill/rietx/SKILL.md`).
     - The candidate check is a Pawley fit already, but its function is still named
       `validate_by_lebail`, and `IndexValidation.mode` reads `lebail` for an old record.
  5. The candidate table at the default width (rulings 3 and 4). Built: it scrolls sideways in
     its own box, so Rwp and Grade sit past the edge until scrolled. Other ways: the lattice as
     its Bravais symbol (`hP`, `mP`), about 60 px; a wider default right pane; or Unindexed and
     Absent moved to Judge.

  *Found, not fixed.* `/next` mounts no help popover (`HELP_CONTEXT` is set only in
  `App.svelte`), so every `<Help>` term there opens nothing: a refutation, the FOM blind spots,
  the peak notes' flags and a held parameter's reason. It belongs to the rebuild's shell.

- **2026-11-23 (third session)** — third PR, #1792: tasks 6 to 9. The four steps of the
  workflow now work at `/next`. Fit peaks lists the overlap groups and draws their windows in
  the Peaks graph, each with its lines' own curves and a Refit. Index holds the search form,
  shows the search while it runs, says what it did not cover, and lists the cells; a row's
  click draws that cell's lines on the Pattern graph. Judge shows one cell's evidence, screens
  its extinctions, offers the class's space groups, and adopts the cell as a Le Bail start
  once Apply is pressed. Apply hands the window to the Refinement workflow. The WP stays 🔄
  until Yue has looked at the screens (§ For Yue to look at, below).

  *Done.* Task 6: `next/PeakFits.svelte` (the windows, ported from #1526's drawing) and the
  Fit step in `next/Indexing.svelte`. Tasks 7 and 8: `next/Candidates.svelte` holds both
  steps, with `coverageLine` and `limitWord` in `lib/peaks.ts`; `next/Pattern.svelte` takes a
  `candidate` overlay drawn by the existing candidate layer. Task 9: a browser pass over Fit,
  Index and Judge by real clicks
  (`test_the_fit_index_and_judge_steps_run_to_an_adopted_cell`), the screenshots below, the
  inventory below, and the lens marks' line in `gui/CLAUDE.md` § Plot. Bytes for that line
  came out of the file's intro and its node bullet, so the file stays under its budget. The
  test the last review named is in: a peak edit typed into the `.rxt` document is one undo
  step (`test_a_peak_edit_typed_in_the_rxt_is_one_undo_step`).

  *Measured* (`[dev]` venv plus playwright, darwin/arm64). Fast suite `-m "not slow"`,
  through the machine queue: 15 359 passed, 438 skipped, 32 xfailed, which is the last
  entry's 15 357 plus this session's two tests. They take 10.29 s (the browser pass, whose
  index runs on cubic alone) and 0.11 s. vitest 61 files, 993 passed; svelte-check 0 errors,
  0 warnings over 490 files. The GUI python files and the two rulebook files: 373 passed.
  Browser files run by hand, since CI runs none: `test_gui_layout_browser.py` and
  `test_gui_console_browser.py`, 53 passed before the review fixes, and the layout file
  again inside the fast suite on the reviewed tree. CI's lint and PR-delta steps exit 0.
  Vale: 0 errors, 281 warnings, none on lines this PR wrote. `gui/CLAUDE.md` is 44 969
  bytes against its 44 972 budget.

  *Settled by Claude under the prototype (the 2026-11-11 ruling) and `gui/STYLE.md`.*
  - χ²ᵣ is not coloured above 10, under STYLE.md's rule that no number is judged by colour.
    The prototype draws it red.
  - The window's fit curve is drawn in `--plot-peakfit`. The prototype draws it orange, which
    is the calculated curve's colour.
  - More settings holds the real controls from #1526's form. The prototype shows them as
    text.
  - A refuted class stays clickable, as in the prototype. Its refuting lines sit behind a
    help popover on "refuted", so each class row is one line, as the prototype draws it.
  - The candidate table carries no "rietx's pick" mark. The gate's pick is said beside Adopt
    in the Judge step.
  - Crystal systems, engines and centrings are toggle buttons, as in the prototype.
  - Search these is left out. § Non-goals says why.

  *Review.* `/code-review high --fix` found ten issues. Fixed: a row chosen in Index left an
  earlier Adopt pending, so Apply could adopt another cell than the one Judge showed; a new
  extinction screen left a pending Adopt on the old group; a streamed frame without an
  elapsed time restarted the run clock; a hidden line curve came back after a Refit. Its fix
  for the last one hid both lines of a pair 0.0007° apart, a pair the fluorapatite list has,
  so the match is now to the nearest line, with a test that fails on the reviewer's version.
  Two cleanups were also applied. The coverage line read the form's systems, so a form edited
  after a run changed what the line said about it. It now keeps the systems the run was
  started with, and falls back to the form only after a reload. Declined: ⌘Z still undoes peak
  edits on the Index and Judge steps, since the workflow's undo covers every step; the
  coverage sentence keeps its own "2-minute" adjective form; a hover redraws all six windows,
  a small cost. A browser look also found and fixed a missing space after each comma in the
  notes and caveats.

  *For Yue to look at.* Screenshots at 1440 × 900, light and dark, in
  `docs/wp/2240-screenshots/` (its README says how they were taken). Each `gui-*` picture has a
  `prototype-*` partner at the same step. Four differences are worth a look.
  1. A chosen cell's lines. The build draws them full height over the data, under the
     written rule in `gui/CLAUDE.md` § Plot (WP-1211). The prototype draws them as a "#n" row
     in the tick band, titles the graph "Ticks of #n", and marks absent and unexplained
     lines in red. On the fluorapatite pattern the full-height lines cover most of the plot
     (`gui-3-index-*.png`). The rule wins until Yue says otherwise. The red marks need the
     Le Bail check's absent lines as tick indices, which § Inherited keeps out of R6.
  2. Caveat and engine names. The build shows the code's words ("fom panel disagrees",
     "trial_error"). The prototype has written words ("figures of merit disagree", "trial
     and error"). Written words need a `rietx.help` arm, since names are described there and
     nowhere else.
  3. Search these, left out as § Non-goals says.
  4. The χ²ᵣ colour and the fit curve's colour, settled above.

  *Inventory: where each feature of today's Peaks tab lives at `/next`.*
  - Pick peaks and the picker's settings: the Pick step, its foot and its Settings.
  - "N of M lines usable": the Pick step's filter counts (All, Used, Not used).
  - The σ-assumed chip: none. `PEAK_SIGMA_ASSUMED` reaches the Index step's notes after a
    search.
  - The picker's notes: "Notes from the picker" in the Pick step.
  - A line's zoom button: a click on its row frames it, and Show all undoes the frame.
  - Origin and flag chips: the Note column's words.
  - The use tickbox: the same tickbox.
  - A group's ↻ refit: the window's Refit in the Peaks graph, in the Fit step.
  - A line's ×: Option-click, the right-click menu, or the line's bar.
  - Add by click, move by drag, exclude by shift-click: the Pattern graph's gestures (rules 1
    to 12). Exclusion is "Leave out of the search" in the menu, or the tickbox.
  - The group windows: the Peaks graph tab while the Fit step is up.
  - Index and its form: the Index step. Its short form holds the systems, the largest volume
    and the time limit. More settings holds the rest.
  - The run's progress and streamed shortlists: "Searching" with each system's state and the
    cells found so far.
  - What the search covered: the line above the candidates.
  - The run's notes: "Notes from the search".
  - A candidate's ▸ (caveats, ambiguity, lines through the data): a row's click draws the
    lines; the Judge step shows the rest.
  - The `best_or_none()` chip and a row's `why`: beside Adopt in the Judge step.
  - The engines that found a cell: "Found by" in the Judge step.
  - Adopt on each row: Adopt in the Judge step, pending until Apply.
  - The extinction screen and its per-group adopt: the Judge step's Space group table and
    its "Adopt in" choice.

  *Gotchas.* Svelte trims the space from a bare `, ` text node inside a block, so a list
  joined with `{#if i}, {/if}` reads "a,b". Write the separator as `{", "}`. A synthetic LaB₆
  index with only cubic on takes seconds; the full quick search on fluorapatite takes its two
  minutes.

  *Next.* Yue's look at the screenshots, then any change it asks for. The swap (WP-2214
  § The swap) retires today's Peaks tab and moves the `gui/CLAUDE.md` § Peaks lines that
  describe it.

- **2026-11-23 (second session)** — second PR, #1791: task 5 and the dotted-mark ruling. The
  Pattern graph is now the peak list's editing surface while the workflow is up. A person can
  add a line by clicking empty space, see where it will land before clicking, choose a line by
  its lens and get its bar, drag it to a new place, take a drag back with Esc, remove it with
  Option-click or from its right-click menu, and type a 2θ into the table's foot to add one
  without the mouse. Every edit to the list can be undone and redone with ⌘Z and ⇧⌘Z. Fit,
  Index and Judge still show their placeholder sentence.

  *Done.* The ruling Yue delegated on 2026-11-23 is applied and recorded in § Rulings: the
  dotted mark for a chosen line left out of the search is drawn in `--plot-peak`. Task 5:
  `POST /api/peaks/undo` and `/redo` over a session-local stack of `peaks.json`'s bytes
  (`GuiSession._peak_step`, `peaks.snapshot`/`restore`; the payload carries `undo` and `redo`
  counts); `next/pattern.ts` keeps 96 px of headroom through its own `ranges.main` and
  reports where each lens went (`markAt`, `markOf`, `lensAt`); `next/Pattern.svelte` holds
  the gestures, the line's bar and three DOM lens marks (hover, dragged or waiting, danger);
  `next/Indexing.svelte` owns the verbs (`edit`, `undo`, `redo`), the ⌘Z keys and the typed
  add row, and brings a chosen line's row into view; `next/Frame.svelte` wires the two and
  adds "Undo the peak edit" and "Redo the peak edit" to the palette. The lens's size moved to
  `lib/plot.ts`, so the page's DOM marks and the canvas share one number.

  *Measured* (`[dev]` venv plus playwright, darwin/arm64). Fast suite `-m "not slow"`: 15 357 passed, 438 skipped, 32 xfailed; the two added tests take 5.75 s (the browser one) and 0.22 s. vitest 59 files, 981 passed; svelte-check 0 errors, 0 warnings over 486 files. Browser files run by hand, since CI runs none: `test_gui_layout_browser.py` and the three other GUI browser files, 58 passed before the review fixes, and passed again inside the fast suite on the final tree. CI's lint and PR-delta steps exit 0. Vale: 0 errors, 281 warnings, none on lines this PR wrote.

  *Settled by Claude under the workshop's round-11 calls and STYLE.md.* Undo restores the stored
  list's bytes rather than running an inverse verb, because a re-added line refits its group
  from a new start and loses its flags (rule 10; alternative: inverse verbs, inexact). Pick
  peaks is one undoable step, and the "replaces N edits" question before it stays, as call 29
  has it. The lens's hit target is 6 px either side of its axis, wider than its 4.5 px ink. A
  click while a region's bar is open only closes it (rule 3). The line's bar shows 2θ as text,
  not a typed field: the typed route is the table's add row. The rulebook line for the undo
  rule did not fit `gui/CLAUDE.md`'s byte budget, so the rule lives in `_peak_travel`'s
  docstring.

  *Review.* `/code-review high --fix` found ten issues and fixed seven; an eighth was fixed by hand (a click outside the workflow cleared its chosen line). Declined: the `gui/CLAUDE.md` § Peaks lines describe today's Peaks tab, which still behaves that way; an undo failure path no code reaches; the 300 ms add timer outliving an unmount. No test yet holds that a `.rxt` peak edit adds an undo step.

  *Gotchas.* A row click chooses its line, so its lens is drawn 1.4× larger; a browser test
  that sweeps for a lens lets the choice go first (Esc), or it finds the larger lens's tip.
  Removing a line can leave the count unchanged: the group's refit re-judges its neighbours
  and may report a line there again, so a test asserts the removed 2θ is gone, not the count.

  *Next.* Task 6 (the Fit step and the group windows with per-line curves in the Peaks graph
  tab, with refit), then 7 (Index), 8 (Judge) and 9 (screenshots beside the prototype's and
  the `gui/CLAUDE.md` line for the lens marks, which needs bytes cut elsewhere in that file
  first). The last PR waits on the maintainer's look.

- **2026-11-23** — first PR, #1788: tasks 1-4. The peaks-and-indexing workflow now opens at
  `/next` from the workflow menu, under the prototype's numbered strip (Pick peaks › Fit peaks ›
  Index › Judge, with ↺ iterate back to the first). Its first step works end to end: a person
  sets the picker's three options, picks, filters the list to the lines used or not used, ticks
  a line in or out of indexing, and clicks a row to frame its line on the Pattern graph, where
  the lines are drawn as the prototype's lens marks. Fit, Index and Judge still show their
  one-sentence placeholder, and the peak gestures on the plot are not wired yet.

  *Done.* Task 2 serves each group's per-line curves and observed counts
  (`PeakEditor.curves`). Task 3 adds the steps' pure helpers to `lib/peaks.ts` with
  `lib/peaksteps.test.ts`. Task 4 adds `next/Indexing.svelte`, the strip in `next/Frame.svelte`,
  the lens layer in `next/pattern.ts` (`peakMarkers`, `LENS_*`), `WORKFLOW_HELP`, and the
  `built`/`loop`/`graphs` fields and `stepGraph` in `lib/workflows.ts`. The corpus labels
  `peak_origins:manual` and `:edited` now read "added by you" and "moved by you".

  *Measured* (`[dev]` venv, darwin/arm64, playwright installed in the venv). vitest 59 files,
  980 passed; svelte-check 0 errors, 0 warnings over 486 files. The GUI and docs pytest files
  (`test_help`, `test_gui_peaks`, `test_gui_server`, `test_gui_dist`, `test_gui_manual`,
  `test_gui_style_guide`, `test_gui_palette`, `test_docs_consistency`): 369 passed. Browser files
  `test_gui_layout_browser.py`, `test_gui_console_browser.py`, `test_gui_peaks_browser.py`,
  `test_gui_browser.py`: 57 passed, one of them new
  (`test_the_pick_step_picks_frames_a_line_and_a_tick_moves_nothing`). The fast suite through the queue: 15343 passed, 438 skipped,
  32 xfailed; the one added pytest costs 4.63 s on this machine.
  ruff clean; Vale 0 errors, its 281 warnings on pages this branch does not touch.

  *Settled by Claude under the 2026-11-11 ruling (the prototype is the ruling at `/next`) and
  STYLE.md.* WP-2202's six open questions: the numbered strip as drawn; one filled action in each
  step's foot, since the action bar hides while a workflow is up; the fit windows in the Peaks
  graph tab; coverage stays and notes fold; no `why` column in the candidate table; "added by
  you" through the corpus label. Smaller calls: the 2θ range placeholder is "default"; 2θ at four
  places without its esd and intensity as I/Imax × 100 (WP-1209's column rule); "↺ iterate" is a
  button back to Pick peaks, since a title on a bare span breaks the title rule; the "used by you
  over …" note is session-local; the filter's counts reserve the longest count's width, so a tick
  moves no button.

  *Review* (`/code-review high --fix`, ten findings, five fixed in their own commit). Fixed: the
  pane is keyed on the project, so opening another one drops the old list; the chosen row is one
  bound value, cleared by a pick; a refused tick puts its box back; a stacked lens sits above the
  twin it stacks on; the chrome inks are read with the plot colours rather than per draw; a dead
  `removed` count is gone. Declined: the dotted mark for a chosen line left out strokes in
  `--accent`, which equals `--plot-diff` on the light theme; it carries no quantity, so chrome
  ink is the rule (WP-1213), and its colour is the prototype's, so task 9's look decides. The lens
  marks drop the hollow, diamond and σ-whisker shapes `gui/CLAUDE.md` § House style states for
  today's Peaks tab, because round 11's design replaced them; the rulebook line moves at the swap
  (WP-2214), not here. The helpers for steps 6-8 stay, being this WP's next tasks. Per-line curves
  refreeze each group once per line; a cheaper form needs `indexing/peakfit.py` and waits until a
  measurement says it costs a click.

  *Gotchas.* The selected lens at the plot's top is clamped until task 5 gives the plot its
  headroom. The panel draws nothing until `GET /api/peaks` answers, a few milliseconds on a
  local server; a probe waits for `.steppane h3`. In the worktree, Bash refuses any command
  containing the letters g-i-t inside a word, so `digits` in a sed script is refused: run such
  edits as python scripts from the scratch directory.

  *Next.* Task 5 first: the gestures and the 96 px headroom, because the Fit and Index steps
  frame and select lines through them. Then 6 (Fit with group windows), 7 (Index), 8 (Judge) and
  9 (screenshots beside the prototype's). Task 9's PR also states the lens marks' rule in `gui/CLAUDE.md` § Plot beside
  today's shapes, since no swap WP exists yet to move it. The last PR waits on the maintainer's look.

- **2026-11-22** — filed by a ghostshift runner for the milestone's R6 row, which had no WP. No
  open WP owns the workflow at `/next`: WP-2202 built the same design inside today's Peaks tab,
  and WP-2214 makes its PR #1526 a source that closes once R6 takes its halves.
