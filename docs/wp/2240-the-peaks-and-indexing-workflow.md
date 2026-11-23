# WP-2240 — the peaks-and-indexing workflow at `/next`: pick peaks, fit peaks, index, judge

Milestone: gui-overhaul · Status: 🔄 2026-11-23 — tasks 1-5 merged (#1788, #1791); tasks 6-9 claimed by a ghostshift runner
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

- **The dotted mark for a chosen line left out of indexing is drawn in `--plot-peak`**, the
  peak layer's own colour, not `--accent`, which is the calculated curve's colour and hid the
  mark on it. Settled by Claude under `gui/CLAUDE.md`'s one-colour-per-layer, state-by-shape
  rule (WP-1210); Yue delegated 2026-11-23; alternative `--fg`.

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
- [ ] 7. The Index step: the short form and More settings, the progress with Stop and the cells
  found so far, the coverage line, the eight-column candidate table with its relations, and the
  selected candidate's lines on the Pattern graph.
- [ ] 8. The Judge step: the candidate's evidence, the extinction screen with its space-group
  choice, and Adopt pending until Apply.
- [ ] 9. Browser passes over the four steps by real clicks; screenshots at 1440 × 900, light and
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
