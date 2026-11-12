# WP-1033 — 2θ limits and excluded regions, visible and selectable

Milestone: v1.0 · Status: ✅ 2026-08-05 — shaded, selectable, and pinned to the
channel count
Track: The human GUI
Depends on: **1032** (strictly — both edit `Plot.svelte`; see below) · 1005,
1008, 1009 (landed)

## Goal

A user can see which part of the pattern is being fitted and change it from the
plot: the fit range and every excluded region shaded where they act, selectable
by pointer, with the typed route the text document already has — and one
authority, so the GUI, the `.rxt` document and the exported figures cannot
disagree about what was masked.

## Context

**The feature exists and is invisible.** Nothing here adds a model, a verb or a
persistence path; all three landed with WP-1005 and WP-1009. What is missing is
that no renderer in the package draws them, and no pointer sets them.

### What is already implemented (read at `660c950`)

- **Two fields, one verb.** `ProjectDoc.two_theta_limits` and
  `ProjectDoc.excluded_regions` (`schemas/project.py:99,106`);
  `Project.set_excluded_regions` (`project.py:275-284`) writes the document
  *and* the in-memory `PatternData` together, "because the two must not
  disagree", and deliberately does **not** rebind history — the fingerprint is
  over the measured arrays, so excluding a region leaves every node replayable.
- **The masking is real, not a weighting.** `PatternData.in_range_mask`
  (`schemas/pattern.py:58-65`) drops the points; `compile_model` applies it as
  its first act and intersects it with `two_theta_limits`
  (`model/forward.py:1075-1082`), raising if fewer than ten points survive. So
  excluded channels never enter the residual, and therefore never enter Rwp or
  χ². The same mask is honoured by background anchor selection
  (`background/select.py:68,108`), background diagnostics
  (`background/diagnostics.py:153`), peak picking (`indexing/peaks.py:307`), the
  GUI's raw peak-plot pattern (`gui/session.py:1118`) and the peak-editor cache
  key (`gui/session.py:1136`) — so changing an exclusion correctly invalidates
  the fitted peak list.
- **The wire verb accepts both already.** `POST /api/project` takes
  `{mode, two_theta_limits, excluded_regions, ui}` and rejects anything else
  (`gui/session.py:341-353`). The frontend's `api.patchProject`
  (`gui/src/api.ts:102`) is called from exactly one place, always with
  `{ui: …}` (`App.svelte:166`).
- **The text document is the only surface.** `textdoc.py:318-322` renders
  `limits 3 60` and `excluded 7.5 8  24 25.2` (or `none`), `:531-548` parses
  them — `excluded` takes pairs and refuses an odd count in its own words — and
  `:991-994` applies through `Project.set_excluded_regions`, echoing the call.
- **Nothing draws them.** There are no `layout.shapes` anywhere in the frontend,
  and `viz/` has no `excluded_regions` consumer at all: not `plot_result`, not
  `plot_for_vlm`, not `write_html`. A region you excluded is invisible in every
  picture the package produces.

### What WP-1032 left in `Plot.svelte` (folded in from its mailbox)

- The reflection ticks are on **`yaxis3`**, a band at `[0.225, 0.275]` between
  the two subplots (`lib/plot.ts:tickBand`). That gap is no longer free, so a
  shaded range or region is drawn as a **shape** across the paper
  (`yref: "paper"`), never by claiming a domain.
- **Which curves are drawn is a client choice** (`hidden`, an *exception* list,
  `curveToggles`) — but a shaded region is not a curve and does not join it: it
  is a fact about the protocol, and the WP-1015 rule that keeps the toggles
  unpersisted is the same rule that puts a *region* in `ProjectDoc`.
- The `ResizeObserver` is coalesced through `lib/resize.ts:coalesce`; one redraw
  of the NAC pattern is ~111 ms, so a per-pointer-move `relayout` would be
  measurable. It is avoided by construction here: the drag is plotly's own
  select box, which costs nothing until it ends.
- Right-click **removes a peak**, and the gestures line under the header names
  every pointer verb. Arming a region selection therefore *suspends* the peak
  gestures rather than competing with them (below).

### The two rules this WP is really about

