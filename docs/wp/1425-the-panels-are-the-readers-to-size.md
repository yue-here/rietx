# WP-1425 — the panels are the reader's to size

Milestone: v1.5 · Status: ✅ 2026-09-16 — both seams are splitters, the two toggles are gone, and the plot is told when its width moves
Track: The live-watcher track
Depends on: 1430 (the page as files, so the port below is importable), 1426 (the legend must hold still under resize before a splitter makes resize continuous)

## Goal

The two seams of the `rietx watch` page, list against run and picture against
console, are splitters a reader can drag, collapse and restore. The sizes
survive a reload and are re-clamped against the window they reopen in. The
two toggle buttons are gone, their job done by the grips.

## Context

WP-1423 made the page two panels with a collapse each. The maintainer asked
for resizable panels. Separately, the two toggles were confusing; WP-1424
renames them as the interim, and this WP removes them, because a grip that
collapses is one control where there were three.

### What is on the page today

The page is four files under `src/rietx/watch/static/` (WP-1430): `index.html`,
`watch.css`, `watch.mjs` (the document) and `watch-core.mjs` (everything that
touches no DOM). A new file there needs a row in `watch.STATIC_FILES` and nothing
else, since the route, the content type and the `.gitignore` guard all read that
dict. The DOM half is `.mjs` because `node --check` reads a `.js` as CommonJS,
where the import of `watch-core.mjs` is a syntax error. Node cases live in
`tests/watch_core.test.mjs` rather than beside the module, since hatchling ships
everything under `src/rietx`; they are invoked from
`tests/test_watch_app.py::test_the_pure_half_of_the_page_is_unit_tested` (15 cases
today), which passes `--test-reporter=tap` because node picks its reporter by
whether stdout is a terminal. `@SUFFIX@`, `@DIST@` and `@HUE@` are gone. A file
cannot carry a token, so the three ride on `/api/runs` as
`payload.page.{suffix,dist,palette}`, read at boot into the module-level `HUE` and
`DIST`.

`#runs { flex: 0 0 72ch }` and `#console { flex: 0 0 30% }` are the two fixed
sizes. `applyPanels` writes `data-runs`/`data-run` on the body from a
`localStorage` key (`rietx-watch-panels`) and calls `Plotly.Plots.resize` on the
plot when the run panel reopens, because plotly's `responsive` option follows the
window and not the element. `togglePanel` refuses to close the last open panel.
The two buttons read `list` and `detail` since WP-1424, with `title` text and
their ids unchanged (`toggle-runs`, `toggle-run`); that rename is the interim this
WP's grips replace. The panel state is already split the way this WP wants
`clampSize`: `parsePanels(raw)` and `nextPanels(p, which)` sit in `watch-core.mjs`
with cases, and `watch.mjs` keeps `localStorage` and the document. Put the port
beside them.

`#run` is a container (`container-type: inline-size`) and the strip's slots are
tiered off it at 990 / 760 / 560 px, dropping whole slots rather than cutting every
one of them a little. A splitter inherits that for nothing: drag the panel and the
strip re-tiers, exactly as collapsing the list already does. Do not convert the
tiers to viewport media queries on the way, because the panel's width is not the
window's. Each slot carries an explicit `grid-column`, the tiers zero a track
through a custom property, and the 12 px between slots is each slot's own
`padding-right` rather than `gap` (a dropped slot would still be charged for a
gap). A new slot needs all three or it will pull its neighbours left when a tier
hides it.

The list's columns are declared `ch` widths sized for their worst content (WP-1423
rule 2 still stands), and the run column takes the remainder. WP-1424 measured that
column at about 12ch at the default 72ch panel and left it the flexible one, which
was the right call while every row in a batch said the same word. WP-1431's
`label=` changed the content: a caller names each run, so the column is the first
thing in the list that varies per row and is worth reading in full. A label long
enough to elide is now the ordinary case, and the `title` behind it (`runTitle`) is
a hover, so it does not serve a reader scanning the column. That column is where a
caller-supplied string competes with `stage`, which already elides. Nothing here
says widen it. That is this WP's measurement to make.

### The GUI already has the rules

