# WP-2200 — The palette

Milestone: gui-overhaul · Status: 🔄 2026-11-10 — built, PR #1517; the six colour questions ruled 2026-11-10
Depends on: 2142 (the style guide)
Priority: P2 2026-11-10 — a gui-overhaul piece the maintainer ruled for on 2026-11-06 and 2026-11-09; the peak-mark colour waits on it

## Goal

The GUI's default theme is the site's palette, light and dark: warm neutrals, the orange
accent, an orange calculated curve and a grey difference curve. The plot palette is
re-measured against WP-1210's floor under it, the picked-peak marks take the ruled blue, and
`rietx watch` and `rietx compare` change with it. Named themes (Solarized, Monokai) have a
seam in the emitter and are not built.

## Context

### The rulings this rests on

- **2026-11-06 (Yue):** the website and the manual are the reference for the new visual
  language. "One default theme consistent with the site, other elements recoloured to fit",
  plus a range of established themes (Solarized light and dark, Monokai) through theme
  machinery. Filled buttons: one filled primary per view, in the accent's text role
  (`#a34c06` on the light theme) with white ink, 5.84:1. Every other button is outlined, as
  on the site.
- **2026-11-07, round 4 (Yue):** the pattern follows rietx's plot conventions in the GUI's
  colours. Observed points are clearly visible.
- **2026-11-08, rounds 11b and 11c (Yue):** peak marks read in the high-angle peak forest,
  in a more eye-catching colour than the thin bars. The workshop drew them in Okabe-Ito blue,
  `#0072B2` light and `#56B4E9` dark, chosen as the complement of the orange fits.
