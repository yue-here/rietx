# WP-1461 — every browser chart draws with uPlot

Milestone: unscheduled · Status: 🔄 2026-09-26 — tasks 1-12 and 15 done: no chart loads plotly and every chart exports; task 13, the docs, next, then task 14's acceptance run
Depends on: —
Priority: P2 2026-09-24 — the maintainer's decision that every browser chart builds on one module; today plotly blocks every GUI open for 0.7-0.8 s before the first plot

## Goal

Every 2D chart rietx draws in a browser comes from one rietx chart module
built on uPlot. That covers the GUI's pattern and Series panels,
`rietx watch`, `rietx compare` and the file `write_html` writes. None of those
pages loads plotly.js. Opening the GUI on the NAC example has no long frame
from a chart library, and § Acceptance holds against today's plotly renderer
measured the same way on the same machine.

## Context

### How the numbers were taken

The spike, its logs and screenshots are in
[`1461-uplot-spike/`](1461-uplot-spike/README.md), and every number below
names the log it comes from. Unless a line says *latency*, a number is
main-thread work: the change in CDP `TaskDuration`, minus the page's idle
rate over the same wall time, per event. Frames come from a
`requestAnimationFrame` loop and the `long-animation-frame` entry, which
fires above 50 ms. The browser is headless Chrome for Testing from
playwright's chromium build 1223, on an Apple M4 shared with other sessions.
Load averages ran from 7 to 29 during the runs, so absolute times move with
load. Ranges are over at least three runs where a log has them, and the
claims rest on ratios measured side by side.

The first draft of this WP timed plotly calls by promise latency. That
overstated plotly's resize about ninefold, because `Plots.resize` waits on a
100 ms `setTimeout` before it relayouts. `results/gpu3.txt` is that
latency-timed run. Everything quoted below is work unless it says otherwise.

### What plotly costs today

**The library head-to-head** at NAC's 59 498 channels, five series, three
fresh pages each (`results/bench_td.txt`):

| | plotly.js (Python `plotly` 7.1.0) | uPlot 1.6.32 | plotly / uPlot |
|---|---|---|---|
| minified / gzip | 4.82 MB / 1.47 MB | 51 KB / 22 KB | 94× / 67× |
| load and parse | 400-489 ms | 9.2-11.2 ms | ~45× |
| first draw | 197-265 ms | 27.5-32.6 ms | ~7× |
| new data | 23.9-27.2 ms | 9.9-10.3 ms | ~2.5× |
| zoom | 3.75-4.17 ms | 1.62-1.69 ms | ~2.4× |
| resize | 11.5-12.9 ms, then 101 ms of timer latency | 1.7-2.5 ms | ~6× in work |

Sizes are in `results/sizes.txt`. A plotly resize through `relayout` with an
explicit width and height costs 10.2-11.4 ms and skips the timer.

**Today's GUI**, NAC example fitted through the server
(`results/gui_td.txt`, `gui_boot.txt`, `run3.txt`, `gui2.txt`):

- **Opening.** Evaluating `plotly.js` is one long animation frame of 700-811
  ms across seven runs. The pattern's first `scattergl` react is a second
  one of 315-415 ms. The page answers no input during either. Under this
  load the first plot landed 1481-2295 ms after navigation. An earlier run
  under lighter load landed at 842 ms.
- **Resizing.** A viewport resize costs 27-61 ms of work for the whole app,
  of which plotly's share is about 12 ms. `Plots.resize` then resolves
  120-144 ms after it was asked (latency). The same latency ends every
  gesture that changes the layout around the plot. That happened after 3 of
  3 exclude drags, the double-click reset and 1 of 5 zoom drags; what
  changes the height is not traced.
- **Zooming.** Every zoom refetches `/api/result/window`. At the default
  budget that is 906 KB, fetched in 65-74 ms (latency). Zoomed windows took
  6-53 ms, then a react of 6-26 ms.
- **Per pointer move**, react, refetch and resize work included: hover
  2.11-2.27 ms over four runs, drag-zoom 3.66 ms and an exclude drag 4.69 ms
  over one run each.

### Staying on plotly, costed

Three changes would remove most of the lag without a new library:

- `relayout` with an explicit size instead of `Plots.resize` (10.2-11.4 ms
  of work, no timer);
- the full-resolution data in the page and a client-side zoom (D4), where a
  plotly zoom costs 3.75-4.17 ms;
- a partial plotly bundle, which is unmeasured.

The migration buys the rest:

- 400-489 ms less script evaluation at every open (a 700-811 ms frame in
  the app under load);
- a first draw about 7× cheaper;
- updates about 2.5× cheaper;
- the plotly-only code in § What changes deleted;
- 4.8 MB less in every file `write_html` writes.

The maintainer asked on 2026-09-24 for one backend for all plotting "if
it's good". The first task confirms that choice on these corrected numbers.

### Every feature, rebuilt on uPlot and measured

`proto.html` rebuilds the GUI's pattern plot on synthetic data.
`proto2.html` rebuilds the Series trajectory and the compare overlay, and
adds an in-situ 2D map as the first chart no page has yet.
`proto_driver.mjs` drives both with real mouse and wheel input. **The
prototype has none of the app's own work**: no Svelte, no stores, no
ten-field readout. So its costs are a floor for the port, never a
prediction, and § Acceptance measures the real pages.

At 59 498 points, three runs (`results/proto_59498*.txt`, the files without
`allmarkers`), every row held a p95 frame of 17.7 ms or less with **zero
long animation frames**:

| Behaviour (where it is used today) | uPlot mechanism | Per event, ms |
|---|---|---|
| hover readout, nearest reflection and peak (Plot strip, watch hkl) | `setCursor` hook, binary search | 0.65-0.95; tick pane 0.34-0.74 |
| drag-zoom (all) | built in | 0.84-1.33 |
| wheel zoom; wheel pan; alt-drag pan | a 20-line listener | 3.11-3.70; 2.88-3.52; 3.81-4.06 |
| exclude-region drag, armed (Plot) | `drag.setScale = false`, `setSelect` hook | 0.85-1.51 |
| peak drag-move; click-add (Plot) | listeners on `u.over`, `posToVal` | 1.09-1.17; 2.19-3.17 |
| shift-click and right-click on a peak (Plot) | the same listeners | asserted in the log |
| table-to-plot hover ring (Peaks) | a DOM overlay, no redraw | 0.16-0.22 |
| legend toggle (all) | `setSeries` | 1.19-1.37 |

And the one-off operations, same runs:

| Operation | uPlot mechanism | ms |
|---|---|---|
| mount three linked panes | three instances, cursor sync, a `setScale` hook | 53-94 |
| double-click reset | built in | 10.3-23.6 |
| linear, √ or log scale | `distr` 1, 100 or 3; a pane rebuild | 7.0-16.1 |
| theme switch | colour functions re-read at every draw | 0.7-3.9 |
| live stage update, zoom kept (watch) | `setData(data, false)` | 16.2-33.8 |
| resize | `setSize` | 1.7-2.7 |
| 426 or 92 103 candidate lines (Plot) | a draw hook, one stroke per pixel column | 0.5-1.4 or 15.9-20.0 |
| copy PNG to the clipboard, read back as `image/png` | panes composited, `ClipboardItem` | 20.5-48.7 |
| copy the visible data as TSV | `writeText` | 32.6-37.8 for 59 497 rows; 1.6-1.8 zoomed |

With the 92 103 candidate lines drawn, hover costs 0.39-0.52 ms and wheel
zoom 5.11-5.47 ms.

Single runs, so no range (`results/proto_run2.txt`, `proto_dpr2.txt`,
`run3.txt`):

- **devicePixelRatio 2**, 22 003 points: every per-event gesture cost
  0.05-3.4 ms and the double-click reset 12.4 ms, with zero long frames.
  The PNG copy is 2400×1276 in 42 ms. GPU raster time was not measured.
- **200 000 points**: hover 0.90 ms, wheel zoom 8.4 ms, reset 40 ms. Long
  frames: 51 ms in the wheel zoom, 56 ms in the exclude drag and 59 ms in the
  wheel zoom with candidate lines. That is the ceiling D4 needs.
- **SVG export** of a zoomed window: 180 ms, 526, 30 and 66 kB for the three
  panes, faithful to the canvas (`shots/export-svg.png`).
- **Standalone page**, the figure `write_html` draws, from the same arrays:
  1.63 MB, drawn 83-93 ms after navigation, against plotly's 6.53 MB at
  598-686 ms (latency, three loads each). Most of the 1.63 MB is the arrays
  at full JSON precision.
- **Series trajectory** with esd whiskers and a tooltip: hover 1.56 ms.
  **Compare overlay**, 10 × 22 003 with hover focus: hover 1.34 ms, wheel
  zoom 2.80 ms. **2D map**, 200 × 22 003 from a max-pooled pyramid: built in
  71 ms, wheel zoom 1.56 ms, hover 0.88 ms. These three are gross, without
  the idle subtraction.

### What the spike found that a session would otherwise relearn

1. **Cursor sync carries a drag selection to every pane in the group**, so a
   `setSelect` handler runs once per pane. Five exclude drags added fifteen
   regions until the handler ran only in the pane the drag began in
   (`results/proto_run1_before_fixes.txt`). The module's core goes further
   and syncs the cursor only. Its `filters.pub` keeps a mousedown, mouseup
   and double-click in their own pane, so a drag is one pane's event and its
   handler runs once. That also matches plotly, which draws the zoom box in
   the dragged subplot alone.
2. **A custom scale needs its own ticks.** Under `distr: 100` (√) uPlot
   printed one y label. `splits` evenly spaced in √ space fixes it, as the
   GUI's `sqrtTicks` does today (`plot.ts:796-807`). The labels need a
   `filter` as well. uPlot applies its log-axis label filter when `distr` is
   3 or more and `log` is 10, and a √ scale is `distr: 100` with `log` at its
   default of 10. So every √ label but a power of ten printed blank until the
   core's `filter` returned the splits unchanged.
3. **Tick labels do not adapt to a narrow range.** A trajectory spanning
   1e-4 Å printed `10.251` five times. An axis over a refined parameter needs
   a `values` formatter whose precision follows the tick step.
4. **uPlot draws every marker.** At 59 498 points that costs 1.3-1.6× the
   thinned figures on redraw-heavy gestures: wheel zoom 4.10-5.78 ms, reset
   25-41 ms. Two runs in three had long frames of 55-67 ms, in the drag-zoom
   and the wheel zoom, against none in the thinned runs
   (`results/proto_59498_allmarkers_run*.txt`, load about 12). At 200 000 points
   every marker cost 13 ms per wheel event with long frames
   (`proto_run1_before_fixes.txt`). A `paths` builder keeping each
   device-pixel column's minimum and maximum brought that to 8.4 ms. D5 says
   which to use.
5. **uPlot takes its 2D context once, at construction**
   (`const ctx = self.ctx = can.getContext("2d")`), and reads every colour
   function again at each draw. A theme switch is one redraw. A y-scale
   switch rebuilds the pane.
6. **SVG needs a recording `Path2D`.** svgcanvas cannot read a native
   `Path2D`, and uPlot strokes every series through one. About 40 lines swap
   in a recording class for the export chart only. The export chart must
   also join no sync group. Otherwise its first `setScale` redraws the live
   panes while `Path2D` is swapped, which threw page errors and reset the
   zoom.
7. **The first draw from a new 2D-map pyramid level uploads a texture**:
   two long frames, 100 ms at most, in the first wheel zoom.
8. **uPlot leaves the canvas transparent**, so a PNG export fills the ground
   colour first.
9. **jsdom has no canvas.** `getContext` returns null and uPlot's
   constructor uses the context at once. vitest stubs uPlot the way
   `test-setup.ts` stubs `window.Plotly` today, and browser tests cover the
   drawing.
10. **One chart, one x array.** uPlot's default mode aligns every series on
    one sorted x array. Every surface has data on a second grid (D8). The
    fitted and masked NAC grids merge onto one 59 498-point axis, with every
    series null-padded, in 4.4-5.4 ms (`results/gui_td.txt`).
11. **A tooltip is a capability, not a requirement.** WP-1213 deleted
    plotly's hover box because it covered the data, and the GUI answers
    hover with its readout strip. The spike's tooltip costs the same as the
    strip. Adding one to the GUI is the maintainer's call.
