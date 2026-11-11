# WP-1210 — The peak layer: hide it, tell it apart, data-only

Milestone: v1.2 · Status: ✅ 2026-08-27 — the layer has its own colours, its own tab and a way off
Depends on: WP-1201

## Goal

The picked-peak markers and their fitted curves can be hidden, look like
nothing else on the plot, appear only where they can be edited, and one click
leaves only the data.

## Context

The user's notes: hide picked peak markers; hide the individual fitted peaks
(which "are not clearly explained"); "an easy way to hide everything except
the data"; and the picked-peak fit line and the model's calculated line "both
the same colour".

Findings (2026-08-25):

- The peak layer is `peakTraces()` (`Plot.svelte:389-447`), pushed
  unconditionally at `:323`: `peak fit` (the joined per-group `y_fit`,
  `scattergl`, width 1.4, colour `--accent`, `hoverinfo: "skip"`), the raw
  view's `(y−fit)/σ` strip, `peaks` (markers plus the σ whiskers as
  `error_x`, capped at 3×FWHM), and the empty `hovered` ring trace.
- `curveToggles()` (`lib/plot.ts:317-345`) derives from the window payload
  and never mentions peaks; the hideable set is `obs`, `masked`, `calc`,
  `bkg`, `diff`, `ticks:<phase>`. No "data only". On the raw view the toggle
  row often does not render (`{#if toggles.length > 1}`, `Plot.svelte:838`).
- Colours: `peak fit` takes `--accent` (`#1f5fa8` light), which **equals
  `--plot-diff`**; `--bad` for unusable markers equals `--plot-calc`
  (`#c23b22`); `calc` is `--plot-calc` at width 1.2 (`Plot.svelte:292-295`).
  The two curves are the same weight, both solid, both on the intensity
  axis, and `y_fit` includes the detection envelope (`gui/peaks.py:395`), so
  they sit at the same counts. Neither has a legend entry.
- The plot is an editing surface **only while the Peaks tab is active**
  (WP-1027), but the layer is drawn in every tab.
- `hidden` is an exception list and unpersisted (`Plot.svelte:124-126`), so
  a curve a later build adds arrives drawn (WP-1032).
- The phase palette rotates in OKLab at a distance floor (WP-1029).

## Non-goals

- Candidate cells on the plot (WP-1211); jitter (WP-1212).

## Tasks

- [x] `curveToggles` grows `peaks` and `peak fit` when a list exists;
      `Plot.svelte` guards `peakTraces` with `shows()`; a **data only**
      button that hides every id but `obs` and restores on second click.
- [x] Tokens `--plot-peak` and `--plot-peakfit` in `app.css`, both themes,
      validated against every other plot token in OKLab (the phase-palette
      floor, asserted in `plot.test.ts`); the fit curve dashed and named in
      the legend and the hover; unusable markers on a tone that is not
      `--plot-calc`.
- [x] The layer drawn only while the Peaks tab is active (a prop from App),
      with the layer's absence stated in the curve toggles.
- [x] Browser pass with a result and a peak list: four distinguishable
      curves in both themes; dist.

## Acceptance

```sh
npm --prefix gui test && npm --prefix gui run check
```

A light and a dark screenshot with obs, calc, bkg, peak fit and markers all
present and each identifiable without the legend.

## References

- WP-1032 (hiding is by exception), WP-1029 (OKLab distance).

## Moved from gui/CLAUDE.md

On 2026-11-09 WP-2134 condensed `gui/CLAUDE.md` to its standing rules, each still
naming this WP. The text below is what that file carried for this WP until then,
verbatim: the rules with the measurements, stories and examples behind them. Where it
and the rulebook disagree, the rulebook is current.