- **2026-11-09 (Yue, on WP-2130's brief):** "I am not liking the colours. what happened to
  the colours I chose in the workshop?" The site theme had no port piece; the mark colour
  moves with this one (WP-2130 § Rulings of 2026-11-09).
- **2026-11-09 (Yue, on the style-guide batch):** "build the main themes first then e.g
  solarized. theme should be in settings." Light and dark come first and named themes later.
  Settings offers Match system (the default), Light and Dark (B2). B4: selection is shown by
  shape, red marks only an unexplained peak, and orange is the fit's alone.

`gui/STYLE.md` § Colour states these as rules; this WP is the piece its paragraph names.

### Rulings of 2026-11-10, on the six visual questions

Ruled by Yue 2026-11-10, on the handover's six open questions and the PR's screenshots.
Every value stays as built.

1. The background stays the figures' brown, `#b5793a` light and `#c99a6a` dark. The dash
   separates it from the calculated curve.
2. The peak-fit curve stays the second blue, `#6f83e6` light and `#516494` dark.
3. The dark peak mark stays `#008ad5`. The ruled `#56b4e9` equals the third phase colour.
4. The zero line stays the site's zero grey.
5. On the light theme the difference grey may share `--muted` with the excluded region's
   edge.
6. The outlined-button rule stands. The clutter it shows goes to a new graph-window piece,
   filed on 2026-11-10.

### The site's palette, and the prototype's plot roles

The site's tokens are `docs/landing/src/tokens.css` (WP-2021). The GUI's nine chrome tokens
take the site's values for the same job: `--fg` is the site's `--ink`, `--panel` its
`--surface`, `--line` its `--rule`, `--bad` its `--danger`; `--bg`, `--muted`, `--accent`,
`--ok` and `--warn` keep their names. The design rounds drew the pattern with the observed
points in ink, the calculated curve in the accent, the background dashed in the figures'
brown (`viz/plots.PALETTES`, `#b5793a` light, `#c99a6a` dark), the difference in the site's
muted grey, and a single phase's ticks in the observed ink.

### Measured before filing (2026-11-10, `structure3d._oklab_distance`)

With the site's chrome and the prototype's plot roles in place:

- The ruled dark peak blue `#56b4e9` **is** `--phase-2`, distance 0.000, and fails
  `test_no_phase_colour_comes_closer_to_a_curve_than_the_recorded_number`. The light value
  `#0072b2` clears every curve (0.187 from the nearest phase). The nearest blue to the ruled
  dark value that clears 0.13 against every curve, `--muted`, `--fg` and every phase colour,
  0.30 against the page, is `#008ad5`: the ruled light hue, lifted for the dark ground.
- The prototype draws the picked peaks' fitted curve in the accent. In the GUI that curve
  shares the pattern pane with the calculated curve, so it cannot be the same orange
  (WP-1210's floor; principle 9, the rule wins over the mockup). The peak layer keeps one hue
  in two tones (`viz/theme.py`'s note): the fit takes a second blue, `#6f83e6` light and
  `#516494` dark, each the nearest to a step of the marks' tone that clears the same set.
  The dark one was first `#2e5e9a`, which cleared every floor at 2.67:1 on the panel;
  `#516494` is the nearest that also clears WCAG's 3:1 for graphics (3.02:1). Every curve
  is now held to 3:1 on both grounds.
- The background brown sits 0.065 from the orange calculated curve on the light theme and
  0.092 on the dark, and 0.110 from the dark difference grey. The dash carries its identity,
  as the point marks do for the greys WP-1210 exempted. These three pairs are named in the
  test and held to their measured value, as WP-1210 named its two.
- White on the orange accent is 4.22:1, under AA. Ink on the accent's text role is 5.84:1
  light and 10.25:1 dark. So the filled primary takes `--accent-ink`, and any text set in the
  accent takes `--accent-ink` too.
- Text on its grounds (bg / panel): `--fg` 16.8 / 17.5, `--muted` 5.72 / 5.97,
  `--accent-ink` 5.60 / 5.84, `--ok` 4.95 / 5.17, `--warn` 5.74 / 5.98, `--bad` 6.19 / 6.46
  on light; every dark pair is above 6.

### The pieces

- `src/rietx/viz/theme.py`: `TOKENS`, the notes, the emitter's seam for a named theme.
- `gui/src/tokens.css`: generated (`python -m rietx.viz.theme > gui/src/tokens.css`).
- `gui/src/app.css` and the panels that set text in `--accent`: the primary fill, the
  outlined button, links and accent text in `--accent-ink`.
- `gui/src/lib/plot.ts`: the light fallbacks (pinned by `test_gui_palette.py`).
- `tests/test_gui_palette.py`: the named pairs, a text-contrast test, ink on the fill.
- `gui/STYLE.md` § Colour: the rules move from target to fact.
- `rietx watch` and `rietx compare` read `/tokens.css`, so they change with no edit.

### The tier of each rule this WP adds

None in rietx's analysis. Every value here is a colour; none is a threshold or an automatic
action on data.

## Non-goals

- Named themes (Solarized, Monokai) and the Settings dialog that lists them: a later piece.
  This WP leaves the seam in the emitter and builds no theme.
- The type faces (Instrument Sans, IBM Plex), sentence-case headings and the redrawn chips:
  their own pieces.
- The lens peak mark, selection by shape and the red unexplained mark: the Peaks redesign.
- The figure palette (`viz/plots.PALETTES`), `viz/figure3d/scene.py`'s cell ink and
  `rietx compare`'s ten variant hues: figure surfaces, outside the theme (WP-1429).

## Tasks

- [x] 1. `theme.py`: the site's chrome, the new roles the GUI reads (`--accent-ink`,
  `--line-strong`, `--hover`), the re-measured plot palette, the notes rewritten; the
  emitter loops over the themes `TOKENS` holds, with the colour scheme each declares.
  Regenerate `tokens.css`.
- [x] 2. `app.css` and the panels: the primary fill and an engaged toggle in
  `--accent-ink` under `--panel` ink; the outlined button in `--line-strong` with `--fg`
  text and the `--hover` ground; every text set in `--accent` moved to `--accent-ink`.
- [x] 3. `plot.ts` fallbacks and the vitest fixtures pinning them; the `Structure3D.svelte`
  fallbacks.
- [x] 4. `test_gui_palette.py`: the named pairs with their measured values; every text
  colour against each ground; ink on the primary fill.
- [x] 5. `gui/STYLE.md` § Colour states what now holds.
- [x] 6. Dist rebuilt; vitest, svelte-check, every `tests/*_browser.py`, the fast suite,
  `python -m tests.reader_output`.
- [x] 7. Screenshots of the built GUI beside the prototype's at the same window size, light
  and dark, in the PR (acceptance rows 4, 11 and 12).

## Acceptance

`.venv/bin/python -m pytest tests/test_gui_palette.py tests/test_gui_style_guide.py
tests/test_gui_dist.py` green; `npm --prefix gui test && npm --prefix gui run check` green;
the screenshots in the PR; the maintainer's look before merge (milestone row 10).

## Handover log
- **2026-11-11** — rulings applied, PR #1517. Main was merged in at c5fe8cf38; the one
  conflict was the milestone's piece table, and both rows stand. Yue's rulings of 2026-11-10
  on the six colour questions are in § Rulings of 2026-11-10. Every value stays as built.

  *Fixed.* Zoomed into a peak on the Peaks tab, the dashed peak fit ran left of the y axis
  into its gutter. uPlot clips its own series to the plot area and leaves a hook's strokes
  alone. So every hook a pattern pane runs now draws through `rxplot.clipped`, one seam in
  `pattern()`. That covers the peak fit, the peak marks and their whiskers, the preview
  lines, candidate lines, region shading, tick rows and the zero line, on every page that
  draws a pattern (GUI, `rietx watch`, `rietx compare`). The observed points, calculated
  curve, background and difference are uPlot series and were already clipped. The peak
  windows, the Background tab and the series trajectory already clipped their own
  drawings. The uPlot stub now records the clip in force on each stroke. The new vitest
  zooms so the zoom cuts a peak group, then asserts every non-series mark on all three panes
  carries its pane's clip; with the seam removed it fails. A browser probe on the FAP
  example at 25.76-26.72° counted the peak-fit colour in the gutter: 1123 device pixels
  before, 0 after.

  *Measured* (worktree `[dev]` venv plus playwright, macOS arm64). vitest 718 passed,
  svelte-check 0 errors, `node --test tests/rxplot.test.mjs` 19 passed. Every
  `tests/*_browser.py` with `test_gui_palette`, `test_watch_app`, `test_compare_ui` and
  `test_gui_dist`: 346 passed, 0 skipped. Fast suite through the serial lock: 14622 passed, 410 skipped, 32 xfailed,
  2 failed. `test_no_parameters_control_moves_the_layout[stacked]` passed alone; the suite
  ran at a load average near 26. `test_every_page_has_a_twin_that_keeps_the_contract` fails
  on an `origin/main` snapshot too: the `theory/estimation` twin is 50 048 characters, over
  its 50 000 cap. This branch changes no page, so that one is main's.
  `python -m tests.reader_output` exit 0, unchanged. ruff clean; Vale 0 errors, its
  warnings all on lines this branch did not write.

  Next: the maintainer merges. The graph window's clutter is its own piece, filed on
  2026-11-10.
- **2026-11-10** — built, PR #1517. The GUI now opens in the site's palette, light and
  dark: warm neutrals, an orange calculated curve, observed points in the ink, a grey
  difference. `rietx watch` and `rietx compare` read the same stylesheet and changed with it.
  The filled primary button now carries legible ink (5.84:1), where white on the orange
  would have been 4.22:1. Six colour choices that no rule settled went to the choice nearest
  the prototype. They wait on the maintainer's look before merge (milestone row 10).

  *Done.* Tasks 1-7. The emitter writes one block per scheme in `theme.SCHEMES`. A named
  theme is an entry there plus its `TOKENS` arm. The review pictures are in
  `2200-screenshots/`, and the manual's GUI screenshots were retaken.

  *Measured* (worktree `[dev]` venv, macOS arm64). vitest 717 passed, svelte-check 0 errors.
  `test_gui_palette`, `test_gui_style_guide` and `test_docs_consistency`: 64 passed. The
  GUI-adjacent files (`test_gui_dist`, `test_watch_app`, `test_compare_ui`,
  `test_gui_manual`, `test_gui_server`): 352 passed. Every `tests/*_browser.py`: 152 passed,
  0 failed (40 + 18 + 94 over three runs). After the review's fixes, `test_compare_browser`
  and `test_watch_browser` passed again, 59. `python -m tests.reader_output` exit 0,
  unchanged. Fast suite on the tree merged with main at e0405b2d6, through the serial lock: 14624
  passed, 410 skipped, 32 xfailed. The branch adds five test functions (nine cases), all in
  `test_gui_palette.py`, 0.04 s together; it removed the grandfathered-pairs test for the
  named-pairs one. No baseline was run for the exact delta.

  *Review* (`/code-review high --fix`, nine findings). Fixed: `rietx watch` and `rietx
  compare` still set links, a pill, `code` and their filled buttons in `--accent`. On the
  light theme that is under AA (4.05:1 and 4.22:1), and white on the dark orange is 2.06:1.
  They now take `--accent-ink`, and a test reads every page's stylesheet for the accent as
  text or fill. The dark peak fit `#2e5e9a` was 2.67:1 on the panel. It is now `#516494`
  (3.02:1), and a test holds every curve to 3:1. `test_compare_ui` no longer allows `#fff`.
  Stale comments were fixed. Declined: the watcher's state pills set text in a state colour
  over an 18 % wash of it (`.running` 3.90:1, `.cancelled` 4.45:1 on light). Changing the
  wash is a pill design call outside the token swap. Questions 2 and 5 below hold the other
  two findings.

  *Open visual questions for the maintainer.* Each is one value in `viz/theme.py` to change.
  The pictures are `2200-screenshots/gui-*.png` beside `prototype-*.png`.
  1. The background is the figures' brown, `#b5793a` light and `#c99a6a` dark, as the
     prototype drew it. It sits under WP-1210's 0.13 floor from the orange calculated curve
     (0.065 light, 0.092 dark) and from the dark difference grey (0.110). The dash tells it
     apart. Alternatives that clear the floor: olive `#a19258` light; `#b2a92a` or
     `#cd7700` dark.
  2. The picked peaks' fitted curve is a second blue, `#6f83e6` light and `#516494` dark.
     The prototype draws it orange, but in the GUI it shares the pane with the orange
     calculated curve, and STYLE.md principle 9 puts the rule over the mockup. The
     alternative is today's magenta.
  3. The dark peak mark is `#008ad5`. The ruled `#56b4e9` is exactly `--phase-2`, distance
     0.000. `#008ad5` is the light mark's hue, lifted for the dark ground.
  4. The zero line takes the site's zero grey (`#cfcfcf` / `#4a4a4a`). The prototype draws
     it in its rule colour.
  5. On the light theme the difference curve is `--muted` exactly, as in the prototype. The
     grey was shared twice. The series trajectory's forward chain wore it, and now wears the
     observed ink. The dotted edge of an excluded region still wears it.
  6. Every non-primary button is outlined in `--line-strong` with ink text, from the
     2026-11-06 ruling. The look is unconfirmed.

  *Gotchas.* A Bash hook here refuses `cd` and a sed operand computed at runtime. The
  prototype's peak marks appear only in its "Peaks and indexing" workflow, which no URL
  parameter reaches: click through the workflow menu, then "Pick peaks".

  Next: the maintainer looks at the six questions and the screenshots. Then the named-theme
  piece builds Solarized and Monokai on `SCHEMES`, and Settings lists them.
- **2026-11-10** — created. No open WP owns the palette: the milestone lists it under "Designed, not yet filed", and WP-2130 deferred the peak-mark colour to it by the ruling of 2026-11-09. Numbered in the milestone's 22xx block by the shift lead.