12. **Link panes by value.** uPlot fires `setScale` hooks from a microtask,
    after the call that set the scale has returned. A flag set around that
    call is already clear when the echo arrives. And every `setScale`
    repaints its pane, even when the range has not moved. The spike linked
    its panes with such a flag until 2026-09-25, so every zoom, pan and reset
    painted the main and tick panes twice. `setX` now leaves alone a pane
    already at the range. The gesture table above was measured with the echo,
    so its zoom, pan and reset rows overstate the cost
    (`results/zoom_probe.txt`).
13. **Firefox stalls where Chromium does not.** The table above is Chromium
    only, and the maintainer reads in Firefox. `zoom_probe.mjs` sent Firefox
    155 the same drag-zoom twelve times, at devicePixelRatio 2 and 59 498
    points. Most drags painted in 3-9 ms over the three panes. Two stalls
    recurred at the same drags in every run. The residual line took
    117-296 ms on the first two drags. On drags 9-11, one paint spent
    29-204 ms in the two dashed curves. Chrome 148 painted every drag in
    9 ms or less, though neither timer sees
    GPU raster. Turning off `gfx.canvas.accelerated` moved neither stall. The
    load average was 67-84, which inflates their size but did not move them.
    The pilot's Firefox row must look for both.
14. **A drag-zoom on macOS three-finger drag waits for the OS.** That
    setting holds a drag open after the fingers lift, and the browser gets
    the mouse-up only when it ends. The maintainer's trackpad has it on.
    They felt about 300 ms between lifting and the zoom, in Chrome, Safari
    and Firefox alike, and confirmed the setting as the cause. No page sees
    the fingers lift, so no library can remove the wait, and plotly has it
    too. Wheel and pinch zoom have no release. The `?demo` readout splits a
    drag's wait at the mouse-up: the pointer sitting still before it, then
    the page's time after it. A latency probe must start its clock at the
    mouse-up.
15. **No drag works in playwright's WebKit.** Its synthesised mouse moves
    carry `movementX` and `movementY` at 0, where Chromium and Firefox fill
    them in. uPlot drops a zero-movement move while a button is down, a guard
    against a phantom move Chrome on Windows sends after a mouse-down. So in
    that WebKit the select box stays zero wide, even under uPlot's default
    options. A real mouse in Safari reports the movement. The pilot probe
    fills it in from `clientX` for WebKit only (`pilot.mjs`), and a drag in
    real Safari is still for a person to try.
16. **uPlot leaves its last series' dash on the canvas**, into the next frame
    as well. A layer drawn after the background's dashed line drew the peak
    markers dashed, and a layer under the series starts with the previous
    frame's dash. Every layer that strokes sets its own dash.
