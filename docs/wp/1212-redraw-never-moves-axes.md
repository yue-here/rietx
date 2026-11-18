# WP-1212 — A redraw never moves the axes

Milestone: v1.2 · Status: ✅ 2026-08-27
Depends on: WP-1210

## Goal

Nothing but a zoom or a double-click changes the plot's axes: not a hover in
the peak table, not an excluded region, not a peak edit. The armed exclude
drag shows two edge lines and a wash while it is dragged.

## Context

The user: "the plot jitters when mousing over in the peaks panel"; "Plot
jitters sometimes when exclude selected. Eliminate all jitters"; "the cursor
changes to the plotly select region cursor (rectangle; desired behaviour is
two vertical lines and shading showing the selected region)".

Findings (2026-08-25), mechanisms identified in code and **not yet measured**:

- **Hover.** The table's `mouseenter` sets `hovered` (`Peaks.svelte:567-569`
  → `App.svelte:818, 768`); `drawRing` (`Plot.svelte:453-461`) restyles the
  `hovered` trace's arrays. That trace is a full `scattergl` trace on the
  data axes with `marker.size: 16` (`Plot.svelte:441-445`). `heldRanges`
  (`lib/plot.ts:195-207`) keeps an axis only when `autorange === false`, so
  on a plot the user has not zoomed every `restyle` lets plotly re-autorange,
  and scatter autorange padding depends on marker size. That is the
  candidate mechanism for the hover jitter.
- **Exclude.** One drag runs: `arm = null` → the knob effect
  (`Plot.svelte:753-767`, `void arm`) → **react #1**; `clearSelection()` →
  `relayout({selections: []})`; the `project` reassignment → `protocolKey`
  → the fetch effect → **react #2**; `await loadPeaks()` → `peaks` → the
  fetch effect → **react #3**. Each react on an unzoomed plot re-autoranges
  over a trace set that now differs (`masked` arm, `maskShapes`).
- **The armed drag.** `dragmode: arm ? "select" : "zoom"`, `selectdirection:
  "h"` (`Plot.svelte:182-183`); nothing sets `layout.newselection` or
  `activeselection`; the two dotted edge lines and the wash come from
  `maskShapes` (`lib/plot.ts:131-150`) only after the POST lands. The cursor
  rule (`col-resize` on `.nsewdrag`, `Plot.svelte:946-956`) is WP-1044's.
- Plotly call sites in `Plot.svelte`: `react` (`:330`), `restyle` (`:460`),
  `relayout` (`:583`), `Plots.resize` (`:666`), `purge` (`:742`); no
  `addTraces`/`deleteTraces`.
- WP-1044's rule ("a redraw is not a reason to move the axes") pins the view
  only after the user zoomed; the shapes are clipped to `extent` because a
  shape on a data axis takes part in the autorange (WP-1033).

Method (from `gui/CLAUDE.md`): **measure first**, in Chrome via
playwright-core; when a claim is about an event, count the events; read
ranges off `_fullLayout` before and after each gesture. Suspect the harness
first when a result is impossible.

Design: after the first paint of a payload the axes are **explicit**
(`range` set, `autorange: false`), so every later `react`/`restyle` holds
them; a payload change (new result, checkout) and a double-click re-autorange
once; the exclude chain coalesces to one paint (arm cleared and the protocol
change land in the same tick; the peaks reload repaints without a fetch of
the window). The ring trace moves off the data axes (an overlaying pair with
`fixedrange`, matched to the data axes) or becomes a `layout.shapes` entry
with `xref: "x"` clipped to the extent, whichever the measurement shows
holds the range. The live selection is styled through `layout.newselection`
(line) and `activeselection` (fill) to match `maskShapes`; if plotly 3.7's
selection styling cannot draw two edge lines, a `plotly_selecting`-driven
shape pair is the fallback, measured for its own jitter.

## Non-goals

