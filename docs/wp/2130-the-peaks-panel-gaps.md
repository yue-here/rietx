# WP-2130 — the Peaks panel's gaps: the search coverage always said, Adopt on every row

Milestone: gui-overhaul · Status: ✅ 2026-11-09 — the coverage line and Adopt on every row merged in #1490; the peak-mark colour moved to the milestone's palette row (ruled 2026-11-09)
Depends on: 2123, 2124 (the shell it draws in, and the adopt arm's `picked` and `why`)

## Goal

The existing Peaks panel (`gui/src/panels/Peaks.svelte`) says how much of the search ran,
whatever the run found. Every candidate row can be adopted, and a row the gate did not pick
says its grade and caveats beside Adopt. The peak marks get the colour the maintainer settled,
or the conflict that colour has with the shipped palette goes to the maintainer with numbers.

This is not the Peaks and indexing redesign (round 11 of the workshop: four steps, the
candidate table's eight columns, lens marks, per-line curves). That is a later piece.

## Context

### Where this comes from

The GUI overhaul was designed between 2026-11-06 and 2026-11-08 in twelve rounds of
prototypes the maintainer reviewed on screen (`docs/milestones/gui-overhaul.md`). Round 11
built the indexing workflow on rietx's own output for fluorapatite (`FAP.XRA`, the shipped
lab Cu Kα pattern). It found three defects in today's Peaks panel and left them for the port,
by the maintainer's ruling of 2026-11-08 that the design work changes nothing on `main`. The
record lists them in § Owed to the port. WP-2124 fixed the server half of the indexing step
and named these three as frontend work "not here".

1. **The panel hides the search's coverage whenever there are candidates.** The panel shows
   `systems_searched`, `search_complete` and the run-level `INDEX_*` diagnostics only in its
   no-candidate branch. With candidates, a run that stopped at its time limit before reaching
   orthorhombic, monoclinic and triclinic reads exactly like a finished one. WP-1042's rule is
   that what was not reached is said loudly (`src/rietx/indexing/CLAUDE.md` § The scheduler,
   the presets and the stream; `INDEX_BUDGET_EXHAUSTED` names the three states searched,
   truncated and not reached in its `where`). Measured by the workshop on FAP's default search:
   cubic, hexagonal and trigonal searched, trigonal stopped early, orthorhombic, monoclinic and
   triclinic not reached, 12 candidates, none graded `high`.
2. **Adopt follows the gate.** The panel enables Adopt only on the row `best_or_none()`
   picks, through the adopt arm's `allowed`. On FAP nothing reaches `high`, so no row can be
   adopted, the right cell included.
3. **The peak marks lose to the data.** `--plot-peak` (purple, `#8c257e` light and `#e687d5`
   dark, `src/rietx/viz/theme.py`) is hard to see over the observed points in the high-angle
   peak forest.

### The rulings this rests on

- **Adopt: option B (Yue, 2026-11-08).** A person may adopt any candidate cell. One the gate
  (`best_or_none()`) did not pick shows its grade and caveats beside Adopt, and the history
  node records them. This reverses WP-1027's gated Adopt for the GUI, on WP-1043's governing
  sentence (the maintainer's, 2026-08-06): give a person "all the information, and let the
  user, human or machine, be the judge". WP-2124 built the server half: every row of `GET
  /api/index/result`'s `adopt` arm carries `picked` (the gate's pick) and `why` (the sentence
  an adoption of any other row writes into its `edit_model` node), and `index_adopt` takes any
  row. `allowed` stayed as `picked` under its old name for this panel until it was redrawn.
- **Never a confident singleton** (root CLAUDE.md § Indexing; `src/rietx/indexing/CLAUDE.md`).
  The candidate list is the answer and the gate's pick is a badge on one row of it. Enabling
  Adopt everywhere must not make any row read as "the answer".
- **Not reached must be loud** (WP-1042, above).
- **The peak-mark colour (Yue, 2026-11-08, round 11b and 11c).** Peak marks must read in the
  high-angle peak forest: lenses that echo the hkl ticks, larger, higher above the peak and in
  a more eye-catching colour than the thin bars. The workshop drew them in Okabe-Ito blue,
  `#0072B2` light and `#56B4E9` dark, "the complement of the orange fits". The maintainer
  closed round 11 on 2026-11-08 with every call standing.

### What the colour would collide with (measured 2026-11-09)

The workshop's palette is not rietx's. In the prototype the difference curve is grey
(`#6b6259`/`#8f8f8f`) and the accent orange; in rietx both are blue (`--plot-diff` and
`--accent` are `#1f5fa8` light). `tests/test_gui_palette.py` holds every plot layer to the
phase palette's 0.13 OKLab floor against every other plot colour (WP-1210), because the peak
layer once borrowed `--accent` and `--bad`, which are the difference and calculated curves to
the last digit on the light theme. Distances from `structure3d._oklab_distance`, the package's
one colour distance:

| Mark colour | to `--plot-diff` | to `--accent` | to the nearest phase colour | to `--plot-obs` |
|---|---|---|---|---|
| `#0072B2` (light, ruled) | 0.053 | 0.053 | 0.187 | 0.166 |
| `#56B4E9` (dark, ruled) | 0.078 | 0.038 | **0.000** (it is `--phase-2`) | 0.143 |
| `#8c257e` (light, shipped) | 0.197 | 0.197 | 0.227 | 0.242 |
| `#e687d5` (dark, shipped) | 0.199 | 0.168 | 0.082 | 0.179 |

So the ruled blue fails the floor three ways: on the light theme it sits 0.053 from the
difference curve (the floor is 0.13), and on the dark theme it is the third phase's tick
colour exactly. The free hue space WP-1210 measured is magenta and green alone, and green is
the candidate overlay's. A measurement contradicts a ruling here, so the colour goes to the
maintainer rather than being changed on a runner's judgement (§ Decision for the maintainer).

### The pieces

- `gui/src/panels/Peaks.svelte`: the indexing section (the candidate table, the extinction
  table's space-group buttons).
- `gui/src/lib/peaks.ts`: `AdoptVerdict` and a pure helper for the coverage line, tested in
  `lib/peaks.test.ts`.
- `src/rietx/gui/session.py` `index_result`: drops `allowed`, which nothing reads once the
  panel reads `picked` (a declared name with no reader, WP-1076). A one-line edit inside one
  function, because other runners edit this file.
- `src/rietx/viz/theme.py`, `gui/src/tokens.css` (generated), `tests/test_gui_palette.py`: the
  colour, if the maintainer rules on it.
- `tests/test_gui_layout_browser.py`: a Peaks-panel case with real clicks.

### The tier of each rule this WP adds

None. The coverage line quotes the result's own fields and diagnostics; the Adopt button reads
the server's arm.

## Non-goals

Not here, left for the piece that redraws the Peaks panel or a WP of its own:

- Per-line peak curves (`PeakEditor.curves` serves each group's sum only; round 11b toggles
  each line's curve). Needs a route.
- A right-click context menu on plot objects (adopted interaction rule 12, 2026-11-08). Today
  right-click removes a peak (WP-1032).
- Undo for peak edits (agreed 2026-11-08). Peak edits live in `peaks.json`, outside the
  history tree, so undo needs its own record there.
- The lens mark shape, its height above the peak and the stacking of near-duplicate marks
  (round 11c). This WP changes at most the colour.
- The candidate table's eight columns, related rows marked ("c doubled of #2"), the four-step
  workflow, the Le Bail check's absent lines as tick indices.
- The panel's look. This WP fixes gaps in the existing panel only, so its screenshots look like
  today's GUI. The round-11 Peaks redesign is a later piece (§ Rulings of 2026-11-09).
- The peak-mark colour, deferred to the palette piece (§ Rulings of 2026-11-09).

## Tasks

- [x] 1. The coverage is said whatever the run found. Above the candidate list (and in the
  no-candidate branch, as before): the systems searched, the ones whose search did not
  complete, and every run-level diagnostic with its `where`, so `INDEX_BUDGET_EXHAUSTED`'s
  "not reached: …" reaches the screen. Vitest: a result with candidates still shows them.
- [x] 2. Adopt on every row, reading `picked` and `why`. The `best_or_none()` badge follows
  `picked`; a row it does not pick shows the server's `why` under its grade, in the same row
  as Adopt (beside the button it widened the table past the side panel); the extinction
  table's space-group buttons are enabled for any screened candidate. `index_result` drops
  `allowed`. Vitest and `test_gui_peaks.py` updated.
- [~] 3. The peak-mark colour: measured above and taken to the maintainer. Deferred, by his
  ruling of 2026-11-09, to a palette piece that adopts the site theme (not yet filed). This
  PR leaves `--plot-peak` as it is (§ Rulings of 2026-11-09).
- [x] 4. A Peaks-panel browser case, in `tests/test_gui_peaks_browser.py` beside the layout
  test whose landmarks it reuses: a served indexing answer, real clicks on the Peaks tab, a
  row's disclosure and Adopt, with the coverage line and the history node asserted, and no
  shell landmark moved.
- [x] Tests: `npm --prefix gui test`, `npm --prefix gui run check`, the dist rebuilt,
  `tests/test_gui_manual.py` (no manual screenshot shows the Peaks panel, so none changed),
  `tests/test_gui_palette.py`.
- [x] Manual: the GUI guide's indexing section says any row can be adopted.

## Decision for the maintainer: the peak-mark colour

**The decision.** Which colour the picked-peak marks take on the Peaks tab. It comes to the
maintainer because a measurement contradicts his ruling of 2026-11-08, and it is a visual
question.

**Why it matters.** The marks are the dots the picker puts on each line it found; on the
Peaks tab a person clicks, drags and removes them. Today they are purple, and the fitted
peak profiles and their residual are a lighter magenta of the same hue, so in the dense
high-angle region the marks merge into the fit lines (seen on FAP's 183 picked lines). The
ruled blue separates them from the fit. But in rietx's palette blue is already taken: the
difference curve and the chrome accent (buttons, links) are blue. A plot mark that shares a
hue with another plot colour is the defect WP-1210 was written to remove, and
`tests/test_gui_palette.py` fails on it (table in § Context). Importance: minor. It changes
how one layer on one tab reads, and every option is a two-line change to undo.

**Aim.** The marks read at a glance in a peak forest, for a person editing a peak list, without
being mistaken for another layer.

**Options.**

- **A. The ruled values**, `#0072B2` light and `#56B4E9` dark, with the palette test naming the
  three collisions as exceptions. The marks stand out from the grey points and the magenta fit
  (screenshots below). Light: 0.053 from the difference curve, which on the Peaks tab is in the
  lower pane and is the peak-fit residual (magenta) until a fit exists. Dark: the same colour as
  the third phase's reflection ticks, which share the plot after a fit with three phases.
- **B. The ruled light value, and a dark blue chosen off the phase palette.** Removes the exact
  dark collision; the dark mark is still near the accent (any blue is). Needs one more colour
  chosen, which is itself a visual call.
- **C. Keep purple**, and get the visibility from the mark's shape: the lens, larger and higher
  above the peak, which round 11c built together with the colour. That is the Peaks redesign's
  piece, not this WP. The palette test stays as it is.
- Dropped: moving the difference curve to grey as the workshop draws it. It clears only the light
  collision, not the accent or the dark phase tick, and recolours a curve on all three browser
  surfaces.

**Practice** (recall, not checked against the programs' docs): no common convention for picked-
peak marks; difference curves are grey in TOPAS, cyan in GSAS-II and blue in FullProf's
WinPLOTR, so rietx's blue difference curve is one of several conventions.

**Recommendation.** Lean B, close call. The crux is whether a blue dot over the data can be
mistaken for the blue difference curve or a link. They are in different panes and are
different marks, so the light collision costs little; the dark mark being the exact colour of
a phase's ticks costs more, because round 11b asks the marks to echo the ticks in shape. If the
FAP screenshots show the blue marks reading as chrome, C wins.

Screenshots of FAP's picked peaks in both colours and both themes were taken in chromium with
the colour overridden on the page; the drawn colour was confirmed by sampling the canvas
(about 7200 pixels of the mark colour in each of the four). They are local to the runner's
machine and named in the PR's hand-off, not committed.

### Rulings of 2026-11-09 (Yue Wu)

**The mark colour is not changed in this PR.** Yue was shown the four options above: the
ruled Okabe-Ito blue with test exceptions (A), a new dark blue (B), today's purple (C), and a
wider plum and pink tone gap. He answered: "I am not liking the colours. what happened to the
colours I chose in the workshop?"

The finding behind that answer. His ruling of 2026-11-06 was "one default theme consistent
with the site". That theme has warm neutrals, the orange accent `#c65d0a`, an orange
calculated curve and a grey difference curve. No port piece adopts that palette yet. The
shipped GUI kept `theme.py`'s blue accent and blue difference curve. The ruled blue `#0072B2`
was chosen as the complement of orange fits. It collides with the plot only under the old
palette, which is what the table in § Context measured.

So the mark colour moves to a palette piece that adopts the site theme. That piece is still to
be filed. It re-measures the mark colour against the new palette under WP-1210's floor.

**The panel's look is not this WP's.** Yue commented that the screenshots look like the old GUI
rather than the new one. This WP fixes only gaps in the existing panel: the coverage line and
Adopt on every row. The round-11 Peaks redesign is a later piece. It will be judged against
the GUI style guide the port is about to distil.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build && npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_peaks_browser.py tests/test_gui_peaks.py tests/test_gui_manual.py tests/test_gui_palette.py tests/test_gui_dist.py -n auto --dist loadgroup
.venv/bin/python -m ruff check src tests examples
```

## References

- WP-1027 (the GUI peak picker and the gated Adopt), WP-1042 (not reached must be loud),
  WP-1043 (let the user be the judge), WP-1210 (the peak layer's palette and its floor),
  WP-2124 (the adopt arm's `picked` and `why`), WP-2123 (the layout shell).
- The gui-overhaul milestone record, `docs/milestones/gui-overhaul.md` § Owed to the port.

## Handover log

### 2026-11-10 — closed; the colour moved to the palette piece

PR #1490 merged on 2026-11-09. The Peaks panel on `main` says what an indexing search covered
whatever it found, and every candidate row offers Adopt. The third task, the peak-mark colour,
was never built here. The maintainer ruled on 2026-11-09 that it moves with the palette piece,
because the ruled blue was chosen against an orange fit that `main` does not have yet. The WP's
title no longer names the colour, so the index row says what this WP shipped.

- *Leftovers, and where each went.* The mark colour: the row "The palette" in
  `docs/milestones/gui-overhaul.md` § Designed, not yet filed, which already lists it. The
  `--plot-peak` item in § Owed to the port now points at that row. The panel's look, the lens
  mark and the candidate table are the row "Peaks and indexing". Per-line curves, the
  right-click menu, undo for peak edits and the Le Bail check's absent lines as tick indices
  were already items in § Owed to the port. The narrative went to `docs/milestones/v1.12.md`.
- Closed by the batch close-out of the port's merged WPs, PR #1516. Docs only; no test moved.
- Next: none here. The palette piece re-measures the mark colour under WP-1210's 0.13 OKLab
  floor.

### 2026-11-09 — two of three in; the colour waits on the maintainer (PR #1490)

The Peaks panel now says how much of an indexing search ran, whatever the search found, so a
run stopped at its time limit no longer reads like a finished one. Every candidate cell can be
adopted from the panel, and a row the gate did not pick says why under its grade, in the
sentence the adoption records. The peak-mark colour is unchanged. The blue the maintainer
ruled collides with rietx's blue difference curve and accent, and on the dark theme it is a
phase's tick colour exactly, so it goes back to him with numbers (§ Decision for the
maintainer). Next: the maintainer picks A, B or C there; then a short follow-up commit on this
WP applies it (`theme.py`, `python -m rietx.viz.theme > gui/src/tokens.css`, the palette test,
a rebuilt dist, and the drawn colour read off the canvas).

- *Done*: items 1, 2 and 4, and the manual. `index_result` drops the arm's `allowed`. The
  `why` sentence moved from beside the Adopt button to under the row's grade, because beside
  the button it widened the table past the side panel and chromium cut it after
  "not best_or_none()'s" (settled by Claude, reversible: under the grade; alternative a
  sub-row, or beside the button with the table scrolling). The coverage block quotes the
  library's own words for an incomplete search (settled by Claude, reversible; alternative the
  workshop's "Not searched: … / Search these", which is the redesign's). The gate's pick keeps
  its green badge and row tint from WP-1027 (settled by Claude, reversible; alternative drop
  the tint so no row is coloured). The `/code-review high --fix` pass made four fixes
  (706c03598): the docs said "beside Adopt" where the code puts it under the grade; the
  coverage codes are `<Help>` terms; a `where` loop keyed by position, since one diagnostic
  can repeat a string; the WP's task 4 and acceptance line. Two findings declined: the
  placement itself (it is the maintainer's call, listed above) and putting the sentence on the
  extinction table's space-group buttons (new visible prose, a design change; the node still
  records it).
- *Measured* (`[dev]` venv plus playwright, darwin/arm64, alone on the serial lock): fast suite 14476 passed, 410 skipped, 32 xfailed in 11:07, on the branch with main merged; this WP adds two python tests (the browser file, 6.6 s together, skipped on CI where no chromium is cached). vitest 24 files, 615
  passed; svelte-check 393 files, 0 errors; three vitest cases added. The new browser file: 2
  passed. `tests/test_gui_layout_browser.py` 12 passed serially. `python -m tests.reader_output`
  exit 0. The colour table in § Context, and screenshots of FAP's 183 picked lines in both
  colours and themes, kept on the runner's machine.
- *Gotchas*: `test_a_pending_edit_moves_nothing_in_the_action_bar[stacked]` (WP-2123's) failed
  once under `-n auto` beside the other browser files and passed alone; it types right after a
  click. Overriding `--plot-peak` inline on the page repaints nothing until the theme changes,
  so a colour comparison clicks the theme buttons and then reads the canvas.
- *Stacking*: on WP-2123's branch (PR #1476, open); this PR merges after it.

- **2026-11-09** — the maintainer's rulings recorded (§ Rulings of 2026-11-09). The mark
  colour is deferred to a palette piece that adopts the site theme, still to be filed, and
  task 3 is marked deferred. The panel's look is the round-11 redesign's, a later piece judged
  against the GUI style guide the port is about to distil. Nothing implemented. Main merged in
  first: WP-2125's preview route (#1479), WP-2126's Parameters panel (#1484) and WP-2127's
  Plan tab (#1483).

- **2026-11-09** — filed by a ghostshift runner from the gui-overhaul record's § Owed to the
  port. No open WP owns these: WP-2124 named them "not here", and the open gui-overhaul runners
  own the Background tab (2129), the Parameters panel (2126), the Plan tab (2127) and the
  Interactive tab (2128), none of which edits `Peaks.svelte`. Stacks on WP-2123's branch
  (PR #1476), which carries the shell and the milestone record.
