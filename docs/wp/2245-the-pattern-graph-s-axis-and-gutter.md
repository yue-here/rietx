# WP-2245 — the Pattern graph's empty difference axis and its blank right margin

Milestone: gui-overhaul · Status: 🔄 2026-11-24 — both fixes landed (PR #1822); two visual questions wait on the maintainer
Depends on: —
Priority: P3 2026-11-24 — two defects on the graph every refinement opens on

## Goal

The Pattern graph at `/next` labels only what it draws, and its plot reaches the legend gutter
the way the prototype's does. A pane that holds no value in view prints no tick labels, so the
difference pane before a fit no longer reads 100 and 0 under the intensity's 500 and 1. The
plot area ends where the gutter starts, instead of 25 px short of it.

## Context

Found 2026-11-23 by the WP-2243 look (`~/.cache/ghostshift/rietx/gui-r7/look/`, screenshot
`a-patterns-light.png`), outside the series work: "the Pattern graph's √-scale y labels read
500, 1, 100, 0 top to bottom, and the plot leaves about a fifth of its pane blank on the right".
No open WP owned the graph: WP-2216 built it and is closed, and the open GUI WPs (2211, 2227,
2231, 2243) are other tabs. Reproduced on the `nac` example at `origin/main` `661997aed`.

- **The labels.** 500 and 1 are the intensity pane's lowest two ticks on its √ axis. They are
  the prototype's rule (`niceTicks`: 1, 2 and 5 times a power of ten from 1 up, each kept 22 px
  from the last), reproduced by `next/rxplot.mjs`'s `decadeSplits`. 100 and 0 are the difference
  pane's. Before a fit that pane draws nothing, and uPlot ranges a scale with no data over 0 to
  100, so its axis labels a range no data has. Today's page `/` shares the defect through
  `src/rietx/viz/static/rxplot.mjs`: its empty difference pane reads 0, 50 and 100. The same
  fallback fires on a fitted pattern zoomed into a region the fit skipped, where the residual
  is null.
- **The margin.** The prototype's plot ends `Rr` = 112 px from the canvas edge and its legend
  labels start 10 px right of the plot. `/next` insets the chart host by `GUTTER` = 112 px for
  the legend, and uPlot then pads the plot's right by 25 px more (`autoPadSide`: half its
  default y axis width, for a side with no axis). Measured at 1500 × 950: plot area 80-562 px, host edge
  587 px, pane edge 699 px, legend labels from 591 px. The blank right of the plot is 137 px,
  20 % of the pane, against the prototype's 112 px. The 25 px also hold a 2θ label centred on
  the plot's right edge, which the canvas would otherwise cut in half.
- `rietx watch` and `rietx compare` draw with the shared module and have no legend gutter, so
  uPlot's right padding is their plot's only margin there. The margin fix is `/next`'s alone.
- The tier of each rule this WP adds: none. It adds no flag, threshold or automatic action.

## Non-goals

- The legend gutter's width. It is ruled (`gui/STYLE.md` § Plots, 2026-11-07) and matches the
  prototype's. Whether it narrows when it holds one label, or on a narrow pane, is a visual
  question for the maintainer (§ Questions).
- The √ axis's lowest label, 1. It is the prototype's rule (§ Questions).

## Tasks

- [x] 1. Reproduce both in a real browser on a real project, with screenshots.
- [x] 2. A pane that draws no value in view labels no range: both copies of `rxplot.mjs`, with a
  case in `tests/test_rxplot_browser.py`.
- [x] 3. The `/next` plot area meets the legend gutter; a `/next` browser case; the dist
  rebuilt.
- [x] Skill: none. The agent skill drives the Python API, never the GUI.

## Questions

For the maintainer, not settled here:

1. **The gutter beside a lone label.** Before a fit, and through the series workflow, the
   gutter holds only "Observed", so 112 px of the pane stays blank beside the plot: 18 % of a
   620 px pane, 40 % of a 280 px one. Options: keep the ruled width; or narrow the gutter to its
   longest label; or drop to an in-plot legend below some pane width.
2. **The √ axis's floor label.** The √ axis labels 1 at its foot, where the value is all but
   zero, and skips 2 to 200 when the pattern reaches 10⁵ counts, so the foot reads "500, 1".
   Options: keep the prototype's rule; or label the foot 0.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check && npm --prefix gui run build
