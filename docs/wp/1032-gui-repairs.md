# WP-1032 — GUI repairs found by use

Milestone: v1.0 · Status: ✅ 2026-08-05
Track: The human GUI
Depends on: 1010-1015, 1027, 1029 (all landed) · **blocks** 1033 (same file)

## Goal

Nine small repairs to controls that already exist, all reported by a user
driving the shipped build: a hover box that is readable in dark mode, reflection
ticks that do not hide under the residual, control over which curves are drawn,
a peak picker whose gestures say what they do, a form with no unexplained field,
and a panel drag that does not lag.

## Context

**Every item came from the user driving the GUI on 2026-08-04**, the same
provenance as WP-1029 and none of it found by reading. The shape is deliberately
WP-1029's: uniformly small repairs, each independently landable, none needing a
design decision. **If an item starts arguing for a redesign it does not belong
here** — the panel layout is [1034](1034-panel-layout.md)'s and the fitted range
is [1033](1033-plot-range-regions.md)'s.

Everything below was **read from the source at `660c950`**, not measured. In
this codebase that distinction is load-bearing: WP-1029's second pass concluded
`lightposition` was inert from six pixel-identical probe pairs, and the next
session's probes contradicted it on the same browser and the same bundle. Treat
each citation as a place to look, not as a finding.

### What is there now

- **No `hoverlabel` styling exists anywhere in the app.** `Plot.svelte:113` sets
  `hovermode: "x unified"` and every trace carries a `hovertemplate`, but
  nothing themes the box — so it keeps plotly's default light background while
  `layout.font.color` is the themed `--fg` (`Plot.svelte:83,96`). Light-grey ink on
  a white box is exactly the report. `Structure3D.svelte` has the same gap.
- **Ticks live inside the residual subplot.** `Plot.svelte:181-189` draws one
  trace per phase on `yaxis2` at `y = -0.5 - row*0.9`, and `yaxis2`'s domain is
  `[0, 0.22]` (`Plot.svelte:111`). Their visibility therefore depends on which
  residual is selected — under a cumulative χ² curve, whose values run to
  thousands, they are pinned at the floor. The domain gap `[0.22, 0.28]` between
  the two subplots is **free**: `yaxis` starts at 0.28 (`Plot.svelte:106`).
- **The background curve is already unconditional.** `Plot.svelte:170-175` draws
  it whenever `w.y_background` is non-empty, and `/api/result/window` sends `[]`
  when the result carries none (`session.py:1424,1440`). So "make it possible to
  toggle the background on" is either the **raw/peaks view** — `paintRaw`
  (`Plot.svelte:300-318`) builds a payload of `two_theta`/`y_obs` only — or a
  request for control over a curve that is currently forced. A missing trace and
  a missing control are different repairs; find out which before building.
- **Nothing throttles a resize.** `Plot.svelte:408-414` calls
  `plotly.Plots.resize(node)` once per `ResizeObserver` callback;
  `Splitter.svelte:64` calls `onsize(next, false)` on every `pointermove` (the
  *network* is already spared — the POST fires once, on `done`); the relayout
  handler refetches the window from the server with no debounce
  (`Plot.svelte:201-208`); and the knob/theme effect (`Plot.svelte:449-454`)
  repaints through a full `plotly.react` with fresh trace objects. Four
  candidates, no measurement. See task 1.
- **The peak picker's right-click is a refit**, not a remove
  (`Plot.svelte:386-394` → `App.svelte:refitGroup`, which prompts through
  `window.prompt`). Remove already exists as the peak table's `×`
  (`Peaks.svelte:226`), and refit as its `↻` (`Peaks.svelte:221-225`).
- **The affordance line renders only in the raw state**: `Plot.svelte:467-471`
  is inside `{:else if !result && peaksActive}`, so once a fit exists the
  gestures are undocumented on screen.
- **Nothing links the peak table and the plot by hover.** The only link is a
  click on the 2θ cell, which zooms (`Peaks.svelte:137-139` → `onzoom` →
  `App.svelte:zoom` → a *server* refetch of that window).