`gui/CLAUDE.md` § Usability, from WP-1029, with the code in
`gui/src/lib/resize.ts` and `gui/src/panels/Splitter.svelte`:

- **Report a size, never write one.** The grip calls `onsize(size, done)`
  and the owner persists on the verb.
- **A stored size is not a settled size.** A drag clamps against the extent it
  happens in, and nothing clamps a width that outlives its window, so the
  owner re-clamps at render (`clampSize`, `fitColumns`). Widths chosen at
  1500 px reopened at 1000 px left a column 24 px wide.
- **One resize in flight, at most one queued** (`resize.ts:coalesce`), because
  a plotly resize per pointer move is a redraw per pointer move.
- The grip flows `inline`, because an absolute grip inside `overflow: auto`
  scrolls away from the edge it marks.

The page cannot import a Svelte component or the GUI's TypeScript. It ports
`clampSize` and `dragged` into `watch-core.mjs` (WP-1430) and the port is
pinned to the original: a `node --test` case table copied from
`gui/src/lib/resize.test.ts`, with a comment naming the source and a
`test_watch_app.py` check that the two tables are equal text. If the GUI's
test changes its cases, the copy fails until it follows.

### The documented pattern

WAI-ARIA Authoring Practices, window splitter: the grip is focusable,
`role="separator"`, `aria-orientation`, `aria-valuenow/min/max`, arrow keys
move it, Enter or a double-click collapses and restores. It is a pattern and
not a library, so the JavaScript is still the page's; the pattern fixes what
the keyboard does so nobody invents it.

### Measured before, to take at the start

WP-1423's browser harness (`tests/test_watch_browser.py`) is the tool, and it took
no diff through WP-1430, so it stays the bar: if it moves, the page moved. Record,
over a drag of the list seam from 72ch to 40ch: how many `Plots.resize` calls
plotly saw, and the plot's inner size before and after.

WP-1426's legend fix has landed, so the picture holds still while a panel moves.
The legend is anchored inside the paper (`y: 1, yanchor: 'top'`), the plot area's
top is the declared 8 px margin at every width, and its height is constant.
Resizing a panel now changes the picture's width alone, which is what makes a drag
measurable; before that fix, narrowing a panel also shortened the picture.
Measured, `[dev]` + playwright, darwin/arm64, at 1400 / 1000 / 700 px viewport:
plot area `[58, 8, 807, 503]`, `[58, 8, 407, 503]`, `[58, 8, 107, 503]`. Before the
fix: top 46 / 65 / 139, height 465 / 446 / 372.
`tests/test_watch_browser.py::test_the_legend_is_a_dimension_the_page_fixes` reads
the geometry at those three widths and is where a panel change gets checked against
the legend.

The cost 1426 hands over is at narrow widths and it belongs to this WP. A
horizontal legend still wraps, and inside the paper it wraps over the data rather
than pushing it down. At an 800 px window with both panels open the run panel is
about 280 px, the legend takes five rows, and it covers the top quarter of the
intensity panel, tallest peak included. `withAlpha(HUE.ground, 0.72)` keeps the
curve faintly visible through it, which is a mitigation and not a fix. The fix is a
panel wide enough for the picture, which is this WP.

#### Measured, 2026-09-16, before any change

`[dev]` + playwright (not a `[dev]` extra), darwin/arm64, 1400x900 viewport,
cached chromium-1223. The seam moved by setting `#runs`'s flex basis, which is
what a drag will do.

**The plot does not hear the seam move.** From 72ch to 40ch: **0**
`Plots.resize` calls, as the WP guessed. The sharper statement is the one the
count does not make. The plot *element* followed the seam, 879 px wide to
1110 px, while plotly's inner size stayed at `[58, 8, 807, 503]` throughout.
The picture is drawn at the old width inside a box 303 px wider than it, and
nothing repairs that until the run panel is closed and reopened, where the one
`Plots.resize` call in `applyPanels` fires and the inner size becomes
`[58, 8, 1328, 503]`. So the splitter's resize is not a refinement of an
existing behaviour. There is no existing behaviour.