**1. These are protocol, not drawing choices, and must not look like the knobs
beside them.** The residual selector and the intensity scale are session-local
and unpersisted, because storing one would make a picture the project's opinion
(WP-1015's rule, applied in `Plot.svelte:73-75`). An excluded region is the
opposite: it changes what is fitted, it persists in `project.json` **on the
verb**, and it lives in the document precisely because *a history node cannot
record what was excluded when it ran* (`schemas/project.py:101-105`). Two kinds
of knob will now sit on one plot; if they wear the same clothes the user cannot
tell which one changes the answer.

**2. A fourth drag meaning is the risk in this WP.** The canvas already carries
peak-add (a plain click on empty space), peak-move (a drag captured from plotly
inside `grabToleranceDeg`), shift-toggle, right-click, and plotly's own zoom
drag — all in `Plot.svelte:324-394`, and all gated on `peaksActive`. WP-1027
measured what happens when two of those overlap: a 10 px grab radius is ±1.9° at
the survey view, so a zoom drag starting 0.9° from a marker silently **moved a
line 11°**. The repair was to derive the radius from the fitted FWHM
(`grabToleranceDeg` = min(10 px, 1.5× median FWHM), `lib/peaks.ts:97-106`), so
that a drag over a subpixel line falls through to the zoom.

**Settle the arbitration before writing a handler.** The obvious candidates:
region selection lives on its own modal state (a "select range" toggle, the way
`peaksActive` gates the peak gestures), or it takes a modifier, or plotly's own
`dragmode: "select"` is turned on while the control is armed. Whatever is
chosen, the rule that survived WP-1027 must survive here: **an ambiguous drag
must do the harmless thing**, and every pointer verb keeps a non-pointer route —
which for this one already exists as the `.rxt` `limits`/`excluded` lines, plus
typed bounds in the panel.

### The `viz/` question, which is a decision and not a task

The GUI would shade regions the exported PNG and HTML do not, making them two
authorities on one picture. That is the shape of the bug WP-1029 (s) found: five
open-coded weighted residuals under three policies, where the pin that caught it
compared **what each renderer drew** against **what the route sent**, because
three re-derivations of one formula agree with each other while all being wrong.
Decide explicitly whether `viz/` shades too — and if the answer is no, write
down why, because the next person will ask.

**Decided 2026-08-05: `viz/` does not shade, and it is not a second authority.**
Three facts settle it, and the first is the one to read:

1. **A `RefinementResult` cannot say what was excluded.** `compile_model` masks
   before a result exists, so `result.two_theta` *is* the surviving channels
   (measured: a 3–24° pattern comes back 8.005–18.990° under limits, with zero
   points inside a 3° exclusion). The exported figure therefore draws exactly
   what was fitted, and the exclusion is present in it as absence. That is the
   same reason a history node cannot record the regions either
   (`schemas/project.py`) — it is *why* they live in `ProjectDoc`.
2. `plot_result`, `plot_for_vlm` and `write_html` all take a result and nothing
   else, and `GuiSession.export` passes `res`, not `p`. Shading would mean a new
   argument on three functions plus a caller that knows the document — three new
   places to be wrong about one fact, which is the WP-1029 (s) shape rather than
   the cure for it.
3. The GUI shades because it is the **settings surface**, not because it is a
   better picture: it must show the range and the regions *before* any run
   exists (the raw peak view), and it must show what a change did *before* the
   next fit agrees with it. Neither statement is about a result, so neither
   belongs to a result renderer.

What the GUI must not do, and does not, is *infer* the protocol from a gap in
the arrays. A gap is what an exclusion leaves; the exclusion itself is read from
`ProjectDoc`, and the two are pinned to each other by the channel count.

## Non-goals

- **Not the repairs** in [1032](1032-gui-repairs.md), which lands first.
- **Not multi-pattern.** `Project.open` refuses a project holding more than one
  pattern (`project.py:196-201`); a per-histogram range is a later milestone's.
- **No `.rxt` format change.** `limits` and `excluded` are already in the
  grammar; if this WP finds it needs a new line, that is a format-version
  question and it stops here.
- **Not a new masking semantics.** Excluded points are dropped, not
  down-weighted; nothing here revisits that.

## Tasks

- [x] **Shade both from `ProjectDoc`** through `layout.shapes` — the fit range
      as what is *outside* it, the excluded regions as bands — legible in both
      themes, from the custom properties, and correct under every intensity
      scale (a shape in log space is not a shape in linear space).
      `lib/plot.ts:maskShapes`, `yref: "paper"`, clipped to the measured extent.
- [x] **Serve what the shading needs**, which the measurement added to this WP:
      both views drop the masked channels, so the bands had nothing to shade and
      the fit range had no outside (`GuiSession._masked_arm`, `Project.fitted_mask`).
- [x] **Settle the gesture arbitration and write the argument down** where the
      handler lives, with WP-1027's measured overlap as the precedent. Then
      implement selection. — an armed *mode*, plotly's own select box, the peak
      verbs suspended while it holds; the argument is at `Plot.svelte:arm`.
- [x] **Typed bounds in the panel** as the non-pointer route, refusing an
      inverted or empty range in the verb's own words
      (`schemas.project.check_interval`, quoted by three surfaces).
- [x] **Send through `POST /api/project`**, which means `api.patchProject` stops
      being a `{ui: …}`-only call site — check that the 409-while-running rule
      still reads correctly for a settings-only patch (the open question in
      [1003](1003-api-freeze-pypi.md)'s mailbox about `ui`-only patches
      is adjacent, and this WP must not settle it unilaterally). — it reads
      correctly and is now asserted: an exclusion changes which channels the
      *compiled* model was built from, so it is a mutating verb in the strict
      sense. Nothing about `ui`-only patches was decided here.
- [x] **The two surfaces agree**, asserted: a region set on the plot renders in
      the `.rxt` document, and one typed into the document shades on the plot.
- [x] **Decide the `viz/` question** and record the answer either way (above).
- [x] Tests: vitest for the shape-building and range-arithmetic pure functions,
      a jsdom mount test for the controls, a `tests/test_gui_server.py` case for
      the settings round trip, and obs/calc/diff PNGs to `tests/output/` if
      `viz/` changes (it did not).

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

Plus, in a real browser on the NAC project (COD 1000236 + `11BM_NAC.fxye`):
exclude a region by pointer, confirm it shades, confirm the `.rxt` document
shows it, re-run, and confirm the fit's channel count dropped by the number of
points in the region. **The channel count is the check that the shading is
telling the truth** — a band drawn over points still in the residual is worse
than no band at all.

## References

- WP-1027's measured pointer overlap (`docs/milestones/v1.0.md`, the 1027 close
  entry) — the precedent for arbitrating a new drag.
