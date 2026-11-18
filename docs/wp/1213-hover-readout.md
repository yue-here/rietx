# WP-1213 — The hover readout

Milestone: v1.2 · Status: ✅ 2026-08-27
Depends on: WP-1212

## Goal

The plot's hover information never covers the data: it is a readout strip
under the plot, with a spike line on the plot marking the 2θ.

## Context

The user: "The tooltip frequently covers a large part of the data. Consider
where to put it so it's visible and useful but not in the way."

Findings (2026-08-25): `hovermode: "x unified"` with a `hoverlabel` from the
theme tokens (`Plot.svelte:210-211`, `lib/plot.ts:63-72`); per-trace
`hovertemplate`s for observed, masked, calculated, background, ticks and
peaks (`Plot.svelte:273-436`); the `diff` and raw-residual traces have
neither template nor `hoverinfo`, so they add plotly's default line to the
box. There is no positioning: plotly offers none for the unified box beyond
`hoverlabel.align`, so "put it elsewhere" is not a setting.

Decision (the plan, 2026-08-25): a readout strip. `hovermode: "x"` with
`showspikes` on the x axis and `hoverinfo: "none"` on every trace; a
`plotly_hover` handler fills a strip of the plot's control rows with 2θ, d,
obs, calc, bkg, the chosen residual, the nearest tick per phase and the
nearest peak (with its index). The strip is under the plot, so it is a
control row under a canvas: the `ResizeObserver` rule (WP-1015/1029) holds.
`plotly_unhover` clears it. The series panel's plot is SVG and keeps its own
hover (WP-1016); this WP is `Plot.svelte` only.

### What the strip has to carry

Folded in from the four WPs that shipped under it (their `Inherited` notes,
consumed 2026-08-27):

- **Every number reads as its table reads it.** A position is
  `formatPosition(tt, esd)` (`lib/peaks.ts`: four places, esd in the last place
  below `POSITION_ESD_MAX_DEG` = 1°, nothing above) and an intensity is
  `formatIntensity(I, imax, flags)` over `imax = intensityScale(rows)` — the
  raw area is in counting units and means nothing on its own, so a readout
  printing `1.2e+3` beside a table saying `100.0` is two answers (WP-1209). For
  a value with an esd, `formatValue`/`formatEsd` write `35.09 ±110` where the
  esd has swallowed the value and `12346(56)` otherwise.
- **The strip names every curve**, which is a *requirement* carried from
  WP-1210 rather than a nicety: the picked-peak fit curve stopped being
  `hoverinfo: "skip"` and started naming itself in the unified box, because a
  reader had no way to tell it from the model. Deleting the templates for a
  strip means the strip says which curve is which.
- **The peak layer is drawn only on the Peaks tab**, so a readout that quotes a
  hovered peak has nothing to quote elsewhere: the strip's content is
  tab-dependent because the plot's is (WP-1210). A peak's state is said in the
  corpus's words (`peak_origins`/`peak_flags` labels, WP-1209), never in a
  third spelling or a colour key.
- **The candidate overlay's `hkl` and `line` are already served and
  deliberately not drawn** (WP-1211): `GET /api/index/ticks` returns
  `two_theta`, `hkl` and `line` as parallel arrays sorted by 2θ, so "the line
  under the pointer is (1 0 4)" needs no new wire surface. Under `hovermode: "x
  unified"` a candidate row would appear in the box at every pointer position,
  which is exactly why the overlay has no hover today and why a strip of its own
  is the right place. Two honesty rules ride with it: past
  `MAX_CANDIDATE_TICKS` the drawn set is thinned by rank, so a readout quotes no
  ordinal and no count (the status line owns both), and the overlay sits on
  `yaxis4` at y ∈ [0, 1] — this layer's `y` means nothing and only its `x` does.

### Constraints from the layer under it (WP-1212)

- **The axes are explicit after every paint** (`pinPatch`, `movedAxes`,
  `userRanges`), so a hover cannot move them however it is drawn, and
  `autorange === false` no longer answers "has the user zoomed". A pixel→2θ
  conversion reads `drawnRange(ax)`, not `ax.range`, which can be stale on a
  fresh plot.
- **The hover ring is a plain `scatter`, not `scattergl`**: every gl trace on a
  subplot shares one `_scene` whose batches are indexed by position, an *empty*
  gl trace is given no index, and a select drag then threw once per pointer
  move. Any new trace that is empty most of the time — a spike marker, a
  readout cursor — takes the same treatment.