**The run column is the first casualty of any narrowing, and it dies whole.**
The other five columns are declared `ch` and held their widths to the pixel at
every seam position (state 94, stage 108, Rwp 72, GoF 65, started 79). The run
column takes the remainder, so it absorbs the entire loss. With a 20-character
label, the WP-1431 ordinary case:

| seam | panel | run column | label needs | elided |
|------|-------|-----------|-------------|--------|
| 90ch | 651px | 231px | 159px | no |
| 80ch | 579px | 159px | 159px | no |
| 72ch | 521px | 101px | 159px | **yes** |
| 64ch | 463px | 43px | 159px | yes |
| 56ch | 406px | **0px** | 159px | yes, and the table overflows the panel |

Two numbers for the tasks below. The list's floor is **56ch**: under it the run
column is gone and the table scrolls sideways inside the panel, so that is where
the splitter clamps rather than at an invented round number. And the default
72ch already elides an ordinary label. The answer to this WP's open question is
that the default is too narrow for what WP-1431 put in that column, not that the
column wants a wider declared share of a panel that is now the reader's.

## Non-goals

- Column widths inside the list. Declared (WP-1423 rule 2).
- Persisting sizes anywhere but `localStorage`. The page has no project and no
  settings document; the GUI's `ProjectDoc.ui` is not this page's.
- Splitting the picture from the strip. The strip is one line by rule.
- The GUI's own panels, which already have this.

## Tasks

- [x] Measure: the drag probe above, before any change, in the handover
- [x] `clampSize` and `dragged` in `watch-core.mjs`, pinned to the GUI's cases
- [x] The list splitter: a grip between `#runs` and `#run`, pointer and
      keyboard, sizes in px re-clamped at render, `Plots.resize` coalesced to
      one per animation frame
- [x] The console splitter: the same grip between `#picture` and `#console`
- [x] Collapse and restore on the grip (double-click, Enter), the last panel
      refusing to close; the two buttons and `data-runs`/`data-run` removed,
      the stored key migrated or dropped
- [x] Browser test: drag moves the seam, reload keeps it, a 900 px viewport
      re-clamps it, the plot's inner size follows
- [x] Manual: `docs/manual/using/cli.md` § `rietx watch`; **there is no
      screenshot of this page to update** — every entry in
      `make_screenshots.py`'s `SHOTS` is of the GUI, and `cli.md` carries no
      image at all
- [x] Skill: none. The page is a human's.

## Acceptance

```sh
.venv/bin/python -m pytest tests/test_watch_app.py tests/test_watch_browser.py
.venv/bin/python -m ruff check src tests examples
node --test tests/watch_core.test.mjs
npm --prefix gui test && npm --prefix gui run check
```

The browser test drags each grip, reloads, and asserts the size persisted and
was clamped at a 900 px viewport. `node --test` runs the GUI's `clampSize`
cases against the port. The browser test skips without a cached chromium, CI
included; the handover names the skip.

**Corrected 2026-09-16.** This block said `node --test src/rietx/watch/static/`,
which has never run anything: WP-1430 put the node cases in
`tests/watch_core.test.mjs` rather than beside the module, because hatchling
ships everything under `src/rietx`, and `static/` has held four files since.
The line was written before 1430 chose that layout. `node --test` on a
directory with no test file in it exits non-zero with `MODULE_NOT_FOUND`, so
this was loud rather than silent, but it was never this WP's check. The vitest
line is new: the port's case table lives in the GUI's own test file, so a
change here can fail a suite over there.

## References

- WAI-ARIA Authoring Practices, Window Splitter pattern.
- WP-1029 (the GUI's resize rules), WP-1423 (the panels), WP-1430 (the module
  the port lives in).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**`lib/resize.ts`'s cases are copied out, and `gui/src` is hashed whole**
(WP-1425). `rietx watch` cannot import TypeScript, so it ports
`clampSize`/`dragged`/`axisOf` and `tests/test_watch_app.py` compares
`resize.test.ts`'s `ported cases` block against `tests/watch_core.test.mjs` **as
text**, comments included: edit them here and the copy fails until it follows.
`build_info.py` hashes `gui/src/**/*`, test files included, so editing any test
here marks the committed dist stale and costs an `npm run build`.

## Handover log