**The peak layer** (WP-1210, `lib/plot.ts`, `panels/Plot.svelte`, `app.css`).
Four rules. **A layer is drawn where it can be edited** — the markers and their
fitted curve are on the plot only while the Peaks tab is up, which is already
the only tab a click there means anything on (WP-1027); `peaksActive` is
therefore a *drawing* input and belongs in the repaint effect, or leaving the
tab redraws nothing. **A curve that cannot be drawn is listed and disabled
carrying the reason**, never dropped: `CurveToggle.absent` is that sentence, and
`dataOnlyHidden` covers absent ids too, or a hidden layer arrives drawn the
moment its tab comes up. **Chrome is not a palette**: `--accent` and `--bad` are
`--plot-diff` and `--plot-calc` **exactly** on the light theme, which is how the
picked-peak fit and the model came to be one red line, so a plot mark takes a
`--plot-*` token of its own — `tests/test_gui_palette.py` holds every one to the
phase palette's 0.13 OKLab floor against every other plot colour, in Python
because `structure3d._oklab_distance` is the one distance this package has. It
also names the two pairs the shipped set already misses rather than exempting
them quietly. And **state rides on the mark, not on a second colour**: one ink
for the whole layer with hollow for unusable and diamond for human-placed, so
it spends two colours and the palette stays separable — measured while
choosing, the free hue space is magenta and green alone (violet is 0.10-0.12
from `--plot-diff`, `--warn` 0.053 from `--plot-calc`). The corollary is where
that rule was broken and caught in review: a mark that is **not** the data may
not borrow the recessive `--muted`, which is 0.032 from `--plot-obs` on the
dark theme — fine for the masked points, which *are* measured data, and wrong
for a marker sitting on top of them.

## Handover log

### 2026-08-27 — the layer has its own colours, its own tab and a way off

Three complaints about the peak layer turned out to be one defect with three
faces, and the sharpest of them was exactly true rather than approximately:
the picked-peak fit curve and the model really were the same colour, because
the layer had no colours of its own and borrowed the app's chrome, which on
the light theme *is* the difference and calculated curves to the last digit.
The layer now has two tokens, is drawn only on the tab where a marker can be
edited, can be switched off like any other curve, and one button clears the
plot to the measured points and puts the picture back. What a reader gets is
a plot where every mark can be named without consulting the legend — and a
gate that will refuse the next panel WP a colour that collides with one
already there.

The part worth carrying: **the plot's free hue space is nearly spent**.
Measured while choosing this pair, only magenta and green clear the phase
palette's 0.13 OKLab floor against the shipped set — violet lands 0.10-0.12
from the difference curve and the obvious alert tone for an unusable marker,
`--warn`, is 0.053 from calculated. Magenta is now taken. A future mark should
plan to spend *no* colour and carry its identity on the mark, which is what
this layer does for peak state — one ink, hollow for unusable and diamond for
human-placed — rather than spending a second.

**Done.** All four tasks. `curveToggles` grows `peaks`/`peak fit` from a
`PeakLayer` passed beside the window payload; `dataOnlyHidden`/`isDataOnly`
are pure and over the same unpersisted `hidden` exception list, with
`Plot.svelte` holding the previous list so the second press restores rather
than showing everything. `--plot-peak`/`--plot-peakfit` in all three theme
blocks, one hue family (334°) in two tones, the fit curve dashed and named in
the legend and the hover, and the markers one ink with the ring carrying the
state. The layer is gated on `peaksActive`, and its two toggles
are listed and **disabled carrying the reason** when it is away.

**Measured**, all darwin/arm64 on this worktree's own venv, `[dev]` — jax and
torch absent. Two trees, because `origin/main` moved under this branch
mid-session (PR #118, the per-phase agreement trajectory) and the counts that
matter are the **merged** tree's.

- Branch alone: fast selection `-m "not slow"` **3148 passed / 117 skipped** in
  152.71 s, against WP-1209's recorded **3138 / 117** on the same extras and
  platform — exactly the ten `tests/test_gui_palette.py` adds, **no new skip**.
  vitest **475**, against 1209's 467, so +8 (5 in `plot.test.ts`, 3 in
  `App.test.ts`).
- Merged with `origin/main` (the tree that lands): **3153 passed / 117
  skipped** in 170.70 s and vitest **476** — main's five python tests and one
  vitest case on top, no interaction. `svelte-check` 0 errors / 0 warnings over
  378 files, `ruff` clean, dist rebuilt at `1926c16de396` (the review's
  fixes rebuilt it again; vitest stayed 476, the assertions changed).

The merge conflicted **only** in the built dist (`app.js`, `build-info.json`),
because main had rebuilt it too; the resolution is a rebuild from the merged
sources, never a hunk choice. The full selection was **not** run and should not
have been: nothing here can move a refinement number (root CLAUDE.md § Numbers).

Browser pass in Chrome on the NAC example, fitted in the served session (Rwp
0.0932, 86 lines picked / 74 usable), both themes. Light — markers `#8c257e`,
fit `#c158b0` dashed, against calc `#c23b22` and Δ/σ `#1f5fa8`. Dark —
`#e687d5` / `#b156a2` against `#e56a52` and `#5897dd`. Unusable markers are the
layer's own ink, hollow, in both (the review note below has why that changed).
`data only` leaves exactly `observed`; the second press restores,
a hand-hidden phase still hidden. On the Report tab the layer is absent and
its toggles disabled with the sentence.

