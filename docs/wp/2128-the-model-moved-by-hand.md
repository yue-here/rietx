# WP-2128 — the model moved by hand: the Interactive tab and the previews

Milestone: gui-overhaul · Status: 🔄 2026-11-09 — filed; the checklist starts
Depends on: 2123 (the shell the previews draw in); 2125 (the preview route)
Priority: P2 2026-11-09 — piece 4's client half of the open gui-overhaul milestone

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

(filled as the checklist lands)

## Non-goals

- The Background tab and its matrices route: piece 5.
- The single-peak comparison against the current shape of one reflection: it needs
  per-reflection curves, which the preview route does not serve (WP-2125 § Non-goals).
- The Parameters panel's own pending edits drawn in the preview: that panel is WP-2126's.
- A slider for an atom position, an occupancy, a Biso, a cell angle or a background term.

## Tasks

- [ ] `POST /api/preview` also answers the three residuals the curves route sends, so the
  residual pane under a preview reads the server's numbers
- [ ] `lib/interactive.ts`: the slider set from the parameter rows, the default ranges, the
  linear and logarithmic tracks, one number format per slider, and the request throttle
  (one request in flight, the newest values sent next, a stale answer dropped)
- [ ] `panels/Interactive.svelte`: the tab, its sliders, the range-and-scale pop-up from the
  name, a typed value from the number, ↺ to the last fit
- [ ] The action bar takes the slider values as pending edits: count, Apply, Revert, Apply and
  refine
- [ ] The Pattern graph draws the preview over the whole pattern at the last fit's scale; the
  title line says "Preview, not refined" with both Rwp values
- [ ] The Single peaks graph tab: three windows at the last fit's scale, stepped by ‹ and ›,
  each with the data, the last fit, the preview and its residual
- [ ] Above `CURVES_CEILING` channels the preview is drawn on the curves payload's own channels
- [ ] Vitest for the logic; the layout browser test drags a slider and types a value with real
  input, and measures drag-to-redraw latency; dist rebuilt
- [ ] Manual: the Interactive tab and the Single peaks tab in the GUI chapters; screenshots
- [ ] Skill: none expected. The agent skill drives the python API, and an agent with a shell
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

- **2026-11-09** — filed by a ghostshift runner as the client half of piece 4. No open WP
  owns it: WP-2125 built the route and named this as its next piece, and the milestone record
  lists piece 4's client half as not yet filed. The branch starts from WP-2123's branch with
  WP-2125's merged in, since neither PR has merged.