### 2026-09-16 — the two seams are the reader's, and the picture finally hears them move

The `rietx watch` page's two divisions are now splitters you drag. The list
against the run, and the picture against the log. What this buys is not mainly
the dragging: it is that the plot was never told when its width changed. A seam
moved by the old buttons redrew the picture; a seam moved any other way did
not, so the plot sat at whatever width it was last told about inside a box that
had moved on. Measured before the change, a 72ch-to-40ch move drew zero
`Plots.resize` calls and left the picture 303 px narrower than its own element.
Both toggle buttons are gone with the grips doing their job, and every floor
the seams stop at is a number measured on the page rather than one somebody
liked. The cost is one capability: the run panel can no longer be hidden
outright, because a splitter's collapse belongs to the pane its grip sizes.

**Done.** All eight tasks. The port (`clampSize`, `dragged`, `axisOf`,
`coalesce`) is in `watch-core.mjs`, pinned to the GUI's own cases by a block of
text copied character for character between `gui/src/lib/resize.test.ts` and
`tests/watch_core.test.mjs` and compared by
`test_watch_app.py::test_the_ported_drag_arithmetic_keeps_the_guis_cases`. The
GUI's three hand-written describes became that table rather than sitting beside
it, so the cases have one authority on its side too. Both grips carry the
WAI-ARIA window splitter keyboard: arrows at 16 px, Shift at ten times that,
Home and End for the stops, Enter to collapse. `parsePanels`/`nextPanels` are
gone, replaced by `parseLayout`/`nextLayout` under a new storage key
(`rietx-watch-layout`); WP-1423's `{runs, run}` is read once for the one bit
with a home here and then removed.

**Measured** (`[dev]` + playwright, no jax, no torch, darwin/arm64,
cached chromium-1223, 1400x900 viewport unless said otherwise):

- *The defect, before any change.* 72ch to 40ch: **0** `Plots.resize` calls.
  The plot element followed, 879 px to 1110; plotly's inner size stayed
  `[58, 8, 807, 503]` throughout. Closing and reopening the run pane fires the
  one `applyPanels` resize and the inner size becomes `[58, 8, 1328, 503]`.
- *The list's floor, 63ch.* The five declared columns are 58ch and that is
  exactly the table's whole min-content (419 px; 1ch = 7.225). The run column
  takes the remainder, so it absorbs every narrowing alone: with a 20-character
  label it is 231 px at 90ch, 159 at 80ch (where the label just fits), 101 at
  72ch, 43 at 64ch, and 0 at 56ch with the table overflowing the panel. `run`
  as a heading inks 36 px, so 58 + 5 is the width below which a column cannot
  show its own name. Plus the pane's 1 px border, read off
  `offsetWidth - clientWidth`.
- *The run pane's keep, 340 px.* Legend rows against pane width: 1 row at
  899 px, 2 from 699 to 459, 3 from 419 to 339, and **6 rows / 124 px** at 299
  and below — a quarter of the 503 px plot, which is the cover WP-1426 handed
  over. The cliff is between 339 and 299.
- *The log's floor, 51 px*: three lines of 13 px plus its 12 px of padding,
  against `#picture`'s declared `min-height: 180px`.
- *Suites.* Fast selection 5185 passed, 132 skipped, 2:24, this session alone on the machine. Net
  **+7** pytest tests (eight added, one renamed away), no new skip.
  `test_watch_browser` 19, `test_watch_app` 48, `node --test` 31 pass, vitest
  584 over 22 files (24 `it` blocks in `resize.test.ts` became 17, so that
  suite is 7 lower than the 591 it was), svelte-check 381 files 0 errors, ruff
  clean, sphinx `-W` clean. The full selection did not run: this WP touches a
  page, its tests and the manual, and moves no measured number
  (`tests/CLAUDE.md` § Running, rung 3).

**Decisions a successor should not have to re-derive.**

- *The run pane is no longer collapsible.* `toggle-run` could hide it; no grip
  can, because a splitter's collapse belongs to the pane its grip sizes and the
  run pane holds the picture. A reader who wants a wide list drags, or presses
  End on the list grip for the same thing in one key. This is the one shipped
  capability the WP removed, and it is the maintainer's to overturn.