- The hover readout (WP-1213).
- Any change to what a region *does* (WP-1033's protocol strip).

## Tasks

- [x] The measurement: a table of (gesture → react count, x/y range before
      and after) for hover, exclude drag, peak move, on the NAC example;
      recorded in this file's log.
- [ ] Explicit ranges after first paint; the double-click and payload-change
      re-autorange; `heldRanges` retargeted; `plot.test.ts` on the pure
      parts.
- [x] The exclude chain coalesced to one paint; the ring off the autorange
      path; re-measure. (The ring stays where it is: the pin holds the range
      against its restyle, which is what task 2 measured.)
- [ ] `newselection`/`activeselection` styling matching `maskShapes`;
      cursor kept; re-measure.
- [x] `gui/CLAUDE.md`: the rule replaces WP-1044's weaker form (one clause
      plus the measurement pointer); dist.

## Acceptance

The before/after table in the handover log shows zero range change on hover
and on an exclude drag, and one react per exclude drag.

```sh
npm --prefix gui test && npm --prefix gui run check
```

## References

- WP-1044 (the view handed back), WP-1033 (shapes and autorange), WP-1032
  (a hover link costs a restyle).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**A redraw never moves the axes** (WP-1212, `panels/Plot.svelte`,
`App.svelte:setProtocol`). Its plotly repairs went with plotly in WP-1461: the
axis pinning, reading `ax._rl`, `movedAxes`, the hover ring kept out of the
WebGL scene, and the `.select-outline` override. Three rules outlived them.
**Arming is the figure's mode** (`setMode`) and repaints nothing; under plotly
`dragmode` was a layout key, and routing it through the repaint cost two of the
four reacts an exclude drag took. **A `$derived` off `project` is a new object
on every settings PATCH**, so an effect keyed on `extent` repaints for two
numbers that did not change — key it by value, beside `protocolKey`. **Two
`$state` assignments either side of an `await` are two flushes**, which is why
`setProtocol` reads the peak list before publishing either (`readPeaks`); one
exclude drag is one fetch and moves no axis.

## Handover log

### 2026-08-27 — closed: what jitters is what nobody zoomed

The plot holds still now. Hovering the peaks table, changing tab, arming the
range gesture and making an exclusion each move no axis at all, and an exclusion
costs one paint rather than four. The cause was one sentence in WP-1044 that had
looked complete: `heldRanges` kept an axis only once `autorange === false`, and
plotly writes that flag on a zoom and nowhere else — so on the plot a person had
*not* zoomed there was nothing to keep, every redraw re-fitted the axes, and the
same gesture on a zoomed plot was clean. That is why the report kept coming back
against a repair that measured correct.

The repair makes the axes explicit as the last act of each paint, which takes the
question away from plotly rather than answering it faster; the two things
`autorange` used to mean are now two functions, `movedAxes` (which axis a person
moved) and `userRanges` (what survives a re-fit a new payload licenses). Two
defects came out of the same gesture and are fixed with it: a select drag threw
inside plotly once per pointer move, and the live selection looked like a
spreadsheet marquee rather than the exclusion it was about to make.

**Before and after, measured.**

Chrome for Testing 1223 driven by playwright-core, plotly 3.7.0 from
`/plotly.js`, the NAC example fitted in the page (Rwp 0.0932), viewport
1500x950, Peaks tab up unless the row says otherwise. Every plotly entry point
wrapped by an init script before the library loads; the "before" reacts were
attributed to the effect that caused them by a temporary tag through `paint`
(`scratchpad/instrument.py`, reverted after the run). Every axis figure is on the
**unzoomed** plot — the case that was broken.

| gesture | react before | react after | axes before | axes after |
|---|---|---|---|---|
| boot → first paint | 3 | 3 | — | — |
| hover a peaks row | 0 (1-2 restyle) | 0 | **yaxis moves** | still |
| pointer off the table | 0 (1 restyle) | 0 | **moves back** | still |
| hover a row, zoomed | 0 | 0 | still | still |
| tab Peaks ⇄ Report | 1 | 0-1 | **yaxis, yaxis2** | still |
| peak move, zoomed | 1 | 1 | still | still |
| arm exclude | 1 | **0** (1 relayout) | **yaxis, yaxis2** | still |
| **exclude drag** | **4** | **1** | **yaxis, yaxis2** | still |
| exclude drag, zoomed | 4 | 1 | yaxis2 | still |
| box-zoom drag | 1 | 1 | the drag's | the drag's |
| double-click | 1 | 1 | resets | resets |