- WP-1029 item (s) — why two renderers of one fact is a bug shape rather than a
  cosmetic mismatch.
- `docs/wp/1005-project-container.md` — why `excluded_regions` lives in the
  document and not in a history node.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**What is fitted, shaded and selectable** (WP-1033, `lib/plot.ts`,
`panels/Plot.svelte`, `session.result_curves`, `Project.fitted_mask`) is the fit
range and the excluded regions made visible, and its founding measurement is
that **a mask is invisible in a picture of its own output**: `compile_model`
masks before a result exists, so both payloads carried only the surviving
channels — a band would have shaded a hole, and a fit range had no *outside* at
all, the axis autoranging inside it. So the masked channels travel beside the
fitted ones (the curves payload's `kept`) and `Project.fitted_mask` is the one
authority for which channels the next run fits, pinned to `compile_model` by
asserting `len(result.two_theta)` against it. Four rules. **Protocol is not a
drawing choice and may not wear its clothes** — the residual selector and the
scale are session-local and unpersisted, while a region changes Rwp and persists
on the verb, so it lives in a strip of its own with typed fields and chips, and
that strip carries the **channel count**, because a band drawn over points still
in the residual is worse than no band. **Settings persist on the verb and curves
move only on a run**, so between the two the picture contradicts the setting: the
route says `stale` by comparing the fitted 2θ *values*, not their count. **The
shading spans every pane's full height and is clipped to the measured extent**
— full height because a rectangle in log space is not the rectangle in linear
space, and an excluded channel is missing from the residual too; clipped
because outside the measured pattern there is nothing to exclude (under plotly
a shape took part in the autorange, and bands drawn past the data *became* the
range: −40 to 100 on a 0.5–59.99° pattern). And **a new pointer
meaning that is ambiguous everywhere is a mode, not an arbitration**: WP-1027
could make the peak grab radius readable because the ambiguity was local, but a
region drag is a zoom drag at every distance — so arming is explicit, hands the
drag to the chart's select mode (x only, zooming nothing), *suspends* the peak
verbs, and disarms after one selection. `viz/` deliberately does not shade (grounds in the WP): a result
cannot say what was excluded, so the exported figure shows it as absence.

## Handover log

- **2026-08-05** — **closed.** Branch `wp1033-plot-range-regions`, six commits.

  **Done.** All eight tasks, plus one the measurement added. The shading is
  `lib/plot.ts:maskShapes` (paper y-ref, clipped to the measured extent) drawn
  from `ProjectDoc`; the gesture is an armed *mode* over plotly's own select box
  (`Plot.svelte:arm`); the typed route and the region chips are the `.protocol`
  strip under the plot; everything goes through `POST /api/project`, which is no
  longer a `{ui: …}`-only call site. Server side: `Project.fitted_mask()`, an
  `excluded` arm and a `stale` flag on `/api/result/window` and the raw peaks
  pattern, `n_fitted` on the project document, and
  `schemas.project.check_interval`. 18 vitest rows (11 pure, 7 mounted) and 4
  server rows; fast suite 1656 → 1660 passed, 108 skipped either way, `[dev]`.

  **The thing to know before touching any of it.** The feature was *not* only
  missing pixels, which is what this file said on 2026-08-04 and what I believed
  for the first hour. **A mask is invisible in a picture of its own output**:
  `compile_model` masks before a result exists, so both payloads carried only
  the surviving channels — measured, a 3–24° pattern comes back 8.005–18.990°
  under limits, with zero points inside a 3° exclusion. Shading alone would have
  drawn a band over a hole, and the fit range would have had no *outside* at all
  because the axis autoranges inside it. Half this WP is therefore server work
  that the plan did not contain, and a successor who deletes the `excluded` arm
  as redundant will silently get the empty picture back.

  **Two more, both found only in a real browser** (chromium is cached;
  `gui/CLAUDE.md` has the recipe). A shape bound to a data axis **takes part in
  the autorange**, so bands drawn past the data — to survive a zoom-out, the
  obvious implementation — *became* the range: −40 to 100 on a 0.5–59.99°
  pattern. And `paintRaw` builds its payload by hand, so the raw view silently
  had no masked points until it was passed them explicitly; that view is the
  only place a fit range can be seen before the first fit.

  **A harness note in the same key as WP-1027's `window.prompt`.** jsdom's div
  has no plotly emitter, so `plotNode.on?.(…)` is a silent no-op and a select
  gesture cannot be driven at all — `App.test.ts` patches `on` /
  `removeAllListeners` onto `HTMLDivElement.prototype` for that one block. And
  in the browser probe a listener registered from `page.evaluate` recorded
  nothing while the app's own handler fired correctly: the component's next
  `react` had cleared it. Suspect the harness first.

  **Next.** Nothing is left open here. [1034](1034-panel-layout.md) is the
  next GUI WP and its mailbox now says what the strip costs in vertical
  space; [1017](1017-gui-manual-onboarding.md) has the controls to document;
  [1003](1003-api-freeze-pypi.md) has the new public surface and the `ui`-only
  question, which this WP deliberately did **not** settle.

  **Gotchas.** The `.rxt` document renders 12 significant digits, so a
  pointer-drawn region reads as `excluded 15.2668475177 34.6747042553` — correct
  and ugly; rounding it would be a second authority on the number, so it stands.
  `formatRegion` rounds the *chip* only. And the region chips are keyed by their
  formatted text, so two regions that print identically at 3 dp would collide in
  the `{#each}` — they cannot both exist after `mergeRegions`, but a future
  writer that stops merging must change that key.

- **2026-08-04** — created from a user's list after driving the shipped GUI,
  alongside [1032](1032-gui-repairs.md), [1034](1034-panel-layout.md),
  [1035](1035-symmetry-surfaced.md) and
  [1036](1036-crystal-system-settings.md). Nothing is started.

  **The feature is done; only the pixels are missing.** The model, the mask, the
  verb, the persistence and the text surface all exist and were read at
  `660c950` — the citations above are a map, and a successor should not go
  looking for the backend half.

  **This WP is sequenced after [1032](1032-gui-repairs.md) deliberately**, and
  the reason is not politeness: both edit `Plot.svelte`, and the repo already
  carries the scar of concurrent sessions in one working directory — WP-1018's
  files are committed inside WP-1004's and WP-1006's commits, whose messages
  name the wrong WP, and `git log -- src/rietx/indexing/` misleads because of
  it. One worktree per session, or one session at a time on this file.

  **The one thing to get right** is the second rule above: an excluded region
  and a residual selector are both knobs on one plot, and only one of them
  changes the answer. If they end up looking alike, this WP has made the GUI
  worse in a way no test will catch.