git diff --exit-code src/rietx/gui/static
node --test tests/rxplot.test.mjs tests/watch_core.test.mjs tests/compare_core.test.mjs
.venv/bin/python -m pytest tests/test_rxplot_browser.py tests/test_gui_layout_browser.py -n 0
```

## References

WP-2216 (the Pattern graph at `/next`), WP-1461 (the chart module), WP-2243's look of 2026-11-23.

## Handover log

- **2026-11-24** — both defects fixed; two visual questions wait on the maintainer (PR #1822)

  The Pattern graph no longer labels a pane that has nothing in it. Before a fit, the difference
  pane's axis read 100 and 0, a range uPlot invents for a pane with no data; now it is blank, with
  no tick marks, gridlines or zero line. Today's page `/` and any zoom onto channels the fit
  skipped had the same fault, and both are fixed too. At `/next` the plot now ends where the
  legend gutter starts: the blank right of the plot fell from 137 px (20 % of a 683 px pane) to
  the prototype's 112 px. The gutter itself still holds one label before a fit. Whether it should
  shrink is § Questions 1, and the √ axis's foot label 1 is § Questions 2.

  *Done.*

  - Both copies of `rxplot.mjs`: `drawsData(u)` asks whether any shown series holds a finite value
    between the channels in view, cached per pane until the view, data or visibility moves.
    `quietWhenEmpty` wraps every labelled y axis without a fixed `range`: blank labels, and null
    from the ticks' and grid's filters. `drawZero` returns early on such a pane.
  - `/next`: `Pattern.svelte`'s `OVERHANG` = 25 px is passed as the panes' `padRight`, and the host
    is inset by `GUTTER − OVERHANG`, so the canvas reaches 25 px into the gutter. The plot ends at
    the gutter and a 2θ label centred on its right edge is drawn whole. The floating bars clamp to
    `columnWidth`, the host short of the gutter, as before. An export keeps uPlot's own padding.
  - `/code-review high --fix` found three things, all taken. It added the trajectory fix: a
    trajectory pane whose forward chain is null in view carried no series for the backward points
    it draws, so it now carries the backward chain as a second, unpainted series in both copies.
    The cut edge label it found led to `OVERHANG`; a first version set the padding to 0. Its third
    finding, the zero line at the foot of the empty pane, is the `drawZero` change. It called the
    last two visual calls. They are not: each restores what the graph drew before or what the
    prototype draws.
  - Tests: `test_a_pane_that_draws_nothing_in_view_labels_no_range` and the review's
    `test_a_trajectory_drawn_by_its_backward_chain_alone_keeps_its_labels` in
    `tests/test_rxplot_browser.py`; `test_the_rebuilt_plot_reaches_its_gutter_and_labels_only_what_it_draws`
    in `tests/test_gui_layout_browser.py`. The first and third failed on the unfixed code (checked by
    reverting the fix in place and rebuilding).

  *Measured* (`.venv` `[dev]` plus playwright 1.65.2, macOS arm64, Python 3.12, node v24.22.1;
  load average 21-60 from other sessions throughout).

  - vitest 67 files, 1030 tests passed; svelte-check 500 files, 0 errors; `node --test` over
    `rxplot`, `watch_core` and `compare_core`, 77 passed. All on the tree with main merged.
  - Every `tests/*_browser.py` file, `-n 4`, before the merge: 191 passed, 1 failed. The failure was
    `test_structure3d_browser.py`'s WebGL draw, which passed 8 of 8 run alone. The series browser
    test timed out once at load 60 and passed on the rerun.
  - Fast selection on the merged tree (`-n auto --dist loadgroup -m "not slow"`, playwright
    installed, so the browser files join it): 15911 passed, 440 skipped, 30 xfailed, in 15 min 57 s
    after 30 min queued behind two other runners' suites. The 3 added tests cost 4.4 s on this
    run (layout 2.1 s, the two rxplot cases 1.4 s and 0.9 s), none in the slow tail. No baseline
    run on main, so passed+skipped is not compared against one.
  - The CI lint job's steps run locally: ruff, ruff format on the tutorials, Vale (0 errors),
    `skill_caps`, `skill_surface`, `audit_delta`, `code_references --delta`, `rulebook_limits`,
    all exit 0. `tests.reader_output` exit 0.
  - Screenshots before and after, light theme, `nac` example:
    `~/.cache/ghostshift/rietx/gui-pattern-ticks/` (`before-*.png`, `after-*.png`, `after2-*.png`).

  *Gotchas.* uPlot draws axis labels on its canvas, so a browser test reads `axes[1]._values` or
  the canvas's pixels, never the DOM. uPlot's right padding is `autoPadSide`, half its default
  y axis size of 50, whatever size the axis is given.

  *Generality.* Not dispatched: no change to `_audit.py`, and no threshold, fallback chain or
  data correction. The rule added is about drawing.

  Next: the maintainer answers § Questions. Each answer is a small change to `Pattern.svelte` or
  `decadeSplits`. With both answered, this WP closes.