The word "jitter", as a number: a hover moved `yaxis` from −18597.7-283838.2 to
−21714.8-284045.7 — the bottom by 3117 counts, 1.03 % of the span — because the
ring is a trace with `marker.size: 16` and scatter autorange pads by marker size.
It moved back when the pointer left the table, so running down the rows pumped
the axis once per row. `xaxis` never moved in any gesture measured: the ring's x
sits inside the pattern's own extent, so its padding is swallowed.

The exclude drag's four reacts, named, and what each became:

1. `arm` → null — the drag mode is one layout key, so it is a `relayout` now, and
   it was **two** of the four (set on the way in, cleared on the way out)
2. a repaint with no knob changed — `extent` is `$derived` off `project`, so
   `patchProject` handed the effect a new array holding the same two numbers;
   keyed by value now, beside `protocolKey`
3. `protocolKey` → the window refetch, which is real: the masked points are an
   arm of the payload
4. `peaks` → `setProtocol`'s `await loadPeaks()`, a second flush after the third;
   `readPeaks` reads without publishing so both land in one flush

**The defect this WP introduced, and how it was caught.**

Pinning is only as good as the number it reads, and the first version read
`_fullLayout.xaxis.range`. On the **raw view** — the state a project is in before
any fit, which is where peaks are picked and cells are indexed — that field was
still plotly's empty-axis default `[-1, 6]` while the axis was drawing 0-60°:
the tick labels, `_length`/`_offset` and `p2d(0)`/`p2d(_length)` all said
−3.07-63.56 and only `range` did not. Pinned, that default became permanent and
the pattern went off-scale — a blank plot. The fitted view escaped because the
run that follows re-fits the axes anyway, which is why three measurement passes
missed it: they all ran a fit first.

Found by looking at a screenshot of a state the table did not cover, and settled
by checking the same state on `main`'s dist, where the picture is correct and
`range` reads `[-1, 6]` just the same. So the field to read is `ax._rl`, the
resolved pair plotly builds its pixel map from (`drawnRange`), and `range` is the
one that can be stale. Both are in log units on a log axis, so the substitution
is safe there too.

**Two findings the WP did not go looking for.**

- **A select drag threw once per pointer move, inside plotly.** `TypeError:
  Cannot read properties of undefined (reading 'length')` at scattergl's
  `selectPoints` ← `moveFn`, 7 times over three exclude drags. Every gl trace on
  a subplot shares one `_scene` whose batches are indexed by position, and an
  *empty* gl trace is given no index at all — so `selectBatch[undefined].length`
  threw, and only after the first hover, because the ring is empty until
  something is hovered. The hover ring is a plain `scatter` now: one marker in
  SVG costs nothing and leaves the scene alone. Measured 0 throws over three
  drags, in both themes.
- **The live selection is now the exclusion it is about to make.**
  `newselection.line` takes `maskShapes`' edge ink from the same `curveColors`
  call, and `selectdirection: "h"` had already made the box full height, so its
  two long sides are the dotted edges the exclusion leaves. The wash needed a
  stylesheet rule with `!important`: plotly writes `fill: rgb(0,0,0);
  fill-opacity: 0` **inline** on `.select-outline`, and nothing else outranks
  that. Computed `rgba(27,27,27,0.08)` light and `rgba(230,230,226,0.08)` dark,
  matching the shapes beside it; screenshots of both in the pass.

**The two inherited questions, answered.**