- *The 72ch default stays.* The WP left the run column's width as this
  session's measurement, and the measurement says 72ch already elides an
  ordinary WP-1431 label, which wants 80ch. It was left alone anyway: widening
  the default takes 58 px of picture from every reader to serve label-readers,
  and picture width is the scarce thing WP-1426 handed over. The seam is now
  the reader's and the choice persists, so one drag settles it per person.
- *`coalesce`, not a per-animation-frame gate.* The task line said the frame;
  `gui/CLAUDE.md` (WP-1032) says every `Plots.resize` goes through `coalesce`,
  and the reason is the trailing run — a frame gate drops the last ask and
  leaves the plot at the size the drag started at. `Plots.resize` returns a
  promise, which `coalesce` already awaits.

**The review pass.** `/code-review high --fix` raised four and all four are
applied; nothing was declined. Two were defects in this WP's own work and
neither had a test, so each now has one, made to fail by reverting its fix.
The migration was **spent on one render** — `readLayout` dropped WP-1423's key
without writing the new one, and nothing else stores a layout, so a reader who
had the list collapsed saw it collapsed exactly once. And a **picture-less run
with a collapsed log showed nothing at all**: `#run.full` hides the console's
grip, the grip is the collapse's only control now, and the two meet on every
run that has not written a snapshot. That second one is the old "closing the
last open panel opens the other" rule, which I had reasoned was trivially
satisfied once the run pane stopped being collapsible; it was not. The other
two were an `oneCh()` reflow four times a pointer move and a dead
`.toggle[aria-pressed]` rule.

**Gotchas, each found by a test rather than by reading.**

- *Read a rect, write a basis, and the box model bites.* The grips measure a
  pane's border box and write its flex basis, which is content-box by default,
  so every arrow key moved the seam 15 px and reported 16 — and the log's
  padding is 12 of them. Both panes are `box-sizing: border-box` now.
- *A stored size is a number or it is nothing.* `Number('420')` is 420, and
  this is the page's own JSON, so a string there is corruption rather than a
  value in another spelling.
- *Editing a GUI test file costs a dist rebuild.* `build_info.py` hashes
  `gui/src/**/*`, test files included, so the case table's new home marked the
  committed dist stale and failed both `test_gui_dist` guards. The bundle came
  back byte-identical; only `build-info.json`'s `source_hash` moved. Now a rule
  in `gui/CLAUDE.md`.
- *A guard that banned a string.*
  `test_the_dialog_says_what_a_click_does_to_the_other_process` asserted that
  `keydown` appears nowhere in the script. Its claim is that no keyboard route
  reaches the stop button, so it now checks that every key listener sits on a
  grip: one on `document` or `window` could reach the verb, one on a grip that
  must be focused first cannot. Made to fail on purpose before being kept.
- *The acceptance block was stale.* It said
  `node --test src/rietx/watch/static/`, which has never run anything — WP-1430
  put the cases in `tests/` because hatchling ships everything under
  `src/rietx`, and the line predates that choice. `node --test` on a directory
  with no test file exits non-zero with `MODULE_NOT_FOUND`, so it was loud
  rather than silent. Corrected in the WP, with the vitest pair added, since a
  change here can now fail a suite in `gui/`.
- *There is no screenshot of this page.* Every entry in
  `make_screenshots.py`'s `SHOTS` is of the GUI and `cli.md` carries no image,
  so task 7's second half had nothing behind it.

**Next.** [1429](1429-one-palette-and-one-theme-for-three-pages.md) is the next
rung and this WP added to its pile: the grips carry four more hard-coded greys.
Then [1427](1427-what-a-poll-costs.md), then
[1428](1428-open-in-the-gui-without-touching-the-fit.md), whose question is the
maintainer's. The two open questions this WP leaves are both the maintainer's
and both stated above: whether the run pane should be collapsible again, and
whether the 72ch default should move to 80ch now that a caller's `label=` is
what fills the column it squeezes.

- **2026-09-16** — created, from the maintainer's reading of the page over the
  demo job; revised the same day: the toggle rename went to 1424 as the
  interim, and the port's pin is now a copied case table under `node --test`.
