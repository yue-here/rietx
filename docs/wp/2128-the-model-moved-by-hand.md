# WP-2128 — the model moved by hand: the Interactive tab and the previews

Milestone: gui-overhaul · Status: ✅ 2026-11-09 — the Interactive tab and both previews landed; the Background tab is piece 5
Depends on: 2123 (the shell the previews draw in); 2125 (the preview route)

## Goal

`rietx gui` gains an Interactive tab beside Parameters. It holds a slider for each value a
person moves by hand: the profile widths, the zero shift, the displacement, the axial
divergence, and each phase's scale, free cell lengths and broadening. Dragging one draws
the pattern at the new values over the data, through `POST /api/preview`, without
refining or writing anything. The Pattern graph shows the preview over the whole pattern,
and a new graph tab shows three single-peak windows. Every graph titles itself "Preview,
not refined" while it shows one, and keeps the last fit's scale. The slider values are
pending edits: the action bar's Apply and Apply and refine commit them, and Revert drops
them.

## Context

### The designs, and the rulings they rest on

The maintainer reviewed these designs on screen in the design rounds of 2026-11-06 to
2026-11-08. The prototypes are not published, so each design is restated here with its
ruling.

1. **Sliders as visual fitting without refinement.** Ruled 2026-11-07 (second Parameters
   review): "sliders as visual fitting without refinement, against data and model". Nothing
   refines until the person asks.
2. **The tab is called Interactive, and it is a mode.** Ruled 2026-11-07 (sixth review):
   "Sliders" becomes "Interactive". The fourth review the same day ruled that the right
   panel's tabs switch mode, Parameters and Sliders, and the two never show at once.
3. **A full-pattern mode as well as single peaks.** Ruled 2026-11-07 (third review): the slider
   panel and the single-peak comparison plots are liked, and a full-pattern mode is wanted too.
4. **Preview modes occupy the graphs, and each graph says what it shows.** Ruled 2026-11-07
   (fourth review): a title on the graphs says what the view shows, so a preview never looks
   like a changed fit. The prototype's title reads "Preview, not refined", then "Rwp x %,
   last fit y %".
5. **The comparison scale is fixed at the last fit.** Ruled 2026-11-07 (fourth review): "that's
   the logical expectation of someone trying to compare something". A preview that grows a
   peak runs off the top of its window rather than rescaling it.
6. **Non-linear slider scales, and a range-and-scale pop-up opened from the parameter name.**
   Ruled 2026-11-07 (third review): some sliders need non-linear scales, since ×0.5 to ×2 on a
   linear track left the left half tiny; the maintainer floated the pop-up from the name.
7. **Slider units live in the range pop-up only.** Ruled 2026-11-07 (fourth review). This
   reverses "units on the number side" for sliders alone.
8. **Slider numbers never switch format while dragging, and no text shifts to re-align.
   Clicking the number lets the person type a value.** Ruled 2026-11-07 (fourth review).
9. **Less text.** Ruled 2026-11-07 (fourth review): no captions and no readouts that restate
   the plot. The sixth review added that no explanation is a permanent line on the page; it
   lives in a tooltip or a help box.
10. **No click or drag moves the layout.** Ruled 2026-11-07 (third review), naming slider drags
    among the gestures that must move nothing; adopted as interaction rule 8 on 2026-11-08.
11. **The panel ends in Apply and Apply and refine.** Ruled 2026-11-07 (fourth review), and
    built by WP-2123 as the action bar. The slider values join its pending edits.

The prototype's slider defaults, which the maintainer saw and did not change, set each range
from the last fit: a scale ×0.5 to ×2 on a logarithmic track; a zero shift ±2 FWHM of the
widest window peak; a cell length the relative change that moves the highest-angle peak by 2
FWHM; a width term from half to double the peak width; the axial S/L and H/L from 0 to 3×
their value, or to 0.05 when that is smaller. The mark on each track is the last fit, and ↺
returns a slider to it. The peak windows are the strongest reflection in each of twelve equal
2θ bins, three on screen, each stepped by ‹ and ›.

### What exists

- `POST /api/preview` (WP-2125) answers the calculated curve, the background, each phase and
  the ticks at values nobody has applied, with their Rwp, in 2.1-15.7 ms on the shipped
  examples when the compile stays frozen. It answers every fitted channel; the curves route
  decimates past `CURVES_CEILING` (150 000), and WP-2125 left the preview's side of that to
  this piece.
- The action bar (WP-2123, `panels/ActionBar.svelte`) counts the Parameters panel's pending
  edits and applies them; the shell (`App.svelte`) owns the refine.
- The pattern figure (`lib/pattern.ts`, `rxplot.pattern`) draws a curves payload and lays
  this panel's layers over it.

### Seams with the pieces in flight

The Parameters panel (WP-2126) and the Plan tab (WP-2127) are open branches. This WP touches
neither panel. Its edits to shared files are one tab in `lib/tabs.ts`, a few lines of
`App.svelte` that sum the pending counts, and no rule in `app.css`.

### Calls settled by Claude