**Gotchas**, all three costing time here.

- **`peaksActive` is a drawing input.** The tab gate looked complete and did
  nothing: nothing repainted on a tab change, so the layer stayed on screen
  from the previous paint. It belongs in the repaint effect beside the knobs.
  `App.test.ts`'s hover-link test is what caught it — the ring stopped being
  the last trace — which is also why `ringAt` is now found by name.
- **A served session holds no result on open.** A result is not persisted,
  only history state, so a browser pass wanting calc/bkg/Δ must run the fit
  *through the server*; fitting in a preparing process leaves the page on the
  raw view and looks like a drawing bug.
- **`POST /api/settings` takes `{"ui": {"theme": …}}`.** A bare `{"theme": …}`
  is a 400, which reads as "the theme did not apply" when driving a browser.
  Drive it with `--state-dir` at a scratch path too, or the pass rewrites the
  person's own theme.

**Not repaired, and predating this WP:** with the residual hidden its subplot
keeps its domain, so `data only` leaves a quarter of the plot empty. Hiding
`Δ/σ` alone has always done that; filed into WP-1212, which is the WP that
touches this layout.

**Where the OKLab assertion lives, and why it is not where the WP said.** The
task named `plot.test.ts`; it is `tests/test_gui_palette.py` instead, reading
`app.css` and using `structure3d._oklab_distance` — the one distance this
package has, where a TypeScript port would have been a second answer to it.
`plot.test.ts` asserts the plumbing (`curveColors` reads each property, falls
back per property), which is the half that belongs in a client test. The
Python file also **names the two pairs the shipped palette already misses**
(light bkg/diff 0.129, dark obs/diff 0.124) rather than exempting them
quietly, holds them at 0.12 so they cannot get worse, and fails if a third
appears — retuning a shipped curve colour was not this WP's.

**The review** (`/code-review medium --fix`, run after the PR was open) found
four things, and two of them were claims this entry had already made.

- **A real bug, fixed.** The peak-fit hover was handed `customdata:
  sparse(fit.y)` — the *plot-unit* array, the same one `y` gets. Under the √
  scale the box read `31.6` where obs and calc at the same 2θ read `1000`.
  Every other hover here passes raw intensity (`calculated` hands plotly
  `w.y_calc`, not the √ of it). One line, and the browser re-check confirms the
  values are back in intensity.
- **The unusable-marker ink was wrong, and by this WP's own rule.** It sat on
  `--muted`, which is **0.032** from `--plot-obs` on the dark theme — the ink of
  the very points those markers sit on. The deeper error is that spending *any*
  second colour on the state is what "state rides on the mark" forbids: the
  layer is now **one** colour with hollow-vs-filled carrying it, which removes
  the collision and the exception together. `--muted` stays right for the masked
  points, because those *are* measured data; the palette test now says so where
  a reader would otherwise re-litigate it.
- **A claim narrowed rather than fixed.** `dataOnlyHidden` covers every id the
  payload offers *when pressed*, so a curve that comes into existence later
  draws on a cleared plot (press it with hand-placed peaks and no groups, then
  refit). The docstring claimed the invariant unconditionally. Fixing it means
  an armed mode that keeps re-hiding and must then decide what a manual toggle
  underneath it means — a bigger design than this button — so the claim now
  states its own limit. Found in review, not in use.
- **One finding measured false.** The review held that the `absent` sentence is
  unreachable because Chrome does not dispatch pointer events to disabled form
  controls. Checked on the real control in Chrome 1223: `disabled: true`,
  `pointer-events: auto`, and a pointer move over it fired
  `pointerover`/`mouseover`/`mousemove`, with the 223-character title in place —
  and nothing in `app.css` sets `pointer-events` on `button:disabled`. The
  tooltip reaches a pointer. Worth knowing, since the claim is a plausible one
  that used to be true.

*Next.* WP-1210 is closed; the successor is [WP-1211](1211-candidate-overlay.md)
(the candidate overlay), whose `### Inherited` now carries the data-only
seam, the hue-space measurement and the tab-gating rule. WP-1212 and WP-1213
have their own notes — 1212's matter most, since this WP moved the line
numbers its findings quote and added a new occasion for the autorange it is
chasing.

- **2026-08-25** — created from the v1.2 triage.
