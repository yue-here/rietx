# WP-2240 — the peaks-and-indexing workflow at `/next`: pick peaks, fit peaks, index, judge

Milestone: gui-overhaul · Status: 🔄 2026-11-22 — claimed by a ghostshift runner; tasks 1-4 are the first PR
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
- [ ] 5. The peak gestures on the Pattern graph under interaction rules 1 to 12: click adds
  with a dashed hover mark, a mark click selects with its bar (2θ, Used or Not used, Delete,
  ×), drag moves, Esc during and right after a drag, Option-click removes, right-click opens
  the menu; a typed add row at the table's foot (row 194); ⌘Z and ⇧⌘Z over peak edits.
- [ ] 6. The Fit step and the group windows with per-line curves in the Peaks graph tab while
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

- **2026-11-22** — filed by a ghostshift runner for the milestone's R6 row, which had no WP. No
  open WP owns the workflow at `/next`: WP-2202 built the same design inside today's Peaks tab,
  and WP-2214 makes its PR #1526 a source that closes once R6 takes its halves.