No ruling covers these. Each took the smallest neutral option, is reversible, and waits for
the maintainer's review of the PR. Grounds are written where a rule settled it.

Most important first.

1. **Preview colours.** Settled by Claude, reversible: the preview is drawn solid and the last
   fit dashed, both in the model's ink (`--plot-calc`). Grounds: `gui/CLAUDE.md` § The peak
   layer, "state rides on the mark, not on a second colour", and WP-1210 measured that the
   plot palette has no free hue left. Alternative: the prototype's accent preview over a grey
   last fit.
2. **Default slider ranges.** Settled by Claude, reversible: displacement ±0.1 mm; a Gaussian
   width term ×¼ to ×4 and a Lorentzian one ×½ to ×2 on a logarithmic track, both meaning half
   to double the peak width; a term at zero linear over one peak width (G² or G). Grounds:
   the prototype's ±2 FWHM rule for position terms, carried to widths. Alternative: the
   prototype's even span in width units, or a displacement range from the goniometer radius.
3. **Graph tab name.** Settled by Claude, reversible: `Single peaks`. The panel corpus is keyed
   by label, so `Peaks` would collide with the side strip's tab. Alternative: `Peak windows`.
4. **Apply order.** Settled by Claude, reversible: the action bar applies the Parameters edits
   first and the sliders second, as two history nodes, so a slider wins on a path both
   touched. Alternative: one merged `set_values` node.
5. **Parameters edits are not in the preview.** Settled by Claude, reversible: the sliders
   start from the head's values. Grounds: that panel is WP-2126's (§ Non-goals).
   Alternative: send the Parameters panel's pending values with every preview request.
6. **Windows.** Settled by Claude, reversible: twelve equal 2θ bins, the strongest reflection
   in each by the last fit's net height, three shown (bins 1, n/2 and n−2), each ±5 FWHM, y
   from zero to a tenth above the last fit. Alternative: windows chosen by the person only.
7. **Decimation.** Settled by Claude: the server sends every channel the next fit would fit,
   and the client draws the preview on the curves payload's own channels, found by equal 2θ.
   Grounds: `gui/CLAUDE.md`, "which points a payload carries is the server's". Alternative:
   the route decimates to the same index itself.
8. **The route sends the residuals.** Settled by Claude: `POST /api/preview` now also answers
   `delta`, `delta_raw` and `cumulative_chi2`. Grounds: the curves route's rule that
   `cumulative_chi2` cannot be built in a client. Alternative: the residual pane keeps the last
   fit's residual under a preview.
9. **Slider edits survive a head move.** Settled by Claude, reversible: a value equal to the
   new head's is dropped, and a range nobody set is rebased on the new value. Alternative:
   every head move clears the sliders.
10. **The residual pane and the hover readout during a preview.** Settled by Claude,
    reversible: the residual pane keeps the last fit's y range, and the readout strip still
    reads the last fit. Alternative: both follow the preview.
11. **Families.** Settled by Claude, reversible: no slider for atoms, occupancies, Biso, cell
    angles or the background (§ Non-goals). A cell length's slider is named by its edge
    (`Lattice parameter a`), because the help corpus has one entry for a, b and c.
12. **Scale choices.** Settled by Claude, reversible: the pop-up offers `Linear` and
    `Logarithmic` only. Alternative: a square-root track for width terms.

## Non-goals

- The Background tab and its matrices route: piece 5.
- The single-peak comparison against the current shape of one reflection: it needs
  per-reflection curves, which the preview route does not serve (WP-2125 § Non-goals).
- The Parameters panel's own pending edits drawn in the preview: that panel is WP-2126's.
- A slider for an atom position, an occupancy, a Biso, a cell angle or a background term.

## Tasks

- [x] `POST /api/preview` also answers the three residuals the curves route sends, so the
  residual pane under a preview reads the server's numbers
- [x] `lib/interactive.ts`: the slider set from the parameter rows, the default ranges, the
  linear and logarithmic tracks, one number format per slider, and the request throttle
  (one request in flight, the newest values sent next, a stale answer dropped)
- [x] `panels/Interactive.svelte`: the tab, its sliders, the range-and-scale pop-up from the
  name, a typed value from the number, ↺ to the last fit
- [x] The action bar takes the slider values as pending edits: count, Apply, Revert, Apply and
  refine
- [x] The Pattern graph draws the preview over the whole pattern at the last fit's scale; the
  title line says "Preview, not refined" with both Rwp values
- [x] The Single peaks graph tab: three windows at the last fit's scale, stepped by ‹ and ›,
  each with the data, the last fit, the preview and its residual
- [x] Above `CURVES_CEILING` channels the preview is drawn on the curves payload's own channels
- [x] Vitest for the logic; the layout browser test drags a slider and types a value with real
  input, and measures drag-to-redraw latency; dist rebuilt
- [x] Manual: the Interactive tab and the Single peaks tab in the GUI chapters; screenshots
- [x] Skill: none expected. The agent skill drives the python API, and an agent with a shell
  calls `Refinement` directly

## Acceptance

