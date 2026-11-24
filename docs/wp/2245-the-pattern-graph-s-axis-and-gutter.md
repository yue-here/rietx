# WP-2245 — the Pattern graph's empty difference axis and its blank right margin

Milestone: gui-overhaul · Status: 🔄 2026-11-24 — claimed by @yue-here
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
  the legend, and uPlot then pads the plot's right by half the y axis's width (its default for
  a side with no axis), 25 px more. Measured at 1500 × 950: plot area 80-562 px, host edge
  587 px, pane edge 699 px, legend labels from 591 px. The blank right of the plot is 137 px,
  20 % of the pane, against the prototype's 112 px.
- `rietx watch` and `rietx compare` draw with the shared module and have no legend gutter, so
  uPlot's right padding is their plot's only margin there. The margin fix is `/next`'s alone.
- The tier of each rule this WP adds: none. It adds no flag, threshold or automatic action.

## Non-goals

- The legend gutter's width. It is ruled (`gui/STYLE.md` § Plots, 2026-11-07) and matches the
  prototype's. Whether it narrows when it holds one label, or on a narrow pane, is a visual
  question for the maintainer (§ Questions).
- The √ axis's lowest label, 1. It is the prototype's rule (§ Questions).

## Tasks

- [ ] 1. Reproduce both in a real browser on a real project, with screenshots.
- [ ] 2. A pane that draws no value in view labels no range: both copies of `rxplot.mjs`, with a
  case in `tests/test_rxplot_browser.py`.
- [ ] 3. The `/next` plot area meets the legend gutter, its labels 10 px from the plot as the
  prototype draws them; a `/next` browser case; the dist rebuilt.
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