- **`packing` has no `title`** in either of the two places it is offered:
  `lib/wizard.ts:48` (`debye_scherrer`) and `:71` (`flat_plate_transmission`),
  and `lib/model.ts:290,300` in the instrument editor. `title=` is the app's
  only help mechanism (`Model.svelte:588` for wizard fields, `:828` for
  instrument fields, where it falls back to the server's `held_because`).
  `PresetField` already declares an optional `title` (`lib/wizard.ts:27-36`).

### One reported item has no located defect

*"Transparent background text headings over picked list clash with other text on
scroll."* It was not found by reading. The **only** `position: sticky` in the
app is the Peaks table's `th` (`Peaks.svelte:482`), and it paints
`var(--panel)` — while `.side` and `.panel` (`App.svelte:762-806`) set no
background at all and show the body's `--bg`. That is a colour *mismatch*
(#ffffff on #fbfbfa light, #1e1e1e on #151515 dark), which is a plausible cause
and is **not** transparency. Other candidates worth checking in the same pass:
the plotly legend (`Plot.svelte:95`, over a transparent `paper_bgcolor`), and
the `h2` block headings in the scrolling section. **Reproduce it before planning
a fix** — task 3 is written as a reproduction, not a repair.

### Rules from the neighbours, restated because they bind here

- **A drawing choice is not persisted.** WP-1029 kept the residual kind and the
  intensity scale as component state for WP-1015's reason one panel over:
  storing one would make a picture the project's opinion (`Plot.svelte:73-75`).
  The curve toggles are the same kind of thing. What *is* persisted goes to
  `ProjectDoc.ui` **on the verb**, never on save.
- **Every pointer verb has a non-pointer route** (WP-1027). The typed-2θ box
  (`Peaks.svelte:153-157`) and the `.rxt` peaks block are the existing ones;
  changing what right-click means must not orphan a verb.
- **A style sampled synchronously inside an effect races the shell's
  `applyTheme`** — `paint()` awaits one microtask before `getComputedStyle`
  (`Plot.svelte:153`). Anything new that samples a custom property at draw time
  inherits that ordering, and the theme must be a **dependency** of the effect
  that draws it.
- **plotly's `responsive: true` listens for window resizes only**, which has now
  bitten two panels; any control row under a plot needs the `ResizeObserver`.
- The dist is committed: every commit touching `gui/` ends with
  `npm --prefix gui run build`, or `tests/test_gui_dist.py` fails on the digest.

## Non-goals

- **Not the panel layout** — Model/Text into the right panel, and the open
  screen, are [1034](1034-panel-layout.md)'s.
- **Not the fitted range** — 2θ limits and excluded regions are
  [1033](1033-plot-range-regions.md)'s, and it lands *after* this WP because
  both edit `Plot.svelte`.
- **Not the manual** — [1017](1017-gui-manual-onboarding.md) documents what this
  changes; land before it and write into its inherited-mailbox section on
  sign-off.
- **Not a new plot library, and no client-side decimation** (WP-1010).

## Tasks

- [x] **Where does the frame go?** Profile a sidebar drag and a plot resize in a
      real browser *before* changing anything, and name the cost. The four
      candidates above are candidates; the plan deliberately picks no winner.
      Fix what the profile indicts, and **record what it exonerated** — a
      throttle added to an innocent path is a permanent claim nobody can audit.
- [x] **Themed `hoverlabel`** on both plotly surfaces (`Plot.svelte:layout()`
      and `Structure3D.svelte`), sourced from the same custom properties
      everything else reads. No component learns a hex value.
- [x] **Reproduce the heading clash**, both themes, and fix what is actually
      there. Either way, give `.side`/`.panel` the surface colour they claim, so
      a sticky `--panel` backdrop stops being a mismatch.
- [x] **A tick band of its own** in the `[0.22, 0.28]` gap — a third y axis,
      one row per phase, ticks legible under every residual kind and every
      intensity scale.
- [x] **Curve toggles** (observed / calculated / background / difference / each
      phase's row), unpersisted. Settle the background question above first and
      say which repair it turned out to be.
- [x] **Right-click removes.** Refit stays on the table's `↻`; the
      `window.prompt` goes with it.
- [x] **The gestures are stated whenever the Peaks tab is active**, fit or no
      fit, with the non-pointer route named beside each.
- [x] **Hover links the table and the plot both ways** — one `hoveredIndex` in
      the shell threaded to both panels, drawn through `restyle` or a dedicated
      one-point trace. A full `react` per mouse move is the defect task 1 is
      about.
- [x] **No form field without help**: `packing` gets its title from the schema's
      own words (`instrument.py:384-386` — fraction of the bore or slab occupied
      by solid, 0.3-0.6 for a tapped powder, 0.64 random close packing,
      estimator input only and never refinable), then a vitest asserts **every**
      `PresetField` and every `instrumentFields()` entry has one.
- [x] Tests: vitest for each pure function added and a jsdom mount test per
      control; `tests/test_gui_server.py` only if a route moves (none should).

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_server.py tests/test_gui_peaks.py -q
.venv/bin/python -m ruff check src tests examples
npm --prefix gui run build && .venv/bin/python -m pytest tests/test_gui_dist.py -q
```

And the part no suite covers: **the screenshot that prompted each item, taken
again**, in both themes at 1500 px and at 1000 px — on the NAC project (COD
1000236 + `11BM_NAC.fxye`, which refines to Rwp ≈ 13.4 %) for the fit path, and
on the qarr corundum project (`corundum.prn`, `has_sigma = False`) for the
raw/peaks path.

Two harness traps that already cost measurements: playwright's viewport option
is `newContext({ viewport })` and **not** `viewportSize`, which is silently
ignored — so a run claiming 1500 px and 1000 px is otherwise a run at the
default 1280 px twice; and the chromium binaries are cached although playwright
is not installed, so `playwright-core` is installed in the job scratchpad,
**never** in `gui/`.

## References

- `gui/CLAUDE.md` — the GUI rulebook; WP-1029's and WP-1027's paragraphs bind
  most of the items here.
- `docs/milestones/v1.0.md` — WP-1027's and WP-1029's measured browser passes.
- `src/rietx/schemas/instrument.py:374-386` — the `packing_fraction` docstring
  the tooltip quotes.

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**Repairs found by use** (WP-1032, `lib/resize.ts`, `lib/plot.ts`,
`panels/{Plot,Peaks,Structure3D}.svelte`) is the pass that measured what the
eleven panels *feel* like, and its rules are about how to find such things.
**A trailing canvas is not a dropped frame**: chunked work behind an
un-coalesced `ResizeObserver` costs *latency*, not jank. Under plotly a drag
issued one ~111 ms resize per pointer move and the last landed 1.10 s late at a
steady 60 fps, so measure when the final size lands, not the frame rate. The
chart module's `setSize` runs in the observer's own frame and the viewer asks
for one `requestAnimationFrame`, so neither queues, and `resize.ts:coalesce`
went with plotly (WP-1461). **Instrument before the library loads**: a
`$state` rune proxies a namespace and caches each property on first read, so a
probe patched in after boot counts nothing while the chart redraws (it was
`window.Plotly`) — use an init script. **A fix that does not remove the symptom is evidence about the cause**:
the sticky peak header's backdrop is opaque and the panel column's missing
surface was a real, separate mismatch; what paints a row over the header is
`opacity: 0.55`, which promotes it to z-index 0 while the sticky `th` sat at
`auto`. Three rules about what a plot may say: **a tick belongs to the model,
not the residual** (a band of its own between the two — on the residual's axis
its visibility was a property of which residual was chosen), **hiding a
curve is by exception** (`curveToggles`/`hidden`, unpersisted, so a curve a
later build adds arrives drawn), and **a hover link never repaints the
pattern** — the ring is a DOM mark over the canvas (WP-1461; under plotly it
was one `restyle` of a two-point trace). Right-click **removes** a
peak (refit stays on the table's `↻`; the `window.prompt` is gone), and the
gestures are stated whenever the Peaks tab is up, each naming its non-pointer
route. **No mute fields**: every `PresetField` and every `instrumentFields()`
entry is described, pinned by a meta-test over every geometry — ten were mute
the day it was written. WP-1203 retargeted it from `title=` to a corpus key.

## Handover log

- **2026-08-05** — **closed.** All nine repairs landed on branch
  `wp1032-gui-repairs`, seven commits, every one of them measured in a real
  browser before and after. Frontend: **303** vitest (was 282 — +21: 4
  `coalesce`, 2 `hoverLabel`, 3 tick band, 4 curve toggles, 3 field-help
  meta-tests, 5 jsdom mounts), svelte-check clean, `tests/test_gui_server.py`
  + `test_gui_peaks.py` + `test_gui_dist.py` **73 passed**, ruff clean, dist
  rebuilt in each commit. Screenshots: both themes × 1500/1000 px × both
  projects, in the job scratchpad.

  **Four findings worth more than the repairs they came from.**

  1. **The lag is a trailing canvas, not stutter.** One `Plotly.Plots.resize`
     of the NAC pattern (22 003 points → 7347 drawn, five traces) costs
     **~111 ms**, and a 60-move sidebar drag issued **sixty** of them —
     latencies climbing 117 134 151 168 …, the last resolving **1.10 s** after
     it was asked for — while the page held 60 fps with **zero** long tasks.
     So the eye sees the plot arrive a second late, and no frame-time metric
     would ever have shown it. Fixed by `lib/resize.ts:coalesce` (one in
     flight, at most one queued, and the queued one *runs* so the last redraw
     is the final size): 60 → 3 calls, 1101 → 116 ms. The structure viewer had
     the identical defect — **measured, not assumed**: 60 calls, max 1115 ms,
     now 6 and 135 ms.
     Exonerated and recorded: Splitter's per-pointermove `onsize` (already one
     POST per drag, 14 ms), the relayout refetch (a drag-zoom emits one
     relayout; plotly's cartesian `scrollZoom` is off, so a wheel emits none —
     10 notches, 0 events), and the knob/theme `react` (12–16 ms per click).
  2. **The heading clash was a `z-index`, and the reported cause was wrong
     twice over.** Not transparency: the sticky `th` backdrop is opaque in both
     themes. Not the `.side` colour mismatch either — that was real (#ffffff on
     #fbfbfa, #1e1e1e on #151515), it is fixed, and **the clash survived it**.
     What puts a row over the header is `tr.out td { opacity: 0.55 }`: opacity
     < 1 paints as though positioned at z-index 0, and `tbody` follows `thead`
     in tree order. Hence only the *excluded* rows ever clashed. Found by
     `elementFromPoint` inside the header band returning the chip.
  3. **A harness trap that cost the first two profiling runs**, and it will
     cost the next session too: instrumentation must be installed from an
     **init script**, before plotly.js assigns `window.Plotly`. `Plot.svelte`
     holds the namespace in a `$state` rune, whose proxy caches each property
     in a signal on first read — so a wrapper *confirmed installed* on
     `window.Plotly.react` counted zero calls while the plot demonstrably
     redrew. "Suspect the harness first" earned again.
  4. **The background question resolved to "a missing control".** The trace is
     drawn unconditionally whenever `y_background` is non-empty, so nothing was
     absent; what was absent is the way to turn a forced curve off.

  Two smaller notes. The task-9 assertion found **ten more** mute fields once
  it existed, which is the argument for writing the meta-test rather than the
  tooltip. And the `.side`/`.panel` surface change is CSS with no pure function
  under it: it is verified by screenshot only, in both themes, at both widths.

  Nothing is left open. `1033` inherits the `Plot.svelte` it now shares.

- **2026-08-04** — created from a user's list after driving the shipped GUI,
  together with [1033](1033-plot-range-regions.md),
  [1034](1034-panel-layout.md), [1035](1035-symmetry-surfaced.md) and
  [1036](1036-crystal-system-settings.md). Nothing is started.

  **Three things a successor should not re-derive.** The domain gap
  `[0.22, 0.28]` is free, so the tick band needs no room made for it. The
  background curve is already drawn unconditionally, so the reported item is
  *not* "add the trace" until someone checks the raw view. And the heading-clash
  item has **no located defect** — the only sticky element in the app already
  has a backdrop, so the reproduction is the work, and finding it is something
  else entirely is a legitimate outcome to write down.

  **Two scope decisions the user took**, binding and not to be re-litigated:
  right-click **removes** (refit survives on the table's `↻`), and "toggle
  individual histograms" means **toggle the plot's curves** — the GUI is
  single-pattern by construction, `Project.open` refuses a project holding more
  than one, so no server change is implied.

  Suggested order is the task list's, and task 1 is first for a reason: the
  hover-link item is the one most likely to *create* the lag complaint, and it
  should be written against a profile rather than a guess.