- **The candidate chain** (WP-1211's). Twelve candidates on the NAC example after
  a 121 s `quick` index; running the pointer down six rows costs **11 reacts at
  19-33 ms** — about two per row, since leaving a row draws as well as entering
  one — and **moves no axis**. Selecting one costs 1 react. So 1211's worry was
  the right one and it is a cost question, not a correctness one; a hover could
  be a `restyle` of the one overlay trace the way WP-1032 made the ring one, and
  that is left to whoever wants the 25 ms.
- **The empty residual subplot** (WP-1210's, inherited through 1211). Decided:
  **not here**. Measured what it would take — the shared x axis is anchored to
  `y2` so the ticks and title sit under the residual, and the tick band's domain
  is the gap between the two panels, so collapsing means moving three domains and
  an anchor together, which is a layout redesign rather than a domain switch. Two
  facts for whoever takes it: with nothing drawn on it plotly **drops** `yaxis2`
  from `_fullLayout` entirely and restores it with exactly its previous range
  (−81.76-61.68 → absent → −81.76-61.68 over a `data only` press and back), so
  the axis never *moves*; and `yaxis.domain` stays `[0.28, 1]` throughout, which
  is the empty quarter, unchanged by this WP and not made worse by it.

**The review pass, and what it was right about.** `/code-review medium --fix`
raised four findings against this WP's own new code and fixed all four; two are
real, one is a guard, and one could not be reproduced — recorded that way rather
than folded together, because a comment claiming a measured defect that does not
reproduce is the same failure this WP spent its afternoon on.

- **Real.** `userSet` remembered a drag on an axis whose *meaning* then changed:
  a range dragged on Δ/σ would have survived into the next re-fit as a range on
  Σχ², which runs to hundreds of thousands. `heldRanges`' `live` gate covers the
  paint the knob causes and not the re-fit after it. The clear is now a pure
  function, `forget`, for a reason worth stating: the fix's first form was
  inline in `paint`, and the App-level test written for it **passed with and
  without the fix**, because `live` hides the difference within one paint. A
  test that cannot fail is worse than none, so the rule moved to where it can be
  asserted exactly.
- **Real.** On the raw view the relayout handler returns at `if (!result)`
  before anything can re-pin, so a double-click left every axis autoranging and
  the next hover moved `yaxis` again — this WP's own bug, surviving on the one
  view that has no window fetch to land back in. A reset there now queues the
  pin. Verified: after a zoom and a double-click the ranges come back explicit,
  and a hover moves nothing.
- **A guard, not a repair.** `pinPatch` now skips an axis with nothing drawn on
  it. The finding said hiding the residual and running a fit would pin `yaxis2`
  to plotly's default and clip the curve when it returned; in Chrome that does
  not happen, because plotly **drops** an unused axis from `_fullLayout`
  entirely (measured: −81.76-61.68 → absent → −81.76-61.68 across a `data only`
  press, a fit while hidden, and the press back). What made it look like a
  defect is this session's own jsdom stub, which synthesises every axis
  unconditionally. Kept anyway: "pin what plotly fitted" should not rest on
  plotly choosing to drop what it could not fit.
- **Unreproduced.** Arming after a checkout aims a `relayout` at a div the fetch
  effect purged — before this WP arming went through the repaint effect, which
  no-oped on `held === null`. A browser pass could not get a checkout to reach
  the purge branch at all (the result survived it), so what plotly does there is
  unproven and `plotted` is a guard on the state rather than a repair of a seen
  throw. Left in, and the comment says so.

**Counts.**

`npm --prefix gui test` **510 passed / 21 files**, from 487 on `main`: 23 new —
16 in `plot.test.ts` over the five new pure functions, 7 in `App.test.ts`'s new
WP-1212 block — with 3 existing ones retargeted rather than added, because the
facts they pinned changed (arming is a relayout, an explicit range no longer
says who set it), and one written for the review's fourth finding **deleted**
for passing either way. `npm --prefix gui run check` 0 errors / 0 warnings over 378
files. Fast python selection **3157 passed / 117 skipped**, exactly 1211's: this
WP moved no python behaviour, and the three suites that could have —
`test_docs_consistency.py`, `test_gui_dist.py`, `test_gui_palette.py` — are
inside that count. `gui/CLAUDE.md`'s cap moved 808 → 838 with its reason beside
it; `ruff` clean. darwin/arm64, `[dev]` (no jax/torch; numba present).

The full selection **did not run**, and the reason is worth stating rather than
leaving to inference: this WP moved no python, the three suites that could have
noticed it are inside the fast selection, and another session's full run was in
flight from 21:24 for the whole of this handover — so a second one would have
been two suites competing for the same cores and the same ports. That
concurrency is also why no wall clock is quoted here: the fast selection above
ran beside it, and a passed/skipped count is load-independent where a duration
is not (`tests/CLAUDE.md` § Quoting numbers).

**Next.**

WP-1213, the hover readout — the `hkl` and `line` arms `GET /api/index/ticks`
already serves and 1211 deliberately did not draw. It inherits the two items
above and the plot's `!important` rule, which is the first stylesheet rule in
this panel that reaches into plotly's own nodes for anything but a cursor.

### 2026-08-27 — the measurement: what jitters is what plotly is still autoranging

The findings above were mechanisms read off the code; this is what the browser
says. Chrome for Testing 1223 driven by playwright-core, plotly 3.7.0 from
`/plotly.js`, the NAC example fitted in the page (Rwp 0.0932), viewport
1500x950, Peaks tab up unless the row says otherwise. Every plotly entry point
is wrapped by an init script before the library loads, and each `react` is
attributed to the effect that caused it by a temporary tag through `paint`
(`scratchpad/instrument.py`, reverted after the run).

| gesture | react | restyle | relayout | resize | xaxis | yaxis | yaxis2 |
|---|---|---|---|---|---|---|---|
| boot → first paint | 3 | — | — | 1 | — | — | — |
| hover a peaks row | **0** | 1-2 | — | — | held | **moves** | held |
| pointer off the table | **0** | 1 | — | — | held | **moves back** | held |
| box-zoom drag | 1 | 5 | — | — | the drag's | the drag's | re-autoranges |
| hover a row, zoomed | 0 | 1 | — | — | held | held | held |
| peak move, zoomed | 1 | 6 | — | — | held | held | held |
| double-click, Report tab | 1 | — | — | — | resets | resets | resets |
| tab Peaks ⇄ Report | 1 | 0-2 | — | 1 | held | **moves** | **moves** |
| arm exclude | 1 | 1 | — | 1 | held | **moves** | **moves** |
| **exclude drag** | **4** | 3-13 | 1 | 1-2 | held | **moves** | **moves** |

**The jitter is on the axes plotly is still autoranging, and on no others.**
WP-1044's `heldRanges` keeps an axis only when `autorange === false`, which is
exactly "the user has zoomed it" — so on the plot a user has *not* zoomed,
every redraw and every `restyle` re-autoranges, and the same gesture on a
zoomed plot is clean (`hover a row, zoomed`, `peak move, zoomed`: nothing
moves). That is why the repair looked complete and the report kept coming.

Sizes, so the word "jitter" carries a number: a hover moves `yaxis` from
−18597.7-283838.2 to −21714.8-284045.7 — the bottom by 3117 counts, 1.03 % of
the span — because the ring is a `scattergl` trace with `marker.size: 16` and
scatter autorange pads by marker size. It moves *back* when the pointer leaves
the table, so running down the rows pumps the axis once per row. `xaxis` never
moved in any gesture measured: the ring's x sits inside the pattern's own
extent, so its padding is swallowed. The hover costs **no** `react` — WP-1032's
`restyle` is doing its job, and the restyle is enough to re-autorange on its
own.

The exclude drag's four reacts, named:

1. `arm` → null (the knob effect: the drag mode is layout, so arming repaints)
2. a knob repaint with **no knob changed** — `extent` is `$derived` off
   `project`, so `project = await api.patchProject(...)` hands the effect a new
   array identity holding the same two numbers
3. `protocolKey` → the window refetch (real: the masked points are an arm of
   the payload)
4. `peaks` → `setProtocol`'s `await loadPeaks()`, a second flush after the
   third

Two findings this WP did not go looking for:

- **A select drag throws once per pointer move, inside plotly.** `TypeError:
  Cannot read properties of undefined (reading 'length')` at scattergl's
  `selectPoints` ← `moveFn`, 7 times over three exclude drags — and none on the
  first drag of a session, only after an exclusion exists. `selectPoints` reads
  `scene.selectBatch[trace.index].length`, and every scattergl trace on a
  subplot shares one `_scene` whose batches are indexed by position, so a trace
  that comes and goes mid-list (`masked` appears the moment a region is
  excluded) leaves the scene's batches short. The selection still lands; the
  console fills. Candidate repair: the trace list keeps its shape, empty rather
  than absent.
- **The candidate chain is not measured yet.** `POST /api/index` was still
  running when the pass's budget ran out and no candidate table was on screen,
  so 1211's inherited question (one react per row the pointer crosses) is
  re-asked after the repair, where the answer is what matters.

- **2026-08-25** — created from the v1.2 triage.