- **A hover already costs a `react` where a candidate is concerned**: running
  the pointer down six candidate rows costs 11 reacts at 19-33 ms, while a
  peaks-table hover costs a single `restyle`. If the readout gives the overlay a
  hover of its own, the cheap shape is WP-1032's: one trace whose coordinates
  move.
- **The residual subplot's empty quarter is still owed.** 1212 decided against
  collapsing it (the shared x axis is anchored to `y2` and the tick band's
  domain is the gap between the panels, so collapsing moves three domains and an
  anchor together). This WP adds a strip under the plot, which is the next time
  that space is worth arguing about.
- **`.select-outline` is the panel's precedent for a stylesheet rule reaching
  into plotly's own nodes** for something other than a cursor, and it carries
  `!important` because plotly writes `fill-opacity: 0` inline. If the readout
  restyles any plotly-owned node, that is the precedent and the trap.

### A declined finding, inherited (WP-1209)

`INTENSITY_UNMEASURED_FLAGS` (`no_intensity`, `fit_failed`) is a TypeScript
literal held to the corpus vocabulary by name only. `gui/CLAUDE.md`'s rule is
that a flag's *meaning* is served, never re-derived — `unusable_flags` rides on
`/api/peaks` for that reason — so a python flag added later meaning "the area is
a bound, not a measurement" would be used as Imax and printed as a real relative
intensity, and the name-only test stays green. The fix is a
`PEAK_INTENSITY_UNMEASURED_FLAGS` constant in `schemas/indexing.py` served
beside `unusable_flags` and read by `formatIntensity`; 1209 declined it as a
wire-contract change outside a table WP, and it stays declined here for the same
reason — this WP quotes `formatIntensity`, it does not touch it.

Method (from `gui/CLAUDE.md`): **measure first**, in Chrome via
playwright-core; when a claim is about an event, count the events.

## Non-goals

- The peak-row hover link (the ring, WP-1212).
- The series plot.

## Tasks

- [x] `lib/plot.ts`: `readout(w, x, ticks, peaks) -> Readout` (pure; nearest
      index by binary search; tested).
- [x] The two facts the strip needs and no route serves it: the source's
      wavelengths (d = λ/2 sin θ, and which line a candidate tick belongs to)
      on `project_doc`'s data arm, and the served `hkl`/`line` carried through
      `CandidateOverlay` in `App.svelte`.
- [x] `Plot.svelte`: hover mode and spikes; the strip; every `hovertemplate`
      and `hoverlabel` deleted; the strip's height in the resize path.
- [x] Browser pass: hover across a peak cluster in both themes; no box over
      the data; dist.
- [x] `gui/CLAUDE.md`: the rule this WP leaves (one clause plus the
      measurement pointer).

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
grep -c "hovertemplate:\|hoverlabel:" gui/src/panels/Plot.svelte   # 0
```

The colons are the point: the panel still *names* `hoverlabel.align` twice, in
the comments saying why the box could not be moved and had to go instead. What
must not survive is a key, and a key is what the colon matches.

## References

- WP-1029 (the residual and scale knobs the strip reads).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**The hover readout** (WP-1213, `lib/plot.ts:readout`, `panels/Plot.svelte`).
The tooltip covered the data, and plotly offered no positioning for the unified
box beyond `hoverlabel.align` — so the box was **deleted rather than moved**,
and a strip of the plot's control rows says what the box said plus the three
things it could not — the candidate's `hkl`, which emission line that line is,
and d. **A new fact about a mark goes in the strip**: the chart takes neither
of the boxes uPlot offers (a legend, a point per series), and `App.test.ts`
holds every pane to that. Under plotly a label on one trace drew a second box
of plotly's own beside it (WP-1438).
So **one reflection has one spelling on all three browser surfaces** —
`peaks.ts:formatHkl` here, `watch-core.mjs:hklLabel` in the wheel — held equal
by `plot.test.ts`, since neither can import the other.
**The strip's shape follows the payload, the tab and the curve toggles — never
the pointer**: one row per *drawn* curve, so `data only` empties it to the
points, while everything that varies under one pointer sweep keeps its slot and
empties it, the resting state included, and the values are sized in `ch` so the
wrap points hold. A strip that grew a field on hover would resize the canvas
above it once per entry — WP-1212's jitter arriving through the repair for it
(measured on NAC: plot 776 px, strip 23 px, unchanged over ten positions).
**A masked channel is in no result, so the readout reads two arms** — nearest
over fitted ∪ excluded (WP-1033), and a masked one has no model to quote, which
is also how the strip says the pointer is inside a region without a field that
changes width to say it. **The pointer's 2θ is the cursor's pixel through the chart's
own x**, never a point some trace matched: the ticks ride on reflection
positions and the markers on peak positions; the line under the pointer is
`nearestPeak` at the **coarse** 10-px radius the non-destructive
verbs aim with (`PICK_RADIUS_PX`, WP-1027's fine `grabToleranceDeg` is the
*move* gesture's, because a drag edits), so the ring, the lit table row and the
strip name one peak rather than `hoverdistance` naming another. **A curve is
read at the nearest drawn channel and a nearby thing is hit-tested against the
pointer**, which are two positions on purpose: a channel is not the pointer, and under
plotly's decimated window it was up to ~0.03° away at a survey view — wider than
the tolerance — so the pointer sat on three picked lines in a row while the row
read `—`. **The pointer's line is chrome, so it is solid and takes `--fg`**: dotted in
`--muted` is `maskShapes`' excluded-region edge exactly, and the pointer drew a
line indistinguishable from a protocol boundary (uPlot's own is dashed
`#607d8b`, and `rxplot.panes` sets `.u-cursor-x` inline for every chart on every page, since a
page stylesheet that forgot the rule left `rietx compare` dashed) — a mark carrying no quantity
needs no `--plot-*` token (WP-1210), it needs the one ink no plot colour is
near. **Prose takes `−`, numbers take `-`**, which this app followed unwritten
until a typographic minus in the tick offsets sat beside `formatValue`'s
`toPrecision` output in one row; `formatHkl` shows where the line is, an index
standing in for an overbar rather than a measurement. And a curves payload is
**`$state.raw`** — a plain `$state` proxies it, so `held` and the payload a
draw was handed are two identities for one object (svelte says so in dev; it
was true before this WP surfaced it).