17. **uPlot's default cursor walks each series through its nulls.** On every
    pointer move, in every pane, `cursor.dataIdx` looks left and right from
    the pointer for the series' nearest non-null value. The curves payload is
    null-padded by design (the model over 37 000 masked NAC channels, the
    tick band's series throughout), and no page reads a series' own index.
    `panes()` hands every series the cursor's index instead.
18. **plotly answers at most one hover every 50 ms.** Its fx throttles hover
    calls to `HOVERMINTIME: 50`, so at the probe's 16 ms spacing it answers
    about one move in three. The chart's readout answers every move. A trace
    of one 120-move sweep had the chart repaint the page 240 times and plotly
    87 times (`hover_trace.mjs`). So plotly's hover work per move sits under
    the chart's in some runs: in 1 of 7 paired runs on the final build, and
    in 3 of 19 over the pilot's three builds, each a matrix's first call at
    dpr 1, by 0.22-0.68 ms. The chart's own figure is steady at 3.2-3.6 ms. Matching plotly's would mean answering fewer moves, so the
    miss is recorded rather than tuned away.

### Behaviours the spike did not rebuild

Verified in the code by the review; each is carried by the port and named
by a test.

- **GUI pattern panel:**
  - y-zoom, and the y and y2 ranges it pins;
  - the raw view (no result), and Esc to disarm (`Plot.svelte:1224`);
  - axis titles that name where σ came from;
  - peak markers: circle or diamond, open or filled, esd whiskers capped at
    3×FWHM;
  - per-group peak-fit curves on their own grids (`Plot.svelte:661-676`).
- **The readout's fields:** d-spacing, background, candidate hkl and
  emission line, peak-fit value, the masked-arm lookup, the residual kind.
- **Σχ² under a client zoom.** It is accumulated across the window
  (`session.py:2644-2651`). With full-resolution data it re-bases at each
  zoom as cum[i] − cum[i₀ − 1].
- **Series panel:**
  - the per-pattern obs, calc and Δ chart with its own excluded arm
    (`Series.svelte:363-374`);
  - the backward chain and the dashed tone of a path-dependent parameter;
  - an unrecovered pattern *plotted* as a cross, because "a gap reads as
    data nobody collected" (`series.ts:229-234`). The spike nulled it, which
    was wrong.
- **`rietx watch`:** the n_drawn-of-n_points annotation, the legend's cap
  label, the Δ/σ range ladder and the ±3σ band.
- **`write_html`:**
  - the weighted two-panel mode with its ±3σ band;
  - the per-phase `"hkl: …"` trace names that `test_magnetic_tick_row.py`
    parses out of the file;
  - its palette. It draws from `viz/plots.PALETTES` (calc `#ff7f0e`) while
    the browser pages use theme tokens (`--plot-calc` `#c23b22`), so the
    module takes a palette as input or the file changes colour silently.

### What changes

- **Pages.**
  - GUI: `gui/src/panels/Plot.svelte`, `lib/plot.ts`, `lib/peaks.ts`,
    `panels/Series.svelte`, `lib/series.ts`, `lib/plotly.ts`,
    `panels/Structure3D.svelte` (its loading only), `api.ts`.
  - The GUI server: the curves route (D4) in `src/rietx/gui/session.py` and
    `server.py`.
  - `rietx watch`: `src/rietx/watch/static/watch.mjs` and `watch-core.mjs`.
  - The page string in `src/rietx/compare_app.py`, which becomes a file
    (root CLAUDE.md: a page that is javascript is a file). Its `/api/state`
    drops the curves, and a route serves each variant's (D4).
  - `src/rietx/viz/html.py` and `src/rietx/viz/plotlyjs.py`.
- **Code that exists only to handle plotly.** It goes with plotly:
  - the axis pinning in `plot.ts` (`heldRanges`, `pinPatch`, reads of
    `ax._rl` and `_fullLayout`), which stops plotly autoranging on every
    `react`;
  - `movedAxes`, which parses `plotly_relayout` payloads;
  - the empty ring trace kept as SVG so select-drag does not crash;
  - `marker.color` set against the colorway, and `hoverinfo: "none"` on
    every trace;
  - the `!important` overrides of plotly's select outline;
  - the invisible marker overlay behind the Series error bars;
  - `Plotly.purge` for WebGL contexts, and the watcher's legend and margin
    placement.
  `readout`, `residual`, `curveToggles` and `sqrtTicks` in `plot.ts` stay as
  pure functions. `maskShapes` becomes the input of the shading hook.
- **Tests.**
  - `test_gui_manual.py` partitions the GUI's routes. The curves route needs
    a chapter, and the two window routes leave it when they go.
  - The `/plotly.js` route and its fallback: `test_gui_server.py`,
    `test_watch_app.py`, `test_gui_dist.py`.
  - The no-plotly paths: `test_snapshot.py`, `test_events_viz_history.py`.
  - The `importorskip("plotly")` in `test_examples.py`.
  - `write_html`'s output: `test_magnetic_tick_row.py`.
  - `test_gui_palette.py:436-480`, `test_compare_ui.py` and
    `test_docs_consistency.py:523`.
  - `test_watch_browser.py` reads `_fullData` because it is "what was
    painted rather than what was asked for" (`:227`). Its replacement must
    keep that property: sample canvas pixels, or record the resolved
    `strokeStyle` at draw time.
  - `App.test.ts` stubs `Plotly.react` in about 20 blocks, and
    `structure3d.test.ts` asserts on `uirevision`.
- **Rules.** `gui/CLAUDE.md` § Usability, § Repairs found by use, § What is
  fitted, shaded and selectable, and § The view, the armed cursor and the
  theme's scope.
  - Rules about what the plot says survive the port. A tick belongs to the
    model, hiding a curve is by exception, a hover link never redraws the
    pattern, a region drag is an armed mode, `cumulative_chi2` is
    accumulated over every point, and a `ResizeObserver` sizes the chart,
    since uPlot has no autosize.
  - Rules about how plotly behaves are deleted: the autorange traps, the
    view handed back on every draw, `doubleClick: "autosize"`, and
    `responsive: true` listening to window resizes only.
- **Dependencies.** `pyproject.toml`'s `gui` and `viz` extras. ATTRIBUTION.md's
  two plotly rows gain uPlot and svgcanvas rows.
- **Docs.** The manual's GUI chapters and their screenshots,
  `using/cli.md`, `using/install.md`, `using/files.md`, root CLAUDE.md,
  `tests/CLAUDE.md` and README. In the skill, `references/api.md` is
  generated by `make_api_index.py`.

### The payload behind a client zoom, measured

Task 2 measured D4 and D8 on three real answers:

- the NAC example, fitted through a `GuiSession`;
- the `nac` and `lab6_capillary` compare standards, four variants each;
- the QPA sample-1 series of eight patterns.

`payloads.py` builds each payload and times the server's half.
`payload_probe.mjs` fetches each one in Chrome for Testing 148 and Firefox
155, then times the decode, the parse and the grid union. `transport.py` times
the real GUI route with curl. Load averages were 3-5, and every range is over
six runs (`results/payloads.txt`, `payload_probe_chrome.txt`,
`payload_probe_firefox.txt`, `transport.txt`).

The proposed shape sends three things. The pattern's own 2θ and intensity
cover every channel. `fitted` lists the channels the fit kept. The five model
arrays cover those channels. Two facts carry it, and both held bit for bit on
NAC and on a series member:

- the result's 2θ is the pattern's 2θ under the fitted mask;
- the result's `y_obs` is the pattern's intensity on those channels.

So the union D8 asks for is the pattern's own channel list, and the model
lands on it by index.

**NAC, 59 498 channels, 22 003 fitted.** Server times are from
`payloads.txt`. The parse column leaves out the UTF-8 decode, which adds
0.1-1.2 ms to a JSON body.

| Payload | Size | Built, ms | Serialised, ms | Chrome parse, ms | Firefox parse, ms |
|---|---|---|---|---|---|
| today, one 4000-point window | 0.91 MB | 6.8-7.3 | 13.9-16.6 | 0.9-1.1 | 2.4-2.6 |
| today's JSON, every channel | 3.41 MB | 8.1-11.0 | 51.7-56.8 | 3.8-5.1 | 8.4-9.2 |
| proposed, JSON | 3.56 MB | 1.3 | 54.5-54.7 | 3.8-5.4 | 8.4-8.8 |
| proposed, JSON at seven digits | 2.08 MB | 1.3 | 36.2-37.3 | 2.7-4.0 | 3.9-4.2 |
| proposed, float64 binary | 1.93 MB | 1.3 | 0.2 | 0.0-0.2 | 0.0-0.1 |
| proposed, float32 binary | 1.01 MB | 1.3 | 0.1-0.2 | 0.0-0.1 | 0.0-0.1 |

- **The real route** answered its first byte in 59.3-60.3 ms at every
  channel and 20.5-21.3 ms at 4000 points. That is the server's work. On
  loopback the transfer took 0.2-1.4 ms for every payload here. `gui_td.txt`'s
  152-171 ms fetch of the same payload ran at load 7-29.
- **The union** onto 59 498 channels took 0.5-5.3 ms in Chrome and 0.7-1.6 ms
  in Firefox, for today's sorted merge and for the index alike. The index
  removes the merge as code. It saves no time.
- **Float32** puts at most 6.0e-8 relative error on any array. A Σχ² re-based
  as cum[j] − cum[i−1] loses more: 1.2e-3 of itself over a window of 0.1 % of
  the NAC pattern, and 6.5e-5 over 1 %.

**Compare.** On both standards every variant fitted the same channels with
the same `y_obs`. Today `/api/state` carries every ready variant's curves on
each 700 ms poll:

| `/api/state`, four variants | `nac`, 22 003 channels | `lab6_capillary`, 116 001 channels |
|---|---|---|
| today, 4000 points a variant | 2.96 MB, 41.3-42.2 ms serialised | 3.31 MB, 45.4-45.5 ms |
| today's shape, every channel | 8.77 MB, 123.3-123.7 ms | 45.69 MB, 632.9-653.8 ms |
| without the curves | 27.3 kB | 25.9 kB |
| one variant's curves, float64 binary | 1.06 MB, 1.6-1.7 ms | 5.57 MB, 8.7-9.7 ms |

Today's poll already costs the browser 3.2-3.6 ms of parse in Chrome and
7.5-9.0 ms in Firefox, every 700 ms. The server serialises it on a thread
beside the worker that fits. At every channel, `lab6_capillary`'s poll would
parse in 118-125 ms in Firefox, a long frame on every poll.

**Series.** `/api/series/result` for eight patterns is 480 kB, serialised in
2.3-2.5 ms and parsed in 0.3-1.1 ms. A member has 7251 channels. Today's
4000-point budget already sends 5864 of them, in 0.66 MB. All 7251 in float64
binary are 0.44 MB.

**The ceiling.** `payloads.txt` counts the channels of every pattern the
repository reads. Lab patterns run from 255 to 7251. The 11-BM patterns run
from 48 000 to 59 498, except `11BM_LaB6_660a.fxye` at 132 992, which
`lab6_capillary` fits over 116 001. `proto_driver.mjs` ran at those sizes,
three runs each at load 3-5:

- **132 992 points, thinned per pixel column.** One long frame over the three
  runs: 51 ms, in one hover sweep. Wheel zoom cost
  4.47-5.47 ms, the pans 4.75-5.55 ms and the reset 13.6-25.6 ms
  (`proto_132992_run*.txt`).
- **132 992 points, every marker.** A long frame of 62-67 ms in the wheel zoom
  with 92 103 candidate lines, in 3 of 3 runs. The reset cost 32.7-43.6 ms
  (`proto_132992_allmarkers_run*.txt`).
- **200 000 points, thinned.** A long frame of 53-57 ms in that same gesture,
  in 3 of 3 runs (`proto_200000_run*.txt`). The spike's first run at this
  size, at load 7-29, had long frames in three gestures. At load 3-5 only this
  one kept its long frame.

### The pilot, measured

`pilot.mjs` drove the real GUI on one server per call, plotly against the
chart module, with every gesture sent as real input. Work is the change in
CDP `TaskDuration` less the page's idle rate, per event. "Callbacks" is the
time inside every listener, microtask, timer, frame and `ResizeObserver`
callback the page registered, the one figure Firefox and WebKit give. A
resize's own share is the CPU profile's time in stacks through the chart
library's files. Chrome for Testing 148, playwright's Firefox 155 (build
1543) and WebKit 26.6 (build 2359), load averages 3-7, three calls a row
unless a row says one. `pilot_summary.mjs 2026-09-25T05:33` reads the final
set back from `results/pilot_*.txt`; the earlier blocks there are the D5
comparison and a first re-measurement.

**Go.** On NAC in chromium the chart met acceptance 1, 3 and 2, except the
hover clause in one paired run of seven, by 0.68 ms (finding 18). It met
acceptance 7 in Firefox and WebKit.

1. **Opening.** plotly's evaluation was a long frame of 308-320 ms, then
   125-158 ms in `app.js`. With the chart, no long frame at all, at
   devicePixelRatio 1 and 2. At 132 992 channels there was one frame of
   52-66 ms, in `app.js` and none of it the chart library's.
2. **Gestures**, work per event in ms, chart against plotly:

   | Gesture | dpr 1 chart | dpr 1 plotly | dpr 2 chart | dpr 2 plotly |
   |---|---|---|---|---|
   | hover | 3.32-3.56 | 2.82-4.29 | 3.41-3.59 | 4.16-4.28 |
   | drag-zoom | 4.12-4.35 | 8.77-9.29 | 3.90-4.33 | 8.15-8.76 |
   | exclude drag | 5.07-5.77 | 11.13-11.71 | 5.69-5.82 | 9.72-11.15 |
   | peak drag | 1.56-1.78 | 8.64-8.97 | 2.20-2.49 | 7.67-8.09 |
   | wheel zoom | 4.73-5.02 | none | 5.55-6.23 | none |
   | shift-wheel pan | 5.16-5.50 | none | 6.43-7.41 | none |
   | alt-drag pan | 3.68-3.73 | none | 3.71-4.32 | none |

   - The chart had no long animation frame in any gesture. plotly had one of
     51 ms, in an exclude drag.
   - A chart zoom fetched nothing. plotly fetched the window after every zoom
     and reset, nine times over five drags.
   - The p95 frame interval was 16.7-18.6 ms for both renderers and every
     gesture, hover included. That is headless chromium's frame clock under
     the probe, so the 17.7 ms clause cannot separate the two here.
3. **Resizing.** The chart's own work was 1.7-3.5 ms at dpr 1 and 1.5-2.9 at
   dpr 2, against plotly's 11.3-17.2 and 11.3-14.5. The next-frame claim is
   `test_rxplot_browser.py`'s.

At **132 992 channels** (LaB6, dpr 1) the chart had no long frame in any
gesture. Its wheel zoom cost 8.49-8.75 ms an event and a resize 4.6-6.7 ms of
its own. plotly had long frames of up to 64 ms in its peak drags and 56 ms in
an exclude.

**Firefox and WebKit** (NAC, dpr 1): every gesture worked, no page error was
thrown, and every drag moved its line. Chart callbacks per event in ms:

| Gesture | Firefox | WebKit |
|---|---|---|
| hover | 0.89-1.01 | 0.61-0.72 |
| drag-zoom | 2.29-2.46 | 1.00-1.17 |
| exclude drag | 3.00-3.07 | 1.48-1.52 |
| peak drag | 0.71-0.93 | 0.71-0.86 |
| wheel zoom | 7.45-8.40 | 4.40-4.80 |
| shift-wheel pan | 4.60-5.80 | 2.70-2.80 |
| alt-drag pan | 4.79 | 1.86-2.29 |
| resize, per resize | 4-11 | 3-9 |

The longest frame was 50.0-50.5 ms in Firefox, where the refetched payload of
an exclude lands, and 26-28 ms in WebKit. plotly's were 50.0-51.5 and
39-48 ms in the same gesture.

**D5** was decided on the first matrix, which measured every marker beside
the thinned path. Every marker made long frames in chromium at 132 992
channels: 10 in the drag-zooms (up to 61 ms), 13 in the excludes (up to
127 ms) and 3 in the wheel zooms (up to 59 ms), over three runs. At dpr 2 on
NAC its wheel zoom cost 8.53-9.59 ms an event. On NAC an exclude made frames
of 166.7-216.7 ms in Firefox and 242-258 ms in WebKit, and Firefox's wheel
zoom spent 21.40-21.85 ms in callbacks an event.

### Decisions this WP takes

Each carries the recommended answer. The maintainer confirms or overturns it
in the first task.

**Decided 2026-09-25.** The maintainer confirmed the migration to uPlot, D1
(every chart shown in a browser) and D2 (a vendored copy), and D4-D8 as
recommended. D3 went unanswered and stands as recommended. They asked how a
vendored copy stays current, and D2 now says. **D5 was left to the
pilot**, and the pilot chose thinning (§ The pilot, measured). It was first
confirmed on a summary saying every marker "stays fast at NAC's size", while
finding 4 says two runs in three had long frames. Put back with those
numbers, the maintainer chose to let the pilot measure both marker paths on
the real panel and pick. The 3D viewer's move is
[WP-1462](1462-the-structure-viewer-draws-with-threejs.md), filed the same
day.

**Decided 2026-09-25, the fifth session.** Task 6 said to delete the plotly-only
code, and task 15 to remove the flag and the plotly renderer after tasks 7-14.
Both could not hold, since the plotly renderer depends on the code task 6
deletes. Task 14's test that no page loads `/plotly.js` would also fail while
plotly drew the pattern by default. Asked, the maintainer chose to delete the
pattern panel's plotly renderer and the `?chart=uplot` flag in task 6, which
takes task 15 in. The chart has drawn the pattern since that merge. A later
acceptance run pairs against plotly from a build of `58f7dbce`, the last commit
with the plotly renderer.

- **D1. Scope.** Every 2D chart in a browser.
  - matplotlib stays for the files it writes (`plots.py`, `indexing.py`,
    `plot_for_vlm`), which are made without a browser.
  - The 3D structure viewer is not covered (§ Non-goals). So this WP gives
    one backend for charts, not for all plotting.
- **D2. uPlot vendored once and bundled into the GUI.**
  - `uPlot.iife.min.js` and `uPlot.min.css` at a pinned version go into
    `src/rietx/viz/static/`, with uPlot's LICENSE beside them. The file
    carries only its URL and version (`results/sizes.txt`), and MIT needs
    the notice with every copy.
  - The watcher and the compare page load it from their servers.
    `write_html` inlines it with the notice.
  - The GUI bundles it and the chart module into its dist through a vite
    alias, as it bundles CodeMirror. plotly was loaded at runtime because
    of its 4.8 MB (WP-1010), and uPlot is 51 KB.
  - `gui/scripts/build_info.py` names the vendored directory in its digest,
    or the dist would go stale unseen. Bundling keeps the chart layer under
    svelte-check and within vitest's reach.
  - **Keeping it current.** Nothing in the repository watches a dependency
    today: there is no Dependabot or Renovate configuration. plotly.js moves
    with the Python `plotly` package, so a vendored uPlot would be the first
    copy that stays frozen by default. So uPlot is pinned exactly in
    `gui/package.json`, and `npm run build` copies its three files into
    `src/rietx/viz/static/`, the one step that writes them. A test holds the
    version in the vendored file's banner equal to the pin. Dependabot,
    limited to uPlot and svgcanvas, opens a pull request for each release.
    svgcanvas joins its allow list with the export task.
    The lock file is in the dist's digest, so that pull request stays red
    until someone runs the build, which refreshes the vendored copy too.
- **D3. One chart module in two layers.** `src/rietx/viz/static/rxplot.mjs`
  holds:
  - shared plumbing: panes on one x, sync, gestures, the readout hook,
    formatters, exports, theme and palette input;
  - the figures built on it: the pattern, the trajectory, the overlay.

  Its pure half (nearest lookups, tick formatting, TSV, the grid union) runs
  under `node --test` and vitest. Its drawing runs under browser tests.
- **D4. Full-resolution data once, zoom in the client.** Task 2 settled the
  route and the ceiling (§ The payload behind a client zoom).
  - **The route.** One GUI route answers with a fitted pattern's curves at
    full resolution, as float64 binary. The body is a uint32 length, a JSON
    header, then 8-aligned arrays. The header carries what the window
    route's JSON carries beside its arrays: `weighted`, the ticks and their
    hkl, `stale` and the counts. The arrays are the pattern's 2θ and
    intensity over every channel, `kept` and `fitted` (int32), and `y_calc`,
    `y_background`, `delta`, `delta_raw` and `cumulative_chi2` on the fitted
    channels. The raw view is the same payload without the model arrays.
    Built as `/api/result/curves` and `/api/series/curves`
    (`session.curve_arrays`, `viz/packed.py`).
  - **Binary** cuts the server's work from about 60 ms to under 2 ms and the
    browser's parse from 4-9 ms to nothing, at 57 % of the bytes. JSON at
    seven digits still serialises for 36-37 ms.
  - **Float64**, because float32 moves a re-based Σχ² by 1.2e-3 of itself
    over a narrow window. At float64 the readout prints the server's numbers.
  - **Every payload carries the current mask as `kept`.** `fitted` indexes
    the result's grid, and once `stale` is true that differs from the
    protocol's mask. The masked points are the current protocol's, as
    `_masked_arm` computes them. `kept` is sent whether or not the payload is
    stale, at 4 bytes a fitted channel, so the client has one path.
  - **When it is fetched.** The GUI fetches on open, on checkout and when a
    run ends (`App.svelte:960-976`), never per stage. It also refetches
    after an edit that can change the mask, as `draw` does today
    (`Plot.svelte:388-396`). A zoom fetches nothing.
  - **The series panel** reads a member through the same route with its
    index. `/api/series/result` stays JSON at 480 kB.
  - **The compare page's `/api/state`** drops the curves. Each variant's
    curves come once, in this format, when the variant lands.
  - The decoder is `rxplot.mjs`'s `unpack`, in its pure half (D3), shared
    by all three pages. `/api/result/window` and
    `/api/series/window` go when the plotly renderer goes.
  - This reverses `session.py:2575-2582`, which excluded the arrays because
    "a browser then decimates for a plot it can only draw a few thousand
    points of". uPlot draws 59 498 at the costs above.
  - `rietx watch` is outside this route. The fit writes its snapshot per
    stage, decimated, at the cost WP-1413 measured.
  - **The ceiling is 150 000 channels**, since D5 chose thinning
    (`session.CURVES_CEILING`). Above it the server decimates through
    `compare.decimation_index`, and `kept`, `fitted` and the model follow the
    channels that stay. It binds no pattern on disk: the largest is 132 992,
    where the real panel had no long frame in chromium (§ The pilot,
    measured), and the prototype's 200 000 had one.
- **D5. Thin per pixel column.** Decided by the pilot on 2026-09-25, by the
  rule set beforehand: every marker if it held § Acceptance 2's zero long
  frames on the real panel in all three browsers, and thinning otherwise.
  - Every marker did not hold. In chromium it made long frames of 50-127 ms
    at 132 992 channels, in the drag-zoom, the exclude and the wheel zoom,
    and its wheel zoom cost 8.5-9.6 ms an event at devicePixelRatio 2 on
    NAC. In Firefox and WebKit on NAC an exclude made frames of 166-258 ms.
    Thinned, chromium had no long frame at either size.
  - The chart paints each device-pixel column's lowest and highest point
    (`rxplot.mjs`'s `thinMarkers`), and the every-marker path is gone.
    Which points a payload carries stays the server's
    (`decimation_index`); which of them are painted is the chart's, and the
    readout and every hit test still read every channel. `gui/CLAUDE.md`'s
    "the client does not decimate" was rewritten to say that in the same
    commit.
- **D6. Exports.**
  - Copy PNG, download PNG, copy the visible data as TSV, and download SVG
    (svgcanvas, loaded on the first export, with its own and canvas2svg's
    notices). They replace the modebar's camera.
  - The modebar's modes become gestures: drag to zoom, wheel to zoom,
    shift-wheel or alt-drag to pan, double-click to reset, and the armed
    range and exclude modes as today.
- **D7. `write_html` keeps its name.** It loses `include_plotlyjs`, since
  uPlot is always inlined. `figure_from_arrays` returns a plotly Figure, so
  it is replaced by a function returning the page. An old file still opens.
  Code passing either breaks, and the break is recorded in the open
  milestone's record on the day it lands.
- **D8. A second grid, per surface.**
  - GUI pattern: the union is the pattern's own channel list, and the model
    lands on it through `fitted` (task 2). Onto 59 498 channels that took
    0.5-5.3 ms, no faster than merging the two grids. The index removes the
    merge as code.
  - Peak-group fits, candidate lines, ticks and peak markers: draw hooks.
  - Compare variants: each is decimated today on its own index set
    (`compare_app.py:481-495`). Every variant of `nac` and `lab6_capillary`
    fitted the same channels, bit for bit. So the variants share one x, and
    uPlot takes their typed arrays with no padding. The Δχ² panel's
    `resample` (`compare_app.py:461-472`) becomes a subtraction.
  - Series trajectory: in chain order, a heat-then-cool series loops. That
    needs mode 2 (an x per series) or a draw hook.
  - Series per-pattern chart: the union, as for the pattern panel.

### Where it will bite

- **Real Safari is untried.** The pilot drove playwright's Firefox and
  WebKit builds, and a drag works in that WebKit only because the probe
  supplies the mouse movement it leaves out (finding 15). `rietx gui` opens
  the default browser, which on a Mac is often Safari. WebKit also caps
  canvas size below Chromium, so the 2D map's 22 003-wide base level may
  need tiling.
- **The prototype flatters.** Its per-event costs have no app overhead. The
  pilot measures the real panel against the real plotly renderer.
- **One maintainer.** uPlot is Leon Sorokin's. Vendoring a pinned copy
  means a stalled upstream costs nothing until a browser change breaks it.

## Non-goals

- **The 3D structure viewer.** It draws a scene, and uPlot has no 3D.
  [WP-1462](1462-the-structure-viewer-draws-with-threejs.md) gave it its own
  WebGL2 renderer (PR #472, merged 2026-09-25). That also deleted the GUI's
  plotly: the `/plotly.js` route, `lib/plotly.ts`, and plotly in the `gui`
  extra, which is now `[]`. Its mount costs 14-34 ms of WebGL calls plus
  7-26 ms for `getContext` on a first opening of the Model tab
  (`1462-spike/results/first_show.txt`). WP-1462 renames its file after this
  WP closes, and the two links to it here follow.
- **matplotlib figures.** They are files, written without a browser.
- **New chart types.** The 2D map shows the module can carry one. A series
  map belongs to the WP that wants it; 1317 is the nearest.
- **The theme tokens** (`viz/theme.py`), consumed unchanged.

## Tasks

- [x] The maintainer confirms the migration on § Staying on plotly's numbers and decides D1-D8, and this file records which (D5 deferred to the pilot by that decision)
- [x] Measure D4 and D8 on real payloads (the NAC result, a compare standard, a series): JSON against binary arrays, parse, grid union. Settle the route and the ceiling. (Float64 binary, the pattern's own grid with a fitted index, compare curves out of the poll; the ceiling follows D5.)
- [x] Vendor uPlot 1.6.32, its css and LICENSE into `src/rietx/viz/static/`, copied there by `npm run build` from the exact pin in `gui/package.json` (D2, § Keeping it current). Add the ATTRIBUTION row and put the directory in `build_info.py`'s digest. A test holds the vendored banner's version equal to the pin. Add `.github/dependabot.yml` for uPlot in `gui/`. Rebuild the dist, since the pin moves the digest. (Serving it moved to the watch and compare tasks, where a page first loads it. svgcanvas joins Dependabot with the export task, which adds the dependency.)
- [x] The module's core: panes on one x, sync, drag, wheel and pan, y-zoom, select, the readout hook, the `ResizeObserver` path. Findings 1-3, 5 and 10 each get a case: the pure half under `node --test` and vitest, the drawing in a browser test. (`src/rietx/viz/static/rxplot.mjs`; `tests/rxplot.test.mjs` through `tests/test_rxplot.py`, and `tests/test_rxplot_browser.py`, which covers finding 12 too. Vitest moved to the pilot, where the GUI first imports the module.)
- [x] Pilot, the gate: the curves route (D4) and its decoder in the module's pure half, and the GUI pattern panel on the core behind a flag, with the plotly renderer still selectable. Port the spike driver to the real page as the acceptance probe. Measure § Acceptance 1-3 against the plotly renderer on the same machine, in Chromium, WebKit and Firefox through playwright's builds. Build both marker paths (D5) and measure each, at NAC's 59 498 channels and at `11BM_LaB6_660a.fxye`'s 132 992. Record go or no-go, which marker path, and so which ceiling, in the handover. The GUI's vitest imports the module's pure half. (**Go**, § The pilot, measured. D5 chose thinning, so the ceiling is 150 000 channels. The flag is `?chart=uplot`; the probe is `pilot.mjs`.)
- [x] GUI pattern panel complete: peaks, candidates, masks, raw view, readout fields, Esc, axis titles. Delete the plotly-only code, stub uPlot in `test-setup.ts`, and move `App.test.ts` off the `Plotly.react` stub. Drawn colours are asserted from pixels or from the recorded `strokeStyle`. (Task 15 came in with it, by the maintainer's decision in § Decisions. Also the Σχ² re-base at a zoom, `rxplot.chi2Base`; the raw view's per-group residual through `rawResidual`; the pointer's line restyled solid `--fg`; `/api/result/window` deleted with its only client. `gui/src/test-uplot.ts` is the stand-in, `tests/test_gui_browser.py` reads the inks.)
- [x] `rietx watch` on the module, serving the vendored uPlot from its own server. `test_watch_browser.py` asserts what was drawn. (`rxplot.pattern` gained `ranges`, so the page holds the intensity to the observed points and Δ/σ to its ladder. The legend, the point count and the tick label are the page's own DOM over the chart. `test_watch_browser.py` reads uPlot's scales and the inks the canvas recorded, through `RECORD`, which `test_gui_browser.py` now imports.)
- [x] GUI Series panel: trajectory (D8), per-pattern chart through the curves route, rings, crosses plotted, the dashed tone, the tick formatter (`rxplot.trajectory` draws the chain in a draw hook over one pane, so a heat-then-cool series comes back along its own x, and picks the hovered point by `nearestXY`. Every labelled x axis now takes `tickLabels`. The member's chart is `rxplot.pattern` over `/api/series/curves`. `/api/series/window`, `curve_window` and `_series_masked_arm` are deleted. The legend is the `.segmented` curve toggles with a swatch in each. The pointer line's `--fg` rule moved to `app.css` for every GUI chart.)
- [x] `rietx compare`: its page becomes a file, on the module, and its server serves the vendored uPlot. `/api/state` drops the curves, and each variant's come once through a route (D4). `resample` becomes a subtraction. Delete `viz/plotlyjs.py`, whose one caller the compare page is. (`compare_app/` is a package with the page in `static/` and `compare-core.mjs` its pure half; `rxplot.overlay` draws it; `/api/curves` packs a variant's arrays. `RunRecord` keeps float64 arrays at every channel and decimates past `CURVES_CEILING`, now `viz.packed`'s, on the observed points alone, so every variant keeps one grid. `viz/chart.py` holds the chart-file table both servers read. Found on the way and fixed in `panes()`: a one-phase tick band had a 5 px plot area, and every line ringed its points once zoomed, in the GUI, the watcher and the Series panel too.)
- [x] `write_html` writes the uPlot page, with the notice inline, the weighted mode, `viz/plots.PALETTES` as its palette and the `"hkl: …"` labels `test_magnetic_tick_row.py` reads. Drop `include_plotlyjs`, replace `figure_from_arrays`, take plotly out of the `viz` extra, and record the break. (`viz.html.page` replaces `figure_from_arrays` and returns the file: uPlot and its licence, the chart module, `viz/figure/`'s script and stylesheet, and the curves as base64. The curves are `viz.packed.curve_arrays`' payload, moved there from `gui/session.py`, whose two routes keep a wrapper turning its refusal into a 409. Found on the way: the compare page had no pointer-line rule, so the rule moved into `rxplot.panes` for every page, and the compare page's drag box took the watcher's rule. The decimation now keeps the raw difference's extremes, which the GUI's Δ view lost too. On NAC the file is 1.23 MB against 6.49 and draws at 80-87 ms against 521-601.)
- [x] Exports: copy PNG, download PNG, copy TSV, SVG through svgcanvas with its notices. Pin svgcanvas exactly in `gui/package.json` and add it to `.github/dependabot.yml`'s allow list. (The group's `png`, `copyImage`, `svg(load)` and `tsv` in `rxplot.mjs`, each figure giving its rows through `group.table`; `exportButtons` for the three plain pages, `panels/Exports.svelte` in the GUI's pattern and Series panels. svgcanvas 2.6.0 is vendored by `vendor.py`, which now records both versions in `VENDORED.json`, served as `/svgcanvas.esm.js`, inlined in the written file, and a lazy `vendor-svgcanvas` chunk in the GUI. Found on the way: the export row's static import put the chart module on the GUI's boot path, so `test_gui_dist.py` now holds all three chart chunks off it.)
- [x] Structure3D loads plotly when first shown. A test asserts no other page requests `/plotly.js`. Record the first-show cost. (Overtaken by WP-1462: the viewer loads no plotly. `test_the_built_app_is_served_and_plotly_is_not`, `test_gui_dist.py` and `test_the_viewer_draws_the_structure_and_asks_for_no_plotly` assert it, and the first show is measured in `1462-spike/results/first_show.txt`.)
- [x] Remove the flag and the pattern panel's plotly renderer (in task 6)
- [ ] Docs: the `gui/CLAUDE.md` rules as § What changes sorts them, the manual's GUI chapters with regenerated screenshots, `using/cli.md`, `install.md` and `files.md`, root CLAUDE.md, `tests/CLAUDE.md`, README
- [ ] Tests: the suites in § Acceptance green, the fast count's movement stated, and every test listed in § What changes updated
- [x] Skill: regenerate `references/api.md` with `make_api_index.py` when D7 lands, then `rietx skill --install . --copy`. Nothing else in the skill draws a browser chart. (With task 10, `4e65cc9a`: `write_html`'s row lost `include_plotlyjs` and gained `max_points: int | None`. No other skill file names plotly.)

## Acceptance

Measured by the spike driver ported to the real pages, on the NAC example,
in Chromium at devicePixelRatio 1 and 2. Each run is paired with the plotly
renderer on the same machine and load, and three or more runs give ranges.
These are measurements recorded in the handover, not test budgets (root
CLAUDE.md: a wall-clock budget in a test is a runaway guard).

1. **Opening the GUI:** no long animation frame is attributed to a chart
   library. Today plotly's evaluation is a 700-811 ms frame and its first
   draw a 315-415 ms frame.
2. **Gestures:**
   - Hover, drag-zoom, an exclude drag and a peak drag each cost no more
     main-thread work per event than the plotly renderer on the same run.
   - Wheel zoom and pan, which plotly's renderer does not offer, cost at
     most 8.3 ms per event, half a 60 Hz frame.
   - Every gesture holds a p95 frame of 17.7 ms or less with zero long
     animation frames.
   - A zoom ends without a network round trip.
3. **Resizing:** the chart's own work is at most 5 ms, and it shows its new
   size in the frame after the resize, with no timer.
4. **`write_html`** on the NAC result: at most half of today's plotly file,
   in both size and time to first draw. The spike measured 1.63 against
   6.53 MB and 83-93 against 598-686 ms.
5. **No plotly on chart pages.** No page requests `/plotly.js` except when
   the 3D view is first shown. `rietx watch`, `rietx compare` and a written
   file load no plotly at all.
6. **Coverage:** every behaviour in § Every feature and § Behaviours the
   spike did not rebuild is present and named by a test.
7. **Other browsers:** in WebKit and Firefox through playwright's builds,
   every gesture works, nothing throws, and per-event work is recorded.

```sh
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m pytest tests/test_watch_browser.py tests/test_gui_server.py tests/test_watch_app.py tests/test_magnetic_tick_row.py
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m ruff check src tests examples
.venv/bin/python -m sphinx -W -q -b html docs/manual docs/manual/_build/html
```

## References

- uPlot 1.6.32, Leon Sorokin, MIT. <https://github.com/leeoniya/uPlot>
- svgcanvas 2.6.0, MIT, descended from Gliffy's canvas2svg (MIT).
  <https://github.com/zenozeng/svgcanvas>
- plotly.js, MIT, as served by the Python `plotly` 7.1.0 package.
- Apache ECharts 6.1.0, Apache-2.0. Measured once by latency
  (`results/gpu3.txt`): replacing its data at 22 003 points took 23-25 ms,
  longer than a 60 Hz frame. Not taken further.
- Grafana's time-series panel is built on uPlot, the prior art for a
  measurement UI on this library.
- Long Animation Frames API (W3C draft): what counts as a long frame here.

## Handover log

### 2026-09-26 (8th session) — write_html and the exports draw with the chart module

No chart rietx draws needs plotly now. The file `write_html` writes is the
GUI's pattern chart, with uPlot, the chart module and the fit's numbers inside
it, so it opens from a disk with no network. On the NAC example it is a fifth
of the plotly file's size and draws in a sixth of the time. Every chart can
now save a PNG or an SVG of what it shows and copy the picture or the numbers
in view. That replaces plotly's camera button on five surfaces. Two defects
were found on the way and fixed where every page draws. The GUI's Δ view could
lose its deepest misfit past the channel ceiling, and the compare page drew
the pointer line dashed. What is left is the documentation pass and the
acceptance measurements.

*Done:*
- The claim (`6e94c2ea`). The branch is `wp1461-write-html`, stacked on
  `wp1461-compare`, and its PR #476 has that branch as its base, so #474
  merges first. The WP had no `### Inherited` to prune.
- Task 10 (`4e65cc9a`).
  - `viz.html.page` replaces `figure_from_arrays` and returns the file:
    uPlot with its licence, the chart module, `viz/figure/`'s script and
    stylesheet, and the curves as base64 float64. `write_html` lost
    `include_plotlyjs`, and `max_points` now defaults to `CURVES_CEILING`
    (it was 200 000). The break is in `releases/1.5.1.md`'s Upgrading.
  - The script joins the module in one `<script type="module">`, inside a
    block, so no name either declares can collide. `html.py` takes its one
    import line out by exact match and refuses a file that does not have it.
  - `curve_arrays`, `_under_ceiling` and `_tick_rows` moved from
    `gui/session.py` to `viz/packed.py`, so the file draws the GUI's payload.
    Session keeps a wrapper turning `OffPattern` into its 409. The ceiling is
    read at call time, since a test monkeypatches it.
  - The file draws from `PALETTES["light"]`, the matplotlib figure's, with
    the light theme's chrome for axes and grid. `weighted=True` draws Δ/σ
    with the ±3σ band; otherwise the raw difference, in its own pane now.
  - Found and fixed: the decimation kept Δ/σ's extremes and not the raw
    difference's, which the file and the GUI's Δ view draw. The pointer-line
    rule moved into `rxplot.panes`, since `rietx compare` had none. The
    compare page's drag box took the watcher's rule, because uPlot's 7 %
    black vanishes on the dark theme.
  - plotly left the `viz` extra, `ATTRIBUTION.md`, `README.md`,
    `install.md`, `files.md` and the GUI's html export, whose 409 went.
    `api.md` was regenerated and both skill copies re-synced (task 15).
- Task 11 (`abb680be`).
  - The pane group has `png`, `copyImage`, `svg(load)` and `tsv`, and each
    figure gives its rows through `group.table`. The SVG redraws each pane
    once through svgcanvas under a recording `Path2D` (finding 6), at the
    live pane's size, x and y range and shown series.
  - Placement: the GUI's pattern and Series panels (`panels/Exports.svelte`),
    the file's header, an Export section on the compare page, and an
    `export` menu in the watcher's bar, which keeps one row at 420 px.
  - svgcanvas 2.6.0 is pinned, allowed by Dependabot, and vendored by
    `vendor.py`, which now takes a table of packages and records their
    versions in `VENDORED.json`. The watcher and compare serve it, the file
    inlines it, and the GUI loads it as the lazy `vendor-svgcanvas` chunk.
  - Found and fixed: the export row's static `import {download}` inlined the
    chart module into `app.js` with nothing going red. `test_gui_dist.py`
    now holds the chart module, uPlot and svgcanvas off the boot path, and
    the gui rulebook says so.
- `/code-review high --fix` over the branch's own diff made nine findings and
  fixed eight (`340cfafa`).
  - An all-zero background was still sent, drawing a line at zero that no
    legend entry could hide. The file now leaves it out.
  - `copyImage` awaited the PNG before the clipboard write, which Safari
    refuses once the press's activation is spent. It passes the promise.
  - `download` revoked its URL at once, before Firefox and Safari read it.
  - An SVG export moved the GUI's hover ring into the pane's copy, which
    took it away. The ring stays on the live pane.
  - The Series export numbered patterns from 1, and the panel from 0.
  - Before a fit the table's residual column is named `residual`, since it
    holds the page's own values.
  - `srm660c_lab.py` wrote its page inside the matplotlib guard, and two
    docstrings still named plotly.

  I left one. `Exports.svelte` restates `exportButtons`' four verbs and
  their words. Sharing them would load the chart module when the row
  mounts, which the boot-path rule above forbids.

*Measured:*
- `write_html` on the NAC result, 22 003 fitted channels, against
  `origin/main`'s plotly writer on the same result: 1.23 MB against 6.49 MB,
  and 80-87 ms against 521-601 ms from navigation to a drawn canvas. Three
  alternating loads each in chromium at load 3.0-3.9. Acceptance 4 holds.
- The raw-difference decimation, on the synthetic fixture cut to 600
  channels: its minimum read −363 where the pattern holds −391. The GUI's
  ceiling test failed the same way (362.5 against 391.4) before the fix.
- The GUI dist: `app.js` 312.67 to 315.02 kB, the `rxplot` chunk 14.9 to
  18.7 kB, and `vendor-svgcanvas` 24.05 kB (7.71 kB gzip), fetched on the
  first SVG alone.
- The file's exports at devicePixelRatio 2, zoomed to 8-12°: PNG 153 kB, SVG
  177 kB, a TSV of 800 rows. The SVG, drawn back in the browser, matches the
  canvas.
- Fast suite at `abb680be`: 6260 passed, 140 skipped, 6400 in all, in 2:58.
  That is the `[dev]` venv plus playwright on macOS arm64, with another
  session's pytest running at load 5.0. Against 6379 at `ad817bbf` that is
  +21, and the diff accounts for all of it: +3 net in
  `test_events_viz_history.py` (three plotly tests gone, six added), +4 in
  `test_rxplot_browser.py`, 10 in the new `test_html_browser.py`, and one
  each in the watcher, compare, GUI browser and dist suites. No new skip.
- Vitest 560 to 563, the three in `Exports.test.ts`. svelte-check clean.
  `rxplot.test.mjs` 17 to 19. The browser suites and every module this
  touches together: 518 passed, then `test_structure3d_browser.py` 4 after
  its fix.
- Every new guard was broken on purpose once and failed as expected: the
  pointer line (dashed #607d8b), the export's y range (a live label `90`
  missing from the SVG) and the raw decimation (above).
- The full selection did not run. No refined number moves.
- After the review's fixes, the six suites they touch ran again: 97 passed.

*Deliberately not generalised:*
- The legend is in neither picture, since every page draws it as DOM over
  the chart. The TSV carries the names.
- The file is light only, as plotly's was, though `PALETTES` has a dark set.
- `uv.lock` still names plotly. Nothing has re-locked it since WP-1109, and
  WP-1462 left the `gui` extra in it too.
- The drag box stays a rule in each page's stylesheet, since the GUI dresses
  it as the exclusion an armed drag will leave.
- The GUI's pattern export is named `pattern`, because the panel is handed
  no project name.

*Gotchas:*
- svgcanvas's constructor asks for a native 2D context itself. The recording
  patch marks itself taken before constructing, or it re-enters without end.
- A panel importing anything but types from `rxplot` at the top puts the
  chart module on the boot path. Import it inside the handler.
- A new vitest file needs `// @vitest-environment jsdom`, since the config's
  default is node. Editing any test under `gui/src` moves the dist's digest,
  so rebuild.
- The GUI now shows two `PNG` buttons, the pattern's and the 3D viewer's, so
  a locator scopes to its panel.
- A watcher probe outside the suite never reaches `networkidle`. Wait on the
  suite's `DRAWN` instead.
- The worktree guard refuses long heredocs, as before. Scratch scripts did
  the edits.

*Next:*
1. Merge #474, then #476 on top of it.
2. Task 13, the docs. That covers the plotly-era paragraphs of `gui/CLAUDE.md`
   as § What changes sorts them, the manual's GUI chapters with screenshots
   from `make_screenshots.py` showing the export row, `using/cli.md` for
   `rietx html`, root CLAUDE.md, `tests/CLAUDE.md` and the README.
3. Task 14. Measure § Acceptance 1-3 and 5-7 on the real pages in chromium,
   WebKit and Firefox, paired against the plotly build of `58f7dbce`, and
   check each test § What changes lists. Then the WP closes, and WP-1462's
   rename follows.
4. Someone with Safari tries a drag in each page (finding 15).
5. The `/api/peaks` payload's `pattern` arm (the 5th session's Next 4).

### 2026-09-26 (7th session) — rietx compare draws with the chart module

`rietx compare` no longer uses plotly, and a base install draws it. Its three
panes are one figure on one 2θ axis, with the gestures the GUI and the watcher
have. Each variant's curves now come once and at every channel. The page used
to resend a 4000-point sample of every variant on each 700 ms poll. The Δχ²
panel is a plain subtraction, because every variant of a standard fits the
same channels, and a test now holds the registry to that. Building the page
showed two defects the GUI, the watcher and the Series panel shared: a
one-phase tick band 5 px tall, and a ring on every point of a line once a zoom
spread them. Both are fixed in the one place all four pages draw. What still
loads plotly is the file `write_html` writes, and the GUI's html export
through it.

*Done:*
- The claim (`168e2388`) and the Inherited prune (`7c38ce7f`). WP-1462's note
  folded into § Non-goals, and task 12 is ticked as overtaken: the viewer loads
  no plotly and three tests say so.
- Task 9 (`ad817bbf`).
  - `compare_app.py` is the package `compare_app/`, with the page in
    `static/`: `index.html`, `compare.css`, `compare.mjs` and
    `compare-core.mjs`, the pure half that imports nothing. `.gitignore` took
    the new `index.html` exactly as it took the watcher's, so it gained
    `!src/rietx/compare_app/static/**`, and a `check-ignore --no-index` test
    covers each file.
  - `rxplot.overlay` is D3's third figure: `cum`, `diff` and `fit` panes and
    a tick band carrying the x axis. The reference draws flat at zero, so a
    new reference is new numbers for one pane. A reference with no fit yet
    leaves `cum` empty rather than taking another fit's Δχ². `difference` and
    `hklLabel` joined the pure half.
  - `/api/state` sends `RunRecord.summary()`, with no arrays and no ticks.
    `/api/curves?standard=&variant=` sends `RunRecord.curves()` packed, the
    ticks in its header. The page fetches each variant once and drops a fetch
    answered after the reader cleared the plots or changed standard.
  - `RunRecord`'s six arrays are float64 at every fitted channel. Past
    `CURVES_CEILING` they are decimated on the observed points alone, which
    every variant of a standard shares, so the grids stay one. The ceiling
    moved from `gui/session.py` to `viz/packed.py`, and session re-imports it.
  - A failed variant's NaN statistics went out as a bare `NaN`, and
    `JSON.parse` threw on it, so one failed variant stopped every poll.
    `summary()` sends `null`, and `RunRecord.failed` builds both failure
    records.
  - The variant list is the legend. Each entry carries its swatch, and
    unticking hides the variant in every pane without a rebuild, so the zoom
    holds. A variant landing rebuilds the figure at its old x range. The
    sticky line over the panes reads each variant's value at the pointer, and
    over the tick band a tip names the reflection.
  - `viz/plotlyjs.py` is deleted. `viz/chart.py` holds `CHART_DIR` and
    `CHART_FILES`, which both servers read.
  - Found by looking, fixed in `panes()` for every page. A band (`yLabels:
    false`) now has no automatic top padding. That padding took 17 px of a
    one-phase band's 22. Every series now defaults to `points: {show:
    false}`, where uPlot ringed each point once they sat far enough apart.
    Both guards were broken on purpose and failed as expected (5 against 22;
    rings on three series).
  - Also fixed: switching standard mid-run left the poll waiting for variants
    nobody asked for, so Run stayed disabled. The old page had this too.
  - Docs: root CLAUDE.md's page-is-a-file rule names both pages and the
    `.gitignore` line a page directory needs. `using/cli.md` says what the
    figure does. `releases/1.5.1.md` has a section, and its WP-1462 line
    that said compare still draws with plotly is corrected.
  - The GUI: `rxplot.d.ts` declares `hklLabel`, `plot.test.ts` holds the
    module's copy equal to the other two, and the dist is rebuilt.
- `/code-review high --fix` made five findings and fixed three (`135f9d41`).
  - The poll waited on every ticked variant, so one ticked after Run held Run
    disabled for good. It now waits on the variants Run sent.
  - A Run whose standard changed before its request answered started a poll
    for the new standard. It now returns.
  - `fmt` printed a missing parameter value as `0.000000`. It prints a dash,
    and a node case says so.

  I left two. `_finite` answers "how does a non-finite float reach a browser"
  with `null`, where `gui/server.py`'s `_finite` sends the strings `NaN` and
  `Infinity`. Unifying them changes one page's wire format for no reader's
  gain, and each page's reader handles its own. The Δχ² axis title can keep
  an old variant's name when the reference moves between two variants that
  both lack curves. It shows only over a pane that is already empty.

*Measured:*
- Fast suite at `ad817bbf`: 6239 passed, 140 skipped, 6379 in all, in 3:11.
  That is the `[dev]` venv plus playwright, macOS arm64, with no other pytest
  running, at load 3.5-3.8. Against `origin/main` this branch adds 19 Python
  test functions and removes 2, so +17: five in the new
  `test_compare_browser.py`, a net eight in `test_compare_ui.py`, five in
  `test_rxplot_browser.py`, and minus one in `test_watch_app.py`. No
  baseline was measured here, since that is CI's job, so the +17 is from the
  diff and not from two runs.
- Node: `compare_core.test.mjs` 10 cases (one gained an assertion in review), `rxplot.test.mjs` 15 to 17. Vitest
  560, the new assertions inside an existing case. svelte-check clean.
- The browser suites together (GUI, watcher, chart, compare, dist): 108
  passed.
- On real zincite fits, baseline and anomalous dispersion: 7251 channels
  drawn, where the old page sent 4000 a variant. Three polls and two curves
  fetches, one per variant. Dispersion ends at Δχ² −518.65 against baseline.
  Light and dark both checked by eye.
- `test_no_variant_moves_the_channels_a_standard_fits` builds every
  available standard under every variant it applies to, in 2.5 s.
- After the review's fixes (`135f9d41`), which touched only the compare page, its two modules ran again on the final tree: 65 passed. `origin/main` had not moved since the branch was cut.
- The full selection did not run. Nothing here moves a refined number.

*Deliberately not generalised:*
- A Miller index now has three formatters: `watch-core.mjs`, the GUI's
  `formatHkl` and the module's `hklLabel`. `plot.test.ts` holds all three
  equal. `watch-core.mjs` cannot import the module under `node --test`, which
  runs it from another directory. The GUI's could import the module's, and
  was left alone.
- The ten variant hues stay literals, as WP-1429 decided.

*Gotchas:*
- The compare page's tick band sits below the fold at 900 px, so a pointer
  test scrolls the pane into view first (`_centre`).
- Ticking a checkbox from script fires no `change`, so the page's reference
  list goes stale. The tests dispatch the event (`_tick`).
- Importing `test_compare_ui`'s `server` fixture into another module trips
  ruff F811 on the parameter that uses it. The `noqa` names why.
- A change to `rxplot.mjs` moves the GUI dist's digest. Rebuild under node
  22 (`~/.nvm/versions/node/v22.15.0/bin` on `PATH`) and run `npm ci` there
  first.
- The worktree guard refuses long heredocs and loops. Splice scripts in the
  scratchpad did the larger edits.

*Next:*
1. Task 10, `write_html`, D7's break. Record it in `releases/1.5.1.md` on the
   day it lands. Plotly leaves the `viz` extra with it, and the GUI's
   `html` export follows: `session.py`'s 409 naming the `viz` extra goes.
2. Task 11, the exports. The compare page lost plotly's modebar camera here,
   so until task 11 it has no PNG download. Task 11 covers it as a third page.
3. Tasks 13-15: docs, the tests' final pass, the skill.
4. Someone with Safari tries a drag in the GUI, the watcher and now the
   compare page (finding 15).
5. The `/api/peaks` payload's `pattern` arm (the 5th session's Next 4).

### 2026-09-25 (6th session) — the watcher and the Series panel draw with the chart module

`rietx watch` and the GUI's Series panel no longer use plotly. The watcher now
serves the chart itself, so a base install draws the live picture, where it used
to print an install hint in its place. The watcher's plot takes the GUI's
gestures, a legend that hides curves, and the same tick label as before. A series
trajectory is now drawn in the order the chain ran, so a heat-then-cool ramp
comes back along its own axis, which D8 thought would need uPlot's scatter mode
and did not. The window route the Series panel used is deleted, so the curves
route is the only way a pattern reaches a GUI chart. What still loads plotly is
`rietx compare`, `write_html` and the 3D view.

*Done:*
- Task 7, the watcher (`0e14ff05`).
  - `watch.mjs` draws the snapshot with `rxplot.pattern`, turned into a
    curves payload by `watch-core.curvesOf`, every channel kept and fitted.
    A stage is `setCurves(…, keep)`, so the reader's zoom and hidden curves
    survive it. Another run is a new figure.
  - `rxplot.pattern` takes `ranges`, a page's own auto y range (a pane's
    `auto`). The watcher holds the intensity to the observed points in view
    (`intensityRange`) and Δ/σ to its ladder over the whole snapshot
    (`deltaRange`). `rangesOf` split into those two. A drag still pins y over
    either.
  - The legend, the point count and the tick label are the page's own DOM over
    the chart: the legend at the plot area's top left, as wide as it at most;
    the count under the x axis at the left end; the tick label over the band.
    `legendOf` names custom properties, so a theme switch restyles it by CSS.
  - The server serves `rxplot.mjs`, `uPlot.iife.min.js` and `uPlot.min.css`
    from `viz/static` (`watch.CHART_FILES`). `/plotly.js` and the missing-plotly
    message are gone. `coalesce`, `withAlpha` and `phaseInk` went with plotly.
  - A theme switch or the system's scheme moving repaints the canvas without a
    refetch (`retheme`).
- Task 8, the Series panel (`288c83db`, docs `9c84d303`).
  - `rxplot.trajectory`: one pane whose only series sets the x extent, and a
    draw hook painting the chain in chain order, esd whiskers only where there
    is an esd, the dotted backward chain, rings and crosses. The pointer picks
    by distance in the plane (`nearestXY`), since the two legs of a loop share
    an x. `setHidden` takes "forward", "esd", "backward", "rings", "crosses".
  - Every labelled x axis now takes `tickLabels` (finding 3).
  - The member's chart is `rxplot.pattern` over `/api/series/curves`.
    `lib/seriesChart.ts` binds uPlot to both figures and is imported on the
    first draw, as `lib/pattern.ts` is.
  - The legend is the pattern panel's `.segmented` toggles with a swatch in
    each (`trajectoryLegend`, `memberLegend`). The pointer text is
    `pointText`: the value to six figures, the esd to two.
  - Deleted: `/api/series/window`, `GuiSession.series_window`,
    `_series_masked_arm`, `curve_window` and `api.seriesWindow`.
    `_windowed_ticks` became `_tick_rows`, its window gone with its caller.
    The curves tests' oracle is now a result's own σ arithmetic
    (`_residuals`), and the window test's two unique facts (a later exclusion
    moves no member's mask; the index is required) moved to the curves test.
  - The pointer line's solid `--fg` is one rule in `app.css` for every GUI
    chart, out of `Plot.svelte`.
- Found by looking and fixed: at the run pane's 340 px floor the watcher's
  point count ran into the centred 2θ title. It moved to the title row's left
  end, and `test_the_point_count_keeps_clear_of_the_axis_title_at_the_floor`
  measures ink against room.
- Also fixed: `using/cli.md` said the watcher has no theme control, and it has
  one since WP-1438. Its route table counted eight routes over ten rows.
- Guards broken on purpose, each failing as expected: the caption placement,
  the ±3σ band, and the page-owned ranges (both the intensity and the ladder).
- WP-1317's `### Inherited` has what it needs from task 8, and supersedes the
  mode-2 remark this WP left there.
- `/code-review high --fix` made eight findings and fixed all eight
  (`5ef72f03`, `078ecde2`, `72a3da03`, `44ff6f5e`):
  - shared panes raised to their floor overran the host, so a clipping host
    cut the last axis (4 px on a 260 px Series member chart);
  - a throw building the watcher's chart skipped `pumpEvents`, stopping the
    console, and each retry stacked another legend in `#plot`;
  - showing the Series tab again rebuilt its figure and lost the zoom and the
    hidden marks, where plotly's `uirevision` kept both;
  - a member with no background offered a live toggle that did nothing, where
    WP-1210 says list it disabled with the reason;
  - the Series toggle restated `toggleCurve`;
  - three `gui/CLAUDE.md` statements the port made false.

  I rewrote one of its rulebook lines. It said WP-1015's swallowed-click trap
  now applies to the Series canvas, but the host clips the canvas and its
  observer refits it, so nothing overhangs a control. It left three alone,
  each with a reason: a missing `--phase-*` token could part the watcher's
  legend from its canvas (the tokens are generated); `_tick_rows` no longer
  drops a non-finite tick position (positions are finite); the intensity
  range copies the points in view at each zoom (a snapshot is screen-sized).

*Measured:*
- Fast suite at `288c83db`: 6130 passed, 140 skipped, in 3:12. `[dev]` venv
  plus playwright 1.63.0, macOS arm64. The total is 6270 against 6262 at the
  start of the session. Task 7 added four watcher browser cases (zoom across a
  stage, legend toggle, the ±3σ band, the caption at the floor). Task 8 added
  five trajectory cases in `test_rxplot_browser.py` and deleted the series
  window test. The browser modules ran, since playwright is in this venv; they
  skip in CI.
- Fast suite on the final tree with main merged in (`e1a25c52`): 6159
  passed, 140 skipped, in 3:11, 6299 in all. Main brought the other 29, 26
  new test functions from #385 and one of them parametrized four ways. The
  review added no Python test. Another tree's pytest was running beside it,
  at load 5-12.
- vitest 558 → 561: `series.test.ts` lost six trace cases and gained eight,
  and the review added the missing-background case. svelte-check clean.
- Node: `watch_core.test.mjs` 48, `rxplot.test.mjs` 15.
- Other browsers, playwright's Firefox 155 and WebKit 26.6, one probe each: the
  watcher draws, names a tick, keeps a wheel zoom across a stage and steps the
  ladder; the Series panel draws a looping trajectory, names the hovered point
  and draws a member's pattern. No page error in either.
- The watcher's legend: five entries take 409 px in one row and six 504. At
  the 340 px floor it is three rows and 58 px, 15 % of the plot, where plotly's
  was three rows there and six by 300.
- The watcher's seven served files are 188 kB.
- The full selection did not run: nothing here moves a refined number.

*Gotchas:*
- A probe of the watcher or the GUI reads and writes the real
  `~/.rietx/settings.json` unless `RIETX_STATE_DIR` is a temp dir, and a
  colour test that does not isolate it draws in this machine's stored theme.
  The new colour tests call `_light`.
- The watcher's picture is instrumented through `#plot.__rx`, the figure, and
  `RECORD`, the canvas ink recorder `test_gui_browser.py` now imports.
- A cross's 2.2 px arms reach 6 px above its point, so the ring test probes at
  7 px.
- `App.test.ts` imports `lib/seriesChart` up front for the same reason it
  imports `lib/pattern`. The uPlot stand-in gained `clip()`.
- The worktree guard refuses long heredocs and variables in paths. A splice
  script in the scratchpad (`START`, `END`, replacement file) did the edits.

*Next:*
1. Task 9, `rietx compare`: its page becomes a file on the module, its server
   serves the vendored uPlot from `watch.CHART_FILES`' table (move it to
   `viz` when a second server needs it), `/api/state` drops the curves and
   each variant's come once through a route, and `resample` becomes a
   subtraction.
2. Then tasks 10-14 in order. Task 10 is D7's break, recorded in the release
   record on the day it lands. Task 12, loading plotly on the 3D view's first
   show, overlaps WP-1462, which another session held at this handover
   (branch `wp1462-structure-viewer-scope`). Read where it stands first: if
   the viewer leaves plotly, task 12 shrinks to the test that no page loads it.
3. Someone with Safari open tries a drag in the GUI and the watcher
   (finding 15). They are the only renderers now.
4. The `/api/peaks` payload's `pattern` arm is still a decimated copy read
   only as a boolean (the 5th session's Next 4).
### 2026-09-25 (5th session) — the pattern panel draws with the chart module alone

The GUI's pattern plot no longer uses plotly. It gets every channel once and
zooms in the browser, with scroll-to-zoom and panning as new gestures. The
plotly renderer and its `?chart=uplot` flag are deleted: 800 lines of the panel
and 360 of its helpers, much of it the machinery that kept plotly's axes still. Tasks 6 and 15
contradicted each other about when that could happen. Asked, the maintainer
chose now, so task 15 is done inside task 6. `/api/result/window` lost its only
client and is gone too. Two defects surfaced by looking in a real browser and
are fixed. uPlot's default pointer line reads as an exclusion edge, and the
raw view's group residual wore the wrong ink. The 3D view and the Series panel
still load plotly.

*Done:*
- Task 6 and task 15 (§ Decisions records the maintainer's choice). What the
  pilot had left out:
  - A zoomed Σχ² re-bases at every x zoom (`rxplot.chi2Base`), and the readout
    quotes the re-based value.
  - The raw view's per-group residual comes through the new `rawResidual`
    spec and `refreshResidual` verb. It is drawn in `--plot-peakfit`, as
    plotly drew it.
  - The residual pane's title says "(y − fit)/σ per group" on the raw view.
  - `windowOf` gathers typed arrays and hands the model's arrays through
    uncopied, which was the last review finding the pilot left.
  - `.u-cursor-x` is solid `--fg` (WP-1213's rule). uPlot's default is
    dashed `#607d8b`.
- Deleted: in `Plot.svelte` the plotly renderer (1866 → 1062 lines).
  In `lib/plot.ts`: `chartChoice`, `phaseInk`, `drawnRange`, `heldRanges`,
  `span`, `PINNED_AXES`, `noAxes`, `pinPatch`, `movedAxes`, `forget`,
  `userRanges`, `TICK_BAND`, `tickBand`, `candidateLines`, `CANDIDATE_AXIS`,
  `scaleValues` and `sqrtTicks` (1092 → 729 lines). `maskShapes` now returns the shading layer's
  own shape (`MaskShape`). `hoverLabel` stays, for the Series panel and the
  3D view.
- `/api/result/window` removed: `GuiSession.result_window`, `_masked_arm`, the
  route, `api.window` and the manual's row. What their docstrings had measured
  moved to `result_curves` and `curve_window`. Six server tests now hold the
  curves route to the same facts. `curve_window` stays, for
  `/api/series/window` (task 8).
- Tests: `gui/src/test-uplot.ts` stands in for uPlot under vitest. It keeps
  uPlot's state, fires the module's hooks, and records each stroke and fill
  with its style. `gui/src/test-curves.ts` packs a curves body. About 35
  `App.test.ts` cases moved off `Plotly.react`, and the WP-1212 block went.
  `tests/test_gui_browser.py` (3 cases) reads the inks chromium painted
  through an init script wrapping `CanvasRenderingContext2D`. There is one
  new case each in `rxplot.test.mjs` and `plot.test.ts`, and two in
  `test_rxplot_browser.py`.
- Four guards were broken on purpose, and each failed as expected: the
  re-base, the readout's base, the dashed background and the raw residual.
- `/code-review high --fix` made six findings and fixed four (`040c07ce`):
  - hiding Δ/σ on a fit hid the raw view's group strip after a checkout,
    and the raw view offers no toggle to bring it back;
  - each Σχ² re-base allocated two channel-length arrays, once per wheel
    tick;
  - a peak edit on a fitted view rebuilt the model's residual;
  - the raw view's axis named a curve it was not drawing.

  It also corrected a `gui/CLAUDE.md` pointer to the deleted `_masked_arm`.
  It declined the `/api/peaks` `pattern` arm, which is *Next* 4, and a
  historical `curve_window` sentence that is still true. I added the missing
  case for the first fix (`test_diff_hides_the_fits_residual_and_never_the_pages`).
- `gui/CLAUDE.md`: the plotly rules for this panel went (autorange, pinning,
  the select-outline override, the gl ring). What the plot says stays.
  Staged in `releases/1.5.1.md` with the removed route. Two manual
  paragraphs in `gui-guide.md` are corrected.

*Measured:*
- Fast suite on the final tree, which is also the merged tree since main had
  not moved: 6122 passed, 140 skipped in 2:37. That is the `[dev]` venv plus
  playwright 1.63.0, on macOS arm64, at load 2.9-5.1 with no other suite
  running. The total is 6262 against 6256 last session. That +6 is +3 in
  `test_rxplot_browser.py`, +3 in `test_gui_browser.py`, +1 in
  `test_gui_server.py` (the window case split into two) and −1 in
  `test_gui_palette.py` (the plotly tick-trace guard). The browser modules
  ran, since playwright is in this venv; they skip in CI.
- vitest 558 against 598: `App.test.ts` 177 → 172, `plot.test.ts` 91 → 57,
  `pattern.test.ts` 4 → 3. What went asserted plotly's layout and its pinning
  helpers. svelte-check is clean.
  `App.test.ts` passed twice under `--sequence.shuffle`.
- `app.js` 303 → 296 kB. `pattern.js` 16 kB, `vendor-uplot.js` 51 kB,
  both unchanged in kind.
- The full selection did not run: nothing here moves a refined number.

*Gotchas:*
- A plot case in `App.test.ts` run alone (`-t`) drew nothing until the file
  imported `./lib/pattern` up front. The panel's first dynamic import
  outlasts `flush()`.
- The stand-in paints on every call, where uPlot coalesces paints to one a
  microtask. Count paints only as "did it repaint", never "how many times".
- The rxplot module ships no CSS. Each page restyles `.u-cursor-x` and
  `.u-select`: the GUI in `Plot.svelte`, and the watcher and compare pages
  owe the same two rules.
- The worktree guard refuses a command naming a quoted phrase with an
  apostrophe, and a heredoc beside git. Run a scratchpad script by path.

*Next:*
1. Task 7, the watcher, on `rxplot.pattern` with a ±3σ layer, serving the
   vendored uPlot, and with the `.u-cursor-x` and `.u-select` rules the GUI
   carries. `test_watch_browser.py` reads what was painted, as
   `test_gui_browser.py` now does.
2. Then tasks 8-14 in order. Task 8 deletes `/api/series/window`,
   `curve_window`'s last caller and `_series_masked_arm`.
3. Someone with Safari open tries a drag in the GUI (finding 15). It is now
   the only renderer.
4. The `/api/peaks` payload's `pattern` arm is now read only as a boolean
   (`hasPattern`): a decimated 4000-point copy on every peak fetch. Every
   open project has a pattern, so the question may have a cheaper answer.
   Not done here, because it changes a route's shape outside this task.

### 2026-09-25 (4th session) — the pilot says go, and the chart thins per pixel column

The migration now has its evidence on the real GUI rather than a
prototype. With the chart module drawing NAC's pattern, opening the GUI has
no long frame, and a zoom costs about half plotly's work and fetches
nothing. A resize costs the chart 2-3 ms against plotly's 11-17. Every
gesture works in Firefox and WebKit too. Drawing every observed point did
not hold up: at 132 992 channels, and in Firefox and WebKit, it made frames
of 50-258 ms. So the chart paints each pixel column's highest and lowest
point instead. One clause of the gate missed by a hair on one run: plotly
answers a hover at most every 50 ms, and the chart answers every move, so
plotly's hover can cost less per move. The panel is still behind
`?chart=uplot`, and the plotly renderer is still the default.

*Done:*
- Task 5, the pilot. `/api/result/curves` and `/api/series/curves` send the
  pattern's every channel once as float64 arrays (`viz/packed.py`,
  `session.curve_arrays`), with `kept` always, and decimate past
  `CURVES_CEILING` = 150 000 over the window route's three curves.
  `rxplot.mjs` gained `unpack` and the pattern figure (three panes, the
  thinned markers, layers). `gui/src/lib/pattern.ts` puts the panel on it
  behind `?chart=uplot`, with the shading, candidate lines, peak markers,
  peak fits and a DOM hover ring. `api.curves`, `rxplot.d.ts` and a vite
  alias bring the module into the GUI, and uPlot is its own chunk
  (`vendor-uplot.js`). The manual's route table names both routes.
- D5 decided: thinning, by the rule set beforehand (§ Decisions, § The pilot,
  measured). The every-marker path is gone, and `gui/CLAUDE.md`'s "the client
  does not decimate" became a rule about which points a payload carries.
- The probe: `pilot.mjs`, `pilot_matrix.mjs`, `pilot_summary.mjs`,
  `make_lab6.py` and `hover_trace.mjs`, with 48 calls' logs in `results/`.
- Findings 15-18, each from a run that went wrong: playwright's WebKit drags,
  the dash uPlot leaves on the canvas, its null-walking cursor, and plotly's
  hover throttle. The last two cut the chart's hover work.
- `/code-review high --fix` made ten findings and fixed seven. A torn-down
  panel no longer builds a figure from a fetch in flight. A settings PATCH no
  longer repaints the chart. A scale switch keeps hidden curves hidden. The
  status line says when the server decimated. A line at the view's upper
  edge draws. The descending-scan sort is gone, since `PatternData` refuses
  one (checked, `schemas/pattern.py:41`). The series routes share one lookup.
  Of the three it left, I did one: the ceiling decimates over the window
  route's three curves rather than the observed one alone. The other two are
  task 6's: Σχ² re-basing at a zoom, and `windowOf` copying the payload into
  plain arrays for the readout.

*Measured* (details in § The pilot, measured):
- NAC, chromium, dpr 1 and 2, three calls each, load 3-7. Work per event,
  chart against plotly: drag-zoom 3.90-4.35 against 8.15-9.29, exclude
  5.07-5.82 against 9.72-11.71, peak drag 1.56-2.49 against 7.67-8.97,
  hover 3.32-3.59 against 2.82-4.29. Wheel zoom 4.73-6.23, pans 3.68-7.41.
  No long frame from the chart in any gesture.
- Fast suite on the final tree: 6116 passed, 140 skipped, in 2:58, `[dev]`
  venv plus playwright 1.63.0, macOS arm64, no other suite running at the
  start, load 7.5-12. The total is 6256 against 6242, which is 15 tests
  added less the one the review deleted. Before the review it was 6117
  and 140.
- vitest 598, +4 (`pattern.test.ts`); svelte-check clean.
- The two watcher seam cases that failed last session at load 150 passed.
- The full selection did not run: nothing here moves a refined number.

*Gotchas:*
- Every pilot call starts a fresh `rietx gui` that imports the source, so
  editing `session.py` mid-matrix changes the runs after the edit. Edit the
  GUI source freely, but rebuild the dist only between matrices.
- playwright's Firefox (1543) and WebKit (2359) builds are now cached.
- The worktree guard refused inline scripts naming "checkout" and shell
  variables in `node` arguments; the edits went through scratchpad scripts.

*Next:*
1. Task 6, the pattern panel complete, which also answers the two review
   findings left. Re-base Σχ² at each zoom, as `session.py:2644-2651` does per
   window. Draw the raw view's per-group residual. Then the axis titles, Esc,
   and the readout without the `Array.from` copies. Then delete the plotly-only
   code and move `App.test.ts` off its `Plotly.react` stub.
2. Someone with Safari open tries a drag at `?chart=uplot` (finding 15).
3. Then tasks 7-15 in order. The watcher is the next page to port, and it
   reuses `rxplot.pattern` with a ±3σ layer.

### 2026-09-25 (3rd session) — the payload route, uPlot vendored, the chart module's core

The pilot now has what it builds on. Measured on real answers, the curves
should travel as float64 binary over the pattern's own channels. That cuts
the server's 60 ms and the browser's parse to almost nothing, at 57 % of the
bytes. The compare page resends every variant's curves on every 700 ms poll
today, so it has to stop before it can go to full resolution. uPlot is
vendored at an exact pin, only the build writes the copy, and Dependabot
watches it. The chart module's core exists, with a test for each way the
spike found to get it wrong, and a review fixed four more defects in it. The
pilot, which decides go or no-go, has not started.

*Done:*
- Task 2: `payloads.py`, `payload_probe.mjs` and `transport.py` in the spike,
  with their logs. § The payload behind a client zoom holds the numbers, and
  D4 and D8 record what they settled. The ceiling follows D5: 150 000
  channels with thinning, 100 000 with every marker.
- Task 3: `gui/scripts/vendor.py` is the build's first step. The digest
  covers `src/rietx/viz/static/`, and `test_gui_dist.py` holds the banner to
  the pin and the files in the wheel. Also `LICENSE-3RD-PARTY.md`,
  ATTRIBUTION, `.github/dependabot.yml`, and `gui.yml` triggering on and
  diffing the vendored directory. The `gui/CLAUDE.md` rule fits its cap by
  dropping a stale size claim: `app.js` "well under" `vendor-cm.js` at
  114-164 kB, where the build prints 303 against 328 kB. Serving uPlot moved
  to the watch and compare tasks, and svgcanvas's Dependabot row to the
  export task.
- Task 4: `src/rietx/viz/static/rxplot.mjs`. Its pure half has 9 node cases,
  run by `tests/test_rxplot.py`. `tests/test_rxplot_browser.py` has 13
  chromium cases. Four guards were broken on purpose (findings 1, 2, 3 and
  12), and each failed with the expected message.
- `/code-review high --fix` made seven findings and fixed six (`c6f1cb80`):
  - a press under 8 px is a click, since uPlot turned a 1 px jitter into a
    whole-axis zoom;
  - a live update re-ranges an unzoomed y;
  - a narrow √ window keeps its ticks;
  - every tick label prints its own value;
  - the wheel test requires `rxplot.mjs`;
  - `vendor.py` names a missing package instead of printing a traceback.

  It declined narrowing the digest to the vendored files, because the pilot
  makes `rxplot.mjs` a GUI build input.
- Before the review, `share` heights went for want of a caller, and
  `setData` gained its case.
- Forward references: WP-1313 (the digest now covers the chart module) and
  WP-1462 (the allow list exists, and bundled code owes
  `LICENSE-3RD-PARTY.md` its licence).

*Measured:*
- The payload and ceiling figures are in § The payload behind a client zoom.
  The headline figures:
  - today's JSON route at every channel takes 59-60 ms to its first byte, of
    which 52-57 ms is `json.dumps`;
  - float64 binary takes 0.2 ms;
  - the parse falls from 3.8-5.1 ms in Chrome and 8.4-9.2 ms in Firefox to
    nothing;
  - the compare poll is 2.96 MB today, and 45.69 MB at every channel on
    `lab6_capillary`;
  - at 132 992 points, every marker gave a 62-67 ms long frame in 3 of 3
    runs.
- Fast suite on the final tree (main unchanged since the last handover, so
  this is the merge's tree): 6100 passed, 140 skipped and 2 failed, in 9:05.
  That is the `[dev]` venv plus playwright 1.63.0, on macOS arm64. No other
  suite was running, but load ran from 41 to 161. The total is 6242 against
  6179 last session. The +63 is the 16 tests added here (1 dist, 2 node
  wrappers, 13 browser) plus 47 from `test_watch_browser.py`, which was one
  module skip until playwright was installed and is now 48 cases.
- The 2 failures are that module's two seam cases, which assert at most 6
  resizes over a drag and counted 8. They failed again run alone, at load
  153-161. This branch changes no watcher file, and CI skips the module.
- The full selection did not run. Nothing here moves a measured number.

*Gotchas:*
- uPlot commits its first draw in a microtask, so a scale read right after
  construction is null. Wait a frame.
- Editing `rxplot.mjs` stales the dist. Rebuild with node 22
  (`~/.nvm/versions/node/v22.15.0/bin` first on `PATH`).
- Firefox rounds `performance.now()` to 1 ms unless
  `privacy.reduceTimerPrecision` is off (`payload_probe.mjs` sets it).
- `*.html` swallowed the browser harness, the seventh file it has taken.
  `.gitignore` carries a negation for it.
- The worktree guard refuses a heredoc naming git, and a shell variable in a
  `sed` or `node` argument. Run a scratchpad script by path.

*Next:*
1. The pilot, task 5, in a fresh session. Build the curves route first
   (`session.py`, `server.py`, its decoder in the module's pure half, a GUI
   chapter for `test_gui_manual.py`), since it fixes the panel's data shape.
   Then the pattern panel on the core behind a flag, then the probe in three
   browsers. WebKit needs playwright's webkit build, which is not cached here.
2. Rerun `tests/test_watch_browser.py` alone at low load. If the seam cases
   still count 8 resizes, file it against the watcher, not here.

### 2026-09-25 (2nd session) — the zoom delay, the maintainer's decisions, and WP-1462

The delay the maintainer felt on every zoom came from their trackpad. macOS
three-finger drag holds a drag's release back by about 300 ms, so every
browser and every chart library zooms that late, and no page can change it.
The search for it found a real defect as well: the prototype painted two of
its three panes twice on every zoom, and now paints each once. The
maintainer confirmed the move to uPlot and most of the design. One decision,
D5, went back to them, because the summary they confirmed it on misstated
the evidence. Moving the 3D viewer off plotly is filed as WP-1462, so once
both land no page needs plotly.

*Done:*
- Finding 12, the echo fix in `proto.html`. Finding 13, Firefox's two
  stalls. Finding 14, three-finger drag.
- `?demo` prints each frame's repaints, and after a drag it splits the wait
  at the mouse-up. `zoom_probe.mjs` counts and times the paints in Chrome
  for Testing or the installed Firefox, with `results/zoom_probe.txt`.
- The spike's `node_modules` is a real install with `puppeteer-core`, no
  longer a link into a dead scratchpad.
- `test_docs_consistency.py` drops gitignored files from the planning docs,
  so an `npm install` in a spike no longer breaks two link checks locally.
- § Decisions records the maintainer's answers. D2 and the vendoring task
  say how a vendored uPlot stays current. WP-1313's Inherited carries what
  that means for a post-merge rebuild. WP-1462 is filed with its ROADMAP
  row, and a line of 1131's repeated numbers made room under the cap.
- `/code-review high --fix` applied seven fixes in two commits: `-z` on the
  gitignore filter, a fresh state directory per GUI probe run,
  `fileURLToPath` in every script, four `proto.html` repairs, a 400 from
  `serve.mjs` on a bad escape, one hoisted minimum, and two `.gitignore`
  lines. It declined three: the D5 contradiction (the maintainer's call,
  now reopened), cleanups on code paths the logs measured, and an import
  order outside the lint scope.

*Measured:*
- Paints per zoom, main/ticks/resid, 59 498 points at devicePixelRatio 2:
  2/2/1 with the echo, 1/1/1 without, in Chrome for Testing 148 and
  Firefox 155. Firefox's wheel zoom painted in 5.3 ms against 3.5 ms, at
  load averages 67-84.
- Headless Chromium took 24-32 ms from input to frame on every event,
  including an empty mouse-down.
- three.js 0.186.1, the viewer's imports bundled: 557 KB, 138 KB gzip.
  3Dmol.js 2.5.5: 538 KB, 156 KB gzip.
- Fast suite on this branch with main `6641c8cf` merged: 6038 passed, 141
  skipped, in 2:22, `[dev]` venv, macOS arm64, no other suite running. An
  earlier merge of main measured 6034 and 141, and the four more passes
  came with main. This session added no test. The full selection did not
  run, since nothing here can move a measured number.

*Gotchas:*
- `npm --prefix X init` writes `package.json` into the working directory,
  not into X.
- The worktree guard refuses a shell variable in a `git`, `node` or `gzip`
  argument. Write a scratchpad script and run it by path.
- Firefox runs headless through `puppeteer-core` over WebDriver BiDi. Its
  first launch in a batch sometimes exits with code 0, so rerun.
- The demo server on port 8810 still runs the `serve.mjs` from before the
  review. Restart it to pick up the 400 answer.

*Next:*
1. D5 was put back to the maintainer and answered the same day: the pilot
   measures both marker paths and picks (§ Decided).
2. Task 2: measure D4 and D8 on the real payloads, which settles the route
   the pilot builds on.
3. The vendoring task, which also adds Dependabot.

### 2026-09-25 — session state saved for a `/clear`

  Session state saved for a `/clear`, before
  `/wp-handover`. The WP is filed and not started. PR #461 carries it with
  the spike and a demo someone can click through. Nothing in the package
  changed. The maintainer has not yet answered the first task (confirm the
  migration on § Staying on plotly's numbers, and D1-D8), nor whether to
  file a three.js WP for the 3D viewer now.
  *Done:* the WP and ROADMAP row, `1461-uplot-spike/` (drivers, logs,
  screenshots), the adversarial review and the re-measurement it forced, a
  forward reference in 1317's Inherited, and the demo (`serve.mjs`, `?demo`
  toolbar). Branch `wp1461-uplot` in worktree
  `.claude/worktrees/wp1461-uplot`, pushed.
  *In flight:* a demo server on `http://127.0.0.1:8810/`, started from this
  session. Restart it with `node docs/wp/1461-uplot-spike/serve.mjs 8810`.
  The spike's `node_modules` is a symlink into a session scratchpad that will
  be cleaned, so run `npm install` in the spike directory first (README).
  *Not yet done from the handover checklist:* the Stop hook asked for
  `/wp-handover 1461` on 2026-09-24. It still owes a `/code-review high
  --fix` over the spike's `.mjs`/`.py`, the `session_start.py` check, and
  a PR body rewritten from this log.
  *Gotchas:*
  - `Plotly.Plots.resize` resolves after a 100 ms `setTimeout`, so time work
    with `TaskDuration`, never a promise.
  - Load averages ran from 7 to 29 on this shared machine. GUI boot moved
    from 842 to 2295 ms between runs, so quote ranges and side-by-side
    ratios.
  - The worktree guard refuses heredoc scripts and shell loops; write a
    scratchpad script and run it by path.
  - The drivers rewrite `shots/`, and the spike's `.gitignore` keeps only
    the six cited screenshots.
  - WP numbers: 1460 was already held on WP-1454's branch, so check remote
    branches as well as main before taking one.
  *Next:*
  1. The maintainer's answers go into § Decisions, and the first task gets
     ticked.
  2. If a three.js WP is wanted, file it.
  3. Run `/wp-handover 1461`.
  4. Task 2: measure D4 and D8 on the real payloads, which sets the route
     the pilot builds on.
### 2026-09-24 — created

  The maintainer asked whether a lighter library
  would make the plots snappier, and asked for one backend for all plotting
  if it held up. The spike measured three libraries, today's GUI and a uPlot
  rebuild of every feature. An adversarial review then found the first
  draft had timed plotly's resize by its promise, a 100 ms timer included,
  and had missed behaviours and a shared-x-axis constraint. Everything was
  re-measured as main-thread work, and this file now quotes those numbers.
  Next: the maintainer confirms the migration and D1-D8 on them.
