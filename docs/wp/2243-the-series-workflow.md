# WP-2243 — the series workflow at `/next`: patterns, first fit, run, results, with Trends and Map

Milestone: gui-overhaul · Status: 🔄 2026-11-23 — Patterns and Run steps built (PR #1794); Results next
Depends on: 2240 soft (the workflow frame R6 builds on); 2300 soft (what each pattern refines)
Priority: P2 2026-11-23 — a feature the open milestone was opened for: R7, the rebuild's last piece before the swap

## Goal

The rebuilt GUI at `/next` gains the series workflow. Chosen from the top bar's workflow
menu, Series walks a person through four steps across the model panel: Patterns, First fit,
Run and Results. Patterns loads the files and sets the walk. First fit refines the walk's
first pattern alone. Run shows each fit as it lands. Results holds one row per pattern, the
values to plot, the warnings and the largest steps. Two graph tabs join Pattern: Trends draws
any refined value against the series coordinate, and Map draws every pattern as a row of
colour. One selected pattern links the three. The scrubbing of WP-1317 is redesigned into
them. The piece is judged whole beside the prototype at 1440 × 900, light and dark.

## Context

WP-2214 is the plan. Its § The pieces names R7 and the inventory rows it owns: 174 to 192
(today's Series tab, each given its home in the four steps). Today the workflow menu lists
Series as "not built yet", and the model panel shows the four step names with a sentence each
(`gui/src/lib/workflows.ts`, R1). The milestone record's § R7 carries the series scrubber and
§ R7 is designed from loading to output state what R7 adds to round 12's design, and are not
restated here.

The server half mostly exists (WP-1016). `PUT /api/series` stages the whole list and the walk
settings, every file read there; `POST /api/series/run` runs the chain on the one run
machine; `GET /api/series/result` serves the entries, trajectories, steps, walk gaps and
fences, with WP-1317's `trace` arm (#1395, merged 2026-11-21); `GET /api/series/curves` and
`GET /api/series/history` serve one member each. During a run, every event carries
`series_index`, `series_label`, `series_n` and `series_pass`, and a pattern's `fit_end`
carries its Rwp and GoF, so the Run step folds the progress out of the stream the Console
already follows. What the server lacks is named in the task that needs it.

WP-1317 belongs to another contributor. Its follow-up PR #1786 is open and edits
`src/rietx/gui/series.py`, `gui/src/panels/Series.svelte` and the trace's drawing in
`src/rietx/viz/static/rxplot.mjs`. R7 reads what is on `main` and edits none of the three
until #1786 has merged. Today's Series tab stays as it is until the swap deletes it.

### The rulings R7 rests on, restated

- **Series is a workflow, not a tab** (the maintainer, sixth review, 2026-11-07). A workflow
  keeps the window and shows its steps across the model panel (`gui/STYLE.md` § Layout and
  panels).
- **Round 12 closed with "looks great"** (2026-11-08), after four looks. All 38 of its settled
  calls stand, and the design below restates them. The tabs are named Trends and Map ("trends/
  map is good", 2026-11-08).
- **Most series fits do not refine zero** (2026-11-08): the full McCusker plan does not suit
  the later patterns, so Patterns offers what each later pattern refines, by group, with zero
  shift and profile held by default (round 12c calls 27 to 29). How a series names that set
  waits on WP-2300 (series rule 1, accepted 2026-11-16).
- **A series can start from one pattern fitted alone** (2026-11-08: "start a pattern in single
  refinement mode, then pass it as a warm start"). That is the First fit step.
- **The scrubber's idea is sound and its UI is redesigned** (2026-11-21, on #1395): "The
  fundamental idea is sound, but we need to bring it into the new gui. … We will need to fully
  re-design the UI however." Its nine features are the milestone's S1 to S9.
- **The whole path is designed, from loading to output** (2026-11-21): "data loading and
  cleaning, pre-visualisation, visualisation against parameters, output formats such as
  interactive html".
- **The averaging window is set by dragging a bar on the plot**, with a typed field kept in
  step (2026-11-08, "a genius move"); a colour key sits in empty space inside the plot, never
  in a margin of its own (2026-11-08). Both are in `gui/STYLE.md`.
- **No permanent explanatory text** (2026-11-07, repeated for the series on 2026-11-08: "again,
  too much AI prose"), and a disclosure stays open across other clicks (2026-11-08).
- **The prototype is the ruling for every visible difference** (2026-11-11, "Merge, then
  polish"). Where it would break a written rule, the rule wins (`gui/STYLE.md` principle 9).

### The design, restated (round 12 and its looks, 2026-11-08)

The step strip is R6's: each step a numbered button, the current one raised, `›` between.
Each step's body scrolls, and its action sits in a foot pinned under it.

1. **Patterns.** A heading names the count and the 2θ span ("17 files · 5.0–49.9° 2θ"). Add
   files… takes many files at once, and Sort by <axis> puts them in order of the coordinate
   (disabled when they already are). The table: #, File, the coordinate as a typed value, the
   point count, and × to remove. There is no drag to reorder (call 15). Under "Walk": the
   axis name, typed, and Order as a segmented choice of First to last, Last to first, and
   Both, and compare, with rietx's default, First to last (call 16). Under "Refined in each
   pattern": one tick per group (each phase's scale and cell, the background, zero shift,
   profile), zero shift and profile unticked (calls 27 to 29). More settings, a disclosure,
   holds the carried-over globs. The foot holds First fit (filled) and Run series, with the
   count and the number of walks beside them, or "Needs two patterns", or "Changed since the
   last run" (call 13).
2. **First fit.** The walk's first pattern, named with its coordinate (call 18). Four
   label-value rows: model, plan, 2θ range, starts from. While it runs, a progress line; when
   it ends, Rwp, GoF, iterations and warnings. The foot: Fit <pattern> (filled) and Open in
   Refinement; after the fit, Run series (filled), Fit again and Open in Refinement. The step
   is optional (call 19).
3. **Run.** A status line ("Fitting <pattern> · <coordinate> · first walk · 3 of 34") over a
   progress bar, and a table that fills as fits land: #, pattern, coordinate, Rwp (%), started
   from (model, first fit, previous, previous with the whole plan) and, for two walks, a
   second-walk column. The graphs follow the pattern being fitted until a row click, and
   "Follow the run" resumes (call 9). The foot holds Stop while running, which keeps what
   finished (call 10); after, See results (filled) and Run again, which replaces everything.
4. **Results.** Three label-value rows: Converged, Largest walk gap and Largest step, the last
   two with Plot, and no verdict (call 11). The per-pattern table: #, coordinate, Rwp, GoF,
   started from, warnings. The Plot list: every refined value and statistic, grouped, a tick
   to plot it on Trends, with its value at the selected pattern and "7/17" where it was
   refined on only some patterns (calls 20, 22). The selected pattern's warnings, the
   series' warnings, and the largest steps under a disclosure.

**One selected pattern** links Pattern, Trends and Map: a row click, a point click, a map-row
click, ‹ › in the graph title and ↑ ↓ all move it (call 2). Pattern draws that pattern's fit
as Refinement draws one.

**Trends** draws the ticked values as small panels sharing the coordinate axis, one per value,
two values sharing a panel when they share a unit and overlap (b and c). Points with esd bars,
never joined (call 6). The second walk draws as rings over the first walk's dots, and each
panel names how far the walks part on it (call 4). A panel's axis spans the values and their
bars, reaching at most one value-spread past the values (call 23). A Plot menu on the view
lists every value, one submenu per group, and stays open while ticking; each panel has ×;
"Against" switches the axis between the coordinate and the pattern number (call 21).

**Map** draws every pattern as a row, first at the top (call 7): Observed on a log scale in
cividis, or Difference, the mean of (obs − calc)/esd under each pixel, red to blue at ±5 esd
(calls 8, 24). Map | Waterfall (Map by default) and a Cuts box (on by default, call 31). A
click sets a cut at that 2θ and selects the row; below the map the selected pattern's profile,
beside it each pattern's intensity at the cut averaged over a width. The width is a bar on the
profile below, drawn, resized by its grips and moved, with a typed width kept in step (calls
35, 36). A drag across zooms 2θ, a drag down shows a window of rows, shift-drag picks an area
to average (calls 32, 34). Flip puts the first pattern at the bottom (call 37). The colour key
is a horizontal bar in the empty corner under the profile beside the map (call 38). Map and
Pattern share one 2θ zoom.

### The tier of each rule this WP adds

None yet. The views read the record's own numbers (`SeriesResult.steps`, `direction_gaps`,
the trace's marks) and set no threshold. A later task that adds a pre-run check (members that
disagree on wavelength, range or step; a blank pattern) names its tier here before it lands.

### Inherited

- From the milestone's § Owed to the port: a GUI series lives in session memory only. Saving
  a series with the project is round 12's decision 2, deferred with series file I/O on
  2026-11-08, and is a stored-format change, so it comes to the maintainer when task 12 is
  reached.
- From round 12's flagged list: the Map needs every member's curves, which the route serves
  one at a time; a walk cannot start mid-series (call 18); Trends cannot plot one refined
  value against another (call 21); the coordinate is not read from file headers (call 14).
  WP-1952's open PR #1659 decides the XYDATA TEMP line.

## Rulings

## Non-goals

- WP-1317's external annotations (a typed transition temperature, a beam dump), deferred by
  the milestone until a series is saved with the project.
- A joint fit of the patterns (`multi.py`, series rule 2's second call), and a series started
  from a joint fit's result (WP-2103).
- The manual's GUI chapters, rewritten at the swap.

## Tasks

- [x] 1. File this WP; the milestone's R7 row names it.
- [x] 2. The workflow built at `/next` with the Patterns step: Add files… for many files,
  Sort by <axis>, the table with the typed coordinate and ×, the axis name, Order, More
  settings with the carried-over globs, and a foot with Run series. A vitest mount case.
- [x] 3. The Run step: Run series, the status line and progress bar, the table folded from the
  run's events as fits land, Stop, and See results and Run again after.
- [ ] 4. The Results step: the summary rows, the per-pattern table, the Plot list, the
  selected pattern's warnings, the series' warnings and the largest steps.
- [ ] 5. The selected pattern: Pattern draws its fit while Series is up, ‹ › in the title,
  ↑ ↓, and the graphs following the run until a row click.
- [ ] 6. The Trends graph tab: small panels, the Plot menu, Against, the second walk's rings,
  the bars' span, a point click selecting its pattern.
- [ ] 7. The Map graph tab, with a route serving every member's observed counts and
  difference on one grid: Map and Waterfall, Observed and Difference, cuts and the two
  profiles, the averaging bar, the row window, area averaging, Flip and the colour key; drawn
  from the observed counts before a run too (pre-visualisation).
- [ ] 8. The scrubber's nine features (S1 to S9) placed in the new design: drawn on real
  pages and brought to the maintainer, since round 12 predates them and neither the workshop
  nor `gui/STYLE.md` places them; then built as ruled.
- [ ] 9. The First fit step, with the verb that fits the walk's first pattern alone under the
  project's plan and starts the series from its result; Open in Refinement.
- [ ] 10. Refined in each pattern, once WP-2300 names the declaration the series call takes.
- [ ] 11. Loading and cleaning: a check before the run that the members agree on wavelength,
  range and step; a pattern with no signal found before it is fitted; excluded regions and a
  2θ range for the whole series; the coordinate from file headers where the reader has it.
- [ ] 12. Output: Save table… (`SeriesResult.to_table`), an interactive page for a series,
  and saving the series with the project (a stored-format change, to the maintainer first).
- [ ] 13. Browser passes over the four steps and both graphs by real clicks; screenshots at
  1440 × 900, light and dark, under `docs/wp/2243-screenshots/`, beside the prototype's in the
  runner's scratch, with an inventory of where each of today's Series features lives. The
  last PR waits on the maintainer's look.
- [ ] Skill: none. The skill drives the Python API, and this piece changes only the GUI.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_series_trace.py tests/test_gui_server.py tests/test_gui_dist.py tests/test_gui_manual.py tests/test_gui_style_guide.py tests/test_gui_palette.py
.venv/bin/python -m pytest tests/*_browser.py   # local: CI runs no browser test
```

The piece closes when every task is ticked and the maintainer has looked at its screens beside
the prototype's (WP-2214 § How the maintainer reviews).

## Handover log

- **2026-11-23** — ghostshift runner gui-r7, first session; PR #1794. The rebuilt page at
  `/next` now has a working Series workflow for its first and third steps. A person can load
  many pattern files at once, type a coordinate for each, sort by it, choose the walk order,
  and run the chain. The Run step shows each pattern's Rwp and where its fit started as the
  fits land, and a page opened after the run reads the same table off the record. First fit
  and Results are drawn in the strip and not built yet, so the strip says so. This PR is an
  early piece and can merge on green; the maintainer's look waits for the last PR (task 13).

  *Done.* Tasks 1-3. `gui/src/next/Series.svelte` holds both steps, `gui/src/next/seriesrun.ts`
  their pure helpers (the span, the order check, the fold of the run's events into a table,
  the record's merge). Tasks 2 and 3 landed as one commit because they share the component.
  `/code-review high --fix` found ten issues and seven fixes landed as their own commit: the
  record is no longer read mid-run or after a failed run, the Run table keeps the list and
  walk that ran, a run started elsewhere starts an empty table, a panel mounted mid-run
  replays the server's event buffer, and three smaller ones. Declined: a cold restart after a
  quarantined or skipped pattern reads "previous" until the record lands, because no event
  says it restarted cold (a stamp in `sequential._SeriesStream` would; that file is under
  Mike's #1786, so it waits); and the panel unmounting on a workflow switch is only covered
  by the replay, since keeping it mounted is a Frame layout change (task 5's question).
  One choice settled here: the progress gauge's fill is an accent wash
  (`color-mix` 70 % over `--line`), since `tests/test_gui_palette.py` refuses a solid accent
  fill and the rebuilt pages lay the accent over an area only as a wash.

  *Measured* (arm64 macOS, worktree venv `[dev]`, node 24.22.1). vitest 995 passed in 61
  files, two of them new (`Series.test.ts`, `seriesrun.test.ts`). svelte-check 0 errors.
  `tests/test_gui_*` python files named in Acceptance: 272 passed. Browser, local only:
  `tests/test_gui_series_browser.py` 1 passed (new), `tests/test_gui_layout_browser.py` with
  it 52 passed. Fast suite (`serial.py`, alone, playwright in the venv): 15358 passed, 438 skipped,
  32 xfailed; the one added test costs 7.29 s in that run, not marked `slow` because CI
  skips it (no playwright there) and the other `*_browser.py` files are unmarked too. Lint as CI runs it: ruff, ruff format on the tutorials,
  Vale (0 errors; its warnings are on manual lines this branch does not touch), skill caps,
  skill surface, audit delta, code references, rulebook limits all clean. Reader output
  unchanged. No rulebook edit; no heuristic the audit table covers (GUI only).

  *Gotchas.* `app.css` gives `.file` `display: inline-flex`, so a `td.file` stops being a
  cell; the file column's class is `fname`. `lib/help.test.ts` counts `title=` by finding the
  last `<` before it, so a `<` inside an attribute expression ahead of a title miscounts:
  derive the boolean first (`few`). A step button's `inner_text` carries a newline between
  its number and name.

  Next: task 4 (Results), then task 5 (the selected pattern, which decides whether Series
  stays mounted across a workflow switch), then Trends and Map (6, 7). Task 8's scrubber
  placement is drawn and brought to the maintainer before it is built.