## Handover log

- **2026-08-27** — The plot's tooltip is gone. Everything it said now sits in a
  strip of labelled numbers under the plot, where it cannot cover the data, and
  the strip says three things the box could not: which reflection of a proposed
  cell sits under the pointer, which emission line that line belongs to, and
  the d-spacing. plotly offers no positioning for its unified box beyond
  `hoverlabel.align`, so "put it somewhere else" was never a setting — the box
  had to go, and what replaced it is DOM, which means a pointer move now costs
  no plotly call at all. The strip's shape follows the payload, the tab and the
  curve toggles rather than the pointer, so nothing about it moves while the
  pointer does; a solid spike marks the 2θ on the plot.

  **Done.** `lib/plot.ts:readout(w, x, inputs)` is the strip's whole content as
  formatted strings — the channel nearest the pointer, `d = λ/(2 sin θ)`, a row
  per drawn curve, the nearest tick per phase as a signed offset, the picked
  line as the peak table prints it (`formatPosition`/`formatIntensity`,
  WP-1209), and the candidate's `hkl` with its λ. `Plot.svelte` drops
  `hovermode: "x unified"` and every `hovertemplate`/`hoverlabel` for
  `hovermode: "x"` with `hoverinfo: "none"` on every trace, adds the strip and
  an `across` spike, and keeps one hover state (`hoverAt`). `project_doc`'s data
  arm grew `wavelengths` (the instrument's, primary first — *not* the peak
  document's, which is the λ the picker ran at) and `CandidateOverlay` carries
  the `hkl`/`line` the ticks route has served since WP-1211. `nearestIndex` and
  `PICK_RADIUS_PX` are single authorities the panel was spelling out in place;
  `formatHkl` writes `(1 0 −4)` where `join("")` wrote `10-4`, and the
  extinction table's refutation chips call it too.

  **Seven rules, in `gui/CLAUDE.md`** (cap 840 → 879, reason beside it). The
  four that are not derivable from the code: the strip must not reflow, so
  every field keeps its slot and is `ch`-sized; the spike is chrome and takes
  `--fg` solid, because dotted in `--muted` is `maskShapes`' excluded-region
  edge *exactly*; a curve is read at the nearest drawn channel while a nearby
  thing is hit-tested against the pointer, because the drawn pattern is
  decimated; and a window payload is `$state.raw`, since a plain `$state`
  proxies it and `held` and the `w` the fetch handed `paint` become two
  identities for one object.

  **Measured.** vitest 510 → **537 passed, 21 files** (node 26.3.1,
  darwin/arm64) — +27, all this WP's, no new skips. Fast python selection
  **3195 passed / 122 skipped in 334.9 s** (darwin/arm64, `[dev]`, no
  jax/torch); the WP adds exactly one python test, so the passed count moved
  3194 → 3195 **on this branch's tree**. It is not 1212's 3157/117 plus one:
  main moved under the branch — PR #115 (background peaks) merged between the
  two and brought `tests/test_background_peaks.py` plus additions to six more
  files — which is `tests/CLAUDE.md`'s rule that two parents' additions cannot
  simply be summed. The figure above is the merged tree's. Browser, Chrome for Testing 1223 at 1500 px on the NAC example:
  the plot stayed **776 px** and the strip **23 px** across ten hover positions
  on the fitted view, **704 px** across seven on the raw view and **669 px**
  with a candidate selected — nothing reflows. A hover costs no `react`
  (asserted in `App.test.ts`, and the plot is DOM-only from here). The peak row
  reads `#4 4.8965(16)° · I 0.2` with `peak fit 268.949` and `(y−fit)/σ
  1.23322` beside it, and the table row lights from a plot hover. The candidate
  row walked the cubic NAC sequence `(1 0 0) · λ 0.4139 Å`, `(1 1 0)`,
  `(1 1 1)`, `(2 0 0)`, `(2 1 0)`, `(2 1 1)`.

  **Three browser findings, none reachable by reading the code.** The spike
  drew a line indistinguishable from a fit-range edge. The tick offsets printed
  a typographic minus beside `formatValue`'s ASCII one, two spellings of the
  same sign in one row — the rule the app already followed unwritten is that
  prose takes `−` and numbers take `-`. And the peak row read `—` with the
  pointer sitting exactly on three picked lines in a row: the hit test was
  asked from the *snapped channel*, which on a decimated pattern is up to
  ~0.03° away — wider than the tolerance — and it was asking with the **move**
  gesture's fine radius, which WP-1027 made fine because a drag edits a line.
  Reading one does not, so it now uses the coarse 10 px the non-destructive
  verbs already aimed with.

  **Gotchas for whoever touches this next.** `hoverinfo: "none"` is load-bearing
  and is *not* `"skip"` — plotly's gate is `!== "skip"`, so `"none"` keeps the
  point-finding and the spike while drawing no label; the hover ring and the
  candidate overlay stay `"skip"` on purpose. The acceptance grep is
  `hovertemplate:`/`hoverlabel:` **with colons**, because the panel still names
  `hoverlabel.align` twice in the comments saying why the box could not be
  moved. The peaks-tab strip is the only place the peak-fit curve is named now
  that the box is gone (WP-1210's requirement, carried). And the `title=` debt
  counter matches `title="` only, so the strip's `title={row.label}` — the
  truncated-value echo the rule allows — is invisible to it, as the app's other
  eleven dynamic titles already were.

  **Deliberately not done.** The tick rows carry no ink, because the ticks
  themselves are drawn in plotly's default colourway and have no `--plot-*`
  token; giving them one is WP-1210's territory and its measurement says the
  hue space is spent. Intensities print at `formatValue`'s six significant
  figures, which is verbose for a residual and is exactly what the deleted
  templates printed (`%{customdata:.6g}`) — inventing a second numeric
  convention for one strip is worse than the verbosity. The residual subplot's
  empty quarter is still owed: this WP added a row under the plot rather than
  redistributing the domains, so 1212's note stands.

  **The review pass** (`/code-review medium --fix`) found four and applied
  three. The one that mattered: the hover link had become conditional on a 2θ
  resolving, so a hover that resolved none — the axis map not in hand after a
  repaint, or a pointer in the margin — left the ring and the lit table row on a
  line the pointer had already left, until it left the plot altogether. It
  answers on every hover while the layer is up now, `null` included, which is
  what the pre-WP handler did. The other two were prose: `candidateTraces`'
  docstring still gave `x unified` as the reason for its `hoverinfo: "skip"`
  (the reason is now that `skip` leaves the point-finding entirely, which
  `none` does not), and `gui/CLAUDE.md` counted two things the box could not say
  where the ROADMAP and the record both count three. **Declined**, and it is a
  fair finding: the `peak fit` row is gated on `peaksActive && groups.length`
  while the drawn curve additionally needs a non-empty peak list, so a payload
  with groups and no picked lines would put a row in the strip for a curve that
  is not drawn. No server payload produces that state — `peaks.groups` are the
  groups *of* the picked lines — and tightening it would change behaviour a
  passing test asserts.

  Next: **WP-1214** (Model — vary and profile save), then 1215/1216, then 1217.
  Nothing in this WP blocks any of them; the one thing to carry is that
  `/api/project`'s data arm is now where an instrument fact reaches a panel that
  does not fetch the instrument.
- **2026-08-25** — created from the v1.2 triage.