```sh
npm --prefix gui ci && npm --prefix gui run build
npm --prefix gui test && npm --prefix gui run check
.venv/bin/python -m pytest tests/test_gui_layout_browser.py tests/test_gui_preview.py tests/test_gui_manual.py tests/test_gui_dist.py
.venv/bin/python -m pytest -n auto --dist loadgroup -m "not slow"
.venv/bin/python -m ruff check src tests examples
```

The layout test reports no movement for a slider drag, a typed slider value, an opened
pop-up or a stepped peak window, and quotes the drag-to-redraw latency as a range.

## References

- The maintainer's rulings of 2026-11-06 to 2026-11-08, restated above with their dates.
- Google, web.dev, "Measure performance with the RAIL model": the 16.7 ms frame and 100 ms
  response budgets WP-2125 measured the route against.

## Handover log

- **2026-11-09** — the Interactive tab and both previews landed, and the WP closes. A person can
  now drag a scale, a cell length, a zero shift or a width term and watch the pattern move
  before anything is committed: the title line says `Preview, not refined` beside both Rwp
  values, and the action bar's Apply writes the values as an ordinary edit. A second graph tab,
  Single peaks, shows three reflections at the last fit's scale, so a change in one peak's shape
  is visible rather than averaged over the pattern. Twelve presentation calls had no ruling and
  were settled as the smallest neutral option; they are listed under § Calls settled by Claude
  for the maintainer's review. The Background tab stays piece 5.

  *Done.* The route answers `delta`, `delta_raw` and `cumulative_chi2` (the curves route's three
  residuals, item 1). `lib/interactive.ts` holds the slider set, the default ranges, the tracks,
  the fixed number format and `PreviewQueue` (one request in flight, the newest values next, an
  answer to reverted values dropped). `panels/Interactive.svelte` is the tab; the range-and-scale
  pop-up opens from the name and a typed value from the number. `lib/pattern.ts:setPreview`
  draws the preview over the last fit on the curves payload's own channels (`channelIndex`, by
  equal 2θ), keeping every y range. `lib/peakwin.ts` and `panels/PeakWindows.svelte` are the
  Single peaks graph. `App.svelte` sums both panels' pending counts and applies Parameters
  first, sliders second. Manual: `reference/gui-guide.md` § Single peaks and § Interactive, the
  quickstart's tab table, two new screenshot pairs (`interactive`, `single-peaks`) and every
  other pair regenerated, since the strip gained a tab.

  *Measured* (arm64 macOS, worktree venv `[dev]`, no other suite running). Drag to redraw in
  chromium, real pointer, synthetic layout pattern: 32-38 ms wide, 32-36 ms stacked, 25 redraws
  a run, from the value change to the second frame after paint (`rx-preview-redraw` User
  Timing). vitest 637 passed (was 612: +25). svelte-check 0 errors. Layout browser test 14
  passed (was 12: +2, the new test at both widths). Fast suite 14506 passed, 410 skipped, 32 xfailed through ghostshift's serial queue (run before the review's fixes, which touched TypeScript only; the dist, layout and manual files were re-run after them: 39 passed, drag to redraw 32-44 ms). ruff clean. sphinx `-W`
  clean. `tests.reader_output` exit 0, unchanged against the merge-base.

  *Gotchas.* In a mac text field `End` is a scroll key: a browser test pressing it scrolled the
  panel 47 px with the caret unmoved, which read as a layout move. Use `ArrowRight`. The chart
  module must stay off the boot path, so the panel imports `rxplot` dynamically for `unpack`; a
  static import was flagged by vite's `INEFFECTIVE_DYNAMIC_IMPORT` warning before any test.
  The panel corpus is keyed by label, which is why the graph tab is `Single peaks`.

  *Code review.* `/code-review high --fix` found nine and fixed eight, in one commit: a shorter window list indexed with the last fit's picks (a render crash), `firstPicks(4)` repeating a window, the residual strip rescaling to the preview, magnetic and extra tick rows shifting the slider groups, a range past the row's bounds accepted, NaN in a picked cumulative χ², `setPreview` dropping `keep`, and redraw timings accumulating. Declined: out-of-order parameter loads, which `Params.svelte` shares and WP-2126 owns; and computing the windows once in `App`, cheap as it is.

  *Generality.* No row added to `rietx._audit`, and nothing in `src/rietx` decides for a caller.
  The slider ranges and window choices are GUI view defaults in TypeScript that change no
  answer, so the judge was not dispatched.

  Next: the maintainer reviews the twelve calls in § Calls settled by Claude; a reversal is a
  `lib/interactive.ts` or `lib/peakwin.ts` constant. The PR, #1487, stacks on #1476 and #1479 and
  merges after both. The Parameters panel's pending edits in the preview wait for WP-2126 to land.

- **2026-11-09** — filed by a ghostshift runner as the client half of piece 4. No open WP
  owns it: WP-2125 built the route and named this as its next piece, and the milestone record
  lists piece 4's client half as not yet filed. The branch starts from WP-2123's branch with
  WP-2125's merged in, since neither PR has merged.
