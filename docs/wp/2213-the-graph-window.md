# WP-2213 — the graph window: legend switches, a view menu, regions as plot objects

Milestone: gui-overhaul · Status: ⬜
Depends on: 2200 (the palette); #1517 (its pull request)
Priority: P2 2026-11-10 — a feature the open milestone was opened for, ruled the same evening

## Goal

The graph pane's chrome looks and behaves as the prototype draws it. The curves are switched
from a legend beside the plot, not from a row of buttons. The view's controls sit on the graph's
title line, and the rarer ones (the residual, the exports, data only) are one menu away. The
fitted range and the excluded regions are objects on the plot: a click selects one and a small
bar edits it. Every function the pane has today stays reachable, and no click moves the layout.

## Context

### Why it exists

On 2026-11-10 the maintainer looked at the palette PR's buttons (#1517, WP-2200) and said:
"a large part of the redesign is concealing a lot of these cluttered buttons. when are you
going to make the graph window more like the prototype? e.g. the toggle curve elements are not
buttons like this, and the range/exclude dialogs should be redesigned to fit the aesthetic of
the prototype". No piece of the milestone covered the graph window. The maintainer ruled the
same evening to file it and build it.

### What the pane has today

Under the Pattern tab, `gui/src/panels/Plot.svelte` draws, below the plot, the hover readout
strip and then two rows. The first row holds three segmented controls (the residual Δ/σ, Δ or
Σχ²; the scale lin, √ or log; one button per curve), a `data only` button, four export buttons
(PNG, SVG, copy image, copy data) and a line counting the channels drawn. The second row is the
protocol strip (WP-1033): two typed 2θ boxes with Set and All, a segmented control arming a
drag (`⇥ range`, `✂ exclude`), one pill and × per excluded region, the count of fitted
channels, the stale warning and the last refusal. The Background tab (`panels/Background.svelte`)
puts its hold boxes and its band multiplier in a row below its plot. The Single peaks tab
(`panels/PeakWindows.svelte`) has no row of controls.

### The design, and the rulings it rests on

The prototypes are not published, so the design is restated here.

- **Curves are switched from a legend in a right-hand gutter.** "Every curve and the data can
  be hidden and shown" (fourth review, 2026-11-07). The prototype puts each label in a gutter
  to the right of the plot, beside the pane its curve is drawn in, and the label is the switch.
  A hidden curve's label is struck through and faint, and its swatch fades (`gui/STYLE.md`
  § Plots). A legend puts its symbols in one column on the left, with the labels aligned after
  them (2026-11-08). The prototype's labels are words: Observed, Last fit, Preview, Background,
  Difference, and each phase's name beside its tick row.
- **The title line carries the view's controls.** One row: what the graph shows on the left,
  the view's own controls on the right, and the title gives way first with an ellipsis (fourth
  review and the bar merge, 2026-11-07; B1, 2026-11-09). The prototype's Pattern controls are
  "Intensity" with a segmented Linear / Square root, and Show all. Its Background controls are
  "Band drawn" with ×1 ×5 ×20.
- **Less on screen.** The maintainer disliked the first GUI's information overload and its
  controls of unclear purpose (2026-11-06). No permanent explanatory text (2026-11-07). No
  caption restates what the plot shows (2026-11-07).
- **Objects on a plot share one grammar** (interaction rules, adopted 2026-11-08): click to
  select, a bar of actions on the selection, closed by ×, Esc or a click elsewhere; Delete
  removes the selection; right-click opens a context menu with the bar's actions. A left-out
  region stays on the plot as shading, because its position is the information (rule 4).
- **No click moves the layout unless it asks to** (2026-11-07, milestone row 1). A menu opens
  over the page; arming a drag says so over the plot, never on a new line.

The prototype draws no residual choice, no export and no protocol control on the graph: its
exports are in the File menu, and it has no fitted range or excluded region at all. Those are
completed here by the guide's rules for their kind, and each departure is a question for the
maintainer (§ Questions).

### Seams

- The title line is `App.svelte`'s `.gtitle`. Each graph panel places its controls there
  through a small portal action (`gui/src/lib/portal.ts`), so the panel keeps its own state and
  the shell gains one empty slot.
- The legend's positions come from the chart's own panes (`PatternChart.geometry`), so a
  resize or a scale switch moves the labels with the panes.
- The menu is one component (`panels/Menu.svelte`) drawn as the File menu is.
- The overlaps with open pull requests: #1526 (WP-2202) rewrites the Peaks tab and edits
  `lib/pattern.ts` and `lib/plot.ts`; #1518 (WP-2210) moves the fit statistics out of
  `.gtitle`. This WP leaves the peak layer and the statistics alone.

## Non-goals

- The Peaks tab's own plot marks and gestures (#1526, WP-2202) and heading words (#1522,
  WP-2201).
- The Background tab's type choice and terms slider, which the prototype draws and rietx's
  background routes do not serve.
- A "peak shape alone" view on the Single peaks tab, which the prototype draws and no route
  serves.

## Tasks

- [ ] The portal and the title line's slot; the Pattern tab's Intensity scale, Show all and
      the view menu on it. Vitest.
- [ ] The legend gutter: one label per curve beside its pane, each a switch. Vitest; a browser
      check that a label click hides its curve and moves nothing.
- [ ] The fitted range and excluded regions as plot objects: click a band to select it, a bar
      with typed bounds, the channel count and Delete; the menu's and the context menu's
      routes to add one. Vitest; a browser check.
- [ ] The Background tab: the band multiplier on the title line, "Hold at last fit" below.
- [ ] `gui/CLAUDE.md` and the manual's GUI chapters follow; screenshots retaken; the built pane
      beside the prototype at 1440 × 900, light and dark, under `docs/wp/2213-screenshots/`.
- [ ] Skill: none. The GUI is a human surface, and an agent drives the python API.

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_browser.py tests/test_gui_peaks_browser.py tests/test_gui_manual.py tests/test_gui_style_guide.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The browser files skip in CI (no playwright there), so the PR quotes their local counts.

## Questions

Filled in by the session that builds the piece, one line of context each.

## References

- The maintainer's words of 2026-11-10, quoted above, and the rulings of 2026-11-06,
  2026-11-07 (fourth review, the bar merge), 2026-11-08 (interaction rules) and 2026-11-09
  (port acceptance, B1), restated above.
- WP-1032 (curve toggles), WP-1033 (the protocol strip), WP-1210 (absent layers), WP-1461
  (exports), WP-2123 (the title line), WP-2129 (the Background tab).

## Handover log

- **2026-11-10** — filed by a ghostshift runner on the maintainer's ruling of the same evening,
  branched from WP-2200's branch (#1517), since this piece redraws the plot chrome the palette
  recoloured. No open WP owns the graph pane's chrome: the milestone's tables have no row for
  it, and #1526 and #1518 leave it alone. Next: build it.
